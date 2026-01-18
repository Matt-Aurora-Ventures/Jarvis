# Feature Plan: Feature Flags System and Structured Logging Architecture

Created: 2026-01-18
Author: architect-agent

---

## Overview

This plan defines two interconnected infrastructure systems for Jarvis:

1. **Feature Flags System**: A runtime-configurable system for enabling/disabling features, A/B testing, gradual rollouts, and environment-specific behavior without code deployment.

2. **Structured Logging Architecture**: A JSON-based logging system with standardized fields, log aggregation, retention policies, and query capabilities for debugging and monitoring.

These systems integrate to provide full observability: logs indicate which flags were active during any operation, enabling powerful debugging and performance analysis.

---

## Part 1: Feature Flags System

### 1.1 Requirements

- [ ] Enable/disable features without deployment
- [ ] Support A/B testing (percentage-based rollouts)
- [ ] Support gradual rollouts (early adopters, user segments)
- [ ] Support environment-specific flags (dev/staging/prod)
- [ ] Hot-reload flags without restart (build on existing ConfigHotReload)
- [ ] Audit trail of flag changes
- [ ] Admin UI for managing flags (Telegram commands + optional web UI)
- [ ] Default-safe behavior (features fail closed if flag unavailable)

### 1.2 Architecture Diagram

```
                    +---------------------------------------------+
                    |              Flag Sources                   |
                    |  +---------+  +---------+  +-------------+  |
                    |  | JSON    |  | Env     |  | Runtime     |  |
                    |  | Files   |  | Vars    |  | Override    |  |
                    |  +----+----+  +----+----+  +------+------+  |
                    +-------|-----------|-------------|------------+
                            |           |             |
                            v           v             v
                    +---------------------------------------------+
                    |          FeatureFlagManager (Singleton)     |
                    |  +-------------------------------------+    |
                    |  | Flag Registry                       |    |
                    |  | - flag_id -> FlagDefinition         |    |
                    |  | - evaluation cache (TTL=30s)        |    |
                    |  | - change callbacks                  |    |
                    |  +-------------------------------------+    |
                    |                                             |
                    |  +-------------------------------------+    |
                    |  | Evaluation Engine                   |    |
                    |  | - percentage rollouts (hash-based)  |    |
                    |  | - user segment matching             |    |
                    |  | - environment filtering             |    |
                    |  | - datetime-based rules              |    |
                    |  +-------------------------------------+    |
                    +-------------------+-------------------------+
                                        |
                    +-------------------+-------------------------+
                    |                   |                         |
                    v                   v                         v
            +---------------+   +---------------+   +---------------+
            | Trading       |   | Telegram      |   | API           |
            | Engine        |   | Bot           |   | Server        |
            +---------------+   +---------------+   +---------------+
```


### 1.3 Data Model

#### 1.3.1 Flag Definition Schema (Python)

```python
# core/feature_flags/models.py

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime


class FlagType(str, Enum):
    BOOLEAN = "boolean"           # Simple on/off
    PERCENTAGE = "percentage"     # % of users/requests
    USER_SEGMENT = "user_segment" # Based on user attributes
    ENVIRONMENT = "environment"   # Based on env (dev/staging/prod)
    SCHEDULE = "schedule"         # Time-based activation


class FlagStatus(str, Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"   # Still works but marked for removal
    DISABLED = "disabled"       # Completely off, ignores all rules


@dataclass
class RolloutRule:
    type: str                  # "percentage", "user_ids", "environments", "schedule"
    value: Any                 # Rule-specific value
    priority: int = 0          # Higher = evaluated first


@dataclass
class FlagDefinition:
    # Identity
    id: str                              # "DEXTER_ENABLED"
    name: str                            # "Dexter ReAct Agent"
    description: str                     # What this flag controls
    
    # State
    enabled: bool = False                # Global default state
    status: FlagStatus = FlagStatus.ACTIVE
    
    # Categorization
    category: str = "general"            # "trading", "ui", "experimental"
    owner: str = ""                      # Who owns this flag
    
    # Rollout rules (evaluated in priority order)
    rules: List[RolloutRule] = field(default_factory=list)
    
    # Environment defaults
    environment_defaults: Dict[str, bool] = field(default_factory=dict)
    # e.g., {"dev": True, "staging": True, "prod": False}
    
    # Metadata
    created_at: str = ""
    updated_at: str = ""
    expires_at: Optional[str] = None     # Optional auto-disable date
    
    # Safety
    requires_restart: bool = False
    dangerous: bool = False              # Extra confirmation required?


@dataclass
class EvaluationContext:
    user_id: Optional[str] = None        # Telegram user ID, etc.
    environment: str = "prod"            # dev/staging/prod
    request_id: Optional[str] = None     # For consistent % evaluation
    attributes: Dict[str, Any] = field(default_factory=dict)
```

#### 1.3.2 JSON File Schema

```json
{
  "$schema": "./feature_flags.schema.json",
  "version": "1.0",
  "environment": "prod",
  "flags": {
    "DEXTER_ENABLED": {
      "name": "Dexter ReAct Agent",
      "description": "Enable the Dexter autonomous trading agent",
      "enabled": false,
      "status": "active",
      "category": "trading",
      "owner": "trading-team",
      "rules": [
        {"type": "environments", "value": ["dev", "staging"], "priority": 10},
        {"type": "user_ids", "value": ["123456789"], "priority": 5}
      ],
      "environment_defaults": {"dev": true, "staging": true, "prod": false},
      "dangerous": true
    },
    "ADVANCED_TRADING_ENABLED": {
      "name": "Advanced Trading Features",
      "description": "Trailing stops, DCA, grid trading",
      "enabled": false,
      "category": "trading",
      "rules": [{"type": "percentage", "value": 10, "priority": 5}],
      "environment_defaults": {"dev": true, "staging": true, "prod": false},
      "dangerous": true
    },
    "NEW_TELEGRAM_UI_ENABLED": {
      "name": "New Telegram UI",
      "description": "Inline buttons and improved navigation",
      "enabled": false,
      "category": "ui",
      "rules": [{"type": "percentage", "value": 25, "priority": 5}],
      "environment_defaults": {"dev": true, "staging": true, "prod": false}
    },
    "LIVE_TRADING_ENABLED": {
      "name": "Live Trading",
      "description": "Allow real trades (vs paper/dry-run)",
      "enabled": false,
      "category": "trading",
      "environment_defaults": {"dev": false, "staging": false, "prod": false},
      "dangerous": true
    }
  }
}
```


### 1.4 API Design

```python
# core/feature_flags/manager.py

class FeatureFlagManager:
    """
    Singleton manager for feature flags.
    
    Usage:
        from core.feature_flags import flags
        
        if flags.is_enabled("DEXTER_ENABLED"):
            await run_dexter()
        
        # With context (for A/B, user segments)
        if flags.is_enabled("NEW_UI", user_id="123456"):
            show_new_ui()
    """
    
    _instance = None
    
    # === Core API ===
    
    def is_enabled(
        self,
        flag_id: str,
        default: bool = False,
        user_id: Optional[str] = None,
        context: Optional[EvaluationContext] = None,
    ) -> bool:
        """Check if a feature flag is enabled."""
        ...
    
    def get_flag(self, flag_id: str) -> Optional[FlagDefinition]:
        """Get full flag definition."""
        ...
    
    def list_flags(
        self,
        category: Optional[str] = None,
        status: Optional[FlagStatus] = None,
    ) -> List[FlagDefinition]:
        """List all flags, optionally filtered."""
        ...
    
    # === Admin API ===
    
    def set_enabled(
        self,
        flag_id: str,
        enabled: bool,
        reason: str = "",
        admin_id: Optional[str] = None,
    ) -> bool:
        """Set flag enabled state (admin only)."""
        ...
    
    def create_flag(self, definition: FlagDefinition) -> bool:
        """Create a new flag."""
        ...
    
    # === Callbacks ===
    
    def on_change(self, flag_id: str, callback: Callable[[str, bool, bool], None]):
        """Register callback for flag changes. Signature: (flag_id, old, new)"""
        ...
    
    # === Persistence ===
    
    def load_from_file(self, path: Path): ...
    def save_to_file(self, path: Path): ...
    def reload(self): ...


# Singleton accessor
def get_flags() -> FeatureFlagManager:
    if FeatureFlagManager._instance is None:
        FeatureFlagManager._instance = FeatureFlagManager()
    return FeatureFlagManager._instance

flags = get_flags()  # Convenience alias
```

### 1.5 File Structure

```
core/
  feature_flags/
    __init__.py           # Exports: flags, is_enabled, get_flags
    models.py             # FlagDefinition, RolloutRule, EvaluationContext
    manager.py            # FeatureFlagManager singleton
    evaluator.py          # Rule evaluation logic
    persistence.py        # JSON file loading/saving
    admin.py              # Admin operations with audit logging

config/
  feature_flags.json        # Primary flag definitions
  feature_flags.local.json  # Local overrides (gitignored)
  feature_flags.schema.json # JSON schema for validation

tg_bot/
  handlers/
    flag_admin_handler.py   # Telegram admin commands for flags
```

### 1.6 Telegram Admin Commands

| Command | Description |
|---------|-------------|
| `/flags` | List all flags with status |
| `/flag <FLAG_ID>` | Show flag details |
| `/flag_enable <FLAG_ID>` | Enable a flag |
| `/flag_disable <FLAG_ID>` | Disable a flag |
| `/flag_toggle <FLAG_ID>` | Toggle flag state |
| `/flag_rollout <FLAG_ID> <PCT>` | Set percentage rollout |
| `/flag_history <FLAG_ID>` | Show change history |

### 1.7 Environment Variable Overrides

```bash
# Force enable in development
export FF_DEXTER_ENABLED=true
export FF_LIVE_TRADING_ENABLED=false  # Always false locally

# Override environment detection
export JARVIS_ENVIRONMENT=staging
```


---

## Part 2: Structured Logging Architecture

### 2.1 Requirements

- [ ] JSON format for all logs (machine-parseable)
- [ ] Standard log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- [ ] Structured fields: timestamp, service, level, message, context
- [ ] Request/correlation ID tracking across components
- [ ] Feature flag state included in relevant logs
- [ ] Log aggregation plan (local files + optional remote)
- [ ] Log retention policy (7 days local, 30 days archived)
- [ ] Query/search capabilities
- [ ] Performance: minimal overhead on hot paths

### 2.2 Architecture Diagram

```
                    +---------------------------------------------+
                    |            Application Code                 |
                    |  +---------+  +---------+  +-------------+  |
                    |  | Trading |  | TG Bot  |  | API Server  |  |
                    |  +----+----+  +----+----+  +------+------+  |
                    +-------|-----------|-------------|------------+
                            |           |             |
                            v           v             v
                    +---------------------------------------------+
                    |         StructuredLogger (per-service)      |
                    |  +-------------------------------------+    |
                    |  | Context Manager                     |    |
                    |  | - correlation_id                    |    |
                    |  | - user_id                           |    |
                    |  | - feature_flags                     |    |
                    |  | - service_name                      |    |
                    |  +-------------------------------------+    |
                    |                                             |
                    |  +-------------------------------------+    |
                    |  | Formatters                          |    |
                    |  | - JSONFormatter                     |    |
                    |  | - HumanFormatter (console)          |    |
                    |  +-------------------------------------+    |
                    +-------------------+-------------------------+
                                        |
                    +-------------------+-------------------+
                    |                   |                   |
                    v                   v                   v
            +---------------+   +---------------+   +---------------+
            | Console       |   | File Handler  |   | Remote        |
            | (human fmt)   |   | (JSON)        |   | (optional)    |
            |               |   |               |   |               |
            | Development   |   | logs/jarvis-  |   | Loki/ELK/     |
            | debugging     |   | YYYY-MM-DD.   |   | CloudWatch    |
            |               |   | jsonl         |   |               |
            +---------------+   +---------------+   +---------------+
```

### 2.3 Log Entry Schema

```python
# core/logging/schema.py

@dataclass
class LogEntry:
    """Structured log entry schema."""
    
    # === Required Fields ===
    timestamp: str              # ISO 8601: "2026-01-18T14:30:00.123456Z"
    level: str                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message: str                # Human-readable message
    service: str                # Component: "trading", "telegram", "api"
    
    # === Correlation ===
    correlation_id: Optional[str] = None  # Links related entries
    request_id: Optional[str] = None      # API request tracking
    
    # === Context ===
    user_id: Optional[str] = None         # User who triggered action
    session_id: Optional[str] = None
    
    # === Feature Flags ===
    active_flags: List[str] = field(default_factory=list)
    
    # === Error Info ===
    error_type: Optional[str] = None      # Exception class name
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    
    # === Performance ===
    duration_ms: Optional[float] = None
    
    # === Custom Context ===
    context: Dict[str, Any] = field(default_factory=dict)
    
    # === Metadata ===
    hostname: str = ""
    environment: str = ""                 # dev, staging, prod
    version: str = ""
```


### 2.4 JSON Log Format Examples

**INFO: Successful trade execution**
```json
{
  "timestamp": "2026-01-18T14:30:00.123456Z",
  "level": "INFO",
  "message": "Trade executed successfully",
  "service": "trading",
  "correlation_id": "trade-abc123",
  "user_id": "tg_123456789",
  "active_flags": ["LIVE_TRADING_ENABLED", "ADVANCED_TRADING_ENABLED"],
  "duration_ms": 1234.56,
  "context": {
    "symbol": "SOL",
    "action": "BUY",
    "amount_usd": 100.00,
    "price": 150.25,
    "tx_signature": "5xYz..."
  },
  "_meta": {"hostname": "jarvis-prod-01", "environment": "prod", "version": "1.2.3"}
}
```

**ERROR: Trade execution failed**
```json
{
  "timestamp": "2026-01-18T14:30:00.123456Z",
  "level": "ERROR",
  "message": "Trade execution failed: insufficient balance",
  "service": "trading",
  "correlation_id": "trade-xyz789",
  "user_id": "tg_123456789",
  "active_flags": ["LIVE_TRADING_ENABLED"],
  "error": {
    "type": "InsufficientBalanceError",
    "message": "Wallet has 0.5 SOL, need 1.0 SOL",
    "stack_trace": "Traceback (most recent call last):\n  File \"trading.py\", line 123..."
  },
  "context": {
    "symbol": "SOL",
    "action": "BUY",
    "requested_amount": 1.0,
    "available_balance": 0.5
  }
}
```

**DEBUG: Dexter reasoning step**
```json
{
  "timestamp": "2026-01-18T14:30:00.123456Z",
  "level": "DEBUG",
  "message": "Dexter iteration 3: analyzing sentiment",
  "service": "dexter",
  "correlation_id": "dexter-session-001",
  "active_flags": ["DEXTER_ENABLED"],
  "context": {
    "symbol": "WIF",
    "iteration": 3,
    "tool_used": "sentiment_analyze",
    "grok_score": 75.5,
    "decision_so_far": "HOLD"
  }
}
```

### 2.5 Logger API Design

```python
# core/logging/structured.py

class StructuredLogger:
    """
    Structured JSON logger with context tracking.
    
    Usage:
        from core.logging import get_logger
        
        logger = get_logger("trading")
        
        # Basic logging
        logger.info("Trade executed", symbol="SOL", amount=100)
        
        # With context manager for correlation
        with logger.context(correlation_id="trade-123", user_id="tg_456"):
            logger.info("Starting trade")
            await execute_trade()
            logger.info("Trade complete", duration_ms=1234)
    """
    
    def __init__(self, service: str, level: int = logging.INFO):
        self.service = service
    
    # === Logging Methods ===
    def debug(self, message: str, **context): ...
    def info(self, message: str, **context): ...
    def warning(self, message: str, **context): ...
    def error(self, message: str, exc_info: bool = False, **context): ...
    def critical(self, message: str, exc_info: bool = False, **context): ...
    
    # === Context Management ===
    def context(
        self,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        flags: Optional[List[str]] = None,
    ) -> "LogContext":
        """Create a logging context for correlation."""
        ...
    
    # === Specialized Logging ===
    def trade_event(self, event_type: str, symbol: str, **details): ...
    def api_call(self, method: str, endpoint: str, status_code: int, duration_ms: float, **details): ...
    def feature_flag_evaluated(self, flag_id: str, result: bool, context: Dict): ...


def get_logger(service: str) -> StructuredLogger:
    """Get a structured logger for a service."""
    return StructuredLogger(service)
```


### 2.6 File Structure

```
core/
  logging/
    __init__.py           # Exports: get_logger, configure_logging
    structured.py         # StructuredLogger, LogContext
    schema.py             # LogEntry dataclass
    formatters.py         # JSONFormatter, HumanFormatter
    handlers.py           # FileHandler, RotatingHandler
    config.py             # Logging configuration
    query.py              # Log query utilities

logs/
  jarvis-2026-01-18.jsonl   # Daily JSON logs
  jarvis-2026-01-17.jsonl
  archive/                  # Compressed older logs
    jarvis-2026-01-10.jsonl.gz
  .gitkeep

scripts/
  log_query.py              # CLI tool for querying logs
  log_rotate.py             # Log rotation/archival script
```

### 2.7 Log Aggregation & Retention

#### Storage Layout
```
logs/
  jarvis-YYYY-MM-DD.jsonl   # Current day's logs (JSON Lines format)
  components/               # Optional per-component separation
    trading-YYYY-MM-DD.jsonl
    telegram-YYYY-MM-DD.jsonl
    dexter-YYYY-MM-DD.jsonl
  archive/
    YYYY-MM/
      jarvis-YYYY-MM-DD.jsonl.gz
```

#### Retention Policy

| Age | Storage | Compression | Location |
|-----|---------|-------------|----------|
| 0-7 days | Active | None | `logs/*.jsonl` |
| 7-30 days | Archive | gzip | `logs/archive/*.jsonl.gz` |
| 30+ days | Purged | N/A | Deleted |

### 2.8 Query Capabilities

#### CLI Query Tool
```bash
# Query recent errors
python scripts/log_query.py --level ERROR --since "1 hour ago"

# Search by correlation ID
python scripts/log_query.py --correlation-id "trade-abc123"

# Filter by service and flag
python scripts/log_query.py --service trading --flag DEXTER_ENABLED

# Full-text search
python scripts/log_query.py --search "insufficient balance"

# Export to CSV
python scripts/log_query.py --level ERROR --format csv > errors.csv
```

#### Programmatic Query
```python
# core/logging/query.py

class LogQuery:
    def search(
        self,
        level: Optional[str] = None,
        service: Optional[str] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        flag: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        text: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search logs with filters."""
        ...
    
    def get_error_summary(self, since: datetime, group_by: str = "error_type") -> Dict[str, int]:
        """Get error counts grouped by type."""
        ...
    
    def trace_correlation(self, correlation_id: str) -> List[Dict[str, Any]]:
        """Get all logs for a correlation ID, ordered by timestamp."""
        ...
```


---

## Part 3: Integration Plan

### 3.1 How Feature Flags Affect Logging

Logs automatically include which flags were active during the operation:

```python
class StructuredLogger:
    def _log(self, level: str, message: str, **context):
        # Get currently active flags relevant to this service
        active_flags = self._get_relevant_flags()
        
        entry = LogEntry(
            # ... other fields
            active_flags=active_flags,
        )

    def _get_relevant_flags(self) -> List[str]:
        from core.feature_flags import flags
        
        # Service-relevant flags mapping
        service_flags = {
            "trading": ["LIVE_TRADING_ENABLED", "ADVANCED_TRADING_ENABLED"],
            "dexter": ["DEXTER_ENABLED"],
            "telegram": ["NEW_TELEGRAM_UI_ENABLED"],
        }
        
        return [f for f in service_flags.get(self.service, []) if flags.is_enabled(f)]
```

### 3.2 Debugging Workflow with Logs + Flags

```
1. User reports issue at 14:30

2. Query logs around that time:
   python scripts/log_query.py --since "14:25" --until "14:35" --level ERROR
   
3. Find correlation ID from error:
   correlation_id: "trade-xyz789"
   
4. Trace full request:
   python scripts/log_query.py --correlation-id "trade-xyz789"
   
5. Check what flags were active:
   Entry shows: active_flags: ["LIVE_TRADING_ENABLED"]
   Notice: ADVANCED_TRADING_ENABLED was OFF
   
6. Reproduce with same flag state:
   export FF_ADVANCED_TRADING_ENABLED=false
   # Run test
```

### 3.3 Integration Code Examples

#### Trading Engine Integration
```python
# bots/treasury/trading.py
from core.feature_flags import flags
from core.logging import get_logger

logger = get_logger("trading")

class TreasuryTrader:
    async def execute_trade(self, signal):
        with logger.context(correlation_id=f"trade-{signal.id}", user_id=signal.user_id):
            if not flags.is_enabled("LIVE_TRADING_ENABLED"):
                logger.info("Live trading disabled, dry-run only")
                return self._simulate_trade(signal)
            
            if flags.is_enabled("ADVANCED_TRADING_ENABLED"):
                signal = await self._apply_trailing_stop(signal)
            
            result = await self._execute_real_trade(signal)
            logger.info("Trade executed", symbol=signal.symbol, amount=signal.amount)
            return result
```

#### Dexter Agent Integration
```python
# core/dexter/agent.py
from core.feature_flags import flags
from core.logging import get_logger

logger = get_logger("dexter")

class DexterAgent:
    async def analyze_trading_opportunity(self, symbol: str, context=None):
        if not flags.is_enabled("DEXTER_ENABLED"):
            logger.info("Dexter disabled by feature flag", symbol=symbol)
            return ReActDecision(decision=DecisionType.HOLD, symbol=symbol)
        
        with logger.context(correlation_id=f"dexter-{uuid.uuid4().hex[:8]}"):
            logger.info("Starting Dexter analysis", symbol=symbol)
            # ... analysis logic
```

#### Telegram Bot Integration
```python
# tg_bot/handlers/flag_admin_handler.py

async def cmd_flags(update, context):
    """Show all flag statuses."""
    if not is_admin(update.effective_user.id):
        return
    
    flags_list = flags.list_flags()
    lines = ["<b>Feature Flags Status:</b>\n"]
    for flag in flags_list:
        status = "ON" if flag.enabled else "OFF"
        lines.append(f"{'[ON]' if flag.enabled else '[OFF]'} <code>{flag.id}</code>")
    
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
```


### 3.4 Testing Strategy

#### Feature Flags Tests
```python
# tests/test_feature_flags.py

def test_basic_boolean_flag(flag_manager):
    """Simple on/off flag."""
    flag_manager.create_flag(FlagDefinition(id="TEST_FLAG", enabled=True))
    assert flag_manager.is_enabled("TEST_FLAG") == True
    flag_manager.set_enabled("TEST_FLAG", False)
    assert flag_manager.is_enabled("TEST_FLAG") == False

def test_percentage_rollout(flag_manager):
    """Percentage-based rollout is consistent."""
    flag_manager.create_flag(FlagDefinition(
        id="TEST_PCT", enabled=True,
        rules=[RolloutRule(type="percentage", value=50)]
    ))
    
    # Same user should get same result
    result1 = flag_manager.is_enabled("TEST_PCT", user_id="user123")
    result2 = flag_manager.is_enabled("TEST_PCT", user_id="user123")
    assert result1 == result2
    
    # ~50% should be enabled across many users
    enabled = sum(1 for i in range(1000) if flag_manager.is_enabled("TEST_PCT", user_id=f"user{i}"))
    assert 400 < enabled < 600

def test_environment_default(flag_manager):
    """Environment-specific defaults."""
    flag_manager.create_flag(FlagDefinition(
        id="TEST_ENV", enabled=False,
        environment_defaults={"dev": True, "prod": False}
    ))
    
    dev_ctx = EvaluationContext(environment="dev")
    prod_ctx = EvaluationContext(environment="prod")
    
    assert flag_manager.is_enabled("TEST_ENV", context=dev_ctx) == True
    assert flag_manager.is_enabled("TEST_ENV", context=prod_ctx) == False
```

#### Structured Logging Tests
```python
# tests/test_structured_logging.py

def test_json_format(caplog):
    """Logs are valid JSON."""
    logger = get_logger("test")
    logger.info("Test message", key="value")
    
    entry = json.loads(caplog.records[-1].getMessage())
    assert entry["level"] == "INFO"
    assert entry["message"] == "Test message"
    assert entry["context"]["key"] == "value"

def test_correlation_context(caplog):
    """Correlation ID propagates through context."""
    logger = get_logger("test")
    
    with logger.context(correlation_id="test-123"):
        logger.info("Step 1")
        logger.info("Step 2")
    
    entries = [json.loads(r.getMessage()) for r in caplog.records[-2:]]
    assert entries[0]["correlation_id"] == "test-123"
    assert entries[1]["correlation_id"] == "test-123"

def test_error_with_traceback(caplog):
    """Error logging includes stack trace."""
    logger = get_logger("test")
    
    try:
        raise ValueError("Test error")
    except:
        logger.error("Operation failed", exc_info=True)
    
    entry = json.loads(caplog.records[-1].getMessage())
    assert entry["error"]["type"] == "ValueError"
    assert "Traceback" in entry["error"]["stack_trace"]
```

---

## Implementation Phases

### Phase 1: Foundation (2-3 days)
**Files:** `core/feature_flags/models.py`, `core/logging/schema.py`  
**Acceptance:** Types compile, model tests pass  
**Effort:** Small

### Phase 2: Core Logic (3-4 days)
**Files:** `core/feature_flags/manager.py`, `core/logging/structured.py`  
**Acceptance:** Basic flag ops work, logs output JSON  
**Effort:** Medium

### Phase 3: Persistence (2 days)
**Files:** `core/feature_flags/persistence.py`, `config/feature_flags.json`  
**Acceptance:** Flags persist, hot-reload works  
**Effort:** Small

### Phase 4: Integration (3-4 days)
**Files:** Modify `supervisor.py`, `trading.py`, `agent.py`, `bot.py`  
**Acceptance:** Flags control behavior, logs include flags  
**Effort:** Medium

### Phase 5: Query Tools (2 days)
**Files:** `core/logging/query.py`, `scripts/log_query.py`  
**Acceptance:** Can query logs by filters  
**Effort:** Small

### Phase 6: Testing & Docs (2-3 days)
**Files:** Tests + documentation  
**Acceptance:** 80%+ coverage, docs complete  
**Effort:** Medium

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hot-reload race conditions | Medium | Atomic writes, lock during reload |
| Log volume too high | Medium | Log levels, sampling, rotation |
| Flag evaluation overhead | Low | Evaluation cache with TTL |
| Breaking existing logging | High | Gradual migration, keep Python logger compat |
| JSON parsing errors | Low | Schema validation, graceful fallbacks |

---

## Open Questions

- [ ] Should flag changes require confirmation via Telegram before applying?
- [ ] Remote log aggregation backend preference (Loki vs CloudWatch vs ELK)?
- [ ] Should DEBUG logs be disabled in production by default?
- [ ] Flag expiration: auto-disable or alert only?

---

## Success Criteria

1. Can enable/disable Dexter via Telegram command without restart
2. Can view which flags were active during any error
3. Can trace a trading flow from start to finish via correlation ID
4. Logs are parseable by standard JSON tools (jq, etc.)
5. Flag changes are audited with who/when/why
6. A/B testing allows 25% rollout of new UI
7. All existing functionality continues working (backward compatible)
