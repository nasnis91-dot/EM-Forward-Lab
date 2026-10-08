"""Sounding-curve plots: apparent resistivity, phase, impedance, skin depth, comparisons."""
import numpy as np

from i18n import tr
from .theme import legend, style_ax


def setup_rho_phase(ax_r, ax_p, theme, xlabel=None):
    xlabel = xlabel or tr("Frequency (Hz)")
    for ax in (ax_r, ax_p):
        style_ax(ax, theme)
        ax.set_xscale("log")
    ax_r.set_yscale("log")
    ax_r.set_ylabel("ρa (Ω·m)")
    ax_p.set_ylabel(tr("Phase φ (°)"))
    ax_p.set_xlabel(xlabel)
    ax_p.set_ylim(0, 90)
    ax_p.set_yticks([0, 15, 30, 45, 60, 75, 90])
    ax_p.axhline(45, color=theme["muted"], lw=0.8, ls=":")
    ax_r.tick_params(labelbottom=False)


def plot_curve(ax_r, ax_p, f, rho_a, phase, label, color, ls="-", lw=1.8, marker=None, noisy=None):
    """noisy = (rho_obs, phase_obs) plotted as markers on top of the clean line."""
    ax_r.plot(f, rho_a, ls=ls, lw=lw, color=color, label=label, marker=marker, ms=3)
    ax_p.plot(f, phase, ls=ls, lw=lw, color=color, marker=marker, ms=3)
    if noisy is not None:
        ax_r.plot(f, noisy[0], "o", ms=3.5, mfc="none", color=color, label=label + " (noisy obs.)")
        ax_p.plot(f, noisy[1], "o", ms=3.5, mfc="none", color=color)


def finish_rho_phase(ax_r, ax_p, theme, f):
    f = np.asarray(f)
    for ax in (ax_r, ax_p):                       # high frequency (shallow) on the left; explicit, so
        ax.set_xlim(f.max() * 1.3, f.min() / 1.3)  # shared axes are never inverted twice
    lo, hi = ax_r.get_ylim()
    if hi / lo < 10:
        g = np.sqrt(10 * lo / hi)
        ax_r.set_ylim(lo / g, hi * g)
    legend(ax_r, theme, loc="best")


def shade_invalid(ax_list, f, ok, theme, label=None):
    label = label or tr("Plane-wave (far-field) assumption violated")
    f = np.asarray(f)
    bad = ~np.asarray(ok)
    if not bad.any():
        return
    order = np.argsort(f)
    fs, bs = f[order], bad[order]
    edges = np.sqrt(fs[1:] * fs[:-1])
    lo_e = np.concatenate([[fs[0] / 1.2], edges])
    hi_e = np.concatenate([edges, [fs[-1] * 1.2]])
    first = True
    for l, h, b in zip(lo_e, hi_e, bs):
        if b:
            for ax in ax_list:
                ax.axvspan(l, h, color=theme["warn"], alpha=0.12, lw=0, label=label if (first and ax is ax_list[0]) else None)
            first = False


def plot_impedance(ax, f, Z, theme):
    style_ax(ax, theme)
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=max(np.abs(Z).min() / 10, 1e-12))
    ax.plot(f, Z.real, color=theme["accent"], label="Re Z")
    ax.plot(f, Z.imag, color=theme["accent2"], label="Im Z")
    ax.set_ylabel("Z (Ω)")
    ax.set_xlabel(tr("Frequency (Hz)"))
    ax.set_xlim(np.max(f) * 1.3, np.min(f) / 1.3)
    legend(ax, theme)


def plot_skin_depth(ax, f, rhos, theme, highlight=None):
    from core.skin_depth import skin_depth
    style_ax(ax, theme)
    for i, r in enumerate(rhos):
        ax.loglog(f, skin_depth(r, f), color=theme["cycle"][i % len(theme["cycle"])], lw=1.3, label=f"ρ = {r:g} Ω·m")
    if highlight is not None:
        ax.loglog(f, skin_depth(highlight, f), color=theme["fg"], lw=2.6, label=f"Selected ρ = {highlight:g} Ω·m")
    ax.set_xlabel(tr("Frequency (Hz)"))
    ax.set_ylabel("Skin depth δ (m)")
    if not ax.yaxis_inverted():
        ax.invert_yaxis()
    if not ax.xaxis_inverted():
        ax.invert_xaxis()
