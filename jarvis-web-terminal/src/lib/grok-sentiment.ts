/**
 * Grok 4.1 Sentiment API - Batch Token Analysis
 *
 * Features:
 * - Batch analysis (multiple tokens in single request = cost efficient)
 * - Budget tracking ($10/day limit)
 * - Caching with TTL
 * - Structured sentiment scores
 */

export interface TokenSentiment {
    mint: string;
    symbol: string;
    score: number; // 0-100
    signal: 'strong_buy' | 'buy' | 'neutral' | 'sell' | 'strong_sell';
    reasoning: string;
    factors: {
        social: number;
        technical: number;
        onChain: number;
        market: number;
    };
    confidence: number;
    timestamp: number;
}

export interface SentimentBatchResult {
    tokens: TokenSentiment[];
    totalCost: number;
    cachedCount: number;
    freshCount: number;
}

interface CacheEntry {
    sentiment: TokenSentiment;
    expiresAt: number;
}

// Daily budget tracking
interface BudgetState {
    date: string;
    spent: number;
    requests: number;
}

const DAILY_BUDGET = 10.0; // $10/day
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const COST_PER_1K_TOKENS = 0.003; // Approximate Grok cost

export class GrokSentimentClient {
    private apiKey: string;
    private baseUrl = 'https://api.x.ai/v1/chat/completions';
    private model = 'grok-beta'; // or 'grok-4.1' when available
    private cache = new Map<string, CacheEntry>();
    private budget: BudgetState;

    constructor(apiKey?: string) {
        this.apiKey = apiKey || process.env.NEXT_PUBLIC_XAI_API_KEY || '';
        this.budget = this.loadBudget();
    }

    private loadBudget(): BudgetState {
        const today = new Date().toISOString().split('T')[0];
        const stored = typeof localStorage !== 'undefined'
            ? localStorage.getItem('grok_budget')
            : null;

        if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed.date === today) {
                return parsed;
            }
        }

        return { date: today, spent: 0, requests: 0 };
    }

    private saveBudget() {
        if (typeof localStorage !== 'undefined') {
            localStorage.setItem('grok_budget', JSON.stringify(this.budget));
        }
    }

    private checkBudget(estimatedCost: number): boolean {
        // Reset if new day
        const today = new Date().toISOString().split('T')[0];
        if (this.budget.date !== today) {
            this.budget = { date: today, spent: 0, requests: 0 };
        }

        return this.budget.spent + estimatedCost <= DAILY_BUDGET;
    }

    private recordCost(cost: number) {
        this.budget.spent += cost;
        this.budget.requests++;
        this.saveBudget();
    }

    /**
     * Analyze a single token
     */
    async analyzeSingle(
        mint: string,
        symbol: string,
        context?: {
            price?: number;
            volume24h?: number;
            holders?: number;
            liquidity?: number;
        }
    ): Promise<TokenSentiment | null> {
        // Check cache
        const cached = this.cache.get(mint);
        if (cached && cached.expiresAt > Date.now()) {
            return cached.sentiment;
        }

        // Build prompt
        const prompt = this.buildSinglePrompt(symbol, mint, context);
        const result = await this.callGrok(prompt);

        if (!result) return null;

        try {
            const sentiment = this.parseSentimentResponse(result, mint, symbol);
            this.cache.set(mint, {
                sentiment,
                expiresAt: Date.now() + CACHE_TTL,
            });
            return sentiment;
        } catch (error) {
            console.error('Failed to parse sentiment:', error);
            return null;
        }
    }

    /**
     * Batch analyze multiple tokens (cost efficient!)
     */
    async analyzeBatch(
        tokens: Array<{ mint: string; symbol: string; price?: number; volume24h?: number }>
    ): Promise<SentimentBatchResult> {
        const result: SentimentBatchResult = {
            tokens: [],
            totalCost: 0,
            cachedCount: 0,
            freshCount: 0,
        };

        // Separate cached vs need-fresh
        const needFresh: typeof tokens = [];

        for (const token of tokens) {
            const cached = this.cache.get(token.mint);
            if (cached && cached.expiresAt > Date.now()) {
                result.tokens.push(cached.sentiment);
                result.cachedCount++;
            } else {
                needFresh.push(token);
            }
        }

        if (needFresh.length === 0) {
            return result;
        }

        // Batch analyze fresh tokens
        const batchPrompt = this.buildBatchPrompt(needFresh);
        const estimatedCost = (batchPrompt.length / 1000) * COST_PER_1K_TOKENS * 2; // Input + output

        if (!this.checkBudget(estimatedCost)) {
            console.warn('🚫 Daily budget exceeded for Grok sentiment');
            return result;
        }

        const response = await this.callGrok(batchPrompt);
        result.totalCost = estimatedCost;
        this.recordCost(estimatedCost);

        if (!response) return result;

        try {
            const parsed = this.parseBatchResponse(response, needFresh);
            for (const sentiment of parsed) {
                this.cache.set(sentiment.mint, {
                    sentiment,
                    expiresAt: Date.now() + CACHE_TTL,
                });
                result.tokens.push(sentiment);
                result.freshCount++;
            }
        } catch (error) {
            console.error('Failed to parse batch sentiment:', error);
        }

        return result;
    }

    private buildSinglePrompt(
        symbol: string,
        mint: string,
        context?: {
            price?: number;
            volume24h?: number;
            holders?: number;
            liquidity?: number;
        }
    ): string {
        let contextStr = '';
        if (context) {
            contextStr = `
Current metrics:
- Price: $${context.price?.toFixed(6) || 'N/A'}
- 24h Volume: $${context.volume24h?.toLocaleString() || 'N/A'}
- Holders: ${context.holders?.toLocaleString() || 'N/A'}
- Liquidity: $${context.liquidity?.toLocaleString() || 'N/A'}`;
        }

        return `Analyze this Solana token for trading sentiment:

Token: ${symbol}
Mint: ${mint}
${contextStr}

Provide a JSON response with:
{
  "score": 0-100 (0=extremely bearish, 100=extremely bullish),
  "signal": "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell",
  "reasoning": "2-3 sentence explanation",
  "factors": {
    "social": 0-100,
    "technical": 0-100,
    "onChain": 0-100,
    "market": 0-100
  },
  "confidence": 0-100
}

Consider: social sentiment, on-chain activity, holder distribution, liquidity depth, recent price action, market conditions.
Be objective and data-driven. If uncertain, reflect that in confidence score.`;
    }

    private buildBatchPrompt(
        tokens: Array<{ mint: string; symbol: string; price?: number; volume24h?: number }>
    ): string {
        const tokenList = tokens.map(t =>
            `- ${t.symbol} (${t.mint.slice(0, 8)}...): $${t.price?.toFixed(6) || 'N/A'}, Vol: $${t.volume24h?.toLocaleString() || 'N/A'}`
        ).join('\n');

        return `Analyze these Solana tokens for trading sentiment. Return a JSON array.

Tokens:
${tokenList}

Return ONLY valid JSON array, no markdown:
[
  {
    "symbol": "TOKEN",
    "score": 0-100,
    "signal": "strong_buy" | "buy" | "neutral" | "sell" | "strong_sell",
    "reasoning": "brief explanation",
    "factors": { "social": 0-100, "technical": 0-100, "onChain": 0-100, "market": 0-100 },
    "confidence": 0-100
  }
]

Be concise but accurate. Score 50 = neutral. Above 70 = bullish. Below 30 = bearish.`;
    }

    private async callGrok(prompt: string): Promise<string | null> {
        if (!this.apiKey) {
            console.warn('Grok API key not configured');
            return null;
        }

        try {
            const response = await fetch(this.baseUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.apiKey}`,
                },
                body: JSON.stringify({
                    model: this.model,
                    messages: [
                        {
                            role: 'system',
                            content: 'You are a crypto market analyst specializing in Solana tokens. Provide objective, data-driven sentiment analysis. Return only valid JSON.'
                        },
                        { role: 'user', content: prompt }
                    ],
                    temperature: 0.3, // Low for consistency
                    max_tokens: 2000,
                }),
            });

            if (!response.ok) {
                console.error('Grok API error:', response.status);
                return null;
            }

            const result = await response.json();
            return result.choices?.[0]?.message?.content || null;
        } catch (error) {
            console.error('Grok API call failed:', error);
            return null;
        }
    }

    private parseSentimentResponse(response: string, mint: string, symbol: string): TokenSentiment {
        // Try to extract JSON from response
        const jsonMatch = response.match(/\{[\s\S]*\}/);
        if (!jsonMatch) {
            throw new Error('No JSON found in response');
        }

        const parsed = JSON.parse(jsonMatch[0]);

        return {
            mint,
            symbol,
            score: parsed.score || 50,
            signal: parsed.signal || 'neutral',
            reasoning: parsed.reasoning || 'Analysis unavailable',
            factors: {
                social: parsed.factors?.social || 50,
                technical: parsed.factors?.technical || 50,
                onChain: parsed.factors?.onChain || 50,
                market: parsed.factors?.market || 50,
            },
            confidence: parsed.confidence || 50,
            timestamp: Date.now(),
        };
    }

    private parseBatchResponse(
        response: string,
        tokens: Array<{ mint: string; symbol: string }>
    ): TokenSentiment[] {
        // Try to extract JSON array from response
        const jsonMatch = response.match(/\[[\s\S]*\]/);
        if (!jsonMatch) {
            throw new Error('No JSON array found in response');
        }

        const parsed = JSON.parse(jsonMatch[0]);
        const results: TokenSentiment[] = [];

        for (const item of parsed) {
            // Match by symbol
            const token = tokens.find(t =>
                t.symbol.toLowerCase() === item.symbol?.toLowerCase()
            );

            if (token) {
                results.push({
                    mint: token.mint,
                    symbol: token.symbol,
                    score: item.score || 50,
                    signal: item.signal || 'neutral',
                    reasoning: item.reasoning || 'Analysis unavailable',
                    factors: {
                        social: item.factors?.social || 50,
                        technical: item.factors?.technical || 50,
                        onChain: item.factors?.onChain || 50,
                        market: item.factors?.market || 50,
                    },
                    confidence: item.confidence || 50,
                    timestamp: Date.now(),
                });
            }
        }

        return results;
    }

    /**
     * Get current budget status
     */
    getBudgetStatus() {
        const today = new Date().toISOString().split('T')[0];
        if (this.budget.date !== today) {
            return { spent: 0, remaining: DAILY_BUDGET, requests: 0 };
        }
        return {
            spent: this.budget.spent,
            remaining: DAILY_BUDGET - this.budget.spent,
            requests: this.budget.requests,
        };
    }

    /**
     * Clear cache (force refresh)
     */
    clearCache() {
        this.cache.clear();
    }

    /**
     * Get signal color for UI
     */
    static getSignalColor(signal: TokenSentiment['signal']): string {
        switch (signal) {
            case 'strong_buy': return '#00FF00';
            case 'buy': return '#22c55e';
            case 'neutral': return '#FFD700';
            case 'sell': return '#FF6B6B';
            case 'strong_sell': return '#FF0000';
            default: return '#808080';
        }
    }

    /**
     * Get score tier label
     */
    static getScoreTier(score: number): string {
        if (score >= 80) return 'Exceptional';
        if (score >= 65) return 'Strong';
        if (score >= 50) return 'Neutral';
        if (score >= 35) return 'Weak';
        return 'Poor';
    }
}

// Singleton
let instance: GrokSentimentClient | null = null;

export function getGrokSentimentClient(): GrokSentimentClient {
    if (!instance) {
        instance = new GrokSentimentClient();
    }
    return instance;
}
