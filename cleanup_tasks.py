"""
cleanup_tasks.py
All cleanup task functions.  Each takes a single argument: log (Callable[[str], None]).
Returns freed_bytes (int).

Third-party app paths are resolved dynamically via path_resolver — no hardcoded
install locations.  Registry keys are used on Windows; XDG dirs, Flatpak, Snap,
and VDF parsing are used on Linux.
"""

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from platform_detect import PLATFORM, Distro
import path_resolver as pr

Log = Callable[[str], None]
HOME = Path.home()


# ══════════════════════════════════════════════════════════════════════════════
#  Low-level helpers
# ══════════════════════════════════════════════════════════════════════════════

def _size(path: Path) -> int:
    total = 0
    try:
        if path.is_file():
            return path.stat().st_size
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += _size(Path(entry.path))
            except OSError:
                pass
    except OSError:
        pass
    return total


def _del_file(p: Path, log: Log) -> int:
    freed = 0
    try:
        freed = p.stat().st_size
        p.unlink(missing_ok=True)
        log(f"  ✓ Deleted {p}")
    except Exception as e:
        log(f"  ✗ {p}: {e}")
    return freed


def _del_dir_contents(p: Path, log: Log) -> int:
    freed = 0
    if not p.exists():
        return 0
    try:
        for child in p.iterdir():
            try:
                if child.is_file() or child.is_symlink():
                    freed += _del_file(child, log)
                elif child.is_dir():
                    freed += _size(child)
                    shutil.rmtree(child, ignore_errors=True)
                    log(f"  ✓ Removed {child}")
            except Exception as e:
                log(f"  ✗ {child}: {e}")
    except Exception as e:
        log(f"  ✗ Cannot read {p}: {e}")
    return freed


def _del_paths(paths: List[Path], log: Log) -> int:
    freed = 0
    for p in paths:
        if not p.exists():
            continue
        if p.is_file() or p.is_symlink():
            freed += _del_file(p, log)
        elif p.is_dir():
            freed += _del_dir_contents(p, log)
    if not paths:
        log("  ℹ Nothing found to clean")
    return freed


def _run(cmd: List[str], log: Log, sudo: bool = False) -> bool:
    if sudo and os.name != "nt":
        try:
            if os.geteuid() != 0:
                cmd = ["sudo", "-n"] + cmd
        except AttributeError:
            pass
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        for line in (result.stdout + result.stderr).strip().splitlines():
            if line.strip():
                log(f"  {line}")
        return result.returncode == 0
    except FileNotFoundError:
        log(f"  ✗ Command not found: {cmd[0]}")
        return False
    except subprocess.TimeoutExpired:
        log(f"  ✗ Timeout: {' '.join(cmd)}")
        return False
    except Exception as e:
        log(f"  ✗ {e}")
        return False


def _sudo_run(cmd: List[str], log: Log) -> bool:
    return _run(cmd, log, sudo=True)


# ══════════════════════════════════════════════════════════════════════════════
#  WINDOWS TASKS
# ══════════════════════════════════════════════════════════════════════════════

def win_recycle_bin(log: Log) -> int:
    try:
        import winshell
        winshell.recycle_bin().empty(confirm=False, show_progress=False, sound=False)
        log("  ✓ Recycle Bin emptied")
    except Exception as e:
        log(f"  ✗ {e}")
    return 0

def win_temp(log: Log) -> int:
    return _del_paths([Path(tempfile.gettempdir())], log)

def win_windows_temp(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows\Temp")], log)

def win_prefetch(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows\Prefetch")], log)

def win_windows_old(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows.old")], log)

def win_update_cache(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows\SoftwareDistribution\Download")], log)

def win_delivery_opt(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows\SoftwareDistribution\DeliveryOptimization")], log)

def win_installer_patch(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows\Installer\$PatchCache$")], log)

def win_crash_dumps(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(
        Path(r"C:\Windows\Minidump"),
        Path(r"C:\Windows\memory.dmp"),
        local / "CrashDumps",
    ), log)

def win_log_files(log: Log) -> int:
    log_dir = Path(r"C:\Windows\Logs")
    files = list(log_dir.glob("**/*.log")) if log_dir.exists() else []
    return _del_paths(files, log)

def win_icon_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    explorer = local / "Microsoft" / "Windows" / "Explorer"
    files = pr._glob_exist(explorer, "iconcache*.db") + pr._exist(local / "IconCache.db")
    return _del_paths(files, log)

def win_flush_dns(log: Log) -> int:
    os.system("ipconfig /flushdns >nul 2>&1")
    log("  ✓ DNS cache flushed")
    return 0

def win_clear_clipboard(log: Log) -> int:
    os.system("cmd /c echo off | clip >nul 2>&1")
    log("  ✓ Clipboard cleared")
    return 0

def win_disk_cleanup(log: Log) -> int:
    log("  ℹ Launching Windows Disk Cleanup (cleanmgr)…")
    os.system("cleanmgr /sagerun:1")
    return 0

def win_event_logs(log: Log) -> int:
    log_dir = Path(r"C:\Windows\System32\winevt\Logs")
    files = list(log_dir.glob("*.evtx")) if log_dir.exists() else []
    return _del_paths(files, log)

def win_font_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(local / "FontCache"), log)

def win_downloads(log: Log) -> int:
    return _del_paths([HOME / "Downloads"], log)

def win_recent_files(log: Log) -> int:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    return _del_paths(pr._exist(roaming / "Microsoft" / "Windows" / "Recent"), log)

def win_jump_lists(log: Log) -> int:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    base = roaming / "Microsoft" / "Windows" / "Recent"
    return _del_paths(pr._exist(base / "AutomaticDestinations", base / "CustomDestinations"), log)

def win_thumbnail_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(local / "Microsoft" / "Windows" / "Explorer"), log)

def win_search_history(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(
        local / "Microsoft" / "Windows" / "ConnectedSearch" / "RequestHistory",
        local / "Packages" / "Microsoft.Windows.Search_cw5n1h2txyewy" / "LocalState" / "ConstraintIndex",
    ), log)

def win_office_cache(log: Log) -> int:
    return _del_paths(pr.win_office_paths(), log)

def win_teams_cache(log: Log) -> int:
    return _del_paths(pr.win_teams_paths(), log)

def win_ms_store(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._glob_exist(local / "Packages", "Microsoft.WindowsStore_*/LocalCache"), log)

def win_wer_reports(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(
        Path(r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue"),
        Path(r"C:\ProgramData\Microsoft\Windows\WER\ReportArchive"),
        local / "Microsoft" / "Windows" / "WER",
    ), log)

def win_vs_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(HOME / ".vs", local / "Microsoft" / "VisualStudio"), log)

def win_vscode_cache(log: Log) -> int:
    return _del_paths(pr.win_vscode_paths(), log)

def win_onedrive_logs(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(
        local / "Microsoft" / "OneDrive" / "logs",
        local / "Microsoft" / "OneDrive" / "setup" / "logs",
    ), log)

def win_skype_cache(log: Log) -> int:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    return _del_paths(pr._exist(roaming / "Skype"), log)

def win_browser_cache(log: Log) -> int:
    return _del_paths(pr.win_browser_paths(), log)

def win_directx_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(local / "D3DSCache", local / "D3DCache", Path(r"C:\Windows\Temp\DirectX")), log)

def win_npm_cache(log: Log) -> int:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    return _del_paths(pr._exist(roaming / "npm-cache"), log)

def win_pip_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(local / "pip" / "cache"), log)

def win_nuget_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(local / "NuGet" / "Cache", HOME / ".nuget" / "packages"), log)

def win_gradle_cache(log: Log) -> int:
    return _del_paths(pr._exist(HOME / ".gradle" / "caches"), log)

def win_maven_cache(log: Log) -> int:
    return _del_paths(pr._exist(HOME / ".m2" / "repository"), log)

def win_cargo_cache(log: Log) -> int:
    cargo = Path(os.environ.get("CARGO_HOME", HOME / ".cargo"))
    return _del_paths(pr._exist(cargo / "registry"), log)

def win_go_cache(log: Log) -> int:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    return _del_paths(pr._exist(local / "go" / "pkg" / "mod" / "cache"), log)

def win_docker_cache(log: Log) -> int:
    for cmd in (["docker","builder","prune","-af"], ["docker","image","prune","-af"],
                ["docker","container","prune","-f"], ["docker","volume","prune","-f"]):
        _run(cmd, log)
    return 0

def win_yarn_cache(log: Log) -> int:
    r = subprocess.run(["yarn","cache","dir"], capture_output=True, text=True)
    return _del_paths(pr._exist(Path(r.stdout.strip())), log) if r.returncode == 0 and r.stdout.strip() else 0

def win_pnpm_cache(log: Log) -> int:
    r = subprocess.run(["pnpm","store","path"], capture_output=True, text=True)
    return _del_paths(pr._exist(Path(r.stdout.strip())), log) if r.returncode == 0 and r.stdout.strip() else 0

def win_discord_cache(log: Log) -> int:
    return _del_paths(pr.win_discord_paths(), log)

def win_spotify_cache(log: Log) -> int:
    return _del_paths(pr.win_spotify_paths(), log)

def win_steam_cache(log: Log) -> int:
    paths = pr.win_steam_paths()
    if not paths:
        log("  ℹ Steam installation not found")
    return _del_paths(paths, log)

def win_epic_cache(log: Log) -> int:
    return _del_paths(pr.win_epic_paths(), log)

def win_zoom_cache(log: Log) -> int:
    return _del_paths(pr.win_zoom_paths(), log)

def win_slack_cache(log: Log) -> int:
    return _del_paths(pr.win_slack_paths(), log)

def win_obs_cache(log: Log) -> int:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    return _del_paths(pr._exist(roaming / "obs-studio" / "logs"), log)

def win_vlc_cache(log: Log) -> int:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    return _del_paths(pr._exist(roaming / "vlc" / "art"), log)


# ══════════════════════════════════════════════════════════════════════════════
#  LINUX TASKS
# ══════════════════════════════════════════════════════════════════════════════

def lx_tmp(log: Log) -> int:
    return _del_paths([Path("/tmp")], log)

def lx_var_tmp(log: Log) -> int:
    return _del_paths([Path("/var/tmp")], log)

def lx_trash(log: Log) -> int:
    return _del_paths(pr._exist(pr.XDG_DATA / "Trash", Path("/root/.local/share/Trash")), log)

def lx_flush_dns(log: Log) -> int:
    for cmd in (
        ["systemd-resolve", "--flush-caches"],
        ["resolvectl", "flush-caches"],
        ["service", "nscd", "restart"],
        ["systemctl", "restart", "dnsmasq"],
    ):
        if shutil.which(cmd[0]):
            if _sudo_run(cmd, log):
                log(f"  ✓ DNS flushed via {cmd[0]}")
                return 0
    log("  ✗ No supported DNS resolver found")
    return 0

def lx_core_dumps(log: Log) -> int:
    paths = list(pr._exist(Path("/var/crash"), Path("/var/lib/apport/coredump")))
    paths += [f for f in HOME.glob("core*") if f.is_file()]
    return _del_paths(paths, log)

def lx_swap_clear(log: Log) -> int:
    log("  ℹ Cycling swap…")
    _sudo_run(["swapoff", "-a"], log)
    _sudo_run(["swapon",  "-a"], log)
    return 0

def lx_var_log(log: Log) -> int:
    var_log = Path("/var/log")
    files: List[Path] = []
    if var_log.exists():
        for pat in ("*.gz", "*.old", "*.1", "*.2", "*.3", "*.4", "*.xz", "*.bz2"):
            files += list(var_log.rglob(pat))
    return _del_paths(files, log)

def lx_apt_clean(log: Log) -> int:
    freed = _size(Path("/var/cache/apt/archives"))
    _sudo_run(["apt-get", "clean"], log)
    log("  ✓ APT cache cleaned")
    return freed

def lx_apt_autoclean(log: Log) -> int:
    _sudo_run(["apt-get", "autoclean"], log); return 0

def lx_apt_autoremove(log: Log) -> int:
    _sudo_run(["apt-get", "autoremove", "-y"], log); return 0

def lx_dnf_clean(log: Log) -> int:
    _sudo_run(["dnf", "clean", "all"], log); return 0

def lx_dnf_autoremove(log: Log) -> int:
    _sudo_run(["dnf", "autoremove", "-y"], log); return 0

def lx_yum_clean(log: Log) -> int:
    _sudo_run(["yum", "clean", "all"], log); return 0

def lx_pacman_clean(log: Log) -> int:
    _sudo_run(["pacman", "-Sc", "--noconfirm"], log); return 0

def lx_pacman_orphans(log: Log) -> int:
    r = subprocess.run(["pacman", "-Qdtq"], capture_output=True, text=True)
    pkgs = r.stdout.strip().split() if r.stdout.strip() else []
    if pkgs:
        _sudo_run(["pacman", "-Rns", "--noconfirm"] + pkgs, log)
        log(f"  ✓ Removed {len(pkgs)} orphan(s)")
    else:
        log("  ✓ No orphan packages found")
    return 0

def lx_paru_clean(log: Log) -> int:
    _run(["paru", "-Sc", "--noconfirm"], log); return 0

def lx_yay_clean(log: Log) -> int:
    _run(["yay", "-Sc", "--noconfirm"], log); return 0

def lx_zypper_clean(log: Log) -> int:
    _sudo_run(["zypper", "clean", "--all"], log); return 0

def lx_emerge_clean(log: Log) -> int:
    _sudo_run(["emerge", "--depclean"], log)
    _sudo_run(["eclean-dist", "-d"], log)
    return 0

def lx_xbps_clean(log: Log) -> int:
    _sudo_run(["xbps-remove", "-Oo"], log); return 0

def lx_apk_clean(log: Log) -> int:
    _sudo_run(["apk", "cache", "clean"], log); return 0

def lx_nix_collect(log: Log) -> int:
    _run(["nix-collect-garbage", "-d"], log); return 0

def lx_eopkg_clean(log: Log) -> int:
    _sudo_run(["eopkg", "delete-cache"], log); return 0

def lx_snap_clean(log: Log) -> int:
    freed = _del_paths(pr._exist(Path("/var/lib/snapd/cache")), log)
    try:
        r = subprocess.run(["snap", "list", "--all"], capture_output=True, text=True)
        removed = 0
        for line in r.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and "disabled" in parts:
                _sudo_run(["snap", "remove", parts[0], f"--revision={parts[2]}"], log)
                removed += 1
        log(f"  ✓ Removed {removed} disabled revision(s)" if removed else "  ✓ No disabled revisions")
    except Exception as e:
        log(f"  ✗ {e}")
    return freed

def lx_flatpak_unused(log: Log) -> int:
    _run(["flatpak", "uninstall", "--unused", "-y"], log); return 0

def lx_old_kernels(log: Log) -> int:
    fam = PLATFORM.distro_family
    if fam == Distro.DEBIAN:
        _sudo_run(["apt-get", "autoremove", "--purge", "-y"], log)
    elif fam == Distro.FEDORA:
        _sudo_run(["dnf", "remove", "$(dnf repoquery --installonly --latest-limit=-1 -q)", "-y"], log)
    elif fam == Distro.ARCH:
        log("  ℹ Arch: manage kernels manually via pacman -Rs linux-*")
    else:
        log(f"  ℹ Not supported for {fam}")
    return 0

def lx_home_cache(log: Log) -> int:
    return _del_paths([pr.XDG_CACHE], log)

def lx_thumbnail_cache(log: Log) -> int:
    return _del_paths(pr._exist(pr.XDG_CACHE / "thumbnails"), log)

def lx_recent_files(log: Log) -> int:
    p = pr.XDG_DATA / "recently-used.xbel"
    return _del_file(p, log) if p.exists() else 0

def lx_xsession_errors(log: Log) -> int:
    p = HOME / ".xsession-errors"
    return _del_file(p, log) if p.exists() else 0

def lx_bash_history(log: Log) -> int:
    p = HOME / ".bash_history"
    if p.exists(): p.write_text(""); log(f"  ✓ Cleared {p}")
    return 0

def lx_zsh_history(log: Log) -> int:
    p = HOME / ".zsh_history"
    if p.exists(): p.write_text(""); log(f"  ✓ Cleared {p}")
    return 0

def lx_fish_history(log: Log) -> int:
    p = pr.XDG_DATA / "fish" / "fish_history"
    if p.exists(): p.write_text(""); log(f"  ✓ Cleared {p}")
    return 0

def lx_journal_vacuum_time(log: Log) -> int:
    _sudo_run(["journalctl", "--vacuum-time=7d"], log); return 0

def lx_journal_vacuum_size(log: Log) -> int:
    _sudo_run(["journalctl", "--vacuum-size=100M"], log); return 0

def lx_browser_cache(log: Log) -> int:
    return _del_paths(pr.lx_browser_paths(), log)

def lx_pip_cache(log: Log) -> int:
    return _del_paths(pr._exist(pr.XDG_CACHE / "pip"), log)

def lx_npm_cache(log: Log) -> int:
    r = subprocess.run(["npm", "config", "get", "cache"], capture_output=True, text=True)
    p = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else HOME / ".npm"
    return _del_paths(pr._exist(p), log)

def lx_yarn_cache(log: Log) -> int:
    r = subprocess.run(["yarn", "cache", "dir"], capture_output=True, text=True)
    p = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else pr.XDG_CACHE / "yarn"
    return _del_paths(pr._exist(p), log)

def lx_pnpm_cache(log: Log) -> int:
    r = subprocess.run(["pnpm", "store", "path"], capture_output=True, text=True)
    p = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else HOME / ".local/share/pnpm/store"
    return _del_paths(pr._exist(p), log)

def lx_cargo_cache(log: Log) -> int:
    cargo = Path(os.environ.get("CARGO_HOME", HOME / ".cargo"))
    return _del_paths(pr._exist(cargo / "registry"), log)

def lx_go_cache(log: Log) -> int:
    gocache = Path(os.environ.get("GOCACHE", pr.XDG_CACHE / "go" / "build"))
    gopath  = Path(os.environ.get("GOPATH",  HOME / "go"))
    return _del_paths(pr._exist(gocache, gopath / "pkg" / "mod" / "cache"), log)

def lx_gradle_cache(log: Log) -> int:
    gradle = Path(os.environ.get("GRADLE_USER_HOME", HOME / ".gradle"))
    return _del_paths(pr._exist(gradle / "caches"), log)

def lx_maven_cache(log: Log) -> int:
    return _del_paths(pr._exist(HOME / ".m2" / "repository"), log)

def lx_gem_cache(log: Log) -> int:
    return _del_paths(pr._exist(HOME / ".gem"), log)

def lx_composer_cache(log: Log) -> int:
    return _del_paths(pr._exist(pr.XDG_CACHE / "composer"), log)

def lx_docker_cache(log: Log) -> int:
    for cmd in (["docker","builder","prune","-af"], ["docker","image","prune","-af"],
                ["docker","container","prune","-f"], ["docker","volume","prune","-f"]):
        _run(cmd, log)
    return 0

def lx_podman_cache(log: Log) -> int:
    _run(["podman", "system", "prune", "-af"], log); return 0

def lx_vscode_cache(log: Log) -> int:
    return _del_paths(pr.lx_vscode_paths(), log)

def lx_python_cache(log: Log) -> int:
    freed = 0
    try:
        for d in HOME.rglob("__pycache__"):
            freed += _size(d)
            shutil.rmtree(d, ignore_errors=True)
            log(f"  ✓ Removed {d}")
    except Exception as e:
        log(f"  ✗ {e}")
    return freed

def lx_discord_cache(log: Log) -> int:
    return _del_paths(pr.lx_discord_paths(), log)

def lx_spotify_cache(log: Log) -> int:
    return _del_paths(pr.lx_spotify_paths(), log)

def lx_steam_cache(log: Log) -> int:
    paths = pr.lx_steam_paths()
    if not paths: log("  ℹ Steam not found")
    return _del_paths(paths, log)

def lx_zoom_cache(log: Log) -> int:
    return _del_paths(pr.lx_zoom_paths(), log)

def lx_slack_cache(log: Log) -> int:
    return _del_paths(pr.lx_slack_paths(), log)

def lx_obs_cache(log: Log) -> int:
    return _del_paths(pr.lx_obs_paths(), log)

def lx_vlc_cache(log: Log) -> int:
    return _del_paths(pr.lx_vlc_paths(), log)

def lx_wine_temp(log: Log) -> int:
    return _del_paths(pr.lx_wine_temp_paths(), log)

def lx_lutris_cache(log: Log) -> int:
    return _del_paths(pr.lx_lutris_paths(), log)

def lx_heroic_cache(log: Log) -> int:
    return _del_paths(pr.lx_heroic_paths(), log)


# ══════════════════════════════════════════════════════════════════════════════
#  TASK CATALOGUE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TaskDef:
    label:     str
    func:      Callable
    paths:     List[Path]
    group:     str
    tooltip:   str           = ""
    need_root: bool          = False
    need_tool: Optional[str] = None


def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


def build_task_catalogue() -> List[TaskDef]:
    p = PLATFORM
    tasks: List[TaskDef] = []

    def add(label, func, paths, group, tooltip="", need_root=False, need_tool=None):
        tasks.append(TaskDef(label, func, list(paths), group, tooltip, need_root, need_tool))

    if p.os == "windows":
        local   = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
        roaming = Path(os.environ.get("APPDATA",      HOME / "AppData/Roaming"))

        add("Empty Recycle Bin",            win_recycle_bin,    [], "System")
        add("Clear User Temp Files",        win_temp,           [Path(tempfile.gettempdir())], "System", r"%TEMP%")
        add("Clear Windows Temp",           win_windows_temp,   [Path(r"C:\Windows\Temp")], "System")
        add("Clear Prefetch Files",         win_prefetch,       [Path(r"C:\Windows\Prefetch")], "System")
        add("Clear Windows.old",            win_windows_old,    [Path(r"C:\Windows.old")], "System", "Previous Windows installation")
        add("Clear Windows Update Cache",   win_update_cache,   [Path(r"C:\Windows\SoftwareDistribution\Download")], "System")
        add("Clear Delivery Optimization",  win_delivery_opt,   [Path(r"C:\Windows\SoftwareDistribution\DeliveryOptimization")], "System")
        add("Clear Installer Patch Cache",  win_installer_patch,[Path(r"C:\Windows\Installer\$PatchCache$")], "System")
        add("Clear Crash Dumps",            win_crash_dumps,    [Path(r"C:\Windows\Minidump")], "System")
        add("Clear Windows Log Files",      win_log_files,      [Path(r"C:\Windows\Logs")], "System")
        add("Clear Icon Cache",             win_icon_cache,     [local / "IconCache.db"], "System", "Rebuilt on next login")
        add("Clear Event Viewer Logs",      win_event_logs,     [], "System", ".evtx files")
        add("Flush DNS Cache",              win_flush_dns,      [], "System", "ipconfig /flushdns")
        add("Clear Clipboard",              win_clear_clipboard,[], "System")
        add("Run Disk Cleanup (cleanmgr)",  win_disk_cleanup,   [], "System", "Launches Windows built-in Disk Cleanup")
        add("Clear Font Cache",             win_font_cache,     [local / "FontCache"], "System")

        add("Clear Downloads Folder",       win_downloads,      [HOME / "Downloads"], "User & Shell", "⚠ Deletes ALL files in Downloads")
        add("Clear Recent Files List",      win_recent_files,   [], "User & Shell")
        add("Clear Jump Lists",             win_jump_lists,     [], "User & Shell")
        add("Clear Thumbnail Cache",        win_thumbnail_cache,[], "User & Shell")
        add("Clear Search History",         win_search_history, [], "User & Shell")

        add("Clear Office Cache",           win_office_cache,   pr.win_office_paths(), "Microsoft Apps")
        add("Clear Teams Cache",            win_teams_cache,    pr.win_teams_paths(),  "Microsoft Apps", "Classic + new Teams")
        add("Clear Microsoft Store Cache",  win_ms_store,       [], "Microsoft Apps")
        add("Clear WER Reports",            win_wer_reports,    [], "Microsoft Apps", "Windows Error Reporting dumps")
        add("Clear Visual Studio Cache",    win_vs_cache,       [], "Microsoft Apps")
        add("Clear VS Code Cache",          win_vscode_cache,   pr.win_vscode_paths(), "Microsoft Apps")
        add("Clear OneDrive Logs",          win_onedrive_logs,  [], "Microsoft Apps")
        add("Clear Skype Cache",            win_skype_cache,    [], "Microsoft Apps")

        add("Clear All Browser Caches",     win_browser_cache,  pr.win_browser_paths(), "Browsers",
            "Edge, Chrome, Brave, Opera, Opera GX, Vivaldi, Thorium, Firefox\nReads Firefox profiles.ini")

        add("Clear npm Cache",      win_npm_cache,    [], "Developer", need_tool="npm")
        add("Clear pip Cache",      win_pip_cache,    [], "Developer", need_tool="pip")
        add("Clear NuGet Cache",    win_nuget_cache,  [], "Developer")
        add("Clear Gradle Cache",   win_gradle_cache, [], "Developer")
        add("Clear Maven Cache",    win_maven_cache,  [], "Developer")
        add("Clear Cargo Registry", win_cargo_cache,  [], "Developer", "Respects $CARGO_HOME", need_tool="cargo")
        add("Clear Go Module Cache",win_go_cache,     [], "Developer", need_tool="go")
        add("Clear Yarn Cache",     win_yarn_cache,   [], "Developer", "Queries: yarn cache dir", need_tool="yarn")
        add("Clear pnpm Store",     win_pnpm_cache,   [], "Developer", "Queries: pnpm store path", need_tool="pnpm")
        add("Clear Docker Cache",   win_docker_cache, [], "Developer", "Builder + images + containers + volumes", need_tool="docker")
        add("Clear DirectX Cache",  win_directx_cache,[], "Developer")

        add("Clear Discord Cache",   win_discord_cache, pr.win_discord_paths(), "Third-party Apps", "Registry + AppData")
        add("Clear Spotify Cache",   win_spotify_cache, pr.win_spotify_paths(), "Third-party Apps", "Registry + AppData")
        add("Clear Steam Cache",     win_steam_cache,   pr.win_steam_paths(),   "Third-party Apps", "Registry + libraryfolders.vdf (all drives)")
        add("Clear Epic Games Cache",win_epic_cache,    pr.win_epic_paths(),    "Third-party Apps", "Registry + AppData")
        add("Clear Zoom Logs",       win_zoom_cache,    pr.win_zoom_paths(),    "Third-party Apps", "Registry + AppData")
        add("Clear Slack Cache",     win_slack_cache,   pr.win_slack_paths(),   "Third-party Apps", "Registry + AppData")
        add("Clear OBS Logs",        win_obs_cache,     [], "Third-party Apps")
        add("Clear VLC Art Cache",   win_vlc_cache,     [], "Third-party Apps")

    elif p.os == "linux":
        add("Clear /tmp",               lx_tmp,         [Path("/tmp")],     "System", need_root=True)
        add("Clear /var/tmp",           lx_var_tmp,     [Path("/var/tmp")], "System", need_root=True)
        add("Empty Trash",              lx_trash,       [pr.XDG_DATA / "Trash"], "System")
        add("Flush DNS Cache",          lx_flush_dns,   [], "System", "systemd-resolve / resolvectl / nscd / dnsmasq", need_root=True)
        add("Clear Core Dumps",         lx_core_dumps,  [], "System", need_root=True)
        add("Clear Swap",               lx_swap_clear,  [], "System", "swapoff -a && swapon -a", need_root=True)
        add("Clear /var/log Rotated",   lx_var_log,     [], "System", "*.gz *.old *.1 *.2 compressed rotated logs", need_root=True)

        if p.has_apt:
            add("APT Clean Cache",          lx_apt_clean,     [Path("/var/cache/apt/archives")], "Package Managers", need_root=True)
            add("APT Autoclean",            lx_apt_autoclean, [], "Package Managers", need_root=True)
            add("APT Autoremove",           lx_apt_autoremove,[], "Package Managers", need_root=True)
            add("Remove Old Kernels",       lx_old_kernels,   [], "Package Managers", "apt autoremove --purge", need_root=True)
        if p.has_dnf:
            add("DNF Clean All",            lx_dnf_clean,     [], "Package Managers", need_root=True)
            add("DNF Autoremove",           lx_dnf_autoremove,[], "Package Managers", need_root=True)
        if p.has_yum:
            add("YUM Clean All",            lx_yum_clean,     [], "Package Managers", need_root=True)
        if p.has_pacman:
            add("Pacman Clean Cache",       lx_pacman_clean,  [], "Package Managers", need_root=True)
            add("Remove Orphan Packages",   lx_pacman_orphans,[], "Package Managers", "pacman -Qdtq | pacman -Rns", need_root=True)
        if _has("paru"):
            add("Paru Clean Cache",         lx_paru_clean,    [], "Package Managers", need_tool="paru")
        if _has("yay"):
            add("Yay Clean Cache",          lx_yay_clean,     [], "Package Managers", need_tool="yay")
        if p.has_zypper:
            add("Zypper Clean All",         lx_zypper_clean,  [], "Package Managers", need_root=True)
        if p.has_emerge:
            add("Emerge Depclean",          lx_emerge_clean,  [], "Package Managers", need_root=True)
        if p.has_xbps:
            add("XBPS Remove Orphans",      lx_xbps_clean,    [], "Package Managers", need_root=True)
        if p.has_apk:
            add("APK Cache Clean",          lx_apk_clean,     [], "Package Managers", need_root=True)
        if p.has_nix:
            add("Nix Garbage Collect",      lx_nix_collect,   [], "Package Managers")
        if p.has_eopkg:
            add("eopkg Delete Cache",       lx_eopkg_clean,   [], "Package Managers", need_root=True)
        if p.has_snap:
            add("Clean Snap Cache & Old Revisions", lx_snap_clean, [Path("/var/lib/snapd/cache")], "Package Managers", need_root=True)
        if p.has_flatpak:
            add("Remove Unused Flatpak Runtimes", lx_flatpak_unused, [], "Package Managers")

        add("Clear ~/.cache (all)",         lx_home_cache,    [pr.XDG_CACHE], "User Cache", "⚠ Clears entire XDG user cache")
        add("Clear Thumbnail Cache",        lx_thumbnail_cache,[pr.XDG_CACHE / "thumbnails"], "User Cache")
        add("Clear Recent Files",           lx_recent_files,  [], "User Cache", "recently-used.xbel")
        add("Clear .xsession-errors",       lx_xsession_errors,[],"User Cache")
        add("Clear Bash History",           lx_bash_history,  [], "User Cache")
        add("Clear Zsh History",            lx_zsh_history,   [], "User Cache")
        add("Clear Fish History",           lx_fish_history,  [], "User Cache")

        add("Vacuum Journal (keep 7 days)", lx_journal_vacuum_time, [], "Logs", need_root=True)
        add("Vacuum Journal (keep 100 MB)", lx_journal_vacuum_size, [], "Logs", need_root=True)

        add("Clear All Browser Caches",     lx_browser_cache, pr.lx_browser_paths(), "Browsers",
            "Chrome/Chromium/Brave/Opera/Vivaldi/Edge/Firefox/Epiphany\nNative + Flatpak + Snap; reads profiles.ini")

        add("Clear pip Cache",          lx_pip_cache,    [pr.XDG_CACHE / "pip"],   "Developer", need_tool="pip")
        add("Clear npm Cache",          lx_npm_cache,    [],                        "Developer", "Respects npm config cache", need_tool="npm")
        add("Clear Yarn Cache",         lx_yarn_cache,   [],                        "Developer", "Queries yarn cache dir", need_tool="yarn")
        add("Clear pnpm Store",         lx_pnpm_cache,   [],                        "Developer", "Queries pnpm store path", need_tool="pnpm")
        add("Clear Cargo Registry",     lx_cargo_cache,  [],                        "Developer", "Respects $CARGO_HOME", need_tool="cargo")
        add("Clear Go Module Cache",    lx_go_cache,     [],                        "Developer", "Respects $GOCACHE / $GOPATH", need_tool="go")
        add("Clear Gradle Cache",       lx_gradle_cache, [],                        "Developer", "Respects $GRADLE_USER_HOME")
        add("Clear Maven Cache",        lx_maven_cache,  [],                        "Developer")
        add("Clear Ruby Gems Cache",    lx_gem_cache,    [],                        "Developer", need_tool="gem")
        add("Clear Composer Cache",     lx_composer_cache,[],                       "Developer", need_tool="composer")
        add("Clear Docker Cache",       lx_docker_cache, [],                        "Developer", "Builder + images + containers + volumes", need_tool="docker")
        add("Clear Podman Cache",       lx_podman_cache, [],                        "Developer", need_tool="podman")
        add("Clear VS Code Cache",      lx_vscode_cache, pr.lx_vscode_paths(),     "Developer", "Native + Flatpak + Insiders + VSCodium")
        add("Clear Python __pycache__", lx_python_cache, [],                        "Developer", "Recursively removes all __pycache__ under ~")

        add("Clear Discord Cache",  lx_discord_cache, pr.lx_discord_paths(), "Third-party Apps", "Native + Flatpak + Snap")
        add("Clear Spotify Cache",  lx_spotify_cache, pr.lx_spotify_paths(), "Third-party Apps", "Native + Flatpak + Snap")
        add("Clear Steam Cache",    lx_steam_cache,   pr.lx_steam_paths(),   "Third-party Apps", "libraryfolders.vdf (all drives) + Flatpak")
        add("Clear Zoom Logs",      lx_zoom_cache,    pr.lx_zoom_paths(),    "Third-party Apps", "Native + Flatpak")
        add("Clear Slack Cache",    lx_slack_cache,   pr.lx_slack_paths(),   "Third-party Apps", "Native + Flatpak + Snap")
        add("Clear OBS Logs",       lx_obs_cache,     pr.lx_obs_paths(),     "Third-party Apps", "Native + Flatpak")
        add("Clear VLC Cache",      lx_vlc_cache,     pr.lx_vlc_paths(),     "Third-party Apps")
        add("Clear Wine Temp",      lx_wine_temp,     pr.lx_wine_temp_paths(),"Third-party Apps", "$WINEPREFIX + ~/.wine + common prefix dirs")
        add("Clear Lutris Cache",   lx_lutris_cache,  pr.lx_lutris_paths(),  "Third-party Apps", "Native + Flatpak")
        add("Clear Heroic Logs",    lx_heroic_cache,  pr.lx_heroic_paths(),  "Third-party Apps", "Native + Flatpak")

    return tasks
