import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Filter, Search, TrendingUp, TrendingDown, BarChart3, Activity,
  Star, StarOff, ChevronDown, ChevronUp, RefreshCw, Settings,
  Save, Trash2, Plus, X, ArrowUpRight, ArrowDownRight, Zap,
  DollarSign, Percent, Clock, Volume2, AlertTriangle, Eye
} from 'lucide-react'

// Screening criteria types
const CRITERIA_TYPES = {
  PRICE_CHANGE_24H: { label: 'Price Change (24h)', unit: '%', min: -100, max: 1000 },
  PRICE_CHANGE_7D: { label: 'Price Change (7d)', unit: '%', min: -100, max: 1000 },
  VOLUME_24H: { label: 'Volume (24h)', unit: '$', min: 0, max: 1e12 },
  MARKET_CAP: { label: 'Market Cap', unit: '$', min: 0, max: 1e12 },
  VOLUME_MCAP_RATIO: { label: 'Vol/MCap Ratio', unit: '%', min: 0, max: 1000 },
  RSI_14: { label: 'RSI (14)', unit: '', min: 0, max: 100 },
  ATH_DISTANCE: { label: 'Distance from ATH', unit: '%', min: -100, max: 0 },
  ATL_DISTANCE: { label: 'Distance from ATL', unit: '%', min: 0, max: 10000 },
  VOLATILITY: { label: 'Volatility (30d)', unit: '%', min: 0, max: 500 },
  CIRCULATING_SUPPLY: { label: 'Circulating Supply %', unit: '%', min: 0, max: 100 }
}

// Operators
const OPERATORS = {
  GT: { label: '>', name: 'Greater than' },
  GTE: { label: '>=', name: 'Greater or equal' },
  LT: { label: '<', name: 'Less than' },
  LTE: { label: '<=', name: 'Less or equal' },
  EQ: { label: '=', name: 'Equal to' },
  BETWEEN: { label: 'between', name: 'Between' }
}

// Categories
const CATEGORIES = ['All', 'Layer 1', 'Layer 2', 'DeFi', 'Gaming', 'AI', 'Meme', 'RWA', 'Storage', 'Oracle']

// Preset screens
const PRESET_SCREENS = {
  TOP_GAINERS: {
    name: 'Top Gainers',
    criteria: [{ type: 'PRICE_CHANGE_24H', operator: 'GT', value: 10 }]
  },
  TOP_LOSERS: {
    name: 'Top Losers',
    criteria: [{ type: 'PRICE_CHANGE_24H', operator: 'LT', value: -10 }]
  },
  HIGH_VOLUME: {
    name: 'High Volume',
    criteria: [{ type: 'VOLUME_24H', operator: 'GT', value: 100000000 }]
  },
  OVERSOLD: {
    name: 'Oversold (RSI)',
    criteria: [{ type: 'RSI_14', operator: 'LT', value: 30 }]
  },
  OVERBOUGHT: {
    name: 'Overbought (RSI)',
    criteria: [{ type: 'RSI_14', operator: 'GT', value: 70 }]
  },
  NEAR_ATH: {
    name: 'Near ATH',
    criteria: [{ type: 'ATH_DISTANCE', operator: 'GT', value: -10 }]
  },
  ACCUMULATION: {
    name: 'Accumulation Zone',
    criteria: [
      { type: 'ATH_DISTANCE', operator: 'LT', value: -50 },
      { type: 'RSI_14', operator: 'LT', value: 40 }
    ]
  }
}

// Generate mock token data
const generateTokens = () => {
  const tokens = [
    { symbol: 'BTC', name: 'Bitcoin', category: 'Layer 1' },
    { symbol: 'ETH', name: 'Ethereum', category: 'Layer 1' },
    { symbol: 'SOL', name: 'Solana', category: 'Layer 1' },
    { symbol: 'AVAX', name: 'Avalanche', category: 'Layer 1' },
    { symbol: 'ADA', name: 'Cardano', category: 'Layer 1' },
    { symbol: 'DOT', name: 'Polkadot', category: 'Layer 1' },
    { symbol: 'NEAR', name: 'Near Protocol', category: 'Layer 1' },
    { symbol: 'ARB', name: 'Arbitrum', category: 'Layer 2' },
    { symbol: 'OP', name: 'Optimism', category: 'Layer 2' },
    { symbol: 'MATIC', name: 'Polygon', category: 'Layer 2' },
    { symbol: 'BASE', name: 'Base', category: 'Layer 2' },
    { symbol: 'UNI', name: 'Uniswap', category: 'DeFi' },
    { symbol: 'AAVE', name: 'Aave', category: 'DeFi' },
    { symbol: 'LINK', name: 'Chainlink', category: 'Oracle' },
    { symbol: 'MKR', name: 'Maker', category: 'DeFi' },
    { symbol: 'CRV', name: 'Curve', category: 'DeFi' },
    { symbol: 'LDO', name: 'Lido', category: 'DeFi' },
    { symbol: 'INJ', name: 'Injective', category: 'DeFi' },
    { symbol: 'DYDX', name: 'dYdX', category: 'DeFi' },
    { symbol: 'GMX', name: 'GMX', category: 'DeFi' },
    { symbol: 'FET', name: 'Fetch.ai', category: 'AI' },
    { symbol: 'RNDR', name: 'Render', category: 'AI' },
    { symbol: 'OCEAN', name: 'Ocean Protocol', category: 'AI' },
    { symbol: 'TAO', name: 'Bittensor', category: 'AI' },
    { symbol: 'IMX', name: 'Immutable X', category: 'Gaming' },
    { symbol: 'GALA', name: 'Gala', category: 'Gaming' },
    { symbol: 'AXS', name: 'Axie Infinity', category: 'Gaming' },
    { symbol: 'SAND', name: 'Sandbox', category: 'Gaming' },
    { symbol: 'DOGE', name: 'Dogecoin', category: 'Meme' },
    { symbol: 'SHIB', name: 'Shiba Inu', category: 'Meme' },
    { symbol: 'PEPE', name: 'Pepe', category: 'Meme' },
    { symbol: 'BONK', name: 'Bonk', category: 'Meme' },
    { symbol: 'FIL', name: 'Filecoin', category: 'Storage' },
    { symbol: 'AR', name: 'Arweave', category: 'Storage' },
    { symbol: 'ONDO', name: 'Ondo Finance', category: 'RWA' },
    { symbol: 'PENDLE', name: 'Pendle', category: 'RWA' }
  ]

  return tokens.map(t => {
    const price = t.symbol === 'BTC' ? 65000 + Math.random() * 5000 :
                  t.symbol === 'ETH' ? 3500 + Math.random() * 500 :
                  t.symbol === 'SOL' ? 150 + Math.random() * 30 :
                  Math.random() * 100 + 0.1

    const marketCap = t.symbol === 'BTC' ? 1200000000000 + Math.random() * 100000000000 :
                      t.symbol === 'ETH' ? 400000000000 + Math.random() * 50000000000 :
                      Math.random() * 20000000000 + 100000000

    const volume24h = marketCap * (0.02 + Math.random() * 0.1)

    return {
      ...t,
      price,
      priceChange24h: (Math.random() - 0.5) * 30,
      priceChange7d: (Math.random() - 0.5) * 50,
      marketCap,
      volume24h,
      volumeMcapRatio: (volume24h / marketCap) * 100,
      rsi14: Math.random() * 100,
      athDistance: -Math.random() * 80,
      atlDistance: Math.random() * 5000 + 100,
      volatility: Math.random() * 100 + 10,
      circulatingSupply: Math.random() * 100,
      rank: 0,
      starred: false
    }
  }).sort((a, b) => b.marketCap - a.marketCap)
    .map((t, idx) => ({ ...t, rank: idx + 1 }))
}

export function MarketScreener() {
  const [tokens, setTokens] = useState([])
  const [criteria, setCriteria] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [searchQuery, setSearchQuery] = useState('')
  const [sortBy, setSortBy] = useState('marketCap')
  const [sortOrder, setSortOrder] = useState('desc')
  const [selectedPreset, setSelectedPreset] = useState(null)
  const [showCriteriaBuilder, setShowCriteriaBuilder] = useState(false)
  const [newCriteria, setNewCriteria] = useState({ type: 'PRICE_CHANGE_24H', operator: 'GT', value: 0, value2: 0 })
  const [savedScreens, setSavedScreens] = useState([])
  const [isRefreshing, setIsRefreshing] = useState(false)

  useEffect(() => {
    setTokens(generateTokens())
  }, [])

  const handleAddCriteria = useCallback(() => {
    setCriteria(prev => [...prev, { ...newCriteria, id: Date.now() }])
    setNewCriteria({ type: 'PRICE_CHANGE_24H', operator: 'GT', value: 0, value2: 0 })
  }, [newCriteria])

  const handleRemoveCriteria = useCallback((id) => {
    setCriteria(prev => prev.filter(c => c.id !== id))
  }, [])

  const handleApplyPreset = useCallback((presetKey) => {
    setSelectedPreset(presetKey)
    setCriteria(PRESET_SCREENS[presetKey].criteria.map(c => ({ ...c, id: Date.now() + Math.random() })))
  }, [])

  const handleClearFilters = useCallback(() => {
    setCriteria([])
    setSelectedPreset(null)
    setSelectedCategory('All')
    setSearchQuery('')
  }, [])

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setTimeout(() => {
      setTokens(generateTokens())
      setIsRefreshing(false)
    }, 1500)
  }, [])

  const handleToggleStar = useCallback((symbol) => {
    setTokens(prev => prev.map(t =>
      t.symbol === symbol ? { ...t, starred: !t.starred } : t
    ))
  }, [])

  const handleSort = useCallback((field) => {
    if (sortBy === field) {
      setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortOrder('desc')
    }
  }, [sortBy])

  // Apply criteria to token
  const matchesCriteria = useCallback((token, criterion) => {
    const getValue = (type) => {
      switch (type) {
        case 'PRICE_CHANGE_24H': return token.priceChange24h
        case 'PRICE_CHANGE_7D': return token.priceChange7d
        case 'VOLUME_24H': return token.volume24h
        case 'MARKET_CAP': return token.marketCap
        case 'VOLUME_MCAP_RATIO': return token.volumeMcapRatio
        case 'RSI_14': return token.rsi14
        case 'ATH_DISTANCE': return token.athDistance
        case 'ATL_DISTANCE': return token.atlDistance
        case 'VOLATILITY': return token.volatility
        case 'CIRCULATING_SUPPLY': return token.circulatingSupply
        default: return 0
      }
    }

    const value = getValue(criterion.type)

    switch (criterion.operator) {
      case 'GT': return value > criterion.value
      case 'GTE': return value >= criterion.value
      case 'LT': return value < criterion.value
      case 'LTE': return value <= criterion.value
      case 'EQ': return value === criterion.value
      case 'BETWEEN': return value >= criterion.value && value <= criterion.value2
      default: return true
    }
  }, [])

  // Filter and sort tokens
  const filteredTokens = useMemo(() => {
    return tokens
      .filter(t => {
        // Category filter
        if (selectedCategory !== 'All' && t.category !== selectedCategory) return false

        // Search filter
        if (searchQuery && !t.symbol.toLowerCase().includes(searchQuery.toLowerCase()) &&
            !t.name.toLowerCase().includes(searchQuery.toLowerCase())) return false

        // Criteria filters
        for (const criterion of criteria) {
          if (!matchesCriteria(t, criterion)) return false
        }

        return true
      })
      .sort((a, b) => {
        const aVal = a[sortBy] || 0
        const bVal = b[sortBy] || 0
        return sortOrder === 'asc' ? aVal - bVal : bVal - aVal
      })
  }, [tokens, selectedCategory, searchQuery, criteria, sortBy, sortOrder, matchesCriteria])

  const formatNumber = (num, decimals = 2) => {
    if (Math.abs(num) >= 1e12) return (num / 1e12).toFixed(decimals) + 'T'
    if (Math.abs(num) >= 1e9) return (num / 1e9).toFixed(decimals) + 'B'
    if (Math.abs(num) >= 1e6) return (num / 1e6).toFixed(decimals) + 'M'
    if (Math.abs(num) >= 1e3) return (num / 1e3).toFixed(decimals) + 'K'
    return num.toFixed(decimals)
  }

  const formatCurrency = (num) => '$' + formatNumber(num)

  const formatPercent = (num) => {
    const prefix = num >= 0 ? '+' : ''
    return prefix + num.toFixed(2) + '%'
  }

  const SortIcon = ({ field }) => {
    if (sortBy !== field) return <ChevronDown className="w-4 h-4 text-white/20" />
    return sortOrder === 'asc' ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
            <Filter className="w-8 h-8 text-cyan-400" />
            Market Screener
          </h1>
          <p className="text-white/60">Filter and discover tokens based on custom criteria</p>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={handleClearFilters}
            className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg font-medium"
          >
            Clear Filters
          </button>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Preset Screens */}
      <div className="mb-6">
        <div className="flex flex-wrap gap-2">
          {Object.entries(PRESET_SCREENS).map(([key, screen]) => (
            <button
              key={key}
              onClick={() => handleApplyPreset(key)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedPreset === key
                  ? 'bg-cyan-500 text-white'
                  : 'bg-white/10 hover:bg-white/20'
              }`}
            >
              {screen.name}
            </button>
          ))}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white/5 rounded-xl border border-white/10 p-4 mb-6">
        <div className="flex flex-col md:flex-row gap-4 mb-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by name or symbol..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
          >
            {CATEGORIES.map(cat => (
              <option key={cat} value={cat} className="bg-[#0a0e14]">{cat}</option>
            ))}
          </select>

          <button
            onClick={() => setShowCriteriaBuilder(!showCriteriaBuilder)}
            className="px-4 py-2 bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30 rounded-lg font-medium flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Filter
          </button>
        </div>

        {/* Active Criteria */}
        {criteria.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {criteria.map((c, idx) => (
              <div key={c.id || idx} className="flex items-center gap-2 px-3 py-1 bg-cyan-500/20 rounded-full">
                <span className="text-sm text-cyan-400">
                  {CRITERIA_TYPES[c.type].label} {OPERATORS[c.operator].label} {c.value}
                  {c.operator === 'BETWEEN' && ` - ${c.value2}`}
                  {CRITERIA_TYPES[c.type].unit}
                </span>
                <button onClick={() => handleRemoveCriteria(c.id)} className="text-cyan-400 hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Criteria Builder */}
        {showCriteriaBuilder && (
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <div className="flex flex-col md:flex-row gap-4">
              <select
                value={newCriteria.type}
                onChange={(e) => setNewCriteria(prev => ({ ...prev, type: e.target.value }))}
                className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
              >
                {Object.entries(CRITERIA_TYPES).map(([key, type]) => (
                  <option key={key} value={key} className="bg-[#0a0e14]">{type.label}</option>
                ))}
              </select>

              <select
                value={newCriteria.operator}
                onChange={(e) => setNewCriteria(prev => ({ ...prev, operator: e.target.value }))}
                className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
              >
                {Object.entries(OPERATORS).map(([key, op]) => (
                  <option key={key} value={key} className="bg-[#0a0e14]">{op.name}</option>
                ))}
              </select>

              <input
                type="number"
                value={newCriteria.value}
                onChange={(e) => setNewCriteria(prev => ({ ...prev, value: parseFloat(e.target.value) || 0 }))}
                className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none w-32"
              />

              {newCriteria.operator === 'BETWEEN' && (
                <>
                  <span className="self-center text-white/60">to</span>
                  <input
                    type="number"
                    value={newCriteria.value2}
                    onChange={(e) => setNewCriteria(prev => ({ ...prev, value2: parseFloat(e.target.value) || 0 }))}
                    className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none w-32"
                  />
                </>
              )}

              <button
                onClick={handleAddCriteria}
                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium"
              >
                Add
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Results Stats */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-white/60">
          Showing <span className="text-white font-medium">{filteredTokens.length}</span> of {tokens.length} tokens
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left p-4 text-white/60 font-medium w-8"></th>
                <th className="text-left p-4 text-white/60 font-medium">#</th>
                <th className="text-left p-4 text-white/60 font-medium">Token</th>
                <th
                  className="text-right p-4 text-white/60 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('price')}
                >
                  <div className="flex items-center justify-end gap-1">
                    Price <SortIcon field="price" />
                  </div>
                </th>
                <th
                  className="text-right p-4 text-white/60 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('priceChange24h')}
                >
                  <div className="flex items-center justify-end gap-1">
                    24h <SortIcon field="priceChange24h" />
                  </div>
                </th>
                <th
                  className="text-right p-4 text-white/60 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('priceChange7d')}
                >
                  <div className="flex items-center justify-end gap-1">
                    7d <SortIcon field="priceChange7d" />
                  </div>
                </th>
                <th
                  className="text-right p-4 text-white/60 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('marketCap')}
                >
                  <div className="flex items-center justify-end gap-1">
                    Market Cap <SortIcon field="marketCap" />
                  </div>
                </th>
                <th
                  className="text-right p-4 text-white/60 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('volume24h')}
                >
                  <div className="flex items-center justify-end gap-1">
                    Volume (24h) <SortIcon field="volume24h" />
                  </div>
                </th>
                <th
                  className="text-right p-4 text-white/60 font-medium cursor-pointer hover:text-white"
                  onClick={() => handleSort('rsi14')}
                >
                  <div className="flex items-center justify-end gap-1">
                    RSI <SortIcon field="rsi14" />
                  </div>
                </th>
                <th className="text-left p-4 text-white/60 font-medium">Category</th>
              </tr>
            </thead>
            <tbody>
              {filteredTokens.map((token, idx) => (
                <tr key={token.symbol} className="border-b border-white/5 hover:bg-white/5">
                  <td className="p-4">
                    <button
                      onClick={() => handleToggleStar(token.symbol)}
                      className={token.starred ? 'text-yellow-400' : 'text-white/20 hover:text-yellow-400'}
                    >
                      {token.starred ? <Star className="w-4 h-4 fill-current" /> : <StarOff className="w-4 h-4" />}
                    </button>
                  </td>
                  <td className="p-4 text-white/60">{token.rank}</td>
                  <td className="p-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-xs font-bold">
                        {token.symbol.slice(0, 2)}
                      </div>
                      <div>
                        <div className="font-medium">{token.symbol}</div>
                        <div className="text-xs text-white/60">{token.name}</div>
                      </div>
                    </div>
                  </td>
                  <td className="p-4 text-right font-medium">
                    ${token.price < 1 ? token.price.toFixed(6) : token.price.toFixed(2)}
                  </td>
                  <td className={`p-4 text-right ${token.priceChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatPercent(token.priceChange24h)}
                  </td>
                  <td className={`p-4 text-right ${token.priceChange7d >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatPercent(token.priceChange7d)}
                  </td>
                  <td className="p-4 text-right">{formatCurrency(token.marketCap)}</td>
                  <td className="p-4 text-right">{formatCurrency(token.volume24h)}</td>
                  <td className="p-4 text-right">
                    <span className={`px-2 py-1 rounded text-xs ${
                      token.rsi14 < 30 ? 'bg-green-500/20 text-green-400' :
                      token.rsi14 > 70 ? 'bg-red-500/20 text-red-400' :
                      'bg-white/10 text-white/60'
                    }`}>
                      {token.rsi14.toFixed(1)}
                    </span>
                  </td>
                  <td className="p-4">
                    <span className="px-2 py-1 bg-white/10 rounded text-xs">{token.category}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredTokens.length === 0 && (
          <div className="p-12 text-center">
            <Filter className="w-12 h-12 mx-auto mb-4 text-white/40" />
            <p className="text-white/60">No tokens match your criteria</p>
            <button
              onClick={handleClearFilters}
              className="mt-4 px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium"
            >
              Clear Filters
            </button>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-6 p-4 bg-white/5 rounded-xl border border-white/10">
        <h3 className="font-medium mb-3 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-cyan-400" />
          RSI Guide
        </h3>
        <div className="flex flex-wrap gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-green-500" />
            <span className="text-white/60">Oversold ({'<'}30) - Potential buy signal</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-white/30" />
            <span className="text-white/60">Neutral (30-70)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-red-500" />
            <span className="text-white/60">Overbought ({'>'}70) - Potential sell signal</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default MarketScreener
