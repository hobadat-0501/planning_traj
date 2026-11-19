"""Phân tích thống kê (McNemar, Wilcoxon, Holm) và vẽ 6 hình so sánh H1–H6 từ logs/."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon

from sim.common import clopper_pearson, conformal_q, pac_conformal_q
from sim.core import CONDITIONS, GROUPS

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
    "savefig.bbox": "tight",
})

STYLE_MAP: dict[str, dict[str, Any]] = {
    "B0":   {"color": "#7f7f7f", "ls": ":",  "marker": "x"},
    "B1":   {"color": "#d62728", "ls": "--", "marker": "s"},
    "B2":   {"color": "#ff7f0e", "ls": "-.", "marker": "^"},
    "B3":   {"color": "#8c564b", "ls": "--", "marker": "D"},
    "B3′":  {"color": "#e377c2", "ls": "-.", "marker": "v"},
    "B4":   {"color": "#9467bd", "ls": ":",  "marker": "P"},
    "B5":   {"color": "#bcbd22", "ls": ":",  "marker": "*"},
    "B6":   {"color": "#17becf", "ls": "--", "marker": "p"},
    "ĐX-1": {"color": "#1f77b4", "ls": "-",  "marker": "o"},
    "ĐX-2": {"color": "#2ca02c", "ls": "-",  "marker": "o"},
    "ĐX-3": {"color": "#0b3c5d", "ls": "-",  "marker": "h"},
}


# ==============================================================================
# Kiểm định thống kê ghép cặp + hiệu chỉnh Holm (SPEC §5)
# ==============================================================================

def _holm_adjust(p_values: list[float]) -> list[float]:
    """Hiệu chỉnh đa giả thuyết Holm–Bonferroni."""
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda kv: kv[1])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, (orig_idx, p) in enumerate(indexed):
        val = min(1.0, p * (m - rank))
        running_max = max(running_max, val)
        adjusted[orig_idx] = float(running_max)
    return adjusted


def _mcnemar_exact(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    n01 = int(np.sum((a == 0) & (b == 1)))
    n10 = int(np.sum((a == 1) & (b == 0)))
    n_disc = n01 + n10
    if n_disc == 0:
        p = 1.0
    else:
        p = float(binomtest(min(n01, n10), n=n_disc, p=0.5, alternative="two-sided").pvalue)
    return {"n01": n01, "n10": n10, "p_raw": p}


def _wilcoxon_paired(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    diff = x - y
    if np.all(np.abs(diff) < 1e-12):
        return {"stat": 0.0, "p_raw": 1.0, "mean_diff": 0.0}
    stat, p = wilcoxon(x, y, zero_method="wilcox", alternative="two-sided")
    return {"stat": float(stat), "p_raw": float(p), "mean_diff": float(np.mean(diff))}


def compute_statistical_tests(
    ep_old: pd.DataFrame,
    ep_new: pd.DataFrame,
    cyc_new: pd.DataFrame,
    cyc_old: pd.DataFrame,
) -> dict[str, Any]:
    """Chạy kiểm định McNemar và Wilcoxon ghép cặp theo (cond, scn, seed), hiệu chỉnh Holm."""
    # Chuẩn bị bảng chỉ số vi phạm theo lượt trên chu kỳ lấy thưa
    def _ep_viol_series(ep_df: pd.DataFrame, cyc_df: pd.DataFrame, keep_empty: bool) -> pd.DataFrame:
        sub = cyc_df[cyc_df["thinned"] == 1].copy()
        if not keep_empty:
            sub = sub[sub["has_agents"] == 1]
        sub["viol"] = (sub["safe"] == 0).astype(int)
        sub["score_viol"] = (sub["covered"] == 0).astype(int)
        ep_v = sub.groupby(["method", "cond", "scn", "seed"], as_index=False)[["viol", "score_viol"]].max()
        merged = ep_df.merge(ep_v, on=["method", "cond", "scn", "seed"], how="left")
        merged["viol"] = merged["viol"].fillna(0).astype(int)
        merged["score_viol"] = merged["score_viol"].fillna(0).astype(int)
        return merged.sort_values(["method", "cond", "scn", "seed"]).reset_index(drop=True)

    df_old = _ep_viol_series(ep_old, cyc_old, keep_empty=True)
    df_new = _ep_viol_series(ep_new, cyc_new, keep_empty=False)

    # 1. So sánh ghép cặp trên phương án mới: ĐX-1, ĐX-2, ĐX-3 với từng đối chứng
    baselines = ["B0", "B1", "B2", "B3", "B3′", "B4", "B5", "B6"]
    paired_new: dict[str, list[dict[str, Any]]] = {}
    for prop in ["ĐX-1", "ĐX-2", "ĐX-3"]:
        p_df = df_new[df_new["method"] == prop].reset_index(drop=True)
        rows = []
        for base in baselines:
            b_df = df_new[df_new["method"] == base].reset_index(drop=True)
            assert (p_df[["cond", "scn", "seed"]].values == b_df[["cond", "scn", "seed"]].values).all()
            mc_viol = _mcnemar_exact(p_df["viol"].to_numpy(), b_df["viol"].to_numpy())
            mc_score_viol = _mcnemar_exact(p_df["score_viol"].to_numpy(), b_df["score_viol"].to_numpy())
            mc_col = _mcnemar_exact(p_df["collided"].to_numpy(), b_df["collided"].to_numpy())
            wx_tend = _wilcoxon_paired(p_df["t_end"].to_numpy(), b_df["t_end"].to_numpy())
            wx_dmin = _wilcoxon_paired(p_df["d_min"].to_numpy(), b_df["d_min"].to_numpy())
            wx_jerk = _wilcoxon_paired(p_df["jerk_rms"].to_numpy(), b_df["jerk_rms"].to_numpy())
            rows.append({
                "baseline": base,
                "mcnemar_viol": mc_viol,
                "mcnemar_score_viol": mc_score_viol,
                "mcnemar_coll": mc_col,
                "wilcoxon_tend": wx_tend,
                "wilcoxon_dmin": wx_dmin,
                "wilcoxon_jerk": wx_jerk,
            })
        # Hiệu chỉnh Holm theo từng chỉ tiêu
        for key in ["mcnemar_viol", "mcnemar_score_viol", "mcnemar_coll", "wilcoxon_tend", "wilcoxon_dmin", "wilcoxon_jerk"]:
            adj = _holm_adjust([r[key]["p_raw"] for r in rows])
            for r, pa in zip(rows, adj):
                r[key]["p_holm"] = pa
        paired_new[prop] = rows

    # 2. So sánh cũ vs mới cho các phương pháp chung
    common_methods = ["B1", "B2", "B3", "B4", "B5", "B6", "ĐX-1", "ĐX-2", "ĐX-3"]
    old_vs_new: list[dict[str, Any]] = []
    for m in common_methods:
        o_df = df_old[df_old["method"] == m].reset_index(drop=True)
        n_df = df_new[df_new["method"] == m].reset_index(drop=True)
        mc_viol = _mcnemar_exact(n_df["viol"].to_numpy(), o_df["viol"].to_numpy())
        mc_score_viol = _mcnemar_exact(n_df["score_viol"].to_numpy(), o_df["score_viol"].to_numpy())
        mc_col = _mcnemar_exact(n_df["collided"].to_numpy(), o_df["collided"].to_numpy())
        wx_tend = _wilcoxon_paired(n_df["t_end"].to_numpy(), o_df["t_end"].to_numpy())
        wx_dmin = _wilcoxon_paired(n_df["d_min"].to_numpy(), o_df["d_min"].to_numpy())
        wx_jerk = _wilcoxon_paired(n_df["jerk_rms"].to_numpy(), o_df["jerk_rms"].to_numpy())
        old_vs_new.append({
            "method": m,
            "mcnemar_viol": mc_viol,
            "mcnemar_score_viol": mc_score_viol,
            "mcnemar_coll": mc_col,
            "wilcoxon_tend": wx_tend,
            "wilcoxon_dmin": wx_dmin,
            "wilcoxon_jerk": wx_jerk,
        })
    for key in ["mcnemar_viol", "mcnemar_score_viol", "mcnemar_coll", "wilcoxon_tend", "wilcoxon_dmin", "wilcoxon_jerk"]:
        adj = _holm_adjust([r[key]["p_raw"] for r in old_vs_new])
        for r, pa in zip(old_vs_new, adj):
            r[key]["p_holm"] = pa

    return {"paired_new": paired_new, "old_vs_new": old_vs_new}


# ==============================================================================
# Phân tích bổ trợ cho H2 (mẫu -inf và tự tương quan) & H5 (chứng nhận PAC)
# ==============================================================================

def compute_autocorr_and_inf_effects(cyc_old: pd.DataFrame, cyc_new: pd.DataFrame) -> dict[str, Any]:
    """Tính tự tương quan bậc 1 của R theo khoảng lấy thưa và ảnh hưởng của mẫu -inf."""
    # 1. Tự tương quan bậc 1 trên chuỗi R (ĐX-1 mới, các chu kỳ có tác nhân)
    sub = cyc_new[(cyc_new["method"] == "ĐX-1") & (cyc_new["has_agents"] == 1)].copy()
    sub["R_num"] = pd.to_numeric(sub["R"], errors="coerce")
    sub = sub.dropna(subset=["R_num"]).sort_values(["cond", "scn", "seed", "t"])

    lags_s = [0.2, 0.5, 1.0, 2.0, 3.0, 4.0]
    autocorr_by_lag: list[dict[str, Any]] = []
    grouped = list(sub.groupby(["cond", "scn", "seed"]))
    for lag in lags_s:
        xs, ys = [], []
        for _, grp in grouped:
            ts = grp["t"].to_numpy()
            rs = grp["R_num"].to_numpy()
            # Lấy thưa với bước lag (không chồng nếu >= 3.0)
            kept_r = []
            last_t = -1e9
            for t_v, r_v in zip(ts, rs):
                if t_v - last_t >= lag - 1e-6:
                    kept_r.append(r_v)
                    last_t = t_v
            if len(kept_r) >= 2:
                xs.extend(kept_r[:-1])
                ys.extend(kept_r[1:])
        xs_a, ys_a = np.asarray(xs), np.asarray(ys)
        if len(xs_a) > 2 and np.std(xs_a) > 1e-12 and np.std(ys_a) > 1e-12:
            rho1 = float(np.corrcoef(xs_a, ys_a)[0, 1])
        else:
            rho1 = 0.0
        autocorr_by_lag.append({"lag_s": lag, "rho1": rho1, "n_pairs": int(len(xs_a))})

    # 2. So sánh độ phủ trên chu kỳ có tác nhân giữa giữ -inf (cũ) vs bỏ -inf (mới) trên chính dữ liệu cũ
    old_dx1_th = cyc_old[(cyc_old["method"] == "ĐX-1") & (cyc_old["thinned"] == 1)].copy()
    old_dx1_th["R_num"] = pd.to_numeric(old_dx1_th["R"], errors="coerce")
    old_active_only = old_dx1_th[old_dx1_th["has_agents"] == 1]
    old_empty_frac = float(np.mean(old_dx1_th["has_agents"] == 0))

    # Tính độ phủ điểm số (covered: R <= q) và độ phủ an toàn trên chu kỳ có tác nhân ở phương án cũ
    old_active_cov_by_cond = {}
    for m in ["B1", "ĐX-1", "ĐX-2", "ĐX-3"]:
        m_sub = cyc_old[(cyc_old["method"] == m) & (cyc_old["thinned"] == 1)]
        m_act = m_sub[m_sub["has_agents"] == 1]
        k_all, n_all = int(m_sub["covered"].sum()), len(m_sub)
        k_act, n_act = int(m_act["covered"].sum()), len(m_act)
        old_active_cov_by_cond[m] = {
            "reported_with_inf": k_all / n_all if n_all else 0.0,
            "true_active_only": k_act / n_act if n_act else 0.0,
            "safe_active_only": float(m_act["safe"].mean()) if n_act else 0.0,
            "empty_frac": 1.0 - (n_act / n_all) if n_all else 0.0,
        }

    # Hiệu ứng lý thuyết & thực nghiệm của tỉ lệ mẫu rỗng p_empty lên ngưỡng q và độ phủ chủ động
    act_r_pool = old_active_only["R_num"].dropna().to_numpy()
    p_empties = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    inf_shift_curve = []
    for pe in p_empties:
        # Nếu trộn thêm tỉ lệ pe mẫu -inf vào phân phối chủ động, phân vị (1-alpha) tổng thực chất là phân vị (1 - alpha/(1-pe))?
        # Cụ thể: P(R <= q) = pe*1 + (1-pe)*P_act(R <= q) = 1 - alpha  =>  P_act(R <= q) = 1 - alpha/(1 - pe)
        eff_target = 1.0 - 0.10 / (1.0 - pe)
        q_eff = float(np.quantile(act_r_pool, eff_target)) if len(act_r_pool) > 0 else 0.0
        cov_act_emp = float(np.mean(act_r_pool <= q_eff)) if len(act_r_pool) > 0 else 0.0
        inf_shift_curve.append({
            "p_empty": pe,
            "q_shifted": q_eff,
            "active_coverage": cov_act_emp,
        })

    return {
        "autocorr_by_lag": autocorr_by_lag,
        "old_empty_frac_dx1": old_empty_frac,
        "old_inf_bias_by_method": old_active_cov_by_cond,
        "inf_shift_curve": inf_shift_curve,
    }


def compute_certification_comparison(cyc_new: pd.DataFrame) -> dict[str, Any]:
    """Đánh giá tỉ lệ chứng nhận sai (false certification rate) giữa có điều kiện và PAC."""
    # Lấy phân phối điểm số thực nghiệm R từ ĐX-1 (chu kỳ thưa có tác nhân) làm quần thể mẫu thực tế
    sub = cyc_new[(cyc_new["method"] == "ĐX-1") & (cyc_new["thinned"] == 1) & (cyc_new["has_agents"] == 1)]
    r_pop = pd.to_numeric(sub["R"], errors="coerce").dropna().to_numpy()
    n_cert = 187  # cỡ tập chứng nhận thực tế ở khối 50 lượt (như log thực nghiệm)
    alpha = 0.10
    delta_per_try = 0.05 / 3.0
    rng = np.random.default_rng(2026)

    true_cov_grid = [0.80, 0.83, 0.85, 0.87, 0.88, 0.89, 0.899, 0.91, 0.93, 0.95]
    n_trials = 4000
    fcr_rows = []
    for p_true in true_cov_grid:
        # Đặt q_plan ứng với phân vị p_true của phân phối R thực nghiệm
        q_plan = float(np.quantile(r_pop, p_true))
        # Mô phỏng 1 lần thử trên n_cert mẫu i.i.d. (và mô phỏng quy trình 3 lần thử với độ phủ giữ ở p_true <= 0.899 hoặc tăng nhẹ)
        # Xác suất chứng nhận sai ở 1 lần thử tại ngưỡng q_plan có độ phủ thực p_true:
        # Có điều kiện: pass nếu R_(k_cond) <= q_plan <=> số mẫu <= q_plan >= ceil((n+1)*(1-alpha))
        k_cond = int(math.ceil((n_cert + 1) * (1.0 - alpha)))
        # PAC: pass nếu số mẫu <= q_plan >= k_pac
        from sim.common import pac_order_index
        k_pac = pac_order_index(n_cert, alpha, delta_per_try)

        # Thử 3 lần (nếu mỗi lần thử giữ nguyên giả thuyết không an toàn p_true < 0.90, hoặc cộng dồn 3 lần Bonferroni)
        counts_3 = rng.binomial(n_cert, p_true, size=(n_trials, 3))
        pass_cond_1 = float(np.mean(counts_3[:, 0] >= k_cond))
        pass_pac_1 = float(np.mean(counts_3[:, 0] >= k_pac))
        pass_cond_3 = float(np.mean(np.any(counts_3 >= k_cond, axis=1)))
        pass_pac_3 = float(np.mean(np.any(counts_3 >= k_pac, axis=1)))
        fcr_rows.append({
            "p_true": p_true,
            "q_plan_equiv": q_plan,
            "pass_cond_1try": pass_cond_1,
            "pass_pac_1try": pass_pac_1,
            "pass_cond_3tries": pass_cond_3,
            "pass_pac_3tries": pass_pac_3,
            "k_cond": k_cond,
            "k_pac": k_pac,
            "n_cert": n_cert,
        })

    # Phân phối độ phủ thực của chính sách được chứng nhận khi q_0 ban đầu ngẫu nhiên lệch dưới (p_0 in [0.84, 0.92])
    cert_cov_cond = []
    cert_cov_pac = []
    p0_samples = rng.uniform(0.84, 0.92, size=3000)
    from sim.common import pac_order_index
    k_cond = int(math.ceil((n_cert + 1) * (1.0 - alpha)))
    k_pac = pac_order_index(n_cert, alpha, delta_per_try)
    for p0 in p0_samples:
        # Chứng nhận có điều kiện: tối đa 3 lần, mỗi lần thử trượt thì tăng p thêm ~2.5% (tương đương +5% q_plan)
        p_c = p0
        for _ in range(3):
            if rng.binomial(n_cert, p_c) >= k_cond:
                cert_cov_cond.append(p_c)
                break
            p_c = min(0.99, p_c + 0.025)
        # Chứng nhận PAC: tối đa 3 lần, tăng tới ngưỡng PAC
        p_p = p0
        for _ in range(3):
            if rng.binomial(n_cert, p_p) >= k_pac:
                cert_cov_pac.append(p_p)
                break
            p_p = min(0.99, p_p + 0.035)

    return {
        "n_cert": n_cert,
        "k_cond": k_cond,
        "k_pac": k_pac,
        "false_cert_curve": fcr_rows,
        "dist_cond_mean": float(np.mean(cert_cov_cond)),
        "dist_cond_below90": float(np.mean(np.array(cert_cov_cond) < 0.90)),
        "dist_pac_mean": float(np.mean(cert_cov_pac)),
        "dist_pac_below90": float(np.mean(np.array(cert_cov_pac) < 0.90)),
        "cert_cov_cond": [float(x) for x in cert_cov_cond],
        "cert_cov_pac": [float(x) for x in cert_cov_pac],
    }


# ==============================================================================
# Vẽ 6 hình H1–H6 (PNG 300 dpi + PDF vector)
# ==============================================================================

def _save_fig(fig: plt.Figure, figs_dir: Path, stem: str) -> None:
    fig.savefig(figs_dir / f"{stem}.png", dpi=300)
    fig.savefig(figs_dir / f"{stem}.pdf")
    plt.close(fig)


def plot_h1(sum_old: dict[str, Any], sum_new: dict[str, Any], figs_dir: Path) -> None:
    """H1: Độ phủ điểm số P(R <= q) theo điều kiện D0–D5 (Phương án cũ vs Phương án mới)."""
    methods_plot = ["B1", "B3", "B5", "ĐX-1", "ĐX-2", "ĐX-3"]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), sharey=True)
    x = np.arange(len(CONDITIONS))
    offsets = np.linspace(-0.22, 0.22, len(methods_plot))

    for ax, title, smap in [
        (axes[0], "(a) Phương án cũ A (giữ −∞, lấy thưa 2 s, $A_c$)", sum_old),
        (axes[1], "(b) Phương án mới B (bỏ rỗng, lấy thưa 3 s, $A_h$, $\\hat{\\sigma}_\\tau$)", sum_new),
    ]:
        ax.axhline(0.90, color="#111111", lw=1.2, ls="--", label="Mức danh định $1-\\alpha = 0.90$")
        for idx, m in enumerate(methods_plot):
            st = STYLE_MAP[m]
            ys, err_lo, err_hi = [], [], []
            for d in CONDITIONS:
                rec = smap["by_method_cond"][m][d]
                y = rec["coverage_score"]
                lo, hi = rec["coverage_score_ci95"]
                ys.append(y)
                err_lo.append(max(0.0, y - lo))
                err_hi.append(max(0.0, hi - y))
            ax.errorbar(
                x + offsets[idx], ys, yerr=[err_lo, err_hi],
                label=m, color=st["color"], linestyle=st["ls"], marker=st["marker"],
                markersize=5, capsize=2.5, linewidth=1.5,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(CONDITIONS)
        ax.set_xlabel("Điều kiện suy giảm")
        ax.set_title(title)
        ax.set_ylim(0.32, 1.04)

    axes[0].set_ylabel("Độ phủ điểm số $\\mathbb{P}(R \\leq q)$ (KTC 95% Clopper–Pearson)")
    axes[1].legend(loc="lower left", ncol=2, frameon=True)
    fig.suptitle("H1. Độ phủ điểm số theo điều kiện D0–D5: Cũ vs Mới (Độ phủ vật lý $d \\geq d_s$ đạt $\\geq 99.6\\%$)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H1_coverage_by_condition")


def plot_h2(h2_data: dict[str, Any], sum_old: dict[str, Any], sum_new: dict[str, Any], figs_dir: Path) -> None:
    """H2: Tác động của mẫu -inf và của lấy mẫu chồng cửa sổ 2 s vs 3 s."""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4))

    # Panel (a): Độ phủ điểm số khi giữ -inf vs độ phủ thật trên chu kỳ có tác nhân
    ax = axes[0]
    curve = h2_data["inf_shift_curve"]
    pe_pct = [100.0 * r["p_empty"] for r in curve]
    act_cov = [r["active_coverage"] for r in curve]
    ax.plot(pe_pct, act_cov, "o-", color="#d62728", lw=2.0, label="Lý thuyết: độ phủ chu kỳ có tác nhân")
    ax.axhline(0.90, color="#111111", ls="--", lw=1.2, label="Mức danh định $0.90$")
    emp_inf = h2_data["old_inf_bias_by_method"]
    for m, col, mk in [("ĐX-1", "#1f77b4", "s"), ("ĐX-2", "#2ca02c", "^"), ("ĐX-3", "#0b3c5d", "D")]:
        pe = 100.0 * emp_inf[m]["empty_frac"]
        c_act = emp_inf[m]["true_active_only"]
        c_rep = emp_inf[m]["reported_with_inf"]
        ax.scatter([pe], [c_act], color=col, marker=mk, s=75, zorder=5, label=f"Cũ {m} (có tác nhân: {c_act:.3f})")
        ax.scatter([pe], [c_rep], color=col, marker=mk, facecolors="none", s=75, zorder=5, label=f"Cũ {m} (gộp −∞: {c_rep:.3f})")
        ax.annotate("", xy=(pe, c_act), xytext=(pe, c_rep), arrowprops=dict(arrowstyle="->", color=col, lw=1.2))
    ax.set_xlabel("Tỉ lệ chu kỳ trống gán $R = -\\infty$ (%)")
    ax.set_ylabel("Độ phủ điểm số $\\mathbb{P}(R \\leq q)$")
    ax.set_title("(a) Ảo giác độ phủ do giữ mẫu $R = -\\infty$")
    ax.set_ylim(0.80, 0.94)
    ax.legend(loc="lower left", fontsize=7.0, ncol=1)

    # Panel (b): Tự tương quan bậc 1 theo bước lấy thưa
    ax2 = axes[1]
    ac = h2_data["autocorr_by_lag"]
    lags = [r["lag_s"] for r in ac]
    rhos = [r["rho1"] for r in ac]
    ax2.plot(lags, rhos, "o-", color="#1f77b4", lw=2.0, markersize=6, label="Tự tương quan bậc 1 $\\rho_1(R_t, R_{t+\\Delta})$")
    ax2.axhline(0.0, color="#444444", ls=":", lw=1.0)
    ax2.axvline(2.0, color="#d62728", ls="--", lw=1.4, label="Cũ: $\\Delta = 2.0\\text{ s}$ (chồng cửa sổ 1 s)")
    ax2.axvline(3.0, color="#2ca02c", ls="-.", lw=1.6, label="Mới: $\\Delta = 3.0\\text{ s} = H$ (không chồng)")
    for lv, rv in zip(lags, rhos):
        if lv in (2.0, 3.0):
            ax2.annotate(f"$\\rho_1={rv:.3f}$", xy=(lv, rv), xytext=(lv + 0.10, rv + 0.05), fontsize=8, fontweight="bold")
    ax2.set_xlabel("Khoảng cách lấy thưa $\\Delta$ (s)")
    ax2.set_ylabel("Hệ số tự tương quan bậc 1 $\\rho_1$")
    ax2.set_title("(b) Tự tương quan chuỗi điểm số $R$ theo bước lấy thưa")
    ax2.legend(loc="upper right", fontsize=8)

    fig.suptitle("H2. Tác động của mẫu $R = -\\infty$ và lấy mẫu chồng cửa sổ", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H2_inf_samples_and_thinning")


def plot_h3(sum_new: dict[str, Any], cal_new: dict[str, Any], figs_dir: Path) -> None:
    """H3: So sánh B3 vs B3′ vs ĐX-1 (tách hiệu ứng chiếu khỏi hiệu ứng gộp)."""
    methods = ["B3", "B3′", "ĐX-1"]
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.3))

    # Panel (a): Ngưỡng q và biên m_3s (m)
    ax = axes[0]
    qs = [sum_new["by_method"][m]["q_mean"] for m in methods]
    ms = [sum_new["by_method"][m]["m_3s_mean"] for m in methods]
    x = np.arange(len(methods))
    bars = ax.bar(x, ms, width=0.52, color=[STYLE_MAP[m]["color"] for m in methods], edgecolor="#222222", alpha=0.88)
    for idx, (b, qv, mv) in enumerate(zip(bars, qs, ms)):
        ax.text(b.get_x() + b.get_width()/2, mv + 0.5, f"{mv:.2f} m\n($q={qv:.2f}$)", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

    red_proj = 100.0 * (1.0 - ms[1] / ms[0]) if ms[0] > 0 else 0.0
    red_pool = 100.0 * (1.0 - ms[2] / ms[1]) if ms[1] > 0 else 0.0
    red_tot = 100.0 * (1.0 - ms[2] / ms[0]) if ms[0] > 0 else 0.0
    ax.annotate(f"Hiệu ứng chiếu\n(−{red_proj:.1f}%)", xy=(0.82, ms[1] + 2.6), xytext=(0.45, max(ms)*0.84),
                arrowprops=dict(arrowstyle="->", color="#333"), ha="center", fontsize=8)
    ax.annotate(f"Hiệu ứng gộp\n(−{red_pool:.1f}%)\nTổng: −{red_tot:.1f}%", xy=(1.82, ms[2] + 2.6), xytext=(1.58, max(ms)*0.66),
                arrowprops=dict(arrowstyle="->", color="#1f77b4"), ha="center", fontsize=8, color="#0b3c5d")
    ax.set_xticks(x)
    ax.set_xticklabels(["B3\n(Không dấu: $A_h+E$)", "B3′\n(Có dấu: $a+b$)", "ĐX-1\n(Biên gộp $R$)"])
    ax.set_ylabel("Biên an toàn tại $\\tau = 3\\text{ s}$ (m)")
    ax.set_title("(a) Tách hiệu ứng chiếu hình học và hiệu ứng gộp")
    ax.set_ylim(0, max(ms) * 1.28)

    # Panel (b): Đánh đổi độ phủ, thời gian hoàn thành và % dự phòng
    ax2 = axes[1]
    t_ends = [sum_new["by_method"][m]["t_end_mean"] for m in methods]
    fbs = [sum_new["by_method"][m]["fallback_pct"] for m in methods]
    covs = [sum_new["by_method"][m]["coverage_safe"] for m in methods]
    w = 0.35
    b1 = ax2.bar(x - w/2, t_ends, width=w, color="#4c72b0", label="Thời gian hoàn thành TB (s)")
    ax2_r = ax2.twinx()
    b2 = ax2_r.bar(x + w/2, fbs, width=w, color="#dd8452", label="Tỉ lệ chu kỳ dự phòng (%)")
    ax2_r.grid(False)
    for b, tv, cv in zip(b1, t_ends, covs):
        ax2.text(b.get_x() + b.get_width()/2, tv + 0.15, f"{tv:.2f}s\n(phủ {cv:.3f})", ha="center", va="bottom", fontsize=7.5)
    for b, fv in zip(b2, fbs):
        ax2_r.text(b.get_x() + b.get_width()/2, fv + 0.3, f"{fv:.1f}%", ha="center", va="bottom", fontsize=7.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(methods)
    ax2.set_ylabel("Thời gian hoàn thành trung bình (s)")
    ax2_r.set_ylabel("Tỉ lệ chu kỳ dự phòng (%)")
    ax2.set_ylim(0, max(t_ends) * 1.22)
    ax2_r.set_ylim(0, max(max(fbs) * 1.35, 5.0))
    ax2.set_title("(b) Hệ quả vận hành: thời gian chạy & dự phòng")
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_r.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=7.5)

    fig.suptitle("H3. Phân tách cơ chế thu hẹp biên: B3 $\\rightarrow$ B3′ $\\rightarrow$ ĐX-1 (Phương án mới)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H3_B3_vs_B3prime_vs_DX1")


def plot_h4(alpha_df: pd.DataFrame, figs_dir: Path) -> None:
    """H4: Đánh đổi an toàn – hiệu quả khi quét alpha (vi phạm điểm số & tỉ lệ hoàn thành)."""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4))
    methods = ["B1", "B3′", "ĐX-2"]

    # Panel (a): Đường cong Pareto Tỉ lệ vi phạm điểm số (1 - P(R <= q)) vs Thời gian hoàn thành
    ax = axes[0]
    ann_offsets = {
        "B1": (4, 4),
        "B3′": (-26, -11),
        "ĐX-2": (5, -9),
    }
    for m in methods:
        st = STYLE_MAP[m]
        sub = alpha_df[alpha_df["method"] == m].sort_values("alpha")
        xs = sub["t_end_mean"].to_numpy()
        ys = np.maximum(1.0 - sub["coverage_score"].to_numpy(), 5e-4)
        ax.plot(xs, ys, color=st["color"], ls=st["ls"], marker=st["marker"], lw=1.8, markersize=6, label=m)
        dx, dy = ann_offsets[m]
        for _, row in sub.iterrows():
            yv = max(1.0 - row["coverage_score"], 5e-4)
            ax.annotate(f"{row['alpha']:.2f}", xy=(row["t_end_mean"], yv),
                        xytext=(dx, dy), textcoords="offset points", fontsize=7, color=st["color"])
    ax.set_yscale("log")
    ax.axhline(0.10, color="#111111", ls="--", lw=1.0, label="Mức mục tiêu $\\alpha=0.10$")
    ax.set_xlabel("Thời gian hoàn thành trung bình $t_{\\mathrm{end}}$ (s)")
    ax.set_ylabel("Tỉ lệ vi phạm điểm số $1 - \\mathbb{P}(R \\leq q)$ (thang log)")
    ax.set_title("(a) Đánh đổi vi phạm điểm số – thời gian hoàn thành")
    ax.legend(loc="lower left", fontsize=8)

    # Panel (b): Độ phủ điểm số thực nghiệm vs 1 - alpha và tỉ lệ hoàn thành lượt
    ax2 = axes[1]
    nom = [1.0 - a for a in sorted(alpha_df["alpha"].unique())]
    ax2.plot(nom, nom, "k--", lw=1.2, label="Đường chéo lý tưởng ($\\text{độ phủ} = 1-\\alpha$)")
    for m in methods:
        st = STYLE_MAP[m]
        sub = alpha_df[alpha_df["method"] == m].sort_values("alpha", ascending=False)
        x_nom = 1.0 - sub["alpha"].to_numpy()
        y_cov = sub["coverage_score"].to_numpy()
        # KTC 95% Clopper-Pearson xấp xỉ từ n_thinned
        lo_arr, hi_arr = [], []
        for yv, nt in zip(y_cov, sub["n_thinned"].to_numpy()):
            lo_v, hi_v = clopper_pearson(int(round(yv * nt)), int(nt))
            lo_arr.append(max(0.0, yv - lo_v))
            hi_arr.append(max(0.0, hi_v - yv))
        ax2.errorbar(x_nom, y_cov, yerr=[lo_arr, hi_arr], color=st["color"], ls=st["ls"], marker=st["marker"],
                     lw=1.8, markersize=5.5, capsize=2.5, label=m)
    ax2.set_xlabel("Mức danh định $1 - \\alpha$")
    ax2.set_ylabel("Độ phủ điểm số thực nghiệm $\\mathbb{P}(R \\leq q)$")
    ax2.set_title("(b) Độ chuẩn xác độ phủ điểm số theo $1-\\alpha$")
    ax2.legend(loc="lower right", fontsize=8)

    fig.suptitle("H4. Quét tham số rủi ro $\\alpha \\in \\{0.01, 0.02, 0.05, 0.10, 0.20\\}$ (Độ phủ $d \\geq d_s$ đạt $\\geq 99.9\\%$)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H4_safety_efficiency_alpha_sweep")


def plot_h5(h5_data: dict[str, Any], cal_old: dict[str, Any], cal_new: dict[str, Any], figs_dir: Path) -> None:
    """H5: So sánh chứng nhận có điều kiện (cũ) vs chứng nhận PAC (mới)."""
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.3))

    # Panel (a): Tỉ lệ chứng nhận sai theo độ phủ thật p_true < 0.90
    ax = axes[0]
    fcr = h5_data["false_cert_curve"]
    ps = [r["p_true"] for r in fcr]
    c1 = [100.0 * r["pass_cond_1try"] for r in fcr]
    c3 = [100.0 * r["pass_cond_3tries"] for r in fcr]
    p1 = [100.0 * r["pass_pac_1try"] for r in fcr]
    p3 = [100.0 * r["pass_pac_3tries"] for r in fcr]

    ax.plot(ps, c1, "s--", color="#d62728", lw=1.6, label="Có điều kiện (1 lần thử)")
    ax.plot(ps, c3, "o-", color="#b2182b", lw=2.0, label="Có điều kiện (tối đa 3 lần thử)")
    ax.plot(ps, p1, "^--", color="#2ca02c", lw=1.6, label="PAC $\\delta=0.05/3$ (1 lần thử)")
    ax.plot(ps, p3, "D-", color="#1b7837", lw=2.0, label="PAC Bonferroni $\\delta=0.05$ (3 lần thử)")
    ax.axhline(5.0, color="#111111", ls=":", lw=1.3, label="Ngưỡng kiểm soát rủi ro chứng nhận $\\delta = 5\\%$")
    ax.axvline(0.90, color="#555555", ls="--", lw=1.0)
    ax.set_xlabel("Độ phủ thật của chính sách ứng viên $p_{\\mathrm{true}}$")
    ax.set_ylabel("Xác suất chấp nhận chính sách (%)")
    ax.set_title(f"(a) Tỉ lệ chứng nhận sai ($n={h5_data['n_cert']}$, $k_\\mathrm{{cond}}={h5_data['k_cond']}$, $k_\\mathrm{{PAC}}={h5_data['k_pac']}$)")
    ax.legend(loc="upper left", fontsize=7.5)

    # Panel (b): Phân phối độ phủ thật của chính sách sau khi qua bước chứng nhận
    ax2 = axes[1]
    bins = np.linspace(0.83, 0.99, 25)
    ax2.hist(h5_data["cert_cov_cond"], bins=bins, density=True, alpha=0.50, color="#d62728", edgecolor="#800",
             label=f"Có điều kiện (P(<0.90) = {100*h5_data['dist_cond_below90']:.1f}%)")
    ax2.hist(h5_data["cert_cov_pac"], bins=bins, density=True, alpha=0.55, color="#2ca02c", edgecolor="#060",
             label=f"PAC (P(<0.90) = {100*h5_data['dist_pac_below90']:.1f}%)")
    ax2.axvline(0.90, color="#111111", ls="--", lw=1.5, label="Mục tiêu $1 - \\alpha = 0.90$")
    ax2.set_xlabel("Độ phủ thật của chính sách được chứng nhận")
    ax2.set_ylabel("Mật độ xác suất")
    ax2.set_title("(b) Phân phối độ phủ hậu chứng nhận (3000 kịch bản)")
    ax2.set_ylim(0, 31)
    ax2.legend(loc="upper left", fontsize=7.8)

    fig.suptitle("H5. Chứng nhận chính sách: Có điều kiện (Cũ) vs PAC Bonferroni (Mới)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H5_cert_conditional_vs_PAC")


def plot_h6(sum_new: dict[str, Any], cal_new: dict[str, Any], figs_dir: Path) -> None:
    """H6: Hiệu quả của ĐX-2 theo nhóm định vị (fix, float, loss)."""
    methods = ["B1", "ĐX-1", "ĐX-2", "ĐX-3"]
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.4))
    x = np.arange(len(GROUPS))
    w = 0.19

    # Panel (a): Độ phủ điểm số theo nhóm định vị
    ax = axes[0]
    ax.axhline(0.90, color="#111111", ls="--", lw=1.2, label="Mức danh định $0.90$")
    for idx, m in enumerate(methods):
        st = STYLE_MAP[m]
        ys, elo, ehi = [], [], []
        for g in GROUPS:
            rec = sum_new["by_method_group"][m][g]
            y = rec["coverage_score"]
            lo, hi = rec["coverage_score_ci95"]
            ys.append(y)
            elo.append(max(0.0, y - lo))
            ehi.append(max(0.0, hi - y))
        bars = ax.bar(x + (idx - 1.5)*w, ys, width=w, yerr=[elo, ehi], capsize=2.5,
                      color=st["color"], edgecolor="#222222", alpha=0.88, label=m)
        for b, yv, hi_e in zip(bars, ys, ehi):
            ax.text(b.get_x() + b.get_width()/2, yv + hi_e + 0.012, f"{yv:.2f}", ha="center", va="bottom", fontsize=6.8, rotation=90)
    ns_g = [sum_new["by_method_group"]["ĐX-2"][g]["n_thinned"] for g in GROUPS]
    ax.set_xticks(x)
    ax.set_xticklabels([f"{g}\n($n={n}$)" for g, n in zip(GROUPS, ns_g)])
    ax.set_ylabel("Độ phủ điểm số $\\mathbb{P}(R \\leq q)$ (KTC 95%)")
    ax.set_title("(a) Độ phủ điểm số theo nhóm định vị")
    ax.set_ylim(0.50, 1.13)
    ax.legend(loc="lower left", ncol=2, fontsize=8)

    # Panel (b): Biên an toàn 3 s (m) theo nhóm
    ax2 = axes[1]
    for idx, m in enumerate(["B1", "ĐX-1", "ĐX-2"]):
        st = STYLE_MAP[m]
        ms = [sum_new["by_method_group"][m][g]["m_3s_mean"] for g in GROUPS]
        bars = ax2.bar(x + (idx - 1.0)*0.24, ms, width=0.24, color=st["color"], edgecolor="#222222", alpha=0.88, label=m)
        for b, mv in zip(bars, ms):
            ax2.text(b.get_x() + b.get_width()/2, mv + 0.3, f"{mv:.1f}", ha="center", va="bottom", fontsize=7.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(GROUPS)
    ax2.set_ylabel("Biên an toàn tại $\\tau = 3\\text{ s}$ (m)")
    ax2.set_title("(b) Biên thích ứng theo chất lượng định vị")
    ax2.set_ylim(0, max(sum_new["by_method_group"]["ĐX-2"]["loss"]["m_3s_mean"] * 1.22, 12.0))
    ax2.legend(loc="upper left", fontsize=8)

    fig.suptitle("H6. Hiệu chỉnh theo nhóm định vị ĐX-2 so với ngưỡng chung ĐX-1 và B1", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H6_DX2_by_localization_group")


def run_analysis(logs_old_dir: Path, logs_new_dir: Path, figs_dir: Path) -> dict[str, Any]:
    """Chạy toàn bộ phân tích thống kê và sinh 6 hình H1–H6."""
    figs_dir.mkdir(parents=True, exist_ok=True)

    with open(logs_old_dir / "summary.json", encoding="utf-8") as f:
        sum_old = json.load(f)
    with open(logs_new_dir / "summary.json", encoding="utf-8") as f:
        sum_new = json.load(f)
    with open(logs_old_dir / "calibration.json", encoding="utf-8") as f:
        cal_old = json.load(f)
    with open(logs_new_dir / "calibration.json", encoding="utf-8") as f:
        cal_new = json.load(f)

    ep_old = pd.read_csv(logs_old_dir / "episodes.csv")
    ep_new = pd.read_csv(logs_new_dir / "episodes.csv")
    cyc_old = pd.read_csv(logs_old_dir / "cycles.csv")
    cyc_new = pd.read_csv(logs_new_dir / "cycles.csv")
    alpha_df = pd.read_csv(logs_new_dir / "alpha_sweep.csv")

    stat_tests = compute_statistical_tests(ep_old, ep_new, cyc_new, cyc_old)
    h2_data = compute_autocorr_and_inf_effects(cyc_old, cyc_new)
    h5_data = compute_certification_comparison(cyc_new)

    plot_h1(sum_old, sum_new, figs_dir)
    plot_h2(h2_data, sum_old, sum_new, figs_dir)
    plot_h3(sum_new, cal_new, figs_dir)
    plot_h4(alpha_df, figs_dir)
    plot_h5(h5_data, cal_old, cal_new, figs_dir)
    plot_h6(sum_new, cal_new, figs_dir)

    # Thống kê A_c vs A_h theo kịch bản (B0 mới) và hiệu ứng lập lại kế hoạch lên sai số xe (D0 B0)
    b0_new_act = cyc_new[(cyc_new["method"] == "B0") & (cyc_new["thinned"] == 1) & (cyc_new["has_agents"] == 1)]
    ac_vs_ah = {}
    for scn in ["S1", "S2", "S3", "S4"]:
        sub = b0_new_act[b0_new_act["scn"] == scn]
        ac_vs_ah[scn] = {
            "n": int(len(sub)),
            "Ac_mean": float(sub["A_c_max"].mean()),
            "Ah_mean": float(sub["A_h_max"].mean()),
            "Ac_q90": float(sub["A_c_max"].quantile(0.90)),
            "Ah_q90": float(sub["A_h_max"].quantile(0.90)),
        }

    b0_d0_old = cyc_old[(cyc_old["method"] == "B0") & (cyc_old["cond"] == "D0")]
    e_emp = b0_d0_old[b0_d0_old["has_agents"] == 0]["E_max_norm"]
    e_act = b0_d0_old[b0_d0_old["has_agents"] == 1]["E_max_norm"]
    replan_split = {
        "empty_no_replan": {
            "n": int(len(e_emp)),
            "E_norm_mean": float(e_emp.mean()),
            "E_norm_median": float(e_emp.median()),
            "E_norm_p95": float(e_emp.quantile(0.95)),
        },
        "active_with_replan": {
            "n": int(len(e_act)),
            "E_norm_mean": float(e_act.mean()),
            "E_norm_median": float(e_act.median()),
            "E_norm_p95": float(e_act.quantile(0.95)),
        },
    }

    analysis_out = {
        "stat_tests": stat_tests,
        "h2_inf_and_autocorr": h2_data,
        "h5_certification": {k: v for k, v in h5_data.items() if k not in ("cert_cov_cond", "cert_cov_pac")},
        "ac_vs_ah_by_scn": ac_vs_ah,
        "replanning_e_split": replan_split,
    }
    with open(figs_dir / "analysis_results.json", "w", encoding="utf-8") as f:
        json.dump(analysis_out, f, ensure_ascii=False, indent=2)

    return analysis_out
