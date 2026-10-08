"""Figure themes (dark for the GUI, light for exported figures/reports)."""
import matplotlib

matplotlib.rcParams["svg.fonttype"] = "none"

DARK = {
    "name": "dark", "fig": "#0f1a2b", "ax": "#13223a", "fg": "#d8e2f0", "muted": "#8a9bb5",
    "grid": "#2a3d5c", "accent": "#4fc3f7", "accent2": "#ffb74d", "te": "#4fc3f7", "tm": "#ff8a65",
    "ref": "#9e9e9e", "warn": "#ef5350", "cycle": ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8",
                                                  "#fff176", "#4dd0e1", "#f06292"],
}
LIGHT = {
    "name": "light", "fig": "#ffffff", "ax": "#ffffff", "fg": "#1a1a1a", "muted": "#555555",
    "grid": "#d0d0d0", "accent": "#0277bd", "accent2": "#e65100", "te": "#0277bd", "tm": "#d84315",
    "ref": "#757575", "warn": "#c62828", "cycle": ["#0277bd", "#e65100", "#2e7d32", "#c62828", "#6a1b9a",
                                                  "#f9a825", "#00838f", "#ad1457"],
}
GUI = {
    "name": "gui", "fig": "#ffffff", "ax": "#ffffff", "fg": "#0d2a4a", "muted": "#607d8b",
    "grid": "#dbe7f3", "accent": "#1565c0", "accent2": "#e65100", "te": "#1565c0", "tm": "#d84315",
    "ref": "#78909c", "warn": "#c62828", "cycle": ["#1565c0", "#e65100", "#2e7d32", "#c62828", "#6a1b9a",
                                                  "#f9a825", "#00838f", "#ad1457"],
}
RHO_CMAP = "turbo"          # blue = conductive (low rho), red = resistive (high rho)
PHASE_CMAP = "coolwarm"


def style_fig(fig, theme):
    fig.set_facecolor(theme["fig"])
    for ax in fig.axes:
        style_ax(ax, theme)


def style_ax(ax, theme):
    ax.set_facecolor(theme["ax"])
    for s in ax.spines.values():
        s.set_color(theme["muted"])
    ax.tick_params(colors=theme["fg"], which="both", labelsize=8)
    ax.xaxis.label.set_color(theme["fg"])
    ax.yaxis.label.set_color(theme["fg"])
    ax.title.set_color(theme["fg"])
    if getattr(ax, "_no_grid", False):
        ax.grid(False)
        return
    ax.grid(True, which="major", color=theme["grid"], lw=0.6, alpha=0.9)
    ax.grid(True, which="minor", color=theme["grid"], lw=0.3, alpha=0.4)


def style_colorbar(cb, theme, label):
    cb.set_label(label, color=theme["fg"], fontsize=8)
    cb.ax.tick_params(colors=theme["fg"], labelsize=7)
    cb.outline.set_edgecolor(theme["muted"])


def legend(ax, theme, **kw):
    lg = ax.legend(fontsize=7, framealpha=0.85, **kw)
    if lg:
        lg.get_frame().set_facecolor(theme["ax"])
        lg.get_frame().set_edgecolor(theme["muted"])
        for t in lg.get_texts():
            t.set_color(theme["fg"])
    return lg


def credit(fig, theme, text):
    fig.text(0.995, 0.004, text, ha="right", va="bottom", fontsize=6.5, color=theme["muted"], style="italic")



def auto_rho_scale(ax, values):
    """Log axis for rho_a unless the values span less than a factor 3 (then linear is clearer)."""
    import numpy as np
    v = np.asarray(values, float)
    v = v[np.isfinite(v) & (v > 0)]
    if v.size and v.max() / v.min() >= 3:
        ax.set_yscale("log")
    else:
        ax.set_yscale("linear")
