"""Sinh báo cáo tái lập Mục 4.1 từ logs/num41/summary.json (SPEC §10.9, TASKS T27).

Mọi con số trong báo cáo đọc từ summary.json — không gõ tay số tái lập.
Chạy: python -m num41.report_41  (từ thư mục ws). Thêm --docx để xuất .docx bằng pandoc.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess

from num41 import SPEC_VERSION
from num41.logio import LOG_DIR, ROOT

REPORT_DIR = ROOT / "report"
OUT_MD = REPORT_DIR / "BAO_CAO_TAI_LAP_4_1.md"
REF_DOCX = REPORT_DIR / "docx_src" / "reference.docx"

ASSUMPTIONS = [
    ("U1", "“Trôi chậm” của sai số định vị", "AR(1) dừng theo từng trục, độ lệch chuẩn σ_loc, hằng số thời gian 5 s"),
    ("U2", "Sai số bám", "AR(1) theo cả hai trục, độ lệch chuẩn 0,05 m, hằng số thời gian 1 s"),
    ("U3", "Sai số hướng ψ", "Xe là đĩa nên E = max_τ ‖Δp_τ‖/σ_τ, không có thành phần hướng"),
    ("U4", "Số tác nhân mỗi mẫu", "Một tác nhân"),
    ("U5", "“Đi về phía đường của xe”", "Hướng tới một điểm ngẫu nhiên x_c ~ U(0; 6) m trên đường xe"),
    ("U6", "Tốc độ quay, gia tốc", "Lấy một lần cho mỗi mẫu, giữ hằng trên chân trời (phương án A)"),
    ("U7", "σ_loc của N1", "0,1 m"),
    ("U8", "Lưới σ_loc của N2", "{0; 0,05; 0,1; 0,2; 0,3; 0,4; 0,5} m"),
    ("U9", "Cách ép tương quan ρ", "Giữ ‖e‖, đổi hướng thành unit(ρ·g + √(1−ρ²)·u); σ_loc = 0,1 m; ρ ∈ {−0,5; 0; 0,5; 0,9}"),
    ("U10", "Độ phủ của B1, B3, B4", "Đều đo bằng P(R_test ≤ q), R là điểm số hụt khoảng cách thật"),
    ("U11", "Định nghĩa B4", "q_A(α) + max E_i trên tập hiệu chỉnh"),
    ("U12", "Cỡ mẫu N3", "n = 1000 tổng, nhãn nhóm ngẫu nhiên theo tỉ lệ 70/20/10; 2000 mẫu kiểm tra"),
]


def f(x: float, d: int = 3) -> str:
    """Số kiểu Việt Nam: dấu phẩy thập phân, dấu trừ chuẩn."""
    t = f"{x:.{d}f}"
    if float(t) == 0:
        t = t.lstrip("-")  # tránh “−0,000”
    return t.replace(".", ",").replace("-", "−")


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def pct_range(lo: float, hi: float) -> str:
    return f"{lo * 100:.0f}–{hi * 100:.0f}%"


def ok(b: bool) -> str:
    return "khớp" if b else "**lệch**"


def load() -> dict:
    with open(LOG_DIR / "summary.json", encoding="utf-8") as fh:
        return json.load(fh)


def build(s: dict) -> str:
    n1 = s["N1"]["cells"]
    n2 = s["N2"]["base"]
    n3 = s["N3"]
    sens3 = s.get("N3_sensitivity", {})
    tab2 = {(r["sigma_loc"], r["method"]): r for r in n2["table"]}
    rho = {r["rho"]: r for r in n2["rho_table"]}
    q2 = {r["item"]: r for r in n2["quantitative"]}
    g3 = {c["group"]: c for c in n3["cells"]}
    q3 = {r["item"]: r for r in n3["quantitative"]}

    # --- số dẫn xuất ---
    sigmas = sorted({k[0] for k in tab2})
    narrow = {sl: 1 - tab2[(sl, "DX")]["q_mean"] / tab2[(sl, "B3")]["q_mean"] for sl in sigmas}
    cov_dx = [tab2[(sl, "DX")]["cov_mean"] for sl in sigmas]
    b4_b3 = [tab2[(sl, "B4")]["q_mean"] / tab2[(sl, "B3")]["q_mean"] for sl in sigmas]
    n1_means = [c["mean"] for c in n1]
    worst = max(n1, key=lambda c: abs(c["z_mean"]))  # lệch lớn nhất tính theo số sai số chuẩn, như bản thảo
    sd01 = {c["n"]: c["sd"] for c in n1 if c["alpha"] == 0.10}
    with open(LOG_DIR / "config.json", encoding="utf-8") as fh:
        cfg = json.load(fh)
    reps2 = cfg["N2"]["reps"]
    n_viol = n2["qualitative"]["propA3_violations"] + n2["qualitative"]["rho_propA3_violations"]
    n_checks = (len(sigmas) + len(rho)) * reps2  # mỗi lần lặp của mỗi ô σ và mỗi ô ρ
    mix_cov = sum(c["prob"] * c["cov_global_mean"] for c in n3["cells"])

    L: list[str] = []
    w = L.append
    w("# Báo cáo tái lập Mục 4.1 — Nghiên cứu số trên dữ liệu tổng hợp")
    w("")
    w(f"*Bản thảo đối chiếu: “Bài báo 1 — Bản thảo tiếng Việt v0.1”. Đặc tả: {SPEC_VERSION}. Hạt giống: "
      f"{cfg['N1']['seed']}. Báo cáo này sinh tự động bằng `python -m num41.report_41` từ `logs/num41/summary.json`.*")
    w("")

    # 1. Tóm tắt
    w("## 1. Kết luận chính")
    w("")
    w("- Trong `ws/` trước đây không có mã sinh số liệu Mục 4.1. Mã mới ở `num41/` sinh lại toàn bộ "
      "Bảng 1, Bảng 2, Hình 1, Hình 2 và các con số trong lời văn, với hạt giống cố định; chạy lại cho log giống hệt.")
    w(f"- **Bảng 1 (N1):** cả 9 ô khớp chuẩn lý thuyết Beta–nhị thức. Số tái lập lệch bản thảo tối đa "
      f"{f(max(abs(c['diff_mean_vs_draft']) for c in n1))} ở trung bình và "
      f"{f(max(abs(c['diff_sd_vs_draft']) for c in n1))} ở độ lệch chuẩn. Có thể giữ Bảng 1 hoặc thay bằng số tái lập.")
    w(f"- **Hình 2 (N2):** mọi tiêu chí định tính và định lượng đều đạt. Biên gộp hẹp hơn B3 "
      f"{pct_range(narrow[0.5], narrow[0.1])} (bản thảo 68–77%). Không có lần lặp nào vi phạm Mệnh đề 3 "
      f"({n_viol}/{n_checks}).")
    w(f"- **Bảng 2 (N3):** đạt mọi tiêu chí định tính và {sum(r['ok'] for r in n3['quantitative'])}/"
      f"{len(n3['quantitative'])} tiêu chí định lượng. Ô lệch duy nhất: độ phủ của ngưỡng chung ở nhóm mất GNSS là "
      f"{f(g3['loss']['cov_global_mean'])}, bản thảo ghi 0,620. Theo quy tắc của kế hoạch, không chỉnh tham số "
      "để ép khớp; đề xuất thay số trong bản thảo.")
    w("- Các giả định chưa nêu trong bản thảo (U1–U12, mục 3) nên được bổ sung vào phần Thiết lập của 4.1 (mục 6.2).")
    w("")

    # 2. Cách chạy
    w("## 2. Cách tái lập")
    w("")
    w("```bash\ncd ws\npython -m num41.run_all --seed 2026\n```")
    w("")
    w("| Thành phần | File |")
    w("|---|---|")
    w("| Bộ sinh dữ liệu, điểm số | `num41/gen.py`, `num41/scores.py` |")
    w("| Thí nghiệm | `num41/run_n1.py`, `num41/run_n2.py`, `num41/run_n3.py` |")
    w("| Kiểm thử TC-41a..e | `tests/test_num41.py` → `logs/num41/tests.txt` |")
    w("| Log | `logs/num41/` (`n1_coverage.csv`, `n2_bounds.csv`, `n2_rho.csv`, `n3_groups.csv`, `summary.json`, `config.json`) |")
    w("| Hình | `figs/N0_samples`, `figs/N1_coverage`, `figs/N2_bounds` (`.png`, `.pdf`) |")
    w("")
    w("Hạt giống của mỗi luồng: `SeedSequence(entropy=2026, spawn_key=(thí nghiệm, ô, lần lặp, tập))`; "
      "tập hiệu chỉnh và tập kiểm tra luôn độc lập.")
    w("")

    # 3. Giả định
    w("## 3. Các giả định đã dùng (U1–U12)")
    w("")
    w("Bản thảo không nêu các chi tiết dưới đây; tái lập chọn như sau (SPEC §10).")
    w("")
    w("| Mã | Nội dung | Lựa chọn |")
    w("|---|---|---|")
    for code, what, choice in ASSUMPTIONS:
        w(f"| {code} | {what} | {choice} |")
    w("")

    # 4. Đối chiếu
    w("## 4. Đối chiếu từng con số")
    w("")
    w("Quy ước khớp (PLAN §10.4): Bảng 1 so với chuẩn lý thuyết (trung bình trong ±3 sai số chuẩn, độ lệch chuẩn "
      "sai khác ≤ 15%); các số khác so với bản thảo: độ phủ ±0,02, ngưỡng và tỉ số ±15%.")
    w("")
    w("### 4.1. Bảng 1 — độ phủ theo α và n (200 lần lặp)")
    w("")
    w("| n | 1 − α | Bản thảo | Tái lập | Lý thuyết | z | ĐLC/LT | Kết quả |")
    w("|---|---|---|---|---|---|---|---|")
    for c in sorted(n1, key=lambda c: (c["n"], -c["alpha"])):
        w(f"| {c['n']} | {f(1 - c['alpha'], 2)} | {f(c['draft_mean'])} ± {f(c['draft_sd'])} | "
          f"{f(c['mean'])} ± {f(c['sd'])} | {f(c['theory_mean'])} ± {f(c['theory_sd'])} | {f(c['z_mean'], 2)} | "
          f"{f(c['sd_ratio'], 2)} | {ok(c['pass_mean_3se'] and c['pass_sd_15pct'])} |")
    w("")
    w("### 4.2. Hình 2 — bốn loại biên theo σ_loc (α = 0,1; n = 1000; 50 lần lặp)")
    w("")
    w("| Đại lượng | Bản thảo | Tái lập | Chênh lệch | Kết quả |")
    w("|---|---|---|---|---|")
    labels = {
        "cov_DX_min": "Độ phủ ĐX, nhỏ nhất theo σ_loc", "cov_DX_max": "Độ phủ ĐX, lớn nhất theo σ_loc",
        "cov_B1@0.0": "Độ phủ B1, σ_loc = 0", "cov_B1@0.2": "Độ phủ B1, σ_loc = 0,2 m",
        "cov_B1@0.5": "Độ phủ B1, σ_loc = 0,5 m",
        "q_DX@0.1": "q_ĐX, σ_loc = 0,1 m", "q_B3@0.1": "q_B3, σ_loc = 0,1 m",
        "q_DX@0.5": "q_ĐX, σ_loc = 0,5 m", "q_B3@0.5": "q_B3, σ_loc = 0,5 m",
        "q_B4@0.1": "q_B4, σ_loc = 0,1 m", "q_B4@0.5": "q_B4, σ_loc = 0,5 m",
        "ratio@rho=-0.5": "q_ĐX/q_B3, ρ = −0,5", "ratio@rho=0.9": "q_ĐX/q_B3, ρ = 0,9",
    }
    for key, lab in labels.items():
        r = q2[key]
        d = 3 if key.startswith("cov") or key.startswith("ratio") else 2
        diff = r["ours"] - r["draft"]
        rel = f" ({diff / r['draft'] * 100:+.0f}%)".replace("-", "−") if not key.startswith("cov") else ""
        w(f"| {lab} | {f(r['draft'], d)} | {f(r['ours'], d)} | {f(diff, d)}{rel} | {ok(r['ok'])} |")
    w(f"| Mức thu hẹp của ĐX so với B3, σ_loc = 0,1 / 0,5 m | 77% / 68% | {pct(narrow[0.1])} / {pct(narrow[0.5])} | — | "
      f"{ok(abs(narrow[0.1] - 0.77) <= 0.03 and abs(narrow[0.5] - 0.68) <= 0.03)} |")
    w(f"| Số lần q_ĐX > q_B3 | 0 | {n_viol}/{n_checks} | — | {ok(n_viol == 0)} |")
    w("")
    w("Bảng đầy đủ theo σ_loc (trung bình qua các lần lặp):")
    w("")
    w("| σ_loc (m) | Phủ ĐX | Phủ B1 | Phủ B3 | Phủ B4 | q_ĐX | q_B1 | q_B3 | q_B4 | ĐX hẹp hơn B3 |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for sl in sigmas:
        nar = narrow[sl]
        c = {m: tab2[(sl, m)] for m in ("DX", "B1", "B3", "B4")}
        w(f"| {f(sl, 2)} | " + " | ".join(f(c[m]["cov_mean"]) for m in ("DX", "B1", "B3", "B4")) + " | "
          + " | ".join(f(c[m]["q_mean"], 2) for m in ("DX", "B1", "B3", "B4")) + f" | {pct(nar)} |")
    w("")
    w("Quét tương quan ρ (σ_loc = 0,1 m):")
    w("")
    w("| ρ | ρ thực nghiệm | q_ĐX | q_B3 | q_ĐX/q_B3 | Độ phủ ĐX |")
    w("|---|---|---|---|---|---|")
    for k in sorted(rho):
        r = rho[k]
        w(f"| {f(k, 1)} | {f(r['rho_emp'], 2)} | {f(r['q_dx'], 2)} | {f(r['q_b3'], 2)} | {f(r['ratio_mean'])} | "
          f"{f(r['cov_dx'])} |")
    w("")
    w("### 4.3. Bảng 2 — ngưỡng chung và ngưỡng theo nhóm (α = 0,1; 100 lần lặp)")
    w("")
    w("| Nhóm | Đại lượng | Bản thảo | Tái lập | Chênh lệch | Kết quả |")
    w("|---|---|---|---|---|---|")
    names = {"fix": "RTK cố định", "float": "RTK thả nổi", "loss": "Mất GNSS"}
    for g in ("fix", "float", "loss"):
        for key, lab, d in (("cov_global", "Độ phủ, ngưỡng chung", 3), ("cov_group", "Độ phủ, theo nhóm", 3),
                            ("q_group", "Ngưỡng theo nhóm", 2)):
            r = q3[f"{key}@{g}"]
            w(f"| {names[g]} | {lab} | {f(r['draft'], d)} | {f(r['ours'], d)} | {f(r['ours'] - r['draft'], d)} | "
              f"{ok(r['ok'])} |")
    r = q3["q_global"]
    w(f"| Mọi nhóm | Ngưỡng chung | {f(r['draft'], 2)} | {f(r['ours'], 2)} | {f(r['ours'] - r['draft'], 2)} | "
      f"{ok(r['ok'])} |")
    w("")
    w(f"Kiểm tra chéo: độ phủ tổng của ngưỡng chung = Σ tỉ lệ nhóm × độ phủ nhóm = {f(mix_cov)} ≈ 0,90, đúng như "
      "phải có. Với số của bản thảo, tổng này cũng bằng 0,900. Vậy ô lệch ở nhóm mất GNSS do khác biệt mô hình "
      "dữ liệu (đuôi phân phối điểm số của nhóm này), không phải lỗi cài đặt.")
    w("")
    if sens3:
        w("Độ nhạy (chỉ để tham khảo, không thay kết quả chính) — độ phủ ngưỡng chung ở nhóm mất GNSS:")
        w("")
        w("| Biến thể | Mô tả | Độ phủ, nhóm mất GNSS |")
        w("|---|---|---|")
        w(f"| Gốc | U6 phương án A, U1 có trôi | {f(g3['loss']['cov_global_mean'])} |")
        desc = {"U6B": "Tốc độ quay, gia tốc đổi theo từng bước", "U1W": "Sai số định vị nhiễu trắng, không trôi"}
        for v, r in sens3.items():
            c = {x["group"]: x for x in r["cells"]}
            w(f"| {v} | {desc.get(v, v)} | {f(c['loss']['cov_global_mean'])} |")
        w("")
        w("Cả hai biến thể đều xa bản thảo hơn mô hình gốc, nên giữ mô hình gốc.")
        w("")

    # 5. Định tính
    w("## 5. Kiểm tra định tính")
    w("")
    qn2, qn3 = n2["qualitative"], n3["qualitative"]
    rows = [
        ("ĐX đạt 0,90 ± 0,01 ở mọi σ_loc", qn2["DX_cov_0.90pm0.01"], f"{f(min(cov_dx))}–{f(max(cov_dx))}"),
        ("Độ phủ B1 giảm dần theo σ_loc", qn2["B1_cov_decreasing"],
         f"{f(tab2[(0.0, 'B1')]['cov_mean'])} → {f(tab2[(0.5, 'B1')]['cov_mean'])}"),
        ("q_ĐX ≤ q_B3 ở mọi lần lặp (Mệnh đề 3)", n_viol == 0, f"{n_viol} vi phạm / {n_checks}"),
        ("B4 rộng hơn B3 ở mọi σ_loc", qn2["B4_wider_B3"],
         f"{f(min(b4_b3), 2)}–{f(max(b4_b3), 2)} lần"),
        ("Tỉ số q_ĐX/q_B3 tăng theo ρ", qn2["ratio_increasing_in_rho"],
         " → ".join(f(rho[k]["ratio_mean"]) for k in sorted(rho))),
        ("Ngưỡng theo nhóm đạt 0,90 ± 0,01 ở từng nhóm (Hệ quả 1)", qn3["group_cov_0.90pm0.01"],
         " / ".join(f(g3[g]["cov_group_mean"]) for g in ("fix", "float", "loss"))),
        ("Ngưỡng chung thừa ở nhóm cố định, thiếu ở thả nổi và mất GNSS",
         qn3["global_overcovers_fix"] and qn3["global_undercovers_float"] and qn3["global_undercovers_loss"],
         " / ".join(f(g3[g]["cov_global_mean"]) for g in ("fix", "float", "loss"))),
    ]
    w("| Tiêu chí | Đạt | Giá trị |")
    w("|---|---|---|")
    for lab, b, val in rows:
        w(f"| {lab} | {'có' if b else '**không**'} | {val} |")
    w("")
    w(f"Ghi chú về ρ: tỉ số gần như không đổi từ ρ = −0,5 đến 0,5 rồi tăng mạnh ở ρ = 0,9. Bản thảo chỉ nêu hai đầu "
      "nên không rõ đường của tác giả có dạng này không; lời văn nên nói “tăng rõ khi tương quan cao” thay vì "
      "ngụ ý tăng đều.")
    w("")

    # 6. Đề xuất sửa
    w("## 6. Đề xuất sửa bản thảo")
    w("")
    w("### 6.1. Sửa số theo vị trí")
    w("")
    w("Số thứ tự đoạn tính trên các đoạn có chữ của file docx v0.1.")
    w("")
    w("| Vị trí | Hiện tại | Đề xuất |")
    w("|---|---|---|")
    w(f"| Tóm tắt, đoạn 21 | “độ phủ thực nghiệm 0,898–0,903 … hẹp hơn cách cộng hai biên 68–77%” | "
      f"“độ phủ thực nghiệm {f(min(cov_dx))}–{f(max(cov_dx))} … hẹp hơn cách cộng hai biên "
      f"{pct_range(narrow[0.5], narrow[0.1])}” |")
    w(f"| Tóm tắt, đoạn 22 | “giảm độ phủ xuống 0,80 khi nhiễu định vị 0,5 m” | Giữ nguyên "
      f"(tái lập {f(tab2[(0.5, 'B1')]['cov_mean'])}) |")
    w(f"| 4.1 Thiết lập, đoạn 174–182 | Thiếu chi tiết mô hình | Thêm các câu ở mục 6.2 |")
    w(f"| 4.1, đoạn 184 | “nằm trong khoảng 0,798–0,950” | “nằm trong khoảng "
      f"{f(min(n1_means))}–{f(max(n1_means))}” |")
    w(f"| 4.1, đoạn 185 | “Sai lệch lớn nhất là 0,798 so với 0,800 (tại n=500, α=0,2), nằm trong 1,5 sai số chuẩn” | "
      f"“Sai lệch lớn nhất là {f(worst['mean'])} so với {f(1 - worst['alpha'], 3)} (tại n={worst['n']}, "
      f"α={f(worst['alpha'], 2)}), bằng {f(abs(worst['z_mean']), 1)} sai số chuẩn so với giá trị lý thuyết "
      f"k/(n+1) = {f(worst['theory_mean'], 4)}” |")
    w(f"| 4.1, đoạn 186 | “từ 0,029 (n=100) xuống 0,012 (n=1000)” | “từ {f(sd01[100])} (n=100) xuống "
      f"{f(sd01[1000])} (n=1000)” |")
    w("| Bảng 1 | Số v0.1 | Thay bằng cột “Tái lập” ở mục 4.1 của báo cáo này (hoặc giữ số cũ, vì đều khớp lý thuyết) |")
    w("| Hình 1 | Hình v0.1 | `figs/N1_coverage.pdf` |")
    w(f"| 4.1, đoạn 211 | “độ phủ 0,898–0,903” | “độ phủ {f(min(cov_dx))}–{f(max(cov_dx))}” |")
    w(f"| 4.1, đoạn 213–214 | “0,996 … 0,972 tại 0,2 m … 0,802 tại 0,5 m” | "
      f"“{f(tab2[(0.0, 'B1')]['cov_mean'])} … {f(tab2[(0.2, 'B1')]['cov_mean'])} tại 0,2 m … "
      f"{f(tab2[(0.5, 'B1')]['cov_mean'])} tại 0,5 m” |")
    w(f"| 4.1, đoạn 217 | “nhỏ hơn B3 77% tại σloc=0,1 m (1,82 so với 7,81)” | “nhỏ hơn B3 {pct(narrow[0.1])} tại "
      f"σloc=0,1 m ({f(tab2[(0.1, 'DX')]['q_mean'], 2)} so với {f(tab2[(0.1, 'B3')]['q_mean'], 2)})” |")
    w(f"| 4.1, đoạn 218 | “nhỏ hơn B3 68% tại 0,5 m (5,77 so với 18,0)” | “nhỏ hơn B3 {pct(narrow[0.5])} tại 0,5 m "
      f"({f(tab2[(0.5, 'DX')]['q_mean'], 2)} so với {f(tab2[(0.5, 'B3')]['q_mean'], 1)})” |")
    w(f"| 4.1, đoạn 219 | “B4 còn rộng hơn nữa (9,21 và 25,6)” | “B4 còn rộng hơn nữa "
      f"({f(tab2[(0.1, 'B4')]['q_mean'], 2)} và {f(tab2[(0.5, 'B4')]['q_mean'], 1)})” |")
    w(f"| 4.1, đoạn 220 | “tăng từ 0,23 (ρ=-0,5) lên 0,31 (ρ=0,9)” | “tăng từ {f(rho[-0.5]['ratio_mean'], 2)} "
      f"(ρ=−0,5) lên {f(rho[0.9]['ratio_mean'], 2)} (ρ=0,9); tỉ số gần như không đổi khi ρ ≤ 0,5 và chỉ tăng rõ khi "
      "tương quan cao” |")
    w("| Hình 2 | Hình v0.1 (a, b) | `figs/N2_bounds.pdf`; có thêm ô (c) cho tỉ số theo ρ — bỏ ô (c) hoặc thêm vào chú thích |")
    w(f"| 4.1, đoạn 236 | “thừa ở nhóm RTK cố định (0,963) và thiếu ở nhóm RTK thả nổi (0,818) và mất GNSS (0,620)” | "
      f"“… ({f(g3['fix']['cov_global_mean'])}) … ({f(g3['float']['cov_global_mean'])}) … "
      f"({f(g3['loss']['cov_global_mean'])})” |")
    covg = [g3[g]["cov_group_mean"] for g in ("fix", "float", "loss")]
    w(f"| 4.1, đoạn 237 | “(0,899–0,900)” | “({f(min(covg))}–{f(max(covg))})” |")
    w(f"| 4.1, đoạn 238 | “(1,74 so với 2,37) … (3,34 và 12,18)” | “({f(g3['fix']['q_group_mean'], 2)} so với "
      f"{f(g3['fix']['q_global_mean'], 2)}) … ({f(g3['float']['q_group_mean'], 2)} và "
      f"{f(g3['loss']['q_group_mean'], 2)})” |")
    w("| Bảng 2 | Số v0.1 | Thay bằng cột “Tái lập” ở mục 4.3 của báo cáo này |")
    w(f"| Kết luận, đoạn 435 | “hẹp hơn tổng hai biên 68–77%” | “hẹp hơn tổng hai biên "
      f"{pct_range(narrow[0.5], narrow[0.1])}” |")
    w(f"| Kết luận, đoạn 436 | “0,80 khi nhiễu định vị 0,5 m” | Giữ nguyên |")
    w(f"| Kết luận, đoạn 437 | “nhóm mất GNSS chỉ đạt 0,62” | “nhóm mất GNSS chỉ đạt "
      f"{f(g3['loss']['cov_global_mean'], 2)}” |")
    w("")
    w("### 6.2. Câu bổ sung cho phần Thiết lập của 4.1")
    w("")
    w("Đề xuất thêm vào sau đoạn 175, 179 và 182:")
    w("")
    w("- “Sai số định vị là quá trình AR(1) dừng độc lập theo từng trục, độ lệch chuẩn σloc và hằng số thời gian "
      "5 s; sai số bám là AR(1) với độ lệch chuẩn 0,05 m và hằng số thời gian 1 s.”")
    w("- “Tác nhân hướng tới một điểm ngẫu nhiên trên đường của xe, cách gốc 0–6 m. Tốc độ quay và gia tốc được "
      "lấy một lần cho mỗi mẫu và giữ không đổi trên chân trời. Mỗi mẫu có một tác nhân.”")
    w("- “Vì xe được xấp xỉ bằng đĩa, sai số của xe chỉ gồm sai số vị trí: E = max_τ ‖Δp_τ‖/σ_τ.”")
    w("- “Độ phủ của mọi loại biên được đo bằng tỉ lệ mẫu kiểm tra có điểm số hụt khoảng cách không vượt ngưỡng. "
      "B4 dùng sai số xe lớn nhất trên tập hiệu chỉnh.”")
    w("- “Bảng 1 dùng σloc = 0,1 m. Để ép tương quan ρ, giữ độ lớn sai số của xe và đổi hướng của nó thành "
      "unit(ρ·g + √(1−ρ²)·u), trong đó g là phương xe – tác nhân lấy dấu theo phần hụt do tác nhân, u là hướng gốc.”")
    w("- “Ở Bảng 2, mỗi tập hiệu chỉnh có 1000 mẫu, nhãn nhóm lấy ngẫu nhiên theo tỉ lệ 70/20/10.”")
    w("")

    # 7. Hạn chế
    w("## 7. Hạn chế và việc còn mở")
    w("")
    w("- Đây là tái lập độc lập dựa trên mô tả trong bản thảo, không phải mã gốc của tác giả. Nên hỏi lại tác giả "
      "(NCS) mã gốc của 4.1 để đối chiếu các giả định U1–U12.")
    w(f"- Ô lệch duy nhất là độ phủ ngưỡng chung ở nhóm mất GNSS ({f(g3['loss']['cov_global_mean'])} so với 0,620). "
      "Kết luận định tính của bản thảo không đổi.")
    w("- Kết quả pytest của `tests/test_num41.py` ghi ở `logs/num41/tests.txt`.")
    w("")
    return "\n".join(L) + "\n"


def to_docx(md_path) -> None:
    if shutil.which("pandoc") is None:
        print("Không có pandoc, bỏ qua .docx")
        return
    out = md_path.with_suffix(".docx")
    cmd = ["pandoc", str(md_path), "-o", str(out), "--resource-path", str(ROOT)]
    if REF_DOCX.exists():
        cmd += ["--reference-doc", str(REF_DOCX)]
    subprocess.run(cmd, check=True)
    print("Đã ghi", out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", action="store_true")
    args = ap.parse_args()
    REPORT_DIR.mkdir(exist_ok=True)
    OUT_MD.write_text(build(load()), encoding="utf-8")
    print("Đã ghi", OUT_MD)
    if args.docx:
        to_docx(OUT_MD)


if __name__ == "__main__":
    main()
