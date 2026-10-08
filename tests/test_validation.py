from core.validation import check_frequency_behaviour
from core.noise import add_impedance_noise
import numpy as np


def test_frequency_behaviour():
    assert all(r["passed"] for r in check_frequency_behaviour())


def test_noise_statistics():
    Z = np.full(200000, 1 + 1j)
    Zn = add_impedance_noise(Z, 0.05, seed=1)
    rel = np.abs(Zn / Z - 1)
    assert abs(np.sqrt(np.mean(rel ** 2)) - 0.05) < 1e-3
    assert np.array_equal(add_impedance_noise(Z[:10], 0.05, 3), add_impedance_noise(Z[:10], 0.05, 3))
