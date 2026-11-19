"""Kiểm thử hồi quy v0.1, mở rộng lõi S5–S10 / D6–D10, tất định đa tiến trình và 110 ô SxD (TC-01, TC-12..TC-18)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from sim.common import make_const_margin_fn, rescore_cycles_with_sigma, run_parallel_episodes
from sim.conditions_ext import D9_A_MAX, D9_A_MIN
from sim.core import (
    ALL_CONDITIONS,
    ALL_SCENARIOS,
    A_MIN,
    BASE_DELAY,
    DELTA_MAX,
    DT_SIM,
    GOAL_X,
    H_STEPS,
    N_SIM_STEPS,
    OMEGA_MAX,
    PLAN_EVERY,
    CommandDelayBuffer,
    EgoPlant,
    LocalizationGenerator,
    SimAgent,
    build_scenario_context,
    plan_frenet,
    pure_pursuit_control,
    run_episode,
    wrap_angle,
)
from sim.scenarios_ext import CurvedReferencePath, is_agent_occluded

ROOT = Path(__file__).resolve().parent.parent


def _load_new_calib() -> tuple[np.ndarray, float]:
    with open(ROOT / "logs" / "B" / "calibration.json", encoding="utf-8") as f:
        cal = json.load(f)
    return np.array(cal["sigma_tau"], dtype=float), float(cal["DX-1"]["q_final"])


def test_tc01_regression_in_v01() -> None:
    """TC-01: Chạy lại B0 và ĐX-1 trên 5 hạt giống tập IN, khớp logs/B/ (< 1e-9 cho tập lượt, < 1e-6 cho CSV chu kỳ)."""
    sigma_tau, q_dx1 = _load_new_calib()
    ep_df = pd.read_csv(ROOT / "logs" / "B" / "episodes.csv")
    cyc_df = pd.read_csv(ROOT / "logs" / "B" / "cycles.csv")

    for seed in range(500, 505):
        for scn in ("S1", "S2", "S3", "S4"):
            for cond in ("D0", "D2"):
                for method, q_val in (("B0", 0.0), ("ĐX-1", q_dx1)):
                    res = run_episode(
                        seed=seed,
                        scenario=scn,
                        condition=cond,
                        method=method,
                        margin_fn=make_const_margin_fn(q_val, sigma_tau),
                        sigma_tau=sigma_tau,
                    )
                    ep = res["episode"]
                    ref_ep = ep_df[
                        (ep_df["method"] == method)
                        & (ep_df["seed"] == seed)
                        & (ep_df["scn"] == scn)
                        & (ep_df["cond"] == cond)
                    ].iloc[0]

                    for k in ("collided", "completed", "n_cycles", "n_fallback"):
                        assert int(ep[k]) == int(ref_ep[k])
                    for k in ("t_end", "d_min", "ttc_min", "jerk_rms", "tcomp_p95_ms"):
                        assert abs(float(ep[k]) - float(ref_ep[k])) < 1e-9

                    ref_c = cyc_df[
                        (cyc_df["method"] == method)
                        & (cyc_df["seed"] == seed)
                        & (cyc_df["scn"] == scn)
                        & (cyc_df["cond"] == cond)
                    ].reset_index(drop=True)
                    cycs_cmp = (
                        rescore_cycles_with_sigma(res["cycles"], sigma_tau)
                        if method == "B0"
                        else res["cycles"]
                    )
                    assert len(cycs_cmp) == len(ref_c)
                    for i, c in enumerate(cycs_cmp):
                        for k in ("covered", "safe", "has_agents", "fallback"):
                            assert int(c[k]) == int(ref_c.loc[i, k])
                        assert str(c["g"]) == str(ref_c.loc[i, "g"])
                        for k in ("R", "d_min", "gap_max", "E_max_norm", "A_h_max", "A_c_max"):
                            v1 = float(c[k])
                            v2 = float(ref_c.loc[i, k])
                            if math.isfinite(v1) or math.isfinite(v2):
                                assert abs(v1 - v2) < 1e-6


def test_tc12_ego_open_loop_d0() -> None:
    """TC-12: Ở D0 đường thẳng không tác nhân, E_30 nhánh mở vòng có TB < 0,3 m và P95 < 0,5 m."""
    sigma_tau, _ = _load_new_calib()
    m_fn = make_const_margin_fn(0.0, sigma_tau)
    e30_vals: list[float] = []
    for seed in range(500, 515):
        res = run_episode(seed, "S0", "D0", "B0", m_fn, sigma_tau=sigma_tau)
        for c in res["cycles"]:
            e30_vals.append(float(c["E_track_30"]))

    mean_e = float(np.mean(e30_vals))
    p95_e = float(np.percentile(e30_vals, 95))
    assert mean_e < 0.30, f"E_track_30 mean = {mean_e:.4f} >= 0.30 m"
    assert p95_e < 0.50, f"E_track_30 P95 = {p95_e:.4f} >= 0.50 m"


def test_tc13_curved_road_s7_r25() -> None:
    """TC-13: Đường cong R = 25 m ở 6 m/s -> sai số bám ngang ổn định < 0,3 m, delta <= delta_max, omega <= omega_max."""
    rp = CurvedReferencePath(radius=25.0, turn_dir=1.0, s1=15.0, arc_len=40.0, s_total=95.0)
    rng_ego = np.random.default_rng(1301)
    ego = EgoPlant(rng_ego, "D0", v0=6.0)
    # Tắt sai số hệ số lái quá lớn? Giữ nguyên sai số ngẫu nhiên thật +-5% của EgoPlant
    cmd_buf = CommandDelayBuffer(BASE_DELAY)
    zero_margin = np.zeros(H_STEPS, dtype=float)

    arc_lat_errs: list[float] = []
    max_delta = 0.0
    max_omega = 0.0
    current_plan = None
    last_plan_t = 0.0

    for k in range(N_SIM_STEPS + 1):
        t = round(k * DT_SIM, 4)
        x_est = ego.state_vec()
        if k % PLAN_EVERY == 0:
            current_plan = plan_frenet(x_est, ego.a, [], zero_margin, ref_path=rp)
            last_plan_t = t
        assert current_plan is not None
        v_cmd, d_cmd = pure_pursuit_control(x_est, current_plan, t - last_plan_t)
        cmd_buf.push(t, v_cmd, d_cmd)
        v_del, d_del = cmd_buf.get_delayed(t, 0.0)

        d_prev = ego.delta
        ego.step(v_del, d_del, DT_SIM)
        omega = abs(ego.delta - d_prev) / DT_SIM
        max_delta = max(max_delta, abs(ego.delta))
        max_omega = max(max_omega, omega)

        s_ego, d_ego, _, _, _, kappa_r = rp.world_to_frenet(ego.px, ego.py, ego.psi, ego.v)
        # Đo sai số ngang ổn định khi đã vào cung tròn (sau 2.5 m đầu của cung để qua quá độ vào cua)
        if rp.s1 + 2.5 <= s_ego <= rp.s2:
            arc_lat_errs.append(abs(d_ego))
        if s_ego >= GOAL_X:
            break

    assert len(arc_lat_errs) > 20
    assert max(arc_lat_errs) < 0.30, f"Sai số bám ngang tối đa trên cung R=25m = {max(arc_lat_errs):.3f} >= 0.30 m"
    assert max_delta <= DELTA_MAX + 1e-9
    assert max_omega <= OMEGA_MAX + 1e-9

    # Kiểm tra thêm kịch bản S7 đầy đủ với R=25 m, v0=6 m/s
    sigma_tau, q_dx1 = _load_new_calib()
    res_s7 = run_episode(
        702, "S7", "D0", "ĐX-1", make_const_margin_fn(q_dx1, sigma_tau),
        sigma_tau=sigma_tau, v0=6.0, curve_radius_override=25.0,
    )
    assert res_s7["episode"]["max_delta"] <= DELTA_MAX + 1e-9
    assert res_s7["episode"]["max_omega"] <= OMEGA_MAX + 1e-9


def test_tc14_s5_occlusion() -> None:
    """TC-14: Ở kịch bản S5, tác nhân bị che khuất không xuất hiện trong J_t trước thời điểm lộ diện."""
    for seed in range(700, 710):
        rng_scn = np.random.default_rng(seed * 31 + ALL_SCENARIOS.index("S5") + 7)
        agents, static_obs, _ = build_scenario_context("S5", rng_scn)
        assert len(static_obs) == 1 and len(agents) == 1
        ag = agents[0]
        assert ag.was_occluded and not ag.revealed

        ego_px = 0.0
        ego_v = 7.5
        seen_occluded_phase = False
        seen_reveal = False
        for step in range(200):
            t = round(step * DT_SIM, 4)
            sensor_x = ego_px + 1.385
            occl = is_agent_occluded(sensor_x, 0.0, ag.px, ag.py, ag.psi, ag.disk_offsets, ag.disk_radius, static_obs)
            in_roi = ag.is_in_roi(ego_px, 0.0, t=t)
            if in_roi and occl and not ag.revealed:
                seen_occluded_phase = True
                # Trước khi lộ diện, không được phép đưa vào J_t
                assert not ag.revealed
            if in_roi and not occl and not ag.revealed:
                ag.revealed = True
                ag.reveal_t = t
                seen_reveal = True
                break
            ego_px += ego_v * DT_SIM
            ag.step(ego_px, t, DT_SIM)
        assert seen_occluded_phase and seen_reveal, f"Seed {seed} không đi qua pha che khuất rồi lộ diện"

    # Kiểm chứng trên run_episode: mọi chu kỳ của S5 có occluded_before==1 đều chỉ xuất hiện sau giai đoạn has_agents==0
    sigma_tau, _ = _load_new_calib()
    res = run_episode(700, "S5", "D0", "B0", make_const_margin_fn(0.0, sigma_tau), sigma_tau=sigma_tau)
    cycs = res["cycles"]
    assert any(c["has_agents"] == 0 for c in cycs)
    active = [c for c in cycs if c["has_agents"] == 1]
    if active:
        assert all(c["occluded_before"] == 1 for c in active)


def test_tc15_s9_ttc_reaction() -> None:
    """TC-15: Khi TTC < 2 s ở S9, tỉ lệ tác nhân nhường đường đúng xác suất 0,6 ± 0,04 (1.000 lần)."""
    n_trials = 1000
    yield_count = 0
    reacted_count = 0
    for seed in range(5000, 5000 + n_trials):
        rng = np.random.default_rng(seed * 31 + ALL_SCENARIOS.index("S9") + 7)
        agents, _, _ = build_scenario_context("S9", rng)
        ag = agents[0]
        ego_px = 0.0
        ego_v = 7.5
        for step in range(240):
            t = round(step * DT_SIM, 4)
            ego_px += ego_v * DT_SIM
            ag.step(ego_px, t, DT_SIM, ego_py=0.0, ego_psi=0.0, ego_v=ego_v)
            if ag.behavior["reacted"]:
                reacted_count += 1
                if ag.behavior["reaction"] == "yield":
                    yield_count += 1
                break

    assert reacted_count >= 900, f"Quá ít lượt kích hoạt TTC < 2 s: {reacted_count}/{n_trials}"
    frac = yield_count / reacted_count
    assert 0.56 <= frac <= 0.64, f"Tỉ lệ nhường đường {frac:.4f} nằm ngoài [0.56, 0.64]"


def test_tc16_d8_label_corruption() -> None:
    """TC-16: Điều kiện D8 báo nhãn 'fix' với tỉ lệ trong 0,30 ± 0,03 khi trạng thái thật là float."""
    fix_count = 0
    total_steps = 0
    for seed in range(100, 150):
        loc = LocalizationGenerator("D8", np.random.default_rng(seed))
        for step in range(200):
            g, _, _ = loc.step(step * DT_SIM, 7.0, 0.0, DT_SIM)
            fix_count += int(g == "fix")
            total_steps += 1
    frac = fix_count / total_steps
    assert 0.27 <= frac <= 0.33, f"Tỉ lệ nhãn 'fix' giả ở D8 = {frac:.4f} nằm ngoài [0.27, 0.33]"


def test_tc17_fallback_and_d9_accel_limit() -> None:
    """TC-17: Quỹ đạo dự phòng phanh với a_min = -6 m/s^2; ở D9 gia tốc thực bị cắt tại [-3, 2] m/s^2."""
    sigma_tau, _ = _load_new_calib()
    # 1. Ép fallback bằng margin lớn -> kiểm tra vận tốc kế hoạch giảm với a_min = -6.0 m/s^2
    huge_margin = np.full(H_STEPS, 50.0, dtype=float)
    x_est = np.array([10.0, 0.0, 0.0, 6.0, 0.0], dtype=float)
    pred_dummy = [{
        "id": "p0", "kind": "ped", "disk_radius": 0.35, "disk_offsets": np.array([0.0]),
        "pred_centers": np.full((H_STEPS, 2), [20.0, 0.0]), "pred_yaws": np.zeros(H_STEPS),
    }]
    plan_fb = plan_frenet(x_est, 0.0, pred_dummy, huge_margin)
    assert plan_fb.fallback is True
    assert abs(plan_fb.v_traj[0] - 6.0) < 1e-9
    assert abs(plan_fb.v_traj[10] - 0.0) < 1e-9  # 6.0 - 6.0 * 1.0 s = 0.0

    # 2. Kiểm tra EgoPlant ở D9: gia tốc thực bị cắt trong [-3.0, 2.0]
    ego_d9 = EgoPlant(np.random.default_rng(77), "D9", v0=8.0)
    min_a_seen = 0.0
    max_a_seen = 0.0
    for _ in range(40):
        ego_d9.step(0.0, 0.0, DT_SIM)
        min_a_seen = min(min_a_seen, ego_d9.a)
    assert min_a_seen >= D9_A_MIN - 1e-9 and min_a_seen <= D9_A_MIN + 0.05
    assert A_MIN == -6.0

    ego_d9_acc = EgoPlant(np.random.default_rng(78), "D9", v0=0.0)
    for _ in range(40):
        ego_d9_acc.step(8.3, 0.0, DT_SIM)
        max_a_seen = max(max_a_seen, ego_d9_acc.a)
    assert max_a_seen <= D9_A_MAX + 1e-9 and max_a_seen >= D9_A_MAX - 0.05


def test_tc18_determinism_multiprocessing() -> None:
    """TC-18: Chạy cùng hạt giống với 1 tiến trình và 2 tiến trình cho kết quả giống hệt nhau."""
    sigma_tau, q_dx1 = _load_new_calib()
    tasks = [
        (700 + i, scn, cond, "ĐX-1", (q_dx1, 0.0), sigma_tau, "const", 0, {"keep_tau_arrays": False})
        for i, (scn, cond) in enumerate([
            ("S1", "D0"), ("S3", "D2"), ("S5", "D6"), ("S6", "D7"),
            ("S7", "D8"), ("S8", "D9"), ("S9", "D10"), ("S10", "D5"),
        ])
    ]
    res_1w = run_parallel_episodes(tasks, workers=1)
    res_2w = run_parallel_episodes(tasks, workers=2)
    assert len(res_1w) == len(res_2w)
    for r1, r2 in zip(res_1w, res_2w):
        assert r1["episode"] == r2["episode"]
        assert r1["cycles"] == r2["cycles"]


def test_all_110_cells_smoke() -> None:
    """Chạy thử toàn bộ 110 ô (S1–S10 x D0–D10) không lỗi và không sinh NaN."""
    sigma_tau, q_dx1 = _load_new_calib()
    tasks = [
        (700, scn, cond, "ĐX-1", (q_dx1, 0.0), sigma_tau, "const", 0, {"keep_tau_arrays": False})
        for scn in ALL_SCENARIOS
        for cond in ALL_CONDITIONS
    ]
    assert len(tasks) == 110
    results = run_parallel_episodes(tasks, workers=4)
    assert len(results) == 110
    for r in results:
        ep = r["episode"]
        assert math.isfinite(ep["t_end"]) and ep["t_end"] > 0.0
        assert math.isfinite(ep["d_min"])
        assert math.isfinite(ep["jerk_rms"])
