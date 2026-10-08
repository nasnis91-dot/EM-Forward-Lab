"""1D inversion tab (Occam smooth / Marquardt layered)."""
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                               QProgressBar, QPushButton, QScrollArea, QSpinBox, QSplitter, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from core.inversion import InvData, marquardt, marquardt_auto, occam
from export.export_edi import read_edi
from i18n import tr
from visualization.response_plots import setup_rho_phase
from visualization.theme import GUI, legend, style_ax, style_fig

from .export_helpers import ask_save, guarded
from .mpl import MplWidget
from .tab_2d import SimWorker
from .widgets import label, sci_spin


def step(rho, thick, zmax):
    tops = np.concatenate([[0.0], np.cumsum(thick)])
    z = np.repeat(np.concatenate([tops, [zmax]]), 2)[1:-1]
    return np.repeat(rho, 2), z


class TabInv1D(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw = None          # dict freq, Z (component dict or array), Zerr, true, source
        self.res = None
        left = QWidget()
        ll = QVBoxLayout(left)
        g = QGroupBox(tr("Data"))
        gl = QFormLayout(g)
        h = QHBoxLayout()
        b_edi, b_csv = QPushButton(tr("Load EDI…")), QPushButton(tr("Load CSV…"))
        h.addWidget(b_edi)
        h.addWidget(b_csv)
        gl.addRow(h)
        self.info = label(tr("No data loaded."))
        gl.addRow(self.info)
        self.comp = QComboBox()
        self.comp.addItems(["Zxy (TE)", "Zyx (TM)", "Determinant"])
        self.use = QComboBox()
        for k, t in (("both", "ρa and φ"), ("rho", "ρa only"), ("phase", "φ only")):
            self.use.addItem(tr(t), k)
        self.floor = sci_spin(0, 50, 2, 2, " %")
        gl.addRow(tr("Component"), self.comp)
        gl.addRow(tr("Invert"), self.use)
        gl.addRow(tr("Error floor"), self.floor)
        ll.addWidget(g)
        g2 = QGroupBox(tr("Inversion"))
        f2 = QFormLayout(g2)
        self.alg = QComboBox()
        self.alg.addItem(tr("Occam (smooth)"), "occam")
        self.alg.addItem(tr("Marquardt (layered)"), "marq")
        f2.addRow(tr("Algorithm"), self.alg)
        self.stack = QStackedWidget()
        w1 = QWidget()
        fo = QFormLayout(w1)
        self.o_n = QSpinBox()
        self.o_n.setRange(5, 100)
        self.o_n.setValue(40)
        self.o_zmin = sci_spin(0, 1e5, 0, 1, " m")
        self.o_zmax = sci_spin(0, 1e7, 0, 0, " m")
        self.o_zmin.setSpecialValueText(tr("auto"))
        self.o_zmax.setSpecialValueText(tr("auto"))
        fo.addRow(tr("Number of layers"), self.o_n)
        fo.addRow(tr("Min depth"), self.o_zmin)
        fo.addRow(tr("Max depth"), self.o_zmax)
        w2 = QWidget()
        fm = QFormLayout(w2)
        self.m_n = QSpinBox()
        self.m_n.setRange(1, 8)
        self.m_n.setValue(3)
        self.m_start = QComboBox()
        self.m_start.addItem(tr("Automatic (from Occam)"), "auto")
        self.m_start.addItem(tr("From table"), "table")
        self.m_tab = QTableWidget(3, 2)
        self.m_tab.setHorizontalHeaderLabels([tr("ρ (Ω·m)"), tr("h (m)")])
        self.m_tab.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.m_tab.setMaximumHeight(150)
        fm.addRow(tr("Number of layers"), self.m_n)
        fm.addRow(tr("Starting model"), self.m_start)
        fm.addRow(self.m_tab)
        self.stack.addWidget(w1)
        self.stack.addWidget(w2)
        f2.addRow(self.stack)
        self.target = sci_spin(0.1, 10, 1.0, 2)
        self.maxit = QSpinBox()
        self.maxit.setRange(1, 100)
        self.maxit.setValue(20)
        f2.addRow(tr("Target RMS"), self.target)
        f2.addRow(tr("Max iterations"), self.maxit)
        self.zaxis = QComboBox()
        self.zaxis.addItems([tr("log"), tr("linear")])
        self.zaxis.setCurrentIndex(1)
        f2.addRow(tr("Depth axis"), self.zaxis)
        self.b_run = QPushButton(tr("▶  Run inversion"))
        self.b_run.setObjectName("primary")
        f2.addRow(self.b_run)
        self.prog = QProgressBar()
        f2.addRow(self.prog)
        ll.addWidget(g2)
        h2 = QHBoxLayout()
        self.b_em, self.b_ef = QPushButton(tr("Export model (CSV)…")), QPushButton(tr("Export fit (CSV)…"))
        h2.addWidget(self.b_em)
        h2.addWidget(self.b_ef)
        ll.addLayout(h2)
        self.msg = label("", "warn")
        ll.addWidget(self.msg)
        ll.addStretch(1)
        sc = QScrollArea()
        sc.setWidget(left)
        sc.setWidgetResizable(True)
        sc.setMaximumWidth(420)
        self.mp_model = MplWidget(figsize=(4.5, 6))
        self.mp_fit = MplWidget(figsize=(6, 6))
        self.txt = QTextBrowser()
        centre = QSplitter(Qt.Orientation.Vertical)
        centre.addWidget(self.mp_model)
        centre.addWidget(self.txt)
        centre.setSizes([600, 260])
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(sc)
        sp.addWidget(centre)
        sp.addWidget(self.mp_fit)
        sp.setSizes([400, 520, 700])
        QVBoxLayout(self).addWidget(sp)
        b_edi.clicked.connect(self.load_edi)
        b_csv.clicked.connect(self.load_csv)
        self.alg.currentIndexChanged.connect(lambda i: self.stack.setCurrentIndex(i))
        self.m_n.valueChanged.connect(lambda n: self.m_tab.setRowCount(n))
        self.b_run.clicked.connect(self.run)
        self.zaxis.currentIndexChanged.connect(self.draw)
        for w in (self.comp, self.use):
            w.currentIndexChanged.connect(self.draw_data_only)
        self.floor.valueChanged.connect(self.draw_data_only)
        self.b_em.clicked.connect(self.export_model)
        self.b_ef.clicked.connect(self.export_fit)

    # ---------------------------------------------------------------- data
    def set_data(self, pkg):
        """pkg: freq, Z (array or dict ZXY/ZYX), Zerr, true, source."""
        self.raw = pkg
        self.res = None
        f = np.asarray(pkg["freq"])
        txt = tr("Loaded: {s}", s=pkg.get("source", "")) + "<br>" + \
            tr("{n} frequencies, {a} – {b} Hz", n=f.size, a=f"{f.min():.3g}", b=f"{f.max():.3g}")
        if pkg.get("true"):
            txt += "<br><b>" + tr("True model known (synthetic)") + "</b>"
        self.info.setText(txt)
        self.comp.setEnabled(isinstance(pkg["Z"], dict))
        self.draw_data_only()

    def load_edi(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("Load EDI…"), "", "EDI (*.edi *.EDI)")
        if p:
            def _l():
                e = read_edi(p)
                Z = {"ZXY": e["Z"]["ZXY"], "ZYX": e["Z"]["ZYX"], "ZXX": e["Z"].get("ZXX"), "ZYY": e["Z"].get("ZYY")}
                E = e["err"] or {}
                self.set_data({"freq": e["freq"], "Z": Z, "Zerr": E, "true": e["true_model"],
                               "source": p.split("/")[-1]})
            guarded(self, _l)

    def load_csv(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("Load CSV…"), "", "CSV (*.csv)")
        if p:
            def _l():
                df = pd.read_csv(p, comment="#")
                f = df["Frequency_Hz"].values
                Z = df["Impedance_Real"].values + 1j * df["Impedance_Imag"].values
                E = df["Impedance_Error"].values if "Impedance_Error" in df else None
                self.set_data({"freq": f, "Z": Z, "Zerr": E, "true": None, "source": p.split("/")[-1]})
            guarded(self, _l)

    def dataset(self):
        pkg = self.raw
        Z, E = pkg["Z"], pkg.get("Zerr")
        if isinstance(Z, dict):
            c = self.comp.currentIndex()
            if c == 0:
                z, e = Z["ZXY"], (E or {}).get("ZXY")
            elif c == 1:
                z, e = -Z["ZYX"], (E or {}).get("ZYX")
            else:
                zxx = Z.get("ZXX") if Z.get("ZXX") is not None else 0
                zyy = Z.get("ZYY") if Z.get("ZYY") is not None else 0
                z = np.sqrt(zxx * zyy - Z["ZXY"] * Z["ZYX"])
                z = np.where(np.angle(z) < 0, -z, z)
                e = None if not E else np.sqrt((E.get("ZXY") ** 2 + E.get("ZYX") ** 2) / 2)
        else:
            z, e = Z, E
        ok = np.isfinite(z)
        d = InvData.from_impedance(np.asarray(pkg["freq"])[ok], z[ok], None if e is None else np.asarray(e)[ok],
                                   floor=self.floor.value() / 100, source=pkg.get("source", ""),
                                   true_model=pkg.get("true"))
        d.use = self.use.currentData()
        return d

    # ---------------------------------------------------------------- run
    def run(self):
        if self.raw is None:
            self.msg.setText(tr("No data loaded."))
            return
        try:
            d = self.dataset()
        except ValueError as e:
            self.msg.setText(str(e))
            return
        self.msg.setText("")
        alg, tgt, mi = self.alg.currentData(), self.target.value(), self.maxit.value()
        n_o = self.o_n.value()
        zmin, zmax = self.o_zmin.value() or None, self.o_zmax.value() or None
        n_m = self.m_n.value()
        table = None
        if alg == "marq" and self.m_start.currentData() == "table":
            try:
                rr = [float(self.m_tab.item(i, 0).text()) for i in range(n_m)]
                hh = [float(self.m_tab.item(i, 1).text()) for i in range(n_m - 1)]
                table = (rr, hh)
            except (AttributeError, ValueError):
                self.msg.setText("Fill the starting-model table (ρ for all layers, h for all but the last).")
                return

        def job(progress, cancelled):
            import time
            t = time.perf_counter()
            if alg == "occam":
                r = occam(d, n_o, zmin, zmax, tgt, mi, progress=progress, cancelled=cancelled)
            elif table:
                r = marquardt(d, *table, max_iter=mi, progress=progress, cancelled=cancelled)
            else:
                r = marquardt_auto(d, n_m, max_iter=mi, progress=progress, cancelled=cancelled)
            r["time"] = time.perf_counter() - t
            r["data"] = d
            return r
        self.b_run.setEnabled(False)
        self.w = SimWorker(job, self)
        self.w.progress.connect(lambda k, n, s: (self.prog.setMaximum(n), self.prog.setValue(k)))
        self.w.done.connect(self._done)
        self.w.failed.connect(lambda s: self.msg.setText(s))
        self.w.finished.connect(lambda: self.b_run.setEnabled(True))
        self.w.start()

    def _done(self, r):
        self.res = r
        if r["method"] == "marquardt":
            self.m_tab.setRowCount(len(r["rho"]))
            for i, v in enumerate(r["rho"]):
                self.m_tab.setItem(i, 0, QTableWidgetItem(f"{v:.4g}"))
                self.m_tab.setItem(i, 1, QTableWidgetItem(f"{r['thick'][i]:.4g}" if i < len(r["thick"]) else ""))
        self.draw()

    # ---------------------------------------------------------------- plots
    def draw_data_only(self, *a):
        self.res = None
        self.draw()

    def draw(self, *a):
        if self.raw is None:
            return
        try:
            d = self.res["data"] if self.res else self.dataset()
        except ValueError as e:
            self.msg.setText(str(e))
            return
        r = self.res
        # ---- fit
        self.mp_fit.clear()
        fig = self.mp_fit.fig
        gs = fig.add_gridspec(3, 1, height_ratios=[3, 2, 1.6])
        ax_r, ax_p, ax_h = (fig.add_subplot(gs[k]) for k in range(3))
        setup_rho_phase(ax_r, ax_p, GUI)
        f = d.freq
        ax_r.errorbar(f, d.rho, yerr=d.rho * d.sd_logrho * np.log(10), fmt="o", ms=4, capsize=2,
                      color=GUI["accent2"], label=tr("Observed"))
        ax_p.errorbar(f, d.phase, yerr=d.sd_phase, fmt="o", ms=4, capsize=2, color=GUI["accent2"])
        if r:
            ax_r.plot(f, r["resp_rho"], "-", color=GUI["accent"], lw=2, label=tr("Model response"))
            ax_p.plot(f, r["resp_phase"], "-", color=GUI["accent"], lw=2)
            it = [h["iter"] for h in r["history"]]
            ax_h.semilogy(it, [h["rms"] for h in r["history"]], "-o", color=GUI["accent"], ms=4)
            ax_h.axhline(r.get("target", 1.0), color=GUI["warn"], ls="--", lw=1)
        style_ax(ax_h, GUI)
        ax_h.set_xlabel(tr("Iteration"))
        ax_h.set_ylabel("RMS")
        for ax in (ax_r, ax_p):
            ax.set_xlim(f.max() * 1.3, f.min() / 1.3)
        legend(ax_r, GUI)
        ax_r.set_title(tr("Data fit"), fontsize=10)
        style_fig(fig, GUI)
        self.mp_fit.draw()
        # ---- model: [true column] [inverted column] [ρ(z) comparison]
        self.mp_model.clear()
        fig = self.mp_model.fig
        tm = d.true_model
        ints = []
        if tm:
            ints += list(np.cumsum(tm["thick"]))
        if r and r["method"] == "marquardt":
            ints += list(np.cumsum(r["thick"]))
        if ints:
            zmax = 2.5 * max(ints)
        else:
            from core.mt_1d import bostick
            db, _ = bostick(d.rho, np.clip(d.phase, 1, 89), d.freq)
            zmax = float(np.nanpercentile(db, 70))
        zmin_log = max(0.5, (min(ints) if ints else zmax / 100) / 20)
        rho_all = list(d.rho)
        if tm:
            rho_all += tm["rho"]
        if r:
            rho_all += list(r["rho"])
        lo, hi = min(rho_all) / 3, max(rho_all) * 3
        from matplotlib.colors import LogNorm
        import matplotlib
        cmap, norm = matplotlib.colormaps["turbo"], LogNorm(lo, hi)
        ncol = (1 if tm else 0) + (1 if r else 0)
        gs = fig.add_gridspec(1, ncol + 1, width_ratios=[0.7] * ncol + [3])
        logz = self.zaxis.currentIndex() == 0

        def column(ax, rho, thick, title):
            tops = np.concatenate([[0.0], np.cumsum(thick)])
            bots = np.concatenate([tops[1:], [zmax * 10]])
            for t_, b_, v in zip(tops, bots, rho):
                ax.axhspan(max(t_, zmin_log if logz else 0), b_, color=cmap(norm(v)), lw=0)
                if t_ < zmax:
                    zc = np.sqrt(max(t_, zmin_log) * min(b_, zmax)) if logz else (t_ + min(b_, zmax)) / 2
                    ax.text(0.5, zc, f"{v:.3g}", ha="center", va="center", fontsize=8, color="white",
                            fontweight="bold", transform=ax.get_yaxis_transform())
            for t_ in tops[1:]:
                ax.axhline(t_, color="k", lw=0.8)
            ax.set_xticks([])
            ax.set_title(title, fontsize=9)
            ax._no_grid = True
        k = 0
        axes = []
        if tm:
            ax0 = fig.add_subplot(gs[0, k])
            column(ax0, tm["rho"], tm["thick"], tr("True"))
            axes.append(ax0)
            k += 1
        if r:
            ax1 = fig.add_subplot(gs[0, k], sharey=axes[0] if axes else None)
            column(ax1, r["rho"], r["thick"], tr("Inverted"))
            axes.append(ax1)
            k += 1
        ax = fig.add_subplot(gs[0, k], sharey=axes[0] if axes else None)
        style_ax(ax, GUI)
        if tm:
            rr, zz = step(tm["rho"], tm["thick"], zmax * 10)
            ax.plot(rr, zz, "-", color="#c62828", lw=2.5, label=tr("True model"))
        if r:
            if r["method"] == "marquardt" and r.get("start"):
                rr, zz = step(r["start"]["rho"], r["start"]["thick"], zmax * 10)
                ax.plot(rr, zz, ":", color=GUI["muted"], lw=1.5, label=tr("Start model"))
            rr, zz = step(r["rho"], r["thick"], zmax * 10)
            ax.plot(rr, zz, "-", color=GUI["accent"], lw=2.5, label=tr("Inverted model"))
            if r["method"] == "marquardt":
                nl = len(r["rho"])
                fac = r["factor"][:nl]
                tops = np.concatenate([[0], np.cumsum(r["thick"]), [zmax * 10]])
                for i in range(nl):
                    ax.fill_betweenx([max(tops[i], zmin_log), tops[i + 1]], r["rho"][i] / min(fac[i], 1e3),
                                     r["rho"][i] * min(fac[i], 1e3), color=GUI["accent"], alpha=0.15, lw=0)
        ax.set_xscale("log")
        ax.set_xlim(lo, hi)
        if logz:
            ax.set_yscale("log")
            ax.set_ylim(zmax, zmin_log)
        else:
            ax.set_ylim(zmax, 0)
        for a_ in axes:
            a_.set_ylabel("")
        (axes[0] if axes else ax).set_ylabel(tr("Depth (m)"))
        if axes:
            ax.tick_params(labelleft=False)
        ax.set_xlabel(tr("Resistivity (Ω·m)"))
        ax.set_title(tr("Model"), fontsize=10)
        legend(ax, GUI, loc="lower left")
        style_fig(fig, GUI)
        self.mp_model.draw()
        self._summary()

    def _summary(self):
        r = self.res
        if not r:
            self.txt.setHtml("")
            return
        n = r["history"][-1]["iter"]
        html = f"<p><b>{tr('Inversion finished: RMS = {r:.3f} after {n} iterations ({t:.1f} s).', r=r['rms'], n=n, t=r.get('time', 0))}</b></p>"
        tm = r["data"].true_model
        if tm:
            html += f"<p><b>{tr('True model')}:</b> ρ = " + " / ".join(f"{v:g}" for v in tm["rho"]) + \
                " Ω·m; h = " + (" / ".join(f"{v:g}" for v in tm["thick"]) or "—") + " m</p>"
        if r["method"] == "marquardt":
            nl = len(r["rho"])
            html += f"<table cellspacing=6><tr><th>{tr('Parameter')}</th><th>{tr('Value')}</th><th>{tr('Uncertainty (×/÷)')}</th></tr>"
            if tm and len(tm["rho"]) == nl:
                html = html.replace(f"<th>{tr('Uncertainty (×/÷)')}</th></tr>",
                                    f"<th>{tr('Uncertainty (×/÷)')}</th><th>{tr('True model')}</th></tr>")
            truev = (list(tm["rho"]) + list(tm["thick"])) if tm and len(tm["rho"]) == nl else None
            for k, nm in enumerate(r["names"]):
                v = r["rho"][k] if k < nl else r["thick"][k - nl]
                fac = r["factor"][k]
                fs = tr("unresolved") if fac > 100 else f"{fac:.2f}"
                tv = f"<td>{truev[k]:g}</td>" if truev else ""
                html += f"<tr><td>{nm}</td><td>{v:.4g}</td><td>{fs}</td>{tv}</tr>"
            html += "</table>"
            for i in range(nl - 1):
                html += f"<p>{tr('Layer')} {i + 1}: S = h/ρ = {r['thick'][i] / r['rho'][i]:.3g} S, T = h·ρ = {r['thick'][i] * r['rho'][i]:.3g} Ω·m²</p>"
            C, names = r["corr"], r["free_names"]
            pairs = [f"{names[a]}–{names[b]} ({C[a, b]:+.2f})" for a in range(len(names)) for b in range(a + 1, len(names))
                     if np.isfinite(C[a, b]) and abs(C[a, b]) > 0.9]
            if pairs:
                html += f"<p style='color:#c62828'>{tr('Strongly correlated parameters (|r| > 0.9) — equivalence:')} {', '.join(pairs)}</p>"
        else:
            html += f"<p>λ = {r['history'][-1]['lam']:.3g}; {tr('Roughness')} = {r['history'][-1]['roughness']:.3g}; {r['n_layers']} layers</p>"
        self.txt.setHtml(html)

    # ---------------------------------------------------------------- export
    def export_model(self):
        if not self.res:
            return
        p = ask_save(self, tr("Export model (CSV)…"), "CSV (*.csv)", "inverted_model_1d.csv")
        if p:
            r = self.res
            df = pd.DataFrame({"Layer": np.arange(1, len(r["rho"]) + 1), "Top_m": r["depth_top"],
                               "Thickness_m": list(r["thick"]) + [np.inf], "Resistivity_OhmM": r["rho"]})
            guarded(self, lambda: df.to_csv(p, index=False), done_msg=tr("Saved {p}", p=p))

    def export_fit(self):
        if not self.res:
            return
        p = ask_save(self, tr("Export fit (CSV)…"), "CSV (*.csv)", "inversion_fit_1d.csv")
        if p:
            r, d = self.res, self.res["data"]
            df = pd.DataFrame({"Frequency_Hz": d.freq, "RhoA_obs": d.rho, "Phase_obs": d.phase,
                               "RhoA_pred": r["resp_rho"], "Phase_pred": r["resp_phase"]})
            guarded(self, lambda: df.to_csv(p, index=False), done_msg=tr("Saved {p}", p=p))
