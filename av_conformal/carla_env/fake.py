"""Backend giả (không cần CARLA): xe đạp động học có trễ bậc nhất. Dùng để test và chạy khói ở máy này.

Giao diện backend (dùng chung với CarlaBackend): dt, ego_state(), apply(ctrl), tick(), sync_agents(agents), close()."""
from __future__ import annotations

import numpy as np


class FakeBackend:
    def __init__(self, vehicle, route, dt=0.05, seed=0, lag_v=0.15, lag_d=0.1):
        self.veh, self.dt = vehicle, dt
        x, y, psi = route.start_pose()
        self.x, self.y, self.psi = x, y, psi        # tại tâm cầu sau
        self.v, self.delta = 0.0, 0.0
        self.a = 0.0
        self.ctrl = None
        self.lag_v, self.lag_d = lag_v, lag_d
        self.frame = 0
        self.closed = False

    def ego_state(self):
        return np.array([self.x, self.y, self.psi, self.v, self.delta])

    def apply(self, ctrl):
        self.ctrl = ctrl

    def tick(self):
        c, p, dt = self.ctrl, self.veh, self.dt
        if c is not None:
            a_cmd = c.throttle * p["a_max"] + c.brake * p["a_min"]
            d_cmd = float(np.clip(np.clip(c.steer, -1, 1) / p["steer_gain"], -p["delta_max"], p["delta_max"]))
        else:
            a_cmd, d_cmd = 0.0, 0.0
        self.a += (a_cmd - self.a) * min(1.0, dt / self.lag_v)
        self.delta += (d_cmd - self.delta) * min(1.0, dt / self.lag_d)
        self.v = max(0.0, self.v + self.a * dt)
        self.x += self.v * np.cos(self.psi) * dt
        self.y += self.v * np.sin(self.psi) * dt
        self.psi += self.v / p["L"] * np.tan(self.delta) * dt
        self.frame += 1
        return self.frame

    def sync_agents(self, agents):
        pass

    def close(self):
        self.closed = True
