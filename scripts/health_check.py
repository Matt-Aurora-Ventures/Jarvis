"""
JARVIS Health Check System

Provides comprehensive health checking for all JARVIS components:
- Bot processes (running, PID, uptime)
- Bot API responses (health endpoints)
- Log error detection (recent error count)
- Memory usage monitoring (per process)
- API quota verification (Telegram, Twitter, etc.)

Compatible with both local development and VPS deployment.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("jarvis.health_check")

# Try to import psutil, but make it optional
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None


class HealthChecker:
    """
    Comprehensive health checker for JARVIS system.

    Attributes:
        bot_names: List of bot names to check
        log_dir: Directory containing log files
        vps_mode: Whether running in VPS mode
    """

    DEFAULT_BOTS = [
        "supervisor",
        "buy_bot",
        "sentiment_reporter",
        "twitter_poster",
        "telegram_bot",
        "autonomous_x",
        "treasury_bot",
        "clawdmatt",
        "clawdjarvis",
        "clawdfriday",
    ]

    def __init__(
        self,
        bot_names: Optional[List[str]] = None,
        log_dir: Optional[str] = None,
        vps_mode: bool = False,
    ):
        """
        Initialize HealthChecker.

        Args:
            bot_names: List of bot names to check
            log_dir: Directory containing log files
            vps_mode: If True, use VPS-specific paths
        """
        self.bot_names = bot_names or self.DEFAULT_BOTS
        self.vps_mode = vps_mode or os.getenv("VPS_MODE", "false").lower() in ("true", "1", "yes")

        if log_dir:
            self.log_dir = Path(log_dir)
        elif self.vps_mode:
            self.log_dir = Path("/root/clawdbots/logs")
        else:
            self.log_dir = Path("logs")

    async def run(self) -> Dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dictionary with all check results
        """
        return await run_all_checks(log_dir=str(self.log_dir))

    def _check_processes(self) -> Dict[str, Dict[str, Any]]:
        """Check bot processes."""
        results = {}
        for bot_name in self.bot_names:
            results[bot_name] = check_bot_process(bot_name)
        return results

    async def _check_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """Check health endpoints."""
        results = {}
        # Currently no endpoints to check
        return results

    def _check_logs(self) -> Dict[str, Dict[str, Any]]:
        """Check log files."""
        results = {}
        for bot_name in self.bot_names:
            results[bot_name] = check_log_errors(bot_name, str(self.log_dir))
        return results

    def _check_memory(self) -> Dict[str, Dict[str, Any]]:
        """Check memory usage."""
        results = {}
        for bot_name in self.bot_names:
            results[bot_name] = check_memory_usage(bot_name)
        return results

    async def _check_apis(self) -> Dict[str, Dict[str, Any]]:
        """Check API quotas."""
        return await check_api_quotas()


def check_bot_process(bot_name: str) -> Dict[str, Any]:
    """
    Check if a bot process is running.

    Args:
        bot_name: Name of the bot to check (matches against cmdline)

    Returns:
        Dictionary with process status information
    """
    if not PSUTIL_AVAILABLE:
        return {
            "status": "unknown",
            "pid": None,
            "message": "psutil not available",
        }

    matching_procs = []

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_percent', 'memory_info', 'cpu_percent', 'create_time']):
            try:
                info = proc.info
                cmdline = info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()

                if bot_name.lower() in cmdline_str:
                    if proc.is_running():
                        matching_procs.append({
                            "pid": info['pid'],
                            "name": info['name'],
                            "cmdline": cmdline,
                            "memory_percent": info.get('memory_percent', 0),
                            "memory_info": info.get('memory_info'),
                            "cpu_percent": info.get('cpu_percent', 0),
                            "create_time": info.get('create_time'),
                        })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        logger.warning(f"Error checking process {bot_name}: {e}")
        return {"status": "error", "pid": None, "error": str(e)}

    if not matching_procs:
        return {"status": "not_running", "pid": None}

    # Get the first (or primary) process
    proc = matching_procs[0]
    uptime = ""
    if proc.get("create_time"):
        uptime_seconds = time.time() - proc["create_time"]
        hours, remainder = divmod(int(uptime_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime = f"{hours}h {minutes}m {seconds}s"

    result = {
        "status": "running",
        "pid": proc["pid"],
        "uptime": uptime,
        "memory_percent": proc.get("memory_percent", 0),
        "cpu_percent": proc.get("cpu_percent", 0),
    }

    # Warn if multiple instances
    if len(matching_procs) > 1:
        result["instance_count"] = len(matching_procs)
        result["warning"] = f"Multiple instances found ({len(matching_procs)})"
        result["pids"] = [p["pid"] for p in matching_procs]

    return result


async def check_bot_response(
    bot_name: str,
    url: str,
    timeout: int = 10,
) -> Dict[str, Any]:
    """
    Check a bot's health endpoint.

    Args:
        bot_name: Name of the bot
        url: URL of the health endpoint
        timeout: Request timeout in seconds

    Returns:
        Dictionary with response status
    """
    start_time = time.time()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                response_time = (time.time() - start_time) * 1000

                if response.status == 200:
                    try:
                        data = await response.json()
                        return {
                            "status": "healthy",
                            "http_status": response.status,
                            "response_time_ms": response_time,
                            "data": data,
                        }
                    except Exception:
                        return {
                            "status": "healthy",
                            "http_status": response.status,
                            "response_time_ms": response_time,
                        }
                else:
                    try:
                        data = await response.json()
                    except Exception:
                        data = {}

                    return {
                        "status": "unhealthy",
                        "http_status": response.status,
                        "response_time_ms": response_time,
                        "data": data,
                    }

    except asyncio.TimeoutError:
        return {
            "status": "timeout",
            "error": f"Request timed out after {timeout}s",
            "response_time_ms": timeout * 1000,
        }
    except aiohttp.ClientError as e:
        return {
            "status": "error",
            "error": str(e),
            "response_time_ms": (time.time() - start_time) * 1000,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "response_time_ms": (time.time() - start_time) * 1000,
        }


def check_log_errors(
    bot_name: str,
    log_dir: str = "logs",
    minutes: int = 5,
) -> Dict[str, Any]:
    """
    Check log files for recent errors.

    Args:
        bot_name: Name of the bot (used to find log file)
        log_dir: Directory containing log files
        minutes: Time window to check (in minutes)

    Returns:
        Dictionary with error information
    """
    log_path = Path(log_dir)

    # Try different log file patterns
    log_patterns = [
        f"{bot_name}.log",
        f"{bot_name}_*.log",
        f"*{bot_name}*.log",
    ]

    log_file = None
    for pattern in log_patterns:
        matches = list(log_path.glob(pattern))
        if matches:
            # Get the most recently modified
            log_file = max(matches, key=lambda p: p.stat().st_mtime if p.exists() else 0)
            break

    if not log_file or not log_file.exists():
        return {
            "status": "unknown",
            "message": f"Log file not found for {bot_name}",
            "error_count": 0,
            "warning_count": 0,
        }

    # Parse log file
    cutoff_time = datetime.now() - timedelta(minutes=minutes)
    error_count = 0
    warning_count = 0
    recent_errors = []

    # Common log timestamp patterns
    timestamp_patterns = [
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
        r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
    ]

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                # Try to extract timestamp
                timestamp = None
                for pattern in timestamp_patterns:
                    match = re.search(pattern, line)
                    if match:
                        try:
                            ts_str = match.group(1)
                            if "T" in ts_str:
                                timestamp = datetime.fromisoformat(ts_str)
                            else:
                                timestamp = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            break
                        except ValueError:
                            continue

                # Check if within time window (only if we found a timestamp)
                if timestamp and timestamp < cutoff_time:
                    continue

                # Count errors and warnings - check multiple patterns
                line_lower = line.lower()
                # Match " - ERROR - " or "- ERROR -" or " ERROR " or just "ERROR"
                if (
                    " - error - " in line_lower or
                    "- error -" in line_lower or
                    " error " in line_lower or
                    line_lower.strip().startswith("error") or
                    " error:" in line_lower or
                    "error:" in line_lower
                ):
                    error_count += 1
                    if len(recent_errors) < 5:
                        recent_errors.append(line.strip()[:200])
                elif (
                    " - warning - " in line_lower or
                    "- warning -" in line_lower or
                    " warning " in line_lower or
                    " warning:" in line_lower
                ):
                    warning_count += 1

    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to read log: {e}",
            "error_count": 0,
            "warning_count": 0,
        }

    # Determine status
    if error_count > 10:
        status = "critical"
    elif error_count > 0:
        status = "warning"
    else:
        status = "healthy"

    return {
        "status": status,
        "error_count": error_count,
        "warning_count": warning_count,
        "recent_errors": recent_errors,
        "log_file": str(log_file),
    }


def check_memory_usage(
    bot_name: str,
    warn_threshold_mb: int = 1000,
    critical_threshold_mb: int = 3000,
) -> Dict[str, Any]:
    """
    Check memory usage of a bot process.

    Args:
        bot_name: Name of the bot to check
        warn_threshold_mb: Warning threshold in MB (default 1000)
        critical_threshold_mb: Critical threshold in MB (default 3000)

    Returns:
        Dictionary with memory information
    """
    if not PSUTIL_AVAILABLE:
        return {
            "status": "unknown",
            "message": "psutil not available",
        }

    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'memory_percent']):
            try:
                info = proc.info
                cmdline = info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline).lower()

                if bot_name.lower() in cmdline_str and proc.is_running():
                    memory_info = proc.memory_info()
                    memory_mb = memory_info.rss / (1024 * 1024)
                    memory_percent = proc.memory_percent()

                    # Determine status - critical must exceed critical threshold
                    if memory_mb > critical_threshold_mb:
                        status = "critical"
                    elif memory_mb > warn_threshold_mb:
                        status = "warning"
                    else:
                        status = "healthy"

                    return {
                        "status": status,
                        "memory_mb": int(memory_mb),
                        "memory_percent": round(memory_percent, 2),
                        "pid": info['pid'],
                    }

            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    except Exception as e:
        return {"status": "error", "error": str(e)}

    return {"status": "not_running", "memory_mb": 0, "memory_percent": 0}


async def check_api_quotas() -> Dict[str, Dict[str, Any]]:
    """
    Check API quota status for various services.

    Returns:
        Dictionary with API quota information
    """
    results = {}

    # Telegram API
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if telegram_token:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://api.telegram.org/bot{telegram_token}/getMe"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            results["telegram"] = {
                                "status": "available",
                                "bot_info": data.get("result", {}),
                            }
                        else:
                            results["telegram"] = {"status": "error", "error": "Invalid response"}
                    elif response.status == 429:
                        results["telegram"] = {"status": "rate_limited"}
                    else:
                        results["telegram"] = {"status": "error", "http_status": response.status}
        except Exception as e:
            results["telegram"] = {"status": "error", "error": str(e)}
    else:
        results["telegram"] = {"status": "not_configured"}

    # Twitter API (check if configured)
    twitter_token = os.getenv("TWITTER_BEARER_TOKEN") or os.getenv("X_BEARER_TOKEN")
    if twitter_token:
        results["twitter"] = {"status": "configured"}  # Don't actually call to avoid rate limits
    else:
        results["twitter"] = {"status": "not_configured"}

    # XAI/Grok API
    xai_key = os.getenv("XAI_API_KEY")
    if xai_key:
        results["xai"] = {"status": "configured"}
    else:
        results["xai"] = {"status": "not_configured"}

    # Anthropic API
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        results["anthropic"] = {"status": "configured"}
    else:
        results["anthropic"] = {"status": "not_configured"}

    # Helius API
    helius_key = os.getenv("HELIUS_API_KEY")
    if helius_key:
        results["helius"] = {"status": "configured"}
    else:
        results["helius"] = {"status": "not_configured"}

    return results


async def run_all_checks(
    bot_names: Optional[List[str]] = None,
    log_dir: str = "logs",
) -> Dict[str, Any]:
    """
    Run all health checks and return comprehensive results.

    Args:
        bot_names: List of bot names to check
        log_dir: Directory containing log files

    Returns:
        Dictionary with all check results
    """
    start_time = time.time()

    if bot_names is None:
        bot_names = HealthChecker.DEFAULT_BOTS

    # Run checks
    processes = {}
    logs = {}
    memory = {}

    for bot_name in bot_names:
        processes[bot_name] = check_bot_process(bot_name)
        logs[bot_name] = check_log_errors(bot_name, log_dir)
        memory[bot_name] = check_memory_usage(bot_name)

    # API quotas
    api_quotas = await check_api_quotas()

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Determine overall status
    all_statuses = []

    for info in processes.values():
        all_statuses.append(info.get("status", "unknown"))
    for info in logs.values():
        all_statuses.append(info.get("status", "unknown"))
    for info in memory.values():
        all_statuses.append(info.get("status", "unknown"))

    # Overall status logic
    if any(s in ("critical", "unhealthy") for s in all_statuses):
        overall_status = "critical"
    elif any(s in ("not_running", "error") for s in all_statuses):
        overall_status = "unhealthy"
    elif any(s in ("warning", "degraded") for s in all_statuses):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    # Summary
    summary = {"healthy": 0, "degraded": 0, "critical": 0, "total": len(all_statuses)}
    for status in all_statuses:
        if status in ("healthy", "running", "available", "configured"):
            summary["healthy"] += 1
        elif status in ("warning", "degraded"):
            summary["degraded"] += 1
        elif status in ("critical", "unhealthy", "error", "not_running"):
            summary["critical"] += 1

    return {
        "overall_status": overall_status,
        "processes": processes,
        "logs": logs,
        "memory": memory,
        "api_quotas": api_quotas,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
        "summary": summary,
    }


def get_exit_code(result: Dict[str, Any]) -> int:
    """
    Get appropriate exit code based on health check result.

    Args:
        result: Health check result dictionary

    Returns:
        Exit code (0=healthy, 1=warning/degraded, 2=critical/unhealthy)
    """
    status = result.get("overall_status", "unknown")

    if status == "healthy":
        return 0
    elif status in ("warning", "degraded"):
        return 1
    elif status in ("critical", "unhealthy"):
        return 2
    else:
        return 3  # Unknown


def detect_environment() -> str:
    """
    Detect the current environment (VPS or local).

    Returns:
        Environment type string
    """
    # Check for VPS indicators
    if Path("/root/clawdbots").exists():
        return "vps"
    if os.getenv("VPS_MODE", "").lower() in ("true", "1", "yes"):
        return "vps"
    if Path("/etc/systemd/system/clawdbots.service").exists():
        return "vps"

    return "local"


def get_default_paths() -> Dict[str, str]:
    """
    Get default paths based on environment.

    Returns:
        Dictionary with path configurations
    """
    env = detect_environment()

    if env == "vps":
        return {
            "bot_dir": "/root/clawdbots",
            "log_dir": "/root/clawdbots/logs",
            "config_dir": "/root/clawdbots/lifeos/config",
            "data_dir": "/root/clawdbots/data",
        }
    else:
        return {
            "bot_dir": str(Path(__file__).parent.parent),
            "log_dir": "logs",
            "config_dir": "lifeos/config",
            "data_dir": "data",
        }


async def main():
    """Main entry point for CLI usage."""
    import argparse

    parser = argparse.ArgumentParser(description="JARVIS Health Check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--log-dir", default="logs", help="Log directory path")
    args = parser.parse_args()

    # Run checks
    result = await run_all_checks(log_dir=args.log_dir)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        # Import format_report from status module
        try:
            from core.health.status import format_report
            print(format_report(result, verbose=args.verbose))
        except ImportError:
            # Fallback to JSON
            print(json.dumps(result, indent=2, default=str))

    # Exit with appropriate code
    sys.exit(get_exit_code(result))


if __name__ == "__main__":
    asyncio.run(main())
