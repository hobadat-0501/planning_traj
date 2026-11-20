"""Test ngoại tuyến (không cần CARLA) cho T28–T31: C1-c, C3, C4, C6-a và các khối lõi."""
import json
import math

import numpy as np
import pytest

from av_conformal.av_core.actuation import Control, TeslaActuator
from av_conformal.av_core.config import load_cfg
from av_conformal.av_core.evaluator import DelayedEvaluator
from av_conformal.av_core.geometry import poly_distance, rect_polygon, wrap_angle
from av_conformal.av_core.noise import Condition, LocalizationNoise
from av_conformal.av_core.planner import FrenetPlanner
from av_conformal.av_core.predictor import ade_fde, predict_cv
from av_conformal.carla_env.coords import from_carla_xyz_yaw, to_carla_xyz_yaw
from av_conformal.carla_env.scenarios import Route, build_scenario
from av_conformal.scripts import batch
from av_conformal.scripts.sim_runner import run_episode

CFG = load_cfg()


# ---- C1-c: quy đổi tọa độ khứ hồi ----
def test_coords_roundtrip():
    rng = np.random.default_rng(0)
    for _ in range(200):
        x, y, psi = rng.uniform(-100, 100), rng.uniform(-100, 100), rng.uniform(-np.pi, np.pi)
        cx, cy, _, cyaw = to_carla_xyz_yaw(x, y, psi)
        bx, by, bpsi = from_carla_xyz_yaw(cx, cy, cyaw)
        assert abs(bx - x) < 1e-6 and abs(by - y) < 1e-6
        assert abs(wrap_angle(bpsi - psi)) < 1e-6


def test_coords_handedness():
    # xe quay sang trái (psi tăng, tay phải) -> yaw CARLA giảm (tay trái)
    _, _, _, y1 = to_carla_xyz_yaw(0, 0, 0.0)
    _, _, _, y2 = to_carla_xyz_yaw(0, 0, 0.1)
    assert y2 < y1


# ---- hình học ----
def test_poly_distance():
    a = rect_polygon(0, 0, 0.0, 4.0, 2.0, 1.0)
    b = rect_polygon(10, 0, 0.0, 2.0, 2.0, 1.0)
    d = poly_distance(a, b)
    assert d > 0
    assert poly_distance(a, a) <= 0.0
    # tịnh tiến thêm 1 m làm khoảng cách tăng đúng 1 m
    b2 = rect_polygon(11, 0, 0.0, 2.0, 2.0, 1.0)
    assert abs(poly_distance(a, b2) - d - 1.0) < 1e-6


# ---- C6-a: bộ đánh giá ----
def _eval_setup(shift):
    H = 30
    ev = DelayedEvaluator(H, (4.69, 2.09, 1.0), np.ones(H), 0.5)
    plan = np.array([[5.0 + 0.1 * k, 0, 0.0] for k in range(1, H + 1)])
    pred = {"a": (np.array([[16.0, 0.0, 0.0]] * H), (0.6, 0.6))}
    return ev, plan, pred


def test_evaluator_exact_and_shift():
    H = 30
    for shift, expect in [(0.0, 0.0), (0.5, 0.5)]:
        ev, plan, pred = _eval_setup(shift)
        ego_true = [tuple(p) for p in plan]
        res = []
        for k in range(H):
            # kế hoạch thêm sau add_truth đầu tiên để khớp thứ tự của sim_runner
            if k == 0:
                res += ev.add_truth((0, 0, 0), {})
                ev.add_plan(0.0, plan, pred, dict(group="fixed"))
            else:
                res += ev.add_truth(ego_true[k - 1], {"a": (16.0 - shift, 0.0, 0.0)})
        res += ev.add_truth(ego_true[H - 1], {"a": (16.0 - shift, 0.0, 0.0)})
        assert len(res) == 1
        R = res[0]["R"]
        if shift == 0.0:
            assert abs(R) < 1e-6
        else:
            # tác nhân thật tiến gần 0,5 m so với dự báo -> d_true nhỏ hơn 0,5 m -> R = 0,5 (σ = 1)
            assert abs(R - shift) < 1e-6


# ---- C3: nhiễu ----
def _rms(state, n=4000, dt=0.05, seed=0):
    nz = LocalizationNoise(CFG["noise"], np.random.default_rng(seed))
    e = np.array([nz.sample(state, 5.0, 0.0, dt) for _ in range(n)])
    return e


def test_noise_groups_ordering():
    e_fix, e_flt = _rms("fixed"), _rms("float")
    s_fix = np.sqrt((e_fix[:, :2] ** 2).mean())
    s_flt = np.sqrt((e_flt[:, :2] ** 2).mean())
    assert s_flt > s_fix > 0


def test_noise_lost_grows():
    e = _rms("lost", n=400)
    assert np.hypot(e[-1, 0], e[-1, 1]) > np.hypot(e[20, 0], e[20, 1]) or abs(e[-1, 2]) > abs(e[20, 2])


def test_condition_d2_outage():
    spec = CFG["conditions"]["D2"]
    c = Condition("D2", spec, np.random.default_rng(3))
    states = {c.rtk_at(t) for t in np.arange(0, 40, 0.05)}
    assert "lost" in states and len(states) >= 2


# ---- bộ chuyển lệnh ----
def test_actuator_delay():
    p = CFG["vehicle"]
    seq = [0.0] * 10 + [5.0] * 10     # lệnh nhảy bậc tại bước 10
    first = {}
    for d in (0.0, 0.2):
        a = TeslaActuator(p, 0.05, d)
        thr = [a(0.0, v, 0.0).throttle for v in seq]
        first[d] = next(k for k, u in enumerate(thr) if u > 0)
    assert first[0.0] == 10
    assert first[0.2] - first[0.0] == 4   # 0,2 s / 0,05 s


# ---- planner ----
def test_planner_free_road_and_fallback():
    veh = CFG["vehicle"]
    route = Route.straight(120.0)
    pl = FrenetPlanner(veh, route, H=30, dt=0.1, d_s=0.5)
    x = np.array([0.0, 0.0, 0.0, 5.0, 0.0])
    p = pl.plan(x, {}, np.zeros(30))
    assert not p.fallback and p.poses_H.shape == (30, 3)
    # vật cản đứng ngay trước, rộng cả làn: kế hoạch phải phanh/dự phòng hoặc né, không đi xuyên
    obs = {"o": (np.tile([8.0, 0.0, 0.0], (30, 1)), (3.0, 6.0))}
    p2 = pl.plan(x, obs, np.zeros(30))
    el, ew, eo = veh["length"], veh["width"], veh["rear_overhang"]
    dmin = min(poly_distance(rect_polygon(*p2.poses_H[k], el, ew, eo), rect_polygon(8, 0, 0, 3.0, 6.0, 1.5))
               for k in range(30))
    assert p2.fallback or dmin >= 0.5 - 1e-9


# ---- dự báo ----
def test_predict_cv_straight_ade_zero():
    track = [[0.0, 0.0, 0.0], [0.1, 0.1, 0.0]]
    pred = predict_cv(track, 30, 0.1)
    true = np.array([[0.1 + 0.1 * k, 0.0] for k in range(1, 31)])
    ade, fde = ade_fde(pred[:, :2], true)
    assert ade < 1e-9 and fde < 1e-9


def test_predict_stationary_keeps_heading():
    from av_conformal.av_core.predictor import ConstantVelocityPredictor
    p = ConstantVelocityPredictor(30, 0.1)
    for k in range(3):
        p.update({"lead": (10.0, 20.0, 1.57)}, 0.1 * k)
    pose = p({"lead": (4.5, 1.9)})["lead"][0]
    assert np.allclose(pose[:, 2], 1.57) and np.allclose(pose[:, :2], [10.0, 20.0])


# ---- C4: tái lập ----
def test_scenario_seed_reproducible():
    route = Route.straight(120.0)
    for name in ("S1", "S2", "S3", "S4"):
        a = build_scenario(name, route, CFG, np.random.default_rng(11))
        b = build_scenario(name, route, CFG, np.random.default_rng(11))
        assert [x.id for x in a] == [x.id for x in b]
        for x, y in zip(a, b):
            for t in range(40):
                x.step((0, 0), t * 0.05, 0.05)
                y.step((0, 0), t * 0.05, 0.05)
            assert np.allclose(x.pose(), y.pose())


# ---- chạy một lượt, logger, batch ----
def test_episode_runs_and_logs(tmp_path):
    m = run_episode(CFG, 0, "B0", "S4", "D0", tmp_path, T_max=6.0)
    assert m["status"] in ("goal", "timeout", "collision")
    assert (tmp_path / f"{m['run_id']}_meta.json").exists()
    assert (tmp_path / f"{m['run_id']}_cycles.csv").exists()


def test_episode_reproducible(tmp_path):
    a = run_episode(CFG, 5, "B0", "S1", "D1", tmp_path / "a", T_max=8.0)
    b = run_episode(CFG, 5, "B0", "S1", "D1", tmp_path / "b", T_max=8.0)
    assert a["status"] == b["status"] and a["d_min"] == b["d_min"]


def test_batch_skip_and_shard(tmp_path):
    cs = batch.combos(["S1", "S4"], ["D0"], ["B0"], range(3))
    assert len(cs) == 6
    sh = [batch.shard(cs, i, 3) for i in range(3)]
    assert sorted(map(str, sum(sh, []))) == sorted(map(str, cs))
    r1 = batch.run_batch(CFG, "t", tmp_path, ["S4"], ["D0"], ["B0"], range(2), T_max=3.0, verbose=False)
    r2 = batch.run_batch(CFG, "t", tmp_path, ["S4"], ["D0"], ["B0"], range(2), T_max=3.0, verbose=False)
    assert r1["run"] == 2 and r2["run"] == 0 and r2["skipped"] == 2


def test_unknown_method_marked_error(tmp_path):
    m = run_episode(CFG, 0, "B3", "S4", "D0", tmp_path, T_max=2.0)
    assert m["status"] == "error"
    assert json.loads((tmp_path / f"{m['run_id']}_meta.json").read_text())["status"] == "error"


def test_poly_distance_batch_matches_scalar():
    from av_conformal.av_core.geometry import poly_distance_batch, rect_polygons
    rng = np.random.default_rng(1)
    n = 300
    ex, ey = rng.uniform(-3, 3, n), rng.uniform(-3, 3, n)
    ep, ap = rng.uniform(-3, 3, n), rng.uniform(-3, 3, n)
    E = rect_polygons(ex, ey, ep, 4.69, 2.09, 1.0)
    A = rect_polygons(np.zeros(n), np.zeros(n), ap, 1.8, 0.6, 0.9)
    got = poly_distance_batch(E, A)
    ref = [poly_distance(rect_polygon(ex[i], ey[i], ep[i], 4.69, 2.09, 1.0), rect_polygon(0, 0, ap[i], 1.8, 0.6, 0.9))
           for i in range(n)]
    assert np.allclose(got, ref, atol=1e-9)
    assert (np.array(ref) == 0).any() and (np.array(ref) > 0).any()
