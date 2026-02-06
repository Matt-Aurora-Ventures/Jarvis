/**
 * Sentiment Data Hook
 * 
 * React hook for fetching and managing sentiment dashboard data
 * with auto-refresh capability.
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { SentimentDashboardData } from '@/types/sentiment-types';
import { fetchAllSentimentData } from '@/lib/sentiment-api';

const REFRESH_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

interface UseSentimentDataOptions {
    autoRefresh?: boolean;
    refreshInterval?: number;
}

export function useSentimentData(options: UseSentimentDataOptions = {}) {
    const {
        autoRefresh = true,
        refreshInterval = REFRESH_INTERVAL_MS
    } = options;

    const [data, setData] = useState<SentimentDashboardData>({
        lastUpdated: new Date(),
        marketRegime: {
            btcTrend: 'NEUTRAL',
            solTrend: 'NEUTRAL',
            btcChange24h: 0,
            solChange24h: 0,
            solPrice: 0,
            riskLevel: 'NORMAL',
            regime: 'NEUTRAL',
        },
        trendingTokens: [],
        convictionPicks: [],
        macroAnalysis: {
            shortTerm: '',
            mediumTerm: '',
            longTerm: '',
            keyEvents: [],
        },
        stockPicks: [],
        commodityMovers: [],
        preciousMetals: {
            goldDirection: 'NEUTRAL',
            goldOutlook: '',
            silverDirection: 'NEUTRAL',
            silverOutlook: '',
            platinumDirection: 'NEUTRAL',
            platinumOutlook: '',
        },
        isLoading: true,
        error: null,
    });

    const intervalRef = useRef<NodeJS.Timeout | null>(null);
    const isMountedRef = useRef(true);

    const fetchData = useCallback(async () => {
        if (!isMountedRef.current) return;

        setData(prev => ({ ...prev, isLoading: true, error: null }));

        try {
            const newData = await fetchAllSentimentData();

            if (isMountedRef.current) {
                setData({
                    ...newData,
                    isLoading: false,
                    error: null,
                });
            }
        } catch (error) {
            console.error('Failed to fetch sentiment data:', error);

            if (isMountedRef.current) {
                setData(prev => ({
                    ...prev,
                    isLoading: false,
                    error: error instanceof Error ? error.message : 'Failed to fetch data',
                }));
            }
        }
    }, []);

    // Initial fetch
    useEffect(() => {
        isMountedRef.current = true;
        fetchData();

        return () => {
            isMountedRef.current = false;
        };
    }, [fetchData]);

    // Auto-refresh
    useEffect(() => {
        if (!autoRefresh) return;

        intervalRef.current = setInterval(fetchData, refreshInterval);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, [autoRefresh, refreshInterval, fetchData]);

    const refresh = useCallback(() => {
        fetchData();
    }, [fetchData]);

    // Calculate derived stats
    const stats = {
        bullishCount: data.trendingTokens.filter(
            t => t.sentimentLabel === 'BULLISH' || t.sentimentLabel === 'SLIGHTLY BULLISH'
        ).length,
        bearishCount: data.trendingTokens.filter(
            t => t.sentimentLabel === 'BEARISH' || t.sentimentLabel === 'SLIGHTLY BEARISH'
        ).length,
        neutralCount: data.trendingTokens.filter(
            t => t.sentimentLabel === 'NEUTRAL'
        ).length,
        topGainer: data.trendingTokens.reduce(
            (best, t) => (t.change24h > (best?.change24h || -Infinity) ? t : best),
            data.trendingTokens[0]
        ),
        topLoser: data.trendingTokens.reduce(
            (worst, t) => (t.change24h < (worst?.change24h || Infinity) ? t : worst),
            data.trendingTokens[0]
        ),
        avgBuySellRatio: data.trendingTokens.length > 0
            ? data.trendingTokens.reduce((sum, t) => sum + t.buySellRatio, 0) / data.trendingTokens.length
            : 1,
    };

    return {
        ...data,
        stats,
        refresh,
        timeSinceUpdate: Math.floor((Date.now() - data.lastUpdated.getTime()) / 1000 / 60), // minutes
    };
}

export type SentimentDataReturn = ReturnType<typeof useSentimentData>;
