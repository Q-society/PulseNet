"""
banner.py
---------
Builds the pyfiglet ASCII-art identity banner and renders it with a
per-line (or per-character, for small terminals) color gradient using
rich.Text -- this is the single biggest visual signature of the app and
what makes the startup screen feel like a dedicated product rather than
a plain script.
"""

from __future__ import annotations

import pyfiglet
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ui.theme import Palette, gradient_stops

APP_NAME = "PULSENET"
TAGLINE = "Premium Network Diagnostics Suite"

# Fonts that render cleanly across narrow Termux terminals as well as wide
# desktop ones. "slant" is the primary choice; "small" is the fallback for
# terminals under 70 columns.
PRIMARY_FONT = "slant"
COMPACT_FONT = "small"


def _render_figlet(text: str, font: str, width: int) -> str:
    fig = pyfiglet.Figlet(font=font, width=max(width, 40))
    return fig.renderText(text)


def build_banner_text(palette: Palette, terminal_width: int) -> Text:
    """
    Render APP_NAME through pyfiglet, then color it with a horizontal
    gradient across the figlet's own line width -- each character column
    gets a color interpolated from gradient_start to gradient_end, which
    is what produces the "premium" cyan-to-violet sweep look.
    """
    font = PRIMARY_FONT if terminal_width >= 78 else COMPACT_FONT
    raw = _render_figlet(APP_NAME, font, terminal_width)
    lines = raw.rstrip("\n").split("\n")
    max_len = max((len(line) for line in lines), default=1) or 1

    stops = gradient_stops(palette.gradient_start, palette.gradient_end, max_len)

    banner = Text()
    for line in lines:
        for col, char in enumerate(line):
            color = stops[min(col, max_len - 1)]
            banner.append(char, style=f"bold {color}")
        banner.append("\n")
    return banner


def build_tagline_text(palette: Palette) -> Text:
    tagline = Text()
    tagline.append("◆ ", style=f"bold {palette.accent}")
    tagline.append(TAGLINE.upper(), style=f"italic {palette.muted}")
    tagline.append(" ◆", style=f"bold {palette.accent}")
    return tagline


def build_version_line(palette: Palette, version: str, platform_name: str) -> Text:
    line = Text()
    line.append(f"v{version}", style=f"bold {palette.secondary}")
    line.append("  •  ", style=palette.muted)
    line.append(f"running on {platform_name}", style=palette.muted)
    return line


def render_splash(
    console: Console,
    palette: Palette,
    version: str,
    platform_name: str,
) -> None:
    """Print the full splash identity block: banner + tagline + version."""
    width = console.size.width
    banner_text = build_banner_text(palette, width)
    tagline_text = build_tagline_text(palette)
    version_text = build_version_line(palette, version, platform_name)

    console.print(Align.center(banner_text))
    console.print(Align.center(tagline_text))
    console.print()
    console.print(Align.center(version_text))
    console.print()


def render_compact_header(console: Console, palette: Palette, subtitle: str = "") -> None:
    """
    A smaller, single-line-figlet-free header used on every screen after
    the splash, so navigating the app still feels branded without
    re-running the full ASCII banner each time (which would be noisy).
    """
    title = Text()
    title.append("◆ ", style=f"bold {palette.accent}")
    title.append("PULSENET", style=f"bold {palette.primary}")
    if subtitle:
        title.append("  ›  ", style=palette.muted)
        title.append(subtitle, style=f"bold {palette.text}")

    console.print(
        Panel(
            Align.center(title),
            border_style=palette.secondary,
            padding=(0, 2),
        )
    )
