"""Drag-to-edit for the 1D layered model plot."""
import numpy as np

PICK_PX = 7


class LayerEditor:
    """Drag a horizontal boundary to change depth, drag a layer's vertical line to change ρ,
    double-click inside a layer to split it."""

    def __init__(self, tab):
        self.tab = tab
        self.ax = None
        self.drag = None
        self.zmax = None
        c = tab.mp_model.canvas
        c.mpl_connect("button_press_event", self.press)
        c.mpl_connect("motion_notify_event", self.motion)
        c.mpl_connect("button_release_event", self.release)

    def attach(self, ax):
        self.ax = ax

    def _px(self, x, z):
        return self.ax.transData.transform((x, z))

    def press(self, ev):
        if self.ax is None or ev.inaxes is not self.ax or ev.xdata is None or self.tab.mp_model.toolbar.mode:
            return
        m = self.tab.model
        tops = m.depths()
        bots = np.concatenate([tops[1:], [np.inf]])
        if ev.dblclick:
            z = ev.ydata
            j = int(np.searchsorted(tops, z, side="right") - 1)
            if z > tops[j] + 1:
                if j < m.n - 1:
                    h_above = z - tops[j]
                    h_below = m.thick[j] - h_above
                    m.thick[j] = h_above
                    m.thick.insert(j + 1, h_below)
                else:
                    m.thick.append(z - tops[j])
                m.rho.insert(j + 1, m.rho[j])
                if m.names:
                    m.names.insert(j + 1, "")
                self._update()
            return
        # boundary?
        for i in range(1, m.n):
            if abs(self._px(ev.xdata, tops[i])[1] - ev.y) < PICK_PX:
                self.drag = ("z", i)
                self.zmax = self.ax.get_ylim()[0]
                return
        # vertical rho line of a layer?
        j = int(np.searchsorted(tops, ev.ydata, side="right") - 1)
        if 0 <= j < m.n and abs(self._px(m.rho[j], ev.ydata)[0] - ev.x) < PICK_PX * 1.5:
            self.drag = ("rho", j)
            self.tab.table.selectRow(j)

    def motion(self, ev):
        if not self.drag or ev.inaxes is None or ev.xdata is None:
            return
        m = self.tab.model
        kind, i = self.drag
        if kind == "z":
            tops = m.depths()
            lo = tops[i - 1] + 0.5
            hi = tops[i + 1] - 0.5 if i + 1 < m.n else np.inf
            z = float(np.clip(ev.ydata, lo, hi))
            z = float(f"{z:.3g}")
            old = tops[i]
            m.thick[i - 1] = z - tops[i - 1]
            if i < m.n - 1:
                m.thick[i] = m.thick[i] + (old - z)
        else:
            m.rho[i] = float(f"{np.clip(ev.xdata, 0.1, 1e5):.3g}")
        self._update(live=True)

    def release(self, ev):
        if self.drag:
            self.drag = None
            self._update()

    def _update(self, live=False):
        t = self.tab
        t.fill_table()
        if live:
            if not t._timer.isActive():
                t._timer.start()
        else:
            t._sel_changed()
            t.schedule()
