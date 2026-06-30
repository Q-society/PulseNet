"""
whois_tool.py
-------------
Domain WHOIS / RDAP lookups. Tries the `python-whois` library first
(classic WHOIS protocol, rich field set); if that's unavailable or the
registry blocks the query, falls back to RDAP over plain HTTPS via
rdap.org, which works almost everywhere firewalls would block raw
WHOIS's port 43.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import requests

try:
    import whois as _whois_lib
    _HAS_PYTHON_WHOIS = True
except ImportError:
    _HAS_PYTHON_WHOIS = False

RDAP_TEMPLATE = "https://rdap.org/domain/{domain}"
REQUEST_TIMEOUT = 8


@dataclass
class WhoisResult:
    domain: str
    registrar: str = "Unavailable"
    creation_date: str = "Unavailable"
    expiration_date: str = "Unavailable"
    updated_date: str = "Unavailable"
    name_servers: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    raw_source: str = ""  # "python-whois" or "rdap"
    success: bool = True
    error: str | None = None


def _stringify_date(value) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, list):
        value = value[0] if value else None
    return str(value) if value else "Unavailable"


def _lookup_via_python_whois(domain: str) -> WhoisResult | None:
    try:
        data = _whois_lib.whois(domain)
    except Exception:
        return None

    if not data or not getattr(data, "domain_name", None):
        return None

    name_servers = data.name_servers or []
    if isinstance(name_servers, str):
        name_servers = [name_servers]

    status = data.status or []
    if isinstance(status, str):
        status = [status]

    return WhoisResult(
        domain=domain,
        registrar=data.registrar or "Unavailable",
        creation_date=_stringify_date(data.creation_date),
        expiration_date=_stringify_date(data.expiration_date),
        updated_date=_stringify_date(data.updated_date),
        name_servers=[str(ns).lower() for ns in name_servers],
        status=[str(s) for s in status],
        raw_source="python-whois",
        success=True,
    )


def _extract_rdap_event(events: list[dict], action: str) -> str:
    for event in events:
        if event.get("eventAction") == action:
            return event.get("eventDate", "Unavailable")
    return "Unavailable"


def _lookup_via_rdap(domain: str) -> WhoisResult:
    url = RDAP_TEMPLATE.format(domain=domain)
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"Accept": "application/rdap+json"})
        if response.status_code == 404:
            return WhoisResult(domain=domain, success=False, error="Domain not found in RDAP registry.")
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return WhoisResult(domain=domain, success=False, error=f"Network error: {exc}")
    except ValueError as exc:
        return WhoisResult(domain=domain, success=False, error=f"Invalid RDAP response: {exc}")

    events = data.get("events", [])
    nameservers = [ns.get("ldhName", "").lower() for ns in data.get("nameservers", []) if ns.get("ldhName")]
    registrar = "Unavailable"
    for entity in data.get("entities", []):
        if "registrar" in entity.get("roles", []):
            vcard = entity.get("vcardArray", [])
            if len(vcard) > 1:
                for field_entry in vcard[1]:
                    if field_entry[0] == "fn":
                        registrar = field_entry[3]
                        break
            break

    return WhoisResult(
        domain=domain,
        registrar=registrar,
        creation_date=_extract_rdap_event(events, "registration"),
        expiration_date=_extract_rdap_event(events, "expiration"),
        updated_date=_extract_rdap_event(events, "last changed"),
        name_servers=nameservers,
        status=data.get("status", []),
        raw_source="rdap",
        success=True,
    )


def lookup_whois(domain: str) -> WhoisResult:
    domain = domain.strip().lower()
    if not domain:
        return WhoisResult(domain=domain, success=False, error="No domain provided.")

    if _HAS_PYTHON_WHOIS:
        result = _lookup_via_python_whois(domain)
        if result is not None:
            return result

    return _lookup_via_rdap(domain)
