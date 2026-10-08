"""White & blue Qt stylesheet."""

QSS = """
* { font-size: 12px; }
QMainWindow, QWidget { background: #ffffff; color: #0d2a4a; }
QWidget#header { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d47a1, stop:1 #1976d2);
                 border-bottom: 1px solid #0d47a1; }
QWidget#header QLabel { background: transparent; }
QLabel#title { font-size: 22px; font-weight: 700; color: #ffffff; }
QLabel#subtitle { font-size: 12px; color: #e3f2fd; }
QWidget#header QLabel#credit { color: #e3f2fd; }
QLabel#credit { color: #546e7a; font-style: italic; }
QLabel#section { font-weight: 700; color: #1565c0; padding-top: 6px; }
QLabel#note { color: #546e7a; font-size: 11px; }
QLabel#warn { color: #c62828; font-size: 11px; }
QLabel#ok { color: #2e7d32; font-size: 11px; }
QTabWidget::pane { border: 1px solid #bbdefb; top: -1px; background: #ffffff; }
QTabBar::tab { background: #e3f2fd; color: #1e4f80; padding: 8px 18px; border: 1px solid #bbdefb;
               border-bottom: none; margin-right: 2px; }
QTabBar::tab:selected { background: #ffffff; color: #0d47a1; font-weight: 600; border-top: 3px solid #1565c0; }
QTabBar::tab:hover { background: #ffffff; }
QGroupBox { border: 1px solid #bbdefb; border-radius: 6px; margin-top: 14px; padding: 8px 6px 6px 6px;
            background: #f7fbff; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #1565c0; font-weight: 700; }
QGroupBox QWidget { background: transparent; }
QPushButton { background: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px; padding: 5px 10px; color: #0d47a1; }
QPushButton:hover { background: #bbdefb; }
QPushButton:pressed { background: #90caf9; }
QPushButton:disabled { color: #9e9e9e; background: #f5f5f5; border-color: #e0e0e0; }
QPushButton#primary { background: #1565c0; border-color: #0d47a1; color: #ffffff; font-weight: 700; }
QPushButton#primary:hover { background: #1976d2; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit {
    background: #ffffff; border: 1px solid #90caf9; border-radius: 3px; padding: 3px; color: #0d2a4a;
    selection-background-color: #1565c0; selection-color: #ffffff; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 1px solid #1565c0; }
QComboBox QAbstractItemView { background: #ffffff; selection-background-color: #1565c0; selection-color: #ffffff; }
QTableWidget, QTableView, QListWidget, QTextBrowser { background: #ffffff; alternate-background-color: #f1f7fe;
    gridline-color: #dbe7f3; border: 1px solid #bbdefb; selection-background-color: #1565c0;
    selection-color: #ffffff; }
QHeaderView::section { background: #1565c0; color: #ffffff; padding: 4px; border: 0px;
    border-right: 1px solid #0d47a1; font-weight: 600; }
QSlider::groove:horizontal { height: 5px; background: #bbdefb; border-radius: 2px; }
QSlider::handle:horizontal { background: #1565c0; width: 14px; margin: -5px 0; border-radius: 7px; }
QProgressBar { border: 1px solid #90caf9; border-radius: 3px; text-align: center; background: #ffffff; }
QProgressBar::chunk { background: #1565c0; }
QScrollArea { border: none; }
QSplitter::handle { background: #e3f2fd; }
QStatusBar { background: #e3f2fd; color: #1e4f80; border-top: 1px solid #bbdefb; }
QMenuBar { background: #ffffff; } QMenuBar::item:selected { background: #e3f2fd; }
QMenu { background: #ffffff; border: 1px solid #90caf9; } QMenu::item:selected { background: #1565c0; color: #ffffff; }
QToolBar { background: transparent; border: none; }
QCheckBox::indicator, QRadioButton::indicator { width: 14px; height: 14px; }
QScrollBar:vertical { background: #f1f7fe; width: 10px; } QScrollBar::handle:vertical { background: #90caf9; border-radius: 4px; }
QScrollBar:horizontal { background: #f1f7fe; height: 10px; } QScrollBar::handle:horizontal { background: #90caf9; border-radius: 4px; }
"""
