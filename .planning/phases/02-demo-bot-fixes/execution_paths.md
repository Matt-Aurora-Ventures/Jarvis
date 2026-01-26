# Demo Bot Execution Paths Analysis

**Generated:** 2026-01-26
**Status:** Post-refactor analysis

## Overview

The demo bot has been successfully refactored from a monolithic 10,015-line file into a modular structure with 7 specialized modules totaling 2,790 lines.

## Module Breakdown

| Module | Lines | Purpose |
|--------|-------|---------|
| demo_core.py | 362 | Main handlers and routing |
| demo_trading.py | 709 | Trade execution logic |
| demo_sentiment.py | 535 | Sentiment analysis integration |
| demo_orders.py | 444 | TP/SL order management |
| demo_ui.py | 118 | UI components |
| demo_callbacks.py | 517 | Callback handlers |
| __init__.py | 105 | Module exports |
| **Total** | **2,790** | **All modules < 1000 lines** ✅ |

## Legacy Preservation

| File | Lines | Status |
|------|-------|--------|
| demo_legacy.py | 10,015 | Preserved for reference |
| demo.py | 34 | Compatibility layer |

## Execution Paths

### 1. Buy Flow
**Entry:** `/demo` → Buy button → Token input
**Modules:** demo_core → demo_trading → demo_orders
**Handlers:**
- `demo()` (demo_core.py:50-100)
- `demo_message_handler()` (demo_core.py:300-330)
- `execute_buy_with_tpsl()` (demo_trading.py)
- TP/SL order creation (demo_orders.py)

**Error Handling:** ✅ Comprehensive try/except blocks
**Registration:** ✅ Registered in bot.py line 167

### 2. Sell Flow
**Entry:** `/demo` → Positions → Sell button
**Modules:** demo_core → demo_trading → demo_orders
**Handlers:**
- Position display (demo_core.py)
- Sell execution (demo_trading.py)
- TP/SL cancellation (demo_orders.py)

**Error Handling:** ✅ Present

### 3. Sentiment Hub
**Entry:** `/demo` → Sentiment Hub
**Modules:** demo_core → demo_sentiment
**Handlers:**
- Market regime display
- AI sentiment fetching
- Treasury activation monitoring
- bags.fm graduation tracking

**Error Handling:** ✅ Present

### 4. TP/SL Management
**Entry:** `/demo` → Positions → Set TP/SL
**Modules:** demo_core → demo_orders
**Handlers:**
- Order creation
- Background monitoring
- Execution triggers
- Ladder exit logic

**Error Handling:** ✅ Present

## Handler Registration

```python
# demo_core.py:337-352
def register_demo_handlers(app):
    app.add_handler(CommandHandler("demo", demo))
    app.add_handler(CallbackQueryHandler(demo_callback, pattern=r"^demo:"))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            demo_message_handler,
        ),
        group=0,
    )
```

**Status:** ✅ Registered in bot.py line 167

## Function Dependencies

### Core Dependencies
- `demo()` → `DemoMenuBuilder` → UI generation
- `demo_callback()` → Route to specialized handlers
- `demo_message_handler()` → Input handlers (buy amount, token address, etc.)

### Trading Dependencies
- `execute_buy_with_tpsl()` → `JupiterSwap` / `bags.fm` API
- `validate_buy_amount()` → Risk checks
- `_execute_swap_with_fallback()` → Retry logic with exponential backoff

### Sentiment Dependencies
- `get_market_regime()` → Grok AI integration
- `get_ai_sentiment_for_token()` → Token scoring
- `get_bags_top_tokens_with_sentiment()` → bags.fm + Grok

### Order Dependencies
- `_background_tp_sl_monitor()` → Continuous price monitoring
- `_process_demo_exit_checks()` → Exit trigger evaluation
- Ladder exits → Partial position selling

## Circular Dependencies

✅ **None detected** - Clear module boundaries maintained

## Duplicate Code

✅ **Minimal** - Shared utilities extracted to demo_ui.py

## Error Handling

**Coverage:** 52 try/except patterns in demo_trading.py alone
**Custom Errors:** Defined in core/errors.py
- `TradeExecutionError`
- `InsufficientFundsError`
- `SlippageExceededError`
- `RPCError`

## Performance Characteristics

- **Async:** All handlers use async/await
- **Non-blocking:** No synchronous sleep() calls in critical paths
- **Retry logic:** 3 attempts with exponential backoff
- **Circuit breakers:** Present in trading execution

## Test Coverage

**Test Files:** 13 dedicated test files
**Total Test Lines:** 4,671
**Coverage:** TBD (need to run pytest --cov)

## Verification Status

- [x] All modules < 1000 lines
- [x] Message handler registered
- [x] Error handling present
- [x] Async patterns used
- [x] No circular dependencies
- [ ] Integration tests run (TODO)
- [ ] Coverage report generated (TODO)

## Next Steps

1. Run integration tests to verify all flows work
2. Generate coverage report (target: 80%+)
3. Complete documentation
4. Performance testing under load
