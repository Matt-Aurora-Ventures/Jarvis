# JARVIS Performance Playbook

> **Version**: 1.0.0 | **Last Updated**: 2026-01-08

A practical guide to maintaining dashboard performance and diagnosing issues.

---

## 1. Performance Budgets

| Metric | Target | Critical | How to Measure |
|--------|--------|----------|----------------|
| First Contentful Paint | <1.5s | <3s | Lighthouse |
| Time to Interactive | <2.5s | <5s | Lighthouse |
| Chart Frame Rate | ≥30 FPS | ≥15 FPS | DevTools Performance |
| API Response Time | <500ms | <2000ms | Network tab |
| Bundle Size (gzip) | <150KB | <500KB | `npm run build` |
| Memory Usage | <100MB | <300MB | DevTools Memory |

---

## 2. Update Batching Strategy

### Why Batch?

Without batching:
```
API Response 1 → setState() → Re-render
API Response 2 → setState() → Re-render  (10ms later)
API Response 3 → setState() → Re-render  (20ms later)
```

With batching (100ms window):
```
API Response 1 → Queue
API Response 2 → Queue
API Response 3 → Queue
                 └→ Single setState() → Single Re-render
```

### Implementation Pattern

```javascript
// Performance: Batch updates to prevent UI thrashing
const BATCH_INTERVAL = 100 // ms

const pendingUpdate = useRef(null)
const batchTimeoutRef = useRef(null)

const scheduleUpdate = useCallback((newData) => {
  pendingUpdate.current = newData

  if (!batchTimeoutRef.current) {
    batchTimeoutRef.current = setTimeout(() => {
      if (pendingUpdate.current) {
        setData(pendingUpdate.current)
      }
      batchTimeoutRef.current = null
      pendingUpdate.current = null
    }, BATCH_INTERVAL)
  }
}, [])
```

### When to Use Batching

| Component | Batch? | Interval | Reason |
|-----------|--------|----------|--------|
| TradingChart | Yes | 100ms | OHLCV updates flood in |
| PriceDisplay | Yes | 100ms | Price ticks are rapid |
| PositionCard | No | - | Updates are infrequent |
| StatsGrid | No | - | Updates are infrequent |

---

## 3. Profiling Instructions

### 3.1 React DevTools Profiler

1. Install React DevTools browser extension
2. Open DevTools → Profiler tab
3. Click "Record" → Interact with UI → Click "Stop"
4. Look for:
   - Components with high "Self Time"
   - Unexpected re-renders (yellow/orange bars)
   - Long render chains

### 3.2 Chrome Performance Tab

1. Open DevTools → Performance tab
2. Click Record → Scroll/interact for 5-10 seconds → Stop
3. Analyze:
   - **Main Thread**: Look for long tasks (>50ms)
   - **Frames**: Should be ~60fps, red = dropped frames
   - **Network**: Waterfall for API calls

### 3.3 Memory Profiling

1. DevTools → Memory tab
2. Take heap snapshot
3. Filter by "Detached" to find memory leaks
4. Compare snapshots before/after navigation

---

## 4. Common Performance Issues

### 4.1 Chart Thrashing

**Symptom**: Chart flickers or updates too frequently.

**Diagnosis**:
```javascript
console.log('Chart update triggered') // Add to scheduleChartUpdate
// If this logs more than once per 100ms, batching isn't working
```

**Fix**: Ensure batching is enabled and `BATCH_INTERVAL >= 100`.

### 4.2 Memory Leak in Price History

**Symptom**: Memory grows over time.

**Diagnosis**:
```javascript
console.log('Price history length:', priceHistory.length)
// If this exceeds maxHistory, slicing isn't working
```

**Fix**: Ensure `priceHistory.slice(-maxHistory)` is applied.

### 4.3 Duplicate API Calls

**Symptom**: Network tab shows repeated identical requests.

**Diagnosis**: Check `lastFetchRef.current` deduplication:
```javascript
const fetchPrice = async () => {
  const now = Date.now()
  console.log('Fetch interval:', now - lastFetchRef.current)
  if (now - lastFetchRef.current < 500) {
    console.log('DEDUPE: Skipping fetch')
    return
  }
  // ...
}
```

**Fix**: Add deduplication guard.

### 4.4 Excessive Re-renders

**Symptom**: Components render without visible changes.

**Diagnosis**: Add render counter:
```javascript
const renderCount = useRef(0)
useEffect(() => {
  console.log(`${ComponentName} rendered ${++renderCount.current} times`)
})
```

**Fix**: Memoize with `React.memo` or `useMemo`.

---

## 5. Optimization Checklist

### Before Shipping

- [ ] Run `npm run build` and check bundle size
- [ ] Profile with React DevTools Profiler (no unnecessary renders)
- [ ] Test on slow 3G network (DevTools → Network → Slow 3G)
- [ ] Memory snapshot after 5 min of use (no growth)
- [ ] Test chart with 500+ candles (smooth scrolling)

### Per-Component

| Component | Check |
|-----------|-------|
| TradingChart | Batch interval = 100ms |
| Lists | Virtualized if >50 items |
| Images | Lazy loaded |
| Modals | Code split (lazy import) |
| Forms | Debounced inputs |

---

## 6. API Best Practices

### 6.1 Polling vs Real-time

| Data Type | Method | Interval | Reason |
|-----------|--------|----------|--------|
| Wallet Balance | Polling | 30s | Low frequency |
| Position P&L | Polling | 5s | Medium frequency |
| Price | Polling + Batch | 2s + 100ms | High frequency |
| Chat | On-demand | - | User-triggered |

### 6.2 Request Timeout

All API calls use 10s timeout:
```javascript
const controller = new AbortController()
const timeoutId = setTimeout(() => controller.abort(), 10000)
```

Show loading state after 500ms of waiting.

### 6.3 Error Retry Strategy

```javascript
// lib/api.js enhancement suggestion
const fetchWithRetry = async (url, options, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      return await fetch(url, options)
    } catch (err) {
      if (i === retries - 1) throw err
      await new Promise(r => setTimeout(r, 1000 * (i + 1))) // Exponential backoff
    }
  }
}
```

---

## 7. Chart Performance

### 7.1 lightweight-charts Tips

| Setting | Recommendation |
|---------|----------------|
| `handleScroll.vertTouchDrag` | `false` (mobile perf) |
| Max visible candles | 500 |
| Update method | `setData()` not `update()` for full refresh |
| Resize handling | Debounce `applyOptions({ width })` |

### 7.2 Candle Data Format

Optimal format for lightweight-charts:
```javascript
{
  time: 1704672000,  // Unix timestamp (seconds)
  open: 100.5,
  high: 102.0,
  low: 99.0,
  close: 101.5,
}
```

Avoid: ISO strings, millisecond timestamps, extra fields.

---

## 8. Bundle Optimization

### 8.1 Code Splitting

```javascript
// Lazy load heavy routes
const Trading = React.lazy(() => import('./pages/TradingNew'))

// In Router
<Route path="/trading" element={
  <Suspense fallback={<LoadingSpinner />}>
    <Trading />
  </Suspense>
} />
```

### 8.2 Tree Shaking

Import only what you need:
```javascript
// Bad - imports entire library
import * as LucideIcons from 'lucide-react'

// Good - tree-shakable
import { TrendingUp, Shield, Search } from 'lucide-react'
```

### 8.3 Analyze Bundle

```bash
npm run build -- --report
# Or use vite-bundle-visualizer
```

---

## 9. Web Worker Offloading

For heavy computations (not yet implemented):

```javascript
// workers/indicatorWorker.js
self.onmessage = ({ data: { candles, indicator } }) => {
  const result = calculateIndicator(candles, indicator)
  self.postMessage(result)
}

// Usage in component
const worker = new Worker(new URL('./workers/indicatorWorker.js', import.meta.url))
worker.postMessage({ candles, indicator: 'SMA' })
worker.onmessage = ({ data }) => setIndicatorData(data)
```

Use cases:
- Moving averages on 1000+ candles
- RSI/MACD calculations
- Large data transformations

---

## 10. Quick Fixes

### Slow Chart?
1. Reduce candle limit from 100 to 50
2. Increase batch interval from 100ms to 200ms
3. Disable volume overlay

### Memory Growing?
1. Check `priceHistory` slice
2. Verify cleanup in `useEffect` returns
3. Look for event listener leaks

### API Hammering Backend?
1. Increase polling intervals
2. Enable request deduplication
3. Add response caching

---

*"Premature optimization is the root of all evil, but mature optimization is the root of all fast."*
