"""Bộ đánh giá trễ H bước (hướng dẫn §6.4).

Thứ tự trong một chu kỳ lập kế hoạch: gọi `add_truth` (giá trị chuẩn tại t) TRƯỚC `add_plan`,
nên kế hoạch lập tại t nhận giá trị chuẩn từ t+0,1 s (τ = 1) đến t+H·0,1 s (τ = H)."""
from __future__ import annotations

from collections import deque

import numpy as np

from .geometry import poly_distance_batch, rect_polygons, wrap_angle


class DelayedEvaluator:
    def __init__(self, H, ego_dims, sigma_tau, d_s):
        """ego_dims = (length, width, rear_overhang)."""
        self.H, self.ego_dims, self.d_s = H, tuple(ego_dims), d_s
        self.sigma = np.broadcast_to(np.asarray(sigma_tau, dtype=float), (H,)).copy()
        self.pending: deque = deque()

    def add_plan(self, t, plan_poses, pred_agents, meta):
        """plan_poses (H,3); pred_agents {id: (pred (H,3), dims (len,wid))}."""
        self.pending.append(dict(t=t, plan=np.asarray(plan_poses), pred=pred_agents, meta=meta,
                                 true_ego=[], true_ag=[]))

    def add_truth(self, ego_pose, agents_truth):
        for rec in self.pending:
            if len(rec["true_ego"]) < self.H:
                rec["true_ego"].append(tuple(ego_pose))
                rec["true_ag"].append(dict(agents_truth))
        out = []
        while self.pending and len(self.pending[0]["true_ego"]) == self.H:
            out.append(self._finalize(self.pending.popleft()))
        return out

    def _finalize(self, rec):
        H = self.H
        el, ew, eo = self.ego_dims
        plan = rec["plan"]
        te = np.asarray(rec["true_ego"], dtype=float)                  # (H,3)
        ep = np.hypot(plan[:, 0] - te[:, 0], plan[:, 1] - te[:, 1])
        ey = np.abs(wrap_angle(plan[:, 2] - te[:, 2]))
        ego_plan = rect_polygons(plan[:, 0], plan[:, 1], plan[:, 2], el, ew, eo)
        ego_true = rect_polygons(te[:, 0], te[:, 1], te[:, 2], el, ew, eo)
        rows, R = [], -np.inf
        for aid, (pred, dims) in rec["pred"].items():
            ks = [k for k in range(H) if aid in rec["true_ag"][k]]
            if not ks:
                continue
            at = np.array([rec["true_ag"][k][aid] for k in ks], dtype=float)
            pr = np.asarray(pred)[ks]
            ag_pred = rect_polygons(pr[:, 0], pr[:, 1], pr[:, 2], dims[0], dims[1], dims[0] / 2)
            ag_true = rect_polygons(at[:, 0], at[:, 1], at[:, 2], dims[0], dims[1], dims[0] / 2)
            d_plan = poly_distance_batch(ego_plan[ks], ag_pred)
            d_true = poly_distance_batch(ego_true[ks], ag_true)
            err = np.hypot(pr[:, 0] - at[:, 0], pr[:, 1] - at[:, 1])
            R = max(R, float(((d_plan - d_true) / self.sigma[ks]).max()))
            for j, k in enumerate(ks):
                rows.append(dict(
                    **rec["meta"], t=rec["t"], tau=k + 1, agent_id=aid,
                    d_plan=float(d_plan[j]), d_true=float(d_true[j]), violation=int(d_true[j] < self.d_s),
                    err_agent=float(err[j]), err_ego_pos=float(ep[k]), err_ego_yaw=float(ey[k])))
        return dict(meta=rec["meta"], t=rec["t"], R=R, rows=rows)
