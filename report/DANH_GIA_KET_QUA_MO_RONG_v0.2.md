# Đánh giá kết quả mở rộng v0.2

*16/11/2026. Báo cáo này phân tích độc lập các kết quả sau:*
- *`logs/ext/*` (summary, calibration_recal, alpha_sweep / e1_iso_coverage, aci_trace, pac_power, calibration_d2, thinning_ext, e6_tracking_split, e7_sensitivity, sigma_by_scn, e9_in30);*
- *các hình `figs/H7–H11`;*
- *báo cáo tự sinh `report/BAO_CAO_MO_RONG_v0.2.md`.*

*Mục tiêu là đối chiếu số liệu thô với lời kết luận trong báo cáo tự sinh, chỉ ra chỗ nào được dữ liệu ủng hộ và chỗ nào bị nói quá.*

---

## 0. Tóm tắt điều hành

1. **Ưu thế của ĐX-1 biến mất khi so ở cùng độ phủ.**
   - Theo E1 / H8, ba phương pháp ĐX-1, B1 và B3′ nằm **trên cùng một đường đánh đổi** giữa độ phủ và thời gian hoàn thành t_end.
   - Khác biệt giữa chúng ở v0.1 thực chất chỉ là chọn một điểm khác nhau trên cùng đường cong đó. Nói cách khác, ĐX-1 cho độ phủ sát mức 1 − α hơn, chứ không hiệu quả hơn.
   - **ĐX-2 là đề xuất duy nhất có lợi thật**: trên tập IN, ở cùng độ phủ, biên m₃ₛ hẹp hơn 0,9–1,5 m và t_end ngắn hơn 0,17–0,32 s, với khoảng tin cậy (KTC) nằm hoàn toàn dưới 0.
   - Tuy vậy, lợi thế này **không còn trên OOD-SD**: mọi KTC ở đó đều chứa 0.
2. **Độ bền khi phân phối dịch chuyển:**
   - ĐX-1 rơi xuống 0,865 ở OOD-D và 0,844 ở OOD-SD.
   - ĐX-2 bền nhất trong ba đề xuất, đạt 0,906–0,936.
   - B3′ phủ cao nhất (0,95–0,99) nhưng biên khoảng 15 m.
   - B5 (Gauss) sụp, chỉ 0,60–0,72.
3. **ACI (ĐX-3) giữ được độ phủ biên khoảng 0,88–0,91, nhưng γ = 0,02 là một lựa chọn sai.**
   - Với γ = 0,02, α_t dao động trong khoảng ±0,5 và thường xuyên âm (H9), khiến q trung bình lên 4,3–4,4.
   - Với γ = 0,005, độ phủ vẫn đạt 0,900–0,901 trong khi q chỉ khoảng 3,6–3,8, tức **biên nhỏ hơn khoảng 15%**.
   - Vì vậy mọi số liệu của ĐX-3 trong các tập OOD và RECAL (đều chạy với γ = 0,02) **đánh giá thấp ACI**.
4. **Báo cáo tự sinh có 5 chỗ nói quá hoặc sai, cần sửa trước khi đưa vào bài.** Chi tiết ở §7: sai số lượng test, khuyến nghị cỡ mẫu PAC mâu thuẫn với chính bảng của nó, câu "ĐX-3 bền nhất", diễn giải E2 và E6, và nhận định S9 "giữ được độ phủ".
5. **Điểm ⑤ (độ phủ an toàn vật lý bão hòa) chỉ được giải quyết một phần.**
   - Trên S5–S10, độ phủ vật lý giảm còn khoảng 0,95, tức thước đo đã phân biệt được các trường hợp.
   - Trên S1–S4 vẫn bão hòa 1,000, kể cả khi đặt d_s = 1,0 m, làn hẹp 3,0 m hay lưới 663 ứng viên (E7).
   - Va chạm **không khác nhau** giữa các phương pháp có biên: p_Holm = 1,0 ở mọi so sánh.

---

## 1. Kiểm thử và tái lập

- `tests.txt` ghi **19/19 test đạt** trong 134,8 s (bản chạy lúc 14:43).
  - Các test này bao gồm TC-01 (hồi quy v0.1), TC-13..TC-17 (lõi mới), TC-18 (tất định khi chạy đa tiến trình) và smoke test cho 110 ô.
- Tập IN khớp v0.1 tuyệt đối: ĐX-1 0,908, ĐX-2 0,939, B1 0,872.
- ⚠️ Báo cáo tự sinh ở §2 ghi "**4/4** bài kiểm thử" và chỉ liệt kê TC-02, 05, 08, 09. Dòng "Ngày tạo" ghi 13:51, trong khi tệp được ghi lúc 14:41. Có vẻ báo cáo đã đọc một `tests.txt` cũ, hoặc bộ sinh báo cáo lọc thiếu dòng. Cần chạy lại `report_ext`.

---

## 2. Dịch chuyển phân phối (H7, `summary.json`)

Mỗi ô ghi: độ phủ điểm số / biên trung bình m₃ₛ (m).

| | IN | OOD-S | OOD-D | OOD-SD | RECAL |
|---|---|---|---|---|---|
| B1 | 0,872 / 7,0 | 0,872 / 7,0 | 0,818 / 7,0 | 0,776 / 7,0 | 0,897 / 9,3 |
| B3′ | 0,990 / 15,0 | 0,981 / 15,0 | 0,967 / 15,0 | 0,952 / 15,0 | 0,983 / 16,3 |
| B4 | 0,864 | 0,783 | 0,806 | **0,701** | 0,869 |
| B5 | 0,748 | 0,718 | 0,661 | **0,604** | 0,667 |
| B6 | 0,903 / 10,8 | 0,924 / 14,4 | 0,878 / 12,6 | 0,916 / 16,3 | 0,909 / 13,5 |
| ĐX-1 | 0,908 / 8,9 | 0,924 / 8,9 | **0,865** / 8,9 | **0,844** / 8,9 | 0,951 / 12,5 |
| ĐX-2 | 0,939 / 10,3 | 0,936 / 10,1 | 0,929 / 11,6 | 0,906 / 11,5 | 0,965 / 13,3 |
| ĐX-3 (γ = 0,02) | 0,897 / 13,1 | 0,885 / 13,2 | 0,909 / 14,7 | 0,882 / 16,4 | 0,889 / 15,5 |

**Nhận xét:**
- **Dịch chuyển theo điều kiện suy giảm (D) nguy hiểm hơn dịch chuyển theo kịch bản (S).** Ở OOD-S, ĐX-1 vẫn đạt 0,924, nhưng ở OOD-D chỉ còn 0,865.
  - Điều kiện tệ nhất là **D7 (mất GNSS dài)**: ĐX-1 đạt 0,75–0,79, B1 0,69–0,72.
  - ĐX-2 lại đạt 0,96–0,97 ở D7, vì nhóm `loss` có ngưỡng riêng.
- **Các ô yếu theo kịch bản:**
  - **S7 (đường cong, xe ngược chiều)**: ĐX-1 / ĐX-2 / ĐX-3 chỉ đạt 0,64 / 0,70 / 0,68 ở OOD-SD.
  - **S5 (khuất tầm nhìn)**: 0,70–0,79.
  - **S10 (hành vi phi vận tốc hằng)**: ĐX-3 chỉ 0,78–0,82.
  - Độ phủ biên 0,90 che giấu các ô chỉ đạt 0,64–0,73. Bài nên báo cáo thêm **độ phủ tệ nhất theo ô**.
- **E8 giải thích vì sao S7 và S10 yếu:**
  - σ_τ của S7 bằng 1,4–1,7 lần σ_τ chung; của S10 bằng 1,35–1,66 lần; của S4 lên tới 2,0–2,8 lần.
  - Ngược lại, S6 chỉ bằng 0,42–0,53 lần.
  - Điểm số chuẩn hóa bằng một σ_τ chung nên bị lệch theo kịch bản. Cần chuẩn hóa theo loại tình huống, hoặc dùng conformal Mondrian theo nhóm kịch bản, tương tự cách ĐX-2 chia theo nhóm định vị.
- **RECAL:**
  - Thuật toán 1 không hội tụ ở cả ĐX-1 (q: 2,29 → 2,55 → 3,56 → 2,66) lẫn S9 (1,51 → 1,77 → 2,34 → 1,46 → 2,01).
  - Chứng nhận PAC trên dữ liệu trộn đẩy q của ĐX-1 lên 3,59, tức m₃ₛ = 12,5 m (+41% so với v0.1). Kết quả là độ phủ 0,951, cao hơn hẳn mục tiêu, và tỉ lệ hoàn thành giảm còn 0,345.
  - Với ĐX-2 ở RECAL, ngưỡng nhóm `loss` lên tới 5,51.

---

## 3. E1 — So sánh ở cùng độ phủ (H8): phát hiện quan trọng nhất

- **Hình H8a và H8b:** các đường của B1, B3′ và ĐX-1 **chồng khít lên nhau**.
- **ĐX-1 so với B1 và B3′:**
  - Mọi KTC của Δt_end và Δm₃ₛ đều chứa 0, ở cả IN và OOD-SD, ở cả mức 0,90 và 0,95.
  - → Bản thảo **không được** viết rằng ĐX-1 "hiệu quả hơn". Chỉ được nói rằng ĐX-1 hiệu chỉnh để đạt đúng mức 1 − α, trong khi B1 phủ thiếu và B3′ phủ thừa.
- **ĐX-2 trên tập IN:** nằm dưới đường cong của các phương pháp khác trong khoảng độ phủ 0,80–0,95.
  - Có 3 cặp đạt ý nghĩa thống kê trong số 24 cặp hợp lệ, tức các cặp nằm trong miền nội suy:
    - ở mức 0,90, so với B1: Δm₃ₛ = −1,10 m [−1,87; −0,37];
    - ở mức 0,95, so với B1: −0,93 m;
    - ở mức 0,95, so với B3′: −1,24 m.
- **ĐX-2 trên OOD-SD:** các đường hội tụ lại và mọi KTC chứa 0.
  - Lợi thế hiệu quả của ĐX-2 chỉ còn trong phân phối đã hiệu chỉnh.
  - Ngoài phân phối, ưu điểm còn lại của ĐX-2 là **độ phủ thực tế cao hơn ở cùng q danh định**, không phải hiệu quả cao hơn.
- ⚠️ **Tập con `hard_S7_S8` ở OOD-SD:** Δt_end ≈ 0,000 với KTC rất hẹp (±0,005 s).
  - Nhiều khả năng t_end bị bão hòa vì lượt chạy hết giờ hoặc phải phanh dự phòng, nên cột này không có sức phân biệt.
  - Ở mức 0,95, cờ nội suy là False, nên không nên dùng tập con này làm bằng chứng.

---

## 4. E2 — ACI (H9)

| ĐX-3 | γ = 0,02 (cấu hình chính) | γ = 0,005 |
|---|---|---|
| IN, active_only: độ phủ / q TB | 0,899 / 4,26 | 0,901 / **3,77** |
| OOD-D, active_only | 0,901 / 4,44 | 0,900 / **3,63** |
| Dao động α_t (H9) | khoảng −0,6 … +0,55; thường âm (q = ∞) | khoảng −0,15 … +0,25 |

- **Kết luận chắc chắn:** γ = 0,02 quá lớn. α_t thường xuyên âm, khi đó q = ∞ và xe phải phanh dự phòng. Điều này giải thích vì sao ĐX-3 có biên 13–16 m và tỉ lệ dự phòng 25–35%.
  - → Nên đổi cấu hình chính sang **γ = 0,005** (hoặc dùng DtACI hay một lưới γ), rồi chạy lại hàng ĐX-3 và B6 cho các tập OOD và RECAL.
- **Chu kỳ trống (active_only so với all_cycles):** cập nhật cả trên chu kỳ trống làm độ phủ giảm khoảng 1,5 điểm phần trăm (0,885 so với 0,900). Hiệu ứng có thật nhưng nhỏ.
  - ⚠️ Báo cáo tự sinh nói chu kỳ trống làm "α_t trôi dương". Bảng của chính nó lại cho thấy α_t trung bình của biến thể all_cycles gần bằng, và α_t cuối còn thấp hơn, so với active_only. Lời giải thích cơ chế chưa được dữ liệu chứng minh, chỉ chênh lệch độ phủ là có thật.
- **ACI không sửa được độ phủ có điều kiện:**
  - Đường độ phủ trượt 200 bước trong H9 vẫn xuống 0,65–0,75 ở cả bốn biến thể.
  - Ở RECAL, S7 đạt 0,73, S10 đạt 0,80.

---

## 5. E3 / E4 — PAC và cỡ mẫu (H10)

**E3 — lực kiểm định PAC:**
- Bảng `pac_power` cho thấy **chỉ cấu hình n = 800, M = 1 mới có dư độ phủ ≤ 2%** (+1,87%).
- Với n = 400, M = 1, dư độ phủ là +2,75%. Xác suất đậu chỉ 62% khi độ phủ thật là 0,93, và 98% khi là 0,95.
- ⚠️ Mục 9 của báo cáo tự sinh khuyến nghị "n_cert ≥ 400, M = 1 (dư ≤ 2%)", **mâu thuẫn với chính bảng 6.1**. Cần sửa thành n ≥ 800 nếu muốn dư ≤ 2%, hoặc chấp nhận dư khoảng 2,75% với n = 400.
- Lần chạy thật với n = 407 đạt, với độ phủ thực tế 0,929.

**E4 — khối chuyên biệt D2:**
- Khối này cho n_loss ≈ 114–117, vượt xa ngưỡng tối thiểu 39, và chứng nhận độc lập được nhóm `loss` ở lần thử 2.
- Ngưỡng q_loss = 4,18 (m₃ₛ = 14,55 m), nhỏ hơn ngưỡng 5,74 của v0.1. Lý do là trước đây nhóm `loss` thiếu mẫu, nên phải dùng ngưỡng bảo thủ.
- Độ phủ nhóm `loss`:
  - trên IN (D2): 0,953, KTC [0,906; 0,981];
  - trên OOD-D (D7): **0,874**, KTC [0,810; 0,923].
- Như vậy, ngưỡng chứng nhận cho mất GNSS ngắn (D2) **không chuyển được sang** mất GNSS dài (D7). Cần ghi đây là giới hạn của bảo đảm theo nhóm.

---

## 6. E5–E9

### E5 — Tự tương quan theo lượt

- Tăng khoảng thinning Δ từ 3 s lên 6 s **không làm giảm ρ₁**: ρ₁ vẫn khoảng 0,15–0,17. Tỉ số n_eff / n chỉ khoảng 0,66–0,77.
- Giả thiết A1 (các mẫu độc lập sau thinning) chưa thỏa.
- Độ phủ lại **tăng theo Δ** (0,908 → 0,930 → 0,946). Đây là dấu hiệu chọn mẫu bị lệch theo thời điểm trong lượt chạy, chứ không chỉ do tương quan. Cần kiểm tra lại.
- Phương án lấy một mẫu ngẫu nhiên mỗi lượt cho 0,914 với KTC rộng ±0,06. Đây là cận tham chiếu sạch về mặt hoán đổi, nhưng tốn mẫu.
- Kết quả `episode_block_max` (0,856) không hợp lệ để so sánh, vì q không được lặp vòng kín. Không nên đưa vào bài.

### E6 — Tách E_track / E_replan (H11)

- ⚠️ Báo cáo tự sinh kết luận E_replan "chiếm phần lớn đuôi" sai số. Điều này **chỉ đúng ở D0 với B0** (E_replan TB 0,40, P95 1,99).
- Với ĐX-1 ở các điều kiện định vị suy giảm, **E_track mới là thành phần chi phối**, còn E_replan gần như bằng 0:

| Điều kiện | P95 của E_track / σ | E_replan |
|---|---|---|
| D1 | 4,9 | ≈ 0 |
| D2 | 6,2 | ≈ 0 |
| D6 | 5,8 | ≈ 0 |
| **D7** | **12,5** | ≈ 0 |
| D8 | 5,5 | ≈ 0 |

- Đề xuất sửa Mục 2.3 của bản thảo vẫn đúng, nhưng lý do cần viết lại cho chính xác:
  - E_replan chỉ quan trọng khi định vị tốt;
  - khi định vị kém, sai số bám thuần (E_track) quyết định độ lớn biên.
- E_replan có trung bình âm ở một số ô và P95 tổng nhỏ hơn P95 của E_track (ví dụ D3: 2,68 so với 3,31). Vậy đây là phân rã **có dấu**; cần ghi rõ định nghĩa này trong bài.

### E7 — Độ nhạy d_s, mật độ lưới, độ rộng làn

- Trên S1–S4, độ phủ vật lý vẫn đạt 1,000 và va chạm 0% với mọi phương pháp có biên, kể cả khi d_s = 1,0 m, làn 3,0 m hay lưới 663 ứng viên.
- Lý do là phanh dự phòng −6 m/s². Điểm ⑤ chỉ được giải quyết nhờ các kịch bản mới S5–S10.
- Đáng chú ý, tỉ lệ hoàn thành của ĐX-1 chỉ khoảng 49–50%, so với B5 khoảng 81–86%. Đây là cái giá về hiệu quả cần nêu thẳng trong bài.

### E9 — Tăng lên 30 hạt giống (IN)

| Phương pháp | Độ phủ | Ghi chú |
|---|---|---|
| B1 | 0,892 (±0,012) | KTC **chứa 0,90** |
| ĐX-1 | 0,921 | Phủ thừa |
| ĐX-2 | 0,944 | Phủ thừa |
| ĐX-3 | 0,900 | Đúng mục tiêu |

- Với 30 hạt giống, **không còn chứng minh được B1 phủ thiếu**. Kết luận "B1 thiếu độ phủ" ở v0.1 (0,872 với 15 hạt giống) phần lớn là nhiễu mẫu.
- ĐX-1 và ĐX-2 lại phủ thừa, nghĩa là bảo thủ hơn mức cần thiết.

---

## 7. Những chỗ báo cáo tự sinh cần sửa

| # | Vị trí | Vấn đề | Sửa |
|---|---|---|---|
| 1 | §2, dòng đầu | Ghi "4/4 test", chỉ liệt kê 4 test; dòng "Ngày tạo" ghi 13:51 | Đọc lại `tests.txt` (19/19), chạy lại `report_ext` |
| 2 | §9, dòng PAC | Khuyến nghị "n ≥ 400, M = 1 (dư ≤ 2%)" mâu thuẫn với bảng 6.1 | Đổi thành n ≥ 800, hoặc ghi dư khoảng 2,75% |
| 3 | §9, dòng ACI | Viết "ĐX-3 bền vững nhất dưới OOD-SD và D8" | Sai. Ở OOD-SD: B3′ 0,952 > B6 0,916 > ĐX-2 0,906 > ĐX-3 0,882. Ở D8, ĐX-2 và ĐX-3 xấp xỉ nhau |
| 4 | §5 (E2) | Cơ chế "α_t trôi dương" không khớp bảng | Chỉ nêu chênh lệch độ phủ khoảng 1,5 điểm phần trăm; bổ sung kết luận γ = 0,005 tốt hơn |
| 5 | §7 / §9 (E6) | Viết "E_replan chiếm phần lớn đuôi" một cách chung chung | Chỉ đúng ở D0. Ở D1/D2/D6–D8, E_track chi phối |
| 6 | §3.3 (S9) | Viết "vẫn giữ được độ phủ" | Thuật toán 1 không hội tụ (dao động 0,55). Ghi là hạn chế |
| 7 | §4 | Diễn giải "ĐX-2 trên OOD-SD bền vững hơn" | Ở cùng độ phủ thì không có khác biệt; chỉ ở cùng q danh định ĐX-2 mới phủ cao hơn |

---

## 8. Cập nhật 7 điểm yếu ①–⑦

| Điểm | Kết luận v0.2 |
|---|---|
| ① So sánh ở cùng độ phủ | ✅ **Đã kiểm chứng và bác bỏ ưu thế hiệu quả của ĐX-1.** Chỉ ĐX-2 trên IN có lợi thật (m₃ₛ hẹp hơn khoảng 1–1,5 m) |
| ② ACI | 🔄 Có tác dụng giữ độ phủ dài hạn. Cấu hình γ = 0,02 kém; γ = 0,005 cho cùng độ phủ với biên nhỏ hơn khoảng 15%. Không sửa được độ phủ có điều kiện |
| ③ PAC / cỡ mẫu | ✅ Có bảng cỡ mẫu (cần n ≈ 800 để dư ≤ 2%); khối D2 chuyên biệt giải quyết chuyện nhóm `loss` thiếu mẫu |
| ④ D2 chuyên biệt | ✅ Chứng nhận được (q_loss 4,18 < 5,74), nhưng không chuyển sang D7 được (0,874) |
| ⑤ An toàn vật lý bão hòa | ◐ Giải quyết trên S5–S10; vẫn bão hòa trên S1–S4 |
| ⑥ E_track / E_replan | ✅ Đã tách. E_track chi phối khi định vị suy giảm |
| ⑦ Phạm vi kịch bản | ✅ Mở rộng; lộ ra S7, S10, D7 và σ_τ lệch theo kịch bản |
| Thêm: A1 (độc lập sau thinning) | ❌ ρ₁ ≈ 0,15 dù đã thinning tới 6 s |
| Thêm: B1 phủ thiếu | ❌ Không còn ý nghĩa thống kê với 30 hạt giống |

---

## 9. Khuyến nghị

**Cho bản thảo:**
1. Viết lại phần đóng góp:
   - ĐX-1 là cách hiệu chỉnh "đúng mức 1 − α", không phải cách "hiệu quả hơn";
   - ĐX-2 là đề xuất có lợi thế thực sự trong phân phối;
   - nêu rõ giới hạn ngoài phân phối, nhất là D7.
2. Báo cáo độ phủ tệ nhất theo ô và σ_τ theo kịch bản; đề xuất chuẩn hóa hoặc chia nhóm theo tình huống.
3. Đưa vào phần hạn chế:
   - Thuật toán 1 dao động, chưa hội tụ;
   - chứng nhận PAC trên dữ liệu trộn làm biên tăng 41%;
   - giả thiết A1 chưa thỏa.

**Cho mô phỏng (nếu chạy tiếp):**
1. Chạy lại ĐX-3 và B6 với γ = 0,005 trên các tập OOD và RECAL.
2. Chạy lại `report_ext` sau khi sửa 7 điểm ở §7.
3. Kiểm tra vì sao độ phủ tăng theo Δ trong E5.
4. Thêm Mondrian theo nhóm kịch bản (cùng cách làm với ĐX-2) để thử khắc phục S7 và S10.
