import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Gift,
  Clock,
  DollarSign,
  CheckCircle,
  XCircle,
  AlertCircle,
  Calendar,
  Target,
  Trophy,
  Star,
  StarOff,
  ExternalLink,
  RefreshCw,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  Twitter,
  Globe,
  Users,
  Activity,
  Zap,
  Shield,
  Coins,
  TrendingUp,
  Percent,
  Timer,
  Play,
  Pause,
  Check,
  X,
  Plus,
  Wallet,
  Copy,
  FileText,
  Bell,
  BellOff,
  BarChart3,
  PieChart
} from 'lucide-react'

// Airdrop status types
const AIRDROP_STATUS = {
  UPCOMING: { label: 'Upcoming', color: 'blue', icon: Timer },
  ACTIVE: { label: 'Active', color: 'green', icon: Play },
  CLAIMABLE: { label: 'Claimable', color: 'yellow', icon: Gift },
  CLAIMED: { label: 'Claimed', color: 'gray', icon: Check },
  ENDED: { label: 'Ended', color: 'gray', icon: Pause },
  MISSED: { label: 'Missed', color: 'red', icon: XCircle },
}

// Airdrop categories
const CATEGORIES = {
  DEFI: { label: 'DeFi', color: 'purple' },
  NFT: { label: 'NFT', color: 'pink' },
  GAMING: { label: 'Gaming', color: 'orange' },
  INFRASTRUCTURE: { label: 'Infrastructure', color: 'blue' },
  SOCIAL: { label: 'Social', color: 'green' },
  AI: { label: 'AI', color: 'cyan' },
  MEME: { label: 'Meme', color: 'yellow' },
  OTHER: { label: 'Other', color: 'gray' },
}

// Eligibility criteria types
const CRITERIA_TYPES = {
  WALLET_AGE: { label: 'Wallet Age', icon: Clock },
  TX_COUNT: { label: 'Transaction Count', icon: Activity },
  BALANCE: { label: 'Min Balance', icon: Wallet },
  NFT_HOLD: { label: 'NFT Holder', icon: Gift },
  STAKING: { label: 'Staking', icon: Shield },
  PROTOCOL_USE: { label: 'Protocol Usage', icon: Target },
  SOCIAL: { label: 'Social Task', icon: Twitter },
  TESTNET: { label: 'Testnet Activity', icon: Zap },
  GOVERNANCE: { label: 'Governance', icon: Users },
}

// Helper functions
function formatNumber(num, decimals = 2) {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(decimals)}B`
  if (num >= 1000000) return `${(num / 1000000).toFixed(decimals)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(decimals)}K`
  return num.toFixed(decimals)
}

function formatDate(date) {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatTimeRemaining(endDate) {
  const now = Date.now()
  const end = new Date(endDate).getTime()
  const diff = end - now

  if (diff < 0) return 'Ended'

  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))

  if (days > 0) return `${days}d ${hours}h left`
  if (hours > 0) return `${hours}h left`
  return 'Ending soon'
}

// Copy Button Component
function CopyButton({ text, className = '' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className={`p-1 hover:bg-gray-700 rounded transition-colors ${className}`}
    >
      {copied ? (
        <Check className="w-3 h-3 text-green-400" />
      ) : (
        <Copy className="w-3 h-3 text-gray-400" />
      )}
    </button>
  )
}

// Eligibility Progress Component
function EligibilityProgress({ criteria = [], userProgress = {} }) {
  const completedCount = criteria.filter(c => userProgress[c.id]?.completed).length
  const progressPercent = criteria.length > 0 ? (completedCount / criteria.length) * 100 : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-gray-400">Eligibility Progress</span>
        <span className="text-sm font-medium">{completedCount}/{criteria.length}</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${
            progressPercent >= 100 ? 'bg-green-500' :
            progressPercent >= 50 ? 'bg-yellow-500' : 'bg-blue-500'
          }`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>
    </div>
  )
}

// Criteria Checklist Component
function CriteriaChecklist({ criteria = [], userProgress = {}, onComplete }) {
  return (
    <div className="space-y-2">
      {criteria.map((criterion, i) => {
        const criteriaType = CRITERIA_TYPES[criterion.type] || { label: criterion.type, icon: Target }
        const CriteriaIcon = criteriaType.icon
        const isCompleted = userProgress[criterion.id]?.completed

        return (
          <div
            key={i}
            className={`flex items-center gap-3 p-2 rounded-lg ${
              isCompleted ? 'bg-green-500/10 border border-green-500/20' : 'bg-gray-900 border border-gray-700'
            }`}
          >
            <button
              onClick={() => onComplete?.(criterion.id, !isCompleted)}
              className={`w-5 h-5 rounded border flex items-center justify-center ${
                isCompleted
                  ? 'bg-green-500 border-green-500'
                  : 'border-gray-500 hover:border-green-500'
              }`}
            >
              {isCompleted && <Check className="w-3 h-3 text-white" />}
            </button>
            <CriteriaIcon className={`w-4 h-4 ${isCompleted ? 'text-green-400' : 'text-gray-400'}`} />
            <div className="flex-1">
              <div className={`text-sm ${isCompleted ? 'text-green-400' : 'text-white'}`}>
                {criterion.label}
              </div>
              {criterion.description && (
                <div className="text-xs text-gray-500">{criterion.description}</div>
              )}
            </div>
            {criterion.link && (
              <a
                href={criterion.link}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1 text-gray-400 hover:text-white"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>
        )
      })}
    </div>
  )
}

// Airdrop Card Component
function AirdropCard({ airdrop, onTrack, isTracked, onUpdateProgress, userProgress = {} }) {
  const [expanded, setExpanded] = useState(false)
  const status = AIRDROP_STATUS[airdrop.status] || AIRDROP_STATUS.UPCOMING
  const StatusIcon = status.icon
  const category = CATEGORIES[airdrop.category] || CATEGORIES.OTHER

  const eligibilityPercent = airdrop.criteria?.length > 0
    ? (airdrop.criteria.filter(c => userProgress[c.id]?.completed).length / airdrop.criteria.length) * 100
    : 0

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden hover:border-gray-600 transition-colors">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            {airdrop.logo ? (
              <img src={airdrop.logo} alt={airdrop.name} className="w-12 h-12 rounded-xl" />
            ) : (
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                <Gift className="w-6 h-6 text-white" />
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{airdrop.name}</h3>
                <span
                  className="px-1.5 py-0.5 rounded text-xs"
                  style={{ backgroundColor: `${category.color === 'purple' ? '#a855f7' : category.color === 'pink' ? '#ec4899' : category.color === 'orange' ? '#f97316' : category.color === 'blue' ? '#3b82f6' : category.color === 'green' ? '#22c55e' : category.color === 'cyan' ? '#06b6d4' : category.color === 'yellow' ? '#eab308' : '#6b7280'}20` }}
                >
                  <span style={{ color: category.color === 'purple' ? '#a855f7' : category.color === 'pink' ? '#ec4899' : category.color === 'orange' ? '#f97316' : category.color === 'blue' ? '#3b82f6' : category.color === 'green' ? '#22c55e' : category.color === 'cyan' ? '#06b6d4' : category.color === 'yellow' ? '#eab308' : '#6b7280' }}>
                    {category.label}
                  </span>
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span
                  className="flex items-center gap-1 px-1.5 py-0.5 rounded"
                  style={{ backgroundColor: `${status.color === 'green' ? '#22c55e' : status.color === 'blue' ? '#3b82f6' : status.color === 'yellow' ? '#eab308' : status.color === 'red' ? '#ef4444' : '#6b7280'}20` }}
                >
                  <StatusIcon className="w-3 h-3" style={{ color: status.color === 'green' ? '#22c55e' : status.color === 'blue' ? '#3b82f6' : status.color === 'yellow' ? '#eab308' : status.color === 'red' ? '#ef4444' : '#6b7280' }} />
                  <span style={{ color: status.color === 'green' ? '#22c55e' : status.color === 'blue' ? '#3b82f6' : status.color === 'yellow' ? '#eab308' : status.color === 'red' ? '#ef4444' : '#6b7280' }}>
                    {status.label}
                  </span>
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={() => onTrack?.(airdrop.id)}
            className={`p-2 rounded-lg ${
              isTracked ? 'text-yellow-400 bg-yellow-500/20' : 'text-gray-400 hover:text-yellow-400 bg-gray-700'
            }`}
          >
            {isTracked ? <Star className="w-5 h-5 fill-yellow-400" /> : <StarOff className="w-5 h-5" />}
          </button>
        </div>

        {/* Description */}
        <p className="text-sm text-gray-400 mb-3 line-clamp-2">{airdrop.description}</p>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div className="bg-gray-900 rounded-lg p-2 text-center">
            <div className="text-xs text-gray-500">Est. Value</div>
            <div className="font-bold text-green-400">
              {airdrop.estimatedValue ? `$${formatNumber(airdrop.estimatedValue)}` : 'TBD'}
            </div>
          </div>
          <div className="bg-gray-900 rounded-lg p-2 text-center">
            <div className="text-xs text-gray-500">Participants</div>
            <div className="font-bold">{formatNumber(airdrop.participants || 0)}</div>
          </div>
          <div className="bg-gray-900 rounded-lg p-2 text-center">
            <div className="text-xs text-gray-500">Ends</div>
            <div className="font-bold text-sm">
              {airdrop.endDate ? formatTimeRemaining(airdrop.endDate) : 'TBD'}
            </div>
          </div>
        </div>

        {/* Eligibility Progress */}
        {airdrop.criteria && airdrop.criteria.length > 0 && (
          <div className="mb-3">
            <EligibilityProgress criteria={airdrop.criteria} userProgress={userProgress} />
          </div>
        )}

        {/* Social Links */}
        <div className="flex items-center gap-2 mb-3">
          {airdrop.twitter && (
            <a
              href={airdrop.twitter}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <Twitter className="w-4 h-4 text-blue-400" />
            </a>
          )}
          {airdrop.website && (
            <a
              href={airdrop.website}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <Globe className="w-4 h-4 text-gray-400" />
            </a>
          )}
          {airdrop.discord && (
            <a
              href={airdrop.discord}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <Users className="w-4 h-4 text-purple-400" />
            </a>
          )}
          {airdrop.docs && (
            <a
              href={airdrop.docs}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <FileText className="w-4 h-4 text-gray-400" />
            </a>
          )}
          <div className="flex-1" />
          {eligibilityPercent >= 100 && airdrop.status === 'CLAIMABLE' && (
            <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs font-medium">
              Ready to Claim!
            </span>
          )}
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          {airdrop.status === 'CLAIMABLE' && eligibilityPercent >= 100 && (
            <a
              href={airdrop.claimUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors flex items-center justify-center gap-2"
            >
              <Gift className="w-4 h-4" />
              Claim Now
            </a>
          )}
          {airdrop.status === 'ACTIVE' && (
            <a
              href={airdrop.participateUrl || airdrop.website}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors flex items-center justify-center gap-2"
            >
              <Zap className="w-4 h-4" />
              Participate
            </a>
          )}
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors flex items-center justify-center gap-2"
          >
            {expanded ? 'Hide Details' : 'Show Details'}
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 bg-gray-900/50">
          {/* Dates */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Start Date</div>
              <div className="font-medium">{airdrop.startDate ? formatDate(airdrop.startDate) : 'TBD'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">End Date</div>
              <div className="font-medium">{airdrop.endDate ? formatDate(airdrop.endDate) : 'TBD'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Claim Start</div>
              <div className="font-medium">{airdrop.claimStartDate ? formatDate(airdrop.claimStartDate) : 'TBD'}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Claim End</div>
              <div className="font-medium">{airdrop.claimEndDate ? formatDate(airdrop.claimEndDate) : 'TBD'}</div>
            </div>
          </div>

          {/* Token Info */}
          {airdrop.tokenInfo && (
            <div className="bg-gray-800 rounded-lg p-3 mb-4">
              <div className="text-sm text-gray-400 mb-2">Token Details</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-gray-500">Symbol:</span> {airdrop.tokenInfo.symbol}
                </div>
                <div>
                  <span className="text-gray-500">Total Supply:</span> {formatNumber(airdrop.tokenInfo.totalSupply || 0)}
                </div>
                <div>
                  <span className="text-gray-500">Airdrop %:</span> {airdrop.tokenInfo.airdropPercent || 'TBD'}%
                </div>
                <div>
                  <span className="text-gray-500">Vesting:</span> {airdrop.tokenInfo.vesting || 'None'}
                </div>
              </div>
            </div>
          )}

          {/* Eligibility Criteria */}
          {airdrop.criteria && airdrop.criteria.length > 0 && (
            <div className="mb-4">
              <div className="text-sm text-gray-400 mb-2">Eligibility Criteria</div>
              <CriteriaChecklist
                criteria={airdrop.criteria}
                userProgress={userProgress}
                onComplete={(criteriaId, completed) => onUpdateProgress?.(airdrop.id, criteriaId, completed)}
              />
            </div>
          )}

          {/* Notes */}
          {airdrop.notes && (
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                <p className="text-sm text-yellow-200">{airdrop.notes}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Stats Summary Component
function AirdropStats({ airdrops, trackedIds }) {
  const stats = useMemo(() => {
    const tracked = airdrops.filter(a => trackedIds.has(a.id))
    const claimable = airdrops.filter(a => a.status === 'CLAIMABLE')
    const active = airdrops.filter(a => a.status === 'ACTIVE')
    const upcoming = airdrops.filter(a => a.status === 'UPCOMING')
    const totalValue = airdrops.reduce((sum, a) => sum + (a.estimatedValue || 0), 0)
    const claimableValue = claimable.reduce((sum, a) => sum + (a.estimatedValue || 0), 0)

    return {
      total: airdrops.length,
      tracked: tracked.length,
      claimable: claimable.length,
      active: active.length,
      upcoming: upcoming.length,
      totalValue,
      claimableValue,
    }
  }, [airdrops, trackedIds])

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Tracked</div>
        <div className="text-2xl font-bold text-yellow-400">{stats.tracked}</div>
        <div className="text-xs text-gray-500">{stats.total} total airdrops</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Ready to Claim</div>
        <div className="text-2xl font-bold text-green-400">{stats.claimable}</div>
        <div className="text-xs text-gray-500">${formatNumber(stats.claimableValue)} value</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Active Now</div>
        <div className="text-2xl font-bold text-blue-400">{stats.active}</div>
        <div className="text-xs text-gray-500">{stats.upcoming} upcoming</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total Est. Value</div>
        <div className="text-2xl font-bold">${formatNumber(stats.totalValue)}</div>
      </div>
    </div>
  )
}

// Main Airdrop Tracker Component
export function AirdropTracker({
  airdrops = [],
  onRefresh,
  onTrack,
  onUpdateProgress,
  trackedIds = [],
  userProgress = {},
  isLoading = false,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [sortBy, setSortBy] = useState('endDate')
  const [sortOrder, setSortOrder] = useState('asc')
  const [showTrackedOnly, setShowTrackedOnly] = useState(false)
  const [trackedSet, setTrackedSet] = useState(new Set(trackedIds))

  // Update tracked set when prop changes
  useEffect(() => {
    setTrackedSet(new Set(trackedIds))
  }, [trackedIds])

  // Filter and sort airdrops
  const filteredAirdrops = useMemo(() => {
    let result = [...airdrops]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(a =>
        a.name.toLowerCase().includes(query) ||
        a.description?.toLowerCase().includes(query)
      )
    }

    // Category filter
    if (selectedCategory !== 'all') {
      result = result.filter(a => a.category === selectedCategory)
    }

    // Status filter
    if (selectedStatus !== 'all') {
      result = result.filter(a => a.status === selectedStatus)
    }

    // Tracked filter
    if (showTrackedOnly) {
      result = result.filter(a => trackedSet.has(a.id))
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'endDate':
          comparison = new Date(a.endDate || '2099-12-31') - new Date(b.endDate || '2099-12-31')
          break
        case 'value':
          comparison = (a.estimatedValue || 0) - (b.estimatedValue || 0)
          break
        case 'name':
          comparison = a.name.localeCompare(b.name)
          break
        case 'participants':
          comparison = (a.participants || 0) - (b.participants || 0)
          break
        default:
          comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [airdrops, searchQuery, selectedCategory, selectedStatus, sortBy, sortOrder, showTrackedOnly, trackedSet])

  const handleTrack = useCallback((id) => {
    setTrackedSet(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      onTrack?.(id, !prev.has(id))
      return newSet
    })
  }, [onTrack])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-lg">
            <Gift className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Airdrop Tracker</h1>
            <p className="text-sm text-gray-400">Track and manage airdrop opportunities</p>
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
      <AirdropStats airdrops={airdrops} trackedIds={trackedSet} />

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search airdrops..."
              className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          <select
            value={selectedCategory}
            onChange={e => setSelectedCategory(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Categories</option>
            {Object.entries(CATEGORIES).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={e => setSelectedStatus(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Status</option>
            {Object.entries(AIRDROP_STATUS).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Sort:</span>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-sm"
              >
                <option value="endDate">End Date</option>
                <option value="value">Est. Value</option>
                <option value="name">Name</option>
                <option value="participants">Participants</option>
              </select>
              <button
                onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
                className="p-1 bg-gray-700 rounded"
              >
                {sortOrder === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              </button>
            </div>

            <button
              onClick={() => setShowTrackedOnly(!showTrackedOnly)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-sm ${
                showTrackedOnly ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <Star className="w-4 h-4" />
              Tracked Only
            </button>
          </div>

          <div className="text-sm text-gray-400">
            {filteredAirdrops.length} airdrops found
          </div>
        </div>
      </div>

      {/* Airdrop Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredAirdrops.map(airdrop => (
          <AirdropCard
            key={airdrop.id}
            airdrop={airdrop}
            onTrack={handleTrack}
            isTracked={trackedSet.has(airdrop.id)}
            onUpdateProgress={onUpdateProgress}
            userProgress={userProgress[airdrop.id] || {}}
          />
        ))}
      </div>

      {filteredAirdrops.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Gift className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No airdrops found</p>
        </div>
      )}
    </div>
  )
}

export default AirdropTracker
