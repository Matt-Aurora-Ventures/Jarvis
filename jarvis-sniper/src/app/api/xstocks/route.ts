import { NextResponse } from 'next/server';
import { XSTOCKS, PRESTOCKS, INDEXES, type TokenizedEquity } from '@/lib/xstocks-data';
import { ServerCache } from '@/lib/server-cache';
import { getCachedTVData, XSTOCKS_TO_TV_SYMBOL } from '@/lib/tv-screener';
import { calcTVEnhancedScoreDetailed } from '@/lib/tv-scoring';
import type { TVStockData } from '@/lib/tv-screener';

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
const xstocksCache = new ServerCache<any>();
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
  if (liq >= 500_000) score += 8;
  else if (liq >= 100_000) score += 5;
  else if (liq >= 50_000) score += 3;
  else score += 1;

  if (bsRatio >= 1.0 && bsRatio <= 2.5 && totalTxns >= 10) {
    score += 7; // healthy buying
  } else if (bsRatio >= 0.5 && bsRatio <= 3.5) {
    score += 4;
  } else {
    score += 1;
  }

  // Spread quality proxy (liq relative to volume)
  if (liq > 200_000 && volLiqRatio > 0.3) score += 5;
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
    const { searchParams } = new URL(request.url);
    const category = searchParams.get('category') || 'XSTOCK';
    const tokens = getCategoryTokens(category);

    if (tokens.length === 0) {
      return NextResponse.json({ graduations: [] });
    }

    // Check cache
    const cacheKey = `xstocks:${category.toUpperCase()}`;
    const cached = xstocksCache.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached, {
        headers: { 'X-Cache': 'HIT' },
      });
    }

    // Batch fetch pair data from DexScreener (max 30 addresses per request)
    const pairsByMint = new Map<string, any>();
    const mintAddresses = tokens.map(t => t.mintAddress);

    // Split into chunks of 30
    for (let i = 0; i < mintAddresses.length; i += 30) {
      const chunk = mintAddresses.slice(i, i + 30);
      const addresses = chunk.join(',');
      try {
        const res = await fetchWithTimeout(`${DEXSCREENER_TOKENS}/${addresses}`);
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
      };
    });

    // Sort by liquidity descending (most liquid tokens first)
    graduations.sort((a, b) => b.liquidity - a.liquidity);

    const responseData = { graduations };
    xstocksCache.set(cacheKey, responseData, CACHE_TTL_MS);

    return NextResponse.json(responseData, {
      headers: { 'X-Cache': 'MISS' },
    });
  } catch (err) {
    console.error('xStocks API error:', err);
    return NextResponse.json({ graduations: [], error: 'Internal error' }, { status: 500 });
  }
}
