"""
theme.py
--------
Visual identity for PulseNet: color palettes, rich.Theme registration,
and small color-math helpers used to build gradient text and progress
bars that feel custom-built rather than default-library output.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.theme import Theme


@dataclass(frozen=True)
class Palette:
    """A named set of hex colors that define one PulseNet visual theme."""

    name: str
    primary: str
    secondary: str
    accent: str
    success: str
    warning: str
    danger: str
    muted: str
    bg_panel: str
    text: str
    gradient_start: str
    gradient_end: str


AURORA = Palette(
    name="aurora",
    primary="#00e5ff",
    secondary="#7c4dff",
    accent="#00ffa3",
    success="#00ffa3",
    warning="#ffd166",
    danger="#ff4d6d",
    muted="#5c6b8a",
    bg_panel="#0d1117",
    text="#e6f1ff",
    gradient_start="#00e5ff",
    gradient_end="#7c4dff",
)

CRIMSON = Palette(
    name="crimson",
    primary="#ff3864",
    secondary="#ff9f1c",
    accent="#ffd23f",
    success="#3ddc97",
    warning="#ffb627",
    danger="#ff3864",
    muted="#7a5c61",
    bg_panel="#1a0e10",
    text="#ffe8e8",
    gradient_start="#ff3864",
    gradient_end="#ff9f1c",
)

MONO = Palette(
    name="mono",
    primary="#e0e0e0",
    secondary="#a0a0a0",
    accent="#ffffff",
    success="#c8e6c9",
    warning="#fff9c4",
    danger="#ef9a9a",
    muted="#6e6e6e",
    bg_panel="#101010",
    text="#f5f5f5",
    gradient_start="#ffffff",
    gradient_end="#707070",
)

PALETTES: dict[str, Palette] = {p.name: p for p in (AURORA, CRIMSON, MONO)}


def get_palette(name: str) -> Palette:
    return PALETTES.get(name, AURORA)


def build_rich_theme(palette: Palette) -> Theme:
    """Build a rich.Theme so the rest of the app can use semantic style
    names (e.g. "pulsenet.primary") instead of hard-coded hex strings."""
    return Theme(
        {
            "pulsenet.primary": palette.primary,
            "pulsenet.secondary": palette.secondary,
            "pulsenet.accent": palette.accent,
            "pulsenet.success": palette.success,
            "pulsenet.warning": palette.warning,
            "pulsenet.danger": palette.danger,
            "pulsenet.muted": palette.muted,
            "pulsenet.text": palette.text,
            "pulsenet.title": f"bold {palette.primary}",
            "pulsenet.subtitle": f"italic {palette.muted}",
            "pulsenet.key": f"bold {palette.accent}",
            "pulsenet.value": palette.text,
        }
    )


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[max(0, min(255, c)) for c in rgb])


def interpolate_color(start_hex: str, end_hex: str, t: float) -> str:
    """Linearly interpolate between two hex colors at position t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = _hex_to_rgb(start_hex)
    r2, g2, b2 = _hex_to_rgb(end_hex)
    return _rgb_to_hex(
        (
            round(r1 + (r2 - r1) * t),
            round(g1 + (g2 - g1) * t),
            round(b1 + (b2 - b1) * t),
        )
    )


def gradient_stops(start_hex: str, end_hex: str, steps: int) -> list[str]:
    if steps <= 1:
        return [start_hex]
    return [interpolate_color(start_hex, end_hex, i / (steps - 1)) for i in range(steps)]
