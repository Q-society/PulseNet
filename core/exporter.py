"""
exporter.py
-----------
Exports speed test results and history snapshots to TXT, JSON, or CSV
files inside the user's config directory. Keeping export logic in one
place ensures every export goes through the same naming/timestamp
convention and the same error handling.
"""

from __future__ import annotations

import csv
import json
import time
from dataclasses import asdict
from pathlib import Path

from core.history_manager import HistoryEntry
from core.speedtest_engine import SpeedTestResult

SUPPORTED_FORMATS = ("json", "csv", "txt")


def _timestamped_filename(prefix: str, extension: str) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.{extension}"


def export_single_result(result: SpeedTestResult, export_dir: Path, fmt: str = "json") -> Path | None:
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        fmt = "json"

    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _timestamped_filename("pulsenet_speedtest", fmt)
    path = export_dir / filename

    try:
        if fmt == "json":
            path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")
        elif fmt == "csv":
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                data = asdict(result)
                writer.writerow(data.keys())
                writer.writerow(data.values())
        else:  # txt
            lines = [
                "PulseNet Speed Test Report",
                "=" * 32,
                f"Timestamp     : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(result.timestamp))}",
                f"Ping          : {result.ping_ms} ms",
                f"Jitter        : {result.jitter_ms} ms",
                f"Download      : {result.download_mbps} Mbps",
                f"Upload        : {result.upload_mbps} Mbps",
                f"Server        : {result.server_name}",
                f"Location      : {result.server_location}",
                f"ISP           : {result.isp}",
                f"Engine        : {result.engine}",
            ]
            path.write_text("\n".join(lines), encoding="utf-8")
        return path
    except OSError:
        return None


def export_history(entries: list[HistoryEntry], export_dir: Path, fmt: str = "csv") -> Path | None:
    fmt = fmt.lower()
    if fmt not in SUPPORTED_FORMATS:
        fmt = "csv"

    export_dir.mkdir(parents=True, exist_ok=True)
    filename = _timestamped_filename("pulsenet_history", fmt)
    path = export_dir / filename

    try:
        if fmt == "json":
            path.write_text(
                json.dumps([asdict(e) for e in entries], indent=2),
                encoding="utf-8",
            )
        elif fmt == "csv":
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                if entries:
                    writer.writerow(asdict(entries[0]).keys())
                    for entry in entries:
                        writer.writerow(asdict(entry).values())
        else:  # txt
            lines = ["PulseNet History Export", "=" * 32]
            for e in entries:
                lines.append(
                    f"{e.formatted_date} | Ping {e.ping_ms}ms | "
                    f"Down {e.download_mbps}Mbps | Up {e.upload_mbps}Mbps | {e.server_name}"
                )
            path.write_text("\n".join(lines), encoding="utf-8")
        return path
    except OSError:
        return None
