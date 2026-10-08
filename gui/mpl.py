"""Matplotlib canvas widget with navigation toolbar (zoom/pan/save) and hover read-out."""
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PySide6.QtWidgets import QVBoxLayout, QWidget

from visualization.theme import GUI


class MplWidget(QWidget):
    def __init__(self, parent=None, figsize=(6, 4), toolbar=True):
        super().__init__(parent)
        self.fig = Figure(figsize=figsize, facecolor=GUI["fig"], layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        if toolbar:
            self.toolbar = NavigationToolbar2QT(self.canvas, self)
            self.toolbar.setStyleSheet("QToolBar{background:#f7fbff; border-bottom:1px solid #e3f2fd;} "
                                       "QToolButton{background:transparent; border-radius:3px; margin:1px;} "
                                       "QToolButton:hover{background:#e3f2fd;} QLabel{color:#546e7a;}")
            lay.addWidget(self.toolbar)
        lay.addWidget(self.canvas)
        self._annot = {}
        self.canvas.mpl_connect("motion_notify_event", self._hover)

    def clear(self):
        self.fig.clear()
        self.fig.set_facecolor(GUI["fig"])
        self._annot = {}

    def draw(self):
        self.canvas.draw_idle()

    # nearest-point hover on line plots
    def _hover(self, ev):
        ax = ev.inaxes
        if ax is None or ev.xdata is None:
            for a in self._annot.values():
                a.set_visible(False)
            return
        best = None
        for ln in ax.get_lines():
            x, y = np.asarray(ln.get_xdata(), float), np.asarray(ln.get_ydata(), float)
            if x.size < 2 or not ln.get_visible() or ln.get_label().startswith("_"):
                continue
            px = ax.transData.transform(np.column_stack([x, y]))
            d = np.hypot(px[:, 0] - ev.x, px[:, 1] - ev.y)
            k = int(np.nanargmin(d))
            if d[k] < 12 and (best is None or d[k] < best[0]):
                best = (d[k], x[k], y[k], ln.get_label())
        an = self._annot.get(ax)
        if an is None:
            an = ax.annotate("", xy=(0, 0), xytext=(10, 10), textcoords="offset points", fontsize=8,
                             color="#0d2a4a", bbox=dict(boxstyle="round", fc="#ffffff", ec="#1565c0", alpha=0.95))
            an.set_visible(False)
            self._annot[ax] = an
        if best:
            an.xy = (best[1], best[2])
            an.set_text(f"{best[3]}\nx = {best[1]:.4g}\ny = {best[2]:.4g}")
            an.set_visible(True)
        else:
            an.set_visible(False)
        self.canvas.draw_idle()
