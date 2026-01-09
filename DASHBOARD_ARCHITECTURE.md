# JARVIS Dashboard Architecture

> **Version**: 3.2.0 | **Last Updated**: 2026-01-08

This document describes the frontend dashboard architecture, data flows, and performance optimizations.

---

## 1. Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | React | 18.2.0 |
| State | Zustand | 4.4.7 |
| Build | Vite | 5.0.4 |
| Styling | TailwindCSS | 3.3.6 |
| Charts | lightweight-charts | 5.1.0 |
| Icons | Lucide React | 0.294.0 |
| Desktop | Electron | 28.0.0 |

---

## 2. Route Architecture

```
/                 → DashboardNew.jsx    (System overview, stats, activity)
/trading          → TradingNew.jsx      (Full-screen trading command center)
/chat             → ChatNew.jsx         (Jarvis conversation interface)
/voice            → VoiceControl.jsx    (Voice interaction)
/research         → Research.jsx        (Research tools)
/settings         → Settings.jsx        (Configuration)
/roadmap          → Roadmap.jsx         (Development roadmap)
```

### Layout Strategy
- **Standard routes** (`/`, `/chat`, `/voice`, etc.) use `Layout.jsx` with global navigation
- **Trading route** (`/trading`) is full-screen with its own `TopNav` + `Sidebar`

---

## 3. Component Hierarchy

```
App.jsx
├── Layout.jsx                     # Global navigation wrapper
│   ├── TopNav (global)
│   └── <Outlet>
│       ├── DashboardNew.jsx       # Main dashboard
│       │   ├── StatCard[]
│       │   ├── ActivityRow
│       │   ├── StatusItem
│       │   └── SuggestionCard[]
│       ├── ChatNew.jsx            # Chat interface
│       │   ├── WelcomeState
│       │   ├── MessageBubble[]
│       │   ├── TypingIndicator
│       │   └── ChatInput
│       └── [other pages]
│
└── TradingNew.jsx                 # Full-screen trading (no Layout)
    ├── TopNav (trading-specific)
    ├── Sidebar
    ├── StatsGrid
    ├── TradingChart
    ├── OrderPanel
    ├── PositionCard
    ├── TokenScanner
    └── FloatingChat
```

---

## 4. Data Flow Architecture

### 4.1 API Communication

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│   React Hooks    │ ──▶  │    lib/api.js    │ ──▶  │  Backend (8765)  │
│  (useWallet,     │      │   jarvisApi      │      │  api_server.py   │
│   usePosition)   │      │   fetch wrapper  │      │                  │
└──────────────────┘      └──────────────────┘      └──────────────────┘
```

### 4.2 API Endpoints

| Endpoint | Method | Description | Hook |
|----------|--------|-------------|------|
| `/api/wallet/status` | GET | Wallet balance, SOL price | `useWallet` |
| `/api/sniper/status` | GET | Sniper bot status | `useSniper` |
| `/api/position/active` | GET | Current position P&L | `usePosition` |
| `/api/jarvis/status` | GET | Jarvis daemon status | Manual |
| `/api/jarvis/chat` | POST | Send message to Jarvis | `jarvisApi.chat` |
| `/api/chart/{mint}` | GET | OHLCV candle data | `TradingChart` |
| `/api/tools/token/{mint}` | GET | Token info | `TokenScanner` |
| `/api/tools/rugcheck/{mint}` | GET | Risk assessment | `TokenScanner` |
| `/api/stats` | GET | System statistics | `useApi` |
| `/api/health` | GET | System health metrics | `useApi` |

### 4.3 Polling Intervals

Defined in `lib/constants.js`:

```javascript
POLLING_INTERVALS = {
  WALLET: 30000,      // 30 seconds
  POSITION: 5000,     // 5 seconds
  SNIPER: 10000,      // 10 seconds
  PRICE: 2000,        // 2 seconds
  STATS: 60000,       // 1 minute
}
```

---

## 5. State Management

### 5.1 Zustand Store (`stores/jarvisStore.js`)

```javascript
{
  // Voice state
  isListening: boolean,
  voiceEnabled: boolean,

  // Connection state
  isConnected: boolean,

  // Conversation
  messages: Array<{ id, timestamp, text, role }>,
  suggestions: Array<{ id, timestamp, text }>,

  // Activity
  currentActivity: { app, window, status },

  // Configuration
  apiKeys: { gemini, groq, anthropic, openai, trello, github },

  // Status
  status: { daemon, voice, monitoring },
}
```

### 5.2 Hook-Based State

| Hook | State | Auto-Refresh |
|------|-------|--------------|
| `useWallet` | `wallet`, `loading`, `error` | 30s |
| `usePosition` | `position`, `loading`, `error` | 5s |
| `useSniper` | `sniper`, `loading`, `error` | 10s |
| `useRealtimePrice` | `price`, `priceHistory` | 2s (batched) |
| `useApi` | Generic data fetching | Configurable |

---

## 6. Performance Architecture

### 6.1 Update Batching

**Problem**: Frequent API responses cause excessive re-renders.

**Solution**: Batch state updates before committing to React.

```javascript
// TradingChart.jsx - Batched chart updates
const BATCH_INTERVAL = 100 // ms

const scheduleChartUpdate = useCallback((candles, volumes, priceData) => {
  pendingChartUpdate.current = { candles, volumes, priceData }

  if (!batchTimeoutRef.current) {
    batchTimeoutRef.current = setTimeout(() => {
      // Commit all pending updates at once
      candleSeriesRef.current.setData(pending.candles)
      volumeSeriesRef.current.setData(pending.volumes)
      setLastPrice(pending.priceData.lastPrice)
      // ...
    }, BATCH_INTERVAL)
  }
}, [])
```

### 6.2 Request Deduplication

**Problem**: Rapid user actions trigger duplicate API calls.

**Solution**: Track last fetch timestamp and skip if too recent.

```javascript
// useRealtimePrice.js
const lastFetchRef = useRef(0)

const fetchPrice = useCallback(async () => {
  const now = Date.now()
  if (now - lastFetchRef.current < 500) return // Dedupe
  lastFetchRef.current = now
  // ... fetch
}, [])
```

### 6.3 Memoization Strategy

| Component | Memoization | Reason |
|-----------|-------------|--------|
| `StatCard` | `React.memo` | Props rarely change |
| `MessageBubble` | `React.memo` | Static after render |
| `chart.setData()` | Batched | Prevent flash updates |

### 6.4 Performance Budgets

| Metric | Target | Action if Exceeded |
|--------|--------|-------------------|
| Chart FPS | ≥30 | Reduce update frequency |
| API Latency | <2000ms | Show loading state |
| Bundle Size | <500KB | Code split routes |
| First Paint | <1.5s | Skeleton loaders |

---

## 7. Chart Architecture (lightweight-charts)

### 7.1 Chart Configuration

```javascript
const chart = createChart(container, {
  layout: {
    background: { type: ColorType.Solid, color: '#FFFFFF' },
    textColor: '#6B7280',
  },
  grid: {
    vertLines: { color: '#F3F4F6' },
    horzLines: { color: '#F3F4F6' },
  },
  crosshair: {
    mode: CrosshairMode.Normal,
    // Indigo crosshair for brand consistency
  },
  timeScale: {
    timeVisible: true,
    secondsVisible: false,
  },
})
```

### 7.2 Data Sources

| Source | API | Priority | Use Case |
|--------|-----|----------|----------|
| BirdEye | `/api/chart/{mint}` | Primary | OHLCV data |
| DexScreener | Fallback | Secondary | When BirdEye fails |
| Synthetic | Generated | Tertiary | No data available |

### 7.3 Timeframes

```javascript
TIMEFRAMES = ['1m', '5m', '15m', '1H', '4H', '1D']
```

---

## 8. Error Handling

### 8.1 API Error Flow

```
fetch() fails
    ↓
ApiError thrown (with status, data)
    ↓
Hook catches, sets error state
    ↓
Component renders ErrorState or fallback UI
    ↓
User can retry via refresh()
```

### 8.2 ErrorBoundary

```jsx
<ErrorBoundary fallback={<ErrorState />}>
  <TradingChart />
</ErrorBoundary>
```

---

## 9. Styling System

### 9.1 CSS Variables (V2 White Knight)

```css
:root {
  /* Colors */
  --primary: #111827;
  --success: #10B981;
  --warning: #F59E0B;
  --danger: #EF4444;
  --accent: #FF385C;

  /* Backgrounds */
  --bg-primary: #FFFFFF;
  --bg-secondary: #FFFFFF;
  --bg-tertiary: #FAFAFA;

  /* Text */
  --text-primary: #111827;
  --text-secondary: #717171;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
}
```

### 9.2 Component Classes

| Class | Purpose |
|-------|---------|
| `.card` | Container with shadow |
| `.btn`, `.btn-primary` | Buttons |
| `.input` | Form inputs |
| `.badge`, `.badge-success` | Status badges |
| `.stat-change.positive` | Green price change |

---

## 10. Development Workflow

### 10.1 Running the Frontend

```bash
cd frontend
npm install
npm run dev          # Start Vite dev server (port 5173)
npm run electron:dev # Start with Electron
```

### 10.2 Backend Requirement

The frontend proxies `/api/*` to `localhost:8765`. Start the backend:

```bash
python core/api_server.py
```

### 10.3 Adding New Pages

1. Create `src/pages/MyPage.jsx`
2. Import in `App.jsx`
3. Add route: `<Route path="mypage" element={<MyPage />} />`
4. Add nav link in `Layout.jsx` if needed

---

## 11. Trade-offs and Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| Polling over WebSocket | Simpler implementation, backend support | Higher latency (~2s) |
| Zustand over Redux | Minimal boilerplate | Less middleware ecosystem |
| lightweight-charts | Small bundle (~45KB) | Fewer features than TradingView |
| Full-screen trading | Pro UX for traders | Different nav than other pages |
| CSS variables | Easy theming | No dynamic runtime themes |

---

## 12. Future Improvements

### P0 - Critical
- [ ] WebSocket support for real-time prices
- [ ] Virtual scrolling for large token lists

### P1 - High Value
- [ ] Dark mode toggle
- [ ] Mobile responsive trading view
- [ ] Persistent filter/sort preferences

### P2 - Polish
- [ ] GSAP page transitions
- [ ] Keyboard shortcuts (trading hotkeys)
- [ ] Accessibility audit (ARIA labels)

---

*This document is the canonical source of truth for dashboard architecture.*
