import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Sprout,
  TrendingUp,
  Clock,
  DollarSign,
  AlertTriangle,
  Shield,
  Zap,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Info,
  Lock,
  Unlock,
  Calculator,
  Percent,
  Coins,
  Layers,
  Filter,
  Search,
  Star,
  StarOff,
  Activity,
  PieChart,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  Wallet,
  Settings,
  CheckCircle,
  XCircle,
  Timer,
  Gift
} from 'lucide-react'

// Protocol types and risk levels
const PROTOCOLS = {
  RAYDIUM: { name: 'Raydium', color: '#58c7e3', icon: 'RAY' },
  ORCA: { name: 'Orca', color: '#ff6b00', icon: 'ORCA' },
  MARINADE: { name: 'Marinade', color: '#309c54', icon: 'MNDE' },
  TULIP: { name: 'Tulip', color: '#d946ef', icon: 'TULIP' },
  FRANCIUM: { name: 'Francium', color: '#f59e0b', icon: 'FAM' },
  SOLEND: { name: 'Solend', color: '#14b8a6', icon: 'SLND' },
  MANGO: { name: 'Mango', color: '#f97316', icon: 'MNGO' },
  METEORA: { name: 'Meteora', color: '#8b5cf6', icon: 'MET' },
}

const RISK_LEVELS = {
  LOW: { label: 'Low Risk', color: 'green', score: 1 },
  MEDIUM: { label: 'Medium Risk', color: 'yellow', score: 2 },
  HIGH: { label: 'High Risk', color: 'orange', score: 3 },
  DEGEN: { label: 'Degen', color: 'red', score: 4 },
}

const POOL_TYPES = {
  LP: 'Liquidity Pool',
  STAKE: 'Staking',
  LEND: 'Lending',
  VAULT: 'Auto-Compound Vault',
  FARM: 'Yield Farm',
}

// APY Calculator Component
function APYCalculator({ pool, isOpen, onClose }) {
  const [amount, setAmount] = useState(1000)
  const [duration, setDuration] = useState(365)

  const calculations = useMemo(() => {
    if (!pool) return null

    const principal = amount
    const apyDecimal = pool.apy / 100
    const dailyRate = apyDecimal / 365

    // Simple interest
    const simpleInterest = principal * (apyDecimal * (duration / 365))

    // Compound interest (daily)
    const compoundDaily = principal * Math.pow(1 + dailyRate, duration) - principal

    // Account for IL if LP pool
    const ilAdjusted = pool.type === 'LP'
      ? compoundDaily * (1 - (pool.estimatedIL || 0.05))
      : compoundDaily

    return {
      simpleInterest,
      compoundDaily,
      ilAdjusted,
      dailyEarning: compoundDaily / duration,
      monthlyEarning: (compoundDaily / duration) * 30,
    }
  }, [pool, amount, duration])

  if (!isOpen || !pool) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl p-6 max-w-md w-full border border-gray-700">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Calculator className="w-5 h-5 text-purple-400" />
            APY Calculator
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          <div>
            <label className="text-sm text-gray-400 mb-1 block">Investment Amount (USD)</label>
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(Number(e.target.value))}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          <div>
            <label className="text-sm text-gray-400 mb-1 block">Duration (days)</label>
            <div className="flex gap-2">
              {[7, 30, 90, 365].map(d => (
                <button
                  key={d}
                  onClick={() => setDuration(d)}
                  className={`flex-1 py-2 rounded-lg text-sm ${
                    duration === d
                      ? 'bg-purple-500/20 border-purple-500 text-purple-400'
                      : 'bg-gray-700 border-gray-600'
                  } border`}
                >
                  {d === 365 ? '1Y' : d === 90 ? '3M' : d === 30 ? '1M' : '1W'}
                </button>
              ))}
            </div>
          </div>

          {calculations && (
            <div className="space-y-3 pt-4 border-t border-gray-700">
              <div className="flex justify-between">
                <span className="text-gray-400">Daily Compound Earnings</span>
                <span className="text-green-400 font-medium">
                  ${calculations.compoundDaily.toFixed(2)}
                </span>
              </div>

              {pool.type === 'LP' && (
                <div className="flex justify-between">
                  <span className="text-gray-400">After IL Adjustment</span>
                  <span className="text-yellow-400 font-medium">
                    ${calculations.ilAdjusted.toFixed(2)}
                  </span>
                </div>
              )}

              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Daily</span>
                <span className="text-gray-300">${calculations.dailyEarning.toFixed(2)}</span>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Monthly</span>
                <span className="text-gray-300">${calculations.monthlyEarning.toFixed(2)}</span>
              </div>

              <div className="bg-gray-900 rounded-lg p-3 mt-4">
                <div className="text-sm text-gray-400 mb-1">Total Value After {duration} Days</div>
                <div className="text-2xl font-bold text-green-400">
                  ${(amount + calculations.ilAdjusted).toFixed(2)}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Risk Assessment Badge
function RiskBadge({ level, showLabel = true }) {
  const risk = RISK_LEVELS[level] || RISK_LEVELS.MEDIUM

  const colorClasses = {
    green: 'bg-green-500/20 text-green-400 border-green-500/30',
    yellow: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    orange: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    red: 'bg-red-500/20 text-red-400 border-red-500/30',
  }

  return (
    <span className={`px-2 py-1 rounded-md text-xs font-medium border ${colorClasses[risk.color]}`}>
      {showLabel ? risk.label : `Risk: ${risk.score}/4`}
    </span>
  )
}

// Pool Card Component
function PoolCard({ pool, onDeposit, onWithdraw, onCalculate, isFavorite, onToggleFavorite }) {
  const [expanded, setExpanded] = useState(false)
  const protocol = PROTOCOLS[pool.protocol] || { name: pool.protocol, color: '#888' }

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden hover:border-gray-600 transition-colors">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold"
              style={{ backgroundColor: `${protocol.color}20`, color: protocol.color }}
            >
              {protocol.icon || protocol.name[0]}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{pool.name}</h3>
                <button
                  onClick={() => onToggleFavorite(pool.id)}
                  className="text-gray-400 hover:text-yellow-400"
                >
                  {isFavorite ? (
                    <Star className="w-4 h-4 fill-yellow-400 text-yellow-400" />
                  ) : (
                    <StarOff className="w-4 h-4" />
                  )}
                </button>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span>{protocol.name}</span>
                <span className="text-gray-600">|</span>
                <span>{POOL_TYPES[pool.type]}</span>
              </div>
            </div>
          </div>
          <RiskBadge level={pool.risk} />
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">APY</div>
            <div className="text-xl font-bold text-green-400">{pool.apy.toFixed(2)}%</div>
            {pool.apyChange && (
              <div className={`text-xs flex items-center gap-1 ${
                pool.apyChange > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {pool.apyChange > 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                {Math.abs(pool.apyChange).toFixed(1)}% 24h
              </div>
            )}
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">TVL</div>
            <div className="text-lg font-semibold">${formatNumber(pool.tvl)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Your Deposit</div>
            <div className="text-lg font-semibold">
              {pool.userDeposit > 0 ? `$${formatNumber(pool.userDeposit)}` : '-'}
            </div>
          </div>
        </div>

        {/* Rewards Preview */}
        {pool.rewards && pool.rewards.length > 0 && (
          <div className="flex items-center gap-2 mb-4">
            <Gift className="w-4 h-4 text-purple-400" />
            <span className="text-sm text-gray-400">Rewards:</span>
            <div className="flex gap-1">
              {pool.rewards.map((reward, i) => (
                <span key={i} className="px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded text-xs">
                  {reward.token}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => onDeposit(pool)}
            className="flex-1 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-colors flex items-center justify-center gap-2"
          >
            <Lock className="w-4 h-4" />
            Deposit
          </button>
          <button
            onClick={() => onWithdraw(pool)}
            disabled={!pool.userDeposit}
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Unlock className="w-4 h-4" />
            Withdraw
          </button>
          <button
            onClick={() => onCalculate(pool)}
            className="px-3 py-2 bg-purple-500/20 text-purple-400 rounded-lg hover:bg-purple-500/30 transition-colors"
          >
            <Calculator className="w-4 h-4" />
          </button>
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-3 py-2 bg-gray-700 text-gray-400 rounded-lg hover:bg-gray-600 transition-colors"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 bg-gray-900/50">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Daily APR</div>
              <div className="font-medium">{(pool.apy / 365).toFixed(4)}%</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Weekly APR</div>
              <div className="font-medium">{(pool.apy / 52).toFixed(3)}%</div>
            </div>
            {pool.type === 'LP' && (
              <>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Est. IL (30d)</div>
                  <div className="font-medium text-orange-400">
                    ~{((pool.estimatedIL || 0.02) * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Volume 24h</div>
                  <div className="font-medium">${formatNumber(pool.volume24h || 0)}</div>
                </div>
              </>
            )}
            <div>
              <div className="text-xs text-gray-500 mb-1">Lock Period</div>
              <div className="font-medium">{pool.lockPeriod || 'None'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Harvest Fee</div>
              <div className="font-medium">{pool.harvestFee || 0}%</div>
            </div>
          </div>

          {/* Pool Composition */}
          {pool.composition && (
            <div className="mb-4">
              <div className="text-xs text-gray-500 mb-2">Pool Composition</div>
              <div className="flex gap-2">
                {pool.composition.map((token, i) => (
                  <div key={i} className="flex-1 bg-gray-800 rounded-lg p-2 text-center">
                    <div className="font-medium">{token.symbol}</div>
                    <div className="text-xs text-gray-400">{token.weight}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* External Links */}
          <div className="flex gap-2">
            <a
              href={pool.poolUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 text-sm text-gray-400 hover:text-white flex items-center justify-center gap-1"
            >
              View on {protocol.name} <ExternalLink className="w-3 h-3" />
            </a>
            {pool.contractAddress && (
              <a
                href={`https://solscan.io/account/${pool.contractAddress}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 py-2 text-sm text-gray-400 hover:text-white flex items-center justify-center gap-1"
              >
                Contract <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Portfolio Summary Component
function PortfolioSummary({ pools, totalDeposited, totalEarnings, pendingRewards }) {
  const activePositions = pools.filter(p => p.userDeposit > 0)
  const avgApy = activePositions.length > 0
    ? activePositions.reduce((sum, p) => sum + (p.apy * p.userDeposit), 0) / totalDeposited
    : 0

  return (
    <div className="bg-gradient-to-r from-purple-900/30 to-blue-900/30 rounded-xl p-6 border border-purple-500/20">
      <div className="flex items-center gap-2 mb-4">
        <Sprout className="w-5 h-5 text-green-400" />
        <h2 className="text-lg font-semibold">Your Yield Farming Portfolio</h2>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        <div>
          <div className="text-sm text-gray-400 mb-1">Total Deposited</div>
          <div className="text-2xl font-bold">${formatNumber(totalDeposited)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-400 mb-1">Total Earnings</div>
          <div className="text-2xl font-bold text-green-400">+${formatNumber(totalEarnings)}</div>
        </div>
        <div>
          <div className="text-sm text-gray-400 mb-1">Weighted APY</div>
          <div className="text-2xl font-bold text-purple-400">{avgApy.toFixed(2)}%</div>
        </div>
        <div>
          <div className="text-sm text-gray-400 mb-1">Pending Rewards</div>
          <div className="text-2xl font-bold text-yellow-400">${formatNumber(pendingRewards)}</div>
          <button className="text-xs text-yellow-400 hover:underline mt-1">Harvest All</button>
        </div>
      </div>

      {activePositions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <div className="text-sm text-gray-400 mb-2">Active Positions ({activePositions.length})</div>
          <div className="flex flex-wrap gap-2">
            {activePositions.map(pool => (
              <div
                key={pool.id}
                className="px-3 py-1.5 bg-gray-800 rounded-lg text-sm flex items-center gap-2"
              >
                <span>{pool.name}</span>
                <span className="text-green-400">{pool.apy.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Deposit Modal
function DepositModal({ pool, isOpen, onClose, onConfirm }) {
  const [amount, setAmount] = useState('')
  const [slippage, setSlippage] = useState(0.5)

  if (!isOpen || !pool) return null

  const protocol = PROTOCOLS[pool.protocol] || { name: pool.protocol, color: '#888' }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl p-6 max-w-md w-full border border-gray-700">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">Deposit to {pool.name}</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <XCircle className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Pool Info */}
          <div className="bg-gray-900 rounded-lg p-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold"
                style={{ backgroundColor: `${protocol.color}20`, color: protocol.color }}
              >
                {protocol.icon}
              </div>
              <div>
                <div className="font-medium">{pool.name}</div>
                <div className="text-xs text-gray-400">{protocol.name}</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-green-400 font-bold">{pool.apy.toFixed(2)}% APY</div>
              <RiskBadge level={pool.risk} showLabel={false} />
            </div>
          </div>

          {/* Amount Input */}
          <div>
            <label className="text-sm text-gray-400 mb-1 block">Amount (USD)</label>
            <div className="relative">
              <input
                type="number"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                placeholder="0.00"
                className="w-full px-3 py-3 bg-gray-900 border border-gray-700 rounded-lg pr-20"
              />
              <button
                onClick={() => setAmount('1000')}
                className="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs"
              >
                MAX
              </button>
            </div>
          </div>

          {/* Slippage */}
          <div>
            <label className="text-sm text-gray-400 mb-1 block">Slippage Tolerance</label>
            <div className="flex gap-2">
              {[0.1, 0.5, 1.0, 2.0].map(s => (
                <button
                  key={s}
                  onClick={() => setSlippage(s)}
                  className={`flex-1 py-2 rounded-lg text-sm ${
                    slippage === s
                      ? 'bg-purple-500/20 border-purple-500 text-purple-400'
                      : 'bg-gray-700 border-gray-600'
                  } border`}
                >
                  {s}%
                </button>
              ))}
            </div>
          </div>

          {/* Estimated Returns */}
          {amount && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3">
              <div className="text-sm text-gray-400 mb-2">Estimated Returns</div>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-xs text-gray-500">Daily</div>
                  <div className="text-green-400">
                    ${((Number(amount) * pool.apy / 100) / 365).toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Monthly</div>
                  <div className="text-green-400">
                    ${((Number(amount) * pool.apy / 100) / 12).toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Yearly</div>
                  <div className="text-green-400">
                    ${(Number(amount) * pool.apy / 100).toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Warning for high risk */}
          {(pool.risk === 'HIGH' || pool.risk === 'DEGEN') && (
            <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-orange-400">
                This pool has elevated risk. Only deposit what you can afford to lose. DYOR.
              </div>
            </div>
          )}

          {/* Confirm Button */}
          <button
            onClick={() => onConfirm(pool, Number(amount), slippage)}
            disabled={!amount || Number(amount) <= 0}
            className="w-full py-3 bg-green-500 text-white rounded-lg font-semibold hover:bg-green-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Confirm Deposit
          </button>
        </div>
      </div>
    </div>
  )
}

// Helper function
function formatNumber(num) {
  if (num >= 1000000000) return (num / 1000000000).toFixed(2) + 'B'
  if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(2) + 'K'
  return num.toFixed(2)
}

// Main Yield Farming Dashboard Component
export function YieldFarming({
  pools = [],
  userPortfolio = {},
  onDeposit,
  onWithdraw,
  onRefresh,
  isLoading = false
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedProtocol, setSelectedProtocol] = useState('all')
  const [selectedRisk, setSelectedRisk] = useState('all')
  const [selectedType, setSelectedType] = useState('all')
  const [sortBy, setSortBy] = useState('apy')
  const [sortOrder, setSortOrder] = useState('desc')
  const [favorites, setFavorites] = useState(new Set())
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [calculatorPool, setCalculatorPool] = useState(null)
  const [depositPool, setDepositPool] = useState(null)

  // Filter and sort pools
  const filteredPools = useMemo(() => {
    let result = [...pools]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(p =>
        p.name.toLowerCase().includes(query) ||
        (PROTOCOLS[p.protocol]?.name || '').toLowerCase().includes(query)
      )
    }

    // Protocol filter
    if (selectedProtocol !== 'all') {
      result = result.filter(p => p.protocol === selectedProtocol)
    }

    // Risk filter
    if (selectedRisk !== 'all') {
      result = result.filter(p => p.risk === selectedRisk)
    }

    // Type filter
    if (selectedType !== 'all') {
      result = result.filter(p => p.type === selectedType)
    }

    // Favorites filter
    if (showFavoritesOnly) {
      result = result.filter(p => favorites.has(p.id))
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'apy': comparison = a.apy - b.apy; break
        case 'tvl': comparison = a.tvl - b.tvl; break
        case 'risk':
          comparison = (RISK_LEVELS[a.risk]?.score || 2) - (RISK_LEVELS[b.risk]?.score || 2)
          break
        case 'name': comparison = a.name.localeCompare(b.name); break
        default: comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [pools, searchQuery, selectedProtocol, selectedRisk, selectedType, sortBy, sortOrder, showFavoritesOnly, favorites])

  const toggleFavorite = useCallback((poolId) => {
    setFavorites(prev => {
      const newFavs = new Set(prev)
      if (newFavs.has(poolId)) {
        newFavs.delete(poolId)
      } else {
        newFavs.add(poolId)
      }
      return newFavs
    })
  }, [])

  // Calculate portfolio stats
  const portfolioStats = useMemo(() => {
    const deposited = pools.reduce((sum, p) => sum + (p.userDeposit || 0), 0)
    const earnings = pools.reduce((sum, p) => sum + (p.userEarnings || 0), 0)
    const pending = pools.reduce((sum, p) => sum + (p.pendingRewards || 0), 0)
    return { totalDeposited: deposited, totalEarnings: earnings, pendingRewards: pending }
  }, [pools])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-lg">
            <Sprout className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Yield Farming</h1>
            <p className="text-sm text-gray-400">Find the best DeFi yields on Solana</p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors flex items-center gap-2"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Portfolio Summary */}
      <PortfolioSummary
        pools={pools}
        {...portfolioStats}
      />

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
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

          {/* Protocol Filter */}
          <select
            value={selectedProtocol}
            onChange={e => setSelectedProtocol(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Protocols</option>
            {Object.entries(PROTOCOLS).map(([key, { name }]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>

          {/* Risk Filter */}
          <select
            value={selectedRisk}
            onChange={e => setSelectedRisk(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Risk Levels</option>
            {Object.entries(RISK_LEVELS).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>

          {/* Type Filter */}
          <select
            value={selectedType}
            onChange={e => setSelectedType(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Types</option>
            {Object.entries(POOL_TYPES).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        {/* Sort and View Options */}
        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Sort by:</span>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-sm"
              >
                <option value="apy">APY</option>
                <option value="tvl">TVL</option>
                <option value="risk">Risk</option>
                <option value="name">Name</option>
              </select>
              <button
                onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
                className="p-1 bg-gray-700 rounded"
              >
                {sortOrder === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              </button>
            </div>

            <button
              onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-sm ${
                showFavoritesOnly ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <Star className="w-4 h-4" />
              Favorites
            </button>
          </div>

          <div className="text-sm text-gray-400">
            {filteredPools.length} pools found
          </div>
        </div>
      </div>

      {/* Pool Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredPools.map(pool => (
          <PoolCard
            key={pool.id}
            pool={pool}
            onDeposit={setDepositPool}
            onWithdraw={onWithdraw}
            onCalculate={setCalculatorPool}
            isFavorite={favorites.has(pool.id)}
            onToggleFavorite={toggleFavorite}
          />
        ))}
      </div>

      {filteredPools.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Sprout className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No pools found matching your criteria</p>
        </div>
      )}

      {/* Modals */}
      <APYCalculator
        pool={calculatorPool}
        isOpen={!!calculatorPool}
        onClose={() => setCalculatorPool(null)}
      />

      <DepositModal
        pool={depositPool}
        isOpen={!!depositPool}
        onClose={() => setDepositPool(null)}
        onConfirm={(pool, amount, slippage) => {
          onDeposit?.(pool, amount, slippage)
          setDepositPool(null)
        }}
      />
    </div>
  )
}

export default YieldFarming
