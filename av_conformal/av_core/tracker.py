"""Bộ bám Pure Pursuit (hướng dẫn §6.3), chạy trên tư thế ƯỚC LƯỢNG."""
from __future__ import annotations

import numpy as np


def pure_pursuit(x, path_xy, path_v, L, ld_min=1.0, k_ld=0.5, dmax=0.4):
    """x = [px,py,psi,v,delta]; path_xy (N,2). Trả về (v_cmd, delta_cmd)."""
    path_xy = np.asarray(path_xy)
    ld = max(ld_min, k_ld * x[3])
    d = np.linalg.norm(path_xy - np.asarray(x[:2]), axis=1)
    i0 = int(np.argmin(d))
    idx = next((i for i in range(i0, len(path_xy)) if d[i] >= ld), len(path_xy) - 1)
    dx, dy = path_xy[idx] - np.asarray(x[:2])
    alpha = np.arctan2(dy, dx) - x[2]
    alpha = (alpha + np.pi) % (2 * np.pi) - np.pi
    delta = np.arctan2(2 * L * np.sin(alpha), ld)
    return float(path_v[idx]), float(np.clip(delta, -dmax, dmax))
