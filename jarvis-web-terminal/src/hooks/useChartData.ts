'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchOHLCV,
  fetchCurrentPrice,
  fetchOHLCVByPool,
  fetchCurrentPriceByPool,
  type Candle,
  type Market,
  type Timeframe,
} from '@/lib/chart-data';

interface UseChartDataReturn {
  candles: Candle[];
  price: number;
  loading: boolean;
  market: Market;
  timeframe: Timeframe;
  setMarket: (m: Market) => void;
  setTimeframe: (t: Timeframe) => void;
  /** Label displayed in the chart header (e.g. "SOL" or "BONK") */
  displaySymbol: string;
  /** True when the chart is showing a custom pool (not SOL/ETH/BTC) */
  isCustomPool: boolean;
}

/**
 * Fetches OHLCV chart data.
 *
 * When `poolAddress` is provided (from TokenSearch), it takes priority over
 * the built-in market selector (SOL/ETH/BTC). The market selector remains
 * functional as a fallback and also activates when the user clicks SOL/ETH/BTC.
 */
export function useChartData(
  initialMarket: Market = 'SOL',
  options?: {
    /** Override pool address from TokenSearch */
    poolAddress?: string;
    /** Symbol to display when using a custom pool */
    tokenSymbol?: string;
  },
): UseChartDataReturn {
  const [market, setMarketInternal] = useState<Market>(initialMarket);
  const [timeframe, setTimeframe] = useState<Timeframe>('1h');
  const [candles, setCandles] = useState<Candle[]>([]);
  const [price, setPrice] = useState(0);
  const [loading, setLoading] = useState(true);
  // Track whether the user has manually clicked a market button to override
  const [manualMarketOverride, setManualMarketOverride] = useState(false);

  const externalPool = options?.poolAddress;
  const externalSymbol = options?.tokenSymbol;

  // When the user clicks a market button (SOL/ETH/BTC), we set the manual override
  const setMarket = useCallback((m: Market) => {
    setMarketInternal(m);
    setManualMarketOverride(true);
  }, []);

  // When an external pool is provided, clear the manual override so we use it
  useEffect(() => {
    if (externalPool) {
      setManualMarketOverride(false);
    }
  }, [externalPool]);

  // Determine if we should use the external pool or the built-in market
  const useExternalPool = !!externalPool && !manualMarketOverride;

  const displaySymbol = useExternalPool
    ? (externalSymbol ?? 'TOKEN')
    : market;

  const isCustomPool = useExternalPool;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let c: Candle[];
      let p: number;

      if (useExternalPool && externalPool) {
        [c, p] = await Promise.all([
          fetchOHLCVByPool(externalPool, timeframe),
          fetchCurrentPriceByPool(externalPool),
        ]);
      } else {
        [c, p] = await Promise.all([
          fetchOHLCV(market, timeframe),
          fetchCurrentPrice(market),
        ]);
      }

      setCandles(c);
      setPrice(p);
    } catch (err) {
      console.error('[ChartData]', err);
    } finally {
      setLoading(false);
    }
  }, [market, timeframe, useExternalPool, externalPool]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 60s
  useEffect(() => {
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  return {
    candles,
    price,
    loading,
    market,
    timeframe,
    setMarket,
    setTimeframe,
    displaySymbol,
    isCustomPool,
  };
}
