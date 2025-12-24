import subprocess
from dataclasses import dataclass
from typing import Dict, List

from core import system_profiler


@dataclass
class Observation:
    title: str
    detail: str
    why_it_matters: str
    confidence: str
    next_step: str


def _top_processes(limit: int = 5) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    try:
        import psutil
    except Exception as e:
        return rows
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            mem_info = proc.info.get("memory_info")
            if not mem_info:
                continue
            mem_mb = mem_info.rss / (1024**2)
            rows.append(
                {
                    "pid": str(proc.info["pid"]),
                    "name": proc.info.get("name", "unknown"),
                    "cpu": f"{proc.info.get('cpu_percent', 0.0):.1f}",
                    "mem_mb": f"{mem_mb:.1f}",
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    rows.sort(key=lambda item: float(item["mem_mb"]), reverse=True)
    return rows[:limit]


def _listening_ports() -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    try:
        output = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
    except Exception as e:
        output = ""

    lines = output.splitlines()
    if not lines:
        return results
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        name = parts[0]
        pid = parts[1]
        address = parts[8]
        results.append({"name": name, "pid": pid, "address": address})
    return results[:10]


def _posture_observations(profile: system_profiler.SystemProfile) -> List[Observation]:
    observations: List[Observation] = []
    if profile.disk_free_gb and profile.disk_free_gb < 10:
        observations.append(
            Observation(
                title="Low disk free space",
                detail=f"Only {profile.disk_free_gb:.1f} GB free on the system drive.",
                why_it_matters="Low disk space can slow the system and break updates.",
                confidence="high",
                next_step="Consider clearing downloads or large unused files.",
            )
        )
    if profile.ram_free_gb and profile.ram_free_gb < 2:
        observations.append(
            Observation(
                title="Low available memory",
                detail=f"Only {profile.ram_free_gb:.1f} GB of RAM appears free.",
                why_it_matters="Low RAM can cause slowdowns and app crashes.",
                confidence="medium",
                next_step="Close unused apps or reduce heavy tabs.",
            )
        )
    if profile.cpu_load and profile.cpu_load > 4:
        observations.append(
            Observation(
                title="High CPU load",
                detail=f"Current load average is {profile.cpu_load:.2f}.",
                why_it_matters="Sustained high load can make the system sluggish.",
                confidence="medium",
                next_step="Identify heavy processes and close what you don't need.",
            )
        )
    return observations


def run_diagnostics(limit: int = 5) -> Dict[str, object]:
    profile = system_profiler.read_profile()
    processes = _top_processes(limit=limit)
    ports = _listening_ports()
    observations = _posture_observations(profile)
    return {
        "profile": profile,
        "processes": processes,
        "ports": ports,
        "observations": observations,
    }
