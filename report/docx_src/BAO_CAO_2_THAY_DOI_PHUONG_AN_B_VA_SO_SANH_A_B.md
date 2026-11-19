---
title: "BÁO CÁO 2 — CÁC THAY ĐỔI CỦA PHƯƠNG ÁN B VÀ SO SÁNH VỚI PHƯƠNG ÁN A"
subtitle: "Biên an toàn phù hợp có xét sai số của xe tự hành — kiểm chứng vòng kín 2D, gói v0.1"
date: "16/11/2026"
---

# 1. Mục đích

Báo cáo này nối tiếp *Báo cáo 1*, với ba nội dung:

1. Từ các điểm mạnh và điểm yếu của Phương án A, xác định những gì Phương án B **giữ lại** và những gì **thay đổi**.
2. Trình bày các thay đổi kèm công thức.
3. So sánh định lượng kết quả của A và B trên cùng tập kiểm tra.

**Nguồn số liệu:**

- `logs/old/` (Phương án A, 3.600 lượt);
- `logs/new/` (Phương án B, 3.960 lượt, cộng thêm `alpha_sweep.csv`);
- các hình H1–H6;
- mã nguồn `sim/run_old.py` và `sim/run_new.py`.

# 2. Điều kiện mô phỏng của Phương án B

## 2.1. Những gì giữ nguyên so với A

Để so sánh công bằng, Phương án B dùng **cùng lõi mô phỏng và cùng điều kiện** với A:

- cùng xe, planner, bộ bám và các công thức (1)–(6) của Báo cáo 1;
- cùng 6 điều kiện D0–D5 và 4 kịch bản S1–S4;
- cùng hạt giống hiệu chỉnh (250–399), chứng nhận (400–499, 600–649) và kiểm tra (500–514);
- cùng $\alpha = 0{,}10$, $d_s = 0{,}5$ m, $H = 3$ s.

Mọi khác biệt kết quả giữa A và B **chỉ đến từ các thay đổi phương pháp** ở mục 3. Đặc biệt, lượt B0 hoàn toàn giống nhau ở hai phương án: 10,6% va chạm, 80,8% hoàn thành.

## 2.2. Phần chạy thực và phần giả lập của Phương án B

**Bảng 1. Phân loại các thành phần ở Phương án B**

| Thành phần | Loại | Ghi chú |
|---|---|---|
| Vòng kín xe – planner – bộ bám, 360 lượt kiểm tra × 11 phương pháp | **Chạy thực** | 3.960 dòng trong `episodes.csv` |
| Ước lượng $\hat{\sigma}_\tau$ (mới) | **Chạy thực** | 50 lượt B0, hạt giống 200–249 |
| Thuật toán 1 và chứng nhận PAC | **Chạy thực** | Vòng kín, `calibration.json` |
| Quét $\alpha \in \{0{,}01;\,0{,}02;\,0{,}05;\,0{,}10;\,0{,}20\}$ (mới) | **Chạy thực** | B1, B3′, ĐX-2: 360 lượt mỗi mức |
| ACI (B6, ĐX-3) | **Chạy thực** | Chỉ cập nhật trên chu kỳ có tác nhân |
| Động lực học, định vị, nhận thức, dự báo vận tốc hằng, tác nhân không phản ứng, đường thẳng | **Giả lập** | Giống hệt A (Báo cáo 1, Bảng 2) |
| Rủi ro chứng nhận có điều kiện so với PAC (H5) | **Tổng hợp** | Monte Carlo nhị thức: 4.000 lần lặp mỗi điểm, 3.000 kịch bản |
| $n_{\min} = 39$ | **Tổng hợp** | Giải tích, công thức (11) |
| $\rho_1$; $A_h$ so với $A_c$; tách khả thi / dự phòng | Tính trên dữ liệu chạy thực | — |

Tổng cộng, cả A lẫn B có khoảng 9.000 lượt vòng kín chạy thực.

# 3. Từ điểm yếu của A đến thay đổi của B

## 3.1. Bảng ánh xạ

**Bảng 2. Mỗi điểm yếu của A và thay đổi tương ứng ở B**

| Điểm yếu của A (Báo cáo 1) | Thay đổi ở Phương án B | Công thức |
|---|---|---|
| W1: giữ chu kỳ rỗng, $R = -\infty$ | **Loại** chu kỳ rỗng khỏi hiệu chỉnh, chứng nhận và đánh giá | (3) |
| W2: lấy thưa 2 s, chồng cửa sổ | Lấy thưa **3 s = H**, không chồng cửa sổ | (4) |
| W3: sai số tâm $A_c$ | Dùng **cận Hausdorff** $A_h$ cho B1, B3, B6 | (5) |
| W4: $\sigma_\tau$ cố định | **Ước lượng thực nghiệm** $\hat{\sigma}_\tau$ trên khối riêng 200–249 | (1), (2) |
| W5: chứng nhận có điều kiện | **Chứng nhận PAC** hiệu chỉnh Bonferroni | (9)–(11) |
| W6: không tách được hai hiệu ứng | Thêm đối chứng **B3′** (hai thành phần có dấu, mỗi phần ở mức $\alpha/2$) | (6)–(8) |
| W7: ĐX-2 thiếu mẫu `loss` | Chứng nhận PAC **tổng thể** trên tỉ số $R/q(g)$; nêu rõ $n_{\min}$ mỗi nhóm | (12) |
| W8: ACI cập nhật trên chu kỳ rỗng | Chỉ cập nhật khi $\mathcal{J}_{t-H} \neq \emptyset$ | (13) |
| W10: chỉ báo cáo độ phủ vật lý, gộp khả thi với dự phòng | Báo cáo **độ phủ điểm số** kèm KTC; **tách** chu kỳ khả thi / dự phòng; kiểm định ghép cặp với hiệu chỉnh Holm | (14) |
| W9: $E_\tau$ trộn sai số bám với độ lệch do lập lại kế hoạch | **Chỉ định lượng** (0,586 so với 1,741), **chưa sửa** trong B | — |

**Những điểm mạnh của A được giữ lại:**

- vòng kín;
- cấu trúc ba đề xuất ĐX-1/2/3;
- thiết kế ghép cặp;
- tính tất định và bộ đối chứng B1–B6.

## 3.2. Ước lượng thực nghiệm $\hat{\sigma}_\tau$ (sửa W4)

Trên 50 lượt B0 (hạt giống 200–249), lấy phân vị 90% của độ lệch khoảng cách tại từng bước $\tau$, chỉ trên chu kỳ có tác nhân:

$$\tilde{\sigma}_\tau = \operatorname{Quantile}_{0{,}9}\Big\{\max_{j}\big(\hat{d}^{\,j}_{\tau,i} - d^{\,j}_{\tau,i}\big)\ :\ \mathcal{J}_i \neq \emptyset\Big\} \qquad (1)$$

Sau đó chặn dưới 0,05 m và ép đơn điệu tăng:

$$\hat{\sigma}_\tau = \max_{s \le \tau}\ \max\big(\tilde{\sigma}_s,\ 0{,}05\big) \qquad (2)$$

**Kết quả ước lượng.** So với $\sigma_{30} = 1{,}25$ m của A, giá trị thực nghiệm gấp 2,8 lần và tăng siêu tuyến tính theo $\tau$:

| $\tau$ | 1 | 10 | 20 | 30 |
|---|---|---|---|---|
| $\hat{\sigma}_\tau$ (m) | 0,172 | 0,627 | 1,409 | 3,484 |

Vector $\hat{\sigma}_\tau$ được **đóng băng** trước Thuật toán 1. Khối hạt giống ước lượng tách khỏi khối hiệu chỉnh và khối kiểm tra.

## 3.3. Loại chu kỳ rỗng và lấy thưa không chồng cửa sổ (sửa W1, W2)

**Loại chu kỳ rỗng.** Tập hiệu chỉnh và tập đánh giá chỉ gồm các chu kỳ có tác nhân:

$$\mathcal{C} = \big\{\, i \ :\ \mathcal{J}_i \neq \emptyset \,\big\} \qquad (3)$$

**Lấy thưa không chồng cửa sổ.** Trong mỗi lượt, hai chu kỳ liên tiếp được chọn phải cách nhau ít nhất một chân trời:

$$t_{k+1} - t_k \;\ge\; H\,T_s = 3\ \text{s} \qquad (4)$$

Nhờ (4), hai cửa sổ dự báo liên tiếp không chồng nhau, phù hợp với giả thiết A1.

## 3.4. Cận Hausdorff cho tác nhân nhiều đĩa (sửa W3)

Với tác nhân gồm các đĩa có độ dời $o_k$ dọc thân, tâm $c$ và hướng $\theta$:

$$A^{h}_{\tau} = \max_{j\in\mathcal{J}_t}\ \max_{k}\ \Big\lVert \big(\hat{c}^{\,j}_{\tau} + o_k\,u(\hat{\theta}^{\,j}_{\tau})\big) - \big(c^{\,j}_{\tau} + o_k\,u(\theta^{\,j}_{\tau})\big) \Big\rVert,\qquad u(\theta) = (\cos\theta,\ \sin\theta) \qquad (5)$$

- Với tác nhân 1 đĩa ($o = 0$), $A^h \equiv A^c$.
- Với tác nhân nhiều đĩa, (5) tính cả sai số do quay, nên $A^h \ge A^c$.

## 3.5. Đối chứng B3′: tách hiệu ứng chiếu hình học (sửa W6)

Đặt $d^{\,\text{mid},j}_\tau = D\big(\mathcal{B}(p_{t+\tau\mid t}), O^j_{t+\tau}\big)$ là khoảng cách từ xe *theo kế hoạch* đến tác nhân *thật*. Độ lệch khoảng cách được tách thành hai thành phần có dấu:

$$\hat{d}^{\,j}_\tau - d^{\,j}_\tau = \underbrace{\big(\hat{d}^{\,j}_\tau - d^{\,\text{mid},j}_\tau\big)}_{a^j_\tau\ \text{(tác nhân)}} + \underbrace{\big(d^{\,\text{mid},j}_\tau - d^{\,j}_\tau\big)}_{b^j_\tau\ \text{(xe)}} \qquad (6)$$

**B3′** hiệu chỉnh riêng từng thành phần ở mức $\alpha/2$ rồi cộng lại:

$$m^{\text{B3}'}_\tau = \Big[\hat{q}_{a}(\alpha/2) + \hat{q}_{b}(\alpha/2)\Big]\hat{\sigma}_\tau,\qquad \hat{q}_a = Q\Big(\max_{\tau,j}\tfrac{a^j_\tau}{\hat{\sigma}_\tau}\Big),\quad \hat{q}_b = Q\Big(\max_{\tau,j}\tfrac{b^j_\tau}{\hat{\sigma}_\tau}\Big) \qquad (7)$$

**Chuỗi so sánh ba bước:**

$$\text{B3}\ \xrightarrow{\ \text{chiếu hình học}\ }\ \text{B3}'\ \xrightarrow{\ \text{gộp đồng thời}\ }\ \text{ĐX-1} \qquad (8)$$

- **Bước 1 (chiếu hình học):** thay chuẩn đẳng hướng $A + E$ bằng các thành phần có dấu, chiếu lên khoảng cách.
- **Bước 2 (gộp đồng thời):** bỏ việc chia rủi ro $\alpha/2 + \alpha/2$, không còn giả định cực đại của $a$ và $b$ xảy ra cùng lúc.

## 3.6. Chứng nhận PAC hiệu chỉnh Bonferroni (sửa W5, W7)

**Bậc thống kê.** Tại lần thử $m \le M$ với $n_m$ mẫu chứng nhận mới, chọn bậc nhỏ nhất $k_m$ sao cho:

$$\mathbb{P}\big(\operatorname{Bin}(n_m,\,1-\alpha) \ge k_m\big) \;\le\; \delta_m = \frac{\delta}{M},\qquad \delta = 0{,}05,\ M = 3 \qquad (9)$$

**Quy tắc chấp nhận.** Chính sách $\pi(q_{\text{plan}})$ được chứng nhận khi:

$$\#\big\{\, i \le n_m : R_i \le q_{\text{plan}} \,\big\} \;\ge\; k_m \quad\Longleftrightarrow\quad R_{(k_m)} \le q_{\text{plan}} \qquad (10)$$

**Bảo đảm.** Xác suất chứng nhận một chính sách có độ phủ thực dưới $1-\alpha$, qua toàn bộ quy trình, không vượt $\delta$.

**Cỡ mẫu tối thiểu.** Để tồn tại $k_m \le n_m$, cần ít nhất:

$$n_{\min} = \left\lceil \frac{\ln(\delta/M)}{\ln(1-\alpha)} \right\rceil = \left\lceil \frac{\ln(0{,}05/3)}{\ln 0{,}9} \right\rceil = 39 \qquad (11)$$

Ví dụ: $n = 187$ cho $k_{\text{PAC}} = 178$, trong khi chứng nhận có điều kiện chỉ yêu cầu $k_{\text{cond}} = 170$.

**ĐX-2 khi thiếu mẫu.** Nhóm `loss` chỉ có 2–19 mẫu mỗi khối, ít hơn $n_{\min}$. Vì vậy ĐX-2 dùng **chứng nhận tổng thể** trên tỉ số chuẩn hóa theo ngưỡng của nhóm:

$$\tilde{R}_i = \frac{R_i}{q_{\text{plan}}(g_i)},\qquad \text{chứng nhận khi}\ \ \tilde{R}_{(k_m)} \le 1 \qquad (12)$$

## 3.7. ACI chỉ cập nhật trên chu kỳ có tác nhân (sửa W8)

$$\alpha_{t+1} = \begin{cases} \alpha_t + \gamma\big(\alpha - \mathbb{1}\{R_{t-H} > q_{t-H}\}\big), & \mathcal{J}_{t-H} \neq \emptyset \\[4pt] \alpha_t, & \mathcal{J}_{t-H} = \emptyset \end{cases} \qquad (13)$$

Các tham số khác giữ nguyên như A: $\gamma = 0{,}02$, cửa sổ 500 điểm số, phản hồi trễ $H$.

## 3.8. Thay đổi trong cách báo cáo (sửa W10)

**Tách độ phủ theo trạng thái chu kỳ.** Độ phủ điểm số được báo cáo riêng cho chu kỳ khả thi ($\mathcal{F}$) và chu kỳ dự phòng ($\bar{\mathcal{F}}$):

$$\widehat{\text{Cov}}_R^{\mathcal{F}} = \frac{1}{|\mathcal{F}|}\sum_{i\in\mathcal{F}} \mathbb{1}\{R_i \le q_i\},\qquad \widehat{\text{Cov}}_R^{\bar{\mathcal{F}}} = \frac{1}{|\bar{\mathcal{F}}|}\sum_{i\in\bar{\mathcal{F}}} \mathbb{1}\{R_i \le q_i\} \qquad (14)$$

**Kiểm định ghép cặp.** So sánh các phương pháp bằng McNemar (biến nhị phân) và Wilcoxon (biến liên tục), sau đó hiệu chỉnh Holm cho $K$ so sánh:

$$p^{\text{Holm}}_{(r)} = \max_{s \le r}\ \min\Big(1,\ (K - s + 1)\,p_{(s)}\Big) \qquad (15)$$

# 4. So sánh kết quả Phương án A và Phương án B

**Lưu ý khi đọc số liệu.** Hai phương án dùng $\sigma_\tau$ khác nhau, nên giá trị $q$ **không so sánh trực tiếp** được. Hãy so $m_{3\text{s}}$ (đơn vị mét) và độ phủ. Ngoài ra, độ phủ điểm số của A tính cả 17,9% mẫu rỗng (luôn phủ), còn của B chỉ tính chu kỳ có tác nhân. Vì vậy con số của A **bị thổi phồng** so với B.

## 4.1. Kết quả tổng thể

**Bảng 3. So sánh A và B** (360 lượt kiểm tra ghép cặp mỗi phương pháp)

| Phương pháp | Độ phủ điểm số A | Độ phủ điểm số B [KTC 95%] | $m_{3\text{s}}$ A → B (m) | Hoàn thành A → B | Dự phòng A → B | Va chạm A / B |
|---|---|---|---|---|---|---|
| B0 | 0,329 | 0,135 [0,116; 0,156] | 0 → 0 | 80,8% → 80,8% | 5,4% → 5,4% | 10,6% / 10,6% |
| B1 | 0,887 | 0,872 [0,853; 0,889] | 4,43 → 7,00 | 70,6% → 55,3% | 3,5% → 4,7% | 0 / 0 |
| B2 | 0,889 | 0,875 [0,857; 0,892] | 4,73 → 7,30 | 68,1% → 53,6% | 3,8% → 5,0% | 0 / 0 |
| B3 | 0,998 | 0,997 [0,992; 0,999] | 16,32 → 25,83 | 27,5% → 10,0% | 8,1% → 16,7% | 0 / 0 |
| B3′ | — | 0,990 [0,984; 0,994] | — → 15,04 | — → 30,8% | — → 7,5% | — / 0 |
| B4 | 0,900 | 0,864 [0,845; 0,880] | 19,32 → 22,42 | 16,4% → 12,8% | 11,9% → 14,7% | 0 / 0 |
| B5 | 0,848 | 0,748 [0,723; 0,771] | 3,48 → 3,56 | 76,7% → 76,7% | 3,8% → 3,7% | 0,3% / 0,3% |
| B6 | 0,926 | 0,903 [0,887; 0,918] | 7,31 → 10,77 | 62,8% → 47,5% | 5,8% → 7,9% | 0 / 0 |
| **ĐX-1** | **0,874** | **0,908 [0,892; 0,922]** | 4,02 → 8,89 | 71,4% → 46,1% | 3,6% → 5,4% | 0 / 0 |
| **ĐX-2** | **0,893** | **0,939 [0,926; 0,951]** | 4,13 → 10,31 | 71,4% → 41,9% | 4,0% → 8,3% | 0 / 0 |
| ĐX-3 | 0,904 | 0,897 [0,880; 0,913] | 8,23 → 13,06 | 60,0% → 42,5% | 7,9% → 14,5% | 0,3% / 0,3% |

**Nhận xét:**

1. **ĐX-1 và ĐX-2 về đúng mức danh định.**
   - ĐX-1: 0,874 → 0,908. KTC của B nằm trên 0,89 và chứa 0,90.
   - ĐX-2: 0,893 → 0,939.
   - Đây là kết quả trung tâm: sửa W1, W2, W4, W5 khôi phục bảo đảm (14) của Định lý 1.
2. **Cái giá là biên rộng hơn.**
   - $m_{3\text{s}}$ của ĐX-1 tăng 2,2 lần (4,02 → 8,89 m) và tỉ lệ hoàn thành giảm từ 71,4% xuống 46,1%.
   - Biên của A **nhỏ một cách sai lệch**: $\sigma_\tau$ quá thấp, cộng với phân vị bị kéo xuống bởi mẫu $-\infty$.
3. **B1, B2, B4, B6 trông như tệ đi khi sang B.** Thực ra con số của A đã được thổi phồng nhờ mẫu rỗng. Khi chỉ tính chu kỳ có tác nhân, các đối chứng "chỉ xét tác nhân" lộ ra phủ thiếu: B1 0,872, B4 0,864.
4. **B5 sụp mạnh hơn** (0,848 → 0,748). Giả định Gauss không phù hợp với đuôi nặng của phân phối thật.
5. **Độ phủ vật lý vẫn bão hòa ở cả hai phương án** (≥ 0,995) và va chạm như nhau. Thước đo an toàn vật lý không phân biệt được A với B.

## 4.2. Độ phủ điểm số theo điều kiện định vị

**Bảng 4. Độ phủ điểm số theo điều kiện, A → B**

| Phương pháp | D0 | D1 | D2 | D3 | D4 | D5 |
|---|---|---|---|---|---|---|
| B1 | 0,948 → 0,935 | 0,779 → 0,748 | 0,746 → 0,759 | 0,946 → 0,935 | 0,950 → 0,927 | 0,956 → 0,927 |
| B5 | 0,917 → 0,820 | 0,705 → **0,544** | 0,678 → **0,556** | 0,923 → 0,837 | 0,926 → 0,869 | 0,937 → 0,863 |
| B6 | 0,960 → 0,945 | 0,873 → 0,840 | 0,838 → 0,833 | 0,970 → 0,944 | 0,955 → 0,936 | 0,958 → 0,924 |
| ĐX-1 | 0,940 → 0,957 | 0,759 → **0,847** | 0,732 → **0,826** | 0,933 → 0,962 | 0,936 → 0,919 | 0,947 → 0,936 |
| ĐX-2 | 0,930 → 0,953 | 0,856 → **0,908** | 0,796 → **0,961** | 0,927 → 0,957 | 0,927 → 0,919 | 0,926 → 0,936 |
| ĐX-3 | 0,899 → 0,876 | 0,892 → 0,909 | 0,898 → 0,906 | 0,907 → 0,886 | 0,906 → 0,906 | 0,923 → 0,899 |

**Nhận xét:**

- **Ở D1 và D2, ĐX-2 của B đạt 0,908 và 0,961, cải thiện lớn nhất.** D2 tăng 16,5 điểm phần trăm nhờ ngưỡng nhóm `loss` hợp lý (mục 4.3).
- **ĐX-1 tăng khoảng 9 điểm ở D1/D2 nhưng vẫn dưới 0,90.** Một ngưỡng chung không đủ khi định vị suy giảm, nên cần ĐX-2 hoặc ACI.
- **ĐX-3 ổn định ở cả hai phương án** (0,876–0,923). Việc chuyển sang chỉ cập nhật trên chu kỳ có tác nhân (13) **không làm thay đổi đáng kể** kết quả.

## 4.3. ĐX-2 theo nhóm định vị

**Bảng 5. ĐX-2 theo nhóm định vị, A so với B**

| | fix | float | loss |
|---|---|---|---|
| Ngưỡng $q$, A | 2,862 | 4,589 | **4,424** (nhỏ hơn float) |
| $m_{3\text{s}}$ (m), A | 3,58 | 5,74 | 5,53 |
| Độ phủ, A | 0,922 | 0,856 | **0,736** |
| Ngưỡng $q$, B | 2,531 | 3,040 | 5,742 |
| $m_{3\text{s}}$ (m), B | 8,82 | 10,59 | 20,01 |
| Độ phủ, B | 0,941 | 0,908 | **0,980** |

**Nhận xét:**

- **Thứ tự biên ở B hợp lý về vật lý:** fix < float < loss. Ở A thứ tự này bị đảo (W7).
- **Chứng nhận của B:** ĐX-2 đạt PAC tổng thể (12) ở lần thử 2 với $k = 190/201$.
- **Hạn chế còn lại:** nhóm `float` ($n = 29$) và `loss` ($n = 19$) vẫn dưới $n_{\min} = 39$, nên chưa chứng nhận riêng được từng nhóm.

## 4.4. Hội tụ và chứng nhận

**Phương án A**, ĐX-1, chứng nhận có điều kiện (21 trong Báo cáo 1):

$$q:\ 3{,}865 \rightarrow 3{,}821 \rightarrow 3{,}234 \rightarrow 3{,}060;\quad q_{\text{final}} = 3{,}213 \qquad (16)$$

**Phương án B**, ĐX-1, chứng nhận PAC (9)–(10):

$$q:\ 2{,}613 \rightarrow 2{,}500 \rightarrow 2{,}016 \rightarrow 2{,}042;\quad q_{\text{final}} = 2{,}552 \qquad (17)$$

- **Lần thử 1 của B bị bác.** Với $q_{\text{plan}} = 2{,}042$ và $n = 187$:
  - ngưỡng có điều kiện là $\hat{q}_{\text{cond}} = 2{,}428$;
  - ngưỡng PAC là $\hat{q}_{\text{PAC}} = R_{(178)} = 3{,}466$.

  PAC từ chối và nâng $q$ lên 2,552 ở lần thử 2.
- **Hai phương án đều cần 2 lần thử.** Khác biệt nằm ở **mức bảo đảm**: Monte Carlo (tổng hợp, Hình H5) cho thấy tại $p_{\text{true}} = 0{,}899$:

**Bảng 6. Rủi ro chứng nhận sai** (tính toán tổng hợp, không phải lượt chạy xe)

| Chỉ số | A: có điều kiện | B: PAC Bonferroni |
|---|---|---|
| Xác suất chấp nhận sai (tối đa 3 lần thử) | **76,8%** | **1,9%** (< $\delta$ = 5%) |
| Tỉ lệ chính sách hậu chứng nhận phủ < 0,90 | 24,8% | 0,2% |

## 4.5. Đóng góp riêng của từng thay đổi

**Bảng 7. Hiệu ứng định lượng của từng sửa đổi**

| Thay đổi | Chỉ số | A | B | Ý nghĩa |
|---|---|---|---|---|
| Loại mẫu rỗng (3) | Độ phủ ĐX-1 trên chu kỳ có tác nhân | 0,847 | 0,908 | +6,1 điểm, vượt 0,90 |
| Lấy thưa 3 s (4) | $\rho_1$ của chuỗi $R$ | 0,353 | 0,152 | Giảm hơn một nửa. Ở 4 s còn 0,150, vẫn chưa bằng 0 |
| $A_h$ (5) | P90 của $A/\sigma$ | S2 1,388; S3 1,672 | S2 1,510; S3 2,005 | +8,8% và +19,9% |
| $\hat{\sigma}_\tau$ (1)–(2) | $\sigma_{30}$ | 1,25 m | 3,484 m | Gấp 2,8 lần; hình dạng siêu tuyến tính |
| B3 → B3′ (chiếu hình học) | $m_{3\text{s}}$ | 25,83 m | 15,04 m | **−41,8%** |
| B3′ → ĐX-1 (gộp) | $m_{3\text{s}}$ | 15,04 m | 8,89 m | **−40,9%** |
| B3 → ĐX-1 (tổng) | $m_{3\text{s}}$ / hoàn thành | 25,83 m / 10,0% | 8,89 m / 46,1% | −65,6%; $\Delta t_{\text{end}} = -1{,}12$ s ($p_{\text{Holm}} = 3{,}1\cdot 10^{-28}$) |
| PAC (9)–(10) | Chấp nhận sai (Monte Carlo) | 76,8% | 1,9% | Bảo đảm $\le \delta$ |
| Tách khả thi / dự phòng (14) | Độ phủ ĐX-1 | — | 0,914 / 0,767 | Chu kỳ dự phòng là nơi độ phủ yếu |

Ghi chú: phép giảm −65,6% so trong cùng Phương án B ($\hat{\sigma}_\tau$, $A_h$), không phải giữa A và B.

## 4.6. Kiểm định thống kê (Phương án B)

**Bảng 8. So sánh ĐX-2 với các đối chứng** (McNemar, Wilcoxon, hiệu chỉnh Holm)

| ĐX-2 so với | $\Delta t_{\text{end}}$ (s) | $p_{\text{Holm}}$ ($t_{\text{end}}$) | $\Delta d_{\min}$ (m) | $p_{\text{Holm}}$ (vi phạm $R > q$) |
|---|---|---|---|---|
| B1 | +0,52 | $2{,}0\cdot 10^{-32}$ | +2,76 | $4{,}0\cdot 10^{-7}$ |
| B3 | −0,94 | $6{,}3\cdot 10^{-26}$ | −14,39 | $1{,}7\cdot 10^{-20}$ |
| B3′ | −0,55 | $7{,}9\cdot 10^{-22}$ | −5,38 | $5{,}0\cdot 10^{-15}$ |
| B5 | +1,44 | $5{,}2\cdot 10^{-43}$ | +5,94 | $2{,}1\cdot 10^{-25}$ |
| B6 | +0,23 | $5\cdot 10^{-4}$ | +1,38 | $3{,}5\cdot 10^{-3}$ |

**Nhận xét:**

- **ĐX-2 nằm giữa các đối chứng:** an toàn hơn có ý nghĩa so với B1, B5, B6 (ít vi phạm hơn), và nhanh hơn có ý nghĩa so với B3, B3′.
- **Phương án A không có kiểm định này.** Đây là bổ sung về phương pháp đánh giá của B.

## 4.7. Đánh đổi an toàn – hiệu quả khi quét $\alpha$ (chỉ Phương án B)

**Bảng 9. Quét α**: độ phủ điểm số / $m_{3\text{s}}$ / hoàn thành

| $\alpha$ | B1 | B3′ | ĐX-2 |
|---|---|---|---|
| 0,01 | 0,989 / 14,45 m / 32,8% | 0,999 / 34,57 m / 3,9% | 0,995 / 16,19 m / 27,5% |
| 0,02 | 0,952 / 11,36 m / 41,9% | 0,997 / 27,78 m / 8,9% | 0,990 / 14,13 m / 34,2% |
| 0,05 | 0,911 / 8,97 m / 45,8% | 0,996 / 21,36 m / 15,6% | 0,961 / 11,74 m / 40,6% |
| 0,10 | 0,872 / 7,00 m / 55,3% | 0,990 / 15,04 m / 30,8% | 0,939 / 10,31 m / 41,9% |
| 0,20 | 0,820 / 4,91 m / 69,7% | 0,904 / 8,54 m / 48,1% | 0,799 / 4,21 m / 74,2% |

**Nhận xét:**

- **Độ phủ giảm đơn điệu theo $\alpha$** ở cả ba phương pháp, đúng như lý thuyết.
- **Ở cùng mức độ phủ khoảng 0,95, các phương pháp khá gần nhau:**
  - B1 tại $\alpha = 0{,}02$: 11,36 m;
  - ĐX-2 tại $\alpha = 0{,}05$: 11,74 m.

  Điều này báo trước rằng lợi thế "biên hẹp hơn" ở cùng $\alpha$ có thể chỉ là chọn một điểm khác trên cùng đường đánh đổi. Giai đoạn mở rộng v0.2 (thí nghiệm E1) sau đó đã xác nhận điều này.

# 5. Đánh giá tổng hợp

## 5.1. Phương án B làm được gì

1. **Khôi phục bảo đảm thống kê của Định lý 1.** Độ phủ điểm số của ĐX-1 tăng từ 0,874 lên 0,908, của ĐX-2 từ 0,893 lên 0,939. Bốn lỗi gốc W1, W2, W4, W5 đều được sửa và định lượng.
2. **Bảo đảm chứng nhận thật sự.** Chứng nhận PAC (9)–(11) hạ xác suất chấp nhận sai từ 76,8% xuống 1,9%. Lần chạy thật có một ví dụ PAC từ chối đúng lúc.
3. **Chứng minh được nguồn lợi ích của biên gộp.** B3′ tách rõ hai hiệu ứng: −41,8% nhờ chiếu hình học và −40,9% nhờ gộp đồng thời.
4. **ĐX-2 xử lý được mất GNSS.** Thứ tự ngưỡng nhóm hợp lý; độ phủ D2 tăng từ 0,796 lên 0,961.
5. **Báo cáo minh bạch hơn.** Có độ phủ điểm số kèm KTC, tách khả thi / dự phòng, kiểm định ghép cặp với hiệu chỉnh Holm và quét $\alpha$.

## 5.2. Phương án B chưa giải quyết được gì

**Bảng 10. Hạn chế còn lại của Phương án B**

| # | Hạn chế | Ghi chú |
|---|---|---|
| H1 | Biên rộng hơn nhiều, hiệu quả giảm | Hoàn thành của ĐX-1 giảm từ 71,4% xuống 46,1%. Đây là cái giá đúng của bảo đảm, nhưng cần trình bày trung thực |
| H2 | So sánh vẫn ở cùng $\alpha$, chưa ở cùng độ phủ | Quét $\alpha$ (Bảng 9) cho thấy B1 và ĐX-2 gần nhau ở cùng độ phủ |
| H3 | Nhóm `float` và `loss` vẫn dưới $n_{\min} = 39$ mỗi khối | Chỉ chứng nhận PAC tổng thể; cần khối D2 riêng khoảng 130–150 lượt |
| H4 | $\rho_1 = 0{,}152$ vẫn khác 0 | Giả thiết A1 chỉ gần đúng |
| H5 | $E_\tau$ vẫn trộn sai số bám với độ lệch do lập lại kế hoạch (W9) | Chưa có nhánh mở vòng |
| H6 | ACI chỉ chạy một cấu hình, $\gamma = 0{,}02$ | Hiệu ứng của (13) chưa được ablation |
| H7 | Độ phủ vật lý vẫn bão hòa; chỉ thử trong phân phối; 15 hạt giống mỗi ô | Giới hạn G1–G6 của môi trường (Báo cáo 1) giữ nguyên |
| H8 | ĐX-1 ở D1/D2 vẫn dưới 0,90 (0,847 / 0,826) | Ngưỡng chung không đủ khi định vị suy giảm |

Báo cáo v0.1 kết luận "Phương án B khắc phục **toàn bộ** sai lệch". Kết luận này **chỉ đúng trong phân phối** và cho các sai lệch W1–W8. Các hạn chế H1–H8 là cơ sở của giai đoạn mở rộng v0.2.

## 5.3. Kết luận

1. **Phương án A chỉ đạt yêu cầu khi nhìn bằng thước đo của bản thảo** (độ phủ vật lý bão hòa ở 1,000). Thực chất A vi phạm bảo đảm mà nó tuyên bố: ĐX-1 phủ 0,847 trên chu kỳ có tác nhân, và chứng nhận có rủi ro chấp nhận sai 76,8%.
2. **Phương án B sửa trực tiếp từng điểm yếu W1–W8 và W10 bằng các thay đổi (1)–(15).** Các thay đổi này khôi phục độ phủ danh định (ĐX-1 0,908; ĐX-2 0,939) và bảo đảm PAC thật sự. Đổi lại, biên rộng hơn khoảng 2,2–2,5 lần.
3. **Các sửa đổi cần đưa vào bản thảo:**
   - ước lượng $\hat{\sigma}_\tau$;
   - loại chu kỳ rỗng;
   - lấy thưa $\Delta = H$;
   - cận Hausdorff $A_h$;
   - chứng nhận PAC Bonferroni;
   - đối chứng B3′;
   - ACI chỉ cập nhật trên chu kỳ có tác nhân;
   - báo cáo độ phủ điểm số, tách khả thi / dự phòng.
4. **ĐX-2 là đề xuất có cơ sở mạnh nhất cho điều kiện định vị suy giảm.** Nhưng cần đủ mẫu mỗi nhóm và nhãn định vị đáng tin.
