"""Chạy bộ mô phỏng mở rộng v0.2: tập IN, OOD-S, OOD-D, OOD-SD và RECAL (SPEC §9.3 & §9.8)."""

from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm as _norm_dist

from sim.common import (
    CALIB_BLOCK_SEEDS,
    OOD_SEEDS,
    RECAL_CALIB_BLOCKS,
    RECAL_CERT_SEEDS,
    RECAL_TEST_SEEDS,
    TEST_SEEDS,
    condition_for_seed,
    condition_for_seed_ext,
    conformal_q,
    mark_thinned_cycles,
    pac_conformal_q,
    rescore_cycles_with_sigma,
    run_aci_ext_suite,
    run_parallel_episodes,
    scenario_for_seed,
    scenario_for_seed_ext,
    write_ext_logs,
)
from sim.conditions_ext import CONDITIONS_EXT
from sim.core import (
    ALL_CONDITIONS,
    ALL_SCENARIOS,
    CONDITIONS,
    DEFAULT_SIGMA_OLD,
    D_S,
    GROUPS,
    H_STEPS,
    SCENARIOS,
    condition_for_seed as _cond_v01,
)
from sim.scenarios_ext import SCENARIOS_EXT

EXT_METHODS: list[str] = ["B0", "B1", "B2", "B3", "B3′", "B4", "B5", "B6", "ĐX-1", "ĐX-2", "ĐX-3"]
EXT_SPLITS: list[str] = ["IN", "OOD-S", "OOD-D", "OOD-SD", "RECAL"]
RECAL_CERT_BLOCKS: list[list[int]] = [
    list(RECAL_CERT_SEEDS),      # 950-999 (SPEC §9.6)
    list(range(1400, 1450)),     # khối dự phòng nếu cần thử lần 2
    list(range(1450, 1500)),     # khối dự phòng nếu cần thử lần 3
]
PAC_DELTA_TOTAL: float = 0.05
PAC_MAX_TRIES: int = 3
PAC_DELTA_PER_TRY: float = PAC_DELTA_TOTAL / PAC_MAX_TRIES


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


def _extract_b0_thinned(
    b0_results: list[dict[str, Any]],
    sigma_tau: np.ndarray,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    eps = [dict(r["episode"]) for r in b0_results]
    raw_cycs: list[dict[str, Any]] = []
    for r in b0_results:
        raw_cycs.extend(rescore_cycles_with_sigma(r["cycles"], sigma_tau))
    thinned = mark_thinned_cycles(raw_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    return eps, raw_cycs, thinned


def _compute_baselines_from_b0_thinned(
    b0_thinned: list[dict[str, Any]],
    sigma_tau: np.ndarray,
    alpha: float,
) -> dict[str, Any]:
    ah_scores = [c["A_h_max"] for c in b0_thinned]
    e_scores = [c["E_max_norm"] for c in b0_thinned]
    a_signed = [c["a_max_norm"] for c in b0_thinned]
    b_signed = [c["b_max_norm"] for c in b0_thinned]
    r_scores = [c["R"] for c in b0_thinned]

    q_b1 = conformal_q(ah_scores, alpha)
    q_b3_a = conformal_q(ah_scores, alpha / 2.0)
    q_b3_e = conformal_q(e_scores, alpha / 2.0)
    q_b3 = q_b3_a + q_b3_e
    q_b3p_a = max(0.0, conformal_q(a_signed, alpha / 2.0))
    q_b3p_b = max(0.0, conformal_q(b_signed, alpha / 2.0))
    q_b3p = q_b3p_a + q_b3p_b
    max_e_calib = float(max(c["E_max_m"] for c in b0_thinned))

    a_mat = np.array([c["a_tau"] for c in b0_thinned], dtype=float)
    b_mat = np.array([c["b_tau"] for c in b0_thinned], dtype=float)
    s_a_tau = np.std(a_mat, axis=0, ddof=1)
    s_e_tau = np.std(b_mat, axis=0, ddof=1)
    z_alpha = float(_norm_dist.ppf(1.0 - alpha))
    m_b5_tau = z_alpha * np.sqrt(s_a_tau**2 + s_e_tau**2)
    q_b5_equiv = float(m_b5_tau[-1] / sigma_tau[-1])

    return {
        "q_b1": float(q_b1),
        "q_b3_a": float(q_b3_a),
        "q_b3_e": float(q_b3_e),
        "q_b3": float(q_b3),
        "q_b3p_a": float(q_b3p_a),
        "q_b3p_b": float(q_b3p_b),
        "q_b3p": float(q_b3p),
        "max_e_calib": max_e_calib,
        "m_b5_tau": m_b5_tau,
        "q_b5_equiv": q_b5_equiv,
        "ah_scores": ah_scores,
        "r_scores": r_scores,
    }


def _run_split_with_calib(
    split_name: str,
    scenarios_list: tuple[str, ...] | list[str],
    conditions_list: tuple[str, ...] | list[str],
    seeds: list[int],
    sigma_tau: np.ndarray,
    calib_params: dict[str, Any],
    alpha: float,
    workers: int,
    seed_base: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Chạy cả 11 phương pháp cho một tập phân phối (IN, OOD-S, OOD-D, OOD-SD hoặc RECAL)."""
    non_aci_specs: list[tuple[str, Any, str]] = [
        ("B0", (0.0, 0.0), "const"),
        ("B1", (calib_params["q_b1"], 0.0), "const"),
        ("B2", (calib_params["q_b1"], 0.3), "const"),
        ("B3", (calib_params["q_b3"], 0.0), "const"),
        ("B3′", (calib_params["q_b3p"], 0.0), "const"),
        ("B4", (calib_params["q_b1"], calib_params["max_e_calib"]), "const"),
        ("B5", (calib_params["m_b5_tau"], calib_params["q_b5_equiv"]), "vector"),
        ("ĐX-1", (calib_params["q_dx1"], 0.0), "const"),
        ("ĐX-2", dict(calib_params["q_dx2"]), "group"),
    ]

    opts = {"split": split_name, "keep_tau_arrays": False, "compute_open_loop": True}
    tasks = []
    for m_name, m_arg, m_mode in non_aci_specs:
        for cond in conditions_list:
            for scn in scenarios_list:
                for seed in seeds:
                    tasks.append((seed, scn, cond, m_name, m_arg, sigma_tau, m_mode, seed_base, opts))

    res_non_aci = run_parallel_episodes(tasks, workers=workers)
    eps: list[dict[str, Any]] = [r["episode"] for r in res_non_aci]
    cycs: list[dict[str, Any]] = [c for r in res_non_aci for c in r["cycles"]]

    # Chạy B6 và ĐX-3 (ACI giữ trạng thái tuần tự trong mỗi điều kiện)
    b6_eps, b6_cycs, b6_alphas = run_aci_ext_suite(
        method="B6",
        split=split_name,
        scenarios_list=scenarios_list,
        conditions_list=conditions_list,
        seeds=seeds,
        init_scores=calib_params["ah_scores"][-500:],
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="A_h_max",
        update_on_empty=False,
        gamma=0.02,
        window_size=500,
        workers=workers,
        seed_base=seed_base,
        opts={"keep_tau_arrays": False, "compute_open_loop": True},
    )
    dx3_eps, dx3_cycs, dx3_alphas = run_aci_ext_suite(
        method="ĐX-3",
        split=split_name,
        scenarios_list=scenarios_list,
        conditions_list=conditions_list,
        seeds=seeds,
        init_scores=calib_params["r_scores"][-500:],
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="R",
        update_on_empty=False,
        gamma=0.02,
        window_size=500,
        workers=workers,
        seed_base=seed_base,
        opts={"keep_tau_arrays": False, "compute_open_loop": True},
    )

    eps.extend(b6_eps)
    eps.extend(dx3_eps)
    cycs.extend(b6_cycs)
    cycs.extend(dx3_cycs)

    mark_thinned_cycles(cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    aci_info = {"B6": b6_alphas, "ĐX-3": dx3_alphas}
    return eps, cycs, aci_info


def calibrate_and_certify_recal(
    sigma_tau: np.ndarray,
    alpha: float,
    workers: int,
    seed_base: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Hiệu chỉnh lại và chứng nhận PAC trên tập trộn S1–S10 x D0–D10 (800–999)."""
    b0_cal_tasks = [
        (
            s,
            scenario_for_seed_ext(s),
            condition_for_seed_ext(s, seed_base),
            "B0",
            (0.0, 0.0),
            DEFAULT_SIGMA_OLD,
            "const",
            seed_base,
            {"keep_tau_arrays": True, "compute_open_loop": False},
        )
        for block in RECAL_CALIB_BLOCKS
        for s in block
    ]
    b0_cal_res = run_parallel_episodes(b0_cal_tasks, workers=workers)
    _, _, b0_cal_thinned = _extract_b0_thinned(b0_cal_res, sigma_tau)
    base = _compute_baselines_from_b0_thinned(b0_cal_thinned, sigma_tau, alpha)

    # Thuật toán 1 cho ĐX-1 (3 khối 800-849, 850-899, 900-949)
    b0_blk1_th = [c for c in b0_cal_thinned if c["seed"] in RECAL_CALIB_BLOCKS[0]]
    q_dx1_curr = max(0.0, conformal_q([c["R"] for c in b0_blk1_th], alpha))
    dx1_iters: list[dict[str, Any]] = []
    for k_idx, blk_seeds in enumerate(RECAL_CALIB_BLOCKS, start=1):
        tasks = [
            (
                s, scenario_for_seed_ext(s), condition_for_seed_ext(s, seed_base),
                "ĐX-1", (q_dx1_curr, 0.0), sigma_tau, "const", seed_base,
                {"keep_tau_arrays": False, "compute_open_loop": False},
            )
            for s in blk_seeds
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

    # Chứng nhận PAC (950-999 ở lần thử 1; nếu cần thì dùng các khối dự phòng 1400-1449, 1450-1499)
    q_dx1_plan = float(q_dx1_curr)
    dx1_cert_tries: list[dict[str, Any]] = []
    dx1_certified = False
    for try_idx, cert_seeds in enumerate(RECAL_CERT_BLOCKS, start=1):
        tasks = [
            (
                s, scenario_for_seed_ext(s), condition_for_seed_ext(s, seed_base),
                "ĐX-1", (q_dx1_plan, 0.0), sigma_tau, "const", seed_base,
                {"keep_tau_arrays": False, "compute_open_loop": False},
            )
            for s in cert_seeds
        ]
        res_cert = run_parallel_episodes(tasks, workers=workers)
        cycs_cert = [c for r in res_cert for c in r["cycles"]]
        th_cert = mark_thinned_cycles(cycs_cert, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        r_cert = [c["R"] for c in th_cert]
        q_pac, k_pac, n_cert = pac_conformal_q(r_cert, alpha, PAC_DELTA_PER_TRY)
        q_cond = conformal_q(r_cert, alpha)
        passed = bool(q_pac <= q_dx1_plan)
        dx1_cert_tries.append({
            "try": try_idx,
            "q_plan": float(q_dx1_plan),
            "q_pac": float(q_pac) if math.isfinite(q_pac) else None,
            "q_cond": float(q_cond),
            "k_pac": int(k_pac),
            "n_thinned": int(n_cert),
            "n_covered": sum(1 for v in r_cert if v <= q_dx1_plan),
            "passed": passed,
        })
        if passed:
            dx1_certified = True
            break
        if math.isfinite(q_pac):
            q_dx1_plan = float(max(q_dx1_plan * 1.05, min(q_pac * 1.01, q_dx1_plan * 1.35)))
        else:
            q_dx1_plan = float(q_dx1_plan * 1.15)

    # Thuật toán 1 + chứng nhận PAC cho ĐX-2
    q_g0_glob = max(0.0, conformal_q([c["R"] for c in b0_blk1_th], alpha))
    q_dx2_curr, _, _ = _group_q_dict_active(b0_blk1_th, alpha, q_g0_glob)
    dx2_iters: list[dict[str, Any]] = []
    for k_idx, blk_seeds in enumerate(RECAL_CALIB_BLOCKS, start=1):
        tasks = [
            (
                s, scenario_for_seed_ext(s), condition_for_seed_ext(s, seed_base),
                "ĐX-2", dict(q_dx2_curr), sigma_tau, "group", seed_base,
                {"keep_tau_arrays": False, "compute_open_loop": False},
            )
            for s in blk_seeds
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
    for try_idx, cert_seeds in enumerate(RECAL_CERT_BLOCKS, start=1):
        tasks = [
            (
                s, scenario_for_seed_ext(s), condition_for_seed_ext(s, seed_base),
                "ĐX-2", dict(q_dx2_plan), sigma_tau, "group", seed_base,
                {"keep_tau_arrays": False, "compute_open_loop": False},
            )
            for s in cert_seeds
        ]
        res_cert = run_parallel_episodes(tasks, workers=workers)
        cycs_cert = [c for r in res_cert for c in r["cycles"]]
        th_cert = mark_thinned_cycles(cycs_cert, every_s=3.0, keep_empty=False, overlapping_bucket=False)

        norm_ratios = [c["R"] / max(q_dx2_plan[c["g"]], 1e-9) for c in th_cert]
        ratio_pac, k_pac_all, n_cert_all = pac_conformal_q(norm_ratios, alpha, PAC_DELTA_PER_TRY)
        passed_overall = bool(ratio_pac <= 1.0)
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
        scale = float(max(1.05, min(ratio_pac * 1.01, 1.35))) if math.isfinite(ratio_pac) else 1.15
        for g in GROUPS:
            q_dx2_plan[g] = float(q_dx2_plan[g] * scale)

    # Kiểm tra hội tụ riêng trên S9 (5 vòng lặp theo PLAN §8.5)
    s9_blocks = [
        list(range(800, 830)),
        list(range(830, 860)),
        list(range(860, 890)),
        list(range(890, 920)),
        list(range(920, 950)),
    ]
    q_s9 = float(q_dx1_curr)
    s9_osc_trace: list[dict[str, Any]] = []
    for k_idx, s9_seeds in enumerate(s9_blocks, start=1):
        t_s9 = [
            (s, "S9", condition_for_seed_ext(s, seed_base), "ĐX-1", (q_s9, 0.0), sigma_tau, "const", seed_base,
             {"keep_tau_arrays": False, "compute_open_loop": False})
            for s in s9_seeds
        ]
        r_s9 = run_parallel_episodes(t_s9, workers=workers)
        c_s9 = [c for r in r_s9 for c in r["cycles"]]
        th_s9 = mark_thinned_cycles(c_s9, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        q_s9_next = max(0.0, conformal_q([c["R"] for c in th_s9], alpha))
        s9_osc_trace.append({
            "iter": k_idx,
            "q_in": float(q_s9),
            "q_out": float(q_s9_next),
            "delta_q": float(q_s9_next - q_s9),
            "n_thinned": len(th_s9),
        })
        q_s9 = q_s9_next

    calib_recal_json = {
        "sigma_tau": [float(x) for x in sigma_tau],
        "sigma_source": "frozen_from_v0.1_seeds_200_249",
        "baselines": {
            "q_B1": base["q_b1"],
            "q_B2": base["q_b1"],
            "B2_extra_m": 0.3,
            "q_B3_A": base["q_b3_a"],
            "q_B3_E": base["q_b3_e"],
            "q_B3_sum": base["q_b3"],
            "q_B3p_a": base["q_b3p_a"],
            "q_B3p_b": base["q_b3p_b"],
            "q_B3p_sum": base["q_b3p"],
            "q_B4_base": base["q_b1"],
            "B4_max_E_m": base["max_e_calib"],
            "m_B5_3s": float(base["m_b5_tau"][-1]),
            "q_B5_equiv": base["q_b5_equiv"],
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
        "s9_algorithm1_5iter_trace": s9_osc_trace,
    }

    calib_params = dict(base)
    calib_params["q_dx1"] = float(q_dx1_plan)
    calib_params["q_dx2"] = {g: float(v) for g, v in q_dx2_plan.items()}
    return calib_params, calib_recal_json


def run_ood_and_recal(
    root: Path,
    seed_base: int = 0,
    workers: int = 8,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """Chạy đầy đủ tập IN, OOD-S, OOD-D, OOD-SD và RECAL, ghi logs/ext/."""
    logs_new = root / "logs" / "B"
    logs_ext = root / "logs" / "ext"
    logs_ext.mkdir(parents=True, exist_ok=True)

    with open(logs_new / "calibration.json", encoding="utf-8") as f:
        cal_v01 = json.load(f)
    sigma_tau = np.array(cal_v01["sigma_tau"], dtype=float)

    # Tái tạo đúng ah_scores, r_scores và m_b5_tau của v0.1 từ hạt giống 250-399 (150 lượt)
    b0_v01_tasks = [
        (
            s, scenario_for_seed(s), _cond_v01(s, seed_base), "B0",
            (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base,
            {"keep_tau_arrays": True, "compute_open_loop": False},
        )
        for blk in CALIB_BLOCK_SEEDS
        for s in blk
    ]
    b0_v01_res = run_parallel_episodes(b0_v01_tasks, workers=workers)
    _, _, b0_v01_th = _extract_b0_thinned(b0_v01_res, sigma_tau)
    v01_base = _compute_baselines_from_b0_thinned(b0_v01_th, sigma_tau, alpha)
    v01_params = {
        **v01_base,
        "q_b1": float(cal_v01["baselines"]["q_B1"]),
        "q_b3": float(cal_v01["baselines"]["q_B3_sum"]),
        "q_b3p": float(cal_v01["baselines"]["q_B3p_sum"]),
        "max_e_calib": float(cal_v01["baselines"]["B4_max_E_m"]),
        "q_dx1": float(cal_v01["DX-1"]["q_final"]),
        "q_dx2": {g: float(v) for g, v in cal_v01["DX-2"]["q_final_by_group"].items()},
    }

    all_eps: list[dict[str, Any]] = []
    all_cycs: list[dict[str, Any]] = []
    aci_alphas_by_split: dict[str, Any] = {}

    split_specs = [
        ("IN", SCENARIOS, CONDITIONS, TEST_SEEDS, v01_params),
        ("OOD-S", SCENARIOS_EXT, CONDITIONS, OOD_SEEDS, v01_params),
        ("OOD-D", SCENARIOS, CONDITIONS_EXT, OOD_SEEDS, v01_params),
        ("OOD-SD", SCENARIOS_EXT, CONDITIONS_EXT, OOD_SEEDS, v01_params),
    ]
    for sp_name, scns_sp, conds_sp, seeds_sp, params_sp in split_specs:
        print(f"  -> Đang chạy tập {sp_name} ({len(scns_sp)*len(conds_sp)*len(seeds_sp)*len(EXT_METHODS)} lượt)...", flush=True)
        eps_sp, cycs_sp, aci_sp = _run_split_with_calib(
            sp_name, scns_sp, conds_sp, seeds_sp, sigma_tau, params_sp, alpha, workers, seed_base
        )
        all_eps.extend(eps_sp)
        all_cycs.extend(cycs_sp)
        aci_alphas_by_split[sp_name] = aci_sp

    # Hiệu chỉnh lại + chứng nhận PAC cho RECAL và chạy kiểm tra trên 710-719
    print("  -> Đang hiệu chỉnh & chứng nhận RECAL (hạt giống 800–999)...", flush=True)
    recal_params, cal_recal_json = calibrate_and_certify_recal(sigma_tau, alpha, workers, seed_base)

    print(f"  -> Đang chạy tập RECAL ({len(ALL_SCENARIOS)*len(ALL_CONDITIONS)*len(RECAL_TEST_SEEDS)*len(EXT_METHODS)} lượt)...", flush=True)
    eps_rec, cycs_rec, aci_rec = _run_split_with_calib(
        "RECAL", ALL_SCENARIOS, ALL_CONDITIONS, RECAL_TEST_SEEDS, sigma_tau, recal_params, alpha, workers, seed_base
    )
    all_eps.extend(eps_rec)
    all_cycs.extend(cycs_rec)
    aci_alphas_by_split["RECAL"] = aci_rec
    cal_recal_json["aci_final_alpha_by_split"] = aci_alphas_by_split

    with open(logs_ext / "calibration_recal.json", "w", encoding="utf-8") as f:
        json.dump(cal_recal_json, f, ensure_ascii=False, indent=2)

    sp_rank = {sp: i for i, sp in enumerate(EXT_SPLITS)}
    m_rank = {m: i for i, m in enumerate(EXT_METHODS)}
    all_eps.sort(key=lambda e: (sp_rank[e["split"]], m_rank[e["method"]], e["cond"], e["scn"], e["seed"]))
    all_cycs.sort(key=lambda c: (sp_rank[c["split"]], m_rank[c["method"]], c["cond"], c["scn"], c["seed"], c["t"]))

    config = {
        "scheme": "extended_v0.2",
        "seed_base": int(seed_base),
        "alpha": float(alpha),
        "d_s": float(D_S),
        "H": int(H_STEPS),
        "thinning_s": 3.0,
        "keep_empty_cycles": False,
        "overlapping_thinning": False,
        "methods": EXT_METHODS,
        "splits": EXT_SPLITS,
        "scenarios_v01": list(SCENARIOS),
        "scenarios_ext": list(SCENARIOS_EXT),
        "conditions_v01": list(CONDITIONS),
        "conditions_ext": list(CONDITIONS_EXT),
        "seeds": {
            "in_test": [TEST_SEEDS[0], TEST_SEEDS[-1]],
            "ood_test": [OOD_SEEDS[0], OOD_SEEDS[-1]],
            "recal_test": [RECAL_TEST_SEEDS[0], RECAL_TEST_SEEDS[-1]],
            "recal_calib": [[b[0], b[-1]] for b in RECAL_CALIB_BLOCKS],
            "recal_cert": [[b[0], b[-1]] for b in RECAL_CERT_BLOCKS],
        },
        "code_version": "sim-2d-v0.2",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }

    summary = write_ext_logs(
        out_dir=logs_ext,
        config=config,
        episodes=all_eps,
        cycles=all_cycs,
        methods_order=EXT_METHODS,
        splits_order=EXT_SPLITS,
    )

    return {
        "config": config,
        "calibration_recal": cal_recal_json,
        "summary": summary,
        "v01_params": v01_params,
        "recal_params": recal_params,
        "sigma_tau": sigma_tau,
    }
