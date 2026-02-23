'use client';

import { useRef, useEffect, useState, useMemo } from 'react';
import { useChartData } from '@/hooks/useChartData';
import { usePriceFlash } from '@/hooks/usePriceFlash';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { computeEMAOverlay, computeBollingerOverlay, computeVolumeColors } from '@/lib/chart-indicators';
import type { Market, Timeframe } from '@/lib/chart-data';
import type { IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import { SkeletonChart } from '@/components/ui/Skeleton';

const MARKETS: Market[] = ['SOL', 'ETH', 'BTC'];
const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1d'];

const TF_LABELS: Record<Timeframe, string> = {
  '1m': '1m',
  '5m': '5m',
  '15m': '15m',
  '1h': '1H',
  '4h': '4H',
  '1d': '1D',
};

type IndicatorToggle = 'ema' | 'bb' | 'vol';

const INDICATOR_LABELS: Record<IndicatorToggle, string> = {
  ema: 'EMA 9/21',
  bb: 'Bollinger',
  vol: 'Volume',
};

interface PriceChartProps {
  /** Override pool address from TokenSearch (custom token) */
  poolAddress?: string;
  /** Token symbol to display when using a custom pool */
  tokenSymbol?: string;
}

export function PriceChart({ poolAddress, tokenSymbol }: PriceChartProps = {}) {
  const {
    candles,
    price,
    loading,
    market,
    timeframe,
    setMarket,
    setTimeframe,
    displaySymbol,
    isCustomPool,
  } = useChartData('SOL', {
    poolAddress,
    tokenSymbol,
  });

  // Flash class for live price updates
  const priceFlash = usePriceFlash(price);

  // AI consensus from backtest engine
  const aiConsensus = useSettingsStore((s) => s.aiConsensus);
  const aiBestWinRate = useSettingsStore((s) => s.aiBestWinRate);
  const aiSignalStrength = useSettingsStore((s) => s.aiSignalStrength);

  // Indicator toggles -- EMA and Volume ON by default, Bollinger OFF
  const [indicators, setIndicators] = useState<Record<IndicatorToggle, boolean>>({
    ema: true,
    bb: false,
    vol: true,
  });

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  // Indicator series refs
  const ema9SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const ema21SeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbUpperSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbMiddleSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const bbLowerSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  // Compute price change from candle range
  const first = candles[0]?.open ?? 0;
  const last = candles[candles.length - 1]?.close ?? 0;
  const change = first > 0 ? ((last - first) / first) * 100 : 0;

  // Pre-compute indicator data whenever candles change
  const emaData = useMemo(() => computeEMAOverlay(candles), [candles]);
  const bbData = useMemo(() => computeBollingerOverlay(candles), [candles]);
  const volumeColored = useMemo(() => computeVolumeColors(candles), [candles]);

  const toggleIndicator = (key: IndicatorToggle) => {
    setIndicators((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Create chart once on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!chartContainerRef.current) return;

    let disposed = false;

    // Dynamic import to avoid SSR issues with canvas
    import('lightweight-charts').then(({ createChart, CandlestickSeries, HistogramSeries, LineSeries, LineStyle }) => {
      if (disposed || !chartContainerRef.current) return;

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth,
        height: 380,
        layout: {
          background: { color: 'transparent' },
          textColor: '#a1a1aa',
          fontSize: 11,
          fontFamily: 'JetBrains Mono, SF Mono, Fira Code, monospace',
        },
        grid: {
          vertLines: { color: 'rgba(255,255,255,0.04)' },
          horzLines: { color: 'rgba(255,255,255,0.04)' },
        },
        crosshair: {
          mode: 0, // CrosshairMode.Normal
          vertLine: { color: 'rgba(255,255,255,0.1)', width: 1, style: 2 },
          horzLine: { color: 'rgba(255,255,255,0.1)', width: 1, style: 2 },
        },
        rightPriceScale: {
          borderColor: 'rgba(255,255,255,0.06)',
        },
        timeScale: {
          borderColor: 'rgba(255,255,255,0.06)',
          timeVisible: true,
          secondsVisible: false,
        },
      });

      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderUpColor: '#22c55e',
        borderDownColor: '#ef4444',
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
      });

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
      });

      chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.85, bottom: 0 },
      });

      // --- EMA Lines ---
      const ema9Series = chart.addSeries(LineSeries, {
        color: '#f59e0b',               // amber for fast EMA
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      const ema21Series = chart.addSeries(LineSeries, {
        color: '#22c55e',               // accent-neon for slow EMA
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      // --- Bollinger Bands ---
      const bbUpperSeries = chart.addSeries(LineSeries, {
        color: 'rgba(34, 197, 94, 0.3)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      const bbMiddleSeries = chart.addSeries(LineSeries, {
        color: 'rgba(34, 197, 94, 0.5)',
        lineWidth: 1,
        lineStyle: LineStyle.Dotted,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      const bbLowerSeries = chart.addSeries(LineSeries, {
        color: 'rgba(34, 197, 94, 0.3)',
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        priceLineVisible: false,
        lastValueVisible: false,
      });

      chartRef.current = chart;
      candleSeriesRef.current = candleSeries;
      volumeSeriesRef.current = volumeSeries;
      ema9SeriesRef.current = ema9Series;
      ema21SeriesRef.current = ema21Series;
      bbUpperSeriesRef.current = bbUpperSeries;
      bbMiddleSeriesRef.current = bbMiddleSeries;
      bbLowerSeriesRef.current = bbLowerSeries;

      // Responsive resize
      const observer = new ResizeObserver((entries) => {
        if (disposed) return;
        const { width } = entries[0].contentRect;
        chart.applyOptions({ width });
      });
      observer.observe(chartContainerRef.current);

      // Store observer for cleanup
      (chartContainerRef.current as any).__resizeObserver = observer;
    });

    return () => {
      disposed = true;
      if (chartContainerRef.current) {
        const obs = (chartContainerRef.current as any).__resizeObserver as ResizeObserver | undefined;
        if (obs) obs.disconnect();
      }
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        candleSeriesRef.current = null;
        volumeSeriesRef.current = null;
        ema9SeriesRef.current = null;
        ema21SeriesRef.current = null;
        bbUpperSeriesRef.current = null;
        bbMiddleSeriesRef.current = null;
        bbLowerSeriesRef.current = null;
      }
    };
  }, []);

  // Update candle data when candles change
  useEffect(() => {
    if (!candleSeriesRef.current || candles.length === 0) return;

    const candleData = candles.map((c) => ({
      time: c.time as UTCTimestamp,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    candleSeriesRef.current.setData(candleData);

    // Fit content to show all candles after data update
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles]);

  // Update volume data (color-coded green/red)
  useEffect(() => {
    if (!volumeSeriesRef.current) return;

    if (indicators.vol && volumeColored.length > 0) {
      volumeSeriesRef.current.setData(
        volumeColored.map((v) => ({ time: v.time as UTCTimestamp, value: v.value, color: v.color }))
      );
    } else {
      volumeSeriesRef.current.setData([]);
    }
  }, [indicators.vol, volumeColored]);

  // Update EMA overlay visibility and data
  useEffect(() => {
    if (!ema9SeriesRef.current || !ema21SeriesRef.current) return;

    if (indicators.ema && emaData.ema9.length > 0) {
      ema9SeriesRef.current.setData(
        emaData.ema9.map((p) => ({ time: p.time as UTCTimestamp, value: p.value }))
      );
      ema21SeriesRef.current.setData(
        emaData.ema21.map((p) => ({ time: p.time as UTCTimestamp, value: p.value }))
      );
    } else {
      ema9SeriesRef.current.setData([]);
      ema21SeriesRef.current.setData([]);
    }
  }, [indicators.ema, emaData]);

  // Update Bollinger Bands overlay visibility and data
  useEffect(() => {
    if (!bbUpperSeriesRef.current || !bbMiddleSeriesRef.current || !bbLowerSeriesRef.current) return;

    if (indicators.bb && bbData.upper.length > 0) {
      bbUpperSeriesRef.current.setData(
        bbData.upper.map((p) => ({ time: p.time as UTCTimestamp, value: p.value }))
      );
      bbMiddleSeriesRef.current.setData(
        bbData.middle.map((p) => ({ time: p.time as UTCTimestamp, value: p.value }))
      );
      bbLowerSeriesRef.current.setData(
        bbData.lower.map((p) => ({ time: p.time as UTCTimestamp, value: p.value }))
      );
    } else {
      bbUpperSeriesRef.current.setData([]);
      bbMiddleSeriesRef.current.setData([]);
      bbLowerSeriesRef.current.setData([]);
    }
  }, [indicators.bb, bbData]);

  return (
    <div className="card-glass p-0 overflow-hidden min-h-[340px] sm:min-h-[420px] relative" aria-label={`Price chart for ${displaySymbol}`} role="region">
      {/* Header overlay -- stacks price below symbol on very small screens */}
      <div className="absolute top-2 sm:top-3 left-2 sm:left-3 z-10 flex flex-col xs:flex-row gap-1 xs:gap-3 xs:items-center">
        <div className="flex items-center gap-2 xs:gap-3">
          <div className="flex flex-col">
            <span className="font-display font-bold text-base sm:text-xl text-text-primary">{displaySymbol}/USDC</span>
            <span className="font-mono text-[9px] sm:text-[10px] text-text-muted">GECKOTERMINAL</span>
          </div>
          <div className="h-6 sm:h-8 w-[1px] bg-border-primary" />
          <div className="flex flex-col">
            <span className={`font-mono font-bold text-accent-neon text-xs sm:text-sm rounded px-0.5 ${priceFlash}`} aria-label={`Current price: ${price > 0 ? `$${price.toFixed(2)}` : 'loading'}`}>
              {price > 0 ? `$${price.toFixed(2)}` : '...'}
            </span>
            <span className={`font-mono text-[9px] sm:text-[10px] ${change >= 0 ? 'text-accent-success' : 'text-accent-error'}`} aria-label={`${change >= 0 ? 'Up' : 'Down'} ${Math.abs(change).toFixed(1)} percent`}>
              {change >= 0 ? '+' : ''}{change.toFixed(1)}%
            </span>
          </div>
          {/* AI Consensus Badge */}
          {aiConsensus !== null && (
            <>
              <div className="h-6 sm:h-8 w-[1px] bg-border-primary" />
              <div
                className={`px-2 py-0.5 rounded-full font-mono text-[10px] sm:text-xs font-bold ${
                  aiConsensus === 'BUY'
                    ? 'text-accent-neon bg-accent-neon/10 animate-pulse'
                    : aiConsensus === 'SELL'
                      ? 'text-accent-error bg-accent-error/10'
                      : 'text-text-muted bg-bg-tertiary'
                }`}
                aria-label={[
                  `AI consensus: ${aiConsensus}`,
                  aiBestWinRate !== null ? `best win rate ${aiBestWinRate}%` : null,
                  aiSignalStrength !== null ? `signal strength ${aiSignalStrength}` : null,
                ].filter(Boolean).join(', ')}
              >
                {[
                  `AI: ${aiConsensus}`,
                  aiBestWinRate !== null ? `${aiBestWinRate}%` : null,
                  aiSignalStrength !== null ? `(${aiSignalStrength})` : null,
                ].filter(Boolean).join(' ')}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Controls - top right, stacks into 2 rows on small screens */}
      <div className="absolute top-2 sm:top-3 right-2 sm:right-3 z-10 flex flex-col sm:flex-row gap-1 sm:gap-2 items-end">
        {/* Row 1: Market + Timeframe */}
        <div className="flex gap-1 sm:gap-2">
          {/* Market Selector (SOL/ETH/BTC fallback) */}
          <div className="flex bg-bg-secondary/80 rounded-md p-0.5 border border-border-primary" role="group" aria-label="Market selector">
            {MARKETS.map((m) => (
              <button
                key={m}
                onClick={() => setMarket(m)}
                aria-pressed={!isCustomPool && market === m}
                aria-label={`Show ${m} chart`}
                className={`px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[10px] font-mono font-bold rounded transition-colors ${
                  !isCustomPool && market === m
                    ? 'bg-accent-neon/20 text-accent-neon'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Timeframe Selector */}
          <div className="flex bg-bg-secondary/80 rounded-md p-0.5 border border-border-primary" role="group" aria-label="Timeframe selector">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                aria-pressed={timeframe === tf}
                aria-label={`${TF_LABELS[tf]} timeframe`}
                className={`px-1 sm:px-2 py-0.5 text-[9px] sm:text-[10px] font-mono font-bold rounded transition-colors ${
                  timeframe === tf
                    ? 'bg-accent-neon/20 text-accent-neon'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {TF_LABELS[tf]}
              </button>
            ))}
          </div>
        </div>

        {/* Row 2: Indicator Toggles */}
        <div className="flex bg-bg-secondary/80 rounded-md p-0.5 border border-border-primary" role="group" aria-label="Chart indicators">
          {(Object.keys(INDICATOR_LABELS) as IndicatorToggle[]).map((key) => (
            <button
              key={key}
              onClick={() => toggleIndicator(key)}
              aria-pressed={indicators[key]}
              aria-label={`${indicators[key] ? 'Hide' : 'Show'} ${INDICATOR_LABELS[key]} indicator`}
              className={`px-1.5 sm:px-2 py-0.5 text-[9px] sm:text-[10px] font-mono font-bold rounded transition-colors ${
                indicators[key]
                  ? 'bg-accent-neon/20 text-accent-neon'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {INDICATOR_LABELS[key]}
            </button>
          ))}
        </div>
      </div>

      {/* Chart body */}
      <div className="pt-[72px] sm:pt-14 px-0 pb-0 relative">
        {loading && candles.length === 0 && (
          <div className="absolute inset-0 z-[5]">
            <SkeletonChart />
          </div>
        )}
        <div ref={chartContainerRef} className="w-full h-[300px] sm:h-[380px]" aria-hidden="true" />
      </div>
    </div>
  );
}
