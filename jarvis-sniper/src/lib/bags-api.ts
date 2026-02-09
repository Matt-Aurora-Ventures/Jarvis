/**
 * Bags.fm API Client for Sniper
 * Graduation detection + token data
 */

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
  // Insight-driven fields (from backtest v3)
  volume_24h?: number;
  boost_amount?: number;
  price_change_5m?: number;
  price_change_1h?: number;
  txn_buys_1h?: number;
  txn_sells_1h?: number;
  age_hours?: number;
  buy_sell_ratio?: number;
  total_txns_1h?: number;
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

const BASE_URL = 'https://public-api-v2.bags.fm/api';

async function apiFetch<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Accept': 'application/json' },
      cache: 'no-store',
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchGraduations(limit = 30): Promise<BagsGraduation[]> {
  const endpoints = [
    `/graduations?limit=${limit}`,
    `/tokens/graduated?limit=${limit}`,
    `/events/graduations?limit=${limit}`,
  ];

  for (const ep of endpoints) {
    const data = await apiFetch<any>(ep);
    if (data) {
      const grads = Array.isArray(data) ? data : (data.graduations || data.data || data.tokens || []);
      if (grads.length > 0) {
        return grads.map((g: any) => ({
          mint: g.mint || g.address || g.token_address || '',
          symbol: g.symbol || '',
          name: g.name || '',
          score: g.score || g.kr8tiv_score || calcScore(g),
          graduation_time: g.graduation_time || g.graduated_at || g.timestamp || Date.now() / 1000,
          bonding_curve_score: g.bonding_curve_score || g.bondingCurveScore || 0,
          holder_distribution_score: g.holder_distribution_score || g.holderScore || 0,
          liquidity_score: g.liquidity_score || g.liquidityScore || 0,
          social_score: g.social_score || g.socialScore || 0,
          market_cap: parseFloat(g.market_cap || g.marketCap || '0'),
          price_usd: parseFloat(g.price_usd || g.priceUsd || g.price || '0'),
          liquidity: parseFloat(g.liquidity || g.initial_liquidity || '0'),
          logo_uri: g.logo_uri || g.logoUri || g.image || undefined,
        }));
      }
    }
  }
  return [];
}

export async function fetchTokenInfo(mint: string): Promise<BagsToken | null> {
  const data = await apiFetch<any>(`/tokens/${mint}`);
  if (!data) return null;
  return {
    symbol: data.symbol || '',
    name: data.name || '',
    decimals: parseInt(data.decimals || '9'),
    price_usd: parseFloat(data.priceUsd || data.price_usd || '0'),
    liquidity: parseFloat(data.liquidity || '0'),
    volume_24h: parseFloat(data.volume24h || data.volume_24h || '0'),
    market_cap: parseFloat(data.marketCap || data.market_cap || '0'),
    mint,
  };
}

function calcScore(t: any): number {
  let score = 50;
  const liq = parseFloat(t.liquidity || '0');
  if (liq > 100000) score += 15;
  else if (liq > 10000) score += 10;
  else if (liq > 1000) score += 5;
  const vol = parseFloat(t.volume_24h || t.volume24h || '0');
  if (vol > 50000) score += 15;
  else if (vol > 10000) score += 10;
  else if (vol > 1000) score += 5;
  const holders = parseInt(t.holders || t.holder_count || '0');
  if (holders > 1000) score += 10;
  else if (holders > 100) score += 5;
  return Math.min(100, Math.max(0, score));
}
