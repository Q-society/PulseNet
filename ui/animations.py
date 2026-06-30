"""
animations.py
-------------
Small, dependency-light animation helpers: boot sequences, typewriter
text, and spinner contexts. Everything here respects config.animation_speed
so users on slow Termux terminals (or anyone impatient) can speed things up.
"""

from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from typing import Iterator

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text

from ui.theme import Palette

BOOT_SEQUENCE = [
    "Initializing core modules",
    "Establishing secure runtime context",
    "Loading network interfaces",
    "Calibrating diagnostic engines",
    "Syncing local configuration",
    "Ready",
]


def typewriter(console: Console, text: str, style: str = "", delay: float = 0.012) -> None:
    """Print text one character at a time. Falls back to instant print if
    stdout isn't a real interactive terminal (e.g. piped output, CI)."""
    if not sys.stdout.isatty():
        console.print(text, style=style)
        return
    for char in text:
        console.print(char, style=style, end="")
        console.file.flush()
        time.sleep(delay)
    console.print()


def boot_sequence(console: Console, palette: Palette, speed_multiplier: float = 1.0) -> None:
    """Animated checklist shown once at startup (skippable via config)."""
    step_delay = 0.18 * speed_multiplier
    settle_delay = 0.05 * speed_multiplier

    with Live(console=console, refresh_per_second=20, transient=True) as live:
        for i, step in enumerate(BOOT_SEQUENCE):
            spinner = Spinner("dots", text=Text(f" {step}...", style=palette.muted))
            live.update(Panel(spinner, border_style=palette.secondary, padding=(0, 2)))
            time.sleep(step_delay)
            done_text = Text()
            done_text.append("  ✓ ", style=f"bold {palette.success}")
            done_text.append(step, style=palette.text)
            live.update(Panel(done_text, border_style=palette.success, padding=(0, 2)))
            time.sleep(settle_delay)


@contextmanager
def spinner_task(
    console: Console,
    palette: Palette,
    message: str,
) -> Iterator[None]:
    """Context manager that shows a spinner for the duration of a blocking
    call (e.g. a DNS lookup or geo-IP request) without blocking forever if
    something goes wrong -- the `with` block's own try/except governs that."""
    text = Text(f" {message}", style=palette.text)
    spinner = Spinner("line", text=text, style=palette.primary)
    with Live(spinner, console=console, refresh_per_second=12, transient=True):
        yield


def pulse_divider(console: Console, palette: Palette, width: int | None = None) -> None:
    """A subtle horizontal divider styled to the active palette, used to
    separate sections without relying on full rich.rule boilerplate."""
    w = width or console.size.width
    line = "─" * w
    console.print(Text(line, style=palette.muted))
