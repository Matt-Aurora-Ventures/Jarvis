import React, { useState, useMemo } from 'react'
import {
  Unlock,
  Lock,
  Calendar,
  Clock,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  DollarSign,
  Percent,
  RefreshCw,
  Search,
  Filter,
  Bell,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Info,
  BarChart3,
  Users,
  Coins,
  CalendarDays
} from 'lucide-react'

// Impact levels
const IMPACT_LEVELS = {
  LOW: { label: 'Low', color: 'text-green-400', bg: 'bg-green-400/10' },
  MEDIUM: { label: 'Medium', color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  HIGH: { label: 'High', color: 'text-orange-400', bg: 'bg-orange-400/10' },
  CRITICAL: { label: 'Critical', color: 'text-red-400', bg: 'bg-red-400/10' }
}

// Unlock types
const UNLOCK_TYPES = {
  CLIFF: { label: 'Cliff', color: 'text-red-400' },
  LINEAR: { label: 'Linear', color: 'text-blue-400' },
  MILESTONE: { label: 'Milestone', color: 'text-purple-400' },
  TGE: { label: 'TGE', color: 'text-yellow-400' }
}

// Recipient types
const RECIPIENT_TYPES = {
  TEAM: { label: 'Team', color: 'text-purple-400' },
  INVESTORS: { label: 'Investors', color: 'text-blue-400' },
  ECOSYSTEM: { label: 'Ecosystem', color: 'text-green-400' },
  TREASURY: { label: 'Treasury', color: 'text-yellow-400' },
  COMMUNITY: { label: 'Community', color: 'text-cyan-400' },
  ADVISORS: { label: 'Advisors', color: 'text-pink-400' }
}

// Mock unlock events
const mockUnlocks = [
  {
    id: 'u1',
    token: 'ARB',
    tokenName: 'Arbitrum',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 2,
    unlockAmount: 92650000,
    unlockValue: 83385000,
    percentOfCirculating: 3.2,
    percentOfTotalSupply: 0.93,
    unlockType: 'LINEAR',
    recipient: 'TEAM',
    impact: 'HIGH',
    priceAtLastUnlock: 0.95,
    currentPrice: 0.90,
    historicalImpact: -5.2,
    description: 'Team and advisor tokens vesting release'
  },
  {
    id: 'u2',
    token: 'APT',
    tokenName: 'Aptos',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 5,
    unlockAmount: 11310000,
    unlockValue: 113100000,
    percentOfCirculating: 2.8,
    percentOfTotalSupply: 1.13,
    unlockType: 'CLIFF',
    recipient: 'INVESTORS',
    impact: 'HIGH',
    priceAtLastUnlock: 10.50,
    currentPrice: 10.00,
    historicalImpact: -8.5,
    description: 'Series A investor cliff unlock'
  },
  {
    id: 'u3',
    token: 'OP',
    tokenName: 'Optimism',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 8,
    unlockAmount: 31340000,
    unlockValue: 75216000,
    percentOfCirculating: 2.1,
    percentOfTotalSupply: 0.73,
    unlockType: 'LINEAR',
    recipient: 'ECOSYSTEM',
    impact: 'MEDIUM',
    priceAtLastUnlock: 2.50,
    currentPrice: 2.40,
    historicalImpact: -3.1,
    description: 'Ecosystem fund allocation'
  },
  {
    id: 'u4',
    token: 'JUP',
    tokenName: 'Jupiter',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 12,
    unlockAmount: 100000000,
    unlockValue: 90000000,
    percentOfCirculating: 7.5,
    percentOfTotalSupply: 1.0,
    unlockType: 'MILESTONE',
    recipient: 'COMMUNITY',
    impact: 'CRITICAL',
    priceAtLastUnlock: 0.95,
    currentPrice: 0.90,
    historicalImpact: -12.5,
    description: 'Community airdrop round 2'
  },
  {
    id: 'u5',
    token: 'STRK',
    tokenName: 'Starknet',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 15,
    unlockAmount: 64000000,
    unlockValue: 89600000,
    percentOfCirculating: 4.5,
    percentOfTotalSupply: 0.64,
    unlockType: 'CLIFF',
    recipient: 'INVESTORS',
    impact: 'HIGH',
    priceAtLastUnlock: 1.50,
    currentPrice: 1.40,
    historicalImpact: -6.8,
    description: 'Early investor tokens unlock'
  },
  {
    id: 'u6',
    token: 'SUI',
    tokenName: 'Sui',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 22,
    unlockAmount: 32000000,
    unlockValue: 128000000,
    percentOfCirculating: 1.2,
    percentOfTotalSupply: 0.32,
    unlockType: 'LINEAR',
    recipient: 'TEAM',
    impact: 'MEDIUM',
    priceAtLastUnlock: 4.20,
    currentPrice: 4.00,
    historicalImpact: -2.8,
    description: 'Team vesting schedule'
  },
  {
    id: 'u7',
    token: 'TIA',
    tokenName: 'Celestia',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 30,
    unlockAmount: 14650000,
    unlockValue: 190450000,
    percentOfCirculating: 5.8,
    percentOfTotalSupply: 1.47,
    unlockType: 'CLIFF',
    recipient: 'INVESTORS',
    impact: 'CRITICAL',
    priceAtLastUnlock: 14.00,
    currentPrice: 13.00,
    historicalImpact: -15.2,
    description: 'Seed round cliff unlock'
  },
  {
    id: 'u8',
    token: 'PYTH',
    tokenName: 'Pyth Network',
    unlockDate: Date.now() + 1000 * 60 * 60 * 24 * 45,
    unlockAmount: 250000000,
    unlockValue: 100000000,
    percentOfCirculating: 8.2,
    percentOfTotalSupply: 2.5,
    unlockType: 'LINEAR',
    recipient: 'ECOSYSTEM',
    impact: 'HIGH',
    priceAtLastUnlock: 0.42,
    currentPrice: 0.40,
    historicalImpact: -4.5,
    description: 'Publisher rewards and ecosystem fund'
  }
]

// Format helpers
const formatNumber = (num) => {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(2)}B`
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toLocaleString()
}

const formatCurrency = (value) => {
  if (value >= 1000000000) return `$${(value / 1000000000).toFixed(2)}B`
  if (value >= 1000000) return `$${(value / 1000000).toFixed(1)}M`
  if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`
  return `$${value.toFixed(2)}`
}

const formatDate = (timestamp) => {
  return new Date(timestamp).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

const formatTimeUntil = (timestamp) => {
  const diff = timestamp - Date.now()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))

  if (days === 0) return `${hours}h`
  if (days === 1) return '1 day'
  return `${days} days`
}

// Get impact level based on percentage
const getImpactLevel = (percent) => {
  if (percent >= 5) return 'CRITICAL'
  if (percent >= 3) return 'HIGH'
  if (percent >= 1.5) return 'MEDIUM'
  return 'LOW'
}

// Unlock card component
const UnlockCard = ({ unlock, isExpanded, onToggle }) => {
  const impact = IMPACT_LEVELS[unlock.impact]
  const unlockType = UNLOCK_TYPES[unlock.unlockType]
  const recipient = RECIPIENT_TYPES[unlock.recipient]
  const daysUntil = Math.floor((unlock.unlockDate - Date.now()) / (1000 * 60 * 60 * 24))
  const isUrgent = daysUntil <= 7

  return (
    <div className={`bg-white/5 rounded-xl border transition-all ${
      isUrgent ? 'border-orange-500/50' : 'border-white/10'
    }`}>
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center">
              <span className="font-bold text-white">{unlock.token.slice(0, 2)}</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">{unlock.token}</span>
                <span className="text-sm text-slate-500">{unlock.tokenName}</span>
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className={`text-xs px-2 py-0.5 rounded ${impact.bg} ${impact.color}`}>
                  {impact.label} Impact
                </span>
                <span className={`text-xs ${unlockType.color}`}>{unlockType.label}</span>
              </div>
            </div>
          </div>

          <div className="text-right">
            <div className={`text-lg font-bold ${isUrgent ? 'text-orange-400' : 'text-white'}`}>
              {formatTimeUntil(unlock.unlockDate)}
            </div>
            <div className="text-xs text-slate-500">{formatDate(unlock.unlockDate)}</div>
          </div>
        </div>

        {/* Main stats */}
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="bg-white/5 rounded-lg p-2">
            <div className="text-xs text-slate-500">Unlock Amount</div>
            <div className="text-sm font-medium text-white">{formatNumber(unlock.unlockAmount)}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-2">
            <div className="text-xs text-slate-500">Value</div>
            <div className="text-sm font-medium text-green-400">{formatCurrency(unlock.unlockValue)}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-2">
            <div className="text-xs text-slate-500">% Circulating</div>
            <div className={`text-sm font-medium ${unlock.percentOfCirculating >= 5 ? 'text-red-400' : unlock.percentOfCirculating >= 3 ? 'text-yellow-400' : 'text-white'}`}>
              {unlock.percentOfCirculating.toFixed(2)}%
            </div>
          </div>
        </div>

        {/* Recipient */}
        <div className="flex items-center justify-between text-sm mb-3">
          <span className="text-slate-500">Recipient</span>
          <span className={recipient.color}>{recipient.label}</span>
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => onToggle(unlock.id)}
          className="w-full pt-3 border-t border-white/5 flex items-center justify-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
        >
          {isExpanded ? (
            <>
              <span>Show less</span>
              <ChevronUp size={16} />
            </>
          ) : (
            <>
              <span>Show more</span>
              <ChevronDown size={16} />
            </>
          )}
        </button>
      </div>

      {/* Expanded content */}
      {isExpanded && (
        <div className="px-4 pb-4 space-y-3">
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Description</div>
            <div className="text-sm text-slate-300">{unlock.description}</div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">% Total Supply</div>
              <div className="text-sm font-medium text-white">{unlock.percentOfTotalSupply.toFixed(2)}%</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">Historical Impact</div>
              <div className={`text-sm font-medium ${unlock.historicalImpact >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {unlock.historicalImpact >= 0 ? '+' : ''}{unlock.historicalImpact}%
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">Price at Last Unlock</div>
              <div className="text-sm font-medium text-white">${unlock.priceAtLastUnlock.toFixed(2)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <div className="text-xs text-slate-500 mb-1">Current Price</div>
              <div className="text-sm font-medium text-white">${unlock.currentPrice.toFixed(2)}</div>
            </div>
          </div>

          <div className="p-3 bg-yellow-400/10 border border-yellow-400/30 rounded-lg flex items-start gap-2">
            <AlertTriangle size={16} className="text-yellow-400 mt-0.5" />
            <div className="text-sm text-yellow-400">
              Historical data suggests {Math.abs(unlock.historicalImpact).toFixed(1)}% price movement after similar unlocks
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Calendar view
const UnlockCalendar = ({ unlocks }) => {
  const currentDate = new Date()
  const [viewMonth, setViewMonth] = useState(currentDate.getMonth())
  const [viewYear, setViewYear] = useState(currentDate.getFullYear())

  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate()
  const firstDayOfMonth = new Date(viewYear, viewMonth, 1).getDay()

  const unlocksInMonth = unlocks.filter(u => {
    const unlockDate = new Date(u.unlockDate)
    return unlockDate.getMonth() === viewMonth && unlockDate.getFullYear() === viewYear
  })

  const getUnlocksForDay = (day) => {
    return unlocksInMonth.filter(u => new Date(u.unlockDate).getDate() === day)
  }

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-white flex items-center gap-2">
          <CalendarDays size={18} className="text-blue-400" />
          Unlock Calendar
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              if (viewMonth === 0) {
                setViewMonth(11)
                setViewYear(viewYear - 1)
              } else {
                setViewMonth(viewMonth - 1)
              }
            }}
            className="p-1 hover:bg-white/10 rounded"
          >
            <ChevronDown size={16} className="text-slate-400 rotate-90" />
          </button>
          <span className="text-white min-w-[120px] text-center">
            {monthNames[viewMonth]} {viewYear}
          </span>
          <button
            onClick={() => {
              if (viewMonth === 11) {
                setViewMonth(0)
                setViewYear(viewYear + 1)
              } else {
                setViewMonth(viewMonth + 1)
              }
            }}
            className="p-1 hover:bg-white/10 rounded"
          >
            <ChevronDown size={16} className="text-slate-400 -rotate-90" />
          </button>
        </div>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-7 gap-1 mb-2">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
          <div key={day} className="text-xs text-slate-500 text-center py-1">
            {day}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1">
        {/* Empty cells for days before first of month */}
        {Array.from({ length: firstDayOfMonth }).map((_, idx) => (
          <div key={`empty-${idx}`} className="aspect-square" />
        ))}

        {/* Days of month */}
        {Array.from({ length: daysInMonth }).map((_, idx) => {
          const day = idx + 1
          const dayUnlocks = getUnlocksForDay(day)
          const hasUnlock = dayUnlocks.length > 0
          const isToday = day === currentDate.getDate() &&
            viewMonth === currentDate.getMonth() &&
            viewYear === currentDate.getFullYear()

          return (
            <div
              key={day}
              className={`aspect-square rounded-lg p-1 text-center relative ${
                isToday ? 'bg-blue-500/20 border border-blue-500' :
                hasUnlock ? 'bg-orange-500/20 hover:bg-orange-500/30 cursor-pointer' :
                'hover:bg-white/5'
              }`}
            >
              <span className={`text-xs ${isToday ? 'text-blue-400' : 'text-slate-400'}`}>
                {day}
              </span>
              {hasUnlock && (
                <div className="absolute bottom-1 left-1/2 -translate-x-1/2 flex gap-0.5">
                  {dayUnlocks.slice(0, 3).map((u, i) => (
                    <div
                      key={i}
                      className={`w-1.5 h-1.5 rounded-full ${IMPACT_LEVELS[u.impact].color.replace('text-', 'bg-')}`}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center justify-center gap-4 text-xs">
        {Object.entries(IMPACT_LEVELS).map(([key, value]) => (
          <div key={key} className="flex items-center gap-1">
            <div className={`w-2 h-2 rounded-full ${value.color.replace('text-', 'bg-')}`} />
            <span className="text-slate-500">{value.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Stats summary
const StatsSummary = ({ unlocks }) => {
  const stats = useMemo(() => {
    const next7Days = unlocks.filter(u =>
      u.unlockDate - Date.now() <= 7 * 24 * 60 * 60 * 1000 && u.unlockDate > Date.now()
    )
    const next30Days = unlocks.filter(u =>
      u.unlockDate - Date.now() <= 30 * 24 * 60 * 60 * 1000 && u.unlockDate > Date.now()
    )
    const totalValue7d = next7Days.reduce((sum, u) => sum + u.unlockValue, 0)
    const totalValue30d = next30Days.reduce((sum, u) => sum + u.unlockValue, 0)
    const criticalUnlocks = unlocks.filter(u => u.impact === 'CRITICAL').length

    return {
      next7Days: next7Days.length,
      next30Days: next30Days.length,
      totalValue7d,
      totalValue30d,
      criticalUnlocks
    }
  }, [unlocks])

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Clock size={16} />
          <span className="text-xs">Next 7 Days</span>
        </div>
        <div className="text-2xl font-bold text-orange-400">{stats.next7Days}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Calendar size={16} />
          <span className="text-xs">Next 30 Days</span>
        </div>
        <div className="text-2xl font-bold text-white">{stats.next30Days}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <DollarSign size={16} />
          <span className="text-xs">Value (7d)</span>
        </div>
        <div className="text-2xl font-bold text-green-400">{formatCurrency(stats.totalValue7d)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <DollarSign size={16} />
          <span className="text-xs">Value (30d)</span>
        </div>
        <div className="text-2xl font-bold text-blue-400">{formatCurrency(stats.totalValue30d)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <AlertTriangle size={16} />
          <span className="text-xs">Critical</span>
        </div>
        <div className="text-2xl font-bold text-red-400">{stats.criticalUnlocks}</div>
      </div>
    </div>
  )
}

// Main TokenUnlocks component
export const TokenUnlocks = () => {
  const [unlocks] = useState(mockUnlocks)
  const [searchQuery, setSearchQuery] = useState('')
  const [impactFilter, setImpactFilter] = useState('ALL')
  const [recipientFilter, setRecipientFilter] = useState('ALL')
  const [expandedUnlock, setExpandedUnlock] = useState(null)

  // Filter unlocks
  const filteredUnlocks = useMemo(() => {
    let result = [...unlocks]

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(u =>
        u.token.toLowerCase().includes(query) ||
        u.tokenName.toLowerCase().includes(query)
      )
    }

    if (impactFilter !== 'ALL') {
      result = result.filter(u => u.impact === impactFilter)
    }

    if (recipientFilter !== 'ALL') {
      result = result.filter(u => u.recipient === recipientFilter)
    }

    return result.sort((a, b) => a.unlockDate - b.unlockDate)
  }, [unlocks, searchQuery, impactFilter, recipientFilter])

  const handleToggle = (unlockId) => {
    setExpandedUnlock(expandedUnlock === unlockId ? null : unlockId)
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Unlock className="text-orange-400" />
              Token Unlocks
            </h1>
            <p className="text-slate-400">Track upcoming token vesting and unlock events</p>
          </div>

          <div className="flex items-center gap-3">
            <button className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <Bell size={18} />
              <span>Set Alert</span>
            </button>
            <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Stats */}
        <StatsSummary unlocks={unlocks} />

        {/* Filters */}
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search tokens..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Impact filter */}
          <div className="flex gap-2">
            <button
              onClick={() => setImpactFilter('ALL')}
              className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                impactFilter === 'ALL'
                  ? 'bg-blue-500 text-white'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              All
            </button>
            {Object.entries(IMPACT_LEVELS).map(([key, value]) => (
              <button
                key={key}
                onClick={() => setImpactFilter(key)}
                className={`px-4 py-2 rounded-lg text-sm transition-colors ${
                  impactFilter === key
                    ? `${value.bg} ${value.color} border border-current`
                    : 'bg-white/5 text-slate-400 hover:bg-white/10'
                }`}
              >
                {value.label}
              </button>
            ))}
          </div>

          {/* Recipient filter */}
          <select
            value={recipientFilter}
            onChange={(e) => setRecipientFilter(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white appearance-none cursor-pointer"
          >
            <option value="ALL">All Recipients</option>
            {Object.entries(RECIPIENT_TYPES).map(([key, value]) => (
              <option key={key} value={key}>{value.label}</option>
            ))}
          </select>
        </div>

        {/* Main content */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Unlock list */}
          <div className="lg:col-span-2 space-y-4">
            {filteredUnlocks.length === 0 ? (
              <div className="bg-white/5 rounded-xl p-12 text-center border border-white/10">
                <Unlock size={48} className="mx-auto mb-4 text-slate-600" />
                <div className="text-lg text-slate-400 mb-2">No unlocks found</div>
                <div className="text-sm text-slate-500">
                  Try adjusting your filters
                </div>
              </div>
            ) : (
              filteredUnlocks.map(unlock => (
                <UnlockCard
                  key={unlock.id}
                  unlock={unlock}
                  isExpanded={expandedUnlock === unlock.id}
                  onToggle={handleToggle}
                />
              ))
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <UnlockCalendar unlocks={unlocks} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default TokenUnlocks
