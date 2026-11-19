"""Cấu hình chung cho chạy CARLA (T15, T18).

Các hằng số động lực học lấy từ `sim.core` để bảo đảm khớp mô phỏng 2D.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sim.core import BASE_DELAY, DELTA_MAX, DT_PLAN, DT_SIM, V_MAX, WHEELBASE

# Mức đầu vào (PLAN §9.1)
LEVELS: tuple[str, ...] = ("M1", "M2", "M3")

# Blueprint mặc định
EGO_BLUEPRINT: str = "vehicle.tesla.model3"
PED_BLUEPRINTS: tuple[str, ...] = ("walker.pedestrian.0001", "walker.pedestrian.0005", "walker.pedestrian.0012")
MOTO_BLUEPRINTS: tuple[str, ...] = ("vehicle.yamaha.yzf", "vehicle.kawasaki.ninja", "vehicle.harley-davidson.low_rider")
CAR_BLUEPRINTS: tuple[str, ...] = ("vehicle.audi.a2", "vehicle.toyota.prius", "vehicle.nissan.micra")


@dataclass
class CarlaConfig:
    """Tham số kết nối, đồng bộ và xe cho một phiên CARLA."""

    # Kết nối
    host: str = "127.0.0.1"
    port: int = 2000
    tm_port: int = 8000
    timeout_s: float = 20.0
    town: str = "Town04"            # Có đoạn đường thẳng dài, làn ~3,5 m
    reload_world: bool = False

    # Đồng bộ (T15): dt 0,05 s, lập kế hoạch 10 Hz
    dt_sim: float = DT_SIM
    dt_plan: float = DT_PLAN
    no_rendering: bool = True
    max_substep_delta: float = 0.01
    max_substeps: int = 10

    # Xe (T15)
    ego_blueprint: str = EGO_BLUEPRINT
    wheelbase_target: float = WHEELBASE
    v_max: float = V_MAX
    delta_max_rad: float = DELTA_MAX

    # Trễ lệnh: CARLA có trễ chấp hành thật; chỉ mô phỏng thêm phần trễ nền còn thiếu.
    # Sau khi đo ở T15, đặt emulated_base_delay = max(0, BASE_DELAY - trễ đo được).
    emulated_base_delay: float = BASE_DELAY
    measured_latency_ms: float | None = None

    # Đường thẳng thử nghiệm: chọn điểm xuất phát có >= straight_len_m đường thẳng
    spawn_index: int | None = None
    straight_len_m: float = 95.0
    straight_yaw_tol_deg: float = 2.0
    # Hành lang thử nghiệm: kịch bản 2D giả định 2 bên đường trống (vỉa hè, nhánh giao cắt).
    # Ẩn rào/hộ lan/cột/cây... trong hành lang |y| <= corridor_half_width để tác nhân không đi xuyên;
    # tác nhân (chế độ replay) ở ngoài hành lang được giấu dưới mặt đất cho tới khi đi vào.
    corridor_half_width: float = 15.0
    clear_corridor: bool = True

    # Tác nhân: "replay" = điều khiển động học theo mã 2D rồi đặt tư thế vào CARLA (tái lập cao);
    #           "physics" = tác nhân là actor vật lý bám theo hành vi kịch bản (walker control / PID xe).
    agent_mode: str = "replay"

    # Mức đầu vào và bộ dự báo
    level: str = "M1"
    predictor: str = "cv"            # "cv" | "trajectron" | "learned"
    predictor_model_dir: str | None = None
    perception: str = "gt_noise"     # "gt_noise" (M1/M2) | "lidar" (M3)

    # Mô phỏng sai số điều kiện D3/D9 trên CARLA
    d9_tire_friction_scale: float = 0.45
    d3_steer_noise_sigma: float = 0.02

    # Đo E_track bằng nhánh mở vòng theo mô hình 2D (xấp xỉ trên CARLA)
    compute_open_loop: bool = False

    # Hiển thị (lệnh `demo`): không ảnh hưởng kết quả mô phỏng
    realtime: bool = False           # Chờ cho mỗi tick kéo dài đúng dt_sim thời gian thực
    camera: str = "none"             # "none" | "chase" (sau lưng xe) | "top" (nhìn từ trên xuống)
    debug_draw: bool = False         # Vẽ khung quanh xe tự hành (xanh) và tác nhân (đỏ)
    status_every_s: float = 0.0      # > 0: in tốc độ/ga/phanh/lái của xe mỗi chừng ấy giây

    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def plan_every(self) -> int:
        return int(round(self.dt_plan / self.dt_sim))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> "CarlaConfig":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def level_defaults(self) -> "CarlaConfig":
        """Đặt bộ dự báo / nhận diện mặc định theo mức M1/M2/M3 (PLAN §9.1)."""
        if self.level not in LEVELS:
            raise ValueError(f"Mức không hợp lệ: {self.level}")
        if self.level == "M1":
            self.predictor, self.perception = "cv", "gt_noise"
        elif self.level == "M2":
            if self.predictor == "cv":
                self.predictor = "trajectron"
            self.perception = "gt_noise"
        else:
            if self.predictor == "cv":
                self.predictor = "trajectron"
            self.perception = "lidar"
        return self
