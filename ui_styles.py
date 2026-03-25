"""
ui_styles.py
QSS stylesheet for Garbage Collector.

Rules:
- NO wildcard background on *  — that causes bleed into scroll viewports
- All backgrounds set explicitly on named widgets only
- Fixed pixel heights replaced with min-height / padding so layout scales
- Consistent colour palette via comments (no CSS variables in QSS)

Palette:
  bg-deep    #0d1117   main background
  bg-surface #13181f   sidebar / panel surface
  bg-raised  #1c2128   group boxes, scroll inner
  bg-control #21262d   inputs, buttons
  border     #2d333b   all borders
  accent     #58a6ff   blue accent (selections, focus)
  green      #3fb950   success / estimate
  red        #f85149   error / cancel
  amber      #d29922   info
  purple     #a371f7   summary
  text-hi    #e6edf3   primary text
  text-mid   #8b949e   secondary text
  text-dim   #484f58   disabled / label
"""

QSS = """
/* ── Base window & root ─────────────────────────────────────────────── */
QMainWindow {
    background-color: #0d1117;
}

QWidget#root {
    background-color: #0d1117;
}

/* ── Generic widget reset (NO background here — avoids bleed) ────────── */
QWidget {
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", monospace;
    font-size: 11px;
    color: #e6edf3;
    outline: none;
}

/* ── Top bar ─────────────────────────────────────────────────────────── */
QWidget#topBar {
    background-color: #13181f;
    border-bottom: 1px solid #2d333b;
}

/* ── Left panel ──────────────────────────────────────────────────────── */
QWidget#leftPanel {
    background-color: #13181f;
    border-right: 1px solid #2d333b;
}

/* ── Scroll area — transparent so panel background shows through ─────── */
QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

/* ── Scroll bar ──────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: transparent;
    width: 5px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #2d333b;
    border-radius: 2px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #58a6ff;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: none;
    height: 0;
    border: none;
}

QScrollBar:horizontal {
    height: 0;
    background: none;
}

/* ── Group boxes ──────────────────────────────────────────────────────── */
QGroupBox {
    background-color: #1c2128;
    border: 1px solid #2d333b;
    border-radius: 6px;
    margin-top: 18px;
    padding: 6px 4px 4px 4px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 0px;
    color: #58a6ff;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1.5px;
    padding: 2px 5px;
    background-color: #13181f;
    border-radius: 2px;
}

/* ── Checkboxes ───────────────────────────────────────────────────────── */
QCheckBox {
    color: #c9d1d9;
    spacing: 9px;
    padding: 3px 6px;
    border-radius: 4px;
    background-color: transparent;
}

QCheckBox:hover {
    background-color: #21262d;
    color: #e6edf3;
}

QCheckBox:disabled {
    color: #484f58;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 13px;
    height: 13px;
    border: 1px solid #444c56;
    border-radius: 3px;
    background-color: #0d1117;
}

QCheckBox::indicator:hover {
    border-color: #58a6ff;
    background-color: #1c2128;
}

QCheckBox::indicator:checked {
    background-color: #238636;
    border-color: #2ea043;
}

QCheckBox::indicator:checked:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

QCheckBox::indicator:disabled {
    background-color: #161b22;
    border-color: #2d333b;
}

/* ── Buttons — base ──────────────────────────────────────────────────── */
QPushButton {
    background-color: #21262d;
    color: #c9d1d9;
    border: 1px solid #2d333b;
    border-radius: 5px;
    padding: 5px 14px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #2d333b;
    border-color: #58a6ff;
    color: #e6edf3;
}

QPushButton:pressed {
    background-color: #13181f;
    border-color: #58a6ff;
}

QPushButton:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

/* ── Start button ────────────────────────────────────────────────────── */
QPushButton#startBtn {
    background-color: #238636;
    color: #ffffff;
    border: 1px solid #2ea043;
    font-size: 12px;
    padding: 9px 0px;
    border-radius: 6px;
    letter-spacing: 0.5px;
}

QPushButton#startBtn:hover {
    background-color: #2ea043;
    border-color: #3fb950;
}

QPushButton#startBtn:pressed {
    background-color: #1c6e2a;
}

QPushButton#startBtn:disabled {
    background-color: #1c2128;
    color: #484f58;
    border-color: #2d333b;
}

/* ── Cancel button ───────────────────────────────────────────────────── */
QPushButton#cancelBtn {
    background-color: #2d1414;
    color: #f85149;
    border: 1px solid #6e1a1a;
    font-size: 12px;
    padding: 9px 0px;
    border-radius: 6px;
}

QPushButton#cancelBtn:hover {
    background-color: #6e1a1a;
    color: #ffffff;
    border-color: #f85149;
}

QPushButton#cancelBtn:pressed {
    background-color: #1c0a0a;
}

QPushButton#cancelBtn:disabled {
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}

/* ── Small utility buttons ───────────────────────────────────────────── */
QPushButton#smallBtn {
    background-color: transparent;
    color: #8b949e;
    border: 1px solid #2d333b;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: normal;
}

QPushButton#smallBtn:hover {
    background-color: #21262d;
    color: #c9d1d9;
    border-color: #444c56;
}

QPushButton#smallBtn:pressed {
    background-color: #13181f;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
QProgressBar {
    border: 1px solid #2d333b;
    border-radius: 4px;
    background-color: #0d1117;
    text-align: center;
    color: #8b949e;
    font-size: 10px;
    min-height: 14px;
    max-height: 14px;
}

QProgressBar::chunk {
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #1c6e2a, stop:1 #2ea043
    );
    border-radius: 3px;
}

/* ── Console ─────────────────────────────────────────────────────────── */
QWidget#rightPanel {
    background-color: #0d1117;
}

QPlainTextEdit#console {
    background-color: #090d12;
    color: #c9d1d9;
    border: none;
    border-top: 1px solid #2d333b;
    padding: 10px 12px;
    font-size: 11px;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}

/* ── Console header bar ──────────────────────────────────────────────── */
QWidget#consoleBar {
    background-color: #13181f;
    border-bottom: 1px solid #2d333b;
}

/* ── Controls panel ──────────────────────────────────────────────────── */
QWidget#controlsPanel {
    background-color: #13181f;
    border-top: 1px solid #2d333b;
}

/* ── Space estimate label ────────────────────────────────────────────── */
QLabel#spaceLabel {
    color: #3fb950;
    font-size: 11px;
    font-weight: bold;
    background-color: transparent;
    padding: 2px 0px;
}

/* ── Selected count label ────────────────────────────────────────────── */
QLabel#selLabel {
    color: #484f58;
    font-size: 10px;
    background-color: transparent;
}

/* ── Platform badge ──────────────────────────────────────────────────── */
QLabel#platformBadge {
    background-color: #1c2128;
    color: #58a6ff;
    border: 1px solid #2d333b;
    border-radius: 4px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#distroLabel {
    color: #8b949e;
    font-size: 10px;
    background-color: transparent;
    padding: 0 2px;
}

/* ── Title label ─────────────────────────────────────────────────────── */
QLabel#titleLabel {
    color: #e6edf3;
    font-size: 13px;
    font-weight: bold;
    letter-spacing: 3px;
    background-color: transparent;
}

/* ── Console header label ────────────────────────────────────────────── */
QLabel#consoleLabel {
    color: #444c56;
    font-size: 9px;
    letter-spacing: 2px;
    background-color: transparent;
}

/* ── Stats bar ───────────────────────────────────────────────────────── */
QWidget#statsBar {
    background-color: #13181f;
    border-top: 1px solid #2d333b;
}

QLabel#statValue {
    color: #58a6ff;
    font-size: 12px;
    font-weight: bold;
    background-color: transparent;
}

QLabel#statLabel {
    color: #484f58;
    font-size: 9px;
    letter-spacing: 0.5px;
    background-color: transparent;
}

QFrame#statDivider {
    background-color: #2d333b;
    border: none;
    max-width: 1px;
}

/* ── Splitter handle ─────────────────────────────────────────────────── */
QSplitter::handle {
    background-color: #2d333b;
    width: 1px;
}

QSplitter::handle:hover {
    background-color: #58a6ff;
}

/* ── Tooltips ────────────────────────────────────────────────────────── */
QToolTip {
    background-color: #1c2128;
    color: #c9d1d9;
    border: 1px solid #2d333b;
    border-radius: 4px;
    padding: 5px 9px;
    font-size: 10px;
}
"""
