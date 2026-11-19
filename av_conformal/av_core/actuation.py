"""Bộ chuyển lệnh (v_cmd, delta_cmd) -> (throttle, steer, brake), có bộ đệm trễ cho D4/D5 (hướng dẫn §2.3).

Không import carla: trả về `Control`; lớp carla_env.ego đổi sang carla.VehicleControl."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class Control:
    throttle: float = 0.0
    steer: float = 0.0
    brake: float = 0.0


class TeslaActuator:
    def __init__(self, p, dt=0.05, delay_s=0.0):
        self.kp, self.ki, self.dt = p["kp_v"], p["ki_v"], dt
        self.steer_gain = p["steer_gain"]
        self.base_delay = float(p.get("cmd_delay", 0.0))
        self.i = 0.0
        self.hist = deque(maxlen=400)       # lịch sử lệnh (v_cmd, d_cmd), mới nhất ở cuối
        self.n = self._steps(delay_s)

    def _steps(self, delay_s):
        return int(round((self.base_delay + max(delay_s, 0.0)) / self.dt))

    def set_delay(self, delay_s):
        """Trễ thêm (D4/D5), cộng với trễ nền cmd_delay. Giữ nguyên lịch sử lệnh."""
        self.n = min(self._steps(delay_s), self.hist.maxlen - 1)

    def __call__(self, v_meas, v_cmd, d_cmd):
        self.hist.append((float(v_cmd), float(d_cmd)))
        idx = max(0, len(self.hist) - 1 - self.n)
        v_ref, d_ref = self.hist[idx]
        e = v_ref - v_meas
        self.i = float(np.clip(self.i + e * self.dt, -5, 5))
        u = self.kp * e + self.ki * self.i
        if u >= 0:
            thr, brk = float(np.clip(u, 0, 1)), 0.0
        else:
            thr, brk = 0.0, float(np.clip(-u, 0, 1))
        if v_ref < 0.05 and v_meas < 0.3:
            thr, brk = 0.0, 1.0
        steer = float(np.clip(self.steer_gain * d_ref, -1, 1))
        return Control(thr, steer, brk)
