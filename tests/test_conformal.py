"""Kiểm thử phân vị phù hợp trên dữ liệu tổng hợp hoán đổi được (TC-05)."""

from __future__ import annotations

import numpy as np

from sim.common import conformal_q


def test_tc05_conformal_quantile_synthetic() -> None:
    """TC-05: n=200, 10.000 lần lặp trên Gauss, Student-t3, Pareto -> độ phủ in [1-a, 1-a+1/(n+1)] +- 0.005."""
    rng = np.random.default_rng(202605)
    n = 200
    n_trials = 10000
    alpha = 0.10
    lo_bound = (1.0 - alpha) - 0.005
    hi_bound = (1.0 - alpha + 1.0 / (n + 1)) + 0.005

    dists = {
        "gauss": lambda sz: rng.normal(0.0, 1.0, size=sz),
        "student_t3": lambda sz: rng.standard_t(3.0, size=sz),
        "pareto": lambda sz: rng.pareto(2.5, size=sz),
    }

    for name, sampler in dists.items():
        calib = sampler((n_trials, n))
        test = sampler(n_trials)
        # Kiểm chứng hàm conformal_q trên một số mẫu đầu
        for j in range(50):
            q_fn = conformal_q(calib[j], alpha)
            k = int(np.ceil((n + 1) * (1.0 - alpha)))
            assert abs(q_fn - np.sort(calib[j])[k - 1]) < 1e-12

        k = int(np.ceil((n + 1) * (1.0 - alpha)))
        qs = np.partition(calib, k - 1, axis=1)[:, k - 1]
        cov = float(np.mean(test <= qs))
        assert lo_bound <= cov <= hi_bound, (
            f"Phân phối {name}: độ phủ {cov:.4f} nằm ngoài [{lo_bound:.4f}, {hi_bound:.4f}]"
        )
