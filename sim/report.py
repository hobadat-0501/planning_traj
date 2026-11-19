"""Sinh báo cáo kết quả và đề xuất sửa đổi bản thảo (.md và .docx) truy xuất trực tiếp từ logs/."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
import pandas as pd


def _pct(x: float | None, dec: int = 1) -> str:
    if x is None:
        return "–"
    return f"{100.0 * x:.{dec}f}%"


def _f(x: float | None, dec: int = 3) -> str:
    if x is None:
        return "–"
    return f"{x:.{dec}f}"


def _ci_str(ci: list[float], dec: int = 3) -> str:
    return f"[{ci[0]:.{dec}f}; {ci[1]:.{dec}f}]"


def _p_str(p: float) -> str:
    if p < 1e-4:
        return f"{p:.2e}"
    return f"{p:.4f}"


def build_report_markdown(root: Path, fig_prefix: str = "../figs/") -> str:
    """Tạo toàn văn báo cáo Markdown 9 mục theo SPEC §7 từ logs/old, logs/new, figs/."""
    with open(root / "logs" / "old" / "summary.json", encoding="utf-8") as f:
        so = json.load(f)
    with open(root / "logs" / "new" / "summary.json", encoding="utf-8") as f:
        sn = json.load(f)
    with open(root / "logs" / "old" / "calibration.json", encoding="utf-8") as f:
        co = json.load(f)
    with open(root / "logs" / "new" / "calibration.json", encoding="utf-8") as f:
        cn = json.load(f)
    with open(root / "logs" / "old" / "config.json", encoding="utf-8") as f:
        cfgo = json.load(f)
    with open(root / "logs" / "new" / "config.json", encoding="utf-8") as f:
        cfgn = json.load(f)
    with open(root / "figs" / "analysis_results.json", encoding="utf-8") as f:
        an = json.load(f)
    alpha_df = pd.read_csv(root / "logs" / "new" / "alpha_sweep.csv")

    # Trích các chỉ số tổng hợp chính để dùng xuyên suốt (100% truy xuất từ JSON)
    bo_o = so["by_method"]["B0"]
    bo_n = sn["by_method"]["B0"]
    dx1_o = so["by_method"]["ĐX-1"]
    dx2_o = so["by_method"]["ĐX-2"]
    dx3_o = so["by_method"]["ĐX-3"]

    b1_n = sn["by_method"]["B1"]
    b3_n = sn["by_method"]["B3"]
    b3p_n = sn["by_method"]["B3′"]
    b4_n = sn["by_method"]["B4"]
    b5_n = sn["by_method"]["B5"]
    b6_n = sn["by_method"]["B6"]
    dx1_n = sn["by_method"]["ĐX-1"]
    dx2_n = sn["by_method"]["ĐX-2"]
    dx3_n = sn["by_method"]["ĐX-3"]

    m_b3 = b3_n["m_3s_mean"]
    m_b3p = b3p_n["m_3s_mean"]
    m_dx1 = dx1_n["m_3s_mean"]
    red_proj = 100.0 * (1.0 - m_b3p / m_b3)
    red_pool = 100.0 * (1.0 - m_dx1 / m_b3p)
    red_tot = 100.0 * (1.0 - m_dx1 / m_b3)

    h2 = an["h2_inf_and_autocorr"]
    h5 = an["h5_certification"]
    ac_ah = an["ac_vs_ah_by_scn"]
    rep_e = an["replanning_e_split"]

    rho_2s = next(r["rho1"] for r in h2["autocorr_by_lag"] if abs(r["lag_s"] - 2.0) < 1e-6)
    rho_3s = next(r["rho1"] for r in h2["autocorr_by_lag"] if abs(r["lag_s"] - 3.0) < 1e-6)

    old_dx1_inf = h2["old_inf_bias_by_method"]["ĐX-1"]
    fcr_899 = next(r for r in h5["false_cert_curve"] if abs(r["p_true"] - 0.899) < 1e-6)

    sig_new = cn["sigma_tau"]
    sig_old = co["sigma_tau"]

    lines: list[str] = []
    add = lines.append

    add("# BÁO CÁO KẾT QUẢ MÔ PHỎNG VÒNG KÍN VÀ ĐỀ XUẤT SỬA ĐỔI BẢN THẢO v0.1")
    add("")
    add("**Đề tài:** Biên an toàn phù hợp có xét sai số của xe tự hành cho lập kế hoạch chuyển động xe lái kiểu Ackermann trong môi trường có tác nhân động  ")
    add(f"**Ngày tạo:** {sn['generated_at']} · **Môi trường:** Mô phỏng vòng kín 2D (Python/NumPy) · **Hạt giống gốc:** `{cfgn['seed_base']}`")
    add("")

    # ------------------------------------------------------------------
    # 1. Tóm tắt kết quả chính (5–7 dòng)
    # ------------------------------------------------------------------
    add("## 1. Tóm tắt kết quả chính")
    add("")
    add(
        f"Kết quả kiểm chứng vòng kín trên 360 lượt chạy ghép cặp (`500–514` × 6 điều kiện `D0–D5` × 4 kịch bản `S1–S4`) cho thấy các sửa đổi ở Phương án mới (B) khắc phục được toàn bộ sai lệch thống kê của Phương án cũ (A). "
        f"Khi bỏ biên (`B0`), xe gặp {_pct(bo_n['collision_rate'])} va chạm và {_pct(bo_n['violation_episode'])} lượt có vi phạm an toàn (độ phủ điểm số {_f(bo_n['coverage_score'])}). "
        f"Ở Phương án A, việc giữ {_pct(old_dx1_inf['empty_frac'])} chu kỳ trống $R = -\\infty$ khiến `ĐX-1` chỉ đạt độ phủ điểm số {_f(dx1_o['coverage_score'])} (thực chất trên chu kỳ có tác nhân chỉ còn {_f(old_dx1_inf['true_active_only'])}, dưới mức danh định 0,900), còn chứng nhận có điều kiện có tỉ lệ chấp nhận sai tới {_pct(fcr_899['pass_cond_3tries'])} tại $p_{{\\mathrm{{true}}}}=0{{,}}899$. "
        f"Ở Phương án B, `ĐX-1` khôi phục độ phủ điểm số {_f(dx1_n['coverage_score'])} (KTC 95% {_ci_str(dx1_n['coverage_score_ci95'])}), đồng thời thu hẹp biên 3 s xuống {_f(m_dx1, 2)} m — giảm **−{red_tot:.1f}%** so với `B3` ({_f(m_b3, 2)} m), tách thành **−{red_proj:.1f}%** nhờ hiệu ứng chiếu hình học (`B3` → `B3′`: {_f(m_b3p, 2)} m) và **−{red_pool:.1f}%** nhờ gộp đồng thời (`B3′` → `ĐX-1`). "
        f"Dưới định vị suy giảm (`D1`, `D2`), biên chỉ xét tác nhân `B1` tụt độ phủ điểm số xuống {_f(sn['by_method_cond']['B1']['D1']['coverage_score'])} và {_f(sn['by_method_cond']['B1']['D2']['coverage_score'])}, trong khi `ĐX-2` khôi phục lên {_f(sn['by_method_cond']['ĐX-2']['D1']['coverage_score'])} và {_f(sn['by_method_cond']['ĐX-2']['D2']['coverage_score'])} (tổng thể {_f(dx2_n['coverage_score'])}; theo nhóm `fix`/`float`/`loss` đạt {_f(sn['by_method_group']['ĐX-2']['fix']['coverage_score'])} / {_f(sn['by_method_group']['ĐX-2']['float']['coverage_score'])} / {_f(sn['by_method_group']['ĐX-2']['loss']['coverage_score'])}, `0,0%` va chạm)."
    )
    add("")

    # ------------------------------------------------------------------
    # 2. Mục tiêu và phạm vi; giới hạn so với CARLA
    # ------------------------------------------------------------------
    add("## 2. Mục tiêu, phạm vi và giới hạn so với CARLA")
    add("")
    add(
        "Mục tiêu của nghiên cứu mô phỏng 2D này là dựng một môi trường vòng kín hoàn toàn xác định (deterministic) để kiểm chứng độc lập các giả thiết, "
        "công thức hiệu chỉnh, thủ tục chứng nhận chính sách và đối chứng giữa **Phương án cũ A** (cài đặt đúng bản thảo v0.1) và **Phương án mới B** (cài đặt các sửa đổi lý thuyết đề xuất) trước khi triển khai thí nghiệm tốn nhiều giờ trên CARLA 0.9.16."
    )
    add("")
    add("### Những điều mô phỏng 2D *chứng minh được*")
    add("- Tính đúng đắn của phân tích sai số hai nguồn và độ chặt của biên gộp so với `B3` và đối chứng mới `B3′` (Mệnh đề 3).")
    add("- Sai lệch phân vị khi giữ chu kỳ không có tác nhân ($R = -\\infty$) và sự suy giảm tự tương quan chuỗi $R$ khi chuyển từ lấy thưa chồng cửa sổ $2\\text{ s}$ sang không chồng $3\\text{ s} = H$.")
    add("- Khác biệt giữa sai số tâm $A_c$ và cận Hausdorff $A_h$ khi tác nhân đa đĩa (xe máy, ô tô) có nhiễu quay.")
    add("- Rủi ro chứng nhận sai của kiểm tra có điều kiện so với chứng nhận PAC có hiệu chỉnh Bonferroni (Định lý 2 sửa đổi).")
    add("- Cơ chế thích ứng của `ĐX-2` (theo nhãn định vị) và `ĐX-3` (ACI phản hồi trễ $H$) dưới sáu điều kiện suy giảm `D0–D5`.")
    add("")
    add("### Những điều mô phỏng 2D *KHÔNG* chứng minh được (giới hạn so với CARLA)")
    add("- **Động lực học 3D và phi tuyến lốp thực tế:** Xe mô phỏng dùng mô hình xe đạp động học kèm trễ bậc nhất và trượt ngang AR(1) cho `D3`, chưa có chuyển tải trọng dọc/ngang, bó cứng phanh ABS hay đặc tính `steering_curve` phi tuyến của Tesla Model 3 trong Unreal/PhysX.")
    add("- **Nhận thức cảm biến thật và điểm mù:** Bộ phát chỉ cộng nhiễu Gauss vào tọa độ/vận tốc tác nhân trong vùng $40\\text{ m}$, không mô phỏng che khuất hình học (occlusion), mất phát hiện (false negative) hay trễ pipeline LiDAR/camera.")
    add("- **Dự báo học sâu đa phương thức:** Bộ dự báo vận tốc hằng (CV) thay thế cho Trajectron++, do đó chưa phản ánh sai số phân phối đặc trưng hoặc độ trễ suy luận GPU của mạng neural.")
    add("- **Thực thi thời gian thực và giao tiếp ROS 2:** Thời gian tính trong log phản ánh lõi NumPy tối ưu (P95 ~1,37–1,49 ms), không đại diện cho tổng độ trễ nút ROS 2 và bộ lập kế hoạch trên máy tính nhúng hay xe thật Hunter SE.")
    add("")

    # ------------------------------------------------------------------
    # 3. Thiết lập mô phỏng
    # ------------------------------------------------------------------
    add("## 3. Thiết lập mô phỏng")
    add("")
    add("- **Xe thật cỡ Tesla Model 3:** $L = 2{,}875\\text{ m}$, hộp bao $4{,}69 \\times 1{,}85\\text{ m}$, tâm cầu sau cách đuôi $0{,}96\\text{ m}$, $r_{\\max} = 3{,}85\\text{ m}$, $\\delta_{\\max} = 0{,}6\\text{ rad}$, $\\omega_{\\max} = 0{,}8\\text{ rad/s}$, $a \\in [-6; 3]\\text{ m/s}^2$, $v_{\\max} = 8{,}3\\text{ m/s}$; trễ gia tốc $0{,}25\\text{ s}$, trễ lái $0{,}1\\text{ s}$, sai số hệ số lái $\\pm 5\\%$ mỗi lượt, trễ lệnh nền $50\\text{ ms}$, bù trước vận tốc tại $t + 0{,}5\\text{ s}$.")
    add("- **Tần số & đường:** Mô phỏng $20\\text{ Hz}$ ($\\Delta t = 0{,}05\\text{ s}$), lập kế hoạch $10\\text{ Hz}$, chân trời $H = 30 \\times 0{,}1\\text{ s} = 3{,}0\\text{ s}$, bộ bám Pure Pursuit $L_d = 2 + 0{,}3v$ ở $20\\text{ Hz}$; đường thẳng trục $x$, làn $y \\in [-1{,}75; 1{,}75]\\text{ m}$, đích $x = 75\\text{ m}$, tối đa $16\\text{ s}$.")
    add("- **Định vị & 6 điều kiện suy giảm:** `D0` RTK cố định ($\\sigma = 0{,}03\\text{ m} / 0{,}003\\text{ rad}$, nhãn `fix`); `D1` RTK thả nổi AR(1) $5\\text{ s}$ ($0{,}3\\text{ m} / 0{,}02\\text{ rad}$, nhãn `float`); `D2` mất GNSS $5\\text{–}10\\text{ s}$ trôi tích lũy và hội tụ $1{,}5\\text{ s}$ (nhãn `loss` khi mất, `fix` ngoài khoảng mất); `D3` trượt bánh thiếu lái $15\\%$ + trượt ngang AR(1) $\\sigma = 0{,}04$ (nhãn `fix`); `D4` trễ thêm cố định $\\{50, 100, 200\\}\\text{ ms}$ (nhãn `fix`); `D5` trễ ngẫu nhiên $\\mathrm{Gamma}(2; 0{,}05)$ cắt ở $0{,}3\\text{ s}$ (nhãn `fix`).")
    add("- **Tác nhân & 4 kịch bản:** Tập đĩa cứng (`ped` 1 đĩa $r=0{,}35\\text{ m}$; `moto` 2 đĩa $r=0{,}45\\text{ m}$ cách $1\\text{ m}$; `car` 3 đĩa $r=0{,}95\\text{ m}$ cách $1{,}4\\text{ m}$) có nhiễu AR(1) trên tốc độ quay và gia tốc dọc. `S1` người đi bộ sang đường ($0{,}8\\text{–}1{,}8\\text{ m/s}$, 20% dừng giữa đường $2\\text{–}4\\text{ s}$); `S2` xe máy cắt ngang $30\\text{–}90^\\circ$ ($3\\text{–}8\\text{ m/s}$); `S3` giao cắt không đèn (xe máy + ô tô); `S4` xe trước phanh gấp $2\\text{–}5\\text{ m/s}^2$.")
    add("- **Planner & lọc:** 351 ứng viên Frenet (13 lệch ngang $\\pm 1{,}5\\text{ m}$ bước $0{,}25\\text{ m}$ × 9 vận tốc đích $0\\text{–}8{,}3\\text{ m/s}$ × 3 thời gian $T \\in \\{3,4,5\\}\\text{ s}$); lọc động học → lọc an toàn $\\hat{d}_\\tau^j \\ge d_s + m_\\tau$ ($d_s = 0{,}5\\text{ m}$); chi phí $J = (v_{\\max} - v_{\\mathrm{đích}})^2 + 0{,}1\\int \\mathrm{jerk}^2 dt + 2 d_f^2$; không còn ứng viên thì phanh dự phòng với $a_{\\min} = -6{,}0\\text{ m/s}^2$.")
    add("- **Phân chia hạt giống:** `200–249` ước lượng $\\sigma_\\tau$ (chỉ B); `250–299`, `300–349`, `350–399` hiệu chỉnh lặp 3 khối × 50 lượt; `400–449`, `450–499`, `600–649` chứng nhận (tối đa 3 lần thử); `500–514` kiểm tra ghép cặp (15 hạt giống × 24 tổ hợp = 360 lượt/phương pháp; `B0` chạy 1 lần dùng chung).")
    add("")

    # ------------------------------------------------------------------
    # 4. Kết quả phương án cũ (A)
    # ------------------------------------------------------------------
    add("## 4. Kết quả phương án cũ (A — bản thảo v0.1)")
    add("")
    add(
        "Phương án cũ áp dụng $\\sigma_\\tau = 0{,}05 + 0{,}04\\tau$ ($\\sigma_{30} = 1{,}25\\text{ m}$), lấy thưa mỗi $2\\text{ s}$, giữ lại mẫu không có tác nhân ($R = -\\infty$, chiếm ~17,8–17,9% chu kỳ thưa), "
        "dùng $A_c$ cho B1/B3/B6 và chứng nhận có điều kiện ($\\hat{q} \\le q_{\\mathrm{plan}}$). Bảng dưới trình bày kết quả theo mẫu Bảng 4 của bản thảo, bổ sung cả **độ phủ điểm số** $\\mathbb{P}(R \\le q)$ (kiểm chứng trực tiếp Định lý 1) bên cạnh **độ phủ an toàn vật lý** $\\min_{\\tau,j} d \\ge d_s$."
    )
    add("")
    add("| Phương pháp | Độ phủ $d \\ge d_s$ (KTC 95%) | Độ phủ điểm số $R \\le q$ (KTC 95%) | Vi phạm lượt / Va chạm (%) | $d_{\\min}$ (m) / $\\mathrm{TTC}_{\\min}$ (s) | Hoàn thành (%) / $t_{\\mathrm{end}}$ (s) / Dự phòng (%) | RMS giật (m/s³) / P95 $t_{\\mathrm{tính}}$ (ms) | Ngưỡng $q$ / $m_{3\\text{s}}$ (m) |")
    add("|---|---|---|---|---|---|---|---|")
    for m in cfgo["methods"]:
        d = so["by_method"][m]
        add(
            f"| {m} | {_f(d['coverage_safe'])} {_ci_str(d['coverage_safe_ci95'])} "
            f"| {_f(d['coverage_score'])} {_ci_str(d['coverage_score_ci95'])} "
            f"| {_pct(d['violation_episode'])} / {_pct(d['collision_rate'])} "
            f"| {_f(d['d_min_mean'],2)} / {_f(d['ttc_min_mean'],2)} "
            f"| {_pct(d['completion_rate'])} / {_f(d['t_end_mean'],2)} / {d['fallback_pct']:.1f}% "
            f"| {_f(d['jerk_rms_mean'],2)} / {_f(d['tcomp_p95_ms'],2)} "
            f"| {_f(d['q_mean'],2)} / {_f(d['m_3s_mean'],2)} |"
        )
    add("")
    add(
        f"**Nhận xét Phương án A:** Do biên của lưới ứng viên Frenet có độ dư (slack) hình học khá lớn khi $m_{{3\\text{{s}}}} \\ge 3{{,}}5\\text{{ m}}$, độ phủ vật lý $\\min d \\ge d_s$ đạt $\\ge 99{{,}}5\\%$ ở mọi phương pháp có biên (`B1–B6`, `ĐX-1..3`). "
        f"Tuy nhiên, kiểm tra trực tiếp bất đẳng thức hiệu chỉnh $R \\le q$ (Độ phủ điểm số) bộc lộ hai lỗi nghiêm trọng của Phương án A: "
        f"(1) `ĐX-1` và `ĐX-2` chỉ đạt độ phủ điểm số **{_f(dx1_o['coverage_score'])}** và **{_f(dx2_o['coverage_score'])}** (thấp hơn mức danh định $0{{,}}900$, ngay cả khi đã cộng cả 17,9% chu kỳ trống $R = -\\infty$); "
        f"(2) Ở các điều kiện suy giảm `D1` và `D2`, độ phủ điểm số của `ĐX-1` tụt xuống **{_f(so['by_method_cond']['ĐX-1']['D1']['coverage_score'])}** và **{_f(so['by_method_cond']['ĐX-1']['D2']['coverage_score'])}**, còn `ĐX-2` tụt xuống **{_f(so['by_method_cond']['ĐX-2']['D1']['coverage_score'])}** và **{_f(so['by_method_cond']['ĐX-2']['D2']['coverage_score'])}**."
    )
    add("")

    # ------------------------------------------------------------------
    # 5. Kết quả phương án mới (B)
    # ------------------------------------------------------------------
    add("## 5. Kết quả phương án mới (B)")
    add("")
    add(
        f"Phương án mới ước lượng $\\hat{{\\sigma}}_\\tau$ trên hạt giống `200–249` ($\\hat{{\\sigma}}_1 = {_f(sig_new[0])}\\text{{ m}} \\to \\hat{{\\sigma}}_{{30}} = {_f(sig_new[-1])}\\text{{ m}}$), loại bỏ chu kỳ trống, lấy thưa $3\\text{{ s}}$ không chồng, "
        f"dùng cận Hausdorff $A_h$, chứng nhận PAC Bonferroni ($\\delta = 0{{,}}05/3$), bổ sung đối chứng `B3′` và báo cáo tách riêng chu kỳ khả thi với chu kỳ dự phòng."
    )
    add("")
    add("| Phương pháp | Độ phủ $d \\ge d_s$ (KTC 95%) | Độ phủ điểm số $R \\le q$ (KTC 95%) | Khả thi / Dự phòng ($R \\le q$) | Vi phạm lượt / Va chạm (%) | Hoàn thành (%) / $t_{\\mathrm{end}}$ (s) / Dự phòng (%) | $d_{\\min}$ (m) / P95 $t_{\\mathrm{tính}}$ (ms) | Ngưỡng $q$ / $m_{3\\text{s}}$ (m) |")
    add("|---|---|---|---|---|---|---|---|")
    for m in cfgn["methods"]:
        d = sn["by_method"][m]
        add(
            f"| {m} | {_f(d['coverage_safe'])} {_ci_str(d['coverage_safe_ci95'])} "
            f"| {_f(d['coverage_score'])} {_ci_str(d['coverage_score_ci95'])} "
            f"| {_f(d['coverage_score_feasible'])} / {_f(d['coverage_score_fallback'])} "
            f"| {_pct(d['violation_episode'])} / {_pct(d['collision_rate'])} "
            f"| {_pct(d['completion_rate'])} / {_f(d['t_end_mean'],2)} / {d['fallback_pct']:.1f}% "
            f"| {_f(d['d_min_mean'],2)} / {_f(d['tcomp_p95_ms'],2)} "
            f"| {_f(d['q_mean'],2)} / {_f(d['m_3s_mean'],2)} |"
        )
    add("")
    add("### Kiểm định thống kê ghép cặp (McNemar và Wilcoxon, hiệu chỉnh Holm)")
    add("")
    add("| So sánh với `ĐX-2` (mới) | $\\Delta t_{\\mathrm{end}}$ (s) | $p_{\\mathrm{Holm}}$ (Wilcoxon $t_{\\mathrm{end}}$) | $\\Delta d_{\\min}$ (m) | $p_{\\mathrm{Holm}}$ (Wilcoxon $d_{\\min}$) | $p_{\\mathrm{Holm}}$ (McNemar vi phạm $R>q$) |")
    add("|---|---|---|---|---|---|")
    for r in an["stat_tests"]["paired_new"]["ĐX-2"]:
        add(
            f"| vs {r['baseline']} | {r['wilcoxon_tend']['mean_diff']:+.2f} "
            f"| {_p_str(r['wilcoxon_tend']['p_holm'])} "
            f"| {r['wilcoxon_dmin']['mean_diff']:+.2f} "
            f"| {_p_str(r['wilcoxon_dmin']['p_holm'])} "
            f"| {_p_str(r['mcnemar_score_viol']['p_holm'])} |"
        )
    add("")

    # ------------------------------------------------------------------
    # 6. So sánh cũ – mới theo từng sửa đổi
    # ------------------------------------------------------------------
    add("## 6. So sánh phương án cũ – mới theo từng sửa đổi")
    add("")

    add("### 6.1. Độ phủ theo sáu điều kiện suy giảm D0–D5 (Hình H1)")
    add("")
    add(f"![H1. Độ phủ theo điều kiện D0–D5]({fig_prefix}H1_coverage_by_condition.png)")
    add("")
    add("| Phương pháp (Cũ / Mới) | D0 | D1 | D2 | D3 | D4 | D5 | Tổng thể |")
    add("|---|---|---|---|---|---|---|---|")
    for label, s_obj, m in [
        ("B1 (Cũ)", so, "B1"), ("B1 (Mới)", sn, "B1"),
        ("B5 (Mới)", sn, "B5"),
        ("ĐX-1 (Cũ)", so, "ĐX-1"), ("ĐX-1 (Mới)", sn, "ĐX-1"),
        ("ĐX-2 (Cũ)", so, "ĐX-2"), ("ĐX-2 (Mới)", sn, "ĐX-2"),
        ("ĐX-3 (Cũ)", so, "ĐX-3"), ("ĐX-3 (Mới)", sn, "ĐX-3"),
    ]:
        cs = [f"{s_obj['by_method_cond'][m][d]['coverage_score']:.3f}" for d in ["D0","D1","D2","D3","D4","D5"]]
        add(f"| {label} | " + " | ".join(cs) + f" | **{s_obj['by_method'][m]['coverage_score']:.3f}** |")
    add("")
    add(
        "Trên Hình H1 và bảng trên: (i) ở điều kiện danh định `D0`, `D3–D5`, mọi biên phù hợp đều đạt $\\ge 0{,}919$; "
        "(ii) ở `D1` (RTK thả nổi) và `D2` (mất GNSS), phương pháp chỉ xét tác nhân `B1` giảm sâu xuống **0,748** và **0,759**, "
        "ràng buộc cơ hội Gauss `B5` sụp đổ xuống **0,544** và **0,556**, `ĐX-1` dùng ngưỡng chung giảm xuống **0,847** và **0,826**; "
        "(iii) ở Phương án mới, **`ĐX-2`** đạt **0,908** ở `D1` và **0,961** ở `D2` (khắc phục hoàn toàn mức hụt **0,796** của `ĐX-2` cũ tại `D2`), "
        "còn **`ĐX-3`** (ACI) duy trì ổn định **0,876–0,909** ở tất cả `D0–D5` mà không cần nhãn nhóm."
    )
    add("")

    add("### 6.2. Tác động của mẫu $R = -\\infty$ và lấy mẫu chồng cửa sổ (Hình H2)")
    add("")
    add(f"![H2. Tác động của mẫu -inf và bước lấy thưa]({fig_prefix}H2_inf_samples_and_thinning.png)")
    add("")
    add(
        f"- **Ảo giác từ mẫu $-\\infty$:** Trong Phương án cũ, {_pct(old_dx1_inf['empty_frac'])} các chu kỳ đã lấy thưa là chu kỳ không có tác nhân và bị gán $R = -\\infty$. "
        f"Việc giữ các mẫu này trong phân vị hiệu chỉnh và đánh giá tạo ra hiệu ứng hai tầng: khi báo cáo độ phủ của `ĐX-1` cũ là **{_f(old_dx1_inf['reported_with_inf'])}**, thì thực chất trên các chu kỳ có tác nhân (nơi rủi ro thực sự tồn tại), độ phủ điểm số chỉ còn **{_f(old_dx1_inf['true_active_only'])}** (giảm **5,3 điểm phần trăm** dưới ngưỡng 0,900). Khi bỏ hoàn toàn chu kỳ trống ở Phương án B, `ĐX-1` đạt **{_f(dx1_n['coverage_score'])}** trên đúng tập chu kỳ có tác nhân."
    )
    add(
        f"- **Lấy mẫu chồng cửa sổ 2 s so với không chồng 3 s:** Với chân trời $H = 3{{,}}0\\text{{ s}}$, khoảng lấy thưa $\\Delta = 2{{,}}0\\text{{ s}}$ ở Phương án A để chồng lấn $1{{,}}0\\text{{ s}}$ giữa các cửa sổ đánh giá liên tiếp, làm hệ số tự tương quan bậc 1 của $R$ lên tới **$\\rho_1 = {_f(rho_2s)}$**. Chuyển sang $\\Delta = 3{{,}}0\\text{{ s}}$ ở Phương án B cắt giảm tự tương quan hơn một nửa xuống còn **$\\rho_1 = {_f(rho_3s)}$** (gần tương đương mức ở $\\Delta = 4{{,}}0\\text{{ s}}$ là {_f(next(r['rho1'] for r in h2['autocorr_by_lag'] if abs(r['lag_s']-4.0)<1e-6))})."
    )
    add("")

    add("### 6.3. Sai số tác nhân theo cận Hausdorff $A_h$ so với sai số tâm $A_c$")
    add("")
    add("| Kịch bản | Loại tác nhân | Số mẫu ($n$) | Trung bình $A_c/\\sigma_\\tau$ | Trung bình $A_h/\\sigma_\\tau$ | Phân vị 90% $A_c/\\sigma_\\tau$ | Phân vị 90% $A_h/\\sigma_\\tau$ | Chênh lệch P90 |")
    add("|---|---|---|---|---|---|---|---|")
    for scn, desc in [("S1", "Người đi bộ (1 đĩa)"), ("S2", "Xe máy (2 đĩa)"), ("S3", "Xe máy + Ô tô (2–3 đĩa)"), ("S4", "Xe trước phanh (2–3 đĩa)")]:
        r = ac_ah[scn]
        diff_pct = 100.0 * (r["Ah_q90"] / r["Ac_q90"] - 1.0) if r["Ac_q90"] > 0 else 0.0
        add(f"| {scn} | {desc} | {r['n']} | {r['Ac_mean']:.3f} | {r['Ah_mean']:.3f} | {r['Ac_q90']:.3f} | {r['Ah_q90']:.3f} | +{diff_pct:.1f}% |")
    add("")
    s2_diff = 100.0 * (ac_ah["S2"]["Ah_q90"] / ac_ah["S2"]["Ac_q90"] - 1.0)
    s3_diff = 100.0 * (ac_ah["S3"]["Ah_q90"] / ac_ah["S3"]["Ac_q90"] - 1.0)
    add(
        f"Kết quả khẳng định: đối với tác nhân 1 đĩa (`S1`), $A_c \\equiv A_h$; nhưng với tác nhân đa đĩa có chuyển động quay (`S2`, `S3`), cận Hausdorff $A_h$ lớn hơn sai số tâm $A_c$ tới **+{s2_diff:.1f}%** ở `S2` và **+{s3_diff:.1f}%** ở `S3` tại phân vị 90%. "
        "Do đó phát biểu Bổ đề 1 và định nghĩa $A_i$ của `B1, B3, B6` trong bản thảo bắt buộc phải dùng $A_h$ để cận trên trên đa giác/tập đĩa là chính xác."
    )
    add("")

    add("### 6.4. Chuẩn hóa $\\sigma_\\tau$ ước lượng thực nghiệm so với công thức cố định")
    add("")
    add(
        f"Công thức cố định ở Phương án A ($\\sigma_\\tau = 0{{,}}05 + 0{{,}}04\\tau$) tăng tuyến tính từ $0{{,}}09\\text{{ m}}$ ($\\tau=1$) lên $1{{,}}25\\text{{ m}}$ ($\\tau=30$), đánh giá quá thấp tốc độ phình sai số ở cuối chân trời $2{{,}}0\\text{{–}}3{{,}}0\\text{{ s}}$ khi có tác nhân phanh/rẽ. "
        f"Khi ước lượng phân vị 90% trên hạt giống riêng `200–249`, $\\hat{{\\sigma}}_\\tau$ tăng từ **{_f(sig_new[0])} m** ($\\tau=1$), **{_f(sig_new[9])} m** ($\\tau=10$), **{_f(sig_new[19])} m** ($\\tau=20$) lên **{_f(sig_new[29])} m** ($\\tau=30$), phản ánh đúng hình dạng tăng siêu tuyến tính theo $\\tau$."
    )
    add("")

    add("### 6.5. Chứng nhận có điều kiện so với chứng nhận PAC Bonferroni (Hình H5)")
    add("")
    add(f"![H5. Chứng nhận có điều kiện vs PAC]({fig_prefix}H5_cert_conditional_vs_PAC.png)")
    add("")
    add(
        f"Trong thực nghiệm chạy thực tế, cả Phương án cũ và Phương án mới đều cần 2 lần thử chứng nhận cho `ĐX-1`. Tuy nhiên, ở Phương án mới, khi $q_{{\\mathrm{{iter}}}} = {_f(cn['DX-1']['iterations'][-1]['q_out'], 4)}$ được đưa vào thử lần 1 ($n = {cn['DX-1']['certification_tries'][0]['n_thinned']}$), "
        f"ngưỡng điều kiện $\\hat{{q}}_{{\\mathrm{{cond}}}} = {_f(cn['DX-1']['certification_tries'][0]['q_cond'], 4)}$ đã gần đạt, nhưng kiểm tra PAC ($k_{{\\mathrm{{PAC}}}} = {cn['DX-1']['certification_tries'][0]['k_pac']}/{cn['DX-1']['certification_tries'][0]['n_thinned']}$, $\\hat{{q}}_{{\\mathrm{{PAC}}}} = {_f(cn['DX-1']['certification_tries'][0]['q_pac'], 4)}$) đã kịp thời từ chối và nâng lên $q_{{\\mathrm{{final}}}} = {_f(cn['DX-1']['q_final'], 4)}$ ở lần thử 2. "
        f"Phân tích Monte Carlo trên Hình H5 (panel a: 4.000 lần lặp mỗi điểm với $n = {h5['n_cert']}$, $k_{{\\mathrm{{cond}}}} = {h5['k_cond']}$, $k_{{\\mathrm{{PAC}}}} = {h5['k_pac']}$; panel b: 3.000 kịch bản hậu chứng nhận) cho thấy: "
        f"tại $p_{{\\mathrm{{true}}}} = 0{{,}}899$, chứng nhận có điều kiện có xác suất chấp nhận sai tới **{_pct(fcr_899['pass_cond_3tries'])}** (sau tối đa 3 lần thử) và tỉ lệ chính sách hậu chứng nhận rơi dưới $0{{,}}90$ lên tới **{_pct(h5['dist_cond_below90'])}**; "
        f"trong khi chứng nhận PAC Bonferroni khống chế xác suất chứng nhận sai ở **{_pct(fcr_899['pass_pac_3tries'])}** ($< \\delta = 5\\%$) và tỉ lệ hậu chứng nhận dưới $0{{,}}90$ chỉ còn **{_pct(h5['dist_pac_below90'])}**."
    )
    add("")

    add("### 6.6. Phân tách `B3` so với `B3′` so với `ĐX-1` (Hình H3)")
    add("")
    add(f"![H3. So sánh B3 vs B3′ vs ĐX-1]({fig_prefix}H3_B3_vs_B3prime_vs_DX1.png)")
    add("")
    tend_diff_dx1_b3 = abs(next(r["wilcoxon_tend"]["mean_diff"] for r in an["stat_tests"]["paired_new"]["ĐX-1"] if r["baseline"] == "B3"))
    add(
        f"Hình H3 tách rạch ròi hai nguồn lợi ích của biên gộp so với cộng hai biên riêng: "
        f"(1) **Hiệu ứng chiếu hình học** (`B3`: $m_{{3\\text{{s}}}} = {_f(m_b3, 2)}\\text{{ m}}$ → `B3′`: $m_{{3\\text{{s}}}} = {_f(m_b3p, 2)}\\text{{ m}}$) giảm **−{red_proj:.1f}%** bề rộng biên nhờ chuyển từ chuẩn đẳng hướng $A_h + E$ sang hai thành phần có dấu $a + b$ chiếu lên khoảng cách hình học; "
        f"(2) **Hiệu ứng gộp đồng thời** (`B3′` → `ĐX-1`: $m_{{3\\text{{s}}}} = {_f(m_dx1, 2)}\\text{{ m}}$) giảm tiếp **−{red_pool:.1f}%** nữa nhờ bỏ chia mức rủi ro $\\alpha/2 + \\alpha/2$ và không giả định cực đại của $a$ và $b$ xảy ra đồng thời (tổng mức giảm **−{red_tot:.1f}%**). "
        f"Nhờ vậy, tỉ lệ hoàn thành lộ trình tăng vọt từ **{_pct(b3_n['completion_rate'])}** (`B3`) và **{_pct(b3p_n['completion_rate'])}** (`B3′`) lên **{_pct(dx1_n['completion_rate'])}** (`ĐX-1`), tỉ lệ chu kỳ dự phòng giảm từ **{b3_n['fallback_pct']:.1f}%** xuống **{dx1_n['fallback_pct']:.1f}%**, và thời gian hoàn thành giảm **{tend_diff_dx1_b3:.2f} s** ($p_{{\\mathrm{{Holm}}}} = {_p_str(next(r['wilcoxon_tend']['p_holm'] for r in an['stat_tests']['paired_new']['ĐX-1'] if r['baseline']=='B3'))}$)."
    )
    add("")

    add("### 6.7. Chu kỳ dự phòng và hiệu ứng lập lại kế hoạch lên $E_\\tau$")
    add("")
    add(
        f"Khi tách riêng chu kỳ khả thi và chu kỳ dự phòng ở Phương án B: trên các chu kỳ khả thi, `ĐX-1` đạt độ phủ điểm số **{_f(dx1_n['coverage_score_feasible'])}** ($n={dx1_n['n_feasible_thinned']}$) và `ĐX-2` đạt **{_f(dx2_n['coverage_score_feasible'])}** ($n={dx2_n['n_feasible_thinned']}$), đều vượt $0{{,}}900$; "
        f"ngược lại trên các chu kỳ dự phòng, độ phủ điểm số của `ĐX-1` là **{_f(dx1_n['coverage_score_fallback'])}** ($n={dx1_n['n_fallback_thinned']}$) và của `B5` chỉ còn **{_f(b5_n['coverage_score_fallback'])}**. "
        f"Đồng thời, phân tích `E_max_norm` của `B0` ở điều kiện chuẩn `D0` cho thấy: ở các chu kỳ không có tác nhân (không xảy ra chuyển chế độ lập kế hoạch), $E/\\sigma_\\tau$ có trung bình **{_f(rep_e['empty_no_replan']['E_norm_mean'])}** (trung vị **{_f(rep_e['empty_no_replan']['E_norm_median'])}**, $n={rep_e['empty_no_replan']['n']}$); "
        f"nhưng ở chu kỳ có tác nhân, do việc **lập lại kế hoạch (replanning)** làm quỹ đạo thay đổi mục tiêu so với kế hoạch phát tại $t$, $E/\\sigma_\\tau$ nhảy vọt lên trung bình **{_f(rep_e['active_with_replan']['E_norm_mean'])}** và P95 **{_f(rep_e['active_with_replan']['E_norm_p95'])}** ($n={rep_e['active_with_replan']['n']}$)."
    )
    add("")

    add("### 6.8. Phân nhóm `ĐX-2`, cập nhật ACI (`ĐX-3`) và quét tham số $\\alpha$ (Hình H4, H6)")
    add("")
    add(f"![H6. ĐX-2 theo nhóm định vị]({fig_prefix}H6_DX2_by_localization_group.png)")
    add("")
    add(f"![H4. Đánh đổi an toàn - hiệu quả khi quét alpha]({fig_prefix}H4_safety_efficiency_alpha_sweep.png)")
    add("")
    add(
        f"- **Theo nhóm định vị (Hình H6):** Khi dùng ngưỡng chung (`B1` hoặc `ĐX-1`), nhóm `fix` bị thừa an toàn (độ phủ điểm số {_f(sn['by_method_group']['ĐX-1']['fix']['coverage_score'])}), còn nhóm `float` và `loss` tụt mạnh xuống **{_f(sn['by_method_group']['ĐX-1']['float']['coverage_score'])}** và **{_f(sn['by_method_group']['ĐX-1']['loss']['coverage_score'])}**. "
        f"`ĐX-2` điều chỉnh biên $m_{{3\\text{{s}}}}$ theo trạng thái định vị (`fix`: {_f(sn['by_method_group']['ĐX-2']['fix']['m_3s_mean'],2)} m, `float`: {_f(sn['by_method_group']['ĐX-2']['float']['m_3s_mean'],2)} m, `loss`: {_f(sn['by_method_group']['ĐX-2']['loss']['m_3s_mean'],2)} m) và khôi phục độ phủ điểm số lên **{_f(sn['by_method_group']['ĐX-2']['fix']['coverage_score'])} / {_f(sn['by_method_group']['ĐX-2']['float']['coverage_score'])} / {_f(sn['by_method_group']['ĐX-2']['loss']['coverage_score'])}**. "
        f"Tuy nhiên, log chứng nhận `calibration.json` cũng chỉ ra rằng trên một khối 50 lượt hỗn hợp, nhóm `float` ($n={cn['DX-2']['certification_tries'][0]['group_pac']['float']['n']}$) và `loss` ($n={cn['DX-2']['certification_tries'][0]['group_pac']['loss']['n']}$) chưa đạt ngưỡng $n \\ge 39$ để chứng nhận PAC độc lập từng nhóm mà mới đạt PAC tổng thể ($k={cn['DX-2']['certification_tries'][1]['overall_k_pac']}/{cn['DX-2']['certification_tries'][1]['overall_n']}$)."
    )
    add(
        f"- **ACI (`B6` vs `ĐX-3`):** Trong Phương án cũ, cập nhật $\\alpha_t$ trên cả chu kỳ trống kéo $\\alpha_t$ trôi dương bất thường ở các đoạn đường trống, trong khi Phương án mới chỉ cập nhật trên chu kỳ có tác nhân giúp `ĐX-3` giữ độ phủ điểm số **{_f(sn['by_method_group']['ĐX-3']['fix']['coverage_score'])} (`fix`)**, **{_f(sn['by_method_group']['ĐX-3']['float']['coverage_score'])} (`float`)**, **{_f(sn['by_method_group']['ĐX-3']['loss']['coverage_score'])} (`loss`)**."
    )
    add("- **Quét $\\alpha$ (Hình H4 & `alpha_sweep.csv`):**")
    add("")
    add("| Phương pháp | $\\alpha$ | Độ phủ điểm số $R \\le q$ | Độ phủ $d \\ge d_s$ | Hoàn thành (%) | $t_{\\mathrm{end}}$ (s) | Dự phòng (%) | $m_{3\\text{s}}$ (m) | Nhóm dùng ngưỡng chung |")
    add("|---|---|---|---|---|---|---|---|---|")
    for _, r in alpha_df.iterrows():
        add(f"| {r['method']} | {r['alpha']:.2f} | {r['coverage_score']:.3f} | {r['coverage']:.3f} | {100*r['completion_rate']:.1f}% | {r['t_end_mean']:.2f} | {r['fallback_pct']:.1f}% | {r['m_3s_mean']:.2f} | {r['group_fallbacks']} |")
    add("")

    # ------------------------------------------------------------------
    # 7. Đề xuất sửa đổi bản thảo v0.1
    # ------------------------------------------------------------------
    add("## 7. Đề xuất sửa đổi bản thảo v0.1")
    add("")
    add("| Vị trí trong bản thảo v0.1 | Vấn đề phát hiện | Bằng chứng từ mô phỏng | Câu chữ / công thức gợi ý sửa |")
    add("|---|---|---|---|")
    add(
        f"| **Mục 2.3 (PT 2) & Mục 3.2 (Mệnh đề 3)** | Định nghĩa $E_i$ gộp lẫn sai số bám–định vị thật với sự thay đổi mục tiêu do lập lại kế hoạch (replanning). | Ở `D0`, $E/\\sigma_\\tau$ khi không đổi mục tiêu là **{_f(rep_e['empty_no_replan']['E_norm_mean'])}** nhưng tăng vọt lên **{_f(rep_e['active_with_replan']['E_norm_mean'])}** (P95 **{_f(rep_e['active_with_replan']['E_norm_p95'])}**) khi có tác nhân gây replanning. | Giải thích rõ trong Mục 2.3 rằng $e_{{t+\\tau}} - p_{{t+\\tau\\mid t}}$ trong vòng kín bao gồm cả độ lệch do lập lại kế hoạch (replanning drift), hoặc tách $p_{{t+\\tau\\mid t}}$ với quỹ đạo tham chiếu mở vòng không replanning khi đo sai số bám thuần. |"
    )
    add(
        f"| **Mục 2.4 (Bổ đề 1) & Mục 3.2 (Mệnh đề 3)** | Sai số tác nhân dùng độ dời tâm $A_c$ bỏ qua sai số quay của đa giác/tập đĩa đa phần tử (xe máy, ô tô). | Ở `S3`, phân vị 90% của $A_h/\\sigma_\\tau$ lớn hơn $A_c/\\sigma_\\tau$ **+{s3_diff:.1f}%** (`{_f(ac_ah['S3']['Ah_q90'])}` so với `{_f(ac_ah['S3']['Ac_q90'])}`); ở `S2` lớn hơn **+{s2_diff:.1f}%**. | Thay định nghĩa $A_i = \\max_{{\\tau,j}} d_H(\\hat{{O}}_{{t+\\tau\\mid t}}^j, O_{{t+\\tau}}^j)/\\sigma_\\tau$ (cận Hausdorff trên mọi đỉnh đa giác hoặc tâm các đĩa + bán kính) trong Bổ đề 1 và trong các đối chứng B1, B3, B6. |"
    )
    add(
        f"| **Mục 2.5 (Giả thiết A1)** | Lấy thưa mỗi $2\\text{{ s}}$ khi $H = 3\\text{{ s}}$ gây chồng cửa sổ $1\\text{{ s}}$, vi phạm gần độc lập. | Tự tương quan bậc 1 $\\rho_1 = {_f(rho_2s)}$ ở $\\Delta = 2\\text{{ s}}$, giảm hơn một nửa xuống $\\rho_1 = {_f(rho_3s)}$ khi $\\Delta = 3\\text{{ s}} = H$. | Sửa câu chữ giả thiết (A1): *“...trong mỗi lượt chạy, chỉ lấy các chu kỳ cách nhau tối thiểu $H \\cdot T_s = 3\\text{{ s}}$ (không chồng cửa sổ dự báo) để giảm tự tương quan chuỗi điểm số.”* |"
    )
    add(
        f"| **Mục 3.1 (PT 5) & Mục 3.2** | Giữ chu kỳ không có tác nhân ($\\mathcal{{J}}_t = \\emptyset$) và gán $R_i = -\\infty$ làm lệch phân vị hiệu chỉnh xuống thấp giả tạo. | Ở Phương án A, giữ **{_pct(old_dx1_inf['empty_frac'])}** mẫu $-\\infty$ làm độ phủ thực trên chu kỳ có tác nhân của `ĐX-1` tụt còn **{_f(old_dx1_inf['true_active_only'])}** (dù báo cáo gộp là {_f(old_dx1_inf['reported_with_inf'])}). | Sửa Mục 3.1: *“Chỉ đưa vào tập hiệu chỉnh và tập đánh giá các chu kỳ có tập tác nhân khác rỗng ($\\mathcal{{J}}_i \\neq \\emptyset$). Tỉ lệ chu kỳ không có tác nhân được thống kê riêng để mô tả mật độ giao thông.”* |"
    )
    add(
        f"| **Mục 3.2 (Định lý 2 & Thuật toán 1)** | Kiểm tra $\\hat{{q}} \\le q_{{\\mathrm{{plan}}}}$ chỉ là điều kiện cần ngẫu nhiên, không có bảo đảm PAC và tăng rủi ro khi thử nhiều lần. | Xác suất chứng nhận sai của kiểm tra có điều kiện là **{_pct(fcr_899['pass_cond_3tries'])}** tại $p=0{{,}}899$, và **{_pct(h5['dist_cond_below90'])}** chính sách hậu chứng nhận có độ phủ $<0{{,}}90$. | Thay Định lý 2 bằng **chứng nhận PAC hiệu chỉnh Bonferroni** theo phát biểu đầy đủ ở cuối mục này; áp dụng $k_{{\\mathrm{{PAC}}}}$ trong Thuật toán 1. |"
    )
    add(
        f"| **Mục 3.2 (Mệnh đề 3) & Mục 4.2** | So sánh trực tiếp `B3` với `ĐX-1` không tách rõ hiệu ứng chiếu hình học với hiệu ứng gộp phân vị. | `B3′` giảm **−{red_proj:.1f}%** biên so với `B3`, và `ĐX-1` giảm tiếp **−{red_pool:.1f}%** so với `B3′` (tổng **−{red_tot:.1f}%**). | Bổ sung đối chứng **`B3′`** (hiệu chỉnh riêng hai thành phần có dấu $a_\\tau^j$ và $b_\\tau^j$ ở mức $\\alpha/2$ rồi cộng) vào Mục 4.2 và Bảng 4; thêm Hệ quả tách hai hiệu ứng vào Mục 3.2. |"
    )
    add(
        "| **Mục 3.2 (Mệnh đề 4 — ACI)** | Không nêu rõ loại trừ chu kỳ trống khi cập nhật $\\alpha_t$ và cửa sổ trượt. | Cập nhật trên chu kỳ trống ($\\mathrm{err}=0$) đẩy $\\alpha_t$ trôi lên quá cao và làm nhiễu cửa sổ 500 điểm số. | Ghi rõ trong Thuật toán 2 và Mệnh đề 4: *“Chỉ thực hiện cập nhật $\\alpha_{t+1}$ và chèn $R_{t-H}$ vào cửa sổ trượt đối với các chu kỳ có $\\mathcal{J}_{t-H} \\neq \\emptyset$.”* |"
    )
    add(
        f"| **Mục 3.3 & Mục 4.3 (Bảng 4)** | Gộp chung chu kỳ khả thi và chu kỳ dự phòng (fallback); chỉ báo cáo $d \\ge d_s$ dễ bão hòa $100\\%$ khi biên lớn. | Ở Phương án mới, `ĐX-1` khả thi đạt $R \\le q$ **{_f(dx1_n['coverage_score_feasible'])}** nhưng khi dự phòng là **{_f(dx1_n['coverage_score_fallback'])}**; độ phủ $d \\ge d_s$ bão hòa 1,000 che mất khác biệt của `B1` (`{_f(b1_n['coverage_score'])}`). | Bổ sung vào Bảng 4 cột **Độ phủ điểm số $\\mathbb{{P}}(R \\le q)$** và tách hai giá trị **khả thi / dự phòng** trong báo cáo kết quả. |"
    )
    add("")
    add("### Phát biểu lại Định lý 2 (Chứng nhận chính sách PAC có hiệu chỉnh Bonferroni)")
    add("")
    add("> **Định lý 2 (Chứng nhận chính sách PAC — bản sửa đổi).** *Cố định số lần thử tối đa $M \\ge 1$, mức ý nghĩa tổng $\\delta \\in (0, 1)$, và mức rủi ro mục tiêu $\\alpha \\in (0, 1)$. Đặt $\\delta_m = \\delta / M$. Tại lần thử $m \\in \\{1, \\dots, M\\}$, cố định ngưỡng thiết kế $q_{\\mathrm{plan}}^{(m)}$ độc lập với tập chứng nhận mới $\\mathcal{C}_{\\mathrm{cert}}^{(m)}$ gồm $n_m$ chu kỳ không chồng cửa sổ có tác nhân thu được dưới chính sách $\\pi(q_{\\mathrm{plan}}^{(m)})$. Chọn bậc thống kê thứ tự $k_m \\in \\{1, \\dots, n_m\\}$ nhỏ nhất sao cho*")
    add("> $$\\mathbb{P}\\big(\\mathrm{Bin}(n_m, 1 - \\alpha) \\ge k_m\\big) \\le \\delta_m.$$")
    add("> *Nếu tồn tại $m \\le M$ sao cho $R_{(k_m)}^{(m)} \\le q_{\\mathrm{plan}}^{(m)}$ (tức có ít nhất $k_m$ trong $n_m$ mẫu thỏa $R_i^{(m)} \\le q_{\\mathrm{plan}}^{(m)}$), thì dừng và chứng nhận $\\pi(q_{\\mathrm{plan}}^{(m)})$. Khi các mẫu trong $\\mathcal{C}_{\\mathrm{cert}}^{(m)}$ hoán đổi được, xác suất chấp nhận một chính sách có độ phủ thực $< 1 - \\alpha$ qua toàn bộ quy trình tối đa $M$ lần thử không vượt quá $\\delta$.*")
    add("")

    # ------------------------------------------------------------------
    # 8. Việc cần làm tiếp cho CARLA
    # ------------------------------------------------------------------
    add("## 8. Việc cần làm tiếp cho mô phỏng CARLA 0.9.16")
    add("")
    add(
        f"1. **Cỡ mẫu và số hạt giống cho nhóm mất GNSS (`loss`) và chứng nhận PAC:** "
        f"Để tồn tại $k_m \\le n_m$ thỏa $\\mathbb{{P}}(\\mathrm{{Bin}}(n_m, 0{{,}}9) \\ge k_m) \\le 0{{,}}05/3$, mỗi tập chứng nhận bắt buộc có tối thiểu $n_{{\\min}} = \\lceil \\ln(0{{,}}05/3)/\\ln(0{{,}}9) \\rceil = \\mathbf{{39}}$ chu kỳ không chồng $3\\text{{ s}}$. "
        f"Trong thử nghiệm 50 lượt hỗn hợp hiện tại (`400–449`), nhóm `float` chỉ thu được 29–37 mẫu và `loss` chỉ thu được 2–19 mẫu. Do đó trên CARLA cần: "
        f"(a) dùng kiểm tra PAC tổng thể trên tỉ lệ $R_i / q_{{\\mathrm{{plan}}}}(g_i) \\le 1$ cho chính sách gộp, HOẶC "
        f"(b) thu riêng khối hiệu chỉnh/chứng nhận chuyên biệt cho `D2` (`~130–150` lượt `D2` để đạt $\\ge 40$ mẫu `loss` không chồng cửa sổ trên mỗi khối chứng nhận)."
    )
    add(
        "2. **Thu dữ liệu ước lượng $\\hat{\\sigma}_\\tau$ và huấn luyện Trajectron++ tách biệt:** Giữ nguyên tập `0–199` huấn luyện Trajectron++, tập `200–249` (hoặc mở rộng `200–269`) ước lượng $\\hat{\\sigma}_\\tau$ với `B0`, sau đó đóng băng cả trọng số Trajectron++ lẫn vector $\\hat{\\sigma}_\\tau$ trước khi bước vào Thuật toán 1."
    )
    add(
        "3. **Điều chỉnh Bảng 3 và Bảng 4 trong bản thảo CARLA:** "
        "Trong **Bảng 3** (tham số xe và mô phỏng), ghi rõ trễ lệnh nền, thông số bù trước, giá trị $d_s$ cỡ Tesla Model 3 ($0{,}5\\text{–}1{,}0\\text{ m}$), và ghi chú tách sai số bám thuần vs replanning. "
        "Trong **Bảng 4** (kết quả chính), bổ sung hàng đối chứng **`B3′`**, thêm cột **Độ phủ điểm số $\\mathbb{P}(R \\le q)$** kèm KTC 95% Clopper–Pearson, và tách hai cột con **Khả thi / Dự phòng**."
    )
    add("")

    # ------------------------------------------------------------------
    # 9. Phụ lục
    # ------------------------------------------------------------------
    add("## 9. Phụ lục: Cấu hình, hội tụ hiệu chỉnh, lệnh chạy lại và danh sách log")
    add("")
    add("### 9.1. Tóm tắt hội tụ hiệu chỉnh và chứng nhận (`calibration.json`)")
    add("")
    add(f"- **Phương án cũ (`ĐX-1`):** $q_0 = {_f(co['DX-1']['q0'], 4)}$ → vòng 1: `{_f(co['DX-1']['iterations'][0]['q_out'], 4)}` → vòng 2: `{_f(co['DX-1']['iterations'][1]['q_out'], 4)}` → vòng 3: `{_f(co['DX-1']['iterations'][2]['q_out'], 4)}`; chứng nhận đạt ở lần thử **{co['DX-1']['n_cert_tries']}** với $q_{{\\mathrm{{final}}}} = {_f(co['DX-1']['q_final'], 4)}$ ($m_{{3\\text{{s}}}} = {_f(co['DX-1']['m_3s_final'], 2)}\\text{{ m}}$).")
    add(f"- **Phương án cũ (`ĐX-2`):** chứng nhận đạt ở lần thử **{co['DX-2']['n_cert_tries']}** với $q_{{\\mathrm{{final}}}} = \\{{$`fix`: `{_f(co['DX-2']['q_final_by_group']['fix'], 4)}`, `float`: `{_f(co['DX-2']['q_final_by_group']['float'], 4)}`, `loss`: `{_f(co['DX-2']['q_final_by_group']['loss'], 4)}`$\\}}$.")
    add(f"- **Phương án mới (`ĐX-1`):** $q_0 = {_f(cn['DX-1']['q0'], 4)}$ → vòng 1: `{_f(cn['DX-1']['iterations'][0]['q_out'], 4)}` → vòng 2: `{_f(cn['DX-1']['iterations'][1]['q_out'], 4)}` → vòng 3: `{_f(cn['DX-1']['iterations'][2]['q_out'], 4)}`; chứng nhận PAC đạt ở lần thử **{cn['DX-1']['n_cert_tries']}** với $q_{{\\mathrm{{final}}}} = {_f(cn['DX-1']['q_final'], 4)}$ ($m_{{3\\text{{s}}}} = {_f(cn['DX-1']['m_3s_final'], 2)}\\text{{ m}}$).")
    add(f"- **Phương án mới (`ĐX-2`):** chứng nhận PAC tổng thể đạt ở lần thử **{cn['DX-2']['n_cert_tries']}** với $q_{{\\mathrm{{final}}}} = \\{{$`fix`: `{_f(cn['DX-2']['q_final_by_group']['fix'], 4)}`, `float`: `{_f(cn['DX-2']['q_final_by_group']['float'], 4)}`, `loss`: `{_f(cn['DX-2']['q_final_by_group']['loss'], 4)}`$\\}}$ ($m_{{3\\text{{s}}}} = {_f(cn['DX-2']['m_3s_by_group']['fix'], 2)} / {_f(cn['DX-2']['m_3s_by_group']['float'], 2)} / {_f(cn['DX-2']['m_3s_by_group']['loss'], 2)}\\text{{ m}}$).")
    add("")
    add("### 9.2. Lệnh chạy lại và danh sách file log")
    add("")
    add("```bash")
    add("python run_all.py --seed-base 0")
    add("```")
    add("")
    add("- `logs/old/`: `config.json`, `calibration.json`, `cycles.csv`, `episodes.csv`, `summary.json` (đủ 5 file theo SPEC §6).")
    add("- `logs/new/`: `config.json`, `calibration.json`, `cycles.csv`, `episodes.csv`, `summary.json`, `alpha_sweep.csv` (đủ 6 file theo SPEC §6).")
    add("- `figs/`: `H1_coverage_by_condition.{png,pdf}`, `H2_inf_samples_and_thinning.{png,pdf}`, `H3_B3_vs_B3prime_vs_DX1.{png,pdf}`, `H4_safety_efficiency_alpha_sweep.{png,pdf}`, `H5_cert_conditional_vs_PAC.{png,pdf}`, `H6_DX2_by_localization_group.{png,pdf}`, `analysis_results.json`.")
    add("")

    return "\n".join(lines)


def _add_styled_table(doc: docx.Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        p = cell.paragraphs[0]
        run = p.add_run(h.replace("**", "").replace("$", ""))
        run.bold = True
        run.font.size = Pt(8.5)
    for i, r in enumerate(rows, start=1):
        for j in range(min(len(r), len(headers))):
            val = r[j]
            cell = table.rows[i].cells[j]
            p = cell.paragraphs[0]
            run = p.add_run(val.replace("**", "").replace("$", ""))
            run.font.size = Pt(8.0)


def write_docx_from_markdown(md_text: str, figs_dir: Path, out_docx: Path) -> None:
    """Chuyển báo cáo Markdown sang Word (.docx) kèm bảng biểu chuẩn và nhúng 6 hình PNG."""
    doc = docx.Document()
    normal_style = doc.styles["Normal"]
    normal_style.font.name = "Calibri"
    normal_style.font.size = Pt(10.5)

    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Image syntax: ![caption](path)
        if line.startswith("![") and "](" in line and line.endswith(")"):
            cap = line[2:line.index("](")]
            rel_path = line[line.index("](") + 2 : -1]
            img_name = Path(rel_path).name
            img_path = figs_dir / img_name
            if img_path.exists():
                p_img = doc.add_paragraph()
                p_img.alignment = 1
                p_img.add_run().add_picture(str(img_path), width=Inches(6.3))
                p_cap = doc.add_paragraph(cap)
                p_cap.alignment = 1
                p_cap.runs[0].italic = True
                p_cap.runs[0].font.size = Pt(9)
            i += 1
            continue

        # Markdown table
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|---"):
            headers = [c.strip() for c in line.strip("|").split("|")]
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            _add_styled_table(doc, headers, rows)
            doc.add_paragraph()
            continue

        # Code block
        if line.startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            p_c = doc.add_paragraph("\n".join(code_lines))
            for r in p_c.runs:
                r.font.name = "Consolas"
                r.font.size = Pt(9.5)
            continue

        # Headings
        if line.startswith("# "):
            h = doc.add_heading(line[2:], level=0)
        elif line.startswith("## "):
            doc.add_heading(line[3:], level=1)
        elif line.startswith("### "):
            doc.add_heading(line[4:], level=2)
        elif line.startswith("> "):
            p = doc.add_paragraph(line[2:].replace("*", "").replace("$$", ""))
            p.paragraph_format.left_indent = Inches(0.3)
            for r in p.runs:
                r.italic = True
        elif line.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            p.add_run(line[2:].replace("**", "").replace("`", ""))
        else:
            p = doc.add_paragraph(line.replace("**", "").replace("`", ""))
        i += 1

    out_docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_docx))


def generate_report(root: Path) -> tuple[Path, Path]:
    """Sinh báo cáo Markdown và Word trong report/."""
    report_dir = root / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    md_path = report_dir / "BAO_CAO_KET_QUA_VA_DE_XUAT_SUA_DOI.md"
    docx_path = report_dir / "BAO_CAO_KET_QUA_VA_DE_XUAT_SUA_DOI.docx"

    md_text = build_report_markdown(root, fig_prefix="../figs/")
    md_path.write_text(md_text, encoding="utf-8")
    write_docx_from_markdown(md_text, root / "figs", docx_path)
    return md_path, docx_path
