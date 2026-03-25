"""
platform_detect.py
Detects OS, Linux distro family, and available package managers.
"""

import os
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── OS flags ──────────────────────────────────────────────────────────────────
IS_WINDOWS: bool = platform.system() == "Windows"
IS_LINUX:   bool = platform.system() == "Linux"
IS_MAC:     bool = platform.system() == "Darwin"


# ── Expanded PATH search ───────────────────────────────────────────────────────
def _expanded_path() -> str:
    """
    Build a PATH string that includes common tool install locations that are
    stripped when running under sudo or from a launcher without a full shell env.

    Covers:
      - System defaults  /usr/bin  /usr/local/bin  /bin  /sbin
      - User local       ~/.local/bin
      - nvm              ~/.nvm/versions/node/*/bin  (all installed node versions)
      - fnm              ~/.local/share/fnm/node-versions/*/installation/bin
      - volta            ~/.volta/bin
      - n                ~/n/bin
      - nodenv           ~/.nodenv/shims  ~/.nodenv/bin
      - pyenv            ~/.pyenv/shims   ~/.pyenv/bin
      - rbenv            ~/.rbenv/shims   ~/.rbenv/bin
      - Homebrew (Linux) /home/linuxbrew/.linuxbrew/bin
      - Cargo            ~/.cargo/bin
      - Go               ~/go/bin
      - Snap bins        /snap/bin
      - Windows extras   %APPDATA%\npm  %PROGRAMFILES%\nodejs
    """
    home  = Path.home()
    extra: list[str] = []

    if IS_LINUX or IS_MAC:
        # System
        extra += ["/usr/local/sbin", "/usr/local/bin", "/usr/sbin",
                  "/usr/bin", "/sbin", "/bin"]
        # User
        extra.append(str(home / ".local" / "bin"))
        # nvm — glob all installed node versions
        nvm_root = Path(os.environ.get("NVM_DIR", home / ".nvm"))
        for node_bin in sorted((nvm_root / "versions" / "node").glob("*/bin")):
            extra.append(str(node_bin))
        # fnm
        for node_bin in sorted((home / ".local" / "share" / "fnm" /
                                 "node-versions").glob("*/installation/bin")):
            extra.append(str(node_bin))
        # volta
        extra.append(str(home / ".volta" / "bin"))
        # n
        extra.append(str(home / "n" / "bin"))
        # nodenv
        extra += [str(home / ".nodenv" / "shims"),
                  str(home / ".nodenv" / "bin")]
        # pyenv
        extra += [str(home / ".pyenv" / "shims"),
                  str(home / ".pyenv" / "bin")]
        # rbenv
        extra += [str(home / ".rbenv" / "shims"),
                  str(home / ".rbenv" / "bin")]
        # Homebrew on Linux
        extra += ["/home/linuxbrew/.linuxbrew/bin",
                  "/home/linuxbrew/.linuxbrew/sbin"]
        # Cargo / Go
        extra += [str(home / ".cargo" / "bin"),
                  str(home / "go" / "bin")]
        # Snap
        extra.append("/snap/bin")

    elif IS_WINDOWS:
        app_data  = os.environ.get("APPDATA",      str(home / "AppData" / "Roaming"))
        prog      = os.environ.get("PROGRAMFILES",  r"C:\Program Files")
        prog_x86  = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local_app = os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local"))
        extra += [
            str(Path(app_data) / "npm"),
            str(Path(prog) / "nodejs"),
            str(Path(prog_x86) / "nodejs"),
            str(Path(local_app) / "Programs" / "Python" / "Python312"),
            str(Path(local_app) / "Programs" / "Python" / "Python311"),
            str(Path(local_app) / "Programs" / "Python" / "Python310"),
            str(Path(prog) / "Git" / "cmd"),
        ]
        # nvm-windows
        nvm_home = os.environ.get("NVM_HOME", str(home / "AppData" / "Roaming" / "nvm"))
        for node_dir in sorted(Path(nvm_home).glob("v*")):
            extra.append(str(node_dir))
        # volta
        extra.append(str(home / ".volta" / "bin"))
        # fnm on Windows
        extra.append(str(Path(local_app) / "fnm"))

    # Merge: existing PATH entries first, then extras (deduped, order preserved)
    existing = os.environ.get("PATH", "").split(os.pathsep)
    seen: set[str] = set()
    merged: list[str] = []
    for p in existing + extra:
        if p and p not in seen:
            seen.add(p)
            merged.append(p)

    return os.pathsep.join(merged)


# Compute once at import time
_SEARCH_PATH: str = _expanded_path()


def _cmd(name: str) -> bool:
    """Return True if `name` is found anywhere on the expanded PATH."""
    return shutil.which(name, path=_SEARCH_PATH) is not None


# ── Distro families ───────────────────────────────────────────────────────────
class Distro:
    UNKNOWN  = "unknown"
    DEBIAN   = "debian"      # Debian, Ubuntu, PopOS, Mint, Elementary, Zorin…
    FEDORA   = "fedora"      # Fedora, Nobara, RHEL, CentOS, AlmaLinux, Rocky…
    ARCH     = "arch"        # Arch, Manjaro, EndeavourOS, Garuda, CachyOS…
    OPENSUSE = "opensuse"    # openSUSE Leap / Tumbleweed
    GENTOO   = "gentoo"      # Gentoo, Funtoo
    VOID     = "void"        # Void Linux
    ALPINE   = "alpine"      # Alpine Linux
    NIXOS    = "nixos"       # NixOS
    SOLUS    = "solus"       # Solus


@dataclass
class PlatformInfo:
    os:              str = "unknown"          # "windows" | "linux" | "mac"
    distro_id:       str = ""                 # raw /etc/os-release ID
    distro_name:     str = ""                 # pretty name
    distro_family:   str = Distro.UNKNOWN     # one of Distro.*
    version:         str = ""
    # package managers present on PATH
    has_apt:         bool = False
    has_dnf:         bool = False
    has_yum:         bool = False
    has_pacman:      bool = False
    has_zypper:      bool = False
    has_emerge:      bool = False
    has_xbps:        bool = False
    has_apk:         bool = False
    has_nix:         bool = False
    has_eopkg:       bool = False
    has_snap:        bool = False
    has_flatpak:     bool = False
    has_docker:      bool = False
    has_podman:      bool = False
    has_npm:         bool = False
    has_pip:         bool = False
    has_cargo:       bool = False
    has_go:          bool = False
    has_gem:         bool = False
    has_composer:    bool = False
    has_gradle:      bool = False
    has_maven:       bool = False
    extra:           dict = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.os == "windows":
            return "Windows"
        if self.os == "linux":
            return self.distro_name or "Linux"
        if self.os == "mac":
            return "macOS"
        return "Unknown OS"

    @property
    def icon(self) -> str:
        icons = {
            "windows": "🪟",
            "mac":     "🍎",
            Distro.DEBIAN:   "🐧",
            Distro.FEDORA:   "🎩",
            Distro.ARCH:     "⚙️",
            Distro.OPENSUSE: "🦎",
            Distro.GENTOO:   "🔧",
            Distro.VOID:     "∅",
            Distro.ALPINE:   "🏔️",
            Distro.NIXOS:    "❄️",
            Distro.SOLUS:    "🌊",
        }
        if self.os == "windows":
            return icons["windows"]
        if self.os == "mac":
            return icons["mac"]
        return icons.get(self.distro_family, "🐧")


# ── Internal helpers ───────────────────────────────────────────────────────────
def _cmd(name: str) -> bool:
    return shutil.which(name) is not None


def _read_os_release() -> dict:
    data: dict = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        p = Path(path)
        if p.exists():
            for line in p.read_text(errors="replace").splitlines():
                if "=" in line:
                    k, _, v = line.partition("=")
                    data[k.strip()] = v.strip().strip('"')
            break
    return data


_DEBIAN_IDS = {
    "debian", "ubuntu", "pop", "linuxmint", "mint", "elementary",
    "zorin", "kali", "parrot", "mx", "raspbian", "deepin", "backbox",
    "tails", "crunchbang", "bunsenlabs", "antix", "sparky", "pureos",
    "lmde", "kubuntu", "xubuntu", "lubuntu", "ubuntu-mate",
}
_FEDORA_IDS = {
    "fedora", "nobara", "rhel", "centos", "almalinux", "rocky",
    "oracle", "scientific", "clearos", "springdale", "eurolinux",
    "amazon", "photon",
}
_ARCH_IDS = {
    "arch", "manjaro", "endeavouros", "garuda", "cachyos",
    "artix", "arco", "rebornos", "crystal", "archcraft",
}
_OPENSUSE_IDS = {"opensuse", "opensuse-leap", "opensuse-tumbleweed", "sled", "sles"}
_GENTOO_IDS   = {"gentoo", "funtoo", "calculate"}
_VOID_IDS     = {"void"}
_ALPINE_IDS   = {"alpine"}
_NIXOS_IDS    = {"nixos"}
_SOLUS_IDS    = {"solus"}


def _family(distro_id: str, like: str) -> str:
    did = distro_id.lower()
    lk  = like.lower()
    for ids, fam in (
        (_DEBIAN_IDS,   Distro.DEBIAN),
        (_FEDORA_IDS,   Distro.FEDORA),
        (_ARCH_IDS,     Distro.ARCH),
        (_OPENSUSE_IDS, Distro.OPENSUSE),
        (_GENTOO_IDS,   Distro.GENTOO),
        (_VOID_IDS,     Distro.VOID),
        (_ALPINE_IDS,   Distro.ALPINE),
        (_NIXOS_IDS,    Distro.NIXOS),
        (_SOLUS_IDS,    Distro.SOLUS),
    ):
        if did in ids or any(l in ids for l in lk.split()):
            return fam
    return Distro.UNKNOWN


# ── Public API ─────────────────────────────────────────────────────────────────
def detect() -> PlatformInfo:
    info = PlatformInfo()

    if IS_WINDOWS:
        info.os = "windows"
        info.distro_name = "Windows"
    elif IS_MAC:
        info.os = "mac"
        info.distro_name = "macOS"
    elif IS_LINUX:
        info.os = "linux"
        rel = _read_os_release()
        info.distro_id   = rel.get("ID", "")
        info.distro_name = rel.get("PRETTY_NAME", rel.get("NAME", "Linux"))
        info.version     = rel.get("VERSION_ID", "")
        info.distro_family = _family(info.distro_id, rel.get("ID_LIKE", ""))

        # package managers
        info.has_apt    = _cmd("apt-get")
        info.has_dnf    = _cmd("dnf")
        info.has_yum    = _cmd("yum")
        info.has_pacman = _cmd("pacman")
        info.has_zypper = _cmd("zypper")
        info.has_emerge = _cmd("emerge")
        info.has_xbps   = _cmd("xbps-install")
        info.has_apk    = _cmd("apk")
        info.has_nix    = _cmd("nix-collect-garbage")
        info.has_eopkg  = _cmd("eopkg")
        info.has_snap   = _cmd("snap")
        info.has_flatpak= _cmd("flatpak")
    else:
        info.os = "unknown"

    # cross-platform tools
    info.has_docker   = _cmd("docker")
    info.has_podman   = _cmd("podman")
    info.has_npm      = _cmd("npm")
    info.has_pip      = _cmd("pip") or _cmd("pip3")
    info.has_cargo    = _cmd("cargo")
    info.has_go       = _cmd("go")
    info.has_gem      = _cmd("gem")
    info.has_composer = _cmd("composer")
    info.has_gradle   = _cmd("gradle")
    info.has_maven    = _cmd("mvn")

    return info


# singleton
PLATFORM: PlatformInfo = detect()
