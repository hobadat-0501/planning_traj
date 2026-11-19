# Mô phỏng Vòng kín 2D — Phương án Cũ (A), Phương án Mới (B) & Mở rộng v0.2

Mã nguồn mô phỏng Python thuần kiểm chứng và so sánh phương pháp **biên an toàn phù hợp có xét sai số của xe tự hành** theo đặc tả tại `.claude/spec/SPEC.md` (v0.1 và mở rộng v0.2) cho bản thảo *Biên an toàn phù hợp có xét sai số của xe tự hành cho lập kế hoạch chuyển động xe lái kiểu Ackermann trong môi trường có tác nhân động*.

## 1. Cấu trúc thư mục

```text
ws/
├── run_all.py               # Chạy toàn bộ quy trình v0.1 (A vs B, H1–H6, báo cáo v0.1)
├── run_ext.py               # Chạy giai đoạn mở rộng v0.2 (OOD, RECAL, E1–E9, H7–H11, báo cáo v0.2)
├── run_carla.py             # CLI chuyển Phương án B sang CARLA (G13–G19: env, latency, smoke, bench, params, run, report)
├── pytest.ini               # Cấu hình pytest (testpaths = tests)
├── README.md                # Tài liệu hướng dẫn này
├── carla_sim/               # Gói cầu nối CARLA (T15–T21, lazy import carla, tái sử dụng lõi sim/)
│   ├── config.py            # Cấu hình kết nối, đồng bộ, xe, mức M1/M2/M3
│   ├── frames.py            # Biến đổi tọa độ CARLA (tay trái) <-> cục bộ 2D (tay phải)
│   ├── infra.py             # Hạ tầng CARLA synchronous mode, tìm đường thẳng, đo trễ chấp hành (T15)
│   ├── control.py           # Cầu nối Pure Pursuit + trễ lệnh + PID dọc -> VehicleControl (T16)
│   ├── agents.py            # Tác nhân S1–S4 (chế độ replay / physics) trên CARLA (T17)
│   ├── perception.py        # M1 (GT+nhiễu+CV), M2 (Trajectron++/CTRA), M3 (LiDAR tracker) (T19–T20)
│   ├── episode.py           # Chạy 1 lượt CARLA + FakeCarlaSession để kiểm thử ngoại tuyến (T16–T17)
│   ├── params.py            # Chốt Bảng §4.2, cỡ mẫu PAC theo E3, lưới vận tốc (T18)
│   ├── runner.py            # Chạy M1/M2/M3 Phương án B có checkpoint & kiểm tra hoán đổi (T19–T20)
│   └── report_carla.py      # Hình H12–H13 và báo cáo CARLA so với 2D (T21)
├── sim/
│   ├── __init__.py
│   ├── core.py              # Lõi mô phỏng 2D dùng chung (hỗ trợ S1–S10, D0–D10, Frenet đường cong, nhánh mở vòng E_track)
│   ├── scenarios_ext.py     # Kịch bản mở rộng S5–S10, đường cong C1, vật cản che khuất S5
│   ├── conditions_ext.py    # Điều kiện suy giảm mở rộng D6–D10
│   ├── common.py            # Hiệu chỉnh phù hợp, PAC, ACI, Clopper–Pearson, ghi log v0.1 & v0.2
│   ├── run_old.py           # Phương án A (cũ — bản thảo v0.1)
│   ├── run_new.py           # Phương án B (mới — đầy đủ các sửa đổi)
│   ├── run_ext.py           # Chạy các tập phân phối IN, OOD-S, OOD-D, OOD-SD và RECAL
│   ├── experiments_ext.py   # Chín thí nghiệm bổ sung E1–E9
│   ├── analyze.py           # Kiểm định McNemar/Wilcoxon/Holm và vẽ 6 hình H1–H6 (v0.1)
│   ├── analyze_ext.py       # Kiểm định OOD và vẽ 5 hình H7–H11 (v0.2)
│   ├── report.py            # Sinh báo cáo v0.1 (.md và .docx)
│   ├── report_ext.py        # Sinh báo cáo mở rộng v0.2 (.md và .docx)
│   └── README.md            # Hướng dẫn tóm tắt trong gói sim/
├── tests/                   # Bộ kiểm thử tự động TC-01..TC-18 (pytest)
├── logs/
│   ├── old/                 # 5 file log Phương án A (v0.1)
│   ├── new/                 # 6 file log Phương án B (v0.1)
│   └── ext/                 # Toàn bộ log mở rộng v0.2 (OOD, RECAL, E1–E9, tests.txt)
├── figs/                    # 11 hình H1–H11 (PNG 300 dpi + PDF vector) và analysis*.json
└── report/                  # Báo cáo v0.1 và báo cáo mở rộng v0.2 (.md và .docx)
```

## 2. Yêu cầu môi trường

- Python >= 3.10 (đã kiểm chứng trên Python 3.13.2)
- Thư viện: `numpy`, `scipy`, `pandas`, `matplotlib`, `python-docx`, `pytest`

## 3. Lệnh chạy lại toàn bộ thí nghiệm

Từ thư mục gốc `ws/`:

1. Chạy bộ kiểm thử tự động (`TC-01..TC-18`):
```bash
python -m pytest
```

2. Chạy lại mô phỏng v0.1 (`logs/old/`, `logs/new/`, `H1–H6`, báo cáo v0.1):
```bash
python run_all.py --seed-base 0
```

3. Chạy lại toàn bộ mở rộng v0.2 (`logs/ext/`, `H7–H11`, báo cáo v0.2):
```bash
python run_ext.py --seed-base 0
```

4. Quy trình chuyển sang CARLA (PLAN §9, TASKS T15–T21):
```bash
python run_carla.py env                                   # Kiểm tra Python, gói carla và GPU (T15)
python run_carla.py latency --host 127.0.0.1 --port 2000  # Đo trễ chấp hành thực của CARLA (T15)
python run_carla.py smoke --backend carla                 # Kiểm tra cầu nối S1+D0 (T16)
python run_carla.py bench --backend carla                 # Kiểm tra S×D và P95 < 100 ms (T17)
python run_carla.py params --out logs/carla_params        # Xuất bảng tham số §4.2 (T18)
python run_carla.py run --level M1 --backend carla        # Chạy M1 (thay M2/M3 cho T20)
python run_carla.py report                                # Sinh hình H12–H13 và report/BAO_CAO_CARLA.md (T21)
```
*(Có thể dùng `--backend fake` để chạy thử ngoại tuyến không cần CARLA server.)*

Các tùy chọn bổ sung cho `run_all.py` và `run_ext.py`:
- `--workers N`: số tiến trình song song.
- `--alpha 0.1`: mức rủi ro danh định (mặc định `0.1`).
- `--skip-sim`: bỏ qua mô phỏng, chỉ chạy lại phân tích thống kê, vẽ hình và sinh báo cáo từ `logs/` hiện có (`run_ext.py` hỗ trợ thêm `--skip-ood`).

## 4. Khác biệt chính giữa Phương án A (cũ) và Phương án B (mới)

| Hạng mục | Phương án A (cũ — v0.1) | Phương án B (mới) |
|---|---|---|
| Chu kỳ không có tác nhân ($\mathcal{J}_t = \emptyset$) | Giữ lại, gán $R = -\infty$ | Loại bỏ khỏi hiệu chỉnh, đánh giá và ACI |
| Lấy mẫu thưa | Mỗi $2{,}0\text{ s}$ (cửa sổ $3\text{ s}$ chồng nhau) | Mỗi $3{,}0\text{ s}$ (không chồng cửa sổ) |
| Chuẩn hóa $\sigma_\tau$ | Cố định $0{,}05 + 0{,}04\tau$ | Phân vị $90\%$ trên hạt giống `200–249`, đơn điệu tăng, cận dưới $0{,}05\text{ m}$ |
| Sai số tác nhân (B1, B3, B6) | Độ dời tâm $A_c$ | Cận Hausdorff $A_h$ (tính cả góc quay đĩa) |
| Chứng nhận (Định lý 2) | Có điều kiện ($\hat{q} \le q_{\text{plan}}$), tối đa 3 lần | PAC Bonferroni ($\mathbb{P}(\text{Bin}(n, 1-\alpha) \ge k) \le 0{,}05/3$) |
| Đối chứng | B0–B6, ĐX-1/2/3 | Bổ sung `B3′` (phân tách có dấu $a + b$) |
| Chu kỳ dự phòng | Gộp chung | Báo cáo riêng khả thi / dự phòng |
| Quét $\alpha$ | Không | $\alpha \in \{0{,}01; 0{,}02; 0{,}05; 0{,}10; 0{,}20\}$ cho `B1`, `B3′`, `ĐX-2` |
