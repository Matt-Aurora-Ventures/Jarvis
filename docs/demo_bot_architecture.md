# Demo Bot Architecture

**Version:** 2.0 (Post-Refactor)
**Last Updated:** 2026-01-26
**Status:** Production

## Overview

The Demo Bot provides a Telegram-based trading interface for Jarvis, featuring buy/sell execution, sentiment analysis, TP/SL management, and comprehensive position tracking.

## Architecture

### Module Structure

```
tg_bot/handlers/
├── demo/                          # Modular demo bot
│   ├── __init__.py               # Public API exports
│   ├── demo_core.py              # Main handlers & routing (362 lines)
│   ├── demo_trading.py           # Trade execution (709 lines)
│   ├── demo_sentiment.py         # Sentiment integration (535 lines)
│   ├── demo_orders.py            # TP/SL management (444 lines)
│   ├── demo_ui.py                # UI components (118 lines)
│   ├── demo_callbacks.py         # Callback router (517 lines)
│   ├── callbacks/                # Specialized callback handlers
│   │   ├── __init__.py
│   │   ├── buy.py               # Buy flow callbacks
│   │   ├── sell.py              # Sell flow callbacks
│   │   ├── position.py          # Position management
│   │   ├── tpsl.py              # TP/SL configuration
│   │   ├── sentiment_hub.py     # Sentiment hub navigation
│   │   ├── bags.py              # bags.fm integration
│   │   ├── snipe.py             # Insta-snipe feature
│   │   ├── watchlist.py         # Watchlist management
│   │   ├── wallet.py            # Wallet operations
│   │   ├── settings.py          # Settings & preferences
│   │   └── ... (12 more files)
│   ├── input_handlers/           # Text input processors
│   │   ├── buy_amount.py        # Custom buy amount input
│   │   ├── token_input.py       # Token address input
│   │   ├── wallet_import.py     # Private key import
│   │   └── watchlist.py         # Watchlist token input
│   └── ui/                       # UI utilities
│       ├── base.py              # Base UI components
│       └── theme.py             # Jarvis theme constants
├── demo.py                       # Compatibility layer (34 lines)
└── demo_legacy.py                # Original monolith (10,015 lines, preserved)
```

### Component Responsibilities

#### demo_core.py
**Purpose:** Main command handlers and routing

**Responsibilities:**
- `/demo` command handler
- Callback query router
- Message input handler
- State management (awaiting input flags)
- Handler registration

**Key Functions:**
- `demo()` - Main entry point
- `demo_callback()` - Routes callbacks to specialized handlers
- `demo_message_handler()` - Processes text input
- `register_demo_handlers()` - Registers all handlers with bot

**Coverage:** 44%

#### demo_trading.py
**Purpose:** Trade execution orchestration

**Responsibilities:**
- Buy execution with TP/SL
- Sell execution
- Swap orchestration (bags.fm → Jupiter fallback)
- Amount validation
- Retry logic with exponential backoff

**Key Functions:**
- `execute_buy_with_tpsl()` - Buy with automatic TP/SL setup
- `validate_buy_amount()` - Enforce min/max limits
- `_execute_swap_with_fallback()` - Primary swap executor
- `_swap_via_bags()` - bags.fm API execution
- `_swap_via_jupiter()` - Jupiter DEX fallback

**Error Handling:** 36 try/except blocks
**Coverage:** 61%

#### demo_sentiment.py
**Purpose:** Sentiment analysis and market intelligence

**Responsibilities:**
- Market regime detection
- Grok AI sentiment scoring
- Treasury activation monitoring
- bags.fm graduation tracking
- Trending tokens with sentiment

**Key Functions:**
- `get_market_regime()` - Current market state
- `get_ai_sentiment_for_token()` - Grok scoring
- `get_trending_with_sentiment()` - Top trending tokens
- `get_conviction_picks()` - High-conviction trades
- `get_bags_top_tokens_with_sentiment()` - bags.fm + Grok

**Coverage:** 84% ✅

#### demo_orders.py
**Purpose:** Take-profit and stop-loss management

**Responsibilities:**
- TP/SL order creation
- Background price monitoring
- Exit trigger evaluation
- Ladder exit execution (partial sells)
- Order persistence to database

**Key Functions:**
- `create_demo_tpsl_order()` - Create new order
- `_background_tp_sl_monitor()` - Continuous monitoring loop
- `_process_demo_exit_checks()` - Check if exit criteria met
- `execute_ladder_exit()` - Partial position selling

**Coverage:** 82% ✅

#### demo_ui.py
**Purpose:** Reusable UI components

**Responsibilities:**
- Button builders
- Message formatters
- Theme constants
- Layout helpers

**Coverage:** 29%

#### demo_callbacks.py
**Purpose:** Callback routing hub

**Responsibilities:**
- Pattern matching for callbacks
- Delegation to specialized handlers
- State preservation during navigation

**Key Functions:**
- `demo_callback()` - Main router
- Pattern format: `demo:action:param1:param2`

**Coverage:** 61%

### Callback Handlers (callbacks/)

Each specialized callback handler manages a specific feature area:

| Handler | Purpose | Lines | Coverage |
|---------|---------|-------|----------|
| buy.py | Buy flow callbacks | 95 | 7% |
| sell.py | Sell execution | 135 | 5% |
| position.py | Position management | 226 | 5% |
| tpsl.py | TP/SL configuration | 161 | 9% |
| sentiment_hub.py | Hub navigation | 139 | 25% |
| bags.py | bags.fm integration | 98 | 6% |
| snipe.py | Insta-snipe | 127 | 5% |
| watchlist.py | Watchlist CRUD | 43 | 10% |
| wallet.py | Wallet operations | 95 | 5% |

### Input Handlers (input_handlers/)

Text input processors for stateful flows:

| Handler | Purpose | Coverage |
|---------|---------|----------|
| buy_amount.py | Custom buy amount | 0% |
| token_input.py | Token address | 0% |
| wallet_import.py | Private key import | 0% |
| watchlist.py | Watchlist additions | 0% |

## Data Flow

### Buy Flow

```
User: /demo
  ↓
demo_core.demo()
  ↓
[UI: Main menu with Buy button]
  ↓
User: Clicks "Buy 🟢"
  ↓
demo_callbacks.demo_callback()
  ↓
callbacks/buy.py: handle_buy_flow()
  ↓
[UI: Buy amount selection]
  ↓
User: Selects "0.1 SOL"
  ↓
context.user_data["awaiting_token"] = True
  ↓
[UI: "Send token address"]
  ↓
User: Sends token address
  ↓
demo_core.demo_message_handler()
  ↓
input_handlers/token_input.py
  ↓
demo_trading.execute_buy_with_tpsl()
  ↓
  ├─ Fetch Grok sentiment score
  ├─ Calculate TP/SL prices
  ├─ Execute swap (bags.fm → Jupiter)
  ├─ Confirm transaction
  ├─ Save position to DB
  └─ Create TP/SL orders
  ↓
demo_orders.create_demo_tpsl_order()
  ↓
[UI: Trade success confirmation]
```

### Sell Flow

```
User: /demo → Positions
  ↓
[UI: List of open positions]
  ↓
User: Clicks position → "Sell 🔴"
  ↓
callbacks/sell.py: handle_sell()
  ↓
demo_trading._execute_swap_with_fallback()
  ↓
  ├─ Get current price
  ├─ Execute swap (bags.fm → Jupiter)
  ├─ Confirm transaction
  ├─ Calculate PnL
  ├─ Update position in DB
  └─ Cancel TP/SL orders
  ↓
[UI: Sell confirmation with PnL]
```

### TP/SL Monitoring Flow

```
Background task: _background_tp_sl_monitor()
  ↓
[Every 10 seconds]
  ↓
Fetch active orders from DB
  ↓
For each order:
  ├─ Get current token price
  ├─ Check if TP reached
  ├─ Check if SL reached
  └─ Check if trailing stop triggered
  ↓
If exit triggered:
  ├─ Execute sell via demo_trading
  ├─ Update order status
  └─ Notify user via Telegram
```

## State Management

### User Context (context.user_data)

| Key | Type | Purpose |
|-----|------|---------|
| awaiting_token | bool | User should send token address |
| awaiting_token_search | bool | User searching for token |
| awaiting_custom_buy | bool | User should send buy amount |
| awaiting_wallet_import | bool | User should send private key |
| awaiting_watchlist_token | bool | User adding to watchlist |
| last_token_address | str | Last token interacted with |
| buy_amount | float | Selected buy amount in SOL |

### Database State

**demo_positions** table:
- Position tracking (entry price, size, PnL)
- TP/SL configuration
- Trade history

**demo_tp_sl_orders** table:
- Active TP/SL orders
- Trigger prices
- Status (pending, executed, cancelled)

## Error Handling

### Error Classes (core/api/errors.py)

- `InsufficientFundsError` - Not enough SOL
- `TransactionError` - On-chain failure
- `WalletError` - Wallet operation failed
- `CircuitOpenError` - Circuit breaker active
- `ValidationError` - Invalid input

### Recovery Strategies

1. **Retry Logic:** 3 attempts with exponential backoff
2. **Fallback:** bags.fm → Jupiter DEX
3. **Circuit Breaker:** Pause after 3 consecutive failures
4. **User Notification:** Clear error messages in Telegram

### Error Flow Example

```python
try:
    # Attempt bags.fm API
    result = await bags_client.swap(...)
except BagsAPIError as e:
    logger.warning("bags.fm failed, falling back to Jupiter")
    try:
        # Fallback to Jupiter
        result = await jupiter_client.swap(...)
    except JupiterError as je:
        logger.error("Both APIs failed")
        await update.effective_message.reply_text(
            "❌ Trade failed. Both exchanges unavailable.\n"
            f"Error: {je}\n"
            "Please try again later."
        )
        raise TransactionError(str(je))
```

## Testing

### Test Coverage

| Module | Coverage | Status |
|--------|----------|--------|
| demo_orders.py | 82% | ✅ Good |
| demo_sentiment.py | 84% | ✅ Good |
| demo_callbacks.py | 61% | 🟡 Moderate |
| demo_trading.py | 61% | 🟡 Moderate |
| demo_core.py | 44% | 🟠 Needs work |
| callbacks/* | 5-25% | 🔴 Low |
| input_handlers/* | 0% | 🔴 None |

**Overall:** 31.86% (240 tests passing)

### Test Files

- `test_demo_trading.py` - 34 tests for trading functions
- `test_demo_sentiment.py` - Sentiment integration tests
- `test_demo_orders.py` - TP/SL order tests
- `test_demo_v1.py` - 206 tests for UI/callbacks
- `test_demo_callbacks_router.py` - Callback routing tests

### Integration Tests

**Full trade cycle test:**
1. User sends `/demo`
2. Selects buy with amount
3. Sends token address
4. Trade executes
5. TP/SL orders created
6. Position tracked

**Status:** ✅ Passing

## Performance

### Response Times

| Operation | Target | Actual |
|-----------|--------|--------|
| /demo command | <1s | ~0.5s |
| Buy execution | <10s | ~5-8s |
| Sell execution | <10s | ~4-6s |
| TP/SL monitoring | 10s interval | 10s |

### Resource Usage

- **Memory:** ~50MB per handler
- **Database queries:** <10 per operation
- **API calls:** 1-3 per trade (bags.fm, Jupiter, Solana RPC)

## Security

### Input Validation

- Token addresses validated (Solana base58)
- Buy amounts min/max enforced
- Private keys sanitized before storage

### Authentication

- Admin-only features (wallet export, settings)
- User-specific data isolation
- Telegram user ID verification

## Migration Notes

### Backward Compatibility

**Old imports still work:**
```python
from tg_bot.handlers.demo import execute_buy_with_tpsl
```

**New imports preferred:**
```python
from tg_bot.handlers.demo.demo_trading import execute_buy_with_tpsl
```

### Rollback Plan

If critical issues arise:
1. Revert to `demo_legacy.py`
2. Update imports to point to legacy
3. Monitor for 24 hours
4. Resume modular migration

## Future Improvements

### Short-term

1. Increase callback handler test coverage (5% → 60%+)
2. Add input handler tests (0% → 80%+)
3. Split trading_operations.py (1,237 lines → <1000)

### Long-term

1. WebSocket price streaming (vs polling)
2. Multi-wallet support
3. Advanced order types (OCO, iceberg)
4. Mobile app integration

## Related Documentation

- `demo_bot_developer_guide.md` - Development workflows
- `demo_bot_troubleshooting.md` - Common issues
- `execution_paths.md` - All handler flows
- `refactoring_design.md` - Migration details
