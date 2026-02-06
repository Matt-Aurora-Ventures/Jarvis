'use client';

import { createChart, ColorType, IChartApi, CandlestickSeries, CandlestickData, ISeriesApi } from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';
import { bagsClient } from '@/lib/bags-api';
import { getJupiterPriceClient, TOKENS } from '@/lib/jupiter-price';

export const MarketChart = () => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let chart: IChartApi | null = null;
        let resizeHandler: (() => void) | null = null;

        const initChart = async () => {
            if (!chartContainerRef.current) return;

            try {
                // 1. Create Chart
                chart = createChart(chartContainerRef.current, {
                    layout: {
                        background: { type: ColorType.Solid, color: 'transparent' },
                        textColor: '#94a3b8',
                        fontFamily: 'JetBrains Mono, monospace',
                    },
                    grid: {
                        vertLines: { color: 'rgba(34, 211, 238, 0.05)' },
                        horzLines: { color: 'rgba(34, 211, 238, 0.05)' },
                    },
                    width: chartContainerRef.current.clientWidth,
                    height: 400,
                    timeScale: {
                        timeVisible: true,
                        secondsVisible: false,
                    },
                });

                // 2. Add Series (v5 API - using addSeries instead of addCandlestickSeries)
                const newSeries = chart.addSeries(CandlestickSeries, {
                    upColor: '#22c55e',
                    downColor: '#EF4444',
                    borderVisible: false,
                    wickUpColor: '#22c55e',
                    wickDownColor: '#EF4444',
                });
                seriesRef.current = newSeries;
                chartRef.current = chart;

                // 3. Fetch Data (SOL) - Try bags.fm first, fallback to Jupiter
                const mint = TOKENS.SOL;
                let candles = await bagsClient.getChartData(mint, '1h', 100);

                if (candles && candles.length > 0) {
                    const formattedData = candles.map(c => ({
                        time: c.timestamp as unknown as CandlestickData['time'],
                        open: c.open,
                        high: c.high,
                        low: c.low,
                        close: c.close,
                    })).sort((a, b) => (a.time as number) - (b.time as number));

                    newSeries.setData(formattedData);
                    chart.timeScale().fitContent();
                } else {
                    // Fallback: Use Jupiter price data
                    console.log('[Chart] bags.fm unavailable, using Jupiter price');
                    const jupiterClient = getJupiterPriceClient();
                    const jupiterCandles = await jupiterClient.getSimulatedCandles(mint, 100);

                    if (jupiterCandles.length > 0) {
                        const formattedData = jupiterCandles.map(c => ({
                            time: c.timestamp as unknown as CandlestickData['time'],
                            open: c.open,
                            high: c.high,
                            low: c.low,
                            close: c.close,
                        })).sort((a, b) => (a.time as number) - (b.time as number));

                        newSeries.setData(formattedData);
                        chart.timeScale().fitContent();
                        console.log(`[Chart] Rendered ${formattedData.length} candlesticks from CoinGecko`);
                    } else {
                        setError('Price data temporarily unavailable');
                    }
                }

                // 4. Resize Handler
                resizeHandler = () => {
                    if (chartContainerRef.current && chart) {
                        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
                    }
                };
                window.addEventListener('resize', resizeHandler);

            } catch (e) {
                console.error("Failed to initialize chart", e);
                setError('Chart initialization failed');
            } finally {
                setLoading(false);
            }
        };

        initChart();

        // Cleanup
        return () => {
            if (resizeHandler) {
                window.removeEventListener('resize', resizeHandler);
            }
            if (chart) {
                chart.remove();
            }
        };
    }, []);

    return (
        <div className="relative w-full h-[400px]">
            {loading && (
                <div className="absolute inset-0 flex items-center justify-center bg-theme-dark/50 z-10 backdrop-blur-sm">
                    <div className="text-accent-neon font-mono animate-pulse">LOADING MARKET DATA...</div>
                </div>
            )}
            {error && !loading && (
                <div className="absolute top-2 right-2 text-xs text-amber-400 font-mono bg-amber-900/20 px-2 py-1 rounded">
                    {error}
                </div>
            )}
            <div ref={chartContainerRef} className="w-full h-full" />
        </div>
    );
};
