'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  normalizeInvestmentBasket,
  normalizeInvestmentDecisions,
  normalizeInvestmentPerformance,
  type InvestmentBasketView,
  type InvestmentDecisionView,
  type InvestmentPerformancePoint,
} from '@/lib/investments/normalizers';

interface UseInvestmentDataState {
  basket: InvestmentBasketView | null;
  performance: InvestmentPerformancePoint[];
  decisions: InvestmentDecisionView[];
  killSwitchActive: boolean;
  driftWarning: string | null;
  loading: boolean;
  error: string | null;
}

function buildInvestmentWriteHeaders(): HeadersInit {
  const token = String(process.env.NEXT_PUBLIC_INVESTMENTS_ADMIN_TOKEN || '').trim();
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export function useInvestmentData() {
  const [state, setState] = useState<UseInvestmentDataState>({
    basket: null,
    performance: [],
    decisions: [],
    killSwitchActive: false,
    driftWarning: null,
    loading: true,
    error: null,
  });

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [basketRes, perfRes, decisionRes, killSwitchRes] = await Promise.all([
        fetch('/api/investments/basket', { cache: 'no-store' }),
        fetch('/api/investments/performance?hours=168', { cache: 'no-store' }),
        fetch('/api/investments/decisions?limit=20', { cache: 'no-store' }),
        fetch('/api/investments/kill-switch', { cache: 'no-store' }),
      ]);

      const next: Partial<UseInvestmentDataState> = {};

      if (basketRes.ok) {
        next.basket = normalizeInvestmentBasket(await basketRes.json());
      }
      if (perfRes.ok) {
        next.performance = normalizeInvestmentPerformance(await perfRes.json());
      }
      if (decisionRes.ok) {
        next.decisions = normalizeInvestmentDecisions(await decisionRes.json());
      }
      if (killSwitchRes.ok) {
        const payload = await killSwitchRes.json();
        next.killSwitchActive = Boolean(payload.active);
      }

      try {
        const versionRes = await fetch('/api/investments/version', { cache: 'no-store' });
        if (versionRes.ok) {
          const payload = await versionRes.json();
          next.driftWarning = payload.driftDetected ? String(payload.warning || 'Investments service SHA drift detected.') : null;
        }
      } catch {
        // Ignore version metadata failures; data panel can still operate.
      }

      next.loading = false;
      next.error = null;
      setState((prev) => ({ ...prev, ...next }));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setState((prev) => ({ ...prev, loading: false, error: `Investment service unavailable (${message})` }));
    }
  }, []);

  const triggerCycle = useCallback(async () => {
    const r = await fetch('/api/investments/trigger-cycle', {
      method: 'POST',
      headers: buildInvestmentWriteHeaders(),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(String(body.error ?? `HTTP ${r.status}`));
    }
    await refresh();
  }, [refresh]);

  const activateKillSwitch = useCallback(async () => {
    const r = await fetch('/api/investments/kill-switch/activate', {
      method: 'POST',
      headers: buildInvestmentWriteHeaders(),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(String(body.error ?? `HTTP ${r.status}`));
    }
    await refresh();
  }, [refresh]);

  const deactivateKillSwitch = useCallback(async () => {
    const r = await fetch('/api/investments/kill-switch/deactivate', {
      method: 'POST',
      headers: buildInvestmentWriteHeaders(),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(String(body.error ?? `HTTP ${r.status}`));
    }
    await refresh();
  }, [refresh]);

  useEffect(() => {
    void refresh();
    timerRef.current = setInterval(() => {
      void refresh();
    }, 30000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [refresh]);

  return {
    ...state,
    refresh,
    triggerCycle,
    activateKillSwitch,
    deactivateKillSwitch,
  };
}
