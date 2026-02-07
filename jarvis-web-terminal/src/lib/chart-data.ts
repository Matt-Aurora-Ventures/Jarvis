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

export type Timeframe = '1h' | '4h' | '1d';
export type Market = 'SOL' | 'ETH' | 'BTC';

const TF_MAP: Record<Timeframe, { tf: string; aggregate: string; limit: number }> = {
  '1h': { tf: 'minute', aggregate: '15', limit: 60 },   // 4 candles/hr × 15 hrs
  '4h': { tf: 'hour',   aggregate: '1',  limit: 96 },   // 96 hours = 4 days
  '1d': { tf: 'hour',   aggregate: '4',  limit: 90 },   // 4-hr candles × 15 days
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
  const url = `${GECKO_BASE}/networks/solana/pools/${pool}`;
  const res = await fetch(url, { next: { revalidate: 30 } } as RequestInit);
  if (!res.ok) return 0;
  const json = await res.json();
  return parseFloat(json?.data?.attributes?.base_token_price_usd ?? '0');
}
