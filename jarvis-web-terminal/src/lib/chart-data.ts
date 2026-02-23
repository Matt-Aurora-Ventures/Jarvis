/**
 * GeckoTerminal OHLCV Chart Data
 *
 * Free API — no key required — 30 req/min rate limit.
 * Pools are Raydium/Orca SOL pairs on Solana.
 */

const GECKO_BASE = 'https://api.geckoterminal.com/api/v2';

export const POOLS: Record<string, string> = {
  SOL: '58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2',
  ETH: 'AU971DrPyhhrpRnmEBp5pDTWL2ny7nofb5vYBjDJkR2E',
  BTC: '55BrDTCLWayM16GwrMEQU57o4PTm6ceF9wavSdNZcEiy',
};

export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d';
export type Market = 'SOL' | 'ETH' | 'BTC';

const TF_MAP: Record<Timeframe, { tf: string; aggregate: string; limit: number }> = {
  '1m':  { tf: 'minute', aggregate: '1',  limit: 300 },  // 1-min candles × 5 hrs
  '5m':  { tf: 'minute', aggregate: '5',  limit: 300 },  // 5-min candles × 25 hrs
  '15m': { tf: 'minute', aggregate: '15', limit: 300 },  // 15-min candles × 75 hrs
  '1h':  { tf: 'hour',   aggregate: '1',  limit: 96 },   // 1-hr candles × 4 days
  '4h':  { tf: 'hour',   aggregate: '4',  limit: 90 },   // 4-hr candles × 15 days
  '1d':  { tf: 'day',    aggregate: '1',  limit: 180 },  // daily candles × 6 months
};

export interface Candle {
  time: number;    // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export async function fetchOHLCV(
  market: Market = 'SOL',
  timeframe: Timeframe = '1h',
): Promise<Candle[]> {
  const pool = POOLS[market];
  const { tf, aggregate, limit } = TF_MAP[timeframe];

  const url =
    `${GECKO_BASE}/networks/solana/pools/${pool}/ohlcv/${tf}` +
    `?aggregate=${aggregate}&limit=${limit}&currency=usd`;

  const res = await fetch(url, { next: { revalidate: 60 } } as RequestInit);
  if (!res.ok) throw new Error(`GeckoTerminal ${res.status}`);

  const json = await res.json();
  const list: number[][] = json?.data?.attributes?.ohlcv_list ?? [];

  // GeckoTerminal returns newest-first — reverse for chart
  return list
    .map(([ts, o, h, l, c, v]) => ({
      time: ts,
      open: o,
      high: h,
      low: l,
      close: c,
      volume: v,
    }))
    .reverse();
}

export async function fetchCurrentPrice(market: Market = 'SOL'): Promise<number> {
  const pool = POOLS[market];
  return fetchCurrentPriceByPool(pool);
}

/**
 * Fetch OHLCV candles for an arbitrary pool address (not limited to SOL/ETH/BTC).
 * Used when the user selects a custom token via TokenSearch.
 */
export async function fetchOHLCVByPool(
  poolAddress: string,
  timeframe: Timeframe = '1h',
): Promise<Candle[]> {
  const { tf, aggregate, limit } = TF_MAP[timeframe];

  const url =
    `${GECKO_BASE}/networks/solana/pools/${poolAddress}/ohlcv/${tf}` +
    `?aggregate=${aggregate}&limit=${limit}&currency=usd`;

  const res = await fetch(url, { next: { revalidate: 60 } } as RequestInit);
  if (!res.ok) throw new Error(`GeckoTerminal ${res.status}`);

  const json = await res.json();
  const list: number[][] = json?.data?.attributes?.ohlcv_list ?? [];

  // GeckoTerminal returns newest-first -- reverse for chart
  return list
    .map(([ts, o, h, l, c, v]) => ({
      time: ts,
      open: o,
      high: h,
      low: l,
      close: c,
      volume: v,
    }))
    .reverse();
}

/**
 * Fetch current price for an arbitrary pool address.
 */
export async function fetchCurrentPriceByPool(poolAddress: string): Promise<number> {
  const url = `${GECKO_BASE}/networks/solana/pools/${poolAddress}`;
  const res = await fetch(url, { next: { revalidate: 30 } } as RequestInit);
  if (!res.ok) return 0;
  const json = await res.json();
  return parseFloat(json?.data?.attributes?.base_token_price_usd ?? '0');
}
