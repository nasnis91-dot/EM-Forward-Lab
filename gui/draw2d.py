"""Interactive drawing / editing of 2D bodies on the resistivity section (Talwani-style)."""
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.path import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QInputDialog, QMenu

from i18n import tr
from models.resistivity_2d import Body

PICK_PX = 9


def corners(b):
    if b.kind == "polygon":
        return [tuple(p) for p in b.points]
    return [(b.x0, b.z0), (b.x1, b.z0), (b.x1, b.z1), (b.x0, b.z1)]


class SectionEditor:
    def __init__(self, tab):
        self.tab = tab
        self.mode = "select"
        self.snap = True
        self.sel = None              # selected body index
        self.pts = []                # polygon being drawn
        self.drag = None             # ("vertex", body, k) | ("body", body, (y0, z0), original_points)
        self.ax = None
        self.ghost = None
        self.handles = None
        c = tab.mp_sec.canvas
        c.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        c.mpl_connect("button_press_event", self.press)
        c.mpl_connect("motion_notify_event", self.motion)
        c.mpl_connect("button_release_event", self.release)
        c.mpl_connect("key_press_event", self.key)

    # ------------------------------------------------------------ helpers
    def attach(self, ax):
        """Called after every redraw of the section."""
        self.ax = ax
        self.ghost = Line2D([], [], color="#ffffff", lw=1.8, ls="-", marker="o", ms=5, mfc="#1565c0", zorder=10)
        self.handles = Line2D([], [], ls="none", marker="s", ms=7, mfc="#ffeb3b", mec="#0d2a4a", zorder=11)
        ax.add_line(self.ghost)
        ax.add_line(self.handles)
        self._show_handles()

    def _snap(self, y, z):
        if not self.snap:
            return float(y), float(z)
        m = self.tab.model
        return float(np.round(y / m.dx) * m.dx), float(max(np.round(z / m.dz) * m.dz, 0.0))

    def _px(self, y, z):
        return self.ax.transData.transform((y, z))

    def _show_handles(self):
        if self.handles is None:
            return
        bodies = self.tab.model.bodies
        if self.sel is not None and self.sel < len(bodies):
            c = np.array(corners(bodies[self.sel]), float)
            c[:, 0] = np.clip(c[:, 0], -0.02 * self.tab.model.width, 1.02 * self.tab.model.width)
            c[:, 1] = np.clip(c[:, 1], 0, 1.02 * self.tab.model.depth)
            self.handles.set_data(c[:, 0], c[:, 1])
        else:
            self.handles.set_data([], [])

    def _hit_vertex(self, ev):
        best = None
        for bi, b in enumerate(self.tab.model.bodies):
            for k, (y, z) in enumerate(corners(b)):
                if abs(y) > 1e7 or abs(z) > 1e7:
                    continue
                px = self._px(y, z)
                d = np.hypot(px[0] - ev.x, px[1] - ev.y)
                if d < PICK_PX and (best is None or d < best[0]):
                    best = (d, bi, k)
        return best

    def _hit_body(self, y, z):
        for bi in range(len(self.tab.model.bodies) - 1, -1, -1):
            if self.tab.model.bodies[bi].mask(np.array([y]), np.array([z]))[0]:
                return bi
        return None

    def _redraw(self):
        self.tab.fill_tables()
        self.tab.model_changed()

    def _ask_rho(self, default=10.0, title=None):
        v, ok = QInputDialog.getDouble(self.tab, title or tr("New body"), tr("Resistivity of the new body (Ω·m):"),
                                       default, 0.01, 1e6, 3)
        return v if ok else None

    # ------------------------------------------------------------ events
    def press(self, ev):
        if ev.inaxes is not self.ax or ev.xdata is None or self.tab.mp_sec.toolbar.mode:
            return
        y, z = self._snap(ev.xdata, ev.ydata)
        if self.mode == "poly":
            if ev.button == 3 or ev.dblclick:
                self._finish_poly()
                return
            self.pts.append((y, z))
            self._update_ghost(self.pts)
            return
        if self.mode == "rect":
            self.drag = ("rect", (y, z))
            return
        # select / edit
        hv = self._hit_vertex(ev)
        bi = hv[1] if hv else self._hit_body(ev.xdata, ev.ydata)
        if ev.button == 3:
            if bi is not None:
                self.sel = bi
                self._menu(bi, hv[2] if hv else None)
            return
        if ev.dblclick and bi is not None:
            b = self.tab.model.bodies[bi]
            v = self._ask_rho(b.rho, b.name)
            if v:
                b.rho = v
                self._redraw()
            return
        self.sel = bi
        if hv:
            self.drag = ("vertex", hv[1], hv[2])
        elif bi is not None:
            self.drag = ("body", bi, (ev.xdata, ev.ydata), corners(self.tab.model.bodies[bi]))
        self._show_handles()
        self.tab.mp_sec.canvas.draw_idle()

    def motion(self, ev):
        if ev.inaxes is not self.ax or ev.xdata is None:
            return
        y, z = self._snap(ev.xdata, ev.ydata)
        if self.mode == "poly" and self.pts:
            self._update_ghost(self.pts + [(y, z)])
        elif self.drag and self.drag[0] == "rect":
            (y0, z0) = self.drag[1]
            self._update_ghost([(y0, z0), (y, z0), (y, z), (y0, z), (y0, z0)])
        elif self.drag and self.drag[0] == "vertex":
            b = self.tab.model.bodies[self.drag[1]]
            self._move_vertex(b, self.drag[2], y, z)
            c = corners(b)
            self._update_ghost(c + [c[0]])
        elif self.drag and self.drag[0] == "body":
            _, bi, (ys, zs), orig = self.drag
            dy, dz = self._snap(ev.xdata - ys, ev.ydata - zs)
            b = self.tab.model.bodies[bi]
            moved = [(p[0] + dy, p[1] + dz) for p in orig]
            self._set_corners(b, moved)
            self._update_ghost(moved + [moved[0]])

    def release(self, ev):
        if not self.drag:
            return
        kind = self.drag[0]
        if kind == "rect" and ev.xdata is not None:
            (y0, z0) = self.drag[1]
            y1, z1 = self._snap(ev.xdata, ev.ydata)
            self.drag = None
            self._update_ghost([])
            if abs(y1 - y0) > 0 and abs(z1 - z0) > 0:
                v = self._ask_rho()
                if v:
                    m = self.tab.model
                    m.bodies.append(Body("rect", v, tr("Body {i}", i=len(m.bodies) + 1), min(y0, y1), max(y0, y1),
                                         min(z0, z1), max(z0, z1)))
                    self.sel = len(m.bodies) - 1
                    self._redraw()
            return
        self.drag = None
        self._update_ghost([])
        self._redraw()

    def key(self, ev):
        if ev.key == "escape":
            self.pts = []
            self.drag = None
            self._update_ghost([])
        elif ev.key in ("delete", "backspace") and self.sel is not None and self.mode == "select":
            self.tab.model.bodies.pop(self.sel)
            self.sel = None
            self._redraw()
        elif ev.key == "enter" and self.mode == "poly":
            self._finish_poly()

    # ------------------------------------------------------------ geometry
    def _update_ghost(self, pts):
        if self.ghost is None:
            return
        if pts:
            a = np.array(pts, float)
            self.ghost.set_data(a[:, 0], a[:, 1])
        else:
            self.ghost.set_data([], [])
        self.tab.mp_sec.canvas.draw_idle()

    def _finish_poly(self):
        pts = list(dict.fromkeys(self.pts))
        self.pts = []
        self._update_ghost([])
        if len(pts) < 3:
            return
        v = self._ask_rho()
        if v:
            m = self.tab.model
            m.bodies.append(Body("polygon", v, tr("Body {i}", i=len(m.bodies) + 1), points=pts))
            self.sel = len(m.bodies) - 1
            self._redraw()

    @staticmethod
    def _set_corners(b, pts):
        if b.kind == "polygon":
            b.points = [tuple(p) for p in pts]
        else:
            ys, zs = [p[0] for p in pts], [p[1] for p in pts]
            b.x0, b.x1, b.z0, b.z1 = min(ys), max(ys), min(zs), max(zs)

    def _move_vertex(self, b, k, y, z):
        if b.kind == "polygon":
            b.points[k] = (y, z)
        else:
            if k in (0, 3):
                b.x0 = y
            else:
                b.x1 = y
            if k in (0, 1):
                b.z0 = z
            else:
                b.z1 = z
            if b.x1 < b.x0:
                b.x0, b.x1 = b.x1, b.x0
            if b.z1 < b.z0:
                b.z0, b.z1 = b.z1, b.z0

    def _menu(self, bi, vertex):
        b = self.tab.model.bodies[bi]
        menu = QMenu(self.tab)
        a_rho = menu.addAction(tr("Set resistivity…"))
        a_name = menu.addAction(tr("Rename…"))
        a_front = menu.addAction(tr("Bring to front"))
        a_vert = menu.addAction(tr("Delete vertex")) if (vertex is not None and b.kind == "polygon" and len(b.points) > 3) else None
        menu.addSeparator()
        a_del = menu.addAction(tr("Delete body"))
        act = menu.exec(QCursor.pos())
        if act is None:
            return
        if act == a_rho:
            v = self._ask_rho(b.rho, b.name)
            if v:
                b.rho = v
        elif act == a_name:
            s, ok = QInputDialog.getText(self.tab, tr("Rename…"), tr("Body name:"), text=b.name)
            if ok and s:
                b.name = s
        elif act == a_front:
            self.tab.model.bodies.append(self.tab.model.bodies.pop(bi))
            self.sel = len(self.tab.model.bodies) - 1
        elif act == a_vert:
            b.points.pop(vertex)
        elif act == a_del:
            self.tab.model.bodies.pop(bi)
            self.sel = None
        self._redraw()
