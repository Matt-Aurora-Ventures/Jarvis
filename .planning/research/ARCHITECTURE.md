# Architecture Patterns: Premium Trading Dashboard

**Domain:** WebGL Trading Dashboard with Real-Time Data
**Researched:** 2026-02-05
**Overall Confidence:** HIGH (verified against existing codebase)

---

## Executive Summary

This architecture document defines how real-time data flows from the existing Jarvis backend (Flask + bags.fm) to a new Next.js WebGL frontend. The recommended approach uses a **dedicated WebSocket relay service** that bridges between bags.fm WebSocket feeds and frontend clients, with TanStack Query for REST data management and Zustand for local UI state.

The key insight: **You already have most of the backend infrastructure built.** The `web_demo/backend/` FastAPI service and `core/bags_websocket.py` provide production-ready WebSocket management. The architecture focuses on integrating these existing components rather than building from scratch.

---

## Recommended Architecture

```
+------------------+       +-------------------+       +------------------+
|   Next.js App    |       |   FastAPI Backend |       |    Data Sources  |
|   (WebGL UI)     |       |   (web_demo/)     |       |                  |
+------------------+       +-------------------+       +------------------+
|                  |       |                   |       |                  |
| Trading Views    |<----->| /api/v1/...       |<----->| Flask 5001       |
| - Portfolio      | REST  | - /positions      | Proxy | (trading_web.py) |
| - Positions      |       | - /trade/buy      |       |                  |
| - Buy/Sell       |       | - /trade/sell     |       | bags.fm API      |
|                  |       |                   |       | (direct)         |
| WebGL Canvas     |       +-------------------+       |                  |
| - Price Charts   |<----->| /ws/prices/...    |<----->| bags.fm WS       |
| - 3D Effects     | WS    | - /ws/portfolio   | WS    | (wss://...)      |
|                  |       |                   |       |                  |
| Zustand Store    |       | WebSocketManager  |       | Jupiter API      |
| - UI State       |       | - Price Relay     |       | (fallback)       |
| - Theme          |       | - Client Mgmt     |       |                  |
|                  |       | - Auto-Reconnect  |       | Grok/xAI         |
| TanStack Query   |       |                   |       | (sentiment)      |
| - Server State   |       | Redis (optional)  |       |                  |
| - Caching        |       | - Price Cache     |       +------------------+
+------------------+       +-------------------+
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Next.js Frontend** | WebGL rendering, user interactions, local state | FastAPI backend via REST + WS |
| **FastAPI Backend** (web_demo/) | API gateway, WebSocket relay, auth, rate limiting | Flask backend, bags.fm, Jupiter |
| **Flask Backend** (trading_web.py) | Trade execution, position management, wallet ops | bags.fm API, Jupiter DEX, Solana RPC |
| **BagsWebSocketClient** (core/) | bags.fm price feed subscription, graduation events | bags.fm WebSocket server |
| **TanStack Query** | Server state management, caching, background sync | REST API endpoints |
| **Zustand** | UI state (modals, themes, selections) | React components |

---

## Data Flow Patterns

### Pattern 1: Real-Time Price Updates

**Flow:** bags.fm WebSocket -> FastAPI Relay -> Browser WebSocket -> Zustand/React State

```
1. BagsWebSocketClient (Python) connects to wss://public-api-v2.bags.fm/ws
2. Subscribes to tokens: { "type": "subscribe", "channel": "price", "mint": "..." }
3. Receives price updates: { "price": 125.42, "volume_24h": 2.4M, ... }
4. FastAPI WebSocketManager broadcasts to all connected frontend clients
5. Frontend useWebSocket hook receives update
6. Component re-renders with new price
```

**Code Path (Existing):**
- `core/bags_websocket.py` - BagsWebSocketClient with auto-reconnect
- `web_demo/backend/app/services/websocket_manager.py` - WebSocketManager
- `web_demo/backend/app/routes/websocket.py` - /ws/prices/{token_address}

**Frontend Integration (New):**
```typescript
// hooks/useRealTimePrice.ts
import { useEffect, useState, useCallback } from 'react';

export function useRealTimePrice(tokenAddress: string) {
  const [price, setPrice] = useState<number | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(
      `${process.env.NEXT_PUBLIC_WS_URL}/ws/prices/${tokenAddress}`
    );

    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      // Reconnect with exponential backoff
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setPrice(data.price);
    };

    return () => ws.close();
  }, [tokenAddress]);

  return { price, connected };
}
```

### Pattern 2: Trade Execution (Buy)

**Flow:** UI Action -> TanStack Mutation -> FastAPI -> Flask -> bags.fm -> Blockchain

```
1. User clicks "Buy" with token address, amount, TP/SL
2. TanStack Query mutation sends POST to /api/v1/trade/buy
3. FastAPI validates request, proxies to Flask /api/trade/buy
4. Flask execute_buy_with_tpsl() calls bags.fm swap API
5. bags.fm submits transaction to Solana
6. Response bubbles back with tx_hash
7. TanStack Query invalidates positions query
8. UI updates with new position
```

**Code Path (Existing):**
- `web/trading_web.py:180` - Flask /api/trade/buy endpoint
- `tg_bot/handlers/demo/demo_trading.py` - execute_buy_with_tpsl()
- `core/bags_api.py` - BagsAPI.swap()

**Why Proxy Through FastAPI Instead of Direct Flask:**
1. **Consistent Auth** - FastAPI handles JWT/session validation
2. **Rate Limiting** - slowapi already configured
3. **Metrics** - Centralized request tracking
4. **CORS** - Single origin configuration
5. **Future-Proof** - Can swap Flask backend without frontend changes

### Pattern 3: Portfolio Polling with WebSocket Invalidation

**Flow:** TanStack Query polls /positions -> WebSocket notifies of changes -> Invalidate & Refetch

```
1. TanStack Query fetches /api/positions with 5s staleTime
2. WebSocket receives position update (trade executed elsewhere)
3. WebSocket handler calls queryClient.invalidateQueries(['positions'])
4. TanStack Query refetches fresh data
5. UI updates automatically
```

**This is the recommended TanStack + WebSocket pattern** per [TkDodo's blog](https://tkdodo.eu/blog/using-web-sockets-with-react-query):
- WebSocket sends "event types" not full data
- TanStack Query handles actual data fetching and caching
- Avoids duplicate state management

### Pattern 4: AI Sentiment Analysis

**Flow:** User requests sentiment -> Frontend -> FastAPI -> Grok API -> Cache & Return

```
1. User clicks "Analyze" on token
2. TanStack Query mutation POST /api/v1/ai/sentiment { token_address }
3. FastAPI SentimentService checks Redis cache (5-min TTL)
4. If miss: calls Grok API with token data
5. Stores result in cache
6. Returns sentiment to frontend
```

**Code Path (Existing):**
- `web_demo/backend/app/routes/ai.py` - /ai/sentiment endpoint
- `web_demo/backend/app/services/sentiment_service.py` - SentimentService
- `tg_bot/handlers/demo/demo_sentiment.py` - get_ai_sentiment_for_token()

---

## State Management Architecture

### Server State (TanStack Query)

Use TanStack Query for all data that comes from the server:

| Query Key | Endpoint | Stale Time | Notes |
|-----------|----------|------------|-------|
| `['status']` | GET /api/status | 10s | Wallet balance, position count |
| `['positions']` | GET /api/positions | 5s | All open positions with P&L |
| `['position', id]` | GET /api/positions/:id | 5s | Single position detail |
| `['sentiment', addr]` | POST /api/ai/sentiment | 5min | AI sentiment cache |
| `['trending']` | GET /api/trending | 30s | bags.fm trending tokens |
| `['regime']` | GET /api/market/regime | 1min | Market regime analysis |

**Mutations:**
```typescript
// Buy token
useMutation({
  mutationFn: (data: BuyRequest) => api.post('/trade/buy', data),
  onSuccess: () => {
    queryClient.invalidateQueries(['positions']);
    queryClient.invalidateQueries(['status']);
  }
});
```

### Client State (Zustand)

Use Zustand for UI-only state that doesn't need server persistence:

```typescript
// stores/uiStore.ts
interface UIStore {
  // Modal state
  buyModalOpen: boolean;
  sellModalOpen: boolean;
  selectedPosition: string | null;

  // Preferences (persisted to localStorage)
  theme: 'dark' | 'darker' | 'matrix';
  chartStyle: 'candles' | 'line' | 'area';

  // WebSocket connection state
  wsConnected: boolean;
  lastPriceUpdate: Record<string, number>;

  // Actions
  openBuyModal: (tokenAddress?: string) => void;
  closeBuyModal: () => void;
  setTheme: (theme: UIStore['theme']) => void;
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      buyModalOpen: false,
      // ... implementation
    }),
    { name: 'jarvis-ui' }
  )
);
```

### Real-Time Price State (Dedicated Store)

For high-frequency price updates, use a separate Zustand store optimized for performance:

```typescript
// stores/priceStore.ts
interface PriceStore {
  prices: Record<string, {
    price: number;
    priceUsd: number;
    change24h: number;
    lastUpdate: number;
  }>;

  updatePrice: (mint: string, data: PriceData) => void;
  getPrice: (mint: string) => PriceData | null;
}

export const usePriceStore = create<PriceStore>((set, get) => ({
  prices: {},

  updatePrice: (mint, data) => set((state) => ({
    prices: {
      ...state.prices,
      [mint]: { ...data, lastUpdate: Date.now() }
    }
  })),

  getPrice: (mint) => get().prices[mint] || null,
}));
```

---

## Integration Points with Existing Backend

### 1. Flask Backend (web/trading_web.py)

**Current Endpoints (PORT 5001):**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/status | GET | Wallet balance, position count, market regime |
| /api/positions | GET | All positions with P&L |
| /api/token/sentiment | POST | AI sentiment for token |
| /api/trade/buy | POST | Execute buy with TP/SL |
| /api/trade/sell | POST | Execute sell |
| /api/market/regime | GET | Market regime analysis |

**VERIFIED:** These endpoints exist and are functional. The new dashboard should proxy through FastAPI for consistency.

### 2. FastAPI Backend (web_demo/backend/)

**Current Endpoints (PORT 8000):**
| Endpoint | Method | Purpose |
|----------|--------|---------|
| /api/v1/ws/prices/{token} | WS | Real-time price feed |
| /api/v1/ws/portfolio | WS | Portfolio updates |
| /api/v1/bags/swap | POST | Direct bags.fm swap |
| /api/v1/ai/sentiment | POST | Grok sentiment analysis |

**VERIFIED:** WebSocket infrastructure is production-ready in `websocket_manager.py`.

### 3. bags.fm WebSocket (core/bags_websocket.py)

**Message Types:**
```python
# Subscribe to price updates
{ "type": "subscribe", "channel": "price", "mint": "TOKEN_MINT" }

# Subscribe to graduations
{ "type": "subscribe", "channel": "graduations" }

# Price update received
{
  "type": "price",
  "mint": "...",
  "price": 0.00123,
  "price_usd": 0.15,
  "volume_24h": 1234567
}

# Graduation event received
{
  "type": "graduation",
  "mint": "...",
  "raydium_pool": "...",
  "bonding_curve_complete": true
}
```

**VERIFIED:** `BagsWebSocketClient` handles auto-reconnect, subscription management, and callbacks.

---

## Build Order Recommendation

Based on dependencies and complexity:

### Phase 1: Foundation (Week 1)
1. **WebSocket Relay** - Connect FastAPI to bags.fm WebSocket
2. **TanStack Query Setup** - Provider, QueryClient, base hooks
3. **Zustand Stores** - UI state, price state
4. **REST API Proxy** - FastAPI routes to Flask endpoints

### Phase 2: Core Trading (Week 2)
1. **Portfolio Dashboard** - Status, balance, positions count
2. **Position List** - All positions with real-time P&L
3. **Buy Flow** - Token input, amounts, TP/SL, execute
4. **Sell Flow** - Position selection, partial sells, execute

### Phase 3: Real-Time Integration (Week 3)
1. **Price Subscriptions** - Subscribe to position tokens
2. **Live P&L Updates** - Calculate from price updates
3. **Connection Status** - Visual indicator, reconnect handling
4. **Portfolio WebSocket** - Total value updates

### Phase 4: WebGL Visualization (Week 3-4)
1. **Price Chart** - Three.js/React Three Fiber integration
2. **Portfolio Visualization** - 3D representation
3. **Animations** - Smooth transitions, effects
4. **Performance Optimization** - Memo, throttle, RAF

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Duplicate Data Sources

**BAD:**
```typescript
// Fetching from both Flask AND FastAPI
const { data: status1 } = useQuery(['status'], () => fetch('http://localhost:5001/api/status'));
const { data: status2 } = useQuery(['status2'], () => fetch('http://localhost:8000/api/v1/status'));
```

**GOOD:**
```typescript
// Single source of truth via FastAPI proxy
const { data: status } = useQuery(['status'], () => api.get('/status'));
```

### Anti-Pattern 2: WebSocket + REST Race Conditions

**BAD:**
```typescript
// WebSocket updates local state, REST query fetches stale data
ws.onmessage = (e) => setPrice(e.price);  // Updates to 125
useQuery(['price'], fetchPrice);           // Returns 120 (stale)
```

**GOOD:**
```typescript
// WebSocket invalidates, TanStack Query fetches fresh
ws.onmessage = (e) => {
  if (e.type === 'price_changed') {
    queryClient.invalidateQueries(['price', e.mint]);
  }
};
```

### Anti-Pattern 3: Heavy State in Components

**BAD:**
```typescript
function TradingDashboard() {
  const [prices, setPrices] = useState({});
  const [positions, setPositions] = useState([]);
  const [ws, setWs] = useState(null);
  // ... 200 lines of state management
}
```

**GOOD:**
```typescript
function TradingDashboard() {
  const prices = usePriceStore(state => state.prices);
  const { data: positions } = usePositions();
  // Component focuses on rendering
}
```

### Anti-Pattern 4: Blocking UI with Blockchain Transactions

**BAD:**
```typescript
const handleBuy = async () => {
  setLoading(true);
  await buyToken(data);  // Blocks UI for 30+ seconds
  setLoading(false);
};
```

**GOOD:**
```typescript
const handleBuy = async () => {
  // Optimistic UI update
  queryClient.setQueryData(['positions'], old => [...old, tempPosition]);

  // Submit transaction in background
  mutation.mutate(data, {
    onError: () => {
      // Rollback on failure
      queryClient.invalidateQueries(['positions']);
    }
  });

  // Close modal immediately
  closeModal();
};
```

---

## Scalability Considerations

| Concern | At 1 User | At 100 Users | At 1000 Users |
|---------|-----------|--------------|---------------|
| WebSocket Connections | Single connection | Connection pooling | Redis pub/sub for horizontal scaling |
| Price Updates | Direct broadcast | Batch updates (100ms) | Message queue (Redis streams) |
| REST API | Direct Flask calls | FastAPI caching | CDN + edge caching |
| Database | SQLite | PostgreSQL | PostgreSQL with read replicas |
| AI Sentiment | Direct Grok calls | 5-min cache | Request queuing + batch processing |

---

## Technology Decisions (Summary)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Real-time Protocol | WebSocket (native) | Full-duplex, low latency, existing bags.fm support |
| Client State | Zustand | Minimal boilerplate, good with frequent updates |
| Server State | TanStack Query v5 | Best-in-class caching, background sync, WS integration pattern |
| WebSocket Library | Native WebSocket | Next.js compatibility, no extra dependencies |
| API Layer | FastAPI proxy | Consistent auth, rate limiting, metrics |
| Price Feed | bags.fm WebSocket | Already integrated in core/bags_websocket.py |

---

## Sources

- [TkDodo: Using WebSockets with React Query](https://tkdodo.eu/blog/using-web-sockets-with-react-query) - Official TanStack Query WebSocket pattern
- [LogRocket: TanStack Query and WebSockets](https://blog.logrocket.com/tanstack-query-websockets-real-time-react-data-fetching/) - Practical implementation guide
- [Socket.IO: How to use with Next.js](https://socket.io/how-to/use-with-nextjs) - Official Socket.IO + Next.js guide (considered but native WS preferred)
- [Medium: Zustand vs Redux Toolkit](https://medium.com/@msmt0452/zustand-vs-redux-toolkit-the-complete-guide-to-state-management-in-react-4dce420741b4) - State management comparison
- Existing Jarvis codebase analysis (VERIFIED):
  - `core/bags_websocket.py` - BagsWebSocketClient implementation
  - `web_demo/backend/app/services/websocket_manager.py` - WebSocketManager
  - `web/trading_web.py` - Flask trading endpoints
  - `jarvis-web-terminal/src/` - Existing Next.js patterns
