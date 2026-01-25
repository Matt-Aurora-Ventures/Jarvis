# Phase 7: Coverage Gap Analysis

**Date**: 2026-01-24
**Status**: GAPS IDENTIFIED
**Current Coverage**: 14.39% (refactored modules only)
**Target Coverage**: 80%+

---

## Executive Summary

**Critical Finding**: The refactored modules from Phase 2 have **low test coverage** despite 6,923 existing tests in the suite.

**Why**: Tests exist but import from legacy modules (demo_legacy.py, old trading.py) rather than the refactored modules. The __init__.py backward compatibility exports don't trigger coverage tracking for the new files.

**Impact**: **Need ~4,000 lines of new tests** to reach 80% coverage.

---

## Coverage Results by Module

### Trading Engine Modules (bots/treasury/trading/)

| Module | Lines | Covered | Missing | Coverage | Priority |
|--------|-------|---------|---------|----------|----------|
| **types.py** | 85 | 82 | 3 | **93.55%** | ✓ DONE |
| **trading_risk.py** | 112 | 67 | 45 | **59.62%** | P1 |
| **trading_positions.py** | 176 | 61 | 115 | **31.02%** | P0 |
| **trading_core.py** | 605 | 151 | 454 | **24.70%** | P0 |
| **treasury_trader.py** | 395 | 41 | 354 | **7.87%** | P0 |
| **trading_execution.py** | 850 | 27 | 823 | **3.19%** | P0 |
| **trading_operations.py** | 313 | 0 | 313 | **0.00%** | P0 |
| **trading_analytics.py** | 250 | 0 | 250 | **0.00%** | P0 |
| **trading_engine.py** | Not tested | - | - | **0.00%** | P0 |
| **constants.py** | 53 | 0 | 53 | **0.00%** | P2 |
| **logging_utils.py** | 66 | 0 | 66 | **0.00%** | P2 |

**Subtotal**: ~2,905 lines, ~429 covered = **14.77% coverage**

**Gap to 80%**: Need to cover **~1,895 additional lines**

### Demo Bot Modules (tg_bot/handlers/demo/)

| Module | Lines | Covered | Missing | Coverage | Priority |
|--------|-------|---------|---------|----------|----------|
| **demo_trading.py** | 160 | 24 | 136 | **11.88%** | P0 |
| **demo_sentiment.py** | 200 | 25 | 175 | **9.69%** | P0 |
| **demo_orders.py** | 229 | 19 | 210 | **5.99%** | P0 |
| **demo_callbacks.py** | 200 | 73 | 127 | **29.92%** | P1 |
| **demo_ui.py** | 2 | 0 | 2 | **0.00%** | P2 |

**Callbacks** (18 modules, ALL 0% coverage):
| Module | Lines | Coverage |
|--------|-------|----------|
| position.py | 226 | **0.00%** |
| sell.py | 135 | **0.00%** |
| sentiment_hub.py | 139 | **0.00%** |
| snipe.py | 127 | **0.00%** |
| dca.py | 103 | **0.00%** |
| bags.py | 98 | **0.00%** |
| wallet.py | 95 | **0.00%** |
| buy.py | 87 | **0.00%** |
| alerts.py | 70 | **0.00%** |
| settings.py | 68 | **0.00%** |
| chart.py | 62 | **0.00%** |
| learning.py | 62 | **0.00%** |
| watchlist.py | 43 | **0.00%** |
| analysis.py | 17 | **0.00%** |
| navigation.py | 14 | **0.00%** |
| misc.py | 13 | **0.00%** |
| trading.py | 53 | **0.00%** |
| __init__.py | 18 | **0.00%** |

**Callback Subtotal**: 1,389 lines, **0 covered = 0.00% coverage**

**Demo Total**: ~2,180 lines, ~141 covered = **6.47% coverage**

**Gap to 80%**: Need to cover **~1,603 additional lines**

---

## Root Cause Analysis

### Why Coverage Is So Low

1. **Backward Compatibility Trap**
   - Tests import from `tg_bot.handlers.demo` (parent)
   - Coverage runs against child modules (demo_trading.py, demo_orders.py)
   - Imports go through __init__.py but coverage doesn't follow

2. **Legacy Test Imports**
   - `from tg_bot.handlers.demo import demo` → imports from demo_legacy.py
   - Should be: `from tg_bot.handlers.demo.demo_core import demo`
   - Tests are running against OLD CODE, not refactored modules

3. **Private Function Access**
   - Tests try to mock `demo._get_jupiter_client()`
   - But __init__.py doesn't export private functions (leading underscore)
   - 3 tests fail: test_exit_triggers_* because they can't access private helpers

4. **Callback Module Isolation**
   - 18 callback modules created during refactoring
   - No tests written for callback-specific logic
   - Callbacks only run via demo_callback() dispatcher

---

## Test Failures

### Failed Tests (3)

```
FAILED tests/unit/test_demo_exit_triggers.py::test_exit_triggers_take_profit_and_stop_loss
FAILED tests/unit/test_demo_exit_triggers.py::test_exit_triggers_trailing_stop
FAILED tests/unit/test_demo_exit_triggers.py::test_maybe_execute_exit_runs_when_enabled
```

**Error**: `AttributeError: module has no attribute '_get_jupiter_client'`

**Cause**: Tests import `from tg_bot.handlers import demo` and try to access private function `demo._get_jupiter_client()` which isn't exported.

**Fix Options**:
1. Export private functions in __init__.py (NOT RECOMMENDED - breaks encapsulation)
2. Rewrite tests to import from demo_orders.py directly
3. Rewrite tests to not mock internal helpers (test from public API only)

**Recommendation**: Option 3 - Tests should test public interfaces, not private helpers.

---

## Prioritized Test Plan

### P0: Critical Modules (Must Have for 80%)

**Target**: 2,708 lines to cover

1. **trading_operations.py** (313 lines, 0% → 80%)
   - open_position()
   - close_position()
   - update_position()
   - Full buy/sell flow

2. **trading_execution.py** (850 lines, 3% → 80%)
   - SwapExecutor class
   - execute_swap()
   - Bags.fm → Jupiter fallback
   - Slippage handling
   - Transaction retry logic

3. **trading_analytics.py** (250 lines, 0% → 80%)
   - calculate_pnl()
   - Performance metrics
   - Win rate calculation
   - Sharpe ratio

4. **trading_core.py** (605 lines, 25% → 80%)
   - TradingEngine class
   - Signal processing
   - Risk validation
   - Position lifecycle

5. **treasury_trader.py** (395 lines, 8% → 80%)
   - TreasuryTrader class
   - Public trading interface
   - Integration with core engine

6. **trading_positions.py** (176 lines, 31% → 80%)
   - PositionManager class
   - Position persistence
   - State management
   - JSON serialization

7. **demo_trading.py** (160 lines, 12% → 80%)
   - execute_buy_with_tpsl()
   - Bags.fm client integration
   - Trade intelligence
   - Success fee manager

8. **demo_orders.py** (229 lines, 6% → 80%)
   - _check_demo_exit_triggers()
   - TP/SL monitoring
   - Trailing stop logic
   - Auto-execution

9. **demo_sentiment.py** (200 lines, 10% → 80%)
   - get_market_regime()
   - get_ai_sentiment_for_token()
   - Sentiment caching
   - Trending tokens

**Estimated Effort**: 2,708 lines × 0.77 (gap) = **2,085 lines to cover**
**Time**: ~3-4 days (assuming 500-700 lines/day of test writing)

### P1: Important Modules

1. **trading_risk.py** (112 lines, 60% → 80%)
   - Need 22 more lines covered
   - Spending limits
   - Token risk classification

2. **demo_callbacks.py** (200 lines, 30% → 80%)
   - Need 100 more lines covered
   - Callback routing logic

**Estimated Effort**: 122 lines
**Time**: ~4-6 hours

### P2: Low Priority (Nice to Have)

1. **18 callback modules** (1,389 lines, 0% → 40%)
   - Focus on critical callbacks: position.py, buy.py, sell.py
   - Skip misc/navigation (trivial)

2. **constants.py**, **logging_utils.py** (119 lines)
   - Mostly configuration
   - Low value tests

**Estimated Effort**: ~600 lines (40% of callbacks)
**Time**: ~1 day

---

## Test Writing Strategy

### Phase 7.1: Fix Failing Tests (2-3 hours)

1. Rewrite test_demo_exit_triggers.py:
   - Import from demo_orders.py directly
   - Test public API, not private helpers
   - Mock at system boundaries (Jupiter client, not internal helpers)

2. Verify all 59 passing tests remain passing

### Phase 7.2: P0 Module Tests (3-4 days)

**Day 1**: Trading operations & execution
- tests/unit/test_trading_operations.py (new)
- tests/unit/test_trading_execution.py (new)
- Target: 1,163 lines → 80% = 930 lines covered

**Day 2**: Trading analytics & core
- tests/unit/test_trading_analytics.py (new)
- tests/unit/test_trading_core.py (expand existing)
- Target: 855 lines → 80% = 684 lines covered

**Day 3**: Treasury trader & positions
- tests/unit/test_treasury_trader.py (new)
- tests/unit/test_trading_positions.py (expand existing)
- Target: 571 lines → 80% = 457 lines covered

**Day 4**: Demo modules
- tests/unit/test_demo_trading.py (new)
- tests/unit/test_demo_orders.py (rewrite)
- tests/unit/test_demo_sentiment.py (new)
- Target: 589 lines → 80% = 471 lines covered

### Phase 7.3: P1 Module Tests (4-6 hours)

- Expand test_trading_risk.py
- Expand test_demo_callbacks.py
- Target: 122 lines covered

### Phase 7.4: Integration Tests (1-2 days)

- Full buy → TP/SL → auto-sell flow
- Bags.fm → Jupiter fallback flow
- Multi-position management
- Concurrent position updates

---

## Success Metrics

**Target**: 80%+ line coverage on refactored modules

**Current**: 14.39%
**Gap**: 65.61 percentage points
**Lines to cover**: ~2,200 lines (from ~4,100 total)

**Milestones**:
- [x] Phase 7.1: Fix failing tests → 14.39% (current)
- [ ] Phase 7.2: P0 modules → 65%+ coverage
- [ ] Phase 7.3: P1 modules → 75%+ coverage
- [ ] Phase 7.4: Integration tests → 80%+ coverage

---

## Key Decisions

### 1. Import Strategy

**Decision**: Tests should import directly from submodules, not parent __init__.py

**Before**:
```python
from tg_bot.handlers.demo import execute_buy_with_tpsl
```

**After**:
```python
from tg_bot.handlers.demo.demo_trading import execute_buy_with_tpsl
```

**Why**: Coverage tracking works correctly, explicit dependencies

### 2. Test Scope

**Decision**: Test public API only, not private helpers

**Rationale**: Private functions change frequently during refactoring. Testing public API ensures tests remain stable.

### 3. Callback Testing

**Decision**: Defer to P2, focus on core logic first

**Rationale**: Callbacks are mostly UI routing. Core trading logic is more critical for V1 launch.

---

## Risks

1. **Time Pressure** - Writing 2,200 lines of tests in 4-5 days is aggressive
2. **Test Brittleness** - New tests may break easily during continued refactoring
3. **Coverage vs Quality** - High coverage doesn't mean good tests
4. **Integration Gaps** - Unit tests won't catch inter-module issues

**Mitigation**:
- Prioritize P0 modules ruthlessly
- Accept 70% coverage for V1 if 80% proves unachievable
- Write integration tests in parallel with unit tests
- Use existing tests as templates for speed

---

## Next Steps

1. **Update Phase 7 plan** with new timeline (4-5 days, not 1-2 weeks)
2. **Start Phase 7.1** - Fix failing tests (NOW)
3. **Create test templates** for each P0 module
4. **Write tests in priority order** - Operations → Execution → Analytics → Core

---

**Document Version**: 1.0
**Author**: Claude Sonnet 4.5 (Ralph Wiggum Loop)
**Status**: Gap analysis complete, ready to write tests
**Next**: Phase 7.1 - Fix 3 failing tests in test_demo_exit_triggers.py
