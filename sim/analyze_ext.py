"""Phân tích thống kê mở rộng (McNemar, Wilcoxon, Holm theo từng tập) và vẽ hình H7–H11."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sim.analyze import STYLE_MAP, _holm_adjust, _mcnemar_exact, _save_fig, _wilcoxon_paired
from sim.core import ALL_CONDITIONS, ALL_SCENARIOS
from sim.run_ext import EXT_SPLITS


def compute_ext_stat_tests(ep_df: pd.DataFrame, cyc_df: pd.DataFrame) -> dict[str, Any]:
    """Kiểm định McNemar và Wilcoxon ghép cặp có hiệu chỉnh Holm cho từng tập IN/OOD-S/OOD-D/OOD-SD/RECAL."""
    sub = cyc_df[(cyc_df["thinned"] == 1) & (cyc_df["has_agents"] == 1)].copy()
    sub["viol_safe"] = (sub["safe"] == 0).astype(int)
    sub["viol_score"] = (sub["covered"] == 0).astype(int)
    ep_v = sub.groupby(["split", "method", "cond", "scn", "seed"], as_index=False)[["viol_safe", "viol_score"]].max()
    merged = ep_df.merge(ep_v, on=["split", "method", "cond", "scn", "seed"], how="left")
    merged["viol_safe"] = merged["viol_safe"].fillna(0).astype(int)
    merged["viol_score"] = merged["viol_score"].fillna(0).astype(int)
    merged = merged.sort_values(["split", "method", "cond", "scn", "seed"]).reset_index(drop=True)

    baselines = ["B0", "B1", "B2", "B3", "B3′", "B4", "B5", "B6"]
    out: dict[str, Any] = {}
    for sp in EXT_SPLITS:
        sp_df = merged[merged["split"] == sp]
        sp_out: dict[str, list[dict[str, Any]]] = {}
        for prop in ("ĐX-1", "ĐX-2", "ĐX-3"):
            p_df = sp_df[sp_df["method"] == prop].reset_index(drop=True)
            rows = []
            for base in baselines:
                b_df = sp_df[sp_df["method"] == base].reset_index(drop=True)
                assert (p_df[["cond", "scn", "seed"]].values == b_df[["cond", "scn", "seed"]].values).all()
                rows.append({
                    "baseline": base,
                    "mcnemar_viol": _mcnemar_exact(p_df["viol_safe"].to_numpy(), b_df["viol_safe"].to_numpy()),
                    "mcnemar_score_viol": _mcnemar_exact(p_df["viol_score"].to_numpy(), b_df["viol_score"].to_numpy()),
                    "mcnemar_coll": _mcnemar_exact(p_df["collided"].to_numpy(), b_df["collided"].to_numpy()),
                    "wilcoxon_tend": _wilcoxon_paired(p_df["t_end"].to_numpy(), b_df["t_end"].to_numpy()),
                    "wilcoxon_dmin": _wilcoxon_paired(p_df["d_min"].to_numpy(), b_df["d_min"].to_numpy()),
                    "wilcoxon_jerk": _wilcoxon_paired(p_df["jerk_rms"].to_numpy(), b_df["jerk_rms"].to_numpy()),
                })
            for key in ("mcnemar_viol", "mcnemar_score_viol", "mcnemar_coll", "wilcoxon_tend", "wilcoxon_dmin", "wilcoxon_jerk"):
                adj = _holm_adjust([r[key]["p_raw"] for r in rows])
                for r, pa in zip(rows, adj):
                    r[key]["p_holm"] = pa
            sp_out[prop] = rows
        out[sp] = sp_out
    return out


def plot_h7(sum_ext: dict[str, Any], figs_dir: Path) -> None:
    """H7: Độ phủ điểm số và độ phủ vật lý theo tập IN / OOD-S / OOD-D / OOD-SD / RECAL."""
    methods_plot = ["B1", "B3′", "B5", "B6", "ĐX-1", "ĐX-2", "ĐX-3"]
    fig, axes = plt.subplots(1, 2, figsize=(12.2, 4.6), sharey=False)
    x = np.arange(len(EXT_SPLITS))
    offsets = np.linspace(-0.24, 0.24, len(methods_plot))

    for ax, metric_key, ci_key, title, ylabel, ylim in [
        (axes[0], "coverage_score", "coverage_score_ci95", "(a) Độ phủ điểm số $\\mathbb{P}(R \\leq q)$", "Độ phủ điểm số (KTC 95%)", (0.15, 1.05)),
        (axes[1], "coverage_safe", "coverage_safe_ci95", "(b) Độ phủ vật lý $d \\geq d_s$", "Độ phủ vật lý (KTC 95%)", (0.55, 1.03)),
    ]:
        ax.axhline(0.90, color="#111111", ls="--", lw=1.2, label="Mức danh định $1-\\alpha=0.90$")
        for idx, m in enumerate(methods_plot):
            st = STYLE_MAP[m]
            ys, elo, ehi = [], [], []
            for sp in EXT_SPLITS:
                rec = sum_ext["by_split_method"][sp][m]
                y = float(rec[metric_key])
                lo, hi = rec[ci_key]
                ys.append(y)
                elo.append(max(0.0, y - lo))
                ehi.append(max(0.0, hi - y))
            ax.errorbar(
                x + offsets[idx], ys, yerr=[elo, ehi], label=m,
                color=st["color"], ls=st["ls"], marker=st["marker"],
                markersize=5.2, capsize=2.3, linewidth=1.6,
            )
        ax.set_xticks(x)
        ax.set_xticklabels(EXT_SPLITS)
        ax.set_xlabel("Tập phân phối")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.set_ylim(*ylim)

    axes[0].legend(loc="lower left", ncol=2, fontsize=7.5)
    fig.suptitle("H7. Độ bền khi dịch chuyển phân phối: IN → OOD-S / OOD-D / OOD-SD → RECAL", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H7_coverage_by_split")


def plot_h8(alpha_ext_df: pd.DataFrame, e1_iso: dict[str, Any], figs_dir: Path) -> None:
    """H8: Đường đánh đổi ở cùng độ phủ và KTC bootstrap (E1)."""
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.4))
    methods = ["B1", "B3′", "ĐX-1", "ĐX-2"]

    for ax, sp_name, sub_name, title in [
        (axes[0], "IN", "all", "(a) Tập IN: đánh đổi ở cùng độ phủ"),
        (axes[1], "OOD-SD", "all", "(b) Tập OOD-SD: đánh đổi ở cùng độ phủ"),
    ]:
        sub = alpha_ext_df[(alpha_ext_df["split"] == sp_name) & (alpha_ext_df["subset"] == sub_name)]
        for m in methods:
            st = STYLE_MAP[m]
            ms = sub[sub["method"] == m].sort_values("alpha")
            ax.plot(ms["coverage_score"], ms["t_end_mean"], color=st["color"], ls=st["ls"], marker=st["marker"], lw=1.7, markersize=5, label=m)
        ax.axvline(0.90, color="#222222", ls="--", lw=1.0, label="0.90 / 0.95")
        ax.axvline(0.95, color="#555555", ls=":", lw=1.0)
        ax.set_xlabel("Độ phủ điểm số thực nghiệm $\\mathbb{P}(R \\leq q)$")
        ax.set_ylabel("Thời gian hoàn thành TB $t_{\\mathrm{end}}$ (s)")
        ax.set_title(title)
        ax.legend(loc="upper left", fontsize=7.5)

    # Panel (c): Hiệu số Delta m_3s (m) giữa ĐX và B1/B3′ ở cùng độ phủ 0.90 & 0.95 kèm KTC bootstrap 95%
    ax3 = axes[2]
    comps = [
        c for c in e1_iso["iso_comparisons"]
        if c["subset"] == "all" and c["proposed"] in ("ĐX-1", "ĐX-2") and c["baseline"] in ("B1", "B3′") and abs(c["target_cov"] - 0.90) < 1e-6
    ]
    labels = [f"{c['split']}: {c['proposed']}−{c['baseline']}" for c in comps]
    deltas = [c["delta_m_3s"] for c in comps]
    elo = [max(0.0, c["delta_m_3s"] - c["delta_m_3s_ci95"][0]) for c in comps]
    ehi = [max(0.0, c["delta_m_3s_ci95"][1] - c["delta_m_3s"]) for c in comps]
    y_pos = np.arange(len(comps))
    cols = ["#1f77b4" if c["m_3s_sig_tighter"] else "#7f7f7f" for c in comps]
    ax3.axvline(0.0, color="#111111", ls="--", lw=1.2)
    ax3.errorbar(deltas, y_pos, xerr=[elo, ehi], fmt="o", color="#0b3c5d", ecolor="#1f77b4", elinewidth=1.8, capsize=3.5)
    for yv, dv, col in zip(y_pos, deltas, cols):
        ax3.scatter([dv], [yv], color=col, s=45, zorder=5)
    ax3.set_yticks(y_pos)
    ax3.set_yticklabels(labels, fontsize=7.5)
    ax3.set_xlabel("$\\Delta m_{3\\mathrm{s}}$ tại độ phủ $0.90$ (m, $<0$ là hẹp hơn)")
    ax3.set_title("(c) KTC bootstrap 95% ở cùng độ phủ 0.90")
    ax3.invert_yaxis()

    fig.suptitle("H8. So sánh hiệu quả và độ rộng biên ở cùng độ phủ thực nghiệm (E1)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H8_iso_coverage_tradeoff")


def plot_h9(aci_df: pd.DataFrame, figs_dir: Path) -> None:
    """H9: Vết alpha_t của ACI theo 4 biến thể 2x2 trên IN và OOD-D (E2)."""
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 7.2))
    dx3 = aci_df[aci_df["method"] == "ĐX-3"]

    var_styles = {
        "active_only_g0.02":  {"color": "#1f77b4", "ls": "-",  "label": "Chỉ có tác nhân, $\\gamma=0.02$"},
        "all_cycles_g0.02":   {"color": "#d62728", "ls": "--", "label": "Mọi chu kỳ (cả rỗng), $\\gamma=0.02$"},
        "active_only_g0.005": {"color": "#2ca02c", "ls": "-.", "label": "Chỉ có tác nhân, $\\gamma=0.005$"},
        "all_cycles_g0.005":  {"color": "#ff7f0e", "ls": ":",  "label": "Mọi chu kỳ (cả rỗng), $\\gamma=0.005$"},
    }

    for col_idx, (sp_name, cond_pick, lbl_c) in enumerate([
        ("IN", "D1", "IN (D1: RTK thả nổi)"),
        ("OOD-D", "D7", "OOD-D (D7: Mất GNSS dài)"),
    ]):
        sub = dx3[(dx3["split"] == sp_name) & (dx3["cond"] == cond_pick)]
        ax_top = axes[0, col_idx]
        ax_bot = axes[1, col_idx]
        ax_top.axhline(0.10, color="#111111", ls="--", lw=1.0, label="Mục tiêu $\\alpha=0.10$")
        ax_bot.axhline(0.90, color="#111111", ls="--", lw=1.0, label="Mục tiêu $1-\\alpha=0.90$")

        for v_name, st in var_styles.items():
            vsub = sub[sub["variant"] == v_name].reset_index(drop=True)
            steps = np.arange(1, len(vsub) + 1)
            ax_top.plot(steps, vsub["alpha_t"], color=st["color"], ls=st["ls"], lw=1.5, label=st["label"])
            ax_bot.plot(steps, vsub["rolling_cov_200"], color=st["color"], ls=st["ls"], lw=1.5, label=st["label"])

        ax_top.set_title(f"Vết $\\alpha_t$ — {lbl_c}")
        ax_top.set_ylabel("$\\alpha_t$")
        ax_bot.set_title(f"Độ phủ cửa sổ trượt 200 bước — {lbl_c}")
        ax_bot.set_xlabel("Số bước chu kỳ tích lũy")
        ax_bot.set_ylabel("Độ phủ trượt 200")
        ax_bot.set_ylim(0.55, 1.03)
        if col_idx == 0:
            ax_top.legend(loc="lower left", fontsize=7.5)

    fig.suptitle("H9. Ablation 2×2 ACI (ĐX-3): ảnh hưởng chu kỳ trống và bước học $\\gamma$ (E2)", y=1.01, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H9_aci_alpha_trace")


def plot_h10(pac_df: pd.DataFrame, cal_d2: dict[str, Any], figs_dir: Path) -> None:
    """H10: Lực kiểm định PAC, cỡ mẫu n_cert và kết quả khối chuyên biệt D2 (E3, E4)."""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    mc = pac_df[pac_df["source"] == "mc_binom"]
    real_pt = pac_df[pac_df["source"] != "mc_binom"]

    # Panel (a): Đường cong lực kiểm định tại M=1, delta=0.05 theo n_cert
    ax = axes[0]
    sub_a = mc[(mc["M"] == 1) & (np.abs(mc["delta"] - 0.05) < 1e-6)]
    cols_n = {100: "#d62728", 200: "#ff7f0e", 400: "#1f77b4", 800: "#2ca02c"}
    for n_val in (100, 200, 400, 800):
        sn = sub_a[sub_a["n_cert"] == n_val].sort_values("p_true")
        ax.plot(sn["p_true"], 100.0 * sn["accept_prob"], "o-", color=cols_n[n_val], lw=1.7, label=f"$n={n_val}$ ($k={int(sn['k_pac'].iloc[0])}$)")
    if not real_pt.empty:
        rp = real_pt.iloc[0]
        ax.scatter([rp["p_true"]], [100.0 * rp["accept_prob"]], color="#0b3c5d", marker="*", s=160, zorder=6,
                   label=f"Chạy thật ($n={int(rp['n_cert'])}$, $M=1$)")
    ax.axhline(5.0, color="#111111", ls=":", lw=1.2, label="Ngưỡng $\\delta = 5\\%$")
    ax.axvline(0.90, color="#444444", ls="--", lw=1.1)
    ax.set_xlabel("Độ phủ thật của chính sách ứng viên $p_{\\mathrm{true}}$")
    ax.set_ylabel("Xác suất chứng nhận (%)")
    ax.set_title("(a) Lực kiểm định PAC ($M=1, \\delta=0.05$)")
    ax.legend(loc="upper left", fontsize=7.5)

    # Panel (b): Dư độ phủ yêu cầu (k_PAC/n - 0.90) theo n_cert, M, delta
    ax2 = axes[1]
    uniq = mc[["n_cert", "M", "delta", "excess_cov_req"]].drop_duplicates()
    for (m_val, d_val), grp in uniq.groupby(["M", "delta"]):
        grp = grp.sort_values("n_cert")
        ls = "-" if m_val == 1 else "--"
        mk = "o" if m_val == 1 else "s"
        ax2.plot(grp["n_cert"], 100.0 * grp["excess_cov_req"], linestyle=ls, marker=mk, lw=1.5,
                 label=f"$M={m_val}, \\delta={d_val:.2f}$")
    ax2.axhline(2.0, color="#d62728", ls="--", lw=1.3, label="Ngưỡng dư độ phủ $\\leq 2\\%$")
    ax2.set_xlabel("Cỡ mẫu chứng nhận $n_{\\mathrm{cert}}$ (chu kỳ không chồng)")
    ax2.set_ylabel("Dư độ phủ yêu cầu $k_{\\mathrm{PAC}}/n - 0.90$ (%)")
    ax2.set_title(f"(b) Yêu cầu dư độ phủ (E4 D2: $n_{{\\mathrm{{loss}}}}={cal_d2['cert_tries'][-1]['n_loss']}$)")
    ax2.legend(loc="upper right", fontsize=7.2, ncol=2)

    fig.suptitle("H10. Lực kiểm định PAC, cỡ mẫu gợi ý cho CARLA và chứng nhận D2 (E3, E4)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H10_pac_power_and_sample_size")


def plot_h11(e6_df: pd.DataFrame, figs_dir: Path) -> None:
    """H11: Phân tách E_track / sigma và E_replan / sigma theo điều kiện D và kịch bản S (E6)."""
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.5))
    sub_dx1 = e6_df[e6_df["method"] == "ĐX-1"]

    for ax, grp_type, order_list, title, xlabel in [
        (axes[0], "cond", list(ALL_CONDITIONS), "(a) Tách sai số theo điều kiện suy giảm D0–D10", "Điều kiện suy giảm"),
        (axes[1], "scn", list(ALL_SCENARIOS), "(b) Tách sai số theo kịch bản S1–S10", "Kịch bản"),
    ]:
        g_df = sub_dx1[sub_dx1["group_type"] == grp_type].set_index("group_val").reindex(order_list)
        x = np.arange(len(order_list))
        et_m = g_df["e_track_mean"].to_numpy()
        er_m = g_df["e_replan_mean"].to_numpy()
        etot_p95 = g_df["e_total_p95"].to_numpy()

        ax.bar(x, et_m, width=0.56, color="#2ca02c", alpha=0.85, label="TB $E_{\\mathrm{track}}/\\sigma_\\tau$ (bám mở vòng)")
        ax.bar(x, er_m, width=0.56, bottom=et_m, color="#ff7f0e", alpha=0.85, label="TB $E_{\\mathrm{replan}}/\\sigma_\\tau$ (lập lại kế hoạch)")
        ax.plot(x, etot_p95, "o--", color="#0b3c5d", lw=1.4, markersize=4.5, label="P95 tổng $E/\\sigma_\\tau$")
        ax.set_xticks(x)
        ax.set_xticklabels(order_list, rotation=0)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Sai số chuẩn hóa ($/\\sigma_\\tau$)")
        ax.set_title(title)
        ax.legend(loc="upper left", fontsize=7.5)

    fig.suptitle("H11. Phân tách sai số bám thuần $E_{\\mathrm{track}}$ và độ lệch lập lại kế hoạch $E_{\\mathrm{replan}}$ (ĐX-1, E6)", y=1.02, fontweight="bold")
    fig.tight_layout()
    _save_fig(fig, figs_dir, "H11_etrack_ereplan_split")


def run_analysis_ext(root: Path) -> dict[str, Any]:
    """Chạy toàn bộ phân tích thống kê mở rộng và vẽ 5 hình H7–H11."""
    logs_ext = root / "logs" / "ext"
    figs_dir = root / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)

    with open(logs_ext / "summary.json", encoding="utf-8") as f:
        sum_ext = json.load(f)
    with open(logs_ext / "calibration_d2.json", encoding="utf-8") as f:
        cal_d2 = json.load(f)
    with open(logs_ext / "e1_iso_coverage.json", encoding="utf-8") as f:
        e1_iso = json.load(f)
    with open(logs_ext / "e9_in30_summary.json", encoding="utf-8") as f:
        e9_sum = json.load(f)

    ep_df = pd.read_csv(logs_ext / "episodes.csv")
    cyc_df = pd.read_csv(logs_ext / "cycles.csv")
    alpha_ext_df = pd.read_csv(logs_ext / "alpha_sweep_ext.csv")
    aci_df = pd.read_csv(logs_ext / "aci_trace.csv")
    pac_df = pd.read_csv(logs_ext / "pac_power.csv")
    e6_df = pd.read_csv(logs_ext / "e6_tracking_split.csv")
    thin_df = pd.read_csv(logs_ext / "thinning_ext.csv")
    e7_df = pd.read_csv(logs_ext / "e7_sensitivity.csv")
    sig_scn_df = pd.read_csv(logs_ext / "sigma_by_scn.csv")

    stat_tests = compute_ext_stat_tests(ep_df, cyc_df)

    plot_h7(sum_ext, figs_dir)
    plot_h8(alpha_ext_df, e1_iso, figs_dir)
    plot_h9(aci_df, figs_dir)
    plot_h10(pac_df, cal_d2, figs_dir)
    plot_h11(e6_df, figs_dir)

    # Tóm tắt định lượng E2 (2x2)
    aci_summary: list[dict[str, Any]] = []
    for (m, sp, var), grp in aci_df.groupby(["method", "split", "variant"]):
        act = grp[grp["has_agents"] == 1]
        aci_summary.append({
            "method": m,
            "split": sp,
            "variant": var,
            "n_steps": int(len(grp)),
            "n_active_steps": int(len(act)),
            "alpha_t_start": float(grp["alpha_t"].iloc[0]),
            "alpha_t_end": float(grp["alpha_t"].iloc[-1]),
            "alpha_t_mean": float(grp["alpha_t"].mean()),
            "active_cov": float(1.0 - act["err"].mean()) if len(act) > 0 else 0.0,
            "q_mean_active": float(act["q"].mean()) if len(act) > 0 else 0.0,
        })

    analysis_ext = {
        "stat_tests_by_split": stat_tests,
        "e1_iso_coverage": e1_iso,
        "e2_aci_ablation_summary": aci_summary,
        "e4_d2_summary": cal_d2,
        "e5_thinning_table": thin_df.to_dict("records"),
        "e7_sensitivity_table": e7_df.to_dict("records"),
        "e8_sigma_by_scn_table": sig_scn_df.to_dict("records"),
        "e9_in30_summary": e9_sum,
    }
    with open(figs_dir / "analysis_ext.json", "w", encoding="utf-8") as f:
        json.dump(analysis_ext, f, ensure_ascii=False, indent=2)

    return analysis_ext
