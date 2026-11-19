"""Điểm số và ngưỡng cho Mục 4.1 (SPEC §10.2, §10.4 bước 6)."""

from __future__ import annotations

import numpy as np

from num41.gen import R_AGENT, R_EGO, SIGMA_TAU, Batch, rho_direction
from sim.common import conformal_q

R_SUM = R_EGO + R_AGENT


def distances(b: Batch) -> tuple[np.ndarray, np.ndarray]:
    """(d̂, d) dạng (n, H): khoảng cách đĩa–đĩa theo kế hoạch và thực tế; có thể âm."""
    d_hat = np.linalg.norm(b.p_hat - b.o_hat, axis=-1) - R_SUM
    d = np.linalg.norm(b.p - b.o, axis=-1) - R_SUM
    return d_hat, d


def scores(b: Batch) -> dict[str, np.ndarray]:
    """R (công thức (5)), A, E — mỗi cái dạng (n,)."""
    d_hat, d = distances(b)
    r = np.max((d_hat - d) / SIGMA_TAU, axis=1)
    a = np.max(np.linalg.norm(b.o - b.o_hat, axis=-1) / SIGMA_TAU, axis=1)
    e = np.max(np.linalg.norm(b.p - b.p_hat, axis=-1) / SIGMA_TAU, axis=1)
    return {"R": r, "A": a, "E": e}


def q(s: np.ndarray, alpha: float) -> float:
    """Ngưỡng phù hợp S_(k), k = ⌈(n+1)(1−α)⌉; +∞ nếu k > n (công thức (6))."""
    return conformal_q(s, alpha)


def thresholds(cal: dict[str, np.ndarray], alpha: float) -> dict[str, float]:
    """Ngưỡng chuẩn hóa của ĐX, B1, B3, B4 từ điểm số hiệu chỉnh (SPEC §10.2)."""
    q_a = q(cal["A"], alpha)
    return {
        "DX": q(cal["R"], alpha),
        "B1": q_a,
        "B3": q(cal["A"], alpha / 2.0) + q(cal["E"], alpha / 2.0),
        "B4": q_a + float(np.max(cal["E"])),
    }


def coverage(r_test: np.ndarray, thr: float) -> float:
    """Tỉ lệ mẫu kiểm tra có R ≤ ngưỡng."""
    return float(np.mean(r_test <= thr))


def group_thresholds(r_cal: np.ndarray, g_cal: np.ndarray, alpha: float, n_groups: int = 3) -> np.ndarray:
    """q_g theo từng nhóm (SPEC §10.5); nhóm thiếu mẫu cho +∞."""
    return np.array([q(r_cal[g_cal == g], alpha) for g in range(n_groups)])


def rho_emp(b: Batch) -> float:
    """corr(e′·n̂, c_A) trên mọi (mẫu, τ) — chỉ để mô tả (SPEC §10.4 bước 6)."""
    _, n_hat = rho_direction(b.p_hat, b.o_hat, b.o)
    ce = np.sum((b.p - b.p_hat) * n_hat, axis=-1).ravel()
    ca = (-np.sum((b.o - b.o_hat) * n_hat, axis=-1)).ravel()
    if np.std(ce) == 0.0 or np.std(ca) == 0.0:
        return float("nan")
    return float(np.corrcoef(ce, ca)[0, 1])
