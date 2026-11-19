# PHÂN TÍCH 2 — Thay đổi của bản mới (v0.2) so với bản cũ (v0.1) và so sánh kết quả

*16/11/2026.*

- *Bản cũ = gói mô phỏng v0.1 (phương án A và B; `logs/old`, `logs/new`).*
- *Bản mới = giai đoạn mở rộng v0.2 (`logs/ext`, `figs/H7–H11`, `report/BAO_CAO_MO_RONG_v0.2.md`). Bản mới chỉ chạy phương án B (cùng B0).*
- *Phân tích chi tiết bản cũ xem Phân tích 1.*

---

## 1. Tóm tắt

- **Bản mới không thay đổi phương pháp.**
  - Vẫn 11 phương pháp: B0–B6, B3′, ĐX-1/2/3.
  - Vẫn giữ α = 0,10, d_s = 0,5 m, H = 3 s, khoảng lấy thưa 3 s và chứng nhận PAC.
- **Bản mới mở rộng phần thử nghiệm:**
  - 6 kịch bản mới, 5 điều kiện suy giảm mới;
  - 5 tập dữ liệu, trong đó có các tập ngoài phân phối (OOD);
  - 9 thí nghiệm E1–E9;
  - 19 bài kiểm thử tự động.
- **Kết quả trên tập IN giống hệt bản cũ.** Nhờ đó, mọi khác biệt về kết luận đến từ phép thử mới, không đến từ mã bị đổi.
- **Ba kết luận của bản cũ bị điều chỉnh mạnh:**
  1. ĐX-1 **không hiệu quả hơn** B1 hay B3′ khi so ở cùng độ phủ.
  2. "Phương án B khắc phục toàn bộ" chỉ đúng **trong phân phối**. Khi điều kiện thay đổi, ĐX-1 tụt xuống 0,844–0,865.
  3. "B1 phủ thiếu" không còn ý nghĩa thống kê khi tăng lên 30 hạt giống.

---

## 2. Thay đổi về thông số và phạm vi

### 2.1. Bảng so sánh thông số

| Hạng mục | Bản cũ v0.1 | Bản mới v0.2 | Thay đổi |
|---|---|---|---|
| Xe, planner, bộ bám | Model 3; 351 ứng viên Frenet; Pure Pursuit; dự phòng −6 m/s² | **Giữ nguyên.** E7 thử thêm lưới 663 ứng viên | — |
| Đường | Chỉ đường thẳng, làn 3,5 m | Thêm **cung tròn R ∈ {25; 50} m** (S7: 15 m thẳng + 40 m cung, Frenet trên đường cong). E7 thử thêm làn 3,0 m | Mới |
| Kịch bản | S1–S4 | S1–S4 + **S5–S10** | +6 |
| Điều kiện | D0–D5 | D0–D5 + **D6–D10** | +5 |
| Số ô S×D | 24 | 110 | ×4,6 |
| Nhận thức | Nhiễu Gauss, không che khuất | Thêm **che khuất hình học** (S5) và **suy giảm nhận thức** (D10: nhiễu ×3, mất phát hiện 10%, trễ 100 ms) | Mới |
| Tác nhân | Không phản ứng | Thêm **phản ứng theo TTC** (S9) | Mới |
| Nhãn định vị | Luôn đúng | Thêm **nhãn sai 30%** (D8) | Mới |
| Chấp hành | a ∈ [−6; 3] luôn đạt | Thêm **đường trơn** (D9: xe chỉ đạt a ∈ [−3; 2] trong khi planner vẫn giả định [−6; 3]) | Mới |
| Tập dữ liệu | Chỉ IN (hiệu chỉnh và kiểm tra cùng 24 ô) | IN, OOD-S, OOD-D, OOD-SD (giữ ngưỡng của IN) và RECAL (hiệu chỉnh lại trên 110 ô) | Mới |
| Hạt giống kiểm tra | 500–514 | 500–514 (IN), 500–529 (E9), 700–709 (OOD), 710–719 (RECAL test), 800–999 và 1400–1499 (RECAL hiệu chỉnh/chứng nhận), 1000–1299 (E4), 1300–1399 (E8), 1500–1604 (E3) | Tách khối, TC-11 kiểm tra không trùng |
| Cờ phân tích | — | `unavoidable` cho S5 (TTC lúc lộ diện < thời gian phanh tối thiểu) | Mới |
| Kiểm thử mã | Không có | 19 test `pytest` (TC-01..TC-18 và smoke test 110 ô) | Mới |
| Quy mô | Khoảng 9.000 lượt | 25.520 dòng lượt trong `logs/ext/episodes.csv`, cộng thêm các lượt của E1–E9 | ×3–5 |

### 2.2. Thông số các kịch bản mới (lấy từ `sim/scenarios_ext.py`)

| Mã | Nội dung | Thông số chính |
|---|---|---|
| S5 | Người đi bộ khuất sau xe đỗ | Xe đỗ 4,5 × 1,8 m tại x = 38–48 m, tâm y ≈ 2,8 m. Người đi bộ 1,2–2,5 m/s, khởi động khi xe cách 16–26 m. Tác nhân chỉ vào tập 𝒥_t khi đường ngắm không bị che |
| S6 | Xe máy chen làn | Từ làn trái y = 3,5 m, góc 5–15°, 6–10 m/s, cách 8–20 m. Dao động ngang AR(1) σ = 0,3 m/s |
| S7 | Đường cong + ô tô ngược chiều | R = 25 hoặc 50 m. Ô tô 5–8 m/s, lấn tâm đường 0–0,5 m |
| S8 | Mật độ cao | 4–6 tác nhân: 1–2 người đi bộ, 2–3 xe máy đi bầy cách nhau 2–4 m, 0–1 ô tô. Xuất hiện lệch nhau 0–3 s |
| S9 | Tác nhân tương tác | Khi TTC < 2 s: nhường (giảm tốc 2 m/s²) với xác suất 0,6, hoặc tăng tốc băng qua với xác suất 0,4 |
| S10 | Trái giả định vận tốc hằng | Người đi bộ zigzag ±60° mỗi 1–2 s. Xe máy rẽ gắt ω = 0,8 rad/s trong 1 s |

### 2.3. Thông số các điều kiện mới (lấy từ `sim/conditions_ext.py`)

| Mã | Nội dung | Thông số | Nhãn |
|---|---|---|---|
| D6 | Kết hợp | D1 + trễ thêm 100 ms | float |
| D7 | Mất GNSS dài | Bắt đầu mất ở 0,5–1,5 s, kéo dài 15–20 s. **Vì mỗi lượt tối đa 16 s, gần như cả lượt bị mất GNSS** | loss |
| D8 | Nhãn sai | Trạng thái thật là float, nhưng 30% thời gian báo `fix` | fix/float (sai) |
| D9 | Đường trơn | Xe đạt a ∈ [−3; 2] m/s²; thiếu lái 25%; trượt ngang AR(1) σ = 0,08 | fix |
| D10 | Nhận thức suy giảm | Nhiễu 0,15 m / 0,30 m/s (×3); mất phát hiện 10% khung; trễ 100 ms | fix |

### 2.4. Các thí nghiệm mới

| Mã | Mục đích | Cách làm |
|---|---|---|
| E1 | So sánh ở cùng độ phủ | Quét 8 mức α ∈ {0,01 … 0,20}, nội suy tại độ phủ 0,90 / 0,95, KTC bootstrap |
| E2 | Ablation ACI 2×2 | (cập nhật trên chu kỳ trống hay không) × (γ = 0,02 hay 0,005), trên IN-D1 và OOD-D7 |
| E3 | Lực kiểm định PAC | Bảng n_cert ∈ {100, 200, 400, 800}, M ∈ {1, 3}; cộng một lần chạy thật |
| E4 | Khối D2 chuyên biệt | 150 lượt hiệu chỉnh + 150 lượt chứng nhận chỉ gồm D2 |
| E5 | Tự tương quan | Khoảng lấy thưa 3/4/6 s; 1 mẫu mỗi lượt; max theo lượt |
| E6 | Tách E_track / E_replan | Nhánh mở vòng chạy song song |
| E7 | Độ nhạy | d_s ∈ {0,5; 1,0} m; lưới 351/663; làn 3,5/3,0 m |
| E8 | σ_τ theo kịch bản | Ước lượng σ_τ riêng cho từng S1–S10 |
| E9 | Tăng cỡ mẫu | 30 hạt giống cho tập IN |

---

## 3. Phần nào chạy thực, phần nào giả lập ở bản mới

*"Chạy thực" = thực thi vòng kín trong bộ mô phỏng 2D và có log. Vẫn **không có** CARLA, xe thật hay ROS 2.*

### 3.1. Chạy thực (vòng kín, có log)

| Hạng mục | Quy mô |
|---|---|
| Tập IN | 15 hạt giống × 24 ô × 11 phương pháp (giống hệt v0.1) |
| OOD-S | 36 ô × 10 hạt giống = 360 lượt cho mỗi phương pháp |
| OOD-D | 20 ô × 10 hạt giống = 200 lượt cho mỗi phương pháp |
| OOD-SD | 30 ô × 10 hạt giống = 300 lượt cho mỗi phương pháp |
| RECAL | Hiệu chỉnh 3 × 50 lượt, chứng nhận tối đa 3 × 50 lượt trên 110 ô; kiểm tra 110 ô × 10 hạt giống = 1.100 lượt cho mỗi phương pháp |
| E1 | 8 mức α × 4 phương pháp, chạy vòng kín trên IN và OOD-SD |
| E2 | ACI 4 biến thể × 2 phương pháp × 2 tập, chạy vòng kín (`aci_trace.csv`, 24 MB) |
| E3 | 1 lần chứng nhận thật trên hạt giống 1500–1604 (n = 407) |
| E4 | 300 lượt D2 |
| E5 | Cấu hình `episode_block_max`: chạy vòng kín với q = 5,841 |
| E7 | 5 cấu hình × 5 phương pháp trên S1–S4 |
| E8 | Lượt B0 trên hạt giống 1300–1399 |
| E9 | Hạt giống 500–529 |
| S9 | Thuật toán 1 chạy 5 vòng lặp riêng |
| E6 | Nhánh mở vòng: quỹ đạo kế hoạch được bám không lập lại kế hoạch, chạy song song trong mô phỏng |

### 3.2. Giả lập (mô hình thay thế)

- **Giữ nguyên như v0.1:** động lực học xe đạp; định vị bằng nhiễu tổng hợp; dự báo **vận tốc hằng** (vẫn chưa có Trajectron++); tác nhân hình đĩa.
- **Mới, nhưng vẫn là mô hình giản lược:**

| Mô hình mới | Cách giả lập | Giới hạn |
|---|---|---|
| Che khuất (S5) | Giao đoạn đường ngắm với hộp chữ nhật 2D (`segment_intersects_aabb`) | Không có chùm tia LiDAR, không che một phần |
| Đường trơn (D9) | Cắt giới hạn gia tốc và tăng thiếu lái | Không có mô hình lốp hay hệ số ma sát μ |
| Mất phát hiện (D10) | Bỏ khung với xác suất 10%, giữ dự báo cũ | Không có cảnh báo giả (false positive) |
| Nhãn sai (D8) | Đổi nhãn ngẫu nhiên | Không có mô hình lỗi của bộ lọc EKF |
| Tương tác (S9) | Luật TTC ngẫu nhiên đơn giản | Không phải mô hình hành vi học từ dữ liệu |

### 3.3. Tính toán tổng hợp (không phải lượt chạy xe)

- **E3:** các cột "xác suất đậu ở p_true = 0,93 / 0,95" và "dư độ phủ" là **tính trên phân phối nhị thức** (giải tích hoặc Monte Carlo). Chỉ dòng n = 407 là từ lượt chạy thật.
- **E1:** giá trị tại độ phủ 0,90 / 0,95 là **nội suy** giữa các mức α đã chạy. Các ô có cờ "trong miền nội suy = False" là ngoại suy, không đáng tin.
- **E5:** ρ_k và n_eff tính trên chuỗi R đã log.
- **E8:** σ_τ tính trên dữ liệu B0 đã log.
- **TC-05, TC-07:** dữ liệu tổng hợp (synthetic) hoặc Monte Carlo trong test.

---

## 4. So sánh kết quả bản cũ và bản mới

### 4.1. Tái lập: tập IN

| Phương pháp | v0.1 (B) | v0.2, IN 15 hạt giống | v0.2, E9 30 hạt giống |
|---|---|---|---|
| B1 | 0,872 | 0,872 | 0,892 (KTC ±0,012, **chứa 0,90**) |
| ĐX-1 | 0,908 | 0,908 | 0,921 |
| ĐX-2 | 0,939 | 0,939 | 0,944 |
| ĐX-3 | 0,897 | 0,897 | 0,900 |

- Kết quả trùng tuyệt đối với 15 hạt giống (TC-01 sai khác < 1e-9). **Mã mở rộng không làm hỏng S1–S4.**
- Với 30 hạt giống, B1 đạt 0,892 và KTC chứa 0,90. Kết luận của v0.1 rằng "B1 phủ thiếu" phần lớn là nhiễu mẫu.

### 4.2. Kết quả theo tập (độ phủ điểm số)

| | v0.1 IN | OOD-S | OOD-D | OOD-SD | RECAL |
|---|---|---|---|---|---|
| B1 | 0,872 | 0,872 | 0,818 | 0,776 | 0,897 |
| B3′ | 0,990 | 0,981 | 0,967 | 0,952 | 0,983 |
| B5 | 0,748 | 0,718 | 0,661 | 0,604 | 0,667 |
| B6 | 0,903 | 0,924 | 0,878 | 0,916 | 0,909 |
| ĐX-1 | 0,908 | 0,924 | **0,865** | **0,844** | 0,951 |
| ĐX-2 | 0,939 | 0,936 | 0,929 | 0,906 | 0,965 |
| ĐX-3 | 0,897 | 0,885 | 0,909 | 0,882 | 0,889 |

### 4.3. Đối chiếu từng kết luận

| # | Kết luận ở v0.1 | Kết quả ở v0.2 | Trạng thái |
|---|---|---|---|
| K1 | ĐX-1 thu hẹp biên 65,6% so với B3 (25,83 → 8,89 m) | Con số vẫn đúng. Nhưng **E1 (H8) cho thấy ở cùng độ phủ, ĐX-1 ≈ B1 ≈ B3′**: mọi KTC của Δt_end và Δm₃ₛ đều chứa 0. Biên hẹp hơn chỉ vì phủ ít hơn | ❌ **Phải sửa cách trình bày** |
| K2 | ĐX-1 đạt độ phủ 0,908 ≥ 0,90 | Đúng trong IN. Sai ở OOD-D (0,865) và OOD-SD (0,844). Ở D7 chỉ còn 0,75 | ◐ Chỉ đúng trong phân phối |
| K3 | ĐX-2 khôi phục D1/D2 (0,908 / 0,961) | Bền nhất trong ba đề xuất: 0,906–0,936 trên OOD; D7 đạt 0,96–0,97. Ở cùng độ phủ trên IN, biên hẹp hơn 0,9–1,5 m với KTC < 0 (3/24 cặp). Trên OOD-SD thì không còn lợi thế hiệu quả | ✅ Được củng cố (có giới hạn) |
| K4 | ACI (ĐX-3) ổn định 0,876–0,909 ở D0–D5 | Vẫn giữ khoảng 0,88–0,91 khi dịch chuyển. Nhưng γ = 0,02 làm α_t dao động ±0,5, thường âm; biên 13–16 m. γ = 0,005 cho cùng độ phủ với q thấp hơn khoảng 15%. Không sửa được độ phủ có điều kiện (S7 0,73; S10 0,80) | ◐ Đúng một phần; cấu hình chưa tối ưu |
| K5 | Cập nhật ACI trên chu kỳ trống làm α_t trôi | E2 đo được: độ phủ giảm khoảng 1,5 điểm phần trăm (0,885 so với 0,900). **Cơ chế "trôi dương" không thấy rõ trong số liệu** | ◐ Hiệu ứng nhỏ |
| K6 | Độ phủ vật lý ≥ 0,995 ở mọi biên | Ở S5–S10 còn khoảng 0,95; d_min giảm từ khoảng 8 m xuống 5,5 m. Ở S1–S4 vẫn 1,000 kể cả khi d_s = 1,0 m hoặc làn 3,0 m (E7) | ◐ Bão hòa là do kịch bản quá dễ |
| K7 | Va chạm bằng 0% với mọi biên | OOD-SD 5,7–7,0%, RECAL 1,2%, **như nhau ở mọi phương pháp có biên** (p_Holm = 1,0). Nguyên nhân: S5 không tránh được (10–12 lượt), D9 trơn (13–17%), S7 | 🔄 Biên conformal không thay được giới hạn vật lý |
| K8 | Khoảng lấy thưa 3 s làm ρ₁ giảm từ 0,353 xuống 0,152 | Lên 6 s, ρ₁ vẫn 0,166. Giả thiết A1 chưa thỏa. Độ phủ tăng theo Δ (0,908 → 0,946), dấu hiệu chọn mẫu lệch | ❌ Chưa đủ |
| K9 | Nhóm `loss` thiếu mẫu (n = 2–19), cần khối D2 khoảng 130–150 lượt | E4 xác nhận: 150 lượt D2 cho n_loss khoảng 114–117, chứng nhận riêng được với q_loss = 4,18 (thấp hơn 5,74 của v0.1). Nhưng phủ D7 chỉ 0,874 | ✅ Xác nhận; thêm giới hạn D7 |
| K10 | n_min = 39 cho PAC | E3: để dư độ phủ ≤ 2% cần **n ≈ 800** với M = 1. Với n = 400, dư là +2,75% | ✅ Có bảng cỡ mẫu cụ thể |
| K11 | E_τ bị lập lại kế hoạch chi phối (D0: 0,586 → 1,741) | E6: đúng với B0 ở D0. **Khi định vị suy giảm (D1, D2, D6–D8), E_track chi phối**: P95 ở D7 là 12,5σ, E_replan ≈ 0 | 🔄 Cần nói hai chiều |
| K12 | PAC cho chứng nhận an toàn hơn (v0.1: q 2,04 → 2,55, đạt ở lần thử 2) | RECAL: Thuật toán 1 dao động (2,29 → 2,55 → 3,56 → 2,66); PAC đẩy q lên 3,59 (m₃ₛ 12,5 m, +41%). Phủ 0,951, cao hơn mục tiêu nhiều. S9 không hội tụ (dao động 0,55) | 🔄 Lộ ra chi phí và hạn chế |
| K13 | σ_τ ước lượng thực nghiệm tốt hơn công thức cố định | E8: σ_τ lệch mạnh theo kịch bản (S4 2–2,8 lần, S7 1,4–1,7 lần, S6 0,45 lần σ_τ chung). Nên chuẩn hóa theo loại tình huống | 🔄 Cần thêm một bước |
| K14 | B5 (Gauss) sụp ở D1/D2 | Sụp mạnh hơn khi dịch chuyển: 0,60–0,72 | ✅ Củng cố |

### 4.4. Hiệu quả: cái giá của độ bền

Mỗi ô ghi biên m₃ₛ / tỉ lệ hoàn thành.

| | v0.1 IN | OOD-SD | RECAL |
|---|---|---|---|
| B1 | 7,0 m / 55% | 7,0 m / 45% | 9,3 m / 42% |
| ĐX-1 | 8,9 m / 46% | 8,9 m / 39% | **12,5 m / 35%** |
| ĐX-2 | 10,3 m / 42% | 11,5 m / 35% | 13,3 m / 33% |
| ĐX-3 | 13,1 m / 43% | 16,4 m / 32% | 15,5 m / 37% |
| B3′ | 15,0 m / 31% | 15,0 m / 28% | 16,3 m / 27% |

- Khi hiệu chỉnh lại trên dữ liệu đa dạng (RECAL), biên của ĐX-1 tăng 41% và tỉ lệ hoàn thành giảm từ 46% xuống 35%.
- Ở mọi tập, tỉ lệ hoàn thành của các phương pháp có biên chỉ khoảng 30–55%. Ở E7, B5 đạt 81–86%, nhưng đổi lại phủ không đủ.

---

## 5. Đánh giá bản mới

**Điểm mạnh:**
1. Thiết kế OOD/RECAL trả lời đúng câu hỏi quan trọng nhất cho triển khai: phương pháp có bền khi điều kiện thay đổi hay không.
2. E1 (so sánh ở cùng độ phủ) loại bỏ được thiên lệch lớn nhất của v0.1.
3. Có bộ kiểm thử tự động 19/19 và tái lập chính xác v0.1.
4. Có cờ `unavoidable`, tách được va chạm do vật lý khỏi va chạm do biên.
5. Kết luận được sửa trung thực theo dữ liệu, kể cả những chỗ bất lợi cho ĐX-1.

**Điểm yếu còn lại:**
1. Vẫn chỉ là mô phỏng 2D với dự báo vận tốc hằng. Chưa đánh giá được bộ dự báo, và S7/S10 yếu chủ yếu vì vận tốc hằng.
2. ĐX-3 và B6 chạy với γ = 0,02 (chưa tối ưu), nên số liệu ACI ở OOD/RECAL đang làm ACI trông kém hơn thực tế.
3. `summary.json` của các tập OOD không có KTC theo tập, nên các chênh lệch nhỏ (0,882 so với 0,90) chưa được kiểm định.
4. **Báo cáo tự sinh v0.2 có 7 chỗ sai hoặc nói quá**:
   - ghi "4/4 test" trong khi thực tế là 19/19;
   - khuyến nghị "n ≥ 400 cho dư ≤ 2%" mâu thuẫn với bảng;
   - viết "ĐX-3 bền nhất";
   - cơ chế "α_t trôi dương" không khớp số liệu;
   - "E_replan chi phối" chỉ đúng ở D0;
   - S9 được viết là "giữ được độ phủ" dù không hội tụ;
   - diễn giải "ĐX-2 bền hơn trên OOD-SD".

   Xem `DANH_GIA_KET_QUA_MO_RONG_v0.2.md` §7.
5. D7 gần như mất GNSS cả lượt (15–20 s so với lượt tối đa 16 s), nên đây là một kịch bản cực đoan. Nên ghi rõ khi trình bày.
6. Ở S1–S4, độ phủ vật lý vẫn bão hòa, nên điểm ⑤ chỉ được giải quyết nhờ các kịch bản mới.

---

## 6. Hệ quả cho bản thảo

| Nội dung trong bài | Theo v0.1 | Sửa theo v0.2 |
|---|---|---|
| Đóng góp của ĐX-1 | "Biên hẹp hơn 65,6%, hiệu quả hơn" | "Hiệu chỉnh đúng mức 1 − α; ở cùng độ phủ, hiệu quả tương đương đối chứng" |
| Đóng góp của ĐX-2 | Khôi phục D1/D2 | Đề xuất có lợi thế thực sự trong phân phối và bền nhất khi dịch chuyển; cần n ≥ 39 mẫu mỗi nhóm và nhãn đáng tin |
| ACI | Ổn định | Giữ được độ phủ dài hạn; nên dùng γ nhỏ (0,005); không bảo đảm độ phủ có điều kiện |
| Phạm vi bảo đảm | Ngầm hiểu là chung | Chỉ trong phân phối hiệu chỉnh; báo cáo thêm độ phủ tệ nhất theo ô |
| Hạn chế | — | Thuật toán 1 có thể dao động; A1 chưa thỏa (ρ₁ ≈ 0,15); σ_τ lệch theo kịch bản; biên không thay được giới hạn phanh |
| CARLA | 50 lượt chứng nhận | n_cert khoảng 400–800; khối D2 riêng khoảng 150 lượt |
