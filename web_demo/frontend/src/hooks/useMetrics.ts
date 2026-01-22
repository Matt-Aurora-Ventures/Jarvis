/**
 * Metrics Hook
 * Provides real-time performance metrics with auto-refresh.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { metricsService } from '../services/metricsService';
import { RealtimeMetrics, HealthMetrics } from '../types/metrics';

export interface UseMetricsReturn {
  metrics: RealtimeMetrics | null;
  health: HealthMetrics | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  toggleAutoRefresh: () => void;
  isAutoRefresh: boolean;
}

export const useMetrics = (autoRefreshInterval: number = 5000): UseMetricsReturn => {
  const [metrics, setMetrics] = useState<RealtimeMetrics | null>(null);
  const [health, setHealth] = useState<HealthMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAutoRefresh, setIsAutoRefresh] = useState(true);
  const intervalRef = useRef<number | null>(null);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [metricsData, healthData] = await Promise.all([
        metricsService.getRealtime(),
        metricsService.getHealth()
      ]);

      setMetrics(metricsData);
      setHealth(healthData);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch metrics');
      console.error('Metrics fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    await fetchMetrics();
  }, [fetchMetrics]);

  const toggleAutoRefresh = useCallback(() => {
    setIsAutoRefresh(prev => !prev);
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // Auto-refresh
  useEffect(() => {
    if (isAutoRefresh) {
      intervalRef.current = window.setInterval(fetchMetrics, autoRefreshInterval);
    } else {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isAutoRefresh, autoRefreshInterval, fetchMetrics]);

  return {
    metrics,
    health,
    loading,
    error,
    refresh,
    toggleAutoRefresh,
    isAutoRefresh
  };
};
