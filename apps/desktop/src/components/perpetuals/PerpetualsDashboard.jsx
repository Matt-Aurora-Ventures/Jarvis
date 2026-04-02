import React, { useState, useMemo, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight, RefreshCw,
  DollarSign, Percent, Activity, BarChart3, Target, AlertTriangle,
  ChevronDown, ChevronUp, Zap, Flame, Scale, Clock, ExternalLink,
  Shield, Crosshair, Layers, ArrowLeftRight, Eye, Settings, Search,
  Filter, Star, StarOff, Bell, Calculator
} from 'lucide-react'

// Exchanges with perpetual markets
const EXCHANGES = {
  BINANCE: { name: 'Binance', color: '#F0B90B', fee: 0.02 },
  BYBIT: { name: 'Bybit', color: '#F7A600', fee: 0.02 },
  OKX: { name: 'OKX', color: '#FFFFFF', fee: 0.02 },
  DYDX: { name: 'dYdX', color: '#6966FF', fee: 0.025 },
  GMX: { name: 'GMX', color: '#4FA3FF', fee: 0.001 },
  HYPERLIQUID: { name: 'Hyperliquid', color: '#00D4AA', fee: 0.025 },
  VERTEX: { name: 'Vertex', color: '#FF6B35', fee: 0.02 },
  DRIFT: { name: 'Drift', color: '#E447FF', fee: 0.01 }
}

// Position side
const SIDE = {
  LONG: { label: 'Long', color: 'text-green-400', bg: 'bg-green-500/20' },
  SHORT: { label: 'Short', color: 'text-red-400', bg: 'bg-red-500/20' }
}

// Mock perpetual market data
const MOCK_MARKETS = [
  {
    symbol: 'BTC-PERP',
    baseAsset: 'BTC',
    price: 97542.50,
    indexPrice: 97538.20,
    markPrice: 97545.80,
    change24h: 2.85,
    high24h: 98200,
    low24h: 94850,
    volume24h: 12500000000,
    openInterest: 8200000000,
    fundingRate: 0.0082,
    nextFunding: '2h 15m',
    maxLeverage: 125,
    longShortRatio: 1.15,
    liquidations24h: { long: 45000000, short: 32000000 },
    topTraders: { longPercent: 52.3, shortPercent: 47.7 }
  },
  {
    symbol: 'ETH-PERP',
    baseAsset: 'ETH',
    price: 3458.75,
    indexPrice: 3456.50,
    markPrice: 3459.20,
    change24h: 1.92,
    high24h: 3520,
    low24h: 3380,
    volume24h: 6800000000,
    openInterest: 4500000000,
    fundingRate: 0.0065,
    nextFunding: '2h 15m',
    maxLeverage: 100,
    longShortRatio: 1.08,
    liquidations24h: { long: 28000000, short: 22000000 },
    topTraders: { longPercent: 51.8, shortPercent: 48.2 }
  },
  {
    symbol: 'SOL-PERP',
    baseAsset: 'SOL',
    price: 198.42,
    indexPrice: 198.35,
    markPrice: 198.48,
    change24h: 4.25,
    high24h: 205,
    low24h: 188,
    volume24h: 3200000000,
    openInterest: 1850000000,
    fundingRate: 0.0145,
    nextFunding: '2h 15m',
    maxLeverage: 75,
    longShortRatio: 1.32,
    liquidations24h: { long: 18000000, short: 12000000 },
    topTraders: { longPercent: 56.2, shortPercent: 43.8 }
  },
  {
    symbol: 'WIF-PERP',
    baseAsset: 'WIF',
    price: 2.48,
    indexPrice: 2.47,
    markPrice: 2.485,
    change24h: -3.15,
    high24h: 2.65,
    low24h: 2.38,
    volume24h: 890000000,
    openInterest: 420000000,
    fundingRate: 0.0185,
    nextFunding: '2h 15m',
    maxLeverage: 50,
    longShortRatio: 0.85,
    liquidations24h: { long: 8500000, short: 5200000 },
    topTraders: { longPercent: 45.5, shortPercent: 54.5 }
  },
  {
    symbol: 'PEPE-PERP',
    baseAsset: 'PEPE',
    price: 0.0000198,
    indexPrice: 0.0000197,
    markPrice: 0.00001982,
    change24h: 8.75,
    high24h: 0.0000215,
    low24h: 0.0000178,
    volume24h: 1200000000,
    openInterest: 580000000,
    fundingRate: 0.0285,
    nextFunding: '2h 15m',
    maxLeverage: 25,
    longShortRatio: 1.52,
    liquidations24h: { long: 12000000, short: 6500000 },
    topTraders: { longPercent: 58.8, shortPercent: 41.2 }
  },
  {
    symbol: 'ARB-PERP',
    baseAsset: 'ARB',
    price: 1.152,
    indexPrice: 1.150,
    markPrice: 1.153,
    change24h: -1.85,
    high24h: 1.20,
    low24h: 1.12,
    volume24h: 650000000,
    openInterest: 380000000,
    fundingRate: -0.0028,
    nextFunding: '2h 15m',
    maxLeverage: 50,
    longShortRatio: 0.92,
    liquidations24h: { long: 5200000, short: 4800000 },
    topTraders: { longPercent: 48.2, shortPercent: 51.8 }
  },
  {
    symbol: 'DOGE-PERP',
    baseAsset: 'DOGE',
    price: 0.385,
    indexPrice: 0.384,
    markPrice: 0.3855,
    change24h: -2.42,
    high24h: 0.405,
    low24h: 0.375,
    volume24h: 1800000000,
    openInterest: 920000000,
    fundingRate: -0.0052,
    nextFunding: '2h 15m',
    maxLeverage: 75,
    longShortRatio: 0.88,
    liquidations24h: { long: 9500000, short: 7200000 },
    topTraders: { longPercent: 46.5, shortPercent: 53.5 }
  },
  {
    symbol: 'AVAX-PERP',
    baseAsset: 'AVAX',
    price: 42.85,
    indexPrice: 42.80,
    markPrice: 42.88,
    change24h: 1.25,
    high24h: 44.20,
    low24h: 41.50,
    volume24h: 520000000,
    openInterest: 290000000,
    fundingRate: 0.0048,
    nextFunding: '2h 15m',
    maxLeverage: 50,
    longShortRatio: 1.05,
    liquidations24h: { long: 3200000, short: 2800000 },
    topTraders: { longPercent: 51.2, shortPercent: 48.8 }
  }
]

// Mock open positions
const MOCK_POSITIONS = [
  {
    id: '1',
    symbol: 'BTC-PERP',
    side: 'LONG',
    size: 0.5,
    leverage: 10,
    entryPrice: 95200,
    markPrice: 97542.50,
    liquidationPrice: 86500,
    margin: 4760,
    unrealizedPnl: 1171.25,
    unrealizedPnlPercent: 24.6,
    roi: 246,
    exchange: 'BINANCE'
  },
  {
    id: '2',
    symbol: 'ETH-PERP',
    side: 'LONG',
    size: 5,
    leverage: 15,
    entryPrice: 3380,
    markPrice: 3458.75,
    liquidationPrice: 3150,
    margin: 1127,
    unrealizedPnl: 393.75,
    unrealizedPnlPercent: 34.9,
    roi: 524,
    exchange: 'HYPERLIQUID'
  },
  {
    id: '3',
    symbol: 'SOL-PERP',
    side: 'SHORT',
    size: 50,
    leverage: 5,
    entryPrice: 205,
    markPrice: 198.42,
    liquidationPrice: 245,
    margin: 2050,
    unrealizedPnl: 329,
    unrealizedPnlPercent: 16.05,
    roi: 80.2,
    exchange: 'GMX'
  }
]

// Format large numbers
const formatValue = (value, decimals = 2) => {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(decimals)}B`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(decimals)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(decimals)}K`
  return `$${value.toFixed(decimals)}`
}

// Funding rate display
const FundingRate = ({ rate, showPredicted }) => {
  const isPositive = rate > 0
  return (
    <div className={`flex items-center gap-1 text-sm font-mono ${
      isPositive ? 'text-green-400' : rate < 0 ? 'text-red-400' : 'text-gray-400'
    }`}>
      {isPositive ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
      {isPositive ? '+' : ''}{(rate * 100).toFixed(4)}%
    </div>
  )
}

// Long/Short ratio bar
const LongShortBar = ({ ratio, topTraders }) => {
  const longPercent = topTraders ? topTraders.longPercent : (ratio / (ratio + 1)) * 100
  const shortPercent = 100 - longPercent

  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-green-400">Long {longPercent.toFixed(1)}%</span>
        <span className="text-red-400">Short {shortPercent.toFixed(1)}%</span>
      </div>
      <div className="h-2 flex rounded-full overflow-hidden">
        <div
          className="bg-green-500 transition-all duration-500"
          style={{ width: `${longPercent}%` }}
        />
        <div
          className="bg-red-500 transition-all duration-500"
          style={{ width: `${shortPercent}%` }}
        />
      </div>
    </div>
  )
}

// Market row component
const MarketRow = ({ market, watchlist, onToggleWatch, onSelect, expanded, onExpand }) => {
  const isWatched = watchlist.includes(market.symbol)
  const priceDecimals = market.price < 1 ? 8 : market.price < 100 ? 4 : 2

  return (
    <div className="border border-white/10 rounded-lg overflow-hidden">
      <div
        className="p-4 bg-white/5 hover:bg-white/[0.07] cursor-pointer transition-colors"
        onClick={() => onExpand(expanded ? null : market.symbol)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleWatch(market.symbol) }}
              className={`p-1 rounded transition-colors ${
                isWatched ? 'text-yellow-400' : 'text-gray-500 hover:text-gray-400'
              }`}
            >
              {isWatched ? <Star className="w-5 h-5 fill-current" /> : <StarOff className="w-5 h-5" />}
            </button>

            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white">{market.symbol}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">
                  {market.maxLeverage}x
                </span>
              </div>
              <div className="text-lg font-mono font-medium">
                ${market.price.toFixed(priceDecimals)}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            {/* 24h Change */}
            <div className="text-right">
              <div className="text-xs text-gray-500 mb-1">24h Change</div>
              <div className={`flex items-center gap-1 font-medium ${
                market.change24h > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {market.change24h > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                {market.change24h > 0 ? '+' : ''}{market.change24h.toFixed(2)}%
              </div>
            </div>

            {/* Funding Rate */}
            <div className="text-right min-w-[100px]">
              <div className="text-xs text-gray-500 mb-1">Funding ({market.nextFunding})</div>
              <FundingRate rate={market.fundingRate} />
            </div>

            {/* Open Interest */}
            <div className="text-right min-w-[90px]">
              <div className="text-xs text-gray-500 mb-1">Open Interest</div>
              <div className="font-medium">{formatValue(market.openInterest, 1)}</div>
            </div>

            {/* Volume */}
            <div className="text-right min-w-[90px]">
              <div className="text-xs text-gray-500 mb-1">24h Volume</div>
              <div className="font-medium">{formatValue(market.volume24h, 1)}</div>
            </div>

            <div className="w-6">
              {expanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </div>
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="p-4 bg-white/[0.02] border-t border-white/10">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Mark Price</div>
              <div className="font-mono">${market.markPrice.toFixed(priceDecimals)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Index Price</div>
              <div className="font-mono">${market.indexPrice.toFixed(priceDecimals)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">24h High</div>
              <div className="font-mono text-green-400">${market.high24h.toFixed(priceDecimals)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">24h Low</div>
              <div className="font-mono text-red-400">${market.low24h.toFixed(priceDecimals)}</div>
            </div>
          </div>

          {/* Long/Short ratio */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-2">Long/Short Ratio ({market.longShortRatio.toFixed(2)})</div>
              <LongShortBar ratio={market.longShortRatio} />
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-2">Top Traders Position</div>
              <LongShortBar topTraders={market.topTraders} />
            </div>
          </div>

          {/* Liquidations */}
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-2">24h Liquidations</div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-green-400" />
                <span className="text-green-400">Long:</span>
                <span className="font-mono">{formatValue(market.liquidations24h.long)}</span>
              </div>
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-red-400" />
                <span className="text-red-400">Short:</span>
                <span className="font-mono">{formatValue(market.liquidations24h.short)}</span>
              </div>
            </div>
          </div>

          {/* Quick trade buttons */}
          <div className="flex gap-3 mt-4">
            <button className="flex-1 py-2 bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Long
            </button>
            <button className="flex-1 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
              <TrendingDown className="w-4 h-4" />
              Short
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// Position card
const PositionCard = ({ position, onClose }) => {
  const isProfitable = position.unrealizedPnl > 0

  return (
    <div className={`bg-white/5 rounded-lg p-4 border ${
      isProfitable ? 'border-green-500/30' : 'border-red-500/30'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-bold">{position.symbol}</span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${SIDE[position.side].bg} ${SIDE[position.side].color}`}>
            {SIDE[position.side].label} {position.leverage}x
          </span>
        </div>
        <span className="text-xs px-2 py-0.5 bg-white/10 rounded text-gray-400">
          {EXCHANGES[position.exchange].name}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3 text-sm">
        <div>
          <div className="text-xs text-gray-500">Size</div>
          <div className="font-mono">{position.size}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Entry</div>
          <div className="font-mono">${position.entryPrice.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Mark</div>
          <div className="font-mono">${position.markPrice.toLocaleString()}</div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3 text-sm">
        <div>
          <div className="text-xs text-gray-500">Margin</div>
          <div className="font-mono">${position.margin.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">Liq. Price</div>
          <div className="font-mono text-orange-400">${position.liquidationPrice.toLocaleString()}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">ROI</div>
          <div className={`font-mono ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {isProfitable ? '+' : ''}{position.roi.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className={`p-3 rounded-lg ${isProfitable ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Unrealized PnL</span>
          <div className={`text-lg font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {isProfitable ? '+' : ''}${position.unrealizedPnl.toFixed(2)}
            <span className="text-sm ml-1">
              ({isProfitable ? '+' : ''}{position.unrealizedPnlPercent.toFixed(1)}%)
            </span>
          </div>
        </div>
      </div>

      <div className="flex gap-2 mt-3">
        <button className="flex-1 py-1.5 bg-white/5 hover:bg-white/10 rounded text-sm transition-colors">
          TP/SL
        </button>
        <button
          onClick={() => onClose(position.id)}
          className="flex-1 py-1.5 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded text-sm transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  )
}

// Overview stats
const OverviewStats = ({ markets, positions }) => {
  const stats = useMemo(() => {
    const totalOI = markets.reduce((sum, m) => sum + m.openInterest, 0)
    const totalVolume = markets.reduce((sum, m) => sum + m.volume24h, 0)
    const totalLiqLong = markets.reduce((sum, m) => sum + m.liquidations24h.long, 0)
    const totalLiqShort = markets.reduce((sum, m) => sum + m.liquidations24h.short, 0)

    const totalPnl = positions.reduce((sum, p) => sum + p.unrealizedPnl, 0)
    const totalMargin = positions.reduce((sum, p) => sum + p.margin, 0)

    return { totalOI, totalVolume, totalLiqLong, totalLiqShort, totalPnl, totalMargin }
  }, [markets, positions])

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Layers className="w-4 h-4" />
          Total Open Interest
        </div>
        <div className="text-2xl font-bold">{formatValue(stats.totalOI, 1)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          24h Volume
        </div>
        <div className="text-2xl font-bold">{formatValue(stats.totalVolume, 1)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Flame className="w-4 h-4 text-orange-400" />
          24h Liquidations
        </div>
        <div className="text-2xl font-bold">{formatValue(stats.totalLiqLong + stats.totalLiqShort, 1)}</div>
        <div className="text-xs text-gray-500 mt-1">
          <span className="text-green-400">L: {formatValue(stats.totalLiqLong)}</span>
          {' / '}
          <span className="text-red-400">S: {formatValue(stats.totalLiqShort)}</span>
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <DollarSign className="w-4 h-4" />
          Your Unrealized PnL
        </div>
        <div className={`text-2xl font-bold ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {stats.totalPnl >= 0 ? '+' : ''}${stats.totalPnl.toFixed(2)}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          Margin: ${stats.totalMargin.toLocaleString()}
        </div>
      </div>
    </div>
  )
}

// Funding heatmap
const FundingHeatmap = ({ markets }) => {
  const sorted = useMemo(() =>
    [...markets].sort((a, b) => b.fundingRate - a.fundingRate),
    [markets]
  )

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Percent className="w-4 h-4" />
        Funding Rate Heatmap
      </h3>

      <div className="space-y-2">
        {sorted.map(market => {
          const intensity = Math.min(Math.abs(market.fundingRate) * 2000, 100)
          const isPositive = market.fundingRate > 0

          return (
            <div key={market.symbol} className="flex items-center gap-3">
              <span className="w-20 text-sm font-medium">{market.baseAsset}</span>
              <div className="flex-1 h-6 bg-white/5 rounded overflow-hidden relative">
                <div
                  className={`h-full transition-all duration-500 ${
                    isPositive ? 'bg-green-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${intensity}%`, opacity: 0.6 }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-xs font-mono">
                  {market.fundingRate > 0 ? '+' : ''}{(market.fundingRate * 100).toFixed(4)}%
                </span>
              </div>
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-red-500" />
          Shorts pay Longs
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded bg-green-500" />
          Longs pay Shorts
        </div>
      </div>
    </div>
  )
}

// Main component
export const PerpetualsDashboard = () => {
  const [markets] = useState(MOCK_MARKETS)
  const [positions] = useState(MOCK_POSITIONS)
  const [searchQuery, setSearchQuery] = useState('')
  const [watchlist, setWatchlist] = useState(['BTC-PERP', 'ETH-PERP', 'SOL-PERP'])
  const [showWatchlistOnly, setShowWatchlistOnly] = useState(false)
  const [expandedMarket, setExpandedMarket] = useState(null)
  const [sortBy, setSortBy] = useState('volume')
  const [activeTab, setActiveTab] = useState('markets')
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1500)
  }, [])

  const toggleWatchlist = useCallback((symbol) => {
    setWatchlist(prev =>
      prev.includes(symbol)
        ? prev.filter(s => s !== symbol)
        : [...prev, symbol]
    )
  }, [])

  const filteredMarkets = useMemo(() => {
    let result = [...markets]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(m =>
        m.symbol.toLowerCase().includes(query) ||
        m.baseAsset.toLowerCase().includes(query)
      )
    }

    if (showWatchlistOnly) {
      result = result.filter(m => watchlist.includes(m.symbol))
    }

    // Sort
    switch (sortBy) {
      case 'volume':
        result.sort((a, b) => b.volume24h - a.volume24h)
        break
      case 'oi':
        result.sort((a, b) => b.openInterest - a.openInterest)
        break
      case 'funding':
        result.sort((a, b) => Math.abs(b.fundingRate) - Math.abs(a.fundingRate))
        break
      case 'change':
        result.sort((a, b) => b.change24h - a.change24h)
        break
    }

    return result
  }, [markets, searchQuery, showWatchlistOnly, watchlist, sortBy])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Scale className="w-7 h-7 text-purple-400" />
              Perpetuals Dashboard
            </h1>
            <p className="text-gray-400 mt-1">Track perpetual futures markets and manage positions</p>
          </div>

          <div className="flex items-center gap-3">
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

        {/* Overview Stats */}
        <OverviewStats markets={markets} positions={positions} />

        {/* Tabs */}
        <div className="flex gap-4 mb-6 border-b border-white/10">
          {['markets', 'positions'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 px-1 text-sm font-medium transition-colors border-b-2 ${
                activeTab === tab
                  ? 'text-white border-purple-500'
                  : 'text-gray-400 border-transparent hover:text-white'
              }`}
            >
              {tab === 'markets' ? 'Markets' : `Positions (${positions.length})`}
            </button>
          ))}
        </div>

        {activeTab === 'markets' ? (
          <>
            {/* Filters */}
            <div className="flex items-center gap-4 mb-6">
              <div className="relative flex-1 max-w-md">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search markets..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50"
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
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
              >
                <option value="volume">Volume</option>
                <option value="oi">Open Interest</option>
                <option value="funding">Funding Rate</option>
                <option value="change">24h Change</option>
              </select>
            </div>

            {/* Main content grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Markets list */}
              <div className="lg:col-span-2 space-y-3">
                {filteredMarkets.map(market => (
                  <MarketRow
                    key={market.symbol}
                    market={market}
                    watchlist={watchlist}
                    onToggleWatch={toggleWatchlist}
                    expanded={expandedMarket === market.symbol}
                    onExpand={setExpandedMarket}
                  />
                ))}

                {filteredMarkets.length === 0 && (
                  <div className="text-center py-12 bg-white/5 rounded-xl border border-white/10">
                    <Scale className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                    <p className="text-gray-400">No markets match your filters</p>
                  </div>
                )}
              </div>

              {/* Sidebar */}
              <div className="space-y-6">
                <FundingHeatmap markets={markets} />
              </div>
            </div>
          </>
        ) : (
          /* Positions tab */
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {positions.map(position => (
              <PositionCard
                key={position.id}
                position={position}
                onClose={(id) => console.log('Close position:', id)}
              />
            ))}

            {positions.length === 0 && (
              <div className="col-span-full text-center py-12 bg-white/5 rounded-xl border border-white/10">
                <Crosshair className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 mb-4">No open positions</p>
                <button
                  onClick={() => setActiveTab('markets')}
                  className="px-4 py-2 bg-purple-500 hover:bg-purple-600 rounded-lg font-medium transition-colors"
                >
                  Browse Markets
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default PerpetualsDashboard
