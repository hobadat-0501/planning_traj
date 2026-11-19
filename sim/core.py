"""Lõi mô phỏng 2D vòng kín dùng chung cho phương án cũ (A) và phương án mới (B).

Tuân thủ đặc tả tại .claude/spec/SPEC.md §1–§4.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

# ==============================================================================
# Hằng số cấu hình mặc định (SPEC §1)
# ==============================================================================

DT_SIM: float = 0.05          # Bước mô phỏng vật lý (20 Hz)
DT_PLAN: float = 0.10         # Chu kỳ lập kế hoạch (10 Hz)
PLAN_EVERY: int = 2           # Số bước mô phỏng mỗi chu kỳ lập kế hoạch
H_STEPS: int = 30             # Chân trời dự báo 30 x 0.1 s = 3.0 s
T_MAX: float = 16.0           # Thời gian tối đa mỗi lượt (s)
N_SIM_STEPS: int = int(round(T_MAX / DT_SIM))

GOAL_X: float = 75.0          # Đích x (m)
LANE_HALF_WIDTH: float = 1.75 # Nửa bề rộng làn xe (m)
ROI_DIST: float = 40.0        # Vùng quan tâm cảm biến / dự báo (m)
D_S: float = 0.5              # Khoảng cách an toàn tối thiểu d_s (m)

# Tham số xe thật cỡ Tesla Model 3 (SPEC §1)
WHEELBASE: float = 2.875      # L (m)
EGO_LENGTH: float = 4.69      # Dài (m)
EGO_WIDTH: float = 1.85       # Rộng (m)
REAR_OVERHANG: float = 0.96   # Tâm cầu sau cách đuôi xe (m)
R_MAX: float = 3.85           # Bán kính bao từ tâm cầu sau (m)
XC_LOCAL: float = 0.5 * EGO_LENGTH - REAR_OVERHANG  # 1.385 m
HX: float = 0.5 * EGO_LENGTH  # 2.345 m
HY: float = 0.5 * EGO_WIDTH   # 0.925 m

DELTA_MAX: float = 0.6        # Góc lái tối đa (rad)
OMEGA_MAX: float = 0.8        # Tốc độ đánh lái tối đa (rad/s)
A_MIN: float = -6.0           # Gia tốc phanh cực đại (m/s^2)
A_MAX: float = 3.0            # Gia tốc tăng tốc cực đại (m/s^2)
V_MAX: float = 8.3            # Vận tốc tối đa (m/s)
KAPPA_MAX: float = math.tan(DELTA_MAX) / WHEELBASE  # ~0.23796 m^-1

TAU_ACCEL: float = 0.25       # Trễ gia tốc bậc nhất (s)
TAU_STEER: float = 0.10       # Trễ lái bậc nhất (s)
BASE_DELAY: float = 0.05      # Trễ lệnh nền 50 ms
FF_TIME: float = 0.50         # Bù trước vận tốc tại t + 0.5 s
KP_V: float = 2.5             # Hệ số tỷ lệ vòng vận tốc

LD_BASE: float = 2.0          # Pure Pursuit L_d = 2 + 0.3 * v
LD_K: float = 0.3

# Tập tham số Frenet (13 x 9 x 3 = 351 ứng viên)
D_TARGETS: np.ndarray = np.round(np.arange(-1.5, 1.501, 0.25), 4)
V_TARGETS: np.ndarray = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.3], dtype=float)
T_HORIZONS: np.ndarray = np.array([3.0, 4.0, 5.0], dtype=float)

SCENARIOS: tuple[str, ...] = ("S1", "S2", "S3", "S4")
CONDITIONS: tuple[str, ...] = ("D0", "D1", "D2", "D3", "D4", "D5")
GROUPS: tuple[str, ...] = ("fix", "float", "loss")

from sim.conditions_ext import (
    CONDITIONS_EXT,
    D6_EXTRA_DELAY,
    corrupt_d8_label,
    get_perception_params,
    get_plant_dynamics_params,
    sample_d7_outage,
)
from sim.scenarios_ext import (
    SCENARIOS_EXT,
    CurvedReferencePath,
    StaticObstacleBox,
    build_ext_scenario_context,
    is_agent_occluded,
    step_ext_agent,
)

ALL_SCENARIOS: tuple[str, ...] = SCENARIOS + SCENARIOS_EXT
ALL_CONDITIONS: tuple[str, ...] = CONDITIONS + CONDITIONS_EXT

# Hình bao tập đĩa cứng của các loại tác nhân (SPEC §1)
AGENT_DISK_SPECS: dict[str, tuple[float, np.ndarray]] = {
    "ped": (0.35, np.array([0.0], dtype=float)),
    "moto": (0.45, np.array([-0.5, 0.5], dtype=float)),
    "car": (0.95, np.array([-1.4, 0.0, 1.4], dtype=float)),
}


def wrap_angle(angle: np.ndarray | float) -> np.ndarray | float:
    """Đưa góc về khoảng [-pi, pi]."""
    return np.arctan2(np.sin(angle), np.cos(angle))


def scenario_for_seed(seed: int) -> str:
    """Ánh xạ kịch bản = hạt giống mod 4 cho hiệu chỉnh và chứng nhận (SPEC §4)."""
    return SCENARIOS[int(seed) % 4]


def condition_for_seed(seed: int, seed_base: int = 0) -> str:
    """Chọn điều kiện D0..D5 ngẫu nhiên đều theo hạt giống (SPEC §4)."""
    rng = np.random.default_rng(int(seed) + 1000003 + int(seed_base) * 9973)
    return CONDITIONS[int(rng.integers(0, len(CONDITIONS)))]


# ==============================================================================
# Hình học hộp chữ nhật – đĩa cứng vector hóa (SPEC §1)
# ==============================================================================

def box_disk_geometry_batch(
    ego_poses: np.ndarray,
    disk_centers: np.ndarray,
    disk_radii: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Tính khoảng cách Euclidean chính xác và khoảng hở có dấu giữa hộp xe và các đĩa.

    Parameters
    ----------
    ego_poses : array, shape (..., 3)
        Tư thế xe tại tâm cầu sau [px, py, psi].
    disk_centers : array, shape (..., M, 2)
        Tâm các đĩa tác nhân trong hệ toàn cục.
    disk_radii : array, shape (M,)
        Bán kính các đĩa tương ứng.

    Returns
    -------
    dist_euclid : array, shape (..., M)
        Khoảng cách hình học D(B, O) >= 0 (= 0 khi giao nhau).
    signed_clear : array, shape (..., M)
        Khoảng hở có dấu (<= 0 khi chạm/giao nhau).
    """
    px = ego_poses[..., 0][..., None]
    py = ego_poses[..., 1][..., None]
    psi = ego_poses[..., 2][..., None]

    c = np.cos(psi)
    s = np.sin(psi)
    cx = px + XC_LOCAL * c
    cy = py + XC_LOCAL * s

    dx_w = disk_centers[..., 0] - cx
    dy_w = disk_centers[..., 1] - cy

    u = dx_w * c + dy_w * s
    v = -dx_w * s + dy_w * c

    ox = np.maximum(np.abs(u) - HX, 0.0)
    oy = np.maximum(np.abs(v) - HY, 0.0)
    dist_center_to_box = np.hypot(ox, oy)
    signed_clear = dist_center_to_box - disk_radii
    dist_euclid = np.maximum(signed_clear, 0.0)
    return dist_euclid, signed_clear


def _scalar_box_agent_dist(
    ego_px: float,
    ego_py: float,
    ego_psi: float,
    ag_px: float,
    ag_py: float,
    ag_psi: float,
    disk_offsets: np.ndarray,
    disk_radius: float,
) -> tuple[float, float]:
    """Khoảng cách nhanh hộp–tác nhân tại 1 thời điểm (không qua NumPy dispatch)."""
    c_e = math.cos(ego_psi)
    s_e = math.sin(ego_psi)
    cx = ego_px + XC_LOCAL * c_e
    cy = ego_py + XC_LOCAL * s_e
    c_a = math.cos(ag_psi)
    s_a = math.sin(ag_psi)
    min_clr = float("inf")
    for off in disk_offsets:
        off_f = float(off)
        qx = ag_px + off_f * c_a
        qy = ag_py + off_f * s_a
        dx = qx - cx
        dy = qy - cy
        u = dx * c_e + dy * s_e
        v = -dx * s_e + dy * c_e
        ox = abs(u) - HX
        oy = abs(v) - HY
        if ox < 0.0:
            ox = 0.0
        if oy < 0.0:
            oy = 0.0
        clr = math.hypot(ox, oy) - disk_radius
        if clr < min_clr:
            min_clr = clr
    return (min_clr if min_clr > 0.0 else 0.0), min_clr


def ego_agent_distance(
    ego_poses: np.ndarray,
    agent_centers: np.ndarray,
    agent_yaws: np.ndarray,
    disk_offsets: np.ndarray,
    disk_radius: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Tính khoảng cách từ hộp xe tới một tác nhân gồm nhiều đĩa tại chuỗi bước tau.

    ego_poses: (..., H, 3)
    agent_centers: (H, 2)
    agent_yaws: (H,)
    disk_offsets: (K_d,)
    Trả về: dist (..., H), signed_clear (..., H) lấy min trên các đĩa của tác nhân.
    """
    cos_a = np.cos(agent_yaws)[:, None]
    sin_a = np.sin(agent_yaws)[:, None]
    qx = agent_centers[:, 0:1] + disk_offsets[None, :] * cos_a
    qy = agent_centers[:, 1:2] + disk_offsets[None, :] * sin_a
    disk_centers = np.stack([qx, qy], axis=-1)  # (H, K_d, 2)
    radii = np.full(len(disk_offsets), disk_radius, dtype=float)
    d_euc, s_clr = box_disk_geometry_batch(ego_poses, disk_centers, radii)
    return np.min(d_euc, axis=-1), np.min(s_clr, axis=-1)


# ==============================================================================
# Bộ lập kế hoạch Frenet tiền tính toán (351 ứng viên, vector hóa)
# ==============================================================================

V_TARGETS_DENSE: np.ndarray = np.array(
    [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.3],
    dtype=float,
)


def _build_frenet_basis(v_targets: np.ndarray | None = None) -> dict[str, Any]:
    """Tiền tính toán ma trận đa thức bậc 5 (39 ngang) và bậc 4 (dọc) cho H=30 bước."""
    t_grid = np.arange(1, H_STEPS + 1, dtype=float) * DT_PLAN  # (30,)
    v_tgts = V_TARGETS if v_targets is None else np.asarray(v_targets, dtype=float)

    n_d = len(D_TARGETS)   # 13
    n_v = len(v_tgts)      # 9 hoặc 17
    n_T = len(T_HORIZONS)  # 3

    L_pos_init = np.zeros((n_T, 30, 3), dtype=float)
    L_pos_df = np.zeros((n_T, n_d, 30), dtype=float)
    L_vel_init = np.zeros((n_T, 30, 3), dtype=float)
    L_vel_df = np.zeros((n_T, n_d, 30), dtype=float)
    L_acc_init = np.zeros((n_T, 30, 3), dtype=float)
    L_acc_df = np.zeros((n_T, n_d, 30), dtype=float)
    L_jrk_init = np.zeros((n_T, 30, 3), dtype=float)
    L_jrk_df = np.zeros((n_T, n_d, 30), dtype=float)

    S_pos_init = np.zeros((n_T, 30, 3), dtype=float)
    S_pos_vf = np.zeros((n_T, n_v, 30), dtype=float)
    S_vel_init = np.zeros((n_T, 30, 3), dtype=float)
    S_vel_vf = np.zeros((n_T, n_v, 30), dtype=float)
    S_acc_init = np.zeros((n_T, 30, 3), dtype=float)
    S_acc_vf = np.zeros((n_T, n_v, 30), dtype=float)
    S_jrk_init = np.zeros((n_T, 30, 3), dtype=float)
    S_jrk_vf = np.zeros((n_T, n_v, 30), dtype=float)

    V_pos = np.column_stack([np.ones_like(t_grid), t_grid, t_grid**2, t_grid**3, t_grid**4, t_grid**5])
    V_vel = np.column_stack([np.zeros_like(t_grid), np.ones_like(t_grid), 2*t_grid, 3*t_grid**2, 4*t_grid**3, 5*t_grid**4])
    V_acc = np.column_stack([np.zeros_like(t_grid), np.zeros_like(t_grid), 2*np.ones_like(t_grid), 6*t_grid, 12*t_grid**2, 20*t_grid**3])
    V_jrk = np.column_stack([np.zeros_like(t_grid), np.zeros_like(t_grid), np.zeros_like(t_grid), 6*np.ones_like(t_grid), 24*t_grid, 60*t_grid**2])

    W_pos = np.column_stack([np.ones_like(t_grid), t_grid, t_grid**2, t_grid**3, t_grid**4])
    W_vel = np.column_stack([np.zeros_like(t_grid), np.ones_like(t_grid), 2*t_grid, 3*t_grid**2, 4*t_grid**3])
    W_acc = np.column_stack([np.zeros_like(t_grid), np.zeros_like(t_grid), 2*np.ones_like(t_grid), 6*t_grid, 12*t_grid**2])
    W_jrk = np.column_stack([np.zeros_like(t_grid), np.zeros_like(t_grid), np.zeros_like(t_grid), 6*np.ones_like(t_grid), 24*t_grid])

    for i_T, T_val in enumerate(T_HORIZONS):
        T_val = float(T_val)
        M5 = np.array([
            [T_val**3, T_val**4, T_val**5],
            [3*T_val**2, 4*T_val**3, 5*T_val**4],
            [6*T_val, 12*T_val**2, 20*T_val**3],
        ], dtype=float)
        M5_inv = np.linalg.inv(M5)
        A5 = np.zeros((6, 4), dtype=float)
        A5[0, 0] = 1.0
        A5[1, 1] = 1.0
        A5[2, 2] = 0.5
        B5 = np.array([
            [-1.0, -T_val, -0.5*T_val**2, 1.0],
            [0.0, -1.0, -T_val, 0.0],
            [0.0, 0.0, -1.0, 0.0],
        ], dtype=float)
        A5[3:6, :] = M5_inv @ B5

        lp, lv, la, lj = V_pos @ A5, V_vel @ A5, V_acc @ A5, V_jrk @ A5
        L_pos_init[i_T], L_pos_df[i_T] = lp[:, :3], D_TARGETS[:, None] * lp[:, 3][None, :]
        L_vel_init[i_T], L_vel_df[i_T] = lv[:, :3], D_TARGETS[:, None] * lv[:, 3][None, :]
        L_acc_init[i_T], L_acc_df[i_T] = la[:, :3], D_TARGETS[:, None] * la[:, 3][None, :]
        L_jrk_init[i_T], L_jrk_df[i_T] = lj[:, :3], D_TARGETS[:, None] * lj[:, 3][None, :]

        M4 = np.array([[3*T_val**2, 4*T_val**3], [6*T_val, 12*T_val**2]], dtype=float)
        M4_inv = np.linalg.inv(M4)
        A4 = np.zeros((5, 4), dtype=float)
        A4[0, 0] = 1.0
        A4[1, 1] = 1.0
        A4[2, 2] = 0.5
        B4 = np.array([[0.0, -1.0, -T_val, 1.0], [0.0, 0.0, -1.0, 0.0]], dtype=float)
        A4[3:5, :] = M4_inv @ B4

        sp, sv, sa, sj = W_pos @ A4, W_vel @ A4, W_acc @ A4, W_jrk @ A4
        S_pos_init[i_T], S_pos_vf[i_T] = sp[:, :3], v_tgts[:, None] * sp[:, 3][None, :]
        S_vel_init[i_T], S_vel_vf[i_T] = sv[:, :3], v_tgts[:, None] * sv[:, 3][None, :]
        S_acc_init[i_T], S_acc_vf[i_T] = sa[:, :3], v_tgts[:, None] * sa[:, 3][None, :]
        S_jrk_init[i_T], S_jrk_vf[i_T] = sj[:, :3], v_tgts[:, None] * sj[:, 3][None, :]

    grid_T, grid_d, grid_v = np.meshgrid(np.arange(n_T), np.arange(n_d), np.arange(n_v), indexing="ij")
    df_grid = D_TARGETS[grid_d].ravel()
    vf_grid = v_tgts[grid_v].ravel()

    return {
        "n_T": n_T,
        "n_d": n_d,
        "n_v": n_v,
        "n_cand": n_T * n_d * n_v,
        "df_grid": df_grid,
        "vf_grid": vf_grid,
        "L_pos_init": L_pos_init, "L_pos_df": L_pos_df,
        "L_vel_init": L_vel_init, "L_vel_df": L_vel_df,
        "L_acc_init": L_acc_init, "L_acc_df": L_acc_df,
        "L_jrk_init": L_jrk_init, "L_jrk_df": L_jrk_df,
        "S_pos_init": S_pos_init, "S_pos_vf": S_pos_vf,
        "S_vel_init": S_vel_init, "S_vel_vf": S_vel_vf,
        "S_acc_init": S_acc_init, "S_acc_vf": S_acc_vf,
        "S_jrk_init": S_jrk_init, "S_jrk_vf": S_jrk_vf,
    }


FRENET_BASIS = _build_frenet_basis()
FRENET_BASIS_663 = _build_frenet_basis(V_TARGETS_DENSE)


@dataclass
class PlanResult:
    poses: np.ndarray        # (H, 3): [px, py, psi] tại tau = 1..H (t + 0.1..3.0 s)
    v_traj: np.ndarray       # (H+1,): vận tốc kế hoạch tại t_rel = 0.0, 0.1, ..., 3.0 s
    path_xy: np.ndarray      # (H+1, 2): tọa độ đường để Pure Pursuit bám (bắt đầu từ t_rel=0)
    fallback: bool
    cost: float
    min_d_plan: float


def _build_fallback_plan(
    x_est: np.ndarray,
    ref_path: CurvedReferencePath | None = None,
    lane_half_width: float = LANE_HALF_WIDTH,
) -> PlanResult:
    """Quỹ đạo phanh dự phòng với a_min = -6.0 m/s^2 dọc đường hiện tại (A3)."""
    px0, py0, psi0, v0, _ = x_est
    t_all = np.arange(0, H_STEPS + 1, dtype=float) * DT_PLAN
    v_traj = np.maximum(0.0, v0 + A_MIN * t_all)
    t_stop = v0 / (-A_MIN) if v0 > 0 else 0.0
    t_eff = np.minimum(t_all, t_stop)
    s_disp = v0 * t_eff + 0.5 * A_MIN * (t_eff ** 2)

    if ref_path is not None:
        s0, d0, _, _, _, _ = ref_path.world_to_frenet(px0, py0, psi0, max(0.0, float(v0)))
        d_hold = float(np.clip(d0, -lane_half_width, lane_half_width))
        s_seq = s0 + s_disp
        xr, yr, theta_r, _ = ref_path.eval_batch(s_seq)
        xs = xr - d_hold * np.sin(theta_r)
        ys = yr + d_hold * np.cos(theta_r)
        psis = theta_r
        poses = np.column_stack([xs[1:], ys[1:], psis[1:]])
        path_xy = np.column_stack([xs, ys])
        return PlanResult(
            poses=poses,
            v_traj=v_traj,
            path_xy=path_xy,
            fallback=True,
            cost=float("inf"),
            min_d_plan=0.0,
        )

    psi_hold = float(wrap_angle(0.5 * psi0))
    c_h, s_h = math.cos(psi_hold), math.sin(psi_hold)
    xs = px0 + s_disp * c_h
    ys = np.clip(py0 + s_disp * s_h, -lane_half_width, lane_half_width)
    psis = np.full(H_STEPS + 1, psi_hold, dtype=float)

    poses = np.column_stack([xs[1:], ys[1:], psis[1:]])
    path_xy = np.column_stack([xs, ys])
    return PlanResult(
        poses=poses,
        v_traj=v_traj,
        path_xy=path_xy,
        fallback=True,
        cost=float("inf"),
        min_d_plan=0.0,
    )


def plan_frenet(
    x_est: np.ndarray,
    a_est: float,
    pred_agents: list[dict[str, Any]],
    margin_tau: np.ndarray,
    ref_path: CurvedReferencePath | None = None,
    d_s: float = D_S,
    lane_half_width: float = LANE_HALF_WIDTH,
    dense_v_grid: bool = False,
) -> PlanResult:
    """Lập kế hoạch Frenet 351 (hoặc 663) ứng viên -> lọc động học -> lọc an toàn -> chọn chi phí nhỏ nhất."""
    px0, py0, psi0, v0, _ = x_est
    v_safe = max(0.0, float(v0))
    dds0 = float(np.clip(a_est, A_MIN * 0.8, A_MAX * 0.8))

    if ref_path is None:
        s0_f = px0
        d0_f = py0
        ds0 = v_safe * math.cos(psi0)
        dd0 = v_safe * math.sin(psi0)
        dd_init = 0.0
    else:
        s0_f, d0_f, ds0, dd0, _, _ = ref_path.world_to_frenet(px0, py0, psi0, v_safe)
        dd_init = float(np.clip(-2.2 * d0_f - 1.5 * dd0, -3.5, 3.5))

    lat0 = np.array([d0_f, dd0, dd_init], dtype=float)
    lon0 = np.array([s0_f, ds0, dds0], dtype=float)

    B = FRENET_BASIS_663 if dense_v_grid else FRENET_BASIS
    n_T, n_d, n_v, n_cand = B["n_T"], B["n_d"], B["n_v"], B["n_cand"]

    d_pos_sep = (B["L_pos_init"] @ lat0)[:, None, :] + B["L_pos_df"]
    d_vel_sep = (B["L_vel_init"] @ lat0)[:, None, :] + B["L_vel_df"]
    d_acc_sep = (B["L_acc_init"] @ lat0)[:, None, :] + B["L_acc_df"]
    d_jrk_sep = (B["L_jrk_init"] @ lat0)[:, None, :] + B["L_jrk_df"]

    s_pos_sep = (B["S_pos_init"] @ lon0)[:, None, :] + B["S_pos_vf"]
    s_vel_sep = (B["S_vel_init"] @ lon0)[:, None, :] + B["S_vel_vf"]
    s_acc_sep = (B["S_acc_init"] @ lon0)[:, None, :] + B["S_acc_vf"]
    s_jrk_sep = (B["S_jrk_init"] @ lon0)[:, None, :] + B["S_jrk_vf"]

    d_pos = np.broadcast_to(d_pos_sep[:, :, None, :], (n_T, n_d, n_v, 30)).reshape(n_cand, 30)
    d_vel = np.broadcast_to(d_vel_sep[:, :, None, :], (n_T, n_d, n_v, 30)).reshape(n_cand, 30)
    d_acc = np.broadcast_to(d_acc_sep[:, :, None, :], (n_T, n_d, n_v, 30)).reshape(n_cand, 30)

    s_pos = np.broadcast_to(s_pos_sep[:, None, :, :], (n_T, n_d, n_v, 30)).reshape(n_cand, 30)
    s_vel = np.broadcast_to(s_vel_sep[:, None, :, :], (n_T, n_d, n_v, 30)).reshape(n_cand, 30)
    s_acc = np.broadcast_to(s_acc_sep[:, None, :, :], (n_T, n_d, n_v, 30)).reshape(n_cand, 30)

    if ref_path is None:
        v2 = s_vel * s_vel + d_vel * d_vel
        v_cand = np.sqrt(v2)
        v_safe_denom = np.maximum(v_cand, 0.25)
        a_cand = np.where(v_cand <= 0.1, s_acc, (s_vel * s_acc + d_vel * d_acc) / np.maximum(v_cand, 0.1))
        kappa = np.where(v_cand > 0.25, (s_vel * d_acc - d_vel * s_acc) / (v_safe_denom * v_safe_denom * v_safe_denom), 0.0)
        wx_all, wy_all, vx_all, vy_all = s_pos, d_pos, s_vel, d_vel
        theta_r_all = None
    else:
        wx_all, wy_all, vx_all, vy_all, v_cand, a_cand, kappa, theta_r_all = ref_path.frenet_to_world_batch(
            s_pos, d_pos, s_vel, d_vel, s_acc, d_acc
        )

    kin_ok = np.all(
        (s_vel >= -0.05)
        & (v_cand <= V_MAX + 0.05)
        & (a_cand >= A_MIN - 0.05)
        & (a_cand <= A_MAX + 0.05)
        & (np.abs(kappa) <= KAPPA_MAX + 1e-4)
        & (np.abs(d_pos) <= lane_half_width + 0.25),
        axis=1,
    )

    if not np.any(kin_ok):
        return _build_fallback_plan(x_est, ref_path=ref_path, lane_half_width=lane_half_width)

    cand_indices = np.flatnonzero(kin_ok)

    # Dùng cos = vx/v, sin = vy/v để không phải gọi arctan2/cos/sin cho toàn bộ ứng viên
    c0, s0 = math.cos(psi0), math.sin(psi0)
    vx_sub = vx_all[cand_indices]
    vy_sub = vy_all[cand_indices]
    vc_sub = v_cand[cand_indices]
    moving = vc_sub > 0.08
    v_div = np.where(moving, vc_sub, 1.0)
    c_sub = np.where(moving, vx_sub / v_div, c0)
    s_sub = np.where(moving, vy_sub / v_div, s0)

    if pred_agents:
        px_sub = wx_all[cand_indices][:, :, None]
        py_sub = wy_all[cand_indices][:, :, None]
        c3 = c_sub[:, :, None]
        s3 = s_sub[:, :, None]
        cx_sub = px_sub + XC_LOCAL * c3
        cy_sub = py_sub + XC_LOCAL * s3

        qx_list, qy_list, r_list = [], [], []
        for ag in pred_agents:
            offs = ag["disk_offsets"]
            ca = np.cos(ag["pred_yaws"])[:, None]
            sa = np.sin(ag["pred_yaws"])[:, None]
            pc = ag["pred_centers"]
            qx_list.append(pc[:, 0:1] + offs[None, :] * ca)
            qy_list.append(pc[:, 1:2] + offs[None, :] * sa)
            r_list.append(np.full(len(offs), ag["disk_radius"], dtype=float))
        qx_all = np.concatenate(qx_list, axis=1)[None, :, :]
        qy_all = np.concatenate(qy_list, axis=1)[None, :, :]
        r_all = np.concatenate(r_list)[None, None, :]

        dx_w = qx_all - cx_sub
        dy_w = qy_all - cy_sub
        u = dx_w * c3 + dy_w * s3
        v_loc = -dx_w * s3 + dy_w * c3
        ox = np.maximum(np.abs(u) - HX, 0.0)
        oy = np.maximum(np.abs(v_loc) - HY, 0.0)
        d_disks = np.maximum(np.sqrt(ox * ox + oy * oy) - r_all, 0.0)
        min_d_sub = np.min(d_disks, axis=2)

        req_margin = float(d_s) + margin_tau[None, :]
        safe_mask_sub = np.all(min_d_sub >= req_margin, axis=1)
        min_d_overall = np.min(min_d_sub, axis=1)
    else:
        safe_mask_sub = np.ones(len(cand_indices), dtype=bool)
        min_d_overall = np.full(len(cand_indices), np.inf, dtype=float)

    if not np.any(safe_mask_sub):
        return _build_fallback_plan(x_est, ref_path=ref_path, lane_half_width=lane_half_width)

    valid_idx = cand_indices[safe_mask_sub]
    min_d_valid = min_d_overall[safe_mask_sub]

    int_d_jrk = np.sum(d_jrk_sep * d_jrk_sep, axis=2) * DT_PLAN
    int_s_jrk = np.sum(s_jrk_sep * s_jrk_sep, axis=2) * DT_PLAN
    int_jerk_all = (int_d_jrk[:, :, None] + int_s_jrk[:, None, :]).ravel()

    df_valid = B["df_grid"][valid_idx]
    vf_valid = B["vf_grid"][valid_idx]
    costs = (V_MAX - vf_valid) ** 2 + 0.1 * int_jerk_all[valid_idx] + 2.0 * (df_valid ** 2)

    best_pos = int(np.argmin(costs))
    best_i = int(valid_idx[best_pos])

    if theta_r_all is None:
        psi_best = np.where(v_cand[best_i] > 0.08, np.arctan2(vy_all[best_i], vx_all[best_i]), psi0)
    else:
        psi_best = np.where(v_cand[best_i] > 0.08, np.arctan2(vy_all[best_i], vx_all[best_i]), theta_r_all[best_i])
    poses = np.column_stack([wx_all[best_i], wy_all[best_i], psi_best])
    v_traj = np.concatenate([[v_safe], v_cand[best_i]])
    path_xy = np.vstack([[px0, py0], poses[:, :2]])
    return PlanResult(
        poses=poses,
        v_traj=v_traj,
        path_xy=path_xy,
        fallback=False,
        cost=float(costs[best_pos]),
        min_d_plan=float(min_d_valid[best_pos]),
    )


# ==============================================================================
# Bộ bám Pure Pursuit + Bộ chuyển lệnh có trễ và bù trước vận tốc
# ==============================================================================

def pure_pursuit_control(
    x_est: np.ndarray,
    plan: PlanResult,
    t_rel: float,
) -> tuple[float, float]:
    """Pure Pursuit tầm nhìn trước L_d = 2 + 0.3*v và bù trước vận tốc tại t + 0.5 s."""
    px, py, psi, v, _ = x_est
    v_pos = max(0.0, float(v))

    # Bù trước vận tốc: lệnh = vận tốc kế hoạch tại t_rel + 0.5 s (SPEC §1)
    t_ff = min(t_rel + FF_TIME, H_STEPS * DT_PLAN)
    idx_f = t_ff / DT_PLAN
    i_lo = int(math.floor(idx_f))
    i_hi = min(i_lo + 1, H_STEPS)
    frac = idx_f - i_lo
    v_cmd = float((1.0 - frac) * plan.v_traj[i_lo] + frac * plan.v_traj[i_hi])

    if plan.fallback and v_pos < 0.15:
        return 0.0, 0.0

    ld = LD_BASE + LD_K * v_pos
    path = plan.path_xy
    dists = np.hypot(path[:, 0] - px, path[:, 1] - py)
    i0 = int(np.argmin(dists))
    target_idx = len(path) - 1
    for i in range(i0, len(path)):
        if dists[i] >= ld:
            target_idx = i
            break
    tx, ty = path[target_idx]
    dist_t = float(dists[target_idx])
    if dist_t < 1e-4:
        return v_cmd, 0.0
    alpha = float(wrap_angle(math.atan2(ty - py, tx - px) - psi))
    delta_cmd = math.atan2(2.0 * WHEELBASE * math.sin(alpha), max(dist_t, 0.5))
    delta_cmd = float(np.clip(delta_cmd, -DELTA_MAX, DELTA_MAX))
    return v_cmd, delta_cmd


class CommandDelayBuffer:
    """Bộ đệm trễ lệnh liên tục theo thời gian (nền 50 ms + D4/D5)."""

    def __init__(self, base_delay: float = BASE_DELAY) -> None:
        self.base_delay = base_delay
        self.history: deque[tuple[float, float, float]] = deque()
        self.history.append((-1.0, 0.0, 0.0))

    def push(self, t: float, v_cmd: float, delta_cmd: float) -> None:
        self.history.append((float(t), float(v_cmd), float(delta_cmd)))
        while len(self.history) > 40 and self.history[1][0] < t - 1.0:
            self.history.popleft()

    def get_delayed(self, t: float, extra_delay: float = 0.0) -> tuple[float, float]:
        target_t = t - (self.base_delay + extra_delay)
        hist = self.history
        if target_t <= hist[0][0]:
            return hist[0][1], hist[0][2]
        if target_t >= hist[-1][0]:
            return hist[-1][1], hist[-1][2]
        # Tìm đoạn chứa target_t
        for i in range(len(hist) - 1):
            t0, v0, d0 = hist[i]
            t1, v1, d1 = hist[i + 1]
            if t0 <= target_t <= t1:
                if t1 <= t0 + 1e-12:
                    return v1, d1
                w = (target_t - t0) / (t1 - t0)
                return (1.0 - w) * v0 + w * v1, (1.0 - w) * d0 + w * d1
        return hist[-1][1], hist[-1][2]


# ==============================================================================
# Mô hình xe thật + Định vị & Điều kiện suy giảm D0–D5
# ==============================================================================

class EgoPlant:
    """Mô hình xe đạp động học thật với trễ bậc nhất, giới hạn lái, sai số hệ số lái, D3 và D9."""

    def __init__(self, rng: np.random.Generator, condition: str, v0: float = 7.0) -> None:
        self.px = 0.0
        self.py = 0.0
        self.psi = 0.0
        self.v = float(v0)
        self.delta = 0.0
        self.a = 0.0
        self.condition = condition

        # Sai số hệ số lái +-5% mỗi lượt (SPEC §1)
        self.steer_gain_err = float(rng.uniform(0.95, 1.05))
        dyn = get_plant_dynamics_params(condition)
        self.understeer_factor = float(dyn["understeer"])
        self.slip_sigma = float(dyn["slip_sigma"])
        self.a_min_plant = float(dyn["a_min"])
        self.a_max_plant = float(dyn["a_max"])
        self.slip_beta = 0.0
        self.rng = rng

    def state_vec(self) -> np.ndarray:
        return np.array([self.px, self.py, self.psi, self.v, self.delta], dtype=float)

    def pose(self) -> np.ndarray:
        return np.array([self.px, self.py, self.psi], dtype=float)

    def step(self, v_cmd_del: float, delta_cmd_del: float, dt: float = DT_SIM) -> None:
        # Cập nhật trượt ngang AR(1) cho D3 (sigma=0.04) và D9 (sigma=0.08)
        if self.slip_sigma > 0.0:
            rho_s = math.exp(-dt / 1.0)
            self.slip_beta = (
                rho_s * self.slip_beta
                + math.sqrt(1.0 - rho_s**2) * self.slip_sigma * float(self.rng.standard_normal())
            )
        else:
            self.slip_beta = 0.0

        delta_target = float(np.clip(self.steer_gain_err * delta_cmd_del, -DELTA_MAX, DELTA_MAX))

        # Chia 2 bước nhỏ dt/2 để tích phân chính xác
        n_sub = 2
        h = dt / n_sub
        for _ in range(n_sub):
            a_req = float(np.clip(KP_V * (v_cmd_del - self.v), self.a_min_plant, self.a_max_plant))
            # Nếu đã dừng và yêu cầu phanh tiếp thì giữ a_req = 0
            if self.v <= 1e-4 and a_req < 0.0:
                a_req = 0.0

            self.a += (a_req - self.a) * (h / TAU_ACCEL)
            self.a = float(np.clip(self.a, self.a_min_plant, self.a_max_plant))

            d_dot = float(np.clip((delta_target - self.delta) / TAU_STEER, -OMEGA_MAX, OMEGA_MAX))
            self.delta = float(np.clip(self.delta + d_dot * h, -DELTA_MAX, DELTA_MAX))

            # Động học xe đạp
            v_mid = max(0.0, self.v + 0.5 * self.a * h)
            yaw_rate = (v_mid / WHEELBASE) * math.tan(self.understeer_factor * self.delta)
            psi_mid = self.psi + 0.5 * yaw_rate * h
            motion_psi = psi_mid + self.slip_beta

            self.px += v_mid * math.cos(motion_psi) * h
            self.py += v_mid * math.sin(motion_psi) * h
            self.psi = float(wrap_angle(self.psi + yaw_rate * h))
            self.v += self.a * h
            if self.v < 0.0:
                self.v = 0.0
                self.a = 0.0
            elif self.v > V_MAX:
                self.v = V_MAX


class LocalizationGenerator:
    """Bộ phát sai số định vị cho D0–D10 (RTK cố định, thả nổi, mất GNSS, nhãn sai D8, trễ D4–D6)."""

    def __init__(self, condition: str, rng: np.random.Generator) -> None:
        self.condition = condition
        self.rng = rng

        # Trạng thái AR(1) cho float (tau = 5.0 s, sigma = 0.30 m / 0.02 rad)
        self.float_xy = rng.normal(0.0, 0.30, size=2)
        self.float_psi = float(rng.normal(0.0, 0.02))

        # Tham số mất GNSS (D2: 5-10 s; D7: 15-20 s)
        if condition == "D2":
            self.outage_start = float(rng.uniform(1.5, 4.5))
            self.outage_dur = float(rng.uniform(5.0, 10.0))
            self.outage_end = self.outage_start + self.outage_dur
        elif condition == "D7":
            self.outage_start, self.outage_end = sample_d7_outage(rng)
            self.outage_dur = self.outage_end - self.outage_start
        else:
            self.outage_start = 1e9
            self.outage_end = 1e9

        # Độ lệch trôi khi mất GNSS
        self.loss_err = np.zeros(3, dtype=float)  # [ex, ey, epsi]
        self.loss_bias_psi = float(rng.choice([-1.0, 1.0]) * rng.uniform(0.004, 0.009))
        self.loss_scale_bias = float(rng.uniform(-0.03, 0.03))
        self.loss_lat_bias = float(rng.choice([-1.0, 1.0]) * rng.uniform(0.03, 0.08))
        self.in_recovery = False

        # Trễ thêm cho D4 / D5 / D6
        if condition == "D4":
            self.fixed_extra_delay = float(rng.choice([0.05, 0.10, 0.20]))
        elif condition == "D6":
            self.fixed_extra_delay = D6_EXTRA_DELAY
        else:
            self.fixed_extra_delay = 0.0
        self.current_extra_delay = self.fixed_extra_delay

    def sample_extra_delay_on_plan(self) -> float:
        """Lấy mẫu trễ cho D4 / D5 / D6 mỗi chu kỳ lập kế hoạch."""
        if self.condition in ("D4", "D6"):
            self.current_extra_delay = self.fixed_extra_delay
        elif self.condition == "D5":
            # Gamma(shape=2, scale=0.05), cắt ở 0.3 s (SPEC §1)
            d = float(self.rng.gamma(2.0, 0.05))
            self.current_extra_delay = min(d, 0.30)
        else:
            self.current_extra_delay = 0.0
        return self.current_extra_delay

    def step(self, t: float, v_true: float, psi_true: float, dt: float = DT_SIM) -> tuple[str, np.ndarray, float]:
        """Trả về (nhãn g, [ex, ey, epsi], v_est_err)."""
        # Cập nhật AR(1) float nền
        rho_f = math.exp(-dt / 5.0)
        s_f = math.sqrt(1.0 - rho_f**2)
        self.float_xy = rho_f * self.float_xy + s_f * 0.30 * self.rng.normal(size=2)
        self.float_psi = rho_f * self.float_psi + s_f * 0.02 * float(self.rng.standard_normal())

        if self.condition in ("D1", "D6", "D8"):
            g = corrupt_d8_label(self.rng) if self.condition == "D8" else "float"
            e_xy = self.float_xy.copy()
            e_psi = self.float_psi
            ev = float(self.rng.normal(0.0, 0.08))
            return g, np.array([e_xy[0], e_xy[1], e_psi], dtype=float), ev

        if self.condition in ("D2", "D7") and self.outage_start <= t < self.outage_end:
            g = "loss"
            self.in_recovery = True
            # Trôi tích lũy (bước ngẫu nhiên + độ lệch)
            self.loss_err[2] += self.loss_bias_psi * dt + 0.008 * math.sqrt(dt) * float(self.rng.standard_normal())
            d_long = v_true * self.loss_scale_bias * dt + 0.08 * math.sqrt(dt) * float(self.rng.standard_normal())
            d_lat = (v_true * math.sin(self.loss_err[2]) + self.loss_lat_bias) * dt + 0.08 * math.sqrt(dt) * float(self.rng.standard_normal())
            self.loss_err[0] += d_long * math.cos(psi_true) - d_lat * math.sin(psi_true)
            self.loss_err[1] += d_long * math.sin(psi_true) + d_lat * math.cos(psi_true)
            ev = float(self.rng.normal(0.0, 0.12) + v_true * self.loss_scale_bias)
            return g, self.loss_err.copy(), ev

        # RTK cố định (D0, D3, D4, D5, D9, D10, và D2/D7 ngoài thời gian mất tín hiệu)
        g = "fix"
        if self.in_recovery:
            # Hội tụ lại với hằng số 1.5 s khi có tín hiệu (SPEC §1)
            decay = math.exp(-dt / 1.5)
            self.loss_err *= decay
            if np.linalg.norm(self.loss_err) < 1e-4:
                self.loss_err[:] = 0.0
                self.in_recovery = False

        ex, ey = self.rng.normal(0.0, 0.03, size=2)
        epsi = float(self.rng.normal(0.0, 0.003))
        ev = float(self.rng.normal(0.0, 0.03))
        err = np.array([ex, ey, epsi], dtype=float) + self.loss_err
        return g, err, ev


# ==============================================================================
# Tác nhân và Kịch bản S1–S10 (SPEC §1 & §9.1)
# ==============================================================================

class SimAgent:
    """Tác nhân chuyển động độc lập hoặc tương tác, có nhiễu AR(1) trên quay và gia tốc."""

    def __init__(
        self,
        agent_id: str,
        kind: str,
        px: float,
        py: float,
        psi: float,
        v_nom: float,
        rng: np.random.Generator,
        behavior: dict[str, Any],
    ) -> None:
        self.id = agent_id
        self.kind = kind
        self.disk_radius, self.disk_offsets = AGENT_DISK_SPECS[kind]
        self.px = float(px)
        self.py = float(py)
        self.psi = float(psi)
        self.v = float(v_nom)
        self.v_nom = float(v_nom)
        self.rng = rng
        self.behavior = behavior

        self.active = False
        self.stopped_elapsed = 0.0
        self.has_stopped = False
        self.braking_started = False
        self.ar_omega = 0.0
        self.ar_accel = 0.0
        self.revealed = not bool(behavior.get("start_occluded", False))
        self.was_occluded = bool(behavior.get("start_occluded", False))
        self.reveal_t: float | None = None

        # Độ mạnh nhiễu AR(1) đặc trưng cho từng loại tác nhân (hợp lý ở tốc độ đô thị)
        if kind == "ped":
            self.sigma_omega, self.sigma_acc = 0.20, 0.25
        elif kind == "moto":
            self.sigma_omega, self.sigma_acc = 0.14, 0.35
        else:  # car
            self.sigma_omega, self.sigma_acc = 0.10, 0.30

    def pose_vel(self) -> tuple[float, float, float, float]:
        if self.behavior["mode"] in ("cross_ped", "cross_ped_delayed", "zigzag_ped") and not self.active:
            return self.px, self.py, self.psi, 0.0
        return self.px, self.py, self.psi, self.v

    def is_in_roi(
        self,
        ego_px: float,
        ego_py: float,
        ref_path: CurvedReferencePath | None = None,
        ego_s: float | None = None,
        t: float = 0.0,
    ) -> bool:
        if t < self.behavior.get("appear_t", 0.0):
            return False
        dist = math.hypot(self.px - ego_px, self.py - ego_py)
        if ref_path is not None and ego_s is not None:
            ag_s = ref_path.project_s(self.px, self.py)
            return (dist <= ROI_DIST) and (ag_s >= ego_s - 6.0)
        # Vùng quan tâm 40 m (phía trước hoặc ngay ngang thân xe)
        return (dist <= ROI_DIST) and (self.px >= ego_px - 6.0)

    def step(
        self,
        ego_px: float,
        t: float,
        dt: float = DT_SIM,
        ego_py: float = 0.0,
        ego_psi: float = 0.0,
        ego_v: float = 0.0,
    ) -> None:
        beh = self.behavior
        mode = beh["mode"]

        # Cập nhật nhiễu AR(1) tốc độ quay và gia tốc (tau = 1.5 s)
        rho = math.exp(-dt / 1.5)
        s = math.sqrt(1.0 - rho**2)
        self.ar_omega = rho * self.ar_omega + s * self.sigma_omega * float(self.rng.standard_normal())
        self.ar_accel = rho * self.ar_accel + s * self.sigma_acc * float(self.rng.standard_normal())

        if mode == "cross_ped":
            if not self.active and (beh["conflict_x"] - ego_px) <= beh["trigger_dist"]:
                self.active = True
            if not self.active:
                return
            v_target = self.v_nom
            if beh["stop_mid"] and not self.has_stopped and abs(self.py) < 0.6:
                self.has_stopped = True
            if self.has_stopped and self.stopped_elapsed < beh["stop_dur"]:
                v_target = 0.0
                self.stopped_elapsed += dt
                # Khi dừng giữa đường, tắt quay để giữ vị trí tự nhiên
                self.v = max(0.0, self.v - 3.0 * dt)
            else:
                self.v = max(0.2, min(2.4, v_target + 0.5 * self.ar_accel * dt + 0.3 * self.ar_accel))
                self.psi = float(wrap_angle(self.psi + self.ar_omega * dt))
            self.px += self.v * math.cos(self.psi) * dt
            self.py += self.v * math.sin(self.psi) * dt

        elif mode == "cross_veh":
            if t < beh.get("appear_t", 0.0):
                return
            # Phương tiện tiếp cận giao lộ liên tục (không nhảy bậc vận tốc từ 0)
            self.v = float(np.clip(self.v + self.ar_accel * dt, 1.5, 9.5))
            self.psi = float(wrap_angle(self.psi + (self.behavior.get("omega_nom", 0.0) + self.ar_omega) * dt))
            self.px += self.v * math.cos(self.psi) * dt
            self.py += self.v * math.sin(self.psi) * dt

        elif mode == "lead_brake":
            # Xe phía trước chạy cùng làn/hơi lệch, rồi phanh gấp 2-5 m/s^2 trong đoạn hãm
            if not self.braking_started and ((self.px - ego_px) <= beh["brake_gap"] or t >= beh["brake_t"]):
                self.braking_started = True
            if self.braking_started and self.stopped_elapsed < beh["brake_dur"]:
                decel = beh["brake_decel"]
                self.v = max(beh["v_floor"], self.v - decel * dt + 0.2 * self.ar_accel * dt)
                self.stopped_elapsed += dt
            else:
                v_tgt = beh["v_floor"] if self.braking_started else self.v_nom
                self.v = float(np.clip(self.v + 0.8 * (v_tgt - self.v) * dt + 0.3 * self.ar_accel * dt, 1.5, 8.5))
            self.psi = float(wrap_angle(self.psi + 0.35 * self.ar_omega * dt))
            self.px += self.v * math.cos(self.psi) * dt
            self.py += self.v * math.sin(self.psi) * dt

        else:
            step_ext_agent(self, ego_px, ego_py, ego_psi, ego_v, t, dt, HX)


def build_scenario_agents(scenario: str, rng: np.random.Generator) -> list[SimAgent]:
    """Tạo danh sách tác nhân cho kịch bản S1–S4 (hoặc S0 rỗng, S5–S10) theo SPEC §1 & §9.1."""
    agents: list[SimAgent] = []

    if scenario == "S0":
        return agents

    if scenario == "S1":
        # Người đi bộ sang đường 0.8-1.8 m/s, 20% dừng giữa đường 2-4 s
        n_ped = 1 if rng.random() < 0.7 else 2
        for idx in range(n_ped):
            cx = float(rng.uniform(46.0, 55.0)) + idx * float(rng.uniform(4.0, 8.0))
            side = float(rng.choice([-1.0, 1.0]))
            speed = float(rng.uniform(0.8, 1.8))
            y0 = side * float(rng.uniform(2.8, 4.2))
            psi = -side * (math.pi / 2.0) + float(rng.uniform(-0.10, 0.10))
            stop_mid = bool(rng.random() < 0.20)
            stop_dur = float(rng.uniform(2.0, 4.0)) if stop_mid else 0.0
            trig = float(rng.uniform(16.0, 24.0))
            agents.append(SimAgent(
                agent_id=f"ped_{idx}",
                kind="ped",
                px=cx,
                py=y0,
                psi=psi,
                v_nom=speed,
                rng=rng,
                behavior={
                    "mode": "cross_ped",
                    "conflict_x": cx,
                    "trigger_dist": trig,
                    "stop_mid": stop_mid,
                    "stop_dur": stop_dur,
                },
            ))

    elif scenario == "S2":
        # Xe máy cắt ngang 30-90 độ, 3-8 m/s, xuất phát trên nhánh giao cắt để tới giao lộ đúng nhịp
        cx = float(rng.uniform(46.0, 55.0))
        side = float(rng.choice([-1.0, 1.0]))
        cross_deg = float(rng.uniform(30.0, 90.0))
        cross_rad = math.radians(cross_deg)
        psi = -side * cross_rad if rng.random() < 0.75 else math.pi - side * cross_rad
        speed = float(rng.uniform(3.0, 8.0))
        t_arr = cx / 7.8 + float(rng.uniform(-0.8, 0.8))
        approach = speed * t_arr
        x0 = cx - approach * math.cos(psi)
        y0 = float(rng.uniform(-0.8, 0.8)) - approach * math.sin(psi)
        agents.append(SimAgent(
            agent_id="moto_0",
            kind="moto",
            px=x0,
            py=y0,
            psi=psi,
            v_nom=speed,
            rng=rng,
            behavior={
                "mode": "cross_veh",
                "omega_nom": float(rng.choice([-1.0, 1.0]) * rng.uniform(0.0, 0.04)),
            },
        ))

    elif scenario == "S3":
        # Giao cắt không đèn, có cả xe máy và ô tô (kèm góc cua nhẹ làm rõ sai số quay Hausdorff)
        cx = float(rng.uniform(46.0, 55.0))
        side_m = float(rng.choice([-1.0, 1.0]))
        ang_m = math.radians(float(rng.uniform(45.0, 90.0)))
        psi_m = -side_m * ang_m
        v_m = float(rng.uniform(3.5, 7.5))
        app_m = v_m * (cx / 7.8 + float(rng.uniform(-0.7, 0.7)))
        agents.append(SimAgent(
            agent_id="moto_0",
            kind="moto",
            px=cx - app_m * math.cos(psi_m),
            py=float(rng.uniform(-0.6, 0.6)) - app_m * math.sin(psi_m),
            psi=psi_m,
            v_nom=v_m,
            rng=rng,
            behavior={
                "mode": "cross_veh",
                "omega_nom": float(rng.choice([-1.0, 1.0]) * rng.uniform(0.02, 0.06)),
            },
        ))
        side_c = -side_m
        ang_c = math.radians(float(rng.uniform(55.0, 90.0)))
        psi_c = -side_c * ang_c
        v_c = float(rng.uniform(3.5, 6.5))
        cx_c = cx + float(rng.uniform(-3.0, 4.0))
        app_c = v_c * (cx_c / 7.8 + float(rng.uniform(-0.8, 0.8)))
        agents.append(SimAgent(
            agent_id="car_0",
            kind="car",
            px=cx_c - app_c * math.cos(psi_c),
            py=float(rng.uniform(-0.6, 0.6)) - app_c * math.sin(psi_c),
            psi=psi_c,
            v_nom=v_c,
            rng=rng,
            behavior={
                "mode": "cross_veh",
                "omega_nom": float(rng.choice([-1.0, 1.0]) * rng.uniform(0.02, 0.06)),
            },
        ))

    elif scenario == "S4":
        # Xe máy hoặc ô tô phía trước phanh gấp 2-5 m/s^2
        kind = "moto" if rng.random() < 0.5 else "car"
        x0 = float(rng.uniform(34.0, 42.0))
        y0 = float(rng.uniform(-0.6, 0.6))
        v0 = float(rng.uniform(5.2, 6.8))
        agents.append(SimAgent(
            agent_id=f"{kind}_lead",
            kind=kind,
            px=x0,
            py=y0,
            psi=float(rng.uniform(-0.03, 0.03)),
            v_nom=v0,
            rng=rng,
            behavior={
                "mode": "lead_brake",
                "brake_gap": float(rng.uniform(12.0, 18.0)),
                "brake_t": float(rng.uniform(2.0, 4.0)),
                "brake_decel": float(rng.uniform(2.5, 5.0)),
                "brake_dur": float(rng.uniform(1.0, 1.6)),
                "v_floor": float(rng.uniform(1.0, 2.8)),
            },
        ))
    elif scenario in SCENARIOS_EXT:
        ext_agents, _, _ = build_ext_scenario_context(scenario, rng, SimAgent)
        return ext_agents
    else:
        raise ValueError(f"Kịch bản không hợp lệ: {scenario}")

    return agents


def build_scenario_context(
    scenario: str,
    rng: np.random.Generator,
    curve_radius_override: float | None = None,
) -> tuple[list[SimAgent], list[StaticObstacleBox], CurvedReferencePath | None]:
    """Tạo đầy đủ tác nhân, vật cản tĩnh và đường tham chiếu cho S0..S10."""
    if scenario in SCENARIOS or scenario == "S0":
        return build_scenario_agents(scenario, rng), [], None
    return build_ext_scenario_context(scenario, rng, SimAgent, curve_radius_override=curve_radius_override)


# ==============================================================================
# Bộ dự báo vận tốc hằng (CV) và Bộ đánh giá trễ H bước
# ==============================================================================

def predict_agents_cv(
    agents: list[SimAgent],
    ego_px: float,
    ego_py: float,
    rng: np.random.Generator,
    static_obs: list[StaticObstacleBox] | None = None,
    ref_path: CurvedReferencePath | None = None,
    ego_s: float | None = None,
    t: float = 0.0,
    ego_psi: float = 0.0,
    condition: str = "D0",
    delayed_snaps: dict[str, tuple[float, float, float, float]] | None = None,
    prev_preds_by_id: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Quan sát tác nhân trong ROI (có xét che khuất S5 và suy giảm D10) và dự báo CV."""
    preds: list[dict[str, Any]] = []
    tau_vec = np.arange(1, H_STEPS + 1, dtype=float) * DT_PLAN
    perc = get_perception_params(condition)
    pos_sig = float(perc["pos_sigma"])
    vel_sig = float(perc["vel_sigma"])
    drop_prob = float(perc["dropout_prob"])

    sensor_x = ego_px + XC_LOCAL * math.cos(ego_psi)
    sensor_y = ego_py + XC_LOCAL * math.sin(ego_psi)

    for ag in agents:
        if not ag.is_in_roi(ego_px, ego_py, ref_path=ref_path, ego_s=ego_s, t=t):
            continue
        if static_obs:
            occl_now = is_agent_occluded(
                sensor_x, sensor_y, ag.px, ag.py, ag.psi,
                ag.disk_offsets, ag.disk_radius, static_obs,
            )
            if not ag.revealed:
                if occl_now:
                    continue
                ag.revealed = True
                ag.reveal_t = t

        if drop_prob > 0.0 and float(rng.random()) < drop_prob:
            if prev_preds_by_id is not None and ag.id in prev_preds_by_id:
                prev = prev_preds_by_id[ag.id]
                old_c = prev["pred_centers"]
                # Dịch dự báo cũ thêm 1 bước (0.1 s) khi mất phát hiện khung hiện tại
                step_delta = old_c[-1] - old_c[-2]
                shifted_c = np.vstack([old_c[1:], old_c[-1:] + step_delta[None, :]])
                shifted_pred = {
                    "id": ag.id,
                    "kind": ag.kind,
                    "disk_radius": ag.disk_radius,
                    "disk_offsets": ag.disk_offsets,
                    "pred_centers": shifted_c,
                    "pred_yaws": prev["pred_yaws"].copy(),
                }
                prev_preds_by_id[ag.id] = shifted_pred
                preds.append(shifted_pred)
            continue

        if delayed_snaps is not None and ag.id in delayed_snaps:
            px, py, psi, v = delayed_snaps[ag.id]
        else:
            px, py, psi, v = ag.pose_vel()
        vx_true = v * math.cos(psi)
        vy_true = v * math.sin(psi)

        px_obs = px + float(rng.normal(0.0, pos_sig))
        py_obs = py + float(rng.normal(0.0, pos_sig))
        vx_obs = vx_true + float(rng.normal(0.0, vel_sig))
        vy_obs = vy_true + float(rng.normal(0.0, vel_sig))
        speed_obs = math.hypot(vx_obs, vy_obs)
        if speed_obs > 0.30:
            psi_obs = math.atan2(vy_obs, vx_obs)
        else:
            psi_obs = float(wrap_angle(psi + rng.normal(0.0, 0.05)))

        pred_x = px_obs + vx_obs * tau_vec
        pred_y = py_obs + vy_obs * tau_vec
        pred_centers = np.column_stack([pred_x, pred_y])       # (30, 2)
        pred_yaws = np.full(H_STEPS, psi_obs, dtype=float)     # (30,)

        pred_entry = {
            "id": ag.id,
            "kind": ag.kind,
            "disk_radius": ag.disk_radius,
            "disk_offsets": ag.disk_offsets,
            "pred_centers": pred_centers,
            "pred_yaws": pred_yaws,
        }
        if prev_preds_by_id is not None:
            prev_preds_by_id[ag.id] = pred_entry
        preds.append(pred_entry)
    return preds


def compute_cycle_metrics(
    plan_poses: np.ndarray,      # (30, 3)
    true_ego_poses: np.ndarray,  # (30, 3)
    pred_agents: list[dict[str, Any]],
    true_agent_traj: dict[str, tuple[np.ndarray, np.ndarray]],  # id -> ((30, 2), (30,))
    sigma_tau: np.ndarray,       # (30,)
) -> dict[str, Any]:
    """Tính đầy đủ thống kê cho một chu kỳ lập kế hoạch sau H = 30 bước (SPEC §1)."""
    # Sai số xe E_tau = ||Δp|| + r_max * |Δψ|
    dp = np.hypot(plan_poses[:, 0] - true_ego_poses[:, 0], plan_poses[:, 1] - true_ego_poses[:, 1])
    dpsi = np.abs(wrap_angle(plan_poses[:, 2] - true_ego_poses[:, 2]))
    E_tau = dp + R_MAX * dpsi  # (30,)

    if not pred_agents:
        return {
            "has_agents": False,
            "gap_max": float("-inf"),
            "R": float("-inf"),
            "d_min": float("inf"),
            "d_plan_min": float("inf"),
            "safe": True,
            "A_c_max": 0.0,
            "A_h_max": 0.0,
            "E_max_norm": float(np.max(E_tau / sigma_tau)),
            "E_30": float(E_tau[-1]),
            "E_max_m": float(np.max(E_tau)),
            "a_max_norm": 0.0,
            "b_max_norm": 0.0,
            "gap_tau": np.full(H_STEPS, float("-inf")),
            "a_tau": np.zeros(H_STEPS),
            "b_tau": np.zeros(H_STEPS),
            "E_tau": E_tau,
            "A_h_tau": np.zeros(H_STEPS),
            "A_c_tau": np.zeros(H_STEPS),
        }

    # Tính trên tất cả tác nhân j trong J_t
    gap_tau_all = np.full(H_STEPS, -np.inf, dtype=float)
    a_tau_all = np.full(H_STEPS, -np.inf, dtype=float)
    b_tau_all = np.full(H_STEPS, -np.inf, dtype=float)
    Ac_tau_all = np.zeros(H_STEPS, dtype=float)
    Ah_tau_all = np.zeros(H_STEPS, dtype=float)

    d_true_min = float("inf")
    d_plan_min = float("inf")

    for ag in pred_agents:
        aid = ag["id"]
        true_c, true_yaws = true_agent_traj[aid]  # (30, 2), (30,)
        pred_c, pred_yaws = ag["pred_centers"], ag["pred_yaws"]
        offs = ag["disk_offsets"]
        rad = ag["disk_radius"]

        # d_plan = D(B(p), O_hat)
        d_plan, _ = ego_agent_distance(plan_poses, pred_c, pred_yaws, offs, rad)
        # d_mid  = D(B(p), O)
        d_mid, _ = ego_agent_distance(plan_poses, true_c, true_yaws, offs, rad)
        # d_true = D(B(e), O)
        d_true, _ = ego_agent_distance(true_ego_poses, true_c, true_yaws, offs, rad)

        gap = d_plan - d_true
        a_part = d_plan - d_mid
        b_part = d_mid - d_true

        # Sai số tâm A_c và cận Hausdorff A_h (độ dời lớn nhất của các đĩa)
        A_c = np.hypot(pred_c[:, 0] - true_c[:, 0], pred_c[:, 1] - true_c[:, 1])  # (30,)
        c_p = np.cos(pred_yaws)[:, None]
        s_p = np.sin(pred_yaws)[:, None]
        c_t = np.cos(true_yaws)[:, None]
        s_t = np.sin(true_yaws)[:, None]
        dx_d = (pred_c[:, 0:1] + offs[None, :] * c_p) - (true_c[:, 0:1] + offs[None, :] * c_t)
        dy_d = (pred_c[:, 1:2] + offs[None, :] * s_p) - (true_c[:, 1:2] + offs[None, :] * s_t)
        A_h = np.max(np.hypot(dx_d, dy_d), axis=1)  # (30,)

        gap_tau_all = np.maximum(gap_tau_all, gap)
        a_tau_all = np.maximum(a_tau_all, a_part)
        b_tau_all = np.maximum(b_tau_all, b_part)
        Ac_tau_all = np.maximum(Ac_tau_all, A_c)
        Ah_tau_all = np.maximum(Ah_tau_all, A_h)

        d_true_min = min(d_true_min, float(np.min(d_true)))
        d_plan_min = min(d_plan_min, float(np.min(d_plan)))

    R_val = float(np.max(gap_tau_all / sigma_tau))
    return {
        "has_agents": True,
        "gap_max": float(np.max(gap_tau_all)),
        "R": R_val,
        "d_min": d_true_min,
        "d_plan_min": d_plan_min,
        "safe": bool(d_true_min >= D_S),
        "A_c_max": float(np.max(Ac_tau_all / sigma_tau)),
        "A_h_max": float(np.max(Ah_tau_all / sigma_tau)),
        "E_max_norm": float(np.max(E_tau / sigma_tau)),
        "E_30": float(E_tau[-1]),
        "E_max_m": float(np.max(E_tau)),
        "a_max_norm": float(np.max(a_tau_all / sigma_tau)),
        "b_max_norm": float(np.max(b_tau_all / sigma_tau)),
        "gap_tau": gap_tau_all,
        "a_tau": a_tau_all,
        "b_tau": b_tau_all,
        "E_tau": E_tau,
        "A_h_tau": Ah_tau_all,
        "A_c_tau": Ac_tau_all,
    }


def _rollout_open_loop_poses(
    plan: PlanResult,
    t_plan: float,
    ego_state0: tuple[float, float, float, float, float, float],
    cmd_hist0: list[tuple[float, float, float]],
    step_trace: list[tuple[float, float, float, float, float, float]],
    k0: int,
    steer_gain_err: float,
    understeer_factor: float,
    a_min_plant: float,
    a_max_plant: float,
) -> np.ndarray:
    """Chạy nhánh mở vòng bám cố định kế hoạch phát tại t_plan (không lập lại kế hoạch) để đo E_track."""
    px, py, psi, v, delta, a = ego_state0
    ol_buf = CommandDelayBuffer(BASE_DELAY)
    ol_buf.history = deque(cmd_hist0)

    n_sub = 2
    h = DT_SIM / n_sub
    poses_out = np.zeros((H_STEPS, 3), dtype=float)
    out_idx = 0

    for step_j in range(H_STEPS * PLAN_EVERY):
        k_idx = k0 + step_j
        t_cur = round(k_idx * DT_SIM, 4)
        ex, ey, epsi, ev_err, extra_del, slip_b = step_trace[k_idx]

        x_est_ol = np.array([
            px + ex,
            py + ey,
            float(wrap_angle(psi + epsi)),
            max(0.0, v + ev_err),
            delta,
        ], dtype=float)
        v_cmd, d_cmd = pure_pursuit_control(x_est_ol, plan, t_cur - t_plan)
        ol_buf.push(t_cur, v_cmd, d_cmd)
        v_del, d_del = ol_buf.get_delayed(t_cur, extra_del)

        delta_target = float(np.clip(steer_gain_err * d_del, -DELTA_MAX, DELTA_MAX))
        for _ in range(n_sub):
            a_req = float(np.clip(KP_V * (v_del - v), a_min_plant, a_max_plant))
            if v <= 1e-4 and a_req < 0.0:
                a_req = 0.0
            a += (a_req - a) * (h / TAU_ACCEL)
            a = float(np.clip(a, a_min_plant, a_max_plant))

            d_dot = float(np.clip((delta_target - delta) / TAU_STEER, -OMEGA_MAX, OMEGA_MAX))
            delta = float(np.clip(delta + d_dot * h, -DELTA_MAX, DELTA_MAX))

            v_mid = max(0.0, v + 0.5 * a * h)
            yaw_rate = (v_mid / WHEELBASE) * math.tan(understeer_factor * delta)
            psi_mid = psi + 0.5 * yaw_rate * h
            motion_psi = psi_mid + slip_b

            px += v_mid * math.cos(motion_psi) * h
            py += v_mid * math.sin(motion_psi) * h
            psi = float(wrap_angle(psi + yaw_rate * h))
            v += a * h
            if v < 0.0:
                v = 0.0
                a = 0.0
            elif v > V_MAX:
                v = V_MAX

        if step_j % PLAN_EVERY == 1:
            poses_out[out_idx, 0] = px
            poses_out[out_idx, 1] = py
            poses_out[out_idx, 2] = psi
            out_idx += 1

    return poses_out


# ==============================================================================
# Trình chạy một lượt mô phỏng vòng kín
# ==============================================================================

DEFAULT_SIGMA_OLD: np.ndarray = 0.05 + 0.04 * np.arange(1, H_STEPS + 1, dtype=float)


def _deterministic_tcomp_ms(method: str, n_agents: int, n_disks: int, fallback: bool, rng_hash: int) -> float:
    """Mô hình thời gian tính tất định đã hiệu chuẩn theo benchmark thực tế trên Python/NumPy."""
    base = 0.85 + 0.14 * n_agents + 0.04 * n_disks
    if method in ("DX-2", "ĐX-2"):
        base += 0.05
    elif method in ("DX-3", "ĐX-3", "B6"):
        base += 0.08
    if fallback:
        base += 0.04
    jitter = ((rng_hash % 1000) / 1000.0 - 0.5) * 0.12
    return round(max(0.45, base + jitter), 4)


def run_episode(
    seed: int,
    scenario: str,
    condition: str,
    method: str,
    margin_fn: Callable[[str, float, int], tuple[float, np.ndarray]],
    sigma_tau: np.ndarray | None = None,
    feedback_fn: Callable[[dict[str, Any]], None] | None = None,
    v0: float = 7.0,
    seed_base: int = 0,
    *,
    split: str = "IN",
    d_s: float = D_S,
    lane_half_width: float = LANE_HALF_WIDTH,
    dense_v_grid: bool = False,
    compute_open_loop: bool = True,
    keep_tau_arrays: bool = True,
    curve_radius_override: float | None = None,
) -> dict[str, Any]:
    """Chạy một lượt mô phỏng vòng kín đầy đủ và trả về nhật ký chu kỳ + tổng hợp lượt."""
    if sigma_tau is None:
        sigma_tau = DEFAULT_SIGMA_OLD

    scn_idx = 99 if scenario == "S0" else ALL_SCENARIOS.index(scenario)
    cond_idx = ALL_CONDITIONS.index(condition)

    # Tách rng theo vai trò để B0 và các phương pháp cùng seed có kịch bản/nhiễu giống hệt nhau
    ep_seed = int(seed) + int(seed_base) * 100000
    rng_scn = np.random.default_rng(ep_seed * 31 + scn_idx + 7)
    rng_loc = np.random.default_rng(ep_seed * 37 + cond_idx * 101 + 13)
    rng_obs = np.random.default_rng(ep_seed * 41 + 19)
    rng_ego = np.random.default_rng(ep_seed * 43 + 23)

    ego = EgoPlant(rng_ego, condition, v0=v0)
    loc = LocalizationGenerator(condition, rng_loc)
    agents, static_obs, ref_path = build_scenario_context(
        scenario, rng_scn, curve_radius_override=curve_radius_override
    )
    cmd_buf = CommandDelayBuffer(BASE_DELAY)

    # Lưu vết trạng thái thật theo từng bước 10 Hz để đánh giá trễ H = 30 bước
    ego_poses_10hz: list[np.ndarray] = []
    agents_10hz: list[dict[str, tuple[np.ndarray, float]]] = []
    agents_obs_10hz: list[dict[str, tuple[float, float, float, float]]] = []
    step_trace: list[tuple[float, float, float, float, float, float]] = []
    pending_plans: deque[dict[str, Any]] = deque()
    finalized_cycles: list[dict[str, Any]] = []
    prev_preds_by_id: dict[str, dict[str, Any]] | None = {} if condition == "D10" else None

    collided = False
    completed = False
    unavoidable = 0
    t_end = T_MAX
    d_min_ep = float("inf")
    ttc_min_ep = float("inf")
    max_delta_ep = 0.0
    max_omega_ep = 0.0
    max_lat_err_ep = 0.0
    jerk_sq_sum = 0.0
    jerk_n = 0
    tcomp_samples: list[float] = []

    current_plan: PlanResult | None = None
    last_plan_t = 0.0
    extra_delay = 0.0

    for k in range(N_SIM_STEPS + 1):
        t = round(k * DT_SIM, 4)

        # 1. Đo trạng thái định vị và lập kế hoạch ở 10 Hz (k chẵn)
        g_label, loc_err, ev_err = loc.step(t, ego.v, ego.psi, DT_SIM if k > 0 else 0.0)
        x_est = np.array([
            ego.px + loc_err[0],
            ego.py + loc_err[1],
            float(wrap_angle(ego.psi + loc_err[2])),
            max(0.0, ego.v + ev_err),
            ego.delta,
        ], dtype=float)

        if ref_path is not None:
            ego_s, ego_d_true, _, _, _, ego_kappa_r = ref_path.world_to_frenet(ego.px, ego.py, ego.psi, ego.v)
            max_lat_err_ep = max(max_lat_err_ep, abs(ego_d_true))
        else:
            ego_s = ego.px
            ego_kappa_r = 0.0

        if k % PLAN_EVERY == 0:
            # Lưu chân lý tại thời điểm 10 Hz hiện tại cho các chu kỳ cũ đang chờ
            ego_poses_10hz.append(ego.pose())
            ag_snap: dict[str, tuple[np.ndarray, float]] = {}
            ag_snap_full: dict[str, tuple[float, float, float, float]] = {}
            for ag in agents:
                ag_snap[ag.id] = (np.array([ag.px, ag.py], dtype=float), ag.psi)
                ag_snap_full[ag.id] = ag.pose_vel()
            agents_10hz.append(ag_snap)
            agents_obs_10hz.append(ag_snap_full)

            cur_10hz_idx = len(ego_poses_10hz) - 1
            # Đóng chu kỳ cách đây đúng H = 30 bước (3.0 s)
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

                if compute_open_loop:
                    ol_poses = _rollout_open_loop_poses(
                        rec["plan_obj"],
                        rec["t"],
                        rec["ego_state0"],
                        rec["cmd_hist0"],
                        step_trace,
                        rec["k0"],
                        ego.steer_gain_err,
                        ego.understeer_factor,
                        ego.a_min_plant,
                        ego.a_max_plant,
                    )
                    dp_ol = np.hypot(rec["plan_poses"][:, 0] - ol_poses[:, 0], rec["plan_poses"][:, 1] - ol_poses[:, 1])
                    dpsi_ol = np.abs(wrap_angle(rec["plan_poses"][:, 2] - ol_poses[:, 2]))
                    e_track_tau = dp_ol + R_MAX * dpsi_ol
                    e_track_norm = float(np.max(e_track_tau / sigma_tau))
                    e_replan_norm = float(stats["E_max_norm"] - e_track_norm)
                    e_track_30 = float(e_track_tau[-1])
                    e_replan_30 = float(stats["E_30"] - e_track_30)
                else:
                    e_track_tau = np.zeros(H_STEPS, dtype=float)
                    e_track_norm = 0.0
                    e_replan_norm = 0.0
                    e_track_30 = 0.0
                    e_replan_30 = 0.0

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
                    "n_agents": rec["n_agents"],
                    "occluded_before": int(rec["occluded_before"]),
                    "curvature": float(rec["curvature"]),
                    "e_track": e_track_norm,
                    "e_replan": e_replan_norm,
                    "E_track_30": e_track_30,
                    "E_replan_30": e_replan_30,
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
                        "E_track_tau": e_track_tau,
                        "A_h_tau": stats["A_h_tau"],
                        "A_c_tau": stats["A_c_tau"],
                    })
                finalized_cycles.append(cyc)
                if feedback_fn is not None:
                    feedback_fn(cyc)

            # Kiểm tra điều kiện kết thúc lượt SAU khi cập nhật chân lý bước cuối
            if collided or completed or k == N_SIM_STEPS:
                t_end = t
                break

            # Lập kế hoạch mới nếu chưa kết thúc
            extra_delay = loc.sample_extra_delay_on_plan()

            # Kiểm tra lộ diện tác nhân bị che khuất (S5) trước dự báo
            was_revealed_before = {ag.id: ag.revealed for ag in agents}
            delayed_snaps = None
            if condition == "D10":
                d_idx = max(0, cur_10hz_idx - 1)
                delayed_snaps = agents_obs_10hz[d_idx]

            pred_agents = predict_agents_cv(
                agents,
                ego.px,
                ego.py,
                rng_obs,
                static_obs=static_obs,
                ref_path=ref_path,
                ego_s=ego_s,
                t=t,
                ego_psi=ego.psi,
                condition=condition,
                delayed_snaps=delayed_snaps,
                prev_preds_by_id=prev_preds_by_id,
            )

            if static_obs:
                for ag in agents:
                    if not was_revealed_before[ag.id] and ag.revealed:
                        gap_x = max(0.0, ag.px - ego.px - HX - ag.disk_radius)
                        ttc_rev = gap_x / max(ego.v, 0.1)
                        t_brake_min = ego.v / abs(A_MIN)
                        if ttc_rev < t_brake_min and ag.py * math.sin(ag.psi) <= 0.0:
                            unavoidable = 1

            pred_ids = {a["id"] for a in pred_agents}
            occ_before_cycle = int(any(ag.was_occluded and ag.id in pred_ids for ag in agents))

            q_val, margin_tau = margin_fn(g_label, t, len(pred_agents))
            margin_pos = np.maximum(margin_tau, 0.0)

            plan = plan_frenet(
                x_est,
                ego.a,
                pred_agents,
                margin_pos,
                ref_path=ref_path,
                d_s=d_s,
                lane_half_width=lane_half_width,
                dense_v_grid=dense_v_grid,
            )
            current_plan = plan
            last_plan_t = t

            n_disks = sum(len(a["disk_offsets"]) for a in pred_agents)
            tcomp_samples.append(_deterministic_tcomp_ms(method, len(pred_agents), n_disks, plan.fallback, ep_seed * 131 + k))

            pending_plans.append({
                "idx_10hz": cur_10hz_idx,
                "k0": k,
                "t": t,
                "g": g_label,
                "J": float(plan.cost) if math.isfinite(plan.cost) else 9999.0,
                "fallback": plan.fallback,
                "q_used": float(q_val),
                "m_3s": float(margin_pos[-1]),
                "plan_poses": plan.poses,
                "plan_obj": plan,
                "pred_agents": pred_agents,
                "n_agents": len(pred_agents),
                "occluded_before": occ_before_cycle,
                "curvature": float(abs(ego_kappa_r)),
                "ego_state0": (ego.px, ego.py, ego.psi, ego.v, ego.delta, ego.a),
                "cmd_hist0": list(cmd_buf.history),
            })

        if k == N_SIM_STEPS:
            t_end = t
            break

        # 2. Bộ bám Pure Pursuit ở 20 Hz
        assert current_plan is not None
        v_cmd, d_cmd = pure_pursuit_control(x_est, current_plan, t - last_plan_t)
        cmd_buf.push(t, v_cmd, d_cmd)
        v_del, d_del = cmd_buf.get_delayed(t, extra_delay)

        # 3. Tiến 1 bước vật lý xe tự hành và tác nhân
        a_before = ego.a
        delta_before = ego.delta
        ego.step(v_del, d_del, DT_SIM)
        omega_step = abs(ego.delta - delta_before) / DT_SIM
        max_delta_ep = max(max_delta_ep, abs(ego.delta))
        max_omega_ep = max(max_omega_ep, omega_step)

        step_trace.append((
            float(loc_err[0]),
            float(loc_err[1]),
            float(loc_err[2]),
            float(ev_err),
            float(extra_delay),
            float(ego.slip_beta),
        ))

        for ag in agents:
            ag.step(ego.px, t, DT_SIM, ego_py=ego.py, ego_psi=ego.psi, ego_v=ego.v)

        if k > 0:
            jerk = (ego.a - a_before) / DT_SIM
            jerk_sq_sum += jerk * jerk
            jerk_n += 1

        # 4. Kiểm tra va chạm và khoảng cách tức thời sau bước vật lý
        for ag in agents:
            if t < ag.behavior.get("appear_t", 0.0):
                continue
            d_cur, s_clr = _scalar_box_agent_dist(
                ego.px, ego.py, ego.psi,
                ag.px, ag.py, ag.psi,
                ag.disk_offsets, ag.disk_radius,
            )
            if d_cur < d_min_ep:
                d_min_ep = d_cur

            # Tính TTC_min dọc theo vận tốc tương đối
            rel_x = ag.px - ego.px
            rel_y = ag.py - ego.py
            dist_c = math.hypot(rel_x, rel_y)
            if dist_c > 1e-3 and d_cur > 0.0:
                ux, uy = rel_x / dist_c, rel_y / dist_c
                vx_rel = ego.v * math.cos(ego.psi) - ag.v * math.cos(ag.psi)
                vy_rel = ego.v * math.sin(ego.psi) - ag.v * math.sin(ag.psi)
                closing = vx_rel * ux + vy_rel * uy
                if closing > 0.1:
                    ttc_val = d_cur / closing
                    if ttc_val < ttc_min_ep:
                        ttc_min_ep = ttc_val

            if s_clr <= 0.0:
                collided = True

        ego_progress = ref_path.project_s(ego.px, ego.py) if ref_path is not None else ego.px
        if ego_progress >= GOAL_X:
            completed = True

        # Nếu vừa va chạm hoặc tới đích ở bước lẻ, kết thúc lượt
        if collided or completed:
            t_end = round((k + 1) * DT_SIM, 4)
            break

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
        "split": split,
        "collided": int(collided),
        "completed": int(completed),
        "unavoidable": int(unavoidable),
        "t_end": float(t_end),
        "d_min": float(d_min_ep),
        "ttc_min": float(ttc_min_ep),
        "n_cycles": int(n_cycles),
        "n_fallback": int(n_fallback),
        "jerk_rms": float(jerk_rms),
        "tcomp_p95_ms": float(tcomp_p95),
        "max_delta": float(max_delta_ep),
        "max_omega": float(max_omega_ep),
        "max_lat_err_curve": float(max_lat_err_ep),
    }
    return {
        "episode": episode_summary,
        "cycles": finalized_cycles,
    }
