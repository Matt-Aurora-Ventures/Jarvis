"""Enhanced Error Handling and Recovery for Jarvis."""

import errno
import gc
import importlib
import json
import random
import threading
import time
import traceback
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG_PATH = ROOT / "data" / "error_recovery.log"

DEFAULT_MAX_HISTORY = 200
MAX_TRACEBACK_CHARS = 4000
MAX_CONTEXT_DEPTH = 4
MAX_CONTEXT_ITEMS = 50
MAX_LOG_BYTES = 5_000_000

TRANSIENT_KEYWORDS = (
    "connection",
    "timeout",
    "temporary",
    "busy",
    "unavailable",
    "rate limit",
    "reset by peer",
    "network",
    "dns",
    "socket",
)

PATH_CONTEXT_KEYS = (
    "path",
    "file_path",
    "filepath",
    "dir",
    "directory",
    "target_path",
    "output_path",
    "input_path",
)


def _safe_string(value: Any, max_len: int = 1000) -> str:
    try:
        text = str(value)
    except Exception:
        text = repr(value)
    if len(text) > max_len:
        return text[:max_len] + "...(truncated)"
    return text


def _safe_serialize(value: Any, depth: int = MAX_CONTEXT_DEPTH) -> Any:
    if depth <= 0:
        return _safe_string(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Exception):
        return {"type": type(value).__name__, "message": _safe_string(value)}
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for idx, (key, item) in enumerate(value.items()):
            if idx >= MAX_CONTEXT_ITEMS:
                result["__truncated__"] = True
                break
            result[_safe_string(key)] = _safe_serialize(item, depth=depth - 1)
        return result
    if isinstance(value, (list, tuple, set)):
        items: List[Any] = []
        for idx, item in enumerate(value):
            if idx >= MAX_CONTEXT_ITEMS:
                items.append("__truncated__")
                break
            items.append(_safe_serialize(item, depth=depth - 1))
        return items
    return _safe_string(value)


def _format_trace(error: BaseException) -> str:
    try:
        if error.__traceback__ is not None:
            trace = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            trace = "".join(traceback.format_exception_only(type(error), error))
    except Exception:
        trace = traceback.format_exc()
    if len(trace) > MAX_TRACEBACK_CHARS:
        return trace[:MAX_TRACEBACK_CHARS] + "\n... truncated ..."
    return trace


def _now_iso(timestamp: Optional[float] = None) -> str:
    if timestamp is None:
        timestamp = time.time()
    return datetime.fromtimestamp(timestamp).isoformat()


def _coerce_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if context is None:
        return {}
    if isinstance(context, dict):
        return dict(context)
    return {"value": _safe_string(context)}


def _extract_path_from_context(context: Dict[str, Any]) -> Optional[Path]:
    for key in PATH_CONTEXT_KEYS:
        value = context.get(key)
        if isinstance(value, Path):
            path = value
        elif isinstance(value, str) and value.strip():
            path = Path(value)
        else:
            continue
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        return path
    return None


def _is_within_root(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False
    return resolved == ROOT or ROOT in resolved.parents


def _is_transient_error(error: Exception) -> bool:
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in TRANSIENT_KEYWORDS)


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for better handling."""

    NETWORK = "network"
    FILESYSTEM = "filesystem"
    DEPENDENCY = "dependency"
    PERMISSION = "permission"
    MEMORY = "memory"
    CONFIGURATION = "configuration"
    MCP_SERVER = "mcp_server"
    AUTONOMOUS_CYCLE = "autonomous_cycle"
    UNKNOWN = "unknown"


@dataclass
class ErrorRecord:
    """Record of an error with context."""

    error: Exception
    context: Dict[str, Any]
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    category: ErrorCategory = ErrorCategory.UNKNOWN
    timestamp: float = field(default_factory=time.time)
    stack_trace: str = ""
    recovery_attempts: int = 0
    resolved: bool = False
    recovery_trace: List[Dict[str, Any]] = field(default_factory=list)
    error_id: str = ""

    def __post_init__(self):
        self.context = _coerce_context(self.context)
        if not self.stack_trace:
            self.stack_trace = _format_trace(self.error)
        if not self.error_id:
            self.error_id = f"err_{int(self.timestamp * 1000)}_{id(self.error)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "id": self.error_id,
            "error": _safe_string(self.error),
            "type": type(self.error).__name__,
            "context": _safe_serialize(self.context),
            "severity": self.severity.value,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "stack_trace": self.stack_trace,
            "recovery_attempts": self.recovery_attempts,
            "resolved": self.resolved,
            "recovery_trace": _safe_serialize(self.recovery_trace),
        }


@dataclass
class StrategyState:
    last_attempt: float = 0.0
    attempts: int = 0
    successes: int = 0
    failures: int = 0


class RecoveryStrategy:
    """Base class for recovery strategies."""

    def __init__(self, name: str, priority: int = 0, cooldown_seconds: int = 0):
        self.name = name
        self.priority = priority
        self.cooldown_seconds = cooldown_seconds

    def can_handle(self, error_record: ErrorRecord) -> bool:
        """Check if this strategy can handle the error."""
        raise NotImplementedError

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        """Attempt to recover from the error."""
        raise NotImplementedError


class RestartMCPServerStrategy(RecoveryStrategy):
    """Recovery strategy for MCP server errors."""

    def __init__(self):
        super().__init__("restart_mcp_server", priority=10, cooldown_seconds=120)

    def can_handle(self, error_record: ErrorRecord) -> bool:
        if error_record.category == ErrorCategory.MCP_SERVER:
            return True
        error_str = str(error_record.error).lower()
        return "mcp" in error_str and "server" in error_str

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        try:
            from core import mcp_loader
        except Exception as exc:
            error_record.context["recovery_error"] = f"mcp_loader_import_failed: {_safe_string(exc)}"
            return False

        stop = getattr(mcp_loader, "stop_mcp_servers", None)
        start = getattr(mcp_loader, "start_mcp_servers", None)
        if not callable(stop) or not callable(start):
            error_record.context["recovery_error"] = "mcp_loader_missing_hooks"
            return False

        try:
            stop()
            time.sleep(2)
            start()
            return True
        except Exception as exc:
            error_record.context["recovery_error"] = _safe_string(exc)
            return False


class RetryWithBackoffStrategy(RecoveryStrategy):
    """Recovery strategy for transient errors."""

    def __init__(self):
        super().__init__("retry_with_backoff", priority=4)
        self.base_delay = 1.0
        self.max_delay = 60.0
        self.jitter = 0.2

    def can_handle(self, error_record: ErrorRecord) -> bool:
        return _is_transient_error(error_record.error)

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        attempt = int(error_record.context.get("_retry_attempts", 0)) + 1
        error_record.context["_retry_attempts"] = attempt
        delay = min(self.max_delay, self.base_delay * (2 ** (attempt - 1)))
        if self.jitter:
            delay *= 1 + random.uniform(-self.jitter, self.jitter)
        error_record.context["retry_after"] = round(delay, 3)
        error_record.context["should_retry"] = True
        should_sleep = bool(error_record.context.get("sleep_on_retry"))
        if should_sleep:
            time.sleep(delay)
        return should_sleep


class ClearCacheStrategy(RecoveryStrategy):
    """Recovery strategy for cache-related errors."""

    def __init__(self):
        super().__init__("clear_cache", priority=7, cooldown_seconds=30)

    def can_handle(self, error_record: ErrorRecord) -> bool:
        cache_keywords = ("cache", "corrupt", "invalid", "malformed")
        error_str = str(error_record.error).lower()
        return any(keyword in error_str for keyword in cache_keywords)

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        try:
            import shutil
        except Exception as exc:
            error_record.context["recovery_error"] = f"shutil_import_failed: {_safe_string(exc)}"
            return False

        cache_dirs = [
            ROOT / "data" / "cache",
            ROOT / "data" / "research_cache",
            ROOT / "data" / "prompt_cache",
        ]

        cleared: List[str] = []
        errors: List[str] = []
        for cache_dir in cache_dirs:
            try:
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                cache_dir.mkdir(parents=True, exist_ok=True)
                cleared.append(str(cache_dir))
            except Exception as exc:
                errors.append(f"{cache_dir}: {_safe_string(exc)}")

        if cleared:
            error_record.context["cleared_caches"] = cleared
        if errors:
            error_record.context["cache_errors"] = errors

        return bool(cleared)


class EnsureDirectoriesStrategy(RecoveryStrategy):
    """Recovery strategy to create missing directories."""

    def __init__(self):
        super().__init__("ensure_directories", priority=6, cooldown_seconds=15)
        self.default_dirs = [
            ROOT / "data",
            ROOT / "logs",
            ROOT / "data" / "cache",
            ROOT / "data" / "research_cache",
            ROOT / "data" / "prompt_cache",
            ROOT / "data" / "tmp",
        ]

    def can_handle(self, error_record: ErrorRecord) -> bool:
        if error_record.category != ErrorCategory.FILESYSTEM:
            return False
        error_str = str(error_record.error).lower()
        if any(keyword in error_str for keyword in ("no such file", "file not found", "directory")):
            return True
        return _extract_path_from_context(error_record.context) is not None

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        created: List[str] = []
        target_path = _extract_path_from_context(error_record.context)
        if target_path and _is_within_root(target_path):
            is_dir_hint = bool(
                error_record.context.get("is_dir")
                or error_record.context.get("expected_dir")
                or error_record.context.get("directory")
            )
            try:
                if is_dir_hint or (not target_path.suffix and not target_path.exists()):
                    path_to_make = target_path
                else:
                    path_to_make = target_path.parent
                path_to_make.mkdir(parents=True, exist_ok=True)
                created.append(str(path_to_make))
            except Exception as exc:
                error_record.context["recovery_error"] = _safe_string(exc)

        for directory in self.default_dirs:
            if directory.exists():
                continue
            try:
                directory.mkdir(parents=True, exist_ok=True)
                created.append(str(directory))
            except Exception as exc:
                error_record.context.setdefault("dir_errors", []).append(_safe_string(exc))

        if created:
            error_record.context["directories_ensured"] = created
        return bool(created)


class InvalidateImportCachesStrategy(RecoveryStrategy):
    """Recovery strategy for dependency errors."""

    def __init__(self):
        super().__init__("invalidate_import_caches", priority=5, cooldown_seconds=10)

    def can_handle(self, error_record: ErrorRecord) -> bool:
        return error_record.category == ErrorCategory.DEPENDENCY

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        import sys

        importlib.invalidate_caches()
        root_str = str(ROOT)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        error_record.context["import_caches_invalidated"] = True
        return True


class GarbageCollectStrategy(RecoveryStrategy):
    """Recovery strategy for memory pressure."""

    def __init__(self):
        super().__init__("garbage_collect", priority=6, cooldown_seconds=30)

    def can_handle(self, error_record: ErrorRecord) -> bool:
        return error_record.category == ErrorCategory.MEMORY or "memory" in str(error_record.error).lower()

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        collected = gc.collect()
        error_record.context["gc_collected"] = collected
        return True


class ResetConfigStrategy(RecoveryStrategy):
    """Recovery strategy for configuration errors."""

    def __init__(self):
        super().__init__("reset_config", priority=8, cooldown_seconds=300)

    def can_handle(self, error_record: ErrorRecord) -> bool:
        if error_record.category == ErrorCategory.CONFIGURATION:
            return True
        error_str = str(error_record.error).lower()
        return any(keyword in error_str for keyword in ("config", "setting", "option", "parameter"))

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        try:
            config_path = error_record.context.get("config_path")
            if config_path:
                path = Path(config_path)
            else:
                path = ROOT / "lifeos" / "config" / "lifeos.config.json"

            if not path.is_absolute():
                path = (ROOT / path).resolve()

            if not _is_within_root(path):
                error_record.context["recovery_error"] = "config_path_outside_project"
                return False

            if path.exists() and path.is_dir():
                error_record.context["recovery_error"] = "config_path_is_directory"
                return False

            if path.exists():
                backup_name = f"{path.name}.backup.{int(time.time())}"
                backup_path = path.with_name(backup_name)
                path.rename(backup_path)
                error_record.context["config_backup"] = str(backup_path)

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
            error_record.context["config_reset"] = str(path)
            return True
        except Exception as exc:
            error_record.context["recovery_error"] = _safe_string(exc)
            return False


class TempPathFallbackStrategy(RecoveryStrategy):
    """Provide a fallback path for file and permission errors."""

    def __init__(self):
        super().__init__("temp_path_fallback", priority=3, cooldown_seconds=10)

    def can_handle(self, error_record: ErrorRecord) -> bool:
        return error_record.category in (ErrorCategory.FILESYSTEM, ErrorCategory.PERMISSION)

    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        target_path = _extract_path_from_context(error_record.context)
        if not target_path:
            return False
        fallback_dir = ROOT / "data" / "tmp"
        try:
            fallback_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            error_record.context["recovery_error"] = _safe_string(exc)
            return False

        fallback_name = target_path.name or f"fallback_{int(time.time())}"
        fallback_path = fallback_dir / fallback_name
        error_record.context["fallback_path"] = str(fallback_path)
        return True


class ErrorRecoveryManager:
    """Manages error detection, categorization, and recovery."""

    def __init__(self, max_history: int = DEFAULT_MAX_HISTORY):
        self.error_history: deque[ErrorRecord] = deque(maxlen=max_history)
        self.max_history = max_history
        self.strategies: List[RecoveryStrategy] = [
            RestartMCPServerStrategy(),
            ResetConfigStrategy(),
            ClearCacheStrategy(),
            EnsureDirectoriesStrategy(),
            GarbageCollectStrategy(),
            InvalidateImportCachesStrategy(),
            RetryWithBackoffStrategy(),
            TempPathFallbackStrategy(),
        ]
        self.error_patterns: Counter[str] = Counter()
        self.max_pattern_entries = 200
        self._strategy_state: Dict[str, StrategyState] = {}
        self._lock = threading.Lock()

    def register_strategy(self, strategy: RecoveryStrategy):
        """Register or replace a recovery strategy."""
        with self._lock:
            self.strategies = [s for s in self.strategies if s.name != strategy.name]
            self.strategies.append(strategy)

    def remove_strategy(self, name: str):
        """Remove a recovery strategy by name."""
        with self._lock:
            self.strategies = [s for s in self.strategies if s.name != name]

    def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    ) -> bool:
        """Handle an error and attempt recovery."""
        context = _coerce_context(context)

        category = self._categorize_error(error)
        error_record = ErrorRecord(error, context, severity, category)

        recovered = self._attempt_recovery(error_record)

        with self._lock:
            self.error_history.append(error_record)
            self._track_error_pattern(error_record)

        self._log_error(error_record)
        return recovered

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error based on its type and message."""
        if isinstance(error, MemoryError):
            return ErrorCategory.MEMORY
        if isinstance(error, (TimeoutError, ConnectionError)):
            return ErrorCategory.NETWORK
        if isinstance(error, FileNotFoundError):
            return ErrorCategory.FILESYSTEM
        if isinstance(error, PermissionError):
            return ErrorCategory.PERMISSION
        if isinstance(error, (ModuleNotFoundError, ImportError)):
            return ErrorCategory.DEPENDENCY
        if isinstance(error, json.JSONDecodeError):
            return ErrorCategory.CONFIGURATION
        if isinstance(error, OSError):
            if error.errno in (errno.EACCES, errno.EPERM):
                return ErrorCategory.PERMISSION
            if error.errno in (errno.ENOENT, errno.ENOSPC):
                return ErrorCategory.FILESYSTEM

        error_str = str(error).lower()
        if any(keyword in error_str for keyword in ("mcp", "model context protocol")):
            return ErrorCategory.MCP_SERVER
        if any(keyword in error_str for keyword in ("config", "setting", "option", "parameter")):
            return ErrorCategory.CONFIGURATION
        if any(keyword in error_str for keyword in ("permission", "access denied", "forbidden")):
            return ErrorCategory.PERMISSION
        if any(keyword in error_str for keyword in ("file not found", "no such file", "directory", "path", "disk", "space")):
            return ErrorCategory.FILESYSTEM
        if any(keyword in error_str for keyword in ("memory", "out of memory", "oom")):
            return ErrorCategory.MEMORY
        if any(keyword in error_str for keyword in ("module", "import", "dependency", "package")):
            return ErrorCategory.DEPENDENCY
        if _is_transient_error(error):
            return ErrorCategory.NETWORK

        return ErrorCategory.UNKNOWN

    def _rotate_log_if_needed(self):
        try:
            if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > MAX_LOG_BYTES:
                backup_path = ERROR_LOG_PATH.with_name(
                    f"{ERROR_LOG_PATH.name}.{int(time.time())}.backup"
                )
                ERROR_LOG_PATH.rename(backup_path)
        except Exception:
            pass

    def _write_log(self, log_entry: Dict[str, Any]):
        try:
            with self._lock:
                self._rotate_log_if_needed()
                ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                with open(ERROR_LOG_PATH, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(log_entry, ensure_ascii=True) + "\n")
        except Exception:
            pass

    def _log_error(self, error_record: ErrorRecord):
        """Log error to file."""
        log_entry = {
            "timestamp": _now_iso(error_record.timestamp),
            "event": "error",
            **error_record.to_dict(),
        }
        self._write_log(log_entry)

    def _track_error_pattern(self, error_record: ErrorRecord):
        """Track error patterns for analysis."""
        key = f"{error_record.category.value}:{type(error_record.error).__name__}"
        self.error_patterns[key] += 1
        if len(self.error_patterns) > self.max_pattern_entries:
            self.error_patterns = Counter(dict(self.error_patterns.most_common(self.max_pattern_entries)))

    def _strategy_key(self, strategy: RecoveryStrategy, category: ErrorCategory) -> str:
        return f"{strategy.name}:{category.value}"

    def _strategy_ready(self, strategy: RecoveryStrategy, category: ErrorCategory) -> bool:
        if strategy.cooldown_seconds <= 0:
            return True
        key = self._strategy_key(strategy, category)
        now = time.time()
        with self._lock:
            state = self._strategy_state.get(key)
            if state and (now - state.last_attempt) < strategy.cooldown_seconds:
                return False
        return True

    def _update_strategy_state(self, strategy: RecoveryStrategy, category: ErrorCategory, success: bool):
        key = self._strategy_key(strategy, category)
        now = time.time()
        with self._lock:
            state = self._strategy_state.setdefault(key, StrategyState())
            state.last_attempt = now
            state.attempts += 1
            if success:
                state.successes += 1
            else:
                state.failures += 1

    def _attempt_recovery(self, error_record: ErrorRecord) -> bool:
        """Attempt to recover from the error using available strategies."""
        applicable_strategies = [s for s in self.strategies if s.can_handle(error_record)]
        applicable_strategies.sort(key=lambda x: x.priority, reverse=True)

        for strategy in applicable_strategies:
            if not self._strategy_ready(strategy, error_record.category):
                error_record.recovery_trace.append(
                    {"strategy": strategy.name, "skipped": True, "reason": "cooldown"}
                )
                continue

            error_record.recovery_attempts += 1
            start = time.time()
            success = False
            recovery_error: Optional[str] = None

            try:
                success = strategy.attempt_recovery(error_record)
            except Exception as exc:
                recovery_error = _safe_string(exc)
                error_record.context[f"recovery_error_{strategy.name}"] = recovery_error

            duration = round(time.time() - start, 4)
            error_record.recovery_trace.append(
                {
                    "strategy": strategy.name,
                    "success": success,
                    "duration": duration,
                    "error": recovery_error,
                }
            )
            self._update_strategy_state(strategy, error_record.category, success)

            if success:
                error_record.resolved = True
                self._log_recovery_success(error_record, strategy)
                return True

        return False

    def _log_recovery_success(self, error_record: ErrorRecord, strategy: RecoveryStrategy):
        """Log successful recovery."""
        log_entry = {
            "timestamp": _now_iso(),
            "event": "recovery_success",
            "error_id": error_record.error_id,
            "original_error": _safe_string(error_record.error),
            "strategy": strategy.name,
            "attempts": error_record.recovery_attempts,
        }
        self._write_log(log_entry)

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        if not self.error_history:
            return {
                "total_errors": 0,
                "resolved_errors": 0,
                "resolution_rate": 0.0,
                "by_category": {},
                "by_severity": {},
                "common_patterns": {},
            }

        by_category = Counter(record.category.value for record in self.error_history)
        by_severity = Counter(record.severity.value for record in self.error_history)
        resolved_count = sum(1 for record in self.error_history if record.resolved)
        total_errors = len(self.error_history)

        return {
            "total_errors": total_errors,
            "resolved_errors": resolved_count,
            "resolution_rate": resolved_count / total_errors if total_errors else 0,
            "by_category": dict(by_category),
            "by_severity": dict(by_severity),
            "common_patterns": dict(self.error_patterns.most_common(10)),
        }

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors."""
        recent = sorted(self.error_history, key=lambda x: x.timestamp, reverse=True)[:limit]
        return [record.to_dict() for record in recent]


# Global error recovery manager
_error_manager: Optional[ErrorRecoveryManager] = None


def get_error_manager() -> ErrorRecoveryManager:
    """Get the global error recovery manager."""
    global _error_manager
    if _error_manager is None:
        _error_manager = ErrorRecoveryManager()
    return _error_manager


def handle_error(
    error: Exception,
    context: Dict[str, Any] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
) -> bool:
    """Convenience function to handle an error."""
    return get_error_manager().handle_error(error, context, severity)


def safe_execute(
    func: Callable,
    *args,
    context: Dict[str, Any] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    fallback: Optional[Callable[[Exception], Any]] = None,
    retries: int = 0,
    retry_backoff: float = 1.0,
    retry_jitter: float = 0.2,
    retry_max_delay: float = 60.0,
    retry_on: Optional[Callable[[Exception], bool]] = None,
    **kwargs,
) -> Any:
    """Execute a function safely with error handling, retries, and optional fallback."""
    base_context = _coerce_context(context)
    base_context.setdefault("function", getattr(func, "__name__", "unknown"))

    last_error: Optional[Exception] = None
    attempt = 0
    while attempt <= retries:
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            attempt_context = dict(base_context)
            attempt_context["attempt"] = attempt + 1
            attempt_context["max_attempts"] = retries + 1
            handle_error(exc, attempt_context, severity)

            if attempt >= retries:
                break

            try:
                should_retry = retry_on(exc) if retry_on else _is_transient_error(exc)
            except Exception:
                should_retry = False

            if not should_retry:
                break

            delay = min(retry_max_delay, retry_backoff * (2 ** attempt))
            if retry_jitter:
                delay *= 1 + random.uniform(-retry_jitter, retry_jitter)
            time.sleep(delay)
            attempt += 1

    if fallback is not None:
        try:
            return fallback(last_error) if callable(fallback) else fallback
        except Exception as fallback_error:
            handle_error(fallback_error, {"function": "safe_execute_fallback"}, severity)
            raise

    if last_error is not None:
        raise last_error
    return None
