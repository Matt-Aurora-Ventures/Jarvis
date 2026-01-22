# JARVIS Chart Integration

## Overview

JARVIS now supports beautiful matplotlib-based chart generation and display directly in Telegram. Charts are generated on-demand with dark theme styling to match the JARVIS aesthetic.

## Features

- **Price Charts**: Line charts with gradient fills
- **Volume Bars**: Optional volume subplot
- **Dark Theme**: Professional dark mode styling (#1E1E1E background, #00D4AA accent)
- **Timestamps**: Automatic time axis formatting
- **Graceful Fallback**: Works even if matplotlib not installed

## Quick Start

### Installation

```bash
# Install matplotlib (optional but recommended)
pip install matplotlib

# Or with project dependencies
pip install -r requirements.txt
```

### Usage in Demo Bot

1. Run `/demo` command in Telegram
2. Click "🤖 AI Report"
3. Click "📊 View BTC/SOL Chart"
4. Charts are generated and sent as images

## Technical Implementation

### Chart Generation Function

Located at: [tg_bot/handlers/demo.py:131-222](tg_bot/handlers/demo.py#L131-L222)

```python
def generate_price_chart(
    prices: List[float],
    timestamps: Optional[List[datetime]] = None,
    symbol: str = "TOKEN",
    timeframe: str = "24H",
    volume: Optional[List[float]] = None,
) -> Optional[BytesIO]:
    """
    Generate a price chart image using matplotlib.

    Returns:
        BytesIO buffer containing PNG image, or None if matplotlib unavailable
    """
```

### Features:

- **Price Line**: Solid line with gradient fill
- **Volume Bars**: Optional subplot (blue bars)
- **Styling**: Dark theme with white text
- **Time Formatting**: Automatic HH:MM format for timestamps
- **Error Handling**: Returns None if generation fails

### Chart Handler

Located at: [tg_bot/handlers/demo.py:7164-7231](tg_bot/handlers/demo.py#L7164-L7231)

```python
elif action == "view_chart":
    # Generate and send BTC/SOL price chart
    btc_chart = generate_price_chart(prices=btc_prices, timestamps=timestamps, symbol="BTC")
    sol_chart = generate_price_chart(prices=sol_prices, timestamps=timestamps, symbol="SOL")

    await query.message.reply_photo(photo=btc_chart, caption="📊 Bitcoin Price Chart")
    await query.message.reply_photo(photo=sol_chart, caption="📊 Solana Price Chart")
```

## Chart Styling

### Color Scheme

| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark Gray | #1E1E1E |
| Chart Area | Medium Gray | #2C2C2C |
| Price Line | JARVIS Green | #00D4AA |
| Volume Bars | Blue | #4A90E2 |
| Text | White | #FFFFFF |
| Grid | Light Gray (30% alpha) | -- |

### Chart Dimensions

- **Standard Chart**: 10x6 inches (1000x600 pixels @ 100 DPI)
- **With Volume**: 10x7 inches (1000x700 pixels @ 100 DPI)
- **DPI**: 100 (optimized for Telegram display)

## Integration with Other Systems

### Real Price Data

To use real price data instead of mock data, fetch from APIs:

```python
# Example: Fetch from Birdeye API
from tg_bot.services.birdeye_service import get_token_ohlcv

ohlcv = await get_token_ohlcv(token_address, timeframe="24H")
prices = [candle['close'] for candle in ohlcv]
timestamps = [candle['time'] for candle in ohlcv]
volumes = [candle['volume'] for candle in ohlcv]

chart = generate_price_chart(
    prices=prices,
    timestamps=timestamps,
    symbol=symbol,
    timeframe="24H",
    volume=volumes
)
```

### Adding to Other Handlers

```python
# In any handler
from tg_bot.handlers.demo import generate_price_chart

# Generate chart
chart_buffer = generate_price_chart(
    prices=[100, 102, 98, 105, 110],
    symbol="TOKEN",
    timeframe="1H"
)

# Send to Telegram
if chart_buffer:
    await update.message.reply_photo(
        photo=chart_buffer,
        caption="📊 *Token Price Chart*",
        parse_mode=ParseMode.MARKDOWN
    )
else:
    await update.message.reply_text("Chart generation failed (matplotlib not available)")
```

## Fallback Behavior

If matplotlib is not installed:

1. `MATPLOTLIB_AVAILABLE` flag set to False
2. `generate_price_chart()` returns None
3. Handler shows error: "Chart generation not available"
4. User instructed to install matplotlib

## Performance

- **Generation Time**: ~100-200ms per chart
- **Memory**: ~1-2MB per chart (in-memory BytesIO)
- **Telegram Limits**: Max 10MB per photo
- **Cleanup**: Matplotlib figures closed after generation

## Alternative Chart Options

### Option 1: Matplotlib (Current Implementation)
- ✅ Full control over styling
- ✅ No API keys required
- ✅ Works offline
- ❌ Requires matplotlib library

### Option 2: QuickChart API
- ✅ No libraries required
- ✅ Simple URL-based
- ❌ External dependency
- ❌ Rate limits

```python
# Example QuickChart URL
chart_url = "https://quickchart.io/chart?c={type:'line',data:{labels:[1,2,3],datasets:[{data:[1,2,3]}]}}"
await update.message.reply_photo(chart_url)
```

### Option 3: TradingView Screenshots
- ✅ Professional trading charts
- ✅ Built-in indicators
- ❌ Requires TradingView account
- ❌ API key needed

## Troubleshooting

### Charts Not Appearing

1. **Check Matplotlib Installation:**
   ```bash
   python -c "import matplotlib; print(matplotlib.__version__)"
   ```

2. **Check Logs:**
   ```bash
   tail -f logs/telegram_bot.log | grep -i chart
   ```

3. **Check Error Tracker:**
   ```bash
   cat data/logs/error_database.json | jq '.[] | select(.component == "telegram_demo" and .context | contains("view_chart"))'
   ```

### Chart Generation Errors

Common issues:
- **Memory Error**: Reduce chart DPI or dimensions
- **Font Error**: Install system fonts or use default
- **Import Error**: Install matplotlib: `pip install matplotlib`

## Future Enhancements

Planned features:
- [ ] Candlestick charts (OHLC data)
- [ ] Multiple timeframes (1H, 4H, 1D, 7D, 1M)
- [ ] Technical indicators (MA, RSI, MACD)
- [ ] Comparison charts (multiple tokens)
- [ ] Portfolio performance charts
- [ ] P&L history charts
- [ ] Custom chart themes
- [ ] Export to PDF

## Related Files

- Chart Generation: [tg_bot/handlers/demo.py:131-222](tg_bot/handlers/demo.py#L131-L222)
- Chart Handler: [tg_bot/handlers/demo.py:7164-7231](tg_bot/handlers/demo.py#L7164-L7231)
- AI Report Menu: [tg_bot/handlers/demo.py:4673-4794](tg_bot/handlers/demo.py#L4673-L4794)
- Error Tracking: [core/logging/error_tracker.py](core/logging/error_tracker.py)

## References

- [Matplotlib Documentation](https://matplotlib.org/stable/index.html)
- [Telegram Bot API - sendPhoto](https://core.telegram.org/bots/api#sendphoto)
- [QuickChart API](https://quickchart.io/)
- [BobTelegramTools](https://robertanto.github.io/bob_telegram_tools/plot_ex/)

---

**Last Updated:** 2026-01-22
**Author:** JARVIS Development Team + Claude Sonnet 4.5
