"""
logger.py
---------
Lightweight rotating-ish file logger. PulseNet is a visual TUI app, so
errors should never be printed raw into the middle of a rendered screen --
they get written here instead, and the UI shows a short, friendly notice
pointing at this file.
"""

from __future__ import annotations

import datetime as _dt
import traceback
from pathlib import Path

_MAX_LOG_BYTES = 1_000_000  # rotate at ~1 MB, keep things lightweight


class AppLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_if_needed(self) -> None:
        try:
            if self.log_path.exists() and self.log_path.stat().st_size > _MAX_LOG_BYTES:
                backup = self.log_path.with_suffix(".log.old")
                self.log_path.replace(backup)
        except OSError:
            pass

    def _write(self, level: str, message: str) -> None:
        self._rotate_if_needed()
        timestamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}\n"
        try:
            with open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass  # Read-only filesystem edge case -- never let logging crash the app.

    def info(self, message: str) -> None:
        self._write("INFO", message)

    def warning(self, message: str) -> None:
        self._write("WARN", message)

    def error(self, message: str, exc: BaseException | None = None) -> None:
        if exc is not None:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            message = f"{message}\n{tb}"
        self._write("ERROR", message)

    def tail(self, lines: int = 30) -> list[str]:
        if not self.log_path.exists():
            return []
        try:
            content = self.log_path.read_text(encoding="utf-8").splitlines()
            return content[-lines:]
        except OSError:
            return []
