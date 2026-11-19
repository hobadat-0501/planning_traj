"""N3 — ngưỡng chung so với ngưỡng theo nhóm chất lượng định vị (Bảng 2 của bản thảo) — SPEC §10.3, §10.5.

Chạy: python -m num41.run_n3  (từ thư mục ws)
"""

from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

from num41 import SPEC_VERSION
from num41.gen import (
    DEFAULT_PARAMS, GROUP_NAMES, GROUP_PROBS, GROUP_SIGMA, SEED, GenParams, make_rng, sample_groups, with_params,
)
from num41.logio import LOG_DIR, stamp, update_json
from num41.scores import coverage, group_thresholds, q, scores

ALPHA = 0.10
N_CAL = 1000
N_TEST = 2000
N_REP = 100

# Biến thể độ nhạy (chỉ để báo cáo, không thay kết quả chính): cell_id 0 = gốc, 1 = U6-B, 2 = U1-W.
VARIANTS = {
    "base": (0, DEFAULT_PARAMS),
    "U6B": (1, with_params(motion="per_step")),
    "U1W": (2, with_params(loc_drift=False)),
}

# Bảng 2 của bản thảo v0.1, theo thứ tự fix / float / loss.
DRAFT_TABLE2 = {
    "cov_global": (0.963, 0.818, 0.620),
    "cov_group": (0.900, 0.900, 0.899),
    "q_global": 2.37,
    "q_group": (1.74, 3.34, 12.18),
}


def run(n_rep: int = N_REP, seed: int = SEED, cell: int = 0, params: GenParams = DEFAULT_PARAMS) -> pd.DataFrame:
    rows = []
    for rep in range(n_rep):
        b_cal = sample_groups(N_CAL, make_rng("N3", cell, rep, 0, seed), params)
        b_test = sample_groups(N_TEST, make_rng("N3", cell, rep, 1, seed), params)
        r_cal, r_test = scores(b_cal)["R"], scores(b_test)["R"]
        q_glob = q(r_cal, ALPHA)
        q_grp = group_thresholds(r_cal, b_cal.group, ALPHA, len(GROUP_NAMES))
        for g, name in enumerate(GROUP_NAMES):
            rt = r_test[b_test.group == g]
            rows.append({
                "rep": rep, "group": name,
                "n_cal_g": int(np.sum(b_cal.group == g)), "n_test_g": int(rt.size),
                "q_global": q_glob, "q_group": float(q_grp[g]),
                "cov_global": coverage(rt, q_glob) if rt.size else float("nan"),
                "cov_group": coverage(rt, q_grp[g]) if rt.size else float("nan"),
            })
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> dict:
    cells = []
    for gi, name in enumerate(GROUP_NAMES):
        g = df[df["group"] == name]
        finite = np.isfinite(g["q_group"])
        cells.append({
            "group": name, "sigma_loc": float(GROUP_SIGMA[gi]), "prob": float(GROUP_PROBS[gi]),
            "n_cal_g_mean": float(g["n_cal_g"].mean()), "n_test_g_mean": float(g["n_test_g"].mean()),
            "q_group_inf_count": int((~finite).sum()),
            "q_global_mean": float(g["q_global"].mean()), "q_global_sd": float(g["q_global"].std()),
            "q_group_mean": float(g.loc[finite, "q_group"].mean()), "q_group_sd": float(g.loc[finite, "q_group"].std()),
            "cov_global_mean": float(g["cov_global"].mean()), "cov_global_sd": float(g["cov_global"].std()),
            "cov_group_mean": float(g["cov_group"].mean()), "cov_group_sd": float(g["cov_group"].std()),
            "cov_group_se": float(g["cov_group"].std() / math.sqrt(len(g))),
        })
    by = {c["group"]: c for c in cells}
    qual = {
        # Hệ quả 1: ngưỡng theo nhóm đạt 1 − α ở từng nhóm.
        "group_cov_0.90pm0.01": all(abs(c["cov_group_mean"] - (1 - ALPHA)) <= 0.01 for c in cells),
        "global_overcovers_fix": by["fix"]["cov_global_mean"] > 1 - ALPHA,
        "global_undercovers_float": by["float"]["cov_global_mean"] < 1 - ALPHA,
        "global_undercovers_loss": by["loss"]["cov_global_mean"] < 1 - ALPHA,
        "q_group_increasing": by["fix"]["q_group_mean"] < by["float"]["q_group_mean"] < by["loss"]["q_group_mean"],
    }
    quant = []
    for i, name in enumerate(GROUP_NAMES):
        c = by[name]
        for key, tol in (("cov_global", 0.02), ("cov_group", 0.02)):
            x, ref = c[f"{key}_mean"], DRAFT_TABLE2[key][i]
            quant.append({"item": f"{key}@{name}", "ours": x, "draft": ref, "ok": abs(x - ref) <= tol})
        x, ref = c["q_group_mean"], DRAFT_TABLE2["q_group"][i]
        quant.append({"item": f"q_group@{name}", "ours": x, "draft": ref, "ok": abs(x - ref) <= 0.15 * ref})
    x, ref = by["fix"]["q_global_mean"], DRAFT_TABLE2["q_global"]
    quant.append({"item": "q_global", "ours": x, "draft": ref, "ok": abs(x - ref) <= 0.15 * ref})
    return {
        "cells": cells, "qualitative": qual, "quantitative": quant,
        "all_qualitative": all(qual.values()), "all_quantitative": all(r["ok"] for r in quant),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--reps", type=int, default=N_REP)
    ap.add_argument("--sensitivity", action="store_true", help="chạy thêm U6-B, U1-W (chỉ ghi vào summary)")
    args = ap.parse_args()

    df = run(args.reps, args.seed)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(LOG_DIR / "n3_groups.csv", index=False, float_format="%.10g")
    res = summarize(df)
    update_json("summary.json", "N3", res)
    update_json("config.json", "N3", {
        "spec": SPEC_VERSION, "seed": args.seed, "reps": args.reps, "alpha": ALPHA,
        "n_cal": N_CAL, "n_test": N_TEST, "groups": list(GROUP_NAMES),
        "group_sigma": GROUP_SIGMA.tolist(), "group_probs": GROUP_PROBS.tolist(),
        "params": DEFAULT_PARAMS.to_dict(), "generated_at": stamp(),
    })

    print(f"{'nhóm':<6} {'n_cal':>6} {'phủ chung':>15} {'phủ nhóm':>15} {'q chung':>13} {'q nhóm':>14} {'inf':>4}")
    for c in res["cells"]:
        print(f"{c['group']:<6} {c['n_cal_g_mean']:>6.1f} {c['cov_global_mean']:.3f} ± {c['cov_global_sd']:.3f}"
              f"   {c['cov_group_mean']:.3f} ± {c['cov_group_sd']:.3f}   {c['q_global_mean']:.2f} ± {c['q_global_sd']:.2f}"
              f"  {c['q_group_mean']:6.2f} ± {c['q_group_sd']:.2f} {c['q_group_inf_count']:>4}")
    for k, v in res["qualitative"].items():
        print(f"  [định tính] {k}: {v}")
    for r in res["quantitative"]:
        print(f"  [định lượng] {r['item']:<18} ours={r['ours']:.4f}  draft={r['draft']:.3f}  {'✓' if r['ok'] else '✗'}")
    print(f"  => định tính: {res['all_qualitative']}, định lượng: {res['all_quantitative']}")
    if args.sensitivity:
        sens = {}
        for v in ("U6B", "U1W"):
            cell, params = VARIANTS[v]
            r = summarize(run(args.reps, args.seed, cell, params))
            sens[v] = {"params": params.to_dict(), **r}
            print(f"\n=== độ nhạy {v} ===")
            for c in r["cells"]:
                print(f"  {c['group']:<6} phủ chung {c['cov_global_mean']:.3f}  phủ nhóm {c['cov_group_mean']:.3f}"
                      f"  q chung {c['q_global_mean']:.2f}  q nhóm {c['q_group_mean']:.2f}")
            print(f"  => định tính: {r['all_qualitative']}, định lượng: {r['all_quantitative']}")
        update_json("summary.json", "N3_sensitivity", sens)
    print("Đã ghi", LOG_DIR / "n3_groups.csv")


if __name__ == "__main__":
    main()
