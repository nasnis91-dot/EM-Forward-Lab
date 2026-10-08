"""
1D plane-wave electromagnetic forward modelling (MT / AMT / RMT / VLF-R far field).

Conventions used throughout EM-Forward Lab
------------------------------------------
* Time dependence:            exp(+i*omega*t)
* Quasi-static approximation: displacement currents neglected (sigma >> omega*eps)
* Coordinates:                x = strike / north, y = east, z = positive DOWN
* Impedance:                  Z = Ex / Hy  [ohm]   (TE / Zxy sense)
* With exp(+i omega t) a homogeneous half-space gives arg(Z) = +45 deg.

Layer j has conductivity sigma_j = 1/rho_j and thickness h_j; the last layer is
a half-space.  Intrinsic quantities:

    k_j   = sqrt(i * omega * mu0 * sigma_j)          (Re k_j > 0)
    Z0_j  = sqrt(i * omega * mu0 / sigma_j) = i*omega*mu0 / k_j

Surface impedance by upward recursion (bottom half-space -> surface):

    Z_j = Z0_j * (Z_{j+1} + Z0_j tanh(k_j h_j)) / (Z0_j + Z_{j+1} tanh(k_j h_j))

    rho_a = |Z|^2 / (omega mu0),   phi = arg(Z)
"""
from __future__ import annotations

import numpy as np

MU0 = 4.0e-7 * np.pi


def _stable_tanh(x: np.ndarray) -> np.ndarray:
    """tanh for complex x with Re(x) >= 0 that never overflows."""
    e = np.exp(-2.0 * x)
    return (1.0 - e) / (1.0 + e)


def validate_layers(rho, thick) -> list[str]:
    """Return a list of human-readable problems (empty list = valid)."""
    errs = []
    rho = np.asarray(rho, dtype=float)
    thick = np.asarray(thick, dtype=float)
    if rho.size < 1:
        errs.append("At least one layer (the half-space) is required.")
    if thick.size != max(rho.size - 1, 0):
        errs.append("Need exactly (n_layers - 1) thicknesses; the last layer is a half-space.")
    if np.any(~np.isfinite(rho)) or np.any(rho <= 0):
        errs.append("All resistivities must be finite and > 0 Ohm.m.")
    if np.any(~np.isfinite(thick)) or np.any(thick <= 0):
        errs.append("All layer thicknesses must be finite and > 0 m.")
    return errs


def validate_freqs(freqs) -> list[str]:
    f = np.atleast_1d(np.asarray(freqs, dtype=float))
    errs = []
    if f.size == 0:
        errs.append("No frequencies defined.")
    if np.any(~np.isfinite(f)) or np.any(f <= 0):
        errs.append("All frequencies must be finite and > 0 Hz.")
    if np.any(f > 1e7):
        errs.append("Frequencies above 10 MHz violate the quasi-static assumption for most rocks.")
    return errs


def impedance_1d(rho, thick, freqs) -> np.ndarray:
    """Complex surface impedance Z(f) [ohm] for a layered earth (exp(+i w t))."""
    rho = np.asarray(rho, dtype=float)
    thick = np.asarray(thick, dtype=float)
    errs = validate_layers(rho, thick) + validate_freqs(freqs)
    if errs:
        raise ValueError("; ".join(errs))
    f = np.atleast_1d(np.asarray(freqs, dtype=float))
    w = 2.0 * np.pi * f
    sigma = 1.0 / rho
    k = np.sqrt(1j * w[:, None] * MU0 * sigma[None, :])        # (nf, nl), Re>0
    z0 = 1j * w[:, None] * MU0 / k                                # intrinsic impedances
    Z = z0[:, -1].copy()
    for j in range(rho.size - 2, -1, -1):
        t = _stable_tanh(k[:, j] * thick[j])
        Z = z0[:, j] * (Z + z0[:, j] * t) / (z0[:, j] + Z * t)
    return Z


def apparent_resistivity(Z, freqs) -> np.ndarray:
    w = 2.0 * np.pi * np.asarray(freqs, dtype=float)
    return np.abs(Z) ** 2 / (MU0 * w)


def phase_deg(Z) -> np.ndarray:
    return np.degrees(np.angle(Z))


def forward_1d(rho, thick, freqs) -> dict:
    """Convenience wrapper returning everything a plot/table needs."""
    f = np.atleast_1d(np.asarray(freqs, dtype=float))
    Z = impedance_1d(rho, thick, f)
    return {"freq": f, "Z": Z, "rho_a": apparent_resistivity(Z, f), "phase": phase_deg(Z)}


def bostick(rho_a, phase_degrees, freqs):
    """Niblett-Bostick approximate depth-resistivity transform.

    D = sqrt(rho_a / (omega mu0)),  rho_B = rho_a * (pi / (2 phi) - 1)   (phi in rad)
    Only an approximate imaging tool, NOT an inversion.
    """
    w = 2.0 * np.pi * np.asarray(freqs, dtype=float)
    phi = np.radians(np.asarray(phase_degrees, dtype=float))
    depth = np.sqrt(np.asarray(rho_a) / (w * MU0))
    with np.errstate(divide="ignore", invalid="ignore"):
        rho_b = np.asarray(rho_a) * (np.pi / (2.0 * phi) - 1.0)
    return depth, rho_b
