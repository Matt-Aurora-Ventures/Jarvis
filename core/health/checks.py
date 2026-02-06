"""
Health Check Classes

Provides reusable health check implementations:
- ProcessCheck - Check if a process is running
- MemoryCheck - Check system memory usage
- ResponseCheck - Check HTTP endpoint response
- APICheck - Check external API connectivity
- DiskCheck - Check disk space availability
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Try to import aiohttp
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    aiohttp = None

# Try to import psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

logger = logging.getLogger("jarvis.health.checks")


@dataclass
class CheckResult:
    """Result of a health check."""
    check_name: str
    status: str
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check_name": self.check_name,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class ProcessCheck:
    """
    Check if a process is running.

    Searches for processes matching the bot name in cmdline.
    """

    def __init__(self, bot_name: str):
        """
        Initialize ProcessCheck.

        Args:
            bot_name: Name to search for in process cmdline
        """
        self.bot_name = bot_name

    async def run(self) -> Dict[str, Any]:
        """
        Run the process check.

        Returns:
            Dictionary with status, running, pid, and other process info
        """
        if not PSUTIL_AVAILABLE:
            return {
                "status": "unknown",
                "running": False,
                "pid": None,
                "message": "psutil not available",
            }

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_percent', 'cpu_percent', 'create_time']):
                try:
                    info = proc.info
                    cmdline = info.get('cmdline') or []
                    cmdline_str = ' '.join(cmdline).lower()

                    if self.bot_name.lower() in cmdline_str and proc.is_running():
                        uptime_seconds = time.time() - info.get('create_time', time.time())
                        return {
                            "status": "healthy",
                            "running": True,
                            "pid": info['pid'],
                            "name": info['name'],
                            "memory_percent": info.get('memory_percent', 0),
                            "cpu_percent": info.get('cpu_percent', 0),
                            "uptime_seconds": uptime_seconds,
                        }
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except Exception as e:
            logger.error(f"Process check error for {self.bot_name}: {e}")
            return {
                "status": "error",
                "running": False,
                "pid": None,
                "message": str(e),
            }

        return {
            "status": "unhealthy",
            "running": False,
            "pid": None,
            "message": f"Process {self.bot_name} not found",
        }


class MemoryCheck:
    """
    Check system memory usage.
    """

    def __init__(
        self,
        warn_threshold_mb: int = 1000,
        critical_threshold_mb: int = 3000,
        warn_threshold_percent: float = 80.0,
        critical_threshold_percent: float = 95.0,
    ):
        """
        Initialize MemoryCheck.

        Args:
            warn_threshold_mb: Warning threshold for free memory in MB
            critical_threshold_mb: Critical threshold for free memory in MB
            warn_threshold_percent: Warning threshold for memory usage percent
            critical_threshold_percent: Critical threshold for memory usage percent
        """
        self.warn_threshold_mb = warn_threshold_mb
        self.critical_threshold_mb = critical_threshold_mb
        self.warn_threshold_percent = warn_threshold_percent
        self.critical_threshold_percent = critical_threshold_percent

    async def run(self) -> Dict[str, Any]:
        """
        Run the memory check.

        Returns:
            Dictionary with status, percent, available_mb, etc.
        """
        if not PSUTIL_AVAILABLE:
            return {
                "status": "unknown",
                "message": "psutil not available",
            }

        try:
            mem = psutil.virtual_memory()
            available_mb = mem.available / (1024 * 1024)
            percent = mem.percent

            # Determine status
            if percent >= self.critical_threshold_percent or available_mb < 500:
                status = "critical"
            elif percent >= self.warn_threshold_percent or available_mb < self.warn_threshold_mb:
                status = "warning"
            else:
                status = "healthy"

            return {
                "status": status,
                "percent": percent,
                "available_mb": int(available_mb),
                "total_mb": int(mem.total / (1024 * 1024)),
                "used_mb": int(mem.used / (1024 * 1024)),
            }

        except Exception as e:
            logger.error(f"Memory check error: {e}")
            return {
                "status": "error",
                "message": str(e),
            }


class ResponseCheck:
    """
    Check HTTP endpoint response.
    """

    def __init__(
        self,
        url: str,
        timeout: int = 10,
        expected_status: int = 200,
    ):
        """
        Initialize ResponseCheck.

        Args:
            url: URL to check
            timeout: Request timeout in seconds
            expected_status: Expected HTTP status code
        """
        self.url = url
        self.timeout = timeout
        self.expected_status = expected_status

    async def run(self) -> Dict[str, Any]:
        """
        Run the response check.

        Returns:
            Dictionary with status, response_code, latency_ms, etc.
        """
        if not AIOHTTP_AVAILABLE:
            return {
                "status": "unknown",
                "message": "aiohttp not available",
            }

        start_time = time.monotonic()

        try:
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.get(self.url) as response:
                    latency_ms = (time.monotonic() - start_time) * 1000

                    if response.status == self.expected_status:
                        try:
                            data = await response.json()
                        except Exception:
                            data = None

                        return {
                            "status": "healthy",
                            "response_code": response.status,
                            "latency_ms": latency_ms,
                            "data": data,
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "response_code": response.status,
                            "latency_ms": latency_ms,
                            "message": f"Unexpected status code: {response.status}",
                        }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "latency_ms": self.timeout * 1000,
                "message": f"Request timed out after {self.timeout}s",
            }
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "message": str(e),
            }


class APICheck:
    """
    Check external API connectivity.
    """

    def __init__(
        self,
        api_name: str,
        url_template: str,
        env_key: Optional[str] = None,
        timeout: int = 10,
    ):
        """
        Initialize APICheck.

        Args:
            api_name: Name of the API (for logging/reporting)
            url_template: URL template with optional {token} placeholder
            env_key: Environment variable name for API key/token
            timeout: Request timeout in seconds
        """
        self.api_name = api_name
        self.url_template = url_template
        self.env_key = env_key
        self.timeout = timeout

    async def run(self) -> Dict[str, Any]:
        """
        Run the API check.

        Returns:
            Dictionary with status and API info
        """
        # Check if API is configured
        if self.env_key:
            token = os.getenv(self.env_key)
            if not token:
                return {
                    "status": "not_configured",
                    "message": f"Environment variable {self.env_key} not set",
                }
            url = self.url_template.replace("{token}", token)
        else:
            url = self.url_template
            token = None

        if not AIOHTTP_AVAILABLE:
            return {
                "status": "unknown",
                "message": "aiohttp not available",
            }

        start_time = time.monotonic()

        try:
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.get(url) as response:
                    latency_ms = (time.monotonic() - start_time) * 1000

                    if response.status == 200:
                        return {
                            "status": "available",
                            "response_code": response.status,
                            "latency_ms": latency_ms,
                        }
                    elif response.status == 429:
                        return {
                            "status": "rate_limited",
                            "response_code": response.status,
                            "latency_ms": latency_ms,
                            "message": "API rate limited",
                        }
                    else:
                        return {
                            "status": "error",
                            "response_code": response.status,
                            "latency_ms": latency_ms,
                            "message": f"API returned status {response.status}",
                        }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "latency_ms": self.timeout * 1000,
                "message": f"API check timed out after {self.timeout}s",
            }
        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            return {
                "status": "error",
                "latency_ms": latency_ms,
                "message": str(e),
            }


class DiskCheck:
    """
    Check disk space availability.
    """

    def __init__(
        self,
        path: str = "/",
        warn_threshold_percent: float = 80.0,
        critical_threshold_percent: float = 90.0,
        min_free_gb: Optional[float] = None,
    ):
        """
        Initialize DiskCheck.

        Args:
            path: Path to check disk space for
            warn_threshold_percent: Warning threshold for disk usage percent
            critical_threshold_percent: Critical threshold for disk usage percent
            min_free_gb: Minimum free space in GB (optional, triggers critical if below)
        """
        self.path = path
        self.warn_threshold_percent = warn_threshold_percent
        self.critical_threshold_percent = critical_threshold_percent
        self.min_free_gb = min_free_gb

    async def run(self) -> Dict[str, Any]:
        """
        Run the disk check.

        Returns:
            Dictionary with status, percent, free_gb, etc.
        """
        if not PSUTIL_AVAILABLE:
            return {
                "status": "unknown",
                "message": "psutil not available",
            }

        try:
            usage = psutil.disk_usage(self.path)
            percent = usage.percent
            free_gb = usage.free / (1024 * 1024 * 1024)
            total_gb = usage.total / (1024 * 1024 * 1024)

            # Determine status
            if percent >= self.critical_threshold_percent:
                status = "critical"
            elif self.min_free_gb and free_gb < self.min_free_gb:
                status = "critical"
            elif percent >= self.warn_threshold_percent:
                status = "warning"
            else:
                status = "healthy"

            return {
                "status": status,
                "percent": percent,
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_gb": round((usage.used / (1024 * 1024 * 1024)), 2),
            }

        except Exception as e:
            logger.error(f"Disk check error for {self.path}: {e}")
            return {
                "status": "error",
                "message": str(e),
            }
