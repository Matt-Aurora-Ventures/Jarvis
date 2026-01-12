"""
Lightweight resource and security monitor for Jarvis.
Tracks CPU/RAM/Disk and warns when the system is under pressure.
"""

import json
import os
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from core import config, diagnostics, state, system_profiler

ROOT = Path(__file__).resolve().parents[1]
MONITOR_DIR = ROOT / "data" / "resource_monitor"
RESOURCE_LOG = MONITOR_DIR / "resource_log.jsonl"
SECURITY_LOG = MONITOR_DIR / "security_log.jsonl"
NETWORK_LOG = MONITOR_DIR / "network_log.jsonl"


@dataclass
class ResourceSnapshot:
    timestamp: float
    cpu_load: float
    ram_total_gb: float
    ram_free_gb: float
    disk_free_gb: float
    ram_free_ratio: float


class ResourceMonitor(threading.Thread):
    """Background monitor for system pressure and basic security posture."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        cfg = config.load_config()
        rcfg = cfg.get("resource_monitor", {})
        self._enabled = bool(rcfg.get("enabled", True))
        self._poll_seconds = int(rcfg.get("poll_seconds", 20))
        self._notify = bool(rcfg.get("notify", True))
        self._notify_interval = int(rcfg.get("notify_interval_seconds", 900))
        self._log_interval = int(rcfg.get("log_interval_seconds", 300))
        self._ram_free_gb_warn = float(rcfg.get("ram_free_gb_warn", 2.0))
        self._ram_free_ratio_warn = float(rcfg.get("ram_free_percent_warn", 0.1))
        self._cpu_load_warn = float(rcfg.get("cpu_load_warn", 4.0))
        self._disk_free_gb_warn = float(rcfg.get("disk_free_gb_warn", 10.0))
        self._security_scan_enabled = bool(rcfg.get("security_scan", True))
        self._security_scan_minutes = int(rcfg.get("security_scan_minutes", 360))
        net_cfg = cfg.get("network_monitor", {})
        self._net_enabled = bool(net_cfg.get("enabled", True))
        self._net_warn_mbps = float(net_cfg.get("throughput_mbps_warn", 20.0))
        self._net_warn_pps = float(net_cfg.get("packets_per_sec_warn", 5000))
        self._net_log_interval = int(net_cfg.get("log_interval_seconds", 120))
        self._last_net_io = None
        self._last_net_log = 0.0
        self._last_conn_scan = 0.0
        pg_cfg = cfg.get("process_guard", {})
        self._process_guard_enabled = bool(pg_cfg.get("enabled", True))
        self._cpu_percent_warn = float(pg_cfg.get("cpu_percent_warn", 180.0))
        self._mem_mb_warn = float(pg_cfg.get("mem_mb_warn", 1500.0))
        self._connections_warn = int(pg_cfg.get("connections_warn", 200))
        self._conn_scan_interval = int(pg_cfg.get("connection_scan_seconds", 120))
        self._auto_kill = bool(pg_cfg.get("auto_kill", False))
        self._force_kill = bool(pg_cfg.get("force_kill", False))
        self._guard_cooldown = int(pg_cfg.get("cooldown_seconds", 900))
        self._protect_processes = set(
            name.lower()
            for name in pg_cfg.get(
                "protect_processes",
                [
                    "kernel_task",
                    "windowserver",
                    "launchd",
                    "systemuiserver",
                    "coreaudiod",
                    "lifeos",
                    "python",
                    "python3",
                ],
            )
        )
        self._hot_counts: Dict[int, int] = {}
        self._last_notify = 0.0
        self._last_log = 0.0
        self._last_security_scan = 0.0
        self._last_ports: Set[str] = set()
        self._last_guard_action = 0.0

    def stop(self) -> None:
        self._stop_event.set()

    def _notify_user(self, title: str, message: str) -> None:
        if not self._notify:
            return
        if time.time() - self._last_notify < self._notify_interval:
            return
        self._last_notify = time.time()
        try:
            from core.platform import send_notification
            send_notification(title, message[:180])
        except Exception:
            pass

    def _append_log(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")

    def _resource_snapshot(self) -> Optional[ResourceSnapshot]:
        profile = system_profiler.read_profile()
        if not profile:
            return None
        ram_ratio = 0.0
        if profile.ram_total_gb:
            ram_ratio = max(min(profile.ram_free_gb / profile.ram_total_gb, 1.0), 0.0)
        return ResourceSnapshot(
            timestamp=time.time(),
            cpu_load=profile.cpu_load,
            ram_total_gb=profile.ram_total_gb,
            ram_free_gb=profile.ram_free_gb,
            disk_free_gb=profile.disk_free_gb,
            ram_free_ratio=ram_ratio,
        )

    def _check_thresholds(self, snapshot: ResourceSnapshot) -> List[str]:
        alerts = []
        if self._ram_free_gb_warn and snapshot.ram_free_gb < self._ram_free_gb_warn:
            alerts.append(f"Low RAM: {snapshot.ram_free_gb:.1f} GB free")
        if self._ram_free_ratio_warn and snapshot.ram_free_ratio < self._ram_free_ratio_warn:
            alerts.append(f"Low RAM ratio: {snapshot.ram_free_ratio*100:.0f}% free")
        if self._cpu_load_warn and snapshot.cpu_load > self._cpu_load_warn:
            alerts.append(f"High CPU load: {snapshot.cpu_load:.2f}")
        if self._disk_free_gb_warn and snapshot.disk_free_gb < self._disk_free_gb_warn:
            alerts.append(f"Low disk space: {snapshot.disk_free_gb:.1f} GB free")
        return alerts

    def _security_scan(self) -> None:
        if not self._security_scan_enabled:
            return
        now = time.time()
        if now - self._last_security_scan < self._security_scan_minutes * 60:
            return
        self._last_security_scan = now
        try:
            diag = diagnostics.run_diagnostics(limit=5)
            ports = diag.get("ports", [])
            port_ids = {f"{p.get('name', '')}:{p.get('address', '')}" for p in ports if p}
            new_ports = port_ids - self._last_ports if self._last_ports else set()
            self._last_ports = port_ids
            payload = {
                "timestamp": now,
                "ports": ports,
                "processes": diag.get("processes", []),
                "observations": [asdict(o) for o in diag.get("observations", [])],
                "new_ports": sorted(new_ports),
            }
            self._append_log(SECURITY_LOG, payload)
            if new_ports:
                self._notify_user("Jarvis Security Pulse", "New listening ports detected.")
        except Exception:
            pass

    def _network_monitor(self) -> None:
        if not self._net_enabled:
            return
        try:
            import psutil  # type: ignore
        except Exception:
            return
        now = time.time()
        counters = psutil.net_io_counters()
        if not counters:
            return
        if self._last_net_io is None:
            self._last_net_io = (now, counters)
            return
        last_ts, last = self._last_net_io
        elapsed = max(now - last_ts, 1e-6)
        rx_bytes = max(counters.bytes_recv - last.bytes_recv, 0)
        tx_bytes = max(counters.bytes_sent - last.bytes_sent, 0)
        rx_packets = max(counters.packets_recv - last.packets_recv, 0)
        tx_packets = max(counters.packets_sent - last.packets_sent, 0)
        rx_mbps = (rx_bytes * 8) / (elapsed * 1_000_000)
        tx_mbps = (tx_bytes * 8) / (elapsed * 1_000_000)
        pps = (rx_packets + tx_packets) / elapsed
        self._last_net_io = (now, counters)

        state.update_state(
            net_rx_mbps=round(rx_mbps, 3),
            net_tx_mbps=round(tx_mbps, 3),
            net_packets_per_sec=round(pps, 1),
        )

        if rx_mbps > self._net_warn_mbps or tx_mbps > self._net_warn_mbps:
            self._notify_user(
                "Jarvis Network Alert",
                f"High throughput: {rx_mbps:.1f} Mbps down, {tx_mbps:.1f} Mbps up",
            )
        if pps > self._net_warn_pps:
            self._notify_user("Jarvis Network Alert", f"High packet rate: {pps:.0f} pps")

        if now - self._last_net_log >= self._net_log_interval:
            payload = {
                "timestamp": now,
                "rx_mbps": rx_mbps,
                "tx_mbps": tx_mbps,
                "packets_per_sec": pps,
                "rx_packets": rx_packets,
                "tx_packets": tx_packets,
            }
            self._append_log(NETWORK_LOG, payload)
            self._last_net_log = now

    def _process_guard(self) -> None:
        if not self._process_guard_enabled:
            return
        if time.time() - self._last_guard_action < self._guard_cooldown:
            return
        try:
            import psutil  # type: ignore
        except Exception:
            return
        now = time.time()
        connection_counts: Dict[int, int] = {}
        if self._connections_warn > 0 and now - self._last_conn_scan >= self._conn_scan_interval:
            try:
                for conn in psutil.net_connections(kind="inet"):
                    if conn.pid is None:
                        continue
                    connection_counts[conn.pid] = connection_counts.get(conn.pid, 0) + 1
            except Exception:
                connection_counts = {}
            self._last_conn_scan = now

        offenders: List[Dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
            try:
                name = proc.info.get("name") or ""
                name_lower = name.lower()
                if name_lower in self._protect_processes:
                    continue
                if proc.pid == os.getpid():
                    continue
                cpu = float(proc.info.get("cpu_percent") or 0.0)
                mem_info = proc.info.get("memory_info")
                mem_mb = (mem_info.rss / (1024**2)) if mem_info else 0.0
                conn_count = connection_counts.get(proc.pid, 0)

                hot = (
                    cpu >= self._cpu_percent_warn
                    or mem_mb >= self._mem_mb_warn
                    or (self._connections_warn and conn_count >= self._connections_warn)
                )
                if not hot:
                    self._hot_counts.pop(proc.pid, None)
                    continue

                self._hot_counts[proc.pid] = self._hot_counts.get(proc.pid, 0) + 1
                if self._hot_counts[proc.pid] < 3:
                    continue
                offenders.append(
                    {
                        "pid": proc.pid,
                        "name": name,
                        "cpu": cpu,
                        "mem_mb": round(mem_mb, 1),
                        "connections": conn_count,
                    }
                )
            except Exception:
                continue

        if not offenders:
            return

        summary = ", ".join(
            f"{o['name']} (pid {o['pid']}, CPU {o['cpu']:.0f}%, {o['mem_mb']} MB, conns {o['connections']})"
            for o in offenders[:3]
        )
        payload = {"timestamp": now, "offenders": offenders, "auto_kill": self._auto_kill}
        self._append_log(SECURITY_LOG, payload)
        if self._auto_kill:
            for offender in offenders:
                try:
                    proc = psutil.Process(offender["pid"])
                    proc.terminate()
                except Exception:
                    continue
            if self._force_kill:
                for offender in offenders:
                    try:
                        proc = psutil.Process(offender["pid"])
                        proc.kill()
                    except Exception:
                        continue
            self._notify_user("Jarvis Process Guard", f"Terminated: {summary[:160]}")
        else:
            self._notify_user("Jarvis Process Guard", f"Heavy processes detected: {summary[:160]}")
        self._last_guard_action = now

    def run(self) -> None:
        if not self._enabled:
            state.update_state(resource_monitor_enabled=False)
            return
        state.update_state(resource_monitor_enabled=True)
        while not self._stop_event.is_set():
            snapshot = self._resource_snapshot()
            if snapshot:
                state.update_state(
                    resource_cpu_load=round(snapshot.cpu_load, 2),
                    resource_ram_free_gb=round(snapshot.ram_free_gb, 2),
                    resource_ram_total_gb=round(snapshot.ram_total_gb, 2),
                    resource_disk_free_gb=round(snapshot.disk_free_gb, 2),
                    resource_ram_free_ratio=round(snapshot.ram_free_ratio, 3),
                )
                alerts = self._check_thresholds(snapshot)
                if alerts:
                    self._notify_user("Jarvis Resource Alert", "; ".join(alerts))
                now = time.time()
                if now - self._last_log >= self._log_interval:
                    self._append_log(RESOURCE_LOG, asdict(snapshot))
                    self._last_log = now
            self._network_monitor()
            self._process_guard()
            self._security_scan()
            self._stop_event.wait(self._poll_seconds)


_monitor: Optional[ResourceMonitor] = None


def start_monitor() -> ResourceMonitor:
    global _monitor
    if _monitor and _monitor.is_alive():
        return _monitor
    monitor = ResourceMonitor()
    monitor.start()
    _monitor = monitor
    return monitor


def stop_monitor() -> None:
    global _monitor
    if _monitor:
        _monitor.stop()
        _monitor.join(timeout=5)
        _monitor = None


__all__ = ["start_monitor", "stop_monitor", "ResourceMonitor"]
