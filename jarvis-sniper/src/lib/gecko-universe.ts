/**
 * GeckoTerminal pool universe discovery (Solana)
 *
 * Purpose:
 * - Provide a reliable candidate set of pools/mints that *definitely* exist on GeckoTerminal,
 *   so Strategy Validation (real OHLCV) doesn't collapse when DexScreener discovery returns
 *   tokens that GeckoTerminal can't serve.
 *
 * Notes:
 * - Free GeckoTerminal API is rate-limited (~30 req/min). These endpoints are cheap and
 *   are only used to build the candidate list (OHLCV is fetched separately).
 */

import { geckoFetchWithProbe } from './gecko-fetch';
import { ServerCache } from './server-cache';
import { recordSourceHealth } from '@/lib/data-plane/health-store';
import { deriveRedundancyState, scoreSourceReliability } from '@/lib/data-plane/reliability';

export interface GeckoPoolCandidate {
  poolAddress: string;
  baseMint: string;
  baseSymbol: string;
  quoteMint: string;
  quoteSymbol: string;
  dexId: string;
  name: string;
  createdAtMs: number;
  volume24hUsd: number;
  liquidityUsd: number;
}

export interface GeckoUniverseProgressEvent {
  endpoint: string;
  page: number;
  pages: number;
  received: number;
}

const GECKO_BASE = 'https://api.geckoterminal.com/api/v2';

const EXCLUDE_MINTS = new Set<string>([
  // WSOL
  'So11111111111111111111111111111111111111112',
  // USDC / USDT
  'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
  'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
]);

function parseIdMint(id: unknown): string {
  if (typeof id !== 'string') return '';
  // Gecko relationships ids look like: "solana_<mint>"
  const parts = id.split('_');
  return parts.length >= 2 ? parts.slice(1).join('_') : '';
}

function safeNumber(v: unknown): number {
  const n = typeof v === 'number' ? v : Number.parseFloat(String(v ?? '0'));
  return Number.isFinite(n) ? n : 0;
}

async function fetchJson(url: string): Promise<any | null> {
  try {
    const { response, probe } = await geckoFetchWithProbe(url);
    const ok = response.ok;
    const reliabilityScore = scoreSourceReliability({
      ok,
      latencyMs: probe.latencyMs,
      httpStatus: probe.httpStatus,
      freshnessMs: 0,
      errorBudgetBurn: ok ? 0 : 1,
    });
    await recordSourceHealth({
      source: 'geckoterminal:universe',
      checkedAt: probe.fetchedAt,
      ok,
      freshnessMs: 0,
      latencyMs: probe.latencyMs,
      httpStatus: probe.httpStatus,
      reliabilityScore,
      errorBudgetBurn: ok ? 0 : 1,
      redundancyState: deriveRedundancyState(2),
    });
    if (!ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function toCandidate(pool: any): GeckoPoolCandidate | null {
  const attr = pool?.attributes ?? {};
  const rel = pool?.relationships ?? {};

  const poolAddress: string = String(attr.address ?? pool?.id?.split('_')?.[1] ?? '').trim();
  if (!poolAddress) return null;

  const baseMint = parseIdMint(rel?.base_token?.data?.id);
  const quoteMint = parseIdMint(rel?.quote_token?.data?.id);
  if (!baseMint || !quoteMint) return null;

  const baseSymbol: string = String(attr.base_token_symbol ?? '').trim();
  const quoteSymbol: string = String(attr.quote_token_symbol ?? '').trim();

  // Many Solana pools are expressed as SOL/token (WSOL as base token). For backtesting we
  // want the *non-excluded* asset as the "base mint" we score/backtest against.
  const baseExcluded = EXCLUDE_MINTS.has(baseMint);
  const quoteExcluded = EXCLUDE_MINTS.has(quoteMint);
  if (baseExcluded && quoteExcluded) return null;

  const primaryMint = baseExcluded ? quoteMint : baseMint;
  const primarySymbol = (baseExcluded ? quoteSymbol : baseSymbol).trim();
  const otherMint = baseExcluded ? baseMint : quoteMint;
  const otherSymbol = (baseExcluded ? baseSymbol : quoteSymbol).trim();

  const dexId: string = String(rel?.dex?.data?.id ?? '').trim();
  const name: string = String(attr.name ?? '').trim();

  const createdAtMs = attr.pool_created_at ? new Date(String(attr.pool_created_at)).getTime() : 0;
  const volume24hUsd = safeNumber(attr?.volume_usd?.h24);
  const liquidityUsd = safeNumber(attr?.reserve_in_usd);

  return {
    poolAddress,
    baseMint: primaryMint,
    baseSymbol: primarySymbol || primaryMint.slice(0, 6),
    quoteMint: otherMint,
    quoteSymbol: otherSymbol || otherMint.slice(0, 6),
    dexId,
    name: name || `${primarySymbol || primaryMint.slice(0, 6)} / ${otherSymbol || otherMint.slice(0, 6)}`,
    createdAtMs: Number.isFinite(createdAtMs) ? createdAtMs : 0,
    volume24hUsd,
    liquidityUsd,
  };
}

function isEligibleByAge(nowMs: number, createdAtMs: number, minAgeMs: number): boolean {
  if (!minAgeMs || minAgeMs <= 0) return true;
  if (!createdAtMs || !Number.isFinite(createdAtMs)) return true; // unknown; allow
  return nowMs - createdAtMs >= minAgeMs;
}

function upsertBestByLiquidity(
  map: Map<string, GeckoPoolCandidate>,
  c: GeckoPoolCandidate,
  nowMs: number,
  minAgeMs: number,
): void {
  const existing = map.get(c.baseMint);
  if (!existing) {
    map.set(c.baseMint, c);
    return;
  }

  const existingEligible = isEligibleByAge(nowMs, existing.createdAtMs, minAgeMs);
  const candidateEligible = isEligibleByAge(nowMs, c.createdAtMs, minAgeMs);

  // Prefer pools that are old enough to satisfy min-candles requirements.
  if (existingEligible !== candidateEligible) {
    if (candidateEligible) map.set(c.baseMint, c);
    return;
  }

  // Keep the candidate with higher liquidity; tie-break with 24h volume.
  if (c.liquidityUsd > existing.liquidityUsd) {
    map.set(c.baseMint, c);
    return;
  }
  if (c.liquidityUsd === existing.liquidityUsd && c.volume24hUsd > existing.volume24hUsd) {
    map.set(c.baseMint, c);
  }
}

async function fetchPoolsFromEndpoint(
  endpoint: string,
  pages: number,
  onProgress?: (event: GeckoUniverseProgressEvent) => void,
): Promise<GeckoPoolCandidate[]> {
  const out: GeckoPoolCandidate[] = [];
  let consecutiveFailures = 0;
  for (let page = 1; page <= pages; page++) {
    const url = `${GECKO_BASE}${endpoint}${endpoint.includes('?') ? '&' : '?'}page=${page}`;
    const json = await fetchJson(url);
    const data: any[] = json?.data;
    if (!Array.isArray(data) || data.length === 0) {
      consecutiveFailures += 1;
      // Don't give up on a single flaky page (timeouts/429 can happen).
      if (consecutiveFailures >= 2) break;
      onProgress?.({ endpoint, page, pages, received: 0 });
      continue;
    }
    consecutiveFailures = 0;
    let received = 0;
    for (const pool of data) {
      const c = toCandidate(pool);
      if (c) {
        out.push(c);
        received += 1;
      }
    }
    onProgress?.({ endpoint, page, pages, received });
  }
  return out;
}

const universeCache = new ServerCache<GeckoPoolCandidate[]>();
const UNIVERSE_TTL_MS = 5 * 60_000;

/**
 * Fetch a reasonably broad pool universe from GeckoTerminal.
 *
 * Returns one best pool per base mint (highest liquidity).
 */
export async function fetchGeckoSolanaPoolUniverse(
  max: number,
  opts?: {
    minAgeMs?: number;
    onProgress?: (event: GeckoUniverseProgressEvent) => void;
  },
): Promise<GeckoPoolCandidate[]> {
  const target = Math.max(10, Math.min(2000, Math.floor(max)));
  // 20 pools/page; cap pages to avoid runaway request counts on free tier.
  const pages = Math.max(2, Math.min(12, Math.ceil(target / 20)));
  const minAgeMs = Math.max(0, Number(opts?.minAgeMs ?? 0) || 0);

  // Server-side cache: universe discovery is expensive under Gecko rate limits.
  const cacheKey = `${target}:${pages}:${minAgeMs}`;
  const cached = universeCache.get(cacheKey);
  if (cached) return cached.slice(0, target);

  const [trending, newPools, topVolume, topTx] = await Promise.all([
    fetchPoolsFromEndpoint('/networks/solana/trending_pools', 1, opts?.onProgress),
    fetchPoolsFromEndpoint('/networks/solana/new_pools', pages, opts?.onProgress),
    fetchPoolsFromEndpoint('/networks/solana/pools?sort=h24_volume_usd_desc', pages, opts?.onProgress),
    fetchPoolsFromEndpoint('/networks/solana/pools?sort=h24_tx_count_desc', pages, opts?.onProgress),
  ]);

  // Prefer trending, then tx/volume leaders, then new pools.
  const byMint = new Map<string, GeckoPoolCandidate>();
  const nowMs = Date.now();
  for (const c of trending) upsertBestByLiquidity(byMint, c, nowMs, minAgeMs);
  for (const c of topTx) upsertBestByLiquidity(byMint, c, nowMs, minAgeMs);
  for (const c of topVolume) upsertBestByLiquidity(byMint, c, nowMs, minAgeMs);
  for (const c of newPools) upsertBestByLiquidity(byMint, c, nowMs, minAgeMs);

  const out = [...byMint.values()].slice(0, target);
  // Avoid caching obviously-broken small outputs (likely from transient 429/timeouts).
  if (out.length >= Math.min(20, Math.floor(target / 3))) {
    universeCache.set(cacheKey, out, UNIVERSE_TTL_MS);
  }
  return out;
}
