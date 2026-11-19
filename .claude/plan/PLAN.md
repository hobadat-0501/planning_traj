# KẾ HOẠCH — Mô phỏng phương án cũ / mới cho bài báo "Biên an toàn phù hợp có xét sai số xe tự hành"

*Phiên bản 0.5.2 — 19/11/2026 — Phần 1 làm theo tài liệu "Hướng dẫn chi tiết mô phỏng CARLA (Tesla Model 3)" (C1–C5, mục 6–7); CARLA chạy trên máy khác, không cài ở máy này*
*Phiên bản 0.5.1 — 19/11/2026 — chốt CARLA 0.9.15 cho cả ba phần*
*Phiên bản 0.5 — 19/11/2026 — thêm §11: CARLA chia ba phần (thiết lập theo Mục 4, vòng kín A, vòng kín B), đề xuất, chưa duyệt*
*Phiên bản 0.4 — 19/11/2026 — thêm §10: tái lập Mục 4.1 (nghiên cứu số, dữ liệu tổng hợp), đề xuất, chưa duyệt*
*Phiên bản 0.3 — 16/11/2026 — G1–G12 (v0.1 và mở rộng v0.2) đã hoàn thành và kiểm tra nghiệm thu*

## 1. Mục tiêu

Dựng hai bản mô phỏng **vòng kín bằng Python thuần (không cần CARLA)** để so sánh:

- **A — Phương án cũ:** cài đặt đúng như bản thảo v0.1.
- **B — Phương án mới:** cài đặt các sửa đổi đã đề xuất khi phân tích bản thảo (PAC cho Định lý 2, bỏ mẫu không có tác nhân, lấy mẫu không chồng cửa sổ, sai số tác nhân theo Hausdorff, σ_τ ước lượng trên tập riêng, đối chứng B3′, báo cáo riêng chu kỳ dự phòng).

Log số liệu thành **hai phần riêng** (`logs/old/`, `logs/new/`), rồi viết **báo cáo kết quả kèm đề xuất sửa đổi bản thảo**.

## 2. Phạm vi

**Trong phạm vi:**
- Mô phỏng 2D: xe cỡ Tesla Model 3, sáu điều kiện suy giảm D0–D5, bốn kịch bản S1–S4.
- 10 phương pháp ở phương án cũ (B0–B6, ĐX-1/2/3), 11 phương pháp ở phương án mới (thêm B3′).
- Quét α cho một số phương pháp chính.

**Ngoài phạm vi:**
- CARLA, cảm biến thật, Trajectron++ (thay bằng dự báo vận tốc hằng).
- Xe thật Hunter SE.
- Viết lại toàn văn bản thảo. Báo cáo chỉ đề xuất sửa theo từng mục.

## 3. Đầu ra

| # | Đầu ra | Định dạng |
|---|---|---|
| 1 | Mã nguồn mô phỏng, README, lệnh chạy lại | `sim/` → file `.zip` |
| 2 | Log phương án cũ | `logs/old/` (CSV, JSON) |
| 3 | Log phương án mới | `logs/new/` (CSV, JSON) |
| 4 | Hình so sánh (5–6 hình) | PNG, nhúng trong báo cáo |
| 5 | Báo cáo kết quả và đề xuất sửa đổi | Claude Docs (xuất được Word/PDF) |

## 4. Các giai đoạn

| Giai đoạn | Nội dung | Điều kiện để chuyển bước |
|---|---|---|
| G1 | Lõi mô phỏng dùng chung | Chạy thử 24 tổ hợp S×D không lỗi; sai số xe ở D0 hợp lý (< 0,5 m tại 3 s) |
| G2 | Phương án cũ (A) | Có `logs/old/` đầy đủ |
| G3 | Phương án mới (B) | Có `logs/new/` đầy đủ |
| G4 | Phân tích, hình | Mọi bảng/hình sinh từ `summary.json` |
| G5 | Báo cáo | Đủ các mục theo SPEC §7 |
| G6 | Kiểm tra | Chạy lại từ hạt giống khớp số liệu; số trong báo cáo khớp log |

## 5. Tài nguyên và thời gian

- Máy có 2 lõi CPU, 7 GB RAM.
- Đã đo: khoảng 0,25 s mỗi lượt chạy.
- Tổng khoảng 9.000 lượt, tức khoảng 25–40 phút tính toán (chạy song song 2 tiến trình).
- Cả quá trình, gồm phân tích và viết báo cáo, ước khoảng 1,5–2 giờ.

## 6. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Mô phỏng 2D không phản ánh đúng động lực học CARLA | Nói rõ giới hạn trong báo cáo; mọi kết luận chỉ ở mức định tính, xu hướng |
| Nhóm "mất GNSS" thiếu mẫu cho ĐX-2 | Dùng ngưỡng chung và báo cáo rõ (đúng như Hệ quả 1) |
| Thiếu thời gian tính | Giảm số lượt kiểm tra từ 15 xuống 10 mỗi ô, và ghi chú lại |
| Sai số bám bị chi phối bởi việc lập lại kế hoạch (replanning) | Tách riêng phần này trong phân tích, đưa vào đề xuất sửa định nghĩa sai số bám |

## 7. Duyệt và Hoàn thành

- [x] Duyệt PLAN
- [x] Duyệt TASKS
- [x] Duyệt SPEC
- [x] Hoàn thành toàn bộ G1–G6 và kiểm tra nghiệm thu SPEC §8

---

## 8. Giai đoạn mở rộng v0.2 — thêm kịch bản và trường hợp kiểm thử (đã hoàn thành)

### 8.1. Mục tiêu

Phân tích kết quả v0.1 cho thấy một số điểm chưa được kiểm chứng (chi tiết ở SPEC §9). Giai đoạn này nhằm:

1. **Mở rộng phạm vi kiểm tra:**
   - 6 kịch bản mới S5–S10: khuất tầm nhìn, chen làn, đường cong và xe ngược chiều, mật độ cao, tác nhân tương tác, hành vi trái giả định vận tốc hằng.
   - 5 điều kiện suy giảm mới D6–D10: kết hợp, mất GNSS dài, nhãn định vị sai, đường trơn, nhận thức suy giảm.
2. **Kiểm tra độ bền khi dịch chuyển phân phối:** chạy các tập IN / OOD-S / OOD-D / OOD-SD mà không hiệu chỉnh lại, và tập RECAL có hiệu chỉnh lại.
3. **Làm rõ 7 điểm còn yếu** qua thí nghiệm E1–E9:
   - so sánh ở cùng độ phủ;
   - vết α_t của ACI;
   - lực kiểm định PAC và cỡ mẫu;
   - khối D2 chuyên biệt;
   - tự tương quan theo lượt;
   - tách E_track / E_replan;
   - độ nhạy d_s và mật độ lưới;
   - σ_τ theo kịch bản;
   - tăng cỡ mẫu theo ô.
4. **Thêm bộ kiểm thử mã tự động** TC-01..TC-18 (`pytest`) để bảo đảm tính đúng của cài đặt và tái lập v0.1.

### 8.2. Phạm vi

**Trong phạm vi:**
- Chỉ phương án B (cộng B0).
- Sửa lõi để hỗ trợ đường cong, vật cản che khuất và tác nhân phản ứng.
- Log riêng ở `logs/ext/`.
- Báo cáo mở rộng.

**Ngoài phạm vi:**
- Chạy lại phương án A trên kịch bản mới (chỉ làm nếu cần đối chiếu).
- CARLA, Trajectron++.
- Viết lại bản thảo.

### 8.3. Các giai đoạn

| Giai đoạn | Nội dung | Điều kiện để chuyển bước |
|---|---|---|
| G7 | Bộ kiểm thử TC-01..TC-18 (viết trước, cho phần đã có: TC-02..TC-12, TC-18) | Các test cho mã v0.1 đạt; TC-01 tái lập đúng `logs/new` |
| G8 | Mở rộng lõi: S5–S10, D6–D10, Frenet trên đường cong, che khuất, tác nhân phản ứng, nhánh mở vòng E_track | TC-01 vẫn đạt (S1–S4 không đổi); TC-13..TC-17 đạt; 110 ô S×D chạy không lỗi |
| G9 | Chạy các tập OOD-S/D/SD, rồi RECAL | Có `logs/ext/` cho các tập này; TC-11 (không rò rỉ hạt giống) đạt |
| G10 | Thí nghiệm E1–E9 theo thứ tự ưu tiên | Có đủ các file `alpha_sweep_ext.csv`, `aci_trace.csv`, `pac_power.csv`, `thinning_ext.csv`, `sigma_by_scn.csv` |
| G11 | Phân tích, hình H7–H11, báo cáo mở rộng | Đủ các mục theo SPEC §9.9; mọi số liệu truy được về `logs/ext/` |
| G12 | Kiểm tra nghiệm thu | Đạt SPEC §9.10; cập nhật bảng đề xuất sửa bản thảo (nhất là ACI và cách trình bày ưu thế ĐX) |

### 8.4. Tài nguyên và thời gian

- Khoảng 55.000 lượt, tức khoảng 3–4 giờ tính toán với 2 tiến trình (SPEC §9.7).
- Viết mã, test và báo cáo ước khoảng 4–6 giờ.
- Nên chạy G9 và G10 ở chế độ nền, theo từng khối, có điểm lưu tạm (checkpoint) để chạy tiếp được nếu bị ngắt.

### 8.5. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Sửa lõi (đường cong, che khuất) làm thay đổi kết quả S1–S4 | TC-01 là cổng bắt buộc; nhánh mã mới chỉ kích hoạt khi kịch bản là S5–S10 |
| S9 (tác nhân tương tác) làm Thuật toán 1 không hội tụ | Giới hạn 5 vòng lặp; ghi lại dao động của q; báo cáo như một phát hiện, không ép hội tụ |
| S5 tạo va chạm không tránh được về vật lý, làm nhiễu so sánh | Ghi cờ `unavoidable` (TTC lúc lộ diện < thời gian phanh tối thiểu); báo cáo kết quả có và không có các lượt này |
| Tổng thời gian tính vượt dự kiến | Theo thứ tự ưu tiên OOD → E1 → E2 → E4 → E6; E1 giảm xuống 5 mức α; giảm OOD xuống 8 hạt giống mỗi ô |
| Kết quả mới bác bỏ một số kết luận v0.1 (ví dụ ACI) | Sửa báo cáo một cách trung thực; ghi rõ thay đổi so với v0.1 |

### 8.6. Duyệt và Hoàn thành (mở rộng)

- [x] Duyệt PLAN §8
- [x] Duyệt TASKS T8–T14
- [x] Duyệt SPEC §9
- [x] Hoàn thành G7–G12 và kiểm tra nghiệm thu SPEC §9.10

---

## 9. Kế hoạch chuyển sang CARLA (đã thay bằng §11)

### 9.1. Mục tiêu và phạm vi

Kiểm chứng phương án B trên CARLA thật, bắt đầu từ ít thay đổi nhất rồi thêm dần phần thật. Mỗi mức chỉ thay phần đầu vào; mã tính biên (điểm số, hiệu chỉnh, PAC, ACI) giữ nguyên.

**Mức đầu vào (làm tuần tự):**

| Mức | Nhận diện | Dự báo | Mục đích |
|---|---|---|---|
| M1 | Ground truth CARLA cộng nhiễu Gauss | Vận tốc hằng | Kiểm tra cầu nối và độ phủ trên động lực học thật |
| M2 | Như M1 | Trajectron++ (hoặc mô hình học được khác) | Đo ảnh hưởng của dự báo tốt hơn lên độ rộng biên |
| M3 (tùy chọn) | Detector và tracker thật trên camera/lidar | Như M2 | Có sai số bỏ sót, nhãn sai, che khuất thật |

Nếu không làm M3, bản thảo phải ghi rõ giới hạn: tác nhân được quan sát bằng ground truth cộng nhiễu.

**Ngoài phạm vi (giữ nguyên):** phương án A trên CARLA; viết lại bản thảo.

### 9.2. Các giai đoạn

| Giai đoạn | Nội dung | Điều kiện để chuyển bước |
|---|---|---|
| G13 | Hạ tầng: cài CARLA server/client, synchronous mode (dt 0,05 s, lập kế hoạch 10 Hz), chỉnh tham số xe (L = 2,875 m, V_MAX 8,3 m/s, góc lái) | Một xe chạy vòng kín ổn định, đo được trễ lệnh |
| G14 | Cầu nối: đọc tư thế thật, gửi `VehicleControl`, nối bộ lập kế hoạch Frenet và pure pursuit; ghi log đúng định dạng của `analyze.py` | S1 + D0 chạy, `analyze.py` đọc được log CARLA không sửa |
| G15 | Kịch bản và điều kiện: S1–S4 trong CARLA (walker AI, traffic manager); bộ phát sai số định vị D1–D5 cài vào dữ liệu CARLA | Đủ S×D chạy không lỗi; đo thời gian lập kế hoạch cộng tính biên nhỏ hơn 0,1 s |
| G16 | Chốt tham số: điền các ô [X] của Bảng §4.2 (mức nhiễu định vị, d_s), cỡ mẫu và số hạt giống theo E3, lưới vận tốc 0,5 m/s hay 1,0 m/s | Có bảng tham số được duyệt |
| G17 | Chạy M1 đầy đủ, so với kết quả 2D | Có `logs/carla_m1/`; báo cáo độ phủ, độ rộng biên, trễ |
| G18 | M2 (dự báo học được); M3 nếu quyết định làm | Có `logs/carla_m2/` (và `m3`) |
| G19 | Phân tích, báo cáo CARLA, đề xuất sửa bản thảo (§4.2, §2.3) | Mọi số liệu truy được về log |

### 9.3. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Bộ lập kế hoạch (351 hoặc 663 ứng viên) không đủ nhanh theo thời gian thực | Đo ở G15; giảm lưới vận tốc hoặc chạy đồng bộ (không thời gian thực) |
| Dữ liệu CARLA tương quan mạnh, vi phạm hoán đổi được giữa các chu kỳ | Giữ lấy mẫu thưa 3 s không chồng; báo cáo độ phủ theo hạt giống |
| Che khuất, bỏ sót, nhãn sai chưa được mô hình hóa ở M1, M2 | Nêu rõ trong giới hạn; chỉ M3 mới kiểm tra được |
| Mỗi lần chạy CARLA tốn thời gian thật, không đủ hạt giống | Dùng bảng cỡ mẫu E3, chạy theo khối có checkpoint |
| Chưa chốt phương án A hay B cho bản thảo | Dùng B; A chỉ làm đối chiếu nếu cần |

### 9.4. Duyệt và Hoàn thành (CARLA)

- [ ] Duyệt PLAN §9
- [ ] Duyệt TASKS T15–T21
- [ ] Hoàn thành G13–G19

---

## 10. Tái lập Mục 4.1 — nghiên cứu số trên dữ liệu tổng hợp (đã duyệt)

### 10.1. Bối cảnh và mục tiêu

Kết quả đối chiếu ngày 19/11/2026:
- Trong `ws/` không có đoạn mã nào sinh ra các số liệu của Mục 4.1 (Bảng 1, Bảng 2, Hình 1, Hình 2 và các con số trong lời văn).
- Kết quả A (`logs/A`) là mô phỏng vòng kín 2D, nên không thay thế được Mục 4.1:
  - độ phủ điểm số của ĐX-1 là 0,874, không đạt 0,90;
  - ĐX-2 chưa khôi phục được độ phủ ở nhóm float và loss.
- A chỉ khớp ở hai điểm: biên gộp hẹp hơn B3 khoảng 75%, và xu hướng của B1 cũng như của ngưỡng chung theo từng nhóm.

**Mục tiêu:**
1. Viết mã sinh dữ liệu tổng hợp **mở vòng** đúng như mô tả ở Mục 4.1, sinh lại toàn bộ số liệu của mục này từ hạt giống 2026.
2. So khớp từng con số với bản thảo v0.1. Con số nào lệch thì ghi lại trung thực và đề xuất sửa bản thảo, coi mã là nguồn sự thật.
3. Đóng gói mã cùng hạt giống để công bố kèm bài, đúng như bản thảo đã cam kết.

**Trong phạm vi:**
- Gói mã mới `num41/`, độc lập với `sim/`.
- Log ở `logs/num41/`, hình N1–N3 ở `figs/`, báo cáo đối chiếu.
- Các số của Mục 4.1 được dùng lại ở Tóm tắt và Kết luận (68–77%, 0,80, 0,62).

**Ngoài phạm vi:**
- Vòng kín, CARLA.
- Sửa `sim/`, `logs/A`, `logs/B`, `logs/ext`.
- Viết lại các mục khác của bản thảo.

### 10.2. Thiết lập lấy từ bản thảo

| Thành phần | Bản thảo v0.1 (Mục 4.1) |
|---|---|
| Kế hoạch xe | Đường thẳng, v ~ U(0,8; 2,0) m/s, H = 30 bước × 0,1 s |
| Tư thế thực | Kế hoạch + sai số định vị (Gauss, σ_loc, trôi chậm) + sai số bám AR(1) + dịch dọc đường do trễ δ ~ U(0; 0,15) s |
| Tác nhân | Xuất phát cách 3–8 m phía trước, lệch ngang ±4 m, đi về phía đường của xe với tốc độ 0,8–3,0 m/s |
| Dự báo / chuyển động thật | Dự báo vận tốc hằng; chuyển động thật có tốc độ quay ngẫu nhiên (σ = 0,25 rad/s) và gia tốc ngẫu nhiên (σ = 0,4 m/s²) |
| Hình bao | Đĩa: xe r = 0,52 m, tác nhân r = 0,35 m |
| Điểm số, ngưỡng | R theo (5); σ_τ = 0,05 + 0,04τ; q = R_(k), k = ⌈(n+1)(1−α)⌉ theo (6) |
| Lặp | Tập hiệu chỉnh và tập kiểm tra độc lập ở mỗi lần lặp; 2000 mẫu kiểm tra mỗi lần; hạt giống 2026 |
| N1: Bảng 1, Hình 1 | α ∈ {0,05; 0,10; 0,20} × n ∈ {100; 500; 1000}, 200 lần lặp mỗi ô |
| N2: Hình 2 | α = 0,1, n = 1000, 50 lần lặp; σ_loc từ 0 đến 0,5 m; so B1, B3 (α_a = α_e = 0,05), B4, ĐX; thêm quét hệ số tương quan ρ từ −0,5 đến 0,9 |
| N3: Bảng 2 | Ba nhóm: fix σ_loc = 0,03 m (70%), float 0,3 m (20%), loss 1,0 m (10%); α = 0,1; 100 lần lặp; so ngưỡng chung với ngưỡng theo nhóm |

**Những điểm bản thảo chưa nói rõ, phải chốt ở SPEC §10 trước khi viết mã (T22):**

| # | Chưa rõ | Giả định đề xuất (có thể đổi khi duyệt) |
|---|---|---|
| U1 | "Trôi chậm" của sai số định vị | AR(1) dừng theo từng trục, độ lệch chuẩn σ_loc, hằng số thời gian 5 s (SPEC §10.1) |
| U2 | Tham số AR(1) của sai số bám | φ = exp(−0,1/1,0), σ = 0,05 m, theo cả hai trục |
| U3 | Sai số hướng ψ | Xe là đĩa nên E = max_τ ‖Δp_τ‖/σ_τ (bỏ r_max·\|Δψ\|) |
| U4 | Số tác nhân mỗi mẫu | Một tác nhân, nên 𝒥 luôn khác rỗng (không có mẫu −∞) |
| U5 | "Đi về phía đường của xe" | Hướng tới một điểm ngẫu nhiên trên đường xe trong 3 s tới |
| U6 | Tốc độ quay và gia tốc: hằng trong mỗi mẫu hay đổi theo từng bước | Hằng trong mỗi mẫu. Nếu N2 lệch nhiều thì thử thêm phương án đổi theo từng bước |
| U7 | σ_loc dùng cho N1 | 0,1 m. Bảng 1 gần như không phụ thuộc giá trị này (xem §10.4) |
| U8 | Lưới σ_loc của N2 | {0; 0,05; 0,1; 0,2; 0,3; 0,4; 0,5} m |
| U9 | Cách "ép tương quan ρ" | Giữ độ lớn sai số xe, đổi hướng thành unit(ρ·g + √(1−ρ²)·u), trong đó g là phương xe – tác nhân lấy dấu theo phần hụt của tác nhân, u là hướng gốc của sai số xe; σ_loc = 0,1 m; lưới ρ ∈ {−0,5; 0; 0,5; 0,9} (SPEC §10.4) |
| U10 | Độ phủ của B1, B3, B4 | Đều đo bằng P(R_test ≤ q_phương pháp), với R là điểm số hụt khoảng cách thật |
| U11 | Định nghĩa B4 | q_A(α) + max E_i trên tập hiệu chỉnh |
| U12 | Cỡ mẫu N3 | n tổng = 1000 (theo nhóm ≈ 700/200/100); 2000 mẫu kiểm tra, cùng tỉ lệ nhóm |

### 10.3. Các giai đoạn

| Giai đoạn | Nội dung | Điều kiện để chuyển bước |
|---|---|---|
| G20 | Chốt SPEC §10 (U1–U12) | SPEC §10 được duyệt |
| G21 | Bộ sinh dữ liệu và điểm số `num41/gen.py`, `num41/scores.py`; test TC-41a..e | Test đạt; kiểm tra bằng mắt vài quỹ đạo mẫu |
| G22 | Chạy N1 | `logs/num41/n1_coverage.csv`; khớp lý thuyết theo §10.4 |
| G23 | Chạy N2 (σ_loc và ρ) | `logs/num41/n2_bounds.csv`, `n2_rho.csv` |
| G24 | Chạy N3 | `logs/num41/n3_groups.csv` |
| G25 | Hình N1–N3, bảng đối chiếu với bản thảo, đề xuất sửa | Báo cáo `report/BAO_CAO_TAI_LAP_4_1.md`; mọi số truy được về log |

### 10.4. Tiêu chí khớp

**N1 (Bảng 1) có chuẩn lý thuyết, không phụ thuộc bộ sinh dữ liệu.** Với điểm số liên tục, độ phủ của phân vị phù hợp có phân phối Beta(k, n+1−k). Cộng thêm phương sai nhị thức của 2000 mẫu kiểm tra, ta có:

| n \ α | 0,20 | 0,10 | 0,05 |
|---|---|---|---|
| 100 | 0,802 ± 0,040 | 0,901 ± 0,030 | 0,950 ± 0,022 |
| 500 | 0,800 ± 0,020 | 0,900 ± 0,015 | 0,950 ± 0,011 |
| 1000 | 0,800 ± 0,015 | 0,900 ± 0,012 | 0,950 ± 0,008 |

- Bảng 1 của bản thảo khớp với bảng này trong phạm vi sai số Monte Carlo.
- **Yêu cầu:** trung bình nằm trong ±3 SE (SE = độ lệch chuẩn/√200) quanh giá trị lý thuyết; độ lệch chuẩn sai khác không quá 15%.
- Nếu không đạt thì đó là lỗi cài đặt (ví dụ có trùng điểm số, hoặc tập hiệu chỉnh và tập kiểm tra không độc lập), không phải do mô hình.

**N2 và N3 phụ thuộc bộ sinh dữ liệu.** Chia thành hai mức:

1. **Khớp định tính (bắt buộc):**
   - ĐX đạt 0,90 ± 0,01 ở mọi σ_loc;
   - B1 giảm dần theo σ_loc;
   - ngưỡng q_ĐX ≤ q_B3 ở mọi lần lặp (Mệnh đề 3);
   - B4 rộng hơn B3;
   - tỉ số q_ĐX/q_B3 tăng theo ρ;
   - ngưỡng theo nhóm đạt 0,90 ở từng nhóm, còn ngưỡng chung thiếu ở nhóm float và loss.
2. **Khớp định lượng (mong muốn):**
   - độ phủ sai khác không quá ±0,02;
   - ngưỡng sai khác không quá ±15% so với bản thảo, gồm 0,996 / 0,972 / 0,802; 1,82 / 7,81; 5,77 / 18,0; 9,21 / 25,6; 0,23 / 0,31; 0,963 / 0,818 / 0,620; 2,37 / 1,74 / 3,34 / 12,18.
   - Nếu không đạt mức 2 sau khi đã thử các phương án U6 và U1, **không chỉnh tham số để ép khớp**. Thay vào đó, chốt mã cùng hạt giống và đề xuất thay số trong bản thảo.

### 10.5. Tài nguyên và thời gian

- Mở vòng nên rất nhẹ:
  - N1 khoảng 9 × 200 × (1000 + 2000) mẫu, tức khoảng 5,4 triệu mẫu;
  - N2 khoảng 7 × 50 × 3000 mẫu, cộng phần quét ρ;
  - N3 khoảng 100 × 3000 mẫu.
- Vector hóa bằng numpy (khoảng cách đĩa–đĩa có công thức đóng), nên tổng thời gian tính dưới 10 phút.
- Viết mã, test và báo cáo ước khoảng 3–4 giờ.

### 10.6. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| Không khôi phục được đúng các giả định (U1–U12) mà tác giả đã dùng khi viết v0.1 | Hỏi NCS về mã gốc trước khi làm G21; nếu không có thì làm theo SPEC §10 và ghi rõ trong báo cáo |
| Điểm số bị trùng (ví dụ σ_loc = 0 và không có nhiễu khác) làm độ phủ vượt danh định | Luôn giữ nhiễu bám và trễ khác 0; TC-41d kiểm tra số điểm số trùng |
| B1 ở σ_loc = 0 không đạt 0,996 vì độ phủ phụ thuộc mạnh vào U5, U6 | Báo cáo độ nhạy theo U5 và U6; chỉ yêu cầu khớp định tính |
| Nhóm loss có ít mẫu (khoảng 100) nên ngưỡng theo nhóm dao động lớn | Báo cáo cả độ lệch chuẩn qua 100 lần lặp, không chỉ trung bình |
| Số liệu mới khác bản thảo ở Tóm tắt và Kết luận | Bảng đề xuất sửa liệt kê mọi vị trí dùng số của 4.1 (Tóm tắt, Mục 4.1, Kết luận) |

### 10.7. Duyệt và Hoàn thành (tái lập 4.1)

- [x] Duyệt PLAN §10 (19/11/2026)
- [x] Duyệt TASKS T22–T27 (19/11/2026)
- [x] Duyệt SPEC §10 (U1–U12) (19/11/2026)
- [ ] Hoàn thành G20–G25

---

## 11. CARLA chia ba phần: thiết lập theo Mục 4 → vòng kín A → vòng kín B (đề xuất, chưa duyệt)

*Thay cho §9 (§9 chỉ làm phương án B). Các việc T15–T21 được gộp vào T28–T37.*

### 11.1. Mục tiêu

Mục 4.2–4.6 của bản thảo v0.1 vẫn còn để trống ([X], "viết sau khi có kết quả"). Phần CARLA chia làm ba phần, chạy tuần tự:

| Phần | Nội dung | Đầu ra cho bản thảo |
|---|---|---|
| **1. Thiết lập theo thông số Mục 4** | Dựng môi trường CARLA theo §4.2 của bản thảo và theo từng bước của tài liệu hướng dẫn (11.2a), chưa đưa biên vào: xe, bộ chuyển lệnh, bộ phát nhiễu D0–D5, kịch bản S1–S4, bộ dự báo, bộ lập kế hoạch, bộ đánh giá trễ H bước, dữ liệu B0 dùng chung | Bảng 3 (tham số xe), ADE/FDE của bộ dự báo, bảng hạt giống, phần chung của 4.6 (thời gian dự báo, lập kế hoạch) |
| **2. Vòng kín theo phương án A** | Chạy B0–B6, ĐX-1/2/3 đúng quy trình bản thảo v0.1 (cột A của SPEC §3) | Bảng 4, Hình 3, Hình 4, Hình 5, Bảng 5, thời gian tính, đúng như 4.3–4.6 đã viết |
| **3. Vòng kín theo phương án B** | Chạy lại với các sửa đổi của phương án B (cột B của SPEC §3) | Cùng bộ bảng và hình theo B; so sánh A–B trên CARLA và so với 2D; đề xuất bản thảo dùng phương án nào |

Phần 2 và Phần 3 dùng chung toàn bộ môi trường, bộ dự báo, kịch bản và hạt giống kiểm tra của Phần 1. Nhờ vậy, so sánh A–B là so sánh ghép cặp, chỉ khác quy trình hiệu chỉnh.

**Giữ nguyên A và B:** định nghĩa hai phương án là hai cột của SPEC §3, không đổi. Bộ chạy CARLA gọi lại (import) phần hiệu chỉnh của `sim/run_old.py` (A) và `sim/run_new.py` (B), không chép và không sửa; `sim/`, `logs/A`, `logs/B` giữ nguyên. Phần 1 chỉ thay môi trường (xe, kịch bản, nhiễu theo hướng dẫn), dùng chung cho cả A và B. Quy trình hiệu chỉnh ở §8 của hướng dẫn trộn A và B (σ_τ phân vị 90% từ hạt giống 200–249 như B, lấy thưa 2 s như A), nên không dùng; Phần 2 theo cột A, Phần 3 theo cột B.

### 11.2. Thông số lấy từ Mục 4 của bản thảo (Phần 1)

| Hạng mục | Theo bản thảo | Ghi chú |
|---|---|---|
| Phần mềm | CARLA **0.9.15** (bạn chốt 19/11/2026, dùng cho cả ba phần), chạy trên **máy khác** (không cài ở máy này); chế độ đồng bộ, bước 0,05 s, Python API, không dùng cầu nối ROS 2 | Bản thảo và hướng dẫn ghi 0.9.16 → đề xuất sửa §4.2 thành 0.9.15. Máy khách nối tới máy chủ qua `--host/--port/--tm-port` |
| Xe | `vehicle.tesla.model3`, vật lý của CARLA | Sai số bám phát sinh tự nhiên |
| Điều khiển | Bộ chuyển lệnh (hướng dẫn §2.3): PI vận tốc, hệ số lái nhận dạng, bộ đệm lệnh tạo trễ D4/D5; Pure Pursuit 20 Hz trên **tư thế ước lượng** (§6.3) | Thứ tự một bước cố định theo §7.1: gửi lệnh → tác nhân → tick → đo có nhiễu → lập kế hoạch 10 Hz → tính lệnh |
| Bảng 3 | L, kích thước, δ_max và hệ số lái (thử vòng tròn), a_max và a_min (thử tăng tốc, phanh), RMS sai số bám nền, v_max 8,3 m/s, H = 30, Δt = 0,1 s, 10 Hz, d_s, α = 0,1, mức nhiễu định vị ba nhóm | Các ô [X] phải đo hoặc nhận dạng |
| Định vị | Bộ phát sai số theo §3.2 hướng dẫn: fixed/float là nhiễu trắng + thiên lệch Gauss–Markov; lost là dead-reckoning tích lũy theo gyro và odometry. Tham số `noise.yaml` của hướng dẫn (TẠM) | D0 fixed; D1 float; D2 mất GNSS bắt đầu 3–8 s, kéo dài 5–10 s; D3 sai số odometry ×3; D4 trễ thêm 50/100/200 ms; D5 trễ lấy mẫu từ phân phối. Nhóm g = trạng thái RTK quan sát được lúc lập kế hoạch (§3.4), không lấy theo tên điều kiện |
| Kịch bản | Theo §4 hướng dẫn: Town03; tác nhân chạy theo kịch bản lập trình sẵn (không autopilot), kích hoạt khi xe tự hành còn cách điểm xung đột P một khoảng s_trig ngẫu nhiên. Người đi bộ điều khiển bằng `WalkerControl`; xe máy, ô tô tắt vật lý và đặt vị trí mỗi bước. S1: 1–3 người đi bộ 0,8–1,8 m/s, s_trig 8–20 m, xuất phát cách tuyến 5 m, dừng giữa đường xác suất 0,2 trong 2 s. S2: 1–2 xe máy 3–8 m/s, góc cắt 30–90°, s_trig 10–25 m, đoạn tiếp cận 25 m. S3: giao cắt không đèn có xe máy và ô tô. S4: xe trước phanh gấp 2–5 m/s² | Hướng dẫn chưa có cấu hình chi tiết S3, S4 (C8). Tầm kích hoạt phải lớn hơn quãng phanh ở v_max cộng dự trữ, tính lại từ a_min đo được |
| Dự báo | Trajectron++ huấn luyện trên nhật ký CARLA, hạt giống 0–199; vận tốc hằng làm mức nền; báo ADE/FDE | Tác nhân quan sát bằng giá trị chuẩn của CARLA (mức M1/M2 của §9); không làm M3 |
| Lập kế hoạch và đánh giá | Frenet có ràng buộc biên (§6.2): độ lệch ngang −1,5…1,5 m bước 0,25 m; vận tốc đích 0…v_max bước 0,5 m/s; thời gian 3, 4, 5 s; dự phòng phanh a_min. Bộ đánh giá trễ H bước (§6.4) ghi d_plan, d_true, err_agent, err_ego theo (τ, j) | Phần 1 chạy B0 với σ_τ = 1 và ghi (d̂ − d) thô để Phần 2, 3 ước lượng σ_τ |
| Thống kê | Lấy thưa, KTC Clopper–Pearson, Wilcoxon và McNemar có hiệu chỉnh Holm | Bước lấy thưa: 2 s ở A, 3 s ở B |
| Hạt giống (Bảng hạt giống của bản thảo) | 0–199 huấn luyện dự báo; 200–249 ước lượng σ_τ; 250–399 hiệu chỉnh; 400–449 chứng nhận; 500–699 kiểm tra | Chỗ cần quyết định: xem 11.5 |

### 11.2a. Phần 1 làm theo các bước của tài liệu hướng dẫn

Tài liệu: `document/Huong dan chi tiet mo phong CARLA (Tesla Model 3) - Bai bao 1 - NCS Nguyen Van Huynh.docx`. Mã trong tài liệu là mã khung, chưa chạy kiểm chứng; mỗi bước chỉ coi là xong khi đạt phép kiểm tra của chính tài liệu.

| Bước hướng dẫn | Nội dung | Phép kiểm tra phải đạt | Giai đoạn |
|---|---|---|---|
| C1 (§1.3, 1.5, 1.6) | Kết nối máy chủ ở máy khác, chế độ đồng bộ, dọn dẹp bằng try/finally, quy đổi tọa độ tay trái ↔ tay phải ở một chỗ | C1-a: phiên bản máy khách = máy chủ, nạp được Town03. C1-b: 1200 bước, số khung tăng đúng 1 mỗi tick. C1-c: quy đổi đi–về sai số < 1e-6; xe quay trái đúng chiều | G26 |
| C2 (§2) | Sinh Tesla Model 3, trích L, δ_max, kích thước, rear_overhang; bộ chuyển lệnh; 6 phép thử nhận dạng, mỗi phép lặp ≥ 5 lần; ghi `tesla_model3.yaml` | C2: bán kính quay khớp L/tan δ sai số < 5% trong vùng tuyến tính; bám quỹ đạo chuẩn ở 8 m/s không dao động; ghi RMS sai số ngang | G27 |
| C3 (§3) | Bộ phát nhiễu, `noise.yaml`, `conditions.yaml` D0–D5, nhãn nhóm định vị | C3: đồ thị sai số một lượt D2 tăng khi mất GNSS, giảm khi có lại; σ theo nhóm khớp `noise.yaml` (sai lệch < 10%) | G28 |
| C4 (§4) | `scenarios.py`, `scenarios.yaml` S1–S4 | C4: cùng hạt giống → cùng quỹ đạo tác nhân (sai khác = 0); video ngắn mỗi kịch bản để GVHD duyệt | G28 |
| Mục 6–7 | Hình học đa giác, Frenet, Pure Pursuit, bộ đánh giá trễ H bước, `sim_runner`, logger (cycles/steps/meta) | C6-a: kế hoạch trùng thật → R = 0; dịch tác nhân lại gần 0,5 m → R ≈ 0,5/σ_τ. Chạy khói (§9.3): 1 hạt giống × mọi tổ hợp S×D, đủ cột | G28 |
| C5 (§5) | Thu dữ liệu B0 hạt giống 0–199 ở 10 Hz; vận tốc hằng; Trajectron++ lịch sử 2 s, H = 3 s; đóng băng trọng số và lưu mã băm | C5: hình dự báo chồng quỹ đạo thật cho 5 tình huống ngẫu nhiên; ADE Trajectron++ < ADE vận tốc hằng | G29 |

Hướng dẫn §8–10 (σ_τ, Thuật toán 1, chạy hàng loạt, thống kê) thuộc Phần 2 và Phần 3. Phần ROS 2 (§1.4, 3.5, 9.4 E8 trên máy nhúng, 9.5 kiểm tra tương đương) không làm trong kế hoạch này (C9).

### 11.3. Các giai đoạn

| Giai đoạn | Phần | Nội dung | Điều kiện để chuyển bước |
|---|---|---|---|
| G26 | 1 | C1: máy khách Python 3.10 + gói `carla` 0.9.15 nối tới máy chủ CARLA trên máy khác; chế độ đồng bộ; quy đổi tọa độ | Đạt C1-a, C1-b, C1-c |
| G27 | 1 | C2: nhận dạng Tesla Model 3, bộ chuyển lệnh, chỉnh PI; điền Bảng 3 | Đạt C2; Bảng 3 không còn ô [X] nào, mỗi số có log |
| G28 | 1 | C3, C4, mục 6–7: bộ phát nhiễu D0–D5, kịch bản S1–S4, lập kế hoạch, bộ bám, bộ đánh giá, chương trình chạy một lượt và chạy hàng loạt (chia shard, chạy tiếp sau khi ngắt, bắt lỗi từng lượt) | Đạt C3, C4, C6-a; chạy khói đủ 24 ô S×D với B0 không lỗi; P95 thời gian một chu kỳ nhỏ hơn 0,1 s |
| G29 | 1 | C5: chạy B0 trên hạt giống 0–249; huấn luyện bộ dự báo; ADE/FDE | Đạt C5; bộ dự báo đã đóng băng (có mã băm) và log B0 dùng chung |
| G30 | 2 | Bộ chạy phương án A cho CARLA (chuyển `sim/run_old.py` sang, như `runner.py` đã làm cho B) | Chạy được trên backend giả; test đạt |
| G31 | 2 | Chạy A: hiệu chỉnh, chứng nhận, kiểm tra, thử loại bỏ cơ chế, quét cho Hình 4 | Có `logs/carla_A/` đầy đủ, có checkpoint |
| G32 | 2 | Phân tích và báo cáo A: Bảng 4, Hình 3–5, Bảng 5, 4.6; so với 2D A | Mọi số truy được về log; có đề xuất lời văn 4.3–4.6 |
| G33 | 3 | Kiểm tra lại bộ chạy B hiện có theo SPEC §3, ước lượng σ_τ từ B0 hạt giống 200–249 | Test đạt |
| G34 | 3 | Chạy B: cùng hạt giống kiểm tra như A, thêm B3′ và quét α | Có `logs/carla_B/` |
| G35 | 3 | Báo cáo B, so sánh A–B trên CARLA và so với 2D; đề xuất bản thảo | Báo cáo tổng hợp; đóng gói |

### 11.4. Tài nguyên và thời gian

- CARLA 0.9.15 chạy trên máy khác (bạn quản lý). Máy này không cài CARLA. Claude viết mã và test trên backend giả ở máy này; chạy thật qua mạng hoặc chép mã sang máy CARLA (C6).
- Máy khách cần Python 3.10 và gói `carla` 0.9.15 (gói này không hỗ trợ Python 3.13), cài ở nơi chạy mã khách.
- Hướng dẫn §9.2 cho phép chạy song song nhiều máy chủ CARLA (cổng RPC cách nhau 2, cổng Traffic Manager riêng), chia việc bằng `--shard`.
- Ước tính theo hướng dẫn §9.2 (đo lại trên 100 lượt đầu ở G28):
  - mỗi lượt khoảng 40 s mô phỏng, chạy không hiển thị nhanh gấp 4 lần thời gian thực;
  - E4 của mỗi phương án: 4 S × 6 D × 10 phương pháp × 50 lượt = 12.000 lượt ≈ 33 giờ trên một máy chủ, ≈ 17 giờ với hai máy chủ;
  - cộng thêm hiệu chỉnh, chứng nhận, quét α, thử loại bỏ cơ chế.
- Chạy theo khối 25 lượt có checkpoint (đã có trong `runner.py`).

### 11.5. Chỗ cần quyết định (chốt ở G28–G29)

| Mã | Vấn đề | Đề xuất |
|---|---|---|
| C1 | Bảng hạt giống của bản thảo chỉ có 400–449 cho chứng nhận, nhưng A cho phép thử lại tối đa 3 lần, mỗi lần một tập mới. Ở 2D dùng 600–649, nhưng dải này trùng tập kiểm tra 500–699 của bản thảo | Dùng 400–449, 450–499, 700–749 |
| C2 | Số lượt kiểm tra mỗi ô S×D. Hướng dẫn §9.1 ghi E4 dùng hạt giống 500–699 và "mỗi ô ≥ 50 lượt" (tổng 12.000 lượt) | Mỗi ô S×D dùng 50 hạt giống 500–549 cho mọi phương pháp (ghép cặp); kiểm tra số mẫu sau lấy thưa ≥ 865 mỗi ô, thiếu thì mở rộng tới 699 |
| C3 | Trajectron++: cần mã và trọng số ngoài. Nếu không huấn luyện được thì dùng CTRA | Thử Trajectron++ trước; nếu không được, ghi rõ trong bản thảo |
| C4 | Hình 4 "quét [ký hiệu mất khi trích] ở S2–D1" | Xác nhận với bản thảo gốc; nhiều khả năng là quét α |
| C5 | Mức nhiễu định vị: hướng dẫn §3.2 có mô hình và `noise.yaml` (TẠM, NCS chốt); `logs/carla_params/params_table_4_2.md` có bộ số khác (fix 0,03 m; float 0,30 m; mất GNSS bước ngẫu nhiên 0,08 m/√s) | Dùng mô hình và số của hướng dẫn, ghi TẠM cho tới khi NCS chốt; dùng chung cho A và B |
| C6 | Nơi chạy mã khách: (a) ở máy này, nối qua mạng tới máy CARLA; (b) chép mã sang máy CARLA và chạy tại chỗ | (b) cho chạy hàng loạt, vì chế độ đồng bộ gọi API nhiều lần mỗi bước nên độ trễ mạng làm chậm; (a) cho kiểm tra C1 ban đầu. Cần bạn cho biết địa chỉ, cổng, hệ điều hành của máy CARLA |
| C7 | Mã hiện có `carla_sim/` dựng lại kịch bản 2D trong CARLA, không theo cấu trúc của hướng dẫn (Town03, kích hoạt theo khoảng cách, bộ phát nhiễu Gauss–Markov) | Viết mới theo cây thư mục của hướng dẫn §0.5 tại `ws/av_conformal/` (configs, av_core, carla_env, scripts); dùng lại thuật toán biên của `sim/` và phần đã chạy được của `carla_sim/`; giữ `carla_sim/` để tham khảo. Bộ chạy A (T32) và B (T35) gắn vào `av_conformal` |
| C8 | Hướng dẫn §4.3 để trống S3 (`{...}`) và S4 | Tự thiết kế theo mô tả của bản thảo (S3: xe máy + ô tô, hướng đến và thời điểm ngẫu nhiên; S4: tác nhân phía trước phanh 2–5 m/s²), ghi TẠM, gửi NCS duyệt |
| C9 | Phần ROS 2 (EKF robot_localization, E8 trên máy nhúng, kiểm tra tương đương) | Không làm; thời gian tính (4.6) đo trong chế độ khóa bước trên máy chạy CARLA, ghi rõ máy đo |

### 11.6. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| GPU không đủ | Giảm chất lượng hiển thị (chế độ không hiển thị, `-RenderOffScreen -quality-level=Low`) |
| Máy chủ ở máy khác: mạng chậm hoặc rớt kết nối; máy chủ "đứng" khi chương trình dừng giữa chế độ đồng bộ | Chạy mã khách ngay trên máy CARLA (C6); try/finally trả về chế độ bất đồng bộ; bỏ qua lượt đã xong khi chạy lại; khởi động lại máy chủ mỗi khoảng 500 lượt |
| Bộ lập kế hoạch không đủ nhanh | Lưới vận tốc 1,0 m/s (351 ứng viên); chạy đồng bộ, không yêu cầu thời gian thực |
| Tốn quá nhiều giờ máy | Chạy A và B tuần tự theo khối có checkpoint; ưu tiên tập kiểm tra và B1, B3, ĐX-2 trước |
| Phương án A trên CARLA cho độ phủ thấp như ở 2D (ĐX-1 0,874) | Báo cáo trung thực; đó là lý do có Phần 3 |
| Mất tính tất định do CARLA (vật lý, AI người đi bộ) | Chế độ đồng bộ, cố định hạt giống của Traffic Manager; test chạy lặp cùng hạt giống |

### 11.7. Duyệt và Hoàn thành (CARLA ba phần)

- [ ] Duyệt PLAN §11 và TASKS T28–T37
- [ ] Phần 1: G26–G29
- [ ] Phần 2: G30–G32
- [ ] Phần 3: G33–G35
