# ĐẶC TẢ KỸ THUẬT — Mô phỏng phương án cũ / mới

*Phiên bản 0.3 — 16/11/2026 — §1–§9 (v0.1 và mở rộng v0.2) đã duyệt và hoàn thành*

## 1. Lõi mô phỏng (dùng chung cho A và B)

| Khối | Đặc tả |
|---|---|
| Bước thời gian | Mô phỏng 0,05 s; lập kế hoạch 10 Hz; H = 30 × 0,1 s (3 s); bộ bám 20 Hz |
| Xe thật | Mô hình xe đạp động học cỡ Tesla Model 3: L = 2,875 m, hộp 4,69 × 1,85 m (tâm cầu sau cách đuôi 0,96 m), r_max = 3,85 m, δ_max = 0,6 rad, ω_max = 0,8 rad/s, a ∈ [−6; 3] m/s², v_max = 8,3 m/s. Trễ gia tốc bậc nhất 0,25 s, trễ lái 0,1 s, sai số hệ số lái ±5% mỗi lượt, trễ lệnh nền 50 ms, bù trước vận tốc (lệnh = vận tốc kế hoạch tại t + 0,5 s) |
| Định vị | RTK cố định σ = 0,03 m / 0,003 rad; RTK thả nổi σ = 0,3 m / 0,02 rad (AR(1), hằng số thời gian 5 s); mất GNSS là trôi tích lũy (bước ngẫu nhiên + độ lệch), hội tụ lại với hằng số 1,5 s khi có tín hiệu |
| Điều kiện suy giảm | D0 RTK cố định · D1 RTK thả nổi · D2 mất GNSS 5–10 s · D3 trượt bánh (thiếu lái 15%, trượt ngang AR(1) σ = 0,04) · D4 trễ thêm cố định 50/100/200 ms · D5 trễ ngẫu nhiên Gamma(2; 0,05), cắt ở 0,3 s |
| Nhãn định vị g | fix / float / loss. D3–D5 mang nhãn fix: suy giảm không quan sát được qua nhãn |
| Tác nhân | Tập đĩa cứng: người đi bộ 1 đĩa r = 0,35 m; xe máy 2 đĩa r = 0,45 m cách 1 m; ô tô 3 đĩa r = 0,95 m cách 1,4 m. Tốc độ quay và gia tốc nhiễu AR(1). Không tương tác với xe tự hành |
| Kịch bản | S1 người đi bộ sang đường 0,8–1,8 m/s, 20% dừng giữa đường 2–4 s · S2 xe máy cắt ngang 30–90°, 3–8 m/s · S3 giao cắt không đèn, có xe máy và ô tô · S4 xe máy hoặc ô tô phía trước phanh 2–5 m/s² |
| Đường | Thẳng theo trục x, làn xe tự hành y ∈ [−1,75; 1,75]; đích x = 75 m; tối đa 16 s |
| Dự báo | Vận tốc hằng từ quan sát có nhiễu (vị trí 0,05 m, vận tốc 0,1 m/s); vùng quan tâm 40 m |
| Planner | Frenet lấy mẫu: lệch ngang ±1,5 m bước 0,25 m; vận tốc đích 0–8,3 m/s bước 1,0 m/s; T ∈ {3, 4, 5} s; tổng 351 ứng viên. Ngang bậc 5, dọc bậc 4 |
| Lọc và chọn | Lọc động học (độ cong, gia tốc, vận tốc) → lọc an toàn d̂ ≥ d_s + m_τ → chi phí J = (v_max − v_đích)² + 0,1·∫độ giật² + 2·d_f² → không còn ứng viên thì phanh dự phòng với a_min. d_s = 0,5 m |
| Bám | Pure Pursuit, tầm nhìn trước L_d = 2 + 0,3v |
| Khoảng cách | Hộp chữ nhật – đĩa, chính xác, vector hóa bằng numpy |

**Thống kê cho mỗi chu kỳ lập kế hoạch,** tính sau khi đủ H bước:
- d̂_τ^j và d_τ^j;
- phần hụt d̂ − d;
- sai số tác nhân theo tâm A_c và theo cận Hausdorff A_h (độ dời lớn nhất của các đĩa);
- sai số xe E_τ = ‖Δp‖ + r_max·|Δψ|;
- phân tách có dấu: phần do tác nhân a = D(ℬ(p), Ô) − D(ℬ(p), O), phần do xe b = D(ℬ(p), O) − D(ℬ(e), O);
- nhãn g, cờ dự phòng, q đang dùng.

**Khác với thiết lập CARLA trong bản thảo:**
- Vận tốc lấy mẫu bước 1,0 m/s thay vì 0,5 m/s (351 thay vì 663 ứng viên), để vừa thời gian tính.
- Dự báo vận tốc hằng thay cho Trajectron++.
- Không có cảm biến thật; chỉ có bộ phát sai số định vị.

## 2. Định nghĩa phương pháp

| Mã | Mô tả | Điểm số / biên |
|---|---|---|
| B0 | Không có biên | m_τ = 0 |
| B1 | Biên phù hợp chỉ cho tác nhân [7] | max A/σ_τ, mức α |
| B2 | B1 + vùng đệm cố định cho xe | B1 + 0,3 m |
| B3 | Cộng hai biên hiệu chỉnh riêng | q_A(α/2)·σ_τ + q_E(α/2)·σ_τ |
| B3′ | Hai phần có dấu, hiệu chỉnh riêng rồi cộng (chỉ có ở B) | q_a(α/2)·σ_τ + q_b(α/2)·σ_τ |
| B4 | Ống bám xấu nhất thực nghiệm | B1 + max_calib E_τ |
| B5 | Ràng buộc cơ hội giả định Gauss | z_{1−α}·√(s_a,τ² + s_e,τ²), theo từng τ |
| B6 | B1 thích nghi [8] | ACI trên điểm số B1 |
| ĐX-1 | Biên gộp | R = max_{τ,j} (d̂ − d)/σ_τ |
| ĐX-2 | Biên gộp theo nhóm định vị | q̂_g theo g; nhóm thiếu mẫu thì dùng ngưỡng chung |
| ĐX-3 | Biên gộp thích nghi | ACI, γ = 0,02, phản hồi trễ H, cửa sổ 500 điểm số |

Tên B4 dùng thống nhất ở cả hai phương án ("ống bám xấu nhất thực nghiệm").

## 3. Khác biệt giữa phương án A (cũ) và B (mới)

| Hạng mục | A — phương án cũ (v0.1) | B — phương án mới |
|---|---|---|
| Mẫu không có tác nhân | Giữ lại, gán R = −∞ | Bỏ; chỉ dùng chu kỳ có 𝒥_t ≠ ∅ |
| Lấy mẫu | Mỗi 2 s (cửa sổ 3 s chồng nhau) | Mỗi 3 s (không chồng); thêm chỉ tiêu theo lượt chạy |
| σ_τ | Cố định 0,05 + 0,04τ (τ là chỉ số bước) | Phân vị 90% của max_j(d̂ − d) trên hạt giống 200–249 (chạy bằng B0), cận dưới 0,05 m, đơn điệu tăng |
| Sai số tác nhân (B1, B3, B6) | A_c: độ dời của tâm (chỉ tịnh tiến) | A_h: cận Hausdorff (có tính quay) |
| Chứng nhận (Định lý 2) | Có điều kiện: q̂ ≤ q_plan thì chứng nhận; nếu không, tăng q_plan 5% và thử lại trên tập mới, tối đa 3 lần | PAC: chọn k sao cho P(Bin(n, 1−α) ≥ k) ≤ δ, với δ = 0,05/3 (Bonferroni cho tối đa 3 lần thử) |
| Chu kỳ dự phòng | Gộp chung khi tính độ phủ | Báo cáo riêng: khả thi / dự phòng |
| Đối chứng | B0–B6 | B0–B6 và B3′ |
| ACI (B6, ĐX-3) | Cập nhật trên mọi chu kỳ (kể cả chu kỳ trống) | Chỉ cập nhật trên chu kỳ có tác nhân |
| α | 0,1 | 0,1 (chính); quét thêm {0,01; 0,02; 0,05; 0,2} cho B1, B3′, ĐX-2 |

## 4. Chia dữ liệu và quy trình

| Hạt giống | Dùng cho |
|---|---|
| 200–249 | Ước lượng σ_τ (chỉ phương án B) |
| 250–299, 300–349, 350–399 | Hiệu chỉnh lặp, 3 khối × 50 lượt (Thuật toán 1), q₀ hiệu chỉnh từ dữ liệu B0 |
| 400–449, 450–499, 600–649 | Chứng nhận, mỗi lần thử một tập mới |
| 500–514 | Kiểm tra: mỗi tổ hợp D0–D5 × S1–S4 chạy 15 lượt, cùng hạt giống cho mọi phương pháp (ghép cặp) |

- Hiệu chỉnh và chứng nhận: kịch bản = hạt giống mod 4; điều kiện D chọn ngẫu nhiên đều theo hạt giống.
- B0 chạy một lần, dùng chung cho cả hai phương án.
- ACI giữ trạng thái xuyên suốt các lượt trong cùng một điều kiện, chạy tuần tự.
- Song song hóa theo cặp (phương pháp, điều kiện), 2 tiến trình.

**Khối lượng ước tính:**
- hiệu chỉnh và chứng nhận khoảng 200–300 lượt mỗi phương pháp;
- kiểm tra 360 lượt mỗi phương pháp;
- quét α khoảng 1.100 lượt;
- tổng khoảng 9.000 lượt, khoảng 25–40 phút.

## 5. Chỉ tiêu đánh giá

| Chỉ tiêu | Định nghĩa |
|---|---|
| Độ phủ | Tỉ lệ chu kỳ đã lấy thưa có min_{τ,j} d ≥ d_s; KTC 95% Clopper–Pearson |
| Độ phủ điểm số | Tỉ lệ R ≤ q (kiểm chứng trực tiếp Định lý 1) |
| Vi phạm | 1 − độ phủ, theo chu kỳ và theo lượt (lượt có ít nhất một vi phạm) |
| Va chạm | Tỉ lệ lượt có hộp xe chạm đĩa tác nhân |
| d_min, TTC_min | Nhỏ nhất trên lượt |
| Hiệu quả | Thời gian hoàn thành, tỉ lệ hoàn thành, % chu kỳ dự phòng |
| Êm dịu | RMS độ giật dọc |
| Thời gian tính | P95 thời gian lập kế hoạch (ms) |
| Ngưỡng | q chuẩn hóa và m_τ tại τ = 3 s (m) |

**Kiểm định:** McNemar cho tỉ lệ ghép cặp, Wilcoxon cho chỉ tiêu liên tục, hiệu chỉnh Holm.

## 6. Log (hai phần riêng)

```
logs/old/   và   logs/new/
  config.json        tham số, hạt giống, phiên bản mã, thời điểm chạy
  calibration.json   σ_τ; q qua từng vòng lặp; kết quả chứng nhận, số lần thử; q theo nhóm
  cycles.csv         method, seed, scn, cond, t, g, J, fallback, q, m_max, gap_max,
                     d_min, covered(R≤q), safe(min d ≥ d_s), thinned
  episodes.csv       method, seed, scn, cond, collided, completed, t_end, d_min,
                     n_cycles, n_fallback, jerk_rms, tcomp_p95_ms
  summary.json       method × cond (và tổng): độ phủ + KTC, vi phạm, va chạm, d_min,
                     thời gian hoàn thành, % dự phòng, độ giật, ngưỡng (m)
  alpha_sweep.csv    (chỉ ở new) method, α, độ phủ, vi phạm, thời gian hoàn thành
```

## 7. Cấu trúc báo cáo (Claude Docs)

1. Tóm tắt kết quả chính (5–7 dòng).
2. Mục tiêu và phạm vi; giới hạn so với CARLA.
3. Thiết lập mô phỏng (tóm tắt SPEC §1–4).
4. Kết quả phương án cũ: bảng chính theo mẫu Bảng 4 của bản thảo.
5. Kết quả phương án mới: bảng chính, kèm B3′.
6. So sánh cũ – mới theo từng sửa đổi (H1–H6):
   - mẫu −∞;
   - lấy mẫu chồng cửa sổ;
   - Hausdorff so với tâm;
   - σ_τ;
   - chứng nhận có điều kiện so với PAC;
   - B3 so với B3′ so với ĐX-1;
   - chu kỳ dự phòng;
   - ACI.
7. Đề xuất sửa đổi bản thảo: bảng theo mục (vị trí, vấn đề, bằng chứng từ mô phỏng, câu chữ gợi ý), có phát biểu lại Định lý 2.
8. Việc cần làm tiếp cho CARLA (cách thu dữ liệu, số hạt giống, điều chỉnh Bảng 3).
9. Phụ lục: cấu hình, cách chạy lại, danh sách file log.

## 8. Tiêu chí nghiệm thu

- Chạy `python run_all.py --seed-base 0` từ đầu sinh lại được toàn bộ log; sai khác < 1e-9 với cùng phiên bản numpy.
- Mọi con số trong báo cáo truy được về `summary.json` hoặc `calibration.json`.
- B0 giống hệt nhau giữa `logs/old` và `logs/new`.
- Mỗi thư mục log có đủ 5 file (cộng `alpha_sweep.csv` ở `new`).
- Báo cáo nêu rõ những gì mô phỏng 2D *không* chứng minh được.

---

## 9. Mở rộng v0.2 — kịch bản và trường hợp kiểm thử bổ sung (đã hoàn thành)

**Lý do mở rộng.** Phân tích kết quả v0.1 cho thấy các điểm sau còn chưa được kiểm chứng:

- ① Khi so ở cùng độ phủ, ĐX-1 gần trùng B1 ở α = 0,05.
- ② ĐX-2 / PAC bị dư độ phủ (0,939).
- ③ Kết luận về ACI không được dữ liệu ủng hộ: ĐX-3 mới 0,897, cũ 0,904.
- ④ Nhóm `float`/`loss` thiếu mẫu cho PAC riêng (n < 39).
- ⑤ Độ phủ vật lý bão hòa 1,000 vì lưới Frenet có dư địa và đường thẳng.
- ⑥ Tự tương quan còn ρ₁ ≈ 0,15 ngay cả ở Δ = 4 s.
- ⑦ Sai số E bị lập lại kế hoạch chi phối.

Ngoài ra, bốn kịch bản S1–S4 chỉ có đường thẳng, tác nhân không tương tác và không bị che khuất. Vì vậy chưa kiểm được lái Ackermann trên đường cong, cũng chưa kiểm được độ bền khi dịch chuyển phân phối.

Phần mở rộng **chỉ chạy cho phương án B** (A đã được chứng minh sai về thống kê). Riêng B0 chạy chung. Có thể chạy A cho ĐX-1/ĐX-2 nếu cần đối chiếu.

### 9.1. Kịch bản mới S5–S10

| Mã | Tên | Mô tả và tham số | Mục đích kiểm tra |
|---|---|---|---|
| S5 | Người đi bộ khuất tầm nhìn | Xe đỗ lề phải (hộp 4,5 × 1,8 m, tâm y = 2,8 m) che người đi bộ. Người bước ra với tốc độ 1,2–2,5 m/s (đi nhanh hoặc chạy). Tác nhân chỉ được quan sát khi đường ngắm từ cảm biến tới ít nhất một đĩa không bị hộp che. Trước thời điểm đó tác nhân không có trong 𝒥_t | Phân phối đuôi của A khi tác nhân xuất hiện đột ngột; tỉ lệ chu kỳ dự phòng; va chạm không tránh được |
| S6 | Xe máy chen làn (cut-in) | Xe máy cùng chiều từ làn trái (y = 3,5 m) chen vào phía trước, góc 5–15°, 6–10 m/s, khoảng cách lúc bắt đầu 8–20 m. Dao động ngang AR(1) σ = 0,3 m/s | Sai số dự báo theo phương ngang, tác nhân đa đĩa có quay (A_h so với A_c) |
| S7 | Đường cong và xe ngược chiều | Đường tham chiếu là cung tròn bán kính R ∈ {25; 50} m, nối với đoạn thẳng. Ô tô ngược chiều lấn tâm đường 0–0,5 m, vận tốc 5–8 m/s. Frenet tính dọc đường cong | Lái Ackermann thật: độ cong lớn, giới hạn δ_max và ω_max; sai số bám E khi đánh lái liên tục; ảnh hưởng của r_max·\|Δψ\| |
| S8 | Mật độ cao hỗn hợp | 4–6 tác nhân cùng lúc (1–2 người đi bộ, 2–3 xe máy theo bầy cách nhau 2–4 m, 0–1 ô tô); thời điểm xuất hiện lệch nhau 0–3 s | Điểm số R = max theo j trên nhiều tác nhân (hiệu ứng lấy max); độ chặt khi \|𝒥_t\| lớn; P95 thời gian tính |
| S9 | Tác nhân tương tác | Người đi bộ hoặc xe máy phản ứng với xe tự hành theo TTC: TTC < 2 s thì nhường (giảm tốc 2 m/s²) với xác suất 0,6, hoặc tăng tốc băng qua với xác suất 0,4 | Vòng phản hồi giữa chính sách và tác nhân phá giả định "dữ liệu không phụ thuộc chính sách". Kiểm tra Thuật toán 1 có hội tụ không và độ phủ có giữ được không |
| S10 | Hành vi trái giả định vận tốc hằng | Người đi bộ đi zigzag (đổi hướng ±60° mỗi 1–2 s). Xe máy rẽ đột ngột: tốc độ quay tới 0,8 rad/s trong 1 s | Sai số đuôi của bộ dự báo vận tốc hằng; σ_τ ước lượng trên S1–S4 có còn đúng không |

**Yêu cầu sửa lõi:**
- Hỗ trợ đường tham chiếu dạng polyline hoặc cung tròn (Frenet tổng quát) cho S7.
- Thêm vật cản tĩnh và kiểm tra đường ngắm cho S5.
- Thêm mô hình phản ứng theo TTC cho S9.

S1–S4 phải cho kết quả **giống hệt** v0.1 (sai khác < 1e-9). Đây là kiểm thử hồi quy TC-01.

### 9.2. Điều kiện suy giảm mới D6–D10

| Mã | Tên | Mô tả | Nhãn g | Mục đích |
|---|---|---|---|---|
| D6 | Kết hợp | D1 (RTK thả nổi) cộng D4 (trễ thêm 100 ms) | float | Hai nguồn sai số xe cộng dồn |
| D7 | Mất GNSS dài | Mất tín hiệu 15–20 s, vượt khoảng 5–10 s dùng khi hiệu chỉnh | loss | Ngoại suy ngoài miền hiệu chỉnh của nhóm `loss` |
| D8 | Nhãn định vị sai | Trạng thái thật như D1 (float), nhưng 30% thời gian báo nhãn `fix` | fix/float (sai) | Độ bền của ĐX-2 khi nhãn nhóm không đáng tin; so với ĐX-3 (không cần nhãn) |
| D9 | Mặt đường trơn | a ∈ [−3; 2] m/s² cho xe thật (planner vẫn giả định [−6; 3]); thiếu lái 25%; trượt ngang AR(1) σ = 0,08 | fix | Sai lệch mô hình chấp hành; phanh dự phòng không đạt a_min |
| D10 | Nhận thức suy giảm | Nhiễu quan sát tác nhân ×3 (0,15 m; 0,3 m/s); mất phát hiện 10% khung (giữ dự báo cũ); trễ nhận thức 100 ms | fix | Sai số tác nhân tăng; ĐX-3 thích nghi được hay không |

### 9.3. Tập kiểm tra và dịch chuyển phân phối

| Tập | Tổ hợp | Hiệu chỉnh dùng | Số lượt |
|---|---|---|---|
| **IN** (trong phân phối) | S1–S4 × D0–D5 | Như v0.1 (giữ nguyên q đã chứng nhận) | Dùng lại log v0.1 |
| **OOD-S** (kịch bản mới) | S5–S10 × D0–D5 | Không hiệu chỉnh lại | 36 ô × 10 hạt giống |
| **OOD-D** (suy giảm mới) | S1–S4 × D6–D10 | Không hiệu chỉnh lại | 20 ô × 10 hạt giống |
| **OOD-SD** | S5–S10 × D6–D10 | Không hiệu chỉnh lại | 30 ô × 10 hạt giống |
| **RECAL** | Toàn bộ S1–S10 × D0–D10 | Hiệu chỉnh và chứng nhận lại trên dữ liệu trộn đủ S1–S10, D0–D10 | 110 ô × 10 hạt giống |

Câu hỏi cần trả lời:
- (a) Khi gặp kịch bản hoặc suy giảm chưa thấy, độ phủ tụt bao nhiêu?
- (b) ĐX-3 (ACI) có khôi phục được không?
- (c) Hiệu chỉnh lại trên dữ liệu đa dạng có khôi phục được 1−α không, và tốn bao nhiêu hiệu quả?

### 9.4. Thí nghiệm bổ sung E1–E9 (gắn với các điểm ①–⑦)

| Mã | Điểm | Giả thuyết | Thiết lập | Chỉ tiêu chính | Tiêu chí kết luận |
|---|---|---|---|---|---|
| E1 | ① | Ở cùng độ phủ thực nghiệm, ĐX cho t_end và biên tốt hơn B1/B3′ ở các ô khó (D1, D2, S7, S8) | Quét α ∈ {0,01; 0,02; 0,03; 0,05; 0,07; 0,1; 0,15; 0,2} cho B1, B3′, ĐX-1, ĐX-2 trên tập IN và OOD-SD. Nội suy t_end và m₃ₛ tại độ phủ thực nghiệm 0,90 và 0,95 | Δt_end và Δm₃ₛ ở cùng độ phủ, KTC bootstrap 95% theo lượt (2.000 lần) | ĐX được coi là hơn nếu KTC của Δ không chứa 0. Nếu chứa 0 thì báo cáo trung thực là "tương đương về hiệu quả, hơn về độ chuẩn xác" |
| E2 | ③ | Cập nhật ACI trên chu kỳ trống làm α_t trôi | 2×2: {cập nhật mọi chu kỳ, chỉ chu kỳ có tác nhân} × {γ = 0,005; 0,02}. Ghi vết α_t theo thời gian. Chạy trên IN và OOD-D | Vết α_t, độ phủ dài hạn, độ phủ trên cửa sổ trượt 200 chu kỳ | Có số liệu định lượng cho Mục 6.8. Nếu không thấy α_t trôi thì rút kết luận khỏi báo cáo |
| E3 | ② | Dư độ phủ của PAC giảm khi tăng cỡ mẫu chứng nhận hoặc giảm số lần thử | Quét n_cert ∈ {100; 200; 400; 800}, M ∈ {1; 3}, δ ∈ {0,01; 0,05; 0,1}. Gồm Monte Carlo nhị thức (4.000 lần) và một điểm chạy thật (n = 400, M = 1) | Xác suất chấp nhận khi p_true ∈ [0,85; 0,97]; độ phủ hậu chứng nhận; m₃ₛ | Bảng gợi ý cỡ mẫu cho CARLA: n tối thiểu để dư độ phủ ≤ 0,02 |
| E4 | ④ | Một khối hiệu chỉnh chuyên biệt cho D2/D7 cho phép chứng nhận PAC riêng nhóm `loss` | Thêm khối 150 lượt chỉ D2 (hạt giống 1000–1149) cho hiệu chỉnh và 150 lượt (1150–1299) cho chứng nhận. So hai cách: (a) PAC tổng thể trên tỉ lệ R/q(g); (b) PAC riêng từng nhóm | n_loss mỗi khối; chứng nhận đạt hay không; độ phủ nhóm `loss` trên IN và D7 | n_loss ≥ 39 mỗi khối; độ phủ `loss` có KTC chứa hoặc vượt 0,90 |
| E5 | ⑥ | Tự tương quan còn lại đến từ tương quan trong cùng lượt | So 4 cách lấy mẫu: Δ ∈ {3; 4; 6} s, và "1 chu kỳ ngẫu nhiên mỗi lượt". Thêm hiệu chỉnh phù hợp theo khối (mỗi lượt là một điểm số max) | ρ₁, ρ theo độ trễ 1–5; độ phủ; độ rộng KTC hiệu dụng (n_eff) | Nếu "1 mẫu/lượt" cho độ phủ chuẩn hơn thì đề xuất sửa giả thiết A1 |
| E6 | ⑦ | Tách sai số bám thuần khỏi độ lệch do lập lại kế hoạch | Với mỗi chu kỳ đã lấy thưa, chạy song song một nhánh "mở vòng" bám đúng kế hoạch phát tại t (không lập lại kế hoạch). Đo E_track (nhánh mở vòng) và E_replan = E − E_track | Trung bình và P95 của E_track/σ, E_replan/σ theo D và S | Có số liệu cho câu chữ sửa Mục 2.3; xác nhận E_track ở D0 < 0,5 m tại 3 s |
| E7 | ⑤ | Độ phủ vật lý bão hòa do dư địa hình học | Quét d_s ∈ {0,5; 1,0}; mật độ lưới vận tốc {1,0; 0,5} m/s (351 và 663 ứng viên); làn hẹp 3,0 m | Độ phủ d ≥ d_s, va chạm, khoảng cách giữa độ phủ điểm số và độ phủ vật lý | Tìm cấu hình mà độ phủ vật lý của B1/B5 < 0,99, để thấy ưu thế của ĐX bằng an toàn vật lý chứ không chỉ điểm số |
| E8 | — | σ_τ ước lượng trên S1–S4 bị lệch khi gặp S5–S10 | Ước lượng σ_τ lại trên từng kịch bản (hạt giống 1300–1399) và so với σ_τ chung | Tỉ số σ_τ(S)/σ_τ(chung) tại τ = 10, 20, 30 | Nếu lệch > 30% thì đề xuất σ_τ theo loại tác nhân |
| E9 | — | Cỡ mẫu 15 lượt mỗi ô quá ít để kết luận theo từng ô | Tăng tập IN lên 30 hạt giống (500–529) cho ĐX-1, ĐX-2, ĐX-3, B1 | Độ rộng KTC theo ô | Độ rộng KTC 95% theo ô ≤ 0,08 |

### 9.5. Trường hợp kiểm thử mã (TC) — kiểm tra tính đúng của cài đặt

Các test đặt trong `tests/` và chạy bằng `pytest`. Mỗi test phải xong trong < 60 s.

| Mã | Loại | Nội dung | Kết quả mong đợi |
|---|---|---|---|
| TC-01 | Hồi quy | Chạy lại B0, ĐX-1 trên 5 hạt giống của tập IN sau khi sửa lõi | Khớp `logs/new` với sai khác < 1e-9 |
| TC-02 | Hình học | Khoảng cách hộp–đĩa: so với lời giải lấy mẫu dày (10⁴ điểm biên) trên 1.000 cấu hình ngẫu nhiên | Sai số tuyệt đối < 1e-6 m; bằng 0 khi chồng lấn |
| TC-03 | Tính chất | A_h ≥ A_c với mọi chu kỳ; A_h = A_c với tác nhân 1 đĩa | Đúng 100% chu kỳ |
| TC-04 | Đồng nhất thức | a + b = d̂ − d (phân tách có dấu) | Sai khác < 1e-9 |
| TC-05 | Thống kê | Phân vị phù hợp trên dữ liệu hoán đổi được tổng hợp (n = 200, 10.000 lần lặp, Gauss/Student-t/Pareto) | Độ phủ ∈ [1−α; 1−α + 1/(n+1)] ± 0,005 |
| TC-06 | Thống kê | Hàm chọn k_PAC: kiểm với n = 39 và n = 187, α = 0,1, δ = 0,05/3 | n_min = 39; k(187) = 178; P(Bin ≥ k) ≤ δ |
| TC-07 | Thống kê | Monte Carlo PAC M = 3 tại p_true = 0,89 | Tỉ lệ chứng nhận sai ≤ δ + 3·SE |
| TC-08 | ACI | Ở chế độ B, chu kỳ có 𝒥 = ∅ không làm đổi α_t và cửa sổ trượt | α_t và cửa sổ trước và sau chu kỳ trống giống hệt nhau |
| TC-09 | ACI | Chuỗi điểm số dịch phân phối đột ngột (tổng hợp) | Độ phủ dài hạn ∈ 1−α ± 0,02 sau 2.000 bước |
| TC-10 | Lấy mẫu | Lấy thưa Δ = 3 s: không có hai chu kỳ nào cùng lượt có cửa sổ [t, t+H] giao nhau | Đúng 100% |
| TC-11 | Rò rỉ dữ liệu | Tập hạt giống của σ_τ, hiệu chỉnh, chứng nhận và kiểm tra (kể cả các khối mới 800–1399) không giao nhau | Giao rỗng |
| TC-12 | Xe | D0, đường thẳng, không tác nhân: E₃₀ (nhánh mở vòng) | Trung bình < 0,3 m; P95 < 0,5 m |
| TC-13 | Xe (S7) | Đường cong R = 25 m ở 6 m/s: sai số ngang bám ổn định | < 0,3 m; δ không vượt δ_max; ω không vượt ω_max |
| TC-14 | Kịch bản S5 | Tác nhân bị che không xuất hiện trong 𝒥_t trước thời điểm lộ diện | Đúng 100% chu kỳ |
| TC-15 | Kịch bản S9 | Khi TTC < 2 s, tác nhân đổi hành vi đúng xác suất 0,6/0,4 (1.000 lần) | Tỉ lệ nhường ∈ 0,6 ± 0,04 |
| TC-16 | Điều kiện D8 | Tỉ lệ khung báo nhãn `fix` khi trạng thái thật là float | ∈ 0,30 ± 0,03 |
| TC-17 | Dự phòng | Khi không còn ứng viên, dự phòng phanh với a_min; ở D9 gia tốc thực bị cắt ở −3 m/s² | Đúng như đặc tả |
| TC-18 | Tất định | Chạy cùng hạt giống 2 lần, song song 1 và 2 tiến trình | Kết quả giống hệt nhau |

### 9.6. Chia hạt giống bổ sung

| Hạt giống | Dùng cho |
|---|---|
| 500–529 | Tập IN mở rộng (E9); 500–514 giữ nguyên để so với v0.1 |
| 700–709 | OOD-S, OOD-D, OOD-SD (mỗi ô 10 lượt, ghép cặp giữa các phương pháp) |
| 710–719 | Tập kiểm tra của RECAL (110 ô × 10 lượt) |
| 800–949 | RECAL: hiệu chỉnh lặp 3 khối × 50 lượt trên S1–S10 × D0–D10 trộn |
| 950–999 | RECAL: chứng nhận |
| 1000–1149 / 1150–1299 | E4: hiệu chỉnh / chứng nhận chuyên biệt D2 |
| 1300–1399 | E8: ước lượng σ_τ theo kịch bản |

### 9.7. Khối lượng ước tính

Đã đo khoảng 0,25 s mỗi lượt. Với S7 và S8 ước tính khoảng 0,4 s mỗi lượt.

| Hạng mục | Số lượt (ước) |
|---|---|
| OOD (86 ô × 10 × 11 phương pháp) | ~9.500 |
| RECAL (hiệu chỉnh và chứng nhận ~300 × 3 ĐX + kiểm tra 1.100 × 11) | ~13.000 |
| E1 (8 α × 4 phương pháp × ~660 lượt) | ~21.000 |
| E2, E5, E6, E7 | ~8.000 |
| E3 (chạy thật), E4, E8, E9 | ~3.000 |
| **Tổng** | **~55.000 lượt, khoảng 3–4 giờ tính với 2 tiến trình** |

Nếu thiếu thời gian, thứ tự ưu tiên là: OOD → E1 → E2 → E4 → E6 → các mục còn lại. E1 có thể giảm xuống 5 mức α.

### 9.8. Log bổ sung

```
logs/ext/
  config.json           tham số S5–S10, D6–D10, các khối hạt giống mới
  calibration_recal.json
  calibration_d2.json   (E4)
  cycles.csv            như v0.1, thêm cột: split (IN/OOD-S/OOD-D/OOD-SD/RECAL),
                        n_agents, occluded_before, curvature, e_track, e_replan
  episodes.csv          như v0.1, thêm cột split
  summary.json          method × split × scn × cond
  alpha_sweep_ext.csv   (E1)
  aci_trace.csv         (E2) method, variant, gamma, seed, t, alpha_t, err
  pac_power.csv         (E3)
  thinning_ext.csv      (E5)
  sigma_by_scn.csv      (E8)
tests/                  test_*.py cho TC-01..TC-18; kết quả pytest ghi ra logs/ext/tests.txt
```

### 9.9. Báo cáo bổ sung

Thêm một phụ lục "Kết quả mở rộng v0.2" vào báo cáo, hoặc làm báo cáo riêng `report/BAO_CAO_MO_RONG_v0.2.md`, gồm:

1. Bảng độ phủ theo tập IN / OOD-S / OOD-D / OOD-SD / RECAL (hình H7).
2. Đường đánh đổi ở cùng độ phủ (E1), có KTC bootstrap (hình H8).
3. Vết α_t của ACI (E2) (hình H9).
4. Đồ thị lực kiểm định PAC và bảng cỡ mẫu gợi ý cho CARLA (E3) (hình H10).
5. Phân tách E_track / E_replan (E6) (hình H11).
6. Bảng TC-01..TC-18: đạt / không đạt.
7. Cập nhật bảng đề xuất sửa đổi bản thảo. Nhất là phần ACI (Mục 6.8) và cách trình bày ưu thế của ĐX (điểm ①).

### 9.10. Tiêu chí nghiệm thu bổ sung

- TC-01..TC-18 đạt toàn bộ. Nếu có test không đạt thì phải ghi nguyên nhân và cách xử lý.
- Log v0.1 (`logs/old`, `logs/new`) không bị ghi đè. Kết quả S1–S4 × D0–D5 tái lập đúng (TC-01).
- `python run_ext.py --seed-base 0` sinh lại toàn bộ `logs/ext/` và các hình H7–H11.
- Mọi kết luận mới trong báo cáo truy được về `logs/ext/`. Kết luận nào không được dữ liệu ủng hộ (ví dụ ACI ở điểm ③) phải được sửa hoặc rút lại.
