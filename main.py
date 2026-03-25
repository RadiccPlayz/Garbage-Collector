"""
main.py
Entry point for Garbage Collector.
"""

import sys
from platform_detect import IS_WINDOWS

# ── Elevate on Windows ────────────────────────────────────────────────────────
if IS_WINDOWS:
    try:
        from elevate import elevate
        elevate()
    except ImportError:
        pass   # elevate not installed — continue without UAC

# ── Qt application ────────────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication
from ui_main   import MainWindow
from ui_styles import QSS


def main():
    # AA_UseHighDpiPixmaps was removed in Qt6 — high-DPI is on by default
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
