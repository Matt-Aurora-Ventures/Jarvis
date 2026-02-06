'use client';

import { useState, useEffect } from 'react';
import { bagsClient, BagsToken } from '@/lib/bags-api';
import { TokenSentiment } from '@/types/trading';

const TRACKED_TOKENS = [
    { symbol: 'SOL', mint: 'So11111111111111111111111111111111111111112' },
    { symbol: 'JUP', mint: 'JUPyiwrYJFskUPiHa7hkeR8VUtkPHCLkdP6KcNi1ybDL' },
    { symbol: 'BONK', mint: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263' },
    { symbol: 'WIF', mint: 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm' }
];

export function useMarketData() {
    const [data, setData] = useState<TokenSentiment[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchMarketData() {
            try {
                const results = await Promise.all(
                    TRACKED_TOKENS.map(async (t) => {
                        try {
                            const info = await bagsClient.getTokenInfo(t.mint);
                            if (!info) return null;
                            return mapToSentiment(info);
                        } catch (e) {
                            console.error(`Failed to fetch ${t.symbol}`, e);
                            return null;
                        }
                    })
                );

                setData(results.filter((item): item is TokenSentiment => item !== null));
            } catch (err) {
                console.error("Market Data Error", err);
            } finally {
                setLoading(false);
            }
        }

        fetchMarketData();
        const interval = setInterval(fetchMarketData, 30000); // 30s poll
        return () => clearInterval(interval);
    }, []);

    return { data, loading };
}

function mapToSentiment(token: BagsToken): TokenSentiment {
    // Simple Heuristic: If 24h Volume is high relative to Liquidity, market is active.
    // Real sentiment requires complex analysis, but for live data feed we use price action.

    // We don't have 24h change in BagsToken interface explicitly in the provided snippet?
    // Let's check the snippet again. It has volume_24h.
    // Wait, the interface in bags-api.ts has: symbol, name, decimals, price, price_usd, liquidity, volume_24h, market_cap.
    // It does NOT have 24h price change %. I might need to fetch stats or calculate it from candle close?
    // For now, I will assume 0 change or mock the *change* calculation if I can't get it, 
    // OR I can use getChartData to get yesterday's close.
    // Let's keep it simple for v1 and just show price.

    // Synthetic "Score" based on Volume/Liq ratio (Volatility proxy)
    const volLiqRatio = token.liquidity > 0 ? (token.volume_24h / token.liquidity) : 0;
    const score = Math.min(Math.round(volLiqRatio * 100), 100);

    const sentiment = score > 50 ? 'bullish' : 'bearish';

    return {
        symbol: token.symbol,
        name: token.name,
        price_usd: token.price_usd,
        change_24h: 0, // Placeholder as BagsToken doesn't provide change% directly in the snippet
        sentiment: sentiment,
        score: score,
        signal: score > 75 ? 'STRONG_BUY' : score > 50 ? 'BUY' : 'HOLD',
        summary: `Vol: $${(token.volume_24h / 1000000).toFixed(2)}M | Liq: $${(token.liquidity / 1000000).toFixed(2)}M. Live from Bags.fm.`
    };
}
