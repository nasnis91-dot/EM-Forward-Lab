"""1D forward-modelling tab."""
import json

import numpy as np
from i18n import tr
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from appinfo import CREDIT, NOISE_MODEL_TEXT, metadata
from core.methods import METHODS, far_field_check
from core.mt_1d import apparent_resistivity, bostick, forward_1d, phase_deg, validate_freqs
from core.noise import NOISE_LEVELS, add_impedance_noise
from core.skin_depth import skin_depth
from education.interpretation import interpret_1d, interpret_change
from export.export_csv import frame_1d, write_csv
from export.export_edi import write_edi
from export.export_excel import write_excel
from export.export_json import read_json, write_json
from export.export_report import write_report
from models.layered_earth import LayeredModel
from models.model_presets import PRESETS_1D
from visualization.resistivity_model import plot_layered
from visualization.response_plots import (finish_rho_phase, plot_curve, plot_impedance, setup_rho_phase,
                                          shade_invalid)
from visualization.theme import GUI, LIGHT, style_fig

from .export_helpers import ask_save, export_figures, guarded
from .mpl import MplWidget
from .widgets import FreqConfig, LogSlider, label


class Tab1D(QWidget):
    computed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = PRESETS_1D["B - Conductive layer"].copy()
        self.reference = None
        self.res = None
        self._timer = QTimer(self, singleShot=True, interval=25)
        self._timer.timeout.connect(self.recompute)

        # ---------------- left panel
        left = QWidget()
        ll = QVBoxLayout(left)
        self.fc = FreqConfig()
        ll.addWidget(self.fc)

        g = QGroupBox(tr("Earth model"))
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        self.preset = QComboBox()
        self.preset.addItems(list(PRESETS_1D.keys()))
        self.preset.setCurrentText("B - Conductive layer")
        b_load = QPushButton(tr("Load"))
        row.addWidget(self.preset, 1)
        row.addWidget(b_load)
        gl.addLayout(row)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([tr("Name"), tr("ρ (Ω·m)"), tr("h (m)"), tr("Top (m)")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(150)
        gl.addWidget(self.table)
        r1 = QHBoxLayout()
        self.b_add, self.b_rem, self.b_reset = QPushButton(tr("+ Layer")), QPushButton(tr("− Layer")), QPushButton(tr("Reset"))
        for b in (self.b_add, self.b_rem, self.b_reset):
            r1.addWidget(b)
        gl.addLayout(r1)
        r2 = QHBoxLayout()
        self.b_save, self.b_open = QPushButton(tr("Save model…")), QPushButton(tr("Load model…"))
        r2.addWidget(self.b_save)
        r2.addWidget(self.b_open)
        gl.addLayout(r2)
        self.sel_lbl = label("", "section")
        gl.addWidget(self.sel_lbl)
        fl = QFormLayout()
        self.s_rho = LogSlider(0.1, 1e5, 100.0, " Ω·m")
        self.s_h = LogSlider(0.5, 1e5, 100.0, " m")
        fl.addRow("ρ", self.s_rho)
        fl.addRow("h", self.s_h)
        gl.addLayout(fl)
        gl.addWidget(label(tr("Draw on the model: drag a layer boundary up/down, drag a layer's resistivity line left/right, "
                              "double-click to split a layer.")))
        ll.addWidget(g)

        g2 = QGroupBox(tr("Display && comparison"))
        f2 = QFormLayout(g2)
        self.c_z = QCheckBox(tr("Show complex impedance (Re/Im Z)"))
        self.c_bos = QCheckBox(tr("Show Niblett–Bostick transform on model"))
        self.c_bos.setChecked(True)
        self.noise = QComboBox()
        self.noise.addItems(list(NOISE_LEVELS.keys()))
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(12345)
        f2.addRow(self.c_z)
        f2.addRow(self.c_bos)
        f2.addRow(tr("Noise level"), self.noise)
        f2.addRow(tr("Random seed"), self.seed)
        f2.addRow(label("Noise model: " + NOISE_MODEL_TEXT))
        rr = QHBoxLayout()
        self.b_pin, self.b_unpin = QPushButton(tr("Pin as reference")), QPushButton(tr("Clear reference"))
        rr.addWidget(self.b_pin)
        rr.addWidget(self.b_unpin)
        f2.addRow(rr)
        ll.addWidget(g2)
        self.msg = label("", "warn")
        ll.addWidget(self.msg)
        ll.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidget(left)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(360)
        scroll.setMaximumWidth(430)

        # ---------------- centre / right
        self.mp_model = MplWidget(figsize=(4.5, 5))
        from .draw1d import LayerEditor
        self.editor = LayerEditor(self)
        self.interp = QTextBrowser()
        self.interp.setOpenExternalLinks(False)
        centre = QSplitter(Qt.Orientation.Vertical)
        centre.addWidget(self.mp_model)
        centre.addWidget(self.interp)
        centre.setSizes([520, 230])
        self.mp_resp = MplWidget(figsize=(6, 5))

        top = QSplitter(Qt.Orientation.Horizontal)
        top.addWidget(scroll)
        top.addWidget(centre)
        top.addWidget(self.mp_resp)
        top.setSizes([380, 520, 700])

        # ---------------- bottom: data table + exports
        bottom = QWidget()
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        er = QHBoxLayout()
        er.addWidget(label(tr("Synthetic data"), "section", False))
        er.addStretch(1)
        self.ex_btns = {}
        for k in ("CSV", "Excel", "JSON", "EDI", tr("Figures (PNG+SVG)"), tr("Report (PDF)")):
            b = QPushButton(tr(k))
            self.ex_btns[k] = b
            er.addWidget(b)
        bl.addLayout(er)
        self.data = QTableWidget()
        self.data.setAlternatingRowColors(True)
        self.data.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data.verticalHeader().setVisible(False)
        bl.addWidget(self.data)

        main = QSplitter(Qt.Orientation.Vertical)
        main.addWidget(top)
        main.addWidget(bottom)
        main.setSizes([760, 220])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(main)

        # ---------------- signals
        b_load.clicked.connect(self.load_preset)
        self.b_add.clicked.connect(self.add_layer)
        self.b_rem.clicked.connect(self.remove_layer)
        self.b_reset.clicked.connect(self.load_preset)
        self.b_save.clicked.connect(self.save_model)
        self.b_open.clicked.connect(self.open_model)
        self.table.itemChanged.connect(self._table_edited)
        self.table.itemSelectionChanged.connect(self._sel_changed)
        self.s_rho.valueChanged.connect(self._slider_rho)
        self.s_h.valueChanged.connect(self._slider_h)
        self.fc.changed.connect(self.schedule)
        for w in (self.c_z, self.c_bos):
            w.toggled.connect(self.schedule)
        self.noise.currentTextChanged.connect(self.schedule)
        self.seed.valueChanged.connect(self.schedule)
        self.b_pin.clicked.connect(self.pin_reference)
        self.b_unpin.clicked.connect(self.clear_reference)
        self.ex_btns["CSV"].clicked.connect(self.export_csv)
        self.ex_btns["Excel"].clicked.connect(self.export_excel)
        self.ex_btns["JSON"].clicked.connect(self.export_json)
        self.ex_btns["EDI"].clicked.connect(self.export_edi)
        self.ex_btns[tr("Figures (PNG+SVG)")].clicked.connect(
            lambda: export_figures(self, [("model_1d", self.draw_model), ("response_1d", self.draw_response)]))
        self.ex_btns[tr("Report (PDF)")].clicked.connect(self.export_report)

        self.fill_table()
        self.table.selectRow(0)
        self.recompute()

    # ================================================================ model editing
    def fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(self.model.n)
        tops = self.model.depths()
        for i in range(self.model.n):
            items = [QTableWidgetItem(self.model.layer_name(i)), QTableWidgetItem(f"{self.model.rho[i]:g}"),
                     QTableWidgetItem(f"{self.model.thick[i]:g}" if i < self.model.n - 1 else "∞"),
                     QTableWidgetItem(f"{tops[i]:g}")]
            if i == self.model.n - 1:
                items[2].setFlags(items[2].flags() & ~Qt.ItemFlag.ItemIsEditable)
            items[3].setFlags(items[3].flags() & ~Qt.ItemFlag.ItemIsEditable)
            for c, it in enumerate(items):
                self.table.setItem(i, c, it)
        self.table.blockSignals(False)

    def _row(self):
        r = self.table.currentRow()
        return max(0, min(r, self.model.n - 1))

    def _sel_changed(self):
        i = self._row()
        self.sel_lbl.setText(tr("Selected layer: {i} — {n}", i=i + 1, n=self.model.layer_name(i)))
        self.s_rho.set_value(self.model.rho[i])
        is_hs = i == self.model.n - 1
        self.s_h.setEnabled(not is_hs)
        if not is_hs:
            self.s_h.set_value(self.model.thick[i])

    def _table_edited(self, item):
        i, c = item.row(), item.column()
        try:
            if c == 0:
                while len(self.model.names) < self.model.n:
                    self.model.names.append("")
                self.model.names[i] = item.text()
            elif c == 1:
                v = float(item.text())
                if v <= 0:
                    raise ValueError(tr("Resistivity must be > 0 Ω·m"))
                self.model.rho[i] = v
            elif c == 2:
                v = float(item.text())
                if v <= 0:
                    raise ValueError(tr("Thickness must be > 0 m"))
                self.model.thick[i] = v
            self.msg.setText("")
        except ValueError as e:
            self.msg.setText(tr("Invalid entry in row {i}: {e}", i=i + 1, e=e))
        self.fill_table()
        self._sel_changed()
        self.schedule()

    def _slider_rho(self, v):
        self.model.rho[self._row()] = v
        self.fill_table()
        self.schedule()

    def _slider_h(self, v):
        i = self._row()
        if i < self.model.n - 1:
            self.model.thick[i] = v
            self.fill_table()
            self.schedule()

    def set_model(self, m: LayeredModel):
        self.model = m.copy()
        self.fill_table()
        self.table.selectRow(0)
        self._sel_changed()
        self.schedule()

    def load_preset(self):
        self.set_model(PRESETS_1D[self.preset.currentText()])

    def add_layer(self):
        i = self._row()
        if self.model.n == 1:
            self.model.rho.insert(0, self.model.rho[0])
            self.model.thick.append(100.0)
            if self.model.names:
                self.model.names.insert(0, "")
        else:
            ref = min(i, self.model.n - 2)
            self.model.rho.insert(ref + 1, self.model.rho[ref])
            self.model.thick.insert(ref + 1, self.model.thick[ref])
            if self.model.names:
                self.model.names.insert(ref + 1, "")
        self.fill_table()
        self.table.selectRow(min(i + 1, self.model.n - 1))
        self.schedule()

    def remove_layer(self):
        if self.model.n <= 1:
            self.msg.setText(tr("A model needs at least the half-space."))
            return
        self.model.remove_layer(self._row())
        self.fill_table()
        self.table.selectRow(0)
        self.schedule()

    def save_model(self):
        p = ask_save(self, tr("Save 1D model"), "JSON (*.json)", "model_1d.json")
        if p:
            guarded(self, write_json, p, {"type": "EM-Forward Lab 1D model", "credit": CREDIT,
                                          "model": self.model.to_dict()})

    def open_model(self):
        from PySide6.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(self, tr("Load 1D model"), "", "JSON (*.json)")
        if p:
            def _load():
                d = read_json(p)
                m = LayeredModel.from_dict(d.get("model", d))
                errs = m.validate()
                if errs:
                    raise ValueError("; ".join(errs))
                self.set_model(m)
            guarded(self, _load)

    # ================================================================ computation
    def schedule(self, *a):
        self._timer.start()

    def compute_dataset(self):
        f = self.fc.freqs()
        errs = self.model.validate() + validate_freqs(f)
        if errs:
            raise ValueError("; ".join(errs))
        r = forward_1d(self.model.rho, self.model.thick, f)
        lvl = NOISE_LEVELS[self.noise.currentText()]
        r["noise"] = lvl
        r["seed"] = self.seed.value()
        r["Zobs"] = add_impedance_noise(r["Z"], lvl, self.seed.value()) if lvl > 0 else None
        r["ff_ratio"], r["ff_ok"] = far_field_check(f, r["rho_a"], self.fc.distance_m())
        r["method"] = self.fc.method_name()
        r["bostick"] = bostick(r["rho_a"], r["phase"], f)
        r["model"] = self.model.copy()
        return r

    def recompute(self):
        try:
            self.res = self.compute_dataset()
            self.msg.setText("")
        except ValueError as e:
            self.msg.setText(f"⚠ {e}")
            return
        self.mp_model.clear()
        self.draw_model(self.mp_model.fig, GUI)
        self.mp_model.draw()
        self.mp_resp.clear()
        self.draw_response(self.mp_resp.fig, GUI)
        self.mp_resp.draw()
        self.update_table()
        self.update_interpretation()
        self.ex_btns["EDI"].setEnabled(METHODS[self.res["method"]]["edi"])
        self.ex_btns["EDI"].setToolTip("" if METHODS[self.res["method"]]["edi"] else
                                       "VLF-R data are exported as documented CSV/JSON, not EDI.")
        self.computed.emit()

    # ================================================================ drawing
    def draw_model(self, fig, theme):
        r = self.res
        ax = fig.add_subplot(111)
        plot_layered(fig, ax, r["model"], theme, bostick=r["bostick"] if self.c_bos.isChecked() else None,
                     max_depth=getattr(self.editor, "zmax", None) if self.editor.drag else None)
        style_fig(fig, theme)
        if fig is self.mp_model.fig:
            self.editor.attach(ax)

    def draw_response(self, fig, theme):
        r = self.res
        n = 3 if self.c_z.isChecked() else 2
        gs = fig.add_gridspec(n, 1, height_ratios=[3, 2, 2][:n])
        ax_r = fig.add_subplot(gs[0])
        ax_p = fig.add_subplot(gs[1], sharex=ax_r)
        setup_rho_phase(ax_r, ax_p, theme)
        f = r["freq"]
        if self.reference is not None:
            ref = self.reference
            plot_curve(ax_r, ax_p, ref["freq"], ref["rho_a"], ref["phase"], "Reference: " + ref["label"],
                       theme["ref"], ls="--", lw=1.5)
        noisy = None
        if r["Zobs"] is not None:
            noisy = (apparent_resistivity(r["Zobs"], f), phase_deg(r["Zobs"]))
        mk = "o" if f.size < 12 else None
        plot_curve(ax_r, ax_p, f, r["rho_a"], r["phase"], f"{r['method']} — {r['model'].title}",
                   theme["accent"], marker=mk, noisy=noisy)
        shade_invalid([ax_r, ax_p], f, r["ff_ok"], theme)
        finish_rho_phase(ax_r, ax_p, theme, f)
        ax_r.set_title(tr("{m} synthetic response (plane wave, exp(+iωt))", m=r['method']), fontsize=10)
        if n == 3:
            ax_p.tick_params(labelbottom=False)
            ax_p.set_xlabel("")
            ax_z = fig.add_subplot(gs[2], sharex=ax_r)
            plot_impedance(ax_z, f, r["Z"], theme)
            ax_z.set_xlim(ax_r.get_xlim())
        style_fig(fig, theme)

    def update_table(self):
        r = self.res
        f = r["freq"]
        dB, _ = r["bostick"]
        cols = {"f (Hz)": f, "T (s)": 1 / f, "ρa (Ω·m)": r["rho_a"], "φ (°)": r["phase"], "Re Z (Ω)": r["Z"].real,
                "Im Z (Ω)": r["Z"].imag, "δ(ρa) (m)": skin_depth(r["rho_a"], f), "Bostick D (m)": dB}
        if r["Zobs"] is not None:
            cols["ρa obs"] = apparent_resistivity(r["Zobs"], f)
            cols["φ obs"] = phase_deg(r["Zobs"])
        if r["method"] == "VLF-R":
            cols["r/δ"] = r["ff_ratio"]
            cols["Far-field OK"] = np.where(r["ff_ok"], 1, 0)
        self.data.setColumnCount(len(cols))
        self.data.setRowCount(f.size)
        self.data.setHorizontalHeaderLabels(list(cols.keys()))
        for c, v in enumerate(cols.values()):
            for i, x in enumerate(v):
                txt = ("yes" if x else "NO") if list(cols.keys())[c] == "Far-field OK" else f"{x:.5g}"
                self.data.setItem(i, c, QTableWidgetItem(txt))
        self.data.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def update_interpretation(self):
        r = self.res
        from education.interpretation import to_id
        from i18n import get_lang
        conv = to_id if get_lang() == "id" else (lambda t: t)
        lines = [conv(t) for t in interpret_1d(r["model"], r["freq"], r["rho_a"], r["phase"])]
        html = "<h3 style='color:#1565c0;margin:2px'>" + tr("Interpretation (computed from the response)") + "</h3><ul>"
        html += "".join(f"<li>{t}</li>" for t in lines) + "</ul>"
        if self.reference is not None and np.array_equal(self.reference["freq"], r["freq"]):
            html += "<p style='color:#e65100'>" + conv(interpret_change(r["freq"], self.reference["rho_a"],
                                                                     self.reference["phase"], r["rho_a"],
                                                                     r["phase"])) + "</p>"
        elif self.reference is not None:
            html += "<p style='color:#546e7a'>" + tr("Reference uses different frequencies — change statistics not shown.") + "</p>"
        if r["method"] == "VLF-R":
            bad = np.sum(~r["ff_ok"])
            html += (f"<p>Far-field check: r/δ ranges {r['ff_ratio'].min():.3g}–{r['ff_ratio'].max():.3g}; "
                     f"{bad} frequency(ies) violate r/δ &gt; 5.</p>")
        if r["Zobs"] is not None:
            html += (f"<p style='color:#546e7a'>Noisy observations: {r['noise'] * 100:g} % complex impedance noise "
                     f"(seed {r['seed']}); expected ρa scatter ≈ {np.sqrt(2) * r['noise'] * 100:.1f} %, phase scatter ≈ "
                     f"{np.degrees(r['noise'] / np.sqrt(2)):.2f}°.</p>")
        self.interp.setHtml(html)

    # ================================================================ reference
    def pin_reference(self):
        if self.res is None:
            return
        self.reference = {"freq": self.res["freq"].copy(), "rho_a": self.res["rho_a"].copy(),
                          "phase": self.res["phase"].copy(),
                          "label": " / ".join(f"{v:g}" for v in self.model.rho) + " Ω·m"}
        self.recompute()

    def clear_reference(self):
        self.reference = None
        self.recompute()

    # ================================================================ export
    def _meta(self):
        r = self.res
        return metadata(method=r["method"], method_assumption=METHODS[r["method"]]["assumption"],
                        model=r["model"].to_dict(), frequency_config=self.fc.state(),
                        noise_level=r["noise"], noise_seed=r["seed"], noise_model=NOISE_MODEL_TEXT,
                        solver="1D impedance recursion (analytic)",
                        transmitter_distance_m=self.fc.distance_m())

    def _frame(self):
        r = self.res
        extra = {}
        if r["Zobs"] is not None:
            extra = {"Apparent_Resistivity_Obs_OhmM": apparent_resistivity(r["Zobs"], r["freq"]),
                     "Phase_Obs_Deg": phase_deg(r["Zobs"]), "Impedance_Obs_Real": r["Zobs"].real,
                     "Impedance_Obs_Imag": r["Zobs"].imag}
        if r["method"] == "VLF-R":
            extra["Transmitter_Distance_m"] = self.fc.distance_m()
            extra["FarField_r_over_delta"] = r["ff_ratio"]
            extra["FarField_OK"] = r["ff_ok"]
        return frame_1d(r["freq"], r["Z"], extra)

    def export_csv(self):
        p = ask_save(self, "Export CSV", "CSV (*.csv)", f"synthetic_1d_{self.res['method']}.csv")
        if p:
            guarded(self, write_csv, p, self._frame(), self._meta(), done_msg=f"Saved {p}")

    def export_excel(self):
        p = ask_save(self, "Export Excel", "Excel (*.xlsx)", f"synthetic_1d_{self.res['method']}.xlsx")
        if p:
            guarded(self, write_excel, p, self._frame(), self.res["model"].to_dict(), self._meta(),
                    done_msg=f"Saved {p}")

    def export_json(self):
        p = ask_save(self, "Export JSON", "JSON (*.json)", f"synthetic_1d_{self.res['method']}.json")
        if p:
            payload = {"metadata": self._meta(), "data": self._frame().to_dict(orient="list")}
            guarded(self, write_json, p, payload, done_msg=f"Saved {p}")

    def export_edi(self):
        r = self.res
        if not METHODS[r["method"]]["edi"]:
            return
        p = ask_save(self, "Export EDI", "EDI (*.edi)", f"synthetic_1d_{r['method']}.edi")
        if p:
            Z = r["Zobs"] if r["Zobs"] is not None else r["Z"]
            info = [f"Method: {r['method']} (1D layered earth)",
                    "Model rho (Ohm.m): " + ", ".join(f"{v:g}" for v in r["model"].rho),
                    "Model thickness (m): " + ", ".join(f"{v:g}" for v in r["model"].thick),
                    f"Noise level: {r['noise'] * 100:g} % (seed {r['seed']})" if r["Zobs"] is not None
                    else "Noise-free synthetic data"]
            guarded(self, write_edi, p, r["freq"], Z, -Z, "SYN1D", info, r["noise"], 0.0, done_msg=f"Saved {p}")

    def export_report(self):
        p = ask_save(self, "Export report", "PDF (*.pdf)", f"report_1d_{self.res['method']}.pdf")
        if not p:
            return
        r = self.res
        m = r["model"]
        tops = m.depths()
        lines = [f"Method: {r['method']}  —  {METHODS[r['method']]['name']}", "",
                 "Source assumption: " + METHODS[r["method"]]["assumption"], "",
                 "Model: " + m.title, f"{'Layer':<28}{'rho (Ohm.m)':>14}{'h (m)':>12}{'top (m)':>12}"]
        for i in range(m.n):
            lines.append(f"{m.layer_name(i)[:27]:<28}{m.rho[i]:>14g}"
                         f"{(f'{m.thick[i]:g}' if i < m.n - 1 else 'inf'):>12}{tops[i]:>12g}")
        lines += ["", f"Frequencies: {r['freq'].size} values, {r['freq'].min():.4g} – {r['freq'].max():.4g} Hz",
                  f"Noise: {r['noise'] * 100:g} %  ({NOISE_MODEL_TEXT})", "",
                  "Conventions: exp(+i w t), Z = Ex/Hy, rho_a = |Z|^2/(w mu0), phase = arg Z", "",
                  "Interpretation (computed):"]
        for t in interpret_1d(m, r["freq"], r["rho_a"], r["phase"]):
            lines += ["- " + t]
        guarded(self, write_report, p, "1D forward model report", lines,
                [lambda fig: self.draw_model(fig, LIGHT), lambda fig: self.draw_response(fig, LIGHT)],
                self._meta(), done_msg=f"Saved {p}")

    # ================================================================ session
    def state(self):
        return {"model": self.model.to_dict(), "freq": self.fc.state(), "noise": self.noise.currentText(),
                "seed": self.seed.value(), "show_z": self.c_z.isChecked(), "bostick": self.c_bos.isChecked(),
                "reference": None if self.reference is None else
                {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.reference.items()}}

    def set_state(self, s):
        self.fc.set_state(s["freq"])
        self.noise.setCurrentText(s.get("noise", "Noise-free"))
        self.seed.setValue(s.get("seed", 12345))
        self.c_z.setChecked(s.get("show_z", False))
        self.c_bos.setChecked(s.get("bostick", True))
        ref = s.get("reference")
        self.reference = None if ref is None else {k: (np.array(v) if isinstance(v, list) else v)
                                                   for k, v in ref.items()}
        self.set_model(LayeredModel.from_dict(s["model"]))

    def load_experiment(self, exp):
        self.fc.method.setCurrentText(exp["method"])
        self.reference = None
        self.set_model(LayeredModel(list(exp["rho"]), list(exp["thick"]), list(exp["names"]), exp["title"]))
