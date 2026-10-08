"""
Simple 2D Occam inversion (TE and/or TM) for teaching.

Model     m = log10(rho) on a coarse block grid (columns between stations, log-spaced layers).
Data      d = log10 rho_a and phase (deg) for every mode / station / frequency.
Forward   the same finite-volume solver as the forward-modelling tab (core.mt_2d).
Jacobian  adjoint method on the discrete system: one LU factorisation per frequency and mode,
          one extra (cheap) solve per station.  dZ/dm = explicit - lambda^T dr/dm,  A^T lambda = dZ/dU.
Update    Gauss-Newton / Occam form   (G^T G + lambda R^T R) m_new = G^T W (d - F(m) + J m)
          R = first differences (horizontal weight alpha, vertical 1).  lambda is chosen from the
          LINEARISED misfit (no extra forward runs), aiming at max(target, 0.5 * current RMS); the step is
          accepted only if the true RMS decreases (otherwise lambda x10).  Once the target RMS is reached,
          the smoothest model that still fits is sought (Occam's principle).

This is a deliberately compact implementation for classroom use (small grids, few frequencies).
"""
from __future__ import annotations

import time

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

from models.resistivity_2d import Model2D

from .fd1d import solve_column
from .mt_1d import MU0, apparent_resistivity, phase_deg
from .mt_2d import SIGMA_AIR, _assemble, _DepthProfile, build_mesh
from .skin_depth import skin_depth

LN10 = np.log(10.0)


class GridModel2D(Model2D):
    """Block-grid resistivity model used by the inversion (edges in metres)."""

    def __init__(self, ye, ze, logrho, stations, dx, dz):
        super().__init__(title="Inversion grid", width=float(ye[-1]), depth=float(ze[-1]), dx=dx, dz=dz,
                         bg_rho=[1.0], bg_thick=[], bodies=[], stations=list(stations))
        self.ye, self.ze = np.asarray(ye, float), np.asarray(ze, float)
        self.logrho = np.asarray(logrho, float).reshape(self.ze.size - 1, self.ye.size - 1)
        self.extra_breaks = (self.ye[1:-1], self.ze[1:-1])

    def index(self, y, z):
        iy = np.clip(np.searchsorted(self.ye, np.clip(y, 0, self.width), side="right") - 1, 0, self.ye.size - 2)
        iz = np.clip(np.searchsorted(self.ze, np.clip(z, 0, self.depth), side="right") - 1, 0, self.ze.size - 2)
        return iz, iy

    def rho_at(self, y, z):
        iz, iy = self.index(np.asarray(y, float), np.asarray(z, float))
        return 10 ** self.logrho[iz, iy]

    def all_rho(self):
        return 10 ** self.logrho.ravel()


# =============================================================================== data
class Data2D:
    """TE/TM data at stations: arrays (nf, ns) of log10 rho_a, phase and their 1-sigma errors."""

    def __init__(self, freq, stations, Z, Zerr, floor=0.05, modes=("TE", "TM"), use="both", true_model=None):
        o = np.argsort(np.asarray(freq, float))[::-1]
        self.freq = np.asarray(freq, float)[o]
        self.stations = np.asarray(stations, float)
        self.modes = [m for m in modes if m in Z]
        if not self.modes:
            raise ValueError("No TE/TM data available.")
        self.use = use
        self.logrho, self.phase, self.sd_lr, self.sd_ph = {}, {}, {}, {}
        for m in self.modes:
            z = np.asarray(Z[m], complex)[o]
            rel = np.zeros(z.shape) if Zerr is None or Zerr.get(m) is None else \
                np.asarray(Zerr[m], float)[o] / np.abs(z)
            rel = np.maximum(np.nan_to_num(rel, nan=floor), floor)
            self.logrho[m] = np.log10(apparent_resistivity(z, self.freq[:, None]))
            self.phase[m] = phase_deg(z)
            self.sd_lr[m] = 2 * rel / LN10
            self.sd_ph[m] = np.degrees(rel)
        self.true_model = true_model
        if np.any([np.any(self.sd_lr[m] <= 0) for m in self.modes]):
            raise ValueError("Zero errors: use an error floor > 0 %.")

    def vector(self):
        d, s = [], []
        for m in self.modes:
            if self.use in ("both", "rho"):
                d.append(self.logrho[m].ravel())
                s.append(self.sd_lr[m].ravel())
            if self.use in ("both", "phase"):
                d.append(self.phase[m].ravel())
                s.append(self.sd_ph[m].ravel())
        return np.concatenate(d), np.concatenate(s)

    def pack(self, lr, ph):
        """Pack predicted dicts {mode: (nf, ns)} like vector()."""
        out = []
        for m in self.modes:
            if self.use in ("both", "rho"):
                out.append(lr[m].ravel())
            if self.use in ("both", "phase"):
                out.append(ph[m].ravel())
        return np.concatenate(out)


def make_grid(data: Data2D, nz=12, pad_frac=0.15, zmin=None, zmax=None):
    """Columns centred on stations (+1 padding column each side), log-spaced layers from skin depths."""
    st = np.sort(data.stations)
    span = st[-1] - st[0] if st.size > 1 else 1000.0
    pad = max(pad_frac * span, 0.5 * (np.diff(st).mean() if st.size > 1 else 500.0))
    y0, y1 = st[0] - pad, st[-1] + pad
    mids = 0.5 * (st[1:] + st[:-1])
    ye = np.concatenate([[y0], mids, [y1]]) - y0
    rho_med = float(np.median(np.concatenate([10 ** data.logrho[m].ravel() for m in data.modes])))
    zmin = zmin or 0.3 * float(skin_depth(rho_med, data.freq.max()))
    zmax = zmax or 1.2 * float(skin_depth(rho_med, data.freq.min()))
    ze = np.concatenate([[0.0], np.logspace(np.log10(zmin), np.log10(zmax), nz)])
    return ye, ze, y0, rho_med


# =============================================================================== forward + Jacobian
_CORNERS = (  # (dP_row, dP_col, dH_row, dH_col, dV_row, dV_col) relative to cell (j, i)
    (0, 0, 0, 1, 1, 0),   # NW corner: H = NE, V = SW
    (0, 1, 0, 0, 1, 1),   # NE: H = NW, V = SE
    (1, 0, 1, 1, 0, 0),   # SW: H = SE, V = NW
    (1, 1, 1, 0, 0, 1),   # SE: H = SW, V = NE
)


def _forward_jac_one(gm: GridModel2D, f, mode, mesh, stations_local, want_jac):
    w = 2 * np.pi * f
    yc, zc = mesh.cell_centers()
    Yc, Zc = np.meshgrid(yc, zc)
    iz, iy = gm.index(Yc, Zc)
    npar = gm.logrho.size
    pidx_e = iz * gm.logrho.shape[1] + iy                       # (nz_e, ny_c)
    rho_e = 10 ** gm.logrho[iz, iy]
    nyc = mesh.hy.size
    if mode == "TE":
        nair = mesh.hz_air.size
        hz = np.concatenate([mesh.hz_air[::-1], mesh.hz])
        sig = np.vstack([np.full((nair, nyc), SIGMA_AIR), 1.0 / rho_e])
        a = np.ones_like(sig, dtype=complex)
        b = 1j * w * MU0 * sig
        pidx = np.vstack([np.full((nair, nyc), -1), pidx_e])
        js = nair
    else:
        hz = mesh.hz
        a = rho_e.astype(complex)
        b = np.full_like(a, 1j * w * MU0)
        pidx = pidx_e
        js = 0
    hy = mesh.hy
    left = solve_column(hz, a[:, 0], b[:, 0], 1.0, 0.0)
    right = solve_column(hz, a[:, -1], b[:, -1], 1.0, 0.0)
    yn = mesh.y_nodes
    bottom = left[-1] + (right[-1] - left[-1]) * (yn - yn[0]) / (yn[-1] - yn[0])
    A, rhs, U = _assemble(hy, hz, a, b, 1.0, left, right, bottom)
    nzn, nyn = U.shape
    lu = splu(A.tocsc())
    U[1:-1, 1:-1] = lu.solve(rhs).reshape(nzn - 2, nyn - 2)

    # ---- surface functionals at surface nodes i = 1..nyn-2 (Fw = sum of contributions of cells below)
    i = np.arange(1, nyn - 1)
    h = hz[js]
    hyl, hyr = hy[i - 1], hy[i]
    wP = (hyl + hyr) / 2
    al, ar, bl, br = a[js, i - 1], a[js, i], b[js, i - 1], b[js, i]
    UP, UL, UR, UD = U[js, i], U[js, i - 1], U[js, i + 1], U[js + 1, i]
    Fw = (al * (h / (2 * hyl) * (UL - UP) + hyl / (2 * h) * (UD - UP)) - bl * hyl * h / 4 * UP +
          ar * (h / (2 * hyr) * (UR - UP) + hyr / (2 * h) * (UD - UP)) - br * hyr * h / 4 * UP)
    F = Fw / wP
    ys = yn[1:-1]
    k = np.clip(np.searchsorted(ys, stations_local, side="right") - 1, 0, ys.size - 2)
    t = (stations_local - ys[k]) / (ys[k + 1] - ys[k])
    us = (1 - t) * UP[k] + t * UP[k + 1]
    Fs = (1 - t) * F[k] + t * F[k + 1]
    if mode == "TE":
        Z = -1j * w * MU0 * us / Fs
    else:
        Z = -Fs / us
    if not want_jac:
        return Z, None

    ns = stations_local.size
    nint = (nzn - 2) * (nyn - 2)

    def gid(row, col):          # interior unknown index or -1
        ok = (row > 0) & (row < nzn - 1) & (col > 0) & (col < nyn - 1)
        return np.where(ok, (row - 1) * (nyn - 2) + (col - 1), -1)

    # dZ/dF and dZ/du
    if mode == "TE":
        dZdF, dZdu = -Z / Fs, Z / us
    else:
        dZdF, dZdu = -1.0 / us, Fs / us ** 2
    # g_U: (ns, nint) dense, and explicit cell derivative (ns, ncells) sparse-ish
    g = np.zeros((ns, nint), complex)
    ncell = a.size
    expl_rows, expl_cols, expl_vals = [], [], []
    for side, kk, ww in (("k", k, 1 - t), ("k1", k + 1, t)):
        node = i[kk]                                       # node column of the surface node
        cF = dZdF * ww / wP[kk]                            # factor on d(Fw)_P
        # left cell (js, node-1): P is its NE corner, H = (js, node-1), V = (js+1, node)
        for cell_col, hyc, H_col in ((node - 1, hy[node - 1], node - 1), (node, hy[node], node + 1)):
            ac, bc = a[js, cell_col], b[js, cell_col]
            cP = -ac * (h / (2 * hyc) + hyc / (2 * h)) - bc * hyc * h / 4
            cH = ac * h / (2 * hyc)
            cV = ac * hyc / (2 * h)
            for (rr, cc, coef) in ((js, node, cP), (js, H_col, cH), (js + 1, node, cV)):
                gi = gid(np.full(ns, rr), cc)
                ok = gi >= 0
                np.add.at(g, (np.arange(ns)[ok], gi[ok]), (cF * coef)[ok])
            # explicit dependence on the cell's a or b
            UPc, UHc, UVc = U[js, node], U[js, H_col], U[js + 1, node]
            if mode == "TM":
                dval = h / (2 * hyc) * (UHc - UPc) + hyc / (2 * h) * (UVc - UPc)     # d(Fw)/da
            else:
                dval = -hyc * h / 4 * UPc                                            # d(Fw)/db
            expl_rows.append(np.arange(ns))
            expl_cols.append(js * nyc + cell_col)
            expl_vals.append(cF * dval)
        # du_s contribution (TE: surface node is an unknown)
        if mode == "TE":
            gi = gid(np.full(ns, js), node)
            ok = gi >= 0
            np.add.at(g, (np.arange(ns)[ok], gi[ok]), (dZdu * ww)[ok])
    lam = lu.solve(np.ascontiguousarray(g.T), trans="T")          # (nint, ns)

    # dr/dtheta for every earth cell (theta = a for TM, b for TE)
    jj, ii = np.meshgrid(np.arange(a.shape[0]), np.arange(nyc), indexing="ij")
    jj, ii = jj.ravel(), ii.ravel()
    earth = pidx.ravel() >= 0
    jj, ii = jj[earth], ii[earth]
    hyc, hzc = hy[ii], hz[jj]
    cells = jj * nyc + ii
    rows, cols, vals = [], [], []
    for dPr, dPc, dHr, dHc, dVr, dVc in _CORNERS:
        Pr, Pc = jj + dPr, ii + dPc
        gi = gid(Pr, Pc)
        ok = gi >= 0
        if mode == "TM":
            v = hzc / (2 * hyc) * (U[jj + dHr, ii + dHc] - U[Pr, Pc]) + hyc / (2 * hzc) * (U[jj + dVr, ii + dVc] - U[Pr, Pc])
        else:
            v = -hyc * hzc / 4 * U[Pr, Pc]
        rows.append(gi[ok])
        cols.append(cells[ok])
        vals.append(v[ok])
    Rt = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nint, ncell))
    S = -(Rt.T @ lam).T                                             # (ns, ncell)
    S = np.asarray(S)
    for r_, c_, v_ in zip(expl_rows, expl_cols, expl_vals):
        np.add.at(S, (r_, np.full(ns, c_)), v_)
    # chain rule theta(m) and aggregation cell -> parameter
    theta = (a if mode == "TM" else b).ravel()
    dtheta = (LN10 * theta) if mode == "TM" else (-LN10 * theta)
    pc = pidx.ravel()
    sel = np.nonzero(pc >= 0)[0]
    Mmap = sp.csr_matrix((dtheta[sel], (sel, pc[sel])), shape=(ncell, npar))
    dZdm = np.asarray(Mmap.T @ S.T).T                              # (ns, npar)
    return Z, dZdm


def forward_jac(gm: GridModel2D, data: Data2D, y0, refine=1.0, want_jac=True, progress=None, cancelled=None):
    """Return predicted dicts lr, ph {mode: (nf, ns)} and Jacobian (ndata x npar) packed like data.vector()."""
    prof = _DepthProfile(gm)
    st_local = data.stations - y0
    lr = {m: np.zeros((data.freq.size, st_local.size)) for m in data.modes}
    ph = {m: np.zeros_like(lr[m]) for m in data.modes}
    Jl = {m: np.zeros((data.freq.size, st_local.size, gm.logrho.size)) for m in data.modes}
    Jp = {m: np.zeros_like(Jl[m]) for m in data.modes}
    nsteps = data.freq.size * len(data.modes)
    k = 0
    for fi, f in enumerate(data.freq):
        mesh = build_mesh(gm, f, refine, prof)
        for m in data.modes:
            if cancelled and cancelled():
                raise RuntimeError("Inversion cancelled by user.")
            Z, dZ = _forward_jac_one(gm, f, m, mesh, st_local, want_jac)
            lr[m][fi] = np.log10(apparent_resistivity(Z, f))
            ph[m][fi] = phase_deg(Z)
            if want_jac:
                q = dZ / Z[:, None]
                Jl[m][fi] = 2 / LN10 * q.real
                Jp[m][fi] = np.degrees(q.imag)
            k += 1
            if progress:
                progress(k, nsteps, f"{m}  f = {f:.4g} Hz")
    J = None
    if want_jac:
        blocks = []
        for m in data.modes:
            if data.use in ("both", "rho"):
                blocks.append(Jl[m].reshape(-1, gm.logrho.size))
            if data.use in ("both", "phase"):
                blocks.append(Jp[m].reshape(-1, gm.logrho.size))
        J = np.vstack(blocks)
    return lr, ph, J


def roughness_matrix(nz, ny, alpha=1.0):
    n = nz * ny
    idx = np.arange(n).reshape(nz, ny)
    rows, cols, vals, r = [], [], [], 0
    for jz in range(nz):
        for iy in range(ny - 1):
            rows += [r, r]
            cols += [idx[jz, iy], idx[jz, iy + 1]]
            vals += [-alpha, alpha]
            r += 1
    for jz in range(nz - 1):
        for iy in range(ny):
            rows += [r, r]
            cols += [idx[jz, iy], idx[jz + 1, iy]]
            vals += [-1.0, 1.0]
            r += 1
    return sp.csr_matrix((vals, (rows, cols)), shape=(r, n)).toarray()


def _rms(d, p, s):
    return float(np.sqrt(np.mean(((d - p) / s) ** 2)))


def occam2d(data: Data2D, nz=12, refine=0.8, target=1.0, max_iter=8, alpha=1.0, progress=None,
            cancelled=None, on_iter=None):
    """Run the Occam-type 2D inversion. Returns dict with grid, model history and data fit."""
    ye, ze, y0, rho0 = make_grid(data, nz)
    ny_p, nz_p = ye.size - 1, ze.size - 1
    st_sorted = np.sort(data.stations - y0)
    dx = max(min(np.diff(st_sorted).min() / 2 if st_sorted.size > 1 else 100.0, ye[-1] / 40), 1.0)
    dz = max(ze[-1] / 60, 1.0)
    m = np.full(ny_p * nz_p, np.log10(rho0))
    R = roughness_matrix(nz_p, ny_p, alpha)
    RtR = R.T @ R
    d, sd = data.vector()
    t0 = time.perf_counter()

    def run(mm, tag):
        gm = GridModel2D(ye, ze, mm, data.stations - y0, dx, dz)

        def prog(k, n, msg):
            if progress:
                progress(k, n, f"{tag}: {msg}")
        return forward_jac(gm, data, y0, refine, True, prog, cancelled)

    lr, ph, J = run(m, "iteration 0")
    pred = data.pack(lr, ph)
    hist = [{"iter": 0, "rms": _rms(d, pred, sd), "roughness": float(np.sum((R @ m) ** 2)), "lam": np.nan,
             "time_s": time.perf_counter() - t0}]
    models = [m.copy()]
    preds = [(lr, ph)]
    if on_iter:
        on_iter(hist[-1], m, lr, ph)
    for it in range(1, max_iter + 1):
        cur = hist[-1]["rms"]
        G = J / sd[:, None]
        dhat = (d - pred + J @ m) / sd
        GtG, Gtd = G.T @ G, G.T @ dhat
        lam0 = np.trace(GtG) / max(np.trace(RtR), 1e-12)
        lams = lam0 * np.logspace(-4, 2, 25)
        aim = max(target, 0.5 * cur)
        cands = []
        for lam in lams:
            mm = np.clip(np.linalg.solve(GtG + lam * RtR, Gtd), -1.0, 5.0)
            cands.append((lam, _rms(d, pred + J @ (mm - m), sd), mm))
        ok = [c for c in cands if c[1] <= aim]
        lam, lin, mn = max(ok, key=lambda c: c[0]) if ok else min(cands, key=lambda c: c[1])
        accepted = False
        for _ in range(3):
            lr_n, ph_n, J_n = run(mn, f"iteration {it}")
            pred_n = data.pack(lr_n, ph_n)
            r_n = _rms(d, pred_n, sd)
            if r_n < cur or (cur <= target * 1.02 and r_n <= target * 1.05):
                accepted = True
                break
            lam *= 10
            mn = np.clip(np.linalg.solve(GtG + lam * RtR, Gtd), -1.0, 5.0)
        if not accepted:
            break
        rough = float(np.sum((R @ mn) ** 2))
        prev = hist[-1]
        m, J, pred, lr, ph = mn, J_n, pred_n, lr_n, ph_n
        hist.append({"iter": it, "rms": r_n, "roughness": rough, "lam": float(lam),
                     "time_s": time.perf_counter() - t0})
        models.append(m.copy())
        preds.append((lr, ph))
        if on_iter:
            on_iter(hist[-1], m, lr, ph)
        if prev["rms"] <= target * 1.02 and r_n <= target * 1.02 and abs(rough - prev["roughness"]) < 0.02 * max(rough, 1e-6):
            break
        if r_n > target and (prev["rms"] - r_n) < 0.01 * prev["rms"]:
            break
    return {"ye": ye + y0, "ze": ze, "logrho": m.reshape(nz_p, ny_p), "history": hist,
            "models": [mm.reshape(nz_p, ny_p) for mm in models], "pred_lr": lr, "pred_ph": ph,
            "rms": hist[-1]["rms"], "target": target, "y0": y0, "rho_start": rho0, "refine": refine,
            "alpha": alpha}
