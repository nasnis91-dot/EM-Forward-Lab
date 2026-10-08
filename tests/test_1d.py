import numpy as np
import pytest
from core.mt_1d import forward_1d, impedance_1d, bostick
from core.skin_depth import skin_depth, skin_depth_approx
from core.validation import check_halfspace, check_layered_vs_fd


def test_halfspace_checks():
    assert all(r["passed"] for r in check_halfspace())


def test_layered_against_fd_benchmark():
    assert all(r["passed"] for r in check_layered_vs_fd())


def test_thin_layer_limit_equals_halfspace():
    f = np.logspace(-2, 3, 11)
    a = forward_1d([100, 100, 100], [50, 70], f)["rho_a"]
    assert np.allclose(a, 100, rtol=1e-12)


def test_extreme_values_finite():
    f = np.logspace(-5, 6, 50)
    Z = impedance_1d([1e5, 0.1, 1e4], [1e4, 10], f)
    assert np.all(np.isfinite(Z))


def test_invalid_inputs():
    with pytest.raises(ValueError):
        impedance_1d([100, -1], [10], [1.0])
    with pytest.raises(ValueError):
        impedance_1d([100, 10], [], [1.0])
    with pytest.raises(ValueError):
        impedance_1d([100], [], [0.0])


def test_skin_depth():
    assert abs(skin_depth(100, 1) - 5032.9) < 0.5
    assert np.allclose(skin_depth(100, 1), skin_depth_approx(100, 1), rtol=1e-3)


def test_bostick_halfspace():
    f = np.logspace(-2, 2, 5)
    r = forward_1d([100], [], f)
    d, rb = bostick(r["rho_a"], r["phase"], f)
    assert np.allclose(rb, 100, rtol=1e-10)
