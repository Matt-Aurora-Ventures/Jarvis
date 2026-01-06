import React, { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, CrosshairMode } from 'lightweight-charts'
import { RefreshCw, TrendingUp, Clock } from 'lucide-react'

const API_BASE = ''

const TIMEFRAMES = [
    { label: '1m', value: '1m' },
    { label: '5m', value: '5m' },
    { label: '15m', value: '15m' },
    { label: '1H', value: '1H' },
    { label: '4H', value: '4H' },
    { label: '1D', value: '1D' },
]

function TradingChart({ mint, symbol = 'TOKEN', onPriceUpdate }) {
    const chartContainerRef = useRef(null)
    const chartRef = useRef(null)
    const candleSeriesRef = useRef(null)
    const volumeSeriesRef = useRef(null)

    const [timeframe, setTimeframe] = useState('15m')
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)
    const [lastPrice, setLastPrice] = useState(null)
    const [priceChange, setPriceChange] = useState(0)
    const [source, setSource] = useState('')

    // Initialize chart
    useEffect(() => {
        if (!chartContainerRef.current) return

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#FFFFFF' },
                textColor: '#6B7280',
            },
            grid: {
                vertLines: { color: '#F3F4F6' },
                horzLines: { color: '#F3F4F6' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: {
                    color: '#6366F1',
                    width: 1,
                    style: 2,
                    labelBackgroundColor: '#6366F1',
                },
                horzLine: {
                    color: '#6366F1',
                    width: 1,
                    style: 2,
                    labelBackgroundColor: '#6366F1',
                },
            },
            rightPriceScale: {
                borderColor: '#E5E7EB',
            },
            timeScale: {
                borderColor: '#E5E7EB',
                timeVisible: true,
                secondsVisible: false,
            },
            handleScroll: { vertTouchDrag: false },
        })

        // Add candlestick series
        const candleSeries = chart.addCandlestickSeries({
            upColor: '#10B981',
            downColor: '#EF4444',
            borderUpColor: '#10B981',
            borderDownColor: '#EF4444',
            wickUpColor: '#10B981',
            wickDownColor: '#EF4444',
        })

        // Add volume series
        const volumeSeries = chart.addHistogramSeries({
            color: '#6366F1',
            priceFormat: { type: 'volume' },
            priceScaleId: '',
            scaleMargins: { top: 0.85, bottom: 0 },
        })

        chartRef.current = chart
        candleSeriesRef.current = candleSeries
        volumeSeriesRef.current = volumeSeries

        // Handle resize
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                })
            }
        }

        window.addEventListener('resize', handleResize)
        handleResize()

        return () => {
            window.removeEventListener('resize', handleResize)
            chart.remove()
        }
    }, [])

    // Fetch chart data
    const fetchChartData = async () => {
        if (!mint || !candleSeriesRef.current) return

        setIsLoading(true)
        setError(null)

        try {
            const response = await fetch(
                `${API_BASE}/api/chart/${mint}?timeframe=${timeframe}&limit=100`
            )

            if (!response.ok) throw new Error('Failed to fetch chart data')

            const data = await response.json()

            if (data.success && data.candles && data.candles.length > 0) {
                // Format candles for lightweight-charts
                const formattedCandles = data.candles.map(c => ({
                    time: c.timestamp,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                }))

                const formattedVolumes = data.candles.map(c => ({
                    time: c.timestamp,
                    value: c.volume || 0,
                    color: c.close >= c.open ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)',
                }))

                candleSeriesRef.current.setData(formattedCandles)
                volumeSeriesRef.current.setData(formattedVolumes)

                // Update price info
                const lastCandle = formattedCandles[formattedCandles.length - 1]
                const firstCandle = formattedCandles[0]
                setLastPrice(lastCandle.close)
                setPriceChange(((lastCandle.close - firstCandle.open) / firstCandle.open) * 100)
                setSource(data.source)

                // Callback for parent
                if (onPriceUpdate) {
                    onPriceUpdate(lastCandle.close)
                }

                // Fit content
                chartRef.current?.timeScale().fitContent()
            } else {
                setError(data.error || 'No chart data available')
            }
        } catch (err) {
            console.error('Chart fetch error:', err)
            setError('Failed to load chart data')
        } finally {
            setIsLoading(false)
        }
    }

    // Fetch on mount and when timeframe changes
    useEffect(() => {
        fetchChartData()
    }, [mint, timeframe])

    // Auto-refresh every 30 seconds
    useEffect(() => {
        const interval = setInterval(fetchChartData, 30000)
        return () => clearInterval(interval)
    }, [mint, timeframe])

    return (
        <div className="card">
            <div className="card-header">
                <div className="card-title">
                    <TrendingUp className="card-title-icon" size={20} />
                    {symbol} Chart
                    {lastPrice && (
                        <span style={{ marginLeft: '12px', fontFamily: 'monospace' }}>
                            ${lastPrice.toFixed(8)}
                        </span>
                    )}
                    {priceChange !== 0 && (
                        <span
                            className={`badge ${priceChange >= 0 ? 'badge-success' : 'badge-danger'}`}
                            style={{ marginLeft: '8px' }}
                        >
                            {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
                        </span>
                    )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {/* Timeframe selector */}
                    <div style={{ display: 'flex', gap: '4px' }}>
                        {TIMEFRAMES.map(tf => (
                            <button
                                key={tf.value}
                                onClick={() => setTimeframe(tf.value)}
                                className={`btn btn-sm ${timeframe === tf.value ? 'btn-primary' : 'btn-ghost'}`}
                            >
                                {tf.label}
                            </button>
                        ))}
                    </div>

                    <button
                        onClick={fetchChartData}
                        disabled={isLoading}
                        className="btn btn-ghost btn-sm"
                    >
                        <RefreshCw size={14} className={isLoading ? 'pulse' : ''} />
                    </button>
                </div>
            </div>

            <div className="card-body" style={{ padding: 0 }}>
                {error ? (
                    <div style={{
                        padding: '48px',
                        textAlign: 'center',
                        color: 'var(--text-secondary)'
                    }}>
                        <TrendingUp size={32} style={{ marginBottom: '8px', opacity: 0.5 }} />
                        <p>{error}</p>
                        <button onClick={fetchChartData} className="btn btn-secondary btn-sm" style={{ marginTop: '12px' }}>
                            Retry
                        </button>
                    </div>
                ) : (
                    <div
                        ref={chartContainerRef}
                        style={{
                            width: '100%',
                            height: '400px',
                            position: 'relative'
                        }}
                    >
                        {isLoading && (
                            <div style={{
                                position: 'absolute',
                                top: '50%',
                                left: '50%',
                                transform: 'translate(-50%, -50%)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                color: 'var(--text-secondary)',
                                zIndex: 10,
                            }}>
                                <RefreshCw size={16} className="pulse" />
                                Loading chart...
                            </div>
                        )}
                    </div>
                )}
            </div>

            {source && (
                <div className="card-footer" style={{
                    fontSize: '0.75rem',
                    color: 'var(--text-tertiary)',
                    display: 'flex',
                    justifyContent: 'space-between'
                }}>
                    <span>
                        <Clock size={12} style={{ marginRight: '4px' }} />
                        Updates every 30s
                    </span>
                    <span>Source: {source}</span>
                </div>
            )}
        </div>
    )
}

export default TradingChart
