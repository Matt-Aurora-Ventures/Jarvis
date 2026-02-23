'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  normalizePerpsCandles,
  normalizePerpsOrderRequest,
  normalizePerpsPriceSnapshot,
  type PerpsCandlePoint,
  type PerpsMarket,
  type PerpsPriceSnapshot,
} from '@/lib/perps/normalizers';

export interface PerpsStatus {
  runner_healthy: boolean;
  runner_pid?: number;
  heartbeat_age_s?: number;
  mode: 'disabled' | 'alert' | 'live';
  arm?: {
    stage?: 'disarmed' | 'prepared' | 'armed';
    expires_at?: number;
    armed_at?: number;
    armed_by?: string;
    last_reason?: string;
  };
}

export interface PerpsPosition {
  pda?: string;
  market?: string;
  side?: 'long' | 'short';
  size_usd?: number;
  entry_price?: number;
  current_price?: number;
  unrealized_pnl_pct?: number;
}

export interface PerpsAuditEvent {
  timestamp?: number;
  event?: string;
  detail?: string;
}

interface UsePerpsDataState {
  prices: PerpsPriceSnapshot | null;
  status: PerpsStatus | null;
  positions: PerpsPosition[];
  audit: PerpsAuditEvent[];
  historyMarket: PerpsMarket;
  historyResolution: string;
  historyCandles: PerpsCandlePoint[];
  loadingHistory: boolean;
  historyError: string | null;
  apiError: string | null;
}

export function usePerpsData() {
  const [state, setState] = useState<UsePerpsDataState>({
    prices: null,
    status: null,
    positions: [],
    audit: [],
    historyMarket: 'SOL-USD',
    historyResolution: '5',
    historyCandles: [],
    loadingHistory: true,
    historyError: null,
    apiError: null,
  });

  const statusTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const historyTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const isLive = useMemo(() => state.status?.mode === 'live', [state.status?.mode]);
  const isArmed = useMemo(() => state.status?.arm?.stage === 'armed', [state.status?.arm?.stage]);

  const refreshStatus = useCallback(async () => {
    try {
      const [pricesRes, statusRes, positionsRes, auditRes] = await Promise.all([
        fetch('/api/perps/prices', { cache: 'no-store' }),
        fetch('/api/perps/status', { cache: 'no-store' }),
        fetch('/api/perps/positions', { cache: 'no-store' }),
        fetch('/api/perps/audit', { cache: 'no-store' }),
      ]);

      const next: Partial<UsePerpsDataState> = {};

      if (pricesRes.ok) {
        next.prices = normalizePerpsPriceSnapshot(await pricesRes.json());
      }
      if (statusRes.ok) {
        next.status = await statusRes.json();
      }
      if (positionsRes.ok) {
        const payload = await positionsRes.json();
        next.positions = Array.isArray(payload) ? payload : (payload.positions ?? []);
      }
      if (auditRes.ok) {
        const payload = await auditRes.json();
        next.audit = Array.isArray(payload) ? payload : (payload.events ?? []);
      }

      next.apiError = null;
      setState((prev) => ({ ...prev, ...next }));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setState((prev) => ({ ...prev, apiError: `Perps API unavailable (${message})` }));
    }
  }, []);

  const refreshHistory = useCallback(async () => {
    const market = state.historyMarket;
    const resolution = state.historyResolution;
    try {
      const r = await fetch(`/api/perps/history/${market}?resolution=${encodeURIComponent(resolution)}`, {
        cache: 'no-store',
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const payload = await r.json();
      const candles = normalizePerpsCandles(payload);
      setState((prev) => ({
        ...prev,
        historyCandles: candles,
        loadingHistory: false,
        historyError: candles.length === 0
          ? `No candle data (${String(payload.reason ?? payload.error ?? 'no_data')})`
          : null,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setState((prev) => ({
        ...prev,
        historyCandles: [],
        loadingHistory: false,
        historyError: `History unavailable (${message})`,
      }));
    }
  }, [state.historyMarket, state.historyResolution]);

  useEffect(() => {
    void refreshStatus();
    statusTimerRef.current = setInterval(() => {
      void refreshStatus();
    }, 5000);
    return () => {
      if (statusTimerRef.current) clearInterval(statusTimerRef.current);
    };
  }, [refreshStatus]);

  useEffect(() => {
    setState((prev) => ({ ...prev, loadingHistory: true }));
    void refreshHistory();
    historyTimerRef.current = setInterval(() => {
      void refreshHistory();
    }, 15000);
    return () => {
      if (historyTimerRef.current) clearInterval(historyTimerRef.current);
    };
  }, [refreshHistory]);

  const setHistoryMarket = useCallback((market: PerpsMarket) => {
    setState((prev) => ({ ...prev, historyMarket: market }));
  }, []);

  const setHistoryResolution = useCallback((resolution: string) => {
    setState((prev) => ({ ...prev, historyResolution: resolution }));
  }, []);

  const openPosition = useCallback(async (params: {
    market: string;
    side: 'long' | 'short';
    collateralUsd: number;
    leverage: number;
    tpPct?: number;
    slPct?: number;
  }) => {
    const payload = normalizePerpsOrderRequest(params);
    const r = await fetch('/api/perps/open', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(String(body.error ?? `HTTP ${r.status}`));
    }
    await refreshStatus();
  }, [refreshStatus]);

  const closePosition = useCallback(async (positionPda: string) => {
    const r = await fetch('/api/perps/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position_pda: positionPda }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(String(body.error ?? `HTTP ${r.status}`));
    }
    await refreshStatus();
  }, [refreshStatus]);

  return {
    ...state,
    isLive,
    isArmed,
    setHistoryMarket,
    setHistoryResolution,
    openPosition,
    closePosition,
    refreshStatus,
  };
}
