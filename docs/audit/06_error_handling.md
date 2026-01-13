# Error Handling & Logging Improvements (71-80)

## 71. Structured Logging

```python
# core/logging/structured.py
import json
import logging
from datetime import datetime
from typing import Any

class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)

def setup_structured_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
```

## 72. Error Classification System

```python
# core/errors/classification.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ErrorCategory(str, Enum):
    VALIDATION = "VAL"
    AUTHENTICATION = "AUTH"
    AUTHORIZATION = "AUTHZ"
    PROVIDER = "PROV"
    SYSTEM = "SYS"
    NETWORK = "NET"
    DATABASE = "DB"
    TRADING = "TRADE"

@dataclass
class ClassifiedError:
    code: str
    category: ErrorCategory
    message: str
    recoverable: bool
    retry_after: Optional[int] = None

ERROR_CODES = {
    "VAL_001": ClassifiedError("VAL_001", ErrorCategory.VALIDATION, "Invalid input", True),
    "AUTH_001": ClassifiedError("AUTH_001", ErrorCategory.AUTHENTICATION, "Invalid credentials", True),
    "PROV_001": ClassifiedError("PROV_001", ErrorCategory.PROVIDER, "Provider unavailable", True, 30),
    "SYS_001": ClassifiedError("SYS_001", ErrorCategory.SYSTEM, "Internal error", False),
    "TRADE_001": ClassifiedError("TRADE_001", ErrorCategory.TRADING, "Insufficient balance", True),
}

def classify_error(exception: Exception) -> ClassifiedError:
    if isinstance(exception, ValueError):
        return ERROR_CODES["VAL_001"]
    if "authentication" in str(exception).lower():
        return ERROR_CODES["AUTH_001"]
    return ERROR_CODES["SYS_001"]
```

## 73. Sentry Integration

```python
# core/monitoring/sentry.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import os

def init_sentry():
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    
    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        before_send=filter_sensitive_data,
    )

def filter_sensitive_data(event, hint):
    if "request" in event:
        headers = event["request"].get("headers", {})
        for key in ["Authorization", "X-API-Key", "Cookie"]:
            if key in headers:
                headers[key] = "[FILTERED]"
    return event

def capture_with_context(exception: Exception, context: dict):
    with sentry_sdk.push_scope() as scope:
        for key, value in context.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(exception)
```

## 74. Custom Exception Hierarchy

```python
# core/errors/exceptions.py
from typing import Optional, Dict, Any

class JarvisError(Exception):
    """Base exception for all Jarvis errors."""
    code: str = "SYS_001"
    status_code: int = 500
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

class ValidationError(JarvisError):
    code = "VAL_001"
    status_code = 400

class AuthenticationError(JarvisError):
    code = "AUTH_001"
    status_code = 401

class AuthorizationError(JarvisError):
    code = "AUTHZ_001"
    status_code = 403

class NotFoundError(JarvisError):
    code = "SYS_002"
    status_code = 404

class RateLimitError(JarvisError):
    code = "RATE_001"
    status_code = 429
    
    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message, {"retry_after": retry_after})
        self.retry_after = retry_after

class ProviderError(JarvisError):
    code = "PROV_001"
    status_code = 503

class TradingError(JarvisError):
    code = "TRADE_001"
    status_code = 400
```

## 75. Error Recovery Strategies

```python
# core/errors/recovery.py
import asyncio
from typing import Callable, TypeVar, Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)
T = TypeVar('T')

class RecoveryStrategy:
    @staticmethod
    async def retry(func: Callable, max_attempts: int = 3, delay: float = 1.0) -> T:
        for attempt in range(max_attempts):
            try:
                return await func()
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise
                logger.warning(f"Attempt {attempt + 1} failed: {e}, retrying...")
                await asyncio.sleep(delay * (2 ** attempt))
    
    @staticmethod
    async def fallback(func: Callable, fallback_func: Callable) -> T:
        try:
            return await func()
        except Exception as e:
            logger.warning(f"Primary failed: {e}, using fallback")
            return await fallback_func()
    
    @staticmethod
    async def circuit_breaker(func: Callable, failure_threshold: int = 5) -> T:
        # Simplified circuit breaker
        if getattr(func, '_failures', 0) >= failure_threshold:
            raise Exception("Circuit breaker open")
        try:
            result = await func()
            func._failures = 0
            return result
        except Exception:
            func._failures = getattr(func, '_failures', 0) + 1
            raise

def with_recovery(strategy: str = "retry", **kwargs):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **inner_kwargs):
            if strategy == "retry":
                return await RecoveryStrategy.retry(lambda: func(*args, **inner_kwargs), **kwargs)
            return await func(*args, **inner_kwargs)
        return wrapper
    return decorator
```

## 76. Dead Letter Queue

```python
# core/errors/dlq.py
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class DeadLetterQueue:
    def __init__(self, path: Path = Path("data/dlq")):
        self.path = path
        self.path.mkdir(parents=True, exist_ok=True)
    
    def add(self, event_type: str, payload: Dict[str, Any], error: Exception):
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "payload": payload,
            "error": str(error),
            "error_type": type(error).__name__,
            "retries": 0
        }
        filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{event_type}.json"
        (self.path / filename).write_text(json.dumps(entry, indent=2))
        logger.error(f"Added to DLQ: {event_type} - {error}")
    
    def process_pending(self, handler: Callable):
        for file in self.path.glob("*.json"):
            entry = json.loads(file.read_text())
            if entry["retries"] < 3:
                try:
                    handler(entry["event_type"], entry["payload"])
                    file.unlink()
                    logger.info(f"Processed DLQ entry: {file.name}")
                except Exception as e:
                    entry["retries"] += 1
                    entry["last_error"] = str(e)
                    file.write_text(json.dumps(entry, indent=2))
```

## 77. Alert Thresholds

```python
# core/monitoring/alerts.py
from dataclasses import dataclass
from typing import Callable, Dict, List
from collections import deque
import time
import logging

logger = logging.getLogger(__name__)

@dataclass
class AlertRule:
    name: str
    metric: str
    threshold: float
    window_seconds: int
    comparison: str  # "gt", "lt", "eq"
    cooldown_seconds: int = 300

class AlertManager:
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.metrics: Dict[str, deque] = {}
        self.last_alert: Dict[str, float] = {}
        self.handlers: List[Callable] = []
    
    def add_rule(self, rule: AlertRule):
        self.rules.append(rule)
        self.metrics[rule.metric] = deque()
    
    def record(self, metric: str, value: float):
        if metric not in self.metrics:
            self.metrics[metric] = deque()
        self.metrics[metric].append((time.time(), value))
        self._check_rules(metric)
    
    def _check_rules(self, metric: str):
        now = time.time()
        for rule in self.rules:
            if rule.metric != metric:
                continue
            
            # Check cooldown
            if now - self.last_alert.get(rule.name, 0) < rule.cooldown_seconds:
                continue
            
            # Get values in window
            values = [v for t, v in self.metrics[metric] if now - t <= rule.window_seconds]
            if not values:
                continue
            
            avg = sum(values) / len(values)
            triggered = (
                (rule.comparison == "gt" and avg > rule.threshold) or
                (rule.comparison == "lt" and avg < rule.threshold)
            )
            
            if triggered:
                self.last_alert[rule.name] = now
                self._fire_alert(rule, avg)
    
    def _fire_alert(self, rule: AlertRule, value: float):
        logger.warning(f"ALERT: {rule.name} - {rule.metric}={value:.2f} (threshold: {rule.threshold})")
        for handler in self.handlers:
            handler(rule, value)
```

## 78. Log Aggregation

```python
# core/logging/aggregation.py
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict
import gzip

class LogAggregator:
    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
    
    def aggregate_daily(self, date: datetime = None) -> Dict:
        date = date or datetime.utcnow()
        log_file = self.log_dir / f"app-{date.strftime('%Y-%m-%d')}.log"
        
        if not log_file.exists():
            return {}
        
        stats = {"total": 0, "errors": 0, "warnings": 0, "by_module": {}}
        
        with open(log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    stats["total"] += 1
                    if entry.get("level") == "ERROR":
                        stats["errors"] += 1
                    elif entry.get("level") == "WARNING":
                        stats["warnings"] += 1
                    
                    module = entry.get("module", "unknown")
                    stats["by_module"][module] = stats["by_module"].get(module, 0) + 1
                except json.JSONDecodeError:
                    continue
        
        return stats
    
    def compress_old_logs(self, days_old: int = 7):
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff.timestamp():
                with open(log_file, 'rb') as f_in:
                    with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                        f_out.writelines(f_in)
                log_file.unlink()
```

## 79. Debug Mode

```python
# core/debug/mode.py
import os
import functools
import time
import logging

logger = logging.getLogger(__name__)

DEBUG_MODE = os.getenv("DEBUG", "false").lower() == "true"

def debug_only(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not DEBUG_MODE:
            return None
        return func(*args, **kwargs)
    return wrapper

def trace_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if DEBUG_MODE:
            logger.debug(f"CALL: {func.__name__}({args}, {kwargs})")
            start = time.time()
            result = func(*args, **kwargs)
            logger.debug(f"RETURN: {func.__name__} = {result} ({time.time()-start:.3f}s)")
            return result
        return func(*args, **kwargs)
    return wrapper

@debug_only
def dump_state(name: str, state: dict):
    import json
    Path(f"debug/{name}_{int(time.time())}.json").write_text(json.dumps(state, indent=2, default=str))
```

## 80. Error Analytics

```python
# core/analytics/errors.py
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, List
import json

class ErrorAnalytics:
    def __init__(self):
        self.errors: List[Dict] = []
    
    def record(self, error_code: str, message: str, context: Dict = None):
        self.errors.append({
            "timestamp": datetime.utcnow().isoformat(),
            "code": error_code,
            "message": message,
            "context": context or {}
        })
    
    def get_summary(self, hours: int = 24) -> Dict:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [e for e in self.errors if datetime.fromisoformat(e["timestamp"]) > cutoff]
        
        return {
            "total": len(recent),
            "by_code": dict(Counter(e["code"] for e in recent)),
            "by_hour": self._group_by_hour(recent),
            "top_messages": Counter(e["message"] for e in recent).most_common(10)
        }
    
    def _group_by_hour(self, errors: List[Dict]) -> Dict[str, int]:
        by_hour = defaultdict(int)
        for e in errors:
            hour = datetime.fromisoformat(e["timestamp"]).strftime("%Y-%m-%d %H:00")
            by_hour[hour] += 1
        return dict(by_hour)
```
