# Phase 7.1: Fix Failing Tests - COMPLETE

**Date**: 2026-01-24
**Status**: ✅ COMPLETE
**Duration**: 1 hour

---

## Summary

Fixed 3 failing tests in `tests/unit/test_demo_exit_triggers.py` that were broken after Phase 2 refactoring.

**Root Cause**: Tests were importing from parent module (`tg_bot.handlers.demo`) but couldn't access private helper functions that weren't exported in `__init__.py`.

---

## Changes Made

### 1. Updated `tg_bot/handlers/demo/__init__.py`

**Added exports** for test helper functions:

```python
# From demo_trading.py
from tg_bot.handlers.demo.demo_trading import (
    execute_buy_with_tpsl,
    get_bags_client,
    get_trade_intelligence,
    get_success_fee_manager,
    validate_buy_amount,
    _get_jupiter_client,  # For testing
    _execute_swap_with_fallback,  # For testing
)

# From demo_orders.py
from tg_bot.handlers.demo.demo_orders import (
    _background_tp_sl_monitor,
    _process_demo_exit_checks,
    _check_demo_exit_triggers,  # For testing
    _maybe_execute_exit,  # For testing
)
```

**Why**: Tests needed access to these functions for mocking and direct testing. Exporting them from `__init__.py` allows backward-compatible testing.

### 2. Fixed `tests/unit/test_demo_exit_triggers.py`

**Problem**: Test was mocking `demo_mod._execute_swap_with_fallback`, but `_maybe_execute_exit` does a local import:

```python
# Inside _maybe_execute_exit (demo_orders.py line 181)
from tg_bot.handlers.demo.demo_trading import _execute_swap_with_fallback
```

Local imports can't be monkeypatched via parent module.

**Solution**: Mock the function in its original module:

```python
# Before (BROKEN)
monkeypatch.setattr(
    demo_mod,  # Parent module
    "_execute_swap_with_fallback",
    AsyncMock(...)
)

# After (FIXED)
from tg_bot.handlers.demo import demo_trading

monkeypatch.setattr(
    demo_trading,  # Actual module where function is defined
    "_execute_swap_with_fallback",
    AsyncMock(return_value={"success": True, "tx_hash": "txhash", "source": "jupiter"}),
)
```

---

## Test Results

### Before Fix

```
FAILED tests/unit/test_demo_exit_triggers.py::test_exit_triggers_take_profit_and_stop_loss
  AttributeError: module has no attribute '_get_jupiter_client'

FAILED tests/unit/test_demo_exit_triggers.py::test_exit_triggers_trailing_stop
  AttributeError: module has no attribute '_get_jupiter_client'

FAILED tests/unit/test_demo_exit_triggers.py::test_maybe_execute_exit_runs_when_enabled
  assert False is True (auto-exit returned False)

3 failed, 0 passed
```

### After Fix

```
tests/unit/test_demo_exit_triggers.py::test_exit_triggers_take_profit_and_stop_loss PASSED
tests/unit/test_demo_exit_triggers.py::test_exit_triggers_trailing_stop PASSED
tests/unit/test_demo_exit_triggers.py::test_maybe_execute_exit_runs_when_enabled PASSED

3 passed in 13.80s
```

---

## Lessons Learned

### 1. Local Imports Break Monkeypatching

When functions do runtime imports:
```python
def my_function():
    from some.module import helper  # Runtime import
    return helper()
```

Tests must mock `some.module.helper`, NOT `caller_module.helper`.

### 2. Private Function Exports for Testing

**Trade-off**: Exporting private functions (`_function`) breaks encapsulation BUT enables thorough testing.

**Decision**: Export private functions with `# For testing` comment to signal they're not part of public API.

**Alternative**: Only test public APIs, accept lower coverage on internals.

### 3. Backward Compatibility Helps Tests

The refactoring preserved backward compatibility via `__init__.py` exports, which meant:
- Most existing tests didn't break
- Only tests accessing NEW private functions needed fixes
- Coverage tracking still works (after exports added)

---

## Coverage Impact

**Before Phase 7.1**: 14.39% coverage (with 3 failing tests)
**After Phase 7.1**: 14.39% coverage (with 3 passing tests)

**Note**: No coverage increase yet - just fixed broken tests. Coverage will increase in Phase 7.2 when we write NEW tests for P0 modules.

---

## Next Steps

**Phase 7.2**: Write P0 module tests
- `tests/unit/test_trading_operations.py` (NEW)
- `tests/unit/test_trading_execution.py` (NEW)
- `tests/unit/test_trading_analytics.py` (NEW)
- `tests/unit/test_trading_core.py` (EXPAND)
- `tests/unit/test_treasury_trader.py` (NEW)
- `tests/unit/test_trading_positions.py` (EXPAND)
- `tests/unit/test_demo_trading.py` (NEW)
- `tests/unit/test_demo_orders.py` (EXPAND)
- `tests/unit/test_demo_sentiment.py` (NEW)

**Target**: Reach 65%+ coverage by end of Phase 7.2

---

**Document Version**: 1.0
**Author**: Claude Sonnet 4.5 (Ralph Wiggum Loop)
**Status**: Phase 7.1 COMPLETE
**Next**: Phase 7.2 - Write P0 module tests
