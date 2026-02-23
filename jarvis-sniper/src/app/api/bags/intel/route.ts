import { NextResponse } from 'next/server';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { safeImageUrl } from '@/lib/safe-url';

/**
 * Bags Intel (Server API)
 *
 * Uses real, upstream data only:
 * - Jupiter Data API: POST https://datapi.jup.ag/v1/pools/gems (bags.fun lists)
 * - Bags internal API: https://api2.bags.fm/api/v1 (creator + lifetime fees)
 *
 * We intentionally do NOT depend on DexScreener for bags.fun tokens because
 * many bags pools are not indexed there.
 */

const JUPITER_GEMS_URL = 'https://datapi.jup.ag/v1/pools/gems';
const BAGS_API2_BASE = 'https://api2.bags.fm/api/v1';

export type BagsIntelCategory = 'recent' | 'aboutToGraduate' | 'graduated' | 'topEarners';

interface BagsStatsWindow {
  priceChange?: number;
  volumeChange?: number;
  buyVolume?: number;
  sellVolume?: number;
  numBuys?: number;
  numSells?: number;
  numTraders?: number;
  numOrganicBuyers?: number;
  numNetBuyers?: number;
}

interface BagsAuditInfo {
  mintAuthorityDisabled?: boolean;
  freezeAuthorityDisabled?: boolean;
  topHoldersPercentage?: number;
  devMigrations?: number;
  devMints?: number;
}

interface BagsTokenInfo {
  id: string;
  name?: string;
  symbol?: string;
  icon?: string;
  website?: string;
  twitter?: string;
  telegram?: string;
  dev?: string;
  holderCount?: number;
  organicScore?: number;
  organicScoreLabel?: string;
  isVerified?: boolean;
  audit?: BagsAuditInfo;
  tags?: string[];
  createdAt?: string | number;
  fdv?: number;
  mcap?: number;
  usdPrice?: number;
  liquidity?: number;
  stats5m?: BagsStatsWindow;
  stats1h?: BagsStatsWindow;
  stats6h?: BagsStatsWindow;
  stats24h?: BagsStatsWindow;
  stats7d?: BagsStatsWindow;
  stats30d?: BagsStatsWindow;
  bondingCurve?: number;
  volume24h?: number;
  updatedAt?: string;
}

interface BagsGemsPool {
  id: string;
  createdAt?: string;
  liquidity?: number;
  bondingCurve?: number;
  volume24h?: number;
  updatedAt?: string;
  baseAsset?: BagsTokenInfo;
}

interface BagsGemsListsResponse {
  recent?: { pools?: BagsGemsPool[] };
  aboutToGraduate?: { pools?: BagsGemsPool[] };
  graduated?: { pools?: BagsGemsPool[] };
}

interface BagsCreatorEntry {
  wallet?: string;
  username?: string;
  pfp?: string;
  provider?: string;
  providerUsername?: string;
  royaltyBps?: number;
  isCreator?: boolean;
  bagsUsername?: string;
}

interface BagsCreatorResponse {
  success?: boolean;
  response?: BagsCreatorEntry[];
}

interface BagsTopEarnersResponse {
  success?: boolean;
  response?: Array<{
    token?: string;
    lifetimeFees?: string;
    tokenInfo?: BagsTokenInfo;
  }>;
}

interface BagsIntelToken {
  mint: string;
  symbol: string;
  name: string;
  logoUri: string | null;
  deployer: string | null;
  royaltyWallet: string | null;
  royaltyUsername: string | null;
  royaltyPfp: string | null;
  poolAddress: string | null;
  priceUsd: number;
  marketCap: number;
  liquidity: number;
  volume24h: number;
  volume1h: number;
  txnBuys1h: number;
  txnSells1h: number;
  txnBuys24h: number;
  txnSells24h: number;
  buySellRatio: number;
  priceChange1h: number;
  priceChange6h: number;
  priceChange24h: number;
  website: string | null;
  twitter: string | null;
  telegram: string | null;
  pairCreatedAt: number | null; // unix ms
  isBags: true;
  // Enrichment
  category: BagsIntelCategory;
  creatorUsername: string | null;
  creatorPfp: string | null;
  royaltyBps: number | null;
  lifetimeFeesLamports: number | null;
  // Scoring
  score: number;
  bondingCurveScore: number;
  holderDistributionScore: number;
  socialScore: number;
  activityScore: number;
  momentumScore: number;
  // Audit quick facts
  topHoldersPct: number | null;
  organicScore: number | null;
  mintAuthorityDisabled: boolean | null;
  freezeAuthorityDisabled: boolean | null;
}

function n(v: unknown, fallback = 0): number {
  const x = typeof v === 'string' ? Number(v) : (typeof v === 'number' ? v : NaN);
  return Number.isFinite(x) ? x : fallback;
}

function clamp(val: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, val));
}

function toUnixMs(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) {
    const sec = v > 1e12 ? Math.floor(v / 1000) : Math.floor(v);
    return sec * 1000;
  }
  if (typeof v === 'string') {
    const ms = Date.parse(v);
    if (Number.isFinite(ms)) return ms;
    const num = Number(v);
    if (Number.isFinite(num)) {
      const sec = num > 1e12 ? Math.floor(num / 1000) : Math.floor(num);
      return sec * 1000;
    }
  }
  return null;
}

function sumVolume(win?: BagsStatsWindow): number {
  return n(win?.buyVolume, 0) + n(win?.sellVolume, 0);
}

function sumTxns(win?: BagsStatsWindow): { buys: number; sells: number; total: number } {
  const buys = Math.max(0, Math.floor(n(win?.numBuys, 0)));
  const sells = Math.max(0, Math.floor(n(win?.numSells, 0)));
  return { buys, sells, total: buys + sells };
}

function calcBuySellRatio(buys: number, sells: number): number {
  if (sells > 0) return buys / sells;
  if (buys > 0) return buys;
  return 0;
}

function scoreFlowConsistency(vol1h: number, vol6h: number, vol24h: number): {
  score: number;
  stalePenalty: number;
  spikePenalty: number;
} {
  if (vol24h <= 0) {
    return { score: 0, stalePenalty: 0, spikePenalty: 0 };
  }

  const ratio1h = (vol1h * 24) / vol24h;
  const ratio6h = (vol6h * 4) / vol24h;

  const scoreFromRatio = (ratio: number): number => {
    if (ratio >= 0.6 && ratio <= 1.6) return 50;
    if (ratio >= 0.4 && ratio <= 2.2) return 38;
    if (ratio >= 0.25 && ratio <= 3.0) return 24;
    if (ratio >= 0.1 && ratio <= 4.0) return 14;
    return 6;
  };

  const s1h = scoreFromRatio(ratio1h);
  const s6h = scoreFromRatio(ratio6h);
  const score = clamp(Math.round(s1h * 0.45 + s6h * 0.55), 0, 100);

  const stalePenalty =
    vol24h >= 10_000 && ratio1h < 0.15 && ratio6h < 0.35
      ? -12
      : vol24h >= 5_000 && ratio1h < 0.2 && ratio6h < 0.45
        ? -8
        : 0;

  const spikePenalty =
    ratio1h > 4.0 && ratio6h < 0.8
      ? -10
      : ratio1h > 3.0 && ratio6h < 0.7
        ? -6
        : 0;

  return { score, stalePenalty, spikePenalty };
}

function normalizeTwitterUrl(raw: string | null): string | null {
  if (!raw) return null;
  const s = raw.trim();
  if (!s) return null;
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  // Accept @handle or handle
  const handle = s.startsWith('@') ? s.slice(1) : s;
  return `https://x.com/${handle}`;
}

function scoreToken(input: {
  bondingCurve: number;
  ageHours: number;
  volume24h: number;
  volume1h: number;
  volume6h: number;
  txns1h: number;
  buySellRatio: number;
  priceChange1h: number;
  priceChange24h: number;
  volumeChange1h: number;
  holderCount: number;
  topHoldersPct: number | null;
  organicScore: number;
  hasTwitter: boolean;
  hasWebsite: boolean;
  hasTelegram: boolean;
  hasCreator: boolean;
  royaltyBps: number | null;
  mintAuthorityDisabled: boolean | null;
  freezeAuthorityDisabled: boolean | null;
}): {
  score: number;
  bondingCurveScore: number;
  holderDistributionScore: number;
  socialScore: number;
  activityScore: number;
  momentumScore: number;
} {
  // Volume & maturity (0-100)
  const age = input.ageHours;
  const bc = clamp(input.bondingCurve, 0, 100);
  const vol24h = input.volume24h;
  const vol1h = input.volume1h;
  const vol6h = input.volume6h;
  const ageBucket =
    age >= 720 ? 10 :
    age >= 336 ? 8 :
    age >= 168 ? 7 :
    age >= 72 ? 6 :
    age >= 48 ? 5 :
    age >= 24 ? 4 :
    age >= 12 ? 3 :
    age >= 6 ? 2 : 1;
  const volBucket =
    vol24h >= 1_000_000 ? 24 :
    vol24h >= 500_000 ? 22 :
    vol24h >= 200_000 ? 20 :
    vol24h >= 100_000 ? 18 :
    vol24h >= 50_000 ? 16 :
    vol24h >= 20_000 ? 14 :
    vol24h >= 5_000 ? 11 :
    vol24h >= 1_000 ? 8 :
    vol24h >= 200 ? 5 :
    vol24h >= 50 ? 3 : 1;
  const flowConsistency = scoreFlowConsistency(vol1h, vol6h, vol24h);
  const sustainedFlowBucket = Math.round((flowConsistency.score / 100) * 24);
  const auditBonus =
    (input.mintAuthorityDisabled ? 5 : 0) +
    (input.freezeAuthorityDisabled ? 5 : 0);
  const bondingCurveScore = clamp(
    bc * 0.45 +
      volBucket +
      sustainedFlowBucket +
      ageBucket +
      auditBonus +
      flowConsistency.stalePenalty +
      flowConsistency.spikePenalty,
    0,
    100,
  );

  // Holder distribution (0-100)
  const holders = input.holderCount;
  const holderBucket =
    holders >= 20_000 ? 50 :
    holders >= 10_000 ? 45 :
    holders >= 5_000 ? 40 :
    holders >= 2_000 ? 34 :
    holders >= 1_000 ? 30 :
    holders >= 500 ? 25 :
    holders >= 200 ? 20 :
    holders >= 100 ? 15 :
    holders >= 50 ? 10 :
    holders >= 20 ? 6 : 2;
  const topPct = input.topHoldersPct;
  const distBucket = topPct == null ? 0 :
    topPct <= 20 ? 40 :
    topPct <= 25 ? 35 :
    topPct <= 30 ? 30 :
    topPct <= 35 ? 22 :
    topPct <= 40 ? 15 :
    topPct <= 50 ? 8 : 3;
  const organicBonus =
    input.organicScore >= 80 ? 10 :
    input.organicScore >= 60 ? 7 :
    input.organicScore >= 40 ? 4 :
    input.organicScore >= 20 ? 2 : 0;
  const holderDistributionScore = clamp(holderBucket + distBucket + organicBonus, 0, 100);

  // Social (0-100)
  let socialScore = 0;
  if (input.hasTwitter) socialScore += 35;
  if (input.hasWebsite) socialScore += 25;
  if (input.hasTelegram) socialScore += 25;
  if (input.hasCreator) socialScore += 10;
  if ((input.royaltyBps ?? 0) > 0) socialScore += 5;
  socialScore = clamp(socialScore, 0, 100);

  // Trading activity (0-100)
  const txns1h = input.txns1h;
  const txBucket =
    txns1h >= 1000 ? 40 :
    txns1h >= 500 ? 34 :
    txns1h >= 200 ? 28 :
    txns1h >= 80 ? 22 :
    txns1h >= 30 ? 16 :
    txns1h >= 10 ? 10 : 4;
  const ratio = input.buySellRatio;
  const ratioBucket =
    ratio >= 1.1 && ratio <= 2.8 ? 30 :
    ratio >= 1.0 && ratio <= 4.0 ? 22 :
    ratio > 0.6 ? 14 : 6;
  const vol1hBucket =
    vol1h >= 100_000 ? 30 :
    vol1h >= 50_000 ? 26 :
    vol1h >= 20_000 ? 22 :
    vol1h >= 10_000 ? 18 :
    vol1h >= 5_000 ? 14 :
    vol1h >= 1_000 ? 10 :
    vol1h >= 200 ? 6 : 2;
  const activityScore = clamp(txBucket + ratioBucket + vol1hBucket + Math.round(flowConsistency.score * 0.12), 0, 100);

  // Momentum (0-100)
  const pc1h = input.priceChange1h;
  const pc24h = input.priceChange24h;
  const base =
    pc1h > 50 ? 90 :
    pc1h > 20 ? 80 :
    pc1h > 10 ? 70 :
    pc1h > 5 ? 62 :
    pc1h > 0 ? 55 :
    pc1h > -5 ? 45 :
    pc1h > -15 ? 35 : 20;
  const adj =
    pc24h > 100 ? 10 :
    pc24h > 50 ? 7 :
    pc24h > 10 ? 4 :
    pc24h > 0 ? 2 :
    pc24h < -20 ? -10 :
    pc24h < -10 ? -7 :
    pc24h < 0 ? -3 : 0;
  const surge = input.volumeChange1h;
  const surgeAdj = surge > 50 ? 6 : surge > 10 ? 4 : surge > 0 ? 2 : 0;
  const momentumScore = clamp(base + adj + surgeAdj, 0, 100);

  const overall = Math.round(
    bondingCurveScore * 0.25 +
    holderDistributionScore * 0.20 +
    socialScore * 0.15 +
    activityScore * 0.25 +
    momentumScore * 0.15,
  );

  return {
    score: clamp(overall, 0, 100),
    bondingCurveScore: Math.round(bondingCurveScore),
    holderDistributionScore: Math.round(holderDistributionScore),
    socialScore: Math.round(socialScore),
    activityScore: Math.round(activityScore),
    momentumScore: Math.round(momentumScore),
  };
}

async function fetchWithTimeout(url: string, opts?: RequestInit, timeoutMs = 10000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...opts, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function fetchGemsLists(minMcap = 0): Promise<Record<'recent' | 'aboutToGraduate' | 'graduated', BagsGemsPool[]>> {
  try {
    const res = await fetchWithTimeout(
      JUPITER_GEMS_URL,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recent: { launchpads: ['bags.fun'], minMcap },
          aboutToGraduate: { launchpads: ['bags.fun'], minMcap },
          graduated: { launchpads: ['bags.fun'], minMcap },
        }),
      },
      15000,
    );

    if (!res.ok) return { recent: [], aboutToGraduate: [], graduated: [] };
    const json = (await res.json()) as BagsGemsListsResponse;
    return {
      recent: Array.isArray(json?.recent?.pools) ? json.recent.pools : [],
      aboutToGraduate: Array.isArray(json?.aboutToGraduate?.pools) ? json.aboutToGraduate.pools : [],
      graduated: Array.isArray(json?.graduated?.pools) ? json.graduated.pools : [],
    };
  } catch {
    return { recent: [], aboutToGraduate: [], graduated: [] };
  }
}

async function fetchTopEarners(): Promise<Array<{ mint: string; lifetimeFeesLamports: number; tokenInfo: BagsTokenInfo }>> {
  try {
    const res = await fetchWithTimeout(
      `${BAGS_API2_BASE}/token-launch/top-tokens/lifetime-fees`,
      { headers: { Accept: 'application/json' } },
      15000,
    );
    if (!res.ok) return [];
    const json = (await res.json()) as BagsTopEarnersResponse;
    const items = Array.isArray(json?.response) ? json.response : [];
    return items
      .map((it) => ({
        mint: it?.tokenInfo?.id || it?.token || '',
        lifetimeFeesLamports: Math.max(0, Math.floor(n(it?.lifetimeFees, 0))),
        tokenInfo: it?.tokenInfo as BagsTokenInfo,
      }))
      .filter((x) => !!x.mint && !!x.tokenInfo);
  } catch {
    return [];
  }
}

async function fetchCreatorEntries(mint: string): Promise<BagsCreatorEntry[]> {
  try {
    const res = await fetchWithTimeout(
      `${BAGS_API2_BASE}/token-launch/creator/v3?tokenMint=${mint}`,
      { headers: { Accept: 'application/json' } },
      8000,
    );
    if (!res.ok) return [];
    const json = (await res.json()) as BagsCreatorResponse;
    const arr = Array.isArray(json?.response) ? json.response : [];
    return arr;
  } catch {
    return [];
  }
}

function pickCreator(entries: BagsCreatorEntry[]): BagsCreatorEntry | null {
  if (!entries || entries.length === 0) return null;
  return entries.find((x) => x.isCreator) || entries[0] || null;
}

function pickRoyalty(entries: BagsCreatorEntry[]): BagsCreatorEntry | null {
  if (!entries || entries.length === 0) return null;
  const withRoyalty = entries
    .filter((e) => Number.isFinite(n(e?.royaltyBps, NaN)) && n(e?.royaltyBps, 0) > 0)
    .sort((a, b) => n(b?.royaltyBps, 0) - n(a?.royaltyBps, 0));
  if (withRoyalty.length > 0) return withRoyalty[0] || null;
  return null;
}

async function mapWithConcurrency<T, R>(
  items: T[],
  concurrency: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let idx = 0;

  const workers = Array.from({ length: Math.max(1, concurrency) }, async () => {
    while (true) {
      const cur = idx;
      idx += 1;
      if (cur >= items.length) break;
      results[cur] = await fn(items[cur]);
    }
  });

  await Promise.allSettled(workers);
  return results;
}

// In-memory cache (shared across requests within the same worker), keyed by requested limit.
const cacheByLimit = new Map<number, { data: unknown; ts: number }>();
const CACHE_TTL_MS = 30_000; // 30s

export async function GET(request: Request) {
  const rawLimit = Number(new URL(request.url).searchParams.get('limit') ?? '');
  const limitSize =
    Number.isFinite(rawLimit) && rawLimit > 0
      ? clamp(Math.floor(rawLimit), 20, 500)
      : 200;

  // Rate limiting
  const ip = getClientIp(request);
  const rl = await apiRateLimiter.check(ip);
  if (!rl.allowed) {
    return NextResponse.json(
      { error: 'Rate limit exceeded', retryAfter: rl.retryAfterMs },
      { status: 429 },
    );
  }

  const cached = cacheByLimit.get(limitSize);
  if (cached && Date.now() - cached.ts < CACHE_TTL_MS) {
    return NextResponse.json(cached.data, {
      headers: { 'X-Cache': 'HIT', 'Cache-Control': 'public, s-maxage=30' },
    });
  }

  try {
    const [lists, topEarners] = await Promise.all([
      fetchGemsLists(0),
      fetchTopEarners(),
    ]);

    // Build a candidate set with categories.
    const byMint = new Map<string, { info: BagsTokenInfo; category: BagsIntelCategory; lifetimeFeesLamports: number | null; poolAddress: string | null }>();

    const ingestPools = (category: BagsIntelCategory, pools: BagsGemsPool[]) => {
      for (const p of pools) {
        const info = p?.baseAsset;
        const mint = info?.id;
        if (!mint) continue;
        const mergedInfo: BagsTokenInfo = {
          ...info,
          // Some pool-level metrics live on the pool object, not baseAsset.
          createdAt: p.createdAt ?? info.createdAt,
          updatedAt: p.updatedAt ?? info.updatedAt,
          liquidity: p.liquidity ?? info.liquidity,
          bondingCurve: p.bondingCurve ?? info.bondingCurve,
          // Optional, but when present it's better than missing window stats.
          volume24h: p.volume24h ?? info.volume24h,
        };
        const existing = byMint.get(mint);
        if (!existing) {
          byMint.set(mint, { info: mergedInfo, category, lifetimeFeesLamports: null, poolAddress: p.id || null });
        } else {
          // Keep first-seen category (recent/aboutToGraduate/graduated), but merge in any missing fields.
          byMint.set(mint, {
            ...existing,
            info: { ...mergedInfo, ...existing.info },
            poolAddress: existing.poolAddress || p.id || null,
          });
        }
      }
    };

    ingestPools('recent', lists.recent);
    ingestPools('aboutToGraduate', lists.aboutToGraduate);
    ingestPools('graduated', lists.graduated);

    // Pull in established "winners" to support deeper intel coverage (top-200 view).
    const topEarnersLimited = topEarners.slice(0, 250);
    for (const e of topEarnersLimited) {
      const mint = e.mint;
      const existing = byMint.get(mint);
      byMint.set(mint, {
        info: existing ? { ...existing.info, ...e.tokenInfo } : e.tokenInfo,
        category: existing?.category ?? 'topEarners',
        lifetimeFeesLamports: e.lifetimeFeesLamports,
        poolAddress: existing?.poolAddress ?? null,
      });
    }

    const candidates = [...byMint.values()];

    // Enrich creator info for each candidate (bounded concurrency, best-effort).
    const creatorPairs = await mapWithConcurrency(candidates, 10, async (c) => ({
      mint: c.info.id,
      entries: await fetchCreatorEntries(c.info.id),
    }));

    const creatorByMint = new Map<string, BagsCreatorEntry[]>(
      creatorPairs.map((p) => [p.mint, p.entries]),
    );

    const tokens: BagsIntelToken[] = candidates.map((c) => {
      const info = c.info;
      const mint = info.id;
      const createdMs = toUnixMs(info.createdAt);
      const ageHours = createdMs ? Math.max(0, (Date.now() - createdMs) / 3600000) : 0;

      const stats1h = info.stats1h;
      const stats6h = info.stats6h;
      const stats24h = info.stats24h;

      const vol24h = sumVolume(stats24h) || n(info.volume24h, 0);
      const vol1h = sumVolume(stats1h);
      const vol6h = sumVolume(stats6h);

      const tx1h = sumTxns(stats1h);
      const tx24h = sumTxns(stats24h);
      const ratio = calcBuySellRatio(tx1h.buys, tx1h.sells);

      const entries = creatorByMint.get(mint) || [];
      const creator = pickCreator(entries);
      const royalty = pickRoyalty(entries);
      const creatorUsername = creator?.providerUsername || creator?.username || null;
      const royaltyUsername = royalty?.providerUsername || royalty?.username || null;
      const royaltyBps = royalty?.royaltyBps ?? creator?.royaltyBps ?? null;

      const twitterUrl = normalizeTwitterUrl(
        info.twitter ||
        (creator?.provider === 'twitter' ? creator?.providerUsername : null) ||
        (royalty?.provider === 'twitter' ? royalty?.providerUsername : null) ||
        null,
      );

      const topHoldersPct = Number.isFinite(n(info.audit?.topHoldersPercentage, NaN))
        ? n(info.audit?.topHoldersPercentage, NaN)
        : null;

      const mintAuthorityDisabled =
        typeof info.audit?.mintAuthorityDisabled === 'boolean' ? info.audit.mintAuthorityDisabled : null;
      const freezeAuthorityDisabled =
        typeof info.audit?.freezeAuthorityDisabled === 'boolean' ? info.audit.freezeAuthorityDisabled : null;

      const bondingCurve = n(info.bondingCurve, 0);
      const scoring = scoreToken({
        bondingCurve,
        ageHours,
        volume24h: vol24h,
        volume1h: vol1h,
        volume6h: vol6h,
        txns1h: tx1h.total,
        buySellRatio: ratio,
        priceChange1h: n(stats1h?.priceChange, 0),
        priceChange24h: n(stats24h?.priceChange, 0),
        volumeChange1h: n(stats1h?.volumeChange, 0),
        holderCount: n(info.holderCount, 0),
        topHoldersPct,
        organicScore: n(info.organicScore, 0),
        hasTwitter: !!twitterUrl,
        hasWebsite: !!info.website,
        hasTelegram: !!info.telegram,
        hasCreator: !!creatorUsername,
        royaltyBps,
        mintAuthorityDisabled,
        freezeAuthorityDisabled,
      });

      const marketCapRaw = n(info.mcap, NaN);
      const fdvRaw = n(info.fdv, NaN);
      const marketCap = Number.isFinite(marketCapRaw) ? marketCapRaw : (Number.isFinite(fdvRaw) ? fdvRaw : 0);

      return {
        mint,
        symbol: info.symbol || '???',
        name: info.name || info.symbol || 'Unknown',
        // Prevent mixed-content/CSP breakage from upstream icon hosts.
        logoUri: safeImageUrl(info.icon) || null,
        deployer: creator?.wallet || info.dev || null,
        royaltyWallet: royalty?.wallet || null,
        royaltyUsername,
        royaltyPfp: safeImageUrl(royalty?.pfp) || null,
        poolAddress: c.poolAddress || mint,
        priceUsd: n(info.usdPrice, 0),
        marketCap,
        liquidity: n(info.liquidity, 0),
        volume24h: vol24h,
        volume1h: vol1h,
        txnBuys1h: tx1h.buys,
        txnSells1h: tx1h.sells,
        txnBuys24h: tx24h.buys,
        txnSells24h: tx24h.sells,
        buySellRatio: ratio,
        priceChange1h: n(stats1h?.priceChange, 0),
        priceChange6h: n(stats6h?.priceChange, 0),
        priceChange24h: n(stats24h?.priceChange, 0),
        website: info.website || null,
        twitter: twitterUrl,
        telegram: info.telegram || null,
        pairCreatedAt: createdMs,
        isBags: true,
        category: c.category,
        creatorUsername,
        creatorPfp: safeImageUrl(creator?.pfp) || null,
        royaltyBps,
        lifetimeFeesLamports: c.lifetimeFeesLamports,
        score: scoring.score,
        bondingCurveScore: scoring.bondingCurveScore,
        holderDistributionScore: scoring.holderDistributionScore,
        socialScore: scoring.socialScore,
        activityScore: scoring.activityScore,
        momentumScore: scoring.momentumScore,
        topHoldersPct,
        organicScore: Number.isFinite(n(info.organicScore, NaN)) ? n(info.organicScore, NaN) : null,
        mintAuthorityDisabled,
        freezeAuthorityDisabled,
      };
    });

    tokens.sort((a, b) => b.score - a.score);
    const limited = tokens.slice(0, limitSize);

    const responseData = {
      tokens: limited,
      count: limited.length,
      requestedLimit: limitSize,
      totalAvailable: tokens.length,
      source: 'bags.fm+datapi',
      timestamp: Date.now(),
    };

    cacheByLimit.set(limitSize, { data: responseData, ts: Date.now() });

    return NextResponse.json(responseData, {
      headers: { 'X-Cache': 'MISS', 'Cache-Control': 'public, s-maxage=30' },
    });
  } catch (error) {
    console.error('[BagsIntel] Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch bags intelligence', tokens: [], count: 0 },
      { status: 500 },
    );
  }
}
