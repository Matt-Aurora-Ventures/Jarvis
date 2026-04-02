import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Droplets,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  AlertTriangle,
  Shield,
  Clock,
  RefreshCw,
  Search,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  BarChart3,
  PieChart,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Lock,
  Unlock,
  Flame,
  Info,
  Eye,
  Plus,
  Minus,
  X,
  Layers,
  Users,
  Percent,
  Wallet
} from 'lucide-react'

// DEX Platforms
const DEX_PLATFORMS = {
  RAYDIUM: { name: 'Raydium', color: '#58c7e3' },
  ORCA: { name: 'Orca', color: '#ff6b00' },
  METEORA: { name: 'Meteora', color: '#8b5cf6' },
  JUPITER: { name: 'Jupiter', color: '#c7f284' },
  PHOENIX: { name: 'Phoenix', color: '#f97316' },
}

// Liquidity health levels
const HEALTH_LEVELS = {
  EXCELLENT: { label: 'Excellent', color: '#22c55e', minScore: 80 },
  GOOD: { label: 'Good', color: '#84cc16', minScore: 60 },
  FAIR: { label: 'Fair', color: '#eab308', minScore: 40 },
  POOR: { label: 'Poor', color: '#f97316', minScore: 20 },
  CRITICAL: { label: 'Critical', color: '#ef4444', minScore: 0 },
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

function getHealthLevel(score) {
  for (const [key, level] of Object.entries(HEALTH_LEVELS)) {
    if (score >= level.minScore) return { key, ...level }
  }
  return { key: 'CRITICAL', ...HEALTH_LEVELS.CRITICAL }
}

// Liquidity Health Score Component
function HealthScoreBadge({ score, size = 'md' }) {
  const health = getHealthLevel(score)

  const sizeClasses = {
    sm: 'w-12 h-12 text-sm',
    md: 'w-16 h-16 text-lg',
    lg: 'w-20 h-20 text-xl',
  }

  return (
    <div className="text-center">
      <div
        className={`${sizeClasses[size]} rounded-full flex items-center justify-center font-bold mx-auto mb-1`}
        style={{
          backgroundColor: `${health.color}20`,
          border: `2px solid ${health.color}`,
          color: health.color
        }}
      >
        {score}
      </div>
      <div className="text-xs text-gray-400">{health.label}</div>
    </div>
  )
}

// Pool Card Component
function PoolCard({ pool, onSelect, isSelected }) {
  const health = getHealthLevel(pool.healthScore || 50)
  const dex = DEX_PLATFORMS[pool.dex] || { name: pool.dex, color: '#888' }

  return (
    <div
      className={`bg-gray-800 rounded-xl border p-4 cursor-pointer transition-all ${
        isSelected ? 'border-purple-500 ring-1 ring-purple-500' : 'border-gray-700 hover:border-gray-600'
      }`}
      onClick={() => onSelect?.(pool)}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="flex -space-x-2">
            {pool.token0Logo ? (
              <img src={pool.token0Logo} alt={pool.token0} className="w-8 h-8 rounded-full border-2 border-gray-800" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center text-xs font-bold border-2 border-gray-800">
                {pool.token0?.[0]}
              </div>
            )}
            {pool.token1Logo ? (
              <img src={pool.token1Logo} alt={pool.token1} className="w-8 h-8 rounded-full border-2 border-gray-800" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-xs font-bold border-2 border-gray-800">
                {pool.token1?.[0]}
              </div>
            )}
          </div>
          <div>
            <div className="font-semibold">{pool.token0}/{pool.token1}</div>
            <div className="text-xs text-gray-400 flex items-center gap-1">
              <span style={{ color: dex.color }}>{dex.name}</span>
              <span className="text-gray-600">|</span>
              <span>{pool.fee}% fee</span>
            </div>
          </div>
        </div>
        <HealthScoreBadge score={pool.healthScore || 50} size="sm" />
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-gray-900 rounded-lg p-2">
          <div className="text-xs text-gray-500">TVL</div>
          <div className="font-bold">{formatNumber(pool.tvl || 0)}</div>
        </div>
        <div className="bg-gray-900 rounded-lg p-2">
          <div className="text-xs text-gray-500">24h Volume</div>
          <div className="font-bold">{formatNumber(pool.volume24h || 0)}</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          {pool.lpBurned ? (
            <span className="flex items-center gap-1 text-green-400">
              <Flame className="w-3 h-3" /> LP Burned
            </span>
          ) : (
            <span className="flex items-center gap-1 text-yellow-400">
              <Lock className="w-3 h-3" /> LP Locked
            </span>
          )}
        </div>
        <div className={`flex items-center gap-1 ${
          (pool.tvlChange24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {(pool.tvlChange24h || 0) >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
          {formatPercent(pool.tvlChange24h || 0)}
        </div>
      </div>
    </div>
  )
}

// Depth Chart Component (Simplified)
function DepthChart({ bids = [], asks = [], midPrice }) {
  const maxBid = Math.max(...bids.map(b => b.total), 0)
  const maxAsk = Math.max(...asks.map(a => a.total), 0)
  const maxTotal = Math.max(maxBid, maxAsk)

  return (
    <div className="bg-gray-900 rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h4 className="font-semibold flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-purple-400" />
          Depth Chart
        </h4>
        <div className="text-sm text-gray-400">
          Mid: {midPrice ? `$${midPrice.toFixed(6)}` : 'N/A'}
        </div>
      </div>

      <div className="flex h-32 gap-1">
        {/* Bids (left side) */}
        <div className="flex-1 flex flex-col justify-end gap-0.5">
          {bids.slice(0, 10).map((bid, i) => (
            <div
              key={i}
              className="bg-green-500/30 rounded-l"
              style={{
                height: '8px',
                width: `${(bid.total / maxTotal) * 100}%`,
                marginLeft: 'auto'
              }}
            />
          ))}
        </div>

        {/* Center line */}
        <div className="w-px bg-gray-700" />

        {/* Asks (right side) */}
        <div className="flex-1 flex flex-col justify-end gap-0.5">
          {asks.slice(0, 10).map((ask, i) => (
            <div
              key={i}
              className="bg-red-500/30 rounded-r"
              style={{
                height: '8px',
                width: `${(ask.total / maxTotal) * 100}%`
              }}
            />
          ))}
        </div>
      </div>

      <div className="flex justify-between mt-2 text-xs text-gray-500">
        <span className="text-green-400">Bids: {formatNumber(maxBid)}</span>
        <span className="text-red-400">Asks: {formatNumber(maxAsk)}</span>
      </div>
    </div>
  )
}

// Liquidity Distribution Component
function LiquidityDistribution({ pool }) {
  const distributions = pool?.distributions || [
    { range: '-10% to -5%', percent: 15, liquidity: 50000 },
    { range: '-5% to -2%', percent: 25, liquidity: 80000 },
    { range: '-2% to +2%', percent: 35, liquidity: 120000 },
    { range: '+2% to +5%', percent: 18, liquidity: 60000 },
    { range: '+5% to +10%', percent: 7, liquidity: 25000 },
  ]

  return (
    <div className="bg-gray-900 rounded-xl p-4">
      <h4 className="font-semibold mb-4 flex items-center gap-2">
        <Layers className="w-4 h-4 text-blue-400" />
        Liquidity Distribution
      </h4>

      <div className="space-y-2">
        {distributions.map((dist, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-24 text-xs text-gray-400">{dist.range}</div>
            <div className="flex-1 h-4 bg-gray-800 rounded overflow-hidden">
              <div
                className={`h-full ${
                  dist.range.includes('+2%') || dist.range.includes('-2%')
                    ? 'bg-purple-500'
                    : 'bg-purple-500/50'
                }`}
                style={{ width: `${dist.percent}%` }}
              />
            </div>
            <div className="w-16 text-right text-xs text-gray-400">
              {dist.percent}%
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Pool Detail Panel
function PoolDetailPanel({ pool, onClose }) {
  if (!pool) return null

  const health = getHealthLevel(pool.healthScore || 50)
  const dex = DEX_PLATFORMS[pool.dex] || { name: pool.dex, color: '#888' }

  const metrics = [
    { label: 'TVL', value: formatNumber(pool.tvl || 0), change: pool.tvlChange24h },
    { label: '24h Volume', value: formatNumber(pool.volume24h || 0), change: pool.volumeChange24h },
    { label: '24h Fees', value: formatNumber(pool.fees24h || 0), change: null },
    { label: 'APR', value: `${(pool.apr || 0).toFixed(2)}%`, change: null },
    { label: 'Trades 24h', value: (pool.trades24h || 0).toLocaleString(), change: null },
    { label: 'Unique Traders', value: (pool.uniqueTraders || 0).toLocaleString(), change: null },
  ]

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-700">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="flex -space-x-2">
              {pool.token0Logo ? (
                <img src={pool.token0Logo} alt={pool.token0} className="w-10 h-10 rounded-full border-2 border-gray-800" />
              ) : (
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center font-bold border-2 border-gray-800">
                  {pool.token0?.[0]}
                </div>
              )}
              {pool.token1Logo ? (
                <img src={pool.token1Logo} alt={pool.token1} className="w-10 h-10 rounded-full border-2 border-gray-800" />
              ) : (
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center font-bold border-2 border-gray-800">
                  {pool.token1?.[0]}
                </div>
              )}
            </div>
            <div>
              <h3 className="text-xl font-bold">{pool.token0}/{pool.token1}</h3>
              <div className="flex items-center gap-2 text-sm">
                <span style={{ color: dex.color }}>{dex.name}</span>
                <span className="text-gray-600">|</span>
                <span className="text-gray-400">{pool.fee}% fee</span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Health Score */}
        <div className="flex items-center gap-4">
          <HealthScoreBadge score={pool.healthScore || 50} />
          <div className="flex-1">
            <div className="text-sm text-gray-400 mb-1">Liquidity Health</div>
            <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pool.healthScore || 50}%`,
                  backgroundColor: health.color
                }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="p-4 border-b border-gray-700">
        <div className="grid grid-cols-3 gap-3">
          {metrics.map((metric, i) => (
            <div key={i} className="bg-gray-900 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">{metric.label}</div>
              <div className="font-bold">{metric.value}</div>
              {metric.change !== null && (
                <div className={`text-xs ${
                  metric.change >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {formatPercent(metric.change)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* LP Info */}
      <div className="p-4 border-b border-gray-700">
        <h4 className="font-semibold mb-3">LP Status</h4>
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-gray-900 rounded-lg p-3 flex items-center gap-2">
            {pool.lpBurned ? (
              <>
                <Flame className="w-5 h-5 text-green-400" />
                <div>
                  <div className="font-medium text-green-400">LP Burned</div>
                  <div className="text-xs text-gray-400">Permanent liquidity</div>
                </div>
              </>
            ) : pool.lpLocked ? (
              <>
                <Lock className="w-5 h-5 text-yellow-400" />
                <div>
                  <div className="font-medium text-yellow-400">LP Locked</div>
                  <div className="text-xs text-gray-400">Until {pool.lpLockEnd || 'TBD'}</div>
                </div>
              </>
            ) : (
              <>
                <Unlock className="w-5 h-5 text-red-400" />
                <div>
                  <div className="font-medium text-red-400">LP Unlocked</div>
                  <div className="text-xs text-gray-400">Can be withdrawn</div>
                </div>
              </>
            )}
          </div>
          <div className="bg-gray-900 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">LP Holders</div>
            <div className="font-bold">{(pool.lpHolders || 0).toLocaleString()}</div>
          </div>
        </div>
      </div>

      {/* Depth Chart */}
      <div className="p-4 border-b border-gray-700">
        <DepthChart
          bids={pool.bids || []}
          asks={pool.asks || []}
          midPrice={pool.midPrice}
        />
      </div>

      {/* Distribution */}
      <div className="p-4 border-b border-gray-700">
        <LiquidityDistribution pool={pool} />
      </div>

      {/* External Links */}
      <div className="p-4">
        <div className="flex gap-2">
          <a
            href={`https://dexscreener.com/solana/${pool.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center justify-center gap-1 text-sm"
          >
            DexScreener <ExternalLink className="w-3 h-3" />
          </a>
          <a
            href={`https://birdeye.so/token/${pool.address}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center justify-center gap-1 text-sm"
          >
            Birdeye <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </div>
  )
}

// Stats Summary Component
function LiquidityStats({ pools }) {
  const stats = useMemo(() => {
    const totalTvl = pools.reduce((sum, p) => sum + (p.tvl || 0), 0)
    const totalVolume = pools.reduce((sum, p) => sum + (p.volume24h || 0), 0)
    const avgHealth = pools.length > 0
      ? pools.reduce((sum, p) => sum + (p.healthScore || 50), 0) / pools.length
      : 0
    const burnedCount = pools.filter(p => p.lpBurned).length
    const lockedCount = pools.filter(p => p.lpLocked).length

    return { totalTvl, totalVolume, avgHealth, burnedCount, lockedCount, total: pools.length }
  }, [pools])

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total TVL</div>
        <div className="text-2xl font-bold">{formatNumber(stats.totalTvl)}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">24h Volume</div>
        <div className="text-2xl font-bold">{formatNumber(stats.totalVolume)}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Avg Health</div>
        <div className="text-2xl font-bold" style={{ color: getHealthLevel(stats.avgHealth).color }}>
          {stats.avgHealth.toFixed(0)}
        </div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">LP Burned</div>
        <div className="text-2xl font-bold text-green-400">{stats.burnedCount}</div>
        <div className="text-xs text-gray-500">{((stats.burnedCount / stats.total) * 100).toFixed(0)}% of pools</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">LP Locked</div>
        <div className="text-2xl font-bold text-yellow-400">{stats.lockedCount}</div>
        <div className="text-xs text-gray-500">{((stats.lockedCount / stats.total) * 100).toFixed(0)}% of pools</div>
      </div>
    </div>
  )
}

// Main Liquidity Analysis Component
export function LiquidityAnalysis({
  pools = [],
  onRefresh,
  isLoading = false,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDex, setSelectedDex] = useState('all')
  const [minTvl, setMinTvl] = useState(0)
  const [minHealth, setMinHealth] = useState(0)
  const [sortBy, setSortBy] = useState('tvl')
  const [sortOrder, setSortOrder] = useState('desc')
  const [selectedPool, setSelectedPool] = useState(null)

  // Filter and sort pools
  const filteredPools = useMemo(() => {
    let result = [...pools]

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(p =>
        p.token0?.toLowerCase().includes(query) ||
        p.token1?.toLowerCase().includes(query) ||
        p.address?.toLowerCase().includes(query)
      )
    }

    // DEX filter
    if (selectedDex !== 'all') {
      result = result.filter(p => p.dex === selectedDex)
    }

    // Min TVL filter
    if (minTvl > 0) {
      result = result.filter(p => (p.tvl || 0) >= minTvl)
    }

    // Min health filter
    if (minHealth > 0) {
      result = result.filter(p => (p.healthScore || 50) >= minHealth)
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'tvl': comparison = (a.tvl || 0) - (b.tvl || 0); break
        case 'volume': comparison = (a.volume24h || 0) - (b.volume24h || 0); break
        case 'health': comparison = (a.healthScore || 50) - (b.healthScore || 50); break
        case 'apr': comparison = (a.apr || 0) - (b.apr || 0); break
        default: comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [pools, searchQuery, selectedDex, minTvl, minHealth, sortBy, sortOrder])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Droplets className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Liquidity Analysis</h1>
            <p className="text-sm text-gray-400">Analyze liquidity pools and their health</p>
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
      <LiquidityStats pools={pools} />

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search pools..."
              className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          <select
            value={selectedDex}
            onChange={e => setSelectedDex(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All DEXes</option>
            {Object.entries(DEX_PLATFORMS).map(([key, { name }]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>

          <select
            value={minTvl}
            onChange={e => setMinTvl(Number(e.target.value))}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value={0}>Any TVL</option>
            <option value={10000}>$10K+ TVL</option>
            <option value={100000}>$100K+ TVL</option>
            <option value={1000000}>$1M+ TVL</option>
          </select>

          <select
            value={minHealth}
            onChange={e => setMinHealth(Number(e.target.value))}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value={0}>Any Health</option>
            <option value={40}>40+ Health</option>
            <option value={60}>60+ Health</option>
            <option value={80}>80+ Health</option>
          </select>
        </div>

        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Sort:</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-sm"
            >
              <option value="tvl">TVL</option>
              <option value="volume">Volume</option>
              <option value="health">Health</option>
              <option value="apr">APR</option>
            </select>
            <button
              onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
              className="p-1 bg-gray-700 rounded"
            >
              {sortOrder === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
          </div>
          <span className="text-sm text-gray-400">{filteredPools.length} pools</span>
        </div>
      </div>

      {/* Content */}
      <div className="flex gap-6">
        {/* Pool Grid */}
        <div className="flex-1">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {filteredPools.map((pool, i) => (
              <PoolCard
                key={pool.address || i}
                pool={pool}
                onSelect={setSelectedPool}
                isSelected={selectedPool?.address === pool.address}
              />
            ))}
          </div>

          {filteredPools.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <Droplets className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No liquidity pools found</p>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        {selectedPool && (
          <div className="w-96 flex-shrink-0">
            <PoolDetailPanel pool={selectedPool} onClose={() => setSelectedPool(null)} />
          </div>
        )}
      </div>
    </div>
  )
}

export default LiquidityAnalysis
