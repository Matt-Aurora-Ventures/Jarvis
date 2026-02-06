"""
Admin Actions - Implementation of admin operations.

Provides the actual implementations of admin actions like:
- System status retrieval
- Log retrieval
- Bot restart
- Cache clearing
- Config reloading
- Health checks
"""

import asyncio
import logging
import os
import platform
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Paths
ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
CACHE_DIRS = [
    ROOT / ".cache",
    ROOT / "data" / "cache",
    Path.home() / ".lifeos" / "cache",
]


def _get_supervisor():
    """Get the bot supervisor if available."""
    try:
        # Try to import the running supervisor
        from bots.supervisor import BotSupervisor

        # Check for global instance (if supervisor exposes one)
        return None  # Supervisor doesn't expose global instance yet
    except ImportError:
        return None


def get_status() -> Dict[str, Any]:
    """
    Get comprehensive system status.

    Returns:
        Dict with system info, bot statuses, and resource usage
    """
    status: Dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "system": _get_system_info(),
        "bots": _get_bot_statuses(),
        "resources": _get_resource_usage(),
    }

    # Add uptime if available
    try:
        import psutil
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        status["uptime"] = str(datetime.now() - boot_time)
    except ImportError:
        pass

    return status


def _get_system_info() -> Dict[str, Any]:
    """Get basic system information."""
    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "hostname": platform.node(),
        "processor": platform.processor() or "unknown",
    }


def _get_bot_statuses() -> Dict[str, str]:
    """Get status of all bot components."""
    supervisor = _get_supervisor()
    if supervisor:
        return {
            name: state.get("status", "unknown")
            for name, state in supervisor.get_status().items()
        }

    # Fallback: check for running processes
    bots = {}
    bot_names = [
        "telegram_bot",
        "treasury_bot",
        "twitter_poster",
        "sentiment_reporter",
        "autonomous_x",
        "bags_intel",
    ]

    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline", []) or [])
                for bot_name in bot_names:
                    if bot_name in cmdline or bot_name.replace("_", "") in cmdline:
                        bots[bot_name] = "running"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Mark missing bots as stopped
        for bot_name in bot_names:
            if bot_name not in bots:
                bots[bot_name] = "stopped"

    except ImportError:
        # psutil not available
        for bot_name in bot_names:
            bots[bot_name] = "unknown"

    return bots


def _get_resource_usage() -> Dict[str, Any]:
    """Get system resource usage."""
    try:
        import psutil

        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent if os.name != "nt" else psutil.disk_usage("C:\\").percent,
        }
    except ImportError:
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "disk_percent": 0,
            "note": "psutil not available",
        }


def get_logs(bot_name: str, lines: int = 50) -> str:
    """
    Get recent logs for a bot.

    Args:
        bot_name: Name of the bot (e.g., "telegram_bot")
        lines: Number of lines to return

    Returns:
        String containing the last N lines of the log
    """
    # Try various log file patterns
    log_patterns = [
        f"{bot_name}.log",
        f"{bot_name.replace('_', '-')}.log",
        f"{bot_name.replace('_', '')}.log",
        "supervisor.log",  # Fallback to supervisor log
    ]

    for pattern in log_patterns:
        log_file = LOG_DIR / pattern
        if log_file.exists():
            return _tail_file(log_file, lines)

    # Check for combined log
    combined_log = LOG_DIR / "jarvis.log"
    if combined_log.exists():
        # Filter for bot-specific entries
        return _filter_log_for_bot(combined_log, bot_name, lines)

    return f"No logs found for {bot_name}"


def _tail_file(file_path: Path, lines: int) -> str:
    """Get the last N lines of a file efficiently."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            # Use deque for efficient tail
            return "\n".join(deque(f, maxlen=lines))
    except Exception as e:
        return f"Error reading log: {e}"


def _filter_log_for_bot(log_file: Path, bot_name: str, lines: int) -> str:
    """Filter a combined log file for bot-specific entries."""
    try:
        matching_lines: deque = deque(maxlen=lines)
        search_terms = [bot_name, bot_name.replace("_", "."), bot_name.replace("_", "-")]

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if any(term.lower() in line.lower() for term in search_terms):
                    matching_lines.append(line.rstrip())

        if matching_lines:
            return "\n".join(matching_lines)
        return f"No log entries found for {bot_name} in combined log"
    except Exception as e:
        return f"Error filtering log: {e}"


async def restart_bot(bot_name: str) -> Dict[str, Any]:
    """
    Restart a specific bot component.

    Args:
        bot_name: Name of the bot to restart

    Returns:
        Dict with success status and details
    """
    supervisor = _get_supervisor()

    if supervisor and hasattr(supervisor, "restart_component"):
        try:
            # Try async restart
            if asyncio.iscoroutinefunction(supervisor.restart_component):
                result = await supervisor.restart_component(bot_name)
            else:
                result = supervisor.restart_component(bot_name)

            return {
                "success": True,
                "bot": bot_name,
                "message": f"Restart initiated for {bot_name}",
            }
        except KeyError:
            return {
                "success": False,
                "bot": bot_name,
                "error": f"Unknown bot: {bot_name}",
            }
        except Exception as e:
            return {
                "success": False,
                "bot": bot_name,
                "error": str(e),
            }

    # Fallback: Signal-based restart (SIGHUP)
    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline", []) or [])
                if bot_name in cmdline:
                    proc.terminate()
                    logger.info(f"Terminated process for {bot_name} (PID: {proc.pid})")
                    return {
                        "success": True,
                        "bot": bot_name,
                        "message": f"Process terminated (will auto-restart via supervisor)",
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "success": False,
            "bot": bot_name,
            "error": f"No running process found for {bot_name}",
        }

    except ImportError:
        return {
            "success": False,
            "bot": bot_name,
            "error": "psutil not available for process management",
        }


def clear_cache() -> Dict[str, Any]:
    """
    Clear all cache directories.

    Returns:
        Dict with cleared cache info
    """
    cleared_files = 0
    cleared_bytes = 0
    errors: List[str] = []

    for cache_dir in CACHE_DIRS:
        if not cache_dir.exists():
            continue

        try:
            for item in cache_dir.rglob("*"):
                if item.is_file():
                    try:
                        size = item.stat().st_size
                        item.unlink()
                        cleared_files += 1
                        cleared_bytes += size
                    except Exception as e:
                        errors.append(f"{item}: {e}")
        except Exception as e:
            errors.append(f"{cache_dir}: {e}")

    return {
        "success": len(errors) == 0,
        "cleared_files": cleared_files,
        "cleared_bytes": cleared_bytes,
        "cleared_mb": round(cleared_bytes / (1024 * 1024), 2),
        "errors": errors if errors else None,
    }


def reload_config() -> Dict[str, Any]:
    """
    Reload all configuration files.

    Returns:
        Dict with reload status
    """
    return _reload_all_configs()


def _reload_all_configs() -> Dict[str, Any]:
    """Internal function to reload all configs."""
    reloaded: List[str] = []
    errors: List[str] = []

    # Reload core config
    try:
        from core import config
        # Force reload by clearing any cached config
        import importlib
        importlib.reload(config)
        reloaded.append("core.config")
    except Exception as e:
        errors.append(f"core.config: {e}")

    # Reload tg_bot config
    try:
        from tg_bot import config as tg_config
        import importlib
        importlib.reload(tg_config)
        reloaded.append("tg_bot.config")
    except Exception as e:
        errors.append(f"tg_bot.config: {e}")

    # Reload bot configs
    try:
        from bots.twitter import config as twitter_config
        import importlib
        importlib.reload(twitter_config)
        reloaded.append("bots.twitter.config")
    except Exception as e:
        errors.append(f"bots.twitter.config: {e}")

    return {
        "success": len(errors) == 0,
        "reloaded": reloaded,
        "errors": errors if errors else None,
    }


async def health_check() -> Dict[str, Any]:
    """
    Perform comprehensive health check.

    Returns:
        Dict with health status of all components
    """
    components: Dict[str, str] = {}
    healthy = True

    # Check database
    db_status = await _check_component_health("database")
    components["database"] = db_status
    if db_status != "ok":
        healthy = False

    # Check Telegram API
    tg_status = await _check_component_health("telegram")
    components["telegram"] = tg_status
    if tg_status != "ok":
        healthy = False

    # Check trading services
    trading_status = await _check_component_health("trading")
    components["trading"] = trading_status
    if trading_status != "ok":
        healthy = False

    # Check RPC endpoints
    rpc_status = await _check_component_health("rpc")
    components["rpc"] = rpc_status
    if rpc_status != "ok":
        healthy = False

    return {
        "healthy": healthy,
        "timestamp": datetime.utcnow().isoformat(),
        "components": components,
    }


async def _check_component_health(component: str) -> str:
    """
    Check health of a specific component.

    Returns:
        "ok", "degraded", or "error"
    """
    try:
        if component == "database":
            # Check SQLite/DB connectivity
            try:
                from tg_bot.config import get_config
                cfg = get_config()
                if cfg.db_path.exists():
                    return "ok"
                return "degraded"
            except Exception:
                return "error"

        elif component == "telegram":
            # Check Telegram bot token validity
            import aiohttp
            token = os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not token:
                return "degraded"

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"https://api.telegram.org/bot{token}/getMe",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            return "ok"
                        return "error"
            except Exception:
                return "error"

        elif component == "trading":
            # Check trading service availability
            try:
                from bots.treasury.trading import TreasuryTrader
                return "ok"
            except ImportError:
                return "degraded"

        elif component == "rpc":
            # Check Solana RPC endpoint
            import aiohttp
            rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        rpc_url,
                        json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"},
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("result") == "ok":
                                return "ok"
                        return "degraded"
            except Exception:
                return "error"

        return "unknown"

    except Exception as e:
        logger.error(f"Health check failed for {component}: {e}")
        return "error"
