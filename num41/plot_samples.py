"""Hình N0: 20 mẫu tổng hợp (kế hoạch/thực của xe, dự báo/thực của tác nhân) — kiểm tra trực quan bộ sinh.

Chạy: python -m num41.plot_samples  (từ thư mục ws)
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from num41.gen import make_rng, sample  # noqa: E402
from num41.logio import save_fig  # noqa: E402
from num41.scores import scores  # noqa: E402


def main(n_show: int = 20, sigma_loc: float = 0.3) -> None:
    b = sample(n_show, make_rng("TEST", 0, 0, 0), sigma_loc=sigma_loc)
    s = scores(b)
    fig, axes = plt.subplots(4, 5, figsize=(15, 11), sharex=True, sharey=True)
    for i, ax in enumerate(axes.ravel()):
        ax.plot(b.p_hat[i, :, 0], b.p_hat[i, :, 1], "-", color="#1f5fbf", lw=1.5, label="xe: kế hoạch")
        ax.plot(b.p[i, :, 0], b.p[i, :, 1], "--", color="#1f5fbf", lw=1.2, label="xe: thực")
        ax.plot(b.o_hat[i, :, 0], b.o_hat[i, :, 1], "-", color="#c0392b", lw=1.5, label="tác nhân: dự báo")
        ax.plot(b.o[i, :, 0], b.o[i, :, 1], "--", color="#c0392b", lw=1.2, label="tác nhân: thực")
        ax.plot(0, 0, "o", color="#1f5fbf", ms=4)
        ax.plot(b.o_hat[i, 0, 0], b.o_hat[i, 0, 1], "o", color="#c0392b", ms=4)
        ax.set_title(f"R={s['R'][i]:.2f}  A={s['A'][i]:.2f}  E={s['E'][i]:.2f}", fontsize=8)
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
    axes[0, 0].legend(fontsize=7, loc="upper left")
    for ax in axes[-1]:
        ax.set_xlabel("x (m)")
    for ax in axes[:, 0]:
        ax.set_ylabel("y (m)")
    fig.suptitle(f"N0 — {n_show} mẫu tổng hợp (σ_loc = {str(sigma_loc).replace('.', ',')} m, H = 30, Δt = 0,1 s)")
    fig.tight_layout()
    print("Đã ghi", save_fig(fig, "N0_samples"))


if __name__ == "__main__":
    main()
