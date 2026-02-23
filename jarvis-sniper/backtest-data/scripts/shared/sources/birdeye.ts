import { fetchJSON, log, RateLimiter } from '../utils';
import type { TokenRecord } from '../types';

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function getBirdeyeApiKey(): string | undefined {
  const key = String(process.env.BIRDEYE_API_KEY || '').trim();
  return key || undefined;
}

interface BirdeyeToken {
  address?: string;
  mintAddress?: string;
  symbol?: string;
  name?: string;
  liquidity?: number;
  liquidityUsd?: number;
  v24hUSD?: number;
  volume24hUSD?: number;
  volume24h?: number;
  priceChange24hPercent?: number;
  v24hChangePercent?: number;
  price?: number;
  value?: number;
  buy24h?: number;
  sell24h?: number;
  holder?: number;
  holders?: number;
  logoURI?: string;
  website?: string;
  twitter?: string;
  telegram?: string;
  pairAddress?: string;
}

interface BirdeyeResponse {
  success?: boolean;
  data?: {
    tokens?: BirdeyeToken[];
    items?: BirdeyeToken[];
  } | BirdeyeToken[];
}

function num(value: unknown, fallback = 0): number {
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function birdeyeToToken(t: BirdeyeToken): TokenRecord | null {
  const mint = t.address || t.mintAddress || '';
  if (!mint || mint.length < 32) return null;

  return {
    mint,
    symbol: t.symbol || 'UNKNOWN',
    name: t.name || t.symbol || 'Unknown',
    pool_address: t.pairAddress || '',
    creation_timestamp: 0,
    liquidity_usd: num(t.liquidityUsd ?? t.liquidity),
    volume_24h_usd: num(t.v24hUSD ?? t.volume24hUSD ?? t.volume24h),
    price_change_1h: 0,
    price_usd: num(t.price ?? t.value),
    buy_txn_count_24h: num(t.buy24h),
    sell_txn_count_24h: num(t.sell24h),
    holder_count: num(t.holder ?? t.holders),
    has_twitter: Boolean(t.twitter),
    has_website: Boolean(t.website),
    has_telegram: Boolean(t.telegram),
    source: 'birdeye',
    source_confidence: 0.75,
    source_details: {
      provider: 'birdeye',
      endpoint: 'tokenlist',
    },
  };
}

export async function fetchBirdeyeTokenList(): Promise<TokenRecord[]> {
  const key = getBirdeyeApiKey();
  if (!key) {
    log('Birdeye API key missing; skipping Birdeye discovery source');
    return [];
  }

  const rpm = envInt('BIRDEYE_RPM', 25);
  const maxPages = envInt('BIRDEYE_MAX_PAGES', 20);
  const pageSize = Math.min(envInt('BIRDEYE_PAGE_SIZE', 100), 100);
  const limiter = new RateLimiter(rpm, 60_000);
  const out: TokenRecord[] = [];

  for (let page = 0; page < maxPages; page++) {
    const offset = page * pageSize;
    const url =
      `https://public-api.birdeye.so/defi/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=${offset}&limit=${pageSize}`;

    const resp = await fetchJSON<BirdeyeResponse>(url, {
      rateLimiter: limiter,
      label: `birdeye:tokenlist:p${page + 1}`,
      retries: 3,
      extraHeaders: {
        'x-api-key': key,
        'x-chain': 'solana',
      },
    });

    const data = resp?.data;
    const items = Array.isArray(data)
      ? data
      : (data?.tokens || data?.items || []);
    if (!items || items.length === 0) break;

    const mapped = items
      .map((item) => birdeyeToToken(item))
      .filter((token): token is TokenRecord => token !== null);

    out.push(...mapped);
    log(`  Birdeye page ${page + 1}: ${mapped.length} tokens (total: ${out.length})`);

    if (items.length < pageSize) break;
  }

  return out;
}
