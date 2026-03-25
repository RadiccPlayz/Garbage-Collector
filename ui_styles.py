"""
ui_styles.py
QSS stylesheet for Garbage Collector.

Aesthetic: dark industrial terminal — tight grid, mono accents,
phosphor-green highlights, subtle scanline texture via gradient.
"""

QSS = """
/* ── Global ──────────────────────────────────────────────────────────── */
* {
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    color: #c9d1d9;
    outline: none;
}

QMainWindow, QWidget#root {
    background-color: #0d1117;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
QWidget#sidebar {
    background-color: #0d1117;
    border-right: 1px solid #21262d;
}

/* ── Platform badge ──────────────────────────────────────────────────── */
QLabel#platformBadge {
    background-color: #161b22;
    color: #58a6ff;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 0.5px;
}

QLabel#distroLabel {
    color: #8b949e;
    font-size: 10px;
    padding: 0 4px 6px 4px;
}

/* ── Group boxes ──────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #21262d;
    border-radius: 4px;
    margin-top: 14px;
    padding-top: 4px;
    background-color: #0d1117;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 8px;
    color: #58a6ff;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 0 4px;
    background-color: #0d1117;
}

/* ── Checkboxes ───────────────────────────────────────────────────────── */
QCheckBox {
    color: #c9d1d9;
    spacing: 8px;
    padding: 2px 4px;
    border-radius: 3px;
}

QCheckBox:hover {
    background-color: #161b22;
    color: #e6edf3;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #30363d;
    border-radius: 2px;
    background-color: #0d1117;
}

QCheckBox::indicator:hover {
    border-color: #58a6ff;
}

QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #2ea043;
    image: none;
}

QCheckBox::indicator:checked:hover {
    background-color: #2ea043;
}

QCheckBox[disabled="true"] {
    color: #484f58;
}

QCheckBox[disabled="true"]::indicator {
    background-color: #161b22;
    border-color: #21262d;
}

/* ── Scroll area ─────────────────────────────────────────────────────── */
QScrollArea {
    background-color: #0d1117;
    border: none;
}

QScrollBar:vertical {
    background: #0d1117;
    width: 6px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #30363d;
    border-radius: 3px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #58a6ff;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 4px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #30363d;
    border-color: #58a6ff;
    color: #e6edf3;
}

QPushButton:pressed {
    background-color: #161b22;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton#startBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    font-size: 12px;
    padding: 8px 20px;
    border-radius: 5px;
    letter-spacing: 0.5px;
}

QPushButton#startBtn:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

QPushButton#startBtn:pressed {
    background-color: #1a7f37;
}

QPushButton#startBtn:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton#cancelBtn {
    background-color: #b91c1c;
    color: #ffffff;
    border: 1px solid #dc2626;
    font-size: 12px;
    padding: 8px 20px;
    border-radius: 5px;
}

QPushButton#cancelBtn:hover {
    background-color: #dc2626;
}

QPushButton#cancelBtn:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

QPushButton#smallBtn {
    font-size: 10px;
    padding: 3px 10px;
    color: #8b949e;
}

QPushButton#smallBtn:hover {
    color: #c9d1d9;
    border-color: #58a6ff;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
QProgressBar {
    border: 1px solid #21262d;
    border-radius: 3px;
    background-color: #161b22;
    text-align: center;
    color: #8b949e;
    font-size: 10px;
    height: 16px;
}

QProgressBar::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #238636, stop:1 #2ea043
    );
    border-radius: 2px;
}

/* ── Console / log output ────────────────────────────────────────────── */
QPlainTextEdit#console {
    background-color: #010409;
    color: #e6edf3;
    border: 1px solid #21262d;
    border-radius: 4px;
    padding: 8px;
    font-size: 11px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

/* ── Space estimate label ─────────────────────────────────────────────── */
QLabel#spaceLabel {
    color: #3fb950;
    font-size: 11px;
    font-weight: bold;
    padding: 4px 6px;
    background-color: #0d1117;
    border-top: 1px solid #21262d;
}

/* ── Section divider labels ──────────────────────────────────────────── */
QLabel#sectionDivider {
    color: #30363d;
    font-size: 9px;
    letter-spacing: 2px;
}

/* ── Stats bar ───────────────────────────────────────────────────────── */
QWidget#statsBar {
    background-color: #161b22;
    border-top: 1px solid #21262d;
}

QLabel#statValue {
    color: #58a6ff;
    font-size: 11px;
    font-weight: bold;
}

QLabel#statLabel {
    color: #484f58;
    font-size: 10px;
}

/* ── Splitter ────────────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #21262d;
    width: 2px;
}

QSplitter::handle:hover {
    background-color: #58a6ff;
}

/* ── Tool tips ───────────────────────────────────────────────────────── */
QToolTip {
    background-color: #161b22;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 3px;
    padding: 4px 8px;
    font-size: 10px;
}
"""
