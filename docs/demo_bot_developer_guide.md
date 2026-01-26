# Demo Bot Developer Guide

**Version:** 2.0
**Last Updated:** 2026-01-26

## Quick Start

### Running Tests

```bash
# All demo tests
pytest tests/unit/test_demo*.py -v

# Specific module
pytest tests/unit/test_demo_trading.py -v

# With coverage
pytest tests/unit/test_demo*.py --cov=tg_bot/handlers/demo --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Starting the Bot

```bash
# Via supervisor (recommended)
python bots/supervisor.py

# Standalone (for testing)
python tg_bot/bot.py
```

### Environment Variables

Required:
- `TELEGRAM_BOT_TOKEN` - Telegram bot API token
- `DEMO_WALLET_PASSWORD` - Encrypted wallet password
- `BAGS_FM_API_KEY` - bags.fm API key (optional)
- `XAI_API_KEY` - Grok AI for sentiment (optional)

## Architecture Overview

### Module Structure

```
demo/
├── demo_core.py         # Main handlers
├── demo_trading.py      # Trade execution
├── demo_sentiment.py    # Sentiment analysis
├── demo_orders.py       # TP/SL management
├── demo_ui.py           # UI components
├── demo_callbacks.py    # Callback router
├── callbacks/           # Specialized handlers
├── input_handlers/      # Text input processors
└── ui/                  # UI utilities
```

### Adding a New Feature

#### 1. Create Callback Handler

```python
# callbacks/my_feature.py

async def handle_my_feature(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
) -> None:
    """
    Handle my feature callbacks.

    Callback format: demo:my_feature:action:param

    Args:
        update: Telegram update
        context: Bot context
        parts: Callback data split by ':'
    """
    action = parts[2] if len(parts) > 2 else "main"

    if action == "main":
        # Show main UI
        text = "🚀 My Feature\n\nDescription here"
        buttons = [
            [InlineKeyboardButton("Action", callback_data="demo:my_feature:action")],
            [InlineKeyboardButton("« Back", callback_data="demo:main")],
        ]
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    elif action == "action":
        # Perform action
        await update.callback_query.answer("Action performed!")
```

#### 2. Register in Callback Router

```python
# demo_callbacks.py

from .callbacks.my_feature import handle_my_feature

async def demo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... existing code ...

    elif parts[1] == "my_feature":
        await handle_my_feature(update, context, parts)
```

#### 3. Add to Main Menu

```python
# demo_core.py

def build_main_menu():
    buttons = [
        # ... existing buttons ...
        [InlineKeyboardButton("🚀 My Feature", callback_data="demo:my_feature:main")],
    ]
```

#### 4. Write Tests

```python
# tests/unit/test_demo_my_feature.py

import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_my_feature_main():
    """Test my feature main view."""
    update = MagicMock()
    update.callback_query = AsyncMock()
    context = MagicMock()

    await handle_my_feature(update, context, ["demo", "my_feature", "main"])

    update.callback_query.edit_message_text.assert_called_once()
    assert "My Feature" in update.callback_query.edit_message_text.call_args[1]["text"]
```

## Common Patterns

### Callback Pattern

**Format:** `demo:section:action:param1:param2`

**Examples:**
- `demo:main` - Main menu
- `demo:buy:select:0.1` - Buy 0.1 SOL
- `demo:position:sell:abc123` - Sell position abc123
- `demo:tpsl:set:abc123:tp` - Set take-profit for position

### State Management

```python
# Set state
context.user_data["awaiting_token"] = True
context.user_data["buy_amount"] = 0.1

# Check state
if context.user_data.get("awaiting_token"):
    # User should send token address
    pass

# Clear state
context.user_data.pop("awaiting_token", None)
```

### Error Handling

```python
from core.api.errors import InsufficientFundsError, TransactionError

async def trade_function():
    try:
        result = await execute_trade()
        return result
    except InsufficientFundsError as e:
        await update.effective_message.reply_text(
            f"❌ Insufficient funds\n\n"
            f"Required: {e.details['required']} SOL\n"
            f"Available: {e.details['available']} SOL"
        )
    except TransactionError as e:
        logger.error(f"Trade failed: {e}")
        await update.effective_message.reply_text(
            f"❌ Trade failed\n\n{e.message}"
        )
    except Exception as e:
        logger.exception("Unexpected error")
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again."
        )
```

### Retry Logic

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def api_call_with_retry():
    """Call external API with automatic retries."""
    return await external_api.call()
```

### Loading Indicators

```python
# Show loading message
loading_msg = await update.effective_message.reply_text("⏳ Processing...")

try:
    # Perform long operation
    result = await long_operation()

    # Update with result
    await loading_msg.edit_text(f"✅ Success!\n\n{result}")
except Exception as e:
    await loading_msg.edit_text(f"❌ Failed: {e}")
```

## Testing Patterns

### Mocking Telegram Objects

```python
from unittest.mock import AsyncMock, MagicMock

# Create mock update
update = MagicMock()
update.effective_user = MagicMock()
update.effective_user.id = 123456
update.effective_message = AsyncMock()
update.callback_query = AsyncMock()

# Create mock context
context = MagicMock()
context.user_data = {}
context.bot_data = {}
```

### Testing Async Functions

```python
@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await my_async_function()
    assert result == expected_value
```

### Testing Database Operations

```python
@pytest.fixture
def db_session():
    """Create test database session."""
    from core.database import get_session
    session = get_session()
    yield session
    session.rollback()
    session.close()

def test_create_position(db_session):
    """Test position creation."""
    position = create_position(db_session, ...)
    assert position.id is not None
```

## Code Style

### Imports

```python
# Standard library
import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict

# Third-party
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Local
from core.api.errors import TransactionError
from core.database import get_session
from .demo_ui import build_button_row
```

### Function Signatures

```python
async def execute_trade(
    token_address: str,
    amount_sol: float,
    slippage_bps: int = 100,
    *,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Execute a token trade.

    Args:
        token_address: Solana token address (base58)
        amount_sol: Amount in SOL to spend
        slippage_bps: Slippage tolerance in basis points (default: 100 = 1%)
        dry_run: If True, simulate trade without executing

    Returns:
        Trade result with transaction signature and amounts

    Raises:
        InsufficientFundsError: Not enough SOL in wallet
        TransactionError: On-chain transaction failed
        ValidationError: Invalid token address or amount
    """
    pass
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Debug info: %s", data)
logger.info("Trade executed: %s", tx_signature)
logger.warning("Fallback to Jupiter after bags.fm failure")
logger.error("Trade failed: %s", error, exc_info=True)
```

## Debugging

### Enable Debug Logging

```python
# In bot.py or your script
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Telegram Bot Inspector

```python
# Add to any handler
logger.debug(f"Update: {update.to_dict()}")
logger.debug(f"Context user_data: {context.user_data}")
logger.debug(f"Callback data: {update.callback_query.data}")
```

### Database Inspection

```python
from core.database import get_session

session = get_session()
positions = session.query(DemoPosition).filter_by(user_id=123456).all()
for p in positions:
    print(f"Position: {p.token_address}, PnL: {p.pnl}")
```

### Testing API Calls

```python
# Use dry_run mode
result = await execute_buy_with_tpsl(
    token_address="...",
    amount_sol=0.1,
    dry_run=True,  # Doesn't execute on-chain
)
print(f"Would have traded: {result}")
```

## Performance Optimization

### Avoid Blocking Operations

```python
# Bad - blocks event loop
result = requests.get("https://api.example.com")

# Good - async
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get("https://api.example.com") as resp:
        result = await resp.json()
```

### Batch Database Operations

```python
# Bad - multiple queries
for position in positions:
    position.update_price()
    session.commit()

# Good - batch commit
for position in positions:
    position.update_price()
session.commit()
```

### Cache Expensive Calls

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_token_metadata(token_address: str):
    """Cache token metadata."""
    return fetch_from_api(token_address)
```

## Common Issues

### Handler Not Triggered

**Symptom:** Callback/command does nothing

**Check:**
1. Handler registered in `demo_core.py`?
2. Callback pattern matches in `demo_callbacks.py`?
3. Any exceptions in logs?

### State Not Persisting

**Symptom:** User state lost between messages

**Solution:** Use `context.user_data`, not local variables:

```python
# Bad
awaiting_token = True

# Good
context.user_data["awaiting_token"] = True
```

### Database Lock

**Symptom:** `database is locked` error

**Solution:** Use proper session management:

```python
from core.database import get_session

session = get_session()
try:
    # Do database operations
    pass
finally:
    session.close()
```

## Deployment

### Pre-Deployment Checklist

- [ ] All tests passing (`pytest`)
- [ ] Coverage > 60% for new code
- [ ] No debug logging in production code
- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] Rollback plan documented

### Deploying New Feature

1. **Test locally:** Verify on test bot
2. **Run full test suite:** `pytest tests/`
3. **Deploy to staging:** Test with real data
4. **Monitor logs:** Watch for errors
5. **Deploy to production:** Gradual rollout
6. **Monitor metrics:** Response times, error rates

### Rollback Procedure

```bash
# Stop bot
supervisorctl stop telegram_bot

# Revert code
git revert <commit-hash>

# Restart bot
supervisorctl start telegram_bot

# Verify
tail -f logs/telegram_bot.log
```

## Resources

### Documentation

- [Telegram Bot API](https://core.telegram.org/bots/api)
- [python-telegram-bot](https://docs.python-telegram-bot.org/)
- [Solana Web3.py](https://solana-py.readthedocs.io/)
- [Jupiter API](https://station.jup.ag/docs)

### Internal Docs

- `demo_bot_architecture.md` - System architecture
- `demo_bot_troubleshooting.md` - Common issues
- `execution_paths.md` - All handler flows
- `refactoring_design.md` - Migration details

### Getting Help

- Check logs: `logs/telegram_bot.log`
- Search tests for examples
- Ask in team chat
- Review git history for similar changes
