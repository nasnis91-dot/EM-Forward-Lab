"""
Genuine 2D plane-wave EM forward solver (finite-volume / finite-difference, SciPy sparse).

Strike direction = x. Profile = y. Depth z positive down. Time dependence exp(+i w t).

TE (E-polarisation, Zxy):   d2Ex/dy2 + d2Ex/dz2 - i w mu0 sigma Ex = 0        (air included)
                            Hy = -(1 / (i w mu0)) dEx/dz,     Z_TE = Ex / Hy
TM (H-polarisation, Zyx):   d/dy(rho dHx/dy) + d/dz(rho dHx/dz) - i w mu0 Hx = 0   (earth only)
                            Ey = rho dHx/dz,                  Z_TM = -Ey / Hx  (sign flipped so that
                                                               both modes give +45 deg on a half-space)

Discretisation: node-based finite volumes on a tensor mesh, cell-constant rho. Coefficients use
area-weighted averages of the 4 cells around each node (standard 5-point stencil).

Boundary conditions (Dirichlet):
  TE: Ex = 1 at the top of the air layer; left/right edges = 1D solutions of the edge columns
      (same mesh, same discretisation); bottom = linear interpolation of the edge-column values.
  TM: Hx = 1 on the earth surface (Hx is constant in a non-conducting air); edges as for TE.
  The mesh is padded with geometrically growing cells to >= 5 skin depths so that the
  Dirichlet values are taken where the structure is effectively 1D.

Surface fields: (a du/dz) at z = 0 is recovered from the discrete balance over the half control
volume just below each surface node (flux recovery), then interpolated to the stations.

A frequency-adaptive mesh is built for every frequency: cells near the surface (and inside
conductors that the field actually reaches) are <= skin depth / (6 * refine).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import spsolve

from .fd1d import solve_column
from .mt_1d import MU0
from .skin_depth import skin_depth

SIGMA_AIR = 1e-10
MAX_NODES = 250_000
GROW_CORE = 1.25
GROW_PAD = 1.3
PAD_SKIN = 5.0
CELLS_PER_SKIN = 10.0


@dataclass
class Mesh:
    hy: np.ndarray        # all horizontal cells (padding + core + padding)
    hz: np.ndarray        # vertical cells, earth only, top -> bottom
    hz_air: np.ndarray    # air cells, surface -> up
    y0: float             # y coordinate of the first node

    @property
    def y_nodes(self):
        return self.y0 + np.concatenate([[0.0], np.cumsum(self.hy)])

    @property
    def z_nodes(self):
        return np.concatenate([[0.0], np.cumsum(self.hz)])

    def cell_centers(self):
        yn, zn = self.y_nodes, self.z_nodes
        return 0.5 * (yn[1:] + yn[:-1]), 0.5 * (zn[1:] + zn[:-1])


# ----------------------------------------------------------------------------- geometry helpers
def _breakpoints(model):
    zb = list(np.cumsum(model.bg_thick)) + [model.depth]
    yb = []
    extra = getattr(model, "extra_breaks", None)          # used by the inversion grid model
    if extra is not None:
        yb += list(extra[0])
        zb += list(extra[1])
    for b in model.bodies:
        if b.kind == "polygon":
            yb += [p[0] for p in b.points]
            zb += [p[1] for p in b.points]
        else:
            yb += [b.x0, b.x1]
            zb += [b.z0, b.z1]
    zb = np.unique([z for z in zb if 0 < z <= model.depth])
    yb = np.unique([y for y in yb if 0 < y < model.width])
    return yb, zb


class _DepthProfile:
    """rho_min(z) and rho_max(z) across the profile, sampled once per run."""

    def __init__(self, model):
        _, zb = _breakpoints(model)
        step = min(model.dz / 4.0, model.depth / 200.0)
        edges = np.unique(np.concatenate([np.arange(0.0, model.depth, step), zb, [model.depth]]))
        self.edges = edges
        zc = 0.5 * (edges[1:] + edges[:-1])
        nys = int(min(800, np.ceil(model.width / (model.dx / 2.0)) + 1))
        ys = np.linspace(0.0, model.width, nys)
        Y, Zc = np.meshgrid(ys, zc)
        r = model.rho_at(Y, Zc)
        self.rmin = r.min(axis=1)
        self.rmax = r.max(axis=1)
        bot = model.rho_at(ys, np.full_like(ys, model.depth))
        self.bottom_max = float(bot.max())
        self.bottom_min = float(bot.min())
        self.surface_min = float(self.rmin[0])

    def index(self, z):
        return np.clip(np.searchsorted(self.edges, z, side="right") - 1, 0, self.rmin.size - 1)


def _vertical_cells(model, prof: _DepthProfile, f, refine):
    _, zb = _breakpoints(model)
    dzmax = model.dz / refine
    # allowed cell size on each sampling interval
    dmin = skin_depth(prof.rmin, f)
    dmax = skin_depth(prof.rmax, f)
    att = np.concatenate([[0.0], np.cumsum(np.diff(prof.edges) / dmax)])[:-1]  # attenuation at interval top
    allowed = np.where(att < 6.0, np.minimum(dzmax, dmin / (CELLS_PER_SKIN * refine)), dzmax)

    cells = []
    z = 0.0
    h_prev = None
    bi = 0
    while z < model.depth - 1e-9:
        i0 = prof.index(z)
        cand = allowed[i0] if h_prev is None else min(h_prev * GROW_CORE, dzmax)
        cand = min(cand, allowed[i0])
        i1 = prof.index(z + cand)
        h = min(cand, allowed[i0:i1 + 1].min())
        while bi < zb.size and zb[bi] <= z + 1e-9:
            bi += 1
        if bi < zb.size and z + h > zb[bi] - 1e-9:
            h = zb[bi] - z
        elif z + h > model.depth:
            h = model.depth - z
        cells.append(h)
        z += h
        h_prev = h
    target = model.depth + PAD_SKIN * skin_depth(prof.bottom_max, f)
    hcap = skin_depth(prof.bottom_min, f) / (CELLS_PER_SKIN * refine)       # resolve the first 2 skin depths
    zcap = model.depth + 2.0 * skin_depth(prof.bottom_max, f)
    h = cells[-1]
    while z < target:
        h = h * GROW_PAD if z > zcap else min(h * GROW_PAD, max(hcap, h))
        cells.append(h)
        z += h
    return np.array(cells)


def _horizontal_cells(model, f, refine, rho_max):
    yb, _ = _breakpoints(model)
    n = max(2, int(np.ceil(model.width / (model.dx / refine))))
    nodes = np.linspace(0.0, model.width, n + 1)
    h0 = model.width / n
    for y in yb:                                         # snap nearest node onto body edges
        k = int(np.argmin(np.abs(nodes - y)))
        if 0 < k < n:
            nodes[k] = y
    nodes = np.unique(nodes)
    core = np.diff(nodes)
    core = core[core > 1e-6 * h0]
    pad = []
    h, ext = h0, 0.0
    target = PAD_SKIN * skin_depth(rho_max, f)
    while ext < target or len(pad) < 4:
        h *= GROW_PAD
        pad.append(h)
        ext += h
    pad = np.array(pad)
    return np.concatenate([pad[::-1], core, pad]), -ext


def _air_cells(h0, height):
    cells, z, h = [], 0.0, h0
    while z < height:
        cells.append(h)
        z += h
        h *= GROW_PAD
    return np.array(cells)


def build_mesh(model, f, refine=1.0, prof=None) -> Mesh:
    prof = prof or _DepthProfile(model)
    rho_max = float(model.all_rho().max())
    hz = _vertical_cells(model, prof, f, refine)
    hy, y0 = _horizontal_cells(model, f, refine, rho_max)
    air_h = max(PAD_SKIN * skin_depth(rho_max, f), model.width)
    return Mesh(hy=hy, hz=hz, hz_air=_air_cells(hz[0], air_h), y0=y0)


# ----------------------------------------------------------------------------- linear algebra
def _assemble(hy, hz, a, b, top, left, right, bottom):
    """Assemble div(a grad u) - b u = 0 (5-point finite volumes) with Dirichlet values on all edges.

    Returns A (interior x interior), rhs, U (with boundary values filled), and the interior index map.
    """
    ny, nz = hy.size + 1, hz.size + 1
    J, I = np.meshgrid(np.arange(1, nz - 1), np.arange(1, ny - 1), indexing="ij")
    J, I = J.ravel(), I.ravel()
    hyl, hyr = hy[I - 1], hy[I]
    hzu, hzd = hz[J - 1], hz[J]
    aNW, aNE, aSW, aSE = a[J - 1, I - 1], a[J - 1, I], a[J, I - 1], a[J, I]
    bNW, bNE, bSW, bSE = b[J - 1, I - 1], b[J - 1, I], b[J, I - 1], b[J, I]
    cE = (aNE * hzu + aSE * hzd) / (2 * hyr)
    cW = (aNW * hzu + aSW * hzd) / (2 * hyl)
    cS = (aSW * hyl + aSE * hyr) / (2 * hzd)
    cN = (aNW * hyl + aNE * hyr) / (2 * hzu)
    B = (bNW * hyl * hzu + bNE * hyr * hzu + bSW * hyl * hzd + bSE * hyr * hzd) / 4.0
    diag = -(cE + cW + cS + cN) - B

    U = np.zeros((nz, ny), dtype=complex)
    U[0, :] = top
    U[-1, :] = bottom
    U[:, 0] = left
    U[:, -1] = right

    nyi = ny - 2
    p = (J - 1) * nyi + (I - 1)
    rows, cols, vals = [p], [p], [diag]
    rhs = np.zeros(p.size, dtype=complex)
    for c, dj, di in ((cE, 0, 1), (cW, 0, -1), (cS, 1, 0), (cN, -1, 0)):
        jn, in_ = J + dj, I + di
        interior = (jn > 0) & (jn < nz - 1) & (in_ > 0) & (in_ < ny - 1)
        rows.append(p[interior])
        cols.append((jn[interior] - 1) * nyi + (in_[interior] - 1))
        vals.append(c[interior])
        bd = ~interior
        np.subtract.at(rhs, p[bd], c[bd] * U[jn[bd], in_[bd]])
    A = sp.csc_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                      shape=(p.size, p.size))
    return A, rhs, U


def _solve_fv(hy, hz, a, b, top, left, right, bottom):
    """Solve div(a grad u) - b u = 0 with Dirichlet values on all four edges."""
    A, rhs, U = _assemble(hy, hz, a, b, top, left, right, bottom)
    nz, ny = U.shape
    x = spsolve(A, rhs)
    res = np.linalg.norm(A @ x - rhs) / max(np.linalg.norm(rhs), 1e-300)
    U[1:-1, 1:-1] = x.reshape(nz - 2, ny - 2)
    return U, float(res)


def _surface_flux(U, hy, hz, a, b, js):
    """(a du/dz) at surface nodes 1..ny-2 by flux recovery on the half volume below row js."""
    i = np.arange(1, hy.size)
    hyl, hyr, h = hy[i - 1], hy[i], hz[js]
    u0, ud = U[js, i], U[js + 1, i]
    al, ar, bl, br = a[js, i - 1], a[js, i], b[js, i - 1], b[js, i]
    Bf = (al * hyl + ar * hyr) / (2 * h) * (ud - u0)
    Lf = al * (h / 2) / hyl * (U[js, i - 1] - u0)
    Rf = ar * (h / 2) / hyr * (U[js, i + 1] - u0)
    Af = (bl * hyl + br * hyr) / 2 * (h / 2) * u0
    w = (hyl + hyr) / 2
    return (Bf + Lf + Rf - Af) / w, u0


def _interp_c(x, xp, fp):
    return np.interp(x, xp, fp.real) + 1j * np.interp(x, xp, fp.imag)


def solve_frequency(model, f, mode, refine=1.0, prof=None, mesh=None):
    """Return (Z at stations, diagnostics dict, mesh)."""
    prof = prof or _DepthProfile(model)
    mesh = mesh or build_mesh(model, f, refine, prof)
    w = 2 * np.pi * f
    yc, zc = mesh.cell_centers()
    Y, Zc = np.meshgrid(yc, zc)
    rho_e = model.rho_at(Y, Zc)                  # (nz_earth, ny) cells
    ny_n = mesh.hy.size + 1
    st = np.asarray(model.stations, float)
    t0 = time.perf_counter()

    if mode == "TE":
        hz = np.concatenate([mesh.hz_air[::-1], mesh.hz])
        sig = np.vstack([np.full((mesh.hz_air.size, mesh.hy.size), SIGMA_AIR), 1.0 / rho_e])
        a = np.ones_like(sig, dtype=complex)
        b = 1j * w * MU0 * sig
        js = mesh.hz_air.size
    elif mode == "TM":
        hz = mesh.hz
        a = rho_e.astype(complex)
        b = np.full_like(a, 1j * w * MU0)
        js = 0
    else:
        raise ValueError("mode must be 'TE' or 'TM'")

    nodes = (hz.size + 1) * ny_n
    if nodes > MAX_NODES:
        raise ValueError(f"Mesh too large at f={f:g} Hz ({nodes} nodes > {MAX_NODES}). "
                         "Increase dx/dz, reduce the model size or the refinement factor.")
    left = solve_column(hz, a[:, 0], b[:, 0], 1.0, 0.0)
    right = solve_column(hz, a[:, -1], b[:, -1], 1.0, 0.0)
    yn = mesh.y_nodes
    bottom = left[-1] + (right[-1] - left[-1]) * (yn - yn[0]) / (yn[-1] - yn[0])
    U, res = _solve_fv(mesh.hy, hz, a, b, 1.0, left, right, bottom)
    flux, u0 = _surface_flux(U, mesh.hy, hz, a, b, js)
    ys = yn[1:-1]
    fl, uu = _interp_c(st, ys, flux), _interp_c(st, ys, u0)
    Z = (-1j * w * MU0 * uu / fl) if mode == "TE" else (-fl / uu)
    dt = time.perf_counter() - t0

    d_surf = skin_depth(prof.surface_min, f)
    core_dx = mesh.hy[(mesh.y_nodes[:-1] >= 0) & (mesh.y_nodes[1:] <= model.width)]
    diag = {"freq": f, "mode": mode, "nodes": int(nodes), "ny": int(ny_n), "nz": int(hz.size + 1),
            "residual": res, "time_s": dt,
            "dz0_over_delta": float(mesh.hz[0] / d_surf),
            "dx_over_delta": float(core_dx.max() / d_surf) if core_dx.size else np.nan,
            "pad_lateral_m": float(-mesh.y0), "depth_extent_m": float(mesh.hz.sum()),
            "air_m": float(mesh.hz_air.sum())}
    return Z, diag, mesh


def run_2d(model, freqs, modes=("TE", "TM"), refine=1.0, progress=None, cancelled=None):
    """Full multi-frequency, multi-mode run.

    Returns dict: freq (nf), stations (ns), Z[mode] (nf, ns) complex, diagnostics list.
    """
    errs = model.validate()
    if errs:
        raise ValueError("; ".join(errs))
    freqs = np.atleast_1d(np.asarray(freqs, float))
    prof = _DepthProfile(model)
    out = {"freq": freqs, "stations": np.asarray(model.stations, float), "Z": {}, "diagnostics": [],
           "refine": refine, "modes": list(modes)}
    for m in modes:
        out["Z"][m] = np.zeros((freqs.size, len(model.stations)), complex)
    total = freqs.size * len(modes)
    k = 0
    for i, f in enumerate(freqs):
        mesh = build_mesh(model, f, refine, prof)
        for m in modes:
            if cancelled and cancelled():
                raise RuntimeError("Simulation cancelled by user.")
            Z, d, _ = solve_frequency(model, f, m, refine, prof, mesh)
            out["Z"][m][i] = Z
            out["diagnostics"].append(d)
            k += 1
            if progress:
                progress(k, total, f"{m}  f = {f:.4g} Hz  ({d['nodes']} nodes, {d['time_s']:.2f} s)")
    return out


def convergence_check(model, freqs, refine=1.0, factor=1.6, modes=("TE", "TM"), progress=None):
    """Compare solutions on mesh `refine` and `refine*factor` (max relative rho_a and phase change)."""
    from .mt_1d import apparent_resistivity, phase_deg
    a = run_2d(model, freqs, modes, refine, progress)
    b = run_2d(model, freqs, modes, refine * factor, progress)
    rows = []
    for m in modes:
        for i, f in enumerate(a["freq"]):
            ra, rb = apparent_resistivity(a["Z"][m][i], f), apparent_resistivity(b["Z"][m][i], f)
            pa, pb = phase_deg(a["Z"][m][i]), phase_deg(b["Z"][m][i])
            rows.append({"mode": m, "freq": f, "max_drho_pct": float(np.max(np.abs(ra / rb - 1)) * 100),
                         "max_dphase_deg": float(np.max(np.abs(pa - pb)))})
    return rows
