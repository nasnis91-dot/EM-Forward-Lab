"""Reusable widgets: log slider, frequency configuration, helpers."""
import numpy as np
from i18n import tr
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSlider, QSpinBox,
                               QVBoxLayout, QWidget)

from core.methods import METHODS, VLF_TRANSMITTERS, frequencies


def label(text, obj="note", wrap=True):
    lb = QLabel(text)
    lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    return lb


def sci_spin(vmin, vmax, value, decimals=4, suffix=""):
    sb = QDoubleSpinBox()
    sb.setDecimals(decimals)
    sb.setRange(vmin, vmax)
    sb.setValue(value)
    sb.setSuffix(suffix)
    sb.setKeyboardTracking(False)
    sb.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
    return sb


class LogSlider(QWidget):
    """Slider on a log10 scale with linked spin box."""
    valueChanged = Signal(float)

    def __init__(self, vmin, vmax, value, suffix="", decimals=3, parent=None):
        super().__init__(parent)
        self.lmin, self.lmax = np.log10(vmin), np.log10(vmax)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.spin = sci_spin(vmin, vmax, value, decimals, suffix)
        self.spin.setMinimumWidth(105)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self._block = False
        self.set_value(value)
        self.slider.valueChanged.connect(self._from_slider)
        self.spin.valueChanged.connect(self._from_spin)

    def _to_pos(self, v):
        return int(round((np.log10(max(v, 1e-30)) - self.lmin) / (self.lmax - self.lmin) * 1000))

    def _from_slider(self, pos):
        if self._block:
            return
        v = 10 ** (self.lmin + pos / 1000 * (self.lmax - self.lmin))
        v = float(f"{v:.3g}")
        self._block = True
        self.spin.setValue(v)
        self._block = False
        self.valueChanged.emit(v)

    def _from_spin(self, v):
        if self._block:
            return
        self._block = True
        self.slider.setValue(self._to_pos(v))
        self._block = False
        self.valueChanged.emit(v)

    def set_value(self, v, emit=False):
        self._block = True
        self.spin.setValue(v)
        self.slider.setValue(self._to_pos(v))
        self._block = False
        if emit:
            self.valueChanged.emit(v)

    def value(self):
        return self.spin.value()


class FreqConfig(QGroupBox):
    """Method selector + frequency sampling + source assumption + far-field distance."""
    changed = Signal()

    def __init__(self, title=None, n_default=None, parent=None):
        super().__init__(title or tr("Method && frequencies"), parent)
        self.n_default = n_default
        self.method = QComboBox()
        self.method.addItems(list(METHODS.keys()))
        self.fmin = sci_spin(1e-6, 1e7, 1e-4, 6, " Hz")
        self.fmax = sci_spin(1e-6, 1e7, 1e3, 2, " Hz")
        self.n = QSpinBox()
        self.n.setRange(1, 400)
        self.spacing = QComboBox()
        self.spacing.addItems(["log", "linear", "custom"])
        self.custom = QLineEdit()
        self.custom.setPlaceholderText(tr("e.g. 19800, 22200, 24000"))
        self.preset_btn = QPushButton(tr("Apply method preset"))
        self.assump = label("")
        self.tx_list = QListWidget()
        self.tx_list.setMaximumHeight(120)
        for name, fr in VLF_TRANSMITTERS.items():
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, fr)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if fr in (19800.0, 22200.0, 24000.0) else Qt.CheckState.Unchecked)
            self.tx_list.addItem(it)
        self.tx_btn = QPushButton(tr("Use checked transmitters"))
        self.distance = sci_spin(0.0, 1e5, 4000.0, 1, " km")
        self.tx_box = QWidget()
        tl = QVBoxLayout(self.tx_box)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.addWidget(label(tr("VLF transmitters (frequency presets):"), "note"))
        tl.addWidget(self.tx_list)
        tl.addWidget(self.tx_btn)
        fl = QFormLayout()
        fl.addRow(tr("Transmitter distance"), self.distance)
        tl.addLayout(fl)
        tl.addWidget(label(tr("Far-field check: frequencies with r/δ < 5 are shaded red."), "note"))

        form = QFormLayout()
        form.addRow(tr("Method"), self.method)
        form.addRow(tr("f min"), self.fmin)
        form.addRow(tr("f max"), self.fmax)
        form.addRow(tr("Samples"), self.n)
        form.addRow(tr("Spacing"), self.spacing)
        form.addRow(tr("Custom (Hz)"), self.custom)
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.preset_btn)
        lay.addWidget(self.tx_box)
        lay.addWidget(self.assump)

        self._mute = False
        self.method.currentTextChanged.connect(self._method_changed)
        self.preset_btn.clicked.connect(self.apply_preset)
        self.tx_btn.clicked.connect(self.use_transmitters)
        for w in (self.fmin, self.fmax, self.distance):
            w.valueChanged.connect(self._emit)
        self.n.valueChanged.connect(self._emit)
        self.spacing.currentTextChanged.connect(self._spacing_changed)
        self.custom.editingFinished.connect(self._emit)
        self._method_changed(self.method.currentText())

    def _emit(self, *a):
        if not self._mute:
            self.changed.emit()

    def _spacing_changed(self, s):
        self.custom.setEnabled(s == "custom")
        for w in (self.fmin, self.fmax, self.n):
            w.setEnabled(s != "custom")
        self._emit()

    def _method_changed(self, m):
        self.tx_box.setVisible(m == "VLF-R")
        self.assump.setText("<b>" + tr("Source assumption:") + "</b> " + METHODS[m]["assumption"])
        self.apply_preset()

    def apply_preset(self):
        m = METHODS[self.method.currentText()]
        self._mute = True
        if self.method.currentText() == "VLF-R":
            self.use_transmitters(emit=False)
        else:
            self.spacing.setCurrentText("log")
            self.fmin.setValue(m["fmin"])
            self.fmax.setValue(m["fmax"])
            self.n.setValue(self.n_default or m["n"])
        self._spacing_changed(self.spacing.currentText())
        self._mute = False
        self.changed.emit()

    def use_transmitters(self, emit=True):
        fs = [self.tx_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.tx_list.count())
              if self.tx_list.item(i).checkState() == Qt.CheckState.Checked]
        if not fs:
            fs = [19800.0]
        self.spacing.setCurrentText("custom")
        self.custom.setText(", ".join(f"{f:g}" for f in sorted(fs)))
        if emit:
            self._emit()

    # ------------------------------------------------------------------ public
    def method_name(self):
        return self.method.currentText()

    def freqs(self):
        sp = self.spacing.currentText()
        if sp == "custom":
            vals = []
            for t in self.custom.text().replace(";", ",").split(","):
                t = t.strip()
                if t:
                    vals.append(float(t))       # ValueError propagates -> shown to user
            return frequencies(0, 0, 0, "custom", vals)
        if self.fmin.value() >= self.fmax.value() and self.n.value() > 1:
            raise ValueError(tr("f min must be smaller than f max."))
        return frequencies(self.fmin.value(), self.fmax.value(), self.n.value(), sp)

    def distance_m(self):
        return self.distance.value() * 1e3 if self.method_name() == "VLF-R" else None

    def state(self):
        return {"method": self.method_name(), "fmin": self.fmin.value(), "fmax": self.fmax.value(),
                "n": self.n.value(), "spacing": self.spacing.currentText(), "custom": self.custom.text(),
                "distance_km": self.distance.value()}

    def set_state(self, s):
        self._mute = True
        self.method.setCurrentText(s.get("method", "MT"))
        self.spacing.setCurrentText(s.get("spacing", "log"))
        self.fmin.setValue(s.get("fmin", 1e-4))
        self.fmax.setValue(s.get("fmax", 1e3))
        self.n.setValue(s.get("n", 41))
        self.custom.setText(s.get("custom", ""))
        self.distance.setValue(s.get("distance_km", 4000.0))
        self._spacing_changed(self.spacing.currentText())
        self._mute = False
        self.changed.emit()
