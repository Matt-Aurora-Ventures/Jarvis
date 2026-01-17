# bot_core.py Refactoring Guide

## Current State
- `bot_core.py`: 4731 lines, 84 functions
- Existing handlers in `handlers/`: admin.py, commands.py, sentiment.py, trading.py

## Proposed Structure

### Phase 1: Market Data (15 commands, ~800 lines)
**File:** `handlers/market_data.py`
- `price()` - Token price lookup
- `chart()` - Price chart generation
- `volume()` - Trading volume
- `mcap()` - Market cap
- `liquidity()` - Liquidity info
- `gainers()` - Top gainers
- `losers()` - Top losers
- `newpairs()` - New trading pairs
- `solprice()` - SOL price

### Phase 2: System Commands (10 commands, ~500 lines)
**File:** `handlers/system.py`
- `health()` - System health
- `uptime()` - Bot uptime
- `metrics()` - System metrics
- `costs()` - API cost tracking
- `keystatus()` - API key status
- `clistats()` - CLI statistics
- `cliqueue()` - CLI queue status
- `flags()` - Feature flags

### Phase 3: Inline Handlers (~600 lines)
**File:** `handlers/inline.py`
- `_handle_status_inline()`
- `_handle_trending_inline()`
- `_refresh_balance_inline()`
- `_refresh_report_inline()`
- `_show_positions_inline()`
- `_show_trade_ticket()`
- `_toggle_live_mode()`
- `_execute_ape_trade()`
- `_execute_trade_percent()`
- `_execute_trade_with_tp_sl()`
- `_close_position_callback()`

### Phase 4: Utilities (~300 lines)
**File:** `handlers/utilities.py`
- `_send_with_retry()`
- `_cleanse_sensitive_info()`
- `_get_chat_responder()`
- `_get_reply_mode()`
- `_should_reply()`
- `_is_message_for_jarvis()`
- `_parse_admin_ids()`
- `_get_treasury_admin_ids()`
- `_is_treasury_admin()`
- `_grade_for_signal()`
- `_get_grade_emoji()`
- `_get_tp_sl_for_grade()`
- `_build_full_trading_report()`

### Already Extracted
- `admin.py` - Admin commands (reload, logs)
- `commands.py` - Basic commands
- `sentiment.py` - Sentiment analysis
- `trading.py` - Trading operations

## Migration Steps

1. For each function group:
   a. Copy functions to new module
   b. Update imports to pull from shared modules
   c. Test in isolation
   d. Update `__init__.py` exports
   e. Update bot.py handler registration
   f. Remove from bot_core.py

2. Keep bot_core.py as the main entry point with:
   - `handle_message()` - Main message router
   - `handle_media()` - Media handler
   - `error_handler()` - Global error handler
   - Handler registration logic

3. Goal: Reduce bot_core.py from 4700 to ~1000 lines

## Dependencies to Watch

- `get_config()` from tg_bot.config
- `CostTracker` from tg_bot.services.cost_tracker
- `ChatResponder` from tg_bot.services.chat_responder
- `SignalService` from tg_bot.services.signal_service
- Treasury engine from bots.treasury

## Testing

After each extraction:
1. Run: `python -c "from tg_bot.handlers import *"`
2. Test affected commands manually
3. Check logs for import errors
