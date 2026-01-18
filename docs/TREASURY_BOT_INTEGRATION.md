# Jarvis Treasury Bot - Integration Guide

## Overview

The Treasury Bot is a comprehensive Telegram trading interface providing:
- Real-time portfolio dashboard with live metrics
- Professional chart visualization (6+ chart types)
- Real-time alert system (8+ alert types)
- Market intelligence and analysis (6+ market views)
- Help system with 50+ commands
- Comprehensive admin controls

## Architecture

```
TreasuryBotManager (unified entry point)
├── TreasuryBot (commands & UI)
├── TreasuryDashboard (metrics display)
├── ChartGenerator (visualization)
├── ChartIntegration (chart rendering)
├── AlertSystem (real-time monitoring)
├── MarketIntelligence (market analysis)
└── HelpReference (documentation)
```

## Installation

### 1. Ensure Dependencies

```bash
pip install python-telegram-bot matplotlib numpy
```

### 2. Directory Structure

```
tg_bot/
├── treasury_bot_manager.py          # Main manager
├── services/
│   ├── treasury_bot.py              # Commands and UI
│   ├── treasury_dashboard.py        # Dashboard display
│   ├── chart_generator.py           # Chart generation
│   ├── chart_integration.py         # Chart integration
│   ├── alert_system.py              # Alerts
│   ├── market_intelligence.py       # Market data
│   └── help_reference.py            # Help system
└── handlers/
    └── treasury_handler.py           # Handler registration
```

## Quick Start Integration

### Option A: Standalone Usage

```python
from tg_bot.treasury_bot_manager import TreasuryBotManager
from bots.treasury.trading import TradingEngine

# Initialize
engine = TradingEngine(risk_level="moderate")
bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
admin_ids = [123456789, 987654321]  # Admin user IDs

manager = TreasuryBotManager(
    bot_token=bot_token,
    trading_engine=engine,
    admin_ids=admin_ids,
)

# Start
await manager.initialize()
await manager.start_polling()

# Shutdown
await manager.shutdown()
```

### Option B: Supervisor Integration

```python
# In supervisor.py

async def start_treasury_bot():
    """Start Treasury Bot component."""
    from tg_bot.treasury_bot_manager import TreasuryBotManager

    manager = TreasuryBotManager(
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        trading_engine=trading_engine,
        admin_ids=ADMIN_IDS,
    )

    if not await manager.initialize():
        raise RuntimeError("Failed to initialize Treasury Bot")

    if not await manager.start_polling():
        raise RuntimeError("Failed to start Treasury Bot polling")

    return manager

# Add to supervisor components
components['treasury_bot'] = {
    'start': start_treasury_bot,
    'max_restarts': 3,
    'backoff_base': 5.0,
}
```

## Commands Reference

### Dashboard & Monitoring

| Command | Purpose |
|---------|---------|
| `/treasury_dashboard` | Live portfolio dashboard |
| `/treasury_positions` | Open positions detail |
| `/treasury_trades` | Trade history |
| `/treasury_report` | Performance analytics |

### Configuration

| Command | Purpose |
|---------|---------|
| `/treasury_settings` | Risk & mode settings |
| `/treasury_help` | Command reference |
| `/quick_start` | New user guide |

### Market Data

| Command | Purpose |
|---------|---------|
| `/market_overview` | Market summary (BTC, ETH, SOL) |
| `/market_sentiment` | Sentiment analysis by asset |
| `/market_liquidations` | Liquidation heatmap |
| `/market_volume` | Volume and whale tracking |
| `/market_trending` | Trending tokens |
| `/market_macro` | Macro economic indicators |

## Key Features

### 1. Real-Time Dashboard

- Live balance, P&L, returns
- Open positions summary
- Win rate and trading stats
- Auto-refresh every 30 seconds

### 2. Chart Visualization

- Price action with moving averages
- Portfolio performance
- Drawdown analysis
- Position allocation pie charts
- Trade P&L distribution
- Risk/return scatter plots
- Sentiment heatmaps

### 3. Alert System

- Price alerts (movement threshold)
- Profit milestone alerts
- Stop loss triggers
- Risk threshold warnings
- Volatility alerts
- Sentiment shift alerts
- Liquidation warnings
- User subscription management
- Anti-spam cooldown

### 4. Market Intelligence

- Market overview with major assets
- Multi-source sentiment analysis
- Liquidation level visualization
- Trading volume analysis
- Whale activity tracking
- Trending tokens detection
- Macro economic indicators
- Fed policy impact

### 5. Admin Controls

- Toggle Live/Dry Run mode
- Set risk levels
- Force close positions
- Export reports

## Customization

### Alert Thresholds

```python
manager.alerts.price_alert_threshold = 0.05  # 5%
manager.alerts.pnl_alert_threshold = 10      # $10
manager.alerts.risk_threshold_pct = 20       # 20% drawdown
```

### Chart Styling

```python
# Edit in chart_generator.py
DARK_THEME = {
    'bg': '#1a1a1a',
    'text': '#ffffff',
    'bull': '#10b981',
    'bear': '#ef4444',
}
```

### Dashboard Refresh Rate

```python
manager.treasury_bot.REFRESH_INTERVAL = 30  # seconds
```

## Data Integration Points

### Trading Engine

Required methods:
- `get_open_positions()` → List[Position]
- `get_balance()` → Dict[str, float]
- `get_closed_trades()` → List[Trade]
- `open_position()` → bool
- `close_position()` → bool
- `monitor_stop_losses()` → List[str]

### Market Data

Configure in `market_intelligence.py`:
- Price feeds (Jupiter, DexScreener)
- Sentiment sources (Grok, Twitter)
- Liquidation data (GlassNode)
- Volume data (CoinGlass)

### Sentiment Integration

```python
# Wire to sentiment aggregator
manager.market_intel.sentiment_agg = sentiment_aggregator
```

## Monitoring & Troubleshooting

### Health Check

```python
# Get status anytime
status = manager.get_status()
print(status)
```

### Logs

Treasury Bot logs to: `jarvis.tg_bot`

```python
import logging
logging.getLogger('jarvis.tg_bot').setLevel(logging.DEBUG)
```

### Common Issues

| Issue | Solution |
|-------|----------|
| No chart generation | Ensure matplotlib, numpy installed |
| Alerts not sending | Check admin_ids, verify subscription |
| Stale market data | Check API rate limits, data freshness |
| Polling not starting | Ensure bot_token valid, not using polling elsewhere |

## Performance Notes

- Dashboard update: ~200ms
- Chart generation: ~500ms-1s per chart
- Alert check cycle: ~10s for full check
- Market data refresh: ~1-5min per source

## Security Notes

- Admin-only access enforced on sensitive commands
- No private keys stored in Telegram
- All trades validated before execution
- Position management isolated
- Audit trail logging enabled

## Future Enhancements

- [ ] Voice alerts (Telegram audio)
- [ ] Video streaming of charts
- [ ] Advanced backtesting in UI
- [ ] Custom alert templates
- [ ] Position scaling strategies
- [ ] Auto-rebalancing
- [ ] Multi-wallet support
- [ ] Mobile app integration

## Support

For issues or questions:
1. Check `/treasury_help`
2. Review `/quick_start`
3. Check troubleshooting in help system
4. Contact admin with screenshot

---

**Last Updated:** 2026-01-18
**Version:** 1.0.0
**Status:** Production Ready
