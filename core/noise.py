"""Synthetic noise models (documented, reproducible).

All methods act on the complex impedance Z(f) and return the 'observed' impedance, the
1-sigma error that is REPORTED with the data (written to EDI variances and used by the inversion),
and a mask of outliers.

Methods (p = relative level, e.g. 0.05 = 5 %):

gauss_z          Z_obs = Z (1 + p (n_r + i n_i)/sqrt2),  n ~ N(0,1)
                 -> |Z_obs/Z - 1| has RMS p;  sd(rho_a)/rho_a ~ 2p/sqrt2 = sqrt2 p,  sd(phi) ~ p/sqrt2 rad
gauss_rho_phase  rho_obs = rho_a (1 + p n1),  phi_obs = phi + s_phi n2   (s_phi in degrees)
                 Z_obs rebuilt from rho_obs, phi_obs
uniform_z        Z_obs = Z (1 + p (u_r + i u_i)),  u ~ U(-1, 1)   (bounded noise)
gauss_outliers   gauss_z, plus a fraction q of frequencies whose error is multiplied by k
                 (outliers are NOT reflected in the reported errors - that is the point of the exercise)

Reported error  sd_Z = standard deviation of each component (Re, Im) of Z  (EDI 'VAR' = sd_Z^2):
                gauss_z: p|Z|/sqrt2 ; uniform_z: p|Z|/sqrt3 ; gauss_rho_phase: |Z| max(p/2, s_phi[rad])
                then sd_Z = max(sd_Z, floor * |Z|)   ('floor' = error floor, e.g. 0.02 = 2 %).
Propagation:    sd(rho_a)/rho_a = 2 sd_Z/|Z| ,  sd(phi) = sd_Z/|Z|  [rad].
"""
from __future__ import annotations

import numpy as np

from .mt_1d import MU0

NOISE_METHODS = ["gauss_z", "gauss_rho_phase", "uniform_z", "gauss_outliers"]

# kept for backwards compatibility / quick presets
NOISE_LEVELS = {"Noise-free": 0.0, "1 %": 0.01, "3 %": 0.03, "5 %": 0.05, "10 %": 0.10}


def add_impedance_noise(Z, level: float, seed: int = 12345):
    Z = np.asarray(Z, dtype=complex)
    if level <= 0:
        return Z.copy()
    rng = np.random.default_rng(seed)
    n = (rng.standard_normal(Z.shape) + 1j * rng.standard_normal(Z.shape)) / np.sqrt(2.0)
    return Z * (1.0 + level * n)


def apply_noise(Z, freqs, method="gauss_z", level=0.05, seed=12345, phase_sd_deg=None,
                outlier_frac=0.1, outlier_factor=5.0, floor=0.0):
    """Return dict(Zobs, Zerr, outlier, method, ...). Z may be 1-D (nf) or 2-D (nf, ns)."""
    Z = np.asarray(Z, complex)
    f = np.asarray(freqs, float).reshape((-1,) + (1,) * (Z.ndim - 1))
    rng = np.random.default_rng(seed)
    absZ = np.abs(Z)
    outl = np.zeros(Z.shape, bool)
    if method not in NOISE_METHODS:
        raise ValueError(f"Unknown noise method '{method}'.")
    if level < 0 or level > 1.0:
        raise ValueError("Noise level must be between 0 and 100 %.")

    if method in ("gauss_z", "gauss_outliers"):
        n = (rng.standard_normal(Z.shape) + 1j * rng.standard_normal(Z.shape)) / np.sqrt(2.0)
        if method == "gauss_outliers" and outlier_frac > 0:
            k = int(round(outlier_frac * Z.shape[0]))
            if k > 0:
                for col in np.ndindex(Z.shape[1:]):
                    idx = rng.choice(Z.shape[0], size=k, replace=False)
                    sl = (idx,) + col
                    outl[sl] = True
            n = np.where(outl, n * outlier_factor, n)
        Zobs = Z * (1.0 + level * n)
        sd = level * absZ / np.sqrt(2.0)                 # sd of each component (Re, Im) of Z
    elif method == "uniform_z":
        u = rng.uniform(-1, 1, Z.shape) + 1j * rng.uniform(-1, 1, Z.shape)
        Zobs = Z * (1.0 + level * u)
        sd = level * absZ / np.sqrt(3.0)                 # sd of U(-p, p) per component
    else:  # gauss_rho_phase
        s_phi = np.degrees(level / 2.0) if phase_sd_deg is None else float(phase_sd_deg)
        w = 2 * np.pi * f
        rho = absZ ** 2 / (MU0 * w)
        phi = np.degrees(np.angle(Z))
        rho_o = rho * np.clip(1.0 + level * rng.standard_normal(Z.shape), 0.05, None)
        phi_o = phi + s_phi * rng.standard_normal(Z.shape)
        Zobs = np.sqrt(rho_o * MU0 * w) * np.exp(1j * np.radians(phi_o))
        sd = absZ * np.maximum(level / 2.0, np.radians(s_phi))
    sd = np.maximum(sd, floor * absZ)
    return {"Zobs": Zobs, "Zerr": sd, "outlier": outl, "method": method, "level": level, "seed": seed,
            "phase_sd_deg": phase_sd_deg, "outlier_frac": outlier_frac, "outlier_factor": outlier_factor,
            "floor": floor}


def impedance_std(Z, level: float):
    """1-sigma error per impedance component implied by gauss_z."""
    return level * np.abs(np.asarray(Z)) / np.sqrt(2.0)


def rho_phase_errors(Z, Zerr):
    """Propagate |Z| errors to apparent resistivity (relative) and phase (degrees).

    rho_a ~ |Z|^2  ->  sd(rho)/rho = 2 sd(Z)/|Z|;   sd(phi) = sd(Z)/|Z|  [rad]
    """
    r = np.asarray(Zerr, float) / np.abs(np.asarray(Z))
    return 2.0 * r, np.degrees(r)
