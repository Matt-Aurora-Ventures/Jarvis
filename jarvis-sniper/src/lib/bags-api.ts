/**
 * Bags.fm API Client for Jarvis Sniper
 *
 * This file defines shared types + scoring tiers for Bags tokens, and provides
 * a single "fetchGraduations" source used by the UI.
 *
 * Data sources (no auth required):
 * - Jupiter Data API (gems lists): POST https://datapi.jup.ag/v1/pools/gems
 * - Bags internal API: GET https://api2.bags.fm/api/v1/token-launch/top-tokens/lifetime-fees
 * - Bags internal token overview: GET https://api2.bags.fm/api/v1/token/{mint}/overview
 *
 * Notes:
 * - bags.fun launches have locked liquidity by design; liquidity is NOT treated
 *   as a rug-risk dimension, but it is still useful as a trade-quality metric.
 */

import { safeImageUrl } from './safe-url';

export interface BagsGraduation {
  mint: string;
  symbol: string;
  name: string;
  score: number;
  graduation_time: number;
  bonding_curve_score: number;
  holder_distribution_score: number;
  liquidity_score: number;
  social_score: number;
  market_cap: number;
  price_usd: number;
  liquidity: number;
  logo_uri?: string;
  // Enriched fields
  volume_24h?: number;
  price_change_5m?: number;
  price_change_1h?: number;
  price_change_24h?: number;
  txn_buys_1h?: number;
  txn_sells_1h?: number;
  age_hours?: number;
  buy_sell_ratio?: number;
  total_txns_1h?: number;
  dex_id?: string;
  holderCount?: number;
  organicScore?: number;
  icon?: string;
  twitter?: string;
  website?: string;
  description?: string;
  source?: string;
  tv_enhanced?: boolean;
  tv_momentum?: number;
  tv_volume_confirmation?: number;
  tv_base_score?: number;
  tv_rsi?: number | null;
  tv_technical_rating?: number | null;
}

export interface BagsToken {
  symbol: string;
  name: string;
  decimals: number;
  price_usd: number;
  liquidity: number;
  volume_24h: number;
  market_cap: number;
  mint: string;
}

export type ScoreTier = 'exceptional' | 'strong' | 'average' | 'weak' | 'poor';

export const getScoreTier = (score: number): ScoreTier => {
  if (score >= 85) return 'exceptional';
  if (score >= 70) return 'strong';
  if (score >= 50) return 'average';
  if (score >= 30) return 'weak';
  return 'poor';
};

export const TIER_CONFIG: Record<ScoreTier, { label: string; color: string; badgeClass: string }> = {
  exceptional: { label: 'EXCEPTIONAL', color: '#10B981', badgeClass: 'badge-exceptional' },
  strong:      { label: 'STRONG',      color: '#22C55E', badgeClass: 'badge-strong' },
  average:     { label: 'AVERAGE',     color: '#EAB308', badgeClass: 'badge-average' },
  weak:        { label: 'WEAK',        color: '#F97316', badgeClass: 'badge-weak' },
  poor:        { label: 'POOR',        color: '#EF4444', badgeClass: 'badge-poor' },
};

// ─────────────────────────────────────────────────────────────────────────────
// Jupiter Data API (gems lists)
// ─────────────────────────────────────────────────────────────────────────────

const JUPITER_GEMS_URL = 'https://datapi.jup.ag/v1/pools/gems';
const BAGS_API2_BASE = 'https://api2.bags.fm/api/v1';

export type BagsGemsCategory = 'recent' | 'aboutToGraduate' | 'graduated' | 'topEarners';

interface BagsStatsWindow {
  priceChange?: number;
  holderChange?: number;
  liquidityChange?: number;
  volumeChange?: number;
  buyVolume?: number;
  sellVolume?: number;
  buyOrganicVolume?: number;
  sellOrganicVolume?: number;
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

export interface BagsGemsTokenInfo {
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
  priceBlockId?: number;
  liquidity?: number;
  // Timeframe stats
  stats5m?: BagsStatsWindow;
  stats1h?: BagsStatsWindow;
  stats6h?: BagsStatsWindow;
  stats24h?: BagsStatsWindow;
  stats7d?: BagsStatsWindow;
  stats30d?: BagsStatsWindow;
  // bags-specific
  bondingCurve?: number;
  updatedAt?: string;
}

interface BagsGemsPool {
  id: string;
  createdAt?: string;
  liquidity?: number;
  bondingCurve?: number;
  volume24h?: number;
  updatedAt?: string;
  baseAsset?: BagsGemsTokenInfo;
}

interface BagsGemsListsResponse {
  recent?: { pools?: BagsGemsPool[] };
  aboutToGraduate?: { pools?: BagsGemsPool[] };
  graduated?: { pools?: BagsGemsPool[] };
}

interface BagsTopEarnersResponse {
  success?: boolean;
  response?: Array<{
    token?: string;
    lifetimeFees?: string;
    tokenInfo?: BagsGemsTokenInfo;
  }>;
}

function n(v: unknown, fallback = 0): number {
  const x = typeof v === 'string' ? Number(v) : (typeof v === 'number' ? v : NaN);
  return Number.isFinite(x) ? x : fallback;
}

function clamp(val: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, val));
}

function toUnixSeconds(v: unknown): number {
  if (typeof v === 'number' && Number.isFinite(v)) {
    return v > 1e12 ? Math.floor(v / 1000) : Math.floor(v);
  }
  if (typeof v === 'string') {
    const ms = Date.parse(v);
    if (Number.isFinite(ms)) return Math.floor(ms / 1000);
    const num = Number(v);
    if (Number.isFinite(num)) return num > 1e12 ? Math.floor(num / 1000) : Math.floor(num);
  }
  return Math.floor(Date.now() / 1000);
}

function coalesceStr(...vals: Array<string | undefined | null>): string | null {
  for (const v of vals) {
    if (typeof v === 'string' && v.trim().length > 0) return v.trim();
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
  if (buys > 0) return buys; // early skew
  return 0;
}

function scoreFromTokenInfo(info: BagsGemsTokenInfo): {
  score: number;
  bondingCurveScore: number;
  holderDistributionScore: number;
  socialScore: number;
} {
  // Bonding curve / maturity (0-100)
  const vol24h = sumVolume(info.stats24h);
  const bc = clamp(n(info.bondingCurve, 0), 0, 100);
  const volBoost =
    vol24h >= 250_000 ? 20 :
    vol24h >= 100_000 ? 15 :
    vol24h >= 50_000 ? 10 :
    vol24h >= 10_000 ? 6 :
    vol24h >= 1_000 ? 3 :
    0;
  const bondingCurveScore = clamp(bc + volBoost, 0, 100);

  // Holder distribution (0-100)
  const holders = n(info.holderCount, 0);
  const holderBase =
    holders >= 10_000 ? 70 :
    holders >= 5_000 ? 64 :
    holders >= 2_000 ? 56 :
    holders >= 1_000 ? 48 :
    holders >= 500 ? 40 :
    holders >= 200 ? 32 :
    holders >= 100 ? 26 :
    holders >= 50 ? 18 :
    holders >= 20 ? 12 :
    6;
  const topPct = n(info.audit?.topHoldersPercentage, NaN);
  const distBonus = Number.isFinite(topPct) ? clamp((40 - topPct) * 1.25, 0, 30) : 0; // reward <= 40%
  const organic = n(info.organicScore, 0);
  const organicBonus = organic >= 80 ? 10 : organic >= 50 ? 6 : organic >= 25 ? 3 : 0;
  const holderDistributionScore = clamp(holderBase + distBonus + organicBonus, 0, 100);

  // Social (0-100)
  let socialScore = 0;
  if (info.twitter) socialScore += 40;
  if (info.website) socialScore += 30;
  if (info.telegram) socialScore += 30;
  socialScore = clamp(socialScore, 0, 100);

  // Overall score (0-100)
  // We keep this conservative: it should be a signal, not a marketing badge.
  const score = Math.round(
    bondingCurveScore * 0.35 +
    holderDistributionScore * 0.30 +
    socialScore * 0.15 +
    // "Activity + Momentum" proxy from 24h window (0-100)
    (() => {
      const { buys, sells, total } = sumTxns(info.stats24h);
      const ratio = calcBuySellRatio(buys, sells);
      const ratioScore =
        ratio >= 1.2 && ratio <= 3.0 ? 60 :
        ratio >= 1.0 && ratio <= 5.0 ? 45 :
        ratio > 0.5 ? 30 :
        15;
      const totalScore = total >= 2000 ? 40 : total >= 800 ? 32 : total >= 250 ? 22 : total >= 80 ? 15 : 8;
      const pc = n(info.stats24h?.priceChange, 0);
      const momScore = pc > 50 ? 40 : pc > 10 ? 30 : pc > 0 ? 22 : pc > -10 ? 15 : 8;
      return clamp(ratioScore + totalScore + momScore, 0, 100);
    })() * 0.20,
  );

  return { score: clamp(score, 0, 100), bondingCurveScore, holderDistributionScore, socialScore };
}

async function fetchGemsLists(minMcap = 0): Promise<Record<'recent' | 'aboutToGraduate' | 'graduated', BagsGemsPool[]>> {
  try {
    const body = {
      recent: { launchpads: ['bags.fun'], minMcap },
      aboutToGraduate: { launchpads: ['bags.fun'], minMcap },
      graduated: { launchpads: ['bags.fun'], minMcap },
    };

    const res = await fetch(JUPITER_GEMS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    });

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

async function fetchTopEarners(): Promise<Array<{ mint: string; lifetimeFeesLamports: number; tokenInfo: BagsGemsTokenInfo }>> {
  try {
    const res = await fetch(`${BAGS_API2_BASE}/token-launch/top-tokens/lifetime-fees`, {
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(15000),
    });
    if (!res.ok) return [];

    const json = (await res.json()) as BagsTopEarnersResponse;
    const items = Array.isArray(json?.response) ? json.response : [];

    return items
      .map((it) => ({
        mint: it?.tokenInfo?.id || it?.token || '',
        lifetimeFeesLamports: Math.max(0, Math.floor(n(it?.lifetimeFees, 0))),
        tokenInfo: it?.tokenInfo as BagsGemsTokenInfo,
      }))
      .filter((x) => !!x.mint && x.tokenInfo && typeof x.tokenInfo === 'object');
  } catch {
    return [];
  }
}

function tokenInfoToGraduation(
  info: BagsGemsTokenInfo,
  category: BagsGemsCategory,
): BagsGraduation {
  const stats1h = info.stats1h;
  const stats24h = info.stats24h;

  const ageHours = Math.max(0, (Date.now() / 1000 - toUnixSeconds(info.createdAt)) / 3600);
  const vol24h = sumVolume(stats24h);
  const vol1h = sumVolume(stats1h);
  const tx1h = sumTxns(stats1h);
  const ratio = calcBuySellRatio(tx1h.buys, tx1h.sells);

  const { score, bondingCurveScore, holderDistributionScore, socialScore } = scoreFromTokenInfo(info);

  return {
    mint: info.id,
    symbol: info.symbol || '???',
    name: info.name || info.symbol || 'Unknown',
    score,
    graduation_time: toUnixSeconds(info.createdAt),
    bonding_curve_score: Math.round(bondingCurveScore),
    holder_distribution_score: Math.round(holderDistributionScore),
    liquidity_score: 100,
    social_score: Math.round(socialScore),
    market_cap: n(info.mcap, 0),
    price_usd: n(info.usdPrice, 0),
    liquidity: n(info.liquidity, 0),
    logo_uri: safeImageUrl(coalesceStr(info.icon, null) || undefined),
    volume_24h: vol24h,
    price_change_5m: n(info.stats5m?.priceChange, 0),
    price_change_1h: n(stats1h?.priceChange, 0),
    txn_buys_1h: tx1h.buys,
    txn_sells_1h: tx1h.sells,
    age_hours: ageHours,
    buy_sell_ratio: ratio,
    total_txns_1h: tx1h.total,
    holderCount: n(info.holderCount, 0),
    organicScore: n(info.organicScore, 0),
    icon: safeImageUrl(info.icon),
    twitter: info.twitter,
    website: info.website,
    source: category === 'topEarners' ? 'bags.fun:topEarners' : `bags.fun:${category}`,
  };
}

// ─── Cache ────────────────────────────────────────────────────────────────

let _cache: { tokens: BagsGraduation[]; ts: number } | null = null;
const CACHE_TTL = 45_000; // 45s cache

/**
 * Fetch bags.fun tokens with metadata and scoring.
 *
 * This is the canonical Bags data feed used by the app.
 */
export async function fetchGraduations(limit = 200): Promise<BagsGraduation[]> {
  if (_cache && Date.now() - _cache.ts < CACHE_TTL) {
    return _cache.tokens.slice(0, limit);
  }

  // 1) Datapi lists (recent/aboutToGraduate/graduated)
  const lists = await fetchGemsLists(0);

  // 2) Established winners (lifetime fees leaderboard)
  const topEarners = await fetchTopEarners();

  // Merge by mint while keeping the most complete tokenInfo.
  const byMint = new Map<string, { info: BagsGemsTokenInfo; category: BagsGemsCategory }>();

  const ingestPoolList = (category: BagsGemsCategory, pools: BagsGemsPool[]) => {
    for (const p of pools) {
      const info = p?.baseAsset;
      const mint = info?.id;
      if (!mint) continue;
      if (!byMint.has(mint)) byMint.set(mint, { info, category });
    }
  };

  ingestPoolList('recent', lists.recent);
  ingestPoolList('aboutToGraduate', lists.aboutToGraduate);
  ingestPoolList('graduated', lists.graduated);

  for (const item of topEarners) {
    const mint = item.mint;
    if (!mint) continue;
    const existing = byMint.get(mint);
    byMint.set(mint, {
      info: existing ? { ...existing.info, ...item.tokenInfo } : item.tokenInfo,
      category: existing?.category ?? 'topEarners',
    });
  }

  const tokens = [...byMint.values()]
    .map((t) => tokenInfoToGraduation(t.info, t.category))
    .filter((t) => !!t.mint);

  // Sort by score desc, then market cap desc
  tokens.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return b.market_cap - a.market_cap;
  });

  // Cache
  _cache = { tokens, ts: Date.now() };

  return tokens.slice(0, limit);
}

// ─────────────────────────────────────────────────────────────────────────────
// Token overview (api2.bags.fm) - used by swap flows and misc UI
// ─────────────────────────────────────────────────────────────────────────────

async function api2Fetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BAGS_API2_BASE}${path}`, {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchTokenInfo(mint: string): Promise<BagsToken | null> {
  const data = await api2Fetch<any>(`/token/${mint}/overview`);
  const info = data?.response;
  if (!info) return null;

  const vol24h = Array.isArray(info?.buyHistory24h) || Array.isArray(info?.sellHistory24h)
    ? 0
    : 0; // api2 overview doesn't provide volume; keep 0 for now.

  return {
    symbol: info.symbol || '',
    name: info.name || '',
    decimals: Math.max(0, Math.floor(n(info.decimals, 9))),
    price_usd: n(info.price, 0),
    liquidity: n(info.liquidity, 0),
    volume_24h: vol24h,
    market_cap: n(info.marketCap, 0),
    mint,
  };
}
