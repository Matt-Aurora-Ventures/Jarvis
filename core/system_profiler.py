import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class SystemProfile:
    os_version: str
    cpu_load: float
    ram_total_gb: float
    ram_free_gb: float
    disk_free_gb: float


def _run_command(cmd: list[str]) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout.strip()
    except Exception as e:
        return ""


def _parse_vm_stat(output: str) -> tuple[Optional[float], Optional[float]]:
    page_size = 4096
    pages_free = pages_inactive = pages_spec = pages_file_cache = 0
    for line in output.splitlines():
        if "page size of" in line:
            parts = line.split("page size of")
            if len(parts) > 1:
                try:
                    page_size = int(parts[1].split("bytes")[0].strip())
                except ValueError:
                    pass
        if line.startswith("Pages free"):
            pages_free = _extract_pages(line)
        elif line.startswith("Pages inactive"):
            pages_inactive = _extract_pages(line)
        elif line.startswith("Pages speculative"):
            pages_spec = _extract_pages(line)
        elif line.startswith("Pages file-backed"):
            pages_file_cache = _extract_pages(line)

    free_pages = pages_free + pages_inactive + pages_spec + pages_file_cache
    return page_size, free_pages


def _extract_pages(line: str) -> int:
    try:
        value = line.split(":")[1].strip().strip(".")
        return int(value)
    except Exception as e:
        return 0


def _cpu_load() -> float:
    output = _run_command(["sysctl", "-n", "vm.loadavg"])
    if not output:
        return 0.0
    try:
        return float(output.split()[0])
    except (ValueError, IndexError):
        return 0.0


def _ram_stats() -> tuple[float, float]:
    total_bytes = 0.0
    output = _run_command(["sysctl", "-n", "hw.memsize"])
    try:
        total_bytes = float(output)
    except ValueError:
        total_bytes = 0.0

    vm_output = _run_command(["vm_stat"])
    page_size, free_pages = _parse_vm_stat(vm_output)
    free_bytes = float(page_size) * float(free_pages)
    return total_bytes / (1024**3), free_bytes / (1024**3)


def _disk_free_gb() -> float:
    try:
        usage = shutil.disk_usage("/")
        return usage.free / (1024**3)
    except Exception as e:
        return 0.0


def read_profile() -> SystemProfile:
    os_version = platform.platform()
    cpu_load = _cpu_load()
    ram_total_gb, ram_free_gb = _ram_stats()
    disk_free_gb = _disk_free_gb()
    return SystemProfile(
        os_version=os_version,
        cpu_load=cpu_load,
        ram_total_gb=ram_total_gb,
        ram_free_gb=ram_free_gb,
        disk_free_gb=disk_free_gb,
    )
