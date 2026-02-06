'use client';

import { useMemo } from 'react';
import { useTradingData } from '@/context/TradingContext';

export function useTreasuryMetrics() {
    const { state } = useTradingData();
    const { positions, history, metrics } = state;

    return useMemo(() => {
        // Determine Market Mood based on recent performance
        let sentiment: 'bull' | 'bear' | 'neutral' = 'neutral';
        if (metrics.winRate > 60 && metrics.totalPnL > 0) sentiment = 'bull';
        else if (metrics.winRate < 40 || metrics.totalPnL < 0) sentiment = 'bear';

        // Calculate formatting
        const winRateFormatted = metrics.winRate.toFixed(1) + '%';
        const sharpeFormatted = metrics.sharpeRatio.toFixed(2);
        const pnlFormatted = (metrics.totalPnL >= 0 ? '+' : '') + '$' + metrics.totalPnL.toFixed(2);

        // Status Emoji
        const moodEmoji = sentiment === 'bull' ? '🚀' : sentiment === 'bear' ? '🐻' : '⚖️';

        return {
            sentiment,
            moodEmoji,
            winRate: winRateFormatted,
            sharpe: sharpeFormatted,
            pnl: pnlFormatted,
            openPositionsCount: positions.length,
            recentTradesCount: history.length,
            rawData: metrics
        };
    }, [positions, history, metrics]);
}
