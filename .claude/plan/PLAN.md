# KẾ HOẠCH — Mô phỏng phương án cũ / mới cho bài báo "Biên an toàn phù hợp có xét sai số xe tự hành"

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

## 9. Kế hoạch chuyển sang CARLA (đề xuất, chưa duyệt)

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
