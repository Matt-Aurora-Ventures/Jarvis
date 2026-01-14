import React, { useState, useMemo } from 'react'
import {
  Grid3X3, TrendingUp, TrendingDown, BarChart3, Clock, Filter,
  RefreshCw, Download, ZoomIn, ZoomOut, Maximize2, Info,
  ChevronDown, Layers, DollarSign, Percent, ArrowUpRight
} from 'lucide-react'

const MARKET_DATA = {
  'Layer 1': [
    { symbol: 'BTC', name: 'Bitcoin', price: 95420, change: 2.5, marketCap: 1890000000000, volume: 45000000000 },
    { symbol: 'ETH', name: 'Ethereum', price: 3280, change: 1.8, marketCap: 394000000000, volume: 18000000000 },
    { symbol: 'SOL', name: 'Solana', price: 185, change: 5.2, marketCap: 85000000000, volume: 4500000000 },
    { symbol: 'ADA', name: 'Cardano', price: 0.95, change: -1.2, marketCap: 33000000000, volume: 800000000 },
    { symbol: 'AVAX', name: 'Avalanche', price: 38.50, change: 3.8, marketCap: 15000000000, volume: 650000000 },
    { symbol: 'DOT', name: 'Polkadot', price: 7.85, change: -0.5, marketCap: 11000000000, volume: 420000000 },
    { symbol: 'NEAR', name: 'NEAR', price: 5.85, change: 4.2, marketCap: 6500000000, volume: 380000000 },
    { symbol: 'ATOM', name: 'Cosmos', price: 9.45, change: 1.5, marketCap: 3600000000, volume: 250000000 }
  ],
  'Layer 2': [
    { symbol: 'MATIC', name: 'Polygon', price: 0.52, change: 2.1, marketCap: 4800000000, volume: 320000000 },
    { symbol: 'ARB', name: 'Arbitrum', price: 1.15, change: 3.5, marketCap: 4200000000, volume: 280000000 },
    { symbol: 'OP', name: 'Optimism', price: 2.85, change: -2.1, marketCap: 3100000000, volume: 220000000 },
    { symbol: 'IMX', name: 'Immutable', price: 2.10, change: 1.8, marketCap: 2800000000, volume: 150000000 },
    { symbol: 'STRK', name: 'Starknet', price: 0.75, change: -3.2, marketCap: 1500000000, volume: 95000000 }
  ],
  'DeFi': [
    { symbol: 'UNI', name: 'Uniswap', price: 13.20, change: 2.8, marketCap: 9900000000, volume: 380000000 },
    { symbol: 'LINK', name: 'Chainlink', price: 22.40, change: 1.2, marketCap: 13500000000, volume: 520000000 },
    { symbol: 'AAVE', name: 'Aave', price: 285, change: 4.5, marketCap: 4200000000, volume: 180000000 },
    { symbol: 'MKR', name: 'Maker', price: 2150, change: -0.8, marketCap: 1900000000, volume: 85000000 },
    { symbol: 'CRV', name: 'Curve', price: 0.85, change: -4.2, marketCap: 1100000000, volume: 120000000 },
    { symbol: 'SNX', name: 'Synthetix', price: 3.20, change: 2.1, marketCap: 980000000, volume: 65000000 },
    { symbol: 'COMP', name: 'Compound', price: 68, change: 1.5, marketCap: 580000000, volume: 45000000 }
  ],
  'Exchange': [
    { symbol: 'BNB', name: 'BNB', price: 680, change: 0.8, marketCap: 98000000000, volume: 1800000000 },
    { symbol: 'OKB', name: 'OKB', price: 52, change: 1.2, marketCap: 3100000000, volume: 85000000 },
    { symbol: 'CRO', name: 'Cronos', price: 0.12, change: -1.5, marketCap: 3200000000, volume: 45000000 },
    { symbol: 'GT', name: 'Gate', price: 8.50, change: 0.5, marketCap: 1200000000, volume: 32000000 }
  ],
  'Meme': [
    { symbol: 'DOGE', name: 'Dogecoin', price: 0.38, change: 8.5, marketCap: 55000000000, volume: 3200000000 },
    { symbol: 'SHIB', name: 'Shiba Inu', price: 0.000025, change: 6.2, marketCap: 14500000000, volume: 850000000 },
    { symbol: 'PEPE', name: 'Pepe', price: 0.000018, change: 12.5, marketCap: 7500000000, volume: 1200000000 },
    { symbol: 'WIF', name: 'dogwifhat', price: 2.45, change: -5.2, marketCap: 2400000000, volume: 320000000 },
    { symbol: 'BONK', name: 'Bonk', price: 0.000032, change: 4.8, marketCap: 2100000000, volume: 280000000 },
    { symbol: 'FLOKI', name: 'Floki', price: 0.00018, change: 3.2, marketCap: 1700000000, volume: 150000000 }
  ],
  'AI': [
    { symbol: 'FET', name: 'Fetch.ai', price: 2.15, change: 5.8, marketCap: 5400000000, volume: 420000000 },
    { symbol: 'RENDER', name: 'Render', price: 8.50, change: 4.2, marketCap: 4400000000, volume: 280000000 },
    { symbol: 'TAO', name: 'Bittensor', price: 520, change: -2.5, marketCap: 3800000000, volume: 150000000 },
    { symbol: 'AGIX', name: 'SingularityNET', price: 0.85, change: 3.5, marketCap: 1100000000, volume: 95000000 },
    { symbol: 'OCEAN', name: 'Ocean', price: 0.95, change: 2.1, marketCap: 580000000, volume: 45000000 }
  ],
  'Gaming': [
    { symbol: 'AXS', name: 'Axie Infinity', price: 8.20, change: 2.5, marketCap: 1200000000, volume: 85000000 },
    { symbol: 'SAND', name: 'Sandbox', price: 0.55, change: -1.8, marketCap: 1100000000, volume: 120000000 },
    { symbol: 'MANA', name: 'Decentraland', price: 0.52, change: 1.2, marketCap: 1000000000, volume: 95000000 },
    { symbol: 'GALA', name: 'Gala', price: 0.042, change: 3.8, marketCap: 1500000000, volume: 180000000 },
    { symbol: 'ENJ', name: 'Enjin', price: 0.28, change: -0.5, marketCap: 280000000, volume: 25000000 }
  ],
  'Privacy': [
    { symbol: 'XMR', name: 'Monero', price: 185, change: 1.5, marketCap: 3400000000, volume: 120000000 },
    { symbol: 'ZEC', name: 'Zcash', price: 42, change: 0.8, marketCap: 680000000, volume: 45000000 },
    { symbol: 'SCRT', name: 'Secret', price: 0.45, change: -2.1, marketCap: 95000000, volume: 8500000 }
  ]
}

const TIME_PERIODS = ['1h', '4h', '24h', '7d', '30d']

export function MarketHeatMap() {
  const [timeframe, setTimeframe] = useState('24h')
  const [viewMode, setViewMode] = useState('category') // category, flat, treemap
  const [sortBy, setSortBy] = useState('marketCap') // marketCap, change, volume
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [showLabels, setShowLabels] = useState(true)
  const [minMarketCap, setMinMarketCap] = useState(0)

  // Get color based on change percentage
  const getColor = (change) => {
    if (change >= 10) return 'bg-green-500'
    if (change >= 5) return 'bg-green-500/80'
    if (change >= 2) return 'bg-green-500/60'
    if (change > 0) return 'bg-green-500/40'
    if (change === 0) return 'bg-gray-500'
    if (change >= -2) return 'bg-red-500/40'
    if (change >= -5) return 'bg-red-500/60'
    if (change >= -10) return 'bg-red-500/80'
    return 'bg-red-500'
  }

  const getTextColor = (change) => {
    if (Math.abs(change) >= 5) return 'text-white'
    return change >= 0 ? 'text-green-400' : 'text-red-400'
  }

  // Flatten all tokens for flat view
  const allTokens = useMemo(() => {
    const tokens = []
    Object.entries(MARKET_DATA).forEach(([category, categoryTokens]) => {
      categoryTokens.forEach(token => {
        tokens.push({ ...token, category })
      })
    })
    return tokens.filter(t => t.marketCap >= minMarketCap)
      .sort((a, b) => {
        if (sortBy === 'marketCap') return b.marketCap - a.marketCap
        if (sortBy === 'change') return b.change - a.change
        return b.volume - a.volume
      })
  }, [sortBy, minMarketCap])

  // Market summary
  const summary = useMemo(() => {
    const gainers = allTokens.filter(t => t.change > 0)
    const losers = allTokens.filter(t => t.change < 0)
    const unchanged = allTokens.filter(t => t.change === 0)
    const totalMcap = allTokens.reduce((sum, t) => sum + t.marketCap, 0)
    const totalVolume = allTokens.reduce((sum, t) => sum + t.volume, 0)
    const avgChange = allTokens.reduce((sum, t) => sum + t.change, 0) / allTokens.length
    const topGainer = allTokens.reduce((max, t) => t.change > max.change ? t : max, allTokens[0])
    const topLoser = allTokens.reduce((min, t) => t.change < min.change ? t : min, allTokens[0])

    return {
      gainers: gainers.length,
      losers: losers.length,
      unchanged: unchanged.length,
      totalMcap,
      totalVolume,
      avgChange,
      topGainer,
      topLoser
    }
  }, [allTokens])

  const formatMarketCap = (value) => {
    if (value >= 1e12) return `$${(value / 1e12).toFixed(2)}T`
    if (value >= 1e9) return `$${(value / 1e9).toFixed(2)}B`
    if (value >= 1e6) return `$${(value / 1e6).toFixed(0)}M`
    return `$${value.toLocaleString()}`
  }

  // Calculate block size based on market cap (for treemap)
  const getBlockSize = (marketCap) => {
    const maxMcap = Math.max(...allTokens.map(t => t.marketCap))
    const ratio = marketCap / maxMcap
    const minSize = 60
    const maxSize = 200
    return minSize + ratio * (maxSize - minSize)
  }

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-orange-500/20 rounded-lg">
            <Grid3X3 className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Market Heat Map</h1>
            <p className="text-sm text-gray-400">Visual market overview by category</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['category', 'flat', 'treemap'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                viewMode === mode ? 'bg-orange-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-gray-400" />
          {TIME_PERIODS.map(period => (
            <button
              key={period}
              onClick={() => setTimeframe(period)}
              className={`px-3 py-1 rounded text-sm ${
                timeframe === period ? 'bg-orange-500 text-black' : 'bg-white/10 text-gray-300 hover:bg-white/20'
              }`}
            >
              {period}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white/10 border border-white/20 rounded px-2 py-1 text-white text-sm"
          >
            <option value="marketCap">Market Cap</option>
            <option value="change">Change %</option>
            <option value="volume">Volume</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoom(Math.max(0.5, zoom - 0.25))}
            className="p-1.5 bg-white/10 rounded hover:bg-white/20"
          >
            <ZoomOut className="w-4 h-4 text-gray-400" />
          </button>
          <span className="text-sm text-gray-400">{(zoom * 100).toFixed(0)}%</span>
          <button
            onClick={() => setZoom(Math.min(2, zoom + 0.25))}
            className="p-1.5 bg-white/10 rounded hover:bg-white/20"
          >
            <ZoomIn className="w-4 h-4 text-gray-400" />
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-400">
          <input
            type="checkbox"
            checked={showLabels}
            onChange={(e) => setShowLabels(e.target.checked)}
            className="rounded bg-white/10"
          />
          Show Labels
        </label>
      </div>

      {/* Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mb-6">
        <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/30">
          <div className="text-xs text-gray-400">Gainers</div>
          <div className="text-xl font-bold text-green-400">{summary.gainers}</div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/30">
          <div className="text-xs text-gray-400">Losers</div>
          <div className="text-xl font-bold text-red-400">{summary.losers}</div>
        </div>
        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <div className="text-xs text-gray-400">Avg Change</div>
          <div className={`text-xl font-bold ${summary.avgChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {summary.avgChange >= 0 ? '+' : ''}{summary.avgChange.toFixed(2)}%
          </div>
        </div>
        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <div className="text-xs text-gray-400">Total MCap</div>
          <div className="text-xl font-bold text-white">{formatMarketCap(summary.totalMcap)}</div>
        </div>
        <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/30">
          <div className="text-xs text-gray-400">Top Gainer</div>
          <div className="text-lg font-bold text-green-400">
            {summary.topGainer?.symbol} +{summary.topGainer?.change}%
          </div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/30">
          <div className="text-xs text-gray-400">Top Loser</div>
          <div className="text-lg font-bold text-red-400">
            {summary.topLoser?.symbol} {summary.topLoser?.change}%
          </div>
        </div>
      </div>

      {/* Category View */}
      {viewMode === 'category' && (
        <div className="space-y-6" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
          {Object.entries(MARKET_DATA).map(([category, tokens]) => (
            <div key={category} className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
              <div className="p-4 border-b border-white/10 flex items-center justify-between bg-white/5">
                <div className="flex items-center gap-2">
                  <Layers className="w-5 h-5 text-orange-400" />
                  <h3 className="font-semibold text-white">{category}</h3>
                  <span className="text-sm text-gray-400">({tokens.length} tokens)</span>
                </div>
                <div className="text-sm text-gray-400">
                  MCap: {formatMarketCap(tokens.reduce((sum, t) => sum + t.marketCap, 0))}
                </div>
              </div>
              <div className="p-4">
                <div className="flex flex-wrap gap-2">
                  {tokens.sort((a, b) => b.marketCap - a.marketCap).map(token => (
                    <div
                      key={token.symbol}
                      className={`${getColor(token.change)} rounded-lg p-3 cursor-pointer hover:opacity-80 transition-opacity`}
                      style={{
                        minWidth: Math.max(80, getBlockSize(token.marketCap) * 0.6),
                        minHeight: Math.max(60, getBlockSize(token.marketCap) * 0.4)
                      }}
                    >
                      {showLabels && (
                        <>
                          <div className={`font-bold ${getTextColor(token.change)}`}>{token.symbol}</div>
                          <div className={`text-xs ${getTextColor(token.change)}`}>
                            {token.change >= 0 ? '+' : ''}{token.change}%
                          </div>
                          <div className={`text-xs opacity-75 ${getTextColor(token.change)}`}>
                            {formatMarketCap(token.marketCap)}
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Flat View */}
      {viewMode === 'flat' && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-4" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
          <div className="flex flex-wrap gap-2">
            {allTokens.map(token => (
              <div
                key={token.symbol}
                className={`${getColor(token.change)} rounded-lg p-3 cursor-pointer hover:opacity-80 transition-opacity`}
                style={{
                  width: Math.max(80, getBlockSize(token.marketCap) * 0.8),
                  height: Math.max(60, getBlockSize(token.marketCap) * 0.5)
                }}
              >
                {showLabels && (
                  <>
                    <div className={`font-bold ${getTextColor(token.change)}`}>{token.symbol}</div>
                    <div className={`text-xs ${getTextColor(token.change)}`}>
                      {token.change >= 0 ? '+' : ''}{token.change}%
                    </div>
                    <div className={`text-xs opacity-75 ${getTextColor(token.change)}`}>
                      {formatMarketCap(token.marketCap)}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Treemap View */}
      {viewMode === 'treemap' && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-4" style={{ transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
          <div className="grid grid-cols-8 gap-1 auto-rows-fr" style={{ gridAutoRows: 'minmax(60px, auto)' }}>
            {allTokens.slice(0, 50).map((token, idx) => {
              // Calculate grid span based on market cap
              const maxMcap = allTokens[0].marketCap
              const ratio = token.marketCap / maxMcap
              const colSpan = Math.max(1, Math.round(ratio * 4))
              const rowSpan = Math.max(1, Math.round(ratio * 2))

              return (
                <div
                  key={token.symbol}
                  className={`${getColor(token.change)} rounded-lg p-2 flex flex-col justify-center cursor-pointer hover:opacity-80 transition-opacity`}
                  style={{
                    gridColumn: `span ${colSpan}`,
                    gridRow: `span ${rowSpan}`
                  }}
                >
                  {showLabels && (
                    <div className="text-center">
                      <div className={`font-bold text-sm ${getTextColor(token.change)}`}>{token.symbol}</div>
                      <div className={`text-xs ${getTextColor(token.change)}`}>
                        {token.change >= 0 ? '+' : ''}{token.change}%
                      </div>
                      {(colSpan > 1 || rowSpan > 1) && (
                        <div className={`text-xs opacity-75 ${getTextColor(token.change)}`}>
                          {formatMarketCap(token.marketCap)}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 flex items-center justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-green-500 rounded" />
          <span className="text-gray-400">+10%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-green-500/60 rounded" />
          <span className="text-gray-400">+5%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-green-500/40 rounded" />
          <span className="text-gray-400">+2%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-gray-500 rounded" />
          <span className="text-gray-400">0%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-red-500/40 rounded" />
          <span className="text-gray-400">-2%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-red-500/60 rounded" />
          <span className="text-gray-400">-5%</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-4 h-4 bg-red-500 rounded" />
          <span className="text-gray-400">-10%</span>
        </div>
      </div>

      {/* Category Performance */}
      <div className="mt-6 bg-white/5 rounded-xl border border-white/10 p-6">
        <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-orange-400" />
          Category Performance ({timeframe})
        </h3>
        <div className="space-y-3">
          {Object.entries(MARKET_DATA).map(([category, tokens]) => {
            const avgChange = tokens.reduce((sum, t) => sum + t.change, 0) / tokens.length
            const totalMcap = tokens.reduce((sum, t) => sum + t.marketCap, 0)

            return (
              <div key={category} className="flex items-center gap-4">
                <span className="text-white font-medium w-24">{category}</span>
                <div className="flex-1 h-6 bg-white/10 rounded-full overflow-hidden relative">
                  {avgChange >= 0 ? (
                    <div
                      className="absolute left-1/2 h-full bg-green-500/70 rounded-r-full"
                      style={{ width: `${Math.min(avgChange * 5, 50)}%` }}
                    />
                  ) : (
                    <div
                      className="absolute right-1/2 h-full bg-red-500/70 rounded-l-full"
                      style={{ width: `${Math.min(Math.abs(avgChange) * 5, 50)}%` }}
                    />
                  )}
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-white/20" />
                </div>
                <span className={`w-16 text-right font-semibold ${avgChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {avgChange >= 0 ? '+' : ''}{avgChange.toFixed(2)}%
                </span>
                <span className="text-gray-400 text-sm w-20">{formatMarketCap(totalMcap)}</span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default MarketHeatMap
