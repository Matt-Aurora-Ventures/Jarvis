/**
 * Trading Chart Component - Beautiful TradingView-style Charts
 * Uses lightweight-charts for performance and jarvislife.io design
 */
import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData } from 'lightweight-charts';
import { GlassCard, GlassCardHeader, GlassCardTitle } from '../UI/GlassCard';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import clsx from 'clsx';

interface TradingChartProps {
  tokenAddress: string;
  tokenSymbol: string;
  interval?: '1m' | '5m' | '15m' | '1h' | '4h' | '1d';
}

export const TradingChart: React.FC<TradingChartProps> = ({
  tokenAddress,
  tokenSymbol,
  interval = '5m',
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  const [priceChange, setPriceChange] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart with jarvislife.io theme
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: 'transparent' },
        textColor: '#A0A0A0',
      },
      grid: {
        vertLines: { color: 'rgba(255, 255, 255, 0.05)' },
        horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
      },
      timeScale: {
        borderColor: 'rgba(255, 255, 255, 0.1)',
        timeVisible: true,
        secondsVisible: false,
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
    });

    // Create candlestick series
    const series = chart.addCandlestickSeries({
      upColor: '#39FF14',
      downColor: '#FF3939',
      borderUpColor: '#39FF14',
      borderDownColor: '#FF3939',
      wickUpColor: '#39FF14',
      wickDownColor: '#FF3939',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    // Fetch and update data
    fetchChartData(tokenAddress, interval);

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chart) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [tokenAddress, interval]);

  const fetchChartData = async (address: string, timeframe: string) => {
    try {
      setLoading(true);

      // Call backend API for chart data (Rule #1: Server provides data)
      const response = await fetch(
        `/api/trading/chart?address=${address}&interval=${timeframe}`
      );

      if (!response.ok) {
        throw new Error('Failed to fetch chart data');
      }

      const data = await response.json();

      // Update chart
      if (seriesRef.current && data.candles) {
        const candles: CandlestickData[] = data.candles.map((c: any) => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));

        seriesRef.current.setData(candles);

        // Calculate price change
        if (candles.length >= 2) {
          const firstCandle = candles[0];
          const lastCandle = candles[candles.length - 1];
          const change = ((lastCandle.close - firstCandle.open) / firstCandle.open) * 100;
          setPriceChange(change);
        }
      }

      setLoading(false);
    } catch (error) {
      console.error('Chart data fetch error:', error);
      setLoading(false);
    }
  };

  return (
    <GlassCard className="w-full">
      <GlassCardHeader>
        <div className="flex items-center justify-between">
          <GlassCardTitle icon={<Activity size={20} />}>
            {tokenSymbol} Chart
          </GlassCardTitle>

          {!loading && (
            <div
              className={clsx(
                'flex items-center gap-1 px-3 py-1 rounded-full text-sm font-semibold',
                priceChange >= 0
                  ? 'bg-success/20 text-success'
                  : 'bg-error/20 text-error'
              )}
            >
              {priceChange >= 0 ? (
                <TrendingUp size={14} />
              ) : (
                <TrendingDown size={14} />
              )}
              <span>{priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%</span>
            </div>
          )}
        </div>
      </GlassCardHeader>

      {/* Chart Container */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-bg-dark/50 z-10 rounded-lg">
            <div className="flex flex-col items-center gap-2">
              <div className="animate-spin">⏳</div>
              <span className="text-muted text-sm">Loading chart...</span>
            </div>
          </div>
        )}

        <div ref={chartContainerRef} className="w-full" />
      </div>

      {/* Interval Selector */}
      <div className="mt-4 flex items-center gap-2">
        {['1m', '5m', '15m', '1h', '4h', '1d'].map((int) => (
          <button
            key={int}
            className={clsx(
              'px-3 py-1 rounded-lg text-sm font-medium transition-all',
              interval === int
                ? 'bg-accent text-bg-dark'
                : 'bg-surface text-muted hover:bg-surface-hover'
            )}
            onClick={() => fetchChartData(tokenAddress, int)}
          >
            {int}
          </button>
        ))}
      </div>
    </GlassCard>
  );
};
