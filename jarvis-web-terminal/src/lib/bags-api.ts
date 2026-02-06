/**
 * Bags.fm API Client v2
 * Updated to use public-api-v2.bags.fm endpoints
 */

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
    strong: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
    average: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
    weak: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30' },
    poor: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
};

export class BagsClient {
    private baseUrl: string;
    private apiKey?: string;

    constructor(apiKey?: string) {
        // Using the correct v2 API base URL
        this.baseUrl = 'https://public-api-v2.bags.fm/api';
        this.apiKey = apiKey || process.env.NEXT_PUBLIC_BAGS_API_KEY;
    }

    private async fetch<T>(path: string, options: RequestInit = {}): Promise<T | null> {
        try {
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            };

            if (this.apiKey) {
                headers['x-api-key'] = this.apiKey;
            }

            const response = await fetch(`${this.baseUrl}${path}`, {
                ...options,
                headers: {
                    ...headers,
                    ...options.headers,
                },
            });

            if (!response.ok) {
                if (response.status === 404) return null;
                console.warn(`Bags API: ${response.status} for ${path}`);
                return null;
            }

            return await response.json();
        } catch (error) {
            console.error('Bags API Request Failed:', error);
            return null;
        }
    }

    /**
     * Get token information from Bags.fm
     */
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
            mint: mint,
        };
    }

    /**
     * Get price chart data for a token
     */
    async getChartData(mint: string, interval: '1m' | '5m' | '1h' | '4h' | '1d' = '1h', limit: number = 100): Promise<BagsCandle[] | null> {
        const safeLimit = Math.min(limit, 1000);

        // Try multiple endpoint formats
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
     * Get recent token graduations (bonding curve completions)
     */
    async getGraduations(limit: number = 20): Promise<BagsGraduation[]> {
        // Try multiple possible endpoints
        const endpoints = [
            `/graduations?limit=${limit}`,
            `/tokens/graduated?limit=${limit}`,
            `/events/graduations?limit=${limit}`,
        ];

        for (const endpoint of endpoints) {
            const data = await this.fetch<any>(endpoint);
            if (data) {
                const grads = Array.isArray(data) ? data : (data.graduations || data.data || data.tokens || []);
                if (grads.length > 0) {
                    return grads.map((g: any) => ({
                        mint: g.mint || g.address || g.token_address || '',
                        symbol: g.symbol || '',
                        name: g.name || '',
                        score: g.score || g.kr8tiv_score || this.calculateScore(g),
                        graduation_time: g.graduation_time || g.graduated_at || g.timestamp || Date.now() / 1000,
                        bonding_curve_score: g.bonding_curve_score || g.bondingCurveScore || 0,
                        holder_distribution_score: g.holder_distribution_score || g.holderScore || 0,
                        liquidity_score: g.liquidity_score || g.liquidityScore || 0,
                        social_score: g.social_score || g.socialScore || 0,
                        market_cap: parseFloat(g.market_cap || g.marketCap || '0'),
                        price_usd: parseFloat(g.price_usd || g.priceUsd || g.price || '0'),
                        logo_uri: g.logo_uri || g.logoUri || g.image || undefined,
                    }));
                }
            }
        }

        return [];
    }

    /**
     * Calculate a synthetic score if not provided
     */
    private calculateScore(token: any): number {
        // Synthetic scoring based on available metrics
        let score = 50; // Base score

        // Liquidity factor
        const liquidity = parseFloat(token.liquidity || '0');
        if (liquidity > 100000) score += 15;
        else if (liquidity > 10000) score += 10;
        else if (liquidity > 1000) score += 5;

        // Volume factor
        const volume = parseFloat(token.volume_24h || token.volume24h || '0');
        if (volume > 50000) score += 15;
        else if (volume > 10000) score += 10;
        else if (volume > 1000) score += 5;

        // Holder distribution (if available)
        const holders = parseInt(token.holders || token.holder_count || '0');
        if (holders > 1000) score += 10;
        else if (holders > 100) score += 5;

        return Math.min(100, Math.max(0, score));
    }

    /**
     * Get trending tokens
     */
    async getTrending(limit: number = 10): Promise<BagsToken[]> {
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
