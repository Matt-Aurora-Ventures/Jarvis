# Jarvis Web Interfaces

Web-based control panels for Jarvis trading and system management.

## Available Interfaces

### 1. Trading Interface (Port 5001)
**File:** `trading_web.py`
**URL:** http://127.0.0.1:5001

Mirrors the Telegram `/demo` UI with web-based trading:

**Features:**
- 📊 Portfolio overview (SOL balance, USD value, P&L)
- 🛒 Buy tokens with mandatory TP/SL
- 📈 View all open positions with real-time P&L
- 💰 Sell positions (25%, 50%, 100%)
- 🔍 AI sentiment analysis for tokens
- 📉 Market regime indicators
- 🔄 Auto-refresh every 30 seconds

**How to Run:**
```bash
cd web
python trading_web.py
```

Then open: http://127.0.0.1:5001

### 2. System Control Deck (Port 5000)
**File:** `task_web.py`
**URL:** http://127.0.0.1:5000

System-wide operations and monitoring:

**Features:**
- System health (CPU, RAM, disk, network)
- Mission control (research, backtesting, diagnostics)
- Task management
- Config toggles (observer, missions, monitors)
- Security & network logs
- Action approval gates

**How to Run:**
```bash
cd web
python task_web.py
```

Then open: http://127.0.0.1:5000

## Architecture

Both interfaces use:
- **Backend:** Flask with async support
- **Frontend:** Vanilla JS + beautiful handcrafted CSS
- **Style:** Matches the warm, professional aesthetic of the demo UI

## API Endpoints (Trading Interface)

### GET /api/status
Returns wallet, balance, positions count, P&L

### GET /api/positions
Returns all open positions with details

### POST /api/token/sentiment
Request body: `{"token_address": "..."}`
Returns AI sentiment analysis

### POST /api/trade/buy
Request body:
```json
{
  "token_address": "...",
  "amount_sol": 0.1,
  "tp_percent": 50,
  "sl_percent": 20,
  "slippage_bps": 100
}
```
Executes buy with TP/SL via bags.fm → Jupiter fallback

### POST /api/trade/sell
Request body:
```json
{
  "position_id": "buy_abc123",
  "percentage": 100
}
```
Sells position (25%, 50%, or 100%)

## Environment Variables

Same as main Jarvis system:
- `DEMO_TRADING_PROFILE` - Trading profile (default: "demo")
- `DEMO_WALLET_PASSWORD` - Wallet password for trades
- `DEMO_WALLET_DIR` - Wallet directory path
- `BAGS_API_KEY` / `BAGS_PARTNER_KEY` - For bags.fm trading
- Jupiter fallback uses same RPC/wallet setup

## Security Notes

- No authentication built-in (assumes localhost-only access)
- For production: Add auth middleware before exposing publicly
- Trading executes real transactions if `DEMO_TRADING_PROFILE` points to live wallet
- Always verify dry-run vs live mode before trading

## Development

To add features:
1. Add API endpoint in `trading_web.py`
2. Add UI component in `templates/trading.html`
3. Follow existing patterns for async loop handling
4. Test with dry-run profile first

## Troubleshooting

**"Failed to get status"**
- Check that demo trading engine is configured
- Verify wallet password is set
- Check logs for specific errors

**"Sentiment analysis fails"**
- Ensure XAI_API_KEY is set for Grok analysis
- Check network connectivity
- Token may not have enough data

**"Buy/Sell fails"**
- Verify sufficient SOL balance
- Check that wallet is unlocked
- Ensure TP/SL are within valid ranges (5-200% TP, 5-99% SL)
- Review console for detailed error messages
