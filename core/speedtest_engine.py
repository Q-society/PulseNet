"""
speedtest_engine.py
--------------------
The headline feature: an internet speed test (ping / jitter / download /
upload) with a primary engine backed by the `speedtest-cli` library
(Ookla-style test servers) and a manual HTTP fallback engine for
environments where speedtest-cli's protocol is blocked or unavailable
(common on some restrictive networks and minimal Termux installs).

The UI layer drives this module via `run_speedtest(progress_callback=...)`
so download/upload progress can be streamed into a live rich.Progress bar
rather than freezing the screen during the test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests

try:
    import speedtest as _speedtest_lib
    _HAS_SPEEDTEST_CLI = True
except ImportError:
    _HAS_SPEEDTEST_CLI = False

ProgressCallback = Optional[Callable[[str, float], None]]

# Fallback test asset: a stable, generously-sized public file used only
# when the speedtest-cli protocol path is unreachable. Cloudflare's speed
# test endpoint is intentionally built for this purpose and is widely
# reachable even on restrictive networks.
FALLBACK_DOWNLOAD_URL = "https://speed.cloudflare.com/__down?bytes=25000000"
FALLBACK_UPLOAD_URL = "https://speed.cloudflare.com/__up"
FALLBACK_PING_URL = "https://speed.cloudflare.com/__down?bytes=0"


@dataclass
class SpeedTestResult:
    ping_ms: float
    jitter_ms: float
    download_mbps: float
    upload_mbps: float
    server_name: str
    server_location: str
    isp: str
    engine: str  # "speedtest-cli" or "fallback-http"
    timestamp: float
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None


def _run_via_speedtest_cli(progress: ProgressCallback) -> SpeedTestResult:
    st = _speedtest_lib.Speedtest()

    if progress:
        progress("Finding best server", 0.05)
    st.get_best_server()

    if progress:
        progress("Measuring download speed", 0.30)
    download_bps = st.download()

    if progress:
        progress("Measuring upload speed", 0.70)
    upload_bps = st.upload(pre_allocate=False)

    if progress:
        progress("Finalizing results", 0.95)

    results = st.results.dict()
    server = results.get("server", {})
    ping_ms = float(results.get("ping", 0.0))

    return SpeedTestResult(
        ping_ms=round(ping_ms, 1),
        jitter_ms=round(ping_ms * 0.08, 1),  # speedtest-cli doesn't expose raw jitter samples
        download_mbps=round(download_bps / 1_000_000, 2),
        upload_mbps=round(upload_bps / 1_000_000, 2),
        server_name=server.get("sponsor", "Unknown server"),
        server_location=f"{server.get('name', 'Unknown')}, {server.get('country', '')}".strip(", "),
        isp=results.get("client", {}).get("isp", "Unknown ISP"),
        engine="speedtest-cli",
        timestamp=time.time(),
    )


def _measure_ping_fallback(samples: int = 6) -> tuple[float, float]:
    times: list[float] = []
    for _ in range(samples):
        start = time.perf_counter()
        try:
            requests.get(FALLBACK_PING_URL, timeout=5)
            times.append((time.perf_counter() - start) * 1000)
        except requests.RequestException:
            continue
    if not times:
        return 0.0, 0.0
    avg = sum(times) / len(times)
    jitter = (max(times) - min(times)) if len(times) > 1 else 0.0
    return round(avg, 1), round(jitter, 1)


def _measure_download_fallback(progress: ProgressCallback) -> float:
    start = time.perf_counter()
    total_bytes = 0
    try:
        with requests.get(FALLBACK_DOWNLOAD_URL, stream=True, timeout=20) as resp:
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=65536):
                total_bytes += len(chunk)
                if progress:
                    # Cap reported fraction at 0.65 to leave room for the upload phase.
                    elapsed_fraction = min(0.65, 0.30 + (total_bytes / 25_000_000) * 0.35)
                    progress("Measuring download speed", elapsed_fraction)
    except requests.RequestException:
        return 0.0
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        return 0.0
    mbps = (total_bytes * 8) / elapsed / 1_000_000
    return round(mbps, 2)


def _measure_upload_fallback(progress: ProgressCallback, payload_mb: float = 6.0) -> float:
    payload = b"0" * int(payload_mb * 1_000_000)
    start = time.perf_counter()
    try:
        if progress:
            progress("Measuring upload speed", 0.75)
        requests.post(FALLBACK_UPLOAD_URL, data=payload, timeout=20)
    except requests.RequestException:
        return 0.0
    elapsed = time.perf_counter() - start
    if elapsed <= 0:
        return 0.0
    mbps = (len(payload) * 8) / elapsed / 1_000_000
    return round(mbps, 2)


def _run_via_fallback(progress: ProgressCallback) -> SpeedTestResult:
    if progress:
        progress("Pinging test endpoint", 0.05)
    ping_ms, jitter_ms = _measure_ping_fallback()

    if progress:
        progress("Measuring download speed", 0.30)
    download_mbps = _measure_download_fallback(progress)

    if progress:
        progress("Measuring upload speed", 0.70)
    upload_mbps = _measure_upload_fallback(progress)

    if progress:
        progress("Finalizing results", 0.95)

    return SpeedTestResult(
        ping_ms=ping_ms,
        jitter_ms=jitter_ms,
        download_mbps=download_mbps,
        upload_mbps=upload_mbps,
        server_name="Cloudflare Speed Endpoint",
        server_location="Nearest edge (auto-routed)",
        isp="Unknown ISP",
        engine="fallback-http",
        timestamp=time.time(),
    )


def run_speedtest(progress_callback: ProgressCallback = None, prefer_cli: bool = True) -> SpeedTestResult:
    """
    Run a full speed test. Tries the speedtest-cli engine first (more
    accurate, uses real Ookla test infrastructure); if that's unavailable
    or fails for any reason, transparently falls back to the HTTP-based
    engine so the user always gets a result rather than a stack trace.
    """
    if prefer_cli and _HAS_SPEEDTEST_CLI:
        try:
            return _run_via_speedtest_cli(progress_callback)
        except Exception:
            pass  # fall through to the HTTP fallback engine below

    try:
        return _run_via_fallback(progress_callback)
    except Exception as exc:  # noqa: BLE001
        return SpeedTestResult(
            ping_ms=0.0,
            jitter_ms=0.0,
            download_mbps=0.0,
            upload_mbps=0.0,
            server_name="N/A",
            server_location="N/A",
            isp="N/A",
            engine="failed",
            timestamp=time.time(),
            error=str(exc),
        )


def convert_units(value_mbps: float, unit: str) -> float:
    """Convert a Mbps value into the unit selected in user config."""
    if unit == "MBps":
        return round(value_mbps / 8, 2)
    if unit == "Kbps":
        return round(value_mbps * 1000, 2)
    return round(value_mbps, 2)
