# Jarvis Architecture Audit Report
Created: 2026-01-18
Author: architect-agent

## Executive Summary

Jarvis is an autonomous LifeOS trading and AI assistant system running on Solana. The codebase is large (~350+ Python files in core/ alone) with significant accumulated technical debt.

**Key Findings:**
- Heavy reliance on singleton pattern (50+ global instances)
- State scattered across multiple JSON files without unified persistence layer
- Configuration in 3+ locations (config.yaml, per-module .env, environment variables)
- Circular dependency risks between core modules
- No central service registry or dependency injection
- Error handling inconsistent across layers

---

## 1. Module Structure Analysis

### Directory Organization

```
Jarvis/
├── core/                 # 350+ files - MONOLITHIC
│   ├── agents/          # Agent implementations
│   ├── ai/              # AI code
│   ├── analytics/       # Event tracking
│   ├── alerts/          # Alert system
│   ├── automation/      # Task automation
│   ├── backup/          # Backup systems
│   ├── cache/           # Caching layer
│   ├── config/          # Configuration loaders
│   ├── errors/          # Error hierarchy
│   ├── event_bus/       # Event-driven architecture
│   ├── monitoring/      # Health checks
│   ├── security/        # Security utilities
│   ├── trading/         # Trading logic
│   └── [200+ top-level .py files]
├── bots/                 # Bot implementations
│   ├── buy_tracker/     # KR8TIV token tracking
│   ├── treasury/        # Trading engine
│   └── twitter/         # X/Twitter bot
├── tg_bot/              # Telegram bot - SEPARATE from bots/
├── api/                 # External API (FastAPI)
└── config.yaml          # Unified config (partial)
```

### Structural Concerns

| Concern | Severity | Impact |
|---------|----------|--------|
| Flat core/ structure with 200+ files | HIGH | Hard to navigate |
| tg_bot/ separate from bots/ | MEDIUM | Inconsistent organization |
| Duplicate config loaders | MEDIUM | Maintenance burden |
| core/ is catch-all namespace | HIGH | No clear domain boundaries |

---

## 2. Dependency Flow Analysis

### Current Import Graph

```
supervisor.py (main entry)
    │
    ├──► buy_tracker bot
    ├──► treasury trading
    ├──► twitter bot
    └──► telegram bot
            │
            └──► core/* (shared code)
                    │
                    ├──► External APIs (Jupiter, Grok, etc.)
                    ├──► State Files (.positions.json, etc.)
                    └──► Config (yaml, env vars)
```

### Singleton Pattern Overuse (50+ instances)

Found throughout codebase:
- get_unified_config()
- get_feedback_loop()
- get_alert_manager()
- get_registry()
- get_event_bus()
- get_grok_client()
- get_sentiment_aggregator()
- 45+ more...

**Problems:**
1. Testing is difficult (hard to mock)
2. Hidden dependencies
3. Initialization order issues
4. Memory leaks

---

## 3. State Management Analysis

### State File Locations

| File | Location | Purpose |
|------|----------|---------|
| .positions.json | bots/treasury/ | Open positions |
| exit_intents.json | ~/.lifeos/trading/ | Exit intent tracking |
| .grok_state.json | bots/twitter/ | Grok API state |
| audit_log.json | ~/.lifeos/trading/ | Trade audit trail |
| jarvis_secure.db | ~/.lifeos/telegram/ | TG bot data |

### Concerns

1. **Race Conditions**: Multiple processes access same files
2. **Partial SafeState Adoption**: core/safe_state.py exists but not universal
3. **No Unified State Layer**: Each component manages own persistence

---

## 4. Configuration Analysis

### Configuration Sources

| Source | Location | Problems |
|--------|----------|----------|
| config.yaml | Project root | Not fully adopted |
| tg_bot/.env | TG bot dir | Duplicates env vars |
| bots/twitter/.env | Twitter dir | Duplicates env vars |
| Environment vars | OS | No validation |
| BotConfig dataclass | tg_bot/config.py | Duplicates config.yaml |

### Recommendation

Single config source via config.yaml with env var expansion.

---

## 5. Error Handling

### Error Hierarchy (Good)

```
JarvisError (base)
├── ValidationError
├── AuthenticationError
├── AuthorizationError
├── NotFoundError
├── RateLimitError
├── ProviderError
├── TradingError
├── ConfigurationError
├── DatabaseError
└── ExternalAPIError
```

### Issues

- Inconsistent exception handling (bare except blocks)
- Error recovery decorator underutilized
- API vs internal error confusion

---

## 6. Async Patterns

### Good Patterns

- TaskTracker (core/async_utils.py)
- fire_and_forget with logging
- RateLimiter with token bucket

### Issues

- asyncio.create_task without tracking
- Blocking calls in async context
- Task cancellation not always handled

---

## 7. Coupling Analysis

| Component Pair | Coupling | Severity |
|----------------|----------|----------|
| bots/* <-> core/* | Import | HIGH |
| State files | Data | HIGH |
| Config sources | Stamp | MEDIUM |
| Event bus | Message | LOW (good) |

---

## 8. Immediate Action Items

1. [ ] Audit asyncio.create_task() calls - use TaskTracker
2. [ ] Create SafeState wrapper for all JSON file access
3. [ ] Remove per-module .env files
4. [ ] Add required key validation to UnifiedConfigLoader
5. [ ] Document error handling conventions
6. [ ] Create interface definitions for services

---

## 9. Key Files Reference

| File | Purpose |
|------|---------|
| bots/supervisor.py | Main orchestrator |
| core/config/unified_config.py | Config loader |
| core/async_utils.py | Async patterns |
| core/safe_state.py | State management |
| core/event_bus/event_bus.py | Event system |
| core/errors/exceptions.py | Error hierarchy |
