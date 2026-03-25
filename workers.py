"""
workers.py
QThread workers:
  - FolderSizeWorker  : async disk-size calculation
  - CleanupWorker     : runs tasks sequentially, emits live log lines + progress
"""

import os
from pathlib import Path
from time import sleep, perf_counter
from typing import List, Tuple, Callable

from PyQt6.QtCore import QThread, pyqtSignal

from cleanup_tasks import TaskDef


# ══════════════════════════════════════════════════════════════════════════════
#  Folder size worker
# ══════════════════════════════════════════════════════════════════════════════

class FolderSizeWorker(QThread):
    """Calculates total disk size of a list of paths asynchronously."""
    result = pyqtSignal(int)      # total bytes
    error  = pyqtSignal(str)

    def __init__(self, paths: List[Path], parent=None):
        super().__init__(parent)
        self._paths   = paths
        self._running = True

    def run(self):
        try:
            total = sum(self._get_size(p) for p in self._paths)
            if self._running:
                self.result.emit(total)
        except Exception as e:
            self.error.emit(str(e))

    def _get_size(self, path: Path) -> int:
        total = 0
        try:
            if path.is_file():
                return path.stat().st_size
            for entry in os.scandir(path):
                if not self._running:
                    return total
                try:
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                    elif entry.is_dir(follow_symlinks=False):
                        total += self._get_size(Path(entry.path))
                except OSError:
                    pass
        except OSError:
            pass
        return total

    def stop(self):
        self._running = False


# ══════════════════════════════════════════════════════════════════════════════
#  Cleanup worker
# ══════════════════════════════════════════════════════════════════════════════

# Log-line kinds — used by the UI to colour lines differently
KIND_HEADER  = "header"    # task name banner
KIND_OK      = "ok"        # ✓ lines
KIND_ERROR   = "error"     # ✗ lines
KIND_INFO    = "info"      # ℹ lines
KIND_PLAIN   = "plain"     # everything else
KIND_SUMMARY = "summary"   # final summary line


def _classify(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("✓") or stripped.startswith("✓"):
        return KIND_OK
    if stripped.startswith("✗"):
        return KIND_ERROR
    if stripped.startswith("ℹ"):
        return KIND_INFO
    if stripped.startswith("━━") or stripped.startswith("▶"):
        return KIND_HEADER
    if stripped.startswith("✅") or stripped.startswith("🧹"):
        return KIND_SUMMARY
    return KIND_PLAIN


class CleanupWorker(QThread):
    """
    Runs cleanup tasks one-by-one in a background thread.

    Signals
    -------
    log_line(str, str)   : (text, kind)  — emit a single console line
    task_started(int)    : index of task that just started (0-based)
    task_done(int, int)  : (task_index, freed_bytes)
    progress(int)        : 0-100
    all_done(int, float) : (total_freed_bytes, elapsed_seconds)
    """

    log_line    = pyqtSignal(str, str)
    task_started= pyqtSignal(int)
    task_done   = pyqtSignal(int, int)
    progress    = pyqtSignal(int)
    all_done    = pyqtSignal(int, float)

    def __init__(self, tasks: List[TaskDef], parent=None):
        super().__init__(parent)
        self._tasks   = tasks
        self._running = True

    # ── helpers ───────────────────────────────────────────────────────────────
    def _emit(self, text: str):
        kind = _classify(text)
        self.log_line.emit(text, kind)

    def _log(self, text: str):
        """Passed as the log callback into each task function."""
        self._emit(text)

    # ── main loop ─────────────────────────────────────────────────────────────
    def run(self):
        total_tasks  = len(self._tasks)
        total_freed  = 0
        t_start      = perf_counter()

        for idx, task in enumerate(self._tasks):
            if not self._running:
                self._emit("⚠ Cleanup cancelled by user.")
                break

            self.task_started.emit(idx)

            # header banner
            bar = "━" * max(0, 54 - len(task.label))
            self._emit(f"▶ [{idx + 1}/{total_tasks}]  {task.label}  {bar}")

            t0 = perf_counter()
            freed = 0
            try:
                freed = task.func(self._log) or 0
            except Exception as e:
                self._emit(f"  ✗ Unhandled error: {e}")

            elapsed = perf_counter() - t0
            freed_str = _bytes_human(freed) if freed else "—"
            self._emit(
                f"  ↳ done in {elapsed:.2f}s  freed {freed_str}\n"
            )

            total_freed += freed
            self.task_done.emit(idx, freed)
            self.progress.emit(int((idx + 1) / total_tasks * 100))

        elapsed_total = perf_counter() - t_start
        self._emit(
            f"🧹 All done — {total_tasks} task(s) in {elapsed_total:.1f}s  "
            f"| Total freed: {_bytes_human(total_freed)}"
        )
        self.all_done.emit(total_freed, elapsed_total)

    def cancel(self):
        self._running = False


# ── utility ───────────────────────────────────────────────────────────────────
def _bytes_human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
