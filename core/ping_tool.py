"""
ping_tool.py
------------
Cross-platform ping wrapper. Shells out to the OS's native `ping` binary
(via utils.platform_utils.ping_command, which already knows the right
flags per-OS) and parses the textual output into structured data, since
each platform's ping output format differs slightly.
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, field

from utils.platform_utils import PROFILE, ping_command, run_silent

# Matches "time=12.3 ms" / "time<1ms" (Windows) / "time=12.3ms" (Linux/mac) loosely.
_TIME_PATTERN = re.compile(r"time[=<]\s*([\d.]+)\s*ms", re.IGNORECASE)
_LOSS_PATTERN_POSIX = re.compile(r"(\d+)%\s+packet loss")
_LOSS_PATTERN_WINDOWS = re.compile(r"\((\d+)%\s+loss\)")


@dataclass
class PingResult:
    host: str
    resolved_ip: str
    sent: int
    received: int
    loss_percent: float
    min_ms: float
    avg_ms: float
    max_ms: float
    raw_times: list[float] = field(default_factory=list)
    success: bool = True
    error: str | None = None


def _resolve_host(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except socket.gaierror:
        return "Unresolved"


def _parse_times(output: str) -> list[float]:
    return [float(m) for m in _TIME_PATTERN.findall(output)]


def _parse_loss(output: str, sent: int, received: int) -> float:
    pattern = _LOSS_PATTERN_WINDOWS if PROFILE.is_windows else _LOSS_PATTERN_POSIX
    match = pattern.search(output)
    if match:
        return float(match.group(1))
    if sent == 0:
        return 100.0
    return round((1 - received / sent) * 100, 1)


def _count_received(output: str, sent: int, times: list[float]) -> int:
    """
    We primarily trust the number of parsed `time=` matches as the received
    count, since it's consistent across platforms. As a sanity fallback we
    never report more received than sent.
    """
    return min(len(times), sent)


def ping_host(host: str, count: int = 4, timeout: float = 15.0) -> PingResult:
    if not host or not host.strip():
        return PingResult(
            host=host, resolved_ip="N/A", sent=0, received=0, loss_percent=100.0,
            min_ms=0.0, avg_ms=0.0, max_ms=0.0, success=False,
            error="No host provided.",
        )

    resolved_ip = _resolve_host(host)
    argv = ping_command(host, count)
    returncode, stdout, stderr = run_silent(argv, timeout=timeout + count * 1.5)

    if returncode == 127:
        return PingResult(
            host=host, resolved_ip=resolved_ip, sent=count, received=0, loss_percent=100.0,
            min_ms=0.0, avg_ms=0.0, max_ms=0.0, success=False,
            error="The 'ping' utility was not found on this system.",
        )

    combined_output = stdout + stderr
    times = _parse_times(combined_output)
    received = _count_received(combined_output, count, times)
    loss = _parse_loss(combined_output, count, received)

    if not times:
        return PingResult(
            host=host, resolved_ip=resolved_ip, sent=count, received=0, loss_percent=100.0,
            min_ms=0.0, avg_ms=0.0, max_ms=0.0, success=False,
            error="Host unreachable or did not respond.",
        )

    return PingResult(
        host=host,
        resolved_ip=resolved_ip,
        sent=count,
        received=received,
        loss_percent=loss,
        min_ms=round(min(times), 1),
        avg_ms=round(sum(times) / len(times), 1),
        max_ms=round(max(times), 1),
        raw_times=times,
        success=True,
    )
