"""Trình chạy thí nghiệm CARLA theo Phương án B cho M1, M2 và M3 (PLAN §9, T16–T20).

- Dùng lại toàn bộ hàm tính biên, hiệu chỉnh, PAC, ACI và ghi log từ `sim.common` & `sim.run_new`.
- Hỗ trợ lưu điểm phục hồi (checkpoint) sau mỗi lượt để chạy lại an toàn khi bị ngắt.
- Hỗ trợ hai backend: `"carla"` (CARLA server thật) và `"fake"` (FakeCarlaSession để kiểm thử).
"""

from __future__ import annotations

import datetime as _dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import norm as _norm_dist

from carla_sim.config import CarlaConfig
from carla_sim.episode import FakeCarlaSession, run_carla_episode
from carla_sim.infra import CarlaSession
from sim.common import (
    CALIB_BLOCK_SEEDS,
    CERT_BLOCK_SEEDS,
    SIGMA_EST_SEEDS,
    TEST_SEEDS,
    AdaptiveConformalState,
    clopper_pearson,
    conformal_q,
    make_const_margin_fn,
    make_group_margin_fn,
    make_vector_margin_fn,
    mark_thinned_cycles,
    pac_conformal_q,
    rescore_cycles_with_sigma,
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
from sim.run_new import (
    NEW_METHODS,
    PAC_DELTA_PER_TRY,
    PAC_DELTA_TOTAL,
    PAC_MAX_TRIES,
    _group_q_dict_active,
    estimate_sigma_tau,
)


def _open_session(cfg: CarlaConfig, backend: str = "carla") -> CarlaSession | FakeCarlaSession:
    if backend == "fake":
        return FakeCarlaSession(cfg)
    if backend == "carla":
        return CarlaSession(cfg)
    raise ValueError(f"Backend không hợp lệ: {backend} (chọn 'carla' hoặc 'fake')")


class _CheckpointStore:
    """Lưu tạm kết quả từng lượt theo khóa (phase, method, cond, scn, seed) dạng JSONL."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.cache: dict[str, dict[str, Any]] = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    # Phục hồi mảng numpy cho các khóa *_tau nếu có
                    for c in rec.get("cycles", []):
                        for k in ("gap_tau", "a_tau", "b_tau", "E_tau", "A_h_tau", "A_c_tau"):
                            if k in c and isinstance(c[k], list):
                                vals = [
                                    float("-inf") if x == "-inf" else (float("inf") if x == "inf" else float(x))
                                    for x in c[k]
                                ]
                                c[k] = np.asarray(vals, dtype=float)
                    self.cache[rec["key"]] = rec

    @staticmethod
    def make_key(phase: str, method: str, cond: str, scn: str, seed: int) -> str:
        return f"{phase}|{method}|{cond}|{scn}|{seed}"

    def get(self, key: str) -> dict[str, Any] | None:
        return self.cache.get(key)

    def put(self, key: str, result: dict[str, Any]) -> None:
        self.cache[key] = {"key": key, **result}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        serializable_cycles = []
        for c in result["cycles"]:
            row = {}
            for k, v in c.items():
                if isinstance(v, np.ndarray):
                    row[k] = [
                        "-inf" if (not math.isfinite(float(x)) and float(x) < 0)
                        else ("inf" if not math.isfinite(float(x)) else float(x))
                        for x in v.tolist()
                    ]
                elif isinstance(v, float) and not math.isfinite(v):
                    row[k] = "-inf" if v < 0 else "inf"
                else:
                    row[k] = v
            serializable_cycles.append(row)
        payload = {
            "key": key,
            "episode": result["episode"],
            "cycles": serializable_cycles,
            "perception_stats": result.get("perception_stats", {}),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _restore_nonfinite(cycles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for c in cycles:
        for k, v in list(c.items()):
            if isinstance(v, str):
                if v == "-inf":
                    c[k] = float("-inf")
                elif v == "inf":
                    c[k] = float("inf")
    return cycles


def analyze_seed_exchangeability(cycles: list[dict[str, Any]], methods: list[str]) -> dict[str, Any]:
    """Kiểm tra độ phủ theo hạt giống và tự tương quan trễ 1 (T19 — kiểm tra hoán đổi được)."""
    out: dict[str, Any] = {}
    for m in methods:
        th = [c for c in cycles if c["method"] == m and c.get("thinned") == 1 and c.get("has_agents") == 1]
        if not th:
            continue
        by_seed: dict[int, list[dict[str, Any]]] = {}
        for c in th:
            by_seed.setdefault(int(c["seed"]), []).append(c)

        seed_covs = []
        for s in sorted(by_seed):
            sc = by_seed[s]
            n_s = len(sc)
            k_s = sum(int(c["covered"]) for c in sc)
            lo, hi = clopper_pearson(k_s, n_s)
            seed_covs.append({
                "seed": s,
                "n_thinned": n_s,
                "coverage_score": float(k_s / n_s),
                "ci95": [float(lo), float(hi)],
            })

        # Tự tương quan trễ 1 của điểm số R giữa các chu kỳ đã lấy thưa trong cùng lượt
        pairs_x, pairs_y = [], []
        by_ep: dict[tuple[int, str, str], list[dict[str, Any]]] = {}
        for c in th:
            by_ep.setdefault((int(c["seed"]), c["scn"], c["cond"]), []).append(c)
        for ep_cycs in by_ep.values():
            ep_cycs.sort(key=lambda r: r["t"])
            rs = [float(c["R"]) for c in ep_cycs if math.isfinite(float(c["R"]))]
            for i in range(len(rs) - 1):
                pairs_x.append(rs[i])
                pairs_y.append(rs[i + 1])

        if len(pairs_x) >= 3 and np.std(pairs_x) > 1e-9 and np.std(pairs_y) > 1e-9:
            rho1 = float(np.corrcoef(pairs_x, pairs_y)[0, 1])
        else:
            rho1 = 0.0

        cov_vals = [x["coverage_score"] for x in seed_covs]
        out[m] = {
            "n_seeds": len(seed_covs),
            "seed_cov_mean": float(np.mean(cov_vals)) if cov_vals else 0.0,
            "seed_cov_std": float(np.std(cov_vals, ddof=1)) if len(cov_vals) > 1 else 0.0,
            "seed_cov_min": float(min(cov_vals)) if cov_vals else 0.0,
            "seed_cov_max": float(max(cov_vals)) if cov_vals else 0.0,
            "lag1_autocorr_R": rho1,
            "n_lag1_pairs": len(pairs_x),
            "per_seed": seed_covs,
        }
    return out


def run_smoke_s1_d0(
    out_dir: Path,
    cfg: CarlaConfig | None = None,
    backend: str = "carla",
    seed: int = 500,
    seed_base: int = 0,
) -> dict[str, Any]:
    """Chạy kiểm tra cầu nối S1 + D0 và xuất log chuẩn cho `analyze.py` (T16 / G14)."""
    cfg = (cfg or CarlaConfig()).level_defaults()
    sigma_tau = DEFAULT_SIGMA_OLD
    m_fn = make_const_margin_fn(0.0, sigma_tau, 0.0)
    with _open_session(cfg, backend=backend) as session:
        res = run_carla_episode(
            session=session,
            seed=seed,
            scenario="S1",
            condition="D0",
            method="B0",
            margin_fn=m_fn,
            sigma_tau=sigma_tau,
            cfg=cfg,
            seed_base=seed_base,
        )
    cycs = res["cycles"]
    mark_thinned_cycles(cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    config = {
        "scheme": "carla_smoke_s1_d0",
        "backend": backend,
        "level": cfg.level,
        "seed": seed,
        "carla_config": cfg.to_dict(),
        "methods": ["B0"],
    }
    calib = {"sigma_tau": [float(x) for x in sigma_tau]}
    summary = write_logs(
        out_dir=out_dir,
        config=config,
        calibration=calib,
        episodes=[res["episode"]],
        cycles=cycs,
        methods_order=["B0"],
        keep_empty=False,
    )
    return {"episode": res["episode"], "summary": summary}


def run_demo(
    cfg: CarlaConfig | None = None,
    *,
    scenario: str = "S1",
    condition: str = "D0",
    n_episodes: int = 1,
    seed: int = 500,
    margin_m: float = 0.0,
    backend: str = "carla",
    out_csv: Path | None = None,
) -> list[dict[str, Any]]:
    """Chạy vài lượt để xem trực quan (lệnh `demo`): in kết quả từng lượt, không ghi file
    trừ khi có `out_csv` (khi đó ghi đúng một file CSV tóm tắt các lượt).

    Bộ lập kế hoạch dùng biên hằng `margin_m` (0 = B0), không cần hiệu chỉnh trước.
    """
    cfg = (cfg or CarlaConfig()).level_defaults()
    sigma_tau = DEFAULT_SIGMA_OLD
    m_fn = make_const_margin_fn(float(margin_m), sigma_tau, 0.0)
    episodes: list[dict[str, Any]] = []
    with _open_session(cfg, backend=backend) as session:
        for i in range(int(n_episodes)):
            print(f"[{i + 1}/{n_episodes}] {scenario} {condition} seed={seed + i}", flush=True)
            res = run_carla_episode(
                session=session,
                seed=seed + i,
                scenario=scenario,
                condition=condition,
                method="B0" if margin_m == 0.0 else f"const{margin_m:g}",
                margin_fn=m_fn,
                sigma_tau=sigma_tau,
                cfg=cfg,
                keep_tau_arrays=False,
            )
            ep = res["episode"]
            episodes.append(ep)
            print(
                f"    -> va chạm={ep['collided']} tới đích={ep['completed']} t_end={ep['t_end']:.1f}s "
                f"d_min={ep['d_min']:.2f}m ttc_min={ep['ttc_min']:.1f}s chu kỳ={ep['n_cycles']} "
                f"dừng dự phòng={ep['n_fallback']} tcomp_p95={ep['tcomp_p95_ms']:.0f}ms",
                flush=True,
            )
    if out_csv is not None and episodes:
        import csv  # noqa: PLC0415

        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(episodes[0].keys()))
            w.writeheader()
            w.writerows(episodes)
    return episodes


def benchmark_s_x_d(
    cfg: CarlaConfig | None = None,
    backend: str = "carla",
    scenarios: tuple[str, ...] = SCENARIOS,
    conditions: tuple[str, ...] = CONDITIONS,
    seed: int = 500,
    dense_v_grid: bool = False,
) -> dict[str, Any]:
    """Chạy đủ tổ hợp S×D để kiểm tra không lỗi và đo P95 thời gian tính < 100 ms (T17 / G15)."""
    cfg = (cfg or CarlaConfig()).level_defaults()
    sigma_tau = DEFAULT_SIGMA_OLD
    m_fn = make_const_margin_fn(1.0, sigma_tau, 0.0)
    tcomp_p95s: list[float] = []
    cells: list[dict[str, Any]] = []

    with _open_session(cfg, backend=backend) as session:
        for cond in conditions:
            for scn in scenarios:
                res = run_carla_episode(
                    session=session,
                    seed=seed,
                    scenario=scn,
                    condition=cond,
                    method="ĐX-1",
                    margin_fn=m_fn,
                    sigma_tau=sigma_tau,
                    cfg=cfg,
                    dense_v_grid=dense_v_grid,
                )
                ep = res["episode"]
                tcomp_p95s.append(float(ep["tcomp_p95_ms"]))
                cells.append({
                    "scn": scn,
                    "cond": cond,
                    "completed": ep["completed"],
                    "collided": ep["collided"],
                    "tcomp_p95_ms": ep["tcomp_p95_ms"],
                })

    overall_p95 = float(np.percentile(tcomp_p95s, 95)) if tcomp_p95s else 0.0
    return {
        "n_cells": len(cells),
        "dense_v_grid": bool(dense_v_grid),
        "tcomp_p95_ms_overall": overall_p95,
        "tcomp_p95_ms_max": float(max(tcomp_p95s)) if tcomp_p95s else 0.0,
        "meets_100ms_budget": bool(overall_p95 < 100.0),
        "cells": cells,
    }


def run_carla_suite(
    out_dir: Path,
    cfg: CarlaConfig | None = None,
    *,
    backend: str = "carla",
    seed_base: int = 0,
    alpha: float = 0.10,
    d_s: float = D_S,
    dense_v_grid: bool = False,
    methods: list[str] | None = None,
    sigma_seeds: list[int] | None = None,
    calib_blocks: list[list[int]] | None = None,
    cert_blocks: list[list[int]] | None = None,
    test_seeds: list[int] | None = None,
    scenarios: tuple[str, ...] = SCENARIOS,
    conditions: tuple[str, ...] = CONDITIONS,
    use_checkpoint: bool = True,
) -> dict[str, Any]:
    """Chạy đầy đủ quy trình Phương án B trên CARLA cho mức M1, M2 hoặc M3 (T19–T20)."""
    cfg = (cfg or CarlaConfig()).level_defaults()
    methods_order = list(NEW_METHODS if methods is None else methods)
    s_seeds = list(SIGMA_EST_SEEDS if sigma_seeds is None else sigma_seeds)
    cal_blks = list(CALIB_BLOCK_SEEDS if calib_blocks is None else calib_blocks)
    crt_blks = list(CERT_BLOCK_SEEDS if cert_blocks is None else cert_blocks)
    t_seeds = list(TEST_SEEDS if test_seeds is None else test_seeds)

    ckpt = _CheckpointStore(out_dir / "checkpoint.jsonl") if use_checkpoint else None
    perc_totals = {"n_gt_in_roi": 0, "n_detected": 0, "n_missed": 0, "n_occluded": 0, "n_id_switch": 0}

    def _run_one(
        session: CarlaSession | FakeCarlaSession,
        phase: str,
        seed: int,
        scn: str,
        cond: str,
        method: str,
        margin_fn,
        sigma_tau: np.ndarray,
        feedback_fn=None,
        allow_ckpt: bool = True,
    ) -> dict[str, Any]:
        key = _CheckpointStore.make_key(phase, method, cond, scn, seed)
        if allow_ckpt and ckpt is not None and feedback_fn is None:
            cached = ckpt.get(key)
            if cached is not None:
                _restore_nonfinite(cached["cycles"])
                return cached
        res = run_carla_episode(
            session=session,
            seed=seed,
            scenario=scn,
            condition=cond,
            method=method,
            margin_fn=margin_fn,
            sigma_tau=sigma_tau,
            cfg=cfg,
            feedback_fn=feedback_fn,
            seed_base=seed_base,
            split=f"CARLA_{cfg.level}",
            d_s=d_s,
            dense_v_grid=dense_v_grid,
        )
        ps = res.get("perception_stats", {})
        for k in perc_totals:
            perc_totals[k] += int(ps.get(k, 0))
        if allow_ckpt and ckpt is not None and feedback_fn is None:
            ckpt.put(key, res)
        return res

    with _open_session(cfg, backend=backend) as session:
        # 1. B0 trên khối sigma (200-249) để ước lượng sigma_tau
        zero_fn = make_const_margin_fn(0.0, DEFAULT_SIGMA_OLD, 0.0)
        b0_sigma_res = [
            _run_one(session, "b0_sigma", s, scenario_for_seed(s), condition_for_seed(s, seed_base), "B0", zero_fn, DEFAULT_SIGMA_OLD)
            for s in s_seeds
        ]
        sigma_tau = estimate_sigma_tau(b0_sigma_res)

        # 2. B0 trên khối hiệu chỉnh (250-399)
        cal_all_seeds = [s for blk in cal_blks for s in blk]
        b0_cal_res = [
            _run_one(session, "b0_cal", s, scenario_for_seed(s), condition_for_seed(s, seed_base), "B0", zero_fn, DEFAULT_SIGMA_OLD)
            for s in cal_all_seeds
        ]
        b0_cal_cycs = []
        for r in b0_cal_res:
            b0_cal_cycs.extend(rescore_cycles_with_sigma(r["cycles"], sigma_tau))
        b0_cal_th = mark_thinned_cycles(b0_cal_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)

        # 3. Hiệu chỉnh các đối chứng B1–B5, B3′ theo Phương án B (Hausdorff A_h)
        ah_scores = [c["A_h_max"] for c in b0_cal_th]
        e_scores = [c["E_max_norm"] for c in b0_cal_th]
        a_signed = [c["a_max_norm"] for c in b0_cal_th]
        b_signed = [c["b_max_norm"] for c in b0_cal_th]
        r_scores = [c["R"] for c in b0_cal_th]

        q_b1 = max(0.0, conformal_q(ah_scores, alpha)) if ah_scores else 1.0
        q_b3_a = max(0.0, conformal_q(ah_scores, alpha / 2.0)) if ah_scores else 1.0
        q_b3_e = max(0.0, conformal_q(e_scores, alpha / 2.0)) if e_scores else 1.0
        q_b3 = q_b3_a + q_b3_e
        q_b3p_a = max(0.0, conformal_q(a_signed, alpha / 2.0)) if a_signed else 0.5
        q_b3p_b = max(0.0, conformal_q(b_signed, alpha / 2.0)) if b_signed else 0.5
        q_b3p = q_b3p_a + q_b3p_b
        max_e_calib = float(max((c["E_max_m"] for c in b0_cal_th), default=0.5))

        a_mat = np.array([c["a_tau"] for c in b0_cal_th], dtype=float) if b0_cal_th else np.zeros((2, H_STEPS))
        b_mat = np.array([c["b_tau"] for c in b0_cal_th], dtype=float) if b0_cal_th else np.zeros((2, H_STEPS))
        s_a_tau = np.std(a_mat, axis=0, ddof=1) if len(a_mat) > 1 else np.full(H_STEPS, 0.1)
        s_e_tau = np.std(b_mat, axis=0, ddof=1) if len(b_mat) > 1 else np.full(H_STEPS, 0.1)
        m_b5_tau = float(_norm_dist.ppf(1.0 - alpha)) * np.sqrt(s_a_tau**2 + s_e_tau**2)
        q_b5_equiv = float(m_b5_tau[-1] / max(sigma_tau[-1], 1e-6))

        # 4. Thuật toán 1 + PAC cho ĐX-1
        blk1_set = set(cal_blks[0])
        b0_blk1_th = [c for c in b0_cal_th if c["seed"] in blk1_set]
        q_dx1_curr = max(0.0, conformal_q([c["R"] for c in b0_blk1_th], alpha)) if b0_blk1_th else 1.0
        if not math.isfinite(q_dx1_curr):
            q_dx1_curr = 1.0
        dx1_iters: list[dict[str, Any]] = []
        if "ĐX-1" in methods_order:
            for k_idx, blk in enumerate(cal_blks, start=1):
                m_fn = make_const_margin_fn(q_dx1_curr, sigma_tau, 0.0)
                res_blk = [
                    _run_one(session, f"dx1_cal_{k_idx}", s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", m_fn, sigma_tau)
                    for s in blk
                ]
                cycs_blk = [c for r in res_blk for c in r["cycles"]]
                th_blk = mark_thinned_cycles(cycs_blk, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                q_next = max(0.0, conformal_q([c["R"] for c in th_blk], alpha)) if th_blk else q_dx1_curr
                if not math.isfinite(q_next):
                    q_next = q_dx1_curr
                dx1_iters.append({"iter": k_idx, "q_in": float(q_dx1_curr), "q_out": float(q_next), "n_thinned_active": len(th_blk)})
                q_dx1_curr = q_next

        q_dx1_plan = float(q_dx1_curr)
        dx1_cert_tries: list[dict[str, Any]] = []
        dx1_certified = False
        if "ĐX-1" in methods_order:
            for try_idx, c_seeds in enumerate(crt_blks, start=1):
                m_fn = make_const_margin_fn(q_dx1_plan, sigma_tau, 0.0)
                res_c = [
                    _run_one(session, f"dx1_cert_{try_idx}", s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-1", m_fn, sigma_tau)
                    for s in c_seeds
                ]
                cycs_c = [c for r in res_c for c in r["cycles"]]
                th_c = mark_thinned_cycles(cycs_c, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                r_c = [c["R"] for c in th_c]
                q_pac, k_pac, n_cert = pac_conformal_q(r_c, alpha, PAC_DELTA_PER_TRY)
                passed = bool(q_pac <= q_dx1_plan)
                dx1_cert_tries.append({
                    "try": try_idx,
                    "q_plan": float(q_dx1_plan),
                    "q_pac": float(q_pac) if math.isfinite(q_pac) else None,
                    "k_pac": int(k_pac),
                    "n_thinned": int(n_cert),
                    "passed": passed,
                })
                if passed:
                    dx1_certified = True
                    break
                if math.isfinite(q_pac):
                    q_dx1_plan = float(max(q_dx1_plan * 1.05, min(q_pac * 1.01, q_dx1_plan * 1.25)))
                else:
                    q_dx1_plan = float(q_dx1_plan * 1.15)

        # 5. Thuật toán 1 + PAC cho ĐX-2
        q_g0_glob = max(0.0, conformal_q([c["R"] for c in b0_blk1_th], alpha)) if b0_blk1_th else 1.0
        if not math.isfinite(q_g0_glob):
            q_g0_glob = 1.0
        q_dx2_curr, _, _ = _group_q_dict_active(b0_blk1_th, alpha, q_g0_glob)
        dx2_iters: list[dict[str, Any]] = []
        if "ĐX-2" in methods_order:
            for k_idx, blk in enumerate(cal_blks, start=1):
                m_fn = make_group_margin_fn(q_dx2_curr, sigma_tau)
                res_blk = [
                    _run_one(session, f"dx2_cal_{k_idx}", s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", m_fn, sigma_tau)
                    for s in blk
                ]
                cycs_blk = [c for r in res_blk for c in r["cycles"]]
                th_blk = mark_thinned_cycles(cycs_blk, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                q_glob = max(0.0, conformal_q([c["R"] for c in th_blk], alpha)) if th_blk else q_g0_glob
                if not math.isfinite(q_glob):
                    q_glob = q_g0_glob
                q_next_d, cnts, fbs = _group_q_dict_active(th_blk, alpha, q_glob)
                dx2_iters.append({"iter": k_idx, "q_in": dict(q_dx2_curr), "q_out": dict(q_next_d), "group_counts": cnts, "group_fallback": fbs})
                q_dx2_curr = q_next_d

        q_dx2_plan = dict(q_dx2_curr)
        dx2_cert_tries: list[dict[str, Any]] = []
        dx2_certified = False
        if "ĐX-2" in methods_order:
            for try_idx, c_seeds in enumerate(crt_blks, start=1):
                m_fn = make_group_margin_fn(q_dx2_plan, sigma_tau)
                res_c = [
                    _run_one(session, f"dx2_cert_{try_idx}", s, scenario_for_seed(s), condition_for_seed(s, seed_base), "ĐX-2", m_fn, sigma_tau)
                    for s in c_seeds
                ]
                cycs_c = [c for r in res_c for c in r["cycles"]]
                th_c = mark_thinned_cycles(cycs_c, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                ratios = [c["R"] / max(q_dx2_plan[c["g"]], 1e-9) for c in th_c]
                ratio_pac, k_pac, n_cert = pac_conformal_q(ratios, alpha, PAC_DELTA_PER_TRY)
                passed = bool(ratio_pac <= 1.0)
                dx2_cert_tries.append({
                    "try": try_idx,
                    "q_plan": dict(q_dx2_plan),
                    "overall_ratio_pac": float(ratio_pac) if math.isfinite(ratio_pac) else None,
                    "overall_k_pac": int(k_pac),
                    "overall_n": int(n_cert),
                    "passed_overall": passed,
                })
                if passed:
                    dx2_certified = True
                    break
                scale = float(max(1.05, min(ratio_pac * 1.01, 1.25))) if math.isfinite(ratio_pac) else 1.15
                for g in GROUPS:
                    q_dx2_plan[g] = float(q_dx2_plan[g] * scale)

        # 6. Chạy tập kiểm tra cho tất cả phương pháp đã chọn
        all_episodes: list[dict[str, Any]] = []
        all_cycles: list[dict[str, Any]] = []

        margin_map = {
            "B0": make_const_margin_fn(0.0, sigma_tau, 0.0),
            "B1": make_const_margin_fn(q_b1, sigma_tau, 0.0),
            "B2": make_const_margin_fn(q_b1, sigma_tau, 0.3),
            "B3": make_const_margin_fn(q_b3, sigma_tau, 0.0),
            "B3′": make_const_margin_fn(q_b3p, sigma_tau, 0.0),
            "B4": make_const_margin_fn(q_b1, sigma_tau, max_e_calib),
            "B5": make_vector_margin_fn(m_b5_tau, q_b5_equiv),
            "ĐX-1": make_const_margin_fn(q_dx1_plan, sigma_tau, 0.0),
            "ĐX-2": make_group_margin_fn(q_dx2_plan, sigma_tau),
        }

        aci_final_alphas: dict[str, dict[str, float]] = {}
        for m_name in methods_order:
            if m_name in ("B6", "ĐX-3"):
                score_key = "A_h_max" if m_name == "B6" else "R"
                init_scores = (ah_scores[-500:] if m_name == "B6" else r_scores[-500:]) or [1.0]
                aci_final_alphas[m_name] = {}
                m_cycs = []
                for cond in conditions:
                    aci = AdaptiveConformalState(
                        init_scores=init_scores,
                        sigma_tau=sigma_tau,
                        alpha=alpha,
                        gamma=0.02,
                        window_size=500,
                        score_key=score_key,
                        update_on_empty=False,
                    )
                    for seed in t_seeds:
                        for scn in scenarios:
                            res = _run_one(
                                session, "test", seed, scn, cond, m_name,
                                aci.margin_fn, sigma_tau, feedback_fn=aci.feedback, allow_ckpt=False,
                            )
                            all_episodes.append(res["episode"])
                            m_cycs.extend(res["cycles"])
                    aci_final_alphas[m_name][cond] = float(aci.alpha_t)
                mark_thinned_cycles(m_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                all_cycles.extend(m_cycs)
            else:
                m_fn = margin_map[m_name]
                m_cycs = []
                for cond in conditions:
                    for scn in scenarios:
                        for seed in t_seeds:
                            res = _run_one(session, "test", seed, scn, cond, m_name, m_fn, sigma_tau)
                            all_episodes.append(res["episode"])
                            m_cycs.extend(res["cycles"])
                mark_thinned_cycles(m_cycs, every_s=3.0, keep_empty=False, overlapping_bucket=False)
                all_cycles.extend(m_cycs)

    # Kiểm tra độ phủ theo hạt giống & tự tương quan (T19)
    exch_info = analyze_seed_exchangeability(all_cycles, methods_order)

    config_out = {
        "scheme": f"carla_{cfg.level}_scheme_B",
        "backend": backend,
        "level": cfg.level,
        "predictor": cfg.predictor,
        "perception": cfg.perception,
        "seed_base": int(seed_base),
        "alpha": float(alpha),
        "d_s": float(d_s),
        "dense_v_grid": bool(dense_v_grid),
        "thinning_s": 3.0,
        "keep_empty_cycles": False,
        "overlapping_thinning": False,
        "agent_error_metric": "A_h",
        "certification_method": "PAC_Bonferroni",
        "pac_delta_total": PAC_DELTA_TOTAL,
        "pac_delta_per_try": PAC_DELTA_PER_TRY,
        "methods": methods_order,
        "scenarios": list(scenarios),
        "conditions": list(conditions),
        "test_seeds": t_seeds,
        "carla_config": cfg.to_dict(),
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    calibration_out = {
        "sigma_tau": [float(x) for x in sigma_tau],
        "q_b1": float(q_b1),
        "q_b3": float(q_b3),
        "q_b3p": float(q_b3p),
        "max_e_calib": float(max_e_calib),
        "q_b5_equiv": float(q_b5_equiv),
        "dx1": {"iters": dx1_iters, "cert_tries": dx1_cert_tries, "certified": dx1_certified, "q_final": float(q_dx1_plan)},
        "dx2": {"iters": dx2_iters, "cert_tries": dx2_cert_tries, "certified": dx2_certified, "q_final": dict(q_dx2_plan)},
        "aci_final_alphas": aci_final_alphas,
        "perception_totals": perc_totals,
        "exchangeability": exch_info,
    }
    summary = write_logs(
        out_dir=out_dir,
        config=config_out,
        calibration=calibration_out,
        episodes=all_episodes,
        cycles=all_cycles,
        methods_order=methods_order,
        keep_empty=False,
    )
    # Đã ghi đủ log chuẩn -> bỏ file checkpoint tạm (chỉ dùng để chạy tiếp khi bị ngắt)
    if ckpt is not None and ckpt.path.exists():
        ckpt.path.unlink()
    return {
        "config": config_out,
        "calibration": calibration_out,
        "summary": summary,
    }
