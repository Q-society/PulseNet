"""
menu.py
-------
The interactive shell: renders the main menu, dispatches to each feature
screen, and owns the top-level navigation loop. Every screen function
follows the same shape: clear screen -> header -> do work -> show result
-> wait for the user -> return to menu. Keeping that rhythm consistent
is most of what makes the app feel like one coherent product instead of
a pile of separate scripts.
"""

from __future__ import annotations

import time

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt

from core import (
    dns_tool,
    exporter,
    geoip_tool,
    network_info,
    ping_tool,
    port_scanner,
    speedtest_engine,
    system_info,
    traceroute_tool,
    whois_tool,
)
from core.history_manager import HistoryManager
from ui import widgets
from ui.animations import pulse_divider, spinner_task
from ui.banner import render_compact_header
from ui.theme import Palette, get_palette
from utils.config import ConfigManager
from utils.logger import AppLogger
from utils.platform_utils import clear_screen

APP_VERSION = "1.0.0"


class AppContext:
    """Holds everything a screen function might need: console, palette,
    config, history, and logger. Passed around instead of relying on
    globals so the module stays easy to test."""

    def __init__(self) -> None:
        self.config_manager = ConfigManager()
        self.palette: Palette = get_palette(self.config_manager.config.theme)
        self.console = Console()
        self.logger = AppLogger(self.config_manager.log_path)
        self.history = HistoryManager(self.config_manager.history_path)
        self.last_result: speedtest_engine.SpeedTestResult | None = None

    def refresh_palette(self) -> None:
        self.palette = get_palette(self.config_manager.config.theme)


MENU_ITEMS: list[tuple[str, str, str]] = [
    ("1", "Internet Speed Test", "Measure download, upload, ping & jitter"),
    ("2", "Network Information", "Local IP, interfaces, public IP & ISP"),
    ("3", "Ping Host", "Check latency & packet loss to any host"),
    ("4", "Traceroute", "Trace the network path to a destination"),
    ("5", "DNS Lookup", "Resolve A/AAAA/MX/TXT/NS/CNAME records"),
    ("6", "Reverse DNS", "Find the hostname behind an IP address"),
    ("7", "GeoIP Lookup", "Locate any IP address or your own"),
    ("8", "WHOIS Lookup", "Domain registration & ownership info"),
    ("9", "Port Scanner", "Check common ports on a host you control"),
    ("10", "System Information", "CPU, memory, disk & uptime"),
    ("11", "Speed Test History", "Review and export past results"),
    ("12", "Settings", "Theme, units, and preferences"),
    ("0", "Exit", "Quit PulseNet"),
]


def _wait_for_continue(console: Console, palette: Palette) -> None:
    console.print()
    Prompt.ask(f"[{palette.muted}]Press Enter to return to the menu[/]", default="", show_default=False)


def _screen_header(ctx: AppContext, subtitle: str) -> None:
    clear_screen()
    render_compact_header(ctx.console, ctx.palette, subtitle)
    ctx.console.print()


def render_main_menu(ctx: AppContext) -> None:
    clear_screen()
    render_compact_header(ctx.console, ctx.palette, "Main Menu")
    ctx.console.print()

    table_rows = []
    for key, label, desc in MENU_ITEMS:
        table_rows.append((f"[{ctx.palette.accent}]{key}[/]", f"[bold]{label}[/]  [dim]— {desc}[/]"))

    grid = widgets.kv_table(ctx.palette, table_rows, key_width=4)
    ctx.console.print(widgets.result_panel(ctx.palette, "Select an Option", grid))
    ctx.console.print()
    pulse_divider(ctx.console, ctx.palette)


# --------------------------------------------------------------------------
# Feature screens
# --------------------------------------------------------------------------

def screen_speedtest(ctx: AppContext) -> None:
    _screen_header(ctx, "Internet Speed Test")
    ctx.console.print(widgets.section_title(ctx.palette, "Running diagnostic test"))
    ctx.console.print()

    progress_state = {"label": "Preparing", "fraction": 0.0}

    def on_progress(label: str, fraction: float) -> None:
        progress_state["label"] = label
        progress_state["fraction"] = fraction

    with Progress(
        SpinnerColumn(style=ctx.palette.primary),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style=ctx.palette.accent, finished_style=ctx.palette.success),
        TextColumn("{task.percentage:>3.0f}%"),
        console=ctx.console,
        transient=True,
    ) as progress:
        task = progress.add_task("Starting...", total=100)

        import threading

        result_holder: dict = {}

        def worker() -> None:
            result_holder["result"] = speedtest_engine.run_speedtest(progress_callback=on_progress)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        while thread.is_alive():
            progress.update(
                task,
                description=progress_state["label"],
                completed=progress_state["fraction"] * 100,
            )
            time.sleep(0.1)
        progress.update(task, description="Complete", completed=100)

    result = result_holder.get("result")
    ctx.console.print()

    if result is None or not result.is_valid:
        error_msg = result.error if result else "Unknown error."
        ctx.console.print(widgets.error_box(ctx.palette, f"Speed test failed: {error_msg}"))
        ctx.logger.error(f"Speed test failed: {error_msg}")
        _wait_for_continue(ctx.console, ctx.palette)
        return

    ctx.last_result = result
    units = ctx.config_manager.config.units

    cards = [
        widgets.stat_card(ctx.palette, "Ping", str(result.ping_ms), "ms"),
        widgets.stat_card(
            ctx.palette, "Download",
            str(speedtest_engine.convert_units(result.download_mbps, units)), units,
            accent=ctx.palette.success,
        ),
        widgets.stat_card(
            ctx.palette, "Upload",
            str(speedtest_engine.convert_units(result.upload_mbps, units)), units,
            accent=ctx.palette.secondary,
        ),
    ]
    ctx.console.print(widgets.stat_row(cards))
    ctx.console.print()

    info_rows = [
        ("Jitter", f"{result.jitter_ms} ms"),
        ("Server", result.server_name),
        ("Location", result.server_location),
        ("ISP", result.isp),
        ("Engine", result.engine),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "Test Details", widgets.kv_table(ctx.palette, info_rows)))

    if ctx.config_manager.config.save_history:
        saved = ctx.history.record(result)
        if saved:
            ctx.console.print(f"\n[{ctx.palette.success}]✓ Result saved to history.[/]")

    if Confirm.ask(f"\n[{ctx.palette.accent}]Export this result to a file?[/]", default=False):
        fmt = Prompt.ask(
            "Format", choices=["json", "csv", "txt"],
            default=ctx.config_manager.config.auto_export_format,
        )
        path = exporter.export_single_result(result, ctx.config_manager.export_dir, fmt)
        if path:
            ctx.console.print(f"[{ctx.palette.success}]✓ Saved to:[/] {path}")
        else:
            ctx.console.print(widgets.error_box(ctx.palette, "Could not write export file."))

    _wait_for_continue(ctx.console, ctx.palette)


def screen_network_info(ctx: AppContext) -> None:
    _screen_header(ctx, "Network Information")

    with spinner_task(ctx.console, ctx.palette, "Gathering network details..."):
        info = network_info.gather_network_info()

    local_rows = [
        ("Hostname", info.hostname),
        ("Local IP", info.local_ip),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "Local Network", widgets.kv_table(ctx.palette, local_rows)))
    ctx.console.print()

    if_rows = []
    for iface in info.interfaces:
        status = "UP" if iface.is_up else "DOWN"
        addr_str = ", ".join(iface.addresses) or "—"
        if_rows.append([iface.name, addr_str, status])
    ctx.console.print(
        widgets.render_table(ctx.palette, ["Interface", "Address(es)", "Status"], if_rows, "Network Interfaces")
    )
    ctx.console.print()

    public = info.public
    if public.error:
        ctx.console.print(widgets.warning_box(ctx.palette, f"Public IP lookup failed: {public.error}"))
    else:
        public_rows = [
            ("Public IP", public.ip),
            ("ISP", public.isp),
            ("Organization", public.org),
            ("ASN", public.asn),
            ("Location", f"{public.city}, {public.region}, {public.country}"),
            ("Timezone", public.timezone),
        ]
        ctx.console.print(
            widgets.result_panel(ctx.palette, "Public Network", widgets.kv_table(ctx.palette, public_rows))
        )

    _wait_for_continue(ctx.console, ctx.palette)


def screen_ping(ctx: AppContext) -> None:
    _screen_header(ctx, "Ping Host")
    host = Prompt.ask(f"[{ctx.palette.accent}]Enter a hostname or IP[/]")
    if not host.strip():
        return

    count = ctx.config_manager.config.ping_count
    with spinner_task(ctx.console, ctx.palette, f"Pinging {host}..."):
        result = ping_tool.ping_host(host, count=count)

    ctx.console.print()
    if not result.success:
        ctx.console.print(widgets.error_box(ctx.palette, result.error or "Ping failed."))
        _wait_for_continue(ctx.console, ctx.palette)
        return

    rows = [
        ("Target", f"{result.host} ({result.resolved_ip})"),
        ("Packets", f"{result.received}/{result.sent} received"),
        ("Packet Loss", f"{result.loss_percent}%"),
        ("Min / Avg / Max", f"{result.min_ms} / {result.avg_ms} / {result.max_ms} ms"),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "Ping Results", widgets.kv_table(ctx.palette, rows)))
    _wait_for_continue(ctx.console, ctx.palette)


def screen_traceroute(ctx: AppContext) -> None:
    _screen_header(ctx, "Traceroute")
    target = Prompt.ask(f"[{ctx.palette.accent}]Enter a destination host[/]")
    if not target.strip():
        return

    max_hops = ctx.config_manager.config.traceroute_max_hops
    ctx.console.print(f"\n[{ctx.palette.muted}]Tracing route to {target}, this can take a moment...[/]\n")

    with spinner_task(ctx.console, ctx.palette, "Tracing route..."):
        result = traceroute_tool.trace_route(target, max_hops=max_hops)

    if not result.success:
        ctx.console.print(widgets.error_box(ctx.palette, result.error or "Traceroute failed."))
        _wait_for_continue(ctx.console, ctx.palette)
        return

    rows = []
    for hop in result.hops:
        time_str = f"{hop.time_ms} ms" if hop.time_ms is not None else "*"
        rows.append([str(hop.number), hop.host, hop.ip, time_str])

    ctx.console.print(widgets.render_table(ctx.palette, ["Hop", "Host", "IP", "Time"], rows, f"Route to {target}"))
    _wait_for_continue(ctx.console, ctx.palette)


def screen_dns(ctx: AppContext) -> None:
    _screen_header(ctx, "DNS Lookup")
    domain = Prompt.ask(f"[{ctx.palette.accent}]Enter a domain name[/]")
    if not domain.strip():
        return

    with spinner_task(ctx.console, ctx.palette, f"Resolving {domain}..."):
        result = dns_tool.lookup_domain(domain)

    ctx.console.print()
    rows = []
    for record in result.records:
        if record.error:
            rows.append([record.record_type, f"[{ctx.palette.muted}]{record.error}[/]"])
        else:
            rows.append([record.record_type, "\n".join(record.values)])

    ctx.console.print(widgets.render_table(ctx.palette, ["Type", "Value(s)"], rows, f"DNS Records for {domain}"))
    _wait_for_continue(ctx.console, ctx.palette)


def screen_reverse_dns(ctx: AppContext) -> None:
    _screen_header(ctx, "Reverse DNS")
    ip = Prompt.ask(f"[{ctx.palette.accent}]Enter an IP address[/]")
    if not ip.strip():
        return

    with spinner_task(ctx.console, ctx.palette, f"Looking up {ip}..."):
        result = dns_tool.reverse_lookup(ip)

    ctx.console.print()
    if result.success:
        rows = [("IP Address", result.ip), ("Hostname", result.hostname or "Unavailable")]
        ctx.console.print(widgets.result_panel(ctx.palette, "Reverse DNS Result", widgets.kv_table(ctx.palette, rows)))
    else:
        ctx.console.print(widgets.warning_box(ctx.palette, result.error or "No PTR record found."))

    _wait_for_continue(ctx.console, ctx.palette)


def screen_geoip(ctx: AppContext) -> None:
    _screen_header(ctx, "GeoIP Lookup")
    target = Prompt.ask(
        f"[{ctx.palette.accent}]Enter an IP/host (leave blank for your own)[/]", default="", show_default=False
    )

    with spinner_task(ctx.console, ctx.palette, "Looking up location..."):
        result = geoip_tool.lookup_ip(target)

    ctx.console.print()
    if not result.success:
        ctx.console.print(widgets.error_box(ctx.palette, result.error or "Lookup failed."))
        _wait_for_continue(ctx.console, ctx.palette)
        return

    flags = []
    if result.is_mobile:
        flags.append("Mobile")
    if result.is_proxy:
        flags.append("Proxy/VPN")
    if result.is_hosting:
        flags.append("Hosting/Datacenter")

    rows = [
        ("IP Address", result.ip),
        ("Country", f"{result.country} ({result.country_code})"),
        ("Region", result.region),
        ("City", result.city),
        ("Postal Code", result.zip_code),
        ("Coordinates", f"{result.latitude}, {result.longitude}"),
        ("Timezone", result.timezone),
        ("ISP", result.isp),
        ("Organization", result.org),
        ("ASN", result.asn),
        ("Flags", ", ".join(flags) if flags else "None detected"),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "GeoIP Result", widgets.kv_table(ctx.palette, rows)))
    _wait_for_continue(ctx.console, ctx.palette)


def screen_whois(ctx: AppContext) -> None:
    _screen_header(ctx, "WHOIS Lookup")
    domain = Prompt.ask(f"[{ctx.palette.accent}]Enter a domain name[/]")
    if not domain.strip():
        return

    with spinner_task(ctx.console, ctx.palette, f"Querying registry for {domain}..."):
        result = whois_tool.lookup_whois(domain)

    ctx.console.print()
    if not result.success:
        ctx.console.print(widgets.error_box(ctx.palette, result.error or "WHOIS lookup failed."))
        _wait_for_continue(ctx.console, ctx.palette)
        return

    rows = [
        ("Domain", result.domain),
        ("Registrar", result.registrar),
        ("Created", result.creation_date),
        ("Expires", result.expiration_date),
        ("Updated", result.updated_date),
        ("Name Servers", "\n".join(result.name_servers) or "Unavailable"),
        ("Status", "\n".join(result.status) or "Unavailable"),
        ("Source", result.raw_source),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "WHOIS Record", widgets.kv_table(ctx.palette, rows)))
    _wait_for_continue(ctx.console, ctx.palette)


def screen_port_scan(ctx: AppContext) -> None:
    _screen_header(ctx, "Port Scanner")
    ctx.console.print(
        widgets.warning_box(
            ctx.palette,
            "Only scan hosts and networks you own or have explicit permission to test.",
        )
    )
    ctx.console.print()
    host = Prompt.ask(f"[{ctx.palette.accent}]Enter a host or IP to scan[/]")
    if not host.strip():
        return

    timeout = ctx.config_manager.config.port_scan_timeout
    with spinner_task(ctx.console, ctx.palette, f"Scanning {len(port_scanner.COMMON_PORTS)} common ports..."):
        result = port_scanner.scan_ports(host, timeout=timeout)

    ctx.console.print()
    if not result.success:
        ctx.console.print(widgets.error_box(ctx.palette, result.error or "Scan failed."))
        _wait_for_continue(ctx.console, ctx.palette)
        return

    open_ports = result.open_ports
    if not open_ports:
        ctx.console.print(widgets.warning_box(ctx.palette, f"No open ports found among {len(result.results)} checked."))
    else:
        rows = [[str(p.port), p.service, "OPEN"] for p in open_ports]
        ctx.console.print(
            widgets.render_table(ctx.palette, ["Port", "Service", "Status"], rows, f"Open Ports on {result.host}")
        )

    ctx.config_manager.update(last_scanned_host=host)
    _wait_for_continue(ctx.console, ctx.palette)


def screen_system_info(ctx: AppContext) -> None:
    _screen_header(ctx, "System Information")

    with spinner_task(ctx.console, ctx.palette, "Reading system metrics..."):
        info = system_info.gather_system_info()

    rows = [
        ("Operating System", f"{info.os_name} {info.os_version}"),
        ("Architecture", info.architecture),
        ("Python Version", info.python_version),
        ("CPU Cores", f"{info.cpu_cores_physical} physical / {info.cpu_cores_logical} logical"),
        ("CPU Usage", info.cpu_usage_percent),
        ("Memory", f"{info.memory_used} / {info.memory_total} ({info.memory_percent})"),
        ("Disk (home)", f"{info.disk_used} / {info.disk_total} ({info.disk_percent})"),
        ("Uptime", info.uptime),
        ("Battery", info.battery),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "System Snapshot", widgets.kv_table(ctx.palette, rows)))
    _wait_for_continue(ctx.console, ctx.palette)


def screen_history(ctx: AppContext) -> None:
    _screen_header(ctx, "Speed Test History")
    entries = ctx.history.fetch_recent(ctx.config_manager.config.history_limit)

    if not entries:
        ctx.console.print(widgets.warning_box(ctx.palette, "No history yet. Run a speed test first."))
        _wait_for_continue(ctx.console, ctx.palette)
        return

    rows = [
        [e.formatted_date, f"{e.ping_ms} ms", f"{e.download_mbps} Mbps", f"{e.upload_mbps} Mbps", e.server_name]
        for e in entries
    ]
    ctx.console.print(
        widgets.render_table(ctx.palette, ["Date", "Ping", "Download", "Upload", "Server"], rows, "Recent Tests")
    )

    averages = ctx.history.averages()
    ctx.console.print()
    avg_rows = [
        ("Tests Recorded", str(averages["count"])),
        ("Average Ping", f"{averages['ping']} ms"),
        ("Average Download", f"{averages['download']} Mbps"),
        ("Average Upload", f"{averages['upload']} Mbps"),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "Averages", widgets.kv_table(ctx.palette, avg_rows)))

    ctx.console.print()
    if Confirm.ask(f"[{ctx.palette.accent}]Export full history?[/]", default=False):
        fmt = Prompt.ask("Format", choices=["json", "csv", "txt"], default="csv")
        all_entries = ctx.history.fetch_recent(ctx.config_manager.config.history_limit)
        path = exporter.export_history(all_entries, ctx.config_manager.export_dir, fmt)
        if path:
            ctx.console.print(f"[{ctx.palette.success}]✓ Saved to:[/] {path}")
        else:
            ctx.console.print(widgets.error_box(ctx.palette, "Could not write export file."))

    if Confirm.ask(f"[{ctx.palette.danger}]Clear all history?[/]", default=False):
        if ctx.history.clear():
            ctx.console.print(f"[{ctx.palette.success}]✓ History cleared.[/]")

    _wait_for_continue(ctx.console, ctx.palette)


def screen_settings(ctx: AppContext) -> None:
    _screen_header(ctx, "Settings")
    cfg = ctx.config_manager.config

    rows = [
        ("Theme", cfg.theme),
        ("Units", cfg.units),
        ("Ping Count", str(cfg.ping_count)),
        ("Traceroute Max Hops", str(cfg.traceroute_max_hops)),
        ("Save History", "Yes" if cfg.save_history else "No"),
        ("Animation Speed", str(cfg.animation_speed)),
    ]
    ctx.console.print(widgets.result_panel(ctx.palette, "Current Settings", widgets.kv_table(ctx.palette, rows)))
    ctx.console.print()

    options = (
        "1. Change theme\n2. Change units\n3. Change ping count\n"
        "4. Toggle history saving\n5. Reset to defaults\n0. Back"
    )
    ctx.console.print(widgets.result_panel(ctx.palette, "Options", options))
    choice = Prompt.ask("Choose an option", choices=["0", "1", "2", "3", "4", "5"], default="0")

    if choice == "1":
        theme = Prompt.ask("New theme", choices=["aurora", "crimson", "mono"], default=cfg.theme)
        ctx.config_manager.update(theme=theme)
        ctx.refresh_palette()
        ctx.console.print(f"[{ctx.palette.success}]✓ Theme updated.[/]")
    elif choice == "2":
        units = Prompt.ask("New units", choices=["Mbps", "MBps", "Kbps"], default=cfg.units)
        ctx.config_manager.update(units=units)
        ctx.console.print(f"[{ctx.palette.success}]✓ Units updated.[/]")
    elif choice == "3":
        count = IntPrompt.ask("New ping count", default=cfg.ping_count)
        ctx.config_manager.update(ping_count=count)
        ctx.console.print(f"[{ctx.palette.success}]✓ Ping count updated.[/]")
    elif choice == "4":
        ctx.config_manager.update(save_history=not cfg.save_history)
        ctx.console.print(f"[{ctx.palette.success}]✓ History saving toggled.[/]")
    elif choice == "5":
        ctx.config_manager.reset()
        ctx.refresh_palette()
        ctx.console.print(f"[{ctx.palette.success}]✓ Settings reset to defaults.[/]")

    _wait_for_continue(ctx.console, ctx.palette)


SCREEN_DISPATCH = {
    "1": screen_speedtest,
    "2": screen_network_info,
    "3": screen_ping,
    "4": screen_traceroute,
    "5": screen_dns,
    "6": screen_reverse_dns,
    "7": screen_geoip,
    "8": screen_whois,
    "9": screen_port_scan,
    "10": screen_system_info,
    "11": screen_history,
    "12": screen_settings,
}


def run_menu_loop(ctx: AppContext) -> None:
    while True:
        render_main_menu(ctx)
        choice = Prompt.ask(
            f"[{ctx.palette.accent}]›[/] Choose an option",
            choices=[item[0] for item in MENU_ITEMS],
            show_choices=False,
        )
        if choice == "0":
            clear_screen()
            ctx.console.print(f"[{ctx.palette.accent}]Thanks for using PulseNet. Stay connected.[/]")
            break

        handler = SCREEN_DISPATCH.get(choice)
        if handler:
            try:
                handler(ctx)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001
                ctx.logger.error(f"Unhandled error in screen '{choice}'", exc=exc)
                ctx.console.print(
                    widgets.error_box(
                        ctx.palette,
                        f"Something went wrong: {exc}\nDetails were written to the log file.",
                    )
                )
                _wait_for_continue(ctx.console, ctx.palette)
