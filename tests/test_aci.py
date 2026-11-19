"""Kiểm thử cơ chế ACI chế độ B và theo dõi dịch chuyển phân phối (TC-08, TC-09)."""

from __future__ import annotations

import numpy as np

from sim.common import AdaptiveConformalState
from sim.core import DEFAULT_SIGMA_OLD


def test_tc08_aci_empty_cycles() -> None:
    """TC-08: Ở chế độ B (update_on_empty=False), chu kỳ trống không làm đổi alpha_t và cửa sổ."""
    init_scores = [0.5, 1.0, 1.5, 2.0, 2.5]
    aci = AdaptiveConformalState(
        init_scores=init_scores,
        sigma_tau=DEFAULT_SIGMA_OLD,
        alpha=0.10,
        gamma=0.02,
        window_size=500,
        score_key="R",
        update_on_empty=False,
    )

    alpha_before = aci.alpha_t
    win_before = list(aci.window)
    n_upd_before = aci.n_updates

    for t_val in (0.0, 0.1, 0.2, 0.3):
        aci.feedback({"has_agents": 0, "R": float("-inf"), "q": aci.current_q(), "t": t_val})

    assert aci.alpha_t == alpha_before
    assert list(aci.window) == win_before
    assert aci.n_updates == n_upd_before

    # Sau đó cho 1 chu kỳ có tác nhân -> phải cập nhật
    aci.feedback({"has_agents": 1, "R": 10.0, "q": aci.current_q(), "t": 0.4})
    assert aci.n_updates == n_upd_before + 1
    assert aci.alpha_t < alpha_before


def test_tc09_aci_distribution_shift() -> None:
    """TC-09: Chuỗi điểm số dịch chuyển phân phối đột ngột -> độ phủ dài hạn in 1-alpha +- 0.02."""
    rng = np.random.default_rng(202609)
    alpha = 0.10
    gamma = 0.02
    n_pre = 500
    n_post = 2000

    init_scores = rng.normal(0.0, 1.0, size=200)
    aci = AdaptiveConformalState(
        init_scores=init_scores,
        sigma_tau=DEFAULT_SIGMA_OLD,
        alpha=alpha,
        gamma=gamma,
        window_size=500,
        score_key="R",
        update_on_empty=False,
        cap_q=50.0,
    )

    # Phân phối trước dịch chuyển N(0, 1), sau bước 500 dịch đột ngột sang N(3.5, 1.8^2)
    scores_all = np.concatenate([
        rng.normal(0.0, 1.0, size=n_pre),
        rng.normal(3.5, 1.8, size=n_post),
    ])

    cov_post = []
    for idx, sc in enumerate(scores_all):
        q_used = aci.current_q()
        covered = float(sc <= q_used)
        aci.feedback({"has_agents": 1, "R": float(sc), "q": q_used})
        if idx >= n_pre:
            cov_post.append(covered)

    mean_cov = float(np.mean(cov_post))
    assert (1.0 - alpha - 0.02) <= mean_cov <= (1.0 - alpha + 0.02), (
        f"Độ phủ dài hạn ACI sau dịch phân phối = {mean_cov:.4f} ngoài [0.88, 0.92]"
    )
