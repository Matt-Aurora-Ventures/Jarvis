/**
 * Bags.fm Unified Data Service
 *
 * Combines three data sources for comprehensive bags token intelligence:
 * 1. Jupiter Gems API (datapi.jup.ag) - Primary: 200+ tokens, rich metadata
 * 2. api2.bags.fm internal API - Creator info, holder data, fees
 * 3. Helius DAS - Token metadata fallback (name, description, image)
 *
 * All bags tokens have LOCKED liquidity (bags.fm enforces this), so
 * liquidity is NOT a risk factor — it's always safe.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface BagsTokenEnriched {
  // Core identity
  mint: string;
  symbol: string;
  name: string;
  description?: string;
  icon?: string;

  // Creator / project
  creator?: {
    wallet?: string;
    username?: string;
    pfp?: string;
    twitter?: string;
    website?: string;
    royaltyBps?: number; // basis points
  };

  // Market data
  price_usd: number;
  market_cap: number;
  volume_24h: number;
  volume_6h: number;
  volume_1h: number;
  liquidity: number; // always locked on bags

  // Token metrics
  holderCount: number;
  organicScore: number; // Jupiter's organic score (0-100)
  topHolderPct?: number;

  // Time data
  createdAt: number; // unix seconds
  ageHours: number;

  // Multi-timeframe stats from Jupiter
  stats?: {
    '1h'?: JupiterTimeframeStat;
    '6h'?: JupiterTimeframeStat;
    '24h'?: JupiterTimeframeStat;
  };

  // Scoring
  kr8tivScore: number;
  scoreTier: ScoreTier;
  scoreBreakdown: ScoreBreakdown;

  // Classification
  isNewLaunch: boolean;  // < 48h old
  isEstablished: boolean; // > 7d old with volume
  isVerified?: boolean;
  auditStatus?: string;

  // Social
  twitterUrl?: string;
  websiteUrl?: string;
  telegramUrl?: string;
}

export interface JupiterTimeframeStat {
  buyers?: number;
  sellers?: number;
  volume?: number;
  volumeOrganic?: number;
  priceChange?: number;
  txCount?: number;
}

export interface ScoreBreakdown {
  community: number;    // holder count, distribution, organic buyers
  momentum: number;     // volume trends, price action, buy/sell ratio
  longevity: number;    // age, sustained activity, volume persistence
  social: number;       // twitter, website, creator identity
  builder: number;      // creator history, royalties, project quality
}

export type ScoreTier = 'exceptional' | 'strong' | 'average' | 'weak' | 'poor';

// ─── Jupiter Gems API ────────────────────────────────────────────────────────

const JUPITER_GEMS_URL = 'https://datapi.jup.ag/v1/pools/gems';

interface JupiterGemsRequest {
  launchpads: string[];
  sortBy?: string;
  sortDir?: 'asc' | 'desc';
  offset?: number;
  limit?: number;
}

interface JupiterGemsToken {
  mint?: string;
  address?: string;
  name?: string;
  symbol?: string;
  icon?: string;
  twitter?: string;
  website?: string;
  telegram?: string;
  devWallet?: string;
  devRoyaltyBps?: number;
  description?: string;
  holderCount?: number;
  organicScore?: number;
  isVerified?: boolean;
  auditStatus?: string;
  marketCap?: number;
  liquidity?: number;
  price?: number;
  createdAt?: number | string;
  stats?: Record<string, any>;
  pool?: string;
  poolAddress?: string;
  creator?: {
    wallet?: string;
    username?: string;
    pfp?: string;
  };
}

async function fetchJupiterGems(
  offset = 0,
  limit = 100,
  sortBy = 'marketCap',
): Promise<JupiterGemsToken[]> {
  try {
    const body: JupiterGemsRequest = {
      launchpads: ['bags.fun'],
      sortBy,
      sortDir: 'desc',
      offset,
      limit: Math.min(limit, 100), // Jupiter caps at 100 per request
    };

    const res = await fetch(JUPITER_GEMS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });

    if (!res.ok) {
      console.warn(`[BagsData] Jupiter gems API returned ${res.status}`);
      return [];
    }

    const data = await res.json();
    // Response could be { tokens: [...] } or direct array
    return Array.isArray(data) ? data : (data.tokens || data.data || data.pools || []);
  } catch (err) {
    console.error('[BagsData] Jupiter gems fetch failed:', err);
    return [];
  }
}

/**
 * Fetch ALL bags tokens (up to `total` count) via pagination.
 * Jupiter caps at 100 per request, so we batch.
 */
async function fetchAllJupiterGems(total = 200): Promise<JupiterGemsToken[]> {
  const batchSize = 100;
  const batches = Math.ceil(total / batchSize);
  const results: JupiterGemsToken[] = [];

  // Fetch first batch immediately
  const first = await fetchJupiterGems(0, batchSize);
  results.push(...first);

  // If we need more and first batch was full, fetch remaining in parallel
  if (batches > 1 && first.length >= batchSize) {
    const remaining = await Promise.allSettled(
      Array.from({ length: batches - 1 }, (_, i) =>
        fetchJupiterGems((i + 1) * batchSize, batchSize),
      ),
    );

    for (const result of remaining) {
      if (result.status === 'fulfilled') {
        results.push(...result.value);
      }
    }
  }

  return results;
}

// ─── api2.bags.fm Enrichment ─────────────────────────────────────────────────

const BAGS_API2_BASE = 'https://api2.bags.fm/api/v1';

interface BagsCreatorInfo {
  wallet?: string;
  username?: string;
  pfp?: string;
  royaltyBps?: number;
  provider?: string;
}

async function fetchBagsCreator(mint: string): Promise<BagsCreatorInfo | null> {
  try {
    const res = await fetch(
      `${BAGS_API2_BASE}/token-launch/creator/v3?tokenMint=${mint}`,
      { signal: AbortSignal.timeout(8000) },
    );
    if (!res.ok) return null;
    const data = await res.json();
    return {
      wallet: data.wallet || data.creator,
      username: data.username || data.name,
      pfp: data.pfp || data.image,
      royaltyBps: data.royaltyBps,
      provider: data.provider,
    };
  } catch {
    return null;
  }
}

interface BagsTopHolder {
  address: string;
  amount: number;
  pct: number;
  label?: string;
  labelType?: string;
}

async function fetchBagsTopHolders(mint: string): Promise<BagsTopHolder[]> {
  try {
    const res = await fetch(
      `${BAGS_API2_BASE}/token/${mint}/top-holders`,
      { signal: AbortSignal.timeout(8000) },
    );
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data.holders || data.data || []);
  } catch {
    return [];
  }
}

// ─── Scoring Engine ──────────────────────────────────────────────────────────

/**
 * Y Combinator-style business assessment scoring.
 *
 * Key principle: bags.fm tokens have LOCKED liquidity, so liquidity
 * is NOT a risk factor. Instead we focus on:
 * - Community (holders, organic buyers, distribution)
 * - Momentum (volume trends, buy/sell ratio, price action)
 * - Longevity (age, sustained activity)
 * - Social (twitter, website, creator transparency)
 * - Builder (creator identity, royalty setup, project quality)
 */
function calculateKR8TIVScore(token: JupiterGemsToken): {
  score: number;
  tier: ScoreTier;
  breakdown: ScoreBreakdown;
} {
  const breakdown: ScoreBreakdown = {
    community: 0,
    momentum: 0,
    longevity: 0,
    social: 0,
    builder: 0,
  };

  // ── Community Score (0-25) ──
  const holders = token.holderCount || 0;
  if (holders >= 5000) breakdown.community = 25;
  else if (holders >= 2000) breakdown.community = 22;
  else if (holders >= 1000) breakdown.community = 19;
  else if (holders >= 500) breakdown.community = 16;
  else if (holders >= 200) breakdown.community = 13;
  else if (holders >= 100) breakdown.community = 10;
  else if (holders >= 50) breakdown.community = 7;
  else if (holders >= 20) breakdown.community = 4;
  else breakdown.community = 2;

  // Organic score bonus (Jupiter's organic trading score)
  const organic = token.organicScore || 0;
  if (organic >= 80) breakdown.community = Math.min(25, breakdown.community + 5);
  else if (organic >= 50) breakdown.community = Math.min(25, breakdown.community + 3);

  // ── Momentum Score (0-25) ──
  const stats24h = token.stats?.['24h'] || {};
  const stats1h = token.stats?.['1h'] || {};
  const volume24h = stats24h.volume || parseFloat(String(token.marketCap || 0)) * 0.01;
  const mcap = token.marketCap || 0;

  // Volume to market cap ratio (healthy = 5-20%)
  const volMcapRatio = mcap > 0 ? volume24h / mcap : 0;
  if (volMcapRatio >= 0.2) breakdown.momentum = 12;
  else if (volMcapRatio >= 0.1) breakdown.momentum = 10;
  else if (volMcapRatio >= 0.05) breakdown.momentum = 8;
  else if (volMcapRatio >= 0.01) breakdown.momentum = 5;
  else breakdown.momentum = 2;

  // Buy/sell ratio (healthy = 1.0-2.5)
  const buyers = stats24h.buyers || 0;
  const sellers = stats24h.sellers || 0;
  if (buyers > 0 && sellers > 0) {
    const bsRatio = buyers / sellers;
    if (bsRatio >= 1.2 && bsRatio <= 3.0) breakdown.momentum += 8;
    else if (bsRatio >= 1.0 && bsRatio <= 5.0) breakdown.momentum += 5;
    else if (bsRatio > 0.5) breakdown.momentum += 3;
  } else if (buyers > 0) {
    breakdown.momentum += 4; // only buyers = early signal
  }

  // Price momentum (positive = good)
  const priceChange = stats24h.priceChange || 0;
  if (priceChange > 50) breakdown.momentum += 5;
  else if (priceChange > 10) breakdown.momentum += 4;
  else if (priceChange > 0) breakdown.momentum += 3;
  else if (priceChange > -10) breakdown.momentum += 2;
  // Negative momentum doesn't add points

  breakdown.momentum = Math.min(25, breakdown.momentum);

  // ── Longevity Score (0-20) ──
  const createdAtRaw = token.createdAt;
  let ageHours = 0;
  if (createdAtRaw) {
    const createdMs = typeof createdAtRaw === 'string'
      ? new Date(createdAtRaw).getTime()
      : (createdAtRaw > 1e12 ? createdAtRaw : createdAtRaw * 1000);
    ageHours = Math.max(0, (Date.now() - createdMs) / 3600000);
  }

  // Age-based longevity
  if (ageHours >= 720) breakdown.longevity = 14; // 30d+
  else if (ageHours >= 336) breakdown.longevity = 12; // 14d+
  else if (ageHours >= 168) breakdown.longevity = 10; // 7d+
  else if (ageHours >= 72) breakdown.longevity = 8; // 3d+
  else if (ageHours >= 48) breakdown.longevity = 6; // 2d+
  else if (ageHours >= 24) breakdown.longevity = 4; // 1d+
  else breakdown.longevity = 2; // brand new

  // Volume persistence bonus (still trading after days = good sign)
  if (ageHours > 72 && volume24h > 1000) breakdown.longevity += 3;
  if (ageHours > 168 && volume24h > 5000) breakdown.longevity += 3;
  breakdown.longevity = Math.min(20, breakdown.longevity);

  // ── Social Score (0-15) ──
  if (token.twitter) breakdown.social += 6;
  if (token.website) breakdown.social += 5;
  if (token.telegram) breakdown.social += 4;
  breakdown.social = Math.min(15, breakdown.social);

  // ── Builder Score (0-15) ──
  const hasCreator = !!(token.devWallet || token.creator?.wallet);
  const hasUsername = !!(token.creator?.username);
  const hasRoyalty = (token.devRoyaltyBps || 0) > 0;
  const hasDescription = !!(token.description && token.description.length > 20);

  if (hasCreator) breakdown.builder += 4;
  if (hasUsername) breakdown.builder += 3;
  if (hasRoyalty) breakdown.builder += 3; // royalties = committed dev
  if (hasDescription) breakdown.builder += 3;
  if (token.isVerified) breakdown.builder += 2;
  breakdown.builder = Math.min(15, breakdown.builder);

  // ── Total ──
  const score = Math.min(100, Math.max(0,
    breakdown.community +
    breakdown.momentum +
    breakdown.longevity +
    breakdown.social +
    breakdown.builder
  ));

  const tier = getScoreTier(score);

  return { score, tier, breakdown };
}

function getScoreTier(score: number): ScoreTier {
  if (score >= 85) return 'exceptional';
  if (score >= 70) return 'strong';
  if (score >= 50) return 'average';
  if (score >= 30) return 'weak';
  return 'poor';
}

// ─── Token Normalization ─────────────────────────────────────────────────────

function normalizeToken(raw: JupiterGemsToken): BagsTokenEnriched {
  const mint = raw.mint || raw.address || '';

  const createdAtRaw = raw.createdAt;
  let createdAtSec = Date.now() / 1000;
  if (createdAtRaw) {
    if (typeof createdAtRaw === 'string') {
      createdAtSec = new Date(createdAtRaw).getTime() / 1000;
    } else {
      createdAtSec = createdAtRaw > 1e12 ? createdAtRaw / 1000 : createdAtRaw;
    }
  }
  const ageHours = Math.max(0, (Date.now() / 1000 - createdAtSec) / 3600);

  const stats24h = raw.stats?.['24h'] || {};
  const stats6h = raw.stats?.['6h'] || {};
  const stats1h = raw.stats?.['1h'] || {};

  const { score, tier, breakdown } = calculateKR8TIVScore(raw);

  return {
    mint,
    symbol: raw.symbol || '???',
    name: raw.name || raw.symbol || 'Unknown Token',
    description: raw.description,
    icon: raw.icon,

    creator: {
      wallet: raw.devWallet || raw.creator?.wallet,
      username: raw.creator?.username,
      pfp: raw.creator?.pfp,
      twitter: raw.twitter,
      website: raw.website,
      royaltyBps: raw.devRoyaltyBps,
    },

    price_usd: raw.price || 0,
    market_cap: raw.marketCap || 0,
    volume_24h: stats24h.volume || 0,
    volume_6h: stats6h.volume || 0,
    volume_1h: stats1h.volume || 0,
    liquidity: raw.liquidity || 0,

    holderCount: raw.holderCount || 0,
    organicScore: raw.organicScore || 0,

    createdAt: createdAtSec,
    ageHours,

    stats: {
      '1h': stats1h,
      '6h': stats6h,
      '24h': stats24h,
    },

    kr8tivScore: score,
    scoreTier: tier,
    scoreBreakdown: breakdown,

    isNewLaunch: ageHours < 48,
    isEstablished: ageHours > 168 && (stats24h.volume || 0) > 1000,
    isVerified: raw.isVerified,
    auditStatus: raw.auditStatus,

    twitterUrl: raw.twitter ? (raw.twitter.startsWith('http') ? raw.twitter : `https://x.com/${raw.twitter}`) : undefined,
    websiteUrl: raw.website,
    telegramUrl: raw.telegram,
  };
}

// ─── Cache ───────────────────────────────────────────────────────────────────

interface CacheEntry {
  tokens: BagsTokenEnriched[];
  timestamp: number;
}

let tokenCache: CacheEntry | null = null;
const CACHE_TTL = 60_000; // 1 minute cache

// ─── Public API ──────────────────────────────────────────────────────────────

/**
 * Fetch all bags tokens with full enrichment.
 * Returns 200+ tokens sorted by market cap.
 * Results are cached for 1 minute.
 */
export async function fetchBagsTokens(options?: {
  forceRefresh?: boolean;
  limit?: number;
}): Promise<BagsTokenEnriched[]> {
  const limit = options?.limit || 200;

  // Return cached if fresh
  if (
    !options?.forceRefresh &&
    tokenCache &&
    Date.now() - tokenCache.timestamp < CACHE_TTL
  ) {
    return tokenCache.tokens.slice(0, limit);
  }

  // Fetch from Jupiter gems
  const rawTokens = await fetchAllJupiterGems(limit);

  if (rawTokens.length === 0) {
    // Fallback: return cached data if available, even if stale
    if (tokenCache) return tokenCache.tokens.slice(0, limit);
    return [];
  }

  // Normalize and score all tokens
  const enriched = rawTokens.map(normalizeToken);

  // Sort by score descending (primary), then market cap (secondary)
  enriched.sort((a, b) => {
    if (b.kr8tivScore !== a.kr8tivScore) return b.kr8tivScore - a.kr8tivScore;
    return b.market_cap - a.market_cap;
  });

  // Update cache
  tokenCache = { tokens: enriched, timestamp: Date.now() };

  return enriched.slice(0, limit);
}

/**
 * Fetch enriched creator info for a specific token from api2.bags.fm.
 * Use this for the detail view to get extra data not in the list.
 */
export async function fetchTokenCreatorDetail(mint: string): Promise<{
  creator: BagsCreatorInfo | null;
  topHolders: BagsTopHolder[];
}> {
  const [creator, topHolders] = await Promise.allSettled([
    fetchBagsCreator(mint),
    fetchBagsTopHolders(mint),
  ]);

  return {
    creator: creator.status === 'fulfilled' ? creator.value : null,
    topHolders: topHolders.status === 'fulfilled' ? topHolders.value : [],
  };
}

/**
 * Get new launches (< 48h old) sorted by score.
 */
export async function fetchNewLaunches(limit = 50): Promise<BagsTokenEnriched[]> {
  const all = await fetchBagsTokens({ limit: 300 });
  return all.filter(t => t.isNewLaunch).slice(0, limit);
}

/**
 * Get established tokens (> 7d old, still active) sorted by score.
 */
export async function fetchEstablishedTokens(limit = 50): Promise<BagsTokenEnriched[]> {
  const all = await fetchBagsTokens({ limit: 300 });
  return all.filter(t => t.isEstablished).slice(0, limit);
}

/**
 * Get token count by tier for stats display.
 */
export function getTokenStats(tokens: BagsTokenEnriched[]): {
  total: number;
  newLaunches: number;
  established: number;
  tiers: Record<ScoreTier, number>;
  avgScore: number;
} {
  const tiers: Record<ScoreTier, number> = {
    exceptional: 0,
    strong: 0,
    average: 0,
    weak: 0,
    poor: 0,
  };

  for (const t of tokens) {
    tiers[t.scoreTier]++;
  }

  const avgScore = tokens.length > 0
    ? Math.round(tokens.reduce((s, t) => s + t.kr8tivScore, 0) / tokens.length)
    : 0;

  return {
    total: tokens.length,
    newLaunches: tokens.filter(t => t.isNewLaunch).length,
    established: tokens.filter(t => t.isEstablished).length,
    tiers,
    avgScore,
  };
}

// Re-export for convenience
export { getScoreTier };
