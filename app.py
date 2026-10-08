"""EM-Forward Lab — desktop application entry point.

Run:  python app.py
Developed by Yanis Mawardinur for Academic Purpose
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib  # noqa: E402

matplotlib.use("QtAgg")

from PySide6.QtWidgets import QApplication  # noqa: E402

from appinfo import APP_NAME  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402
from gui.style import QSS  # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    ref = {}
    w = MainWindow(ref)
    ref["window"] = w
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
