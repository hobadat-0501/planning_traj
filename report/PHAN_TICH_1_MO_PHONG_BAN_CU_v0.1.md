# PHÂN TÍCH 1 — Bộ mô phỏng bản cũ (v0.1): thông số, phạm vi chạy thực / giả lập, điểm mạnh và điểm yếu

*16/11/2026. Nguồn số liệu: `logs/old/`, `logs/new/`, `figs/H1–H6`, `report/BAO_CAO_KET_QUA_VA_DE_XUAT_SUA_DOI.md`, mã `sim/core.py`, `sim/common.py`, `run_old.py`, `run_new.py`.*

**Cách hiểu "bản cũ" trong tài liệu này:** đây là gói mô phỏng v0.1, chạy xong lúc 09:59 ngày 16/11. Gói này gồm hai phương án chạy trên cùng một lõi:

- **Phương án A**: cài đặt đúng theo bản thảo v0.1 của bài báo.
- **Phương án B**: cài đặt các sửa đổi lý thuyết đã đề xuất.

Bản mới (v0.2) được phân tích riêng ở *Phân tích 2*.

---

## 1. Phần nào chạy thực, phần nào giả lập

Toàn bộ dự án là **mô phỏng 2D bằng Python/NumPy**. Không có CARLA, không có xe Hunter SE, không có ROS 2, không có cảm biến thật. Vì vậy, trong tài liệu này "chạy thực" có nghĩa là **được thực thi thật trong vòng kín của bộ mô phỏng và có log từng chu kỳ**. Nó không có nghĩa là chạy trên xe hay trên CARLA.

### 1.1. Phần chạy thực (thực thi vòng kín, có log)

| Thành phần | Mô tả | Bằng chứng log |
|---|---|---|
| Vòng kín xe – planner – bộ bám | Mỗi lượt chạy 20 Hz × tối đa 16 s. Planner Frenet chạy thật ở 10 Hz với 351 ứng viên, lọc an toàn bằng biên m_τ, bộ bám Pure Pursuit | `cycles.csv` và `episodes.csv` ở `logs/old/`, `logs/new/` |
| Ước lượng σ_τ (chỉ B) | 50 lượt B0, hạt giống 200–249 | `logs/new/calibration.json` |
| Hiệu chỉnh lặp (Thuật toán 1) | 3 khối × 50 lượt (250–399), chạy lại vòng kín sau mỗi lần cập nhật q | `calibration.json` |
| Chứng nhận | Tối đa 3 lần thử × 50 lượt (400–499, 600–649) | `calibration.json` |
| Tập kiểm tra ghép cặp | 15 hạt giống (500–514) × 6 điều kiện × 4 kịch bản = 360 lượt cho mỗi phương pháp. A có 10 phương pháp (3.600 lượt), B có 11 phương pháp (3.960 lượt) | `episodes.csv`: 3.600 + 3.960 dòng |
| Quét α | B1, B3′, ĐX-2 (và ĐX-1) với α ∈ {0,01; 0,02; 0,05; 0,10; 0,20}, mỗi mức 360 lượt | `logs/new/alpha_sweep.csv` |
| ACI (B6, ĐX-3) | Cập nhật α_t trực tuyến trong vòng kín, phản hồi trễ H = 30 bước | `cycles.csv` |
| Thời gian tính | Đo thật thời gian chạy lõi NumPy của planner (P95 khoảng 1,37–1,49 ms) | `episodes.csv` |

Tổng cộng khoảng **9.000 lượt** vòng kín (PLAN §5).

### 1.2. Phần giả lập (mô hình thay thế cho thế giới thật)

| Thành phần | Trong mô phỏng | Ngoài đời / CARLA | Hệ quả |
|---|---|---|---|
| Động lực học xe | Mô hình xe đạp động học, có trễ bậc nhất; D3 thêm thiếu lái và trượt ngang AR(1) | PhysX: chuyển tải, lốp phi tuyến, ABS | Sai số bám E nhỏ và "sạch" hơn thực tế |
| Định vị | Nhiễu tổng hợp cộng vào vị trí thật: AR(1), trôi tuyến tính khi mất GNSS. Nhãn fix/float/loss **được gán theo kịch bản điều kiện**, không đến từ máy thu GNSS | Bộ lọc EKF, máy thu RTK thật | Nhãn luôn đúng. Điều này làm ĐX-2 có lợi một cách không thực tế (v0.2 mới thêm D8 nhãn sai) |
| Nhận thức tác nhân | Vị trí thật cộng nhiễu Gauss trong bán kính 40 m. **Không có che khuất, không mất phát hiện, không trễ pipeline** | LiDAR/camera, mạng phát hiện | Sai số A chỉ đến từ dự báo, không đến từ nhận thức |
| Dự báo quỹ đạo | **Vận tốc hằng (CV)** | Trajectron++ (theo bản thảo) | Kết quả định lượng không chuyển thẳng sang được Trajectron++ |
| Tác nhân | Hành vi theo kịch bản, có nhiễu AR(1) ở tốc độ quay và gia tốc dọc; **không phản ứng với xe tự hành** | Người và xe thật có tương tác | Dữ liệu không phụ thuộc chính sách, nên Thuật toán 1 dễ hội tụ hơn thực tế |
| Đường | **Chỉ đường thẳng** trục x, làn ±1,75 m, đích x = 75 m | Đường cong, giao lộ | Không thử được lái Ackermann với độ cong lớn |
| Tác nhân dạng hình | Tập đĩa cứng (người 1 đĩa, xe máy 2 đĩa, ô tô 3 đĩa) | Đa giác hoặc hộp thật | Đủ để so A_h với A_c |

### 1.3. Phần tính toán tổng hợp (không chạy xe, không vòng kín)

| Phân tích | Cách làm | Ghi chú |
|---|---|---|
| H5a: chứng nhận có điều kiện so với PAC | **Monte Carlo trên phân phối nhị thức tổng hợp**: 4.000 lần lặp mỗi điểm p_true, n = 187, k_cond = 170, k_PAC = 178 | Các con số 76,8% (chấp nhận sai) và 1,9% (PAC) **không phải từ lượt chạy xe**, mà là xác suất lý thuyết được mô phỏng số |
| H5b: phân phối hậu chứng nhận | 3.000 kịch bản tổng hợp | Như trên |
| n_min = 39 | Công thức giải tích ⌈ln(0,05/3) / ln(0,9)⌉ | Không cần chạy |
| ρ₁ (tự tương quan) | Tính trên chuỗi R đã log | Từ dữ liệu chạy thực |
| A_h so với A_c | Tính lại trên chuỗi đã log | Từ dữ liệu chạy thực |

---

## 2. Thông số mô phỏng v0.1

### 2.1. Xe và bộ điều khiển

| Thông số | Giá trị |
|---|---|
| Kích thước | Cỡ Tesla Model 3: L = 2,875 m; hộp 4,69 × 1,85 m; cầu sau cách đuôi 0,96 m; r_max = 3,85 m |
| Giới hạn | δ_max = 0,6 rad; ω_max = 0,8 rad/s; a ∈ [−6; 3] m/s²; v_max = 8,3 m/s |
| Trễ và sai số | Trễ gia tốc 0,25 s; trễ lái 0,1 s; sai số hệ số lái ±5% mỗi lượt; trễ lệnh nền 50 ms; bù trước vận tốc tại t + 0,5 s |
| Tần số | Mô phỏng 20 Hz (Δt = 0,05 s); planner 10 Hz; chân trời H = 30 × 0,1 s = 3,0 s |
| Bộ bám | Pure Pursuit, L_d = 2 + 0,3v, chạy 20 Hz |
| Planner | 351 ứng viên Frenet = 13 độ lệch ngang (±1,5 m, bước 0,25 m) × 9 vận tốc đích (0–8,3 m/s) × 3 thời gian T ∈ {3, 4, 5} s |
| Chi phí | J = (v_max − v_đích)² + 0,1∫jerk² + 2d_f² |
| Lọc an toàn | d̂ ≥ d_s + m_τ, với d_s = 0,5 m |
| Dự phòng | Khi không còn ứng viên hợp lệ: phanh a = −6 m/s² |
| Đường và lượt chạy | Đường thẳng, làn ±1,75 m, đích x = 75 m, tối đa 16 s |

### 2.2. Sáu điều kiện suy giảm D0–D5

| Mã | Mô tả | Thông số | Nhãn |
|---|---|---|---|
| D0 | RTK cố định | σ = 0,03 m / 0,003 rad | fix |
| D1 | RTK thả nổi | AR(1) 5 s, 0,3 m / 0,02 rad | float |
| D2 | Mất GNSS | 5–10 s, trôi tích lũy, hội tụ lại sau 1,5 s | loss khi mất, fix khi có |
| D3 | Trượt bánh | Thiếu lái 15%, trượt ngang AR(1) σ = 0,04 | fix |
| D4 | Trễ cố định | Thêm {50, 100, 200} ms | fix |
| D5 | Trễ ngẫu nhiên | Gamma(2; 0,05), cắt ở 0,3 s | fix |

### 2.3. Bốn kịch bản S1–S4

| Mã | Mô tả |
|---|---|
| S1 | Người đi bộ sang đường, 0,8–1,8 m/s; 20% dừng giữa đường 2–4 s |
| S2 | Xe máy cắt ngang góc 30–90°, 3–8 m/s |
| S3 | Giao cắt không đèn: xe máy + ô tô |
| S4 | Xe phía trước phanh gấp 2–5 m/s² |

### 2.4. Phương pháp và hiệu chỉnh

- **Các phương pháp:**
  - B0: không có biên.
  - B1: chỉ xét tác nhân.
  - B2: B1 + 0,3m.
  - B3: cộng hai biên riêng.
  - B3′: hai thành phần có dấu, mỗi phần ở mức α/2 (chỉ có ở phương án B).
  - B4: ống bám xấu nhất.
  - B5: ràng buộc cơ hội dạng Gauss.
  - B6: ACI trên B1.
  - ĐX-1: biên gộp.
  - ĐX-2: biên gộp theo nhóm định vị.
  - ĐX-3: ACI với γ = 0,02, phản hồi trễ H, cửa sổ 500.
- **Tham số chung:** α = 0,10.

**Khác biệt giữa A và B:**

| | A (bản thảo) | B (sửa đổi) |
|---|---|---|
| σ_τ | Công thức cố định 0,05 + 0,04τ (σ₃₀ = 1,25 m) | Ước lượng thực nghiệm trên 200–249 (σ₁ = 0,172 → σ₃₀ = 3,484 m) |
| Chu kỳ không có tác nhân | Giữ lại, gán R = −∞ (khoảng 17,9% mẫu) | Loại bỏ |
| Khoảng lấy thưa | 2 s, chồng cửa sổ 1 s | 3 s, không chồng |
| Sai số tác nhân | Sai số tâm A_c | Cận Hausdorff A_h |
| Chứng nhận | Có điều kiện (q̂ ≤ q_plan) | PAC Bonferroni, δ = 0,05/3, k(187) = 178 |
| Đối chứng | — | Thêm B3′ |
| Báo cáo | Chung | Tách chu kỳ khả thi / chu kỳ dự phòng |

---

## 3. Kết quả chính v0.1

| | A: độ phủ điểm số / m₃ₛ / hoàn thành | B: độ phủ điểm số [KTC 95%] / m₃ₛ / hoàn thành |
|---|---|---|
| B0 | 0,329 / 0 / 80,8% | 0,135 / 0 / 80,8% (va chạm 10,6%) |
| B1 | 0,887 / 4,43 m / 70,6% | 0,872 [0,853; 0,889] / 7,00 m / 55,3% |
| B3 | 0,998 / 16,32 m / 27,5% | 0,997 / 25,83 m / 10,0% |
| B3′ | — | 0,990 / 15,04 m / 30,8% |
| B5 | 0,848 / 3,48 m / 76,7% | 0,748 / 3,56 m / 76,7% |
| B6 | 0,926 / 7,31 m / 62,8% | 0,903 / 10,77 m / 47,5% |
| ĐX-1 | **0,874** / 4,02 m / 71,4% | **0,908** [0,892; 0,922] / 8,89 m / 46,1% |
| ĐX-2 | 0,893 / 4,13 m / 71,4% | **0,939** / 10,31 m / 41,9% |
| ĐX-3 | 0,904 / 8,23 m / 60,0% | 0,897 / 13,06 m / 42,5% |

- **Độ phủ an toàn vật lý (d ≥ d_s):** đạt từ 0,995 đến 1,000 ở **mọi phương pháp có biên** trong cả A lẫn B, và va chạm bằng 0% (trừ B5 0,3% và ĐX-3 0,3%).
- **Độ phủ theo điều kiện định vị, ĐX-1 / ĐX-2:**

| | D1 | D2 |
|---|---|---|
| A | 0,759 / 0,856 | 0,732 / 0,796 |
| B | 0,847 / 0,908 | 0,826 / **0,961** |

---

## 4. Điểm mạnh của bộ mô phỏng v0.1

1. **Vòng kín thật sự.** Biên ảnh hưởng planner, planner ảnh hưởng quỹ đạo, quỹ đạo ảnh hưởng điểm số. Thuật toán 1 phải lặp vì phân phối điểm số phụ thuộc chính sách, nên đây là kiểm chứng đúng tinh thần bài báo, không chỉ là một phép tính ngoài vòng (offline).
2. **Tất định và tái lập được.** Hạt giống được chia khối tách bạch: σ, hiệu chỉnh, chứng nhận và kiểm tra dùng các khối riêng. Sau này v0.2 xác nhận lại bằng TC-01 (sai khác < 1e-9) và TC-18 (chạy đa tiến trình cho cùng kết quả).
3. **Thiết kế ghép cặp.** Mọi phương pháp chạy trên cùng 360 cấu hình hạt giống, nên dùng được kiểm định McNemar và Wilcoxon với hiệu chỉnh Holm. Đây là điểm mạnh thống kê so với việc so sánh trung bình đơn thuần.
4. **Thêm thước đo độ phủ điểm số P(R ≤ q).**
   - Đây là thước đo kiểm chứng trực tiếp Định lý 1.
   - Thước đo này lộ ra lỗi của phương án A mà độ phủ vật lý (bão hòa ở 1,000) không thấy: ĐX-1 của A chỉ đạt 0,874, và chỉ 0,847 nếu tính riêng trên chu kỳ có tác nhân.
5. **Tách được từng sửa đổi.**
   - B3 → B3′ cho thấy hiệu ứng chiếu hình học (−41,8% biên).
   - B3′ → ĐX-1 cho thấy hiệu ứng gộp (−40,9%).
   - Việc tách A_h và A_c cho chênh lệch +8,8% ở S2 và +19,9% ở S3.
   - Khoảng lấy thưa 2 s → 3 s làm ρ₁ giảm từ 0,353 xuống 0,152.
   - Mỗi lỗi của bản thảo đều có một con số định lượng đi kèm.
6. **Định lý 2 sửa đổi có cơ sở.** Monte Carlo cho thấy chứng nhận có điều kiện chấp nhận sai 76,8%, trong khi PAC chỉ 1,9%. Đồng thời lần chạy thật có một ví dụ PAC từ chối đúng lúc: lần thử 1, q = 2,04, bị bác.
7. **Có đối chứng mạnh.** Có B3′, B4, B5 và các đối chứng ACI (B6). B5 sụp ở D1/D2 (0,544 / 0,556) là bằng chứng rõ cho lựa chọn conformal thay vì giả định Gauss.
8. **Nhẹ và nhanh.** Khoảng 0,25 s mỗi lượt, khoảng 9.000 lượt trong 25–40 phút trên máy 2 lõi, nên lặp lại thí nghiệm rất rẻ.

---

## 5. Điểm yếu của bộ mô phỏng v0.1

### 5.1. Điểm yếu về độ trung thực (giả lập quá đơn giản)

| # | Điểm yếu | Hệ quả lên kết luận |
|---|---|---|
| Y1 | Chỉ có đường thẳng, 4 kịch bản đơn giản, 1–2 tác nhân | Không thử được độ cong lớn, mật độ cao, tương tác. Kết luận chỉ đúng trong một miền hẹp |
| Y2 | Tác nhân không phản ứng với xe | Dữ liệu không phụ thuộc chính sách đúng như giả định. Không kiểm tra được Thuật toán 1 khi có vòng phản hồi |
| Y3 | Không có che khuất và không mất phát hiện | Không có tác nhân xuất hiện đột ngột, nên đuôi phân phối của A bị đánh giá thấp |
| Y4 | Nhãn định vị luôn đúng | ĐX-2 được lợi một cách không thực tế |
| Y5 | Dự báo vận tốc hằng thay cho Trajectron++ | Không đánh giá được bộ dự báo. Số liệu định lượng không chuyển sang CARLA |
| Y6 | Động lực học xe đơn giản; phanh −6 m/s² luôn đạt | Va chạm hầu như bằng 0 với mọi biên |

### 5.2. Điểm yếu về thiết kế thí nghiệm

| # | Điểm yếu | Chi tiết |
|---|---|---|
| Y7 | **Độ phủ vật lý bão hòa** | d ≥ d_s đạt 1,000 ở mọi phương pháp có biên, nên thước đo an toàn "thật" không phân biệt được các phương pháp. Tất cả khác biệt nằm ở độ phủ điểm số, vốn là đại lượng thống kê |
| Y8 | **So sánh ở cùng α thay vì cùng độ phủ** | ĐX-1 "tốt hơn" B3′ (biên hẹp hơn) nhưng cũng phủ thấp hơn (0,908 so với 0,990). Chưa biết đây là hiệu quả thật hay chỉ là chọn một điểm khác trên cùng đường đánh đổi |
| Y9 | **Chỉ 15 hạt giống cho mỗi ô** | KTC theo ô rộng khoảng ±0,075. Kết luận "B1 phủ thiếu" (0,872) chưa vững |
| Y10 | **Chỉ có tập trong phân phối (IN)** | Hiệu chỉnh và kiểm tra cùng 24 ô S×D. Không biết các phương pháp bền đến đâu khi điều kiện thay đổi, trong khi đây là câu hỏi chính khi đưa lên xe thật |
| Y11 | **Nhóm `loss` thiếu mẫu** | Mỗi khối chứng nhận chỉ có n_loss = 2–19 < 39, nên không chứng nhận PAC riêng nhóm được. ĐX-2 chỉ có PAC tổng thể |
| Y12 | **E_τ trộn sai số bám với độ lệch do lập lại kế hoạch** | Ở D0, E/σ = 0,586 khi không có tác nhân nhưng 1,741 khi có. Chưa có nhánh mở vòng để tách |
| Y13 | **ACI chỉ chạy một cấu hình** | γ = 0,02, không có ablation. Nhận định "cập nhật trên chu kỳ trống làm α_t trôi" ở mục 6.8 của báo cáo v0.1 **không có bảng số đi kèm** |
| Y14 | **Thiếu kiểm thử mã tự động** | Tính đúng của khoảng cách hộp–đĩa, phân vị, k_PAC… chỉ được kiểm qua kết quả cuối |
| Y15 | **Khoảng lấy thưa 3 s chưa đủ** | ρ₁ = 0,152 vẫn khác 0, chưa có phương án theo khối lượt |
| Y16 | **σ_τ chung cho mọi kịch bản** | Chưa kiểm tra σ_τ có lệch theo kịch bản không |

### 5.3. Điểm yếu trong báo cáo v0.1

- Báo cáo ghi "Phương án B khắc phục **toàn bộ** sai lệch". Điều này quá mạnh, vì mới kiểm tra trong phân phối.
- Kết luận ACI định tính, không có số liệu.
- Lỗi chữ ở mục 6.5 (panel a/b, 4.000 so với 3.000 lần lặp) đã được sửa lúc 12:21.
- B1 của B có biên **lớn hơn** B1 của A (7,00 m so với 4,43 m) nhưng phủ **thấp hơn** (0,872 so với 0,887). Nguyên nhân là A tính cả mẫu −∞, khiến hai con số không so trực tiếp được. Báo cáo có giải thích ở mục 6.2 nhưng bảng chính dễ gây hiểu nhầm.

---

## 6. Đánh giá chung bản cũ

- **Về sửa lỗi lý thuyết của bản thảo, v0.1 làm tốt.** Mỗi lỗi (mẫu −∞, cửa sổ chồng, A_c, σ_τ cố định, chứng nhận có điều kiện) đều được định lượng và có đề xuất sửa cụ thể.
- **Về hiệu năng và độ bền của các đề xuất ĐX, v0.1 chưa đủ.** Lý do là chỉ thử trong phân phối, trên đường thẳng, với thước đo an toàn bão hòa và so sánh ở cùng α.
- Đây chính là 7 điểm ①–⑦ dẫn đến giai đoạn mở rộng v0.2:
  - ① so sánh ở cùng độ phủ (Y8);
  - ② ACI (Y13);
  - ③ PAC và cỡ mẫu (Y11);
  - ④ D2 chuyên biệt (Y11);
  - ⑤ an toàn vật lý bão hòa (Y7);
  - ⑥ E_track / E_replan (Y12);
  - ⑦ phạm vi kịch bản (Y1–Y4, Y10).
