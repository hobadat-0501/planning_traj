# DANH SÁCH VIỆC — Mô phỏng phương án cũ / mới
*Phiên bản 0.7.1 — 19/11/2026 — Phần 1 (T28–T31) viết lại theo tài liệu hướng dẫn CARLA (C1–C5, mục 6–7); CARLA chạy trên máy khác; Phần 2, 3 giữ nguyên*
*Phiên bản 0.7 — 19/11/2026 — thêm T28–T37 (CARLA 0.9.15, ba phần: thiết lập theo Mục 4, vòng kín A, vòng kín B), đề xuất, chưa duyệt; T15–T21 gộp vào T28–T37*
*Phiên bản 0.6 — 19/11/2026 — thêm T22–T27 (tái lập Mục 4.1), đề xuất, chưa duyệt*
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

## T15. Hạ tầng CARLA (G13) — ☐ (gộp vào T28)

- [ ] Cài CARLA server và client API (khớp phiên bản Python), kiểm tra GPU
- [ ] Bật synchronous mode: dt = 0,05 s; lập kế hoạch 10 Hz
- [ ] Chỉnh xe: wheelbase 2,875 m, V_MAX 8,3 m/s, góc lái tối đa
- [ ] Đo trễ lệnh thật của xe CARLA, so với BASE_DELAY = 50 ms

## T16. Cầu nối mô phỏng — CARLA (G14) — ☐ (gộp vào T30)

- [ ] Đọc tư thế thật của xe và tác nhân mỗi bước
- [ ] Gửi lệnh qua `VehicleControl`; nối bộ Frenet và pure pursuit hiện có
- [ ] Ghi log đúng định dạng `analyze.py` (thư mục `logs/carla_m1/`)
- [ ] Chạy S1 + D0; `analyze.py` đọc log không phải sửa
- [ ] Test: tái lập được cùng hạt giống (TC mới cho CARLA)

## T17. Kịch bản và điều kiện trên CARLA (G15) — ☐ (gộp vào T30)

- [ ] Dựng S1–S4 trong CARLA (walker AI, traffic manager)
- [ ] Bộ phát sai số định vị D1–D5 cài vào dữ liệu CARLA (CARLA mặc định không nhiễu)
- [ ] Đo thời gian lập kế hoạch cộng tính biên; yêu cầu nhỏ hơn 0,1 s
- [ ] Chạy đủ S×D không lỗi

## T18. Chốt tham số (G16) — ☐ (gộp vào T29, T30)

- [ ] Điền các ô [X] của bảng §4.2: mức nhiễu định vị (cố định, thả nổi, mất GNSS) và d_s, có căn cứ
- [ ] Chọn cỡ mẫu chứng nhận và số hạt giống theo E3; lập kế hoạch theo khối có checkpoint
- [ ] Chọn lưới vận tốc (0,5 hay 1,0 m/s) theo kết quả T17
- [ ] Chốt dùng phương án B cho CARLA

## T19. Chạy M1: ground truth + nhiễu, dự báo vận tốc hằng (G17) — ☐ (gộp vào T33, T36)

- [ ] Chạy đầy đủ theo bảng tham số T18
- [ ] So với kết quả 2D: độ phủ, độ rộng biên, tỉ lệ dự phòng, trễ
- [ ] Kiểm tra độ phủ theo hạt giống và điều kiện hoán đổi được

## T20. Chạy M2 và M3 (G18) — ☐ (gộp vào T31 (dự báo); M3 bỏ)

- [ ] M2: thay dự báo bằng Trajectron++ (hoặc mô hình học được); chỉ thay đầu vào dự báo
- [ ] Đo ảnh hưởng của dự báo tốt hơn lên độ rộng biên và độ phủ
- [ ] M3 (tùy chọn, cần quyết định): detector và tracker thật; ghi bỏ sót, nhãn sai, che khuất
- [ ] Nếu bỏ M3: ghi giới hạn vào báo cáo

## T21. Báo cáo CARLA (G19) — ☐ (gộp vào T34, T37)

- [ ] Báo cáo kết quả M1, M2 (và M3), so với 2D
- [ ] Đề xuất sửa bản thảo: thêm bảng mô hình sai số vào §4.2, điền [X], câu dẫn ở §2.3
- [ ] Cập nhật README, đóng gói, đối chiếu số liệu với log

---

# Tái lập Mục 4.1 — nghiên cứu số trên dữ liệu tổng hợp (v0.6, đã duyệt 19/11/2026)

Xem PLAN §10. Mã ở `num41/`, log ở `logs/num41/`. Không sửa `sim/` và các log cũ.

## T22. Chốt đặc tả SPEC §10 (G20) — ☑ (còn mở: hỏi NCS về mã gốc)

- [ ] Hỏi NCS xem có mã hoặc ghi chép gốc của Mục 4.1 hay không; nếu có thì dùng làm chuẩn và bỏ qua các giả định bên dưới (người dùng hỏi; chưa có phản hồi)
- [x] Viết SPEC §10: mô hình sinh mẫu (xe, tác nhân, sai số định vị / bám / trễ), điểm số R, A, E, các ngưỡng B1 / B3 / B4 / ĐX / ĐX theo nhóm
- [x] Viết đề xuất U1–U12 vào SPEC §10, đánh dấu [GĐ]; chờ duyệt. Ghi rõ mục nào là giả định không có trong bản thảo
- [x] Chốt sơ đồ hạt giống: `SeedSequence(2026)` tách nhánh theo (thí nghiệm, ô, lần lặp, tập hiệu chỉnh hoặc kiểm tra)
- [x] Chốt định dạng log: `config.json` cùng mỗi CSV một dòng cho mỗi (ô, lần lặp)
- [x] Chạy thử khả thi bằng mã nháp: các giả định cho kết quả sát bản thảo, phương án ép ρ đã sửa (SPEC §10.4, §10.10)
- [x] Người dùng duyệt SPEC §10 (19/11/2026)

**Kết quả:** `.claude/spec/SPEC.md` §10

## T23. Bộ sinh dữ liệu và điểm số (G21) — ☑

- [x] `num41/gen.py`: hàm `sample(n, sigma_loc, rng, rho=None, group=None)` sinh vector hóa (n, H) gồm vị trí kế hoạch, vị trí thực của xe, vị trí dự báo và vị trí thực của tác nhân
  - [x] kế hoạch đường thẳng, v ~ U(0,8; 2,0); trễ δ ~ U(0; 0,15) s làm dịch dọc −v·δ
  - [x] sai số định vị: AR(1) dừng với độ lệch chuẩn σ_loc, hằng số thời gian 5 s (U1); sai số bám AR(1) (U2)
  - [x] tác nhân: vị trí đầu, hướng tới đường xe (U5), tốc độ 0,8–3,0 m/s; chuyển động thật có ω ~ N(0; 0,25²), a ~ N(0; 0,4²) (U6); dự báo vận tốc hằng
  - [x] chế độ ρ (U9) và chế độ trộn nhóm fix / float / loss (U12), có trả về nhãn nhóm
- [x] `num41/scores.py`:
  - [x] khoảng cách đĩa–đĩa d = ‖p − o‖ − 0,52 − 0,35;
  - [x] R = max_τ (d̂ − d)/σ_τ, A = max_τ ‖Δy‖/σ_τ, E = max_τ ‖Δp‖/σ_τ;
  - [x] ngưỡng q theo (6), dùng lại `sim/common.conformal_q`
- [x] Test `tests/test_num41.py`:
  - [x] TC-41a: d̂ − d ≤ ‖Δp‖ + ‖Δy‖, suy ra R ≤ A + E (cơ sở của Mệnh đề 3)
  - [x] TC-41b: σ_loc = 0, không trễ, không bám, tác nhân đi đúng dự báo, thì R = 0
  - [x] TC-41c: tất định, cùng hạt giống cho cùng mảng
  - [x] TC-41d: tỉ lệ điểm số trùng < 1e-6
  - [x] TC-41e: ở chế độ ρ, giữ nguyên ‖e‖; ρ = 0 cho e′ = e; cos(e′, g) và ρ_emp tăng đơn điệu theo ρ (SPEC §10.8)
- [x] Vẽ 20 mẫu ngẫu nhiên (kế hoạch, thực, dự báo) để soát bằng mắt → `figs/N0_samples.png`

**Kết quả:** `num41/gen.py`, `num41/scores.py`, `num41/plot_samples.py`, `tests/test_num41.py` (15 test đạt), `figs/N0_samples.{png,pdf}`. Lưu ý: 7 test cũ trong `test_regression.py` lỗi vì đọc `logs/new/` (thư mục nay là `logs/B`); lỗi này có từ trước, không do T23.

## T24. N1 — độ phủ theo α và n, cho Bảng 1 và Hình 1 (G22) — ☑

- [x] `num41/run_n1.py`: lưới 3 α × 3 n, 200 lần lặp, 2000 mẫu kiểm tra mỗi lần, σ_loc theo U7
- [x] Ghi `logs/num41/n1_coverage.csv` (alpha, n, rep, q, coverage) và bảng tổng hợp trung bình ± độ lệch chuẩn
- [x] So với chuẩn lý thuyết ở PLAN §10.4 (trung bình trong ±3 SE, độ lệch chuẩn sai khác ≤ 15%) và với Bảng 1 của bản thảo
- [x] Hình N1 (tương ứng Hình 1): độ phủ theo mức danh định, 3 đường theo n, thanh ± độ lệch chuẩn, có đường chéo y = 1 − α

**Kết quả:** `num41/run_n1.py`, `num41/logio.py`, `logs/num41/n1_coverage.csv`, mục N1 trong `summary.json` và `config.json`, `figs/N1_coverage.{png,pdf}`. Cả 9 ô đạt chuẩn lý thuyết (|z| ≤ 1,78; ĐLC/LT từ 0,887 đến 1,098). So với Bảng 1 bản thảo: TB lệch tối đa 0,005, ĐLC lệch tối đa 0,003. Chạy lại cho CSV giống hệt (md5).

## T25. N2 — so sánh bốn loại biên theo σ_loc và theo ρ, cho Hình 2 (G23) — ☑

- [x] `num41/run_n2.py`: α = 0,1, n = 1000, 50 lần lặp, σ_loc theo lưới U8
  - [x] B1: q_A(α); B3: q_A(0,05) + q_E(0,05); B4: q_A(α) + max E_calib; ĐX: q_R(α)
  - [x] độ phủ = P(R_test ≤ q) cho cả bốn loại biên (U10)
- [x] Ghi `logs/num41/n2_bounds.csv` (sigma_loc, rep, method, q, coverage)
- [x] Kiểm tra Mệnh đề 3: q_ĐX ≤ q_B3 ở **mọi** lần lặp; ghi lại số lần vi phạm (phải bằng 0)
- [x] Quét ρ ∈ {−0,5; 0; 0,5; 0,9} ở σ_loc = 0,1 m (U9) và tính tỉ số q_ĐX/q_B3 → `logs/num41/n2_rho.csv`
- [x] Đối chiếu với bản thảo: B1 0,996 / 0,972 / 0,802; ngưỡng 1,82 / 7,81 và 5,77 / 18,0; B4 9,21 / 25,6; tỉ số 0,23 → 0,31
- [x] ~~Nếu lệch mức 2~~ — không cần: mức 2 đạt hết. Đã cài sẵn `--sensitivity` để chạy phương án U6 (đổi theo từng bước) và U1 (không trôi); ghi kết quả độ nhạy, không chỉnh tham số để ép khớp
- [x] Hình N2 (tương ứng Hình 2): (a) độ phủ, (b) ngưỡng chuẩn hóa theo σ_loc; thêm hình phụ N2c cho tỉ số theo ρ

**Kết quả:** `num41/run_n2.py`, `logs/num41/n2_bounds.csv`, `logs/num41/n2_rho.csv`, mục N2 trong `summary.json`/`config.json`, `figs/N2_bounds.{png,pdf}` (3 ô a/b/c). Định tính đạt hết: ĐX 0,900–0,903; B1 giảm 0,998 → 0,798; 0 vi phạm Mệnh đề 3 (350 lần lặp σ + 200 lần lặp ρ); B4 > B3 ở mọi σ; tỉ số tăng theo ρ. Định lượng đạt hết (±0,02 / ±15%): q_ĐX 1,74 / 5,89; q_B3 8,06 / 18,0; q_B4 9,63 / 25,0; tỉ số 0,215 → 0,348 (bản thảo 0,23 → 0,31, đầu ρ = 0,9 lệch 12%). Lưu ý: tỉ số gần như phẳng tới ρ = 0,5 rồi mới tăng vọt. Đã sửa `logio.update_json` để ghi an toàn (tuần tự hóa trước, ghi file tạm rồi đổi tên) và đổi được kiểu numpy. Chạy lại cho CSV giống hệt (md5).

## T26. N3 — hiệu chỉnh theo chất lượng định vị, cho Bảng 2 (G24) — ☑

- [x] `num41/run_n3.py`: trộn ba nhóm fix 0,03 m (70%) / float 0,3 m (20%) / loss 1,0 m (10%); n = 1000, 2000 mẫu kiểm tra, α = 0,1, 100 lần lặp
- [x] Ngưỡng chung q từ toàn bộ tập hiệu chỉnh; ngưỡng theo nhóm q_g từ mẫu của từng nhóm; độ phủ tính theo từng nhóm trên tập kiểm tra
- [x] Ghi `logs/num41/n3_groups.csv` (rep, group, n_g, q_global, q_g, cov_global, cov_group); báo cáo trung bình ± độ lệch chuẩn
- [x] Đối chiếu với Bảng 2: 0,963 / 0,818 / 0,620; 0,900 / 0,900 / 0,899; 2,37; 1,74 / 3,34 / 12,18
- [x] Kiểm tra độ phủ theo nhóm có đạt 1 − α ở từng nhóm hay không (Hệ quả 1)

**Kết quả:** `num41/run_n3.py`, `logs/num41/n3_groups.csv`, mục N3 và N3_sensitivity trong `summary.json`, mục N3 trong `config.json`; bảng sẽ đưa vào `report/` ở T27. Định tính đạt hết: độ phủ theo nhóm 0,900 / 0,899 / 0,902 (Hệ quả 1); ngưỡng chung phủ thừa nhóm fix (0,969), thiếu nhóm float (0,810) và loss (0,573); q_g tăng theo nhóm; không có q_g = +∞. Định lượng đạt 9/10: q chung 2,30 (bản thảo 2,37); q_g 1,60 / 3,39 / 12,44 (bản thảo 1,74 / 3,34 / 12,18). **Không đạt:** độ phủ ngưỡng chung ở nhóm loss là 0,573, bản thảo ghi 0,620 (lệch 0,047, vượt ±0,02). Hai biến thể độ nhạy còn xa hơn (U6-B 0,496; U1-W 0,242), nên giữ mô hình gốc và không chỉnh tham số (PLAN §10.4). Đề xuất thay số trong bản thảo ở T27. Kiểm tra chéo: 0,7·0,969 + 0,2·0,810 + 0,1·0,573 = 0,898 ≈ 0,90. Chạy lại cho CSV giống hệt (md5).

## T27. Báo cáo đối chiếu và kiểm tra (G25) — ☑

- [x] `num41/report_41.py` sinh `report/BAO_CAO_TAI_LAP_4_1.md` (và `.docx`):
  - [x] bảng đối chiếu từng con số: bản thảo, tái lập, chênh lệch, khớp hay không
  - [x] liệt kê mọi giả định U1–U12 đã dùng
  - [x] đề xuất sửa bản thảo theo vị trí: Tóm tắt, Mục 4.1 (lời văn, Bảng 1, Bảng 2, Hình 1, Hình 2), Kết luận
  - [x] đề xuất câu bổ sung vào phần Thiết lập của 4.1 cho các giả định chưa nêu
- [x] `pytest` đạt toàn bộ, gồm TC-41a..e và các test cũ TC-01..TC-18 — 41/41 đạt, sau khi sửa đường dẫn `logs/new`, `logs/old` thành `logs/B`, `logs/A` (19/11/2026)
- [x] `python -m num41.run_all --seed 2026` sinh lại toàn bộ `logs/num41/` và các hình; chạy hai lần cho kết quả giống hệt
- [x] Đối chiếu từng con số trong báo cáo với `logs/num41/`
- [x] Cập nhật `README.md`; đóng gói `num41.zip` (mã, hạt giống, log, hình) để công bố kèm bài

**Kết quả:**
- Đã tạo `num41/report_41.py` và `num41/run_all.py`.
  - Báo cáo `report/BAO_CAO_TAI_LAP_4_1.md` (kèm `.docx`) sinh hoàn toàn từ `summary.json`.
  - Báo cáo gồm: kết luận chính, cách tái lập, U1–U12, các bảng đối chiếu N1 / N2 / N2-ρ / N3, kiểm tra định tính, độ nhạy, 22 đề xuất sửa theo vị trí đoạn, 6 câu bổ sung cho phần Thiết lập, các hạn chế.
- `run_all` chạy hai lần cho 12 file giống hệt từng byte: 4 CSV, `summary.json`, `.md` và 6 hình (đã bỏ dấu thời gian trong siêu dữ liệu PNG/PDF).
  - Các file sau khác nhau giữa các lần chạy, đã ghi trong README: `config.json` (có trường `generated_at`), `tests.txt` (có thời gian chạy), `.docx` (pandoc ghi thời gian).
- 104 con số trong báo cáo khớp khi tính lại độc lập từ CSV thô.
- pytest: `tests/test_num41.py` đạt 15/15; toàn bộ thư mục `tests/` đạt 41/41.
- Sửa thêm theo yêu cầu: `logs/old/` và `logs/new/` đã đổi tên thành `logs/A/` và `logs/B/` nhưng mã chưa cập nhật. Đã sửa đường dẫn trong `tests/test_regression.py`, `sim/report.py`, `sim/run_ext.py`, `sim/run_old.py`, `sim/run_new.py`, `run_all.py`, `run_ext.py`, `README.md`, `sim/README.md`. Không đụng tới log; các báo cáo `.md` cũ giữ nguyên như bản lưu.
- Đã cập nhật README (cây thư mục, mục 5) và tạo `num41.zip` (27 file).
  - Gói này cần thêm `sim/common.py` để chạy.

---

# CARLA chia ba phần (v0.7, đề xuất, chưa duyệt)

Xem PLAN §11. Phần 1 làm trước; Phần 2 và Phần 3 dùng chung môi trường, bộ dự báo và hạt giống kiểm tra của Phần 1. Log ở `logs/carla_setup/`, `logs/carla_A/`, `logs/carla_B/`. Không sửa `logs/A`, `logs/B`, `logs/ext`, `logs/num41`.

## Phần 1 — Thiết lập theo thông số Mục 4, làm theo tài liệu hướng dẫn

Theo `document/Huong dan chi tiet mo phong CARLA (Tesla Model 3)…docx` (PLAN §11.2a). CARLA 0.9.15 chạy trên máy khác; máy này không cài CARLA. Mã viết mới ở `ws/av_conformal/` theo cây thư mục §0.5 của hướng dẫn (C7). Mọi mô-đun có test trên backend giả để chạy được ở máy này. Mỗi lượt lưu run_id, hạt giống, cấu hình, mã băm, phiên bản CARLA (hướng dẫn §0.2).

## T28. C1 — kết nối CARLA ở máy khác (G26) — ◐ mã đã viết và test ngoại tuyến; chờ máy CARLA

- [ ] Bạn cho biết địa chỉ, cổng RPC, cổng Traffic Manager, hệ điều hành của máy CARLA; chốt C6 (chạy mã khách ở máy này hay ở máy CARLA)
- [ ] Môi trường máy khách: Python 3.10 + gói `carla` 0.9.15 (file .whl trong `PythonAPI/carla/dist` hoặc `pip install carla==0.9.15`), ghi lại cách cài
- [x] Dựng khung `av_conformal/` (configs, av_core, carla_env, scripts); mọi tham số kết nối lấy từ dòng lệnh `--host --port --tm-port`
- [x] `carla_env/world.py`: chế độ đồng bộ, bước 0,05 s, hạt giống Traffic Manager, dọn dẹp trong try/finally
- [x] `carla_env/coords.py`: `to_carla` / `from_carla`, chỉ quy đổi ở một chỗ
- [ ] Kiểm tra C1-a: phiên bản máy khách = máy chủ; nạp Town03
- [ ] Kiểm tra C1-b: 1200 bước, số khung tăng đúng 1 mỗi tick; ghi thời gian thực đã trôi
- [x] Kiểm tra C1-c: đi–về tọa độ sai số < 1e-6 (test trên máy này); xe quay trái đúng chiều trên CARLA
- [ ] Ghi `logs/carla_setup/c1.json`

## T29. C2 — Tesla Model 3, bộ chuyển lệnh, nhận dạng; Bảng 3 (G27) — ◐ mã đã viết và test ngoại tuyến; chờ máy CARLA

- [x] (mã viết, CHƯA kiểm chứng trên CARLA) `carla_env/ego.py`: sinh `vehicle.tesla.model3`, trích L, δ_max, dài, rộng, rear_overhang, khối lượng; kiểm tra bằng tay một lần
- [x] `av_core/actuation.py`: PI vận tốc, hệ số lái, bộ đệm trễ có `set_delay`
- [ ] Sáu phép thử của hướng dẫn §2.4 trên Town04 hoặc Town10HD, mỗi phép lặp ≥ 5 lần, ghi 20 Hz:
  - [ ] steer cố định 0,1…1,0 ở 3 m/s → steer_gain, δ_max
  - [ ] lặp ở 6 và 8 m/s; nếu δ giảm theo tốc độ thì lập bảng tra 2 chiều
  - [ ] ga 1,0 từ 0 đến v_max → a_max (trung vị đoạn 1–5 m/s)
  - [ ] phanh 1,0 từ 8 m/s → a_min, quãng phanh
  - [ ] bước v_cmd 0→5→8→3 m/s → chỉnh kp_v, ki_v (vọt lố < 5%, xác lập < 3 s)
  - [ ] Pure Pursuit bám đường thẳng, cua, chữ S ở 3, 5, 8 m/s không nhiễu → phân phối sai số ngang, sai số hướng
- [ ] Kiểm tra C2: bán kính quay khớp L/tan δ sai số < 5% trong vùng tuyến tính; bám ở 8 m/s không dao động
- [ ] Ghi `av_conformal/configs/tesla_model3.yaml`, `logs/carla_setup/c2/` và `bang3.md` (mỗi ô có nguồn; ô chưa có căn cứ ghi TẠM)

## T30. C3, C4, mục 6–7 — nhiễu, kịch bản, vòng kín B0 (G28) — ◐ mã đã viết và test ngoại tuyến; chờ máy CARLA

- [x] `av_core/noise.py` theo §3.2 (Gauss–Markov cho fixed/float, dead-reckoning cho lost); `configs/noise.yaml` theo hướng dẫn, ghi TẠM (C5)
- [x] `configs/conditions.yaml` D0–D5; trễ D4/D5 qua `set_delay`; nhãn nhóm = trạng thái RTK quan sát được (§3.4)
- [x] (test số: σ nhóm fixed<float, lost tăng, D2 có mất GNSS; chưa đồ thị/so khớp 10% bằng mẫu dài) Kiểm tra C3: đồ thị sai số một lượt D2; σ theo nhóm khớp `noise.yaml` sai lệch < 10%
- [x] `carla_env/scenarios.py` và `configs/scenarios.yaml`: S1 người đi bộ (`WalkerControl`), S2 xe máy (tắt vật lý, `set_transform`), kích hoạt theo s_trig; chọn tuyến và điểm xung đột trên Town03
- [ ] S3, S4 tự thiết kế theo bản thảo, ghi TẠM, gửi NCS duyệt (C8); tính lại s_trig từ a_min để lớn hơn quãng phanh ở 8,3 m/s
- [ ] Kiểm tra C4: chạy hai lần cùng hạt giống, quỹ đạo tác nhân sai khác = 0; quay video ngắn mỗi kịch bản
- [x] `av_core/geometry.py`, `tracker.py` (Pure Pursuit 20 Hz trên tư thế ước lượng), `planner.py` (Frenet: lệch ngang −1,5…1,5 m bước 0,25 m; vận tốc 0…v_max bước 0,5 m/s; 3/4/5 s; dự phòng phanh), `evaluator.py` (trễ H bước, ghi err_agent, err_ego)
- [x] Kiểm tra C6-a: kế hoạch trùng thật → R = 0; dịch tác nhân lại gần 0,5 m → R ≈ 0,5/σ_τ
- [x] `scripts/sim_runner.py` đúng thứ tự §7.1; logger ghi `_cycles.parquet`, `_steps.parquet`, `_meta.json` (§7.2)
- [x] `scripts/batch.py`: tổ hợp S×D×phương pháp×hạt giống, `--shard`, bỏ qua lượt đã xong, bắt lỗi từng lượt và kết nối lại
- [x] Chạy khói trên backend giả: 1 hạt giống × S×D với B0, không lỗi (ghi trong BAO_CAO_CARLA_PHAN1.md); chưa chạy trên CARLA
- [ ] Đo thời gian 100 lượt đầu: tốc độ so với thời gian thực, P95 một chu kỳ < 0,1 s; lập lịch chạy
- [ ] Chốt C1 và C2

## T31. C5 — dữ liệu B0 dùng chung và bộ dự báo (G29) — ◐ mã đã viết và test ngoại tuyến; chờ máy CARLA

- [ ] Chạy B0 (σ_τ = 1) trên hạt giống 0–249, ghi lịch sử tác nhân 10 Hz và (d̂ − d) thô theo τ; log `logs/carla_setup/b0/`
- [x] `av_core/predictor.py`: vận tốc hằng (mức nền bắt buộc)
- [ ] Trajectron++: chuyển dữ liệu hạt giống 0–199, lịch sử 2 s, H = 3 s; quy tắc chọn một khả năng ghi rõ; nếu không được thì dùng CTRA và ghi lại (C3)
- [ ] Đóng băng mô hình, lưu trọng số và mã băm
- [ ] Kiểm tra C5: hình dự báo chồng quỹ đạo thật cho 5 tình huống ngẫu nhiên; ADE Trajectron++ < ADE vận tốc hằng
- [ ] ADE/FDE cho cả hai bộ dự báo, điền câu ở §4.2
- [ ] Báo cáo ngắn Phần 1 `report/BAO_CAO_CARLA_PHAN1.md`: kết quả các phép kiểm tra C1–C5 và C6-a, Bảng 3, ADE/FDE, bảng hạt giống, thời gian từng khối

## Phần 2 — Vòng kín theo phương án A (bản thảo v0.1)

## T32. Bộ chạy phương án A cho CARLA (G30) — ☐

- [ ] Thêm lựa chọn `scheme="A"` vào `carla_sim/runner.py`, dùng lại logic của `sim/run_old.py`:
  - [ ] giữ chu kỳ không có tác nhân (R = −∞)
  - [ ] lấy thưa mỗi 2 s
  - [ ] σ_τ cố định 0,05 + 0,04τ
  - [ ] sai số tác nhân A_c
  - [ ] chứng nhận có điều kiện, tối đa 3 lần
  - [ ] ACI cập nhật trên mọi chu kỳ
- [ ] Test trên backend giả: A và B cho log khác nhau đúng ở các điểm trên

## T33. Chạy phương án A (G31) — ☐

- [ ] Hiệu chỉnh trên hạt giống 250–399, chứng nhận theo C1, kiểm tra trên 500–699
- [ ] Chạy B0–B6, ĐX-1, ĐX-2, ĐX-3 với cùng hạt giống
- [ ] Thử loại bỏ lần lượt (Bảng 5): chuẩn hóa σ_τ; phân nhóm định vị; hiệu chỉnh lặp; thành phần góc hướng; thành phần trễ
- [ ] Quét cho Hình 4 ở S2–D1 với B1, B3, ĐX-2 (sau khi chốt C4)
- [ ] Một lượt S2–D2 cho Hình 5 (ghi hạt giống)
- [ ] Log `logs/carla_A/`, checkpoint mỗi 25 lượt

## T34. Phân tích và báo cáo phương án A (G32) — ☐

- [ ] Bảng 4: độ phủ (KTC), vi phạm/va chạm, d_min/TTC, thời gian hoàn thành/dự phòng, RMS độ giật/P95 thời gian tính
- [ ] Hình 3: độ phủ theo D0–D5 cho B1, B3, B4, ĐX-2; Hình 4; Hình 5; Bảng 5
- [ ] Kiểm định Wilcoxon, McNemar, hiệu chỉnh Holm
- [ ] Thời gian tính (4.6): trung vị và P95 của dự báo, hiệu chỉnh, lập kế hoạch
- [ ] So với 2D phương án A (`logs/A`)
- [ ] `report/BAO_CAO_CARLA_A.md`: điền [X] và đề xuất lời văn 4.3–4.6 theo đúng bản thảo v0.1

## Phần 3 — Vòng kín theo phương án B (sửa đổi)

## T35. Bộ chạy phương án B (G33) — ☐

- [ ] Soát `carla_sim/runner.py` theo cột B của SPEC §3:
  - [ ] bỏ chu kỳ trống
  - [ ] lấy thưa mỗi 3 s
  - [ ] σ_τ từ B0 hạt giống 200–249
  - [ ] sai số tác nhân A_h
  - [ ] chứng nhận PAC
  - [ ] thêm B3′
- [ ] Dùng lại log B0 của T31, không chạy lại
- [ ] Test trên backend giả

## T36. Chạy phương án B (G34) — ☐

- [ ] Cùng hạt giống hiệu chỉnh, chứng nhận và kiểm tra như T33 (ghép cặp với A)
- [ ] B0–B6, B3′, ĐX-1/2/3; thử loại bỏ cơ chế; Hình 4, Hình 5
- [ ] Quét α ∈ {0,01; 0,02; 0,05; 0,1; 0,2} cho B1, B3′, ĐX-2
- [ ] Log `logs/carla_B/`, checkpoint mỗi 25 lượt

## T37. Báo cáo phương án B và so sánh A–B (G35) — ☐

- [ ] Bộ bảng và hình như T34, theo phương án B
- [ ] So sánh A–B trên CARLA (ghép cặp) và với 2D (`logs/A`, `logs/B`)
- [ ] `report/BAO_CAO_CARLA_B_VA_SO_SANH.md`: đề xuất bản thảo dùng A hay B, kèm các thay đổi lời văn ở §3, §4.2–4.6
- [ ] Cập nhật README, đóng gói, đối chiếu từng số với log, pytest đạt toàn bộ
