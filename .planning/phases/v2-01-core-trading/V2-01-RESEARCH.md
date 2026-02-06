# Phase 1 Research: Core Trading MVP

**Date:** 2026-02-02
**Status:** RESEARCH COMPLETE

## Key Discovery

The V2 Web Trading Dashboard is **80% already built** across 3 parallel implementations:

1. **web/trading_web.py** - Flask backend (342 lines, 7 API endpoints, active on port 5001)
2. **web_demo/** - FastAPI full-stack (production-ready with React frontend)
3. **frontend/** - Electron desktop app (80+ React components)

## Existing Assets

### Backend (web/trading_web.py - Flask)
- `GET /api/status` - Balance, positions, P&L
- `GET /api/positions` - All positions with real-time P&L
- `POST /api/token/sentiment` - AI sentiment
- `POST /api/trade/buy` - Buy with TP/SL
- `POST /api/trade/sell` - Sell positions
- `GET /api/market/regime` - Market conditions

### Trading Logic (tg_bot/handlers/demo/)
- demo_core.py - Portfolio display
- demo_trading.py - Buy/sell execution (bags.fm + Jupiter)
- demo_sentiment.py - Grok AI sentiment
- demo_orders.py - TP/SL monitoring

### Trading Clients
- core/trading/bags_client.py - BagsAPIClient
- bots/treasury/jupiter.py - JupiterClient
- core/exit_intents.py - Position tracking

### FastAPI Backend (web_demo/)
- Async WebSocket price feeds
- Rate limiting & security middleware
- React 18.2 + TypeScript frontend
- Zustand state management

### Electron Frontend (frontend/)
- 80+ React components
- Trading.jsx (25.6KB), PositionCard, StatsGrid
- useWallet, usePosition, useRealtimePrice hooks
- Charts: recharts, chart.js, lightweight-charts

## Recommended Approach

**Option A (FASTEST): Enhance Flask** - Add flask-socketio, serve React build
**Option B (BEST): Consolidate to FastAPI** - Port logic into web_demo/, enhance frontend

## What Still Needs Building
- Flask-SocketIO or FastAPI WebSocket for real-time P&L
- Unified frontend consolidating best components from web_demo + frontend
- Mobile responsive polish
- Integration testing
