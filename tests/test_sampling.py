"""Kiểm thử lấy thưa không chồng cửa sổ và không rò rỉ khối hạt giống (TC-10, TC-11)."""

from __future__ import annotations

from sim.common import (
    CALIB_BLOCK_SEEDS,
    CERT_BLOCK_SEEDS,
    D2_CALIB_BLOCKS,
    D2_CERT_BLOCKS,
    OOD_SEEDS,
    RECAL_CALIB_BLOCKS,
    RECAL_CERT_SEEDS,
    RECAL_TEST_SEEDS,
    SIGMA_EST_SEEDS,
    SIGMA_SCN_SEEDS,
    TEST_IN_EXT_SEEDS,
    TEST_SEEDS,
    mark_thinned_cycles,
)


def test_tc10_thinning_non_overlapping() -> None:
    """TC-10: Lấy thưa Delta=3 s -> không có hai chu kỳ nào cùng lượt có cửa sổ [t, t+H] giao nhau."""
    cycles = []
    for seed in (500, 501, 502):
        for step in range(0, 120):
            t = round(step * 0.1, 4)
            # Xen kẽ một số chu kỳ trống để kiểm tra skip trống vẫn giữ khoảng cách >= 3.0 s
            has_ag = 0 if (step in (15, 16, 30, 31, 32, 60)) else 1
            cycles.append({
                "method": "ĐX-1",
                "seed": seed,
                "scn": "S1",
                "cond": "D0",
                "t": t,
                "has_agents": has_ag,
            })

    thinned = mark_thinned_cycles(cycles, every_s=3.0, keep_empty=False, overlapping_bucket=False)
    assert len(thinned) > 0

    by_ep: dict[tuple[str, int, str, str], list[float]] = {}
    for c in thinned:
        assert c["has_agents"] == 1
        assert c["thinned"] == 1
        key = (c["method"], c["seed"], c["scn"], c["cond"])
        by_ep.setdefault(key, []).append(c["t"])

    for key, ts in by_ep.items():
        ts_sorted = sorted(ts)
        for t_prev, t_next in zip(ts_sorted[:-1], ts_sorted[1:]):
            # Cửa sổ [t_prev, t_prev + 3.0] không giao [t_next, t_next + 3.0]
            assert t_next - t_prev >= 3.0 - 1e-9, f"{key}: chồng cửa sổ tại {t_prev} và {t_next}"


def test_tc11_seed_blocks_disjoint() -> None:
    """TC-11: Mọi khối hạt giống (kể cả 700–1399) đôi một giao rỗng (không rò rỉ dữ liệu)."""
    named_blocks: dict[str, set[int]] = {
        "sigma_est_200_249": set(SIGMA_EST_SEEDS),
        "calib_b1_250_299": set(CALIB_BLOCK_SEEDS[0]),
        "calib_b2_300_349": set(CALIB_BLOCK_SEEDS[1]),
        "calib_b3_350_399": set(CALIB_BLOCK_SEEDS[2]),
        "cert_b1_400_449": set(CERT_BLOCK_SEEDS[0]),
        "cert_b2_450_499": set(CERT_BLOCK_SEEDS[1]),
        "cert_b3_600_649": set(CERT_BLOCK_SEEDS[2]),
        "test_in_500_529": set(TEST_IN_EXT_SEEDS),
        "ood_700_709": set(OOD_SEEDS),
        "recal_test_710_719": set(RECAL_TEST_SEEDS),
        "recal_calib_800_949": {s for blk in RECAL_CALIB_BLOCKS for s in blk},
        "recal_cert_950_999": set(RECAL_CERT_SEEDS),
        "recal_cert_extra_1400_1499": set(range(1400, 1500)),
        "e3_real_1500_1604": set(range(1500, 1605)),
        "d2_calib_1000_1149": {s for blk in D2_CALIB_BLOCKS for s in blk},
        "d2_cert_1150_1299": {s for blk in D2_CERT_BLOCKS for s in blk},
        "sigma_scn_1300_1399": set(SIGMA_SCN_SEEDS),
    }

    # Kiểm tra TEST_SEEDS (500-514) là tập con của TEST_IN_EXT_SEEDS (500-529)
    assert set(TEST_SEEDS).issubset(named_blocks["test_in_500_529"])

    names = list(named_blocks.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            inter = named_blocks[names[i]] & named_blocks[names[j]]
            assert not inter, f"Rò rỉ hạt giống giữa {names[i]} và {names[j]}: {sorted(inter)}"
