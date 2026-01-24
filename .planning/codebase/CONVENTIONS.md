# Jarvis Codebase Conventions

**Generated:** 2026-01-24  
**Purpose:** Coding standards, patterns, and style guide for Jarvis trading bot

---

## Code Style

### Naming Conventions

**Files & Directories:**
- Python modules: `snake_case.py` (`trading.py`, `sentiment_report.py`)
- Directories: `snake_case/` (`bots/`, `core/`, `tg_bot/`)
- Test files: `test_*.py` (`test_actions.py`, `test_smoke.py`)
- Configuration: `*.config.json`, `.env`

**Variables & Functions:**
- Functions: `snake_case` (`get_quote()`, `_open_in_firefox()`)
- Private functions: `_leading_underscore` (`_ui_allowed()`, `_log_twitter_error()`)
- Constants: `UPPER_SNAKE_CASE` (`SOL_MINT`, `USDC_MINT`, `QUOTE_URL`)
- Variables: `snake_case` (`input_mint`, `output_mint`, `slippage_bps`)

**Classes:**
- Classes: `PascalCase` (`TwitterClient`, `TreasuryTrader`, `JupiterClient`)
- Enums: `PascalCase` with UPPER values (`AlgorithmType.SENTIMENT_DRIVEN`)
- Dataclasses: `PascalCase` (`ActionIntent`, `ActionOutcome`, `TradeDecision`)

---

## Documentation Standards

### Module Docstrings

**Format:** Triple-quoted strings at module top with extensive descriptions

See examples in:
- `core/actions.py` - 10-line docstring with action discipline pattern
- `bots/supervisor.py` - 13-line docstring with feature list
- `bots/buy_tracker/sentiment_report.py` - 83-line changelog

### Function Docstrings

**Style:** Google/NumPy with Args, Returns sections

---

## Type Annotations

All functions have full type hints:
- Parameters and returns
- Optional for nullable values
- Tuple for multiple returns
- Dict/List with nested types

---

## Import Organization

1. Future imports
2. Standard library (grouped)
3. Third-party packages
4. Local imports
5. Try/except for optional features

Pattern: Feature flags like `STRUCTURED_LOGGING_AVAILABLE`

---

## Error Handling

- Specific exceptions first
- Structured error logging with context
- Graceful fallbacks for optional features

---

## Async/Await

- `async def` for I/O-bound operations
- Mixed sync/async interfaces when needed

---

## Logging

Per-module logger with structured logging when available

---

## See Full Document

This summary highlights key patterns. See full CONVENTIONS.md for:
- Configuration management
- Dataclasses
- File I/O patterns
- Common design patterns
- Security practices
- Deprecation handling
