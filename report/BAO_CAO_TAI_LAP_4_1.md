# Báo cáo tái lập Mục 4.1 — Nghiên cứu số trên dữ liệu tổng hợp

*Bản thảo đối chiếu: “Bài báo 1 — Bản thảo tiếng Việt v0.1”. Đặc tả: SPEC 0.4 §10 (19/11/2026). Hạt giống: 2026. Báo cáo này sinh tự động bằng `python -m num41.report_41` từ `logs/num41/summary.json`.*

## 1. Kết luận chính

- Trong `ws/` trước đây không có mã sinh số liệu Mục 4.1. Mã mới ở `num41/` sinh lại toàn bộ Bảng 1, Bảng 2, Hình 1, Hình 2 và các con số trong lời văn, với hạt giống cố định; chạy lại cho log giống hệt.
- **Bảng 1 (N1):** cả 9 ô khớp chuẩn lý thuyết Beta–nhị thức. Số tái lập lệch bản thảo tối đa 0,005 ở trung bình và 0,003 ở độ lệch chuẩn. Có thể giữ Bảng 1 hoặc thay bằng số tái lập.
- **Hình 2 (N2):** mọi tiêu chí định tính và định lượng đều đạt. Biên gộp hẹp hơn B3 67–78% (bản thảo 68–77%). Không có lần lặp nào vi phạm Mệnh đề 3 (0/550).
- **Bảng 2 (N3):** đạt mọi tiêu chí định tính và 9/10 tiêu chí định lượng. Ô lệch duy nhất: độ phủ của ngưỡng chung ở nhóm mất GNSS là 0,573, bản thảo ghi 0,620. Theo quy tắc của kế hoạch, không chỉnh tham số để ép khớp; đề xuất thay số trong bản thảo.
- Các giả định chưa nêu trong bản thảo (U1–U12, mục 3) nên được bổ sung vào phần Thiết lập của 4.1 (mục 6.2).

## 2. Cách tái lập

```bash
cd ws
python -m num41.run_all --seed 2026
```

| Thành phần | File |
|---|---|
| Bộ sinh dữ liệu, điểm số | `num41/gen.py`, `num41/scores.py` |
| Thí nghiệm | `num41/run_n1.py`, `num41/run_n2.py`, `num41/run_n3.py` |
| Kiểm thử TC-41a..e | `tests/test_num41.py` → `logs/num41/tests.txt` |
| Log | `logs/num41/` (`n1_coverage.csv`, `n2_bounds.csv`, `n2_rho.csv`, `n3_groups.csv`, `summary.json`, `config.json`) |
| Hình | `figs/N0_samples`, `figs/N1_coverage`, `figs/N2_bounds` (`.png`, `.pdf`) |

Hạt giống của mỗi luồng: `SeedSequence(entropy=2026, spawn_key=(thí nghiệm, ô, lần lặp, tập))`; tập hiệu chỉnh và tập kiểm tra luôn độc lập.

## 3. Các giả định đã dùng (U1–U12)

Bản thảo không nêu các chi tiết dưới đây; tái lập chọn như sau (SPEC §10).

| Mã | Nội dung | Lựa chọn |
|---|---|---|
| U1 | “Trôi chậm” của sai số định vị | AR(1) dừng theo từng trục, độ lệch chuẩn σ_loc, hằng số thời gian 5 s |
| U2 | Sai số bám | AR(1) theo cả hai trục, độ lệch chuẩn 0,05 m, hằng số thời gian 1 s |
| U3 | Sai số hướng ψ | Xe là đĩa nên E = max_τ ‖Δp_τ‖/σ_τ, không có thành phần hướng |
| U4 | Số tác nhân mỗi mẫu | Một tác nhân |
| U5 | “Đi về phía đường của xe” | Hướng tới một điểm ngẫu nhiên x_c ~ U(0; 6) m trên đường xe |
| U6 | Tốc độ quay, gia tốc | Lấy một lần cho mỗi mẫu, giữ hằng trên chân trời (phương án A) |
| U7 | σ_loc của N1 | 0,1 m |
| U8 | Lưới σ_loc của N2 | {0; 0,05; 0,1; 0,2; 0,3; 0,4; 0,5} m |
| U9 | Cách ép tương quan ρ | Giữ ‖e‖, đổi hướng thành unit(ρ·g + √(1−ρ²)·u); σ_loc = 0,1 m; ρ ∈ {−0,5; 0; 0,5; 0,9} |
| U10 | Độ phủ của B1, B3, B4 | Đều đo bằng P(R_test ≤ q), R là điểm số hụt khoảng cách thật |
| U11 | Định nghĩa B4 | q_A(α) + max E_i trên tập hiệu chỉnh |
| U12 | Cỡ mẫu N3 | n = 1000 tổng, nhãn nhóm ngẫu nhiên theo tỉ lệ 70/20/10; 2000 mẫu kiểm tra |

## 4. Đối chiếu từng con số

Quy ước khớp (PLAN §10.4): Bảng 1 so với chuẩn lý thuyết (trung bình trong ±3 sai số chuẩn, độ lệch chuẩn sai khác ≤ 15%); các số khác so với bản thảo: độ phủ ±0,02, ngưỡng và tỉ số ±15%.

### 4.1. Bảng 1 — độ phủ theo α và n (200 lần lặp)

| n | 1 − α | Bản thảo | Tái lập | Lý thuyết | z | ĐLC/LT | Kết quả |
|---|---|---|---|---|---|---|---|
| 100 | 0,80 | 0,806 ± 0,041 | 0,803 ± 0,042 | 0,802 ± 0,040 | 0,30 | 1,05 | khớp |
| 100 | 0,90 | 0,903 ± 0,029 | 0,899 ± 0,032 | 0,901 ± 0,030 | −0,67 | 1,06 | khớp |
| 100 | 0,95 | 0,950 ± 0,023 | 0,949 ± 0,024 | 0,950 ± 0,022 | −0,62 | 1,10 | khớp |
| 500 | 0,80 | 0,798 ± 0,021 | 0,803 ± 0,018 | 0,800 ± 0,020 | 1,78 | 0,89 | khớp |
| 500 | 0,90 | 0,900 ± 0,015 | 0,901 ± 0,016 | 0,900 ± 0,015 | 0,32 | 1,07 | khớp |
| 500 | 0,95 | 0,949 ± 0,010 | 0,951 ± 0,011 | 0,950 ± 0,011 | 0,72 | 0,99 | khớp |
| 1000 | 0,80 | 0,801 ± 0,016 | 0,802 ± 0,014 | 0,800 ± 0,015 | 1,48 | 0,89 | khớp |
| 1000 | 0,90 | 0,900 ± 0,012 | 0,900 ± 0,011 | 0,900 ± 0,012 | 0,38 | 0,97 | khớp |
| 1000 | 0,95 | 0,950 ± 0,009 | 0,950 ± 0,008 | 0,950 ± 0,008 | 0,58 | 0,92 | khớp |

### 4.2. Hình 2 — bốn loại biên theo σ_loc (α = 0,1; n = 1000; 50 lần lặp)

| Đại lượng | Bản thảo | Tái lập | Chênh lệch | Kết quả |
|---|---|---|---|---|
| Độ phủ ĐX, nhỏ nhất theo σ_loc | 0,898 | 0,900 | 0,002 | khớp |
| Độ phủ ĐX, lớn nhất theo σ_loc | 0,903 | 0,903 | 0,000 | khớp |
| Độ phủ B1, σ_loc = 0 | 0,996 | 0,998 | 0,002 | khớp |
| Độ phủ B1, σ_loc = 0,2 m | 0,972 | 0,971 | −0,001 | khớp |
| Độ phủ B1, σ_loc = 0,5 m | 0,802 | 0,798 | −0,004 | khớp |
| q_ĐX, σ_loc = 0,1 m | 1,82 | 1,74 | −0,08 (−4%) | khớp |
| q_B3, σ_loc = 0,1 m | 7,81 | 8,06 | 0,25 (+3%) | khớp |
| q_ĐX, σ_loc = 0,5 m | 5,77 | 5,89 | 0,12 (+2%) | khớp |
| q_B3, σ_loc = 0,5 m | 18,00 | 18,00 | 0,00 (+0%) | khớp |
| q_B4, σ_loc = 0,1 m | 9,21 | 9,63 | 0,42 (+5%) | khớp |
| q_B4, σ_loc = 0,5 m | 25,60 | 25,05 | −0,55 (−2%) | khớp |
| q_ĐX/q_B3, ρ = −0,5 | 0,230 | 0,215 | −0,015 (−7%) | khớp |
| q_ĐX/q_B3, ρ = 0,9 | 0,310 | 0,348 | 0,038 (+12%) | khớp |
| Mức thu hẹp của ĐX so với B3, σ_loc = 0,1 / 0,5 m | 77% / 68% | 78% / 67% | — | khớp |
| Số lần q_ĐX > q_B3 | 0 | 0/550 | — | khớp |

Bảng đầy đủ theo σ_loc (trung bình qua các lần lặp):

| σ_loc (m) | Phủ ĐX | Phủ B1 | Phủ B3 | Phủ B4 | q_ĐX | q_B1 | q_B3 | q_B4 | ĐX hẹp hơn B3 |
|---|---|---|---|---|---|---|---|---|---|
| 0,00 | 0,900 | 0,998 | 1,000 | 1,000 | 1,59 | 3,48 | 6,94 | 7,76 | 77% |
| 0,05 | 0,901 | 0,998 | 1,000 | 1,000 | 1,61 | 3,48 | 7,27 | 8,28 | 78% |
| 0,10 | 0,900 | 0,997 | 1,000 | 1,000 | 1,74 | 3,48 | 8,06 | 9,63 | 78% |
| 0,20 | 0,901 | 0,971 | 1,000 | 1,000 | 2,38 | 3,48 | 10,23 | 13,03 | 77% |
| 0,30 | 0,900 | 0,907 | 1,000 | 1,000 | 3,34 | 3,46 | 12,73 | 16,88 | 74% |
| 0,40 | 0,903 | 0,851 | 1,000 | 1,000 | 4,63 | 3,51 | 15,44 | 21,40 | 70% |
| 0,50 | 0,900 | 0,798 | 1,000 | 1,000 | 5,89 | 3,46 | 18,00 | 25,05 | 67% |

Quét tương quan ρ (σ_loc = 0,1 m):

| ρ | ρ thực nghiệm | q_ĐX | q_B3 | q_ĐX/q_B3 | Độ phủ ĐX |
|---|---|---|---|---|---|
| −0,5 | −0,14 | 1,72 | 8,04 | 0,215 | 0,899 |
| 0,0 | 0,07 | 1,75 | 8,04 | 0,218 | 0,901 |
| 0,5 | 0,26 | 1,78 | 8,03 | 0,222 | 0,899 |
| 0,9 | 0,54 | 2,80 | 8,03 | 0,348 | 0,903 |

### 4.3. Bảng 2 — ngưỡng chung và ngưỡng theo nhóm (α = 0,1; 100 lần lặp)

| Nhóm | Đại lượng | Bản thảo | Tái lập | Chênh lệch | Kết quả |
|---|---|---|---|---|---|
| RTK cố định | Độ phủ, ngưỡng chung | 0,963 | 0,969 | 0,006 | khớp |
| RTK cố định | Độ phủ, theo nhóm | 0,900 | 0,900 | 0,000 | khớp |
| RTK cố định | Ngưỡng theo nhóm | 1,74 | 1,60 | −0,14 | khớp |
| RTK thả nổi | Độ phủ, ngưỡng chung | 0,818 | 0,810 | −0,008 | khớp |
| RTK thả nổi | Độ phủ, theo nhóm | 0,900 | 0,899 | −0,001 | khớp |
| RTK thả nổi | Ngưỡng theo nhóm | 3,34 | 3,39 | 0,05 | khớp |
| Mất GNSS | Độ phủ, ngưỡng chung | 0,620 | 0,573 | −0,047 | **lệch** |
| Mất GNSS | Độ phủ, theo nhóm | 0,899 | 0,902 | 0,003 | khớp |
| Mất GNSS | Ngưỡng theo nhóm | 12,18 | 12,44 | 0,26 | khớp |
| Mọi nhóm | Ngưỡng chung | 2,37 | 2,30 | −0,07 | khớp |

Kiểm tra chéo: độ phủ tổng của ngưỡng chung = Σ tỉ lệ nhóm × độ phủ nhóm = 0,897 ≈ 0,90, đúng như phải có. Với số của bản thảo, tổng này cũng bằng 0,900. Vậy ô lệch ở nhóm mất GNSS do khác biệt mô hình dữ liệu (đuôi phân phối điểm số của nhóm này), không phải lỗi cài đặt.

Độ nhạy (chỉ để tham khảo, không thay kết quả chính) — độ phủ ngưỡng chung ở nhóm mất GNSS:

| Biến thể | Mô tả | Độ phủ, nhóm mất GNSS |
|---|---|---|
| Gốc | U6 phương án A, U1 có trôi | 0,573 |
| U6B | Tốc độ quay, gia tốc đổi theo từng bước | 0,496 |
| U1W | Sai số định vị nhiễu trắng, không trôi | 0,242 |

Cả hai biến thể đều xa bản thảo hơn mô hình gốc, nên giữ mô hình gốc.

## 5. Kiểm tra định tính

| Tiêu chí | Đạt | Giá trị |
|---|---|---|
| ĐX đạt 0,90 ± 0,01 ở mọi σ_loc | có | 0,900–0,903 |
| Độ phủ B1 giảm dần theo σ_loc | có | 0,998 → 0,798 |
| q_ĐX ≤ q_B3 ở mọi lần lặp (Mệnh đề 3) | có | 0 vi phạm / 550 |
| B4 rộng hơn B3 ở mọi σ_loc | có | 1,12–1,39 lần |
| Tỉ số q_ĐX/q_B3 tăng theo ρ | có | 0,215 → 0,218 → 0,222 → 0,348 |
| Ngưỡng theo nhóm đạt 0,90 ± 0,01 ở từng nhóm (Hệ quả 1) | có | 0,900 / 0,899 / 0,902 |
| Ngưỡng chung thừa ở nhóm cố định, thiếu ở thả nổi và mất GNSS | có | 0,969 / 0,810 / 0,573 |

Ghi chú về ρ: tỉ số gần như không đổi từ ρ = −0,5 đến 0,5 rồi tăng mạnh ở ρ = 0,9. Bản thảo chỉ nêu hai đầu nên không rõ đường của tác giả có dạng này không; lời văn nên nói “tăng rõ khi tương quan cao” thay vì ngụ ý tăng đều.

## 6. Đề xuất sửa bản thảo

### 6.1. Sửa số theo vị trí

Số thứ tự đoạn tính trên các đoạn có chữ của file docx v0.1.

| Vị trí | Hiện tại | Đề xuất |
|---|---|---|
| Tóm tắt, đoạn 21 | “độ phủ thực nghiệm 0,898–0,903 … hẹp hơn cách cộng hai biên 68–77%” | “độ phủ thực nghiệm 0,900–0,903 … hẹp hơn cách cộng hai biên 67–78%” |
| Tóm tắt, đoạn 22 | “giảm độ phủ xuống 0,80 khi nhiễu định vị 0,5 m” | Giữ nguyên (tái lập 0,798) |
| 4.1 Thiết lập, đoạn 174–182 | Thiếu chi tiết mô hình | Thêm các câu ở mục 6.2 |
| 4.1, đoạn 184 | “nằm trong khoảng 0,798–0,950” | “nằm trong khoảng 0,802–0,951” |
| 4.1, đoạn 185 | “Sai lệch lớn nhất là 0,798 so với 0,800 (tại n=500, α=0,2), nằm trong 1,5 sai số chuẩn” | “Sai lệch lớn nhất là 0,803 so với 0,800 (tại n=500, α=0,20), bằng 1,8 sai số chuẩn so với giá trị lý thuyết k/(n+1) = 0,8004” |
| 4.1, đoạn 186 | “từ 0,029 (n=100) xuống 0,012 (n=1000)” | “từ 0,032 (n=100) xuống 0,011 (n=1000)” |
| Bảng 1 | Số v0.1 | Thay bằng cột “Tái lập” ở mục 4.1 của báo cáo này (hoặc giữ số cũ, vì đều khớp lý thuyết) |
| Hình 1 | Hình v0.1 | `figs/N1_coverage.pdf` |
| 4.1, đoạn 211 | “độ phủ 0,898–0,903” | “độ phủ 0,900–0,903” |
| 4.1, đoạn 213–214 | “0,996 … 0,972 tại 0,2 m … 0,802 tại 0,5 m” | “0,998 … 0,971 tại 0,2 m … 0,798 tại 0,5 m” |
| 4.1, đoạn 217 | “nhỏ hơn B3 77% tại σloc=0,1 m (1,82 so với 7,81)” | “nhỏ hơn B3 78% tại σloc=0,1 m (1,74 so với 8,06)” |
| 4.1, đoạn 218 | “nhỏ hơn B3 68% tại 0,5 m (5,77 so với 18,0)” | “nhỏ hơn B3 67% tại 0,5 m (5,89 so với 18,0)” |
| 4.1, đoạn 219 | “B4 còn rộng hơn nữa (9,21 và 25,6)” | “B4 còn rộng hơn nữa (9,63 và 25,0)” |
| 4.1, đoạn 220 | “tăng từ 0,23 (ρ=-0,5) lên 0,31 (ρ=0,9)” | “tăng từ 0,21 (ρ=−0,5) lên 0,35 (ρ=0,9); tỉ số gần như không đổi khi ρ ≤ 0,5 và chỉ tăng rõ khi tương quan cao” |
| Hình 2 | Hình v0.1 (a, b) | `figs/N2_bounds.pdf`; có thêm ô (c) cho tỉ số theo ρ — bỏ ô (c) hoặc thêm vào chú thích |
| 4.1, đoạn 236 | “thừa ở nhóm RTK cố định (0,963) và thiếu ở nhóm RTK thả nổi (0,818) và mất GNSS (0,620)” | “… (0,969) … (0,810) … (0,573)” |
| 4.1, đoạn 237 | “(0,899–0,900)” | “(0,899–0,902)” |
| 4.1, đoạn 238 | “(1,74 so với 2,37) … (3,34 và 12,18)” | “(1,60 so với 2,30) … (3,39 và 12,44)” |
| Bảng 2 | Số v0.1 | Thay bằng cột “Tái lập” ở mục 4.3 của báo cáo này |
| Kết luận, đoạn 435 | “hẹp hơn tổng hai biên 68–77%” | “hẹp hơn tổng hai biên 67–78%” |
| Kết luận, đoạn 436 | “0,80 khi nhiễu định vị 0,5 m” | Giữ nguyên |
| Kết luận, đoạn 437 | “nhóm mất GNSS chỉ đạt 0,62” | “nhóm mất GNSS chỉ đạt 0,57” |

### 6.2. Câu bổ sung cho phần Thiết lập của 4.1

Đề xuất thêm vào sau đoạn 175, 179 và 182:

- “Sai số định vị là quá trình AR(1) dừng độc lập theo từng trục, độ lệch chuẩn σloc và hằng số thời gian 5 s; sai số bám là AR(1) với độ lệch chuẩn 0,05 m và hằng số thời gian 1 s.”
- “Tác nhân hướng tới một điểm ngẫu nhiên trên đường của xe, cách gốc 0–6 m. Tốc độ quay và gia tốc được lấy một lần cho mỗi mẫu và giữ không đổi trên chân trời. Mỗi mẫu có một tác nhân.”
- “Vì xe được xấp xỉ bằng đĩa, sai số của xe chỉ gồm sai số vị trí: E = max_τ ‖Δp_τ‖/σ_τ.”
- “Độ phủ của mọi loại biên được đo bằng tỉ lệ mẫu kiểm tra có điểm số hụt khoảng cách không vượt ngưỡng. B4 dùng sai số xe lớn nhất trên tập hiệu chỉnh.”
- “Bảng 1 dùng σloc = 0,1 m. Để ép tương quan ρ, giữ độ lớn sai số của xe và đổi hướng của nó thành unit(ρ·g + √(1−ρ²)·u), trong đó g là phương xe – tác nhân lấy dấu theo phần hụt do tác nhân, u là hướng gốc.”
- “Ở Bảng 2, mỗi tập hiệu chỉnh có 1000 mẫu, nhãn nhóm lấy ngẫu nhiên theo tỉ lệ 70/20/10.”

## 7. Hạn chế và việc còn mở

- Đây là tái lập độc lập dựa trên mô tả trong bản thảo, không phải mã gốc của tác giả. Nên hỏi lại tác giả (NCS) mã gốc của 4.1 để đối chiếu các giả định U1–U12.
- Ô lệch duy nhất là độ phủ ngưỡng chung ở nhóm mất GNSS (0,573 so với 0,620). Kết luận định tính của bản thảo không đổi.
- Kết quả pytest của `tests/test_num41.py` ghi ở `logs/num41/tests.txt`.

