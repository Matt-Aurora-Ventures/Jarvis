import { NextResponse } from 'next/server';

/**
 * Server-side graduation feed using DexScreener API
 * Avoids CORS issues by proxying through our own API route
 *
 * Flow:
 * 1. Fetch latest boosted Solana tokens from DexScreener
 * 2. Batch-fetch pair data for price, liquidity, volume
 * 3. Score and return as graduation-format data
 */

const DEXSCREENER_BOOSTS = 'https://api.dexscreener.com/token-boosts/latest/v1';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';

interface BoostEntry {
  chainId: string;
  tokenAddress: string;
  description?: string;
  icon?: string;
  links?: Array<{ type?: string; url: string }>;
  totalAmount: number;
  amount: number;
}

export async function GET() {
  try {
    // 1. Fetch latest boosted Solana tokens
    const boostRes = await fetch(DEXSCREENER_BOOSTS, {
      headers: { 'Accept': 'application/json' },
      next: { revalidate: 30 },
    });

    if (!boostRes.ok) {
      return NextResponse.json({ graduations: [], error: 'DexScreener boosts unavailable' }, { status: 502 });
    }

    const allBoosts: BoostEntry[] = await boostRes.json();

    // Filter to Solana only, deduplicate by address
    const seen = new Set<string>();
    const solanaTokens = allBoosts.filter(b => {
      if (b.chainId !== 'solana' || seen.has(b.tokenAddress)) return false;
      seen.add(b.tokenAddress);
      return true;
    }).slice(0, 30);

    if (solanaTokens.length === 0) {
      return NextResponse.json({ graduations: [] });
    }

    // 2. Batch fetch pair data (max 30 addresses per call)
    const addresses = solanaTokens.map(t => t.tokenAddress).join(',');
    const pairRes = await fetch(`${DEXSCREENER_TOKENS}/${addresses}`, {
      headers: { 'Accept': 'application/json' },
      next: { revalidate: 30 },
    });

    const pairsByMint = new Map<string, any>();
    if (pairRes.ok) {
      const pairs: any[] = await pairRes.json();
      // Each entry is a pair — group by baseToken.address, pick highest liquidity
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

    // 3. Merge boost data + pair data into graduation format
    const graduations = solanaTokens.map(boost => {
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
      // Buy pressure (0-10)
      if (txnBuys > 0 && txnSells > 0) {
        const ratio = txnBuys / txnSells;
        if (ratio > 3) score += 10;
        else if (ratio > 2) score += 7;
        else if (ratio > 1.2) score += 4;
      }
      // Momentum bonus (0-5)
      if (priceChange5m > 5) score += 5;
      else if (priceChange5m > 0) score += 2;
      // Penalty for dumping
      if (priceChange1h < -30) score -= 15;
      else if (priceChange1h < -15) score -= 8;

      score = Math.min(100, Math.max(0, score));

      const iconUrl = boost.icon
        ? `https://dd.dexscreener.com/ds-data/tokens/solana/${boost.tokenAddress}.png`
        : pair?.info?.imageUrl || undefined;

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
        boost_amount: boost.totalAmount,
        price_change_5m: priceChange5m,
        price_change_1h: priceChange1h,
        txn_buys_1h: txnBuys,
        txn_sells_1h: txnSells,
      };
    });

    // Sort by score descending
    graduations.sort((a, b) => b.score - a.score);

    return NextResponse.json({ graduations });
  } catch (err) {
    console.error('Graduation API error:', err);
    return NextResponse.json({ graduations: [], error: 'Internal error' }, { status: 500 });
  }
}
