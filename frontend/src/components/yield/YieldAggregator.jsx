import React, { useState, useMemo, useCallback } from 'react'
import {
  TrendingUp, TrendingDown, RefreshCw, ExternalLink, Search, Filter,
  DollarSign, Percent, Shield, AlertTriangle, Star, StarOff, Zap,
  Layers, Clock, ChevronDown, ChevronUp, Lock, Unlock, ArrowUpRight,
  PieChart, BarChart3, Wallet, Calculator, Check, X, Info
} from 'lucide-react'

// Chains
const CHAINS = {
  ETHEREUM: { name: 'Ethereum', color: '#627EEA', icon: 'E' },
  ARBITRUM: { name: 'Arbitrum', color: '#28A0F0', icon: 'A' },
  BASE: { name: 'Base', color: '#0052FF', icon: 'B' },
  SOLANA: { name: 'Solana', color: '#9945FF', icon: 'S' },
  POLYGON: { name: 'Polygon', color: '#8247E5', icon: 'P' },
  BSC: { name: 'BNB Chain', color: '#F0B90B', icon: 'B' },
  AVALANCHE: { name: 'Avalanche', color: '#E84142', icon: 'A' },
  OPTIMISM: { name: 'Optimism', color: '#FF0420', icon: 'O' }
}

// Protocol categories
const CATEGORIES = {
  LENDING: { label: 'Lending', color: '#3B82F6' },
  DEX_LP: { label: 'DEX LP', color: '#8B5CF6' },
  STAKING: { label: 'Staking', color: '#22C55E' },
  VAULT: { label: 'Vault', color: '#F59E0B' },
  DERIVATIVES: { label: 'Derivatives', color: '#EF4444' },
  LIQUID_STAKING: { label: 'Liquid Staking', color: '#06B6D4' }
}

// Risk levels
const RISK_LEVELS = {
  LOW: { label: 'Low', color: 'text-green-400', bg: 'bg-green-500/20' },
  MEDIUM: { label: 'Medium', color: 'text-yellow-400', bg: 'bg-yellow-500/20' },
  HIGH: { label: 'High', color: 'text-orange-400', bg: 'bg-orange-500/20' },
  VERY_HIGH: { label: 'Very High', color: 'text-red-400', bg: 'bg-red-500/20' }
}

// Mock yield opportunities
const MOCK_YIELDS = [
  {
    id: '1',
    protocol: 'Aave V3',
    chain: 'ETHEREUM',
    category: 'LENDING',
    asset: 'USDC',
    assetLogo: null,
    apy: 8.52,
    apyBase: 3.2,
    apyReward: 5.32,
    rewardToken: 'AAVE',
    tvl: 2450000000,
    tvlChange24h: 2.3,
    risk: 'LOW',
    audited: true,
    insurance: true,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: null,
    utilization: 78
  },
  {
    id: '2',
    protocol: 'Lido',
    chain: 'ETHEREUM',
    category: 'LIQUID_STAKING',
    asset: 'ETH',
    assetLogo: null,
    apy: 3.85,
    apyBase: 3.85,
    apyReward: 0,
    rewardToken: null,
    tvl: 28500000000,
    tvlChange24h: 0.8,
    risk: 'LOW',
    audited: true,
    insurance: false,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: null,
    utilization: 95
  },
  {
    id: '3',
    protocol: 'GMX',
    chain: 'ARBITRUM',
    category: 'DERIVATIVES',
    asset: 'GLP',
    assetLogo: null,
    apy: 18.45,
    apyBase: 12.5,
    apyReward: 5.95,
    rewardToken: 'esGMX',
    tvl: 520000000,
    tvlChange24h: -1.2,
    risk: 'MEDIUM',
    audited: true,
    insurance: false,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: 800000000,
    utilization: 65
  },
  {
    id: '4',
    protocol: 'Kamino',
    chain: 'SOLANA',
    category: 'VAULT',
    asset: 'SOL-USDC',
    assetLogo: null,
    apy: 42.8,
    apyBase: 28.5,
    apyReward: 14.3,
    rewardToken: 'KMNO',
    tvl: 185000000,
    tvlChange24h: 5.8,
    risk: 'MEDIUM',
    audited: true,
    insurance: false,
    lockPeriod: 0,
    minDeposit: 10,
    maxCapacity: 250000000,
    utilization: 74
  },
  {
    id: '5',
    protocol: 'Convex',
    chain: 'ETHEREUM',
    category: 'VAULT',
    asset: 'CRV/CVX',
    assetLogo: null,
    apy: 25.2,
    apyBase: 8.5,
    apyReward: 16.7,
    rewardToken: 'CVX',
    tvl: 3200000000,
    tvlChange24h: 1.5,
    risk: 'MEDIUM',
    audited: true,
    insurance: false,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: null,
    utilization: 82
  },
  {
    id: '6',
    protocol: 'Aerodrome',
    chain: 'BASE',
    category: 'DEX_LP',
    asset: 'WETH-USDC',
    assetLogo: null,
    apy: 65.3,
    apyBase: 18.2,
    apyReward: 47.1,
    rewardToken: 'AERO',
    tvl: 145000000,
    tvlChange24h: 12.5,
    risk: 'HIGH',
    audited: true,
    insurance: false,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: 200000000,
    utilization: 72.5
  },
  {
    id: '7',
    protocol: 'Pendle',
    chain: 'ARBITRUM',
    category: 'DERIVATIVES',
    asset: 'PT-stETH',
    assetLogo: null,
    apy: 12.8,
    apyBase: 12.8,
    apyReward: 0,
    rewardToken: null,
    tvl: 890000000,
    tvlChange24h: 3.2,
    risk: 'MEDIUM',
    audited: true,
    insurance: false,
    lockPeriod: 180,
    minDeposit: 0,
    maxCapacity: null,
    utilization: 68
  },
  {
    id: '8',
    protocol: 'Marinade',
    chain: 'SOLANA',
    category: 'LIQUID_STAKING',
    asset: 'SOL',
    assetLogo: null,
    apy: 7.85,
    apyBase: 7.85,
    apyReward: 0,
    rewardToken: null,
    tvl: 1250000000,
    tvlChange24h: 2.1,
    risk: 'LOW',
    audited: true,
    insurance: false,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: null,
    utilization: 92
  },
  {
    id: '9',
    protocol: 'Compound V3',
    chain: 'ETHEREUM',
    category: 'LENDING',
    asset: 'USDT',
    assetLogo: null,
    apy: 6.45,
    apyBase: 4.2,
    apyReward: 2.25,
    rewardToken: 'COMP',
    tvl: 1850000000,
    tvlChange24h: 0.5,
    risk: 'LOW',
    audited: true,
    insurance: true,
    lockPeriod: 0,
    minDeposit: 0,
    maxCapacity: null,
    utilization: 75
  },
  {
    id: '10',
    protocol: 'Hyperliquid',
    chain: 'ARBITRUM',
    category: 'DERIVATIVES',
    asset: 'HLP',
    assetLogo: null,
    apy: 28.5,
    apyBase: 22.0,
    apyReward: 6.5,
    rewardToken: 'HYPE',
    tvl: 420000000,
    tvlChange24h: 8.2,
    risk: 'HIGH',
    audited: true,
    insurance: false,
    lockPeriod: 7,
    minDeposit: 100,
    maxCapacity: 600000000,
    utilization: 70
  }
]

// Format large numbers
const formatValue = (value, decimals = 2) => {
  if (value >= 1e9) return `$${(value / 1e9).toFixed(decimals)}B`
  if (value >= 1e6) return `$${(value / 1e6).toFixed(decimals)}M`
  if (value >= 1e3) return `$${(value / 1e3).toFixed(decimals)}K`
  return `$${value.toFixed(decimals)}`
}

// Chain badge
const ChainBadge = ({ chain }) => {
  const chainData = CHAINS[chain]
  return (
    <div
      className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold"
      style={{ backgroundColor: chainData.color, color: '#000' }}
      title={chainData.name}
    >
      {chainData.icon}
    </div>
  )
}

// Category badge
const CategoryBadge = ({ category }) => {
  const cat = CATEGORIES[category]
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: `${cat.color}20`, color: cat.color }}
    >
      {cat.label}
    </span>
  )
}

// Risk badge
const RiskBadge = ({ risk }) => {
  const r = RISK_LEVELS[risk]
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${r.bg} ${r.color}`}>
      {r.label}
    </span>
  )
}

// APY breakdown
const APYBreakdown = ({ base, reward, rewardToken }) => {
  return (
    <div className="text-xs space-y-1">
      <div className="flex justify-between">
        <span className="text-gray-500">Base APY</span>
        <span className="text-gray-300">{base.toFixed(2)}%</span>
      </div>
      {reward > 0 && (
        <div className="flex justify-between">
          <span className="text-gray-500">Reward APY ({rewardToken})</span>
          <span className="text-green-400">+{reward.toFixed(2)}%</span>
        </div>
      )}
    </div>
  )
}

// Yield card
const YieldCard = ({ opportunity, favorites, onToggleFavorite, expanded, onExpand }) => {
  const isFavorite = favorites.includes(opportunity.id)

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden hover:border-white/20 transition-colors">
      <div
        className="p-4 cursor-pointer"
        onClick={() => onExpand(expanded ? null : opportunity.id)}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <ChainBadge chain={opportunity.chain} />
            <div>
              <div className="font-medium flex items-center gap-2">
                {opportunity.protocol}
                {opportunity.audited && (
                  <Shield className="w-4 h-4 text-green-400" title="Audited" />
                )}
                {opportunity.insurance && (
                  <Check className="w-4 h-4 text-blue-400" title="Insurance Available" />
                )}
              </div>
              <div className="text-sm text-gray-400">{opportunity.asset}</div>
            </div>
          </div>

          <button
            onClick={(e) => { e.stopPropagation(); onToggleFavorite(opportunity.id) }}
            className={`p-1.5 rounded-lg transition-colors ${
              isFavorite ? 'text-yellow-400' : 'text-gray-500 hover:text-gray-400'
            }`}
          >
            {isFavorite ? <Star className="w-5 h-5 fill-current" /> : <StarOff className="w-5 h-5" />}
          </button>
        </div>

        <div className="flex items-end justify-between">
          <div>
            <div className="text-3xl font-bold text-green-400">
              {opportunity.apy.toFixed(2)}%
            </div>
            <div className="text-xs text-gray-500">APY</div>
          </div>

          <div className="text-right">
            <div className="font-medium">{formatValue(opportunity.tvl, 1)}</div>
            <div className={`text-xs flex items-center justify-end gap-1 ${
              opportunity.tvlChange24h > 0 ? 'text-green-400' : 'text-red-400'
            }`}>
              {opportunity.tvlChange24h > 0 ? <ArrowUpRight className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              {Math.abs(opportunity.tvlChange24h)}%
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-3">
          <CategoryBadge category={opportunity.category} />
          <RiskBadge risk={opportunity.risk} />
          {opportunity.lockPeriod > 0 && (
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <Lock className="w-3 h-3" />
              {opportunity.lockPeriod}d
            </span>
          )}
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="p-4 bg-white/[0.02] border-t border-white/10">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-2">APY Breakdown</div>
              <APYBreakdown
                base={opportunity.apyBase}
                reward={opportunity.apyReward}
                rewardToken={opportunity.rewardToken}
              />
            </div>

            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-2">Pool Stats</div>
              <div className="text-xs space-y-1">
                <div className="flex justify-between">
                  <span className="text-gray-500">Utilization</span>
                  <span className="text-gray-300">{opportunity.utilization}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Min Deposit</span>
                  <span className="text-gray-300">
                    {opportunity.minDeposit > 0 ? `$${opportunity.minDeposit}` : 'None'}
                  </span>
                </div>
                {opportunity.maxCapacity && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Capacity</span>
                    <span className="text-gray-300">{formatValue(opportunity.maxCapacity)}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Utilization bar */}
          {opportunity.maxCapacity && (
            <div className="mb-4">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-500">Capacity Used</span>
                <span className="text-gray-400">
                  {formatValue(opportunity.tvl)} / {formatValue(opportunity.maxCapacity)}
                </span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-500 to-yellow-500 rounded-full transition-all duration-500"
                  style={{ width: `${(opportunity.tvl / opportunity.maxCapacity) * 100}%` }}
                />
              </div>
            </div>
          )}

          <button className="w-full py-2 bg-green-500/20 hover:bg-green-500/30 text-green-400 rounded-lg font-medium transition-colors flex items-center justify-center gap-2">
            <Wallet className="w-4 h-4" />
            Deposit
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  )
}

// Stats overview
const StatsOverview = ({ yields }) => {
  const stats = useMemo(() => {
    const totalTVL = yields.reduce((sum, y) => sum + y.tvl, 0)
    const avgAPY = yields.reduce((sum, y) => sum + y.apy, 0) / yields.length
    const maxAPY = Math.max(...yields.map(y => y.apy))
    const lowRiskCount = yields.filter(y => y.risk === 'LOW').length

    return { totalTVL, avgAPY, maxAPY, lowRiskCount, totalOpportunities: yields.length }
  }, [yields])

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Total TVL</div>
        <div className="text-2xl font-bold">{formatValue(stats.totalTVL, 1)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Avg APY</div>
        <div className="text-2xl font-bold text-green-400">{stats.avgAPY.toFixed(1)}%</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Max APY</div>
        <div className="text-2xl font-bold text-yellow-400">{stats.maxAPY.toFixed(1)}%</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Low Risk Options</div>
        <div className="text-2xl font-bold">{stats.lowRiskCount}</div>
        <div className="text-xs text-gray-500">of {stats.totalOpportunities} total</div>
      </div>
    </div>
  )
}

// Chain filter
const ChainFilter = ({ chains, selected, onChange }) => {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        onClick={() => onChange([])}
        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
          selected.length === 0
            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
            : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
        }`}
      >
        All Chains
      </button>
      {Object.entries(CHAINS).map(([key, chain]) => (
        <button
          key={key}
          onClick={() => {
            if (selected.includes(key)) {
              onChange(selected.filter(c => c !== key))
            } else {
              onChange([...selected, key])
            }
          }}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-1.5 ${
            selected.includes(key)
              ? 'bg-white/10 text-white border border-white/30'
              : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
          }`}
        >
          <ChainBadge chain={key} />
          {chain.name}
        </button>
      ))}
    </div>
  )
}

// Top yields sidebar
const TopYields = ({ yields }) => {
  const top5 = useMemo(() =>
    [...yields].sort((a, b) => b.apy - a.apy).slice(0, 5),
    [yields]
  )

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Zap className="w-4 h-4 text-yellow-400" />
        Top APY Opportunities
      </h3>

      <div className="space-y-3">
        {top5.map((y, idx) => (
          <div key={y.id} className="flex items-center gap-3">
            <span className="text-lg font-bold text-gray-500 w-5">{idx + 1}</span>
            <ChainBadge chain={y.chain} />
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate">{y.protocol}</div>
              <div className="text-xs text-gray-500">{y.asset}</div>
            </div>
            <div className="text-right">
              <div className="font-bold text-green-400">{y.apy.toFixed(1)}%</div>
              <RiskBadge risk={y.risk} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// TVL by category
const TVLByCategory = ({ yields }) => {
  const byCategory = useMemo(() => {
    const cats = {}
    yields.forEach(y => {
      cats[y.category] = (cats[y.category] || 0) + y.tvl
    })
    const total = Object.values(cats).reduce((a, b) => a + b, 0)
    return Object.entries(cats)
      .map(([cat, tvl]) => ({ category: cat, tvl, percent: (tvl / total) * 100 }))
      .sort((a, b) => b.tvl - a.tvl)
  }, [yields])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <PieChart className="w-4 h-4" />
        TVL by Category
      </h3>

      <div className="space-y-3">
        {byCategory.map(({ category, tvl, percent }) => (
          <div key={category}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span style={{ color: CATEGORIES[category].color }}>
                {CATEGORIES[category].label}
              </span>
              <span className="font-medium">{formatValue(tvl, 1)}</span>
            </div>
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${percent}%`,
                  backgroundColor: CATEGORIES[category].color
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Main component
export const YieldAggregator = () => {
  const [yields] = useState(MOCK_YIELDS)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedChains, setSelectedChains] = useState([])
  const [selectedCategories, setSelectedCategories] = useState([])
  const [selectedRisks, setSelectedRisks] = useState([])
  const [favorites, setFavorites] = useState([])
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [expandedYield, setExpandedYield] = useState(null)
  const [sortBy, setSortBy] = useState('apy')
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1500)
  }, [])

  const toggleFavorite = useCallback((id) => {
    setFavorites(prev =>
      prev.includes(id)
        ? prev.filter(f => f !== id)
        : [...prev, id]
    )
  }, [])

  const filteredYields = useMemo(() => {
    let result = [...yields]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(y =>
        y.protocol.toLowerCase().includes(query) ||
        y.asset.toLowerCase().includes(query)
      )
    }

    if (selectedChains.length > 0) {
      result = result.filter(y => selectedChains.includes(y.chain))
    }

    if (selectedCategories.length > 0) {
      result = result.filter(y => selectedCategories.includes(y.category))
    }

    if (selectedRisks.length > 0) {
      result = result.filter(y => selectedRisks.includes(y.risk))
    }

    if (showFavoritesOnly) {
      result = result.filter(y => favorites.includes(y.id))
    }

    // Sort
    switch (sortBy) {
      case 'apy':
        result.sort((a, b) => b.apy - a.apy)
        break
      case 'tvl':
        result.sort((a, b) => b.tvl - a.tvl)
        break
      case 'risk':
        const riskOrder = ['LOW', 'MEDIUM', 'HIGH', 'VERY_HIGH']
        result.sort((a, b) => riskOrder.indexOf(a.risk) - riskOrder.indexOf(b.risk))
        break
    }

    return result
  }, [yields, searchQuery, selectedChains, selectedCategories, selectedRisks, showFavoritesOnly, favorites, sortBy])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Percent className="w-7 h-7 text-green-400" />
              DeFi Yield Aggregator
            </h1>
            <p className="text-gray-400 mt-1">Discover the best yield opportunities across DeFi</p>
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

        {/* Stats */}
        <StatsOverview yields={yields} />

        {/* Chain filter */}
        <div className="mb-6">
          <ChainFilter
            chains={CHAINS}
            selected={selectedChains}
            onChange={setSelectedChains}
          />
        </div>

        {/* Search and filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search protocols or assets..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-green-500/50"
            />
          </div>

          <button
            onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              showFavoritesOnly
                ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            <Star className="w-4 h-4" />
            Favorites ({favorites.length})
          </button>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
          >
            <option value="apy">Highest APY</option>
            <option value="tvl">Highest TVL</option>
            <option value="risk">Lowest Risk</option>
          </select>
        </div>

        {/* Category quick filters */}
        <div className="flex flex-wrap gap-2 mb-6">
          {Object.entries(CATEGORIES).map(([key, cat]) => (
            <button
              key={key}
              onClick={() => {
                if (selectedCategories.includes(key)) {
                  setSelectedCategories(selectedCategories.filter(c => c !== key))
                } else {
                  setSelectedCategories([...selectedCategories, key])
                }
              }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                selectedCategories.includes(key)
                  ? 'border'
                  : 'bg-white/5 border border-white/10 hover:bg-white/10'
              }`}
              style={selectedCategories.includes(key) ? {
                backgroundColor: `${cat.color}20`,
                borderColor: `${cat.color}50`,
                color: cat.color
              } : { color: '#9CA3AF' }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Main content grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Yields grid */}
          <div className="lg:col-span-3 grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredYields.map(y => (
              <YieldCard
                key={y.id}
                opportunity={y}
                favorites={favorites}
                onToggleFavorite={toggleFavorite}
                expanded={expandedYield === y.id}
                onExpand={setExpandedYield}
              />
            ))}

            {filteredYields.length === 0 && (
              <div className="col-span-full text-center py-12 bg-white/5 rounded-xl border border-white/10">
                <Percent className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400">No yield opportunities match your filters</p>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <TopYields yields={yields} />
            <TVLByCategory yields={yields} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default YieldAggregator
