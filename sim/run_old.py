"""Chạy mô phỏng Phương án A — phương án cũ (bản thảo v0.1) và xuất logs/A/."""

from __future__ import annotations

import datetime as _dt
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm as _norm_dist

from sim.common import (
    CALIB_BLOCK_SEEDS,
    CERT_BLOCK_SEEDS,
    TEST_SEEDS,
    conformal_q,
    mark_thinned_cycles,
    rescore_cycles_with_sigma,
    run_aci_test_suite,
    run_parallel_episodes,
    run_shared_b0_all,
    write_logs,
)
from sim.core import (
    CONDITIONS,
    DEFAULT_SIGMA_OLD,
    D_S,
    GROUPS,
    H_STEPS,
    SCENARIOS,
    condition_for_seed,
    scenario_for_seed,
)

OLD_METHODS: list[str] = ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "ĐX-1", "ĐX-2", "ĐX-3"]


def _group_q_dict(
    thinned_cycles: list[dict[str, Any]],
    alpha: float,
    q_global: float,
) -> tuple[dict[str, float], dict[str, int], dict[str, bool]]:
    min_n = int(math.ceil(1.0 / alpha)) - 1
    out: dict[str, float] = {}
    counts: dict[str, int] = {}
    fallbacks: dict[str, bool] = {}
    for g in GROUPS:
        scores = [c["R"] for c in thinned_cycles if c["g"] == g]
        counts[g] = len(scores)
        if len(scores) >= min_n:
            q_g = conformal_q(scores, alpha)
            if math.isfinite(q_g):
                out[g] = float(q_g)
                fallbacks[g] = False
                continue
        out[g] = float(q_global)
        fallbacks[g] = True
    return out, counts, fallbacks


def _extract_b0_data(
    b0_results: list[dict[str, Any]],
    sigma_tau: np.ndarray,
    every_s: float,
    keep_empty: bool,
    overlapping_bucket: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    eps = [dict(r["episode"]) for r in b0_results]
    raw_cycs = []
    for r in b0_results:
        raw_cycs.extend(rescore_cycles_with_sigma(r["cycles"], sigma_tau))
    thinned = mark_thinned_cycles(raw_cycs, every_s=every_s, keep_empty=keep_empty, overlapping_bucket=overlapping_bucket)
    return eps, raw_cycs, thinned


def run_old(
    out_dir: Path,
    seed_base: int = 0,
    workers: int = 2,
    shared_b0: dict[str, Any] | None = None,
    alpha: float = 0.1,
) -> dict[str, Any]:
    """Chạy toàn bộ Phương án A (cũ): hiệu chỉnh, chứng nhận có điều kiện, kiểm tra 10 phương pháp."""
    if shared_b0 is None:
        shared_b0 = run_shared_b0_all(seed_base=seed_base, workers=workers)

    sigma_tau = DEFAULT_SIGMA_OLD.copy()

    # 1. Dữ liệu B0 dùng chung cho hiệu chỉnh (250-399) và kiểm tra (500-514)
    _, b0_cal_cycs, b0_cal_thinned = _extract_b0_data(
        shared_b0["calib_250_399"], sigma_tau, every_s=2.0, keep_empty=True, overlapping_bucket=True
    )
    b0_test_eps, b0_test_cycs, _ = _extract_b0_data(
        shared_b0["test_500_514"], sigma_tau, every_s=2.0, keep_empty=True, overlapping_bucket=True
    )

    # 2. Hiệu chỉnh các phương pháp mở/đối chứng trên B0 (250-399), giữ mẫu -inf, dùng A_c
    ac_scores_all = [c["A_c_max"] if c["has_agents"] == 1 else float("-inf") for c in b0_cal_thinned]
    e_scores_all = [c["E_max_norm"] for c in b0_cal_thinned]
    r_scores_all = [c["R"] for c in b0_cal_thinned]

    q_b1 = conformal_q(ac_scores_all, alpha)
    q_b3_a = conformal_q(ac_scores_all, alpha / 2.0)
    q_b3_e = conformal_q(e_scores_all, alpha / 2.0)
    q_b3 = q_b3_a + q_b3_e
    max_e_calib = float(max(c["E_max_m"] for c in b0_cal_thinned))

    # B5: ràng buộc cơ hội giả định Gauss theo từng tau
    active_cal = [c for c in b0_cal_thinned if c["has_agents"] == 1]
    a_mat = np.array([c["a_tau"] for c in active_cal], dtype=float)
    b_mat = np.array([c["b_tau"] for c in active_cal], dtype=float)
    s_a_tau = np.std(a_mat, axis=0, ddof=1)
    s_e_tau = np.std(b_mat, axis=0, ddof=1)
    z_alpha = float(_norm_dist.ppf(1.0 - alpha))
    m_b5_tau = z_alpha * np.sqrt(s_a_tau**2 + s_e_tau**2)
    q_b5_equiv = float(m_b5_tau[-1] / sigma_tau[-1])

    # 3. Thuật toán 1 cho ĐX-1 (3 khối x 50 lượt, q0 từ khối 1 B0)
    b0_blk1_thinned = [c for c in b0_cal_thinned if c["seed"] in CALIB_BLOCK_SEEDS[0]]
    q_dx1_curr = max(0.0, conformal_q([c["R"] for c in b0_blk1_thinned], alpha))
    dx1_iters: list[dict[str, Any]] = []
    for k_idx, block_seeds in enumerate(CALIB_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", (q_dx1_curr, 0.0), sigma_tau, "const", seed_base)
            for s in block_seeds
        ]
        res_blk = run_parallel_episodes(tasks, workers=workers)
        cycs_blk = []
        for r in res_blk:
            cycs_blk.extend(r["cycles"])
        th_blk = mark_thinned_cycles(cycs_blk, every_s=2.0, keep_empty=True, overlapping_bucket=True)
        q_next = max(0.0, conformal_q([c["R"] for c in th_blk], alpha))
        dx1_iters.append({
            "iter": k_idx,
            "q_in": float(q_dx1_curr),
            "q_out": float(q_next),
            "n_thinned": len(th_blk),
            "n_empty": sum(1 for c in th_blk if c["has_agents"] == 0),
        })
        q_dx1_curr = q_next

    # Chứng nhận có điều kiện cho ĐX-1 (tối đa 3 lần thử, tăng 5% mỗi lần trượt)
    q_dx1_plan = float(q_dx1_curr)
    dx1_cert_tries: list[dict[str, Any]] = []
    dx1_certified = False
    for try_idx, cert_seeds in enumerate(CERT_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", (q_dx1_plan, 0.0), sigma_tau, "const", seed_base)
            for s in cert_seeds
        ]
        res_cert = run_parallel_episodes(tasks, workers=workers)
        cycs_cert = []
        for r in res_cert:
            cycs_cert.extend(r["cycles"])
        th_cert = mark_thinned_cycles(cycs_cert, every_s=2.0, keep_empty=True, overlapping_bucket=True)
        q_hat = max(0.0, conformal_q([c["R"] for c in th_cert], alpha))
        passed = bool(q_hat <= q_dx1_plan)
        n_ok = sum(1 for c in th_cert if c["R"] <= q_dx1_plan)
        dx1_cert_tries.append({
            "try": try_idx,
            "q_plan": float(q_dx1_plan),
            "q_hat": float(q_hat),
            "n_thinned": len(th_cert),
            "n_covered": n_ok,
            "passed": passed,
        })
        if passed:
            dx1_certified = True
            break
        q_dx1_plan = float(q_dx1_plan * 1.05)

    # 4. Thuật toán 1 cho ĐX-2 (theo nhóm định vị)
    q_g0_glob = max(0.0, conformal_q([c["R"] for c in b0_blk1_thinned], alpha))
    q_dx2_curr, _, _ = _group_q_dict(b0_blk1_thinned, alpha, q_g0_glob)
    dx2_iters: list[dict[str, Any]] = []
    for k_idx, block_seeds in enumerate(CALIB_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", dict(q_dx2_curr), sigma_tau, "group", seed_base)
            for s in block_seeds
        ]
        res_blk = run_parallel_episodes(tasks, workers=workers)
        cycs_blk = []
        for r in res_blk:
            cycs_blk.extend(r["cycles"])
        th_blk = mark_thinned_cycles(cycs_blk, every_s=2.0, keep_empty=True, overlapping_bucket=True)
        q_glob = max(0.0, conformal_q([c["R"] for c in th_blk], alpha))
        q_next_dict, cnts, fbs = _group_q_dict(th_blk, alpha, q_glob)
        dx2_iters.append({
            "iter": k_idx,
            "q_in": dict(q_dx2_curr),
            "q_out": dict(q_next_dict),
            "q_global": float(q_glob),
            "group_counts": cnts,
            "group_fallback": fbs,
        })
        q_dx2_curr = q_next_dict

    # Chứng nhận có điều kiện cho ĐX-2
    q_dx2_plan = dict(q_dx2_curr)
    dx2_cert_tries: list[dict[str, Any]] = []
    dx2_certified = False
    for try_idx, cert_seeds in enumerate(CERT_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", dict(q_dx2_plan), sigma_tau, "group", seed_base)
            for s in cert_seeds
        ]
        res_cert = run_parallel_episodes(tasks, workers=workers)
        cycs_cert = []
        for r in res_cert:
            cycs_cert.extend(r["cycles"])
        th_cert = mark_thinned_cycles(cycs_cert, every_s=2.0, keep_empty=True, overlapping_bucket=True)
        q_hat_glob = max(0.0, conformal_q([c["R"] for c in th_cert], alpha))
        q_hat_dict, cnts, fbs = _group_q_dict(th_cert, alpha, q_hat_glob)

        passed_overall = bool(sum(1 for c in th_cert if c["R"] <= q_dx2_plan[c["g"]]) >= math.ceil((len(th_cert) + 1) * (1.0 - alpha)))
        passed_groups = {g: bool(q_hat_dict[g] <= q_dx2_plan[g]) for g in GROUPS}
        passed = passed_overall and all(passed_groups.values())
        dx2_cert_tries.append({
            "try": try_idx,
            "q_plan": dict(q_dx2_plan),
            "q_hat": dict(q_hat_dict),
            "group_counts": cnts,
            "group_fallback": fbs,
            "passed_groups": passed_groups,
            "passed_overall": passed_overall,
            "passed": passed,
        })
        if passed:
            dx2_certified = True
            break
        for g in GROUPS:
            if not passed_groups[g] or not passed_overall:
                q_dx2_plan[g] = float(q_dx2_plan[g] * 1.05)

    # 5. Chạy kiểm tra 360 lượt cho tất cả phương pháp (B0 lấy từ shared_b0)
    all_episodes: list[dict[str, Any]] = list(b0_test_eps)
    all_cycles: list[dict[str, Any]] = list(b0_test_cycs)

    non_aci_specs: list[tuple[str, Any, str]] = [
        ("B1", (q_b1, 0.0), "const"),
        ("B2", (q_b1, 0.3), "const"),
        ("B3", (q_b3, 0.0), "const"),
        ("B4", (q_b1, max_e_calib), "const"),
        ("B5", (m_b5_tau, q_b5_equiv), "vector"),
        ("ĐX-1", (q_dx1_plan, 0.0), "const"),
        ("ĐX-2", dict(q_dx2_plan), "group"),
    ]
    test_tasks = []
    for m_name, m_arg, m_mode in non_aci_specs:
        for cond in CONDITIONS:
            for scn in SCENARIOS:
                for seed in TEST_SEEDS:
                    test_tasks.append((seed, scn, cond, m_name, m_arg, sigma_tau, m_mode, seed_base))

    res_non_aci = run_parallel_episodes(test_tasks, workers=workers)
    raw_non_aci_cycs = []
    for r in res_non_aci:
        all_episodes.append(r["episode"])
        raw_non_aci_cycs.extend(r["cycles"])
    mark_thinned_cycles(raw_non_aci_cycs, every_s=2.0, keep_empty=True, overlapping_bucket=True)
    all_cycles.extend(raw_non_aci_cycs)

    # B6 (ACI trên điểm số B1 dùng A_c, cập nhật kể cả chu kỳ trống)
    b6_init = ac_scores_all[-500:]
    b6_eps, b6_cycs, b6_final_alphas = run_aci_test_suite(
        method="B6",
        seeds=TEST_SEEDS,
        init_scores=b6_init,
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="A_c_max",
        update_on_empty=True,
        workers=workers,
        seed_base=seed_base,
    )
    mark_thinned_cycles(b6_cycs, every_s=2.0, keep_empty=True, overlapping_bucket=True)
    all_episodes.extend(b6_eps)
    all_cycles.extend(b6_cycs)

    # ĐX-3 (ACI trên điểm số gộp R, cập nhật kể cả chu kỳ trống)
    dx3_init = r_scores_all[-500:]
    dx3_eps, dx3_cycs, dx3_final_alphas = run_aci_test_suite(
        method="ĐX-3",
        seeds=TEST_SEEDS,
        init_scores=dx3_init,
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="R",
        update_on_empty=True,
        workers=workers,
        seed_base=seed_base,
    )
    mark_thinned_cycles(dx3_cycs, every_s=2.0, keep_empty=True, overlapping_bucket=True)
    all_episodes.extend(dx3_eps)
    all_cycles.extend(dx3_cycs)

    # Sắp xếp tất định trước khi ghi file để tái lập bit-for-bit
    m_rank = {m: i for i, m in enumerate(OLD_METHODS)}
    all_episodes.sort(key=lambda e: (m_rank[e["method"]], e["cond"], e["scn"], e["seed"]))
    all_cycles.sort(key=lambda c: (m_rank[c["method"]], c["cond"], c["scn"], c["seed"], c["t"]))

    config = {
        "scheme": "old_v0.1",
        "seed_base": int(seed_base),
        "alpha": float(alpha),
        "d_s": float(D_S),
        "H": int(H_STEPS),
        "thinning_s": 2.0,
        "keep_empty_cycles": True,
        "overlapping_thinning": True,
        "agent_error_metric": "A_c",
        "certification_method": "conditional",
        "aci_update_on_empty": True,
        "aci_gamma": 0.02,
        "aci_window": 500,
        "methods": OLD_METHODS,
        "seeds": {
            "calib_blocks": [[b[0], b[-1]] for b in CALIB_BLOCK_SEEDS],
            "cert_blocks": [[b[0], b[-1]] for b in CERT_BLOCK_SEEDS],
            "test": [TEST_SEEDS[0], TEST_SEEDS[-1]],
        },
        "code_version": "sim-2d-v1.0",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }

    calibration = {
        "sigma_tau": [float(x) for x in sigma_tau],
        "sigma_source": "fixed_0.05+0.04*tau",
        "baselines": {
            "q_B1": float(q_b1),
            "q_B2": float(q_b1),
            "B2_extra_m": 0.3,
            "q_B3_A": float(q_b3_a),
            "q_B3_E": float(q_b3_e),
            "q_B3_sum": float(q_b3),
            "q_B4_base": float(q_b1),
            "B4_max_E_m": float(max_e_calib),
            "m_B5_3s": float(m_b5_tau[-1]),
            "q_B5_equiv": float(q_b5_equiv),
            "n_b0_calib_thinned": len(b0_cal_thinned),
            "n_b0_calib_empty": sum(1 for c in b0_cal_thinned if c["has_agents"] == 0),
        },
        "DX-1": {
            "q0": float(dx1_iters[0]["q_in"]),
            "iterations": dx1_iters,
            "certification_tries": dx1_cert_tries,
            "n_cert_tries": len(dx1_cert_tries),
            "certified": dx1_certified,
            "q_final": float(q_dx1_plan),
            "m_3s_final": float(q_dx1_plan * sigma_tau[-1]),
        },
        "DX-2": {
            "iterations": dx2_iters,
            "certification_tries": dx2_cert_tries,
            "n_cert_tries": len(dx2_cert_tries),
            "certified": dx2_certified,
            "q_final_by_group": {g: float(v) for g, v in q_dx2_plan.items()},
            "m_3s_by_group": {g: float(v * sigma_tau[-1]) for g, v in q_dx2_plan.items()},
        },
        "aci_final_alpha": {
            "B6": b6_final_alphas,
            "ĐX-3": dx3_final_alphas,
        },
    }

    summary = write_logs(
        out_dir=out_dir,
        config=config,
        calibration=calibration,
        episodes=all_episodes,
        cycles=all_cycles,
        methods_order=OLD_METHODS,
        keep_empty=True,
    )
    return {
        "config": config,
        "calibration": calibration,
        "summary": summary,
    }
