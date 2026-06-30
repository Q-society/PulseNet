"""
config.py
---------
Persistent configuration storage for PulseNet.

Settings are stored as JSON in a platform-appropriate config directory
(resolved by utils.platform_utils). The config layer never throws on
missing or corrupted files -- it always falls back to sane defaults so
a damaged config can never prevent the app from starting.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from utils.platform_utils import PROFILE, ensure_dir

CONFIG_FILENAME = "config.json"
DEFAULT_UNITS = "Mbps"
SUPPORTED_UNITS = ("Mbps", "MBps", "Kbps")
DEFAULT_THEME = "aurora"
SUPPORTED_THEMES = ("aurora", "crimson", "mono")


@dataclass
class AppConfig:
    theme: str = DEFAULT_THEME
    units: str = DEFAULT_UNITS
    ping_count: int = 4
    traceroute_max_hops: int = 30
    port_scan_timeout: float = 0.6
    save_history: bool = True
    show_splash: bool = True
    animation_speed: float = 1.0  # multiplier; 0.5 = faster, 2.0 = slower
    last_scanned_host: str = ""
    history_limit: int = 200
    auto_export_format: str = "json"

    def validate(self) -> "AppConfig":
        """Clamp/repair any out-of-range values coming from a hand-edited file."""
        if self.units not in SUPPORTED_UNITS:
            self.units = DEFAULT_UNITS
        if self.theme not in SUPPORTED_THEMES:
            self.theme = DEFAULT_THEME
        self.ping_count = max(1, min(self.ping_count, 50))
        self.traceroute_max_hops = max(1, min(self.traceroute_max_hops, 64))
        self.port_scan_timeout = max(0.1, min(self.port_scan_timeout, 5.0))
        self.animation_speed = max(0.1, min(self.animation_speed, 5.0))
        self.history_limit = max(10, min(self.history_limit, 5000))
        if self.auto_export_format not in ("json", "csv", "txt"):
            self.auto_export_format = "json"
        return self


class ConfigManager:
    """
    Thin wrapper around AppConfig that knows how to read/write itself to
    disk. Kept separate from the dataclass so AppConfig stays a plain,
    test-friendly data object.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = ensure_dir(config_dir or PROFILE.config_dir)
        self.config_path = self.config_dir / CONFIG_FILENAME
        self.config: AppConfig = self._load()

    def _load(self) -> AppConfig:
        if not self.config_path.exists():
            cfg = AppConfig()
            self._write(cfg)
            return cfg
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            known_fields = {f for f in AppConfig.__dataclass_fields__}
            filtered: dict[str, Any] = {k: v for k, v in raw.items() if k in known_fields}
            return AppConfig(**filtered).validate()
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            # Corrupted or hand-edited config -- don't crash, just reset.
            cfg = AppConfig()
            self._write(cfg)
            return cfg

    def _write(self, cfg: AppConfig) -> None:
        try:
            self.config_path.write_text(
                json.dumps(asdict(cfg), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            # If the filesystem is read-only (some Termux/containers), the
            # app should keep running with in-memory settings only.
            pass

    def save(self) -> None:
        self.config.validate()
        self._write(self.config)

    def update(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save()

    def reset(self) -> None:
        self.config = AppConfig()
        self.save()

    @property
    def history_path(self) -> Path:
        return self.config_dir / "history.db"

    @property
    def export_dir(self) -> Path:
        return ensure_dir(self.config_dir / "exports")

    @property
    def log_path(self) -> Path:
        return ensure_dir(self.config_dir / "logs") / "pulsenet.log"
