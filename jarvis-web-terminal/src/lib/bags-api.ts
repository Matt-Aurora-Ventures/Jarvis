/**
 * Bags.fm API Client v3
 *
 * Re-architected to use Jupiter Gems API as primary data source.
 * bags.fm tokens have LOCKED liquidity — liquidity is NOT a risk factor.
 *
 * For the full enriched data pipeline, see bags-data-service.ts.
 * This file re-exports types and provides backward-compatible helpers.
 */

export type {
  BagsTokenEnriched,
  ScoreBreakdown,
  JupiterTimeframeStat,
} from './bags-data-service';

export {
  fetchBagsTokens,
  fetchNewLaunches,
  fetchEstablishedTokens,
  fetchTokenCreatorDetail,
  getTokenStats,
} from './bags-data-service';

// ─── Backward-compatible types ───────────────────────────────────────────────

export interface BagsToken {
  symbol: string;
  name: string;
  decimals: number;
  price: number;
  price_usd: number;
  liquidity: number;
  volume_24h: number;
  market_cap: number;
  mint?: string;
}

export interface BagsCandle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

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
  logo_uri?: string;
  // Enriched fields from v3
  description?: string;
  holderCount?: number;
  volume_24h?: number;
  ageHours?: number;
  twitterUrl?: string;
  websiteUrl?: string;
  creator?: {
    wallet?: string;
    username?: string;
    pfp?: string;
    twitter?: string;
    website?: string;
    royaltyBps?: number;
  };
  isNewLaunch?: boolean;
  isEstablished?: boolean;
  scoreBreakdown?: {
    community: number;
    momentum: number;
    longevity: number;
    social: number;
    builder: number;
  };
}

export type ScoreTier = 'exceptional' | 'strong' | 'average' | 'weak' | 'poor';

export const getScoreTier = (score: number): ScoreTier => {
  if (score >= 85) return 'exceptional';
  if (score >= 70) return 'strong';
  if (score >= 50) return 'average';
  if (score >= 30) return 'weak';
  return 'poor';
};

export const TIER_COLORS: Record<ScoreTier, { bg: string; text: string; border: string }> = {
  exceptional: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  strong: { bg: 'bg-accent-success/10', text: 'text-accent-success', border: 'border-accent-success/30' },
  average: { bg: 'bg-accent-warning/10', text: 'text-text-muted', border: 'border-accent-warning/30' },
  weak: { bg: 'bg-accent-warning/10', text: 'text-accent-warning', border: 'border-accent-warning/30' },
  poor: { bg: 'bg-accent-error/10', text: 'text-accent-error', border: 'border-accent-error/30' },
};

// ─── Legacy BagsClient (chart data + individual token lookup) ────────────────

export class BagsClient {
  private baseUrl: string;

  constructor() {
    this.baseUrl = 'https://public-api-v2.bags.fm/api';
  }

  private async fetch<T>(path: string): Promise<T | null> {
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        headers: { 'Accept': 'application/json' },
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }

  async getTokenInfo(mint: string): Promise<BagsToken | null> {
    const data = await this.fetch<any>(`/tokens/${mint}`);
    if (!data) return null;
    return {
      symbol: data.symbol || '',
      name: data.name || '',
      decimals: parseInt(data.decimals || '9'),
      price: parseFloat(data.price || '0'),
      price_usd: parseFloat(data.priceUsd || data.price_usd || '0'),
      liquidity: parseFloat(data.liquidity || '0'),
      volume_24h: parseFloat(data.volume24h || data.volume_24h || '0'),
      market_cap: parseFloat(data.marketCap || data.market_cap || '0'),
      mint,
    };
  }

  async getChartData(
    mint: string,
    interval: '1m' | '5m' | '1h' | '4h' | '1d' = '1h',
    limit = 100,
  ): Promise<BagsCandle[] | null> {
    const safeLimit = Math.min(limit, 1000);
    const endpoints = [
      `/tokens/${mint}/candles?interval=${interval}&limit=${safeLimit}`,
      `/charts/${mint}?interval=${interval}&limit=${safeLimit}`,
      `/tokens/${mint}/ohlcv?resolution=${interval}&limit=${safeLimit}`,
    ];

    for (const endpoint of endpoints) {
      const data = await this.fetch<any>(endpoint);
      if (data) {
        const candles = Array.isArray(data) ? data : (data.candles || data.data || []);
        if (candles.length > 0) {
          return candles.map((c: any) => ({
            timestamp: c.timestamp || c.t || c.time || 0,
            open: parseFloat(c.open || c.o || 0),
            high: parseFloat(c.high || c.h || 0),
            low: parseFloat(c.low || c.l || 0),
            close: parseFloat(c.close || c.c || 0),
            volume: parseFloat(c.volume || c.v || 0),
          }));
        }
      }
    }
    return null;
  }

  /**
   * Get bags tokens — powered by Jupiter Gems API.
   * Returns enriched data with proper scoring.
   */
  async getGraduations(limit = 200): Promise<BagsGraduation[]> {
    const { fetchBagsTokens: fetchTokens } = await import('./bags-data-service');
    const tokens = await fetchTokens({ limit });

    return tokens.map(t => ({
      mint: t.mint,
      symbol: t.symbol,
      name: t.name,
      score: t.kr8tivScore,
      graduation_time: t.createdAt,
      bonding_curve_score: t.scoreBreakdown.momentum,
      holder_distribution_score: t.scoreBreakdown.community,
      liquidity_score: 100, // Always 100 — bags locks liquidity
      social_score: t.scoreBreakdown.social + t.scoreBreakdown.builder,
      market_cap: t.market_cap,
      price_usd: t.price_usd,
      logo_uri: t.icon,
      description: t.description,
      holderCount: t.holderCount,
      volume_24h: t.volume_24h,
      ageHours: t.ageHours,
      twitterUrl: t.twitterUrl,
      websiteUrl: t.websiteUrl,
      creator: t.creator,
      isNewLaunch: t.isNewLaunch,
      isEstablished: t.isEstablished,
      scoreBreakdown: t.scoreBreakdown,
    }));
  }

  async getTrending(limit = 10): Promise<BagsToken[]> {
    const data = await this.fetch<any>(`/tokens/trending?limit=${limit}`);
    if (!data) return [];
    const tokens = Array.isArray(data) ? data : (data.tokens || data.data || []);
    return tokens.map((t: any) => ({
      symbol: t.symbol || '',
      name: t.name || '',
      decimals: parseInt(t.decimals || '9'),
      price: parseFloat(t.price || '0'),
      price_usd: parseFloat(t.priceUsd || t.price_usd || '0'),
      liquidity: parseFloat(t.liquidity || '0'),
      volume_24h: parseFloat(t.volume24h || t.volume_24h || '0'),
      market_cap: parseFloat(t.marketCap || t.market_cap || '0'),
      mint: t.mint || t.address || '',
    }));
  }
}

export const bagsClient = new BagsClient();
