# Position Monitoring Alert System

Enhanced position monitoring with intelligent alerts for the Jarvis trading system.

## Features

- **P&L Threshold Alerts**: Notifications at configurable profit/loss levels (+20%, -10%, etc.)
- **Stop Loss Monitoring**: Critical alerts when stop loss is triggered or near
- **Take Profit Tracking**: Notifications when TP is reached or close
- **Position Size Changes**: Detect significant changes in position value
- **Volume Spike Detection**: Alert on unusual trading volume
- **Stale Position Detection**: Warn about positions open too long
- **Rapid Loss Detection**: Critical alerts for quick drawdowns
- **Multi-Channel Delivery**: Telegram, core alert engine, and alert system integration

## Quick Start

### Basic Setup

```python
from bots.treasury.alert_integration import setup_position_alerts

# Create trading engine (your existing instance)
from bots.treasury.trading import TradingEngine
engine = TradingEngine(...)

# Setup alerts
monitor, integration = setup_position_alerts(
    trading_engine=engine,
    admin_ids=[12345678]  # Your Telegram user ID
)

# Start monitoring
await monitor.start_monitoring(check_interval=30)  # Check every 30 seconds
```

### With Telegram Integration

```python
from telegram.ext import ContextTypes

# Get your Telegram bot context
context: ContextTypes.DEFAULT_TYPE = ...

monitor, integration = setup_position_alerts(
    trading_engine=engine,
    admin_ids=[12345678],
    telegram_context=context
)

await monitor.start_monitoring()
```

### Custom Thresholds

```python
from bots.treasury.position_alerts import AlertThreshold

custom_thresholds = AlertThreshold(
    profit_levels=[15.0, 30.0, 75.0],  # Alert at +15%, +30%, +75%
    loss_levels=[8.0, 15.0, 25.0],     # Alert at -8%, -15%, -25%
    tp_proximity_pct=3.0,               # Alert when within 3% of TP
    sl_proximity_pct=2.0,               # Alert when within 2% of SL
    stale_position_hours=48.0,          # Alert if open > 48 hours
    rapid_loss_pct=20.0,                # Alert on 20% rapid drop
    rapid_loss_window_minutes=15.0      # Within 15 minute window
)

monitor, integration = setup_position_alerts(
    trading_engine=engine,
    admin_ids=[12345678],
    custom_thresholds=custom_thresholds
)
```

## Alert Types

### 1. Profit Threshold Alerts

Triggered when position reaches profit milestones.

**Example:**
```
✅ Profit Milestone: +20%
Symbol: SOL

Position has reached +20% profit!

Entry Price: $100.00
Current Price: $120.00
Unrealized P&L: $200.00
P&L %: +20.00%
Take Profit: $130.00
```

### 2. Loss Threshold Alerts

Triggered when position hits loss levels.

**Example:**
```
⚠️ Loss Alert: -10%
Symbol: BONK

Position has lost 10% of value.

Entry Price: $0.000010
Current Price: $0.000009
Unrealized P&L: -$50.00
P&L %: -10.00%
Stop Loss: $0.000008
```

### 3. Stop Loss Triggered

Critical alert when stop loss is hit.

**Example:**
```
🚨 Stop Loss Triggered!
Symbol: ETH

Position hit stop loss at $2800.00

Entry Price: $3000.00
Stop Loss: $2800.00
Current Price: $2750.00
Loss: -$200.00
Loss %: -8.33%
```

### 4. Take Profit Reached

Success alert when TP is hit.

**Example:**
```
✅ Take Profit Hit!
Symbol: BTC

Position reached take profit target at $48000.00

Entry Price: $40000.00
Target Price: $48000.00
Current Price: $50000.00
Profit: $10000.00
Profit %: +25.00%
```

### 5. Proximity Alerts

Warns when near TP or SL.

**Example:**
```
🎯 Near Take Profit
Symbol: ADA

Position is within 3.5% of take profit target.

Current Price: $0.57
Take Profit: $0.60
Distance: 3.50%
P&L %: +14.00%
```

### 6. Stale Position

Warns about positions open too long.

**Example:**
```
⏰ Stale Position
Symbol: MATIC

Position has been open for 50.2 hours with no action.

Opened At: 2024-01-15 10:30
Hours Open: 50.2
Current P&L: $15.00
P&L %: +2.50%
```

### 7. Rapid Loss

Critical alert for quick drawdowns.

**Example:**
```
🚨 Rapid Loss Detected
Symbol: AVAX

Position dropped 18.5% from peak in 12 minutes!

Peak P&L: +20.00%
Current P&L: +1.50%
Drawdown: 18.50%
Time Window: 12 min
```

## Advanced Usage

### Manual Position Checks

```python
# Check a specific position
position = engine.get_position_by_id("POS-123")
await monitor.check_position(position)

# Check all open positions
await monitor.check_all_positions()
```

### Custom Alert Handlers

```python
async def custom_alert_handler(alert):
    """Custom handler for alerts."""
    print(f"Alert: {alert.title}")
    # Send to Discord
    # Log to database
    # Trigger automated response
    # etc.

monitor.register_alert_handler(custom_alert_handler)
```

### Multi-Handler Setup

```python
async def telegram_handler(alert):
    """Send to Telegram."""
    await bot.send_message(chat_id=ADMIN_ID, text=alert.to_telegram_message())

async def discord_handler(alert):
    """Send to Discord."""
    await discord_channel.send(alert.message)

async def database_handler(alert):
    """Log to database."""
    await db.insert_alert(alert.to_dict())

# Register all handlers
monitor.register_alert_handler(telegram_handler)
monitor.register_alert_handler(discord_handler)
monitor.register_alert_handler(database_handler)
```

### Monitoring Control

```python
# Start monitoring
await monitor.start_monitoring(check_interval=30)

# Stop monitoring
monitor.stop_monitoring()

# Get statistics
stats = monitor.get_stats()
print(f"Alerts sent: {stats['total_alerts_sent']}")
print(f"Positions tracked: {stats['positions_tracked']}")
print(f"By type: {stats['alerts_by_type']}")
```

### Integration with Treasury UI

```python
from bots.treasury.telegram_ui import TradingUI
from bots.treasury.alert_integration import setup_position_alerts

# Create UI
ui = TradingUI(
    bot_token=BOT_TOKEN,
    trading_engine=engine,
    admin_ids=[ADMIN_ID]
)

# Setup alerts with UI context
monitor, integration = setup_position_alerts(
    trading_engine=engine,
    admin_ids=[ADMIN_ID]
)

# After UI starts, update context
await ui.start()
integration.set_telegram_context(ui.app.bot)

# Start monitoring
await monitor.start_monitoring()
```

## Alert Cooldown

To prevent spam, alerts have a configurable cooldown period (default: 5 minutes).

```python
monitor = PositionMonitor(
    trading_engine=engine,
    alert_cooldown_seconds=300  # 5 minutes
)
```

Once an alert is sent for a specific position/type combination, it won't send again until the cooldown expires.

## Testing

Run the test suite:

```bash
# All tests
pytest tests/unit/test_position_alerts.py -v

# Specific test
pytest tests/unit/test_position_alerts.py::TestPositionMonitor::test_profit_threshold_alert -v

# Integration tests
pytest tests/unit/test_alert_integration.py -v
```

## Production Setup

### Recommended Configuration

```python
from bots.treasury.position_alerts import AlertThreshold
from bots.treasury.alert_integration import setup_position_alerts

# Conservative thresholds for production
production_thresholds = AlertThreshold(
    profit_levels=[10.0, 25.0, 50.0, 100.0],  # Milestone alerts
    loss_levels=[5.0, 10.0, 20.0],            # Early warning
    tp_proximity_pct=5.0,                      # 5% warning before TP
    sl_proximity_pct=3.0,                      # 3% warning before SL (more sensitive)
    stale_position_hours=72.0,                 # 3 days
    rapid_loss_pct=15.0,                       # 15% rapid loss threshold
    rapid_loss_window_minutes=30.0             # 30 minute window
)

monitor, integration = setup_position_alerts(
    trading_engine=engine,
    admin_ids=[ADMIN_ID],
    telegram_context=context,
    custom_thresholds=production_thresholds
)

# Start with reasonable check interval
await monitor.start_monitoring(check_interval=60)  # 1 minute
```

### Supervisor Integration

Add to `bots/supervisor.py`:

```python
# In supervisor startup
from bots.treasury.alert_integration import setup_position_alerts

monitor, integration = setup_position_alerts(
    trading_engine=treasury_trader,
    admin_ids=config.ADMIN_IDS
)

# Add to supervisor's async tasks
asyncio.create_task(monitor.start_monitoring(check_interval=60))
```

## Troubleshooting

### No Alerts Received

1. Check admin IDs are correct
2. Verify Telegram context is set
3. Check monitoring is running: `monitor.get_stats()`
4. Verify positions exist: `engine.get_open_positions()`

### Too Many Alerts

1. Increase alert cooldown: `alert_cooldown_seconds=600` (10 min)
2. Adjust thresholds to be less sensitive
3. Reduce check interval

### Missing Specific Alert Types

1. Check position has required fields (TP/SL prices)
2. Verify thresholds are set correctly
3. Check logs for errors in alert checks

## Performance

- **Memory**: ~1KB per position snapshot
- **CPU**: Negligible (async checks)
- **Network**: 1 Telegram API call per alert per admin
- **Recommended Interval**: 30-60 seconds for production

## Security

- Only admins receive alerts
- Alert messages use HTML parsing (no injection risk)
- No position modification - read-only monitoring
- Alert cooldown prevents spam attacks

## Future Enhancements

Potential additions:

- [ ] Custom alert templates
- [ ] Alert priority/severity filtering
- [ ] Historical alert analysis
- [ ] Alert aggregation (daily summary)
- [ ] Machine learning for anomaly detection
- [ ] Multi-language support
- [ ] Voice/push notifications
- [ ] Alert acknowledgment system
