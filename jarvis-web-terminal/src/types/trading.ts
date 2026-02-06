export interface TokenSentiment {
    symbol: string;
    name: string;
    price_usd: number;
    change_24h: number;
    sentiment: 'bullish' | 'bearish' | 'neutral';
    score: number;
    signal: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'SELL' | 'STRONG_SELL';
    summary: string;
}
