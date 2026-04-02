import React, { useState, useMemo, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight,
  RefreshCw, Bell, BellOff, Filter, Search, Clock, DollarSign,
  BarChart3, AlertTriangle, Zap, ExternalLink, ChevronDown,
  ChevronUp, Star, StarOff, ArrowLeftRight, Percent
} from 'lucide-react'

// Exchanges with funding rate data
const EXCHANGES = {
  BINANCE: { name: 'Binance', color: '#F0B90B', icon: '₿' },
  BYBIT: { name: 'Bybit', color: '#F7A600', icon: 'B' },
  OKX: { name: 'OKX', color: '#FFFFFF', icon: 'O' },
  DYDX: { name: 'dYdX', color: '#6966FF', icon: 'D' },
  GMX: { name: 'GMX', color: '#4FA3FF', icon: 'G' },
  HYPERLIQUID: { name: 'Hyperliquid', color: '#00D4AA', icon: 'H' }
}

// Funding rate intervals
const INTERVALS = {
  '1H': { label: '1H', hours: 1 },
  '4H': { label: '4H', hours: 4 },
  '8H': { label: '8H', hours: 8 },
  '24H': { label: '24H', hours: 24 }
}

// Mock funding rate data
const MOCK_RATES = [
  {
    symbol: 'BTC',
    name: 'Bitcoin',
    price: 97500,
    rates: {
      BINANCE: { rate: 0.0082, predicted: 0.0075, nextIn: '3h 42m' },
      BYBIT: { rate: 0.0078, predicted: 0.0071, nextIn: '3h 42m' },
      OKX: { rate: 0.0085, predicted: 0.0079, nextIn: '3h 42m' },
      DYDX: { rate: 0.0091, predicted: 0.0084, nextIn: '55m' },
      GMX: { rate: 0.0076, predicted: 0.0069, nextIn: '7h 15m' },
      HYPERLIQUID: { rate: 0.0088, predicted: 0.0081, nextIn: '55m' }
    },
    openInterest: 12500000000,
    volume24h: 45000000000,
    avgRate7d: 0.0079
  },
  {
    symbol: 'ETH',
    name: 'Ethereum',
    price: 3450,
    rates: {
      BINANCE: { rate: 0.0065, predicted: 0.0058, nextIn: '3h 42m' },
      BYBIT: { rate: 0.0061, predicted: 0.0055, nextIn: '3h 42m' },
      OKX: { rate: 0.0068, predicted: 0.0062, nextIn: '3h 42m' },
      DYDX: { rate: 0.0072, predicted: 0.0066, nextIn: '55m' },
      GMX: { rate: 0.0059, predicted: 0.0053, nextIn: '7h 15m' },
      HYPERLIQUID: { rate: 0.0070, predicted: 0.0064, nextIn: '55m' }
    },
    openInterest: 6800000000,
    volume24h: 22000000000,
    avgRate7d: 0.0063
  },
  {
    symbol: 'SOL',
    name: 'Solana',
    price: 198,
    rates: {
      BINANCE: { rate: 0.0125, predicted: 0.0118, nextIn: '3h 42m' },
      BYBIT: { rate: 0.0132, predicted: 0.0125, nextIn: '3h 42m' },
      OKX: { rate: 0.0128, predicted: 0.0120, nextIn: '3h 42m' },
      DYDX: { rate: 0.0145, predicted: 0.0138, nextIn: '55m' },
      GMX: { rate: 0.0118, predicted: 0.0110, nextIn: '7h 15m' },
      HYPERLIQUID: { rate: 0.0142, predicted: 0.0135, nextIn: '55m' }
    },
    openInterest: 2100000000,
    volume24h: 8500000000,
    avgRate7d: 0.0128
  },
  {
    symbol: 'DOGE',
    name: 'Dogecoin',
    price: 0.38,
    rates: {
      BINANCE: { rate: -0.0045, predicted: -0.0038, nextIn: '3h 42m' },
      BYBIT: { rate: -0.0052, predicted: -0.0045, nextIn: '3h 42m' },
      OKX: { rate: -0.0048, predicted: -0.0041, nextIn: '3h 42m' },
      DYDX: { rate: -0.0055, predicted: -0.0048, nextIn: '55m' },
      GMX: { rate: -0.0042, predicted: -0.0035, nextIn: '7h 15m' },
      HYPERLIQUID: { rate: -0.0050, predicted: -0.0043, nextIn: '55m' }
    },
    openInterest: 890000000,
    volume24h: 3200000000,
    avgRate7d: -0.0048
  },
  {
    symbol: 'PEPE',
    name: 'Pepe',
    price: 0.0000195,
    rates: {
      BINANCE: { rate: 0.0285, predicted: 0.0275, nextIn: '3h 42m' },
      BYBIT: { rate: 0.0298, predicted: 0.0288, nextIn: '3h 42m' },
      OKX: { rate: 0.0292, predicted: 0.0282, nextIn: '3h 42m' },
      DYDX: null,
      GMX: null,
      HYPERLIQUID: { rate: 0.0305, predicted: 0.0295, nextIn: '55m' }
    },
    openInterest: 420000000,
    volume24h: 1800000000,
    avgRate7d: 0.0292
  },
  {
    symbol: 'WIF',
    name: 'Dogwifhat',
    price: 2.45,
    rates: {
      BINANCE: { rate: 0.0195, predicted: 0.0185, nextIn: '3h 42m' },
      BYBIT: { rate: 0.0208, predicted: 0.0198, nextIn: '3h 42m' },
      OKX: { rate: 0.0201, predicted: 0.0191, nextIn: '3h 42m' },
      DYDX: null,
      GMX: null,
      HYPERLIQUID: { rate: 0.0218, predicted: 0.0208, nextIn: '55m' }
    },
    openInterest: 310000000,
    volume24h: 1200000000,
    avgRate7d: 0.0205
  },
  {
    symbol: 'AVAX',
    name: 'Avalanche',
    price: 42.50,
    rates: {
      BINANCE: { rate: 0.0058, predicted: 0.0052, nextIn: '3h 42m' },
      BYBIT: { rate: 0.0055, predicted: 0.0049, nextIn: '3h 42m' },
      OKX: { rate: 0.0061, predicted: 0.0055, nextIn: '3h 42m' },
      DYDX: { rate: 0.0065, predicted: 0.0059, nextIn: '55m' },
      GMX: { rate: 0.0052, predicted: 0.0046, nextIn: '7h 15m' },
      HYPERLIQUID: { rate: 0.0063, predicted: 0.0057, nextIn: '55m' }
    },
    openInterest: 580000000,
    volume24h: 2100000000,
    avgRate7d: 0.0058
  },
  {
    symbol: 'ARB',
    name: 'Arbitrum',
    price: 1.15,
    rates: {
      BINANCE: { rate: -0.0022, predicted: -0.0018, nextIn: '3h 42m' },
      BYBIT: { rate: -0.0028, predicted: -0.0024, nextIn: '3h 42m' },
      OKX: { rate: -0.0025, predicted: -0.0021, nextIn: '3h 42m' },
      DYDX: { rate: -0.0032, predicted: -0.0028, nextIn: '55m' },
      GMX: { rate: -0.0019, predicted: -0.0015, nextIn: '7h 15m' },
      HYPERLIQUID: { rate: -0.0029, predicted: -0.0025, nextIn: '55m' }
    },
    openInterest: 420000000,
    volume24h: 980000000,
    avgRate7d: -0.0025
  }
]

// Calculate arbitrage opportunities
const calculateArbitrage = (rates) => {
  const validRates = Object.entries(rates)
    .filter(([_, data]) => data !== null)
    .map(([exchange, data]) => ({ exchange, rate: data.rate }))

  if (validRates.length < 2) return null

  const sorted = validRates.sort((a, b) => a.rate - b.rate)
  const lowest = sorted[0]
  const highest = sorted[sorted.length - 1]
  const spread = highest.rate - lowest.rate

  return {
    longExchange: lowest.exchange,
    shortExchange: highest.exchange,
    spread,
    annualized: spread * 3 * 365 // Assuming 8h funding
  }
}

// Rate display component
const RateDisplay = ({ rate, size = 'md' }) => {
  const isPositive = rate > 0
  const absRate = Math.abs(rate)
  const textSize = size === 'lg' ? 'text-lg' : size === 'sm' ? 'text-xs' : 'text-sm'

  return (
    <div className={`flex items-center gap-1 ${textSize} ${
      isPositive ? 'text-green-400' : rate < 0 ? 'text-red-400' : 'text-gray-400'
    }`}>
      {isPositive ? (
        <TrendingUp className={size === 'lg' ? 'w-5 h-5' : 'w-4 h-4'} />
      ) : rate < 0 ? (
        <TrendingDown className={size === 'lg' ? 'w-5 h-5' : 'w-4 h-4'} />
      ) : null}
      <span className="font-mono font-medium">
        {isPositive ? '+' : ''}{(rate * 100).toFixed(4)}%
      </span>
    </div>
  )
}

// Exchange badge
const ExchangeBadge = ({ exchange }) => {
  const ex = EXCHANGES[exchange]
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-1 rounded text-xs font-medium"
      style={{ backgroundColor: `${ex.color}20`, color: ex.color }}
    >
      <span className="w-4 h-4 rounded flex items-center justify-center text-[10px] font-bold"
        style={{ backgroundColor: ex.color, color: '#000' }}>
        {ex.icon}
      </span>
      {ex.name}
    </div>
  )
}

// Asset row component
const AssetRow = ({ asset, watchlist, onToggleWatch, onSelect, expanded, onExpand }) => {
  const arbitrage = useMemo(() => calculateArbitrage(asset.rates), [asset.rates])
  const avgRate = useMemo(() => {
    const validRates = Object.values(asset.rates).filter(r => r !== null)
    return validRates.reduce((sum, r) => sum + r.rate, 0) / validRates.length
  }, [asset.rates])

  const isWatched = watchlist.includes(asset.symbol)

  return (
    <div className="border border-white/10 rounded-lg overflow-hidden">
      <div
        className="p-4 bg-white/5 hover:bg-white/[0.07] cursor-pointer transition-colors"
        onClick={() => onExpand(expanded ? null : asset.symbol)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleWatch(asset.symbol) }}
              className={`p-1 rounded transition-colors ${
                isWatched ? 'text-yellow-400' : 'text-gray-500 hover:text-gray-400'
              }`}
            >
              {isWatched ? <Star className="w-5 h-5 fill-current" /> : <StarOff className="w-5 h-5" />}
            </button>

            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white">{asset.symbol}</span>
                <span className="text-sm text-gray-400">{asset.name}</span>
              </div>
              <div className="text-sm text-gray-400">
                ${asset.price.toLocaleString(undefined, { maximumFractionDigits: asset.price < 1 ? 8 : 2 })}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            {/* Average Rate */}
            <div className="text-right">
              <div className="text-xs text-gray-500 mb-1">Avg Rate</div>
              <RateDisplay rate={avgRate} size="md" />
            </div>

            {/* 7d Average */}
            <div className="text-right">
              <div className="text-xs text-gray-500 mb-1">7d Avg</div>
              <RateDisplay rate={asset.avgRate7d} size="sm" />
            </div>

            {/* Arbitrage Spread */}
            {arbitrage && arbitrage.spread > 0.001 && (
              <div className="text-right">
                <div className="text-xs text-gray-500 mb-1">Arb Spread</div>
                <div className="text-sm font-mono text-cyan-400">
                  {(arbitrage.spread * 100).toFixed(4)}%
                </div>
              </div>
            )}

            {/* Open Interest */}
            <div className="text-right min-w-[100px]">
              <div className="text-xs text-gray-500 mb-1">Open Interest</div>
              <div className="text-sm font-medium">
                ${(asset.openInterest / 1e9).toFixed(2)}B
              </div>
            </div>

            <div className="w-6">
              {expanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </div>
          </div>
        </div>
      </div>

      {/* Expanded exchange details */}
      {expanded && (
        <div className="p-4 bg-white/[0.02] border-t border-white/10">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            {Object.entries(EXCHANGES).map(([key, exchange]) => {
              const data = asset.rates[key]
              return (
                <div key={key} className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <ExchangeBadge exchange={key} />
                    {data && (
                      <a href="#" className="text-gray-500 hover:text-gray-400">
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>

                  {data ? (
                    <>
                      <div className="mb-2">
                        <div className="text-xs text-gray-500">Current</div>
                        <RateDisplay rate={data.rate} size="lg" />
                      </div>
                      <div className="flex justify-between text-xs">
                        <div>
                          <div className="text-gray-500">Predicted</div>
                          <RateDisplay rate={data.predicted} size="sm" />
                        </div>
                        <div className="text-right">
                          <div className="text-gray-500">Next In</div>
                          <div className="text-gray-300 flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {data.nextIn}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-4 text-gray-500 text-sm">
                      Not Listed
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* Arbitrage opportunity */}
          {arbitrage && arbitrage.spread > 0.001 && (
            <div className="mt-4 p-3 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-cyan-400" />
                <span className="text-sm font-medium text-cyan-400">Arbitrage Opportunity</span>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">Long on</span>
                  <ExchangeBadge exchange={arbitrage.longExchange} />
                </div>
                <ArrowLeftRight className="w-4 h-4 text-gray-500" />
                <div className="flex items-center gap-2">
                  <span className="text-gray-400">Short on</span>
                  <ExchangeBadge exchange={arbitrage.shortExchange} />
                </div>
                <div className="ml-auto flex items-center gap-4">
                  <div>
                    <span className="text-gray-400">Spread: </span>
                    <span className="font-mono text-cyan-400">{(arbitrage.spread * 100).toFixed(4)}%</span>
                  </div>
                  <div>
                    <span className="text-gray-400">APR: </span>
                    <span className="font-mono text-cyan-400">{(arbitrage.annualized * 100).toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Funding rate heatmap
const FundingHeatmap = ({ data }) => {
  const getColor = (rate) => {
    if (rate === null) return 'bg-gray-800'
    if (rate > 0.02) return 'bg-green-500'
    if (rate > 0.01) return 'bg-green-600'
    if (rate > 0.005) return 'bg-green-700'
    if (rate > 0) return 'bg-green-900'
    if (rate > -0.005) return 'bg-red-900'
    if (rate > -0.01) return 'bg-red-700'
    if (rate > -0.02) return 'bg-red-600'
    return 'bg-red-500'
  }

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Funding Rate Heatmap
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left text-gray-500 pb-2 pr-4">Asset</th>
              {Object.keys(EXCHANGES).map(ex => (
                <th key={ex} className="text-center text-gray-500 pb-2 px-2">
                  {EXCHANGES[ex].name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.slice(0, 8).map(asset => (
              <tr key={asset.symbol}>
                <td className="py-1 pr-4 font-medium">{asset.symbol}</td>
                {Object.keys(EXCHANGES).map(ex => {
                  const rate = asset.rates[ex]?.rate
                  return (
                    <td key={ex} className="px-1 py-1">
                      <div
                        className={`${getColor(rate)} rounded px-2 py-1 text-center font-mono ${
                          rate === null ? 'text-gray-600' : 'text-white'
                        }`}
                      >
                        {rate === null ? '-' : `${(rate * 100).toFixed(3)}%`}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-4 text-xs">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-red-500"></div>
          <span className="text-gray-400">Negative (shorts pay)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-green-500"></div>
          <span className="text-gray-400">Positive (longs pay)</span>
        </div>
      </div>
    </div>
  )
}

// Top opportunities section
const TopOpportunities = ({ data }) => {
  const opportunities = useMemo(() => {
    return data
      .map(asset => ({
        ...asset,
        arbitrage: calculateArbitrage(asset.rates)
      }))
      .filter(a => a.arbitrage && a.arbitrage.spread > 0.001)
      .sort((a, b) => b.arbitrage.spread - a.arbitrage.spread)
      .slice(0, 5)
  }, [data])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Zap className="w-4 h-4 text-cyan-400" />
        Top Arbitrage Opportunities
      </h3>

      <div className="space-y-3">
        {opportunities.length > 0 ? opportunities.map(opp => (
          <div key={opp.symbol} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
            <div className="flex items-center gap-3">
              <span className="font-bold">{opp.symbol}</span>
              <div className="flex items-center gap-1 text-xs text-gray-400">
                <ExchangeBadge exchange={opp.arbitrage.longExchange} />
                <ArrowLeftRight className="w-3 h-3" />
                <ExchangeBadge exchange={opp.arbitrage.shortExchange} />
              </div>
            </div>
            <div className="flex items-center gap-4 text-right">
              <div>
                <div className="text-xs text-gray-500">Spread</div>
                <div className="font-mono text-cyan-400">{(opp.arbitrage.spread * 100).toFixed(4)}%</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Est. APR</div>
                <div className="font-mono text-green-400">{(opp.arbitrage.annualized * 100).toFixed(1)}%</div>
              </div>
            </div>
          </div>
        )) : (
          <div className="text-center py-8 text-gray-500">
            No significant arbitrage opportunities found
          </div>
        )}
      </div>
    </div>
  )
}

// Historical rates chart (simplified)
const HistoricalRates = ({ symbol }) => {
  const hours = Array.from({ length: 24 }, (_, i) => i)

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Clock className="w-4 h-4" />
        24h Funding History - {symbol}
      </h3>

      <div className="h-32 flex items-end gap-1">
        {hours.map(h => {
          const value = Math.random() * 0.02 - 0.005 // Mock data
          const height = Math.abs(value) * 3000
          const isPositive = value > 0

          return (
            <div key={h} className="flex-1 flex flex-col items-center gap-1">
              <div
                className={`w-full rounded-t ${isPositive ? 'bg-green-500/60' : 'bg-red-500/60'}`}
                style={{ height: `${height}%` }}
              />
            </div>
          )
        })}
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-2">
        <span>24h ago</span>
        <span>Now</span>
      </div>
    </div>
  )
}

// Alert settings modal
const AlertModal = ({ isOpen, onClose, symbol, onSave }) => {
  const [threshold, setThreshold] = useState(0.01)
  const [direction, setDirection] = useState('both')

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Set Funding Rate Alert</h3>
        <p className="text-sm text-gray-400 mb-4">Get notified when {symbol} funding rate crosses your threshold</p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Threshold (%)</label>
            <input
              type="number"
              value={threshold * 100}
              onChange={(e) => setThreshold(parseFloat(e.target.value) / 100)}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
              step="0.01"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Direction</label>
            <div className="flex gap-2">
              {['above', 'below', 'both'].map(d => (
                <button
                  key={d}
                  onClick={() => setDirection(d)}
                  className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    direction === d
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                      : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  {d.charAt(0).toUpperCase() + d.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => { onSave({ symbol, threshold, direction }); onClose() }}
            className="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg font-medium transition-colors"
          >
            Set Alert
          </button>
        </div>
      </div>
    </div>
  )
}

// Stats overview
const StatsOverview = ({ data }) => {
  const stats = useMemo(() => {
    const allRates = data.flatMap(a =>
      Object.values(a.rates).filter(r => r !== null).map(r => r.rate)
    )
    const avgRate = allRates.reduce((a, b) => a + b, 0) / allRates.length
    const positiveCount = data.filter(a => {
      const rates = Object.values(a.rates).filter(r => r !== null)
      const avg = rates.reduce((sum, r) => sum + r.rate, 0) / rates.length
      return avg > 0
    }).length

    const totalOI = data.reduce((sum, a) => sum + a.openInterest, 0)

    return { avgRate, positiveCount, negativeCount: data.length - positiveCount, totalOI }
  }, [data])

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Avg Funding Rate</div>
        <RateDisplay rate={stats.avgRate} size="lg" />
      </div>
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Positive Rates</div>
        <div className="text-2xl font-bold text-green-400">{stats.positiveCount}</div>
      </div>
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Negative Rates</div>
        <div className="text-2xl font-bold text-red-400">{stats.negativeCount}</div>
      </div>
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Total Open Interest</div>
        <div className="text-2xl font-bold">${(stats.totalOI / 1e9).toFixed(1)}B</div>
      </div>
    </div>
  )
}

// Main component
export const FundingRates = () => {
  const [data] = useState(MOCK_RATES)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('rate')
  const [sortDir, setSortDir] = useState('desc')
  const [watchlist, setWatchlist] = useState(['BTC', 'ETH', 'SOL'])
  const [showWatchlistOnly, setShowWatchlistOnly] = useState(false)
  const [expandedAsset, setExpandedAsset] = useState(null)
  const [alertModal, setAlertModal] = useState({ open: false, symbol: null })
  const [selectedInterval, setSelectedInterval] = useState('8H')
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1000)
  }, [])

  const toggleWatchlist = useCallback((symbol) => {
    setWatchlist(prev =>
      prev.includes(symbol)
        ? prev.filter(s => s !== symbol)
        : [...prev, symbol]
    )
  }, [])

  const filteredData = useMemo(() => {
    let result = [...data]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(a =>
        a.symbol.toLowerCase().includes(query) ||
        a.name.toLowerCase().includes(query)
      )
    }

    if (showWatchlistOnly) {
      result = result.filter(a => watchlist.includes(a.symbol))
    }

    // Sort
    result.sort((a, b) => {
      let aVal, bVal

      switch (sortBy) {
        case 'rate':
          aVal = Object.values(a.rates).filter(r => r !== null).reduce((sum, r) => sum + r.rate, 0)
          bVal = Object.values(b.rates).filter(r => r !== null).reduce((sum, r) => sum + r.rate, 0)
          break
        case 'oi':
          aVal = a.openInterest
          bVal = b.openInterest
          break
        case 'volume':
          aVal = a.volume24h
          bVal = b.volume24h
          break
        default:
          aVal = a.symbol
          bVal = b.symbol
      }

      return sortDir === 'desc' ? bVal - aVal : aVal - bVal
    })

    return result
  }, [data, searchQuery, showWatchlistOnly, watchlist, sortBy, sortDir])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Percent className="w-7 h-7 text-cyan-400" />
              Funding Rate Tracker
            </h1>
            <p className="text-gray-400 mt-1">Real-time perpetual funding rates across exchanges</p>
          </div>

          <div className="flex items-center gap-3">
            {/* Interval selector */}
            <div className="flex bg-white/5 rounded-lg p-1">
              {Object.entries(INTERVALS).map(([key, interval]) => (
                <button
                  key={key}
                  onClick={() => setSelectedInterval(key)}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    selectedInterval === key
                      ? 'bg-cyan-500/20 text-cyan-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {interval.label}
                </button>
              ))}
            </div>

            <button
              onClick={handleRefresh}
              className={`p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors ${
                refreshing ? 'animate-spin' : ''
              }`}
            >
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Stats Overview */}
        <StatsOverview data={data} />

        {/* Controls */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search assets..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <button
            onClick={() => setShowWatchlistOnly(!showWatchlistOnly)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showWatchlistOnly
                ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            <Star className="w-4 h-4" />
            Watchlist ({watchlist.length})
          </button>

          <select
            value={`${sortBy}-${sortDir}`}
            onChange={(e) => {
              const [by, dir] = e.target.value.split('-')
              setSortBy(by)
              setSortDir(dir)
            }}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
          >
            <option value="rate-desc">Highest Rate</option>
            <option value="rate-asc">Lowest Rate</option>
            <option value="oi-desc">Highest OI</option>
            <option value="volume-desc">Highest Volume</option>
          </select>
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Asset list - 2 columns */}
          <div className="lg:col-span-2 space-y-3">
            {filteredData.map(asset => (
              <AssetRow
                key={asset.symbol}
                asset={asset}
                watchlist={watchlist}
                onToggleWatch={toggleWatchlist}
                onSelect={(symbol) => setAlertModal({ open: true, symbol })}
                expanded={expandedAsset === asset.symbol}
                onExpand={setExpandedAsset}
              />
            ))}

            {filteredData.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                No assets match your filters
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <TopOpportunities data={data} />
            <FundingHeatmap data={data} />
            {expandedAsset && <HistoricalRates symbol={expandedAsset} />}
          </div>
        </div>

        {/* Alert Modal */}
        <AlertModal
          isOpen={alertModal.open}
          symbol={alertModal.symbol}
          onClose={() => setAlertModal({ open: false, symbol: null })}
          onSave={(alert) => console.log('Alert saved:', alert)}
        />
      </div>
    </div>
  )
}

export default FundingRates
