"""TC-41a..e — kiểm thử bộ sinh và điểm số Mục 4.1 (SPEC §10.8)."""

import zlib

import numpy as np
import pytest

from num41.gen import (
    DEFAULT_PARAMS,
    H,
    apply_rho,
    make_rng,
    rho_direction,
    sample,
    sample_groups,
    with_params,
)
from num41.scores import rho_emp, scores, thresholds


def _rng(rep=0, split=0, cell=0):
    return make_rng("TEST", cell, rep, split)


# ---------- TC-41a: R ≤ A + E (Mệnh đề 3) ----------
@pytest.mark.parametrize(
    "kind,arg",
    [
        ("sigma", 0.1),
        ("sigma", 0.5),
        ("sigma", 1.0),
        ("rho", 0.0),
        ("rho", 0.5),
        ("rho", 0.9),
        ("rho", 1.0),
        ("groups", None),
        ("per_step", 0.3),
    ],
)
def test_tc41a_triangle(kind, arg):
    rng = _rng(cell=zlib.crc32(f"{kind}{arg}".encode()) % 1000)
    n = 100_000
    if kind == "sigma":
        b = sample(n, rng, sigma_loc=arg)
    elif kind == "rho":
        b = sample(n, rng, sigma_loc=0.3, rho=arg)
    elif kind == "groups":
        b = sample_groups(n, rng)
    else:
        b = sample(n, rng, sigma_loc=arg, params=with_params(motion="per_step"))
    s = scores(b)
    assert np.all(s["R"] <= s["A"] + s["E"] + 1e-9)


# ---------- TC-41b: không nhiễu → R = A = E = 0 ----------
def test_tc41b_zero_noise():
    p0 = with_params(sigma_trk=0.0, delay_max=0.0, sigma_omega=0.0, sigma_acc=0.0)
    b = sample(2000, _rng(), sigma_loc=0.0, params=p0)
    s = scores(b)
    for k in ("R", "A", "E"):
        assert np.max(np.abs(s[k])) <= 1e-12, k


# ---------- TC-41c: tất định ----------
def test_tc41c_deterministic():
    b1 = sample(500, make_rng("N2", 3, 7, 1), sigma_loc=0.3, rho=0.5)
    b2 = sample(500, make_rng("N2", 3, 7, 1), sigma_loc=0.3, rho=0.5)
    for f in ("p_hat", "p", "o_hat", "o"):
        assert np.array_equal(getattr(b1, f), getattr(b2, f))
    g1 = sample_groups(500, make_rng("N3", 0, 2, 0))
    g2 = sample_groups(500, make_rng("N3", 0, 2, 0))
    assert np.array_equal(g1.group, g2.group) and np.array_equal(g1.p, g2.p)
    # Khác split → khác dữ liệu
    b3 = sample(500, make_rng("N2", 3, 7, 0), sigma_loc=0.3, rho=0.5)
    assert not np.array_equal(b1.p, b3.p)


# ---------- TC-41d: điểm số gần như không trùng ----------
def test_tc41d_ties():
    s = scores(sample(100_000, _rng(split=1), sigma_loc=0.3))
    for k in ("R", "A", "E"):
        x = s[k]
        frac = 1.0 - np.unique(x).size / x.size
        assert frac < 1e-6, (k, frac)


# ---------- TC-41e: chế độ ρ ----------
def test_tc41e_rho_mode():
    n = 20_000
    base = sample(n, _rng(cell=5), sigma_loc=0.3)
    e = base.p - base.p_hat

    # ρ = 0 cho e′ = e
    assert np.array_equal(apply_rho(e, base.p_hat, base.o_hat, base.o, 0.0), e)

    g, _ = rho_direction(base.p_hat, base.o_hat, base.o)
    cos_means, remp = [], []
    for rho in (0.0, 0.3, 0.6, 0.9, 1.0):
        e2 = apply_rho(e, base.p_hat, base.o_hat, base.o, rho)
        # giữ nguyên độ lớn
        assert np.allclose(np.linalg.norm(e2, axis=-1), np.linalg.norm(e, axis=-1), atol=1e-12)
        nrm = np.linalg.norm(e2, axis=-1)
        cos = np.sum(e2 * g, axis=-1) / np.maximum(nrm, 1e-300)
        cos_means.append(float(np.mean(cos)))
        b2 = sample(n, _rng(cell=5), sigma_loc=0.3, rho=rho)
        remp.append(rho_emp(b2))
    assert np.all(np.diff(cos_means) > 0), cos_means
    assert np.all(np.diff(remp) > 0), remp

    # Cùng rng: chế độ ρ chỉ đổi hướng e, không đổi tác nhân hay kế hoạch
    b_rho = sample(n, _rng(cell=5), sigma_loc=0.3, rho=0.6)
    assert np.array_equal(b_rho.o, base.o) and np.array_equal(b_rho.p_hat, base.p_hat)


# ---------- Kiểm tra phụ ----------
def test_shapes_and_params():
    b = sample(10, _rng(), sigma_loc=0.2)
    assert b.p.shape == (10, H, 2) and b.o.shape == (10, H, 2)
    assert DEFAULT_PARAMS.motion == "const"
    with pytest.raises(ValueError):
        sample(10, _rng(), params=with_params(motion="xx"))
    with pytest.raises(ValueError):
        sample(10, _rng(), rho=1.5)


def test_thresholds_order():
    cal = scores(sample(1000, _rng(cell=9), sigma_loc=0.3))
    t = thresholds(cal, 0.1)
    assert t["B1"] <= t["B4"]
    assert t["DX"] <= t["B3"]
