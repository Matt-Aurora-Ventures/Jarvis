/**
 * Dexter Market Intelligence Client
 *
 * Uses Anthropic Claude for market news, stock analysis, and sector trends.
 * Based on virattt/dexter financial analysis patterns.
 *
 * Coverage:
 * - xStocks (Solana stock tokens)
 * - preStocks (pre-IPO)
 * - Indexes (DeFi, NFT, Gaming)
 * - Solana ecosystem news
 * - Market regime detection
 */

export interface MarketNews {
    id: string;
    title: string;
    summary: string;
    source: string;
    sentiment: 'bullish' | 'neutral' | 'bearish';
    relevance: number; // 0-100
    category: 'crypto' | 'stocks' | 'macro' | 'regulatory' | 'technical';
    timestamp: number;
    symbols?: string[];
}

export interface StockAnalysis {
    symbol: string;
    name: string;
    sector: string;
    priceUsd: number;
    change24h: number;
    sentiment: number; // 0-100
    keyFactors: string[];
    risks: string[];
    opportunities: string[];
    recommendation: 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell';
}

export interface MarketRegime {
    regime: 'risk_on' | 'risk_off' | 'neutral' | 'volatile';
    confidence: number;
    indicators: {
        btcTrend: 'up' | 'down' | 'sideways';
        solTrend: 'up' | 'down' | 'sideways';
        volumeTrend: 'increasing' | 'decreasing' | 'stable';
        sentimentIndex: number;
    };
    recommendation: string;
    timestamp: number;
}

export interface SectorAnalysis {
    sector: string;
    score: number; // 0-100
    trend: 'bullish' | 'neutral' | 'bearish';
    topTokens: string[];
    keyDrivers: string[];
    risks: string[];
}

interface CacheEntry<T> {
    data: T;
    expiresAt: number;
}

const CACHE_TTL = {
    news: 5 * 60 * 1000, // 5 min
    analysis: 15 * 60 * 1000, // 15 min
    regime: 10 * 60 * 1000, // 10 min
};

export class DexterIntelClient {
    private apiKey: string;
    private baseUrl = 'https://api.anthropic.com/v1/messages';
    private model = 'claude-sonnet-4-20250514';
    private cache = new Map<string, CacheEntry<any>>();

    constructor(apiKey?: string) {
        this.apiKey = apiKey || process.env.NEXT_PUBLIC_ANTHROPIC_API_KEY || '';
    }

    private getHeaders(): HeadersInit {
        return {
            'Content-Type': 'application/json',
            'x-api-key': this.apiKey,
            'anthropic-version': '2023-06-01',
        };
    }

    private getCached<T>(key: string): T | null {
        const entry = this.cache.get(key);
        if (entry && entry.expiresAt > Date.now()) {
            return entry.data as T;
        }
        return null;
    }

    private setCache<T>(key: string, data: T, ttl: number) {
        this.cache.set(key, { data, expiresAt: Date.now() + ttl });
    }

    /**
     * Call Anthropic Claude for analysis
     */
    private async callClaude(systemPrompt: string, userPrompt: string): Promise<string | null> {
        if (!this.apiKey) {
            console.warn('Anthropic API key not configured');
            return null;
        }

        try {
            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: this.getHeaders(),
                body: JSON.stringify({
                    model: this.model,
                    max_tokens: 2000,
                    system: systemPrompt,
                    messages: [{ role: 'user', content: userPrompt }],
                }),
            });

            if (!response.ok) {
                console.error('Claude API error:', response.status);
                return null;
            }

            const result = await response.json();
            return result.content?.[0]?.text || null;
        } catch (error) {
            console.error('Claude API call failed:', error);
            return null;
        }
    }

    /**
     * Get market news summary
     */
    async getMarketNews(focus?: string): Promise<MarketNews[]> {
        const cacheKey = `news_${focus || 'general'}`;
        const cached = this.getCached<MarketNews[]>(cacheKey);
        if (cached) return cached;

        const systemPrompt = `You are a financial news analyst specializing in crypto and traditional markets.
Provide concise, actionable market news summaries. Focus on events that could impact trading decisions.
Return ONLY valid JSON array, no markdown.`;

        const userPrompt = `Generate 5 relevant market news items${focus ? ` focused on ${focus}` : ''}.

Return JSON array:
[
  {
    "id": "unique-id",
    "title": "News headline",
    "summary": "2-3 sentence summary with key implications",
    "source": "Source name",
    "sentiment": "bullish" | "neutral" | "bearish",
    "relevance": 0-100,
    "category": "crypto" | "stocks" | "macro" | "regulatory" | "technical",
    "symbols": ["SOL", "BTC"] // if applicable
  }
]

Focus on: Solana ecosystem, major crypto moves, regulatory news, macro events affecting risk assets.`;

        const response = await this.callClaude(systemPrompt, userPrompt);
        if (!response) return [];

        try {
            const jsonMatch = response.match(/\[[\s\S]*\]/);
            if (!jsonMatch) return [];

            const parsed = JSON.parse(jsonMatch[0]);
            const news = parsed.map((item: any) => ({
                ...item,
                timestamp: Date.now(),
            }));

            this.setCache(cacheKey, news, CACHE_TTL.news);
            return news;
        } catch (error) {
            console.error('Failed to parse news:', error);
            return [];
        }
    }

    /**
     * Analyze a stock/xStock
     */
    async analyzeStock(symbol: string, context?: { price?: number; sector?: string }): Promise<StockAnalysis | null> {
        const cacheKey = `stock_${symbol}`;
        const cached = this.getCached<StockAnalysis>(cacheKey);
        if (cached) return cached;

        const systemPrompt = `You are a financial analyst providing stock analysis for tokenized stocks on Solana.
Consider both traditional fundamentals and crypto-specific factors.
Return ONLY valid JSON, no markdown.`;

        const userPrompt = `Analyze ${symbol} for trading:
${context?.price ? `Current price: $${context.price}` : ''}
${context?.sector ? `Sector: ${context.sector}` : ''}

Return JSON:
{
  "symbol": "${symbol}",
  "name": "Full company name",
  "sector": "Sector name",
  "priceUsd": current_price,
  "change24h": percent_change,
  "sentiment": 0-100,
  "keyFactors": ["factor1", "factor2", "factor3"],
  "risks": ["risk1", "risk2"],
  "opportunities": ["opp1", "opp2"],
  "recommendation": "strong_buy" | "buy" | "hold" | "sell" | "strong_sell"
}`;

        const response = await this.callClaude(systemPrompt, userPrompt);
        if (!response) return null;

        try {
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (!jsonMatch) return null;

            const analysis = JSON.parse(jsonMatch[0]);
            this.setCache(cacheKey, analysis, CACHE_TTL.analysis);
            return analysis;
        } catch (error) {
            console.error('Failed to parse stock analysis:', error);
            return null;
        }
    }

    /**
     * Get current market regime
     */
    async getMarketRegime(): Promise<MarketRegime | null> {
        const cacheKey = 'market_regime';
        const cached = this.getCached<MarketRegime>(cacheKey);
        if (cached) return cached;

        const systemPrompt = `You are a macro market analyst determining the current risk environment.
Analyze crypto and traditional markets to determine if we're in risk-on, risk-off, or neutral conditions.
Return ONLY valid JSON, no markdown.`;

        const userPrompt = `Determine the current market regime for crypto trading.

Return JSON:
{
  "regime": "risk_on" | "risk_off" | "neutral" | "volatile",
  "confidence": 0-100,
  "indicators": {
    "btcTrend": "up" | "down" | "sideways",
    "solTrend": "up" | "down" | "sideways",
    "volumeTrend": "increasing" | "decreasing" | "stable",
    "sentimentIndex": 0-100
  },
  "recommendation": "One sentence trading recommendation"
}

Consider: BTC dominance, total crypto market cap trend, funding rates, DeFi TVL, social sentiment.`;

        const response = await this.callClaude(systemPrompt, userPrompt);
        if (!response) return null;

        try {
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (!jsonMatch) return null;

            const regime = {
                ...JSON.parse(jsonMatch[0]),
                timestamp: Date.now(),
            };

            this.setCache(cacheKey, regime, CACHE_TTL.regime);
            return regime;
        } catch (error) {
            console.error('Failed to parse regime:', error);
            return null;
        }
    }

    /**
     * Analyze a sector (DeFi, NFT, Gaming, etc.)
     */
    async analyzeSector(sector: string): Promise<SectorAnalysis | null> {
        const cacheKey = `sector_${sector}`;
        const cached = this.getCached<SectorAnalysis>(cacheKey);
        if (cached) return cached;

        const systemPrompt = `You are a crypto sector analyst specializing in Solana ecosystem.
Analyze sector health, trends, and opportunities.
Return ONLY valid JSON, no markdown.`;

        const userPrompt = `Analyze the ${sector} sector on Solana.

Return JSON:
{
  "sector": "${sector}",
  "score": 0-100,
  "trend": "bullish" | "neutral" | "bearish",
  "topTokens": ["TOKEN1", "TOKEN2", "TOKEN3"],
  "keyDrivers": ["driver1", "driver2"],
  "risks": ["risk1", "risk2"]
}`;

        const response = await this.callClaude(systemPrompt, userPrompt);
        if (!response) return null;

        try {
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (!jsonMatch) return null;

            const analysis = JSON.parse(jsonMatch[0]);
            this.setCache(cacheKey, analysis, CACHE_TTL.analysis);
            return analysis;
        } catch (error) {
            console.error('Failed to parse sector analysis:', error);
            return null;
        }
    }

    /**
     * Get AI trading recommendation
     */
    async getTradeRecommendation(
        token: { symbol: string; mint: string; price: number; sentiment: number }
    ): Promise<{
        action: 'buy' | 'sell' | 'hold';
        confidence: number;
        reasoning: string;
        suggestedTP: number;
        suggestedSL: number;
    } | null> {
        const systemPrompt = `You are a trading advisor for Solana tokens.
Provide specific, actionable recommendations with risk management.
Return ONLY valid JSON, no markdown.`;

        const userPrompt = `Trade recommendation for ${token.symbol}:
- Current price: $${token.price}
- Sentiment score: ${token.sentiment}/100

Return JSON:
{
  "action": "buy" | "sell" | "hold",
  "confidence": 0-100,
  "reasoning": "2-3 sentence explanation",
  "suggestedTP": take_profit_percent (e.g., 20 for 20%),
  "suggestedSL": stop_loss_percent (e.g., 10 for 10%)
}

Consider risk/reward ratio. Conservative approach for low sentiment scores.`;

        const response = await this.callClaude(systemPrompt, userPrompt);
        if (!response) return null;

        try {
            const jsonMatch = response.match(/\{[\s\S]*\}/);
            if (!jsonMatch) return null;

            return JSON.parse(jsonMatch[0]);
        } catch (error) {
            console.error('Failed to parse trade recommendation:', error);
            return null;
        }
    }

    /**
     * Clear all caches
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * Get regime display color
     */
    static getRegimeColor(regime: MarketRegime['regime']): string {
        switch (regime) {
            case 'risk_on': return '#22c55e';
            case 'risk_off': return '#FF6B6B';
            case 'volatile': return '#FFD700';
            default: return '#808080';
        }
    }
}

// Singleton
let instance: DexterIntelClient | null = null;

export function getDexterIntelClient(): DexterIntelClient {
    if (!instance) {
        instance = new DexterIntelClient();
    }
    return instance;
}
