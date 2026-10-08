"""File-dialog based export helpers shared by the tabs."""
import os
import traceback

from matplotlib.figure import Figure
from PySide6.QtWidgets import QFileDialog, QMessageBox

from appinfo import CREDIT
from visualization.theme import LIGHT, credit


def ask_save(parent, title, filt, default):
    path, _ = QFileDialog.getSaveFileName(parent, title, default, filt)
    return path or None


def ask_dir(parent, title):
    return QFileDialog.getExistingDirectory(parent, title) or None


def guarded(parent, fn, *args, done_msg=None):
    try:
        fn(*args)
        if done_msg:
            QMessageBox.information(parent, "Export", done_msg)
        return True
    except Exception as e:  # show the real reason, never fail silently
        QMessageBox.critical(parent, "Error", f"{e}\n\n{traceback.format_exc(limit=3)}")
        return False


def export_figures(parent, builders):
    """builders: list of (basename, callable(fig, theme)). Saves PNG (200 dpi) + SVG, light theme."""
    d = ask_dir(parent, "Choose folder for figures")
    if not d:
        return

    def _do():
        for name, build in builders:
            fig = Figure(figsize=(10, 6.5), layout="constrained")
            build(fig, LIGHT)
            credit(fig, LIGHT, CREDIT)
            fig.savefig(os.path.join(d, name + ".png"), dpi=200, facecolor=fig.get_facecolor())
            fig.savefig(os.path.join(d, name + ".svg"), facecolor=fig.get_facecolor())
    guarded(parent, _do, done_msg=f"Saved {len(builders)} figure(s) as PNG + SVG in\n{d}")
