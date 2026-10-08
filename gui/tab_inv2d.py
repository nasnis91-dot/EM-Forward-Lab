"""2D Occam inversion tab."""
import re

import numpy as np
import pandas as pd
from matplotlib.colors import LogNorm
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QTextBrowser,
                               QVBoxLayout, QWidget)

from core.inv_2d import Data2D, occam2d
from export.export_edi import read_edi
from i18n import tr
from visualization.pseudosection import plot_pseudosection
from visualization.resistivity_model import plot_section
from visualization.theme import GUI, RHO_CMAP, style_ax, style_colorbar, style_fig

from .export_helpers import ask_save, guarded
from .mpl import MplWidget
from .tab_2d import SimWorker
from .widgets import label, sci_spin


class TabInv2D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pkg = None
        self.res = None
        left = QWidget()
        ll = QVBoxLayout(left)
        g = QGroupBox(tr("Data"))
        gl = QFormLayout(g)
        b_edi = QPushButton(tr("Load EDI files…"))
        gl.addRow(b_edi)
        gl.addRow(label(tr("Choose EDI files of one profile (station position is read from the file).")))
        self.info = label(tr("No data loaded."))
        gl.addRow(self.info)
        self.c_te, self.c_tm = QCheckBox("TE"), QCheckBox("TM")
        self.c_te.setChecked(True)
        self.c_tm.setChecked(True)
        h = QHBoxLayout()
        h.addWidget(self.c_te)
        h.addWidget(self.c_tm)
        gl.addRow(tr("Mode"), h)
        self.use = QComboBox()
        for k, t in (("both", "ρa and φ"), ("rho", "ρa only"), ("phase", "φ only")):
            self.use.addItem(tr(t), k)
        self.floor = sci_spin(0.5, 50, 5, 1, " %")
        gl.addRow(tr("Invert"), self.use)
        gl.addRow(tr("Error floor"), self.floor)
        ll.addWidget(g)
        g2 = QGroupBox(tr("Inversion") + " — Occam 2D")
        f2 = QFormLayout(g2)
        self.nz = QSpinBox()
        self.nz.setRange(4, 30)
        self.nz.setValue(12)
        self.alpha = sci_spin(0.1, 10, 1.0, 2)
        self.refine = sci_spin(0.4, 2, 0.8, 2, "×")
        self.target = sci_spin(0.1, 10, 1.0, 2)
        self.maxit = QSpinBox()
        self.maxit.setRange(1, 30)
        self.maxit.setValue(8)
        for lab, w in ((tr("Grid layers"), self.nz), (tr("Horizontal smoothing (α)"), self.alpha),
                       (tr("Mesh refinement"), self.refine), (tr("Target RMS"), self.target),
                       (tr("Max iterations"), self.maxit)):
            f2.addRow(lab, w)
        self.b_run = QPushButton(tr("▶  Run inversion"))
        self.b_run.setObjectName("primary")
        self.b_cancel = QPushButton(tr("Cancel"))
        h2 = QHBoxLayout()
        h2.addWidget(self.b_run, 2)
        h2.addWidget(self.b_cancel, 1)
        f2.addRow(h2)
        self.prog = QProgressBar()
        f2.addRow(self.prog)
        self.status = label("")
        f2.addRow(self.status)
        self.iter = QComboBox()
        f2.addRow(tr("Iteration to show"), self.iter)
        ll.addWidget(g2)
        self.b_exp = QPushButton(tr("Export model (CSV)…"))
        ll.addWidget(self.b_exp)
        self.msg = label("", "warn")
        ll.addWidget(self.msg)
        ll.addStretch(1)
        sc = QScrollArea()
        sc.setWidget(left)
        sc.setWidgetResizable(True)
        sc.setMaximumWidth(400)
        self.mp_m = MplWidget(figsize=(7, 6))
        self.mp_d = MplWidget(figsize=(7, 6))
        self.txt = QTextBrowser()
        c = QSplitter(Qt.Orientation.Vertical)
        c.addWidget(self.mp_m)
        c.addWidget(self.txt)
        c.setSizes([650, 200])
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(sc)
        sp.addWidget(c)
        sp.addWidget(self.mp_d)
        sp.setSizes([380, 650, 650])
        QVBoxLayout(self).addWidget(sp)
        b_edi.clicked.connect(self.load_edis)
        self.b_run.clicked.connect(self.run)
        self.b_cancel.clicked.connect(lambda: getattr(self, "w", None) and self.w.cancel())
        self.iter.currentIndexChanged.connect(self.draw)
        self.b_exp.clicked.connect(self.export)

    def set_data(self, pkg):
        self.pkg = pkg
        self.res = None
        f = np.asarray(pkg["freq"])
        txt = tr("Loaded: {s}", s=pkg.get("source", "")) + "<br>" + \
            tr("{n} frequencies, {a} – {b} Hz", n=f.size, a=f"{f.min():.3g}", b=f"{f.max():.3g}") + \
            f"<br>{tr('Stations')}: {len(pkg['stations'])}"
        if pkg.get("model") is not None:
            txt += "<br><b>" + tr("True model known (synthetic)") + "</b>"
        self.info.setText(txt)
        self.iter.clear()
        self.draw()

    def load_edis(self):
        ps, _ = QFileDialog.getOpenFileNames(self, tr("Load EDI files…"), "", "EDI (*.edi *.EDI)")
        if not ps:
            return

        def _l():
            recs = []
            for p in ps:
                e = read_edi(p)
                y = None
                for line in e["info"]:
                    m = re.search(r"position y = ([-\d.eE+]+)", line)
                    if m:
                        y = float(m.group(1))
                recs.append((y, e))
            if any(y is None for y, _ in recs):
                self.msg.setText(tr("Station positions were not found in the EDI files; equal spacing of 100 m is assumed."))
                recs = [(100.0 * k, e) for k, (_, e) in enumerate(recs)]
            recs.sort(key=lambda t: t[0])
            f0 = recs[0][1]["freq"]
            common = f0
            for _, e in recs[1:]:
                common = np.array([x for x in common if np.any(np.isclose(e["freq"], x, rtol=1e-4))])
            if common.size < f0.size:
                self.msg.setText(tr("Files have different frequencies; only common frequencies are used."))
            Z = {"TE": [], "TM": []}
            E = {"TE": [], "TM": []}
            for _, e in recs:
                idx = [int(np.argmin(np.abs(e["freq"] - x))) for x in common]
                Z["TE"].append(e["Z"]["ZXY"][idx])
                Z["TM"].append(-e["Z"]["ZYX"][idx])
                er = e["err"] or {}
                E["TE"].append(er.get("ZXY", np.zeros(len(f0)))[idx] if er else np.zeros(len(idx)))
                E["TM"].append(er.get("ZYX", np.zeros(len(f0)))[idx] if er else np.zeros(len(idx)))
            self.set_data({"freq": common, "stations": np.array([y for y, _ in recs]),
                           "Z": {k: np.array(v).T for k, v in Z.items()},
                           "Zerr": {k: np.array(v).T for k, v in E.items()}, "model": None,
                           "source": f"{len(ps)} EDI files"})
        guarded(self, _l)

    def run(self):
        if self.pkg is None:
            self.msg.setText(tr("No data loaded."))
            return
        modes = [m for m, c in (("TE", self.c_te), ("TM", self.c_tm)) if c.isChecked()]
        p = self.pkg
        if len(p["stations"]) < 3 or len(p["freq"]) < 3:
            self.msg.setText(tr("2D inversion needs at least 3 stations and 3 frequencies."))
            return
        try:
            d = Data2D(p["freq"], p["stations"], {m: p["Z"][m] for m in modes if m in p["Z"]},
                       {m: p["Zerr"][m] for m in modes if m in p["Zerr"]}, floor=self.floor.value() / 100,
                       modes=modes, use=self.use.currentData())
        except ValueError as e:
            self.msg.setText(str(e))
            return
        self.msg.setText("")
        nz, al, rf, tg, mi = self.nz.value(), self.alpha.value(), self.refine.value(), self.target.value(), self.maxit.value()

        def job(progress, cancelled):
            r = occam2d(d, nz, rf, tg, mi, al, progress=progress, cancelled=cancelled,
                        on_iter=lambda h, *a: progress(0, 1, f"RMS = {h['rms']:.3f} (iteration {h['iter']})"))
            r["data"] = d
            return r
        self.b_run.setEnabled(False)
        self.w = SimWorker(job, self)
        self.w.progress.connect(lambda k, n, s: (self.prog.setMaximum(n), self.prog.setValue(k), self.status.setText(s)))
        self.w.done.connect(self._done)
        self.w.failed.connect(lambda s: self.msg.setText(s))
        self.w.finished.connect(lambda: self.b_run.setEnabled(True))
        self.w.start()

    def _done(self, r):
        self.res = r
        self.iter.blockSignals(True)
        self.iter.clear()
        self.iter.addItems([f"{h['iter']}: RMS {h['rms']:.2f}" for h in r["history"]])
        self.iter.setCurrentIndex(len(r["history"]) - 1)
        self.iter.blockSignals(False)
        h = r["history"][-1]
        self.status.setText(tr("Inversion finished: RMS = {r:.3f} after {n} iterations ({t:.1f} s).",
                               r=h["rms"], n=h["iter"], t=h["time_s"]))
        self.draw()

    def draw(self, *a):
        r = self.res
        self.mp_m.clear()
        fig = self.mp_m.fig
        true = self.pkg.get("model") if self.pkg else None
        if r is None:
            if true is not None:
                ax = fig.add_subplot(111)
                plot_section(fig, ax, true, GUI)
                style_fig(fig, GUI)
            self.mp_m.draw()
            self.mp_d.clear()
            self.mp_d.draw()
            return
        k = max(self.iter.currentIndex(), 0)
        lr = r["models"][k]
        n = 2 if true is not None else 1
        vals = 10 ** lr
        lo, hi = vals.min(), vals.max()
        if true is not None:
            tv = true.all_rho()
            lo, hi = min(lo, tv.min()), max(hi, tv.max())
        norm = LogNorm(lo, hi * 1.0001)
        ax = fig.add_subplot(n, 1, 1)
        style_ax(ax, GUI)
        ax._no_grid = True
        zmax = r["ze"][-1]
        ze = r["ze"].copy()
        pm = ax.pcolormesh(r["ye"], ze, vals, cmap=RHO_CMAP, norm=norm, shading="flat")
        ax.plot(r["data"].stations, np.zeros(len(r["data"].stations)), "v", color="k", ms=5, clip_on=False)
        ax.set_ylim(min(zmax, 3 * (true.depth if true is not None else zmax)), 0)
        ax.set_xlim(r["ye"][0], r["ye"][-1])
        ax.set_title(tr("Inverted 2D model") + f" — {tr('Iteration')} {r['history'][k]['iter']}, RMS {r['history'][k]['rms']:.2f}", fontsize=10)
        ax.set_ylabel(tr("Depth (m)"))
        cb = fig.colorbar(pm, ax=ax, pad=0.02, fraction=0.05)
        style_colorbar(cb, GUI, "ρ (Ω·m)")
        if true is not None:
            ax2 = fig.add_subplot(2, 1, 2, sharex=ax, sharey=ax)
            plot_section(fig, ax2, true, GUI, norm=norm)
            ax2.set_title(tr("True 2D model"), fontsize=10)
            ax2.set_xlim(r["ye"][0], r["ye"][-1])
        ax.set_xlabel(tr("Distance along profile y (m)"))
        style_fig(fig, GUI)
        self.mp_m.draw()
        # data fit pseudosections (first mode)
        self.mp_d.clear()
        fig = self.mp_d.fig
        d = r["data"]
        m0 = d.modes[0]
        gs = fig.add_gridspec(2, 2)
        obs = 10 ** d.logrho[m0]
        pred = 10 ** r["pred_lr"][m0]
        nrm = LogNorm(min(obs.min(), pred.min()), max(obs.max(), pred.max()) * 1.0001)
        plot_pseudosection(fig, fig.add_subplot(gs[0, 0]), d.stations, d.freq, obs, GUI, "rho", f"{m0} ρa {tr('observed')}", norm=nrm)
        plot_pseudosection(fig, fig.add_subplot(gs[0, 1]), d.stations, d.freq, pred, GUI, "rho", f"{m0} ρa {tr('predicted')}", norm=nrm)
        ax_h = fig.add_subplot(gs[1, :])
        style_ax(ax_h, GUI)
        ax_h.semilogy([h["iter"] for h in r["history"]], [h["rms"] for h in r["history"]], "-o", color=GUI["accent"])
        ax_h.axhline(r["target"], color=GUI["warn"], ls="--")
        ax_h.set_xlabel(tr("Iteration"))
        ax_h.set_ylabel("RMS")
        style_fig(fig, GUI)
        self.mp_d.draw()
        self.txt.setHtml(f"<p>Occam 2D: {lr.shape[1]} × {lr.shape[0]} blocks, α = {r['alpha']:g}, "
                         f"start ρ = {r['rho_start']:.3g} Ω·m. RMS: " +
                         " → ".join(f"{h['rms']:.2f}" for h in r["history"]) + "</p>")

    def export(self):
        if not self.res:
            return
        p = ask_save(self, tr("Export model (CSV)…"), "CSV (*.csv)", "inverted_model_2d.csv")
        if p:
            r = self.res
            rows = []
            for j in range(len(r["ze"]) - 1):
                for i in range(len(r["ye"]) - 1):
                    rows.append((r["ye"][i], r["ye"][i + 1], r["ze"][j], r["ze"][j + 1], 10 ** r["logrho"][j, i]))
            df = pd.DataFrame(rows, columns=["Y0_m", "Y1_m", "Z0_m", "Z1_m", "Resistivity_OhmM"])
            guarded(self, lambda: df.to_csv(p, index=False), done_msg=tr("Saved {p}", p=p))
