"""
system_info.py
---------------
Local machine diagnostics: OS details, CPU, memory, disk, uptime,
battery (when present), and Python runtime info. Built around psutil
where available, with safe fallbacks via the standard library so the
screen still renders useful data on systems where psutil is missing.
"""

from __future__ import annotations

import platform as _platform
import sys
import time
from dataclasses import dataclass

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from utils.platform_utils import PROFILE


@dataclass
class SystemInfoResult:
    os_name: str
    os_version: str
    architecture: str
    python_version: str
    cpu_cores_physical: str
    cpu_cores_logical: str
    cpu_usage_percent: str
    memory_total: str
    memory_used: str
    memory_percent: str
    disk_total: str
    disk_used: str
    disk_percent: str
    uptime: str
    battery: str


def _bytes_to_human(num_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def _format_uptime(seconds: float) -> str:
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def _battery_info() -> str:
    if not _HAS_PSUTIL:
        return "Unavailable"
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return "No battery detected"
        charging = "Charging" if battery.power_plugged else "Discharging"
        return f"{battery.percent:.0f}% ({charging})"
    except Exception:
        return "Unavailable"


def gather_system_info() -> SystemInfoResult:
    os_name = PROFILE.name
    os_version = _platform.release()
    architecture = _platform.machine() or "Unknown"
    python_version = sys.version.split()[0]

    if _HAS_PSUTIL:
        try:
            physical = str(psutil.cpu_count(logical=False) or "N/A")
            logical = str(psutil.cpu_count(logical=True) or "N/A")
            cpu_usage = f"{psutil.cpu_percent(interval=0.3):.1f}%"

            vm = psutil.virtual_memory()
            memory_total = _bytes_to_human(vm.total)
            memory_used = _bytes_to_human(vm.used)
            memory_percent = f"{vm.percent:.1f}%"

            disk = psutil.disk_usage(str(PROFILE.home_dir))
            disk_total = _bytes_to_human(disk.total)
            disk_used = _bytes_to_human(disk.used)
            disk_percent = f"{disk.percent:.1f}%"

            uptime = _format_uptime(time.time() - psutil.boot_time())
        except Exception:
            physical = logical = cpu_usage = "Unavailable"
            memory_total = memory_used = memory_percent = "Unavailable"
            disk_total = disk_used = disk_percent = "Unavailable"
            uptime = "Unavailable"
    else:
        physical = logical = cpu_usage = "psutil not installed"
        memory_total = memory_used = memory_percent = "psutil not installed"
        disk_total = disk_used = disk_percent = "psutil not installed"
        uptime = "psutil not installed"

    return SystemInfoResult(
        os_name=os_name,
        os_version=os_version,
        architecture=architecture,
        python_version=python_version,
        cpu_cores_physical=physical,
        cpu_cores_logical=logical,
        cpu_usage_percent=cpu_usage,
        memory_total=memory_total,
        memory_used=memory_used,
        memory_percent=memory_percent,
        disk_total=disk_total,
        disk_used=disk_used,
        disk_percent=disk_percent,
        uptime=uptime,
        battery=_battery_info(),
    )
