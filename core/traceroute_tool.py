"""
traceroute_tool.py
-------------------
Cross-platform traceroute wrapper. Uses `tracert` on Windows and
`traceroute`/`tracepath` on POSIX systems (chosen automatically by
utils.platform_utils.traceroute_command depending on what's installed --
this matters most on Termux, where `traceroute` isn't always present
but `tracepath` usually is).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from utils.platform_utils import PROFILE, run_silent, traceroute_command

_HOP_IP_PATTERN = re.compile(r"\(?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)?")
_HOP_TIME_PATTERN = re.compile(r"([\d.]+)\s*ms", re.IGNORECASE)


@dataclass
class Hop:
    number: int
    host: str
    ip: str
    time_ms: float | None


@dataclass
class TracerouteResult:
    target: str
    hops: list[Hop] = field(default_factory=list)
    success: bool = True
    error: str | None = None
    raw_output: str = ""


def _parse_line(line: str, hop_number: int) -> Hop | None:
    stripped = line.strip()
    if not stripped or not stripped[0].isdigit():
        return None

    parts = stripped.split()
    if not parts:
        return None

    try:
        number = int(parts[0])
    except ValueError:
        number = hop_number

    if "*" in stripped and not _HOP_IP_PATTERN.search(stripped):
        return Hop(number=number, host="*", ip="*", time_ms=None)

    ip_match = _HOP_IP_PATTERN.search(stripped)
    ip = ip_match.group(1) if ip_match else "Unknown"

    time_matches = _HOP_TIME_PATTERN.findall(stripped)
    avg_time = round(sum(float(t) for t in time_matches) / len(time_matches), 1) if time_matches else None

    # Hostname is usually the token right before the IP (or in parentheses).
    host = ip
    for token in parts[1:]:
        cleaned = token.strip("()")
        if cleaned and cleaned != ip and not re.match(r"^[\d.]+ms$", cleaned, re.IGNORECASE) and cleaned != "*":
            if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", cleaned):
                host = cleaned
                break

    return Hop(number=number, host=host, ip=ip, time_ms=avg_time)


def trace_route(target: str, max_hops: int = 30, timeout: float = 60.0) -> TracerouteResult:
    if not target or not target.strip():
        return TracerouteResult(target=target, success=False, error="No target provided.")

    argv = traceroute_command(target, max_hops)
    returncode, stdout, stderr = run_silent(argv, timeout=timeout)

    if returncode == 127:
        return TracerouteResult(
            target=target,
            success=False,
            error=(
                "No traceroute utility found. On Termux, try: pkg install traceroute"
                if PROFILE.is_termux
                else "No traceroute/tracert utility found on this system."
            ),
        )

    combined = stdout + stderr
    hops: list[Hop] = []
    for i, line in enumerate(combined.splitlines(), start=1):
        hop = _parse_line(line, i)
        if hop:
            hops.append(hop)

    if not hops:
        return TracerouteResult(
            target=target, success=False, error="No route data returned (host may block traceroute probes).",
            raw_output=combined,
        )

    return TracerouteResult(target=target, hops=hops, success=True, raw_output=combined)
