'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
    getGrokSentimentClient,
    TokenSentiment as GrokTokenSentiment,
} from '@/lib/grok-sentiment';
import { useSentimentData } from '@/hooks/useSentimentData';

const DEFAULT_REFRESH_INTERVAL = 20 * 60 * 1000; // 20 minutes
const DEFAULT_MAX_TOKENS = 10;

export interface UseGrokLiveOptions {
    enabled?: boolean;
    refreshInterval?: number; // ms, default 20 minutes
    maxTokens?: number; // max tokens to analyze per batch, default 10
}

export interface BudgetStatus {
    spent: number;
    remaining: number;
    requests: number;
}

export interface UseGrokLiveReturn {
    scores: Map<string, GrokTokenSentiment>;
    countdown: number; // seconds until next refresh
    isRefreshing: boolean;
    lastRefreshed: Date | null;
    budgetStatus: BudgetStatus | null;
    forceRefresh: () => Promise<void>;
    error: string | null;
}

export function useGrokLive(options: UseGrokLiveOptions = {}): UseGrokLiveReturn {
    const {
        enabled = true,
        refreshInterval = DEFAULT_REFRESH_INTERVAL,
        maxTokens = DEFAULT_MAX_TOKENS,
    } = options;

    const [scores, setScores] = useState<Map<string, GrokTokenSentiment>>(new Map());
    const [countdown, setCountdown] = useState<number>(Math.floor(refreshInterval / 1000));
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
    const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null);
    const [error, setError] = useState<string | null>(null);

    const isMountedRef = useRef(true);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
    const countdownTimerRef = useRef<NodeJS.Timeout | null>(null);
    const lastRefreshTimeRef = useRef<number>(0);

    const { trendingTokens } = useSentimentData({ autoRefresh: false });

    const runAnalysis = useCallback(async () => {
        if (!isMountedRef.current) return;

        const grokClient = getGrokSentimentClient();

        // Build batch input from trending tokens
        const tokensToAnalyze = trendingTokens
            .slice(0, maxTokens)
            .map((t) => ({
                mint: t.contractAddress,
                symbol: t.symbol,
                price: t.priceUsd,
                volume24h: t.volume24h,
            }));

        if (tokensToAnalyze.length === 0) {
            setError('No trending tokens available to analyze');
            return;
        }

        setIsRefreshing(true);
        setError(null);

        try {
            const result = await grokClient.analyzeBatch(tokensToAnalyze);

            if (!isMountedRef.current) return;

            // Merge new results into existing scores map
            setScores((prev) => {
                const next = new Map(prev);
                for (const sentiment of result.tokens) {
                    next.set(sentiment.mint, sentiment);
                }
                return next;
            });

            setLastRefreshed(new Date());
            lastRefreshTimeRef.current = Date.now();
            setBudgetStatus(grokClient.getBudgetStatus());
        } catch (err) {
            if (!isMountedRef.current) return;
            const message = err instanceof Error ? err.message : 'Grok analysis failed';
            setError(message);
            console.error('useGrokLive analysis error:', err);
        } finally {
            if (isMountedRef.current) {
                setIsRefreshing(false);
            }
        }
    }, [trendingTokens, maxTokens]);

    const forceRefresh = useCallback(async () => {
        // Reset countdown on force refresh
        setCountdown(Math.floor(refreshInterval / 1000));
        lastRefreshTimeRef.current = Date.now();
        await runAnalysis();
    }, [runAnalysis, refreshInterval]);

    // Initial analysis + periodic refresh
    useEffect(() => {
        if (!enabled) return;

        // Run initial analysis
        runAnalysis();

        // Set up periodic refresh
        refreshTimerRef.current = setInterval(() => {
            runAnalysis();
        }, refreshInterval);

        return () => {
            if (refreshTimerRef.current) {
                clearInterval(refreshTimerRef.current);
                refreshTimerRef.current = null;
            }
        };
    }, [enabled, refreshInterval, runAnalysis]);

    // Countdown timer - ticks every second
    useEffect(() => {
        if (!enabled) return;

        // Initialize the reference time if not set
        if (lastRefreshTimeRef.current === 0) {
            lastRefreshTimeRef.current = Date.now();
        }

        countdownTimerRef.current = setInterval(() => {
            if (!isMountedRef.current) return;

            const elapsed = Date.now() - lastRefreshTimeRef.current;
            const remaining = Math.max(0, Math.floor((refreshInterval - elapsed) / 1000));
            setCountdown(remaining);
        }, 1000);

        return () => {
            if (countdownTimerRef.current) {
                clearInterval(countdownTimerRef.current);
                countdownTimerRef.current = null;
            }
        };
    }, [enabled, refreshInterval]);

    // Update budget status on mount
    useEffect(() => {
        if (!enabled) return;
        const grokClient = getGrokSentimentClient();
        setBudgetStatus(grokClient.getBudgetStatus());
    }, [enabled]);

    // Cleanup on unmount
    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    return {
        scores,
        countdown,
        isRefreshing,
        lastRefreshed,
        budgetStatus,
        forceRefresh,
        error,
    };
}
