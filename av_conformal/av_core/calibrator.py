"""Ước lượng σ_τ, lấy thưa, ngưỡng phù hợp (hướng dẫn §8.1–8.2) và bộ ngưỡng theo phương pháp.

Dùng lại `sim.common.conformal_q` để A/B cùng một định nghĩa phân vị."""
from __future__ import annotations

import numpy as np
import pandas as pd

from sim.common import conformal_q  # noqa: F401  (xuất lại)


def estimate_sigma(df, q=0.9, floor=0.05, H=None):
    """df: bảng chu kỳ (run_id, t, tau, d_plan, d_true). Phân vị q của max theo tác nhân, đơn điệu tăng theo τ."""
    g = df.assign(s=df.d_plan - df.d_true).groupby(["run_id", "t", "tau"]).s.max()
    sig = g.groupby("tau").quantile(q).clip(lower=floor).sort_index()
    out = np.maximum.accumulate(sig.to_numpy())
    return out


def thin(df_R, every_s=2.0):
    """Giữ 1 chu kỳ mỗi every_s giây trong mỗi lượt."""
    df_R = df_R.sort_values(["run_id", "t"])
    keep = (df_R.t // every_s).astype(int)
    return df_R.groupby(["run_id", keep]).head(1)


def q_by_group(df_R, alpha, groups=("fixed", "float", "lost")):
    out = {}
    for g in groups:
        R = df_R.loc[df_R.group == g, "R"].to_numpy()
        out[g] = conformal_q(R, alpha) if len(R) >= int(np.ceil(1 / alpha)) - 1 else None
    return out


class B0Calibrator:
    """B0: không nới biên (q = 0), σ_τ = 1; chỉ ghi dữ liệu."""
    name = "B0"

    def q(self, group=None, t=0.0):
        return 0.0

    def feedback(self, res):
        pass


class ConstCalibrator:
    """Ngưỡng hằng (hoặc theo nhóm) cho các phương pháp B1.. ở Phần 2, 3."""

    def __init__(self, name, q, q_by_g=None):
        self.name, self._q, self._g = name, float(q), q_by_g or {}

    def q(self, group=None, t=0.0):
        v = self._g.get(group)
        return self._q if v is None else float(v)

    def feedback(self, res):
        pass


def make_calibrator(method, q_table=None):
    if method == "B0":
        return B0Calibrator()
    q_table = q_table or {}
    if method in q_table:
        e = q_table[method]
        return ConstCalibrator(method, e["q"], e.get("by_group"))
    raise NotImplementedError(f"phương pháp {method} thuộc Phần 2/3 (T33, T36), cần q_table")
