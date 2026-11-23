"""Kết nối CARLA ở máy khác, chế độ đồng bộ, dọn dẹp (hướng dẫn §1.5, C1).

Chỉ chạy được khi có gói `carla` 0.9.15 (Python 3.7–3.10). Mọi tham số kết nối lấy từ dòng lệnh."""
from __future__ import annotations

import random

import numpy as np


class SimWorld:
    def __init__(self, host="localhost", port=2000, tm_port=8000, town="Town03", dt=0.05, seed=0,
                 no_rendering=True, timeout=120.0):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(timeout)
        self.actors = []
        self.dt = dt
        self._sync_applied = False
        try:
            self.world = self.client.load_world(town)
            s = self.world.get_settings()
            s.synchronous_mode = True
            s.fixed_delta_seconds = dt
            s.no_rendering_mode = no_rendering
            self.world.apply_settings(s)
            self._sync_applied = True
            self.tm = self.client.get_trafficmanager(tm_port)
            self.tm.set_synchronous_mode(True)
            self.tm.set_random_device_seed(seed)
            self.world.set_pedestrians_seed(seed)
        except Exception:
            self.close()   # không để máy chủ "đứng" chờ tick()
            raise
        random.seed(seed)
        np.random.seed(seed)
        self.frame = None

    def versions(self):
        return self.client.get_server_version(), self.client.get_client_version()

    def tick(self):
        f = self.world.tick()
        self.frame = f
        return f

    def spawn(self, bp, tf):
        a = self.world.try_spawn_actor(bp, tf)
        if a is not None:
            self.actors.append(a)
        return a

    def close(self):
        """LUÔN gọi khi kết thúc, kể cả khi lỗi (try/finally)."""
        carla = self.carla
        try:
            if self.actors:
                self.client.apply_batch([carla.command.DestroyActor(a) for a in self.actors])
                self.actors = []
        finally:
            try:
                if self._sync_applied:
                    s = self.world.get_settings()
                    s.synchronous_mode = False
                    s.fixed_delta_seconds = None
                    self.world.apply_settings(s)
                    self.tm.set_synchronous_mode(False)
            except Exception:
                pass
