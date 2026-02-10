/**
 * TradingView Screener Integration
 *
 * Direct HTTP integration with TradingView's public scan endpoint.
 * No API key, no Python dependency -- pure TypeScript using fetch().
 *
 * Provides:
 *  - Symbol mapping (xStocks tickers <-> TradingView symbols)
 *  - TVStockData interface (40+ fields: price, indicators, volume, performance)
 *  - fetchTVScreenerData() for batch-fetching all mapped tickers
 *  - getCachedTVData() with 60-second in-memory cache
 *  - MarketPhase detection based on US Eastern Time
 */

import { ALL_TOKENIZED_EQUITIES } from '@/lib/xstocks-data';

// ============================================================================
// Symbol Mapping
// ============================================================================

/**
 * Build xStocks -> TradingView symbol map.
 *
 * Strategy: strip trailing 'x' from the xStocks ticker to derive the real
 * stock ticker, with special-case overrides for ambiguous tickers.
 *
 * Skips PRESTOCK tickers (SPACEX, OPENAI, etc.) since they are pre-IPO
 * and not listed on TradingView.
 */

const PRESTOCK_TICKERS = new Set([
  'SPACEX', 'OPENAI', 'ANTHROPIC', 'XAI', 'ANDURIL', 'KALSHI', 'POLYMARKET',
]);

/**
 * Special-case overrides where naive "strip trailing x" would produce
 * the wrong result or where we want to be explicit.
 */
const SPECIAL_OVERRIDES: Record<string, string> = {
  'Vx':      'V',       // Visa -- single-char ticker
  'MAx':     'MA',      // Mastercard
  'BRK.Bx':  'BRK.B',  // Berkshire Hathaway Class B
  'GMEx':    'GME',     // GameStop
  'GOOGLx':  'GOOGL',   // Alphabet Class A (the L is part of the real ticker)
};

function buildSymbolMap(): Record<string, string> {
  const map: Record<string, string> = {};

  for (const eq of ALL_TOKENIZED_EQUITIES) {
    // Skip pre-IPO tickers -- not on TradingView
    if (PRESTOCK_TICKERS.has(eq.ticker)) continue;

    // Use override if one exists, otherwise strip trailing 'x'
    if (SPECIAL_OVERRIDES[eq.ticker]) {
      map[eq.ticker] = SPECIAL_OVERRIDES[eq.ticker];
    } else {
      // Strip the trailing 'x' that xStocks appends
      map[eq.ticker] = eq.ticker.replace(/x$/, '');
    }
  }

  return map;
}

/** xStocks ticker -> real TradingView ticker (e.g. "AAPLx" -> "AAPL") */
export const XSTOCKS_TO_TV_SYMBOL: Record<string, string> = buildSymbolMap();

/** Reverse map: real ticker -> xStocks ticker (e.g. "AAPL" -> "AAPLx") */
export const TV_SYMBOL_TO_XSTOCKS: Record<string, string> = Object.fromEntries(
  Object.entries(XSTOCKS_TO_TV_SYMBOL).map(([xTicker, realTicker]) => [realTicker, xTicker]),
);

// ============================================================================
// TVStockData Interface
// ============================================================================

/** Structured stock data returned from TradingView's scan endpoint. */
export interface TVStockData {
  /** Full exchange-qualified symbol, e.g. "NASDAQ:AAPL" */
  symbol: string;
  /** Company/instrument description returned by TradingView */
  name: string;

  // --- Price ---
  price: number;
  changePercent: number;
  change: number;
  open: number;
  high: number;
  low: number;
  gap: number | null;

  // --- Volume ---
  volume: number;
  avgVolume10d: number;
  relativeVolume: number;

  // --- Oscillators ---
  rsi14: number | null;
  macdLevel: number | null;
  macdSignal: number | null;
  stochK: number | null;
  williamsR: number | null;
  cci: number | null;
  adx: number | null;
  momentum: number | null;
  moneyFlow: number | null;

  // --- Aggregate Ratings (-1 strong sell ... +1 strong buy) ---
  technicalRating: number | null;
  oscillatorsRating: number | null;
  maRating: number | null;

  // --- Moving Averages ---
  sma20: number | null;
  sma50: number | null;
  sma200: number | null;
  ema20: number | null;
  ema50: number | null;

  // --- Bands & Volatility ---
  bollingerLower: number | null;
  bollingerUpper: number | null;
  atr: number | null;
  volatility: number | null;

  // --- Performance ---
  perfWeek: number | null;
  perfMonth: number | null;
  perf3M: number | null;
  perfYTD: number | null;

  // --- Fundamentals ---
  marketCap: number | null;
  sector: string | null;

  // --- Pre/Post Market ---
  premarketChange: number | null;
  premarketVolume: number | null;
  postmarketChange: number | null;

  // --- Other ---
  vwap: number | null;
  beta: number | null;
  updateMode: string | null;
}

// ============================================================================
// TV_COLUMNS -- Column names sent in the scan request
// ============================================================================

/**
 * Ordered list of columns for the TradingView scan API.
 * The response `d` array values correspond 1:1 with this array.
 */
export const TV_COLUMNS: string[] = [
  'name',                        // 0
  'description',                 // 1
  'close',                       // 2  Price
  'change',                      // 3  Change %
  'change_abs',                  // 4  Change absolute
  'volume',                      // 5  Volume
  'average_volume_10d_calc',     // 6  Avg volume 10d
  'relative_volume_10d_calc',    // 7  Relative volume
  'RSI',                         // 8  RSI (14)
  'MACD.macd',                   // 9  MACD level
  'MACD.signal',                 // 10 MACD signal
  'Recommend.All',               // 11 Technical rating
  'Recommend.Other',             // 12 Oscillators rating
  'Recommend.MA',                // 13 Moving averages rating
  'SMA20',                       // 14
  'SMA50',                       // 15
  'SMA200',                      // 16
  'EMA20',                       // 17
  'EMA50',                       // 18
  'BB.lower',                    // 19 Bollinger lower
  'BB.upper',                    // 20 Bollinger upper
  'ATR',                         // 21
  'Volatility.D',                // 22 Daily volatility
  'high',                        // 23
  'low',                         // 24
  'open',                        // 25
  'gap',                         // 26
  'Perf.W',                      // 27 Weekly performance
  'Perf.1M',                     // 28 Monthly performance
  'Perf.3M',                     // 29 3M performance
  'Perf.YTD',                    // 30 YTD performance
  'market_cap_basic',            // 31 Market cap
  'sector',                      // 32
  'premarket_change',            // 33
  'premarket_volume',            // 34
  'postmarket_change',           // 35
  'Stoch.K',                     // 36 Stochastic %K
  'W.R',                         // 37 Williams %R
  'CCI20',                       // 38 CCI
  'ADX',                         // 39 ADX
  'Mom',                         // 40 Momentum
  'MoneyFlow',                   // 41 Money Flow
  'VWAP',                        // 42
  'beta_1_year',                 // 43 Beta
  'update_mode',                 // 44 Data freshness
];

// ============================================================================
// Market Phase Detection
// ============================================================================

export type MarketPhase = 'PRE_MARKET' | 'REGULAR' | 'AFTER_HOURS' | 'CLOSED';

/**
 * Determine the current US equity market phase based on US Eastern Time.
 *
 * Schedule (ET):
 *   Weekend (Sat/Sun)        -> CLOSED
 *   04:00 - 09:29            -> PRE_MARKET
 *   09:30 - 15:59            -> REGULAR
 *   16:00 - 19:59            -> AFTER_HOURS
 *   Otherwise                -> CLOSED
 */
export function getMarketPhase(): MarketPhase {
  const now = new Date();
  const etString = now.toLocaleString('en-US', { timeZone: 'America/New_York' });
  const et = new Date(etString);

  const day = et.getDay(); // 0 = Sunday, 6 = Saturday
  if (day === 0 || day === 6) return 'CLOSED';

  const timeMinutes = et.getHours() * 60 + et.getMinutes();

  if (timeMinutes >= 240 && timeMinutes < 570) return 'PRE_MARKET';    // 4:00 AM - 9:29 AM
  if (timeMinutes >= 570 && timeMinutes < 960) return 'REGULAR';        // 9:30 AM - 3:59 PM
  if (timeMinutes >= 960 && timeMinutes < 1200) return 'AFTER_HOURS';   // 4:00 PM - 7:59 PM
  return 'CLOSED';
}

// ============================================================================
// TradingView Scan API
// ============================================================================

const TV_SCAN_URL = 'https://scanner.tradingview.com/global/scan';

const TV_HEADERS: Record<string, string> = {
  'Content-Type': 'application/json',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Origin': 'https://www.tradingview.com',
  'Referer': 'https://www.tradingview.com/',
};

/**
 * Parse a single row from TradingView's response into a TVStockData object.
 *
 * The `d` array values correspond to TV_COLUMNS indices.
 */
function parseRow(symbol: string, d: (number | string | null)[]): TVStockData {
  return {
    symbol,
    name: (d[1] as string) ?? symbol.split(':')[1] ?? symbol,
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
    updateMode: d[44] as string | null,
  };
}

/**
 * Fetch stock data from TradingView's scan endpoint for all mapped tickers.
 *
 * Sends a single POST with all tickers across NASDAQ, NYSE, and AMEX exchanges.
 * Returns a Record keyed by the REAL ticker (e.g. "AAPL", not "AAPLx").
 *
 * Never throws -- returns an empty Record on failure so callers can
 * gracefully degrade to DexScreener-only data.
 */
export async function fetchTVScreenerData(): Promise<Record<string, TVStockData>> {
  try {
    const realTickers = Object.values(XSTOCKS_TO_TV_SYMBOL);

    // Send each ticker across all three major exchanges to ensure we find it
    const tickerSymbols = realTickers.flatMap((t) => [
      `NASDAQ:${t}`,
      `NYSE:${t}`,
      `AMEX:${t}`,
    ]);

    const payload = {
      filter: [],
      options: { lang: 'en' },
      symbols: {
        query: { types: [] },
        tickers: tickerSymbols,
      },
      sort: { sortBy: 'market_cap_basic', sortOrder: 'desc' },
      range: [0, 300], // generous range to capture all tickers even with duplicates
      columns: TV_COLUMNS,
      markets: ['america'],
    };

    const response = await fetch(TV_SCAN_URL, {
      method: 'POST',
      headers: TV_HEADERS,
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15_000),
    });

    if (!response.ok) {
      console.error(`[tv-screener] TradingView API returned ${response.status}`);
      return {};
    }

    const json = await response.json();
    const results: Record<string, TVStockData> = {};

    // TradingView may return multiple exchange hits per ticker (e.g. NASDAQ:AAPL
    // and NYSE:AAPL). We keep the first match since it will be the primary listing
    // (sorted by market cap).
    for (const row of json.data ?? []) {
      const fullSymbol = row.s as string;      // e.g. "NASDAQ:AAPL"
      const ticker = fullSymbol.split(':')[1];  // e.g. "AAPL"
      const d = row.d as (number | string | null)[];

      // Only keep the first (highest market-cap) match per ticker
      if (ticker && !results[ticker]) {
        results[ticker] = parseRow(fullSymbol, d);
      }
    }

    return results;
  } catch (err) {
    console.error('[tv-screener] Failed to fetch TradingView data:', err);
    return {};
  }
}

// ============================================================================
// In-Memory Cache (60-second TTL)
// ============================================================================

let cachedData: { data: Record<string, TVStockData>; timestamp: number } | null = null;
const CACHE_TTL = 60_000;

/**
 * Cache-aware wrapper around fetchTVScreenerData().
 *
 * Returns cached data if it is less than 60 seconds old, otherwise
 * fetches fresh data from TradingView and updates the cache.
 */
export async function getCachedTVData(): Promise<Record<string, TVStockData>> {
  if (cachedData && Date.now() - cachedData.timestamp < CACHE_TTL) {
    return cachedData.data;
  }
  const data = await fetchTVScreenerData();
  cachedData = { data, timestamp: Date.now() };
  return data;
}
