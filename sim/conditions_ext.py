"""Mở rộng điều kiện suy giảm D6–D10 cho mô phỏng mở rộng v0.2 (SPEC §9.2).

- D6: Kết hợp D1 (RTK thả nổi) + D4 (trễ thêm cố định 100 ms), nhãn 'float'.
- D7: Mất GNSS dài 15–20 s (nhãn 'loss').
- D8: Trạng thái thật như D1 (float), nhưng 30% khung báo nhãn sai 'fix'.
- D9: Mặt đường trơn: a in [-3, 2] m/s^2, thiếu lái 25%, trượt ngang AR(1) sigma=0.08, nhãn 'fix'.
- D10: Nhận thức suy giảm: nhiễu quan sát x3 (0.15 m, 0.30 m/s), mất phát hiện 10% khung, trễ 100 ms, nhãn 'fix'.
"""

from __future__ import annotations

from typing import Any

import numpy as np

CONDITIONS_EXT: tuple[str, ...] = ("D6", "D7", "D8", "D9", "D10")

D6_EXTRA_DELAY: float = 0.10
D7_OUTAGE_START_RANGE: tuple[float, float] = (0.5, 1.5)
D7_OUTAGE_DUR_RANGE: tuple[float, float] = (15.0, 20.0)
D8_FALSE_FIX_PROB: float = 0.30

D9_A_MIN: float = -3.0
D9_A_MAX: float = 2.0
D9_UNDERSTEER_FACTOR: float = 0.75
D9_SLIP_SIGMA: float = 0.08

D10_POS_NOISE_SIGMA: float = 0.15
D10_VEL_NOISE_SIGMA: float = 0.30
D10_DROPOUT_PROB: float = 0.10
D10_DELAY_STEPS_10HZ: int = 1  # 100 ms = 1 chu kỳ 10 Hz


def is_ext_condition(condition: str) -> bool:
    return condition in CONDITIONS_EXT


def sample_d7_outage(rng: np.random.Generator) -> tuple[float, float]:
    """Lấy mẫu thời điểm bắt đầu và thời lượng mất GNSS dài 15–20 s cho D7."""
    start = float(rng.uniform(*D7_OUTAGE_START_RANGE))
    dur = float(rng.uniform(*D7_OUTAGE_DUR_RANGE))
    return start, start + dur


def get_plant_dynamics_params(condition: str) -> dict[str, float]:
    """Trả về tham số động lực học xe thật (gia tốc, thiếu lái, trượt ngang) theo điều kiện."""
    if condition == "D3":
        return {"understeer": 0.85, "slip_sigma": 0.04, "a_min": -6.0, "a_max": 3.0}
    if condition == "D9":
        return {
            "understeer": D9_UNDERSTEER_FACTOR,
            "slip_sigma": D9_SLIP_SIGMA,
            "a_min": D9_A_MIN,
            "a_max": D9_A_MAX,
        }
    return {"understeer": 1.0, "slip_sigma": 0.0, "a_min": -6.0, "a_max": 3.0}


def corrupt_d8_label(rng: np.random.Generator) -> str:
    """Báo nhãn sai 'fix' với xác suất 30% khi trạng thái thật là 'float'."""
    return "fix" if float(rng.random()) < D8_FALSE_FIX_PROB else "float"


def get_perception_params(condition: str) -> dict[str, Any]:
    """Trả về tham số nhiễu, mất phát hiện và trễ của bộ nhận thức."""
    if condition == "D10":
        return {
            "pos_sigma": D10_POS_NOISE_SIGMA,
            "vel_sigma": D10_VEL_NOISE_SIGMA,
            "dropout_prob": D10_DROPOUT_PROB,
            "delay_steps": D10_DELAY_STEPS_10HZ,
        }
    return {
        "pos_sigma": 0.05,
        "vel_sigma": 0.10,
        "dropout_prob": 0.0,
        "delay_steps": 0,
    }
