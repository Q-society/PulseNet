# PulseNet — Premium Network Diagnostics Suite

PulseNet is a cross-platform terminal application for internet speed
testing and network diagnostics. It runs identically on **Linux**,
**Windows**, **macOS**, and **Termux (Android)**.

```
   ____  __  ____   _____ _______   ______________
  / __ \/ / / / /  / ___// ____/ | / / ____/_  __/
 / /_/ / / / / /   \__ \/ __/ /  |/ / __/   / /
/ ____/ /_/ / /______/ / /___/ /|  / /___  / /
/_/    \____/_____/____/_____/_/ |_/_____/ /_/

      ◆ PREMIUM NETWORK DIAGNOSTICS SUITE ◆
```

## Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Internet Speed Test** | Download, upload, ping & jitter — powered by `speedtest-cli` with an automatic HTTP fallback engine |
| 2 | **Network Information** | Local IP, hostname, active interfaces, public IP, ISP & location |
| 3 | **Ping** | Cross-platform latency & packet loss checker |
| 4 | **Traceroute** | Hop-by-hop route tracing (`traceroute`/`tracepath`/`tracert`) |
| 5 | **DNS Lookup** | A / AAAA / MX / TXT / NS / CNAME record resolution |
| 6 | **Reverse DNS** | PTR lookup for any IP address |
| 7 | **GeoIP Lookup** | Geolocate any IP/host, or your own public IP |
| 8 | **WHOIS Lookup** | Domain registration info via WHOIS, with RDAP/HTTPS fallback |
| 9 | **Port Scanner** | TCP-connect check across 28 common service ports |
| 10 | **System Information** | CPU, memory, disk, uptime, battery |
| 11 | **Speed Test History** | SQLite-backed history with averages and export |
| 12 | **Settings** | Theme (Aurora / Crimson / Mono), units, ping count, etc. |

Every screen is rendered with a custom `rich`-based UI: gradient
`pyfiglet` banner, animated boot sequence, bordered panels, live
progress bars, and consistent color theming throughout.

## Installation

PulseNet requires **Python 3.10+**.

### Linux / macOS

```bash
sudo apt update && sudo apt install python3 python3-pip python3-psutil git -y
cd ~ && rm -rf PulseNet
git clone https://github.com/Q-society/PulseNet && cd PulseNet
pip3 install rich pyfiglet requests speedtest-cli dnspython whois --break-system-packages
python3 main.py
```

### Windows

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue PulseNet
git clone https://github.com/Q-society/PulseNet
cd PulseNet
pip install rich pyfiglet psutil requests speedtest-cli dnspython whois
python main.py
```

> Windows Terminal or PowerShell 7+ is recommended for full color
> support. Legacy `cmd.exe` on very old Windows builds may not render
> ANSI colors — PulseNet detects this automatically and still runs.

### Termux (Android)

```bash
pkg update -y && pkg install clang python python-psutil -y
cd ~ && rm -rf PulseNet
git clone https://github.com/Q-society/PulseNet && cd PulseNet
pip install rich pyfiglet requests speedtest-cli dnspython whois
python main.py
```

> If `psutil` fails to build on your device, PulseNet will still run —
> system/network-interface details will show as "Unavailable" instead
> of crashing.

## Usage

### Interactive mode (recommended)

```bash
python main.py
```

Skip the splash/boot animation:

```bash
python main.py --no-splash
```

### Direct command mode

Run a single tool and exit, useful for scripting:

```bash
python main.py speedtest
python main.py ping example.com -c 6
python main.py traceroute example.com
python main.py dns example.com
python main.py geoip 8.8.8.8
python main.py whois example.com
python main.py scan 192.168.1.1
python main.py sysinfo
python main.py netinfo
```

Run `python main.py --help` for the full list.

## Project structure

```
pulsenet/
├── main.py                  # Entry point (interactive + direct CLI commands)
├── requirements.txt
├── core/                    # Feature engines (no UI code)
│   ├── speedtest_engine.py
│   ├── network_info.py
│   ├── ping_tool.py
│   ├── traceroute_tool.py
│   ├── dns_tool.py
│   ├── geoip_tool.py
│   ├── whois_tool.py
│   ├── port_scanner.py
│   ├── system_info.py
│   ├── history_manager.py
│   └── exporter.py
├── ui/                      # Rendering layer (rich + pyfiglet)
│   ├── banner.py
│   ├── theme.py
│   ├── widgets.py
│   ├── animations.py
│   └── menu.py
└── utils/                   # Cross-cutting concerns
    ├── platform_utils.py
    ├── config.py
    └── logger.py
```

Configuration, history, exports, and logs are stored per-OS in:

- **Linux/Termux**: `~/.config/pulsenet/`
- **macOS**: `~/Library/Application Support/PulseNet/`
- **Windows**: `%APPDATA%\PulseNet\`

## Notes on the Port Scanner

The built-in scanner performs simple TCP `connect()` checks against a
curated list of well-known ports — the same kind of probe a developer
runs to confirm their own server is reachable. It does not perform
banner grabbing, exploitation, or evasion of any kind. **Only scan
hosts and networks you own or are explicitly authorized to test** —
unauthorized scanning may be against the law in your jurisdiction.

## License

Provided as-is for personal and educational use.
