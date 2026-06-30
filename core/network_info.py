"""
network_info.py
----------------
Gathers local and public network information: local IP, hostname,
active interfaces, default gateway (best-effort), and public IP / ISP /
location via a free public API. Every external call is wrapped so a
missing dependency or offline state degrades to "Unavailable" instead
of crashing the screen.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field

import requests

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

REQUEST_TIMEOUT = 6
PUBLIC_IP_API = "https://ip-api.com/json/?fields=status,message,query,country,regionName,city,isp,org,as,lat,lon,timezone"


@dataclass
class InterfaceInfo:
    name: str
    addresses: list[str] = field(default_factory=list)
    is_up: bool = False
    speed_mbps: int | None = None


@dataclass
class PublicIPInfo:
    ip: str = "Unavailable"
    country: str = "Unavailable"
    region: str = "Unavailable"
    city: str = "Unavailable"
    isp: str = "Unavailable"
    org: str = "Unavailable"
    asn: str = "Unavailable"
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "Unavailable"
    error: str | None = None


@dataclass
class NetworkInfoResult:
    hostname: str
    local_ip: str
    interfaces: list[InterfaceInfo]
    public: PublicIPInfo


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "Unknown"


def get_local_ip() -> str:
    """
    The classic 'connect a UDP socket to a public address without sending
    anything' trick -- it never actually transmits a packet, it just asks
    the OS routing table which local interface/IP would be used, which is
    a reliable way to find the active local IP across every platform.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "Unavailable"


def get_interfaces() -> list[InterfaceInfo]:
    """
    Returns interface details via psutil when available. On systems where
    psutil failed to install (some constrained Termux setups), we fall
    back to a single synthetic entry built from get_local_ip() so the UI
    still has something meaningful to show.
    """
    if not _HAS_PSUTIL:
        return [InterfaceInfo(name="default", addresses=[get_local_ip()], is_up=True)]

    results: list[InterfaceInfo] = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for name, addr_list in addrs.items():
            ipv4_addrs = [a.address for a in addr_list if a.family == socket.AF_INET]
            if not ipv4_addrs:
                continue
            stat = stats.get(name)
            results.append(
                InterfaceInfo(
                    name=name,
                    addresses=ipv4_addrs,
                    is_up=bool(stat.isup) if stat else False,
                    speed_mbps=stat.speed if stat and stat.speed > 0 else None,
                )
            )
    except Exception:
        return [InterfaceInfo(name="default", addresses=[get_local_ip()], is_up=True)]

    return results or [InterfaceInfo(name="default", addresses=[get_local_ip()], is_up=True)]


def get_public_ip_info() -> PublicIPInfo:
    try:
        response = requests.get(PUBLIC_IP_API, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "success":
            return PublicIPInfo(error=data.get("message", "Lookup failed"))
        return PublicIPInfo(
            ip=data.get("query", "Unavailable"),
            country=data.get("country", "Unavailable"),
            region=data.get("regionName", "Unavailable"),
            city=data.get("city", "Unavailable"),
            isp=data.get("isp", "Unavailable"),
            org=data.get("org", "Unavailable"),
            asn=data.get("as", "Unavailable"),
            latitude=data.get("lat"),
            longitude=data.get("lon"),
            timezone=data.get("timezone", "Unavailable"),
        )
    except requests.RequestException as exc:
        return PublicIPInfo(error=f"Network error: {exc}")
    except (ValueError, KeyError) as exc:
        return PublicIPInfo(error=f"Could not parse response: {exc}")


def gather_network_info() -> NetworkInfoResult:
    return NetworkInfoResult(
        hostname=get_hostname(),
        local_ip=get_local_ip(),
        interfaces=get_interfaces(),
        public=get_public_ip_info(),
    )
