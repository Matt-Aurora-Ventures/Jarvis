import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react'
import {
  Grid,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  RefreshCw,
  Filter,
  ChevronDown,
  ChevronUp,
  BarChart3,
  PieChart,
  Activity,
  Layers,
  Eye,
  Info,
  X,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  ExternalLink
} from 'lucide-react'

// Categories/Sectors
const SECTORS = {
  ALL: { label: 'All', color: '#6366f1' },
  DEFI: { label: 'DeFi', color: '#8b5cf6' },
  MEME: { label: 'Meme', color: '#eab308' },
  NFT: { label: 'NFT', color: '#ec4899' },
  GAMING: { label: 'Gaming', color: '#f97316' },
  AI: { label: 'AI', color: '#06b6d4' },
  INFRASTRUCTURE: { label: 'Infra', color: '#3b82f6' },
  STABLECOIN: { label: 'Stable', color: '#22c55e' },
  EXCHANGE: { label: 'Exchange', color: '#ef4444' },
  LAYER1: { label: 'L1', color: '#a855f7' },
  LAYER2: { label: 'L2', color: '#14b8a6' },
}

// Time periods
const TIME_PERIODS = {
  '1H': '1 Hour',
  '24H': '24 Hours',
  '7D': '7 Days',
  '30D': '30 Days',
}

// Helper functions
function formatNumber(num, decimals = 2) {
  if (num >= 1000000000) return `$${(num / 1000000000).toFixed(decimals)}B`
  if (num >= 1000000) return `$${(num / 1000000).toFixed(decimals)}M`
  if (num >= 1000) return `$${(num / 1000).toFixed(decimals)}K`
  return `$${num.toFixed(decimals)}`
}

function formatPercent(num) {
  const sign = num >= 0 ? '+' : ''
  return `${sign}${num.toFixed(2)}%`
}

// Get color based on percentage change
function getHeatmapColor(change, intensity = 1) {
  const absChange = Math.abs(change)
  const opacity = Math.min(absChange / 10, 1) * intensity

  if (change >= 0) {
    // Green shades for positive
    if (change > 20) return `rgba(34, 197, 94, ${Math.min(opacity + 0.3, 1)})`
    if (change > 10) return `rgba(34, 197, 94, ${Math.min(opacity + 0.2, 1)})`
    if (change > 5) return `rgba(34, 197, 94, ${Math.min(opacity + 0.1, 1)})`
    return `rgba(34, 197, 94, ${opacity})`
  } else {
    // Red shades for negative
    if (change < -20) return `rgba(239, 68, 68, ${Math.min(opacity + 0.3, 1)})`
    if (change < -10) return `rgba(239, 68, 68, ${Math.min(opacity + 0.2, 1)})`
    if (change < -5) return `rgba(239, 68, 68, ${Math.min(opacity + 0.1, 1)})`
    return `rgba(239, 68, 68, ${opacity})`
  }
}

// Treemap cell component
function HeatmapCell({ token, width, height, onClick, isSelected }) {
  const [isHovered, setIsHovered] = useState(false)
  const change = token.priceChange || 0
  const bgColor = getHeatmapColor(change)

  // Only show content if cell is big enough
  const showSymbol = width > 40 && height > 30
  const showPercent = width > 60 && height > 45
  const showPrice = width > 80 && height > 60

  return (
    <div
      className={`absolute transition-all duration-200 cursor-pointer ${
        isSelected ? 'ring-2 ring-white ring-offset-1 ring-offset-gray-900 z-10' : ''
      }`}
      style={{
        width: `${width}px`,
        height: `${height}px`,
        backgroundColor: bgColor,
        left: token._x,
        top: token._y,
      }}
      onClick={() => onClick?.(token)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className={`w-full h-full p-1 flex flex-col items-center justify-center text-center overflow-hidden ${
        isHovered ? 'bg-black/20' : ''
      }`}>
        {showSymbol && (
          <div className="font-bold text-white text-shadow truncate" style={{
            fontSize: Math.max(10, Math.min(width / 5, 16)),
            textShadow: '0 1px 2px rgba(0,0,0,0.5)'
          }}>
            {token.symbol}
          </div>
        )}
        {showPercent && (
          <div className={`font-medium ${change >= 0 ? 'text-white' : 'text-white'}`} style={{
            fontSize: Math.max(8, Math.min(width / 6, 14)),
            textShadow: '0 1px 2px rgba(0,0,0,0.5)'
          }}>
            {formatPercent(change)}
          </div>
        )}
        {showPrice && token.price && (
          <div className="text-white/80 truncate" style={{
            fontSize: Math.max(7, Math.min(width / 8, 11)),
            textShadow: '0 1px 2px rgba(0,0,0,0.5)'
          }}>
            ${token.price < 0.01 ? token.price.toFixed(6) : token.price.toFixed(2)}
          </div>
        )}
      </div>

      {/* Hover tooltip */}
      {isHovered && !isSelected && (
        <div className="absolute z-20 bottom-full left-1/2 -translate-x-1/2 mb-2 p-2 bg-gray-900 border border-gray-700 rounded-lg shadow-xl whitespace-nowrap">
          <div className="font-bold">{token.name} ({token.symbol})</div>
          <div className="text-sm text-gray-400">{formatNumber(token.marketCap)} MC</div>
          <div className={`text-sm ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatPercent(change)}
          </div>
        </div>
      )}
    </div>
  )
}

// Token detail panel
function TokenDetailPanel({ token, onClose }) {
  if (!token) return null

  const change = token.priceChange || 0

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-4">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          {token.logo ? (
            <img src={token.logo} alt={token.symbol} className="w-10 h-10 rounded-lg" />
          ) : (
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center font-bold">
              {token.symbol?.[0]}
            </div>
          )}
          <div>
            <h3 className="font-bold text-lg">{token.name}</h3>
            <span className="text-gray-400">${token.symbol}</span>
          </div>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Price</div>
          <div className="font-bold">${token.price?.toFixed(token.price < 0.01 ? 8 : 2)}</div>
          <div className={`text-sm flex items-center gap-1 ${change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {change >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
            {formatPercent(change)}
          </div>
        </div>
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Market Cap</div>
          <div className="font-bold">{formatNumber(token.marketCap)}</div>
          <div className="text-xs text-gray-500">Rank #{token.rank || 'N/A'}</div>
        </div>
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Volume 24h</div>
          <div className="font-bold">{formatNumber(token.volume24h || 0)}</div>
        </div>
        <div className="bg-gray-900 rounded-lg p-3">
          <div className="text-xs text-gray-500 mb-1">Sector</div>
          <div className="font-bold">{SECTORS[token.sector]?.label || token.sector}</div>
        </div>
      </div>

      {/* Price changes by period */}
      <div className="mb-4">
        <div className="text-sm text-gray-400 mb-2">Price Changes</div>
        <div className="grid grid-cols-4 gap-2">
          {[
            { period: '1H', value: token.change1h },
            { period: '24H', value: token.change24h },
            { period: '7D', value: token.change7d },
            { period: '30D', value: token.change30d },
          ].map(({ period, value }) => (
            <div key={period} className="bg-gray-900 rounded p-2 text-center">
              <div className="text-xs text-gray-500">{period}</div>
              <div className={`font-medium ${(value || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {value ? formatPercent(value) : 'N/A'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* External links */}
      <div className="flex gap-2">
        <a
          href={`https://dexscreener.com/solana/${token.address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center justify-center gap-1 text-sm"
        >
          Chart <ExternalLink className="w-3 h-3" />
        </a>
        <a
          href={`https://birdeye.so/token/${token.address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center justify-center gap-1 text-sm"
        >
          Birdeye <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  )
}

// Market summary stats
function MarketStats({ tokens, period }) {
  const stats = useMemo(() => {
    if (!tokens.length) return null

    const priceChangeKey = period === '1H' ? 'change1h' :
                          period === '7D' ? 'change7d' :
                          period === '30D' ? 'change30d' : 'priceChange'

    const gainers = tokens.filter(t => (t[priceChangeKey] || 0) > 0)
    const losers = tokens.filter(t => (t[priceChangeKey] || 0) < 0)
    const totalMcap = tokens.reduce((sum, t) => sum + (t.marketCap || 0), 0)
    const avgChange = tokens.reduce((sum, t) => sum + (t[priceChangeKey] || 0), 0) / tokens.length

    const topGainer = [...tokens].sort((a, b) => (b[priceChangeKey] || 0) - (a[priceChangeKey] || 0))[0]
    const topLoser = [...tokens].sort((a, b) => (a[priceChangeKey] || 0) - (b[priceChangeKey] || 0))[0]

    return {
      total: tokens.length,
      gainers: gainers.length,
      losers: losers.length,
      totalMcap,
      avgChange,
      topGainer,
      topLoser,
      neutral: tokens.length - gainers.length - losers.length,
    }
  }, [tokens, period])

  if (!stats) return null

  return (
    <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total Tokens</div>
        <div className="text-2xl font-bold">{stats.total}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Gainers</div>
        <div className="text-2xl font-bold text-green-400">{stats.gainers}</div>
        <div className="text-xs text-gray-500">{((stats.gainers / stats.total) * 100).toFixed(0)}%</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Losers</div>
        <div className="text-2xl font-bold text-red-400">{stats.losers}</div>
        <div className="text-xs text-gray-500">{((stats.losers / stats.total) * 100).toFixed(0)}%</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total MCap</div>
        <div className="text-2xl font-bold">{formatNumber(stats.totalMcap)}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Top Gainer</div>
        <div className="font-bold text-green-400">{stats.topGainer?.symbol}</div>
        <div className="text-sm text-green-400">{formatPercent(stats.topGainer?.priceChange || 0)}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Top Loser</div>
        <div className="font-bold text-red-400">{stats.topLoser?.symbol}</div>
        <div className="text-sm text-red-400">{formatPercent(stats.topLoser?.priceChange || 0)}</div>
      </div>
    </div>
  )
}

// Simple squarified treemap layout
function squarify(tokens, width, height) {
  if (!tokens.length || !width || !height) return []

  const totalValue = tokens.reduce((sum, t) => sum + (t.marketCap || 0), 0)
  if (totalValue === 0) return []

  // Normalize values to area
  const normalizedTokens = tokens.map(t => ({
    ...t,
    _area: ((t.marketCap || 0) / totalValue) * width * height,
  }))

  // Sort by area descending
  normalizedTokens.sort((a, b) => b._area - a._area)

  // Simple row-based layout
  const result = []
  let currentY = 0
  let remainingTokens = [...normalizedTokens]

  while (remainingTokens.length > 0 && currentY < height) {
    const remainingHeight = height - currentY
    const rowTokens = []
    let rowArea = 0
    const targetRowArea = width * Math.min(remainingHeight, height / 3)

    // Fill row
    while (remainingTokens.length > 0 && rowArea < targetRowArea) {
      const token = remainingTokens.shift()
      rowTokens.push(token)
      rowArea += token._area
    }

    if (rowTokens.length === 0) break

    // Calculate row height
    const rowHeight = Math.min(rowArea / width, remainingHeight)
    let currentX = 0

    // Layout tokens in row
    for (const token of rowTokens) {
      const tokenWidth = token._area / rowHeight
      result.push({
        ...token,
        _x: currentX,
        _y: currentY,
        _width: Math.max(tokenWidth, 1),
        _height: Math.max(rowHeight, 1),
      })
      currentX += tokenWidth
    }

    currentY += rowHeight
  }

  return result
}

// Legend component
function HeatmapLegend() {
  const legendItems = [
    { label: '>20%', color: getHeatmapColor(25) },
    { label: '10-20%', color: getHeatmapColor(15) },
    { label: '5-10%', color: getHeatmapColor(7) },
    { label: '0-5%', color: getHeatmapColor(2) },
    { label: '0 to -5%', color: getHeatmapColor(-2) },
    { label: '-5 to -10%', color: getHeatmapColor(-7) },
    { label: '-10 to -20%', color: getHeatmapColor(-15) },
    { label: '<-20%', color: getHeatmapColor(-25) },
  ]

  return (
    <div className="flex items-center gap-2 text-xs">
      {legendItems.map((item, i) => (
        <div key={i} className="flex items-center gap-1">
          <div
            className="w-4 h-3 rounded"
            style={{ backgroundColor: item.color }}
          />
          <span className="text-gray-400">{item.label}</span>
        </div>
      ))}
    </div>
  )
}

// Main Market Heatmap Component
export function MarketHeatmap({
  tokens = [],
  onRefresh,
  isLoading = false,
}) {
  const containerRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const [selectedSector, setSelectedSector] = useState('ALL')
  const [timePeriod, setTimePeriod] = useState('24H')
  const [selectedToken, setSelectedToken] = useState(null)
  const [minMarketCap, setMinMarketCap] = useState(0)

  // Update dimensions on resize
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        setDimensions({ width: rect.width, height: 500 })
      }
    }

    updateDimensions()
    window.addEventListener('resize', updateDimensions)
    return () => window.removeEventListener('resize', updateDimensions)
  }, [])

  // Filter tokens
  const filteredTokens = useMemo(() => {
    let result = [...tokens]

    // Sector filter
    if (selectedSector !== 'ALL') {
      result = result.filter(t => t.sector === selectedSector)
    }

    // Market cap filter
    if (minMarketCap > 0) {
      result = result.filter(t => (t.marketCap || 0) >= minMarketCap)
    }

    // Update price change based on selected period
    result = result.map(t => ({
      ...t,
      priceChange: timePeriod === '1H' ? t.change1h :
                   timePeriod === '7D' ? t.change7d :
                   timePeriod === '30D' ? t.change30d : t.change24h,
    }))

    return result
  }, [tokens, selectedSector, minMarketCap, timePeriod])

  // Calculate layout
  const layoutTokens = useMemo(() => {
    return squarify(filteredTokens, dimensions.width, dimensions.height)
  }, [filteredTokens, dimensions])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Grid className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Market Heatmap</h1>
            <p className="text-sm text-gray-400">Visualize market performance at a glance</p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <MarketStats tokens={filteredTokens} period={timePeriod} />

      {/* Controls */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-wrap items-center gap-4">
          {/* Time Period */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Period:</span>
            <div className="flex bg-gray-700 rounded-lg p-1">
              {Object.entries(TIME_PERIODS).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTimePeriod(key)}
                  className={`px-3 py-1 rounded text-sm ${
                    timePeriod === key
                      ? 'bg-blue-500 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {key}
                </button>
              ))}
            </div>
          </div>

          {/* Sector Filter */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Sector:</span>
            <select
              value={selectedSector}
              onChange={e => setSelectedSector(e.target.value)}
              className="px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-sm"
            >
              {Object.entries(SECTORS).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>

          {/* Min Market Cap */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Min MCap:</span>
            <select
              value={minMarketCap}
              onChange={e => setMinMarketCap(Number(e.target.value))}
              className="px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-sm"
            >
              <option value={0}>All</option>
              <option value={100000}>$100K+</option>
              <option value={1000000}>$1M+</option>
              <option value={10000000}>$10M+</option>
              <option value={100000000}>$100M+</option>
              <option value={1000000000}>$1B+</option>
            </select>
          </div>

          <div className="flex-1" />

          {/* Legend */}
          <HeatmapLegend />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex gap-4">
        {/* Heatmap */}
        <div className="flex-1">
          <div
            ref={containerRef}
            className="relative bg-gray-900 rounded-xl border border-gray-700 overflow-hidden"
            style={{ height: '500px' }}
          >
            {layoutTokens.map((token, i) => (
              <HeatmapCell
                key={token.address || i}
                token={token}
                width={token._width}
                height={token._height}
                onClick={setSelectedToken}
                isSelected={selectedToken?.address === token.address}
              />
            ))}

            {layoutTokens.length === 0 && (
              <div className="absolute inset-0 flex items-center justify-center text-gray-500">
                <div className="text-center">
                  <Grid className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No tokens to display</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Detail Panel */}
        {selectedToken && (
          <div className="w-80 flex-shrink-0">
            <TokenDetailPanel
              token={selectedToken}
              onClose={() => setSelectedToken(null)}
            />
          </div>
        )}
      </div>

      {/* Top Movers */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Top Gainers */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            Top Gainers
          </h3>
          <div className="space-y-2">
            {filteredTokens
              .sort((a, b) => (b.priceChange || 0) - (a.priceChange || 0))
              .slice(0, 5)
              .map((token, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 bg-gray-900 rounded-lg cursor-pointer hover:bg-gray-700"
                  onClick={() => setSelectedToken(token)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 w-4">{i + 1}.</span>
                    <span className="font-medium">{token.symbol}</span>
                  </div>
                  <span className="text-green-400 font-medium">
                    {formatPercent(token.priceChange || 0)}
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* Top Losers */}
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <h3 className="font-semibold mb-3 flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-red-400" />
            Top Losers
          </h3>
          <div className="space-y-2">
            {filteredTokens
              .sort((a, b) => (a.priceChange || 0) - (b.priceChange || 0))
              .slice(0, 5)
              .map((token, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 bg-gray-900 rounded-lg cursor-pointer hover:bg-gray-700"
                  onClick={() => setSelectedToken(token)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-gray-500 w-4">{i + 1}.</span>
                    <span className="font-medium">{token.symbol}</span>
                  </div>
                  <span className="text-red-400 font-medium">
                    {formatPercent(token.priceChange || 0)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MarketHeatmap
