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
  /** Count of new launches (< 48h) */
  newLaunchCount: number;
  /** Count of established tokens (> 7d with volume) */
  establishedCount: number;
}

export function useBagsGraduations(options: UseBagsGraduationsOptions = {}): UseBagsGraduationsReturn {
  const { limit = 200, refreshInterval = 60000 } = options;

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
        setError('No degen tokens found — Jupiter API may be temporarily unavailable');
      }
    } catch (e) {
      console.error('Failed to fetch bags tokens:', e);
      setError('Failed to fetch bags tokens');
    } finally {
      setLoading(false);
    }
  }, [limit, graduations.length]);

  // Initial fetch
  useEffect(() => {
    fetchGraduations();
  }, []);

  // Polling (default 60s to be resource-efficient)
  useEffect(() => {
    if (refreshInterval > 0) {
      const interval = setInterval(fetchGraduations, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [fetchGraduations, refreshInterval]);

  const newLaunchCount = graduations.filter(g => g.isNewLaunch).length;
  const establishedCount = graduations.filter(g => g.isEstablished).length;

  return {
    graduations,
    loading,
    error,
    refresh: fetchGraduations,
    lastUpdated,
    newLaunchCount,
    establishedCount,
  };
}
