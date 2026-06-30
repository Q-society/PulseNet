"""
history_manager.py
-------------------
Persists speed test results to a small local SQLite database so users
can review trends over time. SQLite is part of the Python standard
library, so this works identically on Linux, Windows, macOS, and Termux
with zero extra dependencies.
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from core.speedtest_engine import SpeedTestResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS speed_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    ping_ms REAL NOT NULL,
    jitter_ms REAL NOT NULL,
    download_mbps REAL NOT NULL,
    upload_mbps REAL NOT NULL,
    server_name TEXT,
    server_location TEXT,
    isp TEXT,
    engine TEXT
);
"""


@dataclass
class HistoryEntry:
    id: int
    timestamp: float
    ping_ms: float
    jitter_ms: float
    download_mbps: float
    upload_mbps: float
    server_name: str
    server_location: str
    isp: str
    engine: str

    @property
    def formatted_date(self) -> str:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(self.timestamp))


class HistoryManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        try:
            with self._connect() as conn:
                conn.execute(SCHEMA)
        except sqlite3.Error:
            pass  # If the DB can't be created (read-only fs), history is simply disabled.

    def record(self, result: SpeedTestResult) -> bool:
        if not result.is_valid:
            return False
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO speed_history
                        (timestamp, ping_ms, jitter_ms, download_mbps, upload_mbps,
                         server_name, server_location, isp, engine)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.timestamp,
                        result.ping_ms,
                        result.jitter_ms,
                        result.download_mbps,
                        result.upload_mbps,
                        result.server_name,
                        result.server_location,
                        result.isp,
                        result.engine,
                    ),
                )
            return True
        except sqlite3.Error:
            return False

    def fetch_recent(self, limit: int = 20) -> list[HistoryEntry]:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT * FROM speed_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                )
                columns = [c[0] for c in cursor.description]
                return [HistoryEntry(**dict(zip(columns, row))) for row in cursor.fetchall()]
        except sqlite3.Error:
            return []

    def averages(self) -> dict[str, float]:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "SELECT AVG(ping_ms), AVG(download_mbps), AVG(upload_mbps), COUNT(*) FROM speed_history"
                )
                row = cursor.fetchone()
                if not row or row[3] == 0:
                    return {"ping": 0.0, "download": 0.0, "upload": 0.0, "count": 0}
                return {
                    "ping": round(row[0] or 0.0, 1),
                    "download": round(row[1] or 0.0, 2),
                    "upload": round(row[2] or 0.0, 2),
                    "count": row[3],
                }
        except sqlite3.Error:
            return {"ping": 0.0, "download": 0.0, "upload": 0.0, "count": 0}

    def clear(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("DELETE FROM speed_history")
            return True
        except sqlite3.Error:
            return False

    def count(self) -> int:
        try:
            with self._connect() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM speed_history")
                return cursor.fetchone()[0]
        except sqlite3.Error:
            return 0
