import { NextResponse } from 'next/server';
import { XSTOCKS, PRESTOCKS, INDEXES, type TokenizedEquity } from '@/lib/xstocks-data';
import { ServerCache } from '@/lib/server-cache';

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

    // Map tokens to BagsGraduation format
    const graduations = tokens.map(token => {
      const pair = pairsByMint.get(token.mintAddress);
      return {
        mint: token.mintAddress,
        symbol: token.ticker,
        name: token.name,
        score: 50, // neutral score for equities
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
