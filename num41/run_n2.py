"""N2 — so sánh bốn loại biên ĐX, B1, B3, B4 theo σ_loc và theo ρ (Hình 2 của bản thảo) — SPEC §10.3–10.4.

Chạy: python -m num41.run_n2 [--sensitivity]  (từ thư mục ws)
  --sensitivity: chạy thêm N2-S (U6-B: ω, a đổi từng bước; U1-W: định vị nhiễu trắng không trôi).
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from num41 import SPEC_VERSION
from num41.gen import DEFAULT_PARAMS, SEED, make_rng, sample, with_params
from num41.logio import LOG_DIR, save_fig, stamp, update_json
from num41.scores import coverage, q, rho_emp, scores, thresholds

ALPHA = 0.10
N_CAL = 1000
N_TEST = 2000
N_REP = 50
SIGMAS = (0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5)  # [GĐ U8]
RHOS = (-0.5, 0.0, 0.5, 0.9)                    # [GĐ U9]
RHO_SIGMA = 0.1
METHODS = ("DX", "B1", "B3", "B4")

VARIANTS = {
    "base": ("N2", DEFAULT_PARAMS),
    "U6B": ("N2S", with_params(motion="per_step")),
    "U1W": ("N2S", with_params(loc_drift=False)),
}
VARIANT_OFFSET = {"base": 0, "U6B": 0, "U1W": 100}  # cell_id = offset + chỉ số σ (tách luồng hai biến thể N2-S)

# Số trong bản thảo v0.1 (PLAN §10.4).
DRAFT = {
    "cov_B1": {0.0: 0.996, 0.2: 0.972, 0.5: 0.802},
    "q_DX": {0.1: 1.82, 0.5: 5.77},
    "q_B3": {0.1: 7.81, 0.5: 18.0},
    "q_B4": {0.1: 9.21, 0.5: 25.6},
    "ratio_rho": {-0.5: 0.23, 0.9: 0.31},
    "cov_DX_range": (0.898, 0.903),
}


def run_sigma(variant: str, n_rep: int, seed: int) -> pd.DataFrame:
    exp, params = VARIANTS[variant]
    rows = []
    for ci, sl in enumerate(SIGMAS):
        cell = VARIANT_OFFSET[variant] + ci
        for rep in range(n_rep):
            cal = scores(sample(N_CAL, make_rng(exp, cell, rep, 0, seed), sigma_loc=sl, params=params))
            r_test = scores(sample(N_TEST, make_rng(exp, cell, rep, 1, seed), sigma_loc=sl, params=params))["R"]
            for m, thr in thresholds(cal, ALPHA).items():
                rows.append({"variant": variant, "sigma_loc": sl, "rep": rep, "method": m,
                             "q": thr, "coverage": coverage(r_test, thr)})
    return pd.DataFrame(rows)


def run_rho(n_rep: int, seed: int) -> pd.DataFrame:
    rows = []
    for ci, rho in enumerate(RHOS):
        for rep in range(n_rep):
            b_cal = sample(N_CAL, make_rng("N2rho", ci, rep, 0, seed), sigma_loc=RHO_SIGMA, rho=rho)
            cal = scores(b_cal)
            r_test = scores(sample(N_TEST, make_rng("N2rho", ci, rep, 1, seed), sigma_loc=RHO_SIGMA, rho=rho))["R"]
            q_dx = q(cal["R"], ALPHA)
            q_b3 = q(cal["A"], ALPHA / 2) + q(cal["E"], ALPHA / 2)
            rows.append({"rho": rho, "rep": rep, "q_dx": q_dx, "q_b3": q_b3, "ratio": q_dx / q_b3,
                         "rho_emp": rho_emp(b_cal), "cov_dx": coverage(r_test, q_dx)})
    return pd.DataFrame(rows)


def _agg(df: pd.DataFrame) -> pd.DataFrame:
    return (df.groupby(["variant", "sigma_loc", "method"], sort=False)
              .agg(q_mean=("q", "mean"), q_sd=("q", "std"), cov_mean=("coverage", "mean"), cov_sd=("coverage", "std"))
              .reset_index())


def _within(x: float, ref: float, rel: float | None = None, abs_: float | None = None) -> bool:
    return abs(x - ref) <= (abs_ if abs_ is not None else rel * abs(ref))


def check(df_s: pd.DataFrame, df_r: pd.DataFrame, variant: str) -> dict:
    d = df_s[df_s["variant"] == variant]
    agg = _agg(d).set_index(["sigma_loc", "method"])
    piv = d.pivot_table(index=["sigma_loc", "rep"], columns="method", values="q")
    n_viol = int((piv["DX"] > piv["B3"]).sum())

    cov_dx = [agg.loc[(s, "DX"), "cov_mean"] for s in SIGMAS]
    cov_b1 = [agg.loc[(s, "B1"), "cov_mean"] for s in SIGMAS]
    qual = {
        "DX_cov_0.90pm0.01": bool(all(abs(c - 0.90) <= 0.01 for c in cov_dx)),
        "B1_cov_decreasing": bool(np.all(np.diff(cov_b1) <= 1e-12)),
        "propA3_violations": n_viol,
        "propA3_ok": n_viol == 0,
        "B4_wider_B3": bool(all(agg.loc[(s, "B4"), "q_mean"] > agg.loc[(s, "B3"), "q_mean"] for s in SIGMAS)),
    }
    quant = []
    for s, ref in DRAFT["cov_B1"].items():
        x = agg.loc[(s, "B1"), "cov_mean"]
        quant.append({"item": f"cov_B1@{s}", "ours": x, "draft": ref, "ok": _within(x, ref, abs_=0.02)})
    for key, m in (("q_DX", "DX"), ("q_B3", "B3"), ("q_B4", "B4")):
        for s, ref in DRAFT[key].items():
            x = agg.loc[(s, m), "q_mean"]
            quant.append({"item": f"{key}@{s}", "ours": x, "draft": ref, "ok": _within(x, ref, rel=0.15)})
    lo, hi = DRAFT["cov_DX_range"]
    quant.append({"item": "cov_DX_min", "ours": min(cov_dx), "draft": lo, "ok": _within(min(cov_dx), lo, abs_=0.02)})
    quant.append({"item": "cov_DX_max", "ours": max(cov_dx), "draft": hi, "ok": _within(max(cov_dx), hi, abs_=0.02)})

    out = {"qualitative": qual, "quantitative": quant, "table": agg.reset_index().to_dict("records")}
    if variant == "base" and df_r is not None:
        rr = df_r.groupby("rho").agg(ratio_mean=("ratio", "mean"), ratio_sd=("ratio", "std"),
                                     rho_emp=("rho_emp", "mean"), cov_dx=("cov_dx", "mean"),
                                     q_dx=("q_dx", "mean"), q_b3=("q_b3", "mean"))
        ratios = rr["ratio_mean"].to_numpy()
        qual["ratio_increasing_in_rho"] = bool(np.all(np.diff(ratios) > 0))
        qual["rho_propA3_violations"] = int((df_r["q_dx"] > df_r["q_b3"]).sum())
        for rho, ref in DRAFT["ratio_rho"].items():
            x = float(rr.loc[rho, "ratio_mean"])
            quant.append({"item": f"ratio@rho={rho}", "ours": x, "draft": ref, "ok": _within(x, ref, rel=0.15)})
        out["rho_table"] = rr.reset_index().to_dict("records")
    out["all_qualitative"] = bool(all(v for k, v in qual.items() if not k.endswith("violations")))
    out["all_quantitative"] = bool(all(r["ok"] for r in quant))
    return out


COLORS = {"DX": "#1a7f37", "B1": "#c0392b", "B3": "#1f5fbf", "B4": "#8e44ad"}
LABELS = {"DX": "ĐX (q_R)", "B1": "B1 (chỉ tác nhân)", "B3": "B3 (cộng hai biên)", "B4": "B4 (xấu nhất)"}


def plot(df_s: pd.DataFrame, df_r: pd.DataFrame):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    agg = _agg(df_s[df_s["variant"] == "base"])
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.2))
    for m in METHODS:
        g = agg[agg["method"] == m]
        axes[0].errorbar(g["sigma_loc"], g["cov_mean"], yerr=g["cov_sd"], marker="o", ms=4, capsize=2,
                         color=COLORS[m], label=LABELS[m])
        axes[1].errorbar(g["sigma_loc"], g["q_mean"], yerr=g["q_sd"], marker="o", ms=4, capsize=2,
                         color=COLORS[m], label=LABELS[m])
    axes[0].axhline(1 - ALPHA, ls=":", color="gray", lw=1)
    axes[0].set_ylim(0.75, 1.005)
    axes[0].set_title("(a) Độ phủ theo σ_loc")
    axes[0].set_ylabel("Độ phủ P(R ≤ q)")
    axes[1].set_title("(b) Ngưỡng chuẩn hóa theo σ_loc")
    axes[1].set_ylabel("q")
    for ax in axes[:2]:
        ax.set_xlabel("σ_loc (m)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8, loc="lower left")

    rr = df_r.groupby("rho").agg(m=("ratio", "mean"), s=("ratio", "std"), e=("rho_emp", "mean")).reset_index()
    axes[2].errorbar(rr["rho"], rr["m"], yerr=rr["s"], marker="s", capsize=3, color="#1a7f37", label="Tái lập")
    axes[2].plot(list(DRAFT["ratio_rho"].keys()), list(DRAFT["ratio_rho"].values()), "x--", color="gray",
                 label="Bản thảo v0.1 (hai đầu)")
    for _, r in rr.iterrows():
        axes[2].annotate(f"ρ_emp={r['e']:.2f}", (r["rho"], r["m"]), textcoords="offset points", xytext=(4, -12),
                         fontsize=7)
    axes[2].set_title(f"(c) q_ĐX / q_B3 theo ρ (σ_loc = {RHO_SIGMA} m)".replace(".", ","))
    axes[2].set_xlabel("ρ")
    axes[2].set_ylabel("q_ĐX / q_B3")
    axes[2].grid(alpha=0.3)
    axes[2].legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    return save_fig(fig, "N2_bounds")


def _print(res: dict, name: str) -> None:
    print(f"\n=== {name} ===")
    for k, v in res["qualitative"].items():
        print(f"  [định tính] {k}: {v}")
    for r in res["quantitative"]:
        print(f"  [định lượng] {r['item']:<14} ours={r['ours']:.4f}  draft={r['draft']:.3f}  {'✓' if r['ok'] else '✗'}")
    print(f"  => định tính: {res['all_qualitative']}, định lượng: {res['all_quantitative']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--reps", type=int, default=N_REP)
    ap.add_argument("--sensitivity", action="store_true")
    args = ap.parse_args()

    variants = ["base"] + (["U6B", "U1W"] if args.sensitivity else [])
    df_s = pd.concat([run_sigma(v, args.reps, args.seed) for v in variants], ignore_index=True)
    df_r = run_rho(args.reps, args.seed)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    df_s.to_csv(LOG_DIR / "n2_bounds.csv", index=False, float_format="%.10g")
    df_r.to_csv(LOG_DIR / "n2_rho.csv", index=False, float_format="%.10g")

    results = {v: check(df_s, df_r if v == "base" else None, v) for v in variants}
    update_json("summary.json", "N2", results)
    update_json("config.json", "N2", {
        "spec": SPEC_VERSION, "seed": args.seed, "reps": args.reps, "alpha": ALPHA,
        "n_cal": N_CAL, "n_test": N_TEST, "sigmas": list(SIGMAS), "rhos": list(RHOS), "rho_sigma": RHO_SIGMA,
        "variants": {v: VARIANTS[v][1].to_dict() for v in variants}, "generated_at": stamp(),
    })
    fig_path = plot(df_s, df_r)

    agg = _agg(df_s)
    with pd.option_context("display.width", 140, "display.max_rows", 200):
        print(agg.pivot_table(index=["variant", "sigma_loc"], columns="method",
                              values=["cov_mean", "q_mean"], sort=False).round(4))
    for v, res in results.items():
        _print(res, v)
    if "rho_table" in results["base"]:
        print(pd.DataFrame(results["base"]["rho_table"]).round(4).to_string(index=False))
    print("Đã ghi", LOG_DIR / "n2_bounds.csv", LOG_DIR / "n2_rho.csv", fig_path)


if __name__ == "__main__":
    main()
