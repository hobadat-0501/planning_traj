"""Phân tích, vẽ hình và sinh báo cáo CARLA so với mô phỏng 2D (PLAN §9, T21 / G19)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from carla_sim.params import TABLE_4_2_PARAMS


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def plot_carla_vs_2d(
    sum_2d: dict[str, Any] | None,
    sum_m1: dict[str, Any] | None,
    sum_m2: dict[str, Any] | None,
    sum_m3: dict[str, Any] | None,
    figs_dir: Path,
) -> list[Path]:
    """Vẽ hình H12 (độ phủ CARLA vs 2D) và H13 (độ rộng biên m_3s giữa M1, M2, M3)."""
    figs_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    sources: list[tuple[str, dict[str, Any]]] = []
    if sum_2d is not None:
        sources.append(("2D (Phương án B)", sum_2d))
    if sum_m1 is not None:
        sources.append(("CARLA M1 (CV)", sum_m1))
    if sum_m2 is not None:
        sources.append(("CARLA M2 (Dự báo cải tiến)", sum_m2))
    if sum_m3 is not None:
        sources.append(("CARLA M3 (LiDAR)", sum_m3))

    if not sources:
        return created

    # Tìm tập phương pháp chung (ưu tiên các phương pháp chính)
    preferred = ["B0", "B1", "B3′", "ĐX-1", "ĐX-2", "ĐX-3"]
    avail = set.intersection(*(set(s["by_method"].keys()) for _, s in sources))
    methods = [m for m in preferred if m in avail] or sorted(avail)
    if not methods:
        return created

    x = np.arange(len(methods))
    width = 0.8 / max(1, len(sources))

    # H12: Độ phủ điểm số so sánh 2D vs CARLA
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    for i, (label, sdata) in enumerate(sources):
        vals = [sdata["by_method"][m]["coverage_score"] for m in methods]
        offset = (i - 0.5 * (len(sources) - 1)) * width
        ax.bar(x + offset, vals, width=width * 0.92, label=label)
    ax.axhline(0.90, color="black", linestyle="--", linewidth=1.0, label="Mục tiêu 1 − α = 0,90")
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Độ phủ điểm số (R ≤ q)")
    ax.set_title("H12. So sánh độ phủ giữa mô phỏng 2D và CARLA (M1/M2/M3)")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    for ext in ("png", "pdf"):
        p = figs_dir / f"H12_carla_vs_2d_coverage.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        created.append(p)
    plt.close(fig)

    # H13: Độ rộng biên m_3s trung bình
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    for i, (label, sdata) in enumerate(sources):
        vals = [sdata["by_method"][m]["m_3s_mean"] for m in methods]
        offset = (i - 0.5 * (len(sources) - 1)) * width
        ax.bar(x + offset, vals, width=width * 0.92, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylabel("Độ rộng biên tại τ = 3 s (m)")
    ax.set_title("H13. Ảnh hưởng của động lực học CARLA và bộ dự báo lên độ rộng biên m₃ₛ")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    for ext in ("png", "pdf"):
        p = figs_dir / f"H13_carla_m1_m2_margin.{ext}"
        fig.savefig(p, dpi=300, bbox_inches="tight")
        created.append(p)
    plt.close(fig)
    return created


def generate_carla_report(
    ws_dir: Path,
    *,
    logs_2d_dir: Path | None = None,
    logs_m1_dir: Path | None = None,
    logs_m2_dir: Path | None = None,
    logs_m3_dir: Path | None = None,
    out_md: Path | None = None,
    figs_dir: Path | None = None,
) -> Path:
    """Sinh báo cáo Markdown so sánh CARLA (M1/M2/M3) với mô phỏng 2D và đề xuất sửa bản thảo (T21)."""
    logs_2d_dir = logs_2d_dir or (ws_dir / "logs" / "B")
    logs_m1_dir = logs_m1_dir or (ws_dir / "logs" / "carla_m1")
    logs_m2_dir = logs_m2_dir or (ws_dir / "logs" / "carla_m2")
    logs_m3_dir = logs_m3_dir or (ws_dir / "logs" / "carla_m3")
    figs_dir = figs_dir or (ws_dir / "figs")
    out_md = out_md or (ws_dir / "report" / "BAO_CAO_CARLA.md")

    sum_2d = _load_json(logs_2d_dir / "summary.json")
    sum_m1 = _load_json(logs_m1_dir / "summary.json")
    sum_m2 = _load_json(logs_m2_dir / "summary.json")
    sum_m3 = _load_json(logs_m3_dir / "summary.json")
    cal_m1 = _load_json(logs_m1_dir / "calibration.json")
    cfg_m1 = _load_json(logs_m1_dir / "config.json")

    plot_carla_vs_2d(sum_2d, sum_m1, sum_m2, sum_m3, figs_dir)

    lines: list[str] = [
        "# BÁO CÁO KẾT QUẢ MÔ PHỎNG CARLA (M1 / M2 / M3) VÀ ĐỐI CHIẾU VỚI 2D",
        "",
        "## 1. Phạm vi và cấu hình chạy",
        "",
        "- Áp dụng **Phương án B** (loại chu kỳ trống, lấy thưa 3,0 s không chồng, Hausdorff $A_h$, PAC Bonferroni).",
    ]
    if cfg_m1:
        lines.append(f"- Backend M1: `{cfg_m1.get('backend', 'carla')}`, lưới dày: `{cfg_m1.get('dense_v_grid', False)}`, $d_s = {cfg_m1.get('d_s', 0.5):.2f}$ m.")
    if sum_m3 is None:
        lines.append(
            "- **Giới hạn nhận diện (không chạy M3):** Các tác nhân ở M1 và M2 được quan sát bằng ground truth "
            "của CARLA cộng nhiễu Gauss; các sai số bỏ sót, đổi nhãn và che khuất cảm biến thật chưa được đánh giá."
        )
    else:
        lines.append("- Đã chạy đủ cả ba mức M1 (CV), M2 (dự báo cải tiến) và M3 (detector/tracker LiDAR).")

    lines.extend([
        "",
        "## 2. So sánh kết quả 2D vs CARLA M1 / M2 / M3",
        "",
        "| Nguồn | Phương pháp | Độ phủ điểm số | KTC 95% | $m_{3\\text{s}}$ (m) | Dự phòng (%) | $t_{\\text{end}}$ (s) | Va chạm (%) | P95 tính (ms) |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|",
    ])

    for name, sdata in [("2D (B)", sum_2d), ("CARLA M1", sum_m1), ("CARLA M2", sum_m2), ("CARLA M3", sum_m3)]:
        if sdata is None:
            continue
        for m, st in sdata.get("by_method", {}).items():
            ci = st.get("coverage_score_ci95", [0.0, 1.0])
            lines.append(
                f"| {name} | {m} | {st['coverage_score']:.3f} | [{ci[0]:.3f}; {ci[1]:.3f}] | "
                f"{st['m_3s_mean']:.3f} | {st['fallback_pct']:.1f} | {st['t_end_mean']:.2f} | "
                f"{100.0 * st['collision_rate']:.1f} | {st['tcomp_p95_ms']:.2f} |"
            )

    # Kiểm tra độ phủ theo hạt giống & hoán đổi được (T19)
    if cal_m1 and "exchangeability" in cal_m1:
        lines.extend([
            "",
            "## 3. Kiểm tra độ phủ theo hạt giống và tính hoán đổi được (M1)",
            "",
            "| Phương pháp | Số hạt giống | Độ phủ TB theo hạt giống | Độ lệch chuẩn | Min–Max | Tự tương quan trễ 1 ($\\rho_1$) |",
            "|---|---:|---:|---:|---|---:|",
        ])
        for m, ex in cal_m1["exchangeability"].items():
            lines.append(
                f"| {m} | {ex['n_seeds']} | {ex['seed_cov_mean']:.3f} | {ex['seed_cov_std']:.3f} | "
                f"{ex['seed_cov_min']:.3f}–{ex['seed_cov_max']:.3f} | {ex['lag1_autocorr_R']:.3f} |"
            )

    # Đề xuất sửa bản thảo (§4.2 và §2.3) theo T21
    loc = TABLE_4_2_PARAMS["localization_error_model"]
    lines.extend([
        "",
        "## 4. Đề xuất sửa đổi bản thảo (§4.2 và §2.3)",
        "",
        "### 4.1. Bảng mô hình sai số định vị bổ sung vào Mục 4.2 (điền đầy đủ các ô `[X]`)",
        "",
        "| Trạng thái định vị | Nhãn $g$ | $\\sigma_{xy}$ (m) | $\\sigma_\\psi$ (rad) | $\\sigma_v$ (m/s) | Mô hình thời gian |",
        "|---|---|---:|---:|---:|---|",
        f"| RTK cố định | `fix` | {loc['fix']['sigma_xy_m']:.2f} | {loc['fix']['sigma_psi_rad']:.3f} | {loc['fix']['sigma_v_mps']:.2f} | {loc['fix']['model']} |",
        f"| RTK thả nổi | `float` | {loc['float']['sigma_xy_m']:.2f} | {loc['float']['sigma_psi_rad']:.3f} | {loc['float']['sigma_v_mps']:.2f} | {loc['float']['model']} |",
        f"| Mất GNSS | `loss` | RW {loc['loss']['pos_rw_m_sqrt_s']:.2f} m/$\\sqrt{{\\text{{s}}}}$ | bias {loc['loss']['yaw_bias_radps'][0]:.3f}–{loc['loss']['yaw_bias_radps'][1]:.3f} rad/s | — | {loc['loss']['model']} |",
        "",
        "### 4.2. Câu chữ gợi ý cho Mục 2.3 (tách sai số bám và sai số lập lại kế hoạch)",
        "",
        "> Trong vòng kín có lập kế hoạch lại ở 10 Hz, độ lệch tổng hợp $E_\\tau$ giữa quỹ đạo thực của xe và "
        "quỹ đạo kế hoạch tại thời điểm $t$ bao gồm hai thành phần: sai số bám thuần $E_{\\text{track},\\tau}$ "
        "(đo trên nhánh mở vòng bám cố định kế hoạch $t$) và độ lệch do lập lại kế hoạch $E_{\\text{replan},\\tau}$ "
        "khi có tác nhân mới hoặc điều chỉnh mục tiêu. Biên an toàn phù hợp gộp $R_t$ hấp thụ trực tiếp phần hụt "
        "khoảng cách $\\hat{d} - d$ do cả hai thành phần cùng sai số dự báo tác nhân mà không cần giả định độc lập.",
        "",
    ])

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines), encoding="utf-8")
    return out_md
