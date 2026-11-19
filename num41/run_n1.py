"""N1 — độ phủ của ngưỡng ĐX theo α và n (Bảng 1, Hình 1 của bản thảo) — SPEC §10.3.

Mỗi lần lặp: một mẫu hiệu chỉnh cỡ 1000 (split 0) và một mẫu kiểm tra cỡ 2000 (split 1),
dùng chung cho mọi (α, n); n = 100, 500 lấy n mẫu đầu.

Chạy: python -m num41.run_n1  (từ thư mục ws)
"""

from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

from num41 import SPEC_VERSION
from num41.gen import DEFAULT_PARAMS, SEED, make_rng, sample
from num41.logio import LOG_DIR, save_fig, stamp, update_json
from num41.scores import coverage, q, scores

ALPHAS = (0.20, 0.10, 0.05)
NS = (100, 500, 1000)
N_REP = 200
N_TEST = 2000
SIGMA_LOC = 0.1  # [GĐ U7]

# Bảng 1 của bản thảo v0.1 (trung bình ± độ lệch chuẩn), khóa (n, α).
DRAFT_TABLE1 = {
    (100, 0.20): (0.806, 0.041), (100, 0.10): (0.903, 0.029), (100, 0.05): (0.950, 0.023),
    (500, 0.20): (0.798, 0.021), (500, 0.10): (0.900, 0.015), (500, 0.05): (0.949, 0.010),
    (1000, 0.20): (0.801, 0.016), (1000, 0.10): (0.900, 0.012), (1000, 0.05): (0.950, 0.009),
}


def theory(n: int, alpha: float, m: int = N_TEST) -> tuple[float, float]:
    """Trung bình và độ lệch chuẩn lý thuyết của độ phủ thực nghiệm trên m mẫu kiểm tra.

    Độ phủ có điều kiện C ~ Beta(k, n+1−k), k = ⌈(n+1)(1−α)⌉; độ phủ thực nghiệm = Binom(m, C)/m.
    Var = Var(C) + E[C(1−C)]/m.
    """
    k = math.ceil((n + 1) * (1 - alpha))
    a, b = k, n + 1 - k
    mu = a / (a + b)
    var_c = a * b / ((a + b) ** 2 * (a + b + 1))
    var = var_c + (mu - var_c - mu * mu) / m
    return mu, math.sqrt(var)


def run(n_rep: int = N_REP, seed: int = SEED) -> pd.DataFrame:
    rows = []
    n_max = max(NS)
    for rep in range(n_rep):
        r_cal = scores(sample(n_max, make_rng("N1", 0, rep, 0, seed), sigma_loc=SIGMA_LOC))["R"]
        r_test = scores(sample(N_TEST, make_rng("N1", 0, rep, 1, seed), sigma_loc=SIGMA_LOC))["R"]
        for alpha in ALPHAS:
            for n in NS:
                thr = q(r_cal[:n], alpha)
                rows.append({"alpha": alpha, "n": n, "rep": rep, "q": thr, "coverage": coverage(r_test, thr)})
    return pd.DataFrame(rows)


def summarize(df: pd.DataFrame) -> list[dict]:
    out = []
    for (alpha, n), g in df.groupby(["alpha", "n"], sort=False):
        cov = g["coverage"].to_numpy()
        mean, sd = float(cov.mean()), float(cov.std(ddof=1))
        se = sd / math.sqrt(len(cov))
        mu_t, sd_t = theory(int(n), float(alpha))
        d_mean, d_sd = DRAFT_TABLE1[(int(n), float(alpha))]
        out.append({
            "alpha": float(alpha), "n": int(n), "reps": int(len(cov)),
            "mean": mean, "sd": sd, "se": se, "q_mean": float(g["q"].mean()),
            "theory_mean": mu_t, "theory_sd": sd_t,
            "z_mean": (mean - mu_t) / se,
            "sd_ratio": sd / sd_t,
            "pass_mean_3se": abs(mean - mu_t) <= 3 * se,
            "pass_sd_15pct": abs(sd / sd_t - 1) <= 0.15,
            "draft_mean": d_mean, "draft_sd": d_sd,
            "diff_mean_vs_draft": mean - d_mean, "diff_sd_vs_draft": sd - d_sd,
        })
    return out


def plot(summary: list[dict]):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    nominal = np.array([1 - a for a in ALPHAS])
    ax.plot([0.75, 1.0], [0.75, 1.0], ":", color="gray", lw=1, label="y = 1 − α")
    offs = {100: -0.004, 500: 0.0, 1000: 0.004}
    for n, mk in zip(NS, ("o", "s", "^")):
        rows = sorted((r for r in summary if r["n"] == n), key=lambda r: r["alpha"], reverse=True)
        x = np.array([1 - r["alpha"] for r in rows]) + offs[n]
        ax.errorbar(x, [r["mean"] for r in rows], yerr=[r["sd"] for r in rows],
                    marker=mk, capsize=3, lw=1.2, label=f"n = {n}")
    ax.set_xticks(nominal, [f"{v:.2f}".replace(".", ",") for v in nominal])
    ax.set_xlim(0.76, 0.99)
    ax.set_ylim(0.70, 1.0)
    ax.set_xlabel("Mức phủ danh định 1 − α")
    ax.set_ylabel("Độ phủ thực nghiệm (TB ± ĐLC)")
    ax.set_title(f"N1 — {N_REP} lần lặp, {N_TEST} mẫu kiểm tra")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    return save_fig(fig, "N1_coverage")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--reps", type=int, default=N_REP)
    args = ap.parse_args()

    df = run(args.reps, args.seed)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(LOG_DIR / "n1_coverage.csv", index=False, float_format="%.10g")
    summ = summarize(df)
    update_json("summary.json", "N1", {
        "all_pass_theory": all(r["pass_mean_3se"] and r["pass_sd_15pct"] for r in summ),
        "cells": summ,
    })
    update_json("config.json", "N1", {
        "spec": SPEC_VERSION, "seed": args.seed, "reps": args.reps, "n_test": N_TEST,
        "alphas": list(ALPHAS), "ns": list(NS), "sigma_loc": SIGMA_LOC,
        "params": DEFAULT_PARAMS.to_dict(), "generated_at": stamp(),
    })
    fig_path = plot(summ)

    print(f"{'n':>5} {'α':>5} | {'TB':>6} {'ĐLC':>6} | {'LT TB':>6} {'LT ĐLC':>6} {'z':>6} {'ĐLC/LT':>6} | "
          f"{'BT TB':>6} {'BT ĐLC':>6} | đạt")
    for r in sorted(summ, key=lambda r: (r["n"], -r["alpha"])):
        ok = "✓" if r["pass_mean_3se"] and r["pass_sd_15pct"] else "✗"
        print(f"{r['n']:>5} {r['alpha']:>5.2f} | {r['mean']:.4f} {r['sd']:.4f} | {r['theory_mean']:.4f} "
              f"{r['theory_sd']:.4f} {r['z_mean']:>+6.2f} {r['sd_ratio']:>6.3f} | {r['draft_mean']:.3f}  "
              f"{r['draft_sd']:.3f}  | {ok}")
    print("Đã ghi", LOG_DIR / "n1_coverage.csv", "và", fig_path)


if __name__ == "__main__":
    main()
