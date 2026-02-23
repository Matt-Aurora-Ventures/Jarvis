# TradingView Screener API (tvscreener) Research

**Date:** 2026-02-09
**Repository:** https://github.com/deepentropy/tvscreener
**Version:** 0.2.0 (latest)
**License:** MIT
**Language:** Python (pip install tvscreener)

---

## 1. API Capabilities Summary

### What It Is

tvscreener is an unofficial Python library that wraps TradingView's publicly available
screener HTTP endpoints. It sends POST requests to `https://scanner.tradingview.com/{market}/scan`
with JSON payloads and returns data as Pandas DataFrames.

**No API key required. No authentication. No TradingView account needed.**

### Six Screener Types

| Screener | Class | URL Path | Use Case |
|----------|-------|----------|----------|
| Stock | `StockScreener` | `/global/scan` | Our primary target -- US equities |
| Crypto | `CryptoScreener` | `/crypto/scan` | Could complement on-chain data |
| Forex | `ForexScreener` | `/forex/scan` | Currency pair data |
| Bond | `BondScreener` | `/bond/scan` | Government/corporate bonds |
| Futures | `FuturesScreener` | `/futures/scan` | Futures contracts |
| Coin | `CoinScreener` | `/coin/scan` | CEX/DEX coins |

### Data Volume

- **13,000+ total fields** across all screener types
- **~450+ fields** for stocks alone (StockField enum)
- Fields include price, volume, fundamentals, technical indicators, candlestick patterns, pivot points, pre/post market data, and financial scores
- Default response: 150 rows per query (configurable via `set_range()`)

### Data Freshness

- Data reflects TradingView's screener data -- typically **near real-time** during market hours (slight delay, not tick-by-tick)
- Pre-market and post-market data available as dedicated fields
- Streaming mode available: `ss.stream(interval=10)` polls at configurable intervals (minimum 1 second)
- Technical indicators computed by TradingView servers, not locally

---

## 2. Technical Indicators Available

### Oscillators (all support time intervals)

| Indicator | StockField Enum | API Field |
|-----------|-----------------|-----------|
| RSI (14) | `RELATIVE_STRENGTH_INDEX_14` | `RSI` |
| RSI (7) | `RELATIVE_STRENGTH_INDEX_7` | `RSI7` |
| MACD Level (12,26) | `MACD_LEVEL_12_26` | `MACD.macd` |
| MACD Signal (12,26) | `MACD_SIGNAL_12_26` | `MACD.signal` |
| Stochastic %K (14,3,3) | `STOCHASTIC_PERCENTK_14_3_3` | `Stoch.K` |
| Stochastic %D (14,3,3) | `STOCHASTIC_PERCENTD_14_3_3` | `Stoch.D` |
| Stochastic RSI Fast | `STOCHASTIC_RSI_FAST_3_3_14_14` | `Stoch.RSI.K` |
| Stochastic RSI Slow | `STOCHASTIC_RSI_SLOW_3_3_14_14` | `Stoch.RSI.D` |
| CCI (20) | `COMMODITY_CHANNEL_INDEX_20` | `CCI20` |
| ADX (14) | `AVERAGE_DIRECTIONAL_INDEX_14` | `ADX` |
| Awesome Oscillator | `AWESOME_OSCILLATOR` | `AO` |
| Momentum (10) | `MOMENTUM_10` | `Mom` |
| Williams %R (14) | `WILLIAMS_PERCENT_RANGE_14` | `W.R` |
| Bull Bear Power | `BULL_BEAR_POWER` | `BBPower` |
| Ultimate Oscillator | `ULTIMATE_OSCILLATOR_7_14_28` | `UO` |
| Aroon Down/Up | `AROON_DOWN_14` / `AROON_UP_14` | `Aroon.Down` / `Aroon.Up` |
| Rate of Change (9) | `RATE_OF_CHANGE_9` | `ROC` |
| Money Flow (14) | `MONEY_FLOW_14` | `MoneyFlow` |
| Chaikin Money Flow (20) | `CHAIKIN_MONEY_FLOW_20` | `ChaikinMoneyFlow` |

### Moving Averages (all support time intervals)

| Indicator | StockField Enum | API Field |
|-----------|-----------------|-----------|
| SMA 5/10/20/30/50/100/200 | `SIMPLE_MOVING_AVERAGE_*` | `SMA5` - `SMA200` |
| EMA 5/10/20/30/50/100/200 | `EXPONENTIAL_MOVING_AVERAGE_*` | `EMA5` - `EMA200` |
| Hull MA (9) | `HULL_MOVING_AVERAGE_9` | `HullMA9` |
| VWMA (20) | `VOLUME_WEIGHTED_MOVING_AVERAGE_20` | `VWMA` |
| VWAP | `VOLUME_WEIGHTED_AVERAGE_PRICE` | `VWAP` |
| Ichimoku Cloud | `ICHIMOKU_BASE_LINE_*` etc. | `Ichimoku.*` |

### Bollinger & Channel Bands

| Indicator | API Fields |
|-----------|-----------|
| Bollinger Bands (20) | `BB.lower`, `BB.upper` |
| Donchian Channels (20) | `DonchCh20.Lower`, `DonchCh20.Upper` |
| Keltner Channels (20) | `KltChnl.lower`, `KltChnl.upper` |
| Parabolic SAR | `P.SAR` |

### Aggregate Ratings

| Rating | StockField | API Field | Description |
|--------|-----------|-----------|-------------|
| Technical Rating | `TECHNICAL_RATING` | `Recommend.All` | Combined buy/sell signal (-1 to +1) |
| Oscillators Rating | `OSCILLATORS_RATING` | `Recommend.Other` | Oscillators-only rating |
| Moving Averages Rating | `MOVING_AVERAGES_RATING` | `Recommend.MA` | MA-only rating |

### Time Intervals

All technical fields with `interval=True` can be requested at:
`1, 5, 15, 30, 60, 120, 240, 1D, 1W, 1M` (minutes unless suffix)

```python
# Example: RSI at 1-hour interval
rsi_1h = StockField.RELATIVE_STRENGTH_INDEX_14.with_interval("60")
```

### Candlestick Patterns (30+ patterns detected)

3 Black Crows, 3 White Soldiers, Abandoned Baby (Bull/Bear), Doji variants,
Engulfing (Bull/Bear), Evening/Morning Star, Hammer, Hanging Man, Harami,
Inverted Hammer, Kicking, Marubozu, Shooting Star, Spinning Top, TriStar

---

## 3. Key Fields for xStocks Integration

### Price & Change (essential for every token)

| Field | API Name | Format |
|-------|----------|--------|
| Price (close) | `close` | currency |
| Change | `change_abs` | currency |
| Change % | `change` | percent |
| Open | `open` | currency |
| High | `high` | currency |
| Low | `low` | currency |
| Change from Open % | `change_from_open` | percent |
| Gap % | `gap` | percent |

### Pre-Market / Post-Market (market hours awareness)

| Field | API Name |
|-------|----------|
| Pre-market Open | `premarket_open` |
| Pre-market Close | `premarket_close` |
| Pre-market High/Low | `premarket_high` / `premarket_low` |
| Pre-market Change % | `premarket_change` |
| Pre-market Volume | `premarket_volume` |
| Pre-market Gap % | `premarket_gap` |
| Post-market Close | `postmarket_close` |
| Post-market Change % | `postmarket_change` |
| Post-market Volume | `postmarket_volume` |

### Volume & Relative Volume (volume confirmation)

| Field | API Name |
|-------|----------|
| Volume | `volume` |
| Avg Volume 10d | `average_volume_10d_calc` |
| Avg Volume 30d | `average_volume_30d_calc` |
| Avg Volume 60d | `average_volume_60d_calc` |
| Relative Volume | `relative_volume_10d_calc` |
| Relative Volume at Time | `relative_volume_intraday.5` |
| Volume * Price | `Value.Traded` |

### Performance (multi-timeframe momentum)

| Field | API Name |
|-------|----------|
| Weekly Performance | `Perf.W` |
| Monthly Performance | `Perf.1M` |
| 3-Month Performance | `Perf.3M` |
| 6-Month Performance | `Perf.6M` |
| YTD Performance | `Perf.YTD` |
| Yearly Performance | `Perf.Y` |
| All Time Performance | `Perf.All` |

### Volatility

| Field | API Name |
|-------|----------|
| Volatility (Daily) | `Volatility.D` |
| Volatility (Weekly) | `Volatility.W` |
| Volatility (Monthly) | `Volatility.M` |
| ATR (14) | `ATR` |
| ADR (14) | `ADR` |
| 1Y Beta | `beta_1_year` |

### Fundamentals (sector rotation signals)

| Field | API Name |
|-------|----------|
| Market Cap | `market_cap_basic` |
| Sector | `sector` |
| Industry | `industry` |
| P/E Ratio (TTM) | `price_earnings_ttm` |
| Dividend Yield | `dividends_yield` |
| EPS (TTM) | `earnings_per_share_diluted_ttm` |
| ROE (TTM) | `return_on_equity` |
| Upcoming Earnings Date | `earnings_release_next_date` |

### Financial Scores (advanced scoring)

| Field | API Name |
|-------|----------|
| Altman Z-Score | `altman_z_score_ttm` |
| Piotroski F-Score | `piotroski_f_score_ttm` |

---

## 4. Symbol Mapping: TradingView to xStocks

### Mapping Strategy

TradingView symbols follow the format `EXCHANGE:TICKER` (e.g., `NASDAQ:AAPL`).
Our xStocks tickers follow the format `{TICKER}x` (e.g., `AAPLx`).

**Strip the trailing `x` to get the real stock ticker:**

```typescript
// xStocks ticker -> TradingView symbol mapping
function xStocksToTVSymbol(xTicker: string): string {
  // Strip trailing 'x'
  const realTicker = xTicker.replace(/x$/, '');

  // Handle special cases
  const SPECIAL_MAPPINGS: Record<string, string> = {
    'BRK.B':  'BRK.B',    // Berkshire Hathaway B
    'V':      'V',         // Visa (ticker is 'Vx' which strips to 'V')
    'MA':     'MA',        // Mastercard
    'GME':    'GME',       // GameStop
  };

  return SPECIAL_MAPPINGS[realTicker] ?? realTicker;
}
```

### Full Token Registry Mapping

| xStocks Ticker | Real Ticker | TradingView Query | Category |
|---------------|-------------|-------------------|----------|
| AAPLx | AAPL | Stock search "AAPL" | XSTOCK |
| MSFTx | MSFT | Stock search "MSFT" | XSTOCK |
| GOOGLx | GOOGL | Stock search "GOOGL" | XSTOCK |
| NVDAx | NVDA | Stock search "NVDA" | XSTOCK |
| TSLAx | TSLA | Stock search "TSLA" | XSTOCK |
| AMZNx | AMZN | Stock search "AMZN" | XSTOCK |
| METAx | META | Stock search "META" | XSTOCK |
| SPYx | SPY | ETF search "SPY" | INDEX |
| QQQx | QQQ | ETF search "QQQ" | INDEX |
| TQQQx | TQQQ | ETF search "TQQQ" | INDEX |
| GLDx | GLD | ETF search "GLD" | COMMODITY |

**Important:** tvscreener uses the `search()` method on the screener, not the field.
To query specific symbols, use the screener's `search()` or filter by name:

```python
ss = StockScreener()
ss.search("AAPL")  # Filters to symbols matching "AAPL"
df = ss.get()
```

---

## 5. Rate Limits & Considerations

### What We Know

- **No official rate limits documented** -- this is an unofficial API
- Library enforces a **minimum 1-second interval** for streaming to be respectful
- Uses standard HTTP POST to `scanner.tradingview.com` with browser-like User-Agent
- **30-second timeout** per request (configurable)
- TradingView may throttle or block excessive requests (no documented thresholds)

### Recommendations

| Strategy | Implementation |
|----------|---------------|
| Cache aggressively | Cache responses for 30-60 seconds (data is delayed anyway) |
| Batch queries | Query all ~70 xStocks tickers in a single screener call (up to 150 rows default) |
| Off-peak refresh | Refresh every 60s during market hours, every 5min pre/post |
| Respect market hours | Skip polling entirely when markets are closed (weekends, holidays) |
| Fallback gracefully | If TV API fails, fall back to DexScreener-only scoring |

### Risk Assessment

- **Unofficial API**: TradingView could change endpoints at any time
- **No SLA**: No uptime guarantees
- **IP blocking**: Heavy usage could trigger rate limiting
- **Terms of Service**: Library disclaimer states users are responsible for TOS compliance

---

## 6. Integration Approach for Next.js App (TypeScript)

### Architecture: Python Microservice + API Route

Since tvscreener is Python-only (uses pandas + requests), we cannot import it directly
in our Next.js TypeScript app. We have two approaches:

#### Option A: Direct HTTP (Recommended for our use case)

Call TradingView's scan endpoint directly from a Next.js API route. The tvscreener
library is essentially a wrapper around a simple POST request. We can replicate the
core logic in TypeScript.

```
Next.js API Route (/api/tv-screener)
  -> POST https://scanner.tradingview.com/global/scan
  -> Parse JSON response
  -> Return to frontend
```

#### Option B: Python Sidecar

Run tvscreener as a small Flask/FastAPI service alongside our Next.js app.

```
Next.js App -> /api/tv-data -> Python service (port 5002) -> TradingView
```

**We recommend Option A** because:
1. No Python dependency in production
2. Lower latency (direct call)
3. Simpler deployment
4. The underlying API is just a POST endpoint

### API Route Implementation

```typescript
// jarvis-web-terminal/src/app/api/tv-screener/route.ts

import { NextRequest, NextResponse } from 'next/server';

// TradingView scan endpoint
const TV_SCAN_URL = 'https://scanner.tradingview.com/global/scan';

// Headers to mimic browser request
const TV_HEADERS = {
  'Content-Type': 'application/json',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
  'Origin': 'https://www.tradingview.com',
  'Referer': 'https://www.tradingview.com/',
};

// Map xStocks tickers to real tickers for TradingView query
const XSTOCKS_TO_REAL: Record<string, string> = {
  'AAPLx': 'AAPL', 'MSFTx': 'MSFT', 'GOOGLx': 'GOOGL', 'AMZNx': 'AMZN',
  'METAx': 'META', 'NVDAx': 'NVDA', 'TSLAx': 'TSLA', 'AVGOx': 'AVGO',
  'ORCLx': 'ORCL', 'CRMx': 'CRM', 'CSCOx': 'CSCO', 'ACNx': 'ACN',
  'INTCx': 'INTC', 'IBMx': 'IBM', 'MRVLx': 'MRVL', 'CRWDx': 'CRWD',
  'PLTRx': 'PLTR', 'NFLXx': 'NFLX', 'APPx': 'APP', 'GMEx': 'GME',
  'JPMx': 'JPM', 'GSx': 'GS', 'BACx': 'BAC', 'Vx': 'V', 'MAx': 'MA',
  'COINx': 'COIN', 'HOODx': 'HOOD', 'MSTRx': 'MSTR', 'BRK.Bx': 'BRK.B',
  'LLYx': 'LLY', 'UNHx': 'UNH', 'JNJx': 'JNJ', 'PFEx': 'PFE',
  'MRKx': 'MRK', 'ABBVx': 'ABBV', 'ABTx': 'ABT', 'TMOx': 'TMO',
  'DHRx': 'DHR', 'MDTx': 'MDT', 'AZNx': 'AZN', 'NVOx': 'NVO',
  'KOx': 'KO', 'PEPx': 'PEP', 'MCDx': 'MCD', 'WMTx': 'WMT',
  'SPYx': 'SPY', 'QQQx': 'QQQ', 'TQQQx': 'TQQQ', 'VTIx': 'VTI',
  'TBLLx': 'TBLL', 'GLDx': 'GLD',
};

// Fields we want from TradingView for scoring
const TV_COLUMNS = [
  'name',
  'description',
  'close',              // Price
  'change',             // Change %
  'change_abs',         // Change absolute
  'volume',             // Volume
  'average_volume_10d_calc',  // Avg volume 10d
  'relative_volume_10d_calc', // Relative volume
  'RSI',                // RSI (14)
  'MACD.macd',          // MACD level
  'MACD.signal',        // MACD signal
  'Recommend.All',      // Technical rating (-1 to +1)
  'Recommend.Other',    // Oscillators rating
  'Recommend.MA',       // Moving averages rating
  'SMA20',              // SMA 20
  'SMA50',              // SMA 50
  'SMA200',             // SMA 200
  'EMA20',              // EMA 20
  'EMA50',              // EMA 50
  'BB.lower',           // Bollinger lower
  'BB.upper',           // Bollinger upper
  'ATR',                // ATR (14)
  'Volatility.D',       // Daily volatility
  'high',               // Daily high
  'low',                // Daily low
  'open',               // Open
  'gap',                // Gap %
  'Perf.W',             // Weekly performance
  'Perf.1M',            // Monthly performance
  'Perf.3M',            // 3M performance
  'Perf.YTD',           // YTD performance
  'market_cap_basic',   // Market cap
  'sector',             // Sector
  'premarket_change',   // Pre-market change %
  'premarket_volume',   // Pre-market volume
  'postmarket_change',  // Post-market change %
  'Stoch.K',            // Stochastic %K
  'W.R',                // Williams %R
  'CCI20',              // CCI
  'ADX',                // ADX
  'Mom',                // Momentum
  'MoneyFlow',          // Money Flow
  'VWAP',               // VWAP
  'beta_1_year',        // Beta
  'update_mode',        // Update mode (for data freshness)
];

export interface TVStockData {
  symbol: string;
  name: string;
  price: number;
  changePercent: number;
  change: number;
  volume: number;
  avgVolume10d: number;
  relativeVolume: number;
  rsi14: number | null;
  macdLevel: number | null;
  macdSignal: number | null;
  technicalRating: number | null;   // -1 (strong sell) to +1 (strong buy)
  oscillatorsRating: number | null;
  maRating: number | null;
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  ema20: number | null;
  ema50: number | null;
  bollingerLower: number | null;
  bollingerUpper: number | null;
  atr: number | null;
  volatility: number | null;
  high: number;
  low: number;
  open: number;
  gap: number | null;
  perfWeek: number | null;
  perfMonth: number | null;
  perf3M: number | null;
  perfYTD: number | null;
  marketCap: number | null;
  sector: string | null;
  premarketChange: number | null;
  premarketVolume: number | null;
  postmarketChange: number | null;
  stochK: number | null;
  williamsR: number | null;
  cci: number | null;
  adx: number | null;
  momentum: number | null;
  moneyFlow: number | null;
  vwap: number | null;
  beta: number | null;
}

export async function GET(request: NextRequest) {
  try {
    // Get all real tickers to query
    const tickers = Object.values(XSTOCKS_TO_REAL);

    // Build TradingView scan payload
    const payload = {
      filter: [],
      options: { lang: 'en' },
      symbols: {
        query: { types: [] },
        tickers: tickers.map(t => `NASDAQ:${t}`).concat(
          tickers.map(t => `NYSE:${t}`),
          tickers.map(t => `AMEX:${t}`)
        ),
      },
      sort: { sortBy: 'market_cap_basic', sortOrder: 'desc' },
      range: [0, 200],
      columns: TV_COLUMNS,
      markets: ['america'],
    };

    const response = await fetch(TV_SCAN_URL, {
      method: 'POST',
      headers: TV_HEADERS,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000),
    });

    if (!response.ok) {
      throw new Error(`TradingView API error: ${response.status}`);
    }

    const data = await response.json();

    // Parse response: data.data is array of { s: "EXCHANGE:TICKER", d: [...values] }
    const results: Record<string, TVStockData> = {};

    for (const row of data.data ?? []) {
      const symbol = row.s as string;          // e.g., "NASDAQ:AAPL"
      const ticker = symbol.split(':')[1];     // e.g., "AAPL"
      const d = row.d as (number | string | null)[];

      // Map column index to values
      results[ticker] = {
        symbol,
        name: (d[0] as string) ?? ticker,
        price: (d[2] as number) ?? 0,
        changePercent: (d[3] as number) ?? 0,
        change: (d[4] as number) ?? 0,
        volume: (d[5] as number) ?? 0,
        avgVolume10d: (d[6] as number) ?? 0,
        relativeVolume: (d[7] as number) ?? 0,
        rsi14: d[8] as number | null,
        macdLevel: d[9] as number | null,
        macdSignal: d[10] as number | null,
        technicalRating: d[11] as number | null,
        oscillatorsRating: d[12] as number | null,
        maRating: d[13] as number | null,
        sma20: d[14] as number | null,
        sma50: d[15] as number | null,
        sma200: d[16] as number | null,
        ema20: d[17] as number | null,
        ema50: d[18] as number | null,
        bollingerLower: d[19] as number | null,
        bollingerUpper: d[20] as number | null,
        atr: d[21] as number | null,
        volatility: d[22] as number | null,
        high: (d[23] as number) ?? 0,
        low: (d[24] as number) ?? 0,
        open: (d[25] as number) ?? 0,
        gap: d[26] as number | null,
        perfWeek: d[27] as number | null,
        perfMonth: d[28] as number | null,
        perf3M: d[29] as number | null,
        perfYTD: d[30] as number | null,
        marketCap: d[31] as number | null,
        sector: d[32] as string | null,
        premarketChange: d[33] as number | null,
        premarketVolume: d[34] as number | null,
        postmarketChange: d[35] as number | null,
        stochK: d[36] as number | null,
        williamsR: d[37] as number | null,
        cci: d[38] as number | null,
        adx: d[39] as number | null,
        momentum: d[40] as number | null,
        moneyFlow: d[41] as number | null,
        vwap: d[42] as number | null,
        beta: d[43] as number | null,
      };
    }

    return NextResponse.json({
      success: true,
      count: Object.keys(results).length,
      data: results,
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
```

### Client-Side Hook

```typescript
// jarvis-web-terminal/src/hooks/useTVScreener.ts

import { useState, useEffect, useCallback, useRef } from 'react';
import type { TVStockData } from '@/app/api/tv-screener/route';

const REFRESH_INTERVAL = 60_000; // 60 seconds during market hours
const OFF_HOURS_INTERVAL = 300_000; // 5 minutes outside market hours

function isMarketHours(): boolean {
  const now = new Date();
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const hour = et.getHours();
  const minute = et.getMinutes();
  const day = et.getDay();

  // Weekend
  if (day === 0 || day === 6) return false;

  // Pre-market: 4:00 AM - 9:30 AM ET
  // Regular: 9:30 AM - 4:00 PM ET
  // After-hours: 4:00 PM - 8:00 PM ET
  const timeMinutes = hour * 60 + minute;
  return timeMinutes >= 240 && timeMinutes <= 1200; // 4 AM to 8 PM ET
}

export function useTVScreener() {
  const [data, setData] = useState<Record<string, TVStockData>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch('/api/tv-screener');
      const json = await res.json();
      if (json.success) {
        setData(json.data);
        setLastUpdated(new Date(json.timestamp));
        setError(null);
      } else {
        setError(json.error);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();

    const tick = () => {
      const interval = isMarketHours() ? REFRESH_INTERVAL : OFF_HOURS_INTERVAL;
      intervalRef.current = setTimeout(() => {
        fetchData();
        tick();
      }, interval);
    };

    tick();
    return () => {
      if (intervalRef.current) clearTimeout(intervalRef.current);
    };
  }, [fetchData]);

  return { data, loading, error, lastUpdated, refetch: fetchData };
}
```

---

## 7. Scoring Enhancement for Tokenized Equities

### Current State (DexScreener only)

We currently score xStocks tokens using:
- On-chain price from DexScreener
- 24h volume from DexScreener
- FDV, liquidity from DexScreener

### Proposed Enhanced Scoring

With TradingView data, we can add four new scoring dimensions:

#### A. Momentum Score (0-100)

```typescript
function calcMomentumScore(tv: TVStockData): number {
  let score = 50; // neutral baseline

  // RSI component (30% weight)
  if (tv.rsi14 !== null) {
    if (tv.rsi14 > 70) score -= 15;       // Overbought = bearish
    else if (tv.rsi14 > 55) score += 10;   // Bullish momentum
    else if (tv.rsi14 < 30) score += 15;   // Oversold = potential reversal
    else if (tv.rsi14 < 45) score -= 5;    // Weak momentum
  }

  // MACD component (25% weight)
  if (tv.macdLevel !== null && tv.macdSignal !== null) {
    if (tv.macdLevel > tv.macdSignal) score += 12;  // Bullish crossover
    else score -= 8;
  }

  // TradingView Technical Rating (25% weight)
  if (tv.technicalRating !== null) {
    score += Math.round(tv.technicalRating * 15); // -15 to +15
  }

  // Trend (SMA alignment) (20% weight)
  if (tv.price && tv.sma20 && tv.sma50 && tv.sma200) {
    if (tv.price > tv.sma20 && tv.sma20 > tv.sma50 && tv.sma50 > tv.sma200) {
      score += 10; // Perfect uptrend
    } else if (tv.price < tv.sma20 && tv.sma20 < tv.sma50) {
      score -= 10; // Downtrend
    }
  }

  return Math.max(0, Math.min(100, score));
}
```

#### B. Volume Confirmation Score (0-100)

```typescript
function calcVolumeConfirmation(
  tv: TVStockData,
  dexVolume24h: number
): { score: number; volumeRatio: number } {
  let score = 50;

  // Relative volume vs 10-day average (TV data)
  if (tv.relativeVolume > 2.0) score += 20;      // Surge
  else if (tv.relativeVolume > 1.5) score += 10;  // Above average
  else if (tv.relativeVolume < 0.5) score -= 15;  // Low activity

  // Compare DexScreener tokenized volume to real stock volume
  const realDollarVolume = tv.volume * tv.price;
  const volumeRatio = realDollarVolume > 0
    ? dexVolume24h / realDollarVolume
    : 0;

  // If tokenized volume is >1% of real volume, that's very high
  if (volumeRatio > 0.01) score += 15;
  else if (volumeRatio > 0.001) score += 5;
  else if (volumeRatio < 0.0001) score -= 10; // Negligible tokenized interest

  return { score: Math.max(0, Math.min(100, score)), volumeRatio };
}
```

#### C. Market Hours Awareness

```typescript
type MarketPhase = 'PRE_MARKET' | 'REGULAR' | 'AFTER_HOURS' | 'CLOSED';

function getMarketPhase(): MarketPhase {
  const now = new Date();
  const et = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const hour = et.getHours();
  const minute = et.getMinutes();
  const day = et.getDay();
  const time = hour * 60 + minute;

  if (day === 0 || day === 6) return 'CLOSED';
  if (time >= 240 && time < 570) return 'PRE_MARKET';     // 4:00 - 9:30
  if (time >= 570 && time < 960) return 'REGULAR';          // 9:30 - 16:00
  if (time >= 960 && time < 1200) return 'AFTER_HOURS';     // 16:00 - 20:00
  return 'CLOSED';
}

function getRelevantPrice(tv: TVStockData): number {
  const phase = getMarketPhase();
  switch (phase) {
    case 'PRE_MARKET':
      return tv.premarketChange !== null ? tv.price * (1 + tv.premarketChange / 100) : tv.price;
    case 'AFTER_HOURS':
      return tv.postmarketChange !== null ? tv.price * (1 + tv.postmarketChange / 100) : tv.price;
    default:
      return tv.price;
  }
}
```

#### D. Sector Rotation Score

```typescript
// Compare individual stock momentum vs sector average
function calcSectorRotationScore(
  tv: TVStockData,
  sectorAvgPerf: Record<string, number>
): number {
  if (!tv.sector || !tv.perfMonth) return 50;

  const sectorAvg = sectorAvgPerf[tv.sector] ?? 0;
  const outperformance = tv.perfMonth - sectorAvg;

  // Outperforming sector = higher score
  if (outperformance > 5) return 80;
  if (outperformance > 2) return 65;
  if (outperformance > 0) return 55;
  if (outperformance > -2) return 45;
  if (outperformance > -5) return 35;
  return 20;
}
```

### Combined Enhanced Score

```typescript
interface EnhancedScore {
  momentum: number;        // 0-100 from TV indicators
  volumeConfirmation: number; // 0-100 comparing real vs tokenized volume
  marketPhase: MarketPhase;
  sectorRotation: number;  // 0-100 vs sector
  composite: number;       // Weighted average
  priceDeviation: number;  // % difference between tokenized and real price
}

function calculateEnhancedScore(
  tv: TVStockData,
  dexData: DexPairData,
  sectorAvgPerf: Record<string, number>
): EnhancedScore {
  const momentum = calcMomentumScore(tv);
  const { score: volumeConfirmation } = calcVolumeConfirmation(
    tv,
    dexData.volume24h
  );
  const sectorRotation = calcSectorRotationScore(tv, sectorAvgPerf);
  const marketPhase = getMarketPhase();

  // Price deviation: how far tokenized price is from real price
  const realPrice = getRelevantPrice(tv);
  const tokenPrice = parseFloat(dexData.priceUsd);
  const priceDeviation = realPrice > 0
    ? ((tokenPrice - realPrice) / realPrice) * 100
    : 0;

  // Weighted composite (adjustable)
  const composite = Math.round(
    momentum * 0.35 +
    volumeConfirmation * 0.25 +
    sectorRotation * 0.20 +
    (50 + Math.max(-25, Math.min(25, -priceDeviation * 5))) * 0.20 // Peg deviation penalty
  );

  return {
    momentum,
    volumeConfirmation,
    marketPhase,
    sectorRotation,
    composite: Math.max(0, Math.min(100, composite)),
    priceDeviation,
  };
}
```

---

## 8. MCP Server Integration (Bonus)

tvscreener v0.2.0 ships with an MCP server for Claude:

```bash
pip install tvscreener[mcp]
claude mcp add tvscreener -- tvscreener-mcp
```

MCP tools available:
- `discover_fields` -- search 3,500+ fields by keyword
- `custom_query` -- flexible queries with any fields and filters
- `search_stocks` / `search_crypto` / `search_forex` -- simplified screeners
- `get_top_movers` -- top gainers/losers

This could be useful for ad-hoc research during development.

---

## 9. Implementation Roadmap

### Phase 1: API Route + Cache (1 day)

1. Create `/api/tv-screener/route.ts` with the direct HTTP approach
2. Add 60-second in-memory cache (or Next.js `unstable_cache`)
3. Map all ~70 xStocks tickers to real tickers
4. Return structured `TVStockData` for each

### Phase 2: Client Hook + Display (1 day)

1. Create `useTVScreener()` hook with market-hours-aware polling
2. Add TradingView data columns to xStocksPanel (RSI, MACD, Technical Rating)
3. Show market phase indicator (PRE/REGULAR/AFTER/CLOSED)
4. Show price deviation between tokenized and real price

### Phase 3: Enhanced Scoring (1 day)

1. Implement momentum scoring
2. Implement volume confirmation (DexScreener vs TV volume)
3. Implement sector rotation signals
4. Add composite score to token cards / table

### Phase 4: Advanced Signals (stretch)

1. Multi-timeframe RSI (1h, 4h, 1D)
2. Bollinger Band squeeze detection
3. Earnings date proximity alerts
4. Candlestick pattern signals
5. Sector heatmap visualization

---

## 10. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| TradingView blocks requests | No TV data | Cache last-known data, fall back to DexScreener-only |
| API endpoint changes | Broken queries | Pin tvscreener version, monitor for HTTP errors |
| Stale data during outages | Bad signals | Timestamp all data, show "stale" warning if >5min old |
| Excessive polling | IP ban | Market-hours-aware intervals, 60s minimum |
| Python dependency complexity | Deployment issues | Use direct HTTP (Option A) -- no Python needed |
| Symbol mismatches | Wrong data | Validate mapping at startup, log mismatches |

---

## 11. Quick Reference: TradingView Scan API

### Endpoint

```
POST https://scanner.tradingview.com/global/scan
```

### Headers

```json
{
  "Content-Type": "application/json",
  "User-Agent": "Mozilla/5.0 ...",
  "Origin": "https://www.tradingview.com",
  "Referer": "https://www.tradingview.com/"
}
```

### Payload Structure

```json
{
  "filter": [],
  "options": { "lang": "en" },
  "symbols": {
    "query": { "types": [] },
    "tickers": ["NASDAQ:AAPL", "NYSE:JPM", ...]
  },
  "sort": { "sortBy": "market_cap_basic", "sortOrder": "desc" },
  "range": [0, 150],
  "columns": ["name", "close", "change", "volume", "RSI", ...],
  "markets": ["america"]
}
```

### Response Structure

```json
{
  "totalCount": 42,
  "data": [
    {
      "s": "NASDAQ:AAPL",
      "d": ["Apple Inc.", 232.50, 1.23, 52345678, 58.3, ...]
    },
    ...
  ]
}
```

The `d` array values correspond to the `columns` array in the request, in order.
