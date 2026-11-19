"""Kiểm thử hình học hộp-đĩa, A_h vs A_c và đồng nhất thức phân tách có dấu (TC-02, TC-03, TC-04)."""

from __future__ import annotations

import math

import numpy as np

from sim.common import make_const_margin_fn
from sim.core import (
    DEFAULT_SIGMA_OLD,
    HX,
    HY,
    XC_LOCAL,
    box_disk_geometry_batch,
    ego_agent_distance,
    run_episode,
)


def _dense_boundary_box_disk_dist(
    px: float, py: float, psi: float, qx: float, qy: float, r: float, n_pts: int = 10000
) -> float:
    """Lời giải tham chiếu bằng lấy mẫu dày 10^4 điểm trên biên hộp xe + kiểm tra điểm nằm trong hộp."""
    c, s = math.cos(psi), math.sin(psi)
    cx = px + XC_LOCAL * c
    cy = py + XC_LOCAL * s
    dx = qx - cx
    dy = qy - cy
    u_q = dx * c + dy * s
    v_q = -dx * s + dy * c

    # Nếu tâm đĩa nằm trong hộp xe thì khoảng cách tới hộp bằng 0
    if abs(u_q) <= HX and abs(v_q) <= HY:
        return 0.0

    # Phân bổ 10^4 điểm đều theo chu vi 4 cạnh (bao gồm 4 góc)
    perim = 4.0 * (HX + HY)
    n_top = max(2, int(round(n_pts * (2.0 * HX) / perim)))
    n_side = max(2, (n_pts - 2 * n_top) // 2)

    us_h = np.linspace(-HX, HX, n_top)
    vs_v = np.linspace(-HY, HY, n_side)

    u_b = np.concatenate([us_h, us_h, np.full(n_side, HX), np.full(n_side, -HX)])
    v_b = np.concatenate([np.full(n_top, HY), np.full(n_top, -HY), vs_v, vs_v])

    xw = cx + u_b * c - v_b * s
    yw = cy + u_b * s + v_b * c
    d_center = float(np.min(np.hypot(qx - xw, qy - yw)))
    return max(0.0, d_center - r)


def test_tc02_box_disk_distance() -> None:
    """TC-02: So sánh khoảng cách hộp-đĩa với lời giải lấy mẫu dày (10^4 điểm) trên 1.000 cấu hình."""
    rng = np.random.default_rng(202602)
    n_cfg = 1000
    ego_poses = np.column_stack([
        rng.uniform(-20.0, 20.0, size=n_cfg),
        rng.uniform(-10.0, 10.0, size=n_cfg),
        rng.uniform(-math.pi, math.pi, size=n_cfg),
    ])
    disk_centers = ego_poses[:, :2] + rng.uniform(-5.5, 5.5, size=(n_cfg, 2))
    radii = rng.choice([0.35, 0.45, 0.95], size=n_cfg)

    d_fast = np.zeros(n_cfg, dtype=float)
    s_fast = np.zeros(n_cfg, dtype=float)
    for r_val in (0.35, 0.45, 0.95):
        mask = radii == r_val
        db, sb = box_disk_geometry_batch(
            ego_poses[mask],
            disk_centers[mask][:, None, :],
            np.array([r_val], dtype=float),
        )
        d_fast[mask] = db[:, 0]
        s_fast[mask] = sb[:, 0]

    max_err = 0.0
    n_overlap = 0
    for i in range(n_cfg):
        d_ref = _dense_boundary_box_disk_dist(
            float(ego_poses[i, 0]),
            float(ego_poses[i, 1]),
            float(ego_poses[i, 2]),
            float(disk_centers[i, 0]),
            float(disk_centers[i, 1]),
            float(radii[i]),
            n_pts=10000,
        )
        err = abs(float(d_fast[i]) - d_ref)
        if err > max_err:
            max_err = err
        if s_fast[i] <= 0.0:
            n_overlap += 1
            assert float(d_fast[i]) == 0.0

    assert n_overlap > 50, "Cần có đủ cấu hình chồng lấn trong tập kiểm tra ngẫu nhiên"
    assert max_err < 1e-6, f"Sai số tuyệt đối lớn nhất {max_err:.3e} >= 1e-6 m"


def test_tc03_ah_vs_ac() -> None:
    """TC-03: A_h >= A_c với mọi chu kỳ; A_h == A_c với tác nhân 1 đĩa (S1)."""
    m_fn = make_const_margin_fn(0.0, DEFAULT_SIGMA_OLD)

    # S1: người đi bộ 1 đĩa -> A_h == A_c
    for seed in range(500, 505):
        res_s1 = run_episode(seed, "S1", "D0", "B0", m_fn, sigma_tau=DEFAULT_SIGMA_OLD)
        active_cycs = [c for c in res_s1["cycles"] if c["has_agents"] == 1]
        assert len(active_cycs) > 0
        for c in active_cycs:
            assert np.all(np.abs(c["A_h_tau"] - c["A_c_tau"]) < 1e-12)
            assert abs(c["A_h_max"] - c["A_c_max"]) < 1e-12

    # S2, S3, S6: tác nhân đa đĩa -> A_h >= A_c và có chu kỳ thực sự A_h > A_c
    saw_strict_greater = False
    for scn in ("S2", "S3", "S6"):
        for seed in range(500, 504):
            res = run_episode(seed, scn, "D0", "B0", m_fn, sigma_tau=DEFAULT_SIGMA_OLD)
            active_cycs = [c for c in res["cycles"] if c["has_agents"] == 1]
            assert len(active_cycs) > 0
            for c in active_cycs:
                assert np.all(c["A_h_tau"] >= c["A_c_tau"] - 1e-12)
                assert c["A_h_max"] >= c["A_c_max"] - 1e-12
                if c["A_h_max"] > c["A_c_max"] + 1e-6:
                    saw_strict_greater = True
    assert saw_strict_greater


def test_tc04_signed_decomposition_identity() -> None:
    """TC-04: Đồng nhất thức a + b = d_hat - d cho mọi tác nhân và chu kỳ."""
    # 1. Kiểm tra trực tiếp theo từng bước/tác nhân trên chuỗi ngẫu nhiên
    rng = np.random.default_rng(202604)
    H = 30
    for _ in range(100):
        plan_poses = np.column_stack([
            np.linspace(0.0, 20.0, H) + rng.normal(0.0, 0.2, H),
            rng.normal(0.0, 0.4, H),
            rng.normal(0.0, 0.1, H),
        ])
        true_poses = plan_poses + rng.normal(0.0, 0.3, size=(H, 3))
        pred_c = np.column_stack([np.linspace(15.0, 5.0, H), rng.normal(0.0, 1.0, H)])
        true_c = pred_c + rng.normal(0.0, 0.4, size=(H, 2))
        pred_y = rng.uniform(-math.pi, math.pi, size=H)
        true_y = pred_y + rng.normal(0.0, 0.15, size=H)
        offs = np.array([-0.5, 0.5])
        rad = 0.45

        d_hat, _ = ego_agent_distance(plan_poses, pred_c, pred_y, offs, rad)
        d_mid, _ = ego_agent_distance(plan_poses, true_c, true_y, offs, rad)
        d_true, _ = ego_agent_distance(true_poses, true_c, true_y, offs, rad)

        a = d_hat - d_mid
        b = d_mid - d_true
        assert np.max(np.abs((a + b) - (d_hat - d_true))) < 1e-9

    # 2. Kiểm tra trực tiếp từ run_episode trên các kịch bản 1 tác nhân (S2, S4, S6)
    m_fn = make_const_margin_fn(0.0, DEFAULT_SIGMA_OLD)
    for scn in ("S2", "S4", "S6"):
        res = run_episode(500, scn, "D1", "B0", m_fn, sigma_tau=DEFAULT_SIGMA_OLD)
        active = [c for c in res["cycles"] if c["has_agents"] == 1]
        assert len(active) > 0
        for c in active:
            assert np.max(np.abs((c["a_tau"] + c["b_tau"]) - c["gap_tau"])) < 1e-9
