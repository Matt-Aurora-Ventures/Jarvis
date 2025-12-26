"""Enhanced Error Handling and Recovery for Jarvis."""

import json
import traceback
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

ROOT = Path(__file__).resolve().parents[1]
ERROR_LOG_PATH = ROOT / "data" / "error_recovery.log"


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


class ErrorRecord:
    """Record of an error with context."""
    
    def __init__(
        self,
        error: Exception,
        context: Dict[str, Any],
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        category: ErrorCategory = ErrorCategory.UNKNOWN
    ):
        self.error = error
        self.context = context
        self.severity = severity
        self.category = category
        self.timestamp = time.time()
        self.stack_trace = traceback.format_exc()
        self.recovery_attempts = 0
        self.resolved = False
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "error": str(self.error),
            "type": type(self.error).__name__,
            "context": self.context,
            "severity": self.severity.value,
            "category": self.category.value,
            "timestamp": self.timestamp,
            "stack_trace": self.stack_trace,
            "recovery_attempts": self.recovery_attempts,
            "resolved": self.resolved
        }


class RecoveryStrategy:
    """Base class for recovery strategies."""
    
    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority
        
    def can_handle(self, error_record: ErrorRecord) -> bool:
        """Check if this strategy can handle the error."""
        raise NotImplementedError
        
    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        """Attempt to recover from the error."""
        raise NotImplementedError


class RestartMCPServerStrategy(RecoveryStrategy):
    """Recovery strategy for MCP server errors."""
    
    def __init__(self):
        super().__init__("restart_mcp_server", priority=10)
        
    def can_handle(self, error_record: ErrorRecord) -> bool:
        return (
            error_record.category == ErrorCategory.MCP_SERVER or
            ("mcp" in str(error_record.error).lower() and "server" in str(error_record.error).lower())
        )
        
    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        try:
            from core import mcp_loader
            mcp_loader.stop_mcp_servers()
            time.sleep(2)
            mcp_loader.start_mcp_servers()
            return True
        except Exception as e:
            error_record.context["recovery_error"] = str(e)
            return False


class RetryWithBackoffStrategy(RecoveryStrategy):
    """Recovery strategy for transient errors."""
    
    def __init__(self):
        super().__init__("retry_with_backoff", priority=5)
        
    def can_handle(self, error_record: ErrorRecord) -> bool:
        # Handle network and temporary errors
        transient_keywords = ["connection", "timeout", "temporary", "busy", "unavailable"]
        error_str = str(error_record.error).lower()
        return any(keyword in error_str for keyword in transient_keywords)
        
    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        # Just wait and retry
        backoff_time = min(300, 2 ** error_record.recovery_attempts)  # Max 5 minutes
        time.sleep(backoff_time)
        return True


class ClearCacheStrategy(RecoveryStrategy):
    """Recovery strategy for cache-related errors."""
    
    def __init__(self):
        super().__init__("clear_cache", priority=7)
        
    def can_handle(self, error_record: ErrorRecord) -> bool:
        cache_keywords = ["cache", "corrupt", "invalid", "malformed"]
        error_str = str(error_record.error).lower()
        return any(keyword in error_str for keyword in cache_keywords)
        
    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        try:
            # Clear various caches
            import shutil
            cache_dirs = [
                ROOT / "data" / "cache",
                ROOT / "data" / "research_cache",
                ROOT / "data" / "prompt_cache"
            ]
            
            for cache_dir in cache_dirs:
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
                    cache_dir.mkdir(parents=True, exist_ok=True)
            
            return True
        except Exception as e:
            error_record.context["recovery_error"] = str(e)
            return False


class ResetConfigStrategy(RecoveryStrategy):
    """Recovery strategy for configuration errors."""
    
    def __init__(self):
        super().__init__("reset_config", priority=8)
        
    def can_handle(self, error_record: ErrorRecord) -> bool:
        return error_record.category == ErrorCategory.CONFIGURATION
        
    def attempt_recovery(self, error_record: ErrorRecord) -> bool:
        try:
            # Reset to default configuration
            config_path = ROOT / "lifeos" / "config" / "lifeos.config.json"
            if config_path.exists():
                backup_path = config_path.with_suffix(".json.backup")
                config_path.rename(backup_path)
            return True
        except Exception as e:
            error_record.context["recovery_error"] = str(e)
            return False


class ErrorRecoveryManager:
    """Manages error detection, categorization, and recovery."""
    
    def __init__(self):
        self.error_history: List[ErrorRecord] = []
        self.max_history = 100
        self.strategies: List[RecoveryStrategy] = [
            RestartMCPServerStrategy(),
            ClearCacheStrategy(),
            ResetConfigStrategy(),
            RetryWithBackoffStrategy(),
        ]
        self.error_patterns: Dict[str, int] = {}
        
    def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM
    ) -> bool:
        """Handle an error and attempt recovery."""
        context = context or {}
        
        # Categorize error
        category = self._categorize_error(error)
        
        # Create error record
        error_record = ErrorRecord(error, context, severity, category)
        
        # Log error
        self._log_error(error_record)
        
        # Track patterns
        self._track_error_pattern(error_record)
        
        # Attempt recovery
        recovered = self._attempt_recovery(error_record)
        
        # Add to history
        self.error_history.append(error_record)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
            
        return recovered
        
    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an error based on its type and message."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # Network errors
        if any(keyword in error_str for keyword in ["connection", "network", "internet", "timeout", "unreachable"]):
            return ErrorCategory.NETWORK
            
        # Filesystem errors
        if any(keyword in error_str for keyword in ["file", "directory", "path", "disk", "space"]):
            return ErrorCategory.FILESYSTEM
            
        # Permission errors
        if any(keyword in error_str for keyword in ["permission", "access", "denied", "forbidden"]):
            return ErrorCategory.PERMISSION
            
        # Memory errors
        if any(keyword in error_str for keyword in ["memory", "out of memory", "oom"]):
            return ErrorCategory.MEMORY
            
        # Dependency errors
        if any(keyword in error_str for keyword in ["module", "import", "dependency", "package"]):
            return ErrorCategory.DEPENDENCY
            
        # MCP server errors
        if any(keyword in error_str for keyword in ["mcp", "server", "protocol"]):
            return ErrorCategory.MCP_SERVER
            
        # Configuration errors
        if any(keyword in error_str for keyword in ["config", "setting", "option", "parameter"]):
            return ErrorCategory.CONFIGURATION
            
        return ErrorCategory.UNKNOWN
        
    def _log_error(self, error_record: ErrorRecord):
        """Log error to file."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(error_record.timestamp).isoformat(),
            **error_record.to_dict()
        }
        
        try:
            ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(ERROR_LOG_PATH, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass  # Avoid logging errors causing more errors
            
    def _track_error_pattern(self, error_record: ErrorRecord):
        """Track error patterns for analysis."""
        key = f"{error_record.category.value}:{type(error_record.error).__name__}"
        self.error_patterns[key] = self.error_patterns.get(key, 0) + 1
        
    def _attempt_recovery(self, error_record: ErrorRecord) -> bool:
        """Attempt to recover from the error using available strategies."""
        # Sort strategies by priority
        applicable_strategies = [
            s for s in self.strategies if s.can_handle(error_record)
        ]
        applicable_strategies.sort(key=lambda x: x.priority, reverse=True)
        
        for strategy in applicable_strategies:
            error_record.recovery_attempts += 1
            
            try:
                if strategy.attempt_recovery(error_record):
                    error_record.resolved = True
                    self._log_recovery_success(error_record, strategy)
                    return True
                    
            except Exception as recovery_error:
                error_record.context[f"recovery_error_{strategy.name}"] = str(recovery_error)
                
        return False
        
    def _log_recovery_success(self, error_record: ErrorRecord, strategy: RecoveryStrategy):
        """Log successful recovery."""
        log_entry = {
            "timestamp": datetime.fromtimestamp(time.time()).isoformat(),
            "event": "recovery_success",
            "original_error": str(error_record.error),
            "strategy": strategy.name,
            "attempts": error_record.recovery_attempts
        }
        
        try:
            with open(ERROR_LOG_PATH, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass
            
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        if not self.error_history:
            return {"total_errors": 0}
            
        # Count by category
        by_category = {}
        by_severity = {}
        resolved_count = 0
        
        for record in self.error_history:
            # Category counts
            cat = record.category.value
            by_category[cat] = by_category.get(cat, 0) + 1
            
            # Severity counts
            sev = record.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
            
            # Resolved count
            if record.resolved:
                resolved_count += 1
                
        return {
            "total_errors": len(self.error_history),
            "resolved_errors": resolved_count,
            "resolution_rate": resolved_count / len(self.error_history) if self.error_history else 0,
            "by_category": by_category,
            "by_severity": by_severity,
            "common_patterns": dict(sorted(self.error_patterns.items(), key=lambda x: x[1], reverse=True)[:10])
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
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
) -> bool:
    """Convenience function to handle an error."""
    return get_error_manager().handle_error(error, context, severity)


def safe_execute(
    func: Callable,
    *args,
    context: Dict[str, Any] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    **kwargs
) -> Any:
    """Execute a function safely with error handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        handle_error(e, context or {}, severity)
        raise
