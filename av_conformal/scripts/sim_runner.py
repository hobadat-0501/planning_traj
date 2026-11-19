"""Chạy một lượt khóa bước (hướng dẫn §7.1).

Thứ tự trong một bước (CỐ ĐỊNH, không đảo):
 1. gửi lệnh (đã qua bộ đệm trễ) -> 2. tác nhân cập nhật -> 3. tick -> 4. đo có nhiễu ->
 5. lập kế hoạch (10 Hz) -> 6. bộ bám + bộ chuyển lệnh tính lệnh cho bước sau."""
from __future__ import annotations

import time
import traceback
from pathlib import Path

import numpy as np

from ..av_core.actuation import Control, TeslaActuator
from ..av_core.calibrator import make_calibrator
from ..av_core.config import load_cfg
from ..av_core.evaluator import DelayedEvaluator
from ..av_core.geometry import poly_distance, rect_polygon
from ..av_core.logger import EpisodeLogger, cfg_hash
from ..av_core.noise import Condition, LocalizationNoise
from ..av_core.planner import FrenetPlanner
from ..av_core.predictor import ConstantVelocityPredictor
from ..av_core.tracker import pure_pursuit
from ..carla_env.scenarios import Route, build_scenario


def make_backend(kind, cfg, seed, args=None):
    """Trả về (backend, route). kind: 'fake' hoặc 'carla'."""
    veh, run = cfg["vehicle"], cfg["run"]
    if kind == "fake":
        from ..carla_env.fake import FakeBackend
        route = Route.straight(cfg["scenarios"]["route_length"])
        return FakeBackend(veh, route, run["dt"], seed), route
    if kind == "carla":
        from ..carla_env.backend import CarlaBackend
        a = args or {}
        be = CarlaBackend(veh, a.get("host", run["host"]), a.get("port", run["port"]),
                          a.get("tm_port", run["tm_port"]), cfg["scenarios"]["town"], run["dt"], seed,
                          cfg["scenarios"]["route_length"], a.get("no_rendering", True))
        return be, be.route
    raise ValueError(kind)


def _min_dist(ego_pose, ego_dims, truth, dims):
    if not truth:
        return np.inf
    el, ew, eo = ego_dims
    poly = rect_polygon(*ego_pose, el, ew, eo)
    best = np.inf
    for aid, p in truth.items():
        if np.hypot(p[0] - ego_pose[0], p[1] - ego_pose[1]) > 12.0:
            continue
        best = min(best, poly_distance(poly, rect_polygon(*p, dims[aid][0], dims[aid][1], dims[aid][0] / 2)))
    return best


def run_episode(cfg, seed, method, scenario, condition, out_dir, backend="fake", q_table=None,
                sigma_tau=None, exp="exp", backend_args=None, T_max=None, log_steps=True, fmt="csv"):
    run, veh = cfg["run"], cfg["vehicle"]
    dt, H, dtp = run["dt"], run["H"], run["dt_plan"]
    T_max = run["T_max"] if T_max is None else T_max
    ss = np.random.SeedSequence([int(seed), 7])
    r_scn, r_noise, r_cond = (np.random.default_rng(s) for s in ss.spawn(3))
    run_id = f"{exp}_{scenario}_{condition}_{method}_{seed}"
    sigma = np.ones(H) if sigma_tau is None else np.asarray(sigma_tau, dtype=float)
    meta = dict(seed=seed, method=method, scenario=scenario, condition=condition, exp=exp, backend=backend,
                cfg_hash=cfg_hash(cfg), carla_version=None, sigma_tau_is_one=bool(np.all(sigma == 1.0)))
    logger = EpisodeLogger(out_dir, run_id, meta, fmt=fmt)
    be = None
    status, err = "timeout", None
    plan_ms: list[float] = []
    d_min_ep, n_fallback = np.inf, 0
    try:
        be, route = make_backend(backend, cfg, seed, backend_args)
        if backend == "carla":
            logger.meta["carla_version"] = str(be.sim.versions())
        agents = build_scenario(scenario, route, cfg, r_scn)
        if backend == "carla":
            be.bind_agents(agents, r_scn)
        dims = {a.id: a.dims for a in agents}
        ego_dims = (veh["length"], veh["width"], veh["rear_overhang"])

        act = TeslaActuator(veh, dt)
        cond = Condition(condition, cfg["conditions"][condition], r_cond)
        act.set_delay(cond.fixed_delay)
        noise = LocalizationNoise(cfg["noise"], r_noise)
        v_sigma = cond.speed_sigma(cfg["noise"])
        predictor = ConstantVelocityPredictor(H, dtp)
        planner = FrenetPlanner(veh, route, H=H, dt=dtp, d_s=run["d_s"])
        calib = make_calibrator(method, q_table)
        evalr = DelayedEvaluator(H, ego_dims, sigma, run["d_s"])

        ctrl = Control(brake=1.0)
        x_true = be.ego_state()
        plan = None
        delta_cmd_last = 0.0
        for k in range(int(T_max / dt)):
            t = k * dt
            be.apply(ctrl)                                              # 1
            for a in agents:                                            # 2
                a.step(x_true[:2], t, dt)
            be.sync_agents(agents)
            be.tick()                                                   # 3
            x_true = be.ego_state()
            rtk = cond.rtk_at(t)                                        # 4
            e = noise.sample(rtk, x_true[3], x_true[2], dt)
            x_est = x_true.copy()
            x_est[:3] += e
            x_est[3] = max(0.0, x_true[3] * (1.0 + v_sigma * r_noise.standard_normal())) if v_sigma else x_true[3]
            x_est[4] = delta_cmd_last
            truth = {a.id: a.pose() for a in agents if a.visible(x_true[:2])}
            if k % 2 == 0:                                              # 5
                t0 = time.perf_counter()
                act.set_delay(cond.delay_for_cycle()) if cond.random_delay else None
                for res in evalr.add_truth(x_true[:3], truth):
                    logger.write(res)
                    calib.feedback(res)
                predictor.update(truth, t)
                preds = predictor(dims)
                q = calib.q(group=rtk, t=t)
                plan = planner.plan(x_est, preds, sigma * q)
                n_fallback += int(plan.fallback)
                evalr.add_plan(t, plan.poses_H, preds, meta=dict(
                    group=rtk, q_used=q, fallback=int(plan.fallback), n_agents=len(preds),
                    scenario=scenario, condition=condition, method=method, seed=seed))
                plan_ms.append((time.perf_counter() - t0) * 1e3)
            if plan is None:
                v_cmd, d_cmd = 0.0, 0.0
            else:                                                       # 6
                v_cmd, d_cmd = pure_pursuit(x_est, plan.path_xy, plan.path_v, veh["L"], dmax=veh["delta_max"])
            ctrl = act(x_est[3], v_cmd, d_cmd)
            delta_cmd_last = float(np.clip(ctrl.steer, -1, 1) / veh["steer_gain"])
            dm = _min_dist(x_true[:3], ego_dims, truth, dims)
            d_min_ep = min(d_min_ep, dm)
            if log_steps:
                logger.step(t=t, x=x_true[0], y=x_true[1], psi=x_true[2], v=x_true[3],
                            x_est=x_est[0], y_est=x_est[1], psi_est=x_est[2], v_cmd=v_cmd, d_cmd=d_cmd,
                            throttle=ctrl.throttle, steer=ctrl.steer, brake=ctrl.brake, rtk=rtk,
                            d_min=dm if np.isfinite(dm) else -1.0)
            if dm <= 0.0:
                status = "collision"
                break
            if route.to_frenet(x_true[0], x_true[1])[0] >= route.length - 5.0:
                status = "goal"
                break
    except Exception as ex:   # lượt lỗi được đánh dấu, không xóa
        status, err = "error", f"{type(ex).__name__}: {ex}\n{traceback.format_exc()}"
    finally:
        try:
            if be is not None:
                be.close()
        finally:
            pm = np.asarray(plan_ms) if plan_ms else np.zeros(1)
            logger.close(status=status, error=err, d_min=None if not np.isfinite(d_min_ep) else float(d_min_ep),
                         n_fallback_cycles=n_fallback, plan_ms_median=float(np.median(pm)),
                         plan_ms_p95=float(np.percentile(pm, 95)), sim_time=float(len(logger.steps) * dt))
    return logger.meta


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="fake", choices=["fake", "carla"])
    ap.add_argument("--scenario", default="S1")
    ap.add_argument("--condition", default="D0")
    ap.add_argument("--method", default="B0")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="av_conformal/data/raw/single")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--tm-port", type=int, default=8000)
    a = ap.parse_args()
    m = run_episode(load_cfg(), a.seed, a.method, a.scenario, a.condition, Path(a.out), backend=a.backend,
                    backend_args=dict(host=a.host, port=a.port, tm_port=a.tm_port))
    print(json.dumps({k: m[k] for k in ("run_id", "status", "d_min", "plan_ms_p95", "sim_time")}, indent=1))
