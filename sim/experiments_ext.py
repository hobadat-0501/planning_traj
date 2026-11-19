"""Thí nghiệm bổ sung E1–E9 cho giai đoạn mở rộng v0.2 (SPEC §9.4)."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sim.common import (
    CALIB_BLOCK_SEEDS,
    D2_CALIB_BLOCKS,
    D2_CERT_BLOCKS,
    OOD_SEEDS,
    SIGMA_SCN_SEEDS,
    TEST_IN_EXTRA_SEEDS,
    TEST_SEEDS,
    AdaptiveConformalState,
    clopper_pearson,
    condition_for_seed,
    conformal_q,
    mark_thinned_cycles,
    pac_conformal_q,
    pac_order_index,
    rescore_cycles_with_sigma,
    run_parallel_episodes,
    scenario_for_seed,
    summarize_group,
)
from sim.conditions_ext import CONDITIONS_EXT
from sim.core import (
    ALL_CONDITIONS,
    ALL_SCENARIOS,
    CONDITIONS,
    DEFAULT_SIGMA_OLD,
    GROUPS,
    H_STEPS,
    SCENARIOS,
    run_episode,
)
from sim.run_ext import _compute_baselines_from_b0_thinned, _extract_b0_thinned, _group_q_dict_active
from sim.run_new import estimate_sigma_tau
from sim.scenarios_ext import SCENARIOS_EXT

E1_ALPHAS: list[float] = [0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20]
E1_METHODS: list[str] = ["B1", "B3′", "ĐX-1", "ĐX-2"]


# ==============================================================================
# E1: So sánh ở cùng độ phủ thực nghiệm + KTC bootstrap 2.000 lần
# ==============================================================================

def _interp_at_cov(covs: np.ndarray, vals: np.ndarray, target_cov: float) -> tuple[float, bool]:
    """Nội suy tuyến tính giá trị (t_end hoặc m_3s) tại mức độ phủ thực nghiệm target_cov."""
    order = np.argsort(covs)
    xs = covs[order]
    ys = vals[order]
    in_range = bool(xs[0] <= target_cov <= xs[-1])
    val = float(np.interp(target_cov, xs, ys))
    return val, in_range


def run_e1_iso_coverage(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    b0_v01_th: list[dict[str, Any]],
    workers: int,
    seed_base: int,
) -> dict[str, Any]:
    """E1: Quét 8 mức alpha cho B1, B3′, ĐX-1, ĐX-2 trên IN và OOD-SD; nội suy tại 0.90/0.95."""
    print("  [E1] Quét 8 mức alpha trên IN và OOD-SD...", flush=True)
    ah_scores = [c["A_h_max"] for c in b0_v01_th]
    a_signed = [c["a_max_norm"] for c in b0_v01_th]
    b_signed = [c["b_max_norm"] for c in b0_v01_th]
    r_scores = [c["R"] for c in b0_v01_th]

    cal_params_by_alpha: dict[float, dict[str, Any]] = {}
    for al in E1_ALPHAS:
        q_b1 = conformal_q(ah_scores, al)
        q_b3p = max(0.0, conformal_q(a_signed, al / 2.0)) + max(0.0, conformal_q(b_signed, al / 2.0))
        q_dx1_init = max(0.0, conformal_q(r_scores, al))
        q_dx2_glob = q_dx1_init
        q_dx2_init, _, fbs = _group_q_dict_active(b0_v01_th, al, q_dx2_glob)

        # 1 vòng tinh chỉnh vòng kín trên khối 350-399 cho ĐX-1 và ĐX-2
        t_dx1 = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", (q_dx1_init, 0.0),
             sigma_tau, "const", seed_base, {"keep_tau_arrays": False, "compute_open_loop": False})
            for s in CALIB_BLOCK_SEEDS[2]
        ]
        t_dx2 = [
            (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", dict(q_dx2_init),
             sigma_tau, "group", seed_base, {"keep_tau_arrays": False, "compute_open_loop": False})
            for s in CALIB_BLOCK_SEEDS[2]
        ]
        res_ref = run_parallel_episodes(t_dx1 + t_dx2, workers=workers)
        c1 = [c for r in res_ref[:len(t_dx1)] for c in r["cycles"]]
        c2 = [c for r in res_ref[len(t_dx1):] for c in r["cycles"]]
        th1 = mark_thinned_cycles(c1, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        th2 = mark_thinned_cycles(c2, every_s=3.0, keep_empty=False, overlapping_bucket=False)

        q_dx1_cal = max(0.0, conformal_q([c["R"] for c in th1], al))
        if not math.isfinite(q_dx1_cal):
            q_dx1_cal = q_dx1_init
        q_dx2_cal = dict(q_dx2_init)
        min_n = int(math.ceil(1.0 / al)) - 1
        for g in GROUPS:
            if not fbs[g]:
                gs = [c["R"] for c in th2 if c["g"] == g]
                if len(gs) >= min_n:
                    qg = conformal_q(gs, al)
                    if math.isfinite(qg):
                        q_dx2_cal[g] = float(0.5 * q_dx2_init[g] + 0.5 * qg)

        cal_params_by_alpha[al] = {
            "B1": ((q_b1, 0.0), "const"),
            "B3′": ((q_b3p, 0.0), "const"),
            "ĐX-1": ((q_dx1_cal, 0.0), "const"),
            "ĐX-2": (q_dx2_cal, "group"),
        }

    split_defs = [
        ("IN", SCENARIOS, CONDITIONS, TEST_SEEDS),
        ("OOD-SD", SCENARIOS_EXT, CONDITIONS_EXT, OOD_SEEDS),
    ]
    all_tasks = []
    for sp_name, scns, conds, seeds in split_defs:
        opts = {"split": sp_name, "keep_tau_arrays": False, "compute_open_loop": False}
        for al in E1_ALPHAS:
            for m in E1_METHODS:
                m_arg, m_mode = cal_params_by_alpha[al][m]
                tag = f"{sp_name}|{m}|{al:.4f}"
                for cond in conds:
                    for scn in scns:
                        for s in seeds:
                            all_tasks.append((s, scn, cond, tag, m_arg, sigma_tau, m_mode, seed_base, opts))

    raw_res = run_parallel_episodes(all_tasks, workers=workers)
    by_tag_eps: dict[str, list[dict[str, Any]]] = {}
    by_tag_cycs: dict[str, list[dict[str, Any]]] = {}
    for r in raw_res:
        tag = r["episode"]["method"]
        by_tag_eps.setdefault(tag, []).append(r["episode"])
        by_tag_cycs.setdefault(tag, []).extend(r["cycles"])

    sweep_rows: list[dict[str, Any]] = []
    # Lưu dữ liệu theo từng lượt để bootstrap chính xác theo lượt
    ep_records: dict[tuple[str, str, float], list[dict[str, Any]]] = {}

    for sp_name, _, _, _ in split_defs:
        for al in E1_ALPHAS:
            for m in E1_METHODS:
                tag = f"{sp_name}|{m}|{al:.4f}"
                eps_t = by_tag_eps[tag]
                cycs_t = by_tag_cycs[tag]
                th_t = mark_thinned_cycles(cycs_t, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                sm = summarize_group(eps_t, th_t, keep_empty=False)

                # Nhóm lại theo lượt (scn, cond, seed) để bootstrap
                cyc_by_ep: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
                for c in th_t:
                    if c["has_agents"] == 1:
                        cyc_by_ep.setdefault((c["scn"], c["cond"], c["seed"]), []).append(c)

                ep_recs_list = []
                for e in sorted(eps_t, key=lambda x: (x["scn"], x["cond"], x["seed"])):
                    cs = cyc_by_ep.get((e["scn"], e["cond"], e["seed"]), [])
                    n_c = len(cs)
                    n_cov = sum(c["covered"] for c in cs)
                    m_sum = sum(c["m_max"] for c in cs if math.isfinite(c["m_max"]))
                    ep_recs_list.append({
                        "scn": e["scn"],
                        "cond": e["cond"],
                        "seed": e["seed"],
                        "t_end": float(e["t_end"]),
                        "n_cyc": n_c,
                        "n_cov": n_cov,
                        "m_sum": m_sum,
                    })
                ep_records[(sp_name, m, al)] = ep_recs_list

                sweep_rows.append({
                    "split": sp_name,
                    "subset": "all",
                    "method": m,
                    "alpha": al,
                    "coverage_score": sm["coverage_score"],
                    "cov_score_lo": sm["coverage_score_ci95"][0],
                    "cov_score_hi": sm["coverage_score_ci95"][1],
                    "coverage_safe": sm["coverage_safe"],
                    "t_end_mean": sm["t_end_mean"],
                    "m_3s_mean": sm["m_3s_mean"],
                    "fallback_pct": sm["fallback_pct"],
                    "collision_rate": sm["collision_rate"],
                    "completion_rate": sm["completion_rate"],
                    "n_thinned": sm["n_thinned_cycles"],
                    "n_episodes": sm["n_episodes"],
                })

                # Thêm hàng cho tập con các ô khó: D1,D2 trên IN; S7,S8 trên OOD-SD
                hard_label = "hard_D1_D2" if sp_name == "IN" else "hard_S7_S8"
                if sp_name == "IN":
                    h_eps = [e for e in eps_t if e["cond"] in ("D1", "D2")]
                    h_th = [c for c in th_t if c["cond"] in ("D1", "D2")]
                else:
                    h_eps = [e for e in eps_t if e["scn"] in ("S7", "S8")]
                    h_th = [c for c in th_t if c["scn"] in ("S7", "S8")]
                sm_h = summarize_group(h_eps, h_th, keep_empty=False)
                sweep_rows.append({
                    "split": sp_name,
                    "subset": hard_label,
                    "method": m,
                    "alpha": al,
                    "coverage_score": sm_h["coverage_score"],
                    "cov_score_lo": sm_h["coverage_score_ci95"][0],
                    "cov_score_hi": sm_h["coverage_score_ci95"][1],
                    "coverage_safe": sm_h["coverage_safe"],
                    "t_end_mean": sm_h["t_end_mean"],
                    "m_3s_mean": sm_h["m_3s_mean"],
                    "fallback_pct": sm_h["fallback_pct"],
                    "collision_rate": sm_h["collision_rate"],
                    "completion_rate": sm_h["completion_rate"],
                    "n_thinned": sm_h["n_thinned_cycles"],
                    "n_episodes": sm_h["n_episodes"],
                })

    csv_fields = [
        "split", "subset", "method", "alpha", "coverage_score", "cov_score_lo", "cov_score_hi",
        "coverage_safe", "t_end_mean", "m_3s_mean", "fallback_pct", "collision_rate",
        "completion_rate", "n_thinned", "n_episodes",
    ]
    with open(logs_ext / "alpha_sweep_ext.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        w.writerows(sweep_rows)

    # Tính hiệu số nội suy tại độ phủ 0.90 và 0.95 kèm bootstrap 2.000 lần theo lượt
    rng = np.random.default_rng(202601)
    n_boot = 2000
    iso_comparisons: list[dict[str, Any]] = []

    subsets_to_eval = [
        ("IN", "all", lambda r: True),
        ("IN", "hard_D1_D2", lambda r: r["cond"] in ("D1", "D2")),
        ("OOD-SD", "all", lambda r: True),
        ("OOD-SD", "hard_S7_S8", lambda r: r["scn"] in ("S7", "S8")),
    ]

    for sp_name, sub_name, pred_fn in subsets_to_eval:
        # Xây dựng ma trận (n_ep, n_alpha) cho từng phương pháp để bootstrap vector hóa
        idx_map: dict[str, dict[str, np.ndarray]] = {}
        n_ep_sub = 0
        for m in E1_METHODS:
            cov_m, tend_m, m3s_m = [], [], []
            for al in E1_ALPHAS:
                recs = [r for r in ep_records[(sp_name, m, al)] if pred_fn(r)]
                n_ep_sub = len(recs)
                cov_m.append([r["n_cov"] for r in recs])
                nc_arr = [r["n_cyc"] for r in recs]
                tend_m.append([r["t_end"] for r in recs])
                m3s_m.append([r["m_sum"] for r in recs])
            idx_map[m] = {
                "n_cov": np.asarray(cov_m, dtype=float).T,   # (n_ep, n_al)
                "n_cyc": np.asarray([r["n_cyc"] for r in ep_records[(sp_name, m, E1_ALPHAS[0])] if pred_fn(r)], dtype=float),
                "n_cyc_mat": np.asarray([[r["n_cyc"] for r in ep_records[(sp_name, m, al)] if pred_fn(r)] for al in E1_ALPHAS], dtype=float).T,
                "t_end": np.asarray(tend_m, dtype=float).T,
                "m_sum": np.asarray(m3s_m, dtype=float).T,
            }

        boot_idx = rng.integers(0, n_ep_sub, size=(n_boot, n_ep_sub))
        for target_cov in (0.90, 0.95):
            for prop_m in ("ĐX-1", "ĐX-2"):
                for base_m in ("B1", "B3′"):
                    # Điểm ước lượng thực nghiệm
                    def _point_curve(m_key: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
                        d = idx_map[m_key]
                        cs = d["n_cov"].sum(axis=0) / np.maximum(d["n_cyc_mat"].sum(axis=0), 1.0)
                        ts = d["t_end"].mean(axis=0)
                        ms = d["m_sum"].sum(axis=0) / np.maximum(d["n_cyc_mat"].sum(axis=0), 1.0)
                        return cs, ts, ms

                    cp, tp, mp = _point_curve(prop_m)
                    cb, tb, mb = _point_curve(base_m)
                    t_prop, in_p = _interp_at_cov(cp, tp, target_cov)
                    m_prop, _ = _interp_at_cov(cp, mp, target_cov)
                    t_base, in_b = _interp_at_cov(cb, tb, target_cov)
                    m_base, _ = _interp_at_cov(cb, mb, target_cov)

                    dt_obs = t_prop - t_base
                    dm_obs = m_prop - m_base

                    dt_boots = np.empty(n_boot, dtype=float)
                    dm_boots = np.empty(n_boot, dtype=float)
                    dp = idx_map[prop_m]
                    db = idx_map[base_m]
                    for bi in range(n_boot):
                        idx = boot_idx[bi]
                        ncp = dp["n_cyc_mat"][idx].sum(axis=0)
                        cp_b = dp["n_cov"][idx].sum(axis=0) / np.maximum(ncp, 1.0)
                        tp_b = dp["t_end"][idx].mean(axis=0)
                        mp_b = dp["m_sum"][idx].sum(axis=0) / np.maximum(ncp, 1.0)

                        ncb = db["n_cyc_mat"][idx].sum(axis=0)
                        cb_b = db["n_cov"][idx].sum(axis=0) / np.maximum(ncb, 1.0)
                        tb_b = db["t_end"][idx].mean(axis=0)
                        mb_b = db["m_sum"][idx].sum(axis=0) / np.maximum(ncb, 1.0)

                        tp_v, _ = _interp_at_cov(cp_b, tp_b, target_cov)
                        tb_v, _ = _interp_at_cov(cb_b, tb_b, target_cov)
                        mp_v, _ = _interp_at_cov(cp_b, mp_b, target_cov)
                        mb_v, _ = _interp_at_cov(cb_b, mb_b, target_cov)
                        dt_boots[bi] = tp_v - tb_v
                        dm_boots[bi] = mp_v - mb_v

                    dt_ci = [float(np.percentile(dt_boots, 2.5)), float(np.percentile(dt_boots, 97.5))]
                    dm_ci = [float(np.percentile(dm_boots, 2.5)), float(np.percentile(dm_boots, 97.5))]
                    iso_comparisons.append({
                        "split": sp_name,
                        "subset": sub_name,
                        "target_cov": target_cov,
                        "proposed": prop_m,
                        "baseline": base_m,
                        "in_range_prop": in_p,
                        "in_range_base": in_b,
                        "t_end_prop": t_prop,
                        "t_end_base": t_base,
                        "delta_t_end": dt_obs,
                        "delta_t_end_ci95": dt_ci,
                        "t_end_sig_better": bool(dt_ci[1] < 0.0),
                        "m_3s_prop": m_prop,
                        "m_3s_base": m_base,
                        "delta_m_3s": dm_obs,
                        "delta_m_3s_ci95": dm_ci,
                        "m_3s_sig_tighter": bool(dm_ci[1] < 0.0),
                    })

    out = {"iso_comparisons": iso_comparisons}
    with open(logs_ext / "e1_iso_coverage.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return {"sweep_rows": sweep_rows, "iso_comparisons": iso_comparisons}


# ==============================================================================
# E2: Ablation 2x2 ACI (cập nhật chu kỳ trống x gamma) -> logs/ext/aci_trace.csv
# ==============================================================================

def _worker_e2_chain(task: tuple[Any, ...]) -> list[dict[str, Any]]:
    m_name, score_key, init_sc, sp_name, scns, cond, seeds, var_name, upd_empty, gamma, sigma_tau, alpha, seed_base = task
    aci = AdaptiveConformalState(
        init_scores=init_sc,
        sigma_tau=sigma_tau,
        alpha=alpha,
        gamma=gamma,
        window_size=500,
        score_key=score_key,
        update_on_empty=upd_empty,
    )
    err_hist: list[float] = []
    rows_local: list[dict[str, Any]] = []

    def _trace_cb(cyc: dict[str, Any]) -> None:
        aci.feedback(cyc)
        if cyc["has_agents"] == 1:
            err_hist.append(float(cyc[score_key] > cyc["q"]))
        elif upd_empty:
            err_hist.append(0.0)
        win_200 = err_hist[-200:]
        roll_cov = 1.0 - float(np.mean(win_200)) if win_200 else 1.0
        rows_local.append({
            "method": m_name,
            "variant": var_name,
            "update_on_empty": int(upd_empty),
            "gamma": gamma,
            "split": sp_name,
            "cond": cond,
            "scn": cyc["scn"],
            "seed": cyc["seed"],
            "t": cyc["t"],
            "has_agents": cyc["has_agents"],
            "alpha_t": round(aci.alpha_t, 6),
            "q": round(float(cyc["q"]), 6),
            "err": int(cyc[score_key] > cyc["q"]) if cyc["has_agents"] == 1 else 0,
            "rolling_cov_200": round(roll_cov, 6),
        })

    for s in seeds:
        for scn in scns:
            run_episode(
                seed=s,
                scenario=scn,
                condition=cond,
                method=m_name,
                margin_fn=aci.margin_fn,
                sigma_tau=sigma_tau,
                feedback_fn=_trace_cb,
                seed_base=seed_base,
                split=sp_name,
                compute_open_loop=False,
                keep_tau_arrays=False,
            )
    return rows_local


def run_e2_aci_ablation(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    workers: int,
    seed_base: int,
) -> list[dict[str, Any]]:
    """E2: Chạy song song ablation 2x2 cho ĐX-3 và B6 trên IN và OOD-D, ghi vết alpha_t."""
    print("  [E2] Chạy ablation 2x2 ACI trên IN và OOD-D...", flush=True)
    from concurrent.futures import ProcessPoolExecutor
    alpha = 0.10

    variants = [
        ("active_only_g0.02", False, 0.02),
        ("all_cycles_g0.02", True, 0.02),
        ("active_only_g0.005", False, 0.005),
        ("all_cycles_g0.005", True, 0.005),
    ]
    split_cfgs = [
        ("IN", list(SCENARIOS), ["D0", "D1", "D2"], list(TEST_SEEDS)),
        ("OOD-D", list(SCENARIOS), ["D6", "D7", "D8", "D10"], list(OOD_SEEDS)),
    ]

    tasks = []
    for m_name, score_key, init_sc in [
        ("ĐX-3", "R", list(v01_params["r_scores"][-500:])),
        ("B6", "A_h_max", list(v01_params["ah_scores"][-500:])),
    ]:
        for sp_name, scns, conds, seeds in split_cfgs:
            for var_name, upd_empty, gamma in variants:
                for cond in conds:
                    tasks.append((
                        m_name, score_key, init_sc, sp_name, scns, cond, seeds,
                        var_name, upd_empty, gamma, sigma_tau, alpha, seed_base,
                    ))

    if workers <= 1:
        res_lists = [_worker_e2_chain(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            res_lists = list(ex.map(_worker_e2_chain, tasks))

    trace_rows = [row for sub in res_lists for row in sub]
    fields = [
        "method", "variant", "update_on_empty", "gamma", "split", "cond",
        "scn", "seed", "t", "has_agents", "alpha_t", "q", "err", "rolling_cov_200",
    ]
    with open(logs_ext / "aci_trace.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(trace_rows)
    return trace_rows


# ==============================================================================
# E4: Khối hiệu chỉnh & chứng nhận chuyên biệt D2 -> calibration_d2.json
# ==============================================================================

def run_e4_d2_specialized(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    workers: int,
    seed_base: int,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """E4: Hiệu chỉnh (1000-1149) và chứng nhận (1150-1299) chuyên biệt D2 cho nhóm loss."""
    print("  [E4] Chạy khối chuyên biệt D2 (1000–1299)...", flush=True)
    delta_try = 0.05 / 3.0

    # 1. Chạy B0 trên 1000-1149 (chỉ D2) để khởi tạo q_loss_0
    b0_d2_tasks = [
        (s, scenario_for_seed(s), "D2", "B0", (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base,
         {"keep_tau_arrays": True, "compute_open_loop": False})
        for blk in D2_CALIB_BLOCKS
        for s in blk
    ]
    b0_d2_res = run_parallel_episodes(b0_d2_tasks, workers=workers)
    _, _, b0_d2_th = _extract_b0_thinned(b0_d2_res, sigma_tau)

    q_fix_base = float(v01_params["q_dx2"]["fix"])
    q_flt_base = float(v01_params["q_dx2"]["float"])
    b0_blk1_loss = [c["R"] for c in b0_d2_th if c["seed"] in D2_CALIB_BLOCKS[0] and c["g"] == "loss"]
    q_loss_curr = max(0.0, conformal_q(b0_blk1_loss, alpha))

    calib_iters = []
    for k_idx, blk in enumerate(D2_CALIB_BLOCKS, start=1):
        q_dict = {"fix": q_fix_base, "float": q_flt_base, "loss": q_loss_curr}
        tasks = [
            (s, scenario_for_seed(s), "D2", "ĐX-2", q_dict, sigma_tau, "group", seed_base,
             {"keep_tau_arrays": False, "compute_open_loop": False})
            for s in blk
        ]
        res_b = run_parallel_episodes(tasks, workers=workers)
        cycs_b = [c for r in res_b for c in r["cycles"]]
        th_b = mark_thinned_cycles(cycs_b, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        loss_scores = [c["R"] for c in th_b if c["g"] == "loss"]
        q_next = max(0.0, conformal_q(loss_scores, alpha))
        calib_iters.append({
            "iter": k_idx,
            "n_thinned_total": len(th_b),
            "n_loss": len(loss_scores),
            "q_loss_in": float(q_loss_curr),
            "q_loss_out": float(q_next),
        })
        q_loss_curr = q_next

    # 2. Chứng nhận trên D2_CERT_BLOCKS (1150-1199, 1200-1249, 1250-1299)
    q_loss_plan = float(q_loss_curr)
    cert_tries = []
    certified_standalone = False
    for try_idx, cert_blk in enumerate(D2_CERT_BLOCKS, start=1):
        q_dict = {"fix": q_fix_base, "float": q_flt_base, "loss": q_loss_plan}
        tasks = [
            (s, scenario_for_seed(s), "D2", "ĐX-2", q_dict, sigma_tau, "group", seed_base,
             {"keep_tau_arrays": False, "compute_open_loop": False})
            for s in cert_blk
        ]
        res_c = run_parallel_episodes(tasks, workers=workers)
        cycs_c = [c for r in res_c for c in r["cycles"]]
        th_c = mark_thinned_cycles(cycs_c, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        loss_sc = [c["R"] for c in th_c if c["g"] == "loss"]
        q_pac_loss, k_loss, n_loss = pac_conformal_q(loss_sc, alpha, delta_try)
        ratios_all = [c["R"] / q_dict[c["g"]] for c in th_c]
        r_pac_all, k_all, n_all = pac_conformal_q(ratios_all, alpha, delta_try)
        passed_st = bool(math.isfinite(q_pac_loss) and q_pac_loss <= q_loss_plan)
        cert_tries.append({
            "try": try_idx,
            "q_loss_plan": float(q_loss_plan),
            "n_total": int(n_all),
            "n_loss": int(n_loss),
            "k_pac_loss": int(k_loss),
            "pac_feasible_loss": bool(k_loss <= n_loss),
            "q_pac_loss": float(q_pac_loss) if math.isfinite(q_pac_loss) else None,
            "passed_standalone_loss": passed_st,
            "overall_ratio_pac": float(r_pac_all) if math.isfinite(r_pac_all) else None,
            "passed_overall": bool(r_pac_all <= 1.0),
        })
        if passed_st:
            certified_standalone = True
            break
        q_loss_plan = float(max(q_loss_plan * 1.05, min(q_pac_loss * 1.01, q_loss_plan * 1.35))) if math.isfinite(q_pac_loss) else q_loss_plan * 1.15

    # 3. Đánh giá độ phủ của q_loss chuyên biệt trên tập kiểm tra D2 (IN 500-514) và D7 (OOD-D 700-709)
    q_d2_spec = {"fix": q_fix_base, "float": q_flt_base, "loss": q_loss_plan}
    eval_tasks = (
        [(s, scn, "D2", "ĐX-2-D2spec_IN", q_d2_spec, sigma_tau, "group", seed_base,
          {"keep_tau_arrays": False, "compute_open_loop": False})
         for scn in SCENARIOS for s in TEST_SEEDS]
        + [(s, scn, "D7", "ĐX-2-D2spec_D7", q_d2_spec, sigma_tau, "group", seed_base,
            {"keep_tau_arrays": False, "compute_open_loop": False})
           for scn in SCENARIOS for s in OOD_SEEDS]
    )
    res_ev = run_parallel_episodes(eval_tasks, workers=workers)
    eval_summary = {}
    for tag in ("ĐX-2-D2spec_IN", "ĐX-2-D2spec_D7"):
        cycs_e = [c for r in res_ev if r["episode"]["method"] == tag for c in r["cycles"]]
        th_e = mark_thinned_cycles(cycs_e, every_s=3.0, keep_empty=False, overlapping_bucket=False)
        loss_e = [c for c in th_e if c["g"] == "loss" and c["has_agents"] == 1]
        k_cov = sum(c["covered"] for c in loss_e)
        n_cov = len(loss_e)
        lo, hi = clopper_pearson(k_cov, n_cov)
        eval_summary[tag] = {
            "n_loss_thinned": n_cov,
            "coverage_score_loss": float(k_cov / n_cov) if n_cov else 0.0,
            "ci95_loss": [float(lo), float(hi)],
            "coverage_safe_loss": float(np.mean([c["safe"] for c in loss_e])) if n_cov else 0.0,
        }

    out = {
        "q_v01_loss": float(v01_params["q_dx2"]["loss"]),
        "q_d2_specialized_loss": float(q_loss_plan),
        "m_3s_d2_specialized_loss": float(q_loss_plan * sigma_tau[-1]),
        "calib_iterations": calib_iters,
        "cert_tries": cert_tries,
        "certified_standalone_loss": certified_standalone,
        "eval_loss_coverage": eval_summary,
    }
    with open(logs_ext / "calibration_d2.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


# ==============================================================================
# E6: Tổng hợp tách E_track / E_replan theo D và S -> e6_tracking_split.csv
# ==============================================================================

def run_e6_tracking_summary(logs_ext: Path) -> list[dict[str, Any]]:
    """E6: Tổng hợp E_track / sigma và E_replan / sigma theo từng điều kiện D và kịch bản S."""
    print("  [E6] Tổng hợp tách E_track / E_replan từ logs/ext/cycles.csv...", flush=True)
    df = pd.read_csv(logs_ext / "cycles.csv")
    df_th = df[(df["thinned"] == 1) & (df["has_agents"] == 1) & (df["method"].isin(["B0", "ĐX-1", "ĐX-2"]))].copy()

    rows: list[dict[str, Any]] = []
    for method in ("B0", "ĐX-1", "ĐX-2"):
        m_df = df_th[df_th["method"] == method]
        for group_by in ("cond", "scn"):
            for key, grp in m_df.groupby(group_by):
                rows.append({
                    "method": method,
                    "group_type": group_by,
                    "group_val": key,
                    "n_cycles": int(len(grp)),
                    "e_track_mean": float(grp["e_track"].mean()),
                    "e_track_median": float(grp["e_track"].median()),
                    "e_track_p95": float(grp["e_track"].quantile(0.95)),
                    "e_replan_mean": float(grp["e_replan"].mean()),
                    "e_replan_median": float(grp["e_replan"].median()),
                    "e_replan_p95": float(grp["e_replan"].quantile(0.95)),
                    "e_total_mean": float(grp["E_max_norm"].mean()),
                    "e_total_p95": float(grp["E_max_norm"].quantile(0.95)),
                })

    # Thêm riêng B0 ở D0 trên IN phân tách có/không có tác nhân
    b0_d0 = df[(df["split"] == "IN") & (df["method"] == "B0") & (df["cond"] == "D0")]
    for has_ag, lbl in ((0, "D0_empty"), (1, "D0_active")):
        sub = b0_d0[b0_d0["has_agents"] == has_ag]
        rows.append({
            "method": "B0",
            "group_type": "d0_replan_check",
            "group_val": lbl,
            "n_cycles": int(len(sub)),
            "e_track_mean": float(sub["e_track"].mean()),
            "e_track_median": float(sub["e_track"].median()),
            "e_track_p95": float(sub["e_track"].quantile(0.95)),
            "e_replan_mean": float(sub["e_replan"].mean()),
            "e_replan_median": float(sub["e_replan"].median()),
            "e_replan_p95": float(sub["e_replan"].quantile(0.95)),
            "e_total_mean": float(sub["E_max_norm"].mean()),
            "e_total_p95": float(sub["E_max_norm"].quantile(0.95)),
        })

    fields = [
        "method", "group_type", "group_val", "n_cycles",
        "e_track_mean", "e_track_median", "e_track_p95",
        "e_replan_mean", "e_replan_median", "e_replan_p95",
        "e_total_mean", "e_total_p95",
    ]
    with open(logs_ext / "e6_tracking_split.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


# ==============================================================================
# E3: Lực kiểm định PAC theo n_cert, M, delta + 1 điểm chạy thật -> pac_power.csv
# ==============================================================================

def run_e3_pac_power(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    workers: int,
    seed_base: int,
    alpha: float = 0.10,
) -> list[dict[str, Any]]:
    """E3: Monte Carlo nhị thức (4.000 lần) cho lực kiểm định PAC + 1 điểm chạy thật n≈400, M=1."""
    print("  [E3] Chạy mô phỏng Monte Carlo lực kiểm định PAC + 1 điểm chạy thật...", flush=True)
    df_cyc = pd.read_csv(logs_ext / "cycles.csv")
    r_pop = pd.to_numeric(
        df_cyc[(df_cyc["split"] == "IN") & (df_cyc["method"] == "ĐX-1") & (df_cyc["thinned"] == 1) & (df_cyc["has_agents"] == 1)]["R"],
        errors="coerce",
    ).dropna().to_numpy()

    rng = np.random.default_rng(202603)
    n_trials = 4000
    p_grid = [0.85, 0.87, 0.89, 0.90, 0.91, 0.93, 0.95, 0.97]
    rows: list[dict[str, Any]] = []

    for n_cert in (100, 200, 400, 800):
        for m_tries in (1, 3):
            for delta in (0.01, 0.05, 0.10):
                k_pac = pac_order_index(n_cert, alpha, delta / m_tries)
                req_p = k_pac / n_cert
                excess = req_p - (1.0 - alpha)
                q_eq = float(np.quantile(r_pop, min(req_p, 0.999))) if len(r_pop) > 0 else 0.0
                m3s_eq = q_eq * float(sigma_tau[-1])
                for p_true in p_grid:
                    counts = rng.binomial(n_cert, p_true, size=(n_trials, m_tries))
                    acc_prob = float(np.mean(np.any(counts >= k_pac, axis=1)))
                    rows.append({
                        "source": "mc_binom",
                        "n_cert": n_cert,
                        "M": m_tries,
                        "delta": delta,
                        "k_pac": k_pac,
                        "req_emp_cov": req_p,
                        "excess_cov_req": excess,
                        "m_3s_equiv": m3s_eq,
                        "p_true": p_true,
                        "accept_prob": acc_prob,
                    })

    # 1 điểm chạy thật: 105 hạt giống (1500-1604) để thu ~400 chu kỳ không chồng cho M=1, delta=0.05
    q_dx1 = float(v01_params["q_dx1"])
    real_seeds = list(range(1500, 1605))
    t_real = [
        (s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", (q_dx1, 0.0),
         sigma_tau, "const", seed_base, {"keep_tau_arrays": False, "compute_open_loop": False})
        for s in real_seeds
    ]
    res_real = run_parallel_episodes(t_real, workers=workers)
    c_real = [c for r in res_real for c in r["cycles"]]
    th_real = mark_thinned_cycles(c_real, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    r_real = [c["R"] for c in th_real]
    q_pac_r, k_pac_r, n_real = pac_conformal_q(r_real, alpha, 0.05)
    n_cov_r = sum(1 for v in r_real if v <= q_dx1)
    rows.append({
        "source": "real_sim_n400_M1",
        "n_cert": int(n_real),
        "M": 1,
        "delta": 0.05,
        "k_pac": int(k_pac_r),
        "req_emp_cov": float(k_pac_r / n_real),
        "excess_cov_req": float(k_pac_r / n_real - (1.0 - alpha)),
        "m_3s_equiv": float(q_pac_r * sigma_tau[-1]) if math.isfinite(q_pac_r) else float("inf"),
        "p_true": float(n_cov_r / n_real),
        "accept_prob": float(q_pac_r <= q_dx1),
    })

    fields = [
        "source", "n_cert", "M", "delta", "k_pac", "req_emp_cov",
        "excess_cov_req", "m_3s_equiv", "p_true", "accept_prob",
    ]
    with open(logs_ext / "pac_power.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


# ==============================================================================
# E5: Lấy mẫu Delta in {3, 4, 6} s, 1 mẫu/lượt và hiệu chỉnh theo khối lượt
# ==============================================================================

def _autocorr_lags(series_list: list[list[float]], max_lag: int = 5) -> list[float]:
    rhos = []
    for lag in range(1, max_lag + 1):
        xs, ys = [], []
        for seq in series_list:
            if len(seq) > lag:
                xs.extend(seq[:-lag])
                ys.extend(seq[lag:])
        if len(xs) >= 5 and np.std(xs) > 1e-12 and np.std(ys) > 1e-12:
            rhos.append(float(np.corrcoef(xs, ys)[0, 1]))
        else:
            rhos.append(0.0)
    return rhos


def run_e5_thinning_and_block(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    b0_v01_res: list[dict[str, Any]],
    workers: int,
    seed_base: int,
    alpha: float = 0.10,
) -> list[dict[str, Any]]:
    """E5: So sánh lấy thưa 3/4/6 s, 1 chu kỳ ngẫu nhiên/lượt và hiệu chỉnh theo khối lượt."""
    print("  [E5] Phân tích tự tương quan và hiệu chỉnh theo khối lượt...", flush=True)
    df_cyc = pd.read_csv(logs_ext / "cycles.csv")
    dx1_in = df_cyc[(df_cyc["split"] == "IN") & (df_cyc["method"] == "ĐX-1") & (df_cyc["has_agents"] == 1)].copy()
    dx1_in["R_num"] = pd.to_numeric(dx1_in["R"], errors="coerce")
    dx1_in = dx1_in.dropna(subset=["R_num"]).sort_values(["cond", "scn", "seed", "t"])

    grouped = list(dx1_in.groupby(["cond", "scn", "seed"]))
    rng = np.random.default_rng(202605)
    rows: list[dict[str, Any]] = []

    for delta_s in (3.0, 4.0, 6.0):
        seqs, covs = [], []
        for _, grp in grouped:
            ts = grp["t"].to_numpy()
            rs = grp["R_num"].to_numpy()
            cs = grp["covered"].to_numpy()
            kept_r = []
            last_t = -1e9
            for tv, rv, cv in zip(ts, rs, cs):
                if tv - last_t >= delta_s - 1e-6:
                    kept_r.append(float(rv))
                    covs.append(int(cv))
                    last_t = float(tv)
            if kept_r:
                seqs.append(kept_r)
        rhos = _autocorr_lags(seqs, max_lag=5)
        n_raw = len(covs)
        k_cov = sum(covs)
        lo, hi = clopper_pearson(k_cov, n_raw)
        vif = 1.0 + 2.0 * sum(max(0.0, r) for r in rhos)
        n_eff = n_raw / vif
        rows.append({
            "sampling": f"delta_{int(delta_s)}s",
            "n_samples": n_raw,
            "n_eff": float(n_eff),
            "coverage_score": float(k_cov / n_raw),
            "ci95_width": float(hi - lo),
            "rho1": rhos[0], "rho2": rhos[1], "rho3": rhos[2], "rho4": rhos[3], "rho5": rhos[4],
        })

    # 1 chu kỳ ngẫu nhiên mỗi lượt
    covs_1ep = []
    for _, grp in grouped:
        idx = int(rng.integers(0, len(grp)))
        covs_1ep.append(int(grp.iloc[idx]["covered"]))
    n_1 = len(covs_1ep)
    k_1 = sum(covs_1ep)
    lo1, hi1 = clopper_pearson(k_1, n_1)
    rows.append({
        "sampling": "one_random_per_ep",
        "n_samples": n_1,
        "n_eff": float(n_1),
        "coverage_score": float(k_1 / n_1),
        "ci95_width": float(hi1 - lo1),
        "rho1": 0.0, "rho2": 0.0, "rho3": 0.0, "rho4": 0.0, "rho5": 0.0,
    })

    # Hiệu chỉnh theo khối lượt: mỗi lượt lấy max_t R_t (trên tập hiệu chỉnh 250-399 -> test 500-514)
    ep_max_scores = []
    for r in b0_v01_res:
        res_c = rescore_cycles_with_sigma(r["cycles"], sigma_tau)
        act_r = [c["R"] for c in res_c if c["has_agents"] == 1]
        if act_r:
            ep_max_scores.append(max(act_r))
    q_ep_block = max(0.0, conformal_q(ep_max_scores, alpha))

    t_blk = [
        (s, scn, cond, "ĐX-1-EpBlock", (q_ep_block, 0.0), sigma_tau, "const", seed_base,
         {"keep_tau_arrays": False, "compute_open_loop": False})
        for cond in CONDITIONS for scn in SCENARIOS for s in TEST_SEEDS
    ]
    res_blk = run_parallel_episodes(t_blk, workers=workers)
    ep_cov_flags = []
    for r in res_blk:
        act_r = [c["R"] for c in r["cycles"] if c["has_agents"] == 1]
        if act_r:
            ep_cov_flags.append(int(max(act_r) <= q_ep_block))
    n_eb = len(ep_cov_flags)
    k_eb = sum(ep_cov_flags)
    lob, hib = clopper_pearson(k_eb, n_eb)
    rows.append({
        "sampling": f"episode_block_max_q={q_ep_block:.3f}",
        "n_samples": n_eb,
        "n_eff": float(n_eb),
        "coverage_score": float(k_eb / n_eb),
        "ci95_width": float(hib - lob),
        "rho1": 0.0, "rho2": 0.0, "rho3": 0.0, "rho4": 0.0, "rho5": 0.0,
    })

    fields = [
        "sampling", "n_samples", "n_eff", "coverage_score", "ci95_width",
        "rho1", "rho2", "rho3", "rho4", "rho5",
    ]
    with open(logs_ext / "thinning_ext.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


# ==============================================================================
# E7: Độ nhạy d_s, mật độ lưới 351/663 và bề rộng làn 3.0 m
# ==============================================================================

def run_e7_sensitivity(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    workers: int,
    seed_base: int,
) -> list[dict[str, Any]]:
    """E7: Quét d_s in {0.5, 1.0}, lưới 351/663 ứng viên, làn 3.5/3.0 m trên tập IN (8 hạt giống/ô)."""
    print("  [E7] Chạy phân tích độ nhạy d_s, mật độ lưới 663 và làn 3.0 m...", flush=True)
    e7_seeds = list(range(500, 508))
    configs = [
        ("ds0.5_g351_lane3.5", 0.5, False, 1.75),
        ("ds1.0_g351_lane3.5", 1.0, False, 1.75),
        ("ds1.0_g663_lane3.5", 1.0, True, 1.75),
        ("ds1.0_g351_lane3.0", 1.0, False, 1.50),
        ("ds1.0_g663_lane3.0", 1.0, True, 1.50),
    ]
    m_specs = [
        ("B0", (0.0, 0.0), "const"),
        ("B1", (v01_params["q_b1"], 0.0), "const"),
        ("B5", (v01_params["m_b5_tau"], v01_params["q_b5_equiv"]), "vector"),
        ("ĐX-1", (v01_params["q_dx1"], 0.0), "const"),
        ("ĐX-2", dict(v01_params["q_dx2"]), "group"),
    ]

    tasks = []
    for cfg_name, d_s, dense_v, lhw in configs:
        opts = {
            "d_s": d_s, "dense_v_grid": dense_v, "lane_half_width": lhw,
            "keep_tau_arrays": False, "compute_open_loop": False,
        }
        for m_name, m_arg, m_mode in m_specs:
            tag = f"{cfg_name}|{m_name}"
            for cond in CONDITIONS:
                for scn in SCENARIOS:
                    for s in e7_seeds:
                        tasks.append((s, scn, cond, tag, m_arg, sigma_tau, m_mode, seed_base, opts))

    raw = run_parallel_episodes(tasks, workers=workers)
    by_tag_eps: dict[str, list[dict[str, Any]]] = {}
    by_tag_cycs: dict[str, list[dict[str, Any]]] = {}
    for r in raw:
        tag = r["episode"]["method"]
        by_tag_eps.setdefault(tag, []).append(r["episode"])
        by_tag_cycs.setdefault(tag, []).extend(r["cycles"])

    rows = []
    for cfg_name, d_s, dense_v, lhw in configs:
        for m_name, _, _ in m_specs:
            tag = f"{cfg_name}|{m_name}"
            eps_t = by_tag_eps[tag]
            cycs_t = by_tag_cycs[tag]
            th_t = mark_thinned_cycles(cycs_t, every_s=3.0, keep_empty=False, overlapping_bucket=False)
            sm = summarize_group(eps_t, th_t, keep_empty=False)
            rows.append({
                "config": cfg_name,
                "d_s": d_s,
                "grid": 663 if dense_v else 351,
                "lane_width_m": 2.0 * lhw,
                "method": m_name,
                "coverage_safe": sm["coverage_safe"],
                "coverage_score": sm["coverage_score"],
                "gap_phys_minus_score": sm["coverage_safe"] - sm["coverage_score"],
                "collision_rate": sm["collision_rate"],
                "completion_rate": sm["completion_rate"],
                "t_end_mean": sm["t_end_mean"],
                "fallback_pct": sm["fallback_pct"],
            })

    fields = [
        "config", "d_s", "grid", "lane_width_m", "method", "coverage_safe",
        "coverage_score", "gap_phys_minus_score", "collision_rate",
        "completion_rate", "t_end_mean", "fallback_pct",
    ]
    with open(logs_ext / "e7_sensitivity.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


# ==============================================================================
# E8: Ước lượng sigma_tau theo từng kịch bản (1300-1399) -> sigma_by_scn.csv
# ==============================================================================

def run_e8_sigma_by_scenario(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    workers: int,
    seed_base: int,
) -> list[dict[str, Any]]:
    """E8: Chạy B0 trên hạt giống 1300-1399 cho S1–S10, so tỉ số sigma_tau(S) / sigma_tau(chung)."""
    print("  [E8] Ước lượng sigma_tau theo từng kịch bản S1–S10 (1300–1399)...", flush=True)
    tasks = [
        (s, scn, condition_for_seed(s, seed_base), "B0", (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base,
         {"keep_tau_arrays": True, "compute_open_loop": False})
        for scn in ALL_SCENARIOS
        for s in SIGMA_SCN_SEEDS
    ]
    raw = run_parallel_episodes(tasks, workers=workers)
    by_scn: dict[str, list[dict[str, Any]]] = {}
    for r in raw:
        by_scn.setdefault(r["episode"]["scn"], []).append(r)

    rows = []
    for scn in ALL_SCENARIOS:
        sig_s = estimate_sigma_tau(by_scn[scn])
        n_active = sum(1 for r in by_scn[scn] for c in r["cycles"] if c["has_agents"] == 1)
        rows.append({
            "scenario": scn,
            "n_active_cycles": n_active,
            "sigma_10": float(sig_s[9]),
            "sigma_20": float(sig_s[19]),
            "sigma_30": float(sig_s[29]),
            "ratio_10": float(sig_s[9] / sigma_tau[9]),
            "ratio_20": float(sig_s[19] / sigma_tau[19]),
            "ratio_30": float(sig_s[29] / sigma_tau[29]),
            "max_ratio_over_tau": float(np.max(sig_s / sigma_tau)),
        })

    fields = [
        "scenario", "n_active_cycles", "sigma_10", "sigma_20", "sigma_30",
        "ratio_10", "ratio_20", "ratio_30", "max_ratio_over_tau",
    ]
    with open(logs_ext / "sigma_by_scn.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


# ==============================================================================
# E9: Mở rộng tập IN lên 30 hạt giống (500-529) cho B1, ĐX-1, ĐX-2, ĐX-3
# ==============================================================================

def run_e9_in30(
    logs_ext: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    workers: int,
    seed_base: int,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """E9: Chạy thêm hạt giống 515-529 và ghép với 500-514 để kiểm tra độ rộng KTC 95% theo ô."""
    print("  [E9] Mở rộng tập IN lên 30 hạt giống (500–529)...", flush=True)
    # Tải kết quả 500-514 từ logs/ext/cycles.csv và episodes.csv
    ep_df = pd.read_csv(logs_ext / "episodes.csv")
    cyc_df = pd.read_csv(logs_ext / "cycles.csv")
    methods_e9 = ["B1", "ĐX-1", "ĐX-2", "ĐX-3"]

    in15_ep = ep_df[(ep_df["split"] == "IN") & (ep_df["method"].isin(methods_e9))]
    in15_cyc = cyc_df[(cyc_df["split"] == "IN") & (cyc_df["method"].isin(methods_e9)) & (cyc_df["thinned"] == 1) & (cyc_df["has_agents"] == 1)]

    # Chạy thêm hạt giống 515-529 cho B1, ĐX-1, ĐX-2
    opts = {"split": "IN", "keep_tau_arrays": False, "compute_open_loop": False}
    extra_tasks = []
    for m, arg, mode in [
        ("B1", (v01_params["q_b1"], 0.0), "const"),
        ("ĐX-1", (v01_params["q_dx1"], 0.0), "const"),
        ("ĐX-2", dict(v01_params["q_dx2"]), "group"),
    ]:
        for cond in CONDITIONS:
            for scn in SCENARIOS:
                for s in TEST_IN_EXTRA_SEEDS:
                    extra_tasks.append((s, scn, cond, m, arg, sigma_tau, mode, seed_base, opts))
    res_extra = run_parallel_episodes(extra_tasks, workers=workers)
    extra_cycs = [c for r in res_extra for c in r["cycles"]]
    mark_thinned_cycles(extra_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)

    # Với ĐX-3 (ACI), chạy nối tiếp qua đủ 30 hạt giống 500-529 cho từng điều kiện
    from sim.common import run_aci_test_suite
    _, dx3_30_cycs, _ = run_aci_test_suite(
        method="ĐX-3",
        seeds=list(TEST_SEEDS) + list(TEST_IN_EXTRA_SEEDS),
        init_scores=v01_params["r_scores"][-500:],
        sigma_tau=sigma_tau,
        alpha=alpha,
        score_key="R",
        update_on_empty=False,
        workers=workers,
        seed_base=seed_base,
    )
    mark_thinned_cycles(dx3_30_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)

    cell_rows = []
    cond_summary: dict[str, Any] = {}
    for m in methods_e9:
        if m == "ĐX-3":
            th_30 = [c for c in dx3_30_cycs if c["thinned"] == 1 and c["has_agents"] == 1]
        else:
            th_15 = in15_cyc[in15_cyc["method"] == m].to_dict("records")
            th_ex = [c for c in extra_cycs if c["method"] == m and c["thinned"] == 1 and c["has_agents"] == 1]
            th_30 = th_15 + th_ex

        cond_summary[m] = {}
        for cond in CONDITIONS:
            cs_c = [c for c in th_30 if c["cond"] == cond]
            k_c = sum(int(c["covered"]) for c in cs_c)
            n_c = len(cs_c)
            lo_c, hi_c = clopper_pearson(k_c, n_c)
            cond_summary[m][cond] = {
                "n_thinned": n_c,
                "coverage_score": float(k_c / n_c) if n_c else 0.0,
                "ci95": [float(lo_c), float(hi_c)],
                "ci95_width": float(hi_c - lo_c),
            }
            for scn in SCENARIOS:
                cs_cell = [c for c in cs_c if c["scn"] == scn]
                k_cell = sum(int(c["covered"]) for c in cs_cell)
                n_cell = len(cs_cell)
                lo_cell, hi_cell = clopper_pearson(k_cell, n_cell)

                cs_15 = in15_cyc[(in15_cyc["method"] == m) & (in15_cyc["cond"] == cond) & (in15_cyc["scn"] == scn)]
                lo_15, hi_15 = clopper_pearson(int(cs_15["covered"].sum()), len(cs_15))
                cell_rows.append({
                    "method": m,
                    "cond": cond,
                    "scn": scn,
                    "n_thinned_15": int(len(cs_15)),
                    "ci95_width_15": float(hi_15 - lo_15),
                    "n_thinned_30": n_cell,
                    "coverage_score_30": float(k_cell / n_cell) if n_cell else 0.0,
                    "ci95_width_30": float(hi_cell - lo_cell),
                })

        k_all = sum(int(c["covered"]) for c in th_30)
        n_all = len(th_30)
        lo_a, hi_a = clopper_pearson(k_all, n_all)
        cond_summary[m]["OVERALL"] = {
            "n_thinned": n_all,
            "coverage_score": float(k_all / n_all) if n_all else 0.0,
            "ci95": [float(lo_a), float(hi_a)],
            "ci95_width": float(hi_a - lo_a),
        }

    fields = [
        "method", "cond", "scn", "n_thinned_15", "ci95_width_15",
        "n_thinned_30", "coverage_score_30", "ci95_width_30",
    ]
    with open(logs_ext / "e9_in30_cells.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cell_rows)

    out = {"by_method_cond": cond_summary, "mean_cell_ci95_width_15": float(np.mean([r["ci95_width_15"] for r in cell_rows])), "mean_cell_ci95_width_30": float(np.mean([r["ci95_width_30"] for r in cell_rows]))}
    with open(logs_ext / "e9_in30_summary.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


# ==============================================================================
# Trình điều phối toàn bộ E1–E9 theo thứ tự ưu tiên SPEC §9.4
# ==============================================================================

def run_all_experiments_ext(
    root: Path,
    sigma_tau: np.ndarray,
    v01_params: dict[str, Any],
    seed_base: int = 0,
    workers: int = 8,
    alpha: float = 0.10,
) -> dict[str, Any]:
    """Chạy tuần tự E1 -> E2 -> E4 -> E6 -> E3 -> E5 -> E7 -> E8 -> E9."""
    logs_ext = root / "logs" / "ext"
    logs_ext.mkdir(parents=True, exist_ok=True)

    # Tải tập B0 250-399 dùng cho E1 và E5
    b0_v01_tasks = [
        (
            s, scenario_for_seed(s), condition_for_seed(s, seed_base), "B0",
            (0.0, 0.0), DEFAULT_SIGMA_OLD, "const", seed_base,
            {"keep_tau_arrays": True, "compute_open_loop": False},
        )
        for blk in CALIB_BLOCK_SEEDS
        for s in blk
    ]
    b0_v01_res = run_parallel_episodes(b0_v01_tasks, workers=workers)
    _, _, b0_v01_th = _extract_b0_thinned(b0_v01_res, sigma_tau)

    e1 = run_e1_iso_coverage(logs_ext, sigma_tau, b0_v01_th, workers, seed_base)
    e2 = run_e2_aci_ablation(logs_ext, sigma_tau, v01_params, workers, seed_base)
    e4 = run_e4_d2_specialized(logs_ext, sigma_tau, v01_params, workers, seed_base, alpha=alpha)
    e6 = run_e6_tracking_summary(logs_ext)
    e3 = run_e3_pac_power(logs_ext, sigma_tau, v01_params, workers, seed_base, alpha=alpha)
    e5 = run_e5_thinning_and_block(logs_ext, sigma_tau, v01_params, b0_v01_res, workers, seed_base, alpha=alpha)
    e7 = run_e7_sensitivity(logs_ext, sigma_tau, v01_params, workers, seed_base)
    e8 = run_e8_sigma_by_scenario(logs_ext, sigma_tau, workers, seed_base)
    e9 = run_e9_in30(logs_ext, sigma_tau, v01_params, workers, seed_base, alpha=alpha)

    return {
        "e1": e1, "e2": len(e2), "e4": e4, "e6": len(e6),
        "e3": len(e3), "e5": e5, "e7": len(e7), "e8": e8, "e9": e9,
    }
