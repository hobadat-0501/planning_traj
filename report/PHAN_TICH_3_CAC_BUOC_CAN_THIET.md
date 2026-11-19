# PHÂN TÍCH 3 — Tổng hợp toàn bộ báo cáo và các bước cần thiết tiếp theo

*19/11/2026. Tổng hợp từ bản gốc đến bản cuối, theo thứ tự thời gian.*

## 0. Tài liệu đã đọc

| # | Tài liệu | Vai trò |
|---|---|---|
| 1 | `document/Bai bao 1 - Ban thao tieng Viet v0.1` | Bản thảo gốc. Phương pháp được viết theo **phương án A** |
| 2 | `document/Huong dan chi tiet mo phong CARLA (Tesla Model 3)` | Hướng dẫn C1–C9, 20 tuần, mã khung chưa chạy |
| 3 | `document/Huong dan Muc 4`, `Khung bai bao 1` | Khung và yêu cầu Mục 4 |
| 4 | `ws/report/BAO_CAO_KET_QUA_VA_DE_XUAT_SUA_DOI` (v0.1, tự sinh) | Mô phỏng 2D: so sánh A và B, đề xuất sửa bản thảo |
| 5 | `ws/report/BAO_CAO_MO_RONG_v0.2` (tự sinh) | Kịch bản S5–S10, điều kiện D6–D10, OOD/RECAL, thí nghiệm E1–E9 |
| 6 | `ws/report/DANH_GIA_KET_QUA_MO_RONG_v0.2` | Đánh giá độc lập v0.2, chỉ ra 7 lỗi của báo cáo tự sinh |
| 7 | `ws/report/PHAN_TICH_1`, `PHAN_TICH_2` (và bản docx `BAO_CAO_1`, `BAO_CAO_2`) | Phân tích A, các thay đổi ở B, so sánh A–B |

---

## 1. Diễn tiến kết luận qua các phiên bản

| Kết luận | Bản thảo v0.1 | Mô phỏng 2D v0.1 | Mở rộng v0.2 | Trạng thái hiện tại |
|---|---|---|---|---|
| Cách cài đặt A (giữ R = −∞, lấy thưa 2 s, A_c, chứng nhận có điều kiện) | Đề xuất | Sai: ĐX-1 chỉ đạt 0,874 (0,847 trên chu kỳ có tác nhân); chấp nhận sai 76,8% | — | ❌ **Bỏ, dùng B** |
| ĐX-1 hẹp hơn B3 65,6% | Ngầm định "hiệu quả hơn" | Đúng về số | Ở cùng độ phủ: ĐX-1 ≈ B1 ≈ B3′ (E1) | ❌ Chỉ được nói "hiệu chỉnh đúng mức 1 − α" |
| ĐX-2 (ngưỡng theo nhóm định vị) | Đề xuất | Khôi phục D1/D2 | Lợi thế thật trong phân phối (biên hẹp hơn 0,9–1,5 m, KTC < 0); bền nhất ngoài phân phối (0,906–0,936) | ✅ **Đóng góp chính** |
| ACI (ĐX-3) | Đề xuất | Ổn định 0,88–0,91 | γ = 0,02 sai cấu hình; γ = 0,005 cho biên nhỏ hơn khoảng 15% | ◐ Phải chạy lại với γ = 0,005 |
| Giả thiết A1 (gần độc lập sau lấy thưa) | Giả thiết | ρ₁ từ 0,353 xuống 0,152 | Lên 6 s vẫn ρ₁ ≈ 0,15; độ phủ tăng theo Δ | ❌ Chưa thỏa, phải ghi vào hạn chế |
| B1 phủ thiếu | — | 0,872 | 30 hạt giống: 0,892, KTC chứa 0,90 | ❌ Không còn ý nghĩa thống kê |
| Độ phủ vật lý ≈ 1 | — | Bão hòa | Trên S5–S10 còn khoảng 0,95; trên S1–S4 vẫn bão hòa | ◐ Do kịch bản quá dễ |
| Va chạm | — | 0% | OOD-SD 5,7–7%, như nhau ở mọi biên (p = 1) | 🔄 Biên không thay được giới hạn phanh |
| σ_τ chung | Công thức cố định | Ước lượng thực nghiệm | Lệch mạnh theo kịch bản (S4 ×2–2,8; S6 ×0,45) | 🔄 Cần chuẩn hóa hoặc Mondrian theo kịch bản |
| Cỡ mẫu chứng nhận | 50 lượt | n_min = 39 | Dư độ phủ ≤ 2% cần n ≈ 800 (n = 400 cho dư 2,75%); khối D2 riêng khoảng 150 lượt | ✅ Có bảng cỡ mẫu |
| Sai số xe E_τ | Gộp | Bị lập lại kế hoạch chi phối | Chỉ đúng ở D0; khi định vị kém thì E_track chi phối | 🔄 Viết hai chiều |
| Thuật toán 1 hội tụ | Giả định | Hội tụ | RECAL và S9 dao động, không hội tụ | ❌ Hạn chế |
| Mất GNSS dài (D7) | — | — | ĐX-1 0,75–0,79; ngưỡng D2 không chuyển sang D7 (0,874) | ❌ Giới hạn của bảo đảm theo nhóm |

---

## 2. Khoảng trống phát hiện được

### 2.1. Hướng dẫn CARLA vẫn theo phương án A (quan trọng nhất)

Hướng dẫn chi tiết mô phỏng CARLA được viết trước khi có kết quả mô phỏng 2D. Nếu chạy đúng như hướng dẫn, CARLA sẽ lặp lại các lỗi đã được chứng minh ở 2D.

| Chỗ trong hướng dẫn | Đang ghi | Phải sửa theo B |
|---|---|---|
| §8.2 `thin(every_s=2.0)` | Lấy thưa 2 s, chồng cửa sổ | 3 s không chồng (= H); thêm cận tham chiếu 1 mẫu mỗi lượt |
| §6.4 `_finalize`: `R = -np.inf` | Chu kỳ không có tác nhân vẫn được đưa vào hiệu chỉnh | Loại chu kỳ trống khỏi hiệu chỉnh, chứng nhận và đánh giá; thống kê riêng |
| §6.4 `err_agent` | Độ lệch tư thế (tâm) | Thêm cận Hausdorff A_h (độ dời lớn nhất của đỉnh hoặc đĩa) |
| §8.3 chứng nhận | q̂_cert ≤ q_plan, 50 lượt (400–449), thử lại trên 450–499 | PAC Bonferroni (δ/M), n_cert ≈ 400–800 chu kỳ không chồng |
| §8.2 `q_by_group` | Đủ ⌈1/α⌉ − 1 = 9 mẫu là tính ngưỡng nhóm | Cần n ≥ 39 mỗi nhóm cho PAC; khối D2 riêng khoảng 150 lượt cho nhóm `lost` |
| §9.1 `methods` | Không có B3′ | Thêm B3′ (tách hiệu ứng chiếu hình học và hiệu ứng gộp) |
| B6, ĐX-3 | Không ghi γ | γ = 0,005 (hoặc lưới γ / DtACI); chỉ cập nhật trên chu kỳ có tác nhân |
| §10 thống kê | Độ phủ d ≥ d_s | Thêm độ phủ điểm số P(R ≤ q), tách khả thi / dự phòng, độ phủ tệ nhất theo ô |
| Ghi log | Kế hoạch và thực tế | Thêm rollout mở vòng để tách E_track / E_replan |
| §9.1 kịch bản | S1–S4 | Thêm ít nhất S5 (khuất), S7 (đường cong) để độ phủ vật lý không bão hòa |

### 2.2. Tham số chưa thống nhất giữa ba nguồn

| Tham số | Bản thảo | Hướng dẫn CARLA | Mô phỏng 2D |
|---|---|---|---|
| Nhiễu RTK fixed / float / lost | §4.1: 0,03 / 0,3 / 1,0 m; §4.2: [X] | `noise.yaml` (TẠM): white 0,02 / 0,10 m, bias 0,02 / 0,25 m; lost theo gyro/odo | 0,03 m; AR(1) 5 s 0,3 m / 0,02 rad; trôi 5–10 s |
| d_s | [X] m | Chưa ghi | 0,5 m (E7 thử 1,0 m) |
| Pure Pursuit | — | ld = max(1; 0,5v), δ ≤ 0,4 rad | ld = 2 + 0,3v, δ ≤ 0,6 rad |
| Cỡ mẫu chứng nhận | — | 50 lượt | 187 chu kỳ (v0.1); khuyến nghị 400–800 |
| Đánh số thí nghiệm | E4–E8 | E4–E8 | E1–E9 (khác nghĩa) |

Đánh số thí nghiệm trùng tên nhưng khác nội dung. Cần một bảng đối chiếu trước khi viết Mục 4.

### 2.3. Nhận diện và dự báo

- Hướng dẫn CARLA dùng `update_tracks(truth, t)`, tức tác nhân lấy từ ground truth (có thể thêm nhiễu). **Không cần mô hình nhận diện** cho bài này. Phải ghi giới hạn này trong bài.
- Dự báo: vận tốc hằng là mức nền bắt buộc; Trajectron++ có trong C5, cần dữ liệu hạt giống 0–199 và đóng băng trọng số trước hiệu chỉnh.
- Kết quả 2D cho thấy S7 và S10 yếu chủ yếu do vận tốc hằng, nên Trajectron++ là bước có ý nghĩa thật, không chỉ trang trí.

### 2.4. Báo cáo tự sinh v0.2 còn 7 lỗi

Chi tiết ở `DANH_GIA_KET_QUA_MO_RONG_v0.2.md` §7: ghi "4/4 test" (thực tế 19/19); khuyến nghị n ≥ 400 cho dư ≤ 2% (sai, cần khoảng 800); "ĐX-3 bền nhất"; cơ chế "α_t trôi dương"; "E_replan chi phối"; "S9 giữ được độ phủ"; "ĐX-2 bền hơn trên OOD-SD".

---

## 3. Các bước cần thiết, theo thứ tự

Nguyên tắc: làm việc rẻ, quyết định cấu hình trước; chỉ chạy CARLA (tốn hàng chục giờ) khi cấu hình đã chốt.

### Bước 1 — Chốt hướng (không cần chạy) · ưu tiên cao nhất

1. Chốt dùng **phương án B** cho bản thảo và CARLA.
2. Viết lại phần đóng góp: ĐX-1 = "hiệu chỉnh đúng mức 1 − α"; ĐX-2 = đóng góp chính; ACI = giữ độ phủ dài hạn, không bảo đảm có điều kiện.
3. Sửa 7 lỗi của báo cáo tự sinh v0.2 (để không đưa số sai vào bài).

**Đầu ra:** quyết định được ghi trong PLAN; báo cáo v0.2 đã sửa.

### Bước 2 — Thí nghiệm 2D còn thiếu (rẻ, vài giờ) · trước CARLA

Các kết quả này quyết định cấu hình chạy trên CARLA:

| Việc | Lý do | Quyết định cho CARLA |
|---|---|---|
| Chạy lại ĐX-3 và B6 với γ = 0,005 trên OOD/RECAL | Số liệu ACI hiện đang bị đánh giá thấp | Giá trị γ |
| Kiểm tra vì sao độ phủ tăng theo Δ (E5) | Có thể là lệch chọn mẫu, ảnh hưởng A1 | Cách lấy thưa |
| Thử Mondrian theo nhóm kịch bản (hoặc σ_τ theo kịch bản) | S7, S10 chỉ đạt 0,64–0,82 | Có thêm phương pháp ĐX-4 hay không |
| Thêm KTC theo tập OOD và độ phủ tệ nhất theo ô | Chênh lệch nhỏ chưa được kiểm định | Mẫu bảng kết quả |
| (Tùy chọn) so sánh bộ dự báo E10 | Đo mức Trajectron++ cần đạt | Có cần Trajectron++ không |

### Bước 3 — Cập nhật hướng dẫn CARLA theo phương án B

Sửa đúng các mục liệt kê ở §2.1: lấy thưa, loại chu kỳ trống, A_h, PAC, n ≥ 39 mỗi nhóm, B3′, γ, cột độ phủ điểm số, rollout mở vòng, thêm S5/S7. Có thể chuyển nguyên phần lõi đã kiểm thử từ `ws/sim` (19/19 test) sang `av_core` thay vì viết lại từ mã khung.

### Bước 4 — Chốt tham số Bảng I / Bảng §4.2

- Mức nhiễu fixed / float / lost: thống nhất một bộ số giữa bản thảo, `noise.yaml` và mô phỏng 2D, có căn cứ (datasheet RTK hoặc công bố).
- d_s (0,5 hay 1,0 m).
- n_cert (400 hay 800), M, δ; khối D2 riêng; số hạt giống mỗi ô.
- Lưới vận tốc 351 hay 663 ứng viên (E7 cho thấy kết quả gần như nhau).
- Bảng đối chiếu tên thí nghiệm giữa bản thảo, hướng dẫn và mô phỏng 2D.

### Bước 5 — CARLA mức M1: ground truth + nhiễu, dự báo vận tốc hằng

Theo hướng dẫn C1–C4, C6–C9 (đã sửa ở Bước 3):

1. C1–C2: cài CARLA 0.9.16, chế độ đồng bộ, nhận dạng Tesla Model 3 (kiểm tra C1-a/b/c, C2).
2. C3: bộ phát nhiễu và D0–D5 (+ D7 nếu muốn kiểm tra giới hạn mất GNSS dài).
3. C4: kịch bản S1–S4 (+ S5, S7), kiểm tra tất định.
4. Chạy khói → chạy thử 10 hạt giống → so xu hướng với 2D → báo cáo GVHD.
5. C6–C7: σ_τ, Thuật toán 1 (theo dõi dao động q), chứng nhận PAC.
6. C8: chạy đầy đủ. Ước lượng E4 khoảng 12.000 lượt, 17–33 giờ; chạy theo khối có điểm lưu.

**Điểm dừng kiểm tra:** nếu độ phủ hoặc xu hướng khác hẳn 2D thì dừng, tìm nguyên nhân trước khi chạy tiếp.

### Bước 6 — CARLA mức M2: Trajectron++

C5: thu dữ liệu hạt giống 0–199, huấn luyện, báo cáo ADE/FDE so với vận tốc hằng, đóng băng; chạy lại phần hiệu chỉnh và thí nghiệm chính. Đặc biệt xem S7, S10 có cải thiện không.

### Bước 7 — Sửa bản thảo bằng số liệu CARLA

- §2.3: câu dẫn tới bảng mô hình sai số; định nghĩa có dấu E_track / E_replan.
- §2.4, §3.1, §3.2: A_h, loại chu kỳ trống, Định lý 2 dạng PAC, Mệnh đề 4 chỉ cập nhật chu kỳ có tác nhân.
- §2.5: A1 lấy thưa 3 s, nêu ρ₁ ≈ 0,15 còn lại.
- §4.2: điền [X], thêm bảng mô hình sai số, B3′.
- §4.3: cột độ phủ điểm số, khả thi / dự phòng, độ phủ tệ nhất theo ô, so sánh ở cùng độ phủ.
- Hạn chế: Thuật toán 1 dao động, A1, σ_τ lệch theo kịch bản, D7, ground truth thay nhận diện, biên không thay được giới hạn phanh.

### Bước 8 — Tùy chọn, giai đoạn sau

- Detector và tracker thật (mức M3) nếu muốn bảo đảm bao phủ cả sai số nhận diện.
- ROS 2 và kiểm tra tương đương hai cách chạy (§9.5 hướng dẫn); đo thời gian trên máy nhúng (P95 < 100 ms).
- Đo nhiễu thật trên Hunter SE, kiểm định KS so với bộ phát nhiễu.

---

## 4. Đường găng

```
Bước 1 ─► Bước 2 ─► Bước 3 ─► Bước 4 ─► Bước 5 (M1) ─► Bước 6 (M2) ─► Bước 7
                         └────── C1–C2 cài đặt CARLA có thể làm song song từ đầu ──┘
```

- Bước 1–4 làm trên máy hiện có, không cần CARLA.
- C1–C2 (cài đặt, nhận dạng xe) không phụ thuộc phương án A/B, có thể bắt đầu ngay.
- Rủi ro lớn nhất: chạy CARLA theo hướng dẫn hiện tại (phương án A) rồi phải chạy lại toàn bộ.
