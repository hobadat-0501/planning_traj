"""Đa giác lồi (chữ nhật) và khoảng cách, chỉ dùng numpy (không cần shapely)."""
from __future__ import annotations

import numpy as np


def rect_polygon(px, py, psi, length, width, rear_overhang=0.0):
    """Đỉnh (4,2) của hình chữ nhật. Gốc (px,py) tại tâm cầu sau (xe tự hành,
    rear_overhang = khoảng từ tâm cầu sau tới đuôi) hoặc tâm hình (tác nhân, rear_overhang = length/2)."""
    c, s = np.cos(psi), np.sin(psi)
    xs = np.array([-rear_overhang, length - rear_overhang, length - rear_overhang, -rear_overhang])
    ys = np.array([-width / 2, -width / 2, width / 2, width / 2])
    return np.c_[px + c * xs - s * ys, py + s * xs + c * ys]


def _axes(P):
    e = np.roll(P, -1, axis=0) - P
    n = np.c_[-e[:, 1], e[:, 0]]
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def _intersect(A, B) -> bool:
    for P in (A, B):
        for ax in _axes(P):
            a, b = A @ ax, B @ ax
            if a.max() < b.min() or b.max() < a.min():
                return False
    return True


def _pts_to_edges(pts, Q):
    """Khoảng cách nhỏ nhất từ các điểm pts (m,2) tới các cạnh của đa giác Q (n,2)."""
    a = Q
    b = np.roll(Q, -1, axis=0)
    ab = b - a
    t = ((pts[:, None, :] - a[None]) * ab[None]).sum(-1) / (ab * ab).sum(-1)[None]
    t = np.clip(t, 0.0, 1.0)
    proj = a[None] + t[..., None] * ab[None]
    return np.linalg.norm(pts[:, None, :] - proj, axis=-1).min()


def poly_distance(A, B) -> float:
    """Khoảng cách giữa hai đa giác lồi; 0 nếu giao nhau."""
    if _intersect(A, B):
        return 0.0
    return float(min(_pts_to_edges(A, B), _pts_to_edges(B, A)))


def rect_polygons(px, py, psi, length, width, rear_overhang):
    """Như rect_polygon nhưng theo lô: px, py, psi dạng mảng (n,) -> (n,4,2)."""
    px, py, psi = (np.atleast_1d(np.asarray(v, dtype=float)) for v in (px, py, psi))
    c, s = np.cos(psi)[:, None], np.sin(psi)[:, None]
    ro = np.broadcast_to(np.asarray(rear_overhang, dtype=float), px.shape)[:, None]
    ln = np.broadcast_to(np.asarray(length, dtype=float), px.shape)[:, None]
    wd = np.broadcast_to(np.asarray(width, dtype=float), px.shape)[:, None]
    xs = np.concatenate([-ro, ln - ro, ln - ro, -ro], axis=1)
    ys = np.concatenate([-wd, -wd, wd, wd], axis=1) / 2
    return np.stack([px[:, None] + c * xs - s * ys, py[:, None] + s * xs + c * ys], axis=-1)


def _seg_pts_batch(Pts, Q):
    """Khoảng cách nhỏ nhất từ 4 điểm Pts (n,4,2) tới 4 cạnh của Q (n,4,2) -> (n,)."""
    a = Q
    b = np.roll(Q, -1, axis=1)
    ab = b - a                                                       # (n,4,2)
    ap = Pts[:, :, None, :] - a[:, None, :, :]                       # (n,4pts,4edges,2)
    t = (ap * ab[:, None]).sum(-1) / (ab * ab).sum(-1)[:, None]
    t = np.clip(t, 0.0, 1.0)
    d = ap - t[..., None] * ab[:, None]
    return np.sqrt((d * d).sum(-1)).min(axis=(1, 2))


def poly_distance_batch(A, B):
    """Khoảng cách giữa các cặp hình chữ nhật A[i], B[i] (n,4,2); 0 nếu giao nhau."""
    sep = np.zeros(len(A), dtype=bool)
    for P in (A, B):
        e = np.stack([P[:, 1] - P[:, 0], P[:, 3] - P[:, 0]], axis=1)      # 2 cạnh kề của hình chữ nhật
        ax = np.stack([-e[..., 1], e[..., 0]], axis=-1)
        ax = ax / np.linalg.norm(ax, axis=-1, keepdims=True)              # (n,2,2)
        pa = np.einsum("nvc,nac->nav", A, ax)
        pb = np.einsum("nvc,nac->nav", B, ax)
        sep |= ((pa.max(-1) < pb.min(-1)) | (pb.max(-1) < pa.min(-1))).any(-1)
    d = np.minimum(_seg_pts_batch(A, B), _seg_pts_batch(B, A))
    return np.where(sep, d, 0.0)


def wrap_angle(a):
    return (np.asarray(a) + np.pi) % (2 * np.pi) - np.pi
