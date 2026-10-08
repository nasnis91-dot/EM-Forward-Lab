"""
1D MT/AMT inversion for teaching.

Data vector   d = [log10 rho_a(f_1..n), phase(f_1..n) in degrees]      (or one of the two)
Errors        sd(log10 rho_a) = 2 sd|Z|/|Z| / ln10,   sd(phi) = sd|Z|/|Z|  [rad -> deg]
Misfit        RMS = sqrt( mean( ((d_obs - d_pred) / sd)^2 ) )      target = 1

Two classic algorithms:

OCCAM (Constable, Parker & Constable 1987): many thin layers with fixed (log-spaced) depths,
    unknowns m = log10 rho. Minimise  ||W(d - F(m))||^2 + lambda ||R m||^2  (R = first difference).
    Each iteration linearises F, scans lambda and keeps the SMOOTHEST model that reaches the target
    misfit (or the best-fitting one while the target is not yet reached).

MARQUARDT / Levenberg-Marquardt (layered): a few layers, unknowns m = [log10 rho_i, log10 h_i].
    (G^T G + mu diag(G^T G)) dm = G^T W r,   mu adapted every iteration.
    Final parameter uncertainties from the covariance (G^T G)^-1 at the solution; the correlation
    matrix shows the classic equivalences (S = h/rho for thin conductors, T = h rho for resistors).

Jacobians are computed by finite differences of the analytic 1D forward (cheap and robust).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .mt_1d import apparent_resistivity, bostick, impedance_1d, phase_deg

LN10 = np.log(10.0)
LOGRHO_MIN, LOGRHO_MAX = -1.0, 5.0          # 0.1 ... 1e5 Ohm.m
LOGH_MIN, LOGH_MAX = 0.0, 5.0               # 1 m ... 100 km


# ============================================================================ data
@dataclass
class InvData:
    freq: np.ndarray
    rho: np.ndarray
    phase: np.ndarray
    sd_logrho: np.ndarray
    sd_phase: np.ndarray
    source: str = ""
    true_model: dict | None = None            # {"rho": [...], "thick": [...]} when known (synthetic)
    use: str = "both"                         # "both" | "rho" | "phase"
    mask: np.ndarray | None = None            # frequencies used (True = used)

    @classmethod
    def from_impedance(cls, f, Z, Zerr=None, floor=0.0, source="", true_model=None):
        f = np.asarray(f, float)
        Z = np.asarray(Z, complex)
        rel = np.zeros(f.size) if Zerr is None else np.asarray(Zerr, float) / np.abs(Z)
        rel = np.maximum(rel, floor)
        if np.any(rel <= 0):
            raise ValueError("Data have zero errors: set an error floor > 0 %.")
        o = np.argsort(f)[::-1]
        return cls(freq=f[o], rho=apparent_resistivity(Z, f)[o], phase=phase_deg(Z)[o],
                   sd_logrho=(2 * rel / LN10)[o], sd_phase=np.degrees(rel)[o], source=source,
                   true_model=true_model)

    @classmethod
    def from_rho_phase(cls, f, rho, phase, rel_err_rho=None, sd_phase=None, floor=0.0, source="",
                       true_model=None):
        f = np.asarray(f, float)
        rho = np.asarray(rho, float)
        phase = np.asarray(phase, float)
        rr = np.zeros(f.size) if rel_err_rho is None else np.asarray(rel_err_rho, float)
        rr = np.maximum(rr, 2 * floor)
        sp = np.zeros(f.size) if sd_phase is None else np.asarray(sd_phase, float)
        sp = np.maximum(sp, np.degrees(floor))
        if np.any(rr <= 0) or np.any(sp <= 0):
            raise ValueError("Data have zero errors: set an error floor > 0 %.")
        o = np.argsort(f)[::-1]
        return cls(freq=f[o], rho=rho[o], phase=phase[o], sd_logrho=(rr / LN10)[o], sd_phase=sp[o],
                   source=source, true_model=true_model)

    def _m(self):
        return np.ones(self.freq.size, bool) if self.mask is None else self.mask

    def vector(self):
        m = self._m()
        parts, sds = [], []
        if self.use in ("both", "rho"):
            parts.append(np.log10(self.rho[m]))
            sds.append(self.sd_logrho[m])
        if self.use in ("both", "phase"):
            parts.append(self.phase[m])
            sds.append(self.sd_phase[m])
        return np.concatenate(parts), np.concatenate(sds)

    def predict(self, rho, thick):
        m = self._m()
        f = self.freq[m]
        Z = impedance_1d(rho, thick, f)
        parts = []
        if self.use in ("both", "rho"):
            parts.append(np.log10(apparent_resistivity(Z, f)))
        if self.use in ("both", "phase"):
            parts.append(phase_deg(Z))
        return np.concatenate(parts)

    def validate(self):
        e = []
        if self.freq.size < 3:
            e.append("At least 3 frequencies are required.")
        if np.any(self.rho <= 0) or np.any(~np.isfinite(self.rho)):
            e.append("Apparent resistivities must be positive and finite.")
        if self.use == "phase" and self._m().sum() < 3:
            e.append("Too few data.")
        return e


def rms(d, dp, sd):
    return float(np.sqrt(np.mean(((d - dp) / sd) ** 2)))


def _jacobian(fun, m, h=0.01):
    f0 = fun(m)
    J = np.empty((f0.size, m.size))
    for k in range(m.size):
        mp = m.copy()
        mp[k] += h
        J[:, k] = (fun(mp) - f0) / h
    return f0, J


# ============================================================================ Occam
def occam_mesh(data: InvData, n_layers=40, zmin=None, zmax=None):
    """Log-spaced layer interfaces between zmin and zmax (defaults from the Bostick depths)."""
    d, _ = bostick(data.rho, np.clip(data.phase, 1, 89), data.freq)
    d = d[np.isfinite(d) & (d > 0)]
    zmin = zmin or max(0.3 * float(d.min()), 0.5)
    zmax = zmax or 1.5 * float(d.max())
    if zmax <= zmin * 1.5:
        zmax = zmin * 10
    z = np.logspace(np.log10(zmin), np.log10(zmax), n_layers - 1)
    thick = np.diff(np.concatenate([[0.0], z]))
    return thick, z


def occam(data: InvData, n_layers=40, zmin=None, zmax=None, target=1.0, max_iter=20, start_rho=None,
          progress=None, cancelled=None):
    errs = data.validate()
    if errs:
        raise ValueError("; ".join(errs))
    thick, z = occam_mesh(data, n_layers, zmin, zmax)
    d, sd = data.vector()
    m = np.full(n_layers, np.log10(start_rho or np.median(data.rho)))
    R = np.diff(np.eye(n_layers), axis=0)
    RtR = R.T @ R

    def fwd(mm):
        return data.predict(10 ** mm, thick)
    dp = fwd(m)
    hist = [{"iter": 0, "rms": rms(d, dp, sd), "roughness": float(np.sum((R @ m) ** 2)), "lam": np.nan}]
    lams = np.logspace(-3, 5, 33)
    for it in range(1, max_iter + 1):
        if cancelled and cancelled():
            break
        dp, J = _jacobian(fwd, m)
        G = J / sd[:, None]
        dhat = (d - dp + J @ m) / sd
        GtG, Gtd = G.T @ G, G.T @ dhat
        cands = []
        for lam in lams:
            try:
                mn = np.linalg.solve(GtG + lam * RtR, Gtd)
            except np.linalg.LinAlgError:
                continue
            mn = np.clip(mn, LOGRHO_MIN, LOGRHO_MAX)
            cands.append((lam, rms(d, fwd(mn), sd), mn))
        ok = [c for c in cands if c[1] <= target]
        if ok:
            lam, r, mn = max(ok, key=lambda c: c[0])            # smoothest model at target misfit
            bigger = [c for c in cands if c[0] > lam]
            if bigger:                                          # bisection in log(lambda) towards RMS = target
                lo_l, hi_l = np.log10(lam), np.log10(min(c[0] for c in bigger))
                for _ in range(8):
                    mid = 10 ** ((lo_l + hi_l) / 2)
                    mt = np.clip(np.linalg.solve(GtG + mid * RtR, Gtd), LOGRHO_MIN, LOGRHO_MAX)
                    rt = rms(d, fwd(mt), sd)
                    if rt <= target:
                        lam, r, mn, lo_l = mid, rt, mt, np.log10(mid)
                    else:
                        hi_l = np.log10(mid)
        else:
            lam, r, mn = min(cands, key=lambda c: c[1])         # best fit while target not reached
            if r > hist[-1]["rms"]:                              # cannot improve: step-halving
                for a in (0.5, 0.25, 0.1):
                    mt = m + a * (mn - m)
                    rt = rms(d, fwd(mt), sd)
                    if rt < hist[-1]["rms"]:
                        mn, r = mt, rt
                        break
                else:
                    break
        rough = float(np.sum((R @ mn) ** 2))
        prev = hist[-1]
        m = mn
        hist.append({"iter": it, "rms": r, "roughness": rough, "lam": float(lam)})
        if progress:
            progress(it, max_iter, f"Occam iteration {it}: RMS = {r:.3f}")
        if prev["rms"] <= target * 1.001 and r <= target * 1.001 and abs(rough - prev["roughness"]) <= 0.01 * max(rough, 1e-6):
            break
        if r > target and abs(prev["rms"] - r) < 1e-3 * prev["rms"]:
            break
    rho = 10 ** m
    resp = impedance_1d(rho, thick, data.freq)
    return {"method": "occam", "rho": rho, "thick": thick, "depth_top": np.concatenate([[0.0], z]),
            "history": hist, "rms": hist[-1]["rms"], "target": target,
            "resp_rho": apparent_resistivity(resp, data.freq), "resp_phase": phase_deg(resp),
            "n_layers": n_layers}


# ============================================================================ Marquardt
def _segment(logrho, w, n):
    """Optimal piecewise-constant fit of logrho (weights w) with n segments (dynamic programming)."""
    N = logrho.size
    cw = np.concatenate([[0], np.cumsum(w)])
    cx = np.concatenate([[0], np.cumsum(w * logrho)])
    cxx = np.concatenate([[0], np.cumsum(w * logrho ** 2)])

    def cost(i, j):                       # segment i..j-1
        sw = cw[j] - cw[i]
        return (cxx[j] - cxx[i]) - (cx[j] - cx[i]) ** 2 / sw if sw > 0 else 0.0
    INF = 1e300
    D = np.full((n + 1, N + 1), INF)
    P = np.zeros((n + 1, N + 1), int)
    D[0, 0] = 0.0
    for k in range(1, n + 1):
        for j in range(k, N + 1):
            best, arg = INF, k - 1
            for i in range(k - 1, j):
                v = D[k - 1, i] + cost(i, j)
                if v < best:
                    best, arg = v, i
            D[k, j], P[k, j] = best, arg
    cuts, j = [], N
    for k in range(n, 0, -1):
        i = P[k, j]
        cuts.append((i, j))
        j = i
    return cuts[::-1]


def _layers_from_cuts(lr, tops, w, cuts):
    rho, thick = [], []
    for (i, j) in cuts:
        rho.append(float(10 ** np.average(lr[i:j], weights=w[i:j])))
        if j < lr.size:
            thick.append(float(tops[j] - (tops[i] if i > 0 else 0.0)))
    return rho, thick


def auto_starts(data: InvData, n_layers=3):
    """Candidate starting models for Marquardt, derived from a quick smooth (Occam) inversion:
    (a) optimal piecewise-constant segmentation, (b) interfaces at the steepest resistivity gradients."""
    oc = occam(data, n_layers=30, max_iter=8)
    lr = np.log10(oc["rho"])
    tops = oc["depth_top"]
    bots = np.concatenate([tops[1:], [tops[-1] * 2]])
    w = np.log10(bots / np.maximum(tops, tops[1] / 2))
    out = [_layers_from_cuts(lr, tops, w, _segment(lr, w, n_layers))]
    g = np.abs(np.diff(lr))                                   # change across each interface
    order = np.argsort(g)[::-1]
    picks = []
    for k in order:
        if all(abs(k - p) > 1 for p in picks):
            picks.append(int(k))
        if len(picks) == n_layers - 1:
            break
    if len(picks) == n_layers - 1:
        b = [0] + sorted(p + 1 for p in picks) + [lr.size]
        out.append(_layers_from_cuts(lr, tops, w, list(zip(b[:-1], b[1:]))))
    return out, (oc, lr, tops, w)


def _random_start(rng, lr, tops, w, n_layers):
    """Random interface indices (log-depth uniform on the Occam mesh), rho averaged from Occam."""
    idx = np.sort(rng.choice(np.arange(1, lr.size - 2), size=n_layers - 1, replace=False))
    b = [0] + list(idx) + [lr.size]
    return _layers_from_cuts(lr, tops, w, list(zip(b[:-1], b[1:])))


def auto_start(data: InvData, n_layers=3):
    if n_layers == 1:
        return [float(np.median(data.rho))], []
    return auto_starts(data, n_layers)[0][0]


def marquardt(data: InvData, rho0, thick0, max_iter=40, fix_rho=None, fix_h=None, progress=None, cancelled=None):
    errs = data.validate()
    if errs:
        raise ValueError("; ".join(errs))
    rho0, thick0 = list(map(float, rho0)), list(map(float, thick0))
    nl = len(rho0)
    if len(thick0) != nl - 1 or min(rho0) <= 0 or (thick0 and min(thick0) <= 0):
        raise ValueError("Starting model: need n resistivities > 0 and n-1 thicknesses > 0.")
    d, sd = data.vector()
    m = np.concatenate([np.log10(rho0), np.log10(thick0)]) if thick0 else np.log10(rho0)
    free = np.ones(m.size, bool)
    for i in (fix_rho or []):
        free[i] = False
    for i in (fix_h or []):
        free[nl + i] = False
    lo = np.concatenate([np.full(nl, LOGRHO_MIN), np.full(nl - 1, LOGH_MIN)])
    hi = np.concatenate([np.full(nl, LOGRHO_MAX), np.full(nl - 1, LOGH_MAX)])

    def split(mm):
        return 10 ** mm[:nl], 10 ** mm[nl:]

    def fwd_full(mm):
        r, t = split(mm)
        return data.predict(r, t)

    dp = fwd_full(m)
    hist = [{"iter": 0, "rms": rms(d, dp, sd), "mu": np.nan}]
    mu = 1.0
    for it in range(1, max_iter + 1):
        if cancelled and cancelled():
            break
        mf = m[free]

        def fwd(x):
            mm = m.copy()
            mm[free] = x
            return fwd_full(mm)
        dp, J = _jacobian(fwd, mf, 0.005)
        G = J / sd[:, None]
        r = (d - dp) / sd
        GtG, Gtr = G.T @ G, G.T @ r
        D = np.diag(np.diag(GtG) + 1e-12)
        improved = False
        for _ in range(12):
            try:
                step = np.linalg.solve(GtG + mu * D, Gtr)
            except np.linalg.LinAlgError:
                mu *= 10
                continue
            mt = m.copy()
            mt[free] = np.clip(mf + step, lo[free], hi[free])
            rt = rms(d, fwd_full(mt), sd)
            if rt < hist[-1]["rms"]:
                m, improved = mt, True
                mu = max(mu / 3, 1e-6)
                break
            mu *= 4
        if not improved:
            break
        hist.append({"iter": it, "rms": rt, "mu": mu})
        if progress:
            progress(it, max_iter, f"Marquardt iteration {it}: RMS = {rt:.3f}")
        if len(hist) > 3 and hist[-4]["rms"] - rt < 1e-4 * hist[-4]["rms"]:
            break
    # uncertainties at the solution
    mf = m[free]

    def fwd(x):
        mm = m.copy()
        mm[free] = x
        return fwd_full(mm)
    _, J = _jacobian(fwd, mf, 0.005)
    G = J / sd[:, None]
    chi = max(hist[-1]["rms"], 1.0)                     # scale if data are not fitted to RMS 1
    try:
        C = np.linalg.pinv(G.T @ G) * chi ** 2
        sdm = np.sqrt(np.clip(np.diag(C), 0, None))
        corr = C / np.outer(sdm, sdm)
    except np.linalg.LinAlgError:
        sdm = np.full(mf.size, np.nan)
        corr = np.full((mf.size, mf.size), np.nan)
    sd_full = np.full(m.size, 0.0)
    sd_full[free] = sdm
    names = [f"rho{i + 1}" for i in range(nl)] + [f"h{i + 1}" for i in range(nl - 1)]
    rho, thick = split(m)
    resp = impedance_1d(rho, thick, data.freq)
    return {"method": "marquardt", "rho": rho, "thick": thick,
            "depth_top": np.concatenate([[0.0], np.cumsum(thick)]), "history": hist, "rms": hist[-1]["rms"],
            "sd_log10": sd_full, "factor": 10 ** np.clip(sd_full, 0, 6), "corr": corr,
            "free_names": [n for n, fr in zip(names, free) if fr], "names": names,
            "resp_rho": apparent_resistivity(resp, data.freq), "resp_phase": phase_deg(resp),
            "start": {"rho": rho0, "thick": thick0}}


def marquardt_auto(data: InvData, n_layers=3, n_starts=8, seed=0, max_iter=40, progress=None, cancelled=None):
    """Marquardt with an automatic starting model and a few perturbed restarts (keeps the best).

    Layered inversion is non-linear and can stop in local minima; several starts make the result
    reproducible for students. Every start and its final RMS are returned for inspection.
    """
    rng = np.random.default_rng(seed)
    if n_layers == 1:
        bases, starts = [([float(np.median(data.rho))], [])], [([float(np.median(data.rho))], [])]
    else:
        bases, (oc, lr, tops, w) = auto_starts(data, n_layers)
        starts = list(bases)
        while len(starts) < n_starts:
            starts.append(_random_start(rng, lr, tops, w, n_layers))
    best, tried = None, []
    for k, (r, t) in enumerate(starts):
        if cancelled and cancelled():
            break
        res = marquardt(data, r, t, max_iter=max_iter, cancelled=cancelled)
        tried.append({"start_rho": r, "start_thick": t, "rms": res["rms"]})
        if best is None or res["rms"] < best["rms"]:
            best = res
        if progress:
            progress(k + 1, len(starts), f"Marquardt start {k + 1}/{len(starts)}: RMS = {res['rms']:.3f}")
    best["starts_tried"] = tried
    best["start"] = {"rho": bases[0][0], "thick": bases[0][1]}
    return best
