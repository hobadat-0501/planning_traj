"""Kiểm thử hàm bậc thống kê PAC và Monte Carlo chứng nhận nhiều lần thử (TC-06, TC-07)."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import binom as _binom_dist

from sim.common import pac_conformal_q, pac_order_index


def test_tc06_pac_order_index() -> None:
    """TC-06: Kiểm tra n_min = 39 và k(187) = 178 với alpha=0.1, delta=0.05/3."""
    alpha = 0.10
    delta = 0.05 / 3.0

    # Tìm n_min nhỏ nhất có k_pac <= n
    feasible_ns = [n for n in range(1, 100) if pac_order_index(n, alpha, delta) <= n]
    assert feasible_ns[0] == 39
    assert pac_order_index(38, alpha, delta) > 38
    assert pac_order_index(39, alpha, delta) == 39

    k_187 = pac_order_index(187, alpha, delta)
    assert k_187 == 178
    assert float(_binom_dist.sf(k_187 - 1, 187, 1.0 - alpha)) <= delta
    assert float(_binom_dist.sf(k_187 - 2, 187, 1.0 - alpha)) > delta

    # Kiểm tra pac_conformal_q trả về inf nếu n < 39
    q_small, k_s, n_s = pac_conformal_q(np.arange(38, dtype=float), alpha, delta)
    assert math.isinf(q_small) and k_s == 39 and n_s == 38


def test_tc07_pac_monte_carlo_m3() -> None:
    """TC-07: Monte Carlo PAC M=3 tại p_true=0.89 -> tỉ lệ chứng nhận sai <= delta + 3*SE."""
    rng = np.random.default_rng(202607)
    n_cert = 187
    alpha = 0.10
    delta_total = 0.05
    m_tries = 3
    delta_per_try = delta_total / m_tries
    k_pac = pac_order_index(n_cert, alpha, delta_per_try)

    n_trials = 20000
    p_true = 0.89
    counts = rng.binomial(n_cert, p_true, size=(n_trials, m_tries))
    false_cert_rate = float(np.mean(np.any(counts >= k_pac, axis=1)))
    se = math.sqrt(false_cert_rate * (1.0 - false_cert_rate) / n_trials)
    assert false_cert_rate <= delta_total + 3.0 * se, (
        f"Tỉ lệ chứng nhận sai {false_cert_rate:.4f} vượt {delta_total + 3*se:.4f}"
    )
