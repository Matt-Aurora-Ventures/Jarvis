import { NextResponse } from 'next/server';
import { graduationCache } from '@/lib/server-cache';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { ALL_BLUECHIPS } from '@/lib/bluechip-data';

/**
 * Server-side graduation feed using DexScreener API
 * Avoids CORS issues by proxying through our own API route
 *
 * Caching: 5-second in-memory cache so all concurrent users share one upstream call.
 * Rate limiting: 60 req/min per IP to prevent abuse.
 *
 * Flow:
 * 1. Check cache — return immediately if fresh
 * 2. Fetch latest boosted Solana tokens from DexScreener
 * 3. Batch-fetch pair data for price, liquidity, volume
 * 4. Score and return as graduation-format data
 */

const DEXSCREENER_BOOSTS = 'https://api.dexscreener.com/token-boosts/latest/v1';
const DEXSCREENER_PROFILES = 'https://api.dexscreener.com/token-profiles/latest/v1';
const DEXSCREENER_SOL_PAIRS = 'https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const JUPITER_GEMS_URL = 'https://datapi.jup.ag/v1/pools/gems';
const JUPITER_LAUNCHPADS = ['pump.fun', 'moonshot', 'launchlab', 'boop.fun', 'letsbonk.fun'];
const TARGET_FEED_SIZE = 220;
const TARGET_CANDIDATE_SIZE = 260;

const STABLE_SYMBOLS = new Set([
  'USDC', 'USDT', 'DAI', 'FDUSD', 'USDE', 'USDY', 'PYUSD', 'USDS', 'USDD', 'EURC', 'UXD', 'PAI',
]);
const STABLE_NAME_HINTS = ['usd coin', 'tether', 'stable', 'stables', 'dollar', 'euro coin'];
const EXCLUDED_STABLE_MINTS = new Set([
  // USDC (native + wormhole variants commonly seen on Solana)
  'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
  // USDT
  'Es9vMFrzaCERmJfrF4H2fycb14RJCdxu2YQhR6aY4A7Q',
  // PYUSD
  '2b1kV6DkP4hQ2f7kQ5RkUv4xL7tYQ3b8e8Wv2mJvVxJa',
]);

type IntakeSource = 'boosts' | 'profiles' | 'sol-pairs' | 'jupiter-launchpad' | 'bluechip-registry';

/** Fetch with a timeout to prevent hanging when DexScreener is slow/unreachable */
async function fetchWithTimeout(url: string, timeoutMs = 8000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      headers: { 'Accept': 'application/json' },
      signal: controller.signal,
    });
    return res;
  } finally {
    clearTimeout(timer);
  }
}

interface BoostEntry {
  chainId: string;
  tokenAddress: string;
  description?: string;
  symbol?: string;
  name?: string;
  icon?: string;
  links?: Array<{ type?: string; url: string }>;
  totalAmount: number;
  amount: number;
  sourceTag?: IntakeSource;
}

interface ProfileEntry {
  chainId: string;
  tokenAddress: string;
  description?: string;
  symbol?: string;
  name?: string;
  icon?: string;
  links?: Array<{ type?: string; url: string }>;
}

interface JupiterLaunchpadPool {
  id?: string;
  baseAsset?: {
    id?: string;
    symbol?: string;
    name?: string;
    icon?: string;
    website?: string;
    twitter?: string;
    telegram?: string;
  };
}

interface JupiterLaunchpadResponse {
  recent?: { pools?: JupiterLaunchpadPool[] };
  aboutToGraduate?: { pools?: JupiterLaunchpadPool[] };
  graduated?: { pools?: JupiterLaunchpadPool[] };
}

/**
 * Fetch Solana tokens from the boosts endpoint (primary source).
 * Returns deduplicated entries filtered to chainId === 'solana'.
 */
async function fetchBoostedTokens(): Promise<BoostEntry[]> {
  try {
    const res = await fetchWithTimeout(DEXSCREENER_BOOSTS);
    if (!res.ok) return [];
    const all: BoostEntry[] = await res.json();
    const seen = new Set<string>();
    return all.filter(b => {
      if (b.chainId !== 'solana' || seen.has(b.tokenAddress)) return false;
      seen.add(b.tokenAddress);
      return true;
    }).slice(0, 80).map((b) => ({ ...b, sourceTag: 'boosts' as const }));
  } catch {
    return [];
  }
}

/**
 * Fallback 1: Fetch tokens with recently updated profiles on DexScreener.
 * Profile entries share the same shape as boosts minus totalAmount/amount.
 * We convert them to BoostEntry with totalAmount/amount = 0.
 */
async function fetchProfileTokens(): Promise<BoostEntry[]> {
  try {
    const res = await fetchWithTimeout(DEXSCREENER_PROFILES);
    if (!res.ok) return [];
    const all: ProfileEntry[] = await res.json();
    const seen = new Set<string>();
    return all.filter(p => {
      if (p.chainId !== 'solana' || seen.has(p.tokenAddress)) return false;
      seen.add(p.tokenAddress);
      return true;
    }).slice(0, 80).map(p => ({
      ...p,
      totalAmount: 0,
      amount: 0,
      sourceTag: 'profiles' as const,
    }));
  } catch {
    return [];
  }
}

/**
 * Fallback 2: Fetch top SOL pairs by volume as a last resort.
 * The pairs endpoint returns a different shape, so we convert to BoostEntry.
 */
async function fetchSolPairsAsTokens(): Promise<BoostEntry[]> {
  try {
    const res = await fetchWithTimeout(DEXSCREENER_SOL_PAIRS);
    if (!res.ok) return [];
    const data = await res.json();
    const pairs: any[] = data.pairs || [];
    // Sort by 24h volume descending and pick unique base tokens
    const sorted = pairs
      .filter((p: any) => p.chainId === 'solana')
      .sort((a: any, b: any) => parseFloat(b.volume?.h24 || '0') - parseFloat(a.volume?.h24 || '0'));
    const seen = new Set<string>();
    const results: BoostEntry[] = [];
    for (const pair of sorted) {
      const baseAddr = pair.baseToken?.address;
      const quoteAddr = pair.quoteToken?.address;
      const solMint = 'So11111111111111111111111111111111111111112';
      const addr = baseAddr === solMint ? quoteAddr : (quoteAddr === solMint ? baseAddr : null);
      if (!addr) continue;
      // Skip SOL and obvious stable quote-side artifacts
      if (addr === solMint) continue;
      if (seen.has(addr)) continue;
      seen.add(addr);
      results.push({
        chainId: 'solana',
        tokenAddress: addr,
        symbol: (baseAddr === solMint ? pair.quoteToken?.symbol : pair.baseToken?.symbol) || undefined,
        name: (baseAddr === solMint ? pair.quoteToken?.name : pair.baseToken?.name) || undefined,
        description: (baseAddr === solMint ? pair.quoteToken?.name : pair.baseToken?.name) || undefined,
        icon: pair.info?.imageUrl ? 'true' : undefined, // presence flag
        links: pair.info?.websites?.map((w: any) => ({ type: 'website', url: w.url || w })) || [],
        totalAmount: 0,
        amount: 0,
        sourceTag: 'sol-pairs',
      });
      if (results.length >= 120) break;
    }
    return results;
  } catch {
    return [];
  }
}

/**
 * Pulls tokens from Jupiter launchpad gems across non-bags launchpads.
 * This broadens intake beyond DexScreener boosts-only discovery.
 */
async function fetchJupiterLaunchpadTokens(): Promise<BoostEntry[]> {
  try {
    const body = {
      recent: { launchpads: JUPITER_LAUNCHPADS, minMcap: 0 },
      aboutToGraduate: { launchpads: JUPITER_LAUNCHPADS, minMcap: 0 },
      graduated: { launchpads: JUPITER_LAUNCHPADS, minMcap: 0 },
    };
    // Prefer POST with explicit launchpad filters.
    const postRes = await fetch(JUPITER_GEMS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(12000),
    });
    if (postRes.ok) {
      const json = (await postRes.json()) as JupiterLaunchpadResponse;
      const parsed = parseJupiterPools(json);
      if (parsed.length > 0) return parsed;
    }

    // Fallback: GET endpoint (best effort).
    const res = await fetchWithTimeout(JUPITER_GEMS_URL, 9000);
    if (!res.ok) return [];
    const json = (await res.json()) as JupiterLaunchpadResponse;
    return parseJupiterPools(json);
  } catch {
    return [];
  }
}

function parseJupiterPools(json: JupiterLaunchpadResponse): BoostEntry[] {
  const pools = [
    ...(json.recent?.pools || []),
    ...(json.aboutToGraduate?.pools || []),
    ...(json.graduated?.pools || []),
  ];
  const out: BoostEntry[] = [];
  const seen = new Set<string>();
  for (const p of pools) {
    const base = p.baseAsset;
    const mint = base?.id;
    if (!mint || seen.has(mint)) continue;
    seen.add(mint);
    const links: Array<{ type?: string; url: string }> = [];
    if (base?.website) links.push({ type: 'website', url: base.website });
    if (base?.twitter) links.push({ type: 'twitter', url: base.twitter });
    if (base?.telegram) links.push({ type: 'telegram', url: base.telegram });
    out.push({
      chainId: 'solana',
      tokenAddress: mint,
      symbol: base?.symbol,
      name: base?.name,
      description: base?.name,
      icon: base?.icon,
      links,
      totalAmount: 0,
      amount: 0,
      sourceTag: 'jupiter-launchpad',
    });
    if (out.length >= 120) break;
  }
  return out;
}

function bluechipRegistryAsTokens(): BoostEntry[] {
  return ALL_BLUECHIPS.map((t) => ({
    chainId: 'solana',
    tokenAddress: t.mintAddress,
    symbol: t.ticker,
    name: t.name,
    description: t.description,
    links: [],
    totalAmount: 0,
    amount: 0,
    sourceTag: 'bluechip-registry' as const,
  }));
}

function mergeUniqueCandidates(groups: Array<{ source: IntakeSource; items: BoostEntry[] }>, maxItems: number): BoostEntry[] {
  const byMint = new Map<string, BoostEntry & { _rank: number }>();
  const sourceRank: Record<IntakeSource, number> = {
    boosts: 100,
    profiles: 85,
    'jupiter-launchpad': 80,
    'sol-pairs': 70,
    'bluechip-registry': 90,
  };

  for (const group of groups) {
    for (const item of group.items) {
      const mint = item.tokenAddress;
      if (!mint) continue;
      const rank = sourceRank[group.source] + Math.min(20, item.totalAmount || 0);
      const existing = byMint.get(mint);
      if (!existing || rank > existing._rank) {
        byMint.set(mint, { ...existing, ...item, sourceTag: group.source, _rank: rank });
      }
      if (byMint.size >= maxItems * 2) break;
    }
  }

  return [...byMint.values()]
    .sort((a, b) => b._rank - a._rank)
    .slice(0, maxItems);
}

async function fetchPairsByMints(addresses: string[]): Promise<Map<string, any>> {
  const pairsByMint = new Map<string, any>();
  const unique = [...new Set(addresses)].filter(Boolean);
  const chunks: string[][] = [];
  for (let i = 0; i < unique.length; i += 30) chunks.push(unique.slice(i, i + 30));

  const concurrency = 3;
  let idx = 0;
  const workers = Array.from({ length: concurrency }, async () => {
    while (true) {
      const cur = idx++;
      if (cur >= chunks.length) break;
      const chunk = chunks[cur];
      try {
        const res = await fetchWithTimeout(`${DEXSCREENER_TOKENS}/${chunk.join(',')}`, 9000);
        if (!res.ok) continue;
        const pairs: any[] = await res.json();
        for (const pair of pairs) {
          const mint = pair.baseToken?.address;
          if (!mint) continue;
          const existing = pairsByMint.get(mint);
          const liq = parseFloat(pair.liquidity?.usd || '0');
          if (!existing || liq > (existing._liq || 0)) {
            pairsByMint.set(mint, { ...pair, _liq: liq });
          }
        }
      } catch {
        // best-effort per chunk
      }
    }
  });
  await Promise.allSettled(workers);
  return pairsByMint;
}

function looksStableToken(token: BoostEntry, pair?: any): boolean {
  const mint = token.tokenAddress || '';
  if (EXCLUDED_STABLE_MINTS.has(mint)) return true;

  const symbol = (pair?.baseToken?.symbol || token.symbol || '').toUpperCase();
  if (STABLE_SYMBOLS.has(symbol)) return true;

  const name = (pair?.baseToken?.name || token.name || token.description || '').toLowerCase();
  if (name.length > 0 && STABLE_NAME_HINTS.some((hint) => name.includes(hint))) return true;

  return false;
}

const GRADUATION_CACHE_KEY = 'graduations:latest';
const GRADUATION_TTL_MS = 5_000; // 5 seconds — balances freshness vs API load

export async function GET(request: Request) {
  try {
    const reqUrl = new URL(request.url);
    const mode = (reqUrl.searchParams.get('mode') || '').toLowerCase();
    const launchesOnly = mode === 'launches' || reqUrl.searchParams.get('launches') === '1';
    const maxAgeHoursParam = Number(reqUrl.searchParams.get('maxAgeHours') || '');
    const maxLaunchAgeHours = Number.isFinite(maxAgeHoursParam) && maxAgeHoursParam > 0
      ? Math.min(24 * 14, Math.max(1, maxAgeHoursParam))
      : 96;
    const cacheKey = launchesOnly
      ? `graduations:launches:${maxLaunchAgeHours}`
      : GRADUATION_CACHE_KEY;
    // Rate limit check
    const ip = getClientIp(request);
    const limit = apiRateLimiter.check(ip);
    if (!limit.allowed) {
      return NextResponse.json(
        { graduations: [], error: 'Rate limit exceeded' },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    // Check cache first — all users share the same cached response
    const cached = graduationCache.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached, {
        headers: {
          'X-Cache': 'HIT',
          'X-RateLimit-Remaining': String(limit.remaining),
        },
      });
    }

    // 1. Fetch Solana token candidates from ALL sources (merged, not winner-takes-all).
    const [boostResult, profileResult, pairsResult, jupiterResult] = await Promise.allSettled([
      fetchBoostedTokens(),
      fetchProfileTokens(),
      fetchSolPairsAsTokens(),
      fetchJupiterLaunchpadTokens(),
    ]);

    // Resolve all sources (best effort).
    const boosts = boostResult.status === 'fulfilled' ? boostResult.value : [];
    const profiles = profileResult.status === 'fulfilled' ? profileResult.value : [];
    const pairsTokens = pairsResult.status === 'fulfilled' ? pairsResult.value : [];
    const jupiterTokens = jupiterResult.status === 'fulfilled' ? jupiterResult.value : [];
    const bluechips = launchesOnly ? [] : bluechipRegistryAsTokens();

    const mergedCandidates = mergeUniqueCandidates(
      [
        { source: 'boosts', items: boosts },
        { source: 'profiles', items: profiles },
        { source: 'jupiter-launchpad', items: jupiterTokens },
        { source: 'sol-pairs', items: pairsTokens },
        { source: 'bluechip-registry', items: bluechips },
      ],
      TARGET_CANDIDATE_SIZE,
    );

    if (mergedCandidates.length === 0) {
      console.warn('[Graduations] All DexScreener sources returned 0 Solana tokens');
      return NextResponse.json({ graduations: [], source: 'none' });
    }

    // 2. Fetch best-liquidity pair per mint using chunked batch fetches.
    const pairsByMint = await fetchPairsByMints(mergedCandidates.map((t) => t.tokenAddress));

    // 3. Filter stablecoins from the general sniper universe.
    const solanaTokens = mergedCandidates.filter((t) => !looksStableToken(t, pairsByMint.get(t.tokenAddress)));

    // Quality guardrails for the main sniper feed:
    // keep bluechip registry always, but filter low-signal newly indexed noise.
    const QUALITY_MIN_LIQ_USD = 2_000;
    const QUALITY_MIN_VOL24_USD = 5_000;
    const QUALITY_MIN_TXNS_1H = 12;
    const qualityFiltered = solanaTokens.filter((t) => {
      if (t.sourceTag === 'bluechip-registry') return true;
      const pair = pairsByMint.get(t.tokenAddress);
      if (!pair) return false;
      const liq = parseFloat(pair?.liquidity?.usd || '0');
      const vol24 = parseFloat(pair?.volume?.h24 || '0');
      const tx1h = (pair?.txns?.h1?.buys || 0) + (pair?.txns?.h1?.sells || 0);
      return liq >= QUALITY_MIN_LIQ_USD || vol24 >= QUALITY_MIN_VOL24_USD || tx1h >= QUALITY_MIN_TXNS_1H;
    });

    const sourceCounts = {
      boosts: boosts.length,
      profiles: profiles.length,
      jupiterLaunchpad: jupiterTokens.length,
      solPairs: pairsTokens.length,
      bluechipRegistry: bluechips.length,
      merged: mergedCandidates.length,
      postStableFilter: solanaTokens.length,
      postQualityFilter: qualityFiltered.length,
    };
    console.log('[Graduations] source mix', sourceCounts);

    // Launches mode: strict recency window and no bluechip registry carry-over.
    const launchFiltered = launchesOnly
      ? qualityFiltered.filter((t) => {
          if (t.sourceTag === 'bluechip-registry') return false;
          const pair = pairsByMint.get(t.tokenAddress);
          const createdAtMs = Number(pair?.pairCreatedAt || 0);
          if (!createdAtMs || !Number.isFinite(createdAtMs)) return false;
          const ageHours = (Date.now() - createdAtMs) / (1000 * 60 * 60);
          return ageHours >= 0 && ageHours <= maxLaunchAgeHours;
        })
      : qualityFiltered;

    // 3. Merge boost data + pair data into graduation format
    const graduations = launchFiltered.map(boost => {
      const pair = pairsByMint.get(boost.tokenAddress);
      const liq = parseFloat(pair?.liquidity?.usd || '0');
      const vol24 = parseFloat(pair?.volume?.h24 || '0');
      const mcap = parseFloat(pair?.marketCap || pair?.fdv || '0');
      const priceUsd = parseFloat(pair?.priceUsd || '0');
      const txnBuys = pair?.txns?.h1?.buys || 0;
      const txnSells = pair?.txns?.h1?.sells || 0;
      const priceChange5m = pair?.priceChange?.m5 || 0;
      const priceChange1h = pair?.priceChange?.h1 || 0;

      const hasTwitter = boost.links?.some(l => l.type === 'twitter') || false;
      const hasTelegram = boost.links?.some(l => l.type === 'telegram') || false;
      const hasWebsite = boost.links?.some(l => !l.type || l.type === 'website') || false;
      const socialCount = [hasTwitter, hasTelegram, hasWebsite].filter(Boolean).length;
      const pairSocials: any[] = Array.isArray(pair?.info?.socials) ? pair.info.socials : [];
      const pairWebsites: any[] = Array.isArray(pair?.info?.websites) ? pair.info.websites : [];
      const website =
        pairWebsites.find((w: any) => typeof w?.url === 'string')?.url ||
        boost.links?.find((l) => !l.type || l.type === 'website')?.url ||
        undefined;
      const twitter =
        pairSocials.find((s: any) => String(s?.type || '').toLowerCase() === 'twitter')?.url ||
        boost.links?.find((l) => String(l.type || '').toLowerCase() === 'twitter')?.url ||
        undefined;
      const telegram =
        pairSocials.find((s: any) => String(s?.type || '').toLowerCase() === 'telegram')?.url ||
        boost.links?.find((l) => String(l.type || '').toLowerCase() === 'telegram')?.url ||
        undefined;

      // Score calculation
      let score = 30; // base
      // Liquidity scoring (0-20)
      if (liq > 100000) score += 20;
      else if (liq > 50000) score += 15;
      else if (liq > 10000) score += 10;
      else if (liq > 1000) score += 5;
      // Volume scoring (0-15)
      if (vol24 > 500000) score += 15;
      else if (vol24 > 100000) score += 12;
      else if (vol24 > 10000) score += 8;
      else if (vol24 > 1000) score += 4;
      // Social scoring (0-15)
      score += socialCount * 5;
      // Boost scoring (0-10) — higher boost = more dev investment
      if (boost.totalAmount >= 100) score += 10;
      else if (boost.totalAmount >= 50) score += 7;
      else if (boost.totalAmount >= 20) score += 4;
      // Buy pressure (0-10) — Backtested: ratio 1.0-3.0 = sweet spot
      // Extreme ratios (>3) indicate pump/manipulation, NOT organic demand
      if (txnBuys > 0 && txnSells > 0) {
        const ratio = txnBuys / txnSells;
        if (ratio >= 1.2 && ratio <= 3.0) score += 10;  // Sweet spot
        else if (ratio >= 1.0 && ratio <= 4.0) score += 5;  // Acceptable
        else if (ratio > 5.0) score -= 5;  // Pump signal — penalize
      }
      // Momentum bonus (0-10) — Backtested: positive 1h = 288% predictive power
      if (priceChange1h > 10) score += 10;
      else if (priceChange1h > 5) score += 7;
      else if (priceChange1h > 0) score += 5;
      else if (priceChange5m > 5) score += 3;
      else if (priceChange5m > 0) score += 1;
      // Penalty for dumping
      if (priceChange1h < -30) score -= 15;
      else if (priceChange1h < -15) score -= 8;
      // Activity bonus — Backtested: high total txns = strong signal
      const totalTxns = txnBuys + txnSells;
      if (totalTxns >= 200) score += 5;
      else if (totalTxns >= 100) score += 3;

      // Maturity bonus: favor tokens that have survived longer on-chain.
      const pairCreatedMs = pair?.pairCreatedAt || Date.now();
      const ageHours = (Date.now() - pairCreatedMs) / (1000 * 60 * 60);
      if (ageHours >= 24 * 365) score += 8;
      else if (ageHours >= 24 * 180) score += 6;
      else if (ageHours >= 24 * 30) score += 4;
      else if (ageHours >= 24 * 7) score += 2;

      // Intake diversity bias for stable feed composition.
      if (boost.sourceTag === 'bluechip-registry') score += 8;
      else if (boost.sourceTag === 'sol-pairs') score += 5;
      else if (boost.sourceTag === 'jupiter-launchpad') score += 3;

      score = Math.min(100, Math.max(0, score));

      const iconUrl = boost.icon
        ? `https://dd.dexscreener.com/ds-data/tokens/solana/${boost.tokenAddress}.png`
        : pair?.info?.imageUrl || undefined;

      // Compute age in hours and buy/sell ratio for sniper filters
      const buySellRatio = txnSells > 0 ? txnBuys / txnSells : (txnBuys > 0 ? txnBuys : 0);

      return {
        mint: boost.tokenAddress,
        symbol: pair?.baseToken?.symbol || boost.tokenAddress.slice(0, 6),
        name: pair?.baseToken?.name || boost.description?.slice(0, 30) || 'Unknown',
        score,
        graduation_time: pair?.pairCreatedAt ? pair.pairCreatedAt / 1000 : Date.now() / 1000,
        bonding_curve_score: Math.min(100, boost.totalAmount * 2),
        holder_distribution_score: Math.min(100, (txnBuys + txnSells) / 2),
        liquidity_score: Math.min(100, liq / 1000),
        social_score: socialCount * 33,
        market_cap: mcap,
        price_usd: priceUsd,
        liquidity: liq,
        volume_24h: vol24,
        logo_uri: iconUrl,
        website,
        twitter,
        telegram,
        chart_url: pair?.url || `https://dexscreener.com/solana/${boost.tokenAddress}`,
        pair_address: pair?.pairAddress || undefined,
        source: boost.sourceTag || 'profiles',
        boost_amount: boost.totalAmount,
        price_change_5m: priceChange5m,
        price_change_1h: priceChange1h,
        txn_buys_1h: txnBuys,
        txn_sells_1h: txnSells,
        // New fields for insight-driven filtering
        age_hours: Math.round(ageHours * 10) / 10,
        buy_sell_ratio: Math.round(buySellRatio * 100) / 100,
        total_txns_1h: txnBuys + txnSells,
        dex_id: pair?.dexId || 'unknown',
      };
    });

    // Sort by score descending
    graduations.sort((a, b) => b.score - a.score);

    // Cache the response so all concurrent users share this result
    const responseData = {
      graduations: graduations.slice(0, TARGET_FEED_SIZE),
      meta: {
        sourceCounts,
        launchesOnly,
        maxLaunchAgeHours: launchesOnly ? maxLaunchAgeHours : undefined,
        postLaunchFilter: launchesOnly ? launchFiltered.length : undefined,
        feedSize: Math.min(TARGET_FEED_SIZE, graduations.length),
      },
    };
    graduationCache.set(cacheKey, responseData, GRADUATION_TTL_MS);

    return NextResponse.json(responseData, {
      headers: {
        'X-Cache': 'MISS',
        'X-RateLimit-Remaining': String(limit.remaining),
        'Cache-Control': 'public, s-maxage=5, stale-while-revalidate=10',
      },
    });
  } catch (err) {
    console.error('Graduation API error:', err);
    // Graceful degradation: return empty graduations with 200 instead of 500
    // so client-side polling doesn't trigger error states
    return NextResponse.json({ graduations: [], error: 'Internal error', _fallback: true });
  }
}
