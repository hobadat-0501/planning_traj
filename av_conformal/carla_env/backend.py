"""Backend CARLA thật cho sim_runner (cùng giao diện với FakeBackend).

Chưa chạy kiểm chứng ở máy này (không có CARLA). Chạy ở máy có CARLA 0.9.15 và gói `carla`."""
from __future__ import annotations

import math

import numpy as np

from .coords import from_carla_xyz_yaw
from .ego import read_state, spawn_tesla, to_vehicle_control, vehicle_params
from .scenarios import Route
from .world import SimWorld


def route_from_carla(sim, length=120.0, step=2.0, max_yaw_change_deg=10.0):
    """Chọn tuyến gần thẳng dài `length` m: duyệt các điểm sinh theo thứ tự cố định (tất định).
    TẠM: NCS nên chọn tuyến có vạch người đi bộ (hướng dẫn §4.3 `route`)."""
    m = sim.world.get_map()
    for sp in sorted(m.get_spawn_points(), key=lambda t: (round(t.location.x, 1), round(t.location.y, 1))):
        wp = m.get_waypoint(sp.location)
        chain = [wp]
        while len(chain) * step < length:
            nxt = chain[-1].next(step)
            if len(nxt) != 1:    # ngã rẽ: bỏ
                break
            chain.append(nxt[0])
        if len(chain) * step < length:
            continue
        yaws = np.array([w.transform.rotation.yaw for w in chain])
        if np.max(np.abs((yaws - yaws[0] + 180) % 360 - 180)) > max_yaw_change_deg:
            continue
        xy = np.array([[w.transform.location.x, -w.transform.location.y] for w in chain])
        return Route(xy)
    raise RuntimeError("không tìm được tuyến thẳng đủ dài trên bản đồ")


class CarlaBackend:
    def __init__(self, vehicle, host, port, tm_port, town, dt, seed, route_length=120.0, no_rendering=True):
        self.veh, self.dt = vehicle, dt
        self.sim = SimWorld(host, port, tm_port, town, dt, seed, no_rendering)
        try:
            self.route = route_from_carla(self.sim, route_length)
            x, y, psi = self.route.start_pose()
            carla = self.sim.carla
            tf = carla.Transform(carla.Location(x=x, y=-y, z=0.5), carla.Rotation(yaw=-math.degrees(psi)))
            self.ego = spawn_tesla(self.sim, tf)
            self.rear_dx = vehicle_params(self.ego)["rear_dx"]
        except Exception:
            self.sim.close()
            raise
        self.delta_last = 0.0
        self.frame = self.sim.frame

    def ego_state(self):
        return read_state(self.ego, self.rear_dx, self.delta_last)

    def apply(self, ctrl):
        self.delta_last = float(np.clip(ctrl.steer, -1, 1) / self.veh["steer_gain"])
        self.ego.apply_control(to_vehicle_control(ctrl))

    def tick(self):
        prev = self.frame
        self.frame = self.sim.tick()
        if prev is not None and self.frame != prev + 1:
            raise RuntimeError(f"số khung nhảy bất thường: {prev} -> {self.frame}")
        return self.frame

    def bind_agents(self, agents, rng):
        for a in agents:
            a.bind_carla(self.sim, rng)

    def sync_agents(self, agents):
        for a in agents:
            a.sync()

    def close(self):
        self.sim.close()
