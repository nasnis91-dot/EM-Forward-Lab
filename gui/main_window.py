"""Main window: welcome page + workspace tabs, language switch (EN/ID), session save/load."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

from appinfo import APP_NAME, APP_VERSION
from export.export_json import read_json, write_json
from i18n import get_lang, pick, set_lang, tr

from .tab_1d import Tab1D
from .tab_2d import Tab2D
from .tab_inv1d import TabInv1D
from .tab_inv2d import TabInv2D
from .tab_learning import TabLearning
from .tab_noise import TabNoise

SUBTITLE = "MT | AMT | VLF-R — Forward Modelling & Inversion"
CREDIT = "Developed by Yanis Mawardinur"


class Welcome(QWidget):
    def __init__(self, open_tab):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(60, 40, 60, 30)
        t = QLabel(APP_NAME)
        t.setStyleSheet("font-size: 40px; font-weight: 800; color: #0d47a1;")
        s = QLabel(tr(SUBTITLE) if get_lang() == "id" else SUBTITLE)
        s.setStyleSheet("font-size: 16px; color: #1565c0;")
        purpose = QLabel(pick(
            "This program is designed to help students understand the <b>Geophysical Inversion</b> course "
            "at <b>Universitas Syiah Kuala</b>.<br>Build a resistivity model, compute its electromagnetic "
            "response, add realistic noise, export the data as EDI, invert it, and compare the result with "
            "the true model.",
            "Program ini dibuat untuk membantu mahasiswa memahami perkuliahan <b>Inversi Geofisika</b> di "
            "<b>Universitas Syiah Kuala</b>.<br>Buat model resistivitas, hitung respons elektromagnetiknya, "
            "tambahkan noise realistis, ekspor data ke EDI, lakukan inversi, lalu bandingkan hasilnya dengan "
            "model sebenarnya."))
        purpose.setWordWrap(True)
        purpose.setStyleSheet("font-size: 15px; color: #0d2a4a; padding: 14px; background: #f1f7fe;"
                              "border-left: 5px solid #1565c0; border-radius: 4px;")
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addSpacing(16)
        lay.addWidget(purpose)
        lay.addSpacing(18)
        grid = QGridLayout()
        cards = [(1, tr("1D Forward"), pick("Layered earth: edit layers, instant ρa/φ curves.",
                                             "Bumi berlapis: ubah lapisan, kurva ρa/φ langsung.")),
                 (2, tr("2D Forward"), pick("TE/TM finite-volume solver, presets, pseudosections.",
                                             "Solver TE/TM volume-hingga, preset, pseudosection.")),
                 (3, tr("Noise & Data"), pick("Add Gaussian/uniform/outlier noise and export EDI.",
                                               "Tambah noise Gaussian/uniform/pencilan dan ekspor EDI.")),
                 (4, tr("1D Inversion"), pick("Occam (smooth) and Marquardt (layered) with uncertainties.",
                                               "Occam (halus) dan Marquardt (berlapis) dengan ketidakpastian.")),
                 (5, tr("2D Inversion"), pick("Simple Occam 2D inversion of TE/TM profiles.",
                                               "Inversi Occam 2D sederhana untuk profil TE/TM.")),
                 (6, tr("Learning Mode"), pick("Theory, equations and guided exercises.",
                                                "Teori, persamaan, dan latihan terpandu."))]
        for k, (idx, title, desc) in enumerate(cards):
            fr = QFrame()
            fr.setStyleSheet("QFrame{background:#ffffff; border:1px solid #bbdefb; border-radius:8px;}")
            v = QVBoxLayout(fr)
            a = QLabel(f"<span style='color:#1565c0;font-size:20px;font-weight:800'>{idx}</span>&nbsp; "
                       f"<span style='font-size:15px;font-weight:700'>{title}</span>")
            d = QLabel(desc)
            d.setWordWrap(True)
            d.setStyleSheet("color:#546e7a; border:none;")
            a.setStyleSheet("border:none;")
            v.addWidget(a)
            v.addWidget(d)
            grid.addWidget(fr, k // 3, k % 3)
        lay.addLayout(grid)
        lay.addStretch(1)
        start = QPushButton(tr("Start") + "  →")
        start.setObjectName("primary")
        start.setMinimumHeight(40)
        start.clicked.connect(lambda: open_tab(0))
        lay.addWidget(start, alignment=Qt.AlignmentFlag.AlignLeft)
        c = QLabel(f"<b>{CREDIT}</b> — Universitas Syiah Kuala &nbsp;•&nbsp; v{APP_VERSION}")
        c.setStyleSheet("color:#546e7a; font-size: 13px; padding-top: 10px;")
        lay.addWidget(c)


class MainWindow(QMainWindow):
    def __init__(self, app_ref=None):
        super().__init__()
        self.app_ref = app_ref
        self.setWindowTitle(f"{APP_NAME} — {SUBTITLE}")
        self.resize(1600, 980)
        header = QWidget(objectName="header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)
        tbox = QVBoxLayout()
        tbox.setSpacing(0)
        tbox.addWidget(QLabel(APP_NAME, objectName="title"))
        tbox.addWidget(QLabel(SUBTITLE, objectName="subtitle"))
        hl.addLayout(tbox)
        hl.addStretch(1)
        self.b_home = QPushButton("⌂  " + tr("Home"))
        self.b_home.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        hl.addWidget(self.b_home)
        self.lang = QComboBox()
        self.lang.addItems(["English", "Bahasa Indonesia"])
        self.lang.setCurrentIndex(1 if get_lang() == "id" else 0)
        self.lang.currentIndexChanged.connect(self.switch_language)
        hl.addWidget(QLabel(tr("Language") + ":", objectName="subtitle"))
        hl.addWidget(self.lang)
        hl.addSpacing(12)
        hl.addWidget(QLabel(CREDIT, objectName="credit"))

        self.t1 = Tab1D()
        self.t2 = Tab2D()
        self.tn = TabNoise(self.t1, self.t2)
        self.ti1 = TabInv1D()
        self.ti2 = TabInv2D()
        self.tlearn = TabLearning()
        self.tabs = QTabWidget()
        for w, name in ((self.t1, "1D Forward"), (self.t2, "2D Forward"), (self.tn, "Noise & Data"),
                        (self.ti1, "1D Inversion"), (self.ti2, "2D Inversion"), (self.tlearn, "Learning Mode")):
            self.tabs.addTab(w, tr(name).replace("&", "&&"))
        self.tlearn.load_experiment.connect(self._load_exp)
        self.tn.send1d.connect(self._to_inv1d)
        self.tn.send2d.connect(self._to_inv2d)
        self.tabs.currentChanged.connect(lambda i: self.tn.refresh() if self.tabs.widget(i) is self.tn else None)

        self.stack = QStackedWidget()
        self.stack.addWidget(Welcome(self.open_tab))
        self.stack.addWidget(self.tabs)
        central = QWidget()
        cl = QVBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        cl.addWidget(header)
        cl.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        footer = QLabel(f"  {CREDIT} — Universitas Syiah Kuala   •   {APP_NAME} v{APP_VERSION}   •   "
                        + tr("plane-wave, quasi-static, exp(+iωt)"))
        footer.setObjectName("credit")
        self.statusBar().addPermanentWidget(footer, 1)
        mb = self.menuBar()
        fm = mb.addMenu(tr("File"))
        for text, key, fn in ((tr("Open session…"), QKeySequence.StandardKey.Open, self.open_session),
                              (tr("Save session…"), QKeySequence.StandardKey.Save, self.save_session),
                              (tr("Quit"), QKeySequence.StandardKey.Quit, self.close)):
            a = QAction(text, self)
            a.setShortcut(key)
            a.triggered.connect(fn)
            fm.addAction(a)
        hm = mb.addMenu(tr("Help"))
        a = QAction(tr("About"), self)
        a.triggered.connect(self.about)
        hm.addAction(a)

    def open_tab(self, i):
        self.stack.setCurrentIndex(1)
        self.tabs.setCurrentIndex(i)

    def _load_exp(self, exp):
        self.t1.load_experiment(exp)
        self.open_tab(0)

    def _to_inv1d(self, pkg):
        self.ti1.set_data(pkg)
        self.tabs.setCurrentWidget(self.ti1)

    def _to_inv2d(self, pkg):
        self.ti2.set_data(pkg)
        self.tabs.setCurrentWidget(self.ti2)

    def switch_language(self, idx):
        state = self.session()
        set_lang("id" if idx == 1 else "en")
        w = MainWindow(self.app_ref)
        try:
            w.restore(state)
        except Exception:
            pass
        w.stack.setCurrentIndex(self.stack.currentIndex())
        w.tabs.setCurrentIndex(self.tabs.currentIndex())
        w.setGeometry(self.geometry())
        if self.app_ref is not None:
            self.app_ref["window"] = w
        w.show()
        self.close()

    def session(self):
        from appinfo import metadata
        return {"type": "EM-Forward Lab session", "metadata": metadata(), "tab1d": self.t1.state(),
                "tab2d": self.t2.state()}

    def save_session(self):
        p, _ = QFileDialog.getSaveFileName(self, tr("Save session…"), "session.emflab.json", "Session (*.json)")
        if p:
            try:
                write_json(p, self.session())
                self.statusBar().showMessage(tr("Session saved: {p}", p=p), 5000)
            except Exception as e:
                QMessageBox.critical(self, tr("Error"), str(e))

    def open_session(self):
        p, _ = QFileDialog.getOpenFileName(self, tr("Open session…"), "", "Session (*.json)")
        if p:
            try:
                self.restore(read_json(p))
                self.statusBar().showMessage(tr("Session loaded: {p}", p=p), 5000)
            except Exception as e:
                QMessageBox.critical(self, tr("Error"), tr("Could not load session:\n{e}", e=e))

    def restore(self, s):
        if s.get("type") != "EM-Forward Lab session":
            raise ValueError(tr("Not an EM-Forward Lab session file."))
        self.t1.set_state(s["tab1d"])
        self.t2.set_state(s["tab2d"])

    def about(self):
        QMessageBox.about(self, APP_NAME, f"<h3>{APP_NAME} v{APP_VERSION}</h3><p>{SUBTITLE}</p>"
                          f"<p>{CREDIT}<br>Universitas Syiah Kuala</p>")

    def closeEvent(self, ev):
        for w in (getattr(self.t2, "worker", None), getattr(self.ti1, "w", None), getattr(self.ti2, "w", None)):
            if w is not None and w.isRunning():
                w.cancel()
                w.wait(3000)
        super().closeEvent(ev)
