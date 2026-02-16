/**
 * Phase 1: Token Universe Discovery
 * 
 * Pulls Solana tokens from the last 90 days via:
 *   1. GeckoTerminal (new_pools + top pools by volume)
 *   2. DexScreener (token profiles + boosts)
 *   3. Jupiter Gems (graduation feed)
 *   4. Birdeye (token list + trending, optional)
 * 
 * Goal: 50,000+ unique token mints with metadata.
 * Outputs: universe/universe_raw.json, universe/universe_raw.csv
 * 
 * Resumable: saves progress to discovery_progress.json after every batch.
 * Run: npx tsx backtest-data/scripts/01_discover_universe.ts
 */

import {
  log, logError, fetchJSON, fetchJSONPost, sleep,
  RateLimiter, ProgressTracker, writeJSON, writeCSV,
  deduplicateByMint, ensureDir, readJSON, dataPath, geckoBaseUrl,
} from './shared/utils';
import type { TokenRecord, DiscoveryProgress } from './shared/types';
import * as fs from 'fs';

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function getBirdeyeApiKey(): string {
  return String(process.env.BIRDEYE_API_KEY || process.env.BIRDEYE_API || '').trim();
}

// ─── Rate Limiters (CoinGecko Basic paid: 250 req/min for GeckoTerminal) ───
const geckoLimiter = new RateLimiter(200, 60_000, 300);   // 200 req/min with 300ms min delay (paid tier)
const dexLimiter = new RateLimiter(250, 60_000, 250);     // 250 req/min, min 250ms between requests
const jupiterLimiter = new RateLimiter(60, 60_000, 1000);  // conservative, 1s between requests
const birdeyeLimiter = new RateLimiter(120, 60_000, 500);  // conservative; API key often enforces burst limits

// ─── API Response Types ───

interface GeckoPoolAttributes {
  name: string;
  address: string;
  base_token_price_usd: string | null;
  quote_token_price_usd: string | null;
  reserve_in_usd: string | null;
  pool_created_at: string | null;
  volume_usd: { h24: string | null } | null;
  price_change_percentage: { h1: string | null } | null;
  transactions: { h24: { buys: number | null; sells: number | null } | null } | null;
}

interface GeckoPoolRelationships {
  base_token: { data: { id: string } };
  quote_token: { data: { id: string } };
}

interface GeckoPoolData {
  id: string;
  type: string;
  attributes: GeckoPoolAttributes;
  relationships: GeckoPoolRelationships;
}

interface GeckoPoolsResponse {
  data: GeckoPoolData[];
  links?: { next?: string };
}

interface GeckoTokenAttributes {
  address: string;
  name: string;
  symbol: string;
  websites?: string[];
  discord_url?: string | null;
  telegram_handle?: string | null;
  twitter_handle?: string | null;
}

interface GeckoTokenIncluded {
  id: string;
  type: string;
  attributes: GeckoTokenAttributes;
}

interface GeckoPoolsWithIncludesResponse extends GeckoPoolsResponse {
  included?: GeckoTokenIncluded[];
}

interface DexScreenerProfile {
  chainId: string;
  tokenAddress: string;
  icon?: string;
  header?: string;
  description?: string;
  links?: { type?: string; label?: string; url?: string }[];
}

interface DexScreenerBoost {
  chainId: string;
  tokenAddress: string;
  amount?: number;
  totalAmount?: number;
}

interface DexScreenerTokenResponse {
  pairs?: DexScreenerPair[];
}

interface DexScreenerPair {
  chainId: string;
  dexId: string;
  pairAddress: string;
  baseToken: { address: string; name: string; symbol: string };
  quoteToken: { address: string; name: string; symbol: string };
  priceUsd?: string;
  volume?: { h24?: number };
  liquidity?: { usd?: number };
  priceChange?: { h1?: number };
  txns?: { h24?: { buys?: number; sells?: number } };
  pairCreatedAt?: number;
  info?: { socials?: { type: string; url: string }[]; websites?: { url: string }[] };
}

interface JupiterGemsResponse {
  pools?: JupiterGemPool[];
  tokens?: JupiterGemPool[];
}

interface JupiterGemPool {
  mint?: string;
  address?: string;
  symbol?: string;
  name?: string;
  pool?: string;
  poolAddress?: string;
  liquidity?: number;
  liquidityUsd?: number;
  volume24h?: number;
  volume_24h?: number;
  priceUsd?: number;
  price?: number;
  priceChange1h?: number;
  price_change_1h?: number;
  createdAt?: number;
  created_at?: number;
  buyCount24h?: number;
  sellCount24h?: number;
  holders?: number;
  holderCount?: number;
  twitter?: string | boolean;
  website?: string | boolean;
  telegram?: string | boolean;
  hasTwitter?: boolean;
  hasWebsite?: boolean;
  hasTelegram?: boolean;
  score?: number;
}

interface BirdeyeTokenEntry {
  address?: string;
  mint?: string;
  symbol?: string;
  name?: string;
  logoURI?: string;
  liquidity?: number;
  liquidityUsd?: number;
  v24hUSD?: number;
  volume24hUSD?: number;
  volume24h?: number;
  price?: number;
  priceUsd?: number;
  mc?: number;
  fdv?: number;
  updateUnixTime?: number;
}

interface BirdeyeTokenListResponse {
  success?: boolean;
  data?: {
    items?: BirdeyeTokenEntry[];
    tokens?: BirdeyeTokenEntry[];
  } | BirdeyeTokenEntry[];
}

interface BirdeyeTrendingResponse {
  success?: boolean;
  data?: {
    tokens?: BirdeyeTokenEntry[];
    items?: BirdeyeTokenEntry[];
  } | BirdeyeTokenEntry[];
}

// ─── Conversion Helpers ───

function geckoPoolToToken(pool: GeckoPoolData, included?: GeckoTokenIncluded[]): TokenRecord | null {
  const attr = pool.attributes;
  // Extract base token mint from relationship ID (format: "solana_<address>")
  const baseId = pool.relationships?.base_token?.data?.id || '';
  const mint = baseId.replace('solana_', '');
  if (!mint || mint.length < 32) return null;

  // Find token metadata in included array
  const tokenMeta = included?.find(t => t.id === baseId)?.attributes;

  const liq = parseFloat(attr.reserve_in_usd || '0');
  const vol = parseFloat(attr.volume_usd?.h24 || '0');
  const priceChange = parseFloat(attr.price_change_percentage?.h1 || '0');
  const price = parseFloat(attr.base_token_price_usd || '0');
  const buys = attr.transactions?.h24?.buys || 0;
  const sells = attr.transactions?.h24?.sells || 0;
  const created = attr.pool_created_at ? new Date(attr.pool_created_at).getTime() / 1000 : 0;

  return {
    mint,
    symbol: tokenMeta?.symbol || attr.name?.split('/')[0]?.trim() || 'UNKNOWN',
    name: tokenMeta?.name || attr.name || 'Unknown',
    pool_address: attr.address || pool.id.replace('solana_', ''),
    creation_timestamp: created,
    liquidity_usd: liq,
    volume_24h_usd: vol,
    price_change_1h: priceChange,
    price_usd: price,
    buy_txn_count_24h: buys,
    sell_txn_count_24h: sells,
    holder_count: 0,
    has_twitter: !!tokenMeta?.twitter_handle,
    has_website: !!(tokenMeta?.websites && tokenMeta.websites.length > 0),
    has_telegram: !!tokenMeta?.telegram_handle,
    source: 'geckoterminal',
  };
}

function dexPairToToken(pair: DexScreenerPair, profileLinks?: DexScreenerProfile): TokenRecord | null {
  if (pair.chainId !== 'solana') return null;
  const mint = pair.baseToken?.address;
  if (!mint || mint.length < 32) return null;

  const socials = pair.info?.socials || [];
  const websites = pair.info?.websites || [];
  const profileLinkList = profileLinks?.links || [];

  return {
    mint,
    symbol: pair.baseToken.symbol || 'UNKNOWN',
    name: pair.baseToken.name || 'Unknown',
    pool_address: pair.pairAddress || '',
    creation_timestamp: pair.pairCreatedAt ? pair.pairCreatedAt / 1000 : 0,
    liquidity_usd: pair.liquidity?.usd || 0,
    volume_24h_usd: pair.volume?.h24 || 0,
    price_change_1h: pair.priceChange?.h1 || 0,
    price_usd: parseFloat(pair.priceUsd || '0'),
    buy_txn_count_24h: pair.txns?.h24?.buys || 0,
    sell_txn_count_24h: pair.txns?.h24?.sells || 0,
    holder_count: 0,
    has_twitter: socials.some(s => s.type === 'twitter') || profileLinkList.some(l => l.type === 'twitter'),
    has_website: websites.length > 0 || profileLinkList.some(l => l.type === 'website'),
    has_telegram: socials.some(s => s.type === 'telegram') || profileLinkList.some(l => l.type === 'telegram'),
    source: 'dexscreener',
  };
}

function jupiterGemToToken(gem: JupiterGemPool): TokenRecord | null {
  const mint = gem.mint || gem.address || '';
  if (!mint || mint.length < 32) return null;

  return {
    mint,
    symbol: gem.symbol || 'UNKNOWN',
    name: gem.name || 'Unknown',
    pool_address: gem.pool || gem.poolAddress || '',
    creation_timestamp: gem.createdAt || gem.created_at || 0,
    liquidity_usd: gem.liquidity || gem.liquidityUsd || 0,
    volume_24h_usd: gem.volume24h || gem.volume_24h || 0,
    price_change_1h: gem.priceChange1h || gem.price_change_1h || 0,
    price_usd: gem.priceUsd || gem.price || 0,
    buy_txn_count_24h: gem.buyCount24h || 0,
    sell_txn_count_24h: gem.sellCount24h || 0,
    holder_count: gem.holders || gem.holderCount || 0,
    has_twitter: !!(gem.twitter || gem.hasTwitter),
    has_website: !!(gem.website || gem.hasWebsite),
    has_telegram: !!(gem.telegram || gem.hasTelegram),
    source: 'jupiter_gems',
  };
}

function birdeyeTokenToToken(entry: BirdeyeTokenEntry): TokenRecord | null {
  const mint = entry.address || entry.mint || '';
  if (!mint || mint.length < 32) return null;

  const liq = Number(entry.liquidityUsd ?? entry.liquidity ?? 0) || 0;
  const vol = Number(entry.v24hUSD ?? entry.volume24hUSD ?? entry.volume24h ?? 0) || 0;
  const price = Number(entry.priceUsd ?? entry.price ?? 0) || 0;
  const ts = Number(entry.updateUnixTime || 0) || 0;

  return {
    mint,
    symbol: entry.symbol || 'UNKNOWN',
    name: entry.name || entry.symbol || 'Unknown',
    pool_address: '',
    creation_timestamp: ts > 1_000_000_000 ? ts : 0,
    liquidity_usd: liq,
    volume_24h_usd: vol,
    price_change_1h: 0,
    price_usd: price,
    buy_txn_count_24h: 0,
    sell_txn_count_24h: 0,
    holder_count: 0,
    has_twitter: false,
    has_website: false,
    has_telegram: false,
    source: 'birdeye',
  };
}

function mergeUniverseByMint(
  tokens: TokenRecord[],
  boostedMints: Set<string>,
  trendingMints: Set<string>,
): TokenRecord[] {
  const merged = new Map<string, TokenRecord>();
  const sourceFlags = new Map<string, { gecko: boolean; dex: boolean; jupiter: boolean; birdeye: boolean }>();

  for (const token of tokens) {
    if (!token.mint || token.mint.length < 32) continue;

    const flags = sourceFlags.get(token.mint) || { gecko: false, dex: false, jupiter: false, birdeye: false };
    if (token.source === 'geckoterminal') flags.gecko = true;
    else if (token.source === 'dexscreener') flags.dex = true;
    else if (token.source === 'jupiter_gems') flags.jupiter = true;
    else if (token.source === 'birdeye') flags.birdeye = true;
    sourceFlags.set(token.mint, flags);

    const existing = merged.get(token.mint);
    if (!existing) {
      merged.set(token.mint, { ...token });
      continue;
    }

    if ((!existing.symbol || existing.symbol === 'UNKNOWN') && token.symbol) existing.symbol = token.symbol;
    if ((!existing.name || existing.name === 'Unknown') && token.name) existing.name = token.name;
    if ((!existing.pool_address || existing.pool_address.length < 20) && token.pool_address) existing.pool_address = token.pool_address;

    if (token.creation_timestamp > 0) {
      if (existing.creation_timestamp <= 0) existing.creation_timestamp = token.creation_timestamp;
      else existing.creation_timestamp = Math.min(existing.creation_timestamp, token.creation_timestamp);
    }

    existing.liquidity_usd = Math.max(existing.liquidity_usd || 0, token.liquidity_usd || 0);
    existing.volume_24h_usd = Math.max(existing.volume_24h_usd || 0, token.volume_24h_usd || 0);
    existing.price_usd = Math.max(existing.price_usd || 0, token.price_usd || 0);
    if (Math.abs(token.price_change_1h || 0) > Math.abs(existing.price_change_1h || 0)) {
      existing.price_change_1h = token.price_change_1h || 0;
    }
    existing.buy_txn_count_24h = Math.max(existing.buy_txn_count_24h || 0, token.buy_txn_count_24h || 0);
    existing.sell_txn_count_24h = Math.max(existing.sell_txn_count_24h || 0, token.sell_txn_count_24h || 0);
    existing.holder_count = Math.max(existing.holder_count || 0, token.holder_count || 0);
    existing.has_twitter = !!(existing.has_twitter || token.has_twitter);
    existing.has_website = !!(existing.has_website || token.has_website);
    existing.has_telegram = !!(existing.has_telegram || token.has_telegram);
  }

  const out: TokenRecord[] = [];
  for (const [mint, token] of merged.entries()) {
    const flags = sourceFlags.get(mint) || { gecko: false, dex: false, jupiter: false, birdeye: false };
    const sourceCount = [flags.gecko, flags.dex, flags.jupiter, flags.birdeye].filter(Boolean).length;

    token.seen_on_geckoterminal = flags.gecko;
    token.seen_on_dexscreener = flags.dex;
    token.seen_on_jupiter_gems = flags.jupiter;
    token.seen_on_birdeye = flags.birdeye;
    token.source_count = Math.max(1, sourceCount);
    token.interest_is_boosted = boostedMints.has(mint);
    token.interest_is_trending = trendingMints.has(mint);

    if (flags.dex) token.source = 'dexscreener';
    else if (flags.gecko) token.source = 'geckoterminal';
    else if (flags.birdeye) token.source = 'birdeye';
    else token.source = 'jupiter_gems';

    out.push(token);
  }

  return out;
}

// ─── API Fetch Functions ───

async function fetchGeckoNewPools(page: number): Promise<TokenRecord[]> {
  const url = `${geckoBaseUrl()}/networks/solana/new_pools?page=${page}&include=base_token`;
  const data = await fetchJSON<GeckoPoolsWithIncludesResponse>(url, {
    rateLimiter: geckoLimiter,
    label: `gecko:new_pools:p${page}`,
  });
  if (!data?.data) return [];
  return data.data
    .map(p => geckoPoolToToken(p, data.included))
    .filter((t): t is TokenRecord => t !== null);
}

async function fetchGeckoTopPools(page: number): Promise<TokenRecord[]> {
  const url = `${geckoBaseUrl()}/networks/solana/pools?page=${page}&sort=h24_volume_usd_desc&include=base_token`;
  const data = await fetchJSON<GeckoPoolsWithIncludesResponse>(url, {
    rateLimiter: geckoLimiter,
    label: `gecko:top_pools:p${page}`,
  });
  if (!data?.data) return [];
  return data.data
    .map(p => geckoPoolToToken(p, data.included))
    .filter((t): t is TokenRecord => t !== null);
}

async function fetchGeckoTrendingPools(page: number): Promise<TokenRecord[]> {
  const url = `${geckoBaseUrl()}/networks/solana/trending_pools?page=${page}&include=base_token`;
  const data = await fetchJSON<GeckoPoolsWithIncludesResponse>(url, {
    rateLimiter: geckoLimiter,
    label: `gecko:trending:p${page}`,
  });
  if (!data?.data) return [];
  return data.data
    .map(p => geckoPoolToToken(p, data.included))
    .filter((t): t is TokenRecord => t !== null);
}

async function fetchDexScreenerProfiles(): Promise<DexScreenerProfile[]> {
  const url = 'https://api.dexscreener.com/token-profiles/latest/v1';
  const data = await fetchJSON<DexScreenerProfile[]>(url, {
    rateLimiter: dexLimiter,
    label: 'dex:profiles',
  });
  return (data || []).filter(p => p.chainId === 'solana');
}

async function fetchDexScreenerBoosts(): Promise<DexScreenerBoost[]> {
  const url = 'https://api.dexscreener.com/token-boosts/latest/v1';
  const data = await fetchJSON<DexScreenerBoost[]>(url, {
    rateLimiter: dexLimiter,
    label: 'dex:boosts',
  });
  return (data || []).filter(b => b.chainId === 'solana');
}

async function fetchDexScreenerTokenDetails(mints: string[]): Promise<TokenRecord[]> {
  const tokens: TokenRecord[] = [];
  // DexScreener supports comma-separated mints, up to ~30 at a time
  const batchSize = 30;
  for (let i = 0; i < mints.length; i += batchSize) {
    const batch = mints.slice(i, i + batchSize);
    const url = `https://api.dexscreener.com/tokens/v1/solana/${batch.join(',')}`;
    const data = await fetchJSON<DexScreenerPair[]>(url, {
      rateLimiter: dexLimiter,
      label: `dex:tokens:batch${Math.floor(i / batchSize)}`,
    });
    if (Array.isArray(data)) {
      for (const pair of data) {
        const t = dexPairToToken(pair);
        if (t) tokens.push(t);
      }
    }
    if (i + batchSize < mints.length) await sleep(250);
  }
  return tokens;
}

async function fetchJupiterGems(): Promise<TokenRecord[]> {
  // Try multiple endpoint + payload variants
  const attempts: { url: string; method: 'GET' | 'POST'; body?: unknown }[] = [
    { url: 'https://datapi.jup.ag/v1/pools/gems', method: 'POST', body: {} },
    { url: 'https://datapi.jup.ag/v1/pools/gems', method: 'POST', body: { page: 1, limit: 1000 } },
    { url: 'https://datapi.jup.ag/v1/pools/gems', method: 'GET' },
    { url: 'https://tokens.jup.ag/tokens?tags=pump', method: 'GET' },
    { url: 'https://lite-api.jup.ag/v1/pools/gems', method: 'GET' },
  ];

  for (const attempt of attempts) {
    try {
      let data: unknown;
      if (attempt.method === 'POST') {
        data = await fetchJSONPost<unknown>(attempt.url, attempt.body, {
          rateLimiter: jupiterLimiter, label: `jupiter:gems:post`, retries: 2,
        });
      } else {
        data = await fetchJSON<unknown>(attempt.url, {
          rateLimiter: jupiterLimiter, label: `jupiter:gems:get`, retries: 2,
        });
      }
      const resp = data as JupiterGemsResponse | null;
      const items = resp?.pools || resp?.tokens || (Array.isArray(data) ? data as JupiterGemPool[] : null);
      if (items && items.length > 0) {
        log(`Jupiter returned ${items.length} items from ${attempt.url}`);
        return items
          .map(g => jupiterGemToToken(g))
          .filter((t): t is TokenRecord => t !== null);
      }
    } catch { /* try next */ }
  }

  log('Jupiter Gems returned no data from any endpoint variant');
  return [];
}

function birdeyeItemsFromResponse(data: BirdeyeTokenListResponse | BirdeyeTrendingResponse | null): BirdeyeTokenEntry[] {
  if (!data) return [];
  const payload = data.data;
  if (Array.isArray(payload)) return payload;
  if (!payload) return [];
  const items = Array.isArray(payload.items) ? payload.items : [];
  const tokens = Array.isArray(payload.tokens) ? payload.tokens : [];
  return [...items, ...tokens];
}

async function fetchBirdeyeTokenListPage(page: number, limit: number): Promise<TokenRecord[]> {
  const key = getBirdeyeApiKey();
  if (!key) return [];

  const offset = (page - 1) * limit;
  const urls = [
    `https://public-api.birdeye.so/defi/v3/token/list?sort_by=v24hUSD&sort_type=desc&offset=${offset}&limit=${limit}`,
    `https://public-api.birdeye.so/defi/tokenlist?sort_by=v24hUSD&sort_type=desc&offset=${offset}&limit=${limit}`,
  ];

  for (const url of urls) {
    const resp = await fetchJSON<BirdeyeTokenListResponse>(url, {
      rateLimiter: birdeyeLimiter,
      label: `birdeye:token_list:p${page}`,
      retries: 3,
      extraHeaders: {
        'x-api-key': key,
        'x-chain': 'solana',
      },
    });
    const items = birdeyeItemsFromResponse(resp);
    if (items.length === 0) continue;
    return items.map(birdeyeTokenToToken).filter((t): t is TokenRecord => t !== null);
  }
  return [];
}

async function fetchBirdeyeTrendingPage(page: number, limit: number): Promise<TokenRecord[]> {
  const key = getBirdeyeApiKey();
  if (!key) return [];

  const offset = (page - 1) * limit;
  const urls = [
    `https://public-api.birdeye.so/defi/v3/token/trending?offset=${offset}&limit=${limit}`,
    `https://public-api.birdeye.so/defi/token_trending?sort_by=rank&sort_type=asc&offset=${offset}&limit=${limit}`,
  ];

  for (const url of urls) {
    const resp = await fetchJSON<BirdeyeTrendingResponse>(url, {
      rateLimiter: birdeyeLimiter,
      label: `birdeye:trending:p${page}`,
      retries: 3,
      extraHeaders: {
        'x-api-key': key,
        'x-chain': 'solana',
      },
    });
    const items = birdeyeItemsFromResponse(resp);
    if (items.length === 0) continue;
    return items.map(birdeyeTokenToToken).filter((t): t is TokenRecord => t !== null);
  }
  return [];
}

// ─── Additional GeckoTerminal Endpoints for More Coverage ───

async function fetchGeckoPoolsByToken(mint: string): Promise<TokenRecord[]> {
  const url = `${geckoBaseUrl()}/networks/solana/tokens/${mint}/pools?page=1&include=base_token`;
  const data = await fetchJSON<GeckoPoolsWithIncludesResponse>(url, {
    rateLimiter: geckoLimiter,
    label: `gecko:token_pools:${mint.slice(0, 8)}`,
  });
  if (!data?.data) return [];
  return data.data
    .map(p => geckoPoolToToken(p, data.included))
    .filter((t): t is TokenRecord => t !== null);
}

// GeckoTerminal search endpoint — returns pools matching a query
interface GeckoSearchResponse {
  data?: { id: string; type: string; attributes: { address: string; name: string; network: { identifier: string } }; relationships?: GeckoPoolRelationships }[];
  included?: GeckoTokenIncluded[];
}

async function fetchGeckoSearch(query: string): Promise<TokenRecord[]> {
  const url = `${geckoBaseUrl()}/search/pools?query=${encodeURIComponent(query)}&network=solana&page=1`;
  const data = await fetchJSON<GeckoSearchResponse>(url, {
    rateLimiter: geckoLimiter,
    label: `gecko:search:${query}`,
    retries: 2,
  });
  if (!data?.data) return [];
  // Search returns a different shape; extract what we can
  const tokens: TokenRecord[] = [];
  for (const pool of data.data) {
    const attr = pool.attributes;
    if (!attr.address) continue;
    // Pool address is available, but we need to get token details
    // Use included data if available, otherwise construct minimal record
    const parts = attr.name?.split('/') || [];
    tokens.push({
      mint: '', // will be filled by enrichment
      symbol: parts[0]?.trim() || 'UNKNOWN',
      name: attr.name || 'Unknown',
      pool_address: attr.address,
      creation_timestamp: 0,
      liquidity_usd: 0,
      volume_24h_usd: 0,
      price_change_1h: 0,
      price_usd: 0,
      buy_txn_count_24h: 0,
      sell_txn_count_24h: 0,
      holder_count: 0,
      has_twitter: false,
      has_website: false,
      has_telegram: false,
      source: 'geckoterminal',
    });
  }
  return tokens;
}

// ─── DexScreener search endpoint ───

interface DexSearchResponse {
  pairs?: DexScreenerPair[];
}

async function fetchDexScreenerSearch(query: string): Promise<TokenRecord[]> {
  const url = `https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(query)}`;
  const data = await fetchJSON<DexSearchResponse>(url, {
    rateLimiter: dexLimiter,
    label: `dex:search:${query}`,
    retries: 2,
  });
  if (!data?.pairs) return [];
  return data.pairs
    .filter(p => p.chainId === 'solana')
    .map(p => dexPairToToken(p))
    .filter((t): t is TokenRecord => t !== null);
}

// ─── DexScreener pairs by token address ───

async function fetchDexPairsByToken(mint: string): Promise<TokenRecord[]> {
  const url = `https://api.dexscreener.com/latest/dex/tokens/${mint}`;
  const data = await fetchJSON<DexSearchResponse>(url, {
    rateLimiter: dexLimiter,
    label: `dex:pairs:${mint.slice(0, 8)}`,
    retries: 2,
  });
  if (!data?.pairs) return [];
  return data.pairs
    .filter(p => p.chainId === 'solana')
    .map(p => dexPairToToken(p))
    .filter((t): t is TokenRecord => t !== null);
}

// ─── Cache Layer ───

const CACHE_DIR = 'cache';

function getCachedResponse<T>(key: string): T | null {
  const file = dataPath(`${CACHE_DIR}/${key}.json`);
  if (fs.existsSync(file)) {
    return JSON.parse(fs.readFileSync(file, 'utf-8'));
  }
  return null;
}

function setCachedResponse(key: string, data: unknown): void {
  const dir = dataPath(CACHE_DIR);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(dataPath(`${CACHE_DIR}/${key}.json`), JSON.stringify(data), 'utf-8');
}

// ─── Paginated Gecko Fetch with 429 Retry ───
// Unlike the raw fetchJSON, this retries the SAME PAGE on 429 instead of stopping

async function fetchGeckoPages(
  buildUrl: (page: number) => string,
  label: string,
  maxPages: number,
  startPage: number = 1,
): Promise<{ tokens: TokenRecord[]; lastPage: number }> {
  const allTokens: TokenRecord[] = [];
  let consecutiveEmpty = 0;
  let lastPage = startPage - 1;

  for (let page = startPage; page <= maxPages; page++) {
    const cacheKey = `${label}_p${page}`;
    const cached = getCachedResponse<TokenRecord[]>(cacheKey);
    if (cached) {
      allTokens.push(...cached);
      log(`  Cache hit: ${label} page ${page} (${cached.length} tokens)`);
      lastPage = page;
      continue;
    }

    const url = buildUrl(page);
    const data = await fetchJSON<GeckoPoolsWithIncludesResponse>(url, {
      rateLimiter: geckoLimiter,
      label: `${label}:p${page}`,
      retries: 5, // more retries for 429s
    });

    if (!data?.data || data.data.length === 0) {
      consecutiveEmpty++;
      log(`  ${label} page ${page}: 0 tokens (empty ${consecutiveEmpty}/3)`);
      if (consecutiveEmpty >= 3) {
        log(`  Stopping ${label} after ${consecutiveEmpty} consecutive empty pages`);
        break;
      }
      continue;
    }

    consecutiveEmpty = 0;
    lastPage = page;
    const tokens = data.data
      .map(p => geckoPoolToToken(p, data.included))
      .filter((t): t is TokenRecord => t !== null);

    setCachedResponse(cacheKey, tokens);
    allTokens.push(...tokens);
    log(`  ${label} page ${page}: ${tokens.length} tokens (total: ${allTokens.length})`);
  }

  return { tokens: allTokens, lastPage };
}

// ─── Main Discovery Pipeline ───

async function discoverUniverse(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 1: Token Universe Discovery');
  log('═══════════════════════════════════════════════════════');

  ensureDir('universe');
  ensureDir('cache');

  const progress = new ProgressTracker<DiscoveryProgress>('discovery_progress.json', {
    phase: 'discovery',
    geckoterminal_new_pools_page: 0,
    geckoterminal_top_pools_page: 0,
    dexscreener_profiles_done: false,
    dexscreener_boosts_done: false,
    jupiter_gems_done: false,
    total_tokens_discovered: 0,
    last_updated: new Date().toISOString(),
  });

  const allTokens: TokenRecord[] = readJSON<TokenRecord[]>('universe/universe_raw_partial.json') || [];
  const boostedMints = new Set<string>();
  const trendingMints = new Set<string>();
  if (allTokens.length > 0) {
    log(`Resuming with ${allTokens.length} tokens already discovered`);
  }

  const p = progress.get();

  // Basic plan: 10 pages per endpoint, 250 req/min. Use MANY sort variations
  // to maximize unique tokens (each sort returns different pools).
  const GECKO_MAX_PAGES_NEW_POOLS = envInt('GECKO_MAX_PAGES_NEW_POOLS', 200);
  const GECKO_MAX_PAGES_TOP_POOLS = envInt('GECKO_MAX_PAGES_TOP_POOLS', 200);
  const GECKO_MAX_PAGES_MISC = envInt('GECKO_MAX_PAGES_MISC', 10);

  // ─── 1. GeckoTerminal: New Pools ───
  log('─── GeckoTerminal: New Pools ───');
  {
    const { tokens, lastPage } = await fetchGeckoPages(
      page => `${geckoBaseUrl()}/networks/solana/new_pools?page=${page}&include=base_token`,
      'gecko_new_pools',
      GECKO_MAX_PAGES_NEW_POOLS,
      p.geckoterminal_new_pools_page + 1,
    );
    allTokens.push(...tokens);
    progress.update({ geckoterminal_new_pools_page: lastPage, total_tokens_discovered: deduplicateByMint(allTokens).length });
  }

  // ─── 2. GeckoTerminal: Top Pools by Volume ───
  log('─── GeckoTerminal: Top Pools by Volume ───');
  {
    const { tokens, lastPage } = await fetchGeckoPages(
      page => `${geckoBaseUrl()}/networks/solana/pools?page=${page}&sort=h24_volume_usd_desc&include=base_token`,
      'gecko_top_pools',
      GECKO_MAX_PAGES_TOP_POOLS,
      p.geckoterminal_top_pools_page + 1,
    );
    allTokens.push(...tokens);
    progress.update({ geckoterminal_top_pools_page: lastPage, total_tokens_discovered: deduplicateByMint(allTokens).length });
  }

  // ─── 3. GeckoTerminal: Trending Pools ───
  log('─── GeckoTerminal: Trending Pools ───');
  {
    const { tokens } = await fetchGeckoPages(
      page => `${geckoBaseUrl()}/networks/solana/trending_pools?page=${page}&include=base_token`,
      'gecko_trending',
      GECKO_MAX_PAGES_MISC,
    );
    allTokens.push(...tokens);
    for (const token of tokens) {
      if (token.mint && token.mint.length >= 32) trendingMints.add(token.mint);
    }
  }

  // ─── 3b. GeckoTerminal: Pools sorted by transaction count ───
  log('─── GeckoTerminal: Top Pools by Tx Count ───');
  {
    const { tokens } = await fetchGeckoPages(
      page => `${geckoBaseUrl()}/networks/solana/pools?page=${page}&sort=h24_tx_count_desc&include=base_token`,
      'gecko_top_txns',
      GECKO_MAX_PAGES_MISC,
    );
    allTokens.push(...tokens);
  }

  // Save checkpoint
  writeJSON('universe/universe_raw_partial.json', deduplicateByMint(allTokens));
  log(`After GeckoTerminal: ${deduplicateByMint(allTokens).length} unique tokens`);

  // ─── 4. DexScreener: Token Profiles + Boosts ───
  if (!p.dexscreener_profiles_done) {
    log('─── DexScreener: Token Profiles ───');
    const cacheKey = 'dex_profiles';
    let profiles = getCachedResponse<DexScreenerProfile[]>(cacheKey);
    if (!profiles) {
      profiles = await fetchDexScreenerProfiles();
      setCachedResponse(cacheKey, profiles);
    }
    log(`  ${profiles.length} DexScreener profiles`);

    const existingMints = new Set(allTokens.map(t => t.mint));
    const newMints = profiles
      .map(p => p.tokenAddress)
      .filter(m => m && m.length >= 32 && !existingMints.has(m));

    if (newMints.length > 0) {
      const dexTokens = await fetchDexScreenerTokenDetails(newMints);
      allTokens.push(...dexTokens);
      log(`  Fetched ${dexTokens.length} token details from profiles`);
    }
    progress.update({ dexscreener_profiles_done: true });
  }

  if (!p.dexscreener_boosts_done) {
    log('─── DexScreener: Boosted Tokens ───');
    const cacheKey = 'dex_boosts';
    let boosts = getCachedResponse<DexScreenerBoost[]>(cacheKey);
    if (!boosts) {
      boosts = await fetchDexScreenerBoosts();
      setCachedResponse(cacheKey, boosts);
    }
    log(`  ${boosts.length} DexScreener boosts`);

    const existingMints = new Set(allTokens.map(t => t.mint));
    for (const boost of boosts) {
      if (boost.tokenAddress && boost.tokenAddress.length >= 32) {
        boostedMints.add(boost.tokenAddress);
      }
    }
    const newMints = boosts
      .map(b => b.tokenAddress)
      .filter(m => m && m.length >= 32 && !existingMints.has(m));

    if (newMints.length > 0) {
      const dexTokens = await fetchDexScreenerTokenDetails(newMints);
      allTokens.push(...dexTokens);
      log(`  Fetched ${dexTokens.length} token details from boosts`);
    }
    progress.update({ dexscreener_boosts_done: true });
  }

  // ─── 5. DexScreener: Search with many queries for broad coverage ───
  log('─── DexScreener: Search Queries ───');
  const SEARCH_QUERIES = [
    // Common Solana DEX keywords that return different token sets
    'pump', 'sol', 'meme', 'pepe', 'doge', 'cat', 'dog', 'ai',
    'trump', 'elon', 'moon', 'inu', 'bonk', 'jup', 'ray',
    'wif', 'bome', 'popcat', 'wen', 'jto', 'pyth', 'orca',
    'tensor', 'marinade', 'drift', 'zeta', 'kamino', 'parcl',
    'render', 'helium', 'shadow', 'grass', 'nosana', 'access',
    'io', 'cloud', 'gpt', 'agent', 'nft', 'defi', 'swap',
    'baby', 'mini', 'mega', 'super', 'ultra', 'hyper', 'turbo',
    'alpha', 'beta', 'sigma', 'chad', 'wojak', 'frog',
    'bags', 'snipe', 'gem', 'diamond', 'gold', 'silver',
    'pumpswap', 'raydium', 'jupiter', 'meteora',
    'hawk', 'eagle', 'bull', 'bear', 'whale', 'shark',
    'laser', 'rocket', 'fire', 'flame', 'blaze',
  ];

  for (const query of SEARCH_QUERIES) {
    const cacheKey = `dex_search_${query}`;
    let searchTokens = getCachedResponse<TokenRecord[]>(cacheKey);
    if (!searchTokens) {
      searchTokens = await fetchDexScreenerSearch(query);
      setCachedResponse(cacheKey, searchTokens);
    }
    if (searchTokens.length > 0) {
      allTokens.push(...searchTokens);
    }
  }

  writeJSON('universe/universe_raw_partial.json', deduplicateByMint(allTokens));
  log(`After DexScreener search: ${deduplicateByMint(allTokens).length} unique tokens`);

  // ─── 6. Birdeye (optional): high-interest + trending feeds ───
  const birdeyeKey = getBirdeyeApiKey();
  if (birdeyeKey) {
    log('─── Birdeye: Token List + Trending ───');
    const BIRDEYE_MAX_PAGES = envInt('BIRDEYE_MAX_PAGES', 25);
    const BIRDEYE_LIMIT = envInt('BIRDEYE_PAGE_LIMIT', 50);

    for (let page = 1; page <= BIRDEYE_MAX_PAGES; page++) {
      const listCacheKey = `birdeye_list_p${page}`;
      let listTokens = getCachedResponse<TokenRecord[]>(listCacheKey);
      if (!listTokens) {
        listTokens = await fetchBirdeyeTokenListPage(page, BIRDEYE_LIMIT);
        setCachedResponse(listCacheKey, listTokens);
      }
      if (listTokens.length === 0) {
        if (page <= 3) log(`  birdeye token list page ${page}: empty`);
        break;
      }
      allTokens.push(...listTokens);
      if (page % 5 === 0) {
        log(`  birdeye token list page ${page}: +${listTokens.length} tokens`);
      }
    }

    for (let page = 1; page <= Math.min(BIRDEYE_MAX_PAGES, 10); page++) {
      const trendCacheKey = `birdeye_trending_p${page}`;
      let trendTokens = getCachedResponse<TokenRecord[]>(trendCacheKey);
      if (!trendTokens) {
        trendTokens = await fetchBirdeyeTrendingPage(page, BIRDEYE_LIMIT);
        setCachedResponse(trendCacheKey, trendTokens);
      }
      if (trendTokens.length === 0) break;
      allTokens.push(...trendTokens);
      for (const token of trendTokens) {
        if (token.mint && token.mint.length >= 32) trendingMints.add(token.mint);
      }
    }
    log(`After Birdeye: ${deduplicateByMint(allTokens).length} unique tokens`);
  } else {
    log('─── Birdeye: skipped (BIRDEYE_API_KEY not set) ───');
  }

  // ─── 7. Jupiter Gems ───
  if (!p.jupiter_gems_done) {
    log('─── Jupiter Gems (Graduation Feed) ───');
    const cacheKey = 'jupiter_gems';
    let gemTokens = getCachedResponse<TokenRecord[]>(cacheKey);
    if (!gemTokens) {
      gemTokens = await fetchJupiterGems();
      if (gemTokens.length > 0) setCachedResponse(cacheKey, gemTokens);
    }
    log(`  Jupiter gems: ${gemTokens.length} tokens`);
    if (gemTokens.length > 0) {
      allTokens.push(...gemTokens);
      progress.update({ jupiter_gems_done: true });
    } else {
      log('  WARNING: Jupiter gems returned empty; leaving jupiter_gems_done=false to retry later');
    }
  }

  // ─── 8. GeckoTerminal: Search with diverse queries for more coverage ───
  log('─── GeckoTerminal: Search Queries ───');
  const GECKO_SEARCH_QUERIES = [
    'pump', 'sol', 'meme', 'pepe', 'doge', 'cat', 'dog', 'ai',
    'bonk', 'wif', 'trump', 'moon', 'baby', 'inu', 'bags',
  ];
  for (const query of GECKO_SEARCH_QUERIES) {
    const cacheKey = `gecko_search_${query}`;
    let searchTokens = getCachedResponse<TokenRecord[]>(cacheKey);
    if (!searchTokens) {
      searchTokens = await fetchGeckoSearch(query);
      setCachedResponse(cacheKey, searchTokens);
    }
    if (searchTokens.length > 0) {
      allTokens.push(...searchTokens);
    }
  }

  writeJSON('universe/universe_raw_partial.json', deduplicateByMint(allTokens));

  // ─── 9. Cross-enrich: look up DexScreener for tokens with missing market metadata ───
  log('─── Cross-enrichment: DexScreener lookups for Gecko tokens ───');
  const deduped = deduplicateByMint(allTokens);
  const needsEnrichment = deduped.filter(t =>
    t.mint.length >= 32 &&
    (t.liquidity_usd === 0 || !t.pool_address || t.pool_address.length < 20)
  );
  log(`  ${needsEnrichment.length} tokens need enrichment`);

  // Enrich via DexScreener in batches (faster than GeckoTerminal)
  const enrichBatchSize = 30;
  const maxEnrich = Math.min(needsEnrichment.length, 1500);
  let enriched = 0;
  for (let i = 0; i < maxEnrich; i += enrichBatchSize) {
    const batch = needsEnrichment.slice(i, i + enrichBatchSize);
    const mints = batch.map(t => t.mint).filter(m => m.length >= 32);
    if (mints.length === 0) continue;

    const dexTokens = await fetchDexScreenerTokenDetails(mints);
    for (const dt of dexTokens) {
      const existing = deduped.find(t => t.mint === dt.mint);
      if (existing) {
        if (existing.liquidity_usd === 0 && dt.liquidity_usd > 0) existing.liquidity_usd = dt.liquidity_usd;
        if (existing.volume_24h_usd === 0 && dt.volume_24h_usd > 0) existing.volume_24h_usd = dt.volume_24h_usd;
        if ((!existing.pool_address || existing.pool_address.length < 20) && dt.pool_address) existing.pool_address = dt.pool_address;
        if (existing.price_usd === 0 && dt.price_usd > 0) existing.price_usd = dt.price_usd;
        if (!existing.has_twitter && dt.has_twitter) existing.has_twitter = true;
        if (!existing.has_website && dt.has_website) existing.has_website = true;
        if (!existing.has_telegram && dt.has_telegram) existing.has_telegram = true;
        enriched++;
      } else {
        allTokens.push(dt);
      }
    }

    if ((i / enrichBatchSize) % 10 === 0 && i > 0) {
      log(`  Enriched batch ${i / enrichBatchSize}: ${enriched} tokens updated`);
    }
  }
  log(`  Enrichment complete: ${enriched} tokens updated`);

  // ─── Final Merge + Save ───
  const universe = mergeUniverseByMint(allTokens, boostedMints, trendingMints);

  // Keep all tokens that have a valid mint (relaxed filter to maximize count)
  const validUniverse = universe.filter(t => t.mint.length >= 32);

  log('═══════════════════════════════════════════════════════');
  log(`Total raw tokens: ${allTokens.length}`);
  log(`After dedup: ${universe.length}`);
  log(`After validation: ${validUniverse.length}`);
  log('');
  log('Source breakdown:');
  const bySource = validUniverse.reduce((acc, t) => {
    acc[t.source] = (acc[t.source] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  for (const [source, count] of Object.entries(bySource)) {
    log(`  ${source}: ${count}`);
  }
  log('');

  const withLiquidity = validUniverse.filter(t => t.liquidity_usd > 0).length;
  const withVolume = validUniverse.filter(t => t.volume_24h_usd > 0).length;
  const withPool = validUniverse.filter(t => t.pool_address && t.pool_address.length >= 20).length;
  const withSocials = validUniverse.filter(t => t.has_twitter || t.has_website || t.has_telegram).length;
  const withBoostSignal = validUniverse.filter(t => t.interest_is_boosted).length;
  const withTrendSignal = validUniverse.filter(t => t.interest_is_trending).length;
  const multiSource = validUniverse.filter(t => (t.source_count || 1) >= 2).length;
  log(`Tokens with liquidity > 0: ${withLiquidity}`);
  log(`Tokens with volume > 0: ${withVolume}`);
  log(`Tokens with pool address: ${withPool}`);
  log(`Tokens with socials: ${withSocials}`);
  log(`Tokens with boost signal: ${withBoostSignal}`);
  log(`Tokens with trending signal: ${withTrendSignal}`);
  log(`Tokens seen on >=2 sources: ${multiSource}`);
  log('═══════════════════════════════════════════════════════');

  writeJSON('universe/universe_raw.json', validUniverse);
  writeCSV('universe/universe_raw.csv', validUniverse as unknown as Record<string, unknown>[]);

  // Clean up partial file
  const partialPath = dataPath('universe/universe_raw_partial.json');
  if (fs.existsSync(partialPath)) {
    fs.unlinkSync(partialPath);
  }

  progress.update({ total_tokens_discovered: validUniverse.length });

  log(`\n✓ Phase 1 complete: ${validUniverse.length} unique tokens discovered`);
  log(`  → universe/universe_raw.json`);
  log(`  → universe/universe_raw.csv`);
}

// ─── Entry Point ───
discoverUniverse().catch(err => {
  logError('Fatal error in universe discovery', err);
  process.exit(1);
});
