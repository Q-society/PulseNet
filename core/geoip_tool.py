"""
geoip_tool.py
-------------
IP geolocation lookups via the free ip-api.com endpoint (no API key
required, generous rate limits for non-commercial use). Works for both
a specified IP/host and, when no input is given, for the caller's own
public IP.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass

import requests

REQUEST_TIMEOUT = 6
API_TEMPLATE = (
    "https://ip-api.com/json/{target}"
    "?fields=status,message,query,country,countryCode,regionName,city,zip,"
    "lat,lon,timezone,isp,org,as,mobile,proxy,hosting"
)


@dataclass
class GeoIPResult:
    query: str
    ip: str = "Unavailable"
    country: str = "Unavailable"
    country_code: str = "--"
    region: str = "Unavailable"
    city: str = "Unavailable"
    zip_code: str = "Unavailable"
    latitude: float | None = None
    longitude: float | None = None
    timezone: str = "Unavailable"
    isp: str = "Unavailable"
    org: str = "Unavailable"
    asn: str = "Unavailable"
    is_mobile: bool = False
    is_proxy: bool = False
    is_hosting: bool = False
    success: bool = True
    error: str | None = None


def _resolve_to_ip_if_needed(target: str) -> str:
    """ip-api accepts hostnames directly, but resolving locally first gives
    a clearer error message when DNS itself is the problem."""
    target = target.strip()
    if not target:
        return ""
    try:
        socket.inet_aton(target)
        return target  # already a valid IPv4 literal
    except OSError:
        pass
    try:
        return socket.gethostbyname(target)
    except socket.gaierror:
        return target  # let the API surface its own error message


def lookup_ip(target: str = "") -> GeoIPResult:
    resolved = _resolve_to_ip_if_needed(target) if target else ""
    url = API_TEMPLATE.format(target=resolved)

    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return GeoIPResult(query=target or "self", success=False, error=f"Network error: {exc}")
    except ValueError as exc:
        return GeoIPResult(query=target or "self", success=False, error=f"Invalid response: {exc}")

    if data.get("status") != "success":
        return GeoIPResult(
            query=target or "self",
            success=False,
            error=data.get("message", "Lookup failed."),
        )

    return GeoIPResult(
        query=target or "self",
        ip=data.get("query", "Unavailable"),
        country=data.get("country", "Unavailable"),
        country_code=data.get("countryCode", "--"),
        region=data.get("regionName", "Unavailable"),
        city=data.get("city", "Unavailable"),
        zip_code=data.get("zip", "Unavailable") or "N/A",
        latitude=data.get("lat"),
        longitude=data.get("lon"),
        timezone=data.get("timezone", "Unavailable"),
        isp=data.get("isp", "Unavailable"),
        org=data.get("org", "Unavailable"),
        asn=data.get("as", "Unavailable"),
        is_mobile=bool(data.get("mobile", False)),
        is_proxy=bool(data.get("proxy", False)),
        is_hosting=bool(data.get("hosting", False)),
        success=True,
    )
