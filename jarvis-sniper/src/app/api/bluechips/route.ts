import { NextResponse } from 'next/server';
import { ALL_BLUECHIPS, type BlueChipToken } from '@/lib/bluechip-data';
import { ServerCache } from '@/lib/server-cache';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';

/**
 * Blue Chip Solana Tokens API route
 *
 * Fetches live price data from DexScreener for the curated blue chip registry,
 * then returns data formatted as BagsGraduation[] with dynamic scoring
 * based on momentum, volume, and liquidity.
 *
 * Query params:
 *   ?tier=1|2|3|all  (default: all)
 *   ?category=defi|infra|meme_established|gaming|ai|lsd  (optional filter)
 *
 * Caching: 30-second in-memory cache to avoid hammering DexScreener.
 */

const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const bluechipCache = new ServerCache<any>();
const CACHE_TTL_MS = 30_000;

async function fetchWithTimeout(url: string, timeoutMs = 10000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      headers: { 'Accept': 'application/json' },
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Dynamic scoring for blue chip tokens based on real-time data.
 *
 * Scoring dimensions (total 0-100):
 * - Liquidity Health (0-25): Higher liquidity = safer, more executable trades
 * - Volume Activity (0-25): Active trading = better entries/exits
 * - Price Momentum (0-25): Trending direction and strength
 * - Market Structure (0-25): B/S ratio, spread health, tier bonus
 */
function calcBlueChipScore(
  token: BlueChipToken,
  pair: any,
): number {
  if (!pair) return 40; // No data = below average

  const liq = parseFloat(pair.liquidity?.usd || '0');
  const vol24h = parseFloat(pair.volume?.h24 || '0');
  const change1h = pair.priceChange?.h1 || 0;
  const change24h = pair.priceChange?.h24 || 0;
  const buys1h = pair.txns?.h1?.buys || 0;
  const sells1h = pair.txns?.h1?.sells || 0;
  const totalTxns = buys1h + sells1h;
  const bsRatio = sells1h > 0 ? buys1h / sells1h : buys1h;
  const volLiqRatio = liq > 0 ? vol24h / liq : 0;

  let score = 0;

  // ─── Liquidity Health (0-25) ───
  if (liq >= 2_000_000) score += 25;
  else if (liq >= 1_000_000) score += 22;
  else if (liq >= 500_000) score += 18;
  else if (liq >= 200_000) score += 14;
  else if (liq >= 100_000) score += 10;
  else if (liq >= 50_000) score += 6;
  else score += 3;

  // ─── Volume Activity (0-25) ───
  if (volLiqRatio >= 3.0) score += 25;
  else if (volLiqRatio >= 2.0) score += 22;
  else if (volLiqRatio >= 1.0) score += 18;
  else if (volLiqRatio >= 0.5) score += 14;
  else if (volLiqRatio >= 0.2) score += 10;
  else score += 4;

  // Transaction count bonus
  if (totalTxns >= 500) score += 0; // already captured in vol
  else if (totalTxns < 10) score -= 3; // Very low activity penalty

  // ─── Price Momentum (0-25) ───
  // Reward strong trends in either direction (tradeable)
  const absChange1h = Math.abs(change1h);
  const absChange24h = Math.abs(change24h);

  // 1h momentum
  if (absChange1h >= 10) score += 12;
  else if (absChange1h >= 5) score += 10;
  else if (absChange1h >= 2) score += 7;
  else if (absChange1h >= 0.5) score += 4;
  else score += 2; // flat = less tradeable

  // 24h trend alignment (same direction as 1h = stronger signal)
  if (change1h > 0 && change24h > 0) score += 8; // bullish trend
  else if (change1h < 0 && change24h < 0) score += 5; // bearish but consistent
  else score += 3; // mixed

  // Extreme momentum bonus
  if (absChange1h >= 15) score += 5;

  // ─── Market Structure (0-25) ───
  // Buy/sell ratio
  if (bsRatio >= 1.2 && bsRatio <= 2.5 && totalTxns >= 20) {
    score += 10; // Healthy buying pressure
  } else if (bsRatio >= 0.8 && bsRatio <= 3.0) {
    score += 6; // Acceptable
  } else {
    score += 2; // Extreme imbalance
  }

  // Tier bonus (established tokens deserve baseline trust)
  if (token.mcapTier === 'mega') score += 8;
  else if (token.mcapTier === 'large') score += 6;
  else score += 4;

  // Category bonus
  if (token.category === 'defi' || token.category === 'infra') score += 4;
  else if (token.category === 'lsd') score += 3;
  else score += 2; // memes get less structural bonus

  // Years bonus
  if (token.yearsSolana >= 4) score += 3;
  else if (token.yearsSolana >= 2) score += 1;

  return Math.max(10, Math.min(100, Math.round(score)));
}

export async function GET(request: Request) {
  try {
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

    const { searchParams } = new URL(request.url);
    const tier = searchParams.get('tier') || 'all';
    const category = searchParams.get('category');

    let tokens = ALL_BLUECHIPS;
    if (tier !== 'all') {
      const tierNum = parseInt(tier);
      if (tierNum === 1) tokens = tokens.filter(t => t.mcapTier === 'mega');
      else if (tierNum === 2) tokens = tokens.filter(t => t.mcapTier === 'large' || t.mcapTier === 'mid');
      else if (tierNum === 3) tokens = tokens.filter(t => t.category === 'meme_established');
    }
    if (category) {
      tokens = tokens.filter(t => t.category === category);
    }

    if (tokens.length === 0) {
      return NextResponse.json({ graduations: [] });
    }

    const cacheKey = `bluechips:${tier}:${category || 'all'}`;
    const cached = bluechipCache.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached, { headers: { 'X-Cache': 'HIT' } });
    }

    // Fetch pair data from DexScreener
    const pairsByMint = new Map<string, any>();
    const mintAddresses = tokens.map(t => t.mintAddress);

    for (let i = 0; i < mintAddresses.length; i += 30) {
      const chunk = mintAddresses.slice(i, i + 30);
      try {
        const res = await fetchWithTimeout(`${DEXSCREENER_TOKENS}/${chunk.join(',')}`);
        if (res.ok) {
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
        }
      } catch {
        // continue with partial data
      }
    }

    const graduations = tokens.map(token => {
      const pair = pairsByMint.get(token.mintAddress);
      const liq = parseFloat(pair?.liquidity?.usd || '0');
      const vol24h = parseFloat(pair?.volume?.h24 || '0');
      const buys = pair?.txns?.h1?.buys || 0;
      const sells = pair?.txns?.h1?.sells || 0;

      return {
        mint: token.mintAddress,
        symbol: token.ticker,
        name: token.name,
        score: calcBlueChipScore(token, pair),
        graduation_time: Date.now() / 1000,
        bonding_curve_score: 0,
        holder_distribution_score: 0,
        liquidity_score: Math.min(25, Math.round(liq / 80_000)),
        social_score: 0,
        market_cap: pair?.fdv || pair?.marketCap || 0,
        liquidity: liq,
        volume_24h: vol24h,
        price_usd: parseFloat(pair?.priceUsd || '0'),
        price_change_5m: pair?.priceChange?.m5 || 0,
        price_change_1h: pair?.priceChange?.h1 || 0,
        price_change_24h: pair?.priceChange?.h24 || 0,
        txn_buys_1h: buys,
        txn_sells_1h: sells,
        age_hours: token.yearsSolana * 8760,
        buy_sell_ratio: sells > 0 ? buys / sells : buys,
        total_txns_1h: buys + sells,
        dex_id: pair?.dexId || 'unknown',
        source: 'bluechip',
        fdv: pair?.fdv || 0,
        description: token.description,
        logo_uri: undefined,
      };
    });

    graduations.sort((a, b) => b.score - a.score);

    const responseData = { graduations };
    bluechipCache.set(cacheKey, responseData, CACHE_TTL_MS);

    return NextResponse.json(responseData, {
      headers: {
        'X-Cache': 'MISS',
        'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
      },
    });
  } catch (err) {
    console.error('Blue chips API error:', err);
    // Graceful degradation: return empty graduations with 200 instead of 500
    return NextResponse.json({ graduations: [], error: 'Internal error', _fallback: true });
  }
}
