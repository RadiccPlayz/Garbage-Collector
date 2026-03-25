"""
path_resolver.py

Dynamic install-path discovery for third-party apps.

Windows  — tries registry keys first, falls back to well-known default paths.
Linux    — probes config files, Steam libraryfolders.vdf, XDG dirs, Flatpak,
           Snap mount points, and ~/.config/<app> directories.

All public functions return List[Path] (existing paths only).
"""

from __future__ import annotations

import os
import sys
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from platform_detect import IS_WINDOWS, IS_LINUX

HOME = Path.home()

# ══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _exist(*paths: Path | str) -> List[Path]:
    """Return only the paths that actually exist."""
    out: List[Path] = []
    for p in paths:
        p = Path(p)
        try:
            if p.exists():
                out.append(p)
        except (OSError, ValueError):
            pass
    return out


def _glob_exist(base: Path, pattern: str) -> List[Path]:
    try:
        return [p for p in base.glob(pattern) if p.exists()]
    except Exception:
        return []


# ══════════════════════════════════════════════════════════════════════════════
#  Windows registry helper
# ══════════════════════════════════════════════════════════════════════════════

def _reg_value(hive_str: str, subkey: str, value: str = "") -> Optional[str]:
    """
    Read a single registry value.  Returns None on any failure.
    hive_str: "HKLM" | "HKCU" | "HKCR" | "HKU" | "HKCC"
    """
    if not IS_WINDOWS:
        return None
    try:
        import winreg
        hive_map = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
            "HKCR": winreg.HKEY_CLASSES_ROOT,
            "HKU":  winreg.HKEY_USERS,
            "HKCC": winreg.HKEY_CURRENT_CONFIG,
        }
        hive = hive_map.get(hive_str.upper(), winreg.HKEY_LOCAL_MACHINE)
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            data, _ = winreg.QueryValueEx(key, value)
            return str(data)
    except Exception:
        return None


def _reg_values(hive_str: str, subkey: str) -> dict:
    """Return all values in a registry key as {name: data}."""
    if not IS_WINDOWS:
        return {}
    try:
        import winreg
        hive_map = {
            "HKLM": winreg.HKEY_LOCAL_MACHINE,
            "HKCU": winreg.HKEY_CURRENT_USER,
        }
        hive = hive_map.get(hive_str.upper(), winreg.HKEY_LOCAL_MACHINE)
        result = {}
        with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ) as key:
            i = 0
            while True:
                try:
                    name, data, _ = winreg.EnumValue(key, i)
                    result[name] = data
                    i += 1
                except OSError:
                    break
        return result
    except Exception:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
#  Steam  (cross-platform — library can be on any drive)
# ══════════════════════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def _steam_library_roots() -> List[Path]:
    """
    Parse Steam's libraryfolders.vdf to find every library root,
    including secondary drives.
    """
    roots: List[Path] = []

    if IS_WINDOWS:
        # Registry first
        install = _reg_value("HKCU",
            r"Software\Valve\Steam", "SteamPath")
        if not install:
            install = _reg_value("HKLM",
                r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
        candidates = []
        if install:
            candidates.append(Path(install))
        # Common default locations as fallback
        for drive in _windows_drives():
            candidates += [
                Path(drive) / "Program Files (x86)" / "Steam",
                Path(drive) / "Program Files" / "Steam",
                Path(drive) / "Steam",
                Path(drive) / "Games" / "Steam",
            ]
    elif IS_LINUX:
        candidates = [
            HOME / ".steam" / "steam",
            HOME / ".local" / "share" / "Steam",
            HOME / "snap" / "steam" / "common" / ".steam" / "steam",
            Path("/usr/share/steam"),
        ]
        # Flatpak Steam
        candidates.append(
            HOME / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam"
        )
    else:
        candidates = []

    # From each Steam root, read libraryfolders.vdf
    for base in candidates:
        if not base.exists():
            continue
        roots.append(base)
        vdf = base / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            vdf = base / "config" / "libraryfolders.vdf"
        if vdf.exists():
            try:
                text = vdf.read_text(errors="replace")
                # VDF "path" entries
                for match in re.finditer(r'"path"\s+"([^"]+)"', text):
                    p = Path(match.group(1))
                    if p.exists() and p not in roots:
                        roots.append(p)
            except Exception:
                pass

    return roots


def steam_paths() -> List[Path]:
    """Return Steam cache/log paths across all library roots."""
    out: List[Path] = []
    for root in _steam_library_roots():
        out += _exist(
            root / "logs",
            root / "appcache",
            root / "steamapps" / "downloading",
            root / "steamapps" / "temp",
        )
    return out


# ══════════════════════════════════════════════════════════════════════════════
#  Windows-specific helpers
# ══════════════════════════════════════════════════════════════════════════════

def _windows_drives() -> List[str]:
    """Return all available drive letters on Windows."""
    if not IS_WINDOWS:
        return ["C:\\"]
    try:
        import string
        import ctypes
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        return [
            f"{letter}:\\"
            for i, letter in enumerate(string.ascii_uppercase)
            if bitmask & (1 << i)
        ]
    except Exception:
        return ["C:\\"]


def _reg_install_path(subkey: str, value: str = "InstallLocation",
                      hive: str = "HKCU") -> Optional[Path]:
    v = _reg_value(hive, subkey, value)
    if v:
        p = Path(v)
        if p.exists():
            return p
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  Windows — per-app path resolvers
# ══════════════════════════════════════════════════════════════════════════════

def win_discord_paths() -> List[Path]:
    paths: List[Path] = []
    # Registry uninstall key
    for hive in ("HKCU", "HKLM"):
        for subkey in (
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Discord",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Discord",
        ):
            loc = _reg_install_path(subkey, "InstallLocation", hive)
            if loc:
                for sub in ["Cache", "Code Cache", "GPUCache"]:
                    paths += _exist(loc / sub)

    # Roaming AppData (always present regardless of install path)
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    for name in ("discord", "discordcanary", "discordptb"):
        for sub in ("Cache", "Code Cache", "GPUCache"):
            paths += _exist(roaming / name / sub)
    return paths


def win_spotify_paths() -> List[Path]:
    paths: List[Path] = []
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))

    # Spotify writes cache to LocalAppData regardless of install
    paths += _exist(
        local  / "Spotify" / "Storage",
        local  / "Spotify" / "Browser" / "Cache",
        roaming / "Spotify" / "Storage",
    )
    # Check registry for custom install
    loc = _reg_install_path(
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Spotify",
        "InstallLocation"
    )
    if loc:
        paths += _exist(loc / "Storage")
    return paths


def win_steam_paths() -> List[Path]:
    return steam_paths()


def win_epic_paths() -> List[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    paths: List[Path] = []

    # Registry
    for subkey in (
        r"Software\Epic Games\EpicGamesLauncher",
        r"SOFTWARE\WOW6432Node\Epic Games\EpicGamesLauncher",
    ):
        loc = _reg_install_path(subkey, "AppDataPath", "HKCU") or \
              _reg_install_path(subkey, "AppDataPath", "HKLM")
        if loc:
            paths += _exist(loc / "Logs", loc / "webcache")

    # Default fallback
    paths += _exist(
        local / "EpicGamesLauncher" / "Saved" / "Logs",
        local / "EpicGamesLauncher" / "Saved" / "webcache",
        local / "EpicGamesLauncher" / "Saved" / "webcache_4430",
    )
    return paths


def win_slack_paths() -> List[Path]:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    paths: List[Path] = []

    loc = _reg_install_path(
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\slack",
        "InstallLocation"
    )
    if loc:
        paths += _exist(loc / "Cache", loc / "logs")

    paths += _exist(
        roaming / "Slack" / "Cache",
        roaming / "Slack" / "Code Cache",
        roaming / "Slack" / "logs",
        roaming / "Slack" / "GPUCache",
    )
    return paths


def win_zoom_paths() -> List[Path]:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    local   = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    paths: List[Path] = []

    loc = _reg_install_path(
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ZoomUMX",
        "InstallLocation"
    )
    if loc:
        paths += _exist(loc / "logs")

    paths += _exist(
        roaming / "Zoom" / "logs",
        roaming / "Zoom" / "data",
        local   / "Zoom" / "Logs",
    )
    return paths


def win_teams_paths() -> List[Path]:
    local   = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    roaming = Path(os.environ.get("APPDATA",      HOME / "AppData/Roaming"))
    paths: List[Path] = []

    # New Teams (installed via MS Store — AppData/Local/Packages)
    for pkg in _glob_exist(local / "Packages", "MSTeams_*"):
        paths += _exist(pkg / "LocalCache", pkg / "TempState")

    # Classic Teams
    paths += _exist(
        roaming / "Microsoft" / "Teams" / "Cache",
        roaming / "Microsoft" / "Teams" / "blob_storage",
        roaming / "Microsoft" / "Teams" / "databases",
        roaming / "Microsoft" / "Teams" / "GPUCache",
        roaming / "Microsoft" / "Teams" / "IndexedDB",
        roaming / "Microsoft" / "Teams" / "Local Storage",
        roaming / "Microsoft" / "Teams" / "tmp",
        local   / "Microsoft" / "Teams" / "Cache",
    )
    return paths


def win_vscode_paths() -> List[Path]:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    paths: List[Path] = []

    # Insiders and forks
    for variant in ("Code", "Code - Insiders", "VSCodium"):
        for sub in ("Cache", "CachedData", "Code Cache", "logs", "GPUCache"):
            paths += _exist(roaming / variant / sub)

    loc = _reg_install_path(
        r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{EA457B21-F73E-494C-ACAB-524FDE069978}_is1",
        "InstallLocation"
    )
    return paths


def win_browser_paths() -> List[Path]:
    """All browser caches — respects custom profile locations where detectable."""
    local = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    paths: List[Path] = []

    chromium_bases = {
        "Edge":    local / "Microsoft" / "Edge" / "User Data",
        "Chrome":  local / "Google" / "Chrome" / "User Data",
        "Brave":   local / "BraveSoftware" / "Brave-Browser" / "User Data",
        "Vivaldi": local / "Vivaldi" / "User Data",
        "Opera":   roaming / "Opera Software" / "Opera Stable",
        "Opera GX":roaming / "Opera Software" / "Opera GX Stable",
        "Thorium": local / "Thorium" / "User Data",
        "Ungoogled":local / "Chromium" / "User Data",
    }

    for name, base in chromium_bases.items():
        if not base.exists():
            # check registry for custom user data dir
            pass
        if base.exists():
            # collect all profiles
            for profile in ["Default"] + [f"Profile {i}" for i in range(1, 10)]:
                for sub in ("Cache", "Code Cache", "GPUCache", "Service Worker/CacheStorage"):
                    paths += _exist(base / profile / sub)

    # Firefox — read profiles.ini for actual profile paths
    ff_ini = roaming / "Mozilla" / "Firefox" / "profiles.ini"
    if ff_ini.exists():
        try:
            text = ff_ini.read_text(errors="replace")
            for match in re.finditer(r'^Path=(.+)$', text, re.MULTILINE):
                raw = match.group(1).strip()
                # absolute or relative to profiles dir
                p = Path(raw) if Path(raw).is_absolute() else (ff_ini.parent / raw)
                for sub in ("cache2", "OfflineCache"):
                    paths += _exist(p / sub)
        except Exception:
            pass
    else:
        # fallback
        ff_base = local / "Mozilla" / "Firefox" / "Profiles"
        for prof in _glob_exist(ff_base, "*"):
            for sub in ("cache2", "OfflineCache"):
                paths += _exist(prof / sub)

    return paths


def win_office_paths() -> List[Path]:
    roaming = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
    local   = Path(os.environ.get("LOCALAPPDATA", HOME / "AppData/Local"))
    paths: List[Path] = []
    for ver in ("15.0", "16.0", "17.0"):
        paths += _exist(
            local   / "Microsoft" / "Office" / ver / "OfficeFileCache",
            roaming / "Microsoft" / "Office" / ver / "OfficeFileCache",
        )
    return paths


# ══════════════════════════════════════════════════════════════════════════════
#  Linux — per-app path resolvers
# ══════════════════════════════════════════════════════════════════════════════

def _xdg(var: str, default: Path) -> Path:
    """Return XDG directory, honouring env overrides."""
    v = os.environ.get(var, "")
    return Path(v) if v else default


XDG_CONFIG = _xdg("XDG_CONFIG_HOME", HOME / ".config")
XDG_CACHE  = _xdg("XDG_CACHE_HOME",  HOME / ".cache")
XDG_DATA   = _xdg("XDG_DATA_HOME",   HOME / ".local" / "share")


def _flatpak_app(app_id: str) -> Optional[Path]:
    base = HOME / ".var" / "app" / app_id
    return base if base.exists() else None


def _snap_app(snap_name: str) -> Optional[Path]:
    p = HOME / "snap" / snap_name / "current"
    return p if p.exists() else None


def lx_discord_paths() -> List[Path]:
    paths: List[Path] = []

    # Native install
    for name in ("discord", "discordcanary", "discordptb", "Discord"):
        for sub in ("Cache", "Code Cache", "GPUCache"):
            paths += _exist(XDG_CONFIG / name / sub)

    # Flatpak
    fp = _flatpak_app("com.discordapp.Discord")
    if fp:
        for sub in ("Cache", "Code Cache", "GPUCache"):
            paths += _exist(fp / ".config" / "discord" / sub)

    # Snap
    sn = _snap_app("discord")
    if sn:
        for sub in ("Cache", "Code Cache"):
            paths += _exist(sn / ".config" / "discord" / sub)

    return paths


def lx_spotify_paths() -> List[Path]:
    paths: List[Path] = []

    # Native
    paths += _exist(XDG_CACHE / "spotify")

    # Snap
    sn = _snap_app("spotify")
    if sn:
        paths += _exist(sn / ".cache" / "spotify")

    # Flatpak
    fp = _flatpak_app("com.spotify.Client")
    if fp:
        paths += _exist(fp / ".cache" / "spotify")

    return paths


def lx_steam_paths() -> List[Path]:
    return steam_paths()


def lx_browser_paths() -> List[Path]:
    """
    Find browser caches respecting XDG_CACHE_HOME, Flatpak, Snap, and
    Firefox profiles.ini for actual profile directories.
    """
    paths: List[Path] = []

    # Chromium-family (native)
    chromium_dirs = {
        "google-chrome":               XDG_CONFIG / "google-chrome",
        "chromium":                    XDG_CONFIG / "chromium",
        "BraveSoftware/Brave-Browser": XDG_CONFIG / "BraveSoftware" / "Brave-Browser",
        "opera":                       XDG_CONFIG / "opera",
        "vivaldi":                     XDG_CONFIG / "vivaldi",
        "microsoft-edge":              XDG_CONFIG / "microsoft-edge",
        "thorium":                     XDG_CONFIG / "thorium",
    }
    for name, user_data in chromium_dirs.items():
        if user_data.exists():
            for profile in ["Default"] + [f"Profile {i}" for i in range(1, 10)]:
                for sub in ("Cache", "Code Cache", "GPUCache"):
                    # Cache is under XDG_CACHE in newer Chromium
                    paths += _exist(
                        user_data / profile / sub,
                        XDG_CACHE / name / profile / sub,
                        XDG_CACHE / name / sub,
                    )

    # Flatpak Chrome/Chromium/Brave
    for app_id, cache_rel in (
        ("com.google.Chrome",                     ".cache/google-chrome"),
        ("org.chromium.Chromium",                 ".cache/chromium"),
        ("com.brave.Browser",                     ".cache/BraveSoftware/Brave-Browser"),
        ("com.opera.Opera",                       ".cache/opera"),
        ("org.mozilla.firefox",                   ".cache/mozilla/firefox"),
    ):
        fp = _flatpak_app(app_id)
        if fp:
            paths += _exist(fp / cache_rel)

    # Snap browsers
    for snap_name, cache_rel in (
        ("firefox",  ".cache/mozilla/firefox"),
        ("chromium", ".cache/chromium"),
    ):
        sn = _snap_app(snap_name)
        if sn:
            paths += _exist(sn / cache_rel)

    # Firefox — read profiles.ini for exact profile paths
    for ff_base in (
        HOME / ".mozilla" / "firefox",
        HOME / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
    ):
        ini = ff_base / "profiles.ini"
        if ini.exists():
            try:
                text = ini.read_text(errors="replace")
                for m in re.finditer(r'^Path=(.+)$', text, re.MULTILINE):
                    raw = m.group(1).strip()
                    p = Path(raw) if Path(raw).is_absolute() else (ff_base / raw)
                    for sub in ("cache2", "OfflineCache", "thumbnails"):
                        paths += _exist(p / sub)
            except Exception:
                pass
        elif ff_base.exists():
            # fallback glob
            for prof in ff_base.iterdir():
                for sub in ("cache2", "OfflineCache"):
                    paths += _exist(prof / sub)

    return paths


def lx_slack_paths() -> List[Path]:
    paths: List[Path] = []

    # Native
    for sub in ("Cache", "Code Cache", "logs", "GPUCache"):
        paths += _exist(XDG_CONFIG / "Slack" / sub)

    # Flatpak
    fp = _flatpak_app("com.slack.Slack")
    if fp:
        for sub in ("Cache", "logs"):
            paths += _exist(fp / ".config" / "Slack" / sub)

    # Snap
    sn = _snap_app("slack")
    if sn:
        paths += _exist(sn / ".config" / "Slack" / "Cache")

    return paths


def lx_zoom_paths() -> List[Path]:
    paths: List[Path] = []
    paths += _exist(HOME / ".zoom" / "logs")
    paths += _exist(XDG_CONFIG / "zoom" / "logs")

    fp = _flatpak_app("us.zoom.Zoom")
    if fp:
        paths += _exist(fp / ".zoom" / "logs")
    return paths


def lx_vscode_paths() -> List[Path]:
    paths: List[Path] = []
    for variant in ("Code", "Code - Insiders", "VSCodium", "code-oss"):
        for sub in ("Cache", "CachedData", "Code Cache", "logs", "GPUCache"):
            paths += _exist(XDG_CONFIG / variant / sub)

    # Flatpak
    for app_id in ("com.visualstudio.code", "com.vscodium.codium"):
        fp = _flatpak_app(app_id)
        if fp:
            for sub in ("Cache", "logs"):
                paths += _exist(fp / ".config" / "Code" / sub)
    return paths


def lx_lutris_paths() -> List[Path]:
    paths = list(_exist(XDG_CACHE / "lutris"))
    fp = _flatpak_app("net.lutris.Lutris")
    if fp:
        paths += _exist(fp / ".cache" / "lutris")
    return paths


def lx_heroic_paths() -> List[Path]:
    paths = []
    for sub in ("logs", "GamesConfig"):
        paths += _exist(XDG_CONFIG / "heroic" / sub)
    fp = _flatpak_app("com.heroicgameslauncher.hgl")
    if fp:
        paths += _exist(fp / ".config" / "heroic" / "logs")
    return paths


def lx_obs_paths() -> List[Path]:
    paths = list(_exist(XDG_CONFIG / "obs-studio" / "logs"))
    fp = _flatpak_app("com.obsproject.Studio")
    if fp:
        paths += _exist(fp / ".config" / "obs-studio" / "logs")
    return paths


def lx_vlc_paths() -> List[Path]:
    return list(_exist(XDG_CACHE / "vlc"))


def lx_wine_temp_paths() -> List[Path]:
    paths: List[Path] = []
    # Default prefix
    paths += _exist(HOME / ".wine" / "drive_c" / "windows" / "temp")
    # WINEPREFIX env override
    wp = os.environ.get("WINEPREFIX")
    if wp:
        paths += _exist(Path(wp) / "drive_c" / "windows" / "temp")
    # Scan common prefix locations
    for prefix_parent in (HOME / ".local" / "share" / "wineprefixes",
                          HOME / "Games",
                          HOME / ".wine_prefixes"):
        if prefix_parent.exists():
            for prefix in prefix_parent.iterdir():
                p = prefix / "drive_c" / "windows" / "temp"
                paths += _exist(p)
    return paths
