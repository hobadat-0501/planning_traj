"""Bộ lập kế hoạch Frenet có ràng buộc biên (hướng dẫn §6.2).

Ứng viên: lệch ngang -1,5..1,5 m (bước d_step) x vận tốc đích 0..v_max (bước v_step) x T in {3,4,5} s.
Quỹ đạo ngang: đa thức bậc 5; dọc: đa thức bậc 4 (vận tốc đích, gia tốc cuối = 0).
Lọc theo thứ tự chi phí; ứng viên đầu tiên thỏa động học và biên an toàn
d_hat >= d_s + sigma_tau * q tại mọi (tau, tác nhân) được chọn. Không có thì phanh a_min
dọc đường hiện tại (dự phòng)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry import poly_distance_batch, rect_polygons, wrap_angle


class RefPath:
    """Đường tham chiếu đa tuyến (N,2) với tọa độ cung s."""

    def __init__(self, xy):
        self.xy = np.asarray(xy, dtype=float)
        seg = np.diff(self.xy, axis=0)
        ds = np.linalg.norm(seg, axis=1)
        self.s = np.r_[0.0, np.cumsum(ds)]
        self.theta = np.r_[np.arctan2(seg[:, 1], seg[:, 0]), np.arctan2(seg[-1, 1], seg[-1, 0])]
        self._theta_u = np.unwrap(self.theta)
        self.length = float(self.s[-1])

    def point(self, s):
        s = np.clip(s, 0.0, self.length)
        x = np.interp(s, self.s, self.xy[:, 0])
        y = np.interp(s, self.s, self.xy[:, 1])
        th = np.interp(s, self.s, self._theta_u)
        return x, y, th

    def to_frenet(self, px, py):
        """Hình chiếu lên các đoạn thẳng: (s, d, theta_ref); d dương sang trái."""
        a, b = self.xy[:-1], self.xy[1:]
        ab = b - a
        L2 = (ab ** 2).sum(1)
        t = np.clip(((np.array([px, py]) - a) * ab).sum(1) / np.maximum(L2, 1e-12), 0, 1)
        proj = a + t[:, None] * ab
        i = int(np.argmin(np.linalg.norm(proj - [px, py], axis=1)))
        th = self.theta[i]
        s = self.s[i] + t[i] * np.sqrt(L2[i])
        d = -(px - proj[i, 0]) * np.sin(th) + (py - proj[i, 1]) * np.cos(th)
        return float(s), float(d), float(th)

    def frenet_to_xy(self, s, d):
        x, y, th = self.point(s)
        return x - d * np.sin(th), y + d * np.cos(th), th


def _quintic(x0, v0, a0, x1, T):
    A = np.array([[T ** 3, T ** 4, T ** 5], [3 * T ** 2, 4 * T ** 3, 5 * T ** 4], [6 * T, 12 * T ** 2, 20 * T ** 3]])
    b = np.array([x1 - (x0 + v0 * T + 0.5 * a0 * T ** 2), -(v0 + a0 * T), -a0])
    c3, c4, c5 = np.linalg.solve(A, b)
    return np.array([x0, v0, a0 / 2, c3, c4, c5])


def _quartic(x0, v0, a0, v1, T):
    A = np.array([[3 * T ** 2, 4 * T ** 3], [6 * T, 12 * T ** 2]])
    b = np.array([v1 - (v0 + a0 * T), -a0])
    c3, c4 = np.linalg.solve(A, b)
    return np.array([x0, v0, a0 / 2, c3, c4])


def _poly(c, t, der=0):
    out = np.zeros_like(t, dtype=float)
    for k in range(der, len(c)):
        coef = c[k]
        for j in range(der):
            coef = coef * (k - j)
        out = out + coef * t ** (k - der)
    return out


@dataclass
class Plan:
    poses_H: np.ndarray      # (H,3) tại tau = 1..H
    path_xy: np.ndarray      # (N,2) cho bộ bám
    path_v: np.ndarray       # (N,)
    fallback: bool
    n_candidates: int = 0
    n_checked: int = 0
    v_end: float = 0.0


class FrenetPlanner:
    def __init__(self, vehicle, ref: RefPath, H=30, dt=0.1, d_s=0.5, d_range=1.5, d_step=0.25,
                 v_step=0.5, horizons=(3.0, 4.0, 5.0)):
        self.veh, self.ref, self.H, self.dt, self.d_s = vehicle, ref, H, dt, d_s
        self.ego_dims = (vehicle["length"], vehicle["width"], vehicle["rear_overhang"])
        self.d_targets = np.arange(-d_range, d_range + 1e-9, d_step)
        self.v_targets = np.arange(0.0, vehicle["v_max"] + 1e-9, v_step)
        self.horizons = horizons
        self.kappa_max = np.tan(vehicle["delta_max"]) / vehicle["L"]
        self.tau = dt * np.arange(1, H + 1)

    def plan(self, x_est, preds, margin_tau):
        """x_est=[px,py,psi,v,delta]; preds {id: (pose (H,3), dims)}; margin_tau (H,) = sigma_tau*q."""
        px, py, psi, v0 = x_est[0], x_est[1], x_est[2], x_est[3]
        s0, d0, th0 = self.ref.to_frenet(px, py)
        dpsi = float(wrap_angle(psi - th0))
        dd0 = v0 * np.sin(dpsi)
        v0s = max(v0 * np.cos(dpsi), 0.0)
        margin_tau = np.broadcast_to(np.asarray(margin_tau, dtype=float), (self.H,))
        am, an = self.veh["a_max"], self.veh["a_min"]
        vmax = self.veh["v_max"]
        cands = []
        for T in self.horizons:
            tt = np.arange(0.0, T + 1e-9, self.dt)
            s_prof = []                                  # ứng viên dọc: tính một lần cho mọi dT
            for vT in self.v_targets:
                cs = _quartic(s0, v0s, 0.0, vT, T)
                a_t = _poly(cs, tt, 2)
                if a_t.max() > am or a_t.min() < an:
                    continue
                if _poly(cs, tt, 1).min() < -1e-3:
                    continue
                c_s = (vT - vmax) ** 2 + 0.05 * float((a_t ** 2).mean())                     + 0.2 * float(np.abs(np.diff(a_t)).mean() / self.dt)
                s_prof.append((c_s, cs))
            if not s_prof:
                continue
            for dT in self.d_targets:
                cd = _quintic(d0, dd0, 0.0, dT, T)
                d_t, dd_t = _poly(cd, tt), _poly(cd, tt, 1)
                c_d = 2.0 * dT ** 2 + 0.5 * (dT - d0) ** 2
                for c_s, cs in s_prof:
                    cands.append((c_s + c_d, cs, tt, d_t, dd_t))
        cands.sort(key=lambda c: c[0])
        prep = self._prep(preds)
        n_checked = 0
        CH = 48
        for c0 in range(0, len(cands), CH):
            built = [b for b in self._build_many(cands[c0:c0 + CH]) if b is not None]
            if not built:
                continue
            ok = self._safe_many(np.stack([b[0] for b in built]), prep, margin_tau)
            first = int(np.argmax(ok)) if ok.any() else -1
            if first >= 0:
                n_checked += first + 1
                poses, xy, vv = built[first]
                return Plan(poses, xy, vv, False, len(cands), n_checked, float(vv[-1]))
            n_checked += len(built)
        return self._fallback(s0, v0s, d0, len(cands), n_checked)

    def _build_many(self, chunk):
        """Dựng quỹ đạo cho một lô ứng viên (cùng T thì xử lý vector hóa). Trả về danh sách cùng thứ tự, None nếu vi phạm độ cong."""
        out = [None] * len(chunk)
        groups = {}
        for i, c in enumerate(chunk):
            groups.setdefault(len(c[2]), []).append(i)
        for _, idx in groups.items():
            tt = chunk[idx[0]][2]
            CS = np.stack([chunk[i][1] for i in idx])                   # (n,5)
            D = np.stack([chunk[i][3] for i in idx])                    # (n,m)
            DD = np.stack([chunk[i][4] for i in idx])
            pw = np.stack([tt ** k for k in range(5)])                  # (5,m)
            s_t = CS @ pw
            sd_t = CS[:, 1:] @ (np.arange(1, 5)[:, None] * pw[:4])
            x, y, th = self.ref.frenet_to_xy(s_t, D)
            slope = np.where(sd_t > 0.05, DD / np.maximum(sd_t, 0.05), 0.0)
            psi = th + np.arctan(slope)
            dpsi = np.abs(np.diff(np.unwrap(psi, axis=1), axis=1))
            ds = np.hypot(np.diff(x, axis=1), np.diff(y, axis=1))
            mask = ds > 0.02
            kap = np.where(mask, dpsi / np.where(mask, ds, 1.0), 0.0).max(axis=1)
            ok = kap <= 1.1 * self.kappa_max
            tix = np.minimum(np.round(self.tau / self.dt).astype(int), len(tt) - 1)
            for j, i in enumerate(idx):
                if ok[j]:
                    out[i] = (np.c_[x[j, tix], y[j, tix], psi[j, tix]], np.c_[x[j], y[j]], sd_t[j])
        return out

    def _prep(self, preds):
        """Gom dự báo thành mảng một lần cho mỗi chu kỳ (không lặp lại theo ứng viên)."""
        ids = list(preds)
        if not ids:
            return None
        P = np.stack([preds[a][0] for a in ids])                       # (A,H,3)
        dims = [preds[a][1] for a in ids]
        rad = np.array([np.hypot(*self.ego_dims[:2]) + 0.5 * np.hypot(*d) for d in dims])
        return P, dims, rad

    def _safe_many(self, poses, prep, margin_tau):
        """poses (n,H,3) -> mảng bool (n,): ứng viên nào thỏa biên an toàn với mọi tác nhân và mọi τ."""
        n = poses.shape[0]
        if prep is None:
            return np.ones(n, dtype=bool)
        P, dims, rad = prep
        thr = self.d_s + margin_tau                                    # (H,)
        dist = np.hypot(poses[:, None, :, 0] - P[None, :, :, 0], poses[:, None, :, 1] - P[None, :, :, 1])  # (n,A,H)
        near = dist < rad[None, :, None] + thr[None, None, :]
        ci, ai, ki = np.nonzero(near)
        ok = np.ones(n, dtype=bool)
        if len(ci) == 0:
            return ok
        el, ew, eo = self.ego_dims
        E = rect_polygons(poses[ci, ki, 0], poses[ci, ki, 1], poses[ci, ki, 2], el, ew, eo)
        dm = np.array([dims[a] for a in ai])
        Ag = rect_polygons(P[ai, ki, 0], P[ai, ki, 1], P[ai, ki, 2], dm[:, 0], dm[:, 1], dm[:, 0] / 2)
        bad = poly_distance_batch(E, Ag) < thr[ki]
        ok[np.unique(ci[bad])] = False
        return ok

    def _fallback(self, s0, v0, d0, n_c, n_chk):
        a = self.veh["a_min"]
        tt = np.arange(0.0, 5.0 + 1e-9, self.dt)
        t_stop = v0 / abs(a) if a < 0 else np.inf
        te = np.minimum(tt, t_stop)
        s_t = s0 + v0 * te + 0.5 * a * te ** 2
        v_t = np.maximum(v0 + a * tt, 0.0)
        x, y, th = self.ref.frenet_to_xy(s_t, np.full_like(tt, d0))
        idx = np.minimum(np.round(self.tau / self.dt).astype(int), len(tt) - 1)
        return Plan(np.c_[x[idx], y[idx], th[idx]], np.c_[x, y], v_t, True, n_c, n_chk, float(v_t[-1]))
