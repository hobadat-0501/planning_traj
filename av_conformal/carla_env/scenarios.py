"""Tác nhân và kịch bản S1–S4 (hướng dẫn §4).

Động học tác nhân là Python thuần (tất định theo hạt giống, test được không cần CARLA).
Khi chạy CARLA, `bind_carla` tạo actor và `sync` đẩy trạng thái sang actor
(người đi bộ dùng WalkerControl, xe tắt vật lý và set_transform).
S3 và S4 do nhóm tự thiết kế theo mô tả bản thảo, ghi TẠM (PLAN §11.5 C8)."""
from __future__ import annotations

import math

import numpy as np

from ..av_core.planner import RefPath
from .coords import to_carla_xyz_yaw


class Route(RefPath):
    """Tuyến xe tự hành: đa tuyến + tư thế xuất phát."""

    @classmethod
    def straight(cls, length=120.0, step=1.0, x0=0.0, y0=0.0, heading=0.0):
        n = int(length / step) + 1
        s = np.arange(n) * step
        return cls(np.c_[x0 + s * math.cos(heading), y0 + s * math.sin(heading)])

    def start_pose(self):
        return float(self.xy[0, 0]), float(self.xy[0, 1]), float(self.theta[0])


class Agent:
    kind = "agent"

    def __init__(self, aid, dims):
        self.id, self.dims = aid, tuple(dims)
        self.pos = np.zeros(2)
        self.heading = 0.0
        self.speed = 0.0
        self.active = False
        self.actor = None

    def step(self, ego_xy, t, dt):
        raise NotImplementedError

    def pose(self):
        if self.actor is not None and self.kind == "pedestrian":
            from .coords import from_carla
            return tuple(from_carla(self.actor.get_transform()))
        return (float(self.pos[0]), float(self.pos[1]), float(self.heading))

    def visible(self, ego_xy, rng_m=60.0):
        return float(np.hypot(self.pos[0] - ego_xy[0], self.pos[1] - ego_xy[1])) < rng_m

    # ----- CARLA -----
    blueprint_filter = None

    def bind_carla(self, sim, rng):
        carla = sim.carla
        lib = sim.world.get_blueprint_library()
        bps = sorted(lib.filter(self.blueprint_filter), key=lambda b: b.id)
        bp = bps[int(rng.integers(len(bps)))]
        x, y, z, yaw = to_carla_xyz_yaw(self.pos[0], self.pos[1], self.heading, z=1.0 if self.kind == "pedestrian" else 0.3)
        tf = carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))
        self.actor = sim.spawn(bp, tf)
        if self.actor is None:
            raise RuntimeError(f"không sinh được actor cho {self.id}")
        if self.kind != "pedestrian":
            self.actor.set_simulate_physics(False)
        self._carla = carla

    def sync(self):
        if self.actor is None:
            return
        carla = self._carla
        if self.kind == "pedestrian":
            v = np.array([math.cos(self.heading), math.sin(self.heading)])
            d = carla.Vector3D(x=float(v[0]), y=float(-v[1]), z=0.0)
            self.actor.apply_control(carla.WalkerControl(direction=d, speed=float(self.speed)))
        else:
            x, y, z, yaw = to_carla_xyz_yaw(self.pos[0], self.pos[1], self.heading, z=0.3)
            self.actor.set_transform(carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw)))


class CrossingPedestrian(Agent):
    """S1: người đi bộ sang đường vuông góc với tuyến, qua điểm P."""
    kind = "pedestrian"
    blueprint_filter = "walker.pedestrian.*"

    def __init__(self, aid, route, s_conf, rng, cfg, dims):
        super().__init__(aid, dims)
        self.speed_nom = rng.uniform(*cfg["speed"])
        self.s_trig = rng.uniform(*cfg["trigger_dist"])
        self.stop_mid = rng.random() < cfg["p_stop_mid"]
        side = int(rng.choice([-1, 1]))
        px, py, th = route.point(s_conf + rng.uniform(-2.0, 2.0))
        self.P = np.array([px, py], dtype=float)
        n = np.array([-math.sin(th), math.cos(th)])
        self.pos = self.P + side * cfg["lateral_start"] * n
        self.dir = -side * n
        self.heading = math.atan2(self.dir[1], self.dir[0])
        self.t_stop = None

    def step(self, ego_xy, t, dt):
        if not self.active and np.linalg.norm(np.asarray(ego_xy) - self.P) < self.s_trig:
            self.active = True
        sp = self.speed_nom if self.active else 0.0
        if self.stop_mid and self.active:
            if np.linalg.norm(self.pos - self.P) < 0.3 and self.t_stop is None:
                self.t_stop = t
            if self.t_stop is not None and t - self.t_stop < 2.0:
                sp = 0.0
        self.speed = sp
        self.pos = self.pos + sp * dt * self.dir


class CrossingVehicle(Agent):
    """S2/S3: xe máy hoặc ô tô cắt ngang tuyến qua P với góc cắt và vận tốc ngẫu nhiên."""

    def __init__(self, aid, kind, route, s_conf, rng, cfg, dims, blueprint_filter, angle_deg=None):
        super().__init__(aid, dims)
        self.kind = kind
        self.blueprint_filter = blueprint_filter
        self.speed_nom = rng.uniform(*cfg["speed"])
        ang = math.radians(rng.uniform(*cfg.get("cross_angle_deg", [90, 90])) if angle_deg is None else angle_deg)
        side = int(rng.choice([-1, 1]))
        px, py, th = route.point(s_conf + rng.uniform(-2.0, 2.0))
        self.heading = th + side * ang
        self.s_trig = rng.uniform(*cfg["trigger_dist"])
        self.P = np.array([px, py], dtype=float)
        self.pos = self.P - cfg["approach_len"] * np.array([math.cos(self.heading), math.sin(self.heading)])
        self.dir = np.array([math.cos(self.heading), math.sin(self.heading)])

    def step(self, ego_xy, t, dt):
        if not self.active and np.linalg.norm(np.asarray(ego_xy) - self.P) < self.s_trig:
            self.active = True
        self.speed = self.speed_nom if self.active else 0.0
        self.pos = self.pos + self.speed * dt * self.dir


class LeadVehicle(Agent):
    """S4: xe phía trước chạy trên tuyến rồi phanh gấp (TẠM)."""
    kind = "car"
    blueprint_filter = "vehicle.audi.a2"

    def __init__(self, aid, route, rng, cfg, dims):
        super().__init__(aid, dims)
        self.route = route
        self.s = rng.uniform(*cfg["gap"])
        self.v = rng.uniform(*cfg["speed"])
        self.decel = rng.uniform(*cfg["brake_decel"])
        self.t_brake = rng.uniform(*cfg["brake_time"])
        self._update_pose()

    def _update_pose(self):
        x, y, th = self.route.point(self.s)
        self.pos, self.heading = np.array([x, y]), float(th)

    def step(self, ego_xy, t, dt):
        self.active = True
        if t >= self.t_brake:
            self.v = max(0.0, self.v - self.decel * dt)
        self.speed = self.v
        self.s = min(self.s + self.v * dt, self.route.length)
        self._update_pose()


def build_scenario(name, route, cfg, rng):
    """Trả về danh sách tác nhân; mọi ngẫu nhiên lấy từ rng nên cùng hạt giống cho cùng kịch bản."""
    sc = cfg["scenarios"]
    s_conf = float(sc["conflict_point_s"])
    dims = sc["dims"]
    agents: list[Agent] = []
    if name == "S1":
        c = sc["S1"]["pedestrians"]
        n = int(rng.integers(c["n"][0], c["n"][1] + 1))
        for i in range(n):
            agents.append(CrossingPedestrian(f"ped{i}", route, s_conf, rng, c, dims["pedestrian"]))
    elif name == "S2":
        c = sc["S2"]["motorbikes"]
        n = int(rng.integers(c["n"][0], c["n"][1] + 1))
        for i in range(n):
            agents.append(CrossingVehicle(f"mb{i}", "motorbike", route, s_conf, rng, c, dims["motorbike"],
                                          "vehicle.yamaha.yzf"))
    elif name == "S3":
        m, v = sc["S3"]["motorbike"], sc["S3"]["car"]
        agents.append(CrossingVehicle("mb0", "motorbike", route, s_conf, rng, m, dims["motorbike"],
                                      "vehicle.yamaha.yzf"))
        agents.append(CrossingVehicle("car0", "car", route, s_conf, rng,
                                      dict(v, cross_angle_deg=[90, 90]), dims["car"], "vehicle.audi.a2"))
    elif name == "S4":
        agents.append(LeadVehicle("lead0", route, rng, sc["S4"]["lead"], dims["car"]))
    else:
        raise ValueError(f"kịch bản không biết: {name}")
    return agents
