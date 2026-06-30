"""
platform_utils.py
------------------
Centralized platform detection and platform-specific command resolution.

PulseNet runs identically on Linux, Windows, macOS, and Termux (Android).
Every other module imports from here instead of calling `platform.system()`
or `os.name` directly, so platform quirks are fixed in exactly one place.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path


class OSKind(Enum):
    LINUX = auto()
    WINDOWS = auto()
    MACOS = auto()
    TERMUX = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class PlatformProfile:
    """Immutable snapshot of the runtime environment, computed once."""

    kind: OSKind
    name: str
    is_windows: bool
    is_posix: bool
    is_termux: bool
    home_dir: Path
    config_dir: Path
    shell: str
    python_executable: str
    supports_ansi: bool
    terminal_columns: int
    terminal_lines: int


def _detect_termux() -> bool:
    """
    Termux exposes a unique environment variable set and a predictable
    prefix path. We check both, since relying on a single signal is fragile
    across Termux versions.
    """
    if os.environ.get("TERMUX_VERSION"):
        return True
    prefix = os.environ.get("PREFIX", "")
    if "com.termux" in prefix:
        return True
    return Path("/data/data/com.termux").exists()


def _detect_kind() -> OSKind:
    system = platform.system().lower()
    if _detect_termux():
        return OSKind.TERMUX
    if system == "windows":
        return OSKind.WINDOWS
    if system == "darwin":
        return OSKind.MACOS
    if system == "linux":
        return OSKind.LINUX
    return OSKind.UNKNOWN


def _detect_ansi_support() -> bool:
    """
    Windows Terminal, modern PowerShell, ConEmu, and any POSIX terminal all
    support ANSI escape codes today. Legacy cmd.exe (pre Win10 1511) does
    not, so we enable Windows' native VT100 mode when possible and fall
    back to colorama-style detection if that fails.
    """
    if os.environ.get("NO_COLOR"):
        return False
    if platform.system().lower() == "windows":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return os.environ.get("WT_SESSION") is not None or os.environ.get(
                "ANSICON"
            ) is not None
    return sys.stdout.isatty()


def _resolve_config_dir(kind: OSKind, home: Path) -> Path:
    if kind == OSKind.WINDOWS:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else home / "AppData" / "Roaming"
        return base / "PulseNet"
    if kind == OSKind.MACOS:
        return home / "Library" / "Application Support" / "PulseNet"
    # Linux, Termux, and unknown POSIX systems share the XDG-style layout.
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else home / ".config"
    return base / "pulsenet"


def _terminal_size() -> tuple[int, int]:
    try:
        size = shutil.get_terminal_size(fallback=(100, 30))
        return size.columns, size.lines
    except Exception:
        return 100, 30


def build_profile() -> PlatformProfile:
    kind = _detect_kind()
    home = Path.home()
    cols, lines = _terminal_size()
    shell = os.environ.get("SHELL") or os.environ.get("COMSPEC") or "unknown"

    return PlatformProfile(
        kind=kind,
        name={
            OSKind.LINUX: "Linux",
            OSKind.WINDOWS: "Windows",
            OSKind.MACOS: "macOS",
            OSKind.TERMUX: "Termux (Android)",
            OSKind.UNKNOWN: "Unknown",
        }[kind],
        is_windows=(kind == OSKind.WINDOWS),
        is_posix=(kind in (OSKind.LINUX, OSKind.MACOS, OSKind.TERMUX)),
        is_termux=(kind == OSKind.TERMUX),
        home_dir=home,
        config_dir=_resolve_config_dir(kind, home),
        shell=shell,
        python_executable=sys.executable,
        supports_ansi=_detect_ansi_support(),
        terminal_columns=cols,
        terminal_lines=lines,
    )


# Computed once at import time and reused everywhere else in the app.
PROFILE = build_profile()


def ping_command(host: str, count: int) -> list[str]:
    """Return the correct ping argv for the current OS."""
    if PROFILE.is_windows:
        return ["ping", "-n", str(count), host]
    # Linux, macOS, and Termux all use the same iputils-style flags.
    return ["ping", "-c", str(count), host]


def traceroute_command(host: str, max_hops: int) -> list[str]:
    """Return the correct traceroute/tracert argv for the current OS."""
    if PROFILE.is_windows:
        return ["tracert", "-h", str(max_hops), host]
    if shutil.which("traceroute"):
        return ["traceroute", "-m", str(max_hops), host]
    # Termux frequently lacks `traceroute` unless installed separately;
    # `tracepath` ships with busybox/iputils and works as a fallback.
    if shutil.which("tracepath"):
        return ["tracepath", "-m", str(max_hops), host]
    return ["traceroute", "-m", str(max_hops), host]


def clear_screen() -> None:
    """Clear the terminal in a way that works everywhere, including Termux."""
    os.system("cls" if PROFILE.is_windows else "clear")


def has_binary(binary_name: str) -> bool:
    return shutil.which(binary_name) is not None


def run_silent(argv: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """
    Run a subprocess and capture output without ever raising on the caller's
    behalf. Every tool module that shells out (ping, traceroute, whois)
    funnels through here so failures degrade gracefully instead of crashing
    the whole interface.
    """
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"Command not found: {argv[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s"
    except Exception as exc:  # noqa: BLE001 - last line of defense
        return 1, "", str(exc)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
