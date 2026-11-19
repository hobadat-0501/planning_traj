"""Các hàm dùng chung cho hiệu chỉnh, chứng nhận, ACI, thống kê và ghi log."""

from __future__ import annotations

import csv
import datetime as _dt
import json
import math
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta as _beta_dist
from scipy.stats import binom as _binom_dist

from sim.core import (
    ALL_CONDITIONS,
    ALL_SCENARIOS,
    CONDITIONS,
    DEFAULT_SIGMA_OLD,
    D_S,
    GROUPS,
    H_STEPS,
    SCENARIOS,
    condition_for_seed,
    run_episode,
    scenario_for_seed,
)

CALIB_BLOCK_SEEDS: list[list[int]] = [
    list(range(250, 300)),
    list(range(300, 350)),
    list(range(350, 400)),
]
CERT_BLOCK_SEEDS: list[list[int]] = [
    list(range(400, 450)),
    list(range(450, 500)),
    list(range(600, 650)),
]
SIGMA_EST_SEEDS: list[int] = list(range(200, 250))
TEST_SEEDS: list[int] = list(range(500, 515))

# Các khối hạt giống bổ sung cho mở rộng v0.2 (SPEC §9.6)
TEST_IN_EXT_SEEDS: list[int] = list(range(500, 530))
TEST_IN_EXTRA_SEEDS: list[int] = list(range(515, 530))
OOD_SEEDS: list[int] = list(range(700, 710))
RECAL_TEST_SEEDS: list[int] = list(range(710, 720))
RECAL_CALIB_BLOCKS: list[list[int]] = [
    list(range(800, 850)),
    list(range(850, 900)),
    list(range(900, 950)),
]
RECAL_CERT_SEEDS: list[int] = list(range(950, 1000))
D2_CALIB_BLOCKS: list[list[int]] = [
    list(range(1000, 1050)),
    list(range(1050, 1100)),
    list(range(1100, 1150)),
]
D2_CERT_BLOCKS: list[list[int]] = [
    list(range(1150, 1200)),
    list(range(1200, 1250)),
    list(range(1250, 1300)),
]
SIGMA_SCN_SEEDS: list[int] = list(range(1300, 1400))


def scenario_for_seed_ext(seed: int) -> str:
    """Ánh xạ kịch bản S1–S10 đều theo hạt giống cho RECAL."""
    return ALL_SCENARIOS[int(seed) % len(ALL_SCENARIOS)]


def condition_for_seed_ext(seed: int, seed_base: int = 0) -> str:
    """Chọn điều kiện D0–D10 ngẫu nhiên đều theo hạt giống cho RECAL."""
    rng = np.random.default_rng(int(seed) + 2000003 + int(seed_base) * 9973)
    return ALL_CONDITIONS[int(rng.integers(0, len(ALL_CONDITIONS)))]

CYCLE_FIELDS: list[str] = [
    "method", "seed", "scn", "cond", "t", "g", "J", "fallback",
    "q", "m_max", "gap_max", "d_min", "covered", "safe", "thinned",
    "has_agents", "R", "A_c_max", "A_h_max", "E_max_norm", "a_max_norm", "b_max_norm",
]

EPISODE_FIELDS: list[str] = [
    "method", "seed", "scn", "cond", "collided", "completed", "t_end",
    "d_min", "ttc_min", "n_cycles", "n_fallback", "jerk_rms", "tcomp_p95_ms",
]

CYCLE_FIELDS_EXT: list[str] = [
    "method", "seed", "scn", "cond", "split", "t", "g", "J", "fallback",
    "q", "m_max", "gap_max", "d_min", "covered", "safe", "thinned",
    "has_agents", "n_agents", "occluded_before", "curvature", "e_track", "e_replan",
    "R", "A_c_max", "A_h_max", "E_max_norm", "a_max_norm", "b_max_norm",
]

EPISODE_FIELDS_EXT: list[str] = [
    "method", "seed", "scn", "cond", "split", "collided", "completed", "unavoidable",
    "t_end", "d_min", "ttc_min", "n_cycles", "n_fallback", "jerk_rms", "tcomp_p95_ms",
]


# ==============================================================================
# Hàm lấy thưa và tính ngưỡng phù hợp (Conformal & PAC)
# ==============================================================================

def conformal_q(scores: np.ndarray | list[float], alpha: float) -> float:
    """Tính phân vị hữu hạn R_(ceil((n+1)*(1-alpha))). Trả về inf nếu k > n."""
    arr = np.sort(np.asarray(scores, dtype=float))
    n = len(arr)
    if n == 0:
        return float("inf")
    k = int(math.ceil((n + 1) * (1.0 - alpha)))
    if k <= 0:
        return float(arr[0])
    if k > n:
        return float("inf")
    return float(arr[k - 1])


def pac_order_index(n: int, alpha: float, delta: float) -> int:
    """Tìm bậc thống kê nhỏ nhất k in [1..n] sao cho P(Bin(n, 1-alpha) >= k) <= delta."""
    if n <= 0:
        return 1
    p = 1.0 - alpha
    # binom.sf(k - 1, n, p) = P(Bin(n, p) >= k)
    k_start = max(1, int(math.ceil(n * p)))
    for k in range(k_start, n + 1):
        if float(_binom_dist.sf(k - 1, n, p)) <= delta:
            return k
    return n + 1


def pac_conformal_q(scores: np.ndarray | list[float], alpha: float, delta: float) -> tuple[float, int, int]:
    """Tính ngưỡng chứng nhận PAC. Trả về (q_pac, k_pac, n)."""
    arr = np.sort(np.asarray(scores, dtype=float))
    n = len(arr)
    k = pac_order_index(n, alpha, delta)
    if k > n or n == 0:
        return float("inf"), k, n
    return float(arr[k - 1]), k, n


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Khoảng tin cậy 95% Clopper–Pearson chính xác cho tỉ lệ k/n."""
    if n <= 0:
        return 0.0, 1.0
    lo = 0.0 if k == 0 else float(_beta_dist.ppf(alpha / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(_beta_dist.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return lo, hi


def mark_thinned_cycles(
    cycles: list[dict[str, Any]],
    every_s: float,
    keep_empty: bool,
    overlapping_bucket: bool,
) -> list[dict[str, Any]]:
    """Đánh dấu trường 'thinned' (0/1) trên danh sách chu kỳ của một lượt (hoặc nhiều lượt).

    - Phương án A (cũ): every_s=2.0, keep_empty=True, overlapping_bucket=True (int(t // 2.0)).
    - Phương án B (mới): every_s=3.0, keep_empty=False, overlapping_bucket=False (t - t_last >= 3.0).
    """
    by_ep: dict[tuple[str, int, str, str], list[dict[str, Any]]] = {}
    for c in cycles:
        c["thinned"] = 0
        key = (c["method"], c["seed"], c["scn"], c["cond"])
        by_ep.setdefault(key, []).append(c)

    thinned_rows: list[dict[str, Any]] = []
    for _, ep_cycs in by_ep.items():
        ep_cycs.sort(key=lambda r: r["t"])
        if overlapping_bucket:
            seen_buckets: set[int] = set()
            for c in ep_cycs:
                if not keep_empty and c["has_agents"] == 0:
                    continue
                b = int(math.floor((c["t"] + 1e-9) / every_s))
                if b not in seen_buckets:
                    seen_buckets.add(b)
                    c["thinned"] = 1
                    thinned_rows.append(c)
        else:
            last_t = -1e9
            for c in ep_cycs:
                if not keep_empty and c["has_agents"] == 0:
                    continue
                if c["t"] - last_t >= every_s - 1e-9:
                    c["thinned"] = 1
                    last_t = c["t"]
                    thinned_rows.append(c)
    return thinned_rows


# ==============================================================================
# Lớp tạo margin_fn và bộ ACI (B6, ĐX-3)
# ==============================================================================

def make_const_margin_fn(q_val: float, sigma_tau: np.ndarray, extra_const: float = 0.0):
    """Hàm biên cố định theo thời gian và nhóm định vị."""
    m = np.maximum(0.0, sigma_tau * q_val + extra_const)
    def _fn(g: str, t: float, n_ag: int) -> tuple[float, np.ndarray]:
        return float(q_val), m
    return _fn


def make_group_margin_fn(q_by_g: dict[str, float], sigma_tau: np.ndarray):
    """Hàm biên theo nhóm định vị g in {fix, float, loss}."""
    m_by_g = {g: np.maximum(0.0, sigma_tau * q) for g, q in q_by_g.items()}
    def _fn(g: str, t: float, n_ag: int) -> tuple[float, np.ndarray]:
        return float(q_by_g[g]), m_by_g[g]
    return _fn


def make_vector_margin_fn(margin_tau: np.ndarray, q_equiv: float):
    """Hàm biên cho vector theo từng tau (dùng cho B5)."""
    m = np.maximum(0.0, margin_tau)
    def _fn(g: str, t: float, n_ag: int) -> tuple[float, np.ndarray]:
        return float(q_equiv), m
    return _fn


class AdaptiveConformalState:
    """Trạng thái ACI trễ H bước, cửa sổ trượt 500 điểm số, gamma = 0.02 (SPEC §2 & §3)."""

    def __init__(
        self,
        init_scores: list[float] | np.ndarray,
        sigma_tau: np.ndarray,
        alpha: float = 0.1,
        gamma: float = 0.02,
        window_size: int = 500,
        score_key: str = "R",
        update_on_empty: bool = False,
        cap_q: float = 30.0,
    ) -> None:
        self.alpha = float(alpha)
        self.alpha_t = float(alpha)
        self.gamma = float(gamma)
        self.sigma_tau = np.asarray(sigma_tau, dtype=float)
        self.window_size = int(window_size)
        self.score_key = score_key
        self.update_on_empty = bool(update_on_empty)
        self.cap_q = float(cap_q)

        init_arr = list(np.asarray(init_scores, dtype=float)[-self.window_size:])
        self.window: deque[float] = deque(init_arr, maxlen=self.window_size)
        self.n_updates = 0
        self.alpha_history: list[float] = []

    def current_q(self) -> float:
        eff_alpha = float(np.clip(self.alpha_t, 0.0, 1.0))
        q = conformal_q(list(self.window), eff_alpha)
        if not math.isfinite(q):
            # Khi alpha_t <= 0, dùng cận an toàn trên cùng của cửa sổ * 1.15 để tránh tràn inf trong log JSON
            fin = [v for v in self.window if math.isfinite(v)]
            q = (max(fin) * 1.15) if fin else self.cap_q
        return float(np.clip(q, 0.0, self.cap_q))

    def margin_fn(self, g: str, t: float, n_ag: int) -> tuple[float, np.ndarray]:
        q = self.current_q()
        return q, np.maximum(0.0, self.sigma_tau * q)

    def feedback(self, cyc: dict[str, Any]) -> None:
        """Cập nhật alpha_t và cửa sổ trượt khi có phản hồi sau H bước."""
        has_ag = cyc["has_agents"] == 1
        if not has_ag and not self.update_on_empty:
            return

        if has_ag:
            score = float(cyc[self.score_key])
        else:
            score = float("-inf")

        q_used = float(cyc["q"])
        err = 1.0 if score > q_used else 0.0
        self.alpha_t = self.alpha_t + self.gamma * (self.alpha - err)
        # Giữ alpha_t trong miền lý thuyết [-gamma*(H+1), 1 + gamma*(H+1)]
        lo_bound = -self.gamma * (H_STEPS + 1)
        hi_bound = 1.0 + self.gamma * (H_STEPS + 1)
        self.alpha_t = float(np.clip(self.alpha_t, lo_bound, hi_bound))

        self.window.append(score)
        self.n_updates += 1


# ==============================================================================
# Chạy song song theo task và hàm tiện ích chạy batch
# ==============================================================================

def _worker_run_episode(task: tuple[Any, ...]) -> dict[str, Any]:
    if len(task) == 9:
        seed, scn, cond, method, q_arg, sigma_tau, mode, seed_base, opts = task
    else:
        seed, scn, cond, method, q_arg, sigma_tau, mode, seed_base = task
        opts = {}
    if mode == "const":
        q_val, extra_c = q_arg
        m_fn = make_const_margin_fn(q_val, sigma_tau, extra_c)
    elif mode == "group":
        m_fn = make_group_margin_fn(q_arg, sigma_tau)
    elif mode == "vector":
        m_vec, q_eq = q_arg
        m_fn = make_vector_margin_fn(m_vec, q_eq)
    else:
        raise ValueError(f"Unknown margin mode: {mode}")

    return run_episode(
        seed=seed,
        scenario=scn,
        condition=cond,
        method=method,
        margin_fn=m_fn,
        sigma_tau=sigma_tau,
        feedback_fn=None,
        seed_base=seed_base,
        **opts,
    )


def run_parallel_episodes(
    tasks: list[tuple[Any, ...]],
    workers: int = 2,
) -> list[dict[str, Any]]:
    """Chạy song song các lượt không giữ trạng thái (ProcessPoolExecutor hoặc tuần tự nếu workers<=1)."""
    if workers <= 1 or len(tasks) <= 4:
        return [_worker_run_episode(t) for t in tasks]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(_worker_run_episode, tasks, chunksize=max(1, len(tasks) // (workers * 4))))


def _worker_aci_condition(task: tuple[Any, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Chạy tuần tự các lượt trong 1 điều kiện D cho ACI (B6 / ĐX-3)."""
    cond, seeds, method, init_scores, sigma_tau, alpha, gamma, window_size, score_key, update_on_empty, seed_base = task
    aci = AdaptiveConformalState(
        init_scores=init_scores,
        sigma_tau=sigma_tau,
        alpha=alpha,
        gamma=gamma,
        window_size=window_size,
        score_key=score_key,
        update_on_empty=update_on_empty,
    )
    eps: list[dict[str, Any]] = []
    cycs: list[dict[str, Any]] = []
    for seed in seeds:
        for scn in SCENARIOS:
            res = run_episode(
                seed=seed,
                scenario=scn,
                condition=cond,
                method=method,
                margin_fn=aci.margin_fn,
                sigma_tau=sigma_tau,
                feedback_fn=aci.feedback,
                seed_base=seed_base,
            )
            eps.append(res["episode"])
            cycs.extend(res["cycles"])
    return eps, cycs, aci.alpha_t


def run_aci_test_suite(
    method: str,
    seeds: list[int],
    init_scores: list[float] | np.ndarray,
    sigma_tau: np.ndarray,
    alpha: float,
    score_key: str,
    update_on_empty: bool,
    workers: int = 2,
    seed_base: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    """Chạy kiểm tra ACI: mỗi điều kiện chạy tuần tự, song song hóa giữa các điều kiện (SPEC §4)."""
    tasks = [
        (cond, seeds, method, list(init_scores), sigma_tau, alpha, 0.02, 500, score_key, update_on_empty, seed_base)
        for cond in CONDITIONS
    ]
    if workers <= 1:
        results = [_worker_aci_condition(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(CONDITIONS))) as ex:
            results = list(ex.map(_worker_aci_condition, tasks))

    all_eps, all_cycs = [], []
    final_alphas: dict[str, float] = {}
    for cond, (eps, cycs, a_fin) in zip(CONDITIONS, results):
        all_eps.extend(eps)
        all_cycs.extend(cycs)
        final_alphas[cond] = float(a_fin)
    return all_eps, all_cycs, final_alphas


# ==============================================================================
# Chuẩn hóa B0 dùng chung và tái tính điểm số theo sigma_tau
# ==============================================================================

def run_shared_b0_all(seed_base: int = 0, workers: int = 2) -> dict[str, Any]:
    """Chạy B0 đúng 1 lần cho mọi tập hạt giống dùng chung (200-249, 250-399, 500-514)."""
    sigma_tasks = [
        (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "B0", (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base)
        for s in SIGMA_EST_SEEDS
    ]
    calib_tasks = [
        (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "B0", (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base)
        for block in CALIB_BLOCK_SEEDS
        for s in block
    ]
    test_tasks = [
        (s, scn, cond, "B0", (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base)
        for cond in CONDITIONS
        for scn in SCENARIOS
        for s in TEST_SEEDS
    ]

    all_tasks = sigma_tasks + calib_tasks + test_tasks
    all_res = run_parallel_episodes(all_tasks, workers=workers)

    n1 = len(sigma_tasks)
    n2 = len(calib_tasks)
    return {
        "sigma_200_249": all_res[:n1],
        "calib_250_399": all_res[n1 : n1 + n2],
        "test_500_514": all_res[n1 + n2 :],
    }


def rescore_cycles_with_sigma(cycles: list[dict[str, Any]], sigma_tau: np.ndarray) -> list[dict[str, Any]]:
    """Tính lại bản sao danh sách chu kỳ theo vector sigma_tau mới (không làm biến đổi bản gốc B0)."""
    out: list[dict[str, Any]] = []
    for c in cycles:
        nc = dict(c)
        if nc["has_agents"] == 1:
            nc["R"] = float(np.max(nc["gap_tau"] / sigma_tau))
            nc["A_c_max"] = float(np.max(nc["A_c_tau"] / sigma_tau))
            nc["A_h_max"] = float(np.max(nc["A_h_tau"] / sigma_tau))
            nc["E_max_norm"] = float(np.max(nc["E_tau"] / sigma_tau))
            nc["a_max_norm"] = float(np.max(nc["a_tau"] / sigma_tau))
            nc["b_max_norm"] = float(np.max(nc["b_tau"] / sigma_tau))
        else:
            nc["R"] = float("-inf")
            nc["A_c_max"] = float("-inf")
            nc["A_h_max"] = float("-inf")
            nc["E_max_norm"] = float(np.max(nc["E_tau"] / sigma_tau))
            nc["a_max_norm"] = 0.0
            nc["b_max_norm"] = 0.0
        nc["covered"] = int(nc["R"] <= nc["q"])
        out.append(nc)
    return out


# ==============================================================================
# Tính tổng hợp summary.json và ghi CSV/JSON
# ==============================================================================

def _safe_float(v: float) -> float | None:
    if v is None or not math.isfinite(float(v)):
        return None
    return float(v)


def summarize_group(
    eps: list[dict[str, Any]],
    thinned_cycs: list[dict[str, Any]],
    keep_empty: bool,
) -> dict[str, Any]:
    """Tính đầy đủ các chỉ tiêu SPEC §5 cho một nhóm (method x cond hoặc method tổng)."""
    n_ep = len(eps)
    n_col = sum(e["collided"] for e in eps)
    n_comp = sum(e["completed"] for e in eps)
    col_lo, col_hi = clopper_pearson(n_col, n_ep)
    comp_lo, comp_hi = clopper_pearson(n_comp, n_ep)

    # Chu kỳ để đánh giá độ phủ
    eval_cycs = thinned_cycs if keep_empty else [c for c in thinned_cycs if c["has_agents"] == 1]
    n_cyc = len(eval_cycs)
    n_safe = sum(c["safe"] for c in eval_cycs)
    n_cov_score = sum(c["covered"] for c in eval_cycs)

    cov_safe = n_safe / n_cyc if n_cyc > 0 else 0.0
    safe_lo, safe_hi = clopper_pearson(n_safe, n_cyc)
    cov_score = n_cov_score / n_cyc if n_cyc > 0 else 0.0
    score_lo, score_hi = clopper_pearson(n_cov_score, n_cyc)

    # Tách riêng chu kỳ khả thi vs dự phòng (SPEC §3)
    feas_cycs = [c for c in eval_cycs if c["fallback"] == 0]
    fb_cycs = [c for c in eval_cycs if c["fallback"] == 1]
    n_feas = len(feas_cycs)
    n_fb_eval = len(fb_cycs)
    cov_feas = sum(c["safe"] for c in feas_cycs) / n_feas if n_feas > 0 else None
    cov_fb = sum(c["safe"] for c in fb_cycs) / n_fb_eval if n_fb_eval > 0 else None
    cov_score_feas = sum(c["covered"] for c in feas_cycs) / n_feas if n_feas > 0 else None
    cov_score_fb = sum(c["covered"] for c in fb_cycs) / n_fb_eval if n_fb_eval > 0 else None

    # Vi phạm theo lượt: lượt có ít nhất 1 chu kỳ đã lấy thưa vi phạm (safe == 0)
    ep_viol_map: dict[tuple[int, str, str], int] = {}
    for e in eps:
        ep_viol_map[(e["seed"], e["scn"], e["cond"])] = 0
    for c in eval_cycs:
        if c["safe"] == 0:
            ep_viol_map[(c["seed"], c["scn"], c["cond"])] = 1
    n_ep_viol = sum(ep_viol_map.values())
    ep_viol_rate = n_ep_viol / n_ep if n_ep > 0 else 0.0
    ev_lo, ev_hi = clopper_pearson(n_ep_viol, n_ep)

    # Hiệu quả, độ êm dịu, thời gian tính, ngưỡng
    tot_cycles = sum(e["n_cycles"] for e in eps)
    tot_fb = sum(e["n_fallback"] for e in eps)
    fb_pct = (100.0 * tot_fb / tot_cycles) if tot_cycles > 0 else 0.0

    fin_q = [c["q"] for c in eval_cycs if math.isfinite(c["q"])]
    fin_m = [c["m_max"] for c in eval_cycs if math.isfinite(c["m_max"])]

    return {
        "n_episodes": n_ep,
        "n_thinned_cycles": n_cyc,
        "n_feasible_thinned": n_feas,
        "n_fallback_thinned": n_fb_eval,
        "coverage_safe": float(cov_safe),
        "coverage_safe_ci95": [float(safe_lo), float(safe_hi)],
        "coverage_feasible": _safe_float(cov_feas) if cov_feas is not None else None,
        "coverage_fallback": _safe_float(cov_fb) if cov_fb is not None else None,
        "coverage_score": float(cov_score),
        "coverage_score_ci95": [float(score_lo), float(score_hi)],
        "coverage_score_feasible": _safe_float(cov_score_feas) if cov_score_feas is not None else None,
        "coverage_score_fallback": _safe_float(cov_score_fb) if cov_score_fb is not None else None,
        "violation_cycle": float(1.0 - cov_safe),
        "violation_episode": float(ep_viol_rate),
        "violation_episode_ci95": [float(ev_lo), float(ev_hi)],
        "collision_rate": float(n_col / n_ep) if n_ep > 0 else 0.0,
        "collision_ci95": [float(col_lo), float(col_hi)],
        "completion_rate": float(n_comp / n_ep) if n_ep > 0 else 0.0,
        "completion_ci95": [float(comp_lo), float(comp_hi)],
        "d_min_mean": float(np.mean([e["d_min"] for e in eps])) if n_ep > 0 else 0.0,
        "d_min_p05": float(np.percentile([e["d_min"] for e in eps], 5)) if n_ep > 0 else 0.0,
        "ttc_min_mean": float(np.mean([e["ttc_min"] for e in eps])) if n_ep > 0 else 0.0,
        "ttc_min_p05": float(np.percentile([e["ttc_min"] for e in eps], 5)) if n_ep > 0 else 0.0,
        "t_end_mean": float(np.mean([e["t_end"] for e in eps])) if n_ep > 0 else 0.0,
        "fallback_pct": float(fb_pct),
        "jerk_rms_mean": float(np.mean([e["jerk_rms"] for e in eps])) if n_ep > 0 else 0.0,
        "tcomp_p95_ms": float(np.percentile([e["tcomp_p95_ms"] for e in eps], 95)) if n_ep > 0 else 0.0,
        "q_mean": float(np.mean(fin_q)) if fin_q else 0.0,
        "q_median": float(np.median(fin_q)) if fin_q else 0.0,
        "m_3s_mean": float(np.mean(fin_m)) if fin_m else 0.0,
        "m_3s_median": float(np.median(fin_m)) if fin_m else 0.0,
    }


def write_logs(
    out_dir: Path,
    config: dict[str, Any],
    calibration: dict[str, Any],
    episodes: list[dict[str, Any]],
    cycles: list[dict[str, Any]],
    methods_order: list[str],
    keep_empty: bool,
) -> dict[str, Any]:
    """Ghi 5 file chuẩn (config.json, calibration.json, cycles.csv, episodes.csv, summary.json)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. config.json
    with open(out_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 2. calibration.json
    with open(out_dir / "calibration.json", "w", encoding="utf-8") as f:
        json.dump(calibration, f, ensure_ascii=False, indent=2)

    # 3. episodes.csv
    with open(out_dir / "episodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EPISODE_FIELDS)
        w.writeheader()
        for e in episodes:
            row = {k: e[k] for k in EPISODE_FIELDS}
            w.writerow(row)

    # 4. cycles.csv
    with open(out_dir / "cycles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CYCLE_FIELDS)
        w.writeheader()
        for c in cycles:
            row = {}
            for k in CYCLE_FIELDS:
                val = c[k]
                if isinstance(val, float) and not math.isfinite(val):
                    row[k] = "-inf" if val < 0 else "inf"
                elif isinstance(val, float):
                    row[k] = f"{val:.6f}"
                else:
                    row[k] = val
            w.writerow(row)

    # 5. summary.json
    summary: dict[str, Any] = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "keep_empty_in_eval": keep_empty,
        "by_method": {},
        "by_method_cond": {},
        "by_method_group": {},
    }

    for m in methods_order:
        m_eps = [e for e in episodes if e["method"] == m]
        m_thinned = [c for c in cycles if c["method"] == m and c["thinned"] == 1]
        summary["by_method"][m] = summarize_group(m_eps, m_thinned, keep_empty=keep_empty)
        summary["by_method_cond"][m] = {}
        for d in CONDITIONS:
            d_eps = [e for e in m_eps if e["cond"] == d]
            d_thinned = [c for c in m_thinned if c["cond"] == d]
            summary["by_method_cond"][m][d] = summarize_group(d_eps, d_thinned, keep_empty=keep_empty)

        summary["by_method_group"][m] = {}
        for g in GROUPS:
            g_thinned = [c for c in m_thinned if c["g"] == g and (keep_empty or c["has_agents"] == 1)]
            n_g = len(g_thinned)
            n_safe_g = sum(c["safe"] for c in g_thinned)
            n_cov_g = sum(c["covered"] for c in g_thinned)
            s_lo, s_hi = clopper_pearson(n_safe_g, n_g)
            c_lo, c_hi = clopper_pearson(n_cov_g, n_g)
            fin_m = [c["m_max"] for c in g_thinned if math.isfinite(c["m_max"])]
            fin_q = [c["q"] for c in g_thinned if math.isfinite(c["q"])]
            summary["by_method_group"][m][g] = {
                "n_thinned": n_g,
                "coverage_safe": float(n_safe_g / n_g) if n_g > 0 else 0.0,
                "coverage_safe_ci95": [float(s_lo), float(s_hi)],
                "coverage_score": float(n_cov_g / n_g) if n_g > 0 else 0.0,
                "coverage_score_ci95": [float(c_lo), float(c_hi)],
                "q_mean": float(np.mean(fin_q)) if fin_q else 0.0,
                "m_3s_mean": float(np.mean(fin_m)) if fin_m else 0.0,
            }

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def _worker_aci_ext_condition(task: tuple[Any, ...]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float]:
    """Chạy tuần tự các lượt trong 1 điều kiện D cho ACI trên tập kịch bản tùy ý."""
    (
        cond, scenarios_list, seeds, method, split, init_scores, sigma_tau,
        alpha, gamma, window_size, score_key, update_on_empty, seed_base, opts,
    ) = task
    aci = AdaptiveConformalState(
        init_scores=init_scores,
        sigma_tau=sigma_tau,
        alpha=alpha,
        gamma=gamma,
        window_size=window_size,
        score_key=score_key,
        update_on_empty=update_on_empty,
    )
    eps: list[dict[str, Any]] = []
    cycs: list[dict[str, Any]] = []
    for seed in seeds:
        for scn in scenarios_list:
            res = run_episode(
                seed=seed,
                scenario=scn,
                condition=cond,
                method=method,
                margin_fn=aci.margin_fn,
                sigma_tau=sigma_tau,
                feedback_fn=aci.feedback,
                seed_base=seed_base,
                split=split,
                **opts,
            )
            eps.append(res["episode"])
            cycs.extend(res["cycles"])
    return eps, cycs, aci.alpha_t


def run_aci_ext_suite(
    method: str,
    split: str,
    scenarios_list: list[str] | tuple[str, ...],
    conditions_list: list[str] | tuple[str, ...],
    seeds: list[int],
    init_scores: list[float] | np.ndarray,
    sigma_tau: np.ndarray,
    alpha: float,
    score_key: str,
    update_on_empty: bool,
    gamma: float = 0.02,
    window_size: int = 500,
    workers: int = 2,
    seed_base: int = 0,
    opts: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, float]]:
    """Chạy kiểm tra ACI cho một tập phân phối mở rộng (song song giữa các điều kiện)."""
    opts_dict = dict(opts) if opts else {}
    tasks = [
        (
            cond, list(scenarios_list), seeds, method, split, list(init_scores),
            sigma_tau, alpha, gamma, window_size, score_key, update_on_empty, seed_base, opts_dict,
        )
        for cond in conditions_list
    ]
    if workers <= 1:
        results = [_worker_aci_ext_condition(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as ex:
            results = list(ex.map(_worker_aci_ext_condition, tasks))

    all_eps, all_cycs = [], []
    final_alphas: dict[str, float] = {}
    for cond, (eps, cycs, a_fin) in zip(conditions_list, results):
        all_eps.extend(eps)
        all_cycs.extend(cycs)
        final_alphas[cond] = float(a_fin)
    return all_eps, all_cycs, final_alphas


def write_ext_logs(
    out_dir: Path,
    config: dict[str, Any],
    episodes: list[dict[str, Any]],
    cycles: list[dict[str, Any]],
    methods_order: list[str],
    splits_order: list[str],
) -> dict[str, Any]:
    """Ghi config.json, episodes.csv, cycles.csv và summary.json mở rộng vào logs/ext/."""
    out_dir.mkdir(parents=True, exist_ok=True)

    with open(out_dir / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    with open(out_dir / "episodes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=EPISODE_FIELDS_EXT)
        w.writeheader()
        for e in episodes:
            w.writerow({k: e[k] for k in EPISODE_FIELDS_EXT})

    with open(out_dir / "cycles.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CYCLE_FIELDS_EXT)
        w.writeheader()
        for c in cycles:
            row = {}
            for k in CYCLE_FIELDS_EXT:
                val = c[k]
                if isinstance(val, float) and not math.isfinite(val):
                    row[k] = "-inf" if val < 0 else "inf"
                elif isinstance(val, float):
                    row[k] = f"{val:.6f}"
                else:
                    row[k] = val
            w.writerow(row)

    summary: dict[str, Any] = {
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "by_split_method": {},
        "by_split_method_cond": {},
        "by_split_method_scn": {},
        "by_split_method_group": {},
        "s5_unavoidable_breakdown": {},
    }

    for sp in splits_order:
        sp_eps = [e for e in episodes if e["split"] == sp]
        sp_cycs = [c for c in cycles if c["split"] == sp and c["thinned"] == 1]
        summary["by_split_method"][sp] = {}
        summary["by_split_method_cond"][sp] = {}
        summary["by_split_method_scn"][sp] = {}
        summary["by_split_method_group"][sp] = {}

        conds_in_sp = sorted({e["cond"] for e in sp_eps}, key=lambda x: ALL_CONDITIONS.index(x))
        scns_in_sp = sorted({e["scn"] for e in sp_eps}, key=lambda x: ALL_SCENARIOS.index(x))

        for m in methods_order:
            m_eps = [e for e in sp_eps if e["method"] == m]
            m_th = [c for c in sp_cycs if c["method"] == m]
            summary["by_split_method"][sp][m] = summarize_group(m_eps, m_th, keep_empty=False)

            summary["by_split_method_cond"][sp][m] = {
                d: summarize_group(
                    [e for e in m_eps if e["cond"] == d],
                    [c for c in m_th if c["cond"] == d],
                    keep_empty=False,
                )
                for d in conds_in_sp
            }
            summary["by_split_method_scn"][sp][m] = {
                s: summarize_group(
                    [e for e in m_eps if e["scn"] == s],
                    [c for c in m_th if c["scn"] == s],
                    keep_empty=False,
                )
                for s in scns_in_sp
            }
            summary["by_split_method_group"][sp][m] = {}
            for g in GROUPS:
                g_th = [c for c in m_th if c["g"] == g and c["has_agents"] == 1]
                n_g = len(g_th)
                n_safe_g = sum(c["safe"] for c in g_th)
                n_cov_g = sum(c["covered"] for c in g_th)
                s_lo, s_hi = clopper_pearson(n_safe_g, n_g)
                c_lo, c_hi = clopper_pearson(n_cov_g, n_g)
                fin_m = [c["m_max"] for c in g_th if math.isfinite(c["m_max"])]
                fin_q = [c["q"] for c in g_th if math.isfinite(c["q"])]
                summary["by_split_method_group"][sp][m][g] = {
                    "n_thinned": n_g,
                    "coverage_safe": float(n_safe_g / n_g) if n_g > 0 else 0.0,
                    "coverage_safe_ci95": [float(s_lo), float(s_hi)],
                    "coverage_score": float(n_cov_g / n_g) if n_g > 0 else 0.0,
                    "coverage_score_ci95": [float(c_lo), float(c_hi)],
                    "q_mean": float(np.mean(fin_q)) if fin_q else 0.0,
                    "m_3s_mean": float(np.mean(fin_m)) if fin_m else 0.0,
                }

        # Tách riêng S5 có và không có unavoidable == 1
        if "S5" in scns_in_sp:
            s5_bd: dict[str, Any] = {}
            for m in methods_order:
                m_s5_all = [e for e in sp_eps if e["method"] == m and e["scn"] == "S5"]
                unav_keys = {(e["seed"], e["cond"]) for e in m_s5_all if e["unavoidable"] == 1}
                m_s5_avoid = [e for e in m_s5_all if e["unavoidable"] == 0]
                m_s5_th_all = [c for c in sp_cycs if c["method"] == m and c["scn"] == "S5"]
                m_s5_th_avoid = [c for c in m_s5_th_all if (c["seed"], c["cond"]) not in unav_keys]
                s5_bd[m] = {
                    "n_total": len(m_s5_all),
                    "n_unavoidable": len(unav_keys),
                    "all": summarize_group(m_s5_all, m_s5_th_all, keep_empty=False),
                    "avoidable_only": summarize_group(m_s5_avoid, m_s5_th_avoid, keep_empty=False),
                }
            summary["s5_unavoidable_breakdown"][sp] = s5_bd

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary
