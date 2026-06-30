"""
widgets.py
----------
Reusable rich UI building blocks shared across every feature screen:
section headers, key/value tables, stat cards, status badges, and the
bordered result panel that gives every tool's output a consistent,
"designed" appearance instead of looking like raw print statements.
"""

from __future__ import annotations

from typing import Any, Iterable

from rich.align import Align
from rich.columns import Columns
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ui.theme import Palette


def section_title(palette: Palette, label: str, icon: str = "▸") -> Text:
    text = Text()
    text.append(f"{icon} ", style=f"bold {palette.accent}")
    text.append(label.upper(), style=f"bold {palette.primary}")
    return text


def kv_table(
    palette: Palette,
    rows: Iterable[tuple[str, Any]],
    key_width: int = 22,
) -> Table:
    """A borderless key/value table -- the workhorse for displaying
    structured results (network info, system info, dns records, etc.)."""
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left", min_width=key_width, style=f"bold {palette.muted}")
    table.add_column(justify="left", style=palette.text)
    for key, value in rows:
        table.add_row(str(key), str(value))
    return table


def result_panel(
    palette: Palette,
    title: str,
    content: RenderableType,
    subtitle: str = "",
    border_style: str | None = None,
) -> Panel:
    return Panel(
        content,
        title=f"[bold {palette.primary}]{title}[/]",
        subtitle=f"[italic {palette.muted}]{subtitle}[/]" if subtitle else None,
        border_style=border_style or palette.secondary,
        padding=(1, 2),
        expand=True,
    )


def stat_card(palette: Palette, label: str, value: str, unit: str = "", accent: str | None = None) -> Panel:
    """A small boxed statistic, e.g. used for Download / Upload / Ping in
    the speed test summary -- three of these rendered side by side via
    rich.columns.Columns gives a dashboard-like result row."""
    color = accent or palette.accent
    body = Text(justify="center")
    body.append(f"{value}", style=f"bold {color}")
    if unit:
        body.append(f" {unit}", style=f"{palette.muted}")
    body.append("\n")
    body.append(label.upper(), style=f"{palette.muted}")
    return Panel(Align.center(body), border_style=color, padding=(1, 3))


def stat_row(cards: list[Panel]) -> Columns:
    return Columns(cards, equal=True, expand=True)


def status_badge(palette: Palette, ok: bool, label_ok: str = "OPEN", label_fail: str = "CLOSED") -> Text:
    if ok:
        return Text(f" {label_ok} ", style=f"bold white on {palette.success}")
    return Text(f" {label_fail} ", style=f"bold white on {palette.danger}")


def bullet_list(palette: Palette, items: Iterable[str], bullet: str = "•") -> Text:
    text = Text()
    for item in items:
        text.append(f"{bullet} ", style=f"bold {palette.accent}")
        text.append(f"{item}\n", style=palette.text)
    return text


def warning_box(palette: Palette, message: str) -> Panel:
    return Panel(
        Text(message, style=f"bold {palette.warning}"),
        title="[bold]⚠ NOTICE[/]",
        border_style=palette.warning,
        padding=(0, 2),
    )


def error_box(palette: Palette, message: str) -> Panel:
    return Panel(
        Text(message, style=f"bold {palette.danger}"),
        title="[bold]✕ ERROR[/]",
        border_style=palette.danger,
        padding=(0, 2),
    )


def success_box(palette: Palette, message: str) -> Panel:
    return Panel(
        Text(message, style=f"bold {palette.success}"),
        title="[bold]✓ SUCCESS[/]",
        border_style=palette.success,
        padding=(0, 2),
    )


def render_table(
    palette: Palette,
    columns: list[str],
    rows: list[list[str]],
    title: str = "",
) -> Table:
    table = Table(
        title=f"[bold {palette.primary}]{title}[/]" if title else None,
        border_style=palette.secondary,
        header_style=f"bold {palette.accent}",
        expand=True,
    )
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)
    return table


def print_centered(console: Console, renderable: RenderableType) -> None:
    console.print(Align.center(renderable))
