"""
cleanup_tasks.py
All cleanup task functions.  Each takes a single argument: log (Callable[[str], None]).
Returns (freed_bytes: int) where calculable, else 0.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List

from platform_detect import PLATFORM, Distro

Log = Callable[[str], None]


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
    """Delete children of a directory without removing the dir itself."""
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
    return freed


def _run(cmd: List[str], log: Log, sudo: bool = False) -> bool:
    if sudo and os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120
        )
        if result.stdout.strip():
            for line in result.stdout.strip().splitlines():
                log(f"  {line}")
        if result.returncode != 0 and result.stderr.strip():
            log(f"  ✗ {result.stderr.strip()[:200]}")
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


HOME = Path.home()


# ══════════════════════════════════════════════════════════════════════════════
#  WINDOWS TASKS
# ══════════════════════════════════════════════════════════════════════════════

# ── System ────────────────────────────────────────────────────────────────────
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
    p = Path(r"C:\Windows\SoftwareDistribution\Download")
    return _del_paths([p], log)


def win_delivery_opt(log: Log) -> int:
    p = Path(r"C:\Windows\SoftwareDistribution\DeliveryOptimization")
    return _del_paths([p], log)


def win_installer_patch(log: Log) -> int:
    return _del_paths([Path(r"C:\Windows\Installer\$PatchCache$")], log)


def win_crash_dumps(log: Log) -> int:
    paths = [
        Path(r"C:\Windows\Minidump"),
        Path(r"C:\Windows\memory.dmp"),
        HOME / "AppData/Local/CrashDumps",
    ]
    return _del_paths(paths, log)


def win_log_files(log: Log) -> int:
    log_dir = Path(r"C:\Windows\Logs")
    files = list(log_dir.glob("**/*.log")) if log_dir.exists() else []
    return _del_paths(files, log)


def win_icon_cache(log: Log) -> int:
    paths = [
        HOME / "AppData/Local/IconCache.db",
        HOME / "AppData/Local/Microsoft/Windows/Explorer/iconcache*.db",
    ]
    real: List[Path] = []
    for p in paths:
        real += list(p.parent.glob(p.name)) if "*" in str(p.name) else [p]
    return _del_paths(real, log)


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
    return _del_paths([HOME / "AppData/Local/FontCache"], log)


# ── User / Shell ───────────────────────────────────────────────────────────────
def win_downloads(log: Log) -> int:
    return _del_paths([HOME / "Downloads"], log)


def win_recent_files(log: Log) -> int:
    return _del_paths([HOME / "AppData/Roaming/Microsoft/Windows/Recent"], log)


def win_search_history(log: Log) -> int:
    return _del_paths([HOME / "AppData/Roaming/Microsoft/Windows/Recent/AutomaticDestinations"], log)


def win_jump_lists(log: Log) -> int:
    paths = [
        HOME / "AppData/Roaming/Microsoft/Windows/Recent/AutomaticDestinations",
        HOME / "AppData/Roaming/Microsoft/Windows/Recent/CustomDestinations",
    ]
    return _del_paths(paths, log)


def win_thumbnail_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Local/Microsoft/Windows/Explorer"], log)


def win_explorer_db(log: Log) -> int:
    base = HOME / "AppData/Local/Microsoft/Windows/Explorer"
    files = list(base.glob("*.db")) if base.exists() else []
    return _del_paths(files, log)


# ── Microsoft Apps ─────────────────────────────────────────────────────────────
def win_office_cache(log: Log) -> int:
    paths = [
        HOME / f"AppData/Local/Microsoft/Office/{v}/OfficeFileCache"
        for v in ["15.0", "16.0", "17.0"]
    ]
    return _del_paths(paths, log)


def win_teams_cache(log: Log) -> int:
    paths = [
        HOME / "AppData/Roaming/Microsoft/Teams/Cache",
        HOME / "AppData/Roaming/Microsoft/Teams/blob_storage",
        HOME / "AppData/Roaming/Microsoft/Teams/databases",
        HOME / "AppData/Roaming/Microsoft/Teams/GPUCache",
        HOME / "AppData/Roaming/Microsoft/Teams/IndexedDB",
        HOME / "AppData/Roaming/Microsoft/Teams/Local Storage",
        HOME / "AppData/Roaming/Microsoft/Teams/tmp",
        HOME / "AppData/Local/Microsoft/Teams/Cache",
    ]
    return _del_paths(paths, log)


def win_ms_store(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Local/Packages/Microsoft.WindowsStore_8wekyb3d8bbwe/LocalCache"
    ], log)


def win_wer_reports(log: Log) -> int:
    return _del_paths([
        Path(r"C:\ProgramData\Microsoft\Windows\WER\ReportQueue"),
        Path(r"C:\ProgramData\Microsoft\Windows\WER\ReportArchive"),
        HOME / "AppData/Local/Microsoft/Windows/WER",
    ], log)


def win_vs_cache(log: Log) -> int:
    return _del_paths([
        HOME / ".vs",
        HOME / "AppData/Local/Microsoft/VisualStudio",
        HOME / "AppData/Local/Temp/VSFeedbackIntelliCodeLogs",
    ], log)


def win_vscode_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Roaming/Code/Cache",
        HOME / "AppData/Roaming/Code/CachedData",
        HOME / "AppData/Roaming/Code/Code Cache",
        HOME / "AppData/Roaming/Code/logs",
    ], log)


def win_onedrive_temp(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Local/Microsoft/OneDrive/logs",
        HOME / "AppData/Local/Microsoft/OneDrive/setup/logs",
    ], log)


def win_skype_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Roaming/Skype"], log)


# ── Browsers ───────────────────────────────────────────────────────────────────
def win_browser_cache(log: Log) -> int:
    profiles = ["Default"] + [f"Profile {i}" for i in range(1, 6)]
    paths: List[Path] = []
    browsers = {
        "Edge":    HOME / "AppData/Local/Microsoft/Edge/User Data",
        "Chrome":  HOME / "AppData/Local/Google/Chrome/User Data",
        "Brave":   HOME / "AppData/Local/BraveSoftware/Brave-Browser/User Data",
        "Opera":   HOME / "AppData/Local/Opera Software/Opera Stable",
        "Vivaldi": HOME / "AppData/Local/Vivaldi/User Data",
    }
    for name, base in browsers.items():
        if base.exists():
            for profile in profiles:
                for sub in ["Cache", "Code Cache", "GPUCache"]:
                    p = base / profile / sub
                    if p.exists():
                        paths.append(p)
    # Firefox
    ff = HOME / "AppData/Local/Mozilla/Firefox/Profiles"
    if ff.exists():
        for prof in ff.iterdir():
            c2 = prof / "cache2"
            if c2.exists():
                paths.append(c2)
    return _del_paths(paths, log)


def win_browser_logs(log: Log) -> int:
    paths: List[Path] = []
    for base in [
        HOME / "AppData/Local/Google/Chrome/User Data",
        HOME / "AppData/Local/Microsoft/Edge/User Data",
    ]:
        if base.exists():
            paths += list(base.glob("*.log"))
    return _del_paths(paths, log)


# ── Developer Tools ────────────────────────────────────────────────────────────
def win_directx_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Local/D3DSCache",
        HOME / "AppData/Local/D3DCache",
        Path(r"C:\Windows\Temp\DirectX"),
    ], log)


def win_npm_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Roaming/npm-cache"], log)


def win_pip_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Local/pip/cache"], log)


def win_nuget_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Local/NuGet/Cache",
        HOME / ".nuget/packages",
    ], log)


def win_gradle_cache(log: Log) -> int:
    return _del_paths([HOME / ".gradle/caches"], log)


def win_maven_cache(log: Log) -> int:
    return _del_paths([HOME / ".m2/repository"], log)


def win_cargo_cache(log: Log) -> int:
    return _del_paths([HOME / ".cargo/registry"], log)


def win_go_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Local/go/pkg/mod/cache"], log)


def win_docker_cache(log: Log) -> int:
    _run(["docker", "builder", "prune", "-af"], log)
    _run(["docker", "image", "prune", "-af"], log)
    return 0


def win_yarn_cache(log: Log) -> int:
    result = subprocess.run(["yarn", "cache", "dir"], capture_output=True, text=True)
    if result.returncode == 0:
        return _del_paths([Path(result.stdout.strip())], log)
    return 0


def win_pnpm_cache(log: Log) -> int:
    result = subprocess.run(["pnpm", "store", "path"], capture_output=True, text=True)
    if result.returncode == 0:
        return _del_paths([Path(result.stdout.strip())], log)
    return 0


# ── Third-party ────────────────────────────────────────────────────────────────
def win_discord_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Roaming/discord/Cache",
        HOME / "AppData/Roaming/discord/Code Cache",
        HOME / "AppData/Roaming/discord/GPUCache",
        HOME / "AppData/Local/Discord",
    ], log)


def win_spotify_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Local/Spotify/Storage",
        HOME / "AppData/Local/Spotify/Browser/Cache",
    ], log)


def win_steam_cache(log: Log) -> int:
    return _del_paths([
        Path(r"C:\Program Files (x86)\Steam\steamapps\downloading"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\temp"),
        Path(r"C:\Program Files (x86)\Steam\logs"),
    ], log)


def win_epic_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Local/EpicGamesLauncher/Saved/Logs",
        HOME / "AppData/Local/EpicGamesLauncher/Saved/webcache",
    ], log)


def win_zoom_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Roaming/Zoom/logs",
        HOME / "AppData/Roaming/Zoom/data",
    ], log)


def win_slack_cache(log: Log) -> int:
    return _del_paths([
        HOME / "AppData/Roaming/Slack/Cache",
        HOME / "AppData/Roaming/Slack/Code Cache",
        HOME / "AppData/Roaming/Slack/logs",
    ], log)


def win_obs_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Roaming/obs-studio/logs"], log)


def win_vlc_cache(log: Log) -> int:
    return _del_paths([HOME / "AppData/Roaming/vlc/art/artistalbum"], log)


# ══════════════════════════════════════════════════════════════════════════════
#  LINUX TASKS
# ══════════════════════════════════════════════════════════════════════════════

def _sudo_run(cmd: List[str], log: Log) -> bool:
    return _run(cmd, log, sudo=True)


# ── System ────────────────────────────────────────────────────────────────────
def lx_tmp(log: Log) -> int:
    return _del_paths([Path("/tmp")], log)


def lx_var_tmp(log: Log) -> int:
    return _del_paths([Path("/var/tmp")], log)


def lx_trash(log: Log) -> int:
    paths = [
        HOME / ".local/share/Trash",
        Path("/root/.local/share/Trash"),
    ]
    return _del_paths(paths, log)


def lx_flush_dns(log: Log) -> int:
    if _sudo_run(["systemd-resolve", "--flush-caches"], log):
        log("  ✓ DNS flushed (systemd-resolved)")
    elif _sudo_run(["service", "nscd", "restart"], log):
        log("  ✓ DNS flushed (nscd)")
    elif _sudo_run(["systemctl", "restart", "dnsmasq"], log):
        log("  ✓ DNS flushed (dnsmasq)")
    else:
        log("  ✗ No supported DNS resolver found")
    return 0


def lx_core_dumps(log: Log) -> int:
    paths: List[Path] = []
    for d in [Path("/var/crash"), Path("/var/lib/apport/coredump")]:
        if d.exists():
            paths.append(d)
    # user cores
    for core in HOME.glob("core"):
        paths.append(core)
    return _del_paths(paths, log)


def lx_swap_clear(log: Log) -> int:
    log("  ℹ Cycling swap (requires root)…")
    _sudo_run(["swapoff", "-a"], log)
    _sudo_run(["swapon", "-a"], log)
    return 0


def lx_var_log(log: Log) -> int:
    """Remove rotated/compressed logs in /var/log."""
    paths: List[Path] = []
    var_log = Path("/var/log")
    if var_log.exists():
        for pat in ["*.gz", "*.old", "*.1", "*.2", "*.3", "*.4"]:
            paths += list(var_log.rglob(pat))
    return _del_paths(paths, log)


# ── Package managers ───────────────────────────────────────────────────────────
def lx_apt_clean(log: Log) -> int:
    size = _size(Path("/var/cache/apt/archives"))
    _sudo_run(["apt-get", "clean"], log)
    log("  ✓ APT cache cleaned")
    return size


def lx_apt_autoclean(log: Log) -> int:
    _sudo_run(["apt-get", "autoclean"], log)
    return 0


def lx_apt_autoremove(log: Log) -> int:
    _sudo_run(["apt-get", "autoremove", "-y"], log)
    return 0


def lx_dnf_clean(log: Log) -> int:
    _sudo_run(["dnf", "clean", "all"], log)
    return 0


def lx_dnf_autoremove(log: Log) -> int:
    _sudo_run(["dnf", "autoremove", "-y"], log)
    return 0


def lx_yum_clean(log: Log) -> int:
    _sudo_run(["yum", "clean", "all"], log)
    return 0


def lx_pacman_clean(log: Log) -> int:
    _sudo_run(["pacman", "-Sc", "--noconfirm"], log)
    return 0


def lx_pacman_orphans(log: Log) -> int:
    result = subprocess.run(
        ["pacman", "-Qdtq"], capture_output=True, text=True
    )
    if result.stdout.strip():
        pkgs = result.stdout.strip().split()
        _sudo_run(["pacman", "-Rns", "--noconfirm"] + pkgs, log)
        log(f"  ✓ Removed {len(pkgs)} orphan package(s)")
    else:
        log("  ✓ No orphan packages found")
    return 0


def lx_paru_clean(log: Log) -> int:
    _run(["paru", "-Sc", "--noconfirm"], log)
    return 0


def lx_yay_clean(log: Log) -> int:
    _run(["yay", "-Sc", "--noconfirm"], log)
    return 0


def lx_zypper_clean(log: Log) -> int:
    _sudo_run(["zypper", "clean", "--all"], log)
    return 0


def lx_emerge_clean(log: Log) -> int:
    _sudo_run(["emerge", "--depclean"], log)
    _sudo_run(["eclean-dist", "-d"], log)
    return 0


def lx_xbps_clean(log: Log) -> int:
    _sudo_run(["xbps-remove", "-Oo"], log)
    return 0


def lx_apk_clean(log: Log) -> int:
    _sudo_run(["apk", "cache", "clean"], log)
    return 0


def lx_nix_collect(log: Log) -> int:
    _run(["nix-collect-garbage", "-d"], log)
    return 0


def lx_eopkg_clean(log: Log) -> int:
    _sudo_run(["eopkg", "delete-cache"], log)
    return 0


def lx_snap_clean(log: Log) -> int:
    freed = _del_paths([Path("/var/lib/snapd/cache")], log)
    # Remove disabled snap revisions
    try:
        result = subprocess.run(
            ["snap", "list", "--all"], capture_output=True, text=True
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if "disabled" in parts:
                name, rev = parts[0], parts[2]
                _sudo_run(["snap", "remove", name, f"--revision={rev}"], log)
    except Exception as e:
        log(f"  ✗ {e}")
    return freed


def lx_flatpak_unused(log: Log) -> int:
    _run(["flatpak", "uninstall", "--unused", "-y"], log)
    return 0


def lx_old_kernels(log: Log) -> int:
    fam = PLATFORM.distro_family
    if fam == Distro.DEBIAN:
        _sudo_run(["apt-get", "autoremove", "--purge", "-y"], log)
    elif fam == Distro.FEDORA:
        _sudo_run(["dnf", "remove", "$(dnf repoquery --installonly --latest-limit=-1 -q)", "-y"], log)
    elif fam == Distro.ARCH:
        log("  ℹ Arch: manage kernels manually via pacman")
    else:
        log("  ℹ Kernel cleanup not supported for this distro family")
    return 0


# ── User cache ─────────────────────────────────────────────────────────────────
def lx_home_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache"], log)


def lx_thumbnail_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache/thumbnails"], log)


def lx_recent_files(log: Log) -> int:
    p = HOME / ".local/share/recently-used.xbel"
    if p.exists():
        return _del_file(p, log)
    return 0


def lx_xsession_errors(log: Log) -> int:
    p = HOME / ".xsession-errors"
    if p.exists():
        return _del_file(p, log)
    return 0


def lx_bash_history(log: Log) -> int:
    p = HOME / ".bash_history"
    if p.exists():
        return _del_file(p, log)
    return 0


def lx_zsh_history(log: Log) -> int:
    p = HOME / ".zsh_history"
    if p.exists():
        return _del_file(p, log)
    return 0


# ── Logs ───────────────────────────────────────────────────────────────────────
def lx_journal_vacuum_time(log: Log) -> int:
    _sudo_run(["journalctl", "--vacuum-time=7d"], log)
    return 0


def lx_journal_vacuum_size(log: Log) -> int:
    _sudo_run(["journalctl", "--vacuum-size=100M"], log)
    return 0


# ── Browsers ───────────────────────────────────────────────────────────────────
def lx_browser_cache(log: Log) -> int:
    cache_root = HOME / ".cache"
    paths: List[Path] = []
    for browser_dir in [
        "google-chrome", "chromium", "BraveSoftware/Brave-Browser",
        "opera", "vivaldi", "microsoft-edge", "epiphany/mozilla/epiphany",
    ]:
        p = cache_root / browser_dir
        if p.exists():
            paths.append(p)
    # Firefox
    for ff_base in [HOME / ".mozilla/firefox", HOME / "snap/firefox/common/.mozilla/firefox"]:
        if ff_base.exists():
            for prof in ff_base.iterdir():
                for sub in ["cache2", "OfflineCache", "thumbnails"]:
                    sp = prof / sub
                    if sp.exists():
                        paths.append(sp)
    return _del_paths(paths, log)


# ── Developer tools ────────────────────────────────────────────────────────────
def lx_pip_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache/pip"], log)


def lx_npm_cache(log: Log) -> int:
    return _del_paths([HOME / ".npm"], log)


def lx_yarn_cache(log: Log) -> int:
    result = subprocess.run(["yarn", "cache", "dir"], capture_output=True, text=True)
    if result.returncode == 0:
        return _del_paths([Path(result.stdout.strip())], log)
    return _del_paths([HOME / ".cache/yarn"], log)


def lx_pnpm_cache(log: Log) -> int:
    return _del_paths([HOME / ".local/share/pnpm/store"], log)


def lx_cargo_cache(log: Log) -> int:
    return _del_paths([HOME / ".cargo/registry"], log)


def lx_go_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache/go", HOME / "go/pkg/mod/cache"], log)


def lx_gradle_cache(log: Log) -> int:
    return _del_paths([HOME / ".gradle/caches"], log)


def lx_maven_cache(log: Log) -> int:
    return _del_paths([HOME / ".m2/repository"], log)


def lx_gem_cache(log: Log) -> int:
    return _del_paths([HOME / ".gem"], log)


def lx_composer_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache/composer"], log)


def lx_docker_cache(log: Log) -> int:
    _run(["docker", "builder", "prune", "-af"], log)
    _run(["docker", "image", "prune", "-af"], log)
    _run(["docker", "container", "prune", "-f"], log)
    _run(["docker", "volume", "prune", "-f"], log)
    return 0


def lx_podman_cache(log: Log) -> int:
    _run(["podman", "system", "prune", "-af"], log)
    return 0


def lx_vscode_cache(log: Log) -> int:
    return _del_paths([
        HOME / ".config/Code/Cache",
        HOME / ".config/Code/CachedData",
        HOME / ".config/Code/Code Cache",
        HOME / ".config/Code/logs",
        HOME / ".config/Code - OSS/Cache",
        HOME / ".config/Code - OSS/logs",
    ], log)


def lx_python_cache(log: Log) -> int:
    """Remove __pycache__ dirs inside home."""
    freed = 0
    for d in HOME.rglob("__pycache__"):
        try:
            freed += _size(d)
            shutil.rmtree(d, ignore_errors=True)
            log(f"  ✓ Removed {d}")
        except Exception:
            pass
    return freed


# ── Third-party ────────────────────────────────────────────────────────────────
def lx_discord_cache(log: Log) -> int:
    return _del_paths([
        HOME / ".config/discord/Cache",
        HOME / ".config/discord/Code Cache",
        HOME / ".config/discord/GPUCache",
        HOME / ".config/discordcanary/Cache",
        HOME / ".config/discordptb/Cache",
    ], log)


def lx_spotify_cache(log: Log) -> int:
    return _del_paths([
        HOME / ".cache/spotify",
        HOME / "snap/spotify/common/.cache/spotify",
    ], log)


def lx_steam_cache(log: Log) -> int:
    return _del_paths([
        HOME / ".local/share/Steam/logs",
        HOME / ".local/share/Steam/appcache",
        HOME / ".steam/steam/logs",
    ], log)


def lx_zoom_cache(log: Log) -> int:
    return _del_paths([HOME / ".zoom/logs"], log)


def lx_slack_cache(log: Log) -> int:
    return _del_paths([
        HOME / ".config/Slack/Cache",
        HOME / ".config/Slack/Code Cache",
        HOME / ".config/Slack/logs",
    ], log)


def lx_obs_cache(log: Log) -> int:
    return _del_paths([HOME / ".config/obs-studio/logs"], log)


def lx_vlc_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache/vlc"], log)


def lx_wine_temp(log: Log) -> int:
    return _del_paths([HOME / ".wine/drive_c/windows/temp"], log)


def lx_lutris_cache(log: Log) -> int:
    return _del_paths([HOME / ".cache/lutris"], log)


def lx_heroic_cache(log: Log) -> int:
    return _del_paths([HOME / ".config/heroic/logs"], log)


# ══════════════════════════════════════════════════════════════════════════════
#  TASK CATALOGUE  (used by ui_main to build the option list)
# ══════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass
from typing import Optional


@dataclass
class TaskDef:
    label:       str
    func:        Callable
    paths:       List[Path]
    group:       str
    tooltip:     str             = ""
    need_root:   bool            = False
    need_tool:   Optional[str]   = None   # e.g. "docker", "npm"


def _has(tool: str) -> bool:
    import shutil
    return shutil.which(tool) is not None


def build_task_catalogue() -> List[TaskDef]:
    p = PLATFORM
    home = HOME
    tasks: List[TaskDef] = []

    def add(label, func, paths, group, tooltip="", need_root=False, need_tool=None):
        tasks.append(TaskDef(label, func, paths, group, tooltip, need_root, need_tool))

    if p.os == "windows":
        # ── System ──
        add("Empty Recycle Bin",           win_recycle_bin,    [],  "System",    "Permanently delete Recycle Bin contents")
        add("Clear User Temp Files",       win_temp,           [Path(tempfile.gettempdir())],  "System", r"%TEMP% folder")
        add("Clear Windows Temp",          win_windows_temp,   [Path(r"C:\Windows\Temp")],    "System", r"C:\Windows\Temp")
        add("Clear Prefetch Files",        win_prefetch,       [Path(r"C:\Windows\Prefetch")], "System", "Windows boot prefetch data")
        add("Clear Windows.old",           win_windows_old,    [Path(r"C:\Windows.old")],     "System", "Previous Windows installation")
        add("Clear Windows Update Cache",  win_update_cache,   [Path(r"C:\Windows\SoftwareDistribution\Download")], "System", "Downloaded update packages")
        add("Clear Delivery Optimization", win_delivery_opt,   [Path(r"C:\Windows\SoftwareDistribution\DeliveryOptimization")], "System", "P2P update delivery cache")
        add("Clear Installer Patch Cache", win_installer_patch,[Path(r"C:\Windows\Installer\$PatchCache$")], "System", "MSI patch cache")
        add("Clear Crash Dumps",           win_crash_dumps,    [Path(r"C:\Windows\Minidump")], "System", "Minidump & memory dump files")
        add("Clear Windows Log Files",     win_log_files,      [Path(r"C:\Windows\Logs")],    "System", "*.log files under C:\\Windows\\Logs")
        add("Clear Icon Cache",            win_icon_cache,     [home/"AppData/Local/IconCache.db"], "System", "Rebuilds on next login")
        add("Clear Event Viewer Logs",     win_event_logs,     [],  "System",    ".evtx event log files")
        add("Flush DNS Cache",             win_flush_dns,      [],  "System",    "ipconfig /flushdns")
        add("Clear Clipboard",             win_clear_clipboard,[],  "System",    "Wipe clipboard contents")
        add("Run Disk Cleanup (cleanmgr)", win_disk_cleanup,   [],  "System",    "Launches Windows Disk Cleanup")
        add("Clear Font Cache",            win_font_cache,     [home/"AppData/Local/FontCache"], "System", "Font metadata cache")

        # ── User & Shell ──
        add("Clear Downloads Folder",      win_downloads,      [home/"Downloads"],   "User & Shell", "⚠ Deletes all files in Downloads")
        add("Clear Recent Files List",     win_recent_files,   [home/"AppData/Roaming/Microsoft/Windows/Recent"], "User & Shell")
        add("Clear Search History",        win_search_history, [],  "User & Shell")
        add("Clear Jump Lists",            win_jump_lists,     [],  "User & Shell", "Recent/frequent file jump lists")
        add("Clear Thumbnail Cache",       win_thumbnail_cache,[home/"AppData/Local/Microsoft/Windows/Explorer"], "User & Shell")
        add("Clear Explorer DB Cache",     win_explorer_db,    [],  "User & Shell", "Explorer *.db files")

        # ── Microsoft Apps ──
        add("Clear Office Cache",          win_office_cache,   [], "Microsoft Apps")
        add("Clear Teams Cache",           win_teams_cache,    [], "Microsoft Apps")
        add("Clear Microsoft Store Cache", win_ms_store,       [], "Microsoft Apps")
        add("Clear WER Reports",           win_wer_reports,    [], "Microsoft Apps", "Windows Error Reporting dumps")
        add("Clear Visual Studio Cache",   win_vs_cache,       [], "Microsoft Apps")
        add("Clear VS Code Cache",         win_vscode_cache,   [], "Microsoft Apps")
        add("Clear OneDrive Logs",         win_onedrive_temp,  [], "Microsoft Apps")
        add("Clear Skype Cache",           win_skype_cache,    [], "Microsoft Apps")

        # ── Browsers ──
        add("Clear All Browser Caches",    win_browser_cache,  [], "Browsers", "Edge, Chrome, Brave, Opera, Vivaldi, Firefox")
        add("Clear Browser Log Files",     win_browser_logs,   [], "Browsers")

        # ── Developer Tools ──
        add("Clear npm Cache",       win_npm_cache,    [], "Developer", need_tool="npm")
        add("Clear pip Cache",       win_pip_cache,    [], "Developer", need_tool="pip")
        add("Clear NuGet Cache",     win_nuget_cache,  [], "Developer")
        add("Clear Gradle Cache",    win_gradle_cache, [], "Developer")
        add("Clear Maven Cache",     win_maven_cache,  [], "Developer")
        add("Clear Cargo Cache",     win_cargo_cache,  [], "Developer", need_tool="cargo")
        add("Clear Go Module Cache", win_go_cache,     [], "Developer", need_tool="go")
        add("Clear Yarn Cache",      win_yarn_cache,   [], "Developer", need_tool="yarn")
        add("Clear pnpm Store",      win_pnpm_cache,   [], "Developer", need_tool="pnpm")
        add("Clear Docker Cache",    win_docker_cache, [], "Developer", need_tool="docker")
        add("Clear DirectX Cache",   win_directx_cache,[home/"AppData/Local/D3DSCache"], "Developer")

        # ── Third-party ──
        add("Clear Discord Cache",  win_discord_cache, [], "Third-party Apps")
        add("Clear Spotify Cache",  win_spotify_cache, [], "Third-party Apps")
        add("Clear Steam Cache",    win_steam_cache,   [], "Third-party Apps")
        add("Clear Epic Games Cache",win_epic_cache,   [], "Third-party Apps")
        add("Clear Zoom Logs",      win_zoom_cache,    [], "Third-party Apps")
        add("Clear Slack Cache",    win_slack_cache,   [], "Third-party Apps")
        add("Clear OBS Logs",       win_obs_cache,     [], "Third-party Apps")
        add("Clear VLC Art Cache",  win_vlc_cache,     [], "Third-party Apps")

    elif p.os == "linux":
        fam = p.distro_family

        # ── System ──
        add("Clear /tmp",               lx_tmp,         [Path("/tmp")],      "System", need_root=True)
        add("Clear /var/tmp",           lx_var_tmp,     [Path("/var/tmp")],  "System", need_root=True)
        add("Empty Trash",              lx_trash,       [home/".local/share/Trash"], "System")
        add("Flush DNS Cache",          lx_flush_dns,   [], "System", need_root=True)
        add("Clear Core Dumps",         lx_core_dumps,  [], "System", need_root=True)
        add("Clear Swap",               lx_swap_clear,  [], "System", "Flush and re-enable swap", need_root=True)
        add("Clear Old /var/log",       lx_var_log,     [], "System", "Remove rotated/compressed logs", need_root=True)

        # ── Package Managers (show only what's installed) ──
        if p.has_apt:
            add("APT Clean Cache",   lx_apt_clean,     [Path("/var/cache/apt/archives")], "Package Managers", need_root=True)
            add("APT Autoclean",     lx_apt_autoclean, [], "Package Managers", need_root=True)
            add("APT Autoremove",    lx_apt_autoremove,[], "Package Managers", need_root=True)
            add("Remove Old Kernels",lx_old_kernels,   [], "Package Managers", need_root=True)
        if p.has_dnf:
            add("DNF Clean All",     lx_dnf_clean,     [], "Package Managers", need_root=True)
            add("DNF Autoremove",    lx_dnf_autoremove,[], "Package Managers", need_root=True)
        if p.has_yum:
            add("YUM Clean All",     lx_yum_clean,     [], "Package Managers", need_root=True)
        if p.has_pacman:
            add("Pacman Clean Cache",    lx_pacman_clean,  [], "Package Managers", need_root=True)
            add("Remove Orphan Packages",lx_pacman_orphans,[], "Package Managers", need_root=True)
        if _has("paru"):
            add("Paru Clean Cache",  lx_paru_clean, [], "Package Managers")
        if _has("yay"):
            add("Yay Clean Cache",   lx_yay_clean,  [], "Package Managers")
        if p.has_zypper:
            add("Zypper Clean",      lx_zypper_clean,  [], "Package Managers", need_root=True)
        if p.has_emerge:
            add("Emerge Depclean",   lx_emerge_clean,  [], "Package Managers", need_root=True)
        if p.has_xbps:
            add("XBPS Remove Orphans",lx_xbps_clean,  [], "Package Managers", need_root=True)
        if p.has_apk:
            add("APK Cache Clean",   lx_apk_clean,    [], "Package Managers", need_root=True)
        if p.has_nix:
            add("Nix Garbage Collect",lx_nix_collect, [], "Package Managers")
        if p.has_eopkg:
            add("eopkg Delete Cache", lx_eopkg_clean, [], "Package Managers", need_root=True)
        if p.has_snap:
            add("Clean Snap Cache & Old Revisions", lx_snap_clean, [], "Package Managers", need_root=True)
        if p.has_flatpak:
            add("Remove Unused Flatpak Runtimes", lx_flatpak_unused, [], "Package Managers")

        # ── User Cache ──
        add("Clear ~/.cache (all)",      lx_home_cache,    [home/".cache"], "User Cache", "⚠ Clears entire user cache")
        add("Clear Thumbnail Cache",     lx_thumbnail_cache,[home/".cache/thumbnails"], "User Cache")
        add("Clear Recent Files",        lx_recent_files,  [], "User Cache")
        add("Clear .xsession-errors",    lx_xsession_errors,[],"User Cache")
        add("Clear Bash History",        lx_bash_history,  [], "User Cache")
        add("Clear Zsh History",         lx_zsh_history,   [], "User Cache")

        # ── Logs ──
        add("Vacuum Journal (keep 7d)",  lx_journal_vacuum_time, [], "Logs", need_root=True)
        add("Vacuum Journal (keep 100M)",lx_journal_vacuum_size, [], "Logs", need_root=True)
        add("Clear /var/log Rotated",    lx_var_log,             [], "Logs", need_root=True)

        # ── Browsers ──
        add("Clear All Browser Caches", lx_browser_cache, [], "Browsers",
            "Chrome, Chromium, Brave, Opera, Vivaldi, Edge, Firefox, Epiphany")

        # ── Developer Tools ──
        add("Clear pip Cache",        lx_pip_cache,    [], "Developer", need_tool="pip")
        add("Clear npm Cache",        lx_npm_cache,    [], "Developer", need_tool="npm")
        add("Clear Yarn Cache",       lx_yarn_cache,   [], "Developer", need_tool="yarn")
        add("Clear pnpm Store",       lx_pnpm_cache,   [], "Developer", need_tool="pnpm")
        add("Clear Cargo Cache",      lx_cargo_cache,  [], "Developer", need_tool="cargo")
        add("Clear Go Module Cache",  lx_go_cache,     [], "Developer", need_tool="go")
        add("Clear Gradle Cache",     lx_gradle_cache, [], "Developer")
        add("Clear Maven Cache",      lx_maven_cache,  [], "Developer")
        add("Clear Ruby Gems Cache",  lx_gem_cache,    [], "Developer", need_tool="gem")
        add("Clear Composer Cache",   lx_composer_cache,[],"Developer", need_tool="composer")
        add("Clear Docker Cache",     lx_docker_cache, [], "Developer", need_tool="docker")
        add("Clear Podman Cache",     lx_podman_cache, [], "Developer", need_tool="podman")
        add("Clear VS Code Cache",    lx_vscode_cache, [], "Developer")
        add("Clear Python __pycache__",lx_python_cache,[], "Developer")

        # ── Third-party ──
        add("Clear Discord Cache",   lx_discord_cache, [], "Third-party Apps")
        add("Clear Spotify Cache",   lx_spotify_cache, [], "Third-party Apps")
        add("Clear Steam Cache",     lx_steam_cache,   [], "Third-party Apps")
        add("Clear Zoom Logs",       lx_zoom_cache,    [], "Third-party Apps")
        add("Clear Slack Cache",     lx_slack_cache,   [], "Third-party Apps")
        add("Clear OBS Logs",        lx_obs_cache,     [], "Third-party Apps")
        add("Clear VLC Cache",       lx_vlc_cache,     [], "Third-party Apps")
        add("Clear Wine Temp",       lx_wine_temp,     [], "Third-party Apps")
        add("Clear Lutris Cache",    lx_lutris_cache,  [], "Third-party Apps")
        add("Clear Heroic Logs",     lx_heroic_cache,  [], "Third-party Apps")

    return tasks
