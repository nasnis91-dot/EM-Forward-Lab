"""Noise & Data tab: add noise to the forward result and export EDI/CSV."""
import os

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QPushButton,
                               QRadioButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from appinfo import metadata
from core.mt_1d import apparent_resistivity, phase_deg
from core.noise import apply_noise, rho_phase_errors
from export.export_csv import frame_1d, write_csv
from export.export_edi import write_edi
from i18n import tr
from visualization.response_plots import setup_rho_phase
from visualization.theme import GUI, legend, style_fig

from .export_helpers import ask_dir, ask_save, guarded
from .mpl import MplWidget
from .widgets import label, sci_spin

METHODS = [("gauss_z", "Gaussian on Z (relative)"), ("gauss_rho_phase", "Gaussian on ρa and φ"),
           ("uniform_z", "Uniform on Z (relative)"), ("gauss_outliers", "Gaussian + outliers")]


class TabNoise(QWidget):
    send1d = Signal(object)
    send2d = Signal(object)

    def __init__(self, tab1d, tab2d, parent=None):
        super().__init__(parent)
        self.t1, self.t2 = tab1d, tab2d
        self.res = None
        left = QWidget()
        ll = QVBoxLayout(left)
        g = QGroupBox(tr("Data source"))
        gl = QFormLayout(g)
        self.r1, self.r2 = QRadioButton(tr("1D forward result")), QRadioButton(tr("2D forward result"))
        self.r1.setChecked(True)
        gl.addRow(self.r1)
        gl.addRow(self.r2)
        self.st = QComboBox()
        self.mode = QComboBox()
        self.mode.addItems(["TE", "TM"])
        gl.addRow(tr("Station"), self.st)
        gl.addRow(tr("Mode"), self.mode)
        ll.addWidget(g)
        g2 = QGroupBox(tr("Noise model"))
        f2 = QFormLayout(g2)
        self.meth = QComboBox()
        for k, t in METHODS:
            self.meth.addItem(tr(t), k)
        self.lvl = sci_spin(0, 50, 5, 2, " %")
        self.sphi = sci_spin(0, 30, 1.43, 2, " °")
        self.ofrac = sci_spin(0, 50, 10, 1, " %")
        self.ofac = sci_spin(1, 50, 5, 1, "×")
        self.floor = sci_spin(0, 50, 0, 2, " %")
        self.seed = QSpinBox()
        self.seed.setRange(0, 999999)
        self.seed.setValue(12345)
        b_seed = QPushButton(tr("New seed"))
        for lab, w in ((tr("Method"), self.meth), (tr("Noise level"), self.lvl), (tr("Phase noise (σφ)"), self.sphi),
                       (tr("Outlier fraction"), self.ofrac), (tr("Outlier factor"), self.ofac),
                       (tr("Error floor"), self.floor), (tr("Random seed"), self.seed)):
            f2.addRow(lab, w)
        f2.addRow(b_seed)
        f2.addRow(label("Gaussian on Z: Z_obs = Z(1 + p·n), n ~ N(0,1) complex.  "
                        "Reported error σ = max(p|Z|/√2, floor·|Z|) → ρa ±√2·p, φ ±p/√2 rad."))
        ll.addWidget(g2)
        self.b_edi = QPushButton(tr("Export EDI…"))
        self.b_edi_all = QPushButton(tr("Export all stations (EDI)…"))
        self.b_csv = QPushButton(tr("Export CSV…"))
        self.b_inv1 = QPushButton(tr("→ Invert this data (1D)"))
        self.b_inv2 = QPushButton(tr("→ Invert this data (2D)"))
        self.b_inv1.setObjectName("primary")
        for b in (self.b_edi, self.b_edi_all, self.b_csv, self.b_inv1, self.b_inv2):
            ll.addWidget(b)
        self.msg = label("", "warn")
        ll.addWidget(self.msg)
        ll.addStretch(1)
        sc = QScrollArea()
        sc.setWidget(left)
        sc.setWidgetResizable(True)
        sc.setMaximumWidth(400)
        self.mp = MplWidget(figsize=(7, 6))
        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)
        right = QSplitter(Qt.Orientation.Vertical)
        right.addWidget(self.mp)
        right.addWidget(self.table)
        right.setSizes([600, 250])
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(sc)
        sp.addWidget(right)
        sp.setSizes([380, 1100])
        QVBoxLayout(self).addWidget(sp)
        for w in (self.r1, self.r2):
            w.toggled.connect(self.refresh)
        for w in (self.st, self.mode, self.meth):
            w.currentIndexChanged.connect(self.refresh)
        for w in (self.lvl, self.sphi, self.ofrac, self.ofac, self.floor, self.seed):
            w.valueChanged.connect(self.refresh)
        b_seed.clicked.connect(lambda: self.seed.setValue(int(np.random.default_rng().integers(0, 999999))))
        self.b_edi.clicked.connect(self.export_edi)
        self.b_edi_all.clicked.connect(self.export_edi_all)
        self.b_csv.clicked.connect(self.export_csv)
        self.b_inv1.clicked.connect(lambda: self.res and self.send1d.emit(self.package_1d()))
        self.b_inv2.clicked.connect(lambda: self.res and self.send2d.emit(self.package_2d()))
        tab1d.computed.connect(self.refresh)
        tab2d.computed.connect(self._fill_stations)

    def _fill_stations(self):
        r = self.t2.result
        self.st.blockSignals(True)
        self.st.clear()
        if r is not None:
            self.st.addItems([f"{i + 1}: y = {y:g} m" for i, y in enumerate(r["stations"])])
            self.st.setCurrentIndex(len(r["stations"]) // 2)
        self.st.blockSignals(False)
        self.refresh()

    def _params(self):
        return dict(method=self.meth.currentData(), level=self.lvl.value() / 100, seed=self.seed.value(),
                    phase_sd_deg=self.sphi.value(), outlier_frac=self.ofrac.value() / 100,
                    outlier_factor=self.ofac.value(), floor=self.floor.value() / 100)

    def refresh(self, *a):
        is2 = self.r2.isChecked()
        for w in (self.st, self.mode, self.b_edi_all, self.b_inv2):
            w.setEnabled(is2)
        self.sphi.setEnabled(self.meth.currentData() == "gauss_rho_phase")
        for w in (self.ofrac, self.ofac):
            w.setEnabled(self.meth.currentData() == "gauss_outliers")
        p = self._params()
        if not is2:
            r = self.t1.res
            if r is None:
                self.msg.setText(tr("No forward result yet — compute a model in the 1D or 2D Forward tab first."))
                return
            f = r["freq"]
            nz = apply_noise(r["Z"], f, **p)
            self.res = {"dim": 1, "freq": f, "Z": r["Z"], "Zobs": nz["Zobs"], "Zerr": nz["Zerr"],
                        "outlier": nz["outlier"], "method": r["method"], "model": r["model"], "noise": p,
                        "title": r["model"].title}
        else:
            r = self.t2.result
            if r is None:
                self.msg.setText(tr("Run the 2D simulation first (2D Forward tab)."))
                return
            f = r["freq"]
            Zo, Ze, Ou = {}, {}, {}
            for k, m in enumerate(r["Z"]):
                q = dict(p)
                q["seed"] = p["seed"] + 1000 * k
                nz = apply_noise(r["Z"][m], f, **q)
                Zo[m], Ze[m], Ou[m] = nz["Zobs"], nz["Zerr"], nz["outlier"]
            self.res = {"dim": 2, "freq": f, "Z": r["Z"], "Zobs": Zo, "Zerr": Ze, "outlier": Ou,
                        "stations": r["stations"], "method": r["method"], "model": r["model"], "noise": p,
                        "title": r["model"].title}
        self.msg.setText("")
        self.draw()

    def _sel(self):
        r = self.res
        if r["dim"] == 1:
            return r["Z"], r["Zobs"], r["Zerr"], r["outlier"]
        m = self.mode.currentText() if self.mode.currentText() in r["Z"] else list(r["Z"])[0]
        k = max(self.st.currentIndex(), 0)
        return r["Z"][m][:, k], r["Zobs"][m][:, k], r["Zerr"][m][:, k], r["outlier"][m][:, k]

    def draw(self):
        r = self.res
        f = r["freq"]
        Z, Zo, Ze, ou = self._sel()
        self.mp.clear()
        fig = self.mp.fig
        ax_r, ax_p = fig.add_subplot(211), fig.add_subplot(212)
        setup_rho_phase(ax_r, ax_p, GUI)
        er, ep = rho_phase_errors(Zo, Ze)
        ra, pa = apparent_resistivity(Zo, f), phase_deg(Zo)
        ax_r.plot(f, apparent_resistivity(Z, f), "-", color=GUI["accent"], label=tr("clean"))
        ax_p.plot(f, phase_deg(Z), "-", color=GUI["accent"])
        ax_r.errorbar(f, ra, yerr=er * ra, fmt="o", ms=4, color=GUI["accent2"], capsize=2, label=tr("noisy"))
        ax_p.errorbar(f, pa, yerr=ep, fmt="o", ms=4, color=GUI["accent2"], capsize=2)
        if ou.any():
            ax_r.plot(f[ou], ra[ou], "s", mfc="none", ms=9, color=GUI["warn"], label=tr("outlier"))
            ax_p.plot(f[ou], pa[ou], "s", mfc="none", ms=9, color=GUI["warn"])
        ax_r.set_xlim(f.max() * 1.3, f.min() / 1.3)
        ax_p.set_xlim(f.max() * 1.3, f.min() / 1.3)
        legend(ax_r, GUI)
        ax_r.set_title(tr("Clean vs noisy data") + f" — {r['method']}, {r['noise']['level'] * 100:g} %", fontsize=10)
        style_fig(fig, GUI)
        self.mp.draw()
        cols = ["f (Hz)", "ρa clean", "ρa noisy", "± %", "φ clean", "φ noisy", "± °", tr("outlier")]
        vals = [f, apparent_resistivity(Z, f), ra, er * 100, phase_deg(Z), pa, ep, ou]
        self.table.setColumnCount(len(cols))
        self.table.setRowCount(f.size)
        self.table.setHorizontalHeaderLabels(cols)
        for c, v in enumerate(vals):
            for i, x in enumerate(v):
                self.table.setItem(i, c, QTableWidgetItem(("✕" if x else "") if c == 7 else f"{x:.4g}"))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ------------------------------------------------------------- export / hand-over
    def _info(self):
        r, p = self.res, self.res["noise"]
        lines = [f"Method: {r['method']}", f"Noise: {p['method']} level {p['level'] * 100:g} %, seed {p['seed']}, "
                 f"error floor {p['floor'] * 100:g} %"]
        if r["dim"] == 1:
            lines += ["Model rho (Ohm.m): " + ", ".join(f"{v:g}" for v in r["model"].rho),
                      "Model thickness (m): " + ", ".join(f"{v:g}" for v in r["model"].thick)]
        else:
            lines.append(f"2D model: {r['title']}")
        return lines

    def export_edi(self):
        if not self.res:
            return
        if self.res["method"] == "VLF-R":
            pass
        p = ask_save(self, tr("Export EDI…"), "EDI (*.edi)", "noisy_data.edi")
        if not p:
            return
        r = self.res
        if r["dim"] == 1:
            guarded(self, write_edi, p, r["freq"], r["Zobs"], -r["Zobs"], "SYN1D", self._info(), 0.0, 0.0,
                    r["Zerr"], r["Zerr"], done_msg=tr("Saved {p}", p=p))
        else:
            k = max(self.st.currentIndex(), 0)
            self._write_station(p, k, done=True)

    def _write_station(self, path, k, done=False):
        r = self.res
        Zte = r["Zobs"].get("TE", r["Zobs"].get("TM"))[:, k]
        Ztm = r["Zobs"].get("TM", r["Zobs"].get("TE"))[:, k]
        Ete = r["Zerr"].get("TE", r["Zerr"].get("TM"))[:, k]
        Etm = r["Zerr"].get("TM", r["Zerr"].get("TE"))[:, k]
        info = self._info() + ["Zxy = TE, Zyx = -TM (strike = x)"]
        guarded(self, write_edi, path, r["freq"], Zte, -Ztm, f"ST{k + 1:03d}", info, 0.0,
                float(r["stations"][k]), Ete, Etm, done_msg=tr("Saved {p}", p=path) if done else None)

    def export_edi_all(self):
        if not self.res or self.res["dim"] != 2:
            return
        d = ask_dir(self, tr("Folder for EDI files (one per station)"))
        if d:
            for k in range(len(self.res["stations"])):
                self._write_station(os.path.join(d, f"ST{k + 1:03d}.edi"), k)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, tr("Export"), tr("Saved {n} EDI files in\n{d}",
                                                           n=len(self.res["stations"]), d=d))

    def export_csv(self):
        if not self.res:
            return
        p = ask_save(self, tr("Export CSV…"), "CSV (*.csv)", "noisy_data.csv")
        if p:
            Z, Zo, Ze, ou = self._sel()
            df = frame_1d(self.res["freq"], Zo, {"Impedance_Error": Ze, "Clean_Real": Z.real, "Clean_Imag": Z.imag,
                                                 "Outlier": ou})
            guarded(self, write_csv, p, df, metadata(noise=self.res["noise"], info=self._info()),
                    done_msg=tr("Saved {p}", p=p))

    def package_1d(self):
        r = self.res
        Z, Zo, Ze, ou = self._sel()
        true = {"rho": list(r["model"].rho), "thick": list(r["model"].thick)} if r["dim"] == 1 else None
        src = "Noise tab (1D)" if r["dim"] == 1 else f"Noise tab (2D station {self.st.currentText()}, {self.mode.currentText()})"
        return {"freq": r["freq"], "Z": Zo, "Zerr": Ze, "true": true, "source": src}

    def package_2d(self):
        r = self.res
        return {"freq": r["freq"], "stations": r["stations"], "Z": r["Zobs"], "Zerr": r["Zerr"],
                "model": r["model"], "source": "Noise tab (2D)"}
