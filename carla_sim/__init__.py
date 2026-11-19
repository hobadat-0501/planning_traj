"""Gói chuyển mô phỏng phương án B sang CARLA (PLAN §9, TASKS T15–T21).

Nguyên tắc: chỉ thay phần đầu vào (xe, tác nhân, nhận diện, dự báo); toàn bộ mã tính
biên (điểm số, hiệu chỉnh, PAC, ACI) dùng lại nguyên vẹn từ gói `sim/`.

Mọi module đều import `carla` theo kiểu trễ (lazy) để có thể đọc/kiểm tra mã khi máy
chưa cài CARLA.
"""

__all__ = [
    "config",
    "frames",
    "infra",
    "control",
    "agents",
    "perception",
    "episode",
    "params",
    "runner",
    "report_carla",
]
