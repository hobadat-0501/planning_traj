# Thư viện Mô phỏng `sim/`

Gói `sim/` cài đặt đầy đủ lõi mô phỏng vòng kín 2D (hỗ trợ cả `S1–S4 × D0–D5` v0.1 lẫn mở rộng `S5–S10 × D6–D10`, đường cong Frenet, che khuất, nhánh mở vòng `E_track`), bộ chạy phương án cũ (`run_old.py`), phương án mới (`run_new.py`), bộ chạy OOD/RECAL (`run_ext.py`), thí nghiệm `E1–E9` (`experiments_ext.py`), phân tích – vẽ hình (`analyze.py`, `analyze_ext.py`) và sinh báo cáo tự động (`report.py`, `report_ext.py`).

## Chạy lại từ đầu

Từ thư mục gốc chứa `run_all.py` và `run_ext.py`:

```bash
python -m pytest
python run_all.py --seed-base 0
python run_ext.py --seed-base 0
```

Mọi hạt giống đều được cố định theo `seed_base` nên chạy lại cho kết quả tất định (`< 1e-9`), bảo toàn hoàn toàn `logs/old/` và `logs/new/` khi chạy mở rộng v0.2.
