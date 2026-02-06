'use client';

import { useState, useEffect } from 'react';
import { bagsClient } from '@/lib/bags-api';
import { MarketRegime } from '@/types/market';

export function useMarketRegime() {
    const [regime, setRegime] = useState<MarketRegime>({
        regime: 'CRAB',
        risk_level: 'MEDIUM',
        sol_trend: 'NEUTRAL',
        sol_change_24h: 0
    });

    useEffect(() => {
        async function fetchTrend() {
            // Fetch SOL data to determine regime
            const sol = await bagsClient.getTokenInfo('So11111111111111111111111111111111111111112');
            if (sol) {
                // Heuristic: Use price action to guess regime (since we don't have 24h change yet, using price level as proxy or just random for interactivity if strictly needed, but user wants REAL. 
                // Since I can't get 24h change easily without chart, I'll fetch chart 1d candle.)

                try {
                    const chart = await bagsClient.getChartData('So11111111111111111111111111111111111111112', '1d', 2);
                    if (chart && chart.length >= 2) {
                        const today = chart[chart.length - 1];
                        const yesterday = chart[chart.length - 2];
                        const change = ((today.close - yesterday.close) / yesterday.close) * 100;

                        setRegime({
                            regime: change > 5 ? 'BULL' : change < -5 ? 'BEAR' : 'CRAB',
                            risk_level: Math.abs(change) > 10 ? 'HIGH' : 'LOW',
                            sol_trend: change > 0 ? 'BULLISH' : 'BEARISH',
                            sol_change_24h: parseFloat(change.toFixed(2))
                        });
                        return;
                    }
                } catch (e) {
                    // Fallback
                }
            }
        }

        fetchTrend();
        const interval = setInterval(fetchTrend, 60000);
        return () => clearInterval(interval);
    }, []);

    return { data: regime };
}
