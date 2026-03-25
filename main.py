"""
main.py
Entry point for Garbage Collector.
"""

import sys
from platform_detect import IS_WINDOWS, IS_LINUX

# ── Elevate on Windows ────────────────────────────────────────────────────────
if IS_WINDOWS:
    try:
        from elevate import elevate
        elevate()
    except ImportError:
        pass   # elevate not installed — continue without UAC

# ── Qt application ────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore    import Qt

from ui_main   import MainWindow
from ui_styles import QSS


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    # High-DPI
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
