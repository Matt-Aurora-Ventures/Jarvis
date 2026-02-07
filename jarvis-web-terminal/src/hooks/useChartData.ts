'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchOHLCV, fetchCurrentPrice, type Candle, type Market, type Timeframe } from '@/lib/chart-data';

interface UseChartDataReturn {
  candles: Candle[];
  price: number;
  loading: boolean;
  market: Market;
  timeframe: Timeframe;
  setMarket: (m: Market) => void;
  setTimeframe: (t: Timeframe) => void;
}

export function useChartData(initialMarket: Market = 'SOL'): UseChartDataReturn {
  const [market, setMarket] = useState<Market>(initialMarket);
  const [timeframe, setTimeframe] = useState<Timeframe>('1h');
  const [candles, setCandles] = useState<Candle[]>([]);
  const [price, setPrice] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, p] = await Promise.all([
        fetchOHLCV(market, timeframe),
        fetchCurrentPrice(market),
      ]);
      setCandles(c);
      setPrice(p);
    } catch (err) {
      console.error('[ChartData]', err);
    } finally {
      setLoading(false);
    }
  }, [market, timeframe]);

  useEffect(() => { load(); }, [load]);

  // Auto-refresh every 60s
  useEffect(() => {
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
  }, [load]);

  return { candles, price, loading, market, timeframe, setMarket, setTimeframe };
}
