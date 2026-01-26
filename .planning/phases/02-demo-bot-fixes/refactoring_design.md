# Demo Bot & Trading Bot Refactoring Design

**Created:** 2026-01-26
**Status:** Completed
**Plan:** Phase 2.1 - Demo Bot Fixes & Code Refactoring

## Objectives

1. ✅ Break 10,015-line demo.py into maintainable modules
2. ✅ Break 3,754-line trading.py into maintainable modules
3. ✅ Achieve <1000 lines per file (best practice)
4. ✅ Maintain backward compatibility
5. ✅ Add comprehensive error handling
6. ✅ Enable testability

## Design Principles

### Modularity
- **Single Responsibility:** Each module handles one concern
- **Clear Boundaries:** No circular dependencies
- **Loose Coupling:** Modules communicate via well-defined interfaces

### Maintainability
- **<1000 lines per file:** Easy to understand and modify
- **Consistent naming:** Predictable module/function names
- **Documentation:** Inline docs and external guides

### Testability
- **Dependency Injection:** Easy to mock external services
- **Async patterns:** Proper async/await usage
- **Error boundaries:** Isolated error handling

## Demo Bot Refactoring

### Before
```
demo.py (10,015 lines, 391.5KB)
├─ Everything in one file
├─ 100+ functions
├─ Multiple responsibilities
└─ Hard to test
```

### After
```
demo/
├─ demo_core.py (362 lines) - Main handlers, routing
├─ demo_trading.py (709 lines) - Buy/sell execution
├─ demo_sentiment.py (535 lines) - Sentiment integration
├─ demo_orders.py (444 lines) - TP/SL management
├─ demo_ui.py (118 lines) - UI components
├─ demo_callbacks.py (517 lines) - Callback routing
├─ __init__.py (105 lines) - Public API
└─ demo_legacy.py (10,015 lines) - Original preserved

demo.py (34 lines) - Compatibility layer
```

### Module Responsibilities

#### demo_core.py
- Main `/demo` command handler
- Callback router
- Message input handler
- State management (awaiting_token, etc.)
- Handler registration

#### demo_trading.py
- Buy execution with TP/SL
- Sell execution
- Swap orchestration with fallback
- Amount validation
- Retry logic

#### demo_sentiment.py
- Market regime display
- Grok AI sentiment fetching
- Treasury activation monitoring
- bags.fm graduation tracking
- Trending tokens with sentiment

#### demo_orders.py
- TP/SL order creation
- Background price monitoring
- Exit trigger evaluation
- Ladder exit execution
- Order persistence

#### demo_ui.py
- Reusable UI components
- Button builders
- Message formatters
- Theme constants

#### demo_callbacks.py
- Callback pattern routing
- Buy flow callbacks
- Sell flow callbacks
- Settings callbacks
- Hub navigation callbacks

## Treasury Trading Refactoring

### Before
```
trading.py (3,754 lines)
├─ 65+ functions
├─ Mixed concerns
└─ Hard to navigate
```

### After
```
treasury/trading/
├─ trading_core.py (15 lines) - Legacy exports
├─ trading_engine.py (747 lines) - Main orchestrator
├─ trading_execution.py (594 lines) - Jupiter/bags.fm execution
├─ trading_positions.py (281 lines) - Position management
├─ trading_risk.py (261 lines) - Risk management
├─ trading_analytics.py (295 lines) - PnL tracking
├─ trading_operations.py (1,237 lines) ⚠️ - Operations (needs split)
├─ treasury_trader.py (677 lines) - Trader class
├─ memory_hooks.py (481 lines) - Memory integration
├─ types.py (229 lines) - Type definitions
├─ constants.py (183 lines) - Configuration
├─ logging_utils.py (101 lines) - Logging
└─ __init__.py (101 lines) - Public API

Total: 5,202 lines across 13 files
```

### Module Responsibilities

#### trading_engine.py
- Main trading orchestrator
- Decision matrix integration
- Strategy selection
- Position lifecycle management

#### trading_execution.py
- Jupiter DEX integration
- bags.fm API integration
- Swap execution
- Transaction confirmation
- Fallback logic

#### trading_positions.py
- Position tracking
- Position updates
- Position queries
- Position persistence

#### trading_risk.py
- Risk limits enforcement
- Position sizing
- Exposure calculation
- Circuit breakers

#### trading_analytics.py
- PnL calculation
- Performance metrics
- Trade history
- Reporting

#### trading_operations.py ⚠️
**Status:** 1,237 lines (exceeds 1000-line limit)
**Needs:** Further breakdown into:
- trading_operations_core.py (~400 lines)
- trading_operations_swap.py (~400 lines)
- trading_operations_monitor.py (~400 lines)

#### treasury_trader.py
- Main TreasuryTrader class
- Public API
- Configuration management

#### memory_hooks.py
- Memory system integration
- Context loading
- Learning storage
- Recall queries

## Error Handling Strategy

### Custom Error Classes
```python
# core/errors.py
TradeExecutionError - Trade failed to execute
InsufficientFundsError - Not enough balance
SlippageExceededError - Slippage too high
RPCError - Solana RPC failure
```

### Error Recovery
- **Retry Logic:** 3 attempts with exponential backoff
- **Fallback:** Jupiter → bags.fm fallback
- **User Messaging:** Clear, actionable error messages
- **Logging:** Structured error logs with context

## Testing Strategy

### Unit Tests
- Test individual functions in isolation
- Mock external dependencies (Jupiter, Grok, bags.fm)
- Fast execution (<1s per test)

### Integration Tests
- Test end-to-end flows (buy, sell, TP/SL)
- Use test wallets/tokens
- Verify state changes

### Coverage Target
- **Minimum:** 80% line coverage
- **Focus:** Critical paths (trade execution, TP/SL)
- **Tools:** pytest, pytest-cov, pytest-asyncio

## Migration Strategy

### Backward Compatibility
1. **demo.py:** Acts as compatibility layer, re-exports from modules
2. **demo_legacy.py:** Original preserved for emergency rollback
3. **Import paths:** Both old and new imports work

### Rollout Plan
1. ✅ Create new modular structure
2. ✅ Migrate functions module-by-module
3. ✅ Update imports across codebase
4. ✅ Add tests
5. ⏭️ Run integration tests
6. ⏭️ Monitor in production
7. ⏭️ Archive legacy after 1 month

## Verification Checklist

- [x] All modules <1000 lines (except trading_operations.py ⚠️)
- [x] No circular dependencies
- [x] Backward compatible
- [x] Error handling present
- [x] Async patterns used
- [ ] 80%+ test coverage
- [ ] Integration tests passing
- [ ] Documentation complete
- [ ] Performance validated

## Performance Impact

### Expected Improvements
- **Load time:** Similar (imports lazy-loaded)
- **Memory:** Slightly lower (better gc)
- **Maintainability:** 10x better
- **Debugging:** Much easier

### Monitored Metrics
- Response time for /demo command
- Trade execution latency
- Memory usage per handler
- Error rates

## Outstanding Issues

### 1. trading_operations.py Exceeds Limit
**Lines:** 1,237 (target: <1000)
**Solution:** Split into 3 sub-modules
**Priority:** P1
**Effort:** 1-2 days

### 2. Integration Test Coverage
**Current:** Unknown (tests exist but not run)
**Target:** 80%+
**Priority:** P0
**Effort:** 2-3 days

### 3. Documentation
**Current:** Inline docs present
**Missing:** Developer guide, architecture docs
**Priority:** P1
**Effort:** 1 day

## Success Metrics

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Largest file | 10,015 lines | 1,237 lines | <1000 lines |
| Demo modules | 1 file | 7 files | 5-10 files |
| Trading modules | 1 file | 13 files | 10-15 files |
| Test coverage | Unknown | Unknown | 80%+ |
| Trade success rate | ~80% | Unknown | 95%+ |

## Lessons Learned

### What Worked
1. **Module boundaries:** Clear separation of concerns
2. **Preservation:** Keeping demo_legacy.py for safety
3. **Compatibility layer:** Smooth migration path
4. **Error patterns:** Consistent error handling

### What Could Be Better
1. **trading_operations.py:** Should have been split further initially
2. **Testing:** Should have been done concurrently with refactor
3. **Documentation:** Should have been written during refactor

## Next Steps

1. **Immediate:** Split trading_operations.py into 3 files
2. **Short-term:** Run integration tests, measure coverage
3. **Medium-term:** Complete documentation
4. **Long-term:** Performance optimization based on production metrics
