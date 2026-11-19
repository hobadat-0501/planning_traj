# Báo cáo Phần 1 — CARLA (T28–T31), trạng thái mã và kiểm tra ngoại tuyến

Ngày 19/11/2026. **Chưa có kết quả nào trên CARLA thật**: máy này không cài CARLA, và PLAN §11 còn ghi "đề xuất, chưa duyệt". Mã được viết trước và kiểm tra trên backend giả (xe đạp động học có trễ bậc nhất), để khi có máy CARLA chỉ cần thay backend.

## 1. Đã làm (mã trong `ws/av_conformal/`)

| Khối | Tệp | Trạng thái |
|---|---|---|
| Cấu hình | `configs/*.yaml` | xong; nhiều giá trị ghi TẠM (tham số xe, noise, S3/S4, D3, D5) |
| Quy đổi tọa độ | `carla_env/coords.py` | xong, test khứ hồi < 1e-6 (C1-c, phần số học) |
| Thế giới đồng bộ | `carla_env/world.py` | viết, **chưa chạy** |
| Xe tự hành | `carla_env/ego.py` | viết, **chưa chạy**; công thức `rear_overhang` cần kiểm tra bằng tay |
| Backend CARLA | `carla_env/backend.py` | viết, **chưa chạy**; chọn tuyến thẳng tự động chỉ là TẠM |
| Backend giả | `carla_env/fake.py` | xong, dùng cho test |
| Kịch bản S1–S4 | `carla_env/scenarios.py` | động học tác nhân test được, cùng hạt giống cho cùng quỹ đạo (C4, phần số học); lớp CARLA chưa chạy |
| Bộ chuyển lệnh, bộ bám, planner, nhiễu, dự báo, bộ đánh giá, hiệu chỉnh, logger | `av_core/*` | xong, có test |
| Chạy một lượt, chạy hàng loạt | `scripts/sim_runner.py`, `scripts/batch.py` | xong; batch có `--shard`, bỏ qua lượt đã xong, bắt lỗi từng lượt |

## 2. Kiểm tra đã chạy (máy này)

`python -m pytest tests/test_av_conformal.py` → **16 test đạt**. Bao gồm: C1-c khứ hồi tọa độ và chiều quay; hình học đa giác; C6-a (kế hoạch trùng thật → R = 0; tác nhân tiến gần 0,5 m → R = 0,5 với σ = 1); thứ tự σ giữa fixed/float, dead-reckoning tăng, D2 có mất GNSS; trễ lệnh 0,2 s = 4 bước; planner trên đường trống và khi bị chắn; ADE = 0 với chuyển động thẳng; C4 tái lập hạt giống; một lượt đầy đủ ghi log; lượt lặp cùng hạt giống cho cùng kết quả; batch bỏ qua và chia mảnh; lượt lỗi được đánh dấu `error`.

Chạy khói trên backend giả, B0, hạt giống 0, S×D (24/24 ô, 0 lỗi): 15 goal, 3 collision (S1 ở D1, D4, D5, do B0 không nới biên, đúng hướng kỳ vọng), 6 timeout (cả 6 ô S4: xe tự hành chạy chậm sau xe dẫn phanh, chưa tới đích trong 40 s). Log đủ cột (`cycles`, `steps`, `meta`).

## 3. Chưa đạt hoặc chưa làm

- **Tốc độ planner**: đã tối ưu (kiểm tra an toàn theo lô, dựng quỹ đạo vector hóa theo lô, bộ đánh giá vector hóa). Kết quả mô phỏng không đổi (24 ô khói: 15 goal, 3 collision, 6 timeout). Thời gian một chu kỳ, gồm cả bộ đánh giá: trung vị ~10 ms; P95 theo lượt có trung vị 39 ms, lớn nhất 133 ms; 2/24 lượt có P95 > 0,1 s (lượt bị chắn). Ban đầu là 438 ms và 1464 ms. Số đo trên máy này với backend giả; trên máy CARLA sẽ khác.
- Mọi phần chạy-thật: C1-a/b, C2 sáu phép thử và Bảng 3, C3 đồ thị, C4 video, C5 (Trajectron++ và ADE so sánh), chạy B0 hạt giống 0–249.
- Tham số xe trong `tesla_model3.yaml` là TẠM cho tới khi có nhận dạng C2.
- T32–T37 (phương án A, B): chưa làm; phụ thuộc dữ liệu B0 thật.

## 4. Cần từ bạn

1. Duyệt (hoặc từ chối) §11 để tiến hành chính thức.
2. Địa chỉ, cổng RPC, cổng Traffic Manager, hệ điều hành của máy CARLA; chốt C6 (chạy mã khách ở đâu).
3. Duyệt S3, S4 tự thiết kế (C8).
