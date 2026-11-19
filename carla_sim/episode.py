"""Chạy một lượt mô phỏng vòng kín trên CARLA (T16–T17 / G14–G15).

Ghi log đúng định dạng `EPISODE_FIELDS` và `CYCLE_FIELDS` để `sim.common.write_logs`
và `sim.analyze` đọc trực tiếp không cần sửa đổi.

Cũng cung cấp `FakeCarlaSession` (mô phỏng nhẹ không cần máy chủ CARLA) để kiểm thử
tự động toàn bộ cầu nối, tái lập hạt giống và định dạng log.
"""

from __future__ import annotations

import math
import time
from collections import deque
from typing import Any, Callable

import numpy as np

from carla_sim.agents import CarlaAgentManager
from carla_sim.config import CarlaConfig
from carla_sim.control import VehicleControlBridge
from carla_sim.frames import FrameTransform
from carla_sim.infra import CarlaSession, find_straight_spawn, spawn_ego
from carla_sim.perception import PerceptionPredictor
from sim.core import (
    ALL_CONDITIONS,
    ALL_SCENARIOS,
    A_MIN,
    DEFAULT_SIGMA_OLD,
    D_S,
    DT_SIM,
    GOAL_X,
    H_STEPS,
    HX,
    LANE_HALF_WIDTH,
    N_SIM_STEPS,
    PLAN_EVERY,
    T_MAX,
    XC_LOCAL,
    EgoPlant,
    LocalizationGenerator,
    PlanResult,
    _scalar_box_agent_dist,
    compute_cycle_metrics,
    plan_frenet,
    wrap_angle,
)


class FakeCarlaSession:
    """Phiên giả lập CARLA nhẹ dùng động học `EgoPlant` cho kiểm thử không có server CARLA."""

    def __init__(self, cfg: CarlaConfig) -> None:
        self.cfg = cfg
        self.world = None
        self.is_fake = True

    def __enter__(self) -> "FakeCarlaSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def close(self) -> None:
        return None

    def destroy_tracked_actors(self) -> None:
        return None


def _attach_collision_sensor(session: CarlaSession, ego: Any) -> tuple[Any, list[bool]]:
    """Gắn cảm biến va chạm lên xe tự hành trong CARLA thật."""
    import carla  # noqa: PLC0415

    flag = [False]
    bp = session.world.get_blueprint_library().find("sensor.other.collision")
    sensor = session.world.spawn_actor(bp, carla.Transform(), attach_to=ego)
    session.track_actor(sensor)

    def _on_col(_event: Any) -> None:
        flag[0] = True

    sensor.listen(_on_col)
    return sensor, flag


def run_carla_episode(
    session: CarlaSession | FakeCarlaSession,
    seed: int,
    scenario: str,
    condition: str,
    method: str,
    margin_fn: Callable[[str, float, int], tuple[float, np.ndarray]],
    sigma_tau: np.ndarray | None = None,
    cfg: CarlaConfig | None = None,
    feedback_fn: Callable[[dict[str, Any]], None] | None = None,
    v0: float = 7.0,
    seed_base: int = 0,
    *,
    split: str = "CARLA",
    d_s: float = D_S,
    lane_half_width: float = LANE_HALF_WIDTH,
    dense_v_grid: bool = False,
    keep_tau_arrays: bool = True,
    curve_radius_override: float | None = None,
) -> dict[str, Any]:
    """Chạy một lượt vòng kín trên CARLA (hoặc FakeCarlaSession) và trả về episode + cycles."""
    if cfg is None:
        cfg = CarlaConfig()
    if sigma_tau is None:
        sigma_tau = DEFAULT_SIGMA_OLD

    scn_idx = 99 if scenario == "S0" else ALL_SCENARIOS.index(scenario)
    cond_idx = ALL_CONDITIONS.index(condition)

    # Tách hạt giống hệt `sim.core.run_episode` để ghép cặp 1-1 với mô phỏng 2D
    ep_seed = int(seed) + int(seed_base) * 100000
    rng_scn = np.random.default_rng(ep_seed * 31 + scn_idx + 7)
    rng_loc = np.random.default_rng(ep_seed * 37 + cond_idx * 101 + 13)
    rng_obs = np.random.default_rng(ep_seed * 41 + 19)
    rng_ego = np.random.default_rng(ep_seed * 43 + 23)

    loc = LocalizationGenerator(condition, rng_loc)
    bridge = VehicleControlBridge(cfg, condition, rng_ego)
    agent_mgr = CarlaAgentManager(scenario, rng_scn, cfg, curve_radius_override=curve_radius_override)
    perc_pred = PerceptionPredictor(cfg)

    is_fake = bool(getattr(session, "is_fake", False)) or getattr(session, "world", None) is None
    ego_plant: EgoPlant | None = None
    ego_actor: Any = None
    frame: FrameTransform | None = None
    carla_col_flag = [False]

    if is_fake:
        ego_plant = EgoPlant(rng_ego, condition, v0=v0)
        frame = FrameTransform(x0=0.0, y0=0.0, psi0=0.0, z0=0.0)
    else:
        import carla  # noqa: PLC0415

        spawn_tf, frame = find_straight_spawn(session.world, cfg)
        # Gốc actor Model 3 ~ tâm hộp bao; dời tới XC_LOCAL để tâm cầu sau trùng gốc cục bộ (như EgoPlant px=0)
        ego_tf = frame.make_carla_transform(XC_LOCAL, 0.0, 0.0, z=spawn_tf.location.z)
        ego_actor, _ = spawn_ego(session, ego_tf, cfg, condition=condition)
        # Đặt vận tốc ban đầu v0 dọc trục x cục bộ
        vx0_w, vy0_w = frame.local_to_world_xy(v0, 0.0)
        x0_w, y0_w = frame.local_to_world_xy(0.0, 0.0)
        ego_actor.set_target_velocity(carla.Vector3D(x=vx0_w - x0_w, y=vy0_w - y0_w, z=0.0))
        _, carla_col_flag = _attach_collision_sensor(session, ego_actor)
        agent_mgr.spawn_in_carla(session, frame)
        session.tick()

    agents = agent_mgr.agents
    static_obs = agent_mgr.static_obs
    ref_path = agent_mgr.ref_path

    ego_poses_10hz: list[np.ndarray] = []
    agents_10hz: list[dict[str, tuple[np.ndarray, float]]] = []
    agents_obs_10hz: list[dict[str, tuple[float, float, float, float]]] = []
    pending_plans: deque[dict[str, Any]] = deque()
    finalized_cycles: list[dict[str, Any]] = []
    prev_preds_by_id: dict[str, dict[str, Any]] | None = {} if condition == "D10" else None

    collided = False
    completed = False
    unavoidable = 0
    t_end = T_MAX
    d_min_ep = float("inf")
    ttc_min_ep = float("inf")
    jerk_sq_sum = 0.0
    jerk_n = 0
    tcomp_samples: list[float] = []

    current_plan: PlanResult | None = None
    last_plan_t = 0.0
    extra_delay = 0.0
    prev_a = 0.0
    last_delta_eff = 0.0

    try:
        for k in range(N_SIM_STEPS + 1):
            t = round(k * DT_SIM, 4)

            # 1. Đọc tư thế thật của xe tự hành
            if is_fake:
                assert ego_plant is not None
                ego_px, ego_py, ego_psi = ego_plant.px, ego_plant.py, ego_plant.psi
                ego_v, ego_a, ego_delta = ego_plant.v, ego_plant.a, ego_plant.delta
            else:
                assert frame is not None
                ego_px, ego_py, ego_psi = frame.ego_rear_axle_pose(ego_actor)
                _, _, ego_v = frame.actor_velocity(ego_actor, ego_psi)
                ego_v = max(0.0, float(ego_v))
                ego_a = float(frame.actor_accel_long(ego_actor, ego_psi))
                ego_delta = last_delta_eff

            # 2. Cài sai số định vị D0–D5 (hoặc D6–D10) vào dữ liệu CARLA (T17)
            g_label, loc_err, ev_err = loc.step(t, ego_v, ego_psi, DT_SIM if k > 0 else 0.0)
            x_est = np.array([
                ego_px + loc_err[0],
                ego_py + loc_err[1],
                float(wrap_angle(ego_psi + loc_err[2])),
                max(0.0, ego_v + ev_err),
                ego_delta,
            ], dtype=float)

            ego_s = ref_path.project_s(ego_px, ego_py) if ref_path is not None else ego_px

            if k % PLAN_EVERY == 0:
                ego_poses_10hz.append(np.array([ego_px, ego_py, ego_psi], dtype=float))
                ag_snap: dict[str, tuple[np.ndarray, float]] = {}
                ag_snap_full: dict[str, tuple[float, float, float, float]] = {}
                for ag in agents:
                    ag_snap[ag.id] = (np.array([ag.px, ag.py], dtype=float), ag.psi)
                    ag_snap_full[ag.id] = ag.pose_vel()
                agents_10hz.append(ag_snap)
                agents_obs_10hz.append(ag_snap_full)

                cur_10hz_idx = len(ego_poses_10hz) - 1
                while pending_plans and (cur_10hz_idx - pending_plans[0]["idx_10hz"]) == H_STEPS:
                    rec = pending_plans.popleft()
                    i0 = rec["idx_10hz"]
                    true_ego_seq = np.array(ego_poses_10hz[i0 + 1 : i0 + 1 + H_STEPS], dtype=float)
                    true_ag_traj: dict[str, tuple[np.ndarray, np.ndarray]] = {}
                    for ag in rec["pred_agents"]:
                        aid = ag["id"]
                        cs = np.array([agents_10hz[m][aid][0] for m in range(i0 + 1, i0 + 1 + H_STEPS)], dtype=float)
                        ys = np.array([agents_10hz[m][aid][1] for m in range(i0 + 1, i0 + 1 + H_STEPS)], dtype=float)
                        true_ag_traj[aid] = (cs, ys)

                    stats = compute_cycle_metrics(
                        rec["plan_poses"],
                        true_ego_seq,
                        rec["pred_agents"],
                        true_ag_traj,
                        sigma_tau,
                    )
                    if d_s != D_S and stats["has_agents"]:
                        stats["safe"] = bool(stats["d_min"] >= d_s)

                    q_used = rec["q_used"]
                    covered_score = bool(stats["R"] <= q_used)
                    cyc: dict[str, Any] = {
                        "method": method,
                        "seed": int(seed),
                        "scn": scenario,
                        "cond": condition,
                        "split": split,
                        "t": rec["t"],
                        "g": rec["g"],
                        "J": rec["J"],
                        "fallback": int(rec["fallback"]),
                        "q": float(q_used),
                        "m_max": float(rec["m_3s"]),
                        "gap_max": float(stats["gap_max"]),
                        "d_min": float(stats["d_min"]),
                        "covered": int(covered_score),
                        "safe": int(stats["safe"]),
                        "has_agents": int(stats["has_agents"]),
                        "R": float(stats["R"]),
                        "A_c_max": float(stats["A_c_max"]),
                        "A_h_max": float(stats["A_h_max"]),
                        "E_max_norm": float(stats["E_max_norm"]),
                        "E_30": float(stats["E_30"]),
                        "E_max_m": float(stats["E_max_m"]),
                        "a_max_norm": float(stats["a_max_norm"]),
                        "b_max_norm": float(stats["b_max_norm"]),
                    }
                    if keep_tau_arrays:
                        cyc.update({
                            "gap_tau": stats["gap_tau"],
                            "a_tau": stats["a_tau"],
                            "b_tau": stats["b_tau"],
                            "E_tau": stats["E_tau"],
                            "A_h_tau": stats["A_h_tau"],
                            "A_c_tau": stats["A_c_tau"],
                        })
                    finalized_cycles.append(cyc)
                    if feedback_fn is not None:
                        feedback_fn(cyc)

                if collided or completed or k == N_SIM_STEPS:
                    t_end = t
                    break

                # 3. Nhận diện + dự báo (M1/M2/M3) và lập kế hoạch Frenet; đo thời gian thật (ms)
                extra_delay = loc.sample_extra_delay_on_plan()
                delayed_snaps = agents_obs_10hz[max(0, cur_10hz_idx - 1)] if condition == "D10" else None
                was_rev = {ag.id: ag.revealed for ag in agents}

                t0_perf = time.perf_counter()
                pred_agents = perc_pred.observe_and_predict(
                    agents,
                    ego_px,
                    ego_py,
                    rng_obs,
                    static_obs=static_obs,
                    ref_path=ref_path,
                    ego_s=ego_s,
                    t=t,
                    ego_psi=ego_psi,
                    condition=condition,
                    delayed_snaps=delayed_snaps,
                    prev_preds_by_id=prev_preds_by_id,
                )
                q_val, margin_tau = margin_fn(g_label, t, len(pred_agents))
                margin_pos = np.maximum(margin_tau, 0.0)
                plan = plan_frenet(
                    x_est,
                    ego_a,
                    pred_agents,
                    margin_pos,
                    ref_path=ref_path,
                    d_s=d_s,
                    lane_half_width=lane_half_width,
                    dense_v_grid=dense_v_grid,
                )
                tcomp_ms = (time.perf_counter() - t0_perf) * 1000.0
                tcomp_samples.append(float(tcomp_ms))

                if static_obs:
                    for ag in agents:
                        if not was_rev[ag.id] and ag.revealed:
                            gap_x = max(0.0, ag.px - ego_px - HX - ag.disk_radius)
                            if (gap_x / max(ego_v, 0.1)) < (ego_v / abs(A_MIN)) and ag.py * math.sin(ag.psi) <= 0.0:
                                unavoidable = 1

                current_plan = plan
                last_plan_t = t
                if not is_fake and cfg.debug_draw:
                    session.draw_plan(frame, plan, pred_agents)
                pending_plans.append({
                    "idx_10hz": cur_10hz_idx,
                    "t": t,
                    "g": g_label,
                    "J": float(plan.cost) if math.isfinite(plan.cost) else 9999.0,
                    "fallback": plan.fallback,
                    "q_used": float(q_val),
                    "m_3s": float(margin_pos[-1]),
                    "plan_poses": plan.poses,
                    "pred_agents": pred_agents,
                })

            if k == N_SIM_STEPS:
                t_end = t
                break

            # 4. Gửi lệnh điều khiển 20 Hz qua VehicleControlBridge
            assert current_plan is not None
            ctrl_dict = bridge.compute_control_dict(
                x_est, current_plan, t, t - last_plan_t,
                extra_delay=extra_delay, v_true=ego_v, dt=DT_SIM,
            )
            last_delta_eff = ctrl_dict["delta_eff"]

            if is_fake:
                assert ego_plant is not None
                ego_plant.step(ctrl_dict["v_del"], ctrl_dict["delta_del"], DT_SIM)
                agent_mgr.step_and_sync(ego_plant.px, ego_plant.py, ego_plant.psi, ego_plant.v, t, DT_SIM, frame=None)
                a_now = ego_plant.a
                ego_px_n, ego_py_n, ego_psi_n, ego_v_n = ego_plant.px, ego_plant.py, ego_plant.psi, ego_plant.v
            else:
                ego_actor.apply_control(bridge.to_carla_control(ctrl_dict))
                agent_mgr.step_and_sync(ego_px, ego_py, ego_psi, ego_v, t, DT_SIM, frame=frame)
                session.tick()
                agent_mgr.sync_from_carla_after_tick(frame)
                assert frame is not None
                ego_px_n, ego_py_n, ego_psi_n = frame.ego_rear_axle_pose(ego_actor)
                _, _, ego_v_n = frame.actor_velocity(ego_actor, ego_psi_n)
                ego_v_n = max(0.0, float(ego_v_n))
                a_now = float(frame.actor_accel_long(ego_actor, ego_psi_n))

            if k > 0:
                jerk = (a_now - prev_a) / DT_SIM
                jerk_sq_sum += jerk * jerk
                jerk_n += 1
            prev_a = a_now

            # 5. Kiểm tra va chạm và khoảng cách tức thời
            if carla_col_flag[0]:
                collided = True
            for ag in agents:
                if t < ag.behavior.get("appear_t", 0.0):
                    continue
                d_cur, s_clr = _scalar_box_agent_dist(
                    ego_px_n, ego_py_n, ego_psi_n,
                    ag.px, ag.py, ag.psi,
                    ag.disk_offsets, ag.disk_radius,
                )
                if d_cur < d_min_ep:
                    d_min_ep = d_cur
                rel_x, rel_y = ag.px - ego_px_n, ag.py - ego_py_n
                dist_c = math.hypot(rel_x, rel_y)
                if dist_c > 1e-3 and d_cur > 0.0:
                    ux, uy = rel_x / dist_c, rel_y / dist_c
                    vx_rel = ego_v_n * math.cos(ego_psi_n) - ag.v * math.cos(ag.psi)
                    vy_rel = ego_v_n * math.sin(ego_psi_n) - ag.v * math.sin(ag.psi)
                    closing = vx_rel * ux + vy_rel * uy
                    if closing > 0.1:
                        ttc_val = d_cur / closing
                        if ttc_val < ttc_min_ep:
                            ttc_min_ep = ttc_val
                if s_clr <= 0.0:
                    collided = True

            ego_progress = ref_path.project_s(ego_px_n, ego_py_n) if ref_path is not None else ego_px_n
            if ego_progress >= GOAL_X:
                completed = True

            if collided or completed:
                t_end = round((k + 1) * DT_SIM, 4)
                break
    finally:
        agent_mgr.destroy_all()
        if not is_fake:
            session.destroy_tracked_actors()

    n_cycles = len(finalized_cycles)
    n_fallback = sum(c["fallback"] for c in finalized_cycles)
    jerk_rms = math.sqrt(jerk_sq_sum / jerk_n) if jerk_n > 0 else 0.0
    tcomp_p95 = float(np.percentile(tcomp_samples, 95)) if tcomp_samples else 0.5
    if d_min_ep == float("inf"):
        d_min_ep = 40.0
    if ttc_min_ep == float("inf"):
        ttc_min_ep = 16.0

    episode_summary = {
        "method": method,
        "seed": int(seed),
        "scn": scenario,
        "cond": condition,
        "collided": int(collided),
        "completed": int(completed),
        "t_end": float(t_end),
        "d_min": float(d_min_ep),
        "ttc_min": float(ttc_min_ep),
        "n_cycles": int(n_cycles),
        "n_fallback": int(n_fallback),
        "jerk_rms": float(jerk_rms),
        "tcomp_p95_ms": float(tcomp_p95),
    }
    return {
        "episode": episode_summary,
        "cycles": finalized_cycles,
        "perception_stats": perc_pred.stats.to_dict(),
        "unavoidable": int(unavoidable),
    }
