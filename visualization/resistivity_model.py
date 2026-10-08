"""Resistivity model plots (1D layered column and 2D cross-section)."""
import matplotlib
import numpy as np
from i18n import tr
from matplotlib import cm
from matplotlib.colors import LogNorm
from matplotlib.patches import Polygon, Rectangle

from .theme import RHO_CMAP, style_ax, style_colorbar


def rho_norm(values):
    v = np.asarray(values, float)
    lo, hi = v.min(), v.max()
    if hi / lo < 10:
        g = np.sqrt(10 / (hi / lo))
        lo, hi = lo / g, hi * g
    return LogNorm(vmin=lo, vmax=hi)


def plot_layered(fig, ax, model, theme, bostick=None, max_depth=None, colorbar=True):
    """Coloured layers + true rho(z) step curve (+ optional Niblett-Bostick points)."""
    style_ax(ax, theme)
    rho = np.asarray(model.rho, float)
    tops = model.depths()
    if max_depth is None:
        max_depth = max(tops[-1] * 1.6, 100.0) if len(tops) > 1 else 1000.0
        if bostick is not None and np.isfinite(bostick[0]).any():
            max_depth = max(max_depth, min(np.nanmax(bostick[0]), 3 * max_depth))
    norm = rho_norm(np.concatenate([rho, [rho.min() / 3, rho.max() * 3]]))
    cmap = matplotlib.colormaps[RHO_CMAP]
    xlo = min(rho.min(), np.nanmin(bostick[1]) if bostick is not None and np.isfinite(bostick[1]).any() else rho.min()) / 5
    xhi = max(rho.max(), np.nanmax(bostick[1]) if bostick is not None and np.isfinite(bostick[1]).any() else rho.max()) * 5
    xlo, xhi = max(xlo, 1e-3), min(xhi, 1e7)
    bottoms = np.concatenate([tops[1:], [max_depth]])
    for i, (t, b, r) in enumerate(zip(tops, bottoms, rho)):
        ax.add_patch(Rectangle((xlo, t), xhi - xlo, b - t, color=cmap(norm(r)), alpha=0.55, lw=0))
        if i > 0:
            ax.axhline(t, color=theme["fg"], lw=0.6, alpha=0.5)
        mid = t + (min(b, max_depth) - t) / 2
        lbl = f"{model.layer_name(i)}\n{r:g} Ω·m" + (f",  h = {b - t:g} m" if i < len(rho) - 1 else "")
        ax.text(xlo * 1.15, mid, lbl, color=theme["fg"], fontsize=7.5, va="center",
                bbox=dict(boxstyle="round,pad=0.2", fc=theme["ax"], ec="none", alpha=0.6))
    zz = np.repeat(np.concatenate([tops, [max_depth]]), 2)[1:-1]
    rr = np.repeat(rho, 2)
    ax.plot(rr, zz, color=theme["fg"], lw=2, label=tr("True ρ(z)"))
    if bostick is not None:
        d, rb = bostick
        ok = np.isfinite(rb) & (rb > 0) & (d < max_depth)
        ax.plot(rb[ok], d[ok], "o", ms=3, color=theme["accent2"], label=tr("Niblett–Bostick (approx.)"))
    ax.set_xscale("log")
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(max_depth, 0)
    ax.set_xlabel(tr("Resistivity (Ω·m)"))
    ax.set_ylabel(tr("Depth (m)"))
    ax.set_title(tr("1D layered earth model"), fontsize=10)
    if colorbar:
        sm = cm.ScalarMappable(norm=norm, cmap=cmap)
        cb = fig.colorbar(sm, ax=ax, pad=0.02, fraction=0.05)
        style_colorbar(cb, theme, tr("ρ (Ω·m)"))
    return ax


def section_grid(model, ny=300, nz=200):
    y = np.linspace(0, model.width, ny)
    z = np.linspace(0, model.depth, nz)
    Y, Z = np.meshgrid(y, z)
    return y, z, model.rho_at(Y, Z)


def plot_section(fig, ax, model, theme, stations=True, outlines=True, colorbar=True, norm=None):
    style_ax(ax, theme)
    y, z, R = section_grid(model)
    norm = norm or rho_norm(R.ravel())
    pm = ax.pcolormesh(y, z, R, cmap=RHO_CMAP, norm=norm, shading="nearest", rasterized=True)
    if outlines:
        for b in model.bodies:
            if b.kind == "polygon":
                ax.add_patch(Polygon(b.points, closed=True, fill=False, ec=theme["fg"], lw=0.8, ls="--"))
            else:
                x0, x1 = max(b.x0, -1e6), min(b.x1, 1e7)
                z0, z1 = max(b.z0, -1e6), min(b.z1, 1e7)
                ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fill=False, ec=theme["fg"], lw=0.8, ls="--"))
            cx = np.clip(np.mean([p[0] for p in b.points]) if b.kind == "polygon" else (max(b.x0, 0) + min(b.x1, model.width)) / 2,
                         0.05 * model.width, 0.95 * model.width)
            cz = np.clip(np.mean([p[1] for p in b.points]) if b.kind == "polygon" else (max(b.z0, 0) + min(b.z1, model.depth)) / 2,
                         0.05 * model.depth, 0.95 * model.depth)
            ax.text(cx, cz, f"{b.name}\n{b.rho:g} Ω·m", color="white", fontsize=7, ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="black", ec="none", alpha=0.35))
    if stations and model.stations:
        ax.plot(model.stations, np.zeros(len(model.stations)), "v", color="white", mec="black", ms=6,
                clip_on=False, zorder=5)
    ax._no_grid = True
    ax.grid(False)
    ax.set_xlim(0, model.width)
    ax.set_ylim(model.depth, 0)
    ax.set_xlabel(tr("Distance along profile y (m)"))
    ax.set_ylabel(tr("Depth (m)"))
    ax.set_title(tr("2D resistivity model — {t}", t=model.title), fontsize=10)
    if colorbar:
        cb = fig.colorbar(pm, ax=ax, pad=0.02, fraction=0.05)
        style_colorbar(cb, theme, tr("ρ (Ω·m)"))
    return pm
