'use client';

/**
 * useConfidence Hook - Real-time confidence monitoring for trading safety
 * 
 * Provides:
 * - Live Pyth confidence intervals for established assets
 * - Bags.fm synthetic confidence for micro-cap tokens
 * - Circuit breaker status
 * - Trading safety indicators
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { pythClient, PYTH_PRICE_FEEDS, PriceData } from '@/lib/pyth-client';
import { confidenceRouter, ConfidenceResult, CircuitBreakerStatus } from '@/lib/confidence-router';

export interface ConfidenceState {
    price: number;
    confidence: number;
    confidenceScore: number;
    confidenceRatio: number;
    tier: 'established' | 'micro' | 'unknown';
    source: PriceData['source'];
    isSafeToTrade: boolean;
    isVolatile: boolean;
    reason?: string;
    lastUpdated: number;
}

export interface UseConfidenceOptions {
    symbol?: string;
    mint?: string;
    sigmaMultiplier?: number;
    pollInterval?: number;
    autoStart?: boolean;
}

const DEFAULT_OPTIONS: Required<UseConfidenceOptions> = {
    symbol: 'SOL',
    mint: '',
    sigmaMultiplier: 2.0,
    pollInterval: 1000, // 1 second
    autoStart: true,
};

export function useConfidence(options: UseConfidenceOptions = {}) {
    const opts = { ...DEFAULT_OPTIONS, ...options };

    const [state, setState] = useState<ConfidenceState>({
        price: 0,
        confidence: 0,
        confidenceScore: 0,
        confidenceRatio: 0,
        tier: 'unknown',
        source: 'synthetic',
        isSafeToTrade: true,
        isVolatile: false,
        lastUpdated: 0,
    });

    const [circuitBreaker, setCircuitBreaker] = useState<CircuitBreakerStatus>({
        isTripped: false,
    });

    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Check confidence from router
    const checkConfidence = useCallback(async () => {
        try {
            const result = await confidenceRouter.getValidatedPrice(
                opts.symbol,
                opts.mint || undefined,
                { sigmaMultiplier: opts.sigmaMultiplier }
            );

            // Calculate volatility flag (> 0.5% confidence ratio)
            const isVolatile = result.confidence > 0 &&
                (result.confidence / result.price) > 0.005;

            setState({
                price: result.price,
                confidence: result.confidence,
                confidenceScore: result.confidenceScore,
                confidenceRatio: result.price > 0 ? result.confidence / result.price : 0,
                tier: result.tier,
                source: result.source,
                isSafeToTrade: result.isSafeToTrade,
                isVolatile,
                reason: result.reason,
                lastUpdated: Date.now(),
            });

            setCircuitBreaker(confidenceRouter.getCircuitBreakerStatus());
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to check confidence');
        } finally {
            setIsLoading(false);
        }
    }, [opts.symbol, opts.mint, opts.sigmaMultiplier]);

    // Polling effect
    useEffect(() => {
        if (!opts.autoStart) return;

        checkConfidence();
        const interval = setInterval(checkConfidence, opts.pollInterval);

        return () => clearInterval(interval);
    }, [checkConfidence, opts.pollInterval, opts.autoStart]);

    // Derived safety status for UI
    const safetyStatus = useMemo(() => {
        if (circuitBreaker.isTripped) {
            return {
                level: 'critical' as const,
                label: 'Circuit Breaker',
                color: 'var(--accent-red)',
            };
        }

        if (!state.isSafeToTrade) {
            return {
                level: 'warning' as const,
                label: 'High Risk',
                color: 'var(--accent-orange)',
            };
        }

        if (state.isVolatile) {
            return {
                level: 'caution' as const,
                label: 'Elevated Volatility',
                color: 'var(--accent-yellow)',
            };
        }

        return {
            level: 'safe' as const,
            label: 'Safe to Trade',
            color: 'var(--accent-green)',
        };
    }, [state, circuitBreaker]);

    return {
        ...state,
        circuitBreaker,
        safetyStatus,
        isLoading,
        error,
        refresh: checkConfidence,
        resetCircuitBreaker: () => confidenceRouter.resetCircuitBreaker(),
    };
}

/**
 * Quick hook for just checking if trading is safe
 */
export function useIsSafeToTrade(symbol: string, mint?: string) {
    const { isSafeToTrade, isLoading, safetyStatus } = useConfidence({
        symbol,
        mint,
    });

    return {
        isSafe: isSafeToTrade,
        isLoading,
        status: safetyStatus,
    };
}
