"""Dự báo vận tốc hằng (mức nền, bắt buộc) và ADE/FDE (hướng dẫn §5.2)."""
from __future__ import annotations

import numpy as np


def predict_cv(track, H, dt):
    """track: [[t,x,y],...] (>=2 điểm gần nhất). Trả về (H,3) tư thế dự báo (x,y,psi), τ = 1..H."""
    track = np.asarray(track, dtype=float)
    (t0, x0, y0), (t1, x1, y1) = track[-2], track[-1]
    v = np.array([x1 - x0, y1 - y0]) / max(t1 - t0, 1e-9)
    psi = float(np.arctan2(v[1], v[0])) if np.linalg.norm(v) > 0.05 else 0.0
    xy = np.array([[x1, y1] + v * dt * k for k in range(1, H + 1)])
    return np.c_[xy, np.full(H, psi)]


class ConstantVelocityPredictor:
    """Giữ lịch sử vị trí từng tác nhân; trả về dự báo cho các tác nhân đã có >= 2 điểm."""

    def __init__(self, H, dt, history=20):
        self.H, self.dt, self.history = H, dt, history
        self.tracks: dict = {}

    def update(self, truth: dict, t):
        for aid, pose in truth.items():
            tr = self.tracks.setdefault(aid, [])
            tr.append([t, pose[0], pose[1]])
            del tr[:-self.history]
        for aid in list(self.tracks):
            if aid not in truth:
                del self.tracks[aid]

    def __call__(self, dims: dict):
        out = {}
        for aid, tr in self.tracks.items():
            if len(tr) >= 2:
                out[aid] = (predict_cv(tr, self.H, self.dt), dims[aid])
        return out


def ade_fde(pred_xy, true_xy):
    """pred_xy, true_xy: (N,H,2) hoặc (H,2). Trả về (ADE, FDE)."""
    d = np.linalg.norm(np.asarray(pred_xy) - np.asarray(true_xy), axis=-1)
    return float(d.mean()), float(d[..., -1].mean())
