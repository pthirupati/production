"""
FREE server metrics collector for the admin fleet-monitoring dashboard.

Collects host-level metrics (CPU, memory, disk, load, uptime, processes) for the
LOCAL node with zero paid dependencies. Strategy:

  1. Read /proc + os (Linux containers / VMs) — no extra packages required.
  2. Fall back to psutil if it happens to be installed (nicer on macOS).
  3. Fall back to "n/a" (None) for anything that cannot be measured on this OS,
     so the collector NEVER raises — callers can always render a card.

A multi-node "fleet" is assembled by AdminFleetMonitoringView, which fetches each
configured remote node's own /metrics/ endpoint over HTTP (best-effort).
"""
from __future__ import annotations

import os
import socket
import time

# psutil is optional — only used as a fallback / on non-Linux hosts.
try:  # pragma: no cover - import guard
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:  # pragma: no cover
    psutil = None  # type: ignore
    _HAS_PSUTIL = False

_HAS_PROC = os.path.isdir("/proc")

# Cache one CPU sample so the /proc delta calc works across calls without
# blocking for a sampling window on every request.
_CPU_SAMPLE: dict[str, float] = {}


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _round(value, ndigits=1):
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


# ─── Hostname / IP ────────────────────────────────────────────────────────────

def _get_hostname() -> str:
    return _safe(socket.gethostname, "unknown") or "unknown"


def _get_ip() -> str:
    """Best-effort primary IP. Uses a UDP socket trick (no packets actually sent)
    so we get the outbound interface address rather than 127.0.0.1."""
    def _outbound():
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()

    ip = _safe(_outbound)
    if ip:
        return ip
    # Fall back to resolving the hostname.
    ip = _safe(lambda: socket.gethostbyname(socket.gethostname()))
    return ip or "n/a"


# ─── CPU ──────────────────────────────────────────────────────────────────────

def _cpu_count() -> int | None:
    return _safe(lambda: os.cpu_count())


def _cpu_percent_proc() -> float | None:
    """Compute CPU utilisation from two reads of /proc/stat.

    First call seeds the sample and returns an estimate from the cumulative
    figures; subsequent calls return the delta over the interval since the last
    read, which is what you want for a polling dashboard.
    """
    def _read_total_idle():
        with open("/proc/stat", "r") as fh:
            line = fh.readline()
        parts = [float(p) for p in line.split()[1:]]
        idle = parts[3] + (parts[4] if len(parts) > 4 else 0.0)  # idle + iowait
        total = sum(parts)
        return total, idle

    total, idle = _read_total_idle()
    prev = _CPU_SAMPLE.get("total"), _CPU_SAMPLE.get("idle")
    _CPU_SAMPLE["total"], _CPU_SAMPLE["idle"] = total, idle

    if prev[0] is None or total <= prev[0]:
        # No usable previous sample — approximate from cumulative numbers.
        if total <= 0:
            return None
        return _round(100.0 * (1.0 - idle / total))

    dt = total - prev[0]
    di = idle - prev[1]
    if dt <= 0:
        return None
    return _round(100.0 * (1.0 - di / dt))


def _cpu_percent() -> float | None:
    if _HAS_PROC:
        val = _cpu_percent_proc()
        if val is not None:
            return val
    if _HAS_PSUTIL:
        # Non-blocking; relies on psutil's own internal sample.
        return _round(_safe(lambda: psutil.cpu_percent(interval=None)))
    return None


# ─── Memory ─────────────────────────────────────────────────────────────────--

def _mem_proc() -> dict | None:
    """Parse /proc/meminfo. Values are in kB."""
    info: dict[str, float] = {}
    with open("/proc/meminfo", "r") as fh:
        for line in fh:
            key, _, rest = line.partition(":")
            info[key.strip()] = float(rest.strip().split()[0]) * 1024  # → bytes

    total = info.get("MemTotal")
    if not total:
        return None
    # MemAvailable is the modern, accurate figure; fall back to free+buffers+cache.
    available = info.get("MemAvailable")
    if available is None:
        available = (
            info.get("MemFree", 0)
            + info.get("Buffers", 0)
            + info.get("Cached", 0)
        )
    used = max(total - available, 0)
    return {
        "mem_total": int(total),
        "mem_used": int(used),
        "mem_available": int(available),
        "mem_percent": _round(100.0 * used / total),
    }


def _memory() -> dict:
    if _HAS_PROC:
        data = _safe(_mem_proc)
        if data:
            return data
    if _HAS_PSUTIL:
        vm = _safe(lambda: psutil.virtual_memory())
        if vm is not None:
            return {
                "mem_total": int(vm.total),
                "mem_used": int(vm.total - vm.available),
                "mem_available": int(vm.available),
                "mem_percent": _round(vm.percent),
            }
    return {"mem_total": None, "mem_used": None, "mem_available": None, "mem_percent": None}


# ─── Disk ───────────────────────────────────────────────────────────────────--

def _disk(path: str = "/") -> dict:
    def _usage():
        st = os.statvfs(path)
        total = st.f_blocks * st.f_frsize
        free = st.f_bavail * st.f_frsize
        used = total - (st.f_bfree * st.f_frsize)
        return total, used, free

    res = _safe(_usage)
    if not res:
        return {"disk_total": None, "disk_used": None, "disk_free": None, "disk_percent": None}
    total, used, free = res
    return {
        "disk_total": int(total),
        "disk_used": int(used),
        "disk_free": int(free),
        "disk_percent": _round(100.0 * used / total) if total else None,
    }


# ─── Load average ─────────────────────────────────────────────────────────────

def _load_avg() -> dict:
    res = _safe(lambda: os.getloadavg())  # available on Linux + macOS
    if not res:
        return {"load_1": None, "load_5": None, "load_15": None}
    return {
        "load_1": _round(res[0], 2),
        "load_5": _round(res[1], 2),
        "load_15": _round(res[2], 2),
    }


# ─── Uptime ───────────────────────────────────────────────────────────────────

def _uptime_seconds() -> int | None:
    if _HAS_PROC:
        def _read():
            with open("/proc/uptime", "r") as fh:
                return int(float(fh.readline().split()[0]))
        val = _safe(_read)
        if val is not None:
            return val
    if _HAS_PSUTIL:
        bt = _safe(lambda: psutil.boot_time())
        if bt:
            return int(time.time() - bt)
    return None


# ─── Process count ────────────────────────────────────────────────────────────

def _process_count() -> int | None:
    if _HAS_PROC:
        def _count():
            return sum(1 for n in os.listdir("/proc") if n.isdigit())
        val = _safe(_count)
        if val is not None:
            return val
    if _HAS_PSUTIL:
        return _safe(lambda: len(psutil.pids()))
    return None


# ─── Public API ───────────────────────────────────────────────────────────────

def collect_local_metrics(node_name: str | None = None) -> dict:
    """Collect all host metrics for THIS node. Never raises."""
    mem = _memory()
    disk = _disk("/")
    load = _load_avg()
    metrics = {
        "name": node_name or _get_hostname(),
        "hostname": _get_hostname(),
        "ip": _get_ip(),
        "status": "online",
        "source": "psutil" if (_HAS_PSUTIL and not _HAS_PROC) else ("proc" if _HAS_PROC else "limited"),
        "cpu_percent": _cpu_percent(),
        "cpu_count": _cpu_count(),
        "uptime_seconds": _uptime_seconds(),
        "process_count": _process_count(),
        "collected_at": int(time.time()),
        "is_local": True,
    }
    metrics.update(mem)
    metrics.update(disk)
    metrics.update(load)
    return metrics
