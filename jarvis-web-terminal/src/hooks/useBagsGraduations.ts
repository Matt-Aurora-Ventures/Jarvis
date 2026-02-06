'use client';

import { useState, useEffect, useCallback } from 'react';
import { bagsClient, BagsGraduation } from '@/lib/bags-api';

interface UseBagsGraduationsOptions {
    limit?: number;
    refreshInterval?: number;
}

interface UseBagsGraduationsReturn {
    graduations: BagsGraduation[];
    loading: boolean;
    error: string | null;
    refresh: () => Promise<void>;
    lastUpdated: Date | null;
}

export function useBagsGraduations(options: UseBagsGraduationsOptions = {}): UseBagsGraduationsReturn {
    const { limit = 20, refreshInterval = 30000 } = options;

    const [graduations, setGraduations] = useState<BagsGraduation[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    const fetchGraduations = useCallback(async () => {
        try {
            setError(null);
            const data = await bagsClient.getGraduations(limit);

            if (data.length > 0) {
                setGraduations(data);
                setLastUpdated(new Date());
            } else if (graduations.length === 0) {
                // Only show demo data if we have no real data
                setGraduations(generateDemoGraduations());
                setError('Using demo data - Waiting for live graduations');
            }
        } catch (e) {
            console.error('Failed to fetch graduations:', e);
            setError('Failed to fetch graduations');

            // Fallback to demo data
            if (graduations.length === 0) {
                setGraduations(generateDemoGraduations());
            }
        } finally {
            setLoading(false);
        }
    }, [limit, graduations.length]);

    // Initial fetch
    useEffect(() => {
        fetchGraduations();
    }, []);

    // Polling
    useEffect(() => {
        if (refreshInterval > 0) {
            const interval = setInterval(fetchGraduations, refreshInterval);
            return () => clearInterval(interval);
        }
    }, [fetchGraduations, refreshInterval]);

    return {
        graduations,
        loading,
        error,
        refresh: fetchGraduations,
        lastUpdated,
    };
}

// Demo data generator for when API is unavailable
function generateDemoGraduations(): BagsGraduation[] {
    const symbols = ['PEPE', 'WOJAK', 'DOGE2', 'MOON', 'PUMP', 'BASED', 'SIGMA', 'CHAD'];
    const now = Date.now() / 1000;

    return symbols.map((symbol, i) => ({
        mint: `Demo${symbol}Mint${i}`,
        symbol,
        name: `${symbol} Token`,
        score: Math.floor(Math.random() * 60) + 30, // 30-90 range
        graduation_time: now - (i * 3600), // 1 hour apart
        bonding_curve_score: Math.floor(Math.random() * 100),
        holder_distribution_score: Math.floor(Math.random() * 100),
        liquidity_score: Math.floor(Math.random() * 100),
        social_score: Math.floor(Math.random() * 100),
        market_cap: Math.floor(Math.random() * 1000000) + 50000,
        price_usd: Math.random() * 0.01,
        logo_uri: undefined,
    }));
}
