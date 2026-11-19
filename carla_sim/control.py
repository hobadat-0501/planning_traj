"""Cầu nối điều khiển (T16): (v_cmd, delta_cmd) của Pure Pursuit -> `carla.VehicleControl`.

- `LongitudinalPID`: vận tốc -> ga/phanh chuẩn hóa [0, 1].
- `VehicleControlBridge`: gói Pure Pursuit + bộ đệm trễ (nền + D4/D5/D6) + PID + ánh xạ lái
  (đảo dấu tay phải -> tay trái CARLA), kèm sai số hệ số lái ±5% và nhiễu lái D3/D9.

Không import `carla` ở cấp module để chạy được với `FakeCarlaSession`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from carla_sim.config import CarlaConfig
from sim.conditions_ext import get_plant_dynamics_params
from sim.core import (
    A_MAX,
    A_MIN,
    DELTA_MAX,
    DT_SIM,
    KP_V,
    OMEGA_MAX,
    TAU_STEER,
    V_MAX,
    CommandDelayBuffer,
    PlanResult,
    pure_pursuit_control,
)


@dataclass
class LongitudinalPID:
    """PI vận tốc -> gia tốc mong muốn -> ga/phanh.

    a_des = kp (v_t - v) + ki ∫e, cắt trong [a_min, a_max] của điều kiện (D9: [-3, 2]).
    throttle = a_des / a_throttle_full; brake = -a_des / a_brake_full (a_brake_full = |A_MIN| = 6 m/s²,
    nên D9 có brake tối đa 0,5). Hai hệ số "full" cần chỉnh lại theo phép đo T15.
    """

    kp: float = KP_V
    ki: float = 0.3
    a_min: float = A_MIN
    a_max: float = A_MAX
    a_throttle_full: float = 4.0
    a_brake_full: float = abs(A_MIN)
    v_max: float = V_MAX
    coast_band: float = 0.05
    integ_lim: float = 2.0
    integ: float = 0.0
    last_a_des: float = 0.0

    def reset(self) -> None:
        self.integ = 0.0
        self.last_a_des = 0.0

    def step(self, v_target: float, v_current: float, dt: float = DT_SIM) -> tuple[float, float]:
        v_t = float(np.clip(v_target, 0.0, self.v_max))
        err = v_t - float(v_current)
        self.integ = float(np.clip(self.integ + err * dt, -self.integ_lim, self.integ_lim))
        a_des = float(np.clip(self.kp * err + self.ki * self.integ, self.a_min, self.a_max))
        self.last_a_des = a_des
        if v_t < 0.05 and v_current < 0.3:
            # Giữ xe đứng yên với lực phanh tối đa cho phép của điều kiện
            return 0.0, float(np.clip(abs(self.a_min) / self.a_brake_full, 0.0, 1.0))
        if a_des > self.coast_band:
            return float(np.clip(a_des / self.a_throttle_full, 0.0, 1.0)), 0.0
        if a_des < -self.coast_band:
            return 0.0, float(np.clip(-a_des / self.a_brake_full, 0.0, 1.0))
        return 0.0, 0.0


class VehicleControlBridge:
    """Tính lệnh điều khiển 20 Hz cho xe tự hành trên CARLA (hoặc FakeCarlaSession)."""

    def __init__(self, cfg: CarlaConfig, condition: str, rng: np.random.Generator) -> None:
        self.cfg = cfg
        self.condition = condition
        self.rng = rng
        dyn = get_plant_dynamics_params(condition)
        self.pid = LongitudinalPID(a_min=float(dyn["a_min"]), a_max=float(dyn["a_max"]), v_max=cfg.v_max)
        self.delay_buf = CommandDelayBuffer(cfg.emulated_base_delay)
        # Sai số hệ số lái ±5% mỗi lượt (giống EgoPlant); rút từ rng riêng để không làm lệch rng_ego
        sub = np.random.default_rng(int(rng.integers(0, 2**31 - 1)))
        self.steer_gain_err = float(sub.uniform(0.95, 1.05))
        self.noise_rng = sub
        if condition == "D3":
            self.steer_noise_sigma = float(cfg.d3_steer_noise_sigma)
        elif condition == "D9":
            self.steer_noise_sigma = 2.0 * float(cfg.d3_steer_noise_sigma)
        else:
            self.steer_noise_sigma = 0.0
        self._noise = 0.0
        # Ước lượng góc lái hiệu dụng (bậc nhất + giới hạn tốc độ đánh lái) để đưa vào x_est
        self.delta_eff = 0.0

    def compute_control_dict(
        self,
        x_est: np.ndarray,
        plan: PlanResult,
        t: float,
        t_rel: float,
        extra_delay: float = 0.0,
        v_true: float = 0.0,
        dt: float = DT_SIM,
    ) -> dict[str, Any]:
        """Trả về dict gồm lệnh gốc, lệnh sau trễ, góc lái hiệu dụng và (throttle, steer, brake)."""
        v_cmd, d_cmd = pure_pursuit_control(x_est, plan, t_rel)
        self.delay_buf.push(t, v_cmd, d_cmd)
        v_del, d_del = self.delay_buf.get_delayed(t, extra_delay)

        # Góc lái hiệu dụng (cùng mô hình trễ lái của EgoPlant)
        d_dot = float(np.clip((d_del - self.delta_eff) / TAU_STEER, -OMEGA_MAX, OMEGA_MAX))
        self.delta_eff = float(np.clip(self.delta_eff + d_dot * dt, -DELTA_MAX, DELTA_MAX))

        # Nhiễu lái AR(1) cho D3/D9 (CARLA không có trượt ngang tham số hóa như 2D)
        if self.steer_noise_sigma > 0.0:
            rho = math.exp(-dt / 1.0)
            self._noise = rho * self._noise + math.sqrt(1.0 - rho**2) * self.steer_noise_sigma * float(
                self.noise_rng.standard_normal()
            )
        delta_applied = self.steer_gain_err * d_del + self._noise
        steer = float(np.clip(-delta_applied / self.cfg.delta_max_rad, -1.0, 1.0))  # tay trái: dương = rẽ phải

        throttle, brake = self.pid.step(v_del, v_true, dt)
        return {
            "v_cmd": float(v_cmd),
            "delta_cmd": float(d_cmd),
            "v_del": float(v_del),
            "delta_del": float(d_del),
            "delta_eff": float(self.delta_eff),
            "a_des": float(self.pid.last_a_des),
            "throttle": float(throttle),
            "steer": steer,
            "brake": float(brake),
        }

    @staticmethod
    def to_carla_control(ctrl: dict[str, Any]):
        import carla  # noqa: PLC0415

        return carla.VehicleControl(
            throttle=float(ctrl["throttle"]),
            steer=float(ctrl["steer"]),
            brake=float(ctrl["brake"]),
            hand_brake=False,
            reverse=False,
            manual_gear_shift=False,
        )
