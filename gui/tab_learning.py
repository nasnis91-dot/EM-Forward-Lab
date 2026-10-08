"""Learning mode: theory, equations, parameters and guided experiments."""
import io
import re

from matplotlib import mathtext
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QImage, QTextDocument
from PySide6.QtWidgets import (QGroupBox, QHBoxLayout, QListWidget, QPushButton, QSplitter, QTextBrowser,
                               QVBoxLayout, QWidget)

from education.experiments import EXPERIMENTS
from education import theory_id
from education.theory import TOPICS as TOPICS_EN
from i18n import get_lang, tr

PARAMS_HTML = """
<h2>Parameters and units</h2>
<table cellspacing=6>
<tr><th align=left>Symbol</th><th align=left>Meaning</th><th align=left>Unit</th></tr>
<tr><td>ρ</td><td>Resistivity (σ = 1/ρ conductivity)</td><td>Ω·m (S/m)</td></tr>
<tr><td>h</td><td>Layer thickness</td><td>m</td></tr>
<tr><td>f, ω = 2πf</td><td>Frequency, angular frequency</td><td>Hz, rad/s</td></tr>
<tr><td>T = 1/f</td><td>Period</td><td>s</td></tr>
<tr><td>μ₀</td><td>Magnetic permeability of free space, 4π×10⁻⁷</td><td>H/m</td></tr>
<tr><td>Z</td><td>Impedance E/H (EDI files: mV/km/nT; 1 Ω = 795.8 mV/km/nT)</td><td>Ω</td></tr>
<tr><td>ρa</td><td>Apparent resistivity |Z|²/(ωμ₀)</td><td>Ω·m</td></tr>
<tr><td>φ</td><td>Impedance phase arg Z</td><td>degrees</td></tr>
<tr><td>δ</td><td>Skin depth ≈ 503√(ρ/f)</td><td>m</td></tr>
<tr><td>S = h/ρ</td><td>Conductance of a layer</td><td>S (siemens)</td></tr>
<tr><td>T = hρ</td><td>Transverse resistance of a layer</td><td>Ω·m²</td></tr>
<tr><td>r</td><td>Transmitter distance (VLF-R)</td><td>km</td></tr>
</table>
"""


PARAMS_HTML_ID = (PARAMS_HTML.replace("Parameters and units", "Parameter dan satuan")
                  .replace("Symbol", "Simbol").replace("Meaning", "Arti").replace("Unit", "Satuan")
                  .replace("Resistivity (σ = 1/ρ conductivity)", "Resistivitas (σ = 1/ρ konduktivitas)")
                  .replace("Layer thickness", "Ketebalan lapisan")
                  .replace("Frequency, angular frequency", "Frekuensi, frekuensi sudut")
                  .replace("Period", "Periode")
                  .replace("Magnetic permeability of free space", "Permeabilitas magnetik ruang hampa")
                  .replace("Impedance E/H (EDI files", "Impedansi E/H (berkas EDI")
                  .replace("Apparent resistivity", "Resistivitas semu")
                  .replace("Impedance phase", "Fase impedansi")
                  .replace("degrees", "derajat")
                  .replace("Conductance of a layer", "Konduktansi lapisan")
                  .replace("Transverse resistance of a layer", "Resistansi transversal lapisan")
                  .replace("Transmitter distance", "Jarak pemancar"))


class TabLearning(QWidget):
    load_experiment = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.topics = QListWidget()
        self.T = theory_id.TOPICS if get_lang() == "id" else TOPICS_EN
        self.topics.addItems(list(self.T) + [tr("Parameters & units"), tr("Guided experiments")])
        self.topics.setMaximumWidth(260)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(self._anchor)
        self.view.document().setDefaultStyleSheet(
            "h2{color:#1565c0;} h3{color:#1976d2;} th{color:#1565c0;} li{margin-bottom:4px;}")
        sp = QSplitter(Qt.Orientation.Horizontal)
        sp.addWidget(self.topics)
        sp.addWidget(self.view)
        sp.setSizes([250, 1100])
        QVBoxLayout(self).addWidget(sp)
        self._eq_cache = {}
        self.topics.currentRowChanged.connect(self.show_topic)
        self.topics.setCurrentRow(0)

    def _eq(self, tex):
        key = f"eq{len(self._eq_cache)}" if tex not in self._eq_cache else self._eq_cache[tex]
        if tex not in self._eq_cache:
            buf = io.BytesIO()
            mathtext.math_to_image(tex, buf, dpi=150, format="png", color="#0d2a4a")
            img = QImage.fromData(buf.getvalue())
            self.view.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(key), img)
            self._eq_cache[tex] = key
        return f"<p align=center><img src='{key}'></p>"

    def render(self, html):
        return re.sub(r"\[\[EQ:(.*?)\]\]", lambda m: self._eq(m.group(1).strip()), html, flags=re.S)

    def show_topic(self, row):
        name = self.topics.item(row).text()
        idl = get_lang() == "id"
        if name in self.T:
            html = self.T[name]
        elif name == tr("Parameters & units"):
            html = PARAMS_HTML_ID if idl else PARAMS_HTML
        else:
            html = ("<h2>Eksperimen terpandu</h2><p>Klik tautan untuk memuat model ke tab Forward 1D.</p>" if idl else
                    "<h2>Guided experiments</h2><p>Click the link to put the model into the 1D tab.</p>")
            for i, e in enumerate(EXPERIMENTS):
                title, task, obs = (theory_id.EXPERIMENTS[i] if idl and i < len(theory_id.EXPERIMENTS)
                                    else (e["title"], e["task"], e["observe"]))
                L = ("Metode", "Model", "Tugas", "Amati", f"▶ Muat eksperimen {i + 1} ke tab Forward 1D") if idl else \
                    ("Method", "Model", "Task", "Observe", f"▶ Load experiment {i + 1} into the 1D tab")
                html += (f"<h3>{title}</h3><p><b>{L[0]}:</b> {e['method']} &nbsp; <b>{L[1]}:</b> ρ = "
                         + " / ".join(f"{v:g}" for v in e["rho"]) + " Ω·m, h = "
                         + (" / ".join(f"{v:g}" for v in e["thick"]) or "—") + " m</p>"
                         f"<p><b>{L[2]}:</b> {task}<br><b>{L[3]}:</b> {obs}</p>"
                         f"<p><a href='exp:{i}' style='color:#1565c0'>{L[4]}</a></p>")
        self.view.setHtml(self.render(html))

    def _anchor(self, url):
        s = url.toString()
        if s.startswith("exp:"):
            self.load_experiment.emit(EXPERIMENTS[int(s[4:])])
