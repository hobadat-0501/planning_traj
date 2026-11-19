"""Bộ sinh mẫu tổng hợp cho Mục 4.1 (SPEC §10.1, §10.4, §10.5, §10.6).

Mỗi mẫu là một lần lập kế hoạch với một tác nhân trên chân trời H = 30 bước, Δt = 0,1 s.
Hệ trục: gốc tại vị trí xe lúc lập kế hoạch, trục x theo hướng xe.
Mọi mảng quỹ đạo có dạng (n, H, 2), chỉ số bước τ = 1..H ứng với cột 0..H-1.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Sequence

import numpy as np

H = 30
DT = 0.1
TAU = np.arange(1, H + 1, dtype=float)
SIGMA_TAU = 0.05 + 0.04 * TAU  # σ_τ (m), τ = 1..30
R_EGO = 0.52
R_AGENT = 0.35
SEED = 2026

# Mã thí nghiệm dùng trong spawn_key (SPEC §10.6).
EXP_IDS = {"N1": 1, "N2": 2, "N2rho": 3, "N3": 4, "N2S": 5, "TEST": 99}
SPLIT_CAL, SPLIT_TEST = 0, 1

# Nhóm định vị cho N3 (SPEC §10.5).
GROUP_NAMES = ("fix", "float", "loss")
GROUP_SIGMA = np.array([0.03, 0.30, 1.00])
GROUP_PROBS = np.array([0.7, 0.2, 0.1])


@dataclass(frozen=True)
class GenParams:
    """Tham số mô hình sinh. Mặc định đúng SPEC §10.1; các trường [GĐ] ghi rõ."""

    v_min: float = 0.8
    v_max: float = 2.0
    tc_loc: float = 5.0          # [GĐ U1] hằng số thời gian trôi định vị (s)
    loc_drift: bool = True       # [GĐ U1] False: nhiễu trắng độc lập từng bước (biến thể N2-S)
    sigma_trk: float = 0.05      # [GĐ U2] độ lệch chuẩn dừng của sai số bám (m)
    tc_trk: float = 1.0          # [GĐ U2] hằng số thời gian sai số bám (s)
    delay_max: float = 0.15      # trễ δ ~ U(0; delay_max) (s)
    x0_min: float = 3.0
    x0_max: float = 8.0
    y0_abs: float = 4.0
    xc_min: float = 0.0          # [GĐ U5] điểm đích trên đường xe
    xc_max: float = 6.0
    s0_min: float = 0.8
    s0_max: float = 3.0
    sigma_omega: float = 0.25    # rad/s
    sigma_acc: float = 0.4       # m/s²
    motion: str = "const"        # [GĐ U6] "const" (U6-A) hoặc "per_step" (U6-B)

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_PARAMS = GenParams()


@dataclass
class Batch:
    """Một lô mẫu: kế hoạch / thực của xe, dự báo / thực của tác nhân."""

    p_hat: np.ndarray   # (n, H, 2) kế hoạch xe
    p: np.ndarray       # (n, H, 2) tư thế thực của xe
    o_hat: np.ndarray   # (n, H, 2) dự báo tác nhân
    o: np.ndarray       # (n, H, 2) vị trí thực của tác nhân
    sigma_loc: np.ndarray  # (n,) σ_loc của từng mẫu
    group: np.ndarray | None = None  # (n,) chỉ số nhóm 0/1/2 (chỉ ở chế độ trộn nhóm)

    @property
    def n(self) -> int:
        return int(self.p.shape[0])


def make_rng(exp: str, cell_id: int, rep: int, split: int, seed: int = SEED) -> np.random.Generator:
    """Luồng ngẫu nhiên độc lập cho (thí nghiệm, ô, lần lặp, tập) — SPEC §10.6."""
    key = (EXP_IDS[exp], int(cell_id), int(rep), int(split))
    return np.random.default_rng(np.random.SeedSequence(entropy=seed, spawn_key=key))


def _unit_ar1(rng: np.random.Generator, n: int, tc: float) -> np.ndarray:
    """AR(1) dừng 2 chiều có độ lệch chuẩn 1 theo từng trục, trả về các bước τ = 1..H: (n, H, 2)."""
    phi = math.exp(-DT / tc)
    s = math.sqrt(1.0 - phi * phi)
    x = rng.standard_normal((n, 2))  # ε_0
    out = np.empty((n, H, 2))
    for t in range(H):
        x = phi * x + s * rng.standard_normal((n, 2))
        out[:, t] = x
    return out


def _unit(v: np.ndarray, eps: float = 1e-12) -> tuple[np.ndarray, np.ndarray]:
    """Trả về (véc tơ đơn vị, chuẩn) theo trục cuối; véc tơ gần 0 cho kết quả 0."""
    nrm = np.linalg.norm(v, axis=-1, keepdims=True)
    return np.where(nrm > eps, v / np.maximum(nrm, eps), 0.0), nrm


def rho_direction(p_hat: np.ndarray, o_hat: np.ndarray, o: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Hướng "cùng hướng" g_τ và phương n̂_τ (SPEC §10.4 bước 2–3)."""
    n_hat, _ = _unit(o_hat - p_hat)
    c_a = -np.sum((o - o_hat) * n_hat, axis=-1, keepdims=True)
    sgn = np.where(c_a >= 0.0, 1.0, -1.0)
    return sgn * n_hat, n_hat


def apply_rho(e: np.ndarray, p_hat: np.ndarray, o_hat: np.ndarray, o: np.ndarray, rho: float) -> np.ndarray:
    """Đổi hướng sai số xe: e′ = ‖e‖·unit(ρ·g + √(1−ρ²)·u), giữ nguyên độ lớn (SPEC §10.4)."""
    if not -1.0 <= rho <= 1.0:
        raise ValueError(f"rho phải trong [-1, 1], nhận {rho}")
    if rho == 0.0:
        return e.copy()
    g, _ = rho_direction(p_hat, o_hat, o)
    u, e_norm = _unit(e)
    mix, _ = _unit(rho * g + math.sqrt(1.0 - rho * rho) * u)
    return e_norm * mix


def sample(
    n: int,
    rng: np.random.Generator,
    sigma_loc: float | Sequence[float] | np.ndarray = 0.1,
    rho: float | None = None,
    params: GenParams = DEFAULT_PARAMS,
    group: np.ndarray | None = None,
) -> Batch:
    """Sinh n mẫu theo SPEC §10.1. sigma_loc là số hoặc mảng (n,). rho ≠ None bật chế độ §10.4."""
    sl = np.broadcast_to(np.asarray(sigma_loc, dtype=float), (n,)).copy()
    if np.any(sl < 0):
        raise ValueError("sigma_loc phải ≥ 0")

    # --- Xe tự hành ---
    v = rng.uniform(params.v_min, params.v_max, n)
    delay = rng.uniform(0.0, params.delay_max, n)
    t_grid = TAU * DT
    p_hat = np.zeros((n, H, 2))
    p_hat[..., 0] = v[:, None] * t_grid

    if params.loc_drift:
        eps = _unit_ar1(rng, n, params.tc_loc)
    else:
        eps = rng.standard_normal((n, H, 2))
    eps *= sl[:, None, None]
    eta = _unit_ar1(rng, n, params.tc_trk) * params.sigma_trk
    e = eps + eta
    e[..., 0] -= (v * delay)[:, None]

    # --- Tác nhân ---
    x0 = rng.uniform(params.x0_min, params.x0_max, n)
    y0 = rng.uniform(-params.y0_abs, params.y0_abs, n)
    xc = rng.uniform(params.xc_min, params.xc_max, n)
    th0 = np.arctan2(-y0, xc - x0)
    s0 = rng.uniform(params.s0_min, params.s0_max, n)

    o_hat = np.empty((n, H, 2))
    o_hat[..., 0] = x0[:, None] + s0[:, None] * t_grid * np.cos(th0)[:, None]
    o_hat[..., 1] = y0[:, None] + s0[:, None] * t_grid * np.sin(th0)[:, None]

    if params.motion == "const":
        omega = np.broadcast_to(rng.normal(0.0, 1.0, n)[:, None] * params.sigma_omega, (n, H))
        acc = np.broadcast_to(rng.normal(0.0, 1.0, n)[:, None] * params.sigma_acc, (n, H))
    elif params.motion == "per_step":
        omega = rng.normal(0.0, 1.0, (n, H)) * params.sigma_omega
        acc = rng.normal(0.0, 1.0, (n, H)) * params.sigma_acc
    else:
        raise ValueError(f"motion không hợp lệ: {params.motion}")

    o = np.empty((n, H, 2))
    px, py, th, sp = x0.copy(), y0.copy(), th0.copy(), s0.copy()
    for t in range(H):
        th = th + omega[:, t] * DT
        sp = np.maximum(0.0, sp + acc[:, t] * DT)
        px = px + sp * DT * np.cos(th)
        py = py + sp * DT * np.sin(th)
        o[:, t, 0] = px
        o[:, t, 1] = py

    if rho is not None:
        e = apply_rho(e, p_hat, o_hat, o, float(rho))

    return Batch(p_hat=p_hat, p=p_hat + e, o_hat=o_hat, o=o, sigma_loc=sl, group=group)


def sample_groups(n: int, rng: np.random.Generator, params: GenParams = DEFAULT_PARAMS) -> Batch:
    """Chế độ trộn nhóm fix/float/loss (SPEC §10.5): nhãn theo phân phối đa thức."""
    g = rng.choice(len(GROUP_NAMES), size=n, p=GROUP_PROBS)
    return sample(n, rng, sigma_loc=GROUP_SIGMA[g], params=params, group=g)


def with_params(**kw) -> GenParams:
    """Tiện ích: tạo GenParams từ mặc định với một số trường thay đổi."""
    return replace(DEFAULT_PARAMS, **kw)
