export type PerpsMarket = 'SOL-USD' | 'BTC-USD' | 'ETH-USD';

export interface PerpsPriceSnapshot {
  sol: number;
  btc: number;
  eth: number;
  updatedAt: number;
}

export interface PerpsCandlePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface PerpsOrderRequest {
  market: PerpsMarket;
  side: 'long' | 'short';
  collateral_usd: number;
  leverage: number;
  tp_pct?: number;
  sl_pct?: number;
}

function asNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function extractMarketPrice(payload: Record<string, unknown>, market: PerpsMarket, symbol: 'SOL' | 'BTC' | 'ETH'): number {
  const marketObj = payload[market] as Record<string, unknown> | undefined;
  if (marketObj && typeof marketObj === 'object') {
    const price = asNumber(marketObj.price);
    if (price > 0) return price;
  }

  const upper = asNumber(payload[symbol]);
  if (upper > 0) return upper;
  const lower = asNumber(payload[symbol.toLowerCase()]);
  if (lower > 0) return lower;

  return asNumber(payload[market]);
}

export function normalizePerpsPriceSnapshot(payload: unknown): PerpsPriceSnapshot {
  const obj = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  return {
    sol: extractMarketPrice(obj, 'SOL-USD', 'SOL'),
    btc: extractMarketPrice(obj, 'BTC-USD', 'BTC'),
    eth: extractMarketPrice(obj, 'ETH-USD', 'ETH'),
    updatedAt: Date.now(),
  };
}

export function normalizePerpsCandles(payload: unknown): PerpsCandlePoint[] {
  const obj = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const raw = Array.isArray(obj.candles) ? obj.candles : [];

  return raw
    .map((item) => {
      const candle = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>;
      return {
        time: asNumber(candle.time ?? candle.t),
        open: asNumber(candle.open ?? candle.o),
        high: asNumber(candle.high ?? candle.h),
        low: asNumber(candle.low ?? candle.l),
        close: asNumber(candle.close ?? candle.c),
      };
    })
    .filter((c) => c.time > 0 && c.high >= c.low);
}

export function normalizePerpsOrderRequest(input: {
  market: string;
  side: 'long' | 'short';
  collateralUsd: number;
  leverage: number;
  tpPct?: number;
  slPct?: number;
}): PerpsOrderRequest {
  const market = (['SOL-USD', 'BTC-USD', 'ETH-USD'] as const).includes(input.market as PerpsMarket)
    ? (input.market as PerpsMarket)
    : 'SOL-USD';

  const payload: PerpsOrderRequest = {
    market,
    side: input.side,
    collateral_usd: asNumber(input.collateralUsd),
    leverage: asNumber(input.leverage),
  };

  if (input.tpPct !== undefined && Number.isFinite(input.tpPct)) {
    payload.tp_pct = asNumber(input.tpPct);
  }
  if (input.slPct !== undefined && Number.isFinite(input.slPct)) {
    payload.sl_pct = asNumber(input.slPct);
  }

  return payload;
}
