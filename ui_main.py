"""
ui_main.py
Main application window for Garbage Collector.

Design rules:
- Every widget that needs styling has an objectName, styled in ui_styles.QSS
- NO inline setStyleSheet() calls — all visual rules live in QSS
- NO setFixedHeight() except where truly fixed (scrollbar widths etc.)
  — use setContentsMargins + padding in QSS instead, so layout scales
- All self._ attributes declared None in __init__ before _build_ui()
- _wire_signals() called after _build_ui() — safe to reference any widget
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore    import Qt, QTimer, pyqtSlot
from PyQt6.QtGui     import QColor, QIcon, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QPlainTextEdit, QPushButton, QProgressBar,
    QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from cleanup_tasks   import TaskDef, build_task_catalogue
from platform_detect import PLATFORM
from workers         import CleanupWorker, FolderSizeWorker

KIND_COLORS: Dict[str, str] = {
    "header":  "#58a6ff",
    "ok":      "#3fb950",
    "error":   "#f85149",
    "info":    "#d29922",
    "summary": "#a371f7",
    "plain":   "#8b949e",
}


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _cmd_exists(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


# ══════════════════════════════════════════════════════════════════════════════
#  Live console
# ══════════════════════════════════════════════════════════════════════════════

class LiveConsole(QPlainTextEdit):
    MAX_BLOCKS = 5_000

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._buffer: List[tuple[str, str]] = []
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._flush)
        self._timer.start()

    def append_line(self, text: str, kind: str = "plain") -> None:
        self._buffer.append((text, kind))

    def clear_console(self) -> None:
        self._buffer.clear()
        self.clear()

    def _flush(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = self._buffer[:120], self._buffer[120:]
        cur = self.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        for text, kind in batch:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(KIND_COLORS.get(kind, KIND_COLORS["plain"])))
            cur.setCharFormat(fmt)
            cur.insertText(text + "\n")
        self.setTextCursor(cur)
        self.ensureCursorVisible()


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar
# ══════════════════════════════════════════════════════════════════════════════

class _Row:
    def __init__(self, task: TaskDef, cb: QCheckBox):
        self.task = task
        self.cb   = cb


class OptionSidebar(QWidget):
    def __init__(self, tasks: List[TaskDef], parent=None):
        super().__init__(parent)
        # No objectName here — parent leftPanel handles background
        self._rows:   List[_Row]            = []
        self._groups: Dict[str, List[_Row]] = defaultdict(list)
        self._build(tasks)

    def _build(self, tasks: List[TaskDef]) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # The viewport must be transparent so leftPanel bg shows through
        scroll.viewport().setAutoFillBackground(False)

        inner = QWidget()
        inner.setAutoFillBackground(False)   # transparent — panel colour shows
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(10, 10, 6, 10)
        lay.setSpacing(4)

        grouped: Dict[str, List[TaskDef]] = defaultdict(list)
        for t in tasks:
            grouped[t.group].append(t)

        for group_name, group_tasks in grouped.items():
            box     = QGroupBox(group_name.upper())
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(4, 2, 4, 6)
            box_lay.setSpacing(0)

            for task in group_tasks:
                cb = QCheckBox(task.label)
                if task.tooltip:
                    cb.setToolTip(task.tooltip)
                if task.need_tool and not _cmd_exists(task.need_tool):
                    cb.setEnabled(False)
                    tip = (cb.toolTip() + "\n" if cb.toolTip() else "")
                    cb.setToolTip(tip + f"⚠ '{task.need_tool}' not found in PATH")

                row = _Row(task, cb)
                self._rows.append(row)
                self._groups[group_name].append(row)
                box_lay.addWidget(cb)

            lay.addWidget(box)

        lay.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def checked_tasks(self) -> List[TaskDef]:
        return [r.task for r in self._rows if r.cb.isChecked() and r.cb.isEnabled()]

    def checked_paths(self) -> List[Path]:
        out: List[Path] = []
        for r in self._rows:
            if r.cb.isChecked() and r.cb.isEnabled():
                out.extend(r.task.paths)
        return out

    def select_all(self) -> None:
        for r in self._rows:
            if r.cb.isEnabled():
                r.cb.setChecked(True)

    def deselect_all(self) -> None:
        for r in self._rows:
            r.cb.setChecked(False)

    def connect_changed(self, slot) -> None:
        for r in self._rows:
            r.cb.stateChanged.connect(slot)

    @property
    def checked_count(self) -> int:
        return sum(1 for r in self._rows if r.cb.isChecked())


# ══════════════════════════════════════════════════════════════════════════════
#  Stats bar
# ══════════════════════════════════════════════════════════════════════════════

class _StatCell(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(2)

        self._val = QLabel("—")
        self._val.setObjectName("statValue")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl = QLabel(label)
        lbl.setObjectName("statLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._val)
        lay.addWidget(lbl)

    def set(self, v: str) -> None:
        self._val.setText(v)


class StatsBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsBar")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._sel  = _StatCell("SELECTED")
        self._est  = _StatCell("EST. SPACE")
        self._free = _StatCell("FREED")
        self._time = _StatCell("TIME")

        for i, cell in enumerate((self._sel, self._est, self._free, self._time)):
            lay.addWidget(cell, 1)
            if i < 3:
                div = QFrame()
                div.setObjectName("statDivider")
                div.setFrameShape(QFrame.Shape.VLine)
                lay.addWidget(div)

    def set_selected(self, n: int)  -> None: self._sel.set(str(n))
    def set_estimate(self, n: int)  -> None: self._est.set(_fmt_bytes(n))
    def set_freed(self, n: int)     -> None: self._free.set(_fmt_bytes(n))
    def set_elapsed(self, s: float) -> None: self._time.set(f"{s:.1f}s")


# ══════════════════════════════════════════════════════════════════════════════
#  Main window
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Garbage Collector")
        try:
            self.setWindowIcon(QIcon("trash-logo.ico"))
        except Exception:
            pass
        self.resize(1280, 800)
        self.setMinimumSize(900, 560)

        # Declare every attribute before _build_ui
        self._console:        Optional[LiveConsole]      = None
        self._sidebar:        Optional[OptionSidebar]    = None
        self._stats:          Optional[StatsBar]         = None
        self._progress:       Optional[QProgressBar]     = None
        self._space_label:    Optional[QLabel]           = None
        self._sel_label:      Optional[QLabel]           = None
        self._start_btn:      Optional[QPushButton]      = None
        self._cancel_btn:     Optional[QPushButton]      = None
        self._cleanup_worker: Optional[CleanupWorker]    = None
        self._size_worker:    Optional[FolderSizeWorker] = None
        self._total_freed:    int = 0

        self._size_debounce = QTimer(self)
        self._size_debounce.setSingleShot(True)
        self._size_debounce.setInterval(300)
        self._size_debounce.timeout.connect(self._recalculate_size)

        self._build_ui()
        self._wire_signals()
        self._welcome()
        self._update_selected_count()

    # ══════════════════════════════════════════════════════════════════════════
    #  Build
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── 1. Top bar ────────────────────────────────────────────────────
        root_lay.addWidget(self._make_topbar())

        # ── 2. Splitter ───────────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left panel
        left = QWidget()
        left.setObjectName("leftPanel")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        self._sidebar = OptionSidebar(build_task_catalogue())
        left_lay.addWidget(self._sidebar, 1)          # stretches to fill
        left_lay.addWidget(self._make_controls())     # fixed at bottom

        splitter.addWidget(left)

        # Right panel — console must be created BEFORE console header
        right = QWidget()
        right.setObjectName("rightPanel")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self._console = LiveConsole()                 # created first ✓
        right_lay.addWidget(self._make_console_header())
        right_lay.addWidget(self._console, 1)

        splitter.addWidget(right)
        splitter.setSizes([360, 920])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root_lay.addWidget(splitter, 1)

        # ── 3. Stats bar ──────────────────────────────────────────────────
        self._stats = StatsBar()
        root_lay.addWidget(self._stats)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _make_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("topBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(12)
        bar.setMinimumHeight(44)

        title = QLabel("GARBAGE COLLECTOR")
        title.setObjectName("titleLabel")
        lay.addWidget(title)
        lay.addStretch()

        badge = QLabel(f"{PLATFORM.icon}  {PLATFORM.distro_name or PLATFORM.display_name}")
        badge.setObjectName("platformBadge")
        lay.addWidget(badge)

        if PLATFORM.os == "linux" and PLATFORM.version:
            ver = QLabel(PLATFORM.version)
            ver.setObjectName("distroLabel")
            lay.addWidget(ver)

        return bar

    # ── Controls (bottom of left panel) ──────────────────────────────────────

    def _make_controls(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("controlsPanel")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        # Select-all row
        sel_row = QHBoxLayout()
        sel_row.setSpacing(6)

        all_btn = QPushButton("Select All")
        all_btn.setObjectName("smallBtn")
        all_btn.clicked.connect(self._sidebar.select_all)

        none_btn = QPushButton("Clear")
        none_btn.setObjectName("smallBtn")
        none_btn.clicked.connect(self._sidebar.deselect_all)

        self._sel_label = QLabel("0 selected")
        self._sel_label.setObjectName("selLabel")

        sel_row.addWidget(all_btn)
        sel_row.addWidget(none_btn)
        sel_row.addStretch()
        sel_row.addWidget(self._sel_label)
        lay.addLayout(sel_row)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setFormat("%p%")
        lay.addWidget(self._progress)

        # Space estimate
        self._space_label = QLabel("Estimated: —")
        self._space_label.setObjectName("spaceLabel")
        lay.addWidget(self._space_label)

        # Action buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._start_btn = QPushButton("▶  START CLEANUP")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.setEnabled(False)

        self._cancel_btn = QPushButton("■  CANCEL")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setEnabled(False)

        btn_row.addWidget(self._start_btn, 3)
        btn_row.addWidget(self._cancel_btn, 2)
        lay.addLayout(btn_row)

        return panel

    # ── Console header ────────────────────────────────────────────────────────

    def _make_console_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("consoleBar")
        bar.setMinimumHeight(32)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(8)

        lbl = QLabel("CONSOLE OUTPUT")
        lbl.setObjectName("consoleLabel")
        lay.addWidget(lbl)
        lay.addStretch()

        clr = QPushButton("CLEAR")
        clr.setObjectName("smallBtn")
        clr.clicked.connect(self._console.clear_console)   # _console exists ✓
        lay.addWidget(clr)

        return bar

    # ── Wire signals ──────────────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        self._sidebar.connect_changed(self._on_selection_changed)
        self._start_btn.clicked.connect(self._start_cleanup)
        self._cancel_btn.clicked.connect(self._cancel_cleanup)

    # ══════════════════════════════════════════════════════════════════════════
    #  Slots
    # ══════════════════════════════════════════════════════════════════════════

    def _on_selection_changed(self) -> None:
        self._update_selected_count()
        self._size_debounce.start()

    def _update_selected_count(self) -> None:
        n = self._sidebar.checked_count
        self._sel_label.setText(f"{n} selected")
        self._stats.set_selected(n)
        running = self._cancel_btn.isEnabled()
        self._start_btn.setEnabled(n > 0 and not running)

    @pyqtSlot()
    def _recalculate_size(self) -> None:
        if self._size_worker and self._size_worker.isRunning():
            self._size_worker.stop()
            self._size_worker.wait(200)

        paths = self._sidebar.checked_paths()
        if not paths:
            self._space_label.setText("Estimated: —")
            self._stats.set_estimate(0)
            return

        self._space_label.setText("Estimating…")
        self._size_worker = FolderSizeWorker(paths)
        self._size_worker.result.connect(self._on_size_result)
        self._size_worker.start()

    @pyqtSlot(int)
    def _on_size_result(self, total: int) -> None:
        self._space_label.setText(f"Estimated: {_fmt_bytes(total)}")
        self._stats.set_estimate(total)

    def _start_cleanup(self) -> None:
        tasks = self._sidebar.checked_tasks()
        if not tasks:
            return

        self._console.clear_console()
        self._total_freed = 0
        self._progress.setValue(0)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        self._console.append_line(
            f"▶  Starting — {len(tasks)} task(s) on {PLATFORM.display_name}\n",
            "header",
        )

        self._cleanup_worker = CleanupWorker(tasks)
        self._cleanup_worker.log_line.connect(self._on_log_line)
        self._cleanup_worker.progress.connect(self._progress.setValue)
        self._cleanup_worker.task_done.connect(self._on_task_done)
        self._cleanup_worker.all_done.connect(self._on_all_done)
        self._cleanup_worker.start()

    def _cancel_cleanup(self) -> None:
        if self._cleanup_worker:
            self._cleanup_worker.cancel()
        self._cancel_btn.setEnabled(False)
        self._console.append_line("  ⚠ Cancellation requested…", "error")

    @pyqtSlot(str, str)
    def _on_log_line(self, text: str, kind: str) -> None:
        self._console.append_line(text, kind)

    @pyqtSlot(int, int)
    def _on_task_done(self, _idx: int, freed: int) -> None:
        self._total_freed += freed
        self._stats.set_freed(self._total_freed)

    @pyqtSlot(int, float)
    def _on_all_done(self, total_freed: int, elapsed: float) -> None:
        self._stats.set_freed(total_freed)
        self._stats.set_elapsed(elapsed)
        self._cancel_btn.setEnabled(False)
        self._start_btn.setEnabled(self._sidebar.checked_count > 0)
        self._recalculate_size()

    def _welcome(self) -> None:
        p = PLATFORM
        self._console.append_line("GARBAGE COLLECTOR  —  ready", "header")
        self._console.append_line(f"  Platform  : {p.display_name}", "info")
        if p.os == "linux":
            self._console.append_line(
                f"  Distro    : {p.distro_name}  [{p.distro_family}]", "info"
            )
            self._console.append_line(
                f"  Version   : {p.version or 'unknown'}", "info"
            )
            mgrs = [k for k in
                ("apt","dnf","yum","pacman","zypper","emerge","xbps","apk","nix","eopkg")
                if getattr(p, f"has_{k}", False)]
            self._console.append_line(
                f"  Pkg mgrs  : {', '.join(mgrs) or 'none detected'}", "info"
            )
        tools = [t for t in
            ("docker","podman","npm","pip","cargo","go","gem","gradle","maven")
            if getattr(p, f"has_{t}", False)]
        self._console.append_line(
            f"  Dev tools : {', '.join(tools) or 'none detected'}", "info"
        )
        self._console.append_line(
            "\n  Select tasks on the left and press  ▶  START CLEANUP\n", "plain"
        )
