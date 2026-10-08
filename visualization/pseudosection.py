"""Pseudosections (station x frequency) for 2D responses."""
import numpy as np
from i18n import tr
from matplotlib.colors import LogNorm, Normalize

from .theme import PHASE_CMAP, RHO_CMAP, style_ax, style_colorbar


def _edges(v, log=False):
    v = np.asarray(v, float)
    if v.size == 1:
        return np.array([v[0] / 1.5, v[0] * 1.5]) if log else np.array([v[0] - 1, v[0] + 1])
    if log:
        lv = np.log10(v)
        e = np.concatenate([[lv[0] - (lv[1] - lv[0]) / 2], (lv[1:] + lv[:-1]) / 2, [lv[-1] + (lv[-1] - lv[-2]) / 2]])
        return 10 ** e
    return np.concatenate([[v[0] - (v[1] - v[0]) / 2], (v[1:] + v[:-1]) / 2, [v[-1] + (v[-1] - v[-2]) / 2]])


def plot_pseudosection(fig, ax, stations, freqs, values, theme, kind="rho", title="", norm=None):
    style_ax(ax, theme)
    order = np.argsort(freqs)
    f = np.asarray(freqs)[order]
    vals = np.asarray(values)[order]
    if kind == "rho":
        norm = norm or LogNorm(vmin=np.nanmin(vals), vmax=np.nanmax(vals) * (1.0001))
        cmap, lab = RHO_CMAP, "ρa (Ω·m)"
    else:
        norm = norm or Normalize(0, 90)
        cmap, lab = PHASE_CMAP, "φ (°)"
    pm = ax.pcolormesh(_edges(stations), _edges(f, log=True), vals, cmap=cmap, norm=norm, shading="flat",
                       rasterized=True)
    ax.set_yscale("log")
    ax.set_ylim(f.min() / 1.3, f.max() * 1.3)      # high frequency (shallow) at the top
    ax._no_grid = True
    ax.grid(False)
    ax.set_ylabel(tr("Frequency (Hz)"))
    ax.set_xlabel(tr("Station y (m)"))
    ax.plot(stations, np.full(len(stations), f.max() * 1.25), "v", color=theme["fg"], ms=3, clip_on=False)
    ax.set_title(title, fontsize=9)
    cb = fig.colorbar(pm, ax=ax, pad=0.02, fraction=0.06)
    style_colorbar(cb, theme, lab)
    return pm
