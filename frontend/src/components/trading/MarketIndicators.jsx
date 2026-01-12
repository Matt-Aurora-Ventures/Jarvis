import React, { useState, useEffect } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  AlertTriangle,
  Shield,
  Zap,
  Clock,
} from 'lucide-react'

/**
 * MarketIndicators - Display current market conditions
 * Shows volatility, trend, regime, and fear/greed index
 */
export function MarketIndicators({ className = '' }) {
  const [data, setData] = useState({
    volatility: 'medium',
    trend: 'neutral',
    regime: 'ranging',
    fearGreed: 50,
    lastUpdate: null,
    loading: true,
  })

  useEffect(() => {
    fetchMarketData()
    const interval = setInterval(fetchMarketData, 60000) // Update every minute
    return () => clearInterval(interval)
  }, [])

  const fetchMarketData = async () => {
    try {
      const response = await fetch('/api/market/indicators')
      if (response.ok) {
        const result = await response.json()
        setData({
          ...result,
          lastUpdate: new Date(),
          loading: false,
        })
      }
    } catch (error) {
      // Use mock data on error
      setData({
        volatility: 'medium',
        trend: 'bullish',
        regime: 'trending',
        fearGreed: 65,
        lastUpdate: new Date(),
        loading: false,
      })
    }
  }

  const getVolatilityConfig = (level) => {
    const configs = {
      low: { color: 'var(--success)', label: 'Low', icon: Shield },
      medium: { color: 'var(--warning)', label: 'Medium', icon: Activity },
      high: { color: 'var(--danger)', label: 'High', icon: AlertTriangle },
      extreme: { color: 'var(--danger)', label: 'Extreme', icon: Zap },
    }
    return configs[level] || configs.medium
  }

  const getTrendConfig = (trend) => {
    const configs = {
      bullish: { color: 'var(--success)', label: 'Bullish', icon: TrendingUp },
      bearish: { color: 'var(--danger)', label: 'Bearish', icon: TrendingDown },
      neutral: { color: 'var(--text-secondary)', label: 'Neutral', icon: Minus },
    }
    return configs[trend] || configs.neutral
  }

  const getRegimeConfig = (regime) => {
    const configs = {
      trending: { color: 'var(--accent-primary)', label: 'Trending' },
      ranging: { color: 'var(--text-secondary)', label: 'Ranging' },
      volatile: { color: 'var(--warning)', label: 'Volatile' },
      breakdown: { color: 'var(--danger)', label: 'Breakdown' },
      breakout: { color: 'var(--success)', label: 'Breakout' },
    }
    return configs[regime] || configs.ranging
  }

  const getFearGreedConfig = (value) => {
    if (value <= 25) return { label: 'Extreme Fear', color: 'var(--danger)' }
    if (value <= 45) return { label: 'Fear', color: 'var(--warning)' }
    if (value <= 55) return { label: 'Neutral', color: 'var(--text-secondary)' }
    if (value <= 75) return { label: 'Greed', color: 'var(--success)' }
    return { label: 'Extreme Greed', color: 'var(--success)' }
  }

  const volatilityConfig = getVolatilityConfig(data.volatility)
  const trendConfig = getTrendConfig(data.trend)
  const regimeConfig = getRegimeConfig(data.regime)
  const fearGreedConfig = getFearGreedConfig(data.fearGreed)
  const VolatilityIcon = volatilityConfig.icon
  const TrendIcon = trendConfig.icon

  return (
    <div className={`market-indicators ${className}`}>
      <div className="indicators-header">
        <h3>Market Conditions</h3>
        {data.lastUpdate && (
          <span className="last-update">
            <Clock size={12} />
            {data.lastUpdate.toLocaleTimeString()}
          </span>
        )}
      </div>

      <div className="indicators-grid">
        {/* Volatility */}
        <div className="indicator-card">
          <div className="indicator-icon" style={{ color: volatilityConfig.color }}>
            <VolatilityIcon size={20} />
          </div>
          <div className="indicator-info">
            <span className="indicator-label">Volatility</span>
            <span className="indicator-value" style={{ color: volatilityConfig.color }}>
              {volatilityConfig.label}
            </span>
          </div>
        </div>

        {/* Trend */}
        <div className="indicator-card">
          <div className="indicator-icon" style={{ color: trendConfig.color }}>
            <TrendIcon size={20} />
          </div>
          <div className="indicator-info">
            <span className="indicator-label">4H Trend</span>
            <span className="indicator-value" style={{ color: trendConfig.color }}>
              {trendConfig.label}
            </span>
          </div>
        </div>

        {/* Regime */}
        <div className="indicator-card">
          <div className="indicator-info">
            <span className="indicator-label">Regime</span>
            <span className="indicator-value" style={{ color: regimeConfig.color }}>
              {regimeConfig.label}
            </span>
          </div>
        </div>

        {/* Fear & Greed */}
        <div className="indicator-card fear-greed">
          <div className="indicator-info">
            <span className="indicator-label">Fear & Greed</span>
            <span className="indicator-value" style={{ color: fearGreedConfig.color }}>
              {data.fearGreed} - {fearGreedConfig.label}
            </span>
          </div>
          <div className="fear-greed-bar">
            <div
              className="fear-greed-fill"
              style={{
                width: `${data.fearGreed}%`,
                background: fearGreedConfig.color,
              }}
            />
            <div
              className="fear-greed-marker"
              style={{ left: `${data.fearGreed}%` }}
            />
          </div>
        </div>
      </div>

      <style jsx>{`
        .market-indicators {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 16px;
        }

        .indicators-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }

        .indicators-header h3 {
          margin: 0;
          font-size: 14px;
          font-weight: 600;
          color: var(--text-primary);
        }

        .last-update {
          display: flex;
          align-items: center;
          gap: 4px;
          font-size: 11px;
          color: var(--text-tertiary);
        }

        .indicators-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .indicator-card {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 12px;
          background: var(--bg-primary);
          border-radius: 8px;
          border: 1px solid var(--border-primary);
        }

        .indicator-card.fear-greed {
          grid-column: 1 / -1;
          flex-direction: column;
          align-items: stretch;
          gap: 8px;
        }

        .indicator-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          background: var(--bg-secondary);
          border-radius: 8px;
        }

        .indicator-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }

        .fear-greed .indicator-info {
          flex-direction: row;
          justify-content: space-between;
          align-items: center;
        }

        .indicator-label {
          font-size: 11px;
          color: var(--text-tertiary);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .indicator-value {
          font-size: 14px;
          font-weight: 600;
        }

        .fear-greed-bar {
          position: relative;
          height: 6px;
          background: linear-gradient(
            to right,
            var(--danger),
            var(--warning),
            var(--success)
          );
          border-radius: 3px;
          overflow: visible;
        }

        .fear-greed-fill {
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          border-radius: 3px;
          opacity: 0;
        }

        .fear-greed-marker {
          position: absolute;
          top: 50%;
          transform: translate(-50%, -50%);
          width: 12px;
          height: 12px;
          background: white;
          border: 2px solid var(--bg-primary);
          border-radius: 50%;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }

        @media (max-width: 480px) {
          .indicators-grid {
            grid-template-columns: 1fr;
          }

          .indicator-card.fear-greed {
            grid-column: 1;
          }
        }
      `}</style>
    </div>
  )
}

/**
 * MiniMarketIndicator - Compact indicator for nav/header
 */
export function MiniMarketIndicator({ type = 'volatility' }) {
  const [value, setValue] = useState('medium')

  useEffect(() => {
    // Fetch from API
    fetch('/api/market/indicators')
      .then(r => r.json())
      .then(data => setValue(data[type] || 'medium'))
      .catch(() => setValue('medium'))
  }, [type])

  const colors = {
    low: 'var(--success)',
    medium: 'var(--warning)',
    high: 'var(--danger)',
    bullish: 'var(--success)',
    bearish: 'var(--danger)',
    neutral: 'var(--text-secondary)',
  }

  return (
    <span
      className="mini-indicator"
      title={`${type}: ${value}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        padding: '4px 8px',
        background: 'var(--bg-secondary)',
        borderRadius: '4px',
        fontSize: '12px',
        fontWeight: '500',
        color: colors[value] || 'var(--text-secondary)',
      }}
    >
      <span
        style={{
          width: '6px',
          height: '6px',
          borderRadius: '50%',
          background: 'currentColor',
        }}
      />
      {value}
    </span>
  )
}

export default MarketIndicators
