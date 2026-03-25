# Garbage Collector

> A cross-platform system cleanup tool built with PyQt6.  
> Dark terminal aesthetic · live streaming console · smart distro detection.

---

## File Structure

```
.
├── main.py              # Entry point — launches the Qt app
├── platform_detect.py   # OS + Linux distro detection (singleton PLATFORM)
├── cleanup_tasks.py     # All cleanup functions + task catalogue builder
├── workers.py           # QThread workers (size calc, cleanup runner)
├── ui_main.py           # Main window, sidebar, live console, stats bar
├── ui_styles.py         # QSS stylesheet (dark industrial theme)
├── build.bat            # Windows PyInstaller build script
├── build.sh             # Linux PyInstaller build script
└── requirements.txt
```

---

## Features

### UI / UX
- Dark industrial terminal aesthetic (phosphor green + GitHub-blue accents)
- Live streaming console output — lines buffered & flushed at ~25 fps so the UI never freezes
- Colour-coded log lines: green (ok), red (error), blue (task header), amber (info), purple (summary)
- Stats bar: selected count · estimated space · freed bytes · elapsed time
- Debounced async size estimator (doesn't block the UI while scanning)
- Select All / None controls per sidebar
- Cancel button mid-cleanup
- Splitter between sidebar and console

### Platform detection

| Linux family | Distros detected |
|---|---|
| Debian | Debian, Ubuntu, Pop!_OS, Mint, Elementary, Zorin, Kali, Parrot, MX, Raspbian, Deepin, BackBox, Tails, Sparky, PureOS, LMDE, Kubuntu, Xubuntu, Lubuntu, and more |
| Fedora | Fedora, Nobara, RHEL, CentOS, AlmaLinux, Rocky, Oracle, Scientific, Amazon Linux |
| Arch | Arch, Manjaro, EndeavourOS, Garuda, CachyOS, Artix, ArcoLinux, RebornOS, Archcraft |
| openSUSE | Leap, Tumbleweed, SLED, SLES |
| Gentoo | Gentoo, Funtoo, Calculate |
| Void | Void Linux |
| Alpine | Alpine Linux |
| NixOS | NixOS |
| Solus | Solus |

Package managers auto-detected: `apt`, `dnf`, `yum`, `pacman`, `paru`, `yay`, `zypper`, `emerge`, `xbps`, `apk`, `nix`, `eopkg`, `snap`, `flatpak`

Dev tools auto-detected: `docker`, `podman`, `npm`, `pip`, `cargo`, `go`, `gem`, `composer`, `gradle`, `mvn`

Options that require unavailable tools are shown greyed out.

---

## Windows Options

| Group | Options |
|---|---|
| System | Recycle Bin, User Temp, Windows Temp, Prefetch, Windows.old, Update Cache, Delivery Optimization, Installer Patch Cache, Crash Dumps, Windows Logs, Icon Cache, Event Viewer Logs, DNS Flush, Clipboard, Disk Cleanup (cleanmgr), Font Cache |
| User & Shell | Downloads, Recent Files, Search History, Jump Lists, Thumbnail Cache, Explorer DB Cache |
| Microsoft Apps | Office Cache, Teams Cache, MS Store Cache, WER Reports, Visual Studio, VS Code, OneDrive Logs, Skype |
| Browsers | Edge, Chrome, Brave, Opera, Vivaldi, Firefox (all profiles) |
| Developer | npm, pip, NuGet, Gradle, Maven, Cargo, Go modules, Yarn, pnpm, Docker, DirectX Cache |
| Third-party | Discord, Spotify, Steam, Epic Games, Zoom, Slack, OBS, VLC |

## Linux Options

| Group | Options |
|---|---|
| System | /tmp, /var/tmp, Trash, DNS Flush, Core Dumps, Swap Cycle, /var/log rotated |
| Package Managers | (shown only if installed) APT clean/autoclean/autoremove, DNF, YUM, Pacman + orphans, paru, yay, zypper, emerge, xbps, apk, nix, eopkg, snap revisions, flatpak unused |
| User Cache | ~/.cache (all), Thumbnails, Recent Files, .xsession-errors, Bash/Zsh history |
| Logs | Journal vacuum by time (7d) or size (100M), /var/log rotated |
| Browsers | Chrome, Chromium, Brave, Opera, Vivaldi, Edge, Firefox, Epiphany |
| Developer | pip, npm, Yarn, pnpm, Cargo, Go modules, Gradle, Maven, Gem, Composer, Docker, Podman, VS Code, Python __pycache__ |
| Third-party | Discord, Spotify, Steam, Zoom, Slack, OBS, VLC, Wine temp, Lutris, Heroic |

---

## Requirements

- Python 3.10+
- PyQt6

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
# Run directly
python main.py

# Windows — UAC elevation is automatic via the `elevate` package
# Linux — run with sudo for system-level tasks (APT, journal, /tmp, etc.)
sudo python main.py
```

---

## Build

**Windows:**
```bat
build.bat
```

**Linux:**
```bash
chmod +x build.sh && ./build.sh
```

Output: `dist/GarbageCollector` (or `.exe` on Windows)

---

## Notes

- Close apps like Teams, Discord, Spotify, Office before cleaning their caches.
- The Downloads option **permanently deletes** all files in your Downloads folder — use with care.
- `~/.cache (all)` clears your entire user cache; individual apps may take time to regenerate thumbnails, icons, etc.
- Kernel removal on Debian/Ubuntu uses `apt autoremove --purge` — safe only when you've booted into the kernel you want to keep.

---

## License

MIT
