"""Scientific validation suite (used by the GUI 'Validation' tab and by pytest).

Every check returns a dict: name, passed, detail.
"""
from __future__ import annotations

import numpy as np

from .fd1d import solve_column, surface_flux
from .mt_1d import MU0, apparent_resistivity, forward_1d, phase_deg

TOL_RHO_1D = 1e-9      # analytic half-space
TOL_FD_PCT = 0.5       # independent FD benchmark
TOL_2D_PCT = 1.0       # 2D vs 1D for laterally uniform models
TOL_2D_DEG = 0.5


def _r(name, ok, detail):
    return {"name": name, "passed": bool(ok), "detail": detail}


def fd_column_impedance(rho, thick, f, cells_per_skin=40):
    """Independent 1D benchmark: fine-mesh finite-volume TM column + flux recovery."""
    rho = np.asarray(rho, float)
    tops = np.cumsum(thick)
    dmin = 503.0 * np.sqrt(rho.min() / f)
    zmax = (tops[-1] if len(tops) else 0) + 8 * 503.0 * np.sqrt(rho[-1] / f)
    hz, z, h = [], 0.0, dmin / cells_per_skin
    h0 = h
    while z < zmax:
        hh = h
        for t in tops:
            if z < t < z + hh:
                hh = t - z
        hz.append(hh)
        z += hh
        h = min(h * 1.02, max(h0, 503.0 * np.sqrt(rho[np.searchsorted(tops, z, side='right')] / f) / cells_per_skin))
    hz = np.array(hz)
    zc = np.cumsum(hz) - hz / 2
    rr = rho[np.searchsorted(tops, zc, side="right")].astype(complex)
    b = np.full(hz.size, 1j * 2 * np.pi * f * MU0)
    u = solve_column(hz, rr, b, 1.0, 0.0)
    return -surface_flux(u, hz, rr, b, 0) / u[0]


def check_halfspace():
    out = []
    f = np.logspace(-4, 5, 37)
    for rho in (1.0, 100.0, 10000.0):
        r = forward_1d([rho], [], f)
        err = np.max(np.abs(r["rho_a"] / rho - 1))
        perr = np.max(np.abs(r["phase"] - 45.0))
        out.append(_r(f"1D half-space rho={rho:g}: rho_a = rho, phase = +45 deg",
                      err < TOL_RHO_1D and perr < 1e-9, f"max |rho_a/rho-1| = {err:.1e}, max |phi-45| = {perr:.1e} deg"))
    return out


def check_layered_vs_fd():
    out = []
    f = np.logspace(-3, 4, 15)
    for name, rho, th in [("conductive layer", [100, 10, 500], [200, 300]),
                          ("resistive layer", [20, 1000, 50], [200, 300]),
                          ("four layers", [50, 500, 5, 1000], [100, 400, 600])]:
        ref = forward_1d(rho, th, f)
        Zfd = np.array([fd_column_impedance(rho, th, fi) for fi in f])
        er = np.max(np.abs(apparent_resistivity(Zfd, f) / ref["rho_a"] - 1)) * 100
        ep = np.max(np.abs(phase_deg(Zfd) - ref["phase"]))
        out.append(_r(f"1D recursion vs independent fine-mesh FD ({name})",
                      er < TOL_FD_PCT and ep < 0.3, f"max d(rho_a) = {er:.3f} %, max d(phi) = {ep:.3f} deg"))
    return out


def check_frequency_behaviour():
    out = []
    f = np.logspace(-4, 6, 201)
    for rho, th in [([100, 10, 500], [200, 300]), ([20, 1000, 50], [200, 300])]:
        r = forward_1d(rho, th, f)
        hi = abs(r["rho_a"][-1] / rho[0] - 1)
        lo = abs(r["rho_a"][0] / rho[-1] - 1)
        out.append(_r(f"Asymptotes rho={rho}: rho_a -> rho_1 (high f), -> rho_N (low f)",
                      hi < 0.01 and lo < 0.05, f"high-f error {hi * 100:.2f} %, low-f error {lo * 100:.2f} %"))
        ok_phase = np.all((r["phase"] > 0) & (r["phase"] < 90))
        out.append(_r(f"Phase in (0, 90) deg for all f, rho={rho}", ok_phase,
                      f"range {r['phase'].min():.2f} .. {r['phase'].max():.2f} deg"))
        # phase > 45 where rho_a decreases with decreasing frequency (Weidelt-type consistency, smooth part)
        lf = np.log10(f)
        slope = np.gradient(np.log10(r["rho_a"]), lf)          # d log rho_a / d log f
        approx = 45.0 * (1.0 + slope)                           # local approximation phi ~ 45(1 + dlogrho/dlogf)
        corr = np.corrcoef(approx, r["phase"])[0, 1]
        out.append(_r(f"Phase consistent with rho_a slope (corr > 0.9), rho={rho}", corr > 0.9,
                      f"correlation(phi, 45(1+dlog rho_a/dlog f)) = {corr:.3f}"))
    return out


def check_2d(quick=True):
    from models.resistivity_2d import Body, Model2D
    from .mt_2d import run_2d
    out = []
    f = np.logspace(-2, 4, 7 if quick else 13)
    for name, rho, th in [("half-space", [100.0], []), ("3-layer", [100.0, 10.0, 500.0], [200.0, 300.0])]:
        m = Model2D(width=3000, depth=1000, dx=100, dz=25, bg_rho=rho, bg_thick=th, stations=[300, 1500, 2700])
        r = run_2d(m, f)
        ref = forward_1d(rho, th, f)
        for mode in ("TE", "TM"):
            ra = apparent_resistivity(r["Z"][mode], f[:, None])
            ph = phase_deg(r["Z"][mode])
            er = np.max(np.abs(ra / ref["rho_a"][:, None] - 1)) * 100
            ep = np.max(np.abs(ph - ref["phase"][:, None]))
            out.append(_r(f"2D {mode} -> 1D for laterally uniform {name}", er < TOL_2D_PCT and ep < TOL_2D_DEG,
                          f"max d(rho_a) = {er:.3f} %, max d(phi) = {ep:.3f} deg"))
        dte = np.max(np.abs(r["Z"]["TE"] / r["Z"]["TM"] - 1))
        out.append(_r(f"TE = TM for 1D {name}", dte < 0.01, f"max |Z_TE/Z_TM - 1| = {dte:.2e}"))

    # vertical contact: TE continuous, TM discontinuous, far field -> local 1D
    st = list(np.arange(500.0, 9501.0, 100.0))
    m = Model2D(width=10000, depth=3000, dx=100, dz=50, bg_rho=[100.0],
                bodies=[Body("rect", 10.0, "right", 5050, 1e9, 0, 1e9)], stations=st)
    fc = np.array([100.0])
    r = run_2d(m, fc)
    te = apparent_resistivity(r["Z"]["TE"][0], 100.0)
    tm = apparent_resistivity(r["Z"]["TM"][0], 100.0)
    jte = np.max(np.abs(np.diff(np.log10(te))))
    jtm = np.max(np.abs(np.diff(np.log10(tm))))
    out.append(_r("Vertical contact: TM rho_a jumps across contact, TE is smoother",
                  jtm > 1.5 * jte, f"max step log10(rho_a): TM {jtm:.3f}, TE {jte:.3f}"))
    far = abs(te[0] / 100 - 1) < 0.02 and abs(te[-1] / 10 - 1) < 0.02 and \
        abs(tm[0] / 100 - 1) < 0.02 and abs(tm[-1] / 10 - 1) < 0.02
    out.append(_r("Vertical contact: far from contact both modes -> local 1D (100 / 10 Ohm.m)", far,
                  f"TE ends {te[0]:.2f}/{te[-1]:.2f}, TM ends {tm[0]:.2f}/{tm[-1]:.2f}"))
    return out


def run_all(include_2d=True):
    res = check_halfspace() + check_layered_vs_fd() + check_frequency_behaviour()
    if include_2d:
        res += check_2d()
    return res
