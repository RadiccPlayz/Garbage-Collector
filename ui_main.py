"""
ui_main.py
Main application window for Garbage Collector.
"""

from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtCore    import Qt, QTimer, pyqtSlot
from PyQt6.QtGui     import QColor, QFont, QIcon, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QPlainTextEdit, QPushButton, QProgressBar,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

from cleanup_tasks import TaskDef, build_task_catalogue
from platform_detect import PLATFORM
from ui_styles import QSS
from workers import CleanupWorker, FolderSizeWorker, _bytes_human

# ── Colour map for log-line kinds ─────────────────────────────────────────────
KIND_COLORS: Dict[str, str] = {
    "header":  "#58a6ff",   # blue — task banner
    "ok":      "#3fb950",   # green — success
    "error":   "#f85149",   # red — failure
    "info":    "#d29922",   # amber — informational
    "summary": "#a371f7",   # purple — final summary
    "plain":   "#8b949e",   # grey — everything else
}


def _bytes_human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ══════════════════════════════════════════════════════════════════════════════
#  Live console widget
# ══════════════════════════════════════════════════════════════════════════════

class LiveConsole(QPlainTextEdit):
    """
    Read-only coloured console.
    Lines are buffered and flushed via a QTimer so the UI
    never blocks even when tasks emit hundreds of lines/second.
    """

    MAX_BLOCKS = 4_000   # cap scrollback

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("console")
        self.setReadOnly(True)
        self.setMaximumBlockCount(self.MAX_BLOCKS)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self._buffer: List[tuple[str, str]] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(40)   # flush ~25 times/s
        self._flush_timer.timeout.connect(self._flush)
        self._flush_timer.start()

    # ── public ────────────────────────────────────────────────────────────────
    def append_line(self, text: str, kind: str = "plain"):
        self._buffer.append((text, kind))

    def clear_console(self):
        self._buffer.clear()
        self.clear()

    # ── internal ──────────────────────────────────────────────────────────────
    def _flush(self):
        if not self._buffer:
            return
        batch, self._buffer = self._buffer[:120], self._buffer[120:]
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for text, kind in batch:
            fmt = QTextCharFormat()
            colour = KIND_COLORS.get(kind, KIND_COLORS["plain"])
            fmt.setForeground(QColor(colour))
            cursor.setCharFormat(fmt)
            cursor.insertText(text + "\n")
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar option list
# ══════════════════════════════════════════════════════════════════════════════

class OptionRow:
    """One checkbox + its TaskDef."""
    def __init__(self, task: TaskDef, checkbox: QCheckBox):
        self.task     = task
        self.checkbox = checkbox


class OptionSidebar(QWidget):
    def __init__(self, tasks: List[TaskDef], parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._rows: List[OptionRow] = []
        self._groups: Dict[str, List[OptionRow]] = defaultdict(list)
        self._build(tasks)

    # ── build ─────────────────────────────────────────────────────────────────
    def _build(self, tasks: List[TaskDef]):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner_widget = QWidget()
        inner_layout = QVBoxLayout(inner_widget)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.setSpacing(6)

        # group tasks
        grouped: Dict[str, List[TaskDef]] = defaultdict(list)
        for t in tasks:
            grouped[t.group].append(t)

        for group_name, group_tasks in grouped.items():
            box = QGroupBox(group_name.upper())
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(6, 4, 6, 6)
            box_layout.setSpacing(1)

            for task in group_tasks:
                cb = QCheckBox(task.label)
                if task.tooltip:
                    cb.setToolTip(task.tooltip)
                # dim unavailable tools
                if task.need_tool and not _tool_available(task.need_tool):
                    cb.setEnabled(False)
                    cb.setToolTip(
                        (cb.toolTip() + "\n" if cb.toolTip() else "") +
                        f"⚠ '{task.need_tool}' not found in PATH"
                    )
                row = OptionRow(task, cb)
                self._rows.append(row)
                self._groups[group_name].append(row)
                box_layout.addWidget(cb)

            inner_layout.addWidget(box)

        inner_layout.addStretch()
        scroll.setWidget(inner_widget)
        outer.addWidget(scroll)

    # ── public helpers ────────────────────────────────────────────────────────
    def checked_tasks(self) -> List[TaskDef]:
        return [r.task for r in self._rows if r.checkbox.isChecked() and r.checkbox.isEnabled()]

    def checked_paths(self) -> List[Path]:
        paths = []
        for r in self._rows:
            if r.checkbox.isChecked() and r.checkbox.isEnabled():
                paths.extend(r.task.paths)
        return paths

    def select_all(self):
        for r in self._rows:
            if r.checkbox.isEnabled():
                r.checkbox.setChecked(True)

    def deselect_all(self):
        for r in self._rows:
            r.checkbox.setChecked(False)

    def select_group(self, group_name: str, state: bool):
        for r in self._groups.get(group_name, []):
            if r.checkbox.isEnabled():
                r.checkbox.setChecked(state)

    def connect_changed(self, slot):
        for r in self._rows:
            r.checkbox.stateChanged.connect(slot)

    @property
    def total_rows(self) -> int:
        return len(self._rows)

    @property
    def checked_count(self) -> int:
        return sum(1 for r in self._rows if r.checkbox.isChecked())


def _tool_available(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


# ══════════════════════════════════════════════════════════════════════════════
#  Stats bar
# ══════════════════════════════════════════════════════════════════════════════

class _Stat(QWidget):
    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(0)
        self._val = QLabel("—")
        self._val.setObjectName("statValue")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(label)
        lbl.setObjectName("statLabel")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._val)
        lay.addWidget(lbl)

    def set_value(self, v: str):
        self._val.setText(v)


class StatsBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsBar")
        self.setFixedHeight(56)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._selected = _Stat("SELECTED")
        self._estimate = _Stat("EST. SPACE")
        self._freed    = _Stat("FREED")
        self._elapsed  = _Stat("TIME")

        for stat in (self._selected, self._estimate, self._freed, self._elapsed):
            lay.addWidget(stat)
            div = QFrame()
            div.setFrameShape(QFrame.Shape.VLine)
            div.setStyleSheet("color: #21262d;")
            lay.addWidget(div)

        lay.takeAt(lay.count() - 1)   # remove trailing divider

    def set_selected(self, n: int):  self._selected.set_value(str(n))
    def set_estimate(self, n: int):  self._estimate.set_value(_bytes_human(n))
    def set_freed(self, n: int):     self._freed.set_value(_bytes_human(n))
    def set_elapsed(self, s: float): self._elapsed.set_value(f"{s:.1f}s")


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
        self.setMinimumSize(900, 600)

        self._cleanup_worker:  Optional[CleanupWorker]    = None
        self._size_worker:     Optional[FolderSizeWorker] = None
        self._total_freed:     int   = 0
        self._size_debounce:   QTimer = QTimer(self)
        self._size_debounce.setSingleShot(True)
        self._size_debounce.setInterval(300)
        self._size_debounce.timeout.connect(self._recalculate_size)

        self._build_ui()
        self._update_selected_count()

    # ══════════════════════════════════════════════════════════════════════════
    #  UI construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── top bar ───────────────────────────────────────────────────────────
        topbar = self._build_topbar()
        root_lay.addWidget(topbar)

        # ── splitter: sidebar | console ───────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # left: sidebar
        left = QWidget()
        left.setObjectName("sidebar")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(0)

        tasks = build_task_catalogue()
        self._sidebar = OptionSidebar(tasks)
        self._sidebar.connect_changed(self._on_selection_changed)
        left_lay.addWidget(self._sidebar)

        # bottom of sidebar: select row + progress + start
        ctrl = self._build_controls()
        left_lay.addWidget(ctrl)

        splitter.addWidget(left)

        # right: console
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        console_header = self._build_console_header()
        right_lay.addWidget(console_header)

        self._console = LiveConsole()
        right_lay.addWidget(self._console)

        splitter.addWidget(right)
        splitter.setSizes([380, 900])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        root_lay.addWidget(splitter, 1)

        # ── stats bar ─────────────────────────────────────────────────────────
        self._stats = StatsBar()
        root_lay.addWidget(self._stats)

        # ── welcome message ───────────────────────────────────────────────────
        self._welcome()

    # ── top bar ───────────────────────────────────────────────────────────────
    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            "background-color:#161b22; border-bottom:1px solid #21262d;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)

        title = QLabel("GARBAGE COLLECTOR")
        title.setStyleSheet(
            "color:#e6edf3; font-size:14px; font-weight:bold; letter-spacing:3px;"
        )
        lay.addWidget(title)
        lay.addStretch()

        # platform badge
        icon = PLATFORM.icon
        name = PLATFORM.distro_name or PLATFORM.display_name
        badge = QLabel(f"{icon}  {name}")
        badge.setObjectName("platformBadge")
        lay.addWidget(badge)

        if PLATFORM.os == "linux" and PLATFORM.version:
            ver = QLabel(PLATFORM.version)
            ver.setObjectName("distroLabel")
            lay.addWidget(ver)

        return bar

    # ── controls strip (bottom of sidebar) ───────────────────────────────────
    def _build_controls(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background-color:#0d1117; border-top:1px solid #21262d;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        # select row
        sel_row = QHBoxLayout()
        all_btn = QPushButton("All")
        all_btn.setObjectName("smallBtn")
        all_btn.clicked.connect(self._sidebar.select_all)
        none_btn = QPushButton("None")
        none_btn.setObjectName("smallBtn")
        none_btn.clicked.connect(self._sidebar.deselect_all)
        self._sel_label = QLabel("0 selected")
        self._sel_label.setStyleSheet("color:#484f58; font-size:10px;")
        sel_row.addWidget(all_btn)
        sel_row.addWidget(none_btn)
        sel_row.addStretch()
        sel_row.addWidget(self._sel_label)
        lay.addLayout(sel_row)

        # progress
        self._progress = QProgressBar()
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%p%")
        lay.addWidget(self._progress)

        # space label
        self._space_label = QLabel("Estimated: —")
        self._space_label.setObjectName("spaceLabel")
        lay.addWidget(self._space_label)

        # action buttons
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("▶  START CLEANUP")
        self._start_btn.setObjectName("startBtn")
        self._start_btn.clicked.connect(self._start_cleanup)

        self._cancel_btn = QPushButton("■  CANCEL")
        self._cancel_btn.setObjectName("cancelBtn")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.clicked.connect(self._cancel_cleanup)

        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._cancel_btn)
        lay.addLayout(btn_row)

        return panel

    # ── console header ────────────────────────────────────────────────────────
    def _build_console_header(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            "background-color:#161b22; border-bottom:1px solid #21262d;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 10, 0)

        lbl = QLabel("CONSOLE OUTPUT")
        lbl.setStyleSheet("color:#484f58; font-size:10px; letter-spacing:2px;")
        lay.addWidget(lbl)
        lay.addStretch()

        clr = QPushButton("CLEAR")
        clr.setObjectName("smallBtn")
        clr.clicked.connect(self._console.clear_console)
        lay.addWidget(clr)

        return bar

    # ══════════════════════════════════════════════════════════════════════════
    #  Event handlers
    # ══════════════════════════════════════════════════════════════════════════

    def _on_selection_changed(self):
        self._update_selected_count()
        self._size_debounce.start()

    def _update_selected_count(self):
        n = self._sidebar.checked_count
        self._sel_label.setText(f"{n} selected")
        self._stats.set_selected(n)
        self._start_btn.setEnabled(n > 0)

    @pyqtSlot()
    def _recalculate_size(self):
        # stop previous size worker
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
    def _on_size_result(self, total: int):
        self._space_label.setText(f"Estimated: {_bytes_human(total)}")
        self._stats.set_estimate(total)

    # ── cleanup ────────────────────────────────────────────────────────────────
    def _start_cleanup(self):
        tasks = self._sidebar.checked_tasks()
        if not tasks:
            return

        self._console.clear_console()
        self._total_freed = 0
        self._progress.setValue(0)
        self._start_btn.setEnabled(False)
        self._cancel_btn.setEnabled(True)

        n = len(tasks)
        self._console.append_line(
            f"▶ Starting cleanup — {n} task(s) selected on "
            f"{PLATFORM.display_name}\n",
            "header"
        )

        self._cleanup_worker = CleanupWorker(tasks)
        self._cleanup_worker.log_line.connect(self._on_log_line)
        self._cleanup_worker.progress.connect(self._progress.setValue)
        self._cleanup_worker.task_done.connect(self._on_task_done)
        self._cleanup_worker.all_done.connect(self._on_all_done)
        self._cleanup_worker.start()

    def _cancel_cleanup(self):
        if self._cleanup_worker:
            self._cleanup_worker.cancel()
            self._cancel_btn.setEnabled(False)

    # ── worker slots ───────────────────────────────────────────────────────────
    @pyqtSlot(str, str)
    def _on_log_line(self, text: str, kind: str):
        self._console.append_line(text, kind)

    @pyqtSlot(int, int)
    def _on_task_done(self, idx: int, freed: int):
        self._total_freed += freed
        self._stats.set_freed(self._total_freed)

    @pyqtSlot(int, float)
    def _on_all_done(self, total_freed: int, elapsed: float):
        self._stats.set_freed(total_freed)
        self._stats.set_elapsed(elapsed)
        self._start_btn.setEnabled(True)
        self._cancel_btn.setEnabled(False)
        self._recalculate_size()

    # ── welcome ────────────────────────────────────────────────────────────────
    def _welcome(self):
        p = PLATFORM
        self._console.append_line("GARBAGE COLLECTOR  —  ready", "header")
        self._console.append_line(
            f"  Platform  : {p.display_name}", "info"
        )
        if p.os == "linux":
            self._console.append_line(
                f"  Distro    : {p.distro_name}  [{p.distro_family}]", "info"
            )
            self._console.append_line(
                f"  Version   : {p.version or 'unknown'}", "info"
            )
            pkg_mgrs = [k for k in [
                "apt","dnf","yum","pacman","zypper","emerge","xbps","apk","nix","eopkg"
            ] if getattr(p, f"has_{k}", False)]
            self._console.append_line(
                f"  Pkg mgrs  : {', '.join(pkg_mgrs) or 'none detected'}", "info"
            )
        tools = [t for t in ["docker","podman","npm","pip","cargo","go","gem","gradle","maven"]
                 if getattr(p, f"has_{t}", False)]
        self._console.append_line(
            f"  Dev tools : {', '.join(tools) or 'none detected'}", "info"
        )
        self._console.append_line(
            "\n  Select tasks on the left and press  ▶ START CLEANUP\n", "plain"
        )
