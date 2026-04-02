import { fetchJSON, log, RateLimiter } from '../utils';
import type { TokenRecord } from '../types';

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

interface PumpfunCoin {
  mint?: string;
  symbol?: string;
  name?: string;
  created_timestamp?: number;
  market_cap?: number;
  usd_market_cap?: number;
  volume_24h?: number;
  liquidity?: number;
  website?: string;
  telegram?: string;
  twitter?: string;
  complete?: boolean;
}

function num(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function coinToToken(c: PumpfunCoin): TokenRecord | null {
  const mint = c.mint || '';
  if (!mint || mint.length < 32) return null;

  const created = num(c.created_timestamp);
  const createdSec = created > 2_000_000_000 ? Math.floor(created / 1000) : created;

  return {
    mint,
    symbol: c.symbol || 'UNKNOWN',
    name: c.name || c.symbol || 'Unknown',
    pool_address: '',
    creation_timestamp: createdSec,
    liquidity_usd: num(c.liquidity),
    volume_24h_usd: num(c.volume_24h),
    price_change_1h: 0,
    price_usd: 0,
    buy_txn_count_24h: 0,
    sell_txn_count_24h: 0,
    holder_count: 0,
    has_twitter: Boolean(c.twitter),
    has_website: Boolean(c.website),
    has_telegram: Boolean(c.telegram),
    source: 'pumpfun',
    source_confidence: c.complete ? 0.8 : 0.7,
    source_details: {
      provider: 'pumpfun',
      endpoint: 'coins',
      complete: Boolean(c.complete),
      market_cap_usd: num(c.usd_market_cap ?? c.market_cap),
    },
  };
}

export async function fetchPumpfunCoins(): Promise<TokenRecord[]> {
  const rpm = envInt('PUMPFUN_RPM', 40);
  const maxPages = envInt('PUMPFUN_MAX_PAGES', 20);
  const pageSize = Math.min(envInt('PUMPFUN_PAGE_SIZE', 200), 200);
  const limiter = new RateLimiter(rpm, 60_000);
  const out: TokenRecord[] = [];

  const key = String(process.env.PUMPFUN_API_KEY || '').trim();
  const headers = key ? { Authorization: `Bearer ${key}` } : undefined;

  for (let page = 0; page < maxPages; page++) {
    const offset = page * pageSize;
    const url =
      `https://frontend-api.pump.fun/coins?offset=${offset}&limit=${pageSize}` +
      '&sort=created_timestamp&order=DESC&includeNsfw=false';

    const data = await fetchJSON<PumpfunCoin[] | { data?: PumpfunCoin[] }>(url, {
      rateLimiter: limiter,
      label: `pumpfun:coins:p${page + 1}`,
      retries: 3,
      extraHeaders: headers,
    });

    const rows = Array.isArray(data) ? data : (data?.data || []);
    if (!rows || rows.length === 0) break;

    const mapped = rows
      .map((coin) => coinToToken(coin))
      .filter((token): token is TokenRecord => token !== null);

    out.push(...mapped);
    log(`  Pump.fun page ${page + 1}: ${mapped.length} tokens (total: ${out.length})`);

    if (rows.length < pageSize) break;
  }

  return out;
}
