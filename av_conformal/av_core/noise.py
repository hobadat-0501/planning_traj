"""Bộ phát sai số định vị D0–D5 (hướng dẫn §3.2–3.4)."""
from __future__ import annotations

import numpy as np


class LocalizationNoise:
    """Sai số định vị theo trạng thái RTK: 'fixed', 'float', 'lost'.
    fixed/float: nhiễu trắng + thiên lệch Gauss–Markov.
    lost: dead-reckoning, sai số tích lũy theo gyro và odometry."""

    def __init__(self, p, rng):
        self.p, self.rng = p, rng
        self.bias = np.zeros(2)
        self.dr = np.zeros(3)

    def sample(self, state, v, psi, dt):
        """Trả về (ex, ey, epsi) trong hệ toàn cục; psi là hướng thật của xe."""
        g = self.p[state]
        if state in ("fixed", "float"):
            beta = np.exp(-dt / g["tau_bias"])
            self.bias = beta * self.bias + np.sqrt(1 - beta ** 2) * g["sigma_bias"] * self.rng.standard_normal(2)
            exy = self.bias + g["sigma_white"] * self.rng.standard_normal(2)
            epsi = g["sigma_yaw"] * self.rng.standard_normal()
            self.dr[:] = [exy[0], exy[1], epsi]   # điểm xuất phát khi chuyển sang mất GNSS
            return tuple(self.dr)
        self.dr[2] += g["gyro_bias"] * dt + g["sigma_gyro"] * np.sqrt(dt) * self.rng.standard_normal()
        e_long = v * dt * g["odo_scale"] * self.rng.standard_normal()
        e_lat = v * dt * np.sin(self.dr[2])
        self.dr[0] += e_long * np.cos(psi) - e_lat * np.sin(psi)
        self.dr[1] += e_long * np.sin(psi) + e_lat * np.cos(psi)
        return tuple(self.dr)


class Condition:
    """Một điều kiện D0–D5 đã rút mẫu theo hạt giống của lượt chạy."""

    def __init__(self, name, spec, rng, delay_samples=None):
        self.name, self.spec = name, spec
        self.base_rtk = spec["rtk"]
        self.odo_mult = float(spec.get("odo_scale_mult", 1.0))
        self.outage = None
        if "outage" in spec:
            o = spec["outage"]
            start = rng.uniform(*o["start_range"])
            self.outage = (start, start + rng.uniform(*o["duration_range"]))
        self.fixed_delay = 0.0
        if "extra_delay" in spec:
            self.fixed_delay = float(rng.choice(spec["extra_delay"]))
        self.random_delay = "extra_delay_dist" in spec
        self.delay_samples = delay_samples
        self._rng = rng

    def rtk_at(self, t):
        if self.outage and self.outage[0] <= t < self.outage[1]:
            return "lost"
        return self.base_rtk

    def delay_for_cycle(self):
        """D5: mỗi chu kỳ một mẫu trễ; D4: trễ cố định của lượt; còn lại 0."""
        if self.random_delay:
            if self.delay_samples is not None and len(self.delay_samples):
                return float(self._rng.choice(self.delay_samples))
            return float(min(0.5, self._rng.lognormal(np.log(0.10), 0.5)))   # TẠM
        return self.fixed_delay

    def speed_sigma(self, noise_cfg):
        """D3: độ lệch chuẩn tương đối của vận tốc đo (odometry) = odo_scale·odo_mult; các điều kiện khác = 0. TẠM."""
        return noise_cfg["lost"]["odo_scale"] * self.odo_mult if self.odo_mult != 1.0 else 0.0
