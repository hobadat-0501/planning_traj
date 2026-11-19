"""Chạy mô phỏng Phương án B — phương án mới và xuất logs/new/ (kèm alpha_sweep.csv)."""

from __future__ import annotations

import csv
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
    clopper_pearson,
    conformal_q,
    mark_thinned_cycles,
    pac_conformal_q,
    pac_order_index,
    rescore_cycles_with_sigma,
    run_aci_test_suite,
    run_parallel_episodes,
    run_shared_b0_all,
    summarize_group,
    write_logs,
)
from sim.core import (
    CONDITIONS,
    D_S,
    GROUPS,
    H_STEPS,
    SCENARIOS,
    condition_for_seed,
    scenario_for_seed,
)

NEW_METHODS: list[str] = ["B0", "B1", "B2", "B3", "B3′", "B4", "B5", "B6", "ĐX-1", "ĐX-2", "ĐX-3"]
ALPHA_SWEEP_VALUES: list[float] = [0.01, 0.02, 0.05, 0.10, 0.20]
ALPHA_SWEEP_METHODS: list[str] = ["B1", "B3′", "ĐX-2"]
PAC_DELTA_TOTAL: float = 0.05
PAC_MAX_TRIES: int = 3
PAC_DELTA_PER_TRY: float = PAC_DELTA_TOTAL / PAC_MAX_TRIES


def estimate_sigma_tau(b0_sigma_results: list[dict[str, Any]], quantile: float = 0.90, floor: float = 0.05) -> np.ndarray:
    """Ước lượng sigma_tau từ hạt giống 200-249 (B0): phân vị 90% của max_j(d_hat - d), cận dưới 0.05 m, đơn điệu tăng."""
    active_gaps = []
    for r in b0_sigma_results:
        for c in r["cycles"]:
            if c["has_agents"] == 1:
                active_gaps.append(c["gap_tau"])
    gap_mat = np.asarray(active_gaps, dtype=float)  # (N_active, 30)
    raw_q = np.quantile(gap_mat, quantile, axis=0)
    clipped = np.maximum(raw_q, floor)
    return np.maximum.accumulate(clipped)


def _group_q_dict_active(
    thinned_cycles: list[dict[str, Any]],
    alpha: float,
    q_global: float,
) -> tuple[dict[str, float], dict[str, int], dict[str, bool]]:
    min_n = int(math.ceil(1.0 / alpha)) - 1
    out: dict[str, float] = {}
    counts: dict[str, int] = {}
    fallbacks: dict[str, bool] = {}
    for g in GROUPS:
        scores = [c["R"] for c in thinned_cycles if c["g"] == g and c["has_agents"] == 1]
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


def _extract_b0_new(
    b0_results: list[dict[str, Any]],
    sigma_tau: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    eps = [dict(r["episode"]) for r in b0_results]
    raw_cycs = []
    for r in b0_results:
        raw_cycs.extend(rescore_cycles_with_sigma(r["cycles"], sigma_tau))
    thinned = mark_thinned_cycles(raw_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    return eps, raw_cycs, thinned


def run_new(
    out_dir: Path,
    seed_base: int = 0,
    workers: int = 2,
    shared_b0: dict[str, Any] | None = None,
    alpha: float = 0.1,
) -> dict[str, Any]:
    """Chạy toàn bộ Phương án B (mới): sigma_tau, hiệu chỉnh, PAC, B3′, quét alpha."""
    if shared_b0 is None:
        shared_b0 = run_shared_b0_all(seed_base=seed_base, workers=workers)

    # 1. Ước lượng sigma_tau trên hạt giống 200-249
    sigma_tau = estimate_sigma_tau(shared_b0["sigma_200_249"])

    # 2. Tái tính điểm số B0 (250-399 và 500-514) theo sigma_tau mới, bỏ chu kỳ trống, lấy thưa 3 s không chồng
    _, b0_cal_cycs, b0_cal_thinned = _extract_b0_new(shared_b0["calib_250_399"], sigma_tau)
    b0_test_eps, b0_test_cycs, _ = _extract_b0_new(shared_b0["test_500_514"], sigma_tau)

    # 3. Hiệu chỉnh các phương pháp đối chứng trên chu kỳ có tác nhân (dùng cận Hausdorff A_h)
    ah_scores = [c["A_h_max"] for c in b0_cal_thinned]
    e_scores = [c["E_max_norm"] for c in b0_cal_thinned]
    a_signed_scores = [c["a_max_norm"] for c in b0_cal_thinned]
    b_signed_scores = [c["b_max_norm"] for c in b0_cal_thinned]
    r_scores = [c["R"] for c in b0_cal_thinned]

    q_b1 = conformal_q(ah_scores, alpha)
    q_b3_a = conformal_q(ah_scores, alpha / 2.0)
    q_b3_e = conformal_q(e_scores, alpha / 2.0)
    q_b3 = q_b3_a + q_b3_e

    # B3′: hai phần có dấu a và b, hiệu chỉnh riêng ở alpha/2 rồi cộng
    q_b3p_a = max(0.0, conformal_q(a_signed_scores, alpha / 2.0))
    q_b3p_b = max(0.0, conformal_q(b_signed_scores, alpha / 2.0))
    q_b3p = q_b3p_a + q_b3p_b

    max_e_calib = float(max(c["E_max_m"] for c in b0_cal_thinned))

    # B5: ràng buộc cơ hội giả định Gauss
    a_mat = np.array([c["a_tau"] for c in b0_cal_thinned], dtype=float)
    b_mat = np.array([c["b_tau"] for c in b0_cal_thinned], dtype=float)
    s_a_tau = np.std(a_mat, axis=0, ddof=1)
    s_e_tau = np.std(b_mat, axis=0, ddof=1)
    z_alpha = float(_norm_dist.ppf(1.0 - alpha))
    m_b5_tau = z_alpha * np.sqrt(s_a_tau**2 + s_e_tau**2)
    q_b5_equiv = float(m_b5_tau[-1] / sigma_tau[-1])

    # 4. Thuật toán 1 + chứng nhận PAC (Bonferroni delta = 0.05/3) cho ĐX-1
    b0_blk1_thinned = [c for c in b0_cal_thinned if c["seed"] in CALIB_BLOCK_SEEDS[0]]
    q_dx1_curr = max(0.0, conformal_q([c["R"] for c in b0_blk1_thinned], alpha))
    dx1_iters: list[dict[str, Any]] = []
    for k_idx, block_seeds in enumerate(CALIB_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", (q_dx1_curr, 0.0), sigma_tau, "const", seed_base)
            for s in block_seeds
        ]
        res_blk = run_parallel_episodes(tasks, workers=workers)
        cycs_blk = [c for r in res_blk for c in r["cycles"]]
        th_blk = mark_thinned_cycles(cycs_blk, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        q_next = max(0.0, conformal_q([c["R"] for c in th_blk], alpha))
        dx1_iters.append({
            "iter": k_idx,
            "q_in": float(q_dx1_curr),
            "q_out": float(q_next),
            "n_thinned_active": len(th_blk),
        })
        q_dx1_curr = q_next

    q_dx1_plan = float(q_dx1_curr)
    dx1_cert_tries: list[dict[str, Any]] = []
    dx1_certified = False
    for try_idx, cert_seeds in enumerate(CERT_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", (q_dx1_plan, 0.0), sigma_tau, "const", seed_base)
            for s in cert_seeds
        ]
        res_cert = run_parallel_episodes(tasks, workers=workers)
        cycs_cert = [c for r in res_cert for c in r["cycles"]]
        th_cert = mark_thinned_cycles(cycs_cert, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        r_cert = [c["R"] for c in th_cert]
        q_pac, k_pac, n_cert = pac_conformal_q(r_cert, alpha, PAC_DELTA_PER_TRY)
        q_cond = conformal_q(r_cert, alpha)
        passed = bool(q_pac <= q_dx1_plan)
        n_cov = sum(1 for v in r_cert if v <= q_dx1_plan)
        dx1_cert_tries.append({
            "try": try_idx,
            "q_plan": float(q_dx1_plan),
            "q_pac": float(q_pac) if math.isfinite(q_pac) else None,
            "q_cond": float(q_cond),
            "k_pac": int(k_pac),
            "n_thinned": int(n_cert),
            "n_covered": int(n_cov),
            "passed": passed,
        })
        if passed:
            dx1_certified = True
            break
        # Tăng q_plan đủ để tiến tới ngưỡng PAC (chạy trên tập chứng nhận độc lập tiếp theo)
        if math.isfinite(q_pac):
            q_dx1_plan = float(max(q_dx1_plan * 1.05, min(q_pac * 1.01, q_dx1_plan * 1.25)))
        else:
            q_dx1_plan = float(q_dx1_plan * 1.15)

    # 5. Thuật toán 1 + chứng nhận PAC cho ĐX-2 (theo nhóm định vị)
    q_g0_glob = max(0.0, conformal_q([c["R"] for c in b0_blk1_thinned], alpha))
    q_dx2_curr, _, _ = _group_q_dict_active(b0_blk1_thinned, alpha, q_g0_glob)
    dx2_iters: list[dict[str, Any]] = []
    for k_idx, block_seeds in enumerate(CALIB_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", dict(q_dx2_curr), sigma_tau, "group", seed_base)
            for s in block_seeds
        ]
        res_blk = run_parallel_episodes(tasks, workers=workers)
        cycs_blk = [c for r in res_blk for c in r["cycles"]]
        th_blk = mark_thinned_cycles(cycs_blk, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        q_glob = max(0.0, conformal_q([c["R"] for c in th_blk], alpha))
        q_next_dict, cnts, fbs = _group_q_dict_active(th_blk, alpha, q_glob)
        dx2_iters.append({
            "iter": k_idx,
            "q_in": dict(q_dx2_curr),
            "q_out": dict(q_next_dict),
            "q_global": float(q_glob),
            "group_counts": cnts,
            "group_fallback": fbs,
        })
        q_dx2_curr = q_next_dict

    q_dx2_plan = dict(q_dx2_curr)
    dx2_cert_tries: list[dict[str, Any]] = []
    dx2_certified = False
    for try_idx, cert_seeds in enumerate(CERT_BLOCK_SEEDS, start=1):
        tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", dict(q_dx2_plan), sigma_tau, "group", seed_base)
            for s in cert_seeds
        ]
        res_cert = run_parallel_episodes(tasks, workers=workers)
        cycs_cert = [c for r in res_cert for c in r["cycles"]]
        th_cert = mark_thinned_cycles(cycs_cert, every_s=3.0, keep_empty=False, overlapping_bucket=False)

        # Kiểm tra PAC tổng thể trên tỉ lệ chuẩn hóa R_i / q_plan(g_i) <= 1.0
        norm_ratios = [c["R"] / max(q_dx2_plan[c["g"]], 1e-9) for c in th_cert]
        ratio_pac, k_pac_all, n_cert_all = pac_conformal_q(norm_ratios, alpha, PAC_DELTA_PER_TRY)
        passed_overall = bool(ratio_pac <= 1.0)

        # Kiểm tra PAC riêng từng nhóm để ghi nhận nhóm nào đủ mẫu (>= 39 ở alpha=0.1)
        group_pac_info: dict[str, Any] = {}
        for g in GROUPS:
            g_scores = [c["R"] for c in th_cert if c["g"] == g]
            q_g_pac, k_g, n_g = pac_conformal_q(g_scores, alpha, PAC_DELTA_PER_TRY)
            group_pac_info[g] = {
                "n": int(n_g),
                "k_pac": int(k_g),
                "pac_feasible": bool(k_g <= n_g),
                "q_pac": float(q_g_pac) if math.isfinite(q_g_pac) else None,
                "passed_standalone": bool(math.isfinite(q_g_pac) and q_g_pac <= q_dx2_plan[g]),
            }

        dx2_cert_tries.append({
            "try": try_idx,
            "q_plan": dict(q_dx2_plan),
            "overall_ratio_pac": float(ratio_pac) if math.isfinite(ratio_pac) else None,
            "overall_k_pac": int(k_pac_all),
            "overall_n": int(n_cert_all),
            "passed_overall": passed_overall,
            "group_pac": group_pac_info,
        })
        if passed_overall:
            dx2_certified = True
            break
        scale = float(max(1.05, min(ratio_pac * 1.01, 1.25))) if math.isfinite(ratio_pac) else 1.15
        for g in GROUPS:
            q_dx2_plan[g] = float(q_dx2_plan[g] * scale)

    # 6. Chạy kiểm tra 360 lượt cho cả 11 phương pháp (B0 dùng chung từ shared_b0)
    all_episodes: list[dict[str, Any]] = list(b0_test_eps)
    all_cycles: list[dict[str, Any]] = list(b0_test_cycs)

    non_aci_specs: list[tuple[str, Any, str]] = [
        ("B1", (q_b1, 0.0), "const"),
        ("B2", (q_b1, 0.3), "const"),
        ("B3", (q_b3, 0.0), "const"),
        ("B3′", (q_b3p, 0.0), "const"),
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
    raw_non_aci_cycs = [c for r in res_non_aci for c in r["cycles"]]
    for r in res_non_aci:
        all_episodes.append(r["episode"])
    mark_thinned_cycles(raw_non_aci_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    all_cycles.extend(raw_non_aci_cycs)

    # B6 (ACI trên A_h, CHỈ cập nhật trên chu kỳ có tác nhân)
    b6_eps, b6_cycs, b6_final_alphas = run_aci_test_suite(
        method="B6",
        seeds=TEST_SEEDS,
        init_scores=ah_scores[-500:],
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="A_h_max",
        update_on_empty=False,
        workers=workers,
        seed_base=seed_base,
    )
    mark_thinned_cycles(b6_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    all_episodes.extend(b6_eps)
    all_cycles.extend(b6_cycs)

    # ĐX-3 (ACI trên R, CHỈ cập nhật trên chu kỳ có tác nhân)
    dx3_eps, dx3_cycs, dx3_final_alphas = run_aci_test_suite(
        method="ĐX-3",
        seeds=TEST_SEEDS,
        init_scores=r_scores[-500:],
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="R",
        update_on_empty=False,
        workers=workers,
        seed_base=seed_base,
    )
    mark_thinned_cycles(dx3_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    all_episodes.extend(dx3_eps)
    all_cycles.extend(dx3_cycs)

    m_rank = {m: i for i, m in enumerate(NEW_METHODS)}
    all_episodes.sort(key=lambda e: (m_rank[e["method"]], e["cond"], e["scn"], e["seed"]))
    all_cycles.sort(key=lambda c: (m_rank[c["method"]], c["cond"], c["scn"], c["seed"], c["t"]))

    config = {
        "scheme": "new_proposed",
        "seed_base": int(seed_base),
        "alpha": float(alpha),
        "d_s": float(D_S),
        "H": int(H_STEPS),
        "thinning_s": 3.0,
        "keep_empty_cycles": False,
        "overlapping_thinning": False,
        "agent_error_metric": "A_h",
        "certification_method": "PAC_Bonferroni",
        "pac_delta_total": PAC_DELTA_TOTAL,
        "pac_delta_per_try": PAC_DELTA_PER_TRY,
        "aci_update_on_empty": False,
        "aci_gamma": 0.02,
        "aci_window": 500,
        "methods": NEW_METHODS,
        "alpha_sweep_values": ALPHA_SWEEP_VALUES,
        "alpha_sweep_methods": ALPHA_SWEEP_METHODS,
        "seeds": {
            "sigma_est": [200, 249],
            "calib_blocks": [[b[0], b[-1]] for b in CALIB_BLOCK_SEEDS],
            "cert_blocks": [[b[0], b[-1]] for b in CERT_BLOCK_SEEDS],
            "test": [TEST_SEEDS[0], TEST_SEEDS[-1]],
        },
        "code_version": "sim-2d-v1.0",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }

    calibration = {
        "sigma_tau": [float(x) for x in sigma_tau],
        "sigma_source": "empirical_B0_seeds_200_249_q90_monotone_floor0.05",
        "baselines": {
            "q_B1": float(q_b1),
            "q_B2": float(q_b1),
            "B2_extra_m": 0.3,
            "q_B3_A": float(q_b3_a),
            "q_B3_E": float(q_b3_e),
            "q_B3_sum": float(q_b3),
            "q_B3p_a": float(q_b3p_a),
            "q_B3p_b": float(q_b3p_b),
            "q_B3p_sum": float(q_b3p),
            "q_B4_base": float(q_b1),
            "B4_max_E_m": float(max_e_calib),
            "m_B5_3s": float(m_b5_tau[-1]),
            "q_B5_equiv": float(q_b5_equiv),
            "n_b0_calib_thinned_active": len(b0_cal_thinned),
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
        methods_order=NEW_METHODS,
        keep_empty=False,
    )

    # 7. Quét alpha in {0.01, 0.02, 0.05, 0.1, 0.2} cho B1, B3′, ĐX-2 -> logs/new/alpha_sweep.csv
    sweep_rows: list[dict[str, Any]] = []
    sweep_tasks: list[tuple[Any, ...]] = []
    sweep_meta: dict[tuple[str, float], dict[str, Any]] = {}

    for al in ALPHA_SWEEP_VALUES:
        if abs(al - alpha) < 1e-9:
            for m_name in ALPHA_SWEEP_METHODS:
                sm = summary["by_method"][m_name]
                fb_str = "none"
                if m_name == "ĐX-2":
                    fb_str = "none"
                sweep_rows.append({
                    "method": m_name,
                    "alpha": float(al),
                    "coverage": sm["coverage_safe"],
                    "cov_lo": sm["coverage_safe_ci95"][0],
                    "cov_hi": sm["coverage_safe_ci95"][1],
                    "coverage_feasible": sm["coverage_feasible"],
                    "coverage_score": sm["coverage_score"],
                    "violation_cycle": sm["violation_cycle"],
                    "violation_episode": sm["violation_episode"],
                    "collision_rate": sm["collision_rate"],
                    "completion_rate": sm["completion_rate"],
                    "t_end_mean": sm["t_end_mean"],
                    "fallback_pct": sm["fallback_pct"],
                    "q_mean": sm["q_mean"],
                    "m_3s_mean": sm["m_3s_mean"],
                    "n_thinned": sm["n_thinned_cycles"],
                    "n_episodes": sm["n_episodes"],
                    "group_fallbacks": fb_str,
                })
            continue

        # Hiệu chỉnh lại từ tập B0 (250-399) ở mức alpha mới (và hiệu chỉnh lặp 1 vòng cho ĐX-2)
        q_b1_al = conformal_q(ah_scores, al)
        q_b3p_al = max(0.0, conformal_q(a_signed_scores, al / 2.0)) + max(0.0, conformal_q(b_signed_scores, al / 2.0))
        q_dx2_glob_al = max(0.0, conformal_q(r_scores, al))
        q_dx2_al, cnts_al, fbs_al = _group_q_dict_active(b0_cal_thinned, al, q_dx2_glob_al)

        # Vòng tinh chỉnh ĐX-2 trên khối 350-399 để phản ánh đúng vòng kín ở alpha mới
        blk3_tasks = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", dict(q_dx2_al), sigma_tau, "group", seed_base)
            for s in CALIB_BLOCK_SEEDS[2]
        ]
        blk3_res = run_parallel_episodes(blk3_tasks, workers=workers)
        blk3_cycs = [c for r in blk3_res for c in r["cycles"]]
        blk3_th = mark_thinned_cycles(blk3_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        # Kiểm tra số mẫu theo nhóm trên tập 250-399 (150 lượt) để dùng ngưỡng chung nếu nhóm thiếu mẫu theo Hệ quả 1
        fb_list = [g for g, is_fb in fbs_al.items() if is_fb]
        q_blk3_glob = max(0.0, conformal_q([c["R"] for c in blk3_th], al))
        # Chỉ giữ ngưỡng theo nhóm nếu tập hiệu chỉnh tổng (150 lượt) đủ ceil(1/alpha)-1 mẫu
        for g in GROUPS:
            if not fbs_al[g]:
                g_scores_b3 = [c["R"] for c in blk3_th if c["g"] == g]
                if len(g_scores_b3) >= int(math.ceil(1.0 / al)) - 1:
                    q_dx2_al[g] = float(0.5 * q_dx2_al[g] + 0.5 * conformal_q(g_scores_b3, al))

        fb_str = ",".join(fb_list) if fb_list else "none"
        sweep_meta[("B1", al)] = {"arg": (q_b1_al, 0.0), "mode": "const", "fb": "none"}
        sweep_meta[("B3′", al)] = {"arg": (q_b3p_al, 0.0), "mode": "const", "fb": "none"}
        sweep_meta[("ĐX-2", al)] = {"arg": dict(q_dx2_al), "mode": "group", "fb": fb_str}

        for m_name in ALPHA_SWEEP_METHODS:
            meta = sweep_meta[(m_name, al)]
            tag = f"{m_name}@a={al}"
            for cond in CONDITIONS:
                for scn in SCENARIOS:
                    for seed in TEST_SEEDS:
                        sweep_tasks.append((seed, scn, cond, tag, meta["arg"], sigma_tau, meta["mode"], seed_base))

    if sweep_tasks:
        sweep_res = run_parallel_episodes(sweep_tasks, workers=workers)
        by_tag_eps: dict[str, list[dict[str, Any]]] = {}
        by_tag_cycs: dict[str, list[dict[str, Any]]] = {}
        for r in sweep_res:
            tag = r["episode"]["method"]
            by_tag_eps.setdefault(tag, []).append(r["episode"])
            by_tag_cycs.setdefault(tag, []).extend(r["cycles"])

        for al in ALPHA_SWEEP_VALUES:
            if abs(al - alpha) < 1e-9:
                continue
            for m_name in ALPHA_SWEEP_METHODS:
                tag = f"{m_name}@a={al}"
                eps_t = by_tag_eps[tag]
                cycs_t = by_tag_cycs[tag]
                th_t = mark_thinned_cycles(cycs_t, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                sm = summarize_group(eps_t, th_t, keep_empty=False)
                sweep_rows.append({
                    "method": m_name,
                    "alpha": float(al),
                    "coverage": sm["coverage_safe"],
                    "cov_lo": sm["coverage_safe_ci95"][0],
                    "cov_hi": sm["coverage_safe_ci95"][1],
                    "coverage_feasible": sm["coverage_feasible"],
                    "coverage_score": sm["coverage_score"],
                    "violation_cycle": sm["violation_cycle"],
                    "violation_episode": sm["violation_episode"],
                    "collision_rate": sm["collision_rate"],
                    "completion_rate": sm["completion_rate"],
                    "t_end_mean": sm["t_end_mean"],
                    "fallback_pct": sm["fallback_pct"],
                    "q_mean": sm["q_mean"],
                    "m_3s_mean": sm["m_3s_mean"],
                    "n_thinned": sm["n_thinned_cycles"],
                    "n_episodes": sm["n_episodes"],
                    "group_fallbacks": sweep_meta[(m_name, al)]["fb"],
                })

    sweep_rows.sort(key=lambda r: (ALPHA_SWEEP_METHODS.index(r["method"]), r["alpha"]))
    sweep_fields = [
        "method", "alpha", "coverage", "cov_lo", "cov_hi", "coverage_feasible",
        "coverage_score", "violation_cycle", "violation_episode", "collision_rate",
        "completion_rate", "t_end_mean", "fallback_pct", "q_mean", "m_3s_mean",
        "n_thinned", "n_episodes", "group_fallbacks",
    ]
    with open(out_dir / "alpha_sweep.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sweep_fields)
        w.writeheader()
        for row in sweep_rows:
            w.writerow(row)

    return {
        "config": config,
        "calibration": calibration,
        "summary": summary,
        "alpha_sweep": sweep_rows,
    }
