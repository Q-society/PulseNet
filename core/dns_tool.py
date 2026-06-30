"""
dns_tool.py
-----------
DNS resolution utilities: forward lookups for A/AAAA/MX/TXT/NS/CNAME
records (via dnspython when available, with a socket-only fallback for
A records so the feature never fully disappears if dnspython is missing),
plus reverse DNS lookups.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass, field

try:
    import dns.resolver
    _HAS_DNSPYTHON = True
except ImportError:
    _HAS_DNSPYTHON = False

RECORD_TYPES = ("A", "AAAA", "MX", "TXT", "NS", "CNAME")
LOOKUP_TIMEOUT = 6.0


@dataclass
class DNSRecordSet:
    record_type: str
    values: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class DNSLookupResult:
    domain: str
    records: list[DNSRecordSet] = field(default_factory=list)


@dataclass
class ReverseDNSResult:
    ip: str
    hostname: str | None
    success: bool
    error: str | None = None


def _lookup_with_dnspython(domain: str, record_type: str) -> DNSRecordSet:
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = LOOKUP_TIMEOUT
        resolver.lifetime = LOOKUP_TIMEOUT
        answer = resolver.resolve(domain, record_type)
        values = [str(rdata).strip('"') for rdata in answer]
        return DNSRecordSet(record_type=record_type, values=values)
    except dns.resolver.NXDOMAIN:
        return DNSRecordSet(record_type=record_type, error="Domain does not exist.")
    except dns.resolver.NoAnswer:
        return DNSRecordSet(record_type=record_type, error="No records of this type.")
    except dns.exception.Timeout:
        return DNSRecordSet(record_type=record_type, error="Lookup timed out.")
    except Exception as exc:  # noqa: BLE001
        return DNSRecordSet(record_type=record_type, error=str(exc))


def _lookup_a_fallback(domain: str) -> DNSRecordSet:
    """Used only when dnspython isn't installed -- covers the most common
    case (A records) using nothing but the standard library."""
    try:
        _, _, addresses = socket.gethostbyname_ex(domain)
        return DNSRecordSet(record_type="A", values=addresses)
    except socket.gaierror as exc:
        return DNSRecordSet(record_type="A", error=str(exc))


def lookup_domain(domain: str, record_types: tuple[str, ...] = RECORD_TYPES) -> DNSLookupResult:
    domain = domain.strip()
    records: list[DNSRecordSet] = []

    if not _HAS_DNSPYTHON:
        records.append(_lookup_a_fallback(domain))
        records.append(
            DNSRecordSet(
                record_type="info",
                error="Install 'dnspython' for AAAA/MX/TXT/NS/CNAME support.",
            )
        )
        return DNSLookupResult(domain=domain, records=records)

    for record_type in record_types:
        records.append(_lookup_with_dnspython(domain, record_type))

    return DNSLookupResult(domain=domain, records=records)


def reverse_lookup(ip: str) -> ReverseDNSResult:
    try:
        hostname, _, _ = socket.gethostbyaddr(ip.strip())
        return ReverseDNSResult(ip=ip, hostname=hostname, success=True)
    except socket.herror:
        return ReverseDNSResult(ip=ip, hostname=None, success=False, error="No PTR record found.")
    except socket.gaierror as exc:
        return ReverseDNSResult(ip=ip, hostname=None, success=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001
        return ReverseDNSResult(ip=ip, hostname=None, success=False, error=str(exc))
