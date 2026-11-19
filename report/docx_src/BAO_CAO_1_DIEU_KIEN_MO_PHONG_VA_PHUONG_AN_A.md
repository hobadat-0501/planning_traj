---
title: "BÁO CÁO 1 — ĐIỀU KIỆN MÔ PHỎNG VÀ KẾT QUẢ PHƯƠNG ÁN A"
subtitle: "Biên an toàn phù hợp có xét sai số của xe tự hành — kiểm chứng vòng kín 2D, gói v0.1"
date: "16/11/2026"
---

# 1. Mục đích và phạm vi

**Mục đích.** Báo cáo này trình bày ba nội dung:

1. Toàn bộ điều kiện mô phỏng đã dùng để kiểm chứng bản thảo v0.1.
2. Phần nào được **chạy thực** trong vòng kín, phần nào là **giả lập** (mô hình thay thế), phần nào là **tính toán tổng hợp**.
3. Kết quả, điểm mạnh và điểm yếu của **Phương án A**: cài đặt đúng theo bản thảo v0.1, chưa sửa đổi.

**Nguồn số liệu:**

- `logs/old/`: `config.json`, `calibration.json`, `cycles.csv`, `episodes.csv` (3.600 lượt), `summary.json`;
- các hình H1–H6 trong `figs/`;
- mã nguồn `sim/core.py`, `sim/common.py`, `sim/run_old.py`.

**Phạm vi.** Phương án B (các sửa đổi) và so sánh A–B được trình bày ở *Báo cáo 2*.

# 2. Điều kiện mô phỏng

## 2.1. Môi trường

Toàn bộ thí nghiệm là **mô phỏng vòng kín 2D viết bằng Python/NumPy**, chạy tất định theo hạt giống.

- **Không có:** CARLA, xe Hunter SE, ROS 2, cảm biến hay bộ dự báo học sâu.
- **Nghĩa của "chạy thực" trong báo cáo:** được thực thi thật trong vòng kín *xe – lập kế hoạch – bám quỹ đạo* của bộ mô phỏng và có log từng chu kỳ. Không có nghĩa là chạy trên xe hay trên CARLA.

## 2.2. Phần chạy thực, phần giả lập, phần tính toán tổng hợp

**Bảng 1. Phần chạy thực (thực thi vòng kín, có log)**

| Thành phần | Mô tả | Bằng chứng |
|---|---|---|
| Vòng kín xe – planner – bộ bám | Mô phỏng 20 Hz, tối đa 16 s mỗi lượt. Planner Frenet 10 Hz với 351 ứng viên, lọc an toàn bằng biên. Pure Pursuit 20 Hz | `cycles.csv`, `episodes.csv` |
| Hiệu chỉnh lặp (Thuật toán 1) cho ĐX-1, ĐX-2 | 3 khối × 50 lượt (hạt giống 250–399). Sau mỗi lần cập nhật q, chạy lại vòng kín với chính sách mới | `calibration.json` |
| Chứng nhận | Tối đa 3 lần thử × 50 lượt (400–449, 450–499, 600–649) | `calibration.json` |
| Hiệu chỉnh các đối chứng B1–B5 | Trên lượt B0 dùng chung, hạt giống 250–399 | `calibration.json` |
| Kiểm tra ghép cặp | 15 hạt giống (500–514) × 6 điều kiện × 4 kịch bản = 360 lượt mỗi phương pháp. 10 phương pháp, tổng 3.600 lượt | `episodes.csv` |
| ACI (B6, ĐX-3) | Cập nhật α_t trực tuyến trong vòng kín, phản hồi trễ H = 30 bước | `cycles.csv` |
| Thời gian tính | Đo thật thời gian lõi NumPy của planner: P95 khoảng 1,37–1,47 ms | `episodes.csv` |

**Bảng 2. Phần giả lập (mô hình thay thế cho thế giới thật)**

| Thành phần | Cách giả lập trong mô phỏng | Ngoài đời / CARLA | Hệ quả |
|---|---|---|---|
| Động lực học xe | Mô hình xe đạp động học, trễ bậc nhất | PhysX: lốp phi tuyến, chuyển tải, ABS | Sai số bám nhỏ, "sạch" hơn thực tế |
| Định vị | Nhiễu tổng hợp cộng vào trạng thái thật. Nhãn fix/float/loss **gán theo điều kiện** | Máy thu RTK và bộ lọc EKF | Nhãn luôn đúng |
| Nhận thức tác nhân | Vị trí và vận tốc thật cộng nhiễu Gauss, bán kính 40 m | LiDAR/camera, mạng phát hiện | Không có che khuất, mất phát hiện hay trễ pipeline |
| Dự báo quỹ đạo | **Vận tốc hằng (CV)** | Trajectron++ (theo bản thảo) | Không đánh giá được bộ dự báo của bài báo |
| Tác nhân | Hành vi theo kịch bản, nhiễu AR(1); **không phản ứng** với xe | Người và xe có tương tác | Phân phối điểm số ít phụ thuộc chính sách |
| Hình học | Đường thẳng; tác nhân là tập đĩa cứng | Đường cong, giao lộ; đa giác | Không thử được độ cong lớn |

**Bảng 3. Phần tính toán tổng hợp (không chạy xe)**

| Phân tích | Cách làm | Ghi chú |
|---|---|---|
| Rủi ro chứng nhận có điều kiện (H5a) | Monte Carlo trên phân phối nhị thức: 4.000 lần lặp mỗi giá trị $p_{\text{true}}$, $n = 187$ | Con số 76,8% chấp nhận sai là xác suất mô phỏng số, không phải từ lượt chạy xe |
| Phân phối độ phủ hậu chứng nhận (H5b) | 3.000 kịch bản tổng hợp | Như trên |
| Tự tương quan $\rho_1$, tỉ lệ mẫu rỗng, $A_h$ so với $A_c$ | Tính lại trên chuỗi đã log | Đầu vào là dữ liệu chạy thực |
| Khoảng tin cậy, kiểm định | Clopper–Pearson; McNemar/Wilcoxon với hiệu chỉnh Holm | Trên dữ liệu chạy thực |

## 2.3. Xe và bộ điều khiển

**Bảng 4. Thông số xe và vòng điều khiển**

| Thông số | Giá trị |
|---|---|
| Xe (cỡ Tesla Model 3) | $L = 2{,}875$ m; hộp $4{,}69 \times 1{,}85$ m; cầu sau cách đuôi 0,96 m; $r_{\max} = 3{,}85$ m |
| Giới hạn | $\delta_{\max} = 0{,}6$ rad; $\omega_{\max} = 0{,}8$ rad/s; $a \in [-6;\,3]$ m/s²; $v_{\max} = 8{,}3$ m/s |
| Trễ và sai số chấp hành | Trễ gia tốc 0,25 s; trễ lái 0,1 s; sai số hệ số lái ±5% mỗi lượt; trễ lệnh nền 50 ms; bù trước vận tốc tại $t + 0{,}5$ s |
| Tần số | Mô phỏng 20 Hz ($\Delta t = 0{,}05$ s); planner 10 Hz ($T_s = 0{,}1$ s); chân trời $H = 30$ bước = 3,0 s |
| Đường | Thẳng theo trục $x$; làn $y \in [-1{,}75;\,1{,}75]$ m; đích $x = 75$ m; tối đa 16 s mỗi lượt |
| Planner | 351 ứng viên Frenet = 13 độ lệch ngang (±1,5 m, bước 0,25 m) × 9 vận tốc đích (0–8,3 m/s) × 3 thời gian $T \in \{3, 4, 5\}$ s |
| Dự phòng | Không còn ứng viên hợp lệ thì phanh với $a = -6$ m/s² |

**Động học xe.** Xe dùng mô hình xe đạp động học tại tâm cầu sau:

$$\dot{x} = v\cos\psi,\qquad \dot{y} = v\sin\psi,\qquad \dot{\psi} = \frac{v}{L}\tan\delta,\qquad \dot{v} = a \qquad (1)$$

**Trễ chấp hành.** Gia tốc và góc lái được đưa qua khâu trễ bậc nhất:

$$\dot{a} = \frac{a_{\text{cmd}} - a}{T_a},\qquad \dot{\delta} = \frac{\delta_{\text{cmd}} - \delta}{T_\delta},\qquad T_a = 0{,}25\ \text{s},\ T_\delta = 0{,}1\ \text{s} \qquad (2)$$

**Bộ bám Pure Pursuit.** Tầm nhìn trước và góc lái:

$$L_d = 2 + 0{,}3\,v,\qquad \delta_{\text{cmd}} = \arctan\!\left(\frac{2L\sin\eta}{L_d}\right) \qquad (3)$$

trong đó $\eta$ là góc giữa hướng xe và điểm nhìn trước.

**Chi phí của planner.** Planner chọn ứng viên có chi phí nhỏ nhất:

$$J = \left(v_{\max} - v_{\text{đích}}\right)^2 + 0{,}1\int_0^{T} \dddot{s}^{\,2}\,dt + 2\,d_f^2 \qquad (4)$$

trong đó $d_f$ là độ lệch ngang cuối của ứng viên.

**Bộ lọc an toàn.** Ứng viên chỉ hợp lệ khi, với mọi bước $\tau$ và mọi tác nhân $j$:

$$\hat{d}^{\,j}_{\tau} \;\ge\; d_s + m_\tau,\qquad \forall \tau \in \{1,\dots,H\},\ \forall j \in \mathcal{J}_t,\qquad d_s = 0{,}5\ \text{m} \qquad (5)$$

## 2.4. Điều kiện định vị D0–D5

**Bảng 5. Sáu điều kiện suy giảm**

| Mã | Mô tả | Thông số | Nhãn |
|---|---|---|---|
| D0 | RTK cố định | $\sigma = 0{,}03$ m / 0,003 rad | fix |
| D1 | RTK thả nổi | AR(1), hằng số thời gian 5 s, 0,3 m / 0,02 rad | float |
| D2 | Mất GNSS | Mất 5–10 s, trôi tích lũy, hội tụ lại sau 1,5 s | loss khi mất, fix ngoài khoảng mất |
| D3 | Trượt bánh | Thiếu lái 15%; trượt ngang AR(1), $\sigma = 0{,}04$ | fix |
| D4 | Trễ cố định | Thêm {50, 100, 200} ms | fix |
| D5 | Trễ ngẫu nhiên | Gamma(2; 0,05), cắt ở 0,3 s | fix |

Nhiễu AR(1) dùng cho định vị thả nổi (D1) và trượt ngang (D3):

$$\varepsilon_{k+1} = \rho\,\varepsilon_k + \sigma\sqrt{1-\rho^2}\;\xi_k,\qquad \rho = e^{-\Delta t/\tau_c},\qquad \xi_k \sim \mathcal{N}(0, 1) \qquad (6)$$

với $\tau_c = 5$ s ở D1.

## 2.5. Tác nhân và kịch bản S1–S4

**Hình dạng tác nhân.** Mỗi tác nhân là một tập đĩa cứng, có nhiễu AR(1) trên tốc độ quay và gia tốc dọc:

- người đi bộ: 1 đĩa, $r = 0{,}35$ m;
- xe máy: 2 đĩa, $r = 0{,}45$ m, cách nhau 1 m;
- ô tô: 3 đĩa, $r = 0{,}95$ m, cách nhau 1,4 m.

**Bảng 6. Bốn kịch bản**

| Mã | Mô tả | Thông số |
|---|---|---|
| S1 | Người đi bộ sang đường | 0,8–1,8 m/s; 20% dừng giữa đường 2–4 s |
| S2 | Xe máy cắt ngang | Góc 30–90°, 3–8 m/s |
| S3 | Giao cắt không đèn | Xe máy + ô tô |
| S4 | Xe phía trước phanh gấp | Giảm tốc 2–5 m/s² |

## 2.6. Phân chia hạt giống

**Bảng 7. Các khối hạt giống của Phương án A**

| Khối | Hạt giống | Số lượt | Mục đích |
|---|---|---|---|
| Hiệu chỉnh | 250–299, 300–349, 350–399 | 3 × 50 | Thuật toán 1 và hiệu chỉnh đối chứng |
| Chứng nhận | 400–449, 450–499, 600–649 | Tối đa 3 × 50 | Chứng nhận có điều kiện |
| Kiểm tra | 500–514 | 15 × 24 ô = 360 mỗi phương pháp | Đánh giá ghép cặp |

Phương án A **không có** khối ước lượng $\sigma_\tau$, vì dùng công thức cố định (7).

# 3. Phương pháp và công thức của Phương án A

## 3.1. Chuẩn hóa và các thành phần sai số

**Hệ số chuẩn hóa.** Phương án A dùng công thức cố định của bản thảo:

$$\sigma_\tau = 0{,}05 + 0{,}04\,\tau\ \ [\text{m}],\qquad \tau = 1,\dots,30 \;\Rightarrow\; \sigma_1 = 0{,}09\ \text{m},\ \sigma_{30} = 1{,}25\ \text{m} \qquad (7)$$

**Sai số xe.** Gọi $p_{t+\tau\mid t}$ là tư thế kế hoạch phát tại $t$ và $e_{t+\tau}$ là tư thế thật:

$$E_\tau = \big\lVert p^{xy}_{t+\tau\mid t} - e^{xy}_{t+\tau}\big\rVert + r_{\max}\,\big|\psi_{t+\tau\mid t} - \psi^{e}_{t+\tau}\big| \qquad (8)$$

**Sai số tác nhân.** Phương án A dùng sai số tâm:

$$A^{c}_{\tau} = \max_{j\in\mathcal{J}_t} \big\lVert \hat{c}^{\,j}_{t+\tau\mid t} - c^{\,j}_{t+\tau} \big\rVert \qquad (9)$$

## 3.2. Điểm số và ngưỡng phù hợp

**Điểm số.** Gọi $\hat{d}^{\,j}_\tau = D\big(\mathcal{B}(p_{t+\tau\mid t}), \hat{O}^{j}_{t+\tau\mid t}\big)$ là khoảng cách theo kế hoạch và dự báo, $d^{\,j}_\tau = D\big(\mathcal{B}(e_{t+\tau}), O^{j}_{t+\tau}\big)$ là khoảng cách thật. Điểm số của chu kỳ $i$:

$$R_i = \max_{\tau\in\{1..H\}}\ \max_{j\in\mathcal{J}_i}\ \frac{\hat{d}^{\,j}_\tau - d^{\,j}_\tau}{\sigma_\tau} \qquad (10)$$

**Chu kỳ không có tác nhân.** Ở Phương án A, chu kỳ có $\mathcal{J}_i = \emptyset$ vẫn được giữ lại với giá trị:

$$R_i = -\infty\quad \text{khi } \mathcal{J}_i = \emptyset \qquad (11)$$

**Ngưỡng phù hợp.** Với $n$ điểm số hiệu chỉnh sắp xếp tăng dần:

$$\hat{q} = R_{(k)},\qquad k = \big\lceil (n+1)(1-\alpha) \big\rceil,\qquad \alpha = 0{,}10 \qquad (12)$$

**Biên an toàn:**

$$m_\tau = \hat{q}\,\sigma_\tau \qquad (13)$$

**Bảo đảm của Định lý 1.** Nếu các điểm số hoán đổi được, thì:

$$\mathbb{P}\big(R_{n+1} \le \hat{q}\big) \;\ge\; 1-\alpha \qquad (14)$$

## 3.3. Lấy thưa mẫu

Phương án A lấy một chu kỳ trong mỗi ô thời gian 2 s, **giữ cả chu kỳ rỗng**:

$$b_i = \left\lfloor \frac{t_i}{2\ \text{s}} \right\rfloor,\qquad \text{chọn chu kỳ đầu tiên của mỗi } b_i \qquad (15)$$

Vì $\Delta = 2\ \text{s} < H\,T_s = 3\ \text{s}$, hai cửa sổ dự báo liên tiếp **chồng nhau 1 s**.

## 3.4. Các phương pháp so sánh

**Bảng 8. Định nghĩa các phương pháp ở Phương án A**

| Mã | Tên | Biên $m_\tau$ |
|---|---|---|
| B0 | Không biên | $m_\tau = 0$ |
| B1 | Chỉ sai số tác nhân | $q_{A}\,\sigma_\tau$, với $q_A$ là phân vị (12) của $\max_\tau A^c_\tau/\sigma_\tau$ |
| B2 | B1 + hằng số | $q_{A}\,\sigma_\tau + 0{,}3$ m |
| B3 | Cộng hai biên riêng | Công thức (16) |
| B4 | Ống bám xấu nhất | Công thức (17) |
| B5 | Ràng buộc cơ hội Gauss | Công thức (18) |
| B6 | ACI trên điểm số tác nhân | Công thức (19), cửa sổ 500 |
| ĐX-1 | Biên gộp | $\hat{q}_R\,\sigma_\tau$, với $\hat{q}_R$ từ (12) trên điểm số (10) |
| ĐX-2 | Biên gộp theo nhóm định vị | $\hat{q}_R(g)\,\sigma_\tau$ với $g \in \{\text{fix}, \text{float}, \text{loss}\}$ |
| ĐX-3 | ACI trên điểm số gộp | (19) áp dụng cho $R$, $\gamma = 0{,}02$, phản hồi trễ $H$ |

**B3.** Mỗi thành phần được hiệu chỉnh riêng ở mức $\alpha/2$ rồi cộng lại:

$$m^{\text{B3}}_\tau = \Big[\hat{q}_{A^c}(\alpha/2) + \hat{q}_{E}(\alpha/2)\Big]\,\sigma_\tau \qquad (16)$$

**B4.** Biên B1 cộng với sai số bám lớn nhất trên tập hiệu chỉnh:

$$m^{\text{B4}}_\tau = q_A\,\sigma_\tau + \max_{i\in\text{cal}} \max_\tau E_{\tau,i} \qquad (17)$$

**B5.** Giả định Gauss, với $s_{a,\tau}$ và $s_{b,\tau}$ là độ lệch chuẩn mẫu của hai thành phần có dấu tại bước $\tau$:

$$m^{\text{B5}}_\tau = z_{1-\alpha}\sqrt{s_{a,\tau}^2 + s_{b,\tau}^2},\qquad z_{0{,}9} = 1{,}2816 \qquad (18)$$

**B6 và ĐX-3 (ACI).** Mức rủi ro được cập nhật sau phản hồi trễ $H$ bước:

$$\alpha_{t+1} = \alpha_t + \gamma\left(\alpha - \mathbb{1}\{R_{t-H} > q_{t-H}\}\right),\qquad \gamma = 0{,}02 \qquad (19)$$

Ở Phương án A, cập nhật (19) thực hiện ở **mọi chu kỳ**, kể cả chu kỳ rỗng ($R = -\infty$, luôn tính là "không vi phạm").

## 3.5. Thuật toán 1 và chứng nhận có điều kiện

**Thuật toán 1.** Ngưỡng được cập nhật lặp trên dữ liệu thu dưới chính sách hiện hành $\pi(q_k)$:

$$q_{k+1} = \operatorname{Quantile}_{(12)}\Big(\{R_i\}_{i \in \text{khối }k}\ \text{thu dưới}\ \pi(q_k)\Big),\qquad k = 0, 1, 2 \qquad (20)$$

**Chứng nhận có điều kiện (Định lý 2 bản thảo).** Chính sách được chấp nhận nếu:

$$\hat{q}_{\text{cert}} = R^{\text{cert}}_{(\lceil (n+1)(1-\alpha)\rceil)} \;\le\; q_{\text{plan}} \qquad (21)$$

Nếu không đạt, tăng $q$ và thử lại, tối đa $M = 3$ lần.

## 3.6. Chỉ số đánh giá

**Độ phủ điểm số.** Kiểm chứng trực tiếp (14):

$$\widehat{\text{Cov}}_R = \frac{1}{n}\sum_{i=1}^{n} \mathbb{1}\{R_i \le q_i\} \qquad (22)$$

**Độ phủ an toàn vật lý:**

$$\widehat{\text{Cov}}_d = \frac{1}{n}\sum_{i=1}^{n} \mathbb{1}\Big\{\min_{\tau, j} d^{\,j}_{\tau,i} \ge d_s\Big\} \qquad (23)$$

**Khoảng tin cậy 95% Clopper–Pearson** cho $k$ thành công trên $n$:

$$\Big[\,B^{-1}\!\big(0{,}025;\,k,\,n-k+1\big),\ \ B^{-1}\!\big(0{,}975;\,k+1,\,n-k\big)\Big] \qquad (24)$$

trong đó $B^{-1}$ là hàm ngược của phân phối Beta.

**Các chỉ số khác:**

- va chạm, vi phạm lượt;
- $d_{\min}$, $\text{TTC}_{\min}$;
- tỉ lệ hoàn thành, $t_{\text{end}}$, tỉ lệ dự phòng;
- RMS độ giật, P95 thời gian tính;
- biên tại 3 s:

$$m_{3\text{s}} = q\,\sigma_{30} \qquad (25)$$

# 4. Kết quả Phương án A

## 4.1. Kết quả tổng thể

**Bảng 9. Kết quả chính của Phương án A** (360 lượt mỗi phương pháp; KTC 95%)

| Phương pháp | Độ phủ $d \ge d_s$ | Độ phủ điểm số $R \le q$ | Vi phạm lượt / va chạm | $d_{\min}$ (m) | Hoàn thành / $t_{\text{end}}$ (s) / dự phòng | $q$ / $m_{3\text{s}}$ (m) |
|---|---|---|---|---|---|---|
| B0 | 0,896 [0,881; 0,910] | 0,329 [0,308; 0,351] | 33,1% / 10,6% | 1,31 | 80,8% / 12,34 / 5,4% | 0 / 0 |
| B1 | 1,000 [0,998; 1,000] | 0,887 [0,873; 0,900] | 0% / 0% | 4,15 | 70,6% / 13,87 / 3,5% | 3,55 / 4,43 |
| B2 | 1,000 [0,998; 1,000] | 0,889 [0,875; 0,902] | 0% / 0% | 4,45 | 68,1% / 13,95 / 3,8% | 3,55 / 4,73 |
| B3 | 1,000 [0,998; 1,000] | 0,998 [0,995; 0,999] | 0% / 0% | 15,78 | 27,5% / 15,57 / 8,1% | 13,06 / 16,32 |
| B4 | 1,000 [0,999; 1,000] | 0,900 [0,888; 0,912] | 0% / 0% | 18,57 | 16,4% / 15,73 / 11,9% | 3,55 / 19,32 |
| B5 | 0,995 [0,990; 0,997] | 0,848 [0,832; 0,863] | 1,7% / 0,3% | 3,12 | 76,7% / 13,47 / 3,8% | 2,78 / 3,48 |
| B6 | 1,000 [0,998; 1,000] | 0,926 [0,914; 0,936] | 0,3% / 0% | 6,06 | 62,8% / 14,41 / 5,8% | 5,85 / 7,31 |
| **ĐX-1** | 1,000 [0,998; 1,000] | **0,874 [0,859; 0,888]** | 0% / 0% | 3,80 | 71,4% / 13,77 / 3,6% | 3,21 / 4,02 |
| **ĐX-2** | 0,999 [0,997; 1,000] | **0,893 [0,879; 0,906]** | 0,3% / 0% | 3,91 | 71,4% / 13,79 / 4,0% | 3,30 / 4,13 |
| ĐX-3 | 0,999 [0,997; 1,000] | 0,904 [0,891; 0,916] | 0,6% / 0,3% | 6,75 | 60,0% / 14,24 / 7,9% | 6,59 / 8,23 |

**Nhận xét:**

- **Độ phủ vật lý bão hòa.** Ở mọi phương pháp có biên, độ phủ vật lý đạt 0,995–1,000 và va chạm bằng 0% (trừ B5 và ĐX-3, mỗi phương pháp 0,3%). Nếu chỉ nhìn chỉ số (23) như Bảng 4 của bản thảo, Phương án A **trông như đạt yêu cầu**.
- **Độ phủ điểm số lộ ra lỗi.** Chỉ số (22) kiểm tra trực tiếp Định lý 1:
  - ĐX-1 đạt 0,874 và ĐX-2 đạt 0,893, đều **dưới mức danh định** $1-\alpha = 0{,}90$.
  - KTC của ĐX-1 nằm hoàn toàn dưới 0,90.
  - Các con số này đã được "đẩy lên" nhờ 17,9% mẫu $R = -\infty$ luôn tính là phủ (mục 4.4).
- **Không biên thì không an toàn.** B0 va chạm ở 10,6% lượt. Biên là cần thiết.
- **B3 thận trọng quá mức.** $m_{3\text{s}} = 16{,}3$ m, chỉ 27,5% lượt hoàn thành.

## 4.2. Độ phủ điểm số theo điều kiện định vị

**Bảng 10. Độ phủ điểm số theo điều kiện D0–D5 (Phương án A)**

| Phương pháp | D0 | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|---|
| B1 | 0,948 | 0,779 | 0,746 | 0,946 | 0,950 | 0,956 |
| B4 | 0,949 | 0,761 | 0,840 | 0,959 | 0,942 | 0,952 |
| B5 | 0,917 | 0,705 | 0,678 | 0,923 | 0,926 | 0,937 |
| B6 | 0,960 | 0,873 | 0,838 | 0,970 | 0,955 | 0,958 |
| ĐX-1 | 0,940 | **0,759** | **0,732** | 0,933 | 0,936 | 0,947 |
| ĐX-2 | 0,930 | **0,856** | **0,796** | 0,927 | 0,927 | 0,926 |
| ĐX-3 | 0,899 | 0,892 | 0,898 | 0,907 | 0,906 | 0,923 |

**Nhận xét:**

- Ở D0 và D3–D5, mọi phương pháp có biên đều thừa độ phủ (0,93–0,96).
- Ở D1 và D2, độ phủ tụt mạnh:
  - ĐX-1 còn 0,759 / 0,732;
  - ngay cả ĐX-2, phương pháp được thiết kế cho suy giảm định vị, cũng chỉ đạt 0,856 / 0,796.
- ĐX-3 (ACI) là phương pháp duy nhất giữ được khoảng 0,90 ở mọi điều kiện, nhưng biên trung bình lớn (8,23 m).

## 4.3. ĐX-2 theo nhóm định vị và kết quả hiệu chỉnh

**Bảng 11. Độ phủ điểm số theo nhóm định vị (Phương án A)**

| Phương pháp | fix | float | loss |
|---|---|---|---|
| B1 | 0,945 (n = 1.581) | 0,779 (n = 348) | 0,620 (n = 200) |
| ĐX-1 | 0,934 (n = 1.567) | 0,759 (n = 345) | 0,604 (n = 197) |
| ĐX-2 | 0,922 (n = 1.556) | 0,856 (n = 361) | 0,736 (n = 201) |
| ĐX-3 | 0,916 (n = 1.628) | 0,892 (n = 372) | 0,834 (n = 211) |

**Ngưỡng ĐX-2 sau chứng nhận:**

$$q_{\text{fix}} = 2{,}862,\qquad q_{\text{float}} = 4{,}589,\qquad q_{\text{loss}} = 4{,}424 \qquad (26)$$

- **Ngưỡng không đơn điệu:** nhóm `loss` có ngưỡng *nhỏ hơn* nhóm `float`, trái với trực giác vật lý (mất GNSS phải xấu hơn RTK thả nổi).
- **Nguyên nhân:** mỗi khối hiệu chỉnh chỉ có vài mẫu `loss`, nên phân vị (12) dao động mạnh.
- **Hệ quả:** độ phủ nhóm `loss` chỉ đạt 0,736.

**Hội tụ của ĐX-1 (Thuật toán 1):**

$$q_0 = 3{,}865 \;\rightarrow\; 3{,}821 \;\rightarrow\; 3{,}234 \;\rightarrow\; 3{,}060;\qquad q_{\text{final}} = 3{,}213\ (m_{3\text{s}} = 4{,}02\ \text{m}) \qquad (27)$$

Chứng nhận có điều kiện (21) đạt ở lần thử 2.

## 4.4. Các phân tích bổ sung (đã định lượng)

**Bảng 12. Các phép đo chẩn đoán trên Phương án A**

| Phân tích | Kết quả | Loại số liệu |
|---|---|---|
| Tỉ lệ chu kỳ rỗng ($R = -\infty$) sau lấy thưa | 17,9% | Chạy thực |
| Độ phủ ĐX-1 nếu chỉ tính chu kỳ có tác nhân | **0,847** (thay vì 0,874) | Chạy thực |
| Tự tương quan bậc 1 của chuỗi $R$ với $\Delta = 2$ s | $\rho_1 = 0{,}353$ | Chạy thực |
| Phân vị 90% của $A_h$ so với $A_c$ | S1 +0,0%; S2 **+8,8%**; S3 **+19,9%**; S4 +0,1% | Chạy thực |
| $\sigma_{30}$ cố định so với thực nghiệm | 1,25 m so với 3,484 m (thấp hơn 2,8 lần) | Chạy thực (khối 200–249) |
| Xác suất chấp nhận sai của (21) tại $p_{\text{true}} = 0{,}899$ | **76,8%** sau tối đa 3 lần thử | **Tổng hợp** (Monte Carlo) |
| Tỉ lệ chính sách hậu chứng nhận có độ phủ < 0,90 | **24,8%** | **Tổng hợp** (Monte Carlo) |
| $E/\sigma_\tau$ của B0 ở D0 | Không có tác nhân: 0,586. Có tác nhân: 1,741 (P95 5,783) | Chạy thực |

**Vì sao giữ mẫu rỗng làm phân vị bị lệch.** Gọi $\pi_0$ là tỉ lệ mẫu rỗng. Mẫu rỗng luôn thỏa $R \le q$, nên độ phủ tổng hợp là:

$$\text{Cov}_{\text{gộp}} = \pi_0 \cdot 1 + (1-\pi_0)\,\text{Cov}_{\text{có tác nhân}} \qquad (28)$$

Do đó, để độ phủ gộp đạt $1-\alpha$, phần có tác nhân chỉ cần đạt:

$$\text{Cov}_{\text{có tác nhân}} = \frac{1-\alpha-\pi_0}{1-\pi_0} = \frac{0{,}90 - 0{,}179}{0{,}821} \approx 0{,}878 \qquad (29)$$

Như vậy, khi giữ mẫu rỗng, phân vị (12) **tự hạ mức** bảo đảm trên các chu kỳ có rủi ro thực xuống khoảng 0,878. Số đo thực tế còn thấp hơn: 0,847.

# 5. Điểm mạnh của Phương án A

1. **Cài đặt trung thực bản thảo.** Mọi lựa chọn (σ cố định, giữ $R = -\infty$, lấy thưa 2 s, $A_c$, chứng nhận có điều kiện) theo đúng bản thảo v0.1. Vì vậy mọi sai lệch đo được là sai lệch *của bản thảo*, không phải của cách cài đặt.
2. **Vòng kín thật sự.** Biên ảnh hưởng planner, planner ảnh hưởng quỹ đạo, quỹ đạo ảnh hưởng điểm số. Thuật toán 1 thực sự phải lặp, như (27) cho thấy.
3. **Các đề xuất có hiệu quả cao trên danh nghĩa.**
   - ĐX-1 có biên nhỏ nhất trong nhóm đạt độ phủ vật lý 1,000: $m_{3\text{s}} = 4{,}02$ m, hoàn thành 71,4%.
   - So với B3, biên của ĐX-1 nhỏ hơn 75% và tỉ lệ hoàn thành cao gấp 2,6 lần.
4. **Không va chạm và đủ nhanh.** Mọi biên có thiết kế phù hợp đều không gây va chạm. Thời gian tính P95 khoảng 1,4 ms, rất xa ngân sách 100 ms.
5. **Có đối chứng.** Đã có B1–B6. B5 (Gauss) sụp ở D1/D2 (0,705 / 0,678), củng cố lựa chọn conformal thay vì giả định Gauss.
6. **ĐX-3 (ACI) bền theo điều kiện.** Độ phủ 0,892–0,923 ở cả sáu điều kiện mà không cần nhãn định vị.
7. **Tái lập và ghép cặp.**
   - Hạt giống tách khối, chạy tất định.
   - Mọi phương pháp chạy trên cùng 360 cấu hình, nên dùng được kiểm định ghép cặp.
   - Nhẹ: khoảng 0,25 s mỗi lượt.

# 6. Điểm yếu của Phương án A

## 6.1. Điểm yếu về phương pháp (lỗi của bản thảo, lộ ra qua Phương án A)

**Bảng 13. Điểm yếu phương pháp của Phương án A**

| # | Điểm yếu | Bằng chứng | Mức độ |
|---|---|---|---|
| W1 | Giữ chu kỳ rỗng với $R = -\infty$ (11) làm phân vị bị kéo xuống | 17,9% mẫu rỗng; ĐX-1 chỉ phủ 0,847 trên chu kỳ có tác nhân; công thức (29) | **Nghiêm trọng**: vi phạm bảo đảm (14) |
| W2 | Lấy thưa 2 s < H = 3 s, cửa sổ chồng 1 s (15) | $\rho_1 = 0{,}353$, vi phạm giả thiết gần độc lập A1 | Nghiêm trọng |
| W3 | Sai số tác nhân dùng tâm $A_c$ (9), bỏ qua sai số quay của tác nhân nhiều đĩa | P90 của $A_h$ lớn hơn $A_c$: +8,8% (S2), +19,9% (S3) | Trung bình: B1, B3, B6 bị đánh giá thấp |
| W4 | $\sigma_\tau$ cố định (7) không bám hình dạng thật của sai số | $\sigma_{30}$ thực nghiệm 3,484 m, gấp 2,8 lần; sai số tăng siêu tuyến tính theo $\tau$ | Trung bình: $q$ phải "gánh" sai hình dạng, biên không cân giữa các $\tau$ |
| W5 | Chứng nhận có điều kiện (21) không có bảo đảm PAC; thử nhiều lần làm rủi ro cộng dồn | Chấp nhận sai 76,8%; 24,8% chính sách hậu chứng nhận phủ < 0,90 (Monte Carlo) | **Nghiêm trọng** |
| W6 | Không có đối chứng tách hiệu ứng chiếu hình học với hiệu ứng gộp | So sánh trực tiếp B3 với ĐX-1 trộn hai hiệu ứng | Trung bình: không chứng minh được nguồn lợi ích |
| W7 | ĐX-2 thiếu mẫu ở nhóm `loss`; ngưỡng không đơn điệu (26) | $q_{\text{loss}} < q_{\text{float}}$; phủ `loss` 0,736; D2 0,796 | Nghiêm trọng với D2 |
| W8 | ACI cập nhật cả trên chu kỳ rỗng (19) | Chu kỳ rỗng luôn tính "không vi phạm", làm $\alpha_t$ trôi | Nhẹ |
| W9 | $E_\tau$ trộn sai số bám với độ lệch do lập lại kế hoạch | $E/\sigma$: 0,586 khi không có tác nhân, 1,741 khi có (D0) | Trung bình: diễn giải hai nguồn sai số chưa đúng |
| W10 | Báo cáo chỉ dùng độ phủ vật lý (23), gộp chu kỳ khả thi với chu kỳ dự phòng | Độ phủ vật lý bão hòa 1,000 che mất W1–W7 | Trung bình: thước đo của bản thảo không phát hiện được lỗi |

## 6.2. Điểm yếu về điều kiện mô phỏng (chung cho cả A và B)

**Bảng 14. Giới hạn của môi trường mô phỏng**

| # | Điểm yếu | Hệ quả |
|---|---|---|
| G1 | Dự báo vận tốc hằng thay cho Trajectron++ | Không đánh giá được bộ dự báo của bài báo |
| G2 | Đường thẳng, 4 kịch bản, 1–2 tác nhân, tác nhân không phản ứng | Miền kiểm chứng hẹp. Độ phủ vật lý bão hòa vì kịch bản quá dễ |
| G3 | Nhận thức không có che khuất hay mất phát hiện; nhãn định vị luôn đúng | Đuôi phân phối sai số tác nhân bị đánh giá thấp; ĐX-2 được lợi |
| G4 | Động lực học đơn giản; phanh −6 m/s² luôn đạt | Va chạm hầu như bằng 0, không phân biệt được các phương pháp |
| G5 | Hiệu chỉnh và kiểm tra cùng 24 ô S×D; 15 hạt giống mỗi ô | Chỉ đánh giá trong phân phối; KTC theo ô rộng (khoảng ±0,075) |
| G6 | So sánh ở cùng $\alpha$, không phải ở cùng độ phủ | Chưa biết "biên hẹp hơn" là hiệu quả thật hay chỉ là phủ thấp hơn |

# 7. Kết luận

1. **Thước đo của bản thảo không phát hiện được lỗi.** Theo độ phủ vật lý, Phương án A đạt yêu cầu: 0,995–1,000, không va chạm.
2. **Độ phủ điểm số cho thấy bản thảo vi phạm chính bảo đảm của nó.**
   - ĐX-1 phủ 0,874 (0,847 trên chu kỳ có tác nhân).
   - Dưới D1/D2, độ phủ chỉ còn 0,73–0,86.
3. **Bốn nguyên nhân chính:**
   - giữ mẫu $R = -\infty$ (W1);
   - lấy thưa chồng cửa sổ (W2);
   - chứng nhận có điều kiện không có bảo đảm PAC (W5);
   - thiếu mẫu nhóm `loss` cho ĐX-2 (W7).

   Thêm vào đó là các nguyên nhân phụ W3, W4, W6, W8–W10.
4. **Các điểm yếu W1–W10 là cơ sở trực tiếp để xây dựng Phương án B**, trình bày ở *Báo cáo 2*.
5. **Kết quả chỉ có giá trị định tính với CARLA và xe thật**, do các giới hạn G1–G6 của môi trường 2D (dự báo vận tốc hằng, đường thẳng, nhãn định vị lý tưởng).
