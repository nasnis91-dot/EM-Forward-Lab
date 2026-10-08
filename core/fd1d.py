"""Finite-volume solver for the 1D (column) problem

    d/dz ( a(z) du/dz ) - b(z) u = 0

TE:  u = Ex, a = 1,   b = i omega mu0 sigma
TM:  u = Hx, a = rho, b = i omega mu0

Used (1) for the Dirichlet side boundaries of the 2D solver and (2) as an
independent numerical benchmark for the analytic impedance recursion.
Nodes z_0..z_N, cells k = 0..N-1 with width hz[k] and constant a[k], b[k].
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import solve_banded


def solve_column(hz, a, b, top=1.0, bottom=0.0) -> np.ndarray:
    hz = np.asarray(hz, float)
    a = np.asarray(a, complex)
    b = np.asarray(b, complex)
    n = hz.size + 1
    ab = np.zeros((3, n), dtype=complex)  # upper, main, lower
    rhs = np.zeros(n, dtype=complex)
    ab[1, 0] = 1.0
    rhs[0] = top
    ab[1, -1] = 1.0
    rhs[-1] = bottom
    cu = a[:-1] / hz[:-1]          # coupling to node above, for nodes 1..n-2
    cd = a[1:] / hz[1:]            # coupling to node below
    bb = b[:-1] * hz[:-1] / 2 + b[1:] * hz[1:] / 2
    idx = np.arange(1, n - 1)
    ab[1, idx] = -(cu + cd) - bb
    ab[2, idx - 1] = cu            # lower diagonal: A[i, i-1]
    ab[0, idx + 1] = cd            # upper diagonal: A[i, i+1]
    return solve_banded((1, 1), ab, rhs)


def surface_flux(u, hz, a, b, k0: int) -> complex:
    """Recover (a du/dz) at node k0 from the half control volume BELOW it."""
    return a[k0] / hz[k0] * (u[k0 + 1] - u[k0]) - b[k0] * hz[k0] / 2 * u[k0]
