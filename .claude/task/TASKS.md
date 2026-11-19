# DANH SÁCH VIỆC — Mô phỏng phương án cũ / mới
*Phiên bản 0.5 — 19/11/2026 — T1–T14 đã hoàn thành; T15–T21 (CARLA) là đề xuất, chưa duyệt*
*Phiên bản 0.4 — 16/11/2026 — T1–T14 đã hoàn thành và kiểm tra nghiệm thu đầy đủ (v0.1 + mở rộng v0.2)*

Trạng thái: ☐ chưa làm · ◐ đang làm · ☑ xong

## T1. Lõi mô phỏng 2D dùng chung — ☑

- [x] Mô hình xe đạp động học "thật": trễ chấp hành, giới hạn tốc độ đánh lái, sai số hệ số lái
- [x] Bộ phát sai số định vị: RTK cố định / RTK thả nổi / mất GNSS
- [x] Điều kiện D3 (trượt bánh), D4 (trễ cố định), D5 (trễ ngẫu nhiên)
- [x] Tác nhân dạng tập đĩa cứng; kịch bản S1–S4
- [x] Dự báo vận tốc hằng; planner Frenet; Pure Pursuit; quỹ đạo dự phòng
- [x] Thống kê sau H bước: d̂, d, phần hụt, A (theo tâm và Hausdorff), E, phân tách có dấu
- [x] Sửa bám vận tốc (thêm bù trước); kiểm tra sai số xe ở D0 < 0,5 m tại 3 s (chu kỳ không đổi mục tiêu E_30 mean=0,293 m, median=0,184 m)
- [x] Kiểm tra 24 tổ hợp S×D chạy không lỗi; ghi tỉ lệ va chạm của B0 (10,6%)

**Kết quả:** `sim/core.py`, `sim/common.py`

## T2. Mô phỏng A — phương án cũ (v0.1) — ☑

- [x] Điểm số R theo (5), gán R = −∞ cho chu kỳ không có tác nhân
- [x] Lấy thưa mỗi 2 s
- [x] σ_τ = 0,05 + 0,04τ
- [x] Sai số tác nhân theo tâm (chỉ tịnh tiến)
- [x] Thuật toán 1 (hiệu chỉnh lặp 3 khối) và chứng nhận có điều kiện, thử lại tối đa 3 lần
- [x] Các phương pháp B0–B6, ĐX-1, ĐX-2, ĐX-3
- [x] Chạy tập kiểm tra D0–D5 × S1–S4

**Kết quả:** `sim/run_old.py`, `logs/old/`

## T3. Mô phỏng B — phương án mới — ☑

- [x] Chỉ hiệu chỉnh trên chu kỳ có tác nhân
- [x] Lấy thưa mỗi 3 s; thêm chỉ tiêu theo lượt chạy
- [x] σ_τ ước lượng trên hạt giống 200–249 (phân vị 90%, cận dưới 0,05 m, đơn điệu)
- [x] Sai số tác nhân theo cận Hausdorff
- [x] Chứng nhận PAC (δ = 0,05, Bonferroni theo số lần thử)
- [x] Thêm đối chứng B3′
- [x] Báo cáo riêng chu kỳ dự phòng
- [x] ACI chỉ cập nhật trên chu kỳ có tác nhân
- [x] Quét α ∈ {0,01; 0,02; 0,05; 0,1; 0,2} cho B1, B3′, ĐX-2

**Kết quả:** `sim/run_new.py`, `logs/new/`

## T4. Ghi log hai phần — ☑

- [x] `config.json`, `calibration.json`, `cycles.csv`, `episodes.csv`, `summary.json` cho mỗi phương án
- [x] KTC Clopper–Pearson cho mọi tỉ lệ

**Kết quả:** `logs/old/`, `logs/new/`

## T5. Phân tích và vẽ hình — ☑

- [x] H1: độ phủ theo D0–D5 (cũ / mới)
- [x] H2: tác động của mẫu −∞ và của lấy mẫu chồng cửa sổ
- [x] H3: B3 so với B3′ so với ĐX-1 (tách hiệu ứng chiếu khỏi hiệu ứng gộp)
- [x] H4: đánh đổi an toàn – hiệu quả khi quét α
- [x] H5: chứng nhận có điều kiện so với PAC (tỉ lệ chứng nhận sai)
- [x] H6: ĐX-2 theo nhóm định vị
- [x] Kiểm định Wilcoxon / McNemar, hiệu chỉnh Holm

**Kết quả:** `sim/analyze.py`, `figs/*.png`, `figs/*.pdf`

## T6. Báo cáo và đề xuất sửa đổi — ☑

- [x] Viết theo cấu trúc SPEC §7
- [x] Bảng đề xuất sửa theo từng mục của bản thảo, kèm câu chữ gợi ý
- [x] Phát biểu lại Định lý 2

**Kết quả:** `sim/report.py`, `report/BAO_CAO_KET_QUA_VA_DE_XUAT_SUA_DOI.md`, `report/BAO_CAO_KET_QUA_VA_DE_XUAT_SUA_DOI.docx`

## T7. Kiểm tra — ☑

- [x] Chạy lại một phần từ hạt giống, so khớp `summary.json` và `episodes.csv` (< 1e-9)
- [x] Đối chiếu từng con số trong báo cáo với log
- [x] Mở báo cáo và các hình để soát trình bày
- [x] Đóng gói `sim.zip` (mã, README, log, hình, báo cáo)

---

# Mở rộng v0.2 — kịch bản và trường hợp kiểm thử bổ sung

## T8. Bộ kiểm thử mã tự động (G7) — ☑

- [x] Tạo `tests/` và cấu hình `pytest`; ghi kết quả ra `logs/ext/tests.txt`
- [x] TC-01 hồi quy: B0, ĐX-1 trên 5 hạt giống IN khớp `logs/new` (< 1e-9)
- [x] TC-02 khoảng cách hộp–đĩa so với lời giải lấy mẫu dày (1.000 cấu hình)
- [x] TC-03 A_h ≥ A_c; A_h = A_c với tác nhân 1 đĩa
- [x] TC-04 đồng nhất thức a + b = d̂ − d
- [x] TC-05 độ phủ phân vị phù hợp trên dữ liệu tổng hợp (Gauss, Student-t, Pareto)
- [x] TC-06 hàm k_PAC: n_min = 39, k(187) = 178
- [x] TC-07 Monte Carlo PAC M = 3: tỉ lệ chứng nhận sai ≤ δ
- [x] TC-08 ACI không cập nhật trên chu kỳ trống (chế độ B)
- [x] TC-09 ACI trên chuỗi dịch phân phối: độ phủ dài hạn 1−α ± 0,02
- [x] TC-10 lấy thưa 3 s không chồng cửa sổ
- [x] TC-11 các khối hạt giống không giao nhau (kể cả 700–1399)
- [x] TC-12 E₃₀ ở D0 đường thẳng (mở vòng): trung bình < 0,3 m, P95 < 0,5 m
- [x] TC-18 tất định: 1 và 2 tiến trình cho kết quả giống hệt

**Kết quả:** `tests/test_geometry.py`, `tests/test_conformal.py`, `tests/test_pac.py`, `tests/test_aci.py`, `tests/test_sampling.py`, `tests/test_regression.py`

## T9. Mở rộng lõi mô phỏng (G8) — ☑

- [x] Đường tham chiếu tổng quát (polyline/cung tròn); Frenet và Pure Pursuit trên đường cong (S7)
- [x] Vật cản tĩnh và kiểm tra đường ngắm; tác nhân chỉ vào 𝒥_t khi lộ diện (S5); cờ `unavoidable`
- [x] Xe máy chen làn có dao động ngang AR(1) (S6)
- [x] Sinh 4–6 tác nhân hỗn hợp, xe máy theo bầy (S8)
- [x] Tác nhân phản ứng theo TTC: nhường 0,6 / tăng tốc 0,4 (S9)
- [x] Người đi bộ zigzag, xe máy rẽ đột ngột (S10)
- [x] D6 (D1 + trễ 100 ms), D7 (mất GNSS 15–20 s), D8 (nhãn sai 30%), D9 (đường trơn), D10 (nhận thức suy giảm)
- [x] Nhánh mở vòng đo E_track; ghi thêm E_replan = E − E_track
- [x] Thêm cột vào `cycles.csv`: split, n_agents, occluded_before, curvature, e_track, e_replan
- [x] Viết TC-13 (đường cong R = 25 m), TC-14 (che khuất), TC-15 (S9), TC-16 (D8), TC-17 (dự phòng ở D9)
- [x] Chạy lại TC-01 xác nhận S1–S4 × D0–D5 không đổi; chạy thử 110 ô S×D không lỗi

**Kết quả:** `sim/core.py` (mở rộng), `sim/scenarios_ext.py`, `sim/conditions_ext.py`

## T10. Chạy tập dịch chuyển phân phối (G9) — ☑

- [x] OOD-S: S5–S10 × D0–D5, hạt giống 700–709, giữ q đã chứng nhận ở v0.1
- [x] OOD-D: S1–S4 × D6–D10, hạt giống 700–709
- [x] OOD-SD: S5–S10 × D6–D10, hạt giống 700–709
- [x] RECAL: hiệu chỉnh lặp (800–949) và chứng nhận PAC (950–999) trên S1–S10 × D0–D10 trộn; kiểm tra trên 710–719
- [x] Ghi `logs/ext/` (config, calibration_recal, cycles, episodes, summary)

**Kết quả:** `sim/run_ext.py`, `logs/ext/`

## T11. Thí nghiệm bổ sung E1–E9 (G10) — ☑

Thứ tự ưu tiên: E1 → E2 → E4 → E6 → E3 → E5 → E7 → E8 → E9.

- [x] E1 so sánh ở cùng độ phủ: quét 8 mức α cho B1, B3′, ĐX-1, ĐX-2; nội suy t_end, m₃ₛ tại 0,90/0,95; KTC bootstrap → `alpha_sweep_ext.csv`
- [x] E2 ablation ACI 2×2 (chu kỳ trống × γ); ghi vết α_t → `aci_trace.csv`
- [x] E4 khối chuyên biệt D2 (1000–1149 hiệu chỉnh, 1150–1299 chứng nhận); PAC tổng thể so với PAC riêng nhóm → `calibration_d2.json`
- [x] E6 tách E_track / E_replan theo D và S
- [x] E3 lực kiểm định PAC: n_cert × M × δ (Monte Carlo) và 1 điểm chạy thật → `pac_power.csv`
- [x] E5 lấy mẫu Δ ∈ {3, 4, 6} s và "1 chu kỳ/lượt"; hiệu chỉnh theo khối → `thinning_ext.csv`
- [x] E7 quét d_s ∈ {0,5; 1,0}, lưới 351/663 ứng viên, làn 3,0 m
- [x] E8 σ_τ theo từng kịch bản (1300–1399) → `sigma_by_scn.csv`
- [x] E9 mở rộng tập IN lên 30 hạt giống (500–529) cho B1, ĐX-1, ĐX-2, ĐX-3

**Kết quả:** `sim/experiments_ext.py`, các file CSV/JSON trong `logs/ext/`

## T12. Phân tích và vẽ hình mở rộng (G11) — ☑

- [x] H7: độ phủ theo tập IN / OOD-S / OOD-D / OOD-SD / RECAL cho từng phương pháp
- [x] H8: đường đánh đổi ở cùng độ phủ, có KTC bootstrap (E1)
- [x] H9: vết α_t của ACI theo 4 biến thể (E2)
- [x] H10: lực kiểm định PAC và độ phủ hậu chứng nhận theo n_cert (E3)
- [x] H11: phân tách E_track / E_replan theo D, S (E6)
- [x] Kiểm định McNemar/Wilcoxon/Holm cho từng tập OOD

**Kết quả:** `sim/analyze_ext.py`, `figs/H7..H11.{png,pdf}`, `figs/analysis_ext.json`

## T13. Báo cáo mở rộng (G11) — ☑

- [x] Viết `report/BAO_CAO_MO_RONG_v0.2.md` (và `.docx`) theo SPEC §9.9
- [x] Bảng kết quả TC-01..TC-18
- [x] Cập nhật bảng đề xuất sửa bản thảo: cách trình bày ưu thế ĐX (theo E1), Mục 6.8 về ACI (theo E2), cỡ mẫu chứng nhận cho CARLA (theo E3, E4), định nghĩa sai số bám (theo E6), giả thiết A1 (theo E5)
- [x] Sửa lỗi trình bày v0.1: Mục 6.5 ghi "4.000 kịch bản" cho panel (b), trong khi panel này dùng 3.000

**Kết quả:** `sim/report_ext.py`, `report/BAO_CAO_MO_RONG_v0.2.{md,docx}`

## T14. Kiểm tra nghiệm thu mở rộng (G12) — ☑

- [x] `pytest` đạt TC-01..TC-18
- [x] `python run_ext.py --seed-base 0` sinh lại `logs/ext/` và H7–H11
- [x] `logs/old`, `logs/new` không bị ghi đè
- [x] Đối chiếu từng con số trong báo cáo mở rộng với `logs/ext/`
- [x] Cập nhật `README.md` và đóng gói lại `sim.zip`

---

# Mở rộng: chuyển sang CARLA (v0.5, đề xuất, chưa duyệt)

## T15. Hạ tầng CARLA (G13) — ☐

- [ ] Cài CARLA server và client API (khớp phiên bản Python), kiểm tra GPU
- [ ] Bật synchronous mode: dt = 0,05 s; lập kế hoạch 10 Hz
- [ ] Chỉnh xe: wheelbase 2,875 m, V_MAX 8,3 m/s, góc lái tối đa
- [ ] Đo trễ lệnh thật của xe CARLA, so với BASE_DELAY = 50 ms

## T16. Cầu nối mô phỏng — CARLA (G14) — ☐

- [ ] Đọc tư thế thật của xe và tác nhân mỗi bước
- [ ] Gửi lệnh qua `VehicleControl`; nối bộ Frenet và pure pursuit hiện có
- [ ] Ghi log đúng định dạng `analyze.py` (thư mục `logs/carla_m1/`)
- [ ] Chạy S1 + D0; `analyze.py` đọc log không phải sửa
- [ ] Test: tái lập được cùng hạt giống (TC mới cho CARLA)

## T17. Kịch bản và điều kiện trên CARLA (G15) — ☐

- [ ] Dựng S1–S4 trong CARLA (walker AI, traffic manager)
- [ ] Bộ phát sai số định vị D1–D5 cài vào dữ liệu CARLA (CARLA mặc định không nhiễu)
- [ ] Đo thời gian lập kế hoạch cộng tính biên; yêu cầu nhỏ hơn 0,1 s
- [ ] Chạy đủ S×D không lỗi

## T18. Chốt tham số (G16) — ☐

- [ ] Điền các ô [X] của bảng §4.2: mức nhiễu định vị (cố định, thả nổi, mất GNSS) và d_s, có căn cứ
- [ ] Chọn cỡ mẫu chứng nhận và số hạt giống theo E3; lập kế hoạch theo khối có checkpoint
- [ ] Chọn lưới vận tốc (0,5 hay 1,0 m/s) theo kết quả T17
- [ ] Chốt dùng phương án B cho CARLA

## T19. Chạy M1: ground truth + nhiễu, dự báo vận tốc hằng (G17) — ☐

- [ ] Chạy đầy đủ theo bảng tham số T18
- [ ] So với kết quả 2D: độ phủ, độ rộng biên, tỉ lệ dự phòng, trễ
- [ ] Kiểm tra độ phủ theo hạt giống và điều kiện hoán đổi được

## T20. Chạy M2 và M3 (G18) — ☐

- [ ] M2: thay dự báo bằng Trajectron++ (hoặc mô hình học được); chỉ thay đầu vào dự báo
- [ ] Đo ảnh hưởng của dự báo tốt hơn lên độ rộng biên và độ phủ
- [ ] M3 (tùy chọn, cần quyết định): detector và tracker thật; ghi bỏ sót, nhãn sai, che khuất
- [ ] Nếu bỏ M3: ghi giới hạn vào báo cáo

## T21. Báo cáo CARLA (G19) — ☐

- [ ] Báo cáo kết quả M1, M2 (và M3), so với 2D
- [ ] Đề xuất sửa bản thảo: thêm bảng mô hình sai số vào §4.2, điền [X], câu dẫn ở §2.3
- [ ] Cập nhật README, đóng gói, đối chiếu số liệu với log
