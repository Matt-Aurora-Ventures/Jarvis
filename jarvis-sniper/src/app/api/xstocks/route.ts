import { NextResponse } from 'next/server';
import { XSTOCKS, PRESTOCKS, INDEXES, type TokenizedEquity } from '@/lib/xstocks-data';
import { AsyncServerCache } from '@/lib/server-cache';
import { getCachedTVData, XSTOCKS_TO_TV_SYMBOL } from '@/lib/tv-screener';
import { calcTVEnhancedScoreDetailed } from '@/lib/tv-scoring';
import type { TVStockData } from '@/lib/tv-screener';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { buildDataPointProvenance } from '@/lib/data-plane/provenance';
import { deriveRedundancyState, scoreSourceReliability } from '@/lib/data-plane/reliability';
import { recordSourceHealth } from '@/lib/data-plane/health-store';
import { buildDatasetManifestV2, persistDatasetManifestV2 } from '@/lib/data-plane/manifest-v2';

/**
 * xStocks / PreStocks / Indexes API route
 *
 * Fetches live price data from DexScreener for the curated token registry,
 * then returns data formatted as BagsGraduation[] so the scanner can display
 * these tokens seamlessly alongside memecoins.
 *
 * Query params:
 *   ?category=XSTOCK|PRESTOCK|INDEX  (default: XSTOCK)
 *
 * Caching: 30-second in-memory cache per category to avoid hammering DexScreener.
 */

const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';

// 30-second cache per category
const xstocksCache = new AsyncServerCache<any>('xstocks-feed');
const CACHE_TTL_MS = 30_000;

/** Fetch with timeout to prevent hanging */
async function fetchWithTimeout(url: string, timeoutMs = 10000): Promise<Response> {
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

/**
 * Legacy: kept for reference. Active scoring uses calcTVEnhancedScore from tv-scoring.ts
 *
 * Dynamic scoring for xStocks/PreStocks/Indexes.
 *
 * Traditional assets have guaranteed liquidity (backed by real stocks),
 * so scoring focuses on:
 * - Trading Activity (0-30): Volume, transaction count
 * - Price Momentum (0-30): Trending strength, directional clarity
 * - Market Quality (0-20): B/S ratio, spread health
 * - Asset Class Bonus (0-20): Blue chip stocks > speculative pre-IPO
 */
function calcEquityScore(
  token: TokenizedEquity,
  pair: any,
): number {
  if (!pair) return 35;

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

  // ─── Trading Activity (0-30) ───
  if (volLiqRatio >= 2.0) score += 20;
  else if (volLiqRatio >= 1.0) score += 16;
  else if (volLiqRatio >= 0.5) score += 12;
  else if (volLiqRatio >= 0.2) score += 8;
  else score += 4;

  if (totalTxns >= 200) score += 10;
  else if (totalTxns >= 50) score += 7;
  else if (totalTxns >= 20) score += 5;
  else if (totalTxns >= 5) score += 3;
  else score += 1;

  // ─── Price Momentum (0-30) ───
  const absChange1h = Math.abs(change1h);
  if (absChange1h >= 3) score += 15;  // Strong move for a stock
  else if (absChange1h >= 1.5) score += 12;
  else if (absChange1h >= 0.5) score += 8;
  else score += 4;  // Very flat

  // Trend consistency (1h and 24h aligned)
  if ((change1h > 0 && change24h > 0) || (change1h < 0 && change24h < 0)) {
    score += 10; // aligned trend
  } else if (Math.abs(change24h) < 1) {
    score += 5; // rangebound — can still trade mean reversion
  } else {
    score += 3; // mixed signals
  }

  // Strong intraday momentum bonus
  if (absChange1h >= 5) score += 5;

  // ─── Market Quality (0-20) ───
  // Liquidity is NOT a quality signal for tokenized equities — the platform
  // guarantees it. Instead, weight buy/sell health and trading activity depth.
  score += 8; // Baseline: platform-backed liquidity

  if (bsRatio >= 1.0 && bsRatio <= 2.5 && totalTxns >= 10) {
    score += 7; // healthy buying
  } else if (bsRatio >= 0.5 && bsRatio <= 3.5) {
    score += 4;
  } else {
    score += 1;
  }

  // Activity depth proxy (transaction count relative to typical)
  if (totalTxns >= 100) score += 5;
  else if (totalTxns >= 20) score += 3;
  else score += 2;

  // ─── Asset Class Bonus (0-20) ───
  const cat = token.category;
  const sector = token.sector.toLowerCase();
  if (cat === 'INDEX') {
    // Indexes get high structural score (diversified, always liquid)
    score += 15;
    if (token.ticker === 'TQQQx') score -= 3; // Leveraged = riskier
  } else if (cat === 'XSTOCK') {
    // Blue chip stocks
    if (['technology', 'finance'].includes(sector)) score += 12;
    else if (['healthcare', 'consumer', 'energy'].includes(sector)) score += 10;
    else score += 8;
    // Mega-cap bonus
    if (['AAPLx', 'MSFTx', 'GOOGLx', 'AMZNx', 'NVDAx', 'METAx'].includes(token.ticker)) {
      score += 5;
    }
  } else if (cat === 'PRESTOCK') {
    // Pre-IPO = more speculative
    score += 5;
  } else if (cat === 'COMMODITY') {
    score += 12; // Gold = stable
  }

  return Math.max(10, Math.min(100, Math.round(score)));
}

function getCategoryTokens(category: string): TokenizedEquity[] {
  switch (category.toUpperCase()) {
    case 'XSTOCK': return XSTOCKS;
    case 'PRESTOCK': return PRESTOCKS;
    case 'INDEX': return INDEXES;
    default: return XSTOCKS;
  }
}

export async function GET(request: Request) {
  try {
    // Rate limit check
    const ip = getClientIp(request);
    const limit = await apiRateLimiter.check(ip);
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
    const category = searchParams.get('category') || 'XSTOCK';
    const tokens = getCategoryTokens(category);

    if (tokens.length === 0) {
      return NextResponse.json({ graduations: [] });
    }

    // Check cache
    const cacheKey = `xstocks:${category.toUpperCase()}`;
    const cached = await xstocksCache.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached, {
        headers: {
          'X-Cache': 'HIT',
          'X-RateLimit-Remaining': String(limit.remaining),
          'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
        },
      });
    }

    // Batch fetch pair data from DexScreener (max 30 addresses per request)
    const pairsByMint = new Map<string, any>();
    const mintAddresses = tokens.map(t => t.mintAddress);
    const dexFetchStartedAt = Date.now();
    let dexLatencyMsTotal = 0;
    let dexCalls = 0;
    let dexFailures = 0;

    // Split into chunks of 30
    for (let i = 0; i < mintAddresses.length; i += 30) {
      const chunk = mintAddresses.slice(i, i + 30);
      const addresses = chunk.join(',');
      const chunkStartedAt = Date.now();
      try {
        const res = await fetchWithTimeout(`${DEXSCREENER_TOKENS}/${addresses}`);
        dexCalls += 1;
        dexLatencyMsTotal += Date.now() - chunkStartedAt;
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
        } else {
          dexFailures += 1;
        }
      } catch {
        dexCalls += 1;
        dexFailures += 1;
        dexLatencyMsTotal += Date.now() - chunkStartedAt;
        // Continue with partial data if one chunk fails
      }
    }

    // Fetch TradingView data (cached, non-blocking)
    let tvData: Record<string, TVStockData> = {};
    try {
      tvData = await getCachedTVData();
    } catch {
      // TV data is a nice-to-have, not a requirement
    }

    // Map tokens to BagsGraduation format
    const nowIso = new Date().toISOString();
    const dexLatencyMs = dexCalls > 0 ? Math.round(dexLatencyMsTotal / dexCalls) : (Date.now() - dexFetchStartedAt);
    const dexOk = dexCalls === 0 ? true : dexFailures < dexCalls;
    const dexReliability = scoreSourceReliability({
      ok: dexOk,
      latencyMs: dexLatencyMs,
      httpStatus: dexOk ? 200 : 500,
      freshnessMs: 0,
      errorBudgetBurn: dexCalls > 0 ? (dexFailures / dexCalls) : 0,
    });
    await recordSourceHealth({
      source: 'dexscreener:xstocks',
      checkedAt: nowIso,
      ok: dexOk,
      freshnessMs: 0,
      latencyMs: dexLatencyMs,
      httpStatus: dexOk ? 200 : 500,
      reliabilityScore: dexReliability,
      errorBudgetBurn: dexCalls > 0 ? (dexFailures / dexCalls) : 0,
      redundancyState: deriveRedundancyState(2),
    });

    const graduations = tokens.map(token => {
      const pair = pairsByMint.get(token.mintAddress);
      const tvTicker = XSTOCKS_TO_TV_SYMBOL[token.ticker];
      const tvStock = tvTicker ? tvData[tvTicker] ?? null : null;
      const scoreDetails = calcTVEnhancedScoreDetailed(tvStock, pair, token);
      return {
        mint: token.mintAddress,
        symbol: token.ticker,
        name: token.name,
        score: scoreDetails.composite,
        graduation_time: Date.now() / 1000, // established tokens
        bonding_curve_score: 0,
        holder_distribution_score: 0,
        liquidity_score: 0,
        social_score: 0,
        market_cap: pair?.fdv || pair?.marketCap || 0,
        liquidity: parseFloat(pair?.liquidity?.usd || '0'),
        volume_24h: parseFloat(pair?.volume?.h24 || '0'),
        price_usd: parseFloat(pair?.priceUsd || '0'),
        price_change_5m: pair?.priceChange?.m5 || 0,
        price_change_1h: pair?.priceChange?.h1 || 0,
        price_change_24h: pair?.priceChange?.h24 || 0,
        txn_buys_1h: pair?.txns?.h1?.buys || 0,
        txn_sells_1h: pair?.txns?.h1?.sells || 0,
        age_hours: 99999, // established tokens
        buy_sell_ratio: 1.0,
        total_txns_1h: (pair?.txns?.h1?.buys || 0) + (pair?.txns?.h1?.sells || 0),
        dex_id: pair?.dexId || 'unknown',
        source: token.category.toLowerCase(),
        fdv: pair?.fdv || 0,
        description: token.description,
        logo_uri: undefined,
        // TV-enhanced scoring breakdown
        tv_enhanced: scoreDetails.hasTVData,
        tv_momentum: scoreDetails.momentum,
        tv_volume_confirmation: scoreDetails.volumeConfirmation,
        tv_base_score: scoreDetails.baseEquityScore,
        provenance: buildDataPointProvenance({
          source: 'dexscreener',
          fetchedAt: nowIso,
          latencyMs: dexLatencyMs,
          httpStatus: dexOk ? 200 : 500,
          reliabilityScore: dexReliability,
          raw: {
            mint: token.mintAddress,
            pairAddress: pair?.pairAddress || null,
            category: token.category,
          },
        }),
      };
    });


    // Sort by score descending (liquidity is not a signal for tokenized equities)
    graduations.sort((a, b) => (b.score - a.score) || (b.volume_24h - a.volume_24h));

    const manifest = buildDatasetManifestV2({
      family: `xstocks_${category.toLowerCase()}`,
      surface: 'tradfi',
      timeRange: {
        from: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
        to: nowIso,
      },
      records: graduations.map((g) => ({
        mint: g.mint,
        symbol: g.symbol,
        score: g.score,
        source: g.source,
        provenance: g.provenance,
      })),
    });
    const manifestPersisted = await persistDatasetManifestV2(manifest).catch(() => null);

    const responseData = {
      graduations,
      meta: {
        category: category.toUpperCase(),
        datasetManifestId: manifest.datasetId,
        datasetManifestSha256: manifest.sha256,
        datasetManifestPath: manifestPersisted?.path || null,
        sourceReliability: {
          dexscreener: dexReliability,
        },
      },
    };
    await xstocksCache.set(cacheKey, responseData, CACHE_TTL_MS);

    return NextResponse.json(responseData, {
      headers: {
        'X-Cache': 'MISS',
        'Cache-Control': 'public, s-maxage=30, stale-while-revalidate=60',
      },
    });
  } catch (err) {
    console.error('xStocks API error:', err);
    // Graceful degradation: return empty graduations with 200 instead of 500
    return NextResponse.json({ graduations: [], error: 'Internal error', _fallback: true });
  }
}
