"""2D forward-modelling tab (finite-volume TE/TM solver, run in a worker thread)."""
import os

import numpy as np
from i18n import tr
from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSpinBox,
                               QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from appinfo import NOISE_MODEL_TEXT, metadata
from core.methods import METHODS
from core.mt_1d import apparent_resistivity, forward_1d, phase_deg
from core.mt_2d import convergence_check, run_2d
from core.noise import NOISE_LEVELS, add_impedance_noise
from export.export_csv import frame_2d, write_csv
from export.export_edi import write_edi
from export.export_excel import write_excel
from export.export_json import write_json
from export.export_report import write_report
from models.model_presets import PRESET_2D_DEFAULTS, PRESETS_2D, preset_2d
from models.resistivity_2d import Body, Model2D
from visualization.pseudosection import plot_pseudosection
from visualization.resistivity_model import plot_section
from visualization.response_plots import finish_rho_phase, plot_curve, setup_rho_phase
from visualization.theme import GUI, LIGHT, legend, auto_rho_scale, style_ax, style_fig

from .export_helpers import ask_dir, ask_save, export_figures, guarded
from .mpl import MplWidget
from .widgets import FreqConfig, label, sci_spin


class SimWorker(QThread):
    progress = Signal(int, int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            out = self.fn(lambda k, n, msg: self.progress.emit(k, n, msg), lambda: self._cancel)
            self.done.emit(out)
        except Exception as e:      # reported to the user, never hidden
            self.failed.emit(str(e))


def local_column(model: Model2D, y: float, nz=3000):
    """1D layered model directly below station y (for 2D-vs-1D comparison)."""
    z = np.linspace(0, model.depth, nz)
    r = model.rho_at(np.full_like(z, y), z)
    rho, thick, top = [r[0]], [], 0.0
    for k in range(1, nz):
        if r[k] != rho[-1]:
            zt = 0.5 * (z[k] + z[k - 1])
            thick.append(zt - top)
            top = zt
            rho.append(r[k])
    return rho, thick


class Tab2D(QWidget):
    computed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.result = None
        self.worker = None

        left = QWidget()
        ll = QVBoxLayout(left)
        g = QGroupBox(tr("2D model builder"))
        gl = QFormLayout(g)
        self.preset = QComboBox()
        self.preset.addItems(PRESETS_2D)
        self.preset.setCurrentIndex(3)
        self.width = sci_spin(100, 2e5, 4000, 0, " m")
        self.depth = sci_spin(50, 1e5, 2000, 0, " m")
        self.dx = sci_spin(1, 1e4, 25, 1, " m")
        self.dz = sci_spin(0.5, 1e4, 25, 1, " m")
        self.bg = sci_spin(0.01, 1e6, 300, 2, " Ω·m")
        self.an = sci_spin(0.01, 1e6, 5, 2, " Ω·m")
        self.aw = sci_spin(1, 1e5, 1000, 0, " m")
        self.at = sci_spin(0, 1e5, 200, 0, " m")
        self.ah = sci_spin(1, 1e5, 400, 0, " m")
        gl.addRow(tr("Preset"), self.preset)
        gl.addRow(tr("Model width"), self.width)
        gl.addRow(tr("Model depth"), self.depth)
        gl.addRow(tr("Δy (horizontal)"), self.dx)
        gl.addRow(tr("Δz (vertical, max)"), self.dz)
        gl.addRow(tr("Background ρ"), self.bg)
        gl.addRow(tr("Anomaly ρ"), self.an)
        gl.addRow(tr("Anomaly width"), self.aw)
        gl.addRow(tr("Anomaly top depth"), self.at)
        gl.addRow(tr("Anomaly thickness"), self.ah)
        self.b_build = QPushButton(tr("Build model from preset"))
        gl.addRow(self.b_build)
        sv = QHBoxLayout()
        self.b_save2d, self.b_load2d = QPushButton(tr("Save model…")), QPushButton(tr("Load model…"))
        sv.addWidget(self.b_save2d)
        sv.addWidget(self.b_load2d)
        gl.addRow(sv)
        ll.addWidget(g)

        gb = QGroupBox(tr("Background layers && bodies (table, optional)"))
        bl = QVBoxLayout(gb)
        self.t_bg = QTableWidget(0, 2)
        self.t_bg.setHorizontalHeaderLabels([tr("ρ (Ω·m)"), tr("h (m)")])
        self.t_bg.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.t_bg.setMaximumHeight(110)
        bl.addWidget(label(tr("Background (last row = half-space):")))
        bl.addWidget(self.t_bg)
        r0 = QHBoxLayout()
        self.b_bg_add, self.b_bg_rem = QPushButton(tr("+ Layer")), QPushButton(tr("− Layer"))
        r0.addWidget(self.b_bg_add)
        r0.addWidget(self.b_bg_rem)
        bl.addLayout(r0)
        self.t_bod = QTableWidget(0, 4)
        self.t_bod.setHorizontalHeaderLabels([tr("Name"), tr("Type"), tr("ρ (Ω·m)"), tr("Geometry")])
        self.t_bod.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.t_bod.setMinimumHeight(130)
        bl.addWidget(label(tr("Bodies (painted in order). rect geometry: y0, y1, z0, z1 — polygon: y:z; y:z; …")))
        bl.addWidget(self.t_bod)
        r1 = QHBoxLayout()
        self.b_rect, self.b_poly, self.b_brem = QPushButton(tr("+ Rect")), QPushButton(tr("+ Polygon")), QPushButton(tr("− Body"))
        for b in (self.b_rect, self.b_poly, self.b_brem):
            r1.addWidget(b)
        bl.addLayout(r1)
        ll.addWidget(gb)

        gs = QGroupBox(tr("Stations"))
        sl = QFormLayout(gs)
        self.st0 = sci_spin(0, 2e5, 200, 0, " m")
        self.st1 = sci_spin(0, 2e5, 3800, 0, " m")
        self.stn = QSpinBox()
        self.stn.setRange(1, 201)
        self.stn.setValue(21)
        self.b_st = QPushButton(tr("Apply stations"))
        sl.addRow(tr("First"), self.st0)
        sl.addRow(tr("Last"), self.st1)
        sl.addRow(tr("Number"), self.stn)
        sl.addRow(self.b_st)
        ll.addWidget(gs)

        self.fc = FreqConfig(n_default=13)
        ll.addWidget(self.fc)

        gr = QGroupBox(tr("Simulation"))
        rl = QFormLayout(gr)
        self.c_te, self.c_tm = QCheckBox(tr("TE (E-pol, Zxy)")), QCheckBox(tr("TM (H-pol, Zyx)"))
        self.c_te.setChecked(True)
        self.c_tm.setChecked(True)
        mr = QHBoxLayout()
        mr.addWidget(self.c_te)
        mr.addWidget(self.c_tm)
        rl.addRow(mr)
        self.refine = sci_spin(0.5, 3.0, 1.0, 2, "×")
        rl.addRow(tr("Mesh refinement"), self.refine)
        self.noise = QComboBox()
        self.noise.addItems(list(NOISE_LEVELS.keys()))
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(12345)
        rl.addRow(tr("Noise level"), self.noise)
        rl.addRow(tr("Random seed"), self.seed)
        self.b_run = QPushButton(tr("▶  Run simulation"))
        self.b_run.setObjectName("primary")
        self.b_cancel = QPushButton(tr("Cancel"))
        self.b_cancel.setEnabled(False)
        rr = QHBoxLayout()
        rr.addWidget(self.b_run, 2)
        rr.addWidget(self.b_cancel, 1)
        rl.addRow(rr)
        self.b_conv = QPushButton(tr("Mesh convergence check (3 frequencies)"))
        rl.addRow(self.b_conv)
        self.prog = QProgressBar()
        rl.addRow(self.prog)
        self.status = label("", "note")
        rl.addRow(self.status)
        ll.addWidget(gr)
        self.msg = label("", "warn")
        ll.addWidget(self.msg)
        ll.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(left)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(370)
        scroll.setMaximumWidth(450)

        # centre: drawing toolbar + section
        self.mp_sec = MplWidget(figsize=(6, 4))
        from PySide6.QtWidgets import QButtonGroup
        from .draw2d import SectionEditor
        self.editor = SectionEditor(self)
        drawbar = QWidget()
        dl_ = QHBoxLayout(drawbar)
        dl_.setContentsMargins(4, 2, 4, 2)
        dl_.addWidget(label("<b>" + tr("Draw the model") + ":</b>", "note", False))
        grp = QButtonGroup(self)
        for key, txt in (("select", tr("Select / edit")), ("poly", tr("Draw polygon")), ("rect", tr("Draw rectangle"))):
            b = QPushButton(txt)
            b.setCheckable(True)
            b.setChecked(key == "select")
            grp.addButton(b)
            b.clicked.connect(lambda _=False, k=key: self._set_draw_mode(k))
            dl_.addWidget(b)
        self.c_snap = QCheckBox(tr("Snap to grid"))
        self.c_snap.setChecked(True)
        self.c_snap.toggled.connect(lambda v: setattr(self.editor, "snap", v))
        dl_.addWidget(self.c_snap)
        dl_.addStretch(1)
        self.draw_hint = label(tr("Polygon: click to add vertices, double-click or right-click to close, Esc to cancel. "
                                  "Rectangle: press and drag. Edit: drag a vertex or a body; right-click a body for options; "
                                  "double-click a body to set ρ."))
        secw = QWidget()
        sl_ = QVBoxLayout(secw)
        sl_.setContentsMargins(0, 0, 0, 0)
        sl_.setSpacing(2)
        sl_.addWidget(drawbar)
        sl_.addWidget(self.draw_hint)
        sl_.addWidget(self.mp_sec, 1)
        self.diag = QTextBrowser()
        centre = QSplitter(Qt.Orientation.Vertical)
        centre.addWidget(secw)
        centre.addWidget(self.diag)
        centre.setSizes([520, 260])

        # right
        self.rtabs = QTabWidget()
        self.mp_ps = MplWidget(figsize=(7, 6))
        self.rtabs.addTab(self.mp_ps, tr("Pseudosections"))
        w_st = QWidget()
        wl = QVBoxLayout(w_st)
        self.st_combo = QComboBox()
        self.c_loc1d = QCheckBox(tr("Overlay 1D response of the column below the station"))
        self.c_loc1d.setChecked(True)
        h = QHBoxLayout()
        h.addWidget(label(tr("Station:"), "note", False))
        h.addWidget(self.st_combo, 1)
        h.addWidget(self.c_loc1d)
        wl.addLayout(h)
        self.mp_st = MplWidget(figsize=(7, 6))
        wl.addWidget(self.mp_st)
        self.rtabs.addTab(w_st, tr("Station curves"))
        w_pr = QWidget()
        pl = QVBoxLayout(w_pr)
        self.f_combo = QComboBox()
        h2 = QHBoxLayout()
        h2.addWidget(label(tr("Frequency:"), "note", False))
        h2.addWidget(self.f_combo, 1)
        pl.addLayout(h2)
        self.mp_pr = MplWidget(figsize=(7, 6))
        pl.addWidget(self.mp_pr)
        self.rtabs.addTab(w_pr, tr("Profiles"))
        w_dt = QWidget()
        dl = QVBoxLayout(w_dt)
        er = QHBoxLayout()
        self.ex = {}
        for k in ("CSV", "Excel", "JSON", tr("EDI (per station)"), tr("Figures (PNG+SVG)"), tr("Report (PDF)")):
            self.ex[k] = QPushButton(tr(k))
            er.addWidget(self.ex[k])
        dl.addLayout(er)
        self.data = QTableWidget()
        self.data.setAlternatingRowColors(True)
        self.data.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data.verticalHeader().setVisible(False)
        dl.addWidget(self.data)
        self.rtabs.addTab(w_dt, tr("Data table && export"))

        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(scroll)
        sp.addWidget(centre)
        sp.addWidget(self.rtabs)
        sp.setSizes([400, 560, 720])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(sp)

        # signals
        self.preset.currentTextChanged.connect(self._preset_defaults)
        self.b_build.clicked.connect(self.build_from_preset)
        self.b_save2d.clicked.connect(self.save_model)
        self.b_load2d.clicked.connect(self.open_model)
        self.b_st.clicked.connect(self.apply_stations)
        self.t_bg.itemChanged.connect(self._bg_edited)
        self.t_bod.itemChanged.connect(self._body_edited)
        self.b_bg_add.clicked.connect(self._bg_add)
        self.b_bg_rem.clicked.connect(self._bg_rem)
        self.b_rect.clicked.connect(lambda: self._add_body("rect"))
        self.b_poly.clicked.connect(lambda: self._add_body("polygon"))
        self.b_brem.clicked.connect(self._rem_body)
        for w in (self.width, self.depth, self.dx, self.dz):
            w.valueChanged.connect(self._grid_changed)
        self.b_run.clicked.connect(self.run)
        self.b_cancel.clicked.connect(self.cancel)
        self.b_conv.clicked.connect(self.convergence)
        self.st_combo.currentIndexChanged.connect(self.draw_station_tab)
        self.c_loc1d.toggled.connect(self.draw_station_tab)
        self.f_combo.currentIndexChanged.connect(self.draw_profile_tab)
        self.noise.currentTextChanged.connect(self._renoise)
        self.seed.valueChanged.connect(self._renoise)
        self.ex["CSV"].clicked.connect(self.export_csv)
        self.ex["Excel"].clicked.connect(self.export_excel)
        self.ex["JSON"].clicked.connect(self.export_json)
        self.ex[tr("EDI (per station)")].clicked.connect(self.export_edi)
        self.ex[tr("Figures (PNG+SVG)")].clicked.connect(lambda: export_figures(self, self._fig_builders()))
        self.ex[tr("Report (PDF)")].clicked.connect(self.export_report)
        self._set_export_enabled(False)

        self._preset_defaults(self.preset.currentText())
        self.build_from_preset()

    # ============================================================ model building
    def _preset_defaults(self, name):
        bg, an = PRESET_2D_DEFAULTS[name[0]]
        self.bg.setValue(bg)
        self.an.setValue(an)

    def params(self):
        return dict(bg=self.bg.value(), anom=self.an.value(), a_width=self.aw.value(), a_top=self.at.value(),
                    a_thick=self.ah.value(), width=self.width.value(), depth=self.depth.value(),
                    dx=self.dx.value(), dz=self.dz.value())

    def build_from_preset(self):
        m = preset_2d(self.preset.currentText(), **self.params())
        self.st0.setValue(round(0.05 * m.width))
        self.st1.setValue(round(0.95 * m.width))
        self.set_model(m)

    def set_model(self, m: Model2D):
        self.model = m
        self.fill_tables()
        self.model_changed()

    def save_model(self):
        p = ask_save(self, tr("Save 2D model"), "JSON (*.json)", "model_2d.json")
        if p:
            from appinfo import CREDIT
            guarded(self, write_json, p, {"type": "EM-Forward Lab 2D model", "credit": CREDIT,
                                          "model": self.model.to_dict()})

    def open_model(self):
        from PySide6.QtWidgets import QFileDialog
        from export.export_json import read_json
        p, _ = QFileDialog.getOpenFileName(self, tr("Load 2D model"), "", "JSON (*.json)")
        if p:
            def _load():
                d = read_json(p)
                m = Model2D.from_dict(d.get("model", d))
                errs = m.validate()
                if errs:
                    raise ValueError("; ".join(errs))
                self.set_model(m)
            guarded(self, _load)

    def _grid_changed(self):
        if self.model is None:
            return
        self.model.width, self.model.depth = self.width.value(), self.depth.value()
        self.model.dx, self.model.dz = self.dx.value(), self.dz.value()
        self.model.stations = [s for s in self.model.stations if s <= self.model.width]
        self.model_changed()

    def apply_stations(self):
        a, b, n = self.st0.value(), self.st1.value(), self.stn.value()
        if not (0 <= a <= self.model.width and 0 <= b <= self.model.width):
            self.msg.setText(tr("Stations must lie inside 0 … model width."))
            return
        self.model.stations = list(np.round(np.linspace(a, b, n), 2)) if n > 1 else [a]
        self.model_changed()

    def fill_tables(self):
        m = self.model
        self.t_bg.blockSignals(True)
        self.t_bg.setRowCount(len(m.bg_rho))
        for i, r in enumerate(m.bg_rho):
            self.t_bg.setItem(i, 0, QTableWidgetItem(f"{r:g}"))
            it = QTableWidgetItem(f"{m.bg_thick[i]:g}" if i < len(m.bg_thick) else "∞")
            if i == len(m.bg_rho) - 1:
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.t_bg.setItem(i, 1, it)
        self.t_bg.blockSignals(False)
        self.t_bod.blockSignals(True)
        self.t_bod.setRowCount(len(m.bodies))
        for i, b in enumerate(m.bodies):
            geo = ("; ".join(f"{p[0]:g}:{p[1]:g}" for p in b.points) if b.kind == "polygon"
                   else f"{b.x0:g}, {b.x1:g}, {b.z0:g}, {b.z1:g}")
            kind = QTableWidgetItem(b.kind)
            kind.setFlags(kind.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for c, it in enumerate([QTableWidgetItem(b.name), kind, QTableWidgetItem(f"{b.rho:g}"),
                                    QTableWidgetItem(geo)]):
                self.t_bod.setItem(i, c, it)
        self.t_bod.blockSignals(False)
        for w, v in ((self.width, m.width), (self.depth, m.depth), (self.dx, m.dx), (self.dz, m.dz)):
            w.blockSignals(True)
            w.setValue(v)
            w.blockSignals(False)

    def _bg_edited(self, item):
        try:
            v = float(item.text())
            if v <= 0:
                raise ValueError("value must be > 0")
            if item.column() == 0:
                self.model.bg_rho[item.row()] = v
            else:
                self.model.bg_thick[item.row()] = v
            self.msg.setText("")
        except ValueError as e:
            self.msg.setText(tr("Background row {i}: {e}", i=item.row() + 1, e=e))
        self.fill_tables()
        self.model_changed()

    def _bg_add(self):
        self.model.bg_rho.insert(len(self.model.bg_rho) - 1, self.model.bg_rho[-1])
        self.model.bg_thick.append(max(self.model.depth / 4, 1.0))
        self.fill_tables()
        self.model_changed()

    def _bg_rem(self):
        if len(self.model.bg_rho) > 1:
            self.model.bg_rho.pop(-2)
            self.model.bg_thick.pop(-1)
            self.fill_tables()
            self.model_changed()

    def _body_edited(self, item):
        i, c = item.row(), item.column()
        b = self.model.bodies[i]
        try:
            if c == 0:
                b.name = item.text()
            elif c == 2:
                v = float(item.text())
                if v <= 0:
                    raise ValueError("ρ must be > 0")
                b.rho = v
            elif c == 3:
                if b.kind == "polygon":
                    pts = [tuple(float(x) for x in p.split(":")) for p in item.text().split(";") if p.strip()]
                    if len(pts) < 3 or any(len(p) != 2 for p in pts):
                        raise ValueError("polygon needs ≥ 3 points written as y:z; y:z; …")
                    b.points = pts
                else:
                    v = [float(x) for x in item.text().split(",")]
                    if len(v) != 4 or v[1] <= v[0] or v[3] <= v[2]:
                        raise ValueError("rect needs y0, y1, z0, z1 with y1 > y0 and z1 > z0")
                    b.x0, b.x1, b.z0, b.z1 = v
            self.msg.setText("")
        except ValueError as e:
            self.msg.setText(tr("Body {i}: {e}", i=i + 1, e=e))
        self.fill_tables()
        self.model_changed()

    def _add_body(self, kind):
        w, d = self.model.width, self.model.depth
        if kind == "rect":
            b = Body("rect", 10.0, f"Body {len(self.model.bodies) + 1}", 0.4 * w, 0.6 * w, 0.1 * d, 0.3 * d)
        else:
            b = Body("polygon", 10.0, f"Body {len(self.model.bodies) + 1}",
                     points=[(0.3 * w, 0.1 * d), (0.7 * w, 0.1 * d), (0.6 * w, 0.4 * d), (0.4 * w, 0.4 * d)])
        self.model.bodies.append(b)
        self.fill_tables()
        self.model_changed()

    def _rem_body(self):
        i = self.t_bod.currentRow()
        if 0 <= i < len(self.model.bodies):
            self.model.bodies.pop(i)
            self.fill_tables()
            self.model_changed()

    def model_changed(self):
        errs = self.model.validate()
        if errs:
            self.msg.setText("⚠ " + "; ".join(errs))
        elif not self.msg.text().startswith(("Body", "Background", "Badan", "Baris")):
            self.msg.setText("")
        self.mp_sec.clear()
        self.draw_section(self.mp_sec.fig, GUI)
        self.mp_sec.draw()
        if self.result is not None:
            self.status.setText(tr("⚠ Model changed — the responses shown belong to the previous model. Press Run to update."))

    def draw_section(self, fig, theme, model=None):
        ax = fig.add_subplot(111)
        plot_section(fig, ax, model or self.model, theme)
        style_fig(fig, theme)
        if model is None and fig is self.mp_sec.fig and hasattr(self, "editor"):
            self.editor.attach(ax)

    def _set_draw_mode(self, k):
        self.editor.mode = k
        self.editor.pts = []
        self.mp_sec.canvas.setFocus()
        if self.mp_sec.toolbar.mode:
            if "pan" in str(self.mp_sec.toolbar.mode):
                self.mp_sec.toolbar.pan()
            else:
                self.mp_sec.toolbar.zoom()

    # ============================================================ simulation
    def _modes(self):
        return [m for m, c in (("TE", self.c_te), ("TM", self.c_tm)) if c.isChecked()]

    def _start(self, fn, on_done):
        if self.worker is not None and self.worker.isRunning():
            return
        self.b_run.setEnabled(False)
        self.b_conv.setEnabled(False)
        self.b_cancel.setEnabled(True)
        self.prog.setValue(0)
        self.worker = SimWorker(fn, self)
        self.worker.progress.connect(self._progress)
        self.worker.done.connect(on_done)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _progress(self, k, n, msg):
        self.prog.setMaximum(n)
        self.prog.setValue(k)
        self.status.setText(msg)

    def _failed(self, msg):
        self.status.setText("")
        QMessageBox.warning(self, tr("2D simulation"), msg)

    def _finished(self):
        self.b_run.setEnabled(True)
        self.b_conv.setEnabled(True)
        self.b_cancel.setEnabled(False)

    def cancel(self):
        if self.worker:
            self.worker.cancel()

    def run(self):
        try:
            f = self.fc.freqs()
        except ValueError as e:
            self.msg.setText(f"⚠ {e}")
            return
        modes = self._modes()
        errs = self.model.validate()
        if not modes:
            errs.append(tr("Select at least one mode (TE/TM)."))
        if errs:
            self.msg.setText("⚠ " + "; ".join(errs))
            return
        model = self.model.copy()
        refine = self.refine.value()
        method = self.fc.method_name()

        def job(progress, cancelled):
            r = run_2d(model, f, modes, refine, progress, cancelled)
            r["model"] = model
            r["method"] = method
            return r
        self._start(job, self._done)

    def _done(self, r):
        self.result = r
        self._renoise()
        d = r["diagnostics"]
        tt = sum(x["time_s"] for x in d)
        self.status.setText(tr("Done: {n} solves in {t:.1f} s.", n=len(d), t=tt))
        self._set_export_enabled(True)
        self.ex[tr("EDI (per station)")].setEnabled(METHODS[r["method"]]["edi"] and set(r["Z"]) == {"TE", "TM"})
        self.st_combo.blockSignals(True)
        self.st_combo.clear()
        self.st_combo.addItems([f"{i + 1}:  y = {y:g} m" for i, y in enumerate(r["stations"])])
        self.st_combo.setCurrentIndex(len(r["stations"]) // 2)
        self.st_combo.blockSignals(False)
        self.f_combo.blockSignals(True)
        self.f_combo.clear()
        self.f_combo.addItems([f"{f:.4g} Hz" for f in r["freq"]])
        self.f_combo.setCurrentIndex(len(r["freq"]) // 2)
        self.f_combo.blockSignals(False)
        self.redraw_results()
        self.computed.emit()

    def _renoise(self):
        r = self.result
        if r is None:
            return
        lvl = NOISE_LEVELS[self.noise.currentText()]
        r["noise"], r["seed"] = lvl, self.seed.value()
        r["Zobs"] = {m: add_impedance_noise(Z, lvl, self.seed.value() + k) for k, (m, Z) in
                     enumerate(r["Z"].items())} if lvl > 0 else None
        self.redraw_results()

    def redraw_results(self):
        if self.result is None:
            return
        self.write_diagnostics()
        self.mp_ps.clear()
        self.draw_pseudosections(self.mp_ps.fig, GUI)
        self.mp_ps.draw()
        self.draw_station_tab()
        self.draw_profile_tab()
        self.fill_data()

    def write_diagnostics(self):
        r = self.result
        d = r["diagnostics"]
        warn = [x for x in d if x["dx_over_delta"] > 0.5]
        res = max(x["residual"] for x in d)
        html = ("<h3 style='color:#1565c0;margin:2px'>Solver diagnostics</h3>"
                f"<p>Finite-volume TE/TM solver, frequency-adaptive mesh, refinement {r['refine']:g}×. "
                f"Max relative residual ‖Ax−b‖/‖b‖ = {res:.1e}. Max nodes = {max(x['nodes'] for x in d)}.</p>"
                "<table cellspacing=4><tr><th>mode</th><th>f (Hz)</th><th>nodes</th><th>Δz₀/δ</th>"
                "<th>Δy/δ</th><th>pad (m)</th><th>air (m)</th><th>t (s)</th></tr>")
        for x in d:
            col = "#c62828" if x["dx_over_delta"] > 0.5 else "#0d2a4a"
            html += (f"<tr style='color:{col}'><td>{x['mode']}</td><td>{x['freq']:.4g}</td><td>{x['nodes']}</td>"
                     f"<td>{x['dz0_over_delta']:.3f}</td><td>{x['dx_over_delta']:.2f}</td>"
                     f"<td>{x['pad_lateral_m']:.3g}</td><td>{x['air_m']:.3g}</td><td>{x['time_s']:.2f}</td></tr>")
        html += "</table>"
        if warn:
            html += ("<p style='color:#c62828'>Red rows: horizontal cells larger than half the surface skin depth. "
                     "Lateral variations at those frequencies are under-resolved — reduce Δy or increase "
                     "the refinement, then verify with the convergence check.</p>")
        html += ("<p style='color:#546e7a'>δ = skin depth of the most conductive surface material. Vertical cells "
                 "are automatically ≤ δ/10 near the surface and in conductors reached by the field.</p>")
        if r["method"] == "VLF-R":
            html += ("<p>VLF-R: choose TE if the transmitter's E-field is parallel to strike, TM if perpendicular. "
                     "Plane-wave (far-field) source assumed.</p>")
        self.diag.setHtml(html)

    def convergence(self):
        try:
            f = self.fc.freqs()
        except ValueError as e:
            self.msg.setText(f"⚠ {e}")
            return
        fs = np.unique([f.max(), f[len(f) // 2], f.min()])[::-1]
        model, refine, modes = self.model.copy(), self.refine.value(), self._modes() or ["TE"]

        def job(progress, cancelled):
            return convergence_check(model, fs, refine, 1.6, modes, progress)

        def done(rows):
            html = ("<h3 style='color:#1565c0;margin:2px'>Mesh convergence check</h3>"
                    f"<p>Mesh refinement {refine:g}× vs {refine * 1.6:g}× — maximum change over all stations:</p>"
                    "<table cellspacing=6><tr><th>mode</th><th>f (Hz)</th><th>max Δρa (%)</th><th>max Δφ (°)</th></tr>")
            for x in rows:
                col = "#2e7d32" if x["max_drho_pct"] < 2 and x["max_dphase_deg"] < 1 else "#c62828"
                html += (f"<tr style='color:{col}'><td>{x['mode']}</td><td>{x['freq']:.4g}</td>"
                         f"<td>{x['max_drho_pct']:.2f}</td><td>{x['max_dphase_deg']:.2f}</td></tr>")
            html += ("</table><p style='color:#546e7a'>Green: change &lt; 2 % / 1°. Larger changes usually occur only "
                     "at stations sitting exactly on a sharp contact (TM). Otherwise refine the mesh.</p>")
            self.diag.setHtml(html)
            self.status.setText(tr("Convergence check finished."))
        self._start(job, done)

    # ============================================================ result plots
    def _rho_phase(self, mode, obs=False):
        r = self.result
        Z = r["Zobs"][mode] if obs and r.get("Zobs") else r["Z"][mode]
        return apparent_resistivity(Z, r["freq"][:, None]), phase_deg(Z)

    def draw_pseudosections(self, fig, theme):
        r = self.result
        modes = list(r["Z"].keys())
        if len(r["freq"]) < 2:
            ax = fig.add_subplot(111)
            style_ax(ax, theme)
            ax.text(0.5, 0.5, "Pseudosections need ≥ 2 frequencies.\nSee the 'Profiles' tab.",
                    ha="center", va="center", color=theme["fg"], transform=ax.transAxes)
            style_fig(fig, theme)
            return
        gs = fig.add_gridspec(2, len(modes))
        allr = np.concatenate([self._rho_phase(m)[0].ravel() for m in modes])
        from matplotlib.colors import LogNorm
        norm = LogNorm(allr.min(), allr.max() * 1.0001)
        for j, m in enumerate(modes):
            ra, ph = self._rho_phase(m)
            plot_pseudosection(fig, fig.add_subplot(gs[0, j]), r["stations"], r["freq"], ra, theme, "rho",
                               f"{m} apparent resistivity", norm=norm)
            plot_pseudosection(fig, fig.add_subplot(gs[1, j]), r["stations"], r["freq"], ph, theme, "phase",
                               f"{m} phase")
        style_fig(fig, theme)

    def draw_station_tab(self):
        if self.result is None:
            return
        self.mp_st.clear()
        self.draw_station(self.mp_st.fig, GUI, self.st_combo.currentIndex())
        self.mp_st.draw()

    def draw_station(self, fig, theme, k):
        r = self.result
        k = max(0, min(k, len(r["stations"]) - 1))
        y = r["stations"][k]
        f = r["freq"]
        ax_r = fig.add_subplot(211)
        ax_p = fig.add_subplot(212, sharex=ax_r)
        setup_rho_phase(ax_r, ax_p, theme)
        mk = "o" if f.size < 12 else None
        for m in r["Z"]:
            ra, ph = self._rho_phase(m)
            noisy = None
            if r.get("Zobs"):
                ro, po = self._rho_phase(m, True)
                noisy = (ro[:, k], po[:, k])
            plot_curve(ax_r, ax_p, f, ra[:, k], ph[:, k], f"2D {m}", theme["te" if m == "TE" else "tm"],
                       marker=mk, noisy=noisy)
        if self.c_loc1d.isChecked():
            rho, th = local_column(r["model"], y)
            ref = forward_1d(rho, th, f)
            plot_curve(ax_r, ax_p, f, ref["rho_a"], ref["phase"], tr("1D column below station"), theme["ref"], ls="--")
        finish_rho_phase(ax_r, ax_p, theme, f)
        ax_r.set_title(tr("Station at y = {y} m ({m})", y=f"{y:g}", m=r['method']), fontsize=10)
        style_fig(fig, theme)

    def draw_profile_tab(self):
        if self.result is None:
            return
        self.mp_pr.clear()
        self.draw_profile(self.mp_pr.fig, GUI, self.f_combo.currentIndex())
        self.mp_pr.draw()

    def draw_profile(self, fig, theme, i):
        r = self.result
        i = max(0, min(i, len(r["freq"]) - 1))
        st = r["stations"]
        ax_r = fig.add_subplot(311)
        ax_p = fig.add_subplot(312, sharex=ax_r)
        ax_m = fig.add_subplot(313, sharex=ax_r)
        for ax in (ax_r, ax_p):
            style_ax(ax, theme)
        auto_rho_scale(ax_r, np.concatenate([self._rho_phase(m)[0][i] for m in r["Z"]]))
        for m in r["Z"]:
            ra, ph = self._rho_phase(m)
            c = theme["te" if m == "TE" else "tm"]
            ax_r.plot(st, ra[i], "-o", ms=3, color=c, label=m)
            ax_p.plot(st, ph[i], "-o", ms=3, color=c)
            if r.get("Zobs"):
                ro, po = self._rho_phase(m, True)
                ax_r.plot(st, ro[i], "o", mfc="none", color=c, label=f"{m} noisy obs.")
                ax_p.plot(st, po[i], "o", mfc="none", color=c)
        ax_r.set_ylabel("ρa (Ω·m)")
        ax_p.set_ylabel("φ (°)")
        ax_p.axhline(45, color=theme["muted"], ls=":", lw=0.8)
        ax_r.set_title(tr("Profile at f = {f} Hz ({m})", f=f"{r['freq'][i]:.4g}", m=r['method']), fontsize=10)
        legend(ax_r, theme)
        plot_section(fig, ax_m, r["model"], theme, colorbar=False)
        ax_m.set_title("")
        ax_m.set_xlim(0, r["model"].width)
        ax_r.tick_params(labelbottom=False)
        ax_p.tick_params(labelbottom=False)
        style_fig(fig, theme)

    def fill_data(self):
        df = self._frame()
        self.data.setRowCount(len(df))
        self.data.setColumnCount(len(df.columns))
        self.data.setHorizontalHeaderLabels(list(df.columns))
        vals = df.values
        for i in range(min(len(df), 5000)):
            for j, v in enumerate(vals[i]):
                self.data.setItem(i, j, QTableWidgetItem(v if isinstance(v, str) else f"{v:.5g}"))
        self.data.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ============================================================ export
    def _set_export_enabled(self, on):
        for b in self.ex.values():
            b.setEnabled(on)

    def _frame(self):
        r = self.result
        df = frame_2d(r)
        if r.get("Zobs"):
            obs = frame_2d(r, r["Zobs"])
            df["Apparent_Resistivity_Obs_OhmM"] = obs["Apparent_Resistivity_OhmM"]
            df["Phase_Obs_Deg"] = obs["Phase_Deg"]
            df["Impedance_Obs_Real"] = obs["Impedance_Real"]
            df["Impedance_Obs_Imag"] = obs["Impedance_Imag"]
        return df

    def _meta(self):
        r = self.result
        return metadata(method=r["method"], method_assumption=METHODS[r["method"]]["assumption"],
                        model=r["model"].to_dict(), frequency_config=self.fc.state(), modes=list(r["Z"]),
                        solver=("2D finite-volume (node-based, 5-point), frequency-adaptive tensor mesh, "
                                "Dirichlet BC from 1D edge columns, SciPy SuperLU"),
                        mesh_refinement=r["refine"], noise_level=r.get("noise", 0.0), noise_seed=r.get("seed"),
                        noise_model=NOISE_MODEL_TEXT,
                        mode_convention="TE: Z = Ex/Hy (Zxy); TM: Z = -Ey/Hx (= -Zyx)",
                        diagnostics=r["diagnostics"])

    def export_csv(self):
        p = ask_save(self, "Export CSV", "CSV (*.csv)", f"synthetic_2d_{self.result['method']}.csv")
        if p:
            guarded(self, write_csv, p, self._frame(), self._meta(), done_msg=f"Saved {p}")

    def export_excel(self):
        p = ask_save(self, "Export Excel", "Excel (*.xlsx)", f"synthetic_2d_{self.result['method']}.xlsx")
        if p:
            guarded(self, write_excel, p, self._frame(), self.result["model"].to_dict(), self._meta(),
                    done_msg=f"Saved {p}")

    def export_json(self):
        p = ask_save(self, "Export JSON", "JSON (*.json)", f"synthetic_2d_{self.result['method']}.json")
        if p:
            guarded(self, write_json, p, {"metadata": self._meta(), "data": self._frame().to_dict(orient="list")},
                    done_msg=f"Saved {p}")

    def export_edi(self):
        r = self.result
        d = ask_dir(self, tr("Folder for EDI files (one per station)"))
        if not d:
            return

        def _do():
            Z = r["Zobs"] if r.get("Zobs") else r["Z"]
            for k, y in enumerate(r["stations"]):
                name = f"ST{k + 1:03d}"
                info = [f"Method: {r['method']} 2D synthetic, strike = x, Zxy = TE, Zyx = -Z_TM",
                        f"Model: {r['model'].title}"]
                write_edi(os.path.join(d, name + ".edi"), r["freq"], Z["TE"][:, k], -Z["TM"][:, k], name, info,
                          r.get("noise", 0.0), y)
        guarded(self, _do, done_msg=f"Saved {len(r['stations'])} EDI files in\n{d}")

    def _fig_builders(self):
        r = self.result
        k, i = self.st_combo.currentIndex(), self.f_combo.currentIndex()
        return [("model_2d", lambda fig, th: self.draw_section(fig, th, r["model"])),
                ("pseudosections_2d", self.draw_pseudosections),
                ("station_curves_2d", lambda fig, th: self.draw_station(fig, th, k)),
                ("profile_2d", lambda fig, th: self.draw_profile(fig, th, i))]

    def export_report(self):
        p = ask_save(self, "Export report", "PDF (*.pdf)", f"report_2d_{self.result['method']}.pdf")
        if not p:
            return
        r = self.result
        m = r["model"]
        lines = [f"Method: {r['method']}  —  {METHODS[r['method']]['name']}",
                 "Source assumption: " + METHODS[r["method"]]["assumption"], "",
                 f"Model: {m.title}; width {m.width:g} m, depth {m.depth:g} m, dy {m.dx:g} m, dz(max) {m.dz:g} m",
                 "Background rho: " + ", ".join(f"{v:g}" for v in m.bg_rho) + " Ohm.m; thickness: " +
                 ", ".join(f"{v:g}" for v in m.bg_thick) + " m"]
        for b in m.bodies:
            geo = (str([tuple(round(c, 1) for c in p) for p in b.points]) if b.kind == "polygon"
                   else f"y {b.x0:g}..{b.x1:g}, z {b.z0:g}..{b.z1:g}")
            lines.append(f"  Body '{b.name}': {b.rho:g} Ohm.m, {b.kind} {geo}")
        lines += ["", f"Stations: {len(r['stations'])} ({r['stations'].min():g} – {r['stations'].max():g} m)",
                  f"Frequencies: {r['freq'].size} ({r['freq'].min():.4g} – {r['freq'].max():.4g} Hz); modes "
                  + ", ".join(r["Z"]), "",
                  "Solver: 2D finite-volume, frequency-adaptive mesh; Dirichlet BCs from 1D edge columns.",
                  f"Mesh refinement {r['refine']:g}x; max residual {max(x['residual'] for x in r['diagnostics']):.1e}",
                  f"Noise: {r.get('noise', 0) * 100:g} %  ({NOISE_MODEL_TEXT})"]
        builders = [(lambda b: (lambda fig: b(fig, LIGHT)))(b) for _, b in self._fig_builders()]
        guarded(self, write_report, p, "2D forward model report", lines, builders, self._meta(),
                done_msg=f"Saved {p}")

    # ============================================================ session
    def state(self):
        return {"model": self.model.to_dict(), "preset": self.preset.currentText(), "params": self.params(),
                "freq": self.fc.state(), "modes": self._modes(), "refine": self.refine.value(),
                "noise": self.noise.currentText(), "seed": self.seed.value()}

    def set_state(self, s):
        self.preset.blockSignals(True)
        self.preset.setCurrentText(s.get("preset", PRESETS_2D[3]))
        self.preset.blockSignals(False)
        p = s.get("params", {})
        for w, k in ((self.bg, "bg"), (self.an, "anom"), (self.aw, "a_width"), (self.at, "a_top"),
                     (self.ah, "a_thick")):
            if k in p:
                w.setValue(p[k])
        self.fc.set_state(s["freq"])
        self.c_te.setChecked("TE" in s.get("modes", ["TE", "TM"]))
        self.c_tm.setChecked("TM" in s.get("modes", ["TE", "TM"]))
        self.refine.setValue(s.get("refine", 1.0))
        self.noise.setCurrentText(s.get("noise", "Noise-free"))
        self.seed.setValue(s.get("seed", 12345))
        self.result = None
        self.set_model(Model2D.from_dict(s["model"]))
