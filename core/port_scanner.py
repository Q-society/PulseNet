"""
port_scanner.py
----------------
A basic TCP-connect port checker for network troubleshooting -- e.g.
confirming that a web server you administer has port 443 open, or that
a database port is reachable from a given host. This performs simple
connect() probes against a curated list of well-known ports; it does not
perform banner grabbing, OS fingerprinting, or any exploit activity.

Intended use: diagnosing hosts and networks you own or are authorized to
test. Scanning systems without authorization may be illegal in your
jurisdiction -- that responsibility sits with whoever runs the tool.
"""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

COMMON_PORTS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    119: "NNTP",
    123: "NTP",
    143: "IMAP",
    161: "SNMP",
    389: "LDAP",
    443: "HTTPS",
    445: "SMB",
    465: "SMTPS",
    587: "SMTP (Submission)",
    993: "IMAPS",
    995: "POP3S",
    1433: "MSSQL",
    1521: "Oracle DB",
    2222: "SSH (Alt)",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
    6379: "Redis",
    8080: "HTTP (Alt)",
    8443: "HTTPS (Alt)",
    9200: "Elasticsearch",
    27017: "MongoDB",
}

MAX_WORKERS = 40


@dataclass
class PortResult:
    port: int
    service: str
    is_open: bool


@dataclass
class PortScanResult:
    host: str
    resolved_ip: str
    results: list[PortResult] = field(default_factory=list)
    success: bool = True
    error: str | None = None

    @property
    def open_ports(self) -> list[PortResult]:
        return [r for r in self.results if r.is_open]


def _check_port(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except (socket.gaierror, socket.timeout, OSError):
        return False


def scan_ports(
    host: str,
    ports: dict[int, str] | None = None,
    timeout: float = 0.6,
) -> PortScanResult:
    host = host.strip()
    if not host:
        return PortScanResult(host=host, resolved_ip="N/A", success=False, error="No host provided.")

    try:
        resolved_ip = socket.gethostbyname(host)
    except socket.gaierror:
        return PortScanResult(
            host=host, resolved_ip="Unresolved", success=False,
            error="Could not resolve hostname.",
        )

    target_ports = ports or COMMON_PORTS
    results: list[PortResult] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_to_port = {
            pool.submit(_check_port, resolved_ip, port, timeout): (port, service)
            for port, service in target_ports.items()
        }
        for future in as_completed(future_to_port):
            port, service = future_to_port[future]
            is_open = future.result()
            results.append(PortResult(port=port, service=service, is_open=is_open))

    results.sort(key=lambda r: r.port)
    return PortScanResult(host=host, resolved_ip=resolved_ip, results=results, success=True)


def scan_single_port(host: str, port: int, timeout: float = 1.5) -> PortResult:
    is_open = _check_port(host, port, timeout)
    service = COMMON_PORTS.get(port, "Unknown")
    return PortResult(port=port, service=service, is_open=is_open)
