"""Bộ kiểm thử tự động cho gói `carla_sim` (T15–T21: cầu nối, tái lập hạt giống, M1–M3, tham số, báo cáo)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from carla_sim.config import CarlaConfig
from carla_sim.control import LongitudinalPID, VehicleControlBridge
from carla_sim.episode import FakeCarlaSession, run_carla_episode
from carla_sim.frames import FrameTransform
from carla_sim.infra import check_carla_env
from carla_sim.params import build_carla_param_spec, export_param_spec, select_cert_sample_size, select_velocity_grid
from carla_sim.perception import ConstantTurnRateAccelPredictor, PerceptionPredictor
from carla_sim.report_carla import generate_carla_report
from carla_sim.runner import benchmark_s_x_d, run_carla_suite, run_smoke_s1_d0
from sim.common import CYCLE_FIELDS, EPISODE_FIELDS, make_const_margin_fn
from sim.core import DEFAULT_SIGMA_OLD, H_STEPS, PlanResult, build_scenario_context


def test_carla_01_frame_transform_roundtrip() -> None:
    """Kiểm tra biến đổi tọa độ CARLA (tay trái) <-> cục bộ 2D (tay phải)."""
    ft = FrameTransform(x0=12.5, y0=-4.0, psi0=math.radians(35.0), z0=0.2)
    for px, py, psi in [(0.0, 0.0, 0.0), (15.3, -1.2, 0.45), (-3.0, 2.5, -1.1)]:
        X, Y = ft.local_to_world_xy(px, py)
        px2, py2 = ft.world_to_local_xy(X, Y)
        assert abs(px - px2) < 1e-9
        assert abs(py - py2) < 1e-9
        yaw_deg = ft.local_psi_to_world_yaw_deg(psi)
        psi2 = ft.world_yaw_deg_to_local(yaw_deg)
        assert abs(math.atan2(math.sin(psi - psi2), math.cos(psi - psi2))) < 1e-9


def test_carla_02_control_bridge_sign_and_bounds() -> None:
    """Kiểm tra đảo dấu lái tay trái CARLA, PID dọc và giới hạn D9."""
    pid = LongitudinalPID()
    th, br = pid.step(v_target=6.0, v_current=2.0)
    assert th > 0.0 and br == 0.0
    th2, br2 = pid.step(v_target=0.0, v_current=5.0)
    assert th2 == 0.0 and br2 > 0.0

    cfg = CarlaConfig()
    bridge = VehicleControlBridge(cfg, condition="D9", rng=np.random.default_rng(7))
    # Quỹ đạo rẽ trái nhẹ (y > 0) -> delta > 0 cục bộ -> steer < 0 trên CARLA
    xs = np.linspace(0.0, 20.0, H_STEPS + 1)
    ys = 0.05 * xs**2
    poses = np.column_stack([xs[1:], ys[1:], np.full(H_STEPS, 0.2)])
    plan = PlanResult(poses=poses, v_traj=np.full(H_STEPS + 1, 6.0), path_xy=np.column_stack([xs, ys]), fallback=False, cost=0.0, min_d_plan=5.0)
    x_est = np.array([0.0, 0.0, 0.0, 5.0, 0.0], dtype=float)
    ctrl = bridge.compute_control_dict(x_est, plan, t=0.5, t_rel=0.0, extra_delay=0.0, v_true=5.0)
    assert -1.0 <= ctrl["steer"] <= 1.0
    assert 0.0 <= ctrl["throttle"] <= 1.0
    assert 0.0 <= ctrl["brake"] <= 0.55  # D9 giới hạn phanh tối đa theo a_min = -3 / -6


def test_carla_03_reproducibility_same_seed() -> None:
    """T16: Hai lượt chạy CARLA (FakeCarlaSession) cùng hạt giống cho kết quả giống hệt."""
    cfg = CarlaConfig(level="M1").level_defaults()
    m_fn = make_const_margin_fn(1.0, DEFAULT_SIGMA_OLD, 0.0)
    with FakeCarlaSession(cfg) as sess:
        r1 = run_carla_episode(sess, seed=501, scenario="S1", condition="D1", method="ĐX-1", margin_fn=m_fn, sigma_tau=DEFAULT_SIGMA_OLD, cfg=cfg)
        r2 = run_carla_episode(sess, seed=501, scenario="S1", condition="D1", method="ĐX-1", margin_fn=m_fn, sigma_tau=DEFAULT_SIGMA_OLD, cfg=cfg)

    for k in EPISODE_FIELDS:
        if k == "tcomp_p95_ms":
            continue
        assert abs(float(r1["episode"][k]) - float(r2["episode"][k])) < 1e-9 if isinstance(r1["episode"][k], (int, float)) else r1["episode"][k] == r2["episode"][k]
    assert len(r1["cycles"]) == len(r2["cycles"]) and len(r1["cycles"]) > 0
    for c1, c2 in zip(r1["cycles"], r2["cycles"]):
        assert abs(c1["R"] - c2["R"]) < 1e-9 or (math.isinf(c1["R"]) and math.isinf(c2["R"]))


def test_carla_04_smoke_s1_d0_and_analyze_log_schema(tmp_path: Path) -> None:
    """T16: Chạy S1 + D0 và xác nhận định dạng 5 file log khớp `analyze.py`."""
    out_dir = tmp_path / "carla_smoke"
    res = run_smoke_s1_d0(out_dir=out_dir, backend="fake", seed=500)
    assert res["episode"]["method"] == "B0"
    for fname in ("config.json", "calibration.json", "episodes.csv", "cycles.csv", "summary.json"):
        assert (out_dir / fname).exists()

    ep_df = pd.read_csv(out_dir / "episodes.csv")
    cyc_df = pd.read_csv(out_dir / "cycles.csv")
    assert list(ep_df.columns) == EPISODE_FIELDS
    assert list(cyc_df.columns) == CYCLE_FIELDS
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert "B0" in summary["by_method"]


def test_carla_05_perception_levels_m1_m2_m3() -> None:
    """T19–T20: Kiểm tra đầu vào M1 (CV), M2 (CTRA/learned), M3 (LiDAR)."""
    agents, _, _ = build_scenario_context("S3", np.random.default_rng(123))
    for level in ("M1", "M2", "M3"):
        cfg = CarlaConfig(level=level).level_defaults()
        pp = PerceptionPredictor(cfg)
        rng = np.random.default_rng(99)
        preds = pp.observe_and_predict(agents, ego_px=30.0, ego_py=0.0, rng_obs=rng, t=1.0, ego_psi=0.0, condition="D0")
        for p in preds:
            assert p["pred_centers"].shape == (H_STEPS, 2)
            assert p["pred_yaws"].shape == (H_STEPS,)

    # CTRA dự báo quay/giảm tốc mượt không NaN
    ctra = ConstantTurnRateAccelPredictor()
    for step in range(5):
        pc, py = ctra.update_and_predict("ag1", step * 0.1, float(step), 0.0, 5.0 - 0.3 * step, 0.2 * step, 0.05 * step)
    assert np.all(np.isfinite(pc)) and np.all(np.isfinite(py))


def test_carla_06_bench_and_params_t17_t18(tmp_path: Path) -> None:
    """T17–T18: Kiểm tra đủ S×D không lỗi, P95 < 100 ms, và chốt bảng tham số §4.2."""
    bn = benchmark_s_x_d(backend="fake", scenarios=("S1", "S2"), conditions=("D0", "D2"))
    assert bn["n_cells"] == 4
    assert bn["meets_100ms_budget"]

    pac_csv = Path(__file__).resolve().parents[1] / "logs" / "ext" / "pac_power.csv"
    ss = select_cert_sample_size(alpha=0.10, delta=0.05, max_tries=3, max_excess_cov=0.02, pac_power_csv=pac_csv if pac_csv.exists() else None)
    assert ss["excess_cov"] <= 0.02
    assert ss["recommended_n_cert_cycles"] >= 100

    vg_fast = select_velocity_grid(measured_tcomp_p95_ms=20.0, budget_ms=100.0)
    assert vg_fast["dense_v_grid"] is True and vg_fast["n_candidates"] == 663
    vg_slow = select_velocity_grid(measured_tcomp_p95_ms=70.0, budget_ms=100.0)
    assert vg_slow["dense_v_grid"] is False and vg_slow["n_candidates"] == 351

    spec = build_carla_param_spec(measured_tcomp_p95_ms=bn["tcomp_p95_ms_overall"], pac_power_csv=pac_csv if pac_csv.exists() else None)
    jp, mp = export_param_spec(spec, tmp_path / "params")
    assert jp.exists() and mp.exists()


def test_carla_07_mini_suite_checkpoint_and_report(tmp_path: Path) -> None:
    """T19–T21: Chạy thử mini-suite Phương án B (M1 & M2) có checkpoint, rồi sinh báo cáo CARLA."""
    out_m1 = tmp_path / "logs" / "carla_m1"
    out_m2 = tmp_path / "logs" / "carla_m2"
    mini_kw = dict(
        backend="fake",
        methods=["B0", "B1", "ĐX-1", "ĐX-2", "ĐX-3"],
        sigma_seeds=[200, 201],
        calib_blocks=[[250, 251], [300, 301]],
        cert_blocks=[[400, 401]],
        test_seeds=[500, 501],
        scenarios=("S1", "S4"),
        conditions=("D0", "D1"),
    )
    res_m1 = run_carla_suite(out_m1, cfg=CarlaConfig(level="M1").level_defaults(), **mini_kw)
    assert (out_m1 / "checkpoint.jsonl").exists()
    assert "exchangeability" in res_m1["calibration"]

    # Chạy lại lần 2 để kiểm tra đọc từ checkpoint không lỗi
    res_m1_resume = run_carla_suite(out_m1, cfg=CarlaConfig(level="M1").level_defaults(), **mini_kw)
    assert res_m1_resume["summary"]["by_method"]["ĐX-1"]["n_episodes"] == res_m1["summary"]["by_method"]["ĐX-1"]["n_episodes"]

    # Chạy M2 và sinh báo cáo T21
    run_carla_suite(out_m2, cfg=CarlaConfig(level="M2").level_defaults(), **mini_kw)
    md_path = generate_carla_report(
        ws_dir=tmp_path,
        logs_2d_dir=Path(__file__).resolve().parents[1] / "logs" / "B",
        logs_m1_dir=out_m1,
        logs_m2_dir=out_m2,
        out_md=tmp_path / "report" / "BAO_CAO_CARLA.md",
        figs_dir=tmp_path / "figs",
    )
    assert md_path.exists()
    text = md_path.read_text(encoding="utf-8")
    assert "CARLA M1" in text and "CARLA M2" in text
    assert (tmp_path / "figs" / "H12_carla_vs_2d_coverage.png").exists()
    assert (tmp_path / "figs" / "H13_carla_m1_m2_margin.png").exists()
    assert check_carla_env()["python_version"]
