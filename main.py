#!/usr/bin/env python3
"""
main.py
-------
PulseNet entry point.

Two modes of operation:
  1. Interactive mode (no arguments): shows the splash screen and the
     full menu-driven dashboard.
  2. Direct command mode (e.g. `python main.py speedtest`): runs a single
     tool non-interactively and exits, useful for scripting or quick
     terminal use without entering the full UI.

Run `python main.py --help` to see all direct commands.
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from core import dns_tool, geoip_tool, network_info, ping_tool, port_scanner, speedtest_engine, system_info, traceroute_tool, whois_tool
from ui import widgets
from ui.animations import boot_sequence
from ui.banner import render_splash
from ui.menu import APP_VERSION, AppContext, run_menu_loop
from ui.theme import get_palette
from utils.config import ConfigManager
from utils.platform_utils import PROFILE, clear_screen


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pulsenet",
        description="PulseNet — Premium Network Diagnostics Suite",
    )
    parser.add_argument("--version", action="version", version=f"PulseNet {APP_VERSION}")
    parser.add_argument("--no-splash", action="store_true", help="Skip the startup animation in interactive mode")

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("speedtest", help="Run a one-off internet speed test and exit")

    ping_parser = subparsers.add_parser("ping", help="Ping a host and exit")
    ping_parser.add_argument("host", help="Hostname or IP address to ping")
    ping_parser.add_argument("-c", "--count", type=int, default=4, help="Number of pings to send")

    trace_parser = subparsers.add_parser("traceroute", help="Trace the route to a host and exit")
    trace_parser.add_argument("host", help="Destination hostname or IP")

    dns_parser = subparsers.add_parser("dns", help="Resolve DNS records for a domain and exit")
    dns_parser.add_argument("domain", help="Domain name to resolve")

    geoip_parser = subparsers.add_parser("geoip", help="Look up the location of an IP/host and exit")
    geoip_parser.add_argument("target", nargs="?", default="", help="IP or hostname (blank = your own IP)")

    whois_parser = subparsers.add_parser("whois", help="Look up domain WHOIS/RDAP info and exit")
    whois_parser.add_argument("domain", help="Domain name to query")

    scan_parser = subparsers.add_parser("scan", help="Scan common ports on a host you control, then exit")
    scan_parser.add_argument("host", help="Host or IP to scan")

    subparsers.add_parser("sysinfo", help="Print local system information and exit")
    subparsers.add_parser("netinfo", help="Print local + public network information and exit")

    return parser


def _run_direct_command(args: argparse.Namespace) -> int:
    console = Console()
    config = ConfigManager()
    palette = get_palette(config.config.theme)

    if args.command == "speedtest":
        console.print(f"[{palette.primary}]Running speed test...[/]")
        result = speedtest_engine.run_speedtest()
        if not result.is_valid:
            console.print(widgets.error_box(palette, result.error or "Speed test failed."))
            return 1
        rows = [
            ("Ping", f"{result.ping_ms} ms"), ("Jitter", f"{result.jitter_ms} ms"),
            ("Download", f"{result.download_mbps} Mbps"), ("Upload", f"{result.upload_mbps} Mbps"),
            ("Server", result.server_name), ("Engine", result.engine),
        ]
        console.print(widgets.result_panel(palette, "Speed Test Result", widgets.kv_table(palette, rows)))
        return 0

    if args.command == "ping":
        result = ping_tool.ping_host(args.host, count=args.count)
        if not result.success:
            console.print(widgets.error_box(palette, result.error or "Ping failed."))
            return 1
        rows = [
            ("Target", f"{result.host} ({result.resolved_ip})"),
            ("Loss", f"{result.loss_percent}%"),
            ("Min/Avg/Max", f"{result.min_ms}/{result.avg_ms}/{result.max_ms} ms"),
        ]
        console.print(widgets.result_panel(palette, "Ping Result", widgets.kv_table(palette, rows)))
        return 0

    if args.command == "traceroute":
        result = traceroute_tool.trace_route(args.host)
        if not result.success:
            console.print(widgets.error_box(palette, result.error or "Traceroute failed."))
            return 1
        rows = [[str(h.number), h.host, h.ip, f"{h.time_ms} ms" if h.time_ms else "*"] for h in result.hops]
        console.print(widgets.render_table(palette, ["Hop", "Host", "IP", "Time"], rows, f"Route to {args.host}"))
        return 0

    if args.command == "dns":
        result = dns_tool.lookup_domain(args.domain)
        rows = [[r.record_type, ", ".join(r.values) if r.values else (r.error or "—")] for r in result.records]
        console.print(widgets.render_table(palette, ["Type", "Value"], rows, f"DNS: {args.domain}"))
        return 0

    if args.command == "geoip":
        result = geoip_tool.lookup_ip(args.target)
        if not result.success:
            console.print(widgets.error_box(palette, result.error or "Lookup failed."))
            return 1
        rows = [
            ("IP", result.ip), ("Country", result.country), ("City", result.city),
            ("ISP", result.isp), ("Coordinates", f"{result.latitude}, {result.longitude}"),
        ]
        console.print(widgets.result_panel(palette, "GeoIP Result", widgets.kv_table(palette, rows)))
        return 0

    if args.command == "whois":
        result = whois_tool.lookup_whois(args.domain)
        if not result.success:
            console.print(widgets.error_box(palette, result.error or "WHOIS lookup failed."))
            return 1
        rows = [
            ("Registrar", result.registrar), ("Created", result.creation_date),
            ("Expires", result.expiration_date), ("Name Servers", ", ".join(result.name_servers)),
        ]
        console.print(widgets.result_panel(palette, f"WHOIS: {args.domain}", widgets.kv_table(palette, rows)))
        return 0

    if args.command == "scan":
        console.print(widgets.warning_box(palette, "Only scan hosts you own or are authorized to test."))
        result = port_scanner.scan_ports(args.host)
        if not result.success:
            console.print(widgets.error_box(palette, result.error or "Scan failed."))
            return 1
        open_ports = result.open_ports
        if not open_ports:
            console.print(widgets.warning_box(palette, "No open ports found."))
        else:
            rows = [[str(p.port), p.service, "OPEN"] for p in open_ports]
            console.print(widgets.render_table(palette, ["Port", "Service", "Status"], rows, f"Open Ports: {args.host}"))
        return 0

    if args.command == "sysinfo":
        info = system_info.gather_system_info()
        rows = [
            ("OS", f"{info.os_name} {info.os_version}"), ("CPU", info.cpu_cores_logical + " logical cores"),
            ("Memory", f"{info.memory_used} / {info.memory_total}"), ("Uptime", info.uptime),
        ]
        console.print(widgets.result_panel(palette, "System Info", widgets.kv_table(palette, rows)))
        return 0

    if args.command == "netinfo":
        info = network_info.gather_network_info()
        rows = [
            ("Hostname", info.hostname), ("Local IP", info.local_ip),
            ("Public IP", info.public.ip), ("ISP", info.public.isp),
        ]
        console.print(widgets.result_panel(palette, "Network Info", widgets.kv_table(palette, rows)))
        return 0

    return 1


def run_interactive(skip_splash: bool = False) -> int:
    ctx = AppContext()
    console = ctx.console

    try:
        if ctx.config_manager.config.show_splash and not skip_splash:
            clear_screen()
            render_splash(console, ctx.palette, APP_VERSION, PROFILE.name)
            boot_sequence(console, ctx.palette, ctx.config_manager.config.animation_speed)

        run_menu_loop(ctx)
        return 0
    except KeyboardInterrupt:
        clear_screen()
        console.print(f"\n[{ctx.palette.muted}]Interrupted. Goodbye.[/]")
        return 130
    except Exception as exc:  # noqa: BLE001
        ctx.logger.error("Fatal error in main loop", exc=exc)
        console.print(widgets.error_box(ctx.palette, f"A fatal error occurred: {exc}"))
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.command:
        return _run_direct_command(args)

    return run_interactive(skip_splash=args.no_splash)


if __name__ == "__main__":
    sys.exit(main())
