"""Electromagnetic skin depth for a HOMOGENEOUS medium (quasi-static).

delta = sqrt(2 / (omega mu0 sigma)) = sqrt(2 rho / (omega mu0)) ~= 503 * sqrt(rho / f)  [m]

It is the depth at which the amplitude of a plane wave decays to 1/e (~37 %).
In a layered earth it is only an indicative 'investigation depth'.
"""
import numpy as np

from .mt_1d import MU0


def skin_depth(rho, freq):
    rho = np.asarray(rho, dtype=float)
    f = np.asarray(freq, dtype=float)
    return np.sqrt(2.0 * rho / (2.0 * np.pi * f * MU0))


def skin_depth_approx(rho, freq):
    """The textbook 503*sqrt(rho/f) form (identical to 3 significant figures)."""
    return 503.0 * np.sqrt(np.asarray(rho, float) / np.asarray(freq, float))
