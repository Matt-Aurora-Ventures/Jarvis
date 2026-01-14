import React, { useState, useMemo, useCallback } from 'react'
import {
  Brain,
  TrendingUp,
  TrendingDown,
  Wallet,
  Star,
  StarOff,
  Bell,
  BellOff,
  Copy,
  Check,
  ExternalLink,
  Filter,
  Search,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Clock,
  DollarSign,
  Percent,
  Target,
  Award,
  Flame,
  Zap,
  Eye,
  EyeOff,
  Users,
  Building,
  UserCheck,
  Shield,
  X,
  ArrowUpRight,
  ArrowDownLeft,
  ArrowLeftRight,
  BarChart3
} from 'lucide-react'

// Wallet categories
const WALLET_CATEGORIES = {
  VC: { label: 'VC Fund', icon: Building, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  WHALE: { label: 'Whale', icon: Wallet, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  DEV: { label: 'Developer', icon: Shield, color: 'text-green-400', bg: 'bg-green-400/10' },
  INFLUENCER: { label: 'Influencer', icon: UserCheck, color: 'text-pink-400', bg: 'bg-pink-400/10' },
  TRADER: { label: 'Top Trader', icon: Target, color: 'text-orange-400', bg: 'bg-orange-400/10' },
  INSIDER: { label: 'Insider', icon: Eye, color: 'text-red-400', bg: 'bg-red-400/10' },
  MM: { label: 'Market Maker', icon: BarChart3, color: 'text-cyan-400', bg: 'bg-cyan-400/10' },
  UNKNOWN: { label: 'Unknown', icon: Users, color: 'text-slate-400', bg: 'bg-slate-400/10' }
}

// Trade types
const TRADE_TYPES = {
  BUY: { label: 'Buy', icon: ArrowDownLeft, color: 'text-green-400' },
  SELL: { label: 'Sell', icon: ArrowUpRight, color: 'text-red-400' },
  SWAP: { label: 'Swap', icon: ArrowLeftRight, color: 'text-blue-400' }
}

// Performance tiers
const PERFORMANCE_TIERS = {
  LEGENDARY: { label: 'Legendary', color: 'text-yellow-400', bg: 'bg-yellow-400/10', minWinRate: 80 },
  ELITE: { label: 'Elite', color: 'text-purple-400', bg: 'bg-purple-400/10', minWinRate: 70 },
  SKILLED: { label: 'Skilled', color: 'text-blue-400', bg: 'bg-blue-400/10', minWinRate: 60 },
  AVERAGE: { label: 'Average', color: 'text-slate-400', bg: 'bg-slate-400/10', minWinRate: 0 }
}

// Mock smart wallets data
const mockSmartWallets = [
  {
    id: 'w1',
    address: '7xKq2mNp3YzT8vRs5WqL9jKm4NxP2qRt6vXy',
    label: 'Alameda Research (Legacy)',
    category: 'VC',
    isVerified: true,
    isFollowing: true,
    hasAlerts: true,
    stats: {
      winRate: 82,
      avgRoi: 156,
      totalTrades: 1247,
      totalPnl: 12500000,
      avgHoldTime: '4.2 days',
      bestTrade: { token: 'SOL', roi: 2400 },
      recentAccuracy: 85
    },
    trades: [
      { token: 'WIF', type: 'BUY', amount: 500000, value: 1250000, time: Date.now() - 1000 * 60 * 30 },
      { token: 'JUP', type: 'SELL', amount: 100000, value: 90000, time: Date.now() - 1000 * 60 * 60 * 2 }
    ]
  },
  {
    id: 'w2',
    address: '9PqR4mNx5TyU8wSt6XrM2kLn7QyV3sZa8bCd',
    label: 'Multicoin Capital',
    category: 'VC',
    isVerified: true,
    isFollowing: true,
    hasAlerts: false,
    stats: {
      winRate: 78,
      avgRoi: 124,
      totalTrades: 892,
      totalPnl: 8900000,
      avgHoldTime: '12 days',
      bestTrade: { token: 'BONK', roi: 1800 },
      recentAccuracy: 72
    },
    trades: [
      { token: 'PYTH', type: 'BUY', amount: 250000, value: 95000, time: Date.now() - 1000 * 60 * 60 }
    ]
  },
  {
    id: 'w3',
    address: '3KmL8xYz2WvQ7nRp4TsJ6mHg9CxF5kBd1eAw',
    label: 'GigaChad Whale',
    category: 'WHALE',
    isVerified: false,
    isFollowing: false,
    hasAlerts: false,
    stats: {
      winRate: 74,
      avgRoi: 89,
      totalTrades: 3421,
      totalPnl: 45000000,
      avgHoldTime: '2.1 days',
      bestTrade: { token: 'RNDR', roi: 890 },
      recentAccuracy: 68
    },
    trades: [
      { token: 'RENDER', type: 'BUY', amount: 50000, value: 425000, time: Date.now() - 1000 * 60 * 15 },
      { token: 'SOL', type: 'SELL', amount: 10000, value: 1800000, time: Date.now() - 1000 * 60 * 45 }
    ]
  },
  {
    id: 'w4',
    address: '5UxV7nMa4BcD9eRq2YtK8wLj6PxN3sGh7iOm',
    label: 'Ansem',
    category: 'INFLUENCER',
    isVerified: true,
    isFollowing: true,
    hasAlerts: true,
    stats: {
      winRate: 71,
      avgRoi: 234,
      totalTrades: 567,
      totalPnl: 5600000,
      avgHoldTime: '6 hours',
      bestTrade: { token: 'WIF', roi: 4500 },
      recentAccuracy: 75
    },
    trades: [
      { token: 'POPCAT', type: 'BUY', amount: 10000000, value: 85000, time: Date.now() - 1000 * 60 * 5 }
    ]
  },
  {
    id: 'w5',
    address: '8HjK3nPo6QrS9tUv2WxY4zAb5cDe7fGh8iJk',
    label: 'Jump Trading',
    category: 'MM',
    isVerified: true,
    isFollowing: false,
    hasAlerts: false,
    stats: {
      winRate: 68,
      avgRoi: 12,
      totalTrades: 89432,
      totalPnl: 156000000,
      avgHoldTime: '45 min',
      bestTrade: { token: 'ETH', roi: 45 },
      recentAccuracy: 71
    },
    trades: [
      { token: 'SOL', type: 'SWAP', amount: 100000, value: 18000000, time: Date.now() - 1000 * 60 * 2 },
      { token: 'USDC', type: 'SWAP', amount: 5000000, value: 5000000, time: Date.now() - 1000 * 60 * 3 }
    ]
  },
  {
    id: 'w6',
    address: '1AbC4dEf7gHi8jKl2mNo3pQr4sTu5vWx6yZa',
    label: 'Early SOL Dev',
    category: 'DEV',
    isVerified: true,
    isFollowing: false,
    hasAlerts: false,
    stats: {
      winRate: 85,
      avgRoi: 567,
      totalTrades: 124,
      totalPnl: 78000000,
      avgHoldTime: '180 days',
      bestTrade: { token: 'SOL', roi: 12000 },
      recentAccuracy: 90
    },
    trades: []
  },
  {
    id: 'w7',
    address: '2BcD5eFg8hIj9kLm0nOp1qRs2tUv3wXy4zA5',
    label: 'Degen Alpha Caller',
    category: 'TRADER',
    isVerified: false,
    isFollowing: true,
    hasAlerts: true,
    stats: {
      winRate: 62,
      avgRoi: 345,
      totalTrades: 2341,
      totalPnl: 2300000,
      avgHoldTime: '3 hours',
      bestTrade: { token: 'BOME', roi: 8900 },
      recentAccuracy: 58
    },
    trades: [
      { token: 'MICHI', type: 'BUY', amount: 50000000, value: 45000, time: Date.now() - 1000 * 60 * 8 },
      { token: 'SLERF', type: 'SELL', amount: 100000000, value: 32000, time: Date.now() - 1000 * 60 * 25 }
    ]
  },
  {
    id: 'w8',
    address: '4DeF6gHi9jKl0mNo2pQr3sTu4vWx5yZa6bCd',
    label: 'Suspicious Wallet',
    category: 'INSIDER',
    isVerified: false,
    isFollowing: false,
    hasAlerts: false,
    stats: {
      winRate: 92,
      avgRoi: 456,
      totalTrades: 45,
      totalPnl: 890000,
      avgHoldTime: '15 min',
      bestTrade: { token: 'ZEUS', roi: 2300 },
      recentAccuracy: 95
    },
    trades: [
      { token: 'NEW_TOKEN', type: 'BUY', amount: 10000000000, value: 5000, time: Date.now() - 1000 * 60 * 1 }
    ]
  }
]

// Format helpers
const formatAddress = (address) => `${address.slice(0, 6)}...${address.slice(-4)}`
const formatNumber = (num) => {
  if (num >= 1000000000) return `$${(num / 1000000000).toFixed(2)}B`
  if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
  if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`
  return `$${num.toFixed(2)}`
}
const formatTime = (timestamp) => {
  const diff = Date.now() - timestamp
  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return `${Math.floor(diff / 86400000)}d ago`
}

// Get performance tier
const getPerformanceTier = (winRate) => {
  if (winRate >= PERFORMANCE_TIERS.LEGENDARY.minWinRate) return PERFORMANCE_TIERS.LEGENDARY
  if (winRate >= PERFORMANCE_TIERS.ELITE.minWinRate) return PERFORMANCE_TIERS.ELITE
  if (winRate >= PERFORMANCE_TIERS.SKILLED.minWinRate) return PERFORMANCE_TIERS.SKILLED
  return PERFORMANCE_TIERS.AVERAGE
}

// Category badge
const CategoryBadge = ({ category }) => {
  const cat = WALLET_CATEGORIES[category] || WALLET_CATEGORIES.UNKNOWN
  const IconComponent = cat.icon

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${cat.bg} ${cat.color}`}>
      <IconComponent size={12} />
      {cat.label}
    </span>
  )
}

// Performance badge
const PerformanceBadge = ({ winRate }) => {
  const tier = getPerformanceTier(winRate)

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${tier.bg} ${tier.color}`}>
      {tier.label}
    </span>
  )
}

// Copy button
const CopyButton = ({ text }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Copy failed:', err)
    }
  }

  return (
    <button onClick={handleCopy} className="p-1 hover:bg-white/10 rounded">
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} className="text-slate-400" />}
    </button>
  )
}

// Recent trade row
const TradeRow = ({ trade }) => {
  const tradeType = TRADE_TYPES[trade.type]
  const IconComponent = tradeType.icon

  return (
    <div className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
      <div className="flex items-center gap-2">
        <IconComponent size={14} className={tradeType.color} />
        <span className="font-medium text-white">{trade.token}</span>
        <span className="text-xs text-slate-500">{formatTime(trade.time)}</span>
      </div>
      <div className="text-right">
        <div className={`text-sm ${tradeType.color}`}>
          {formatNumber(trade.value)}
        </div>
      </div>
    </div>
  )
}

// Wallet card component
const WalletCard = ({ wallet, onToggleFollow, onToggleAlerts, onSelect, isSelected }) => {
  const [expanded, setExpanded] = useState(false)
  const tier = getPerformanceTier(wallet.stats.winRate)

  return (
    <div
      className={`bg-white/5 rounded-xl border transition-all cursor-pointer ${
        isSelected ? 'border-blue-500 ring-1 ring-blue-500' : 'border-white/10 hover:border-white/20'
      }`}
      onClick={() => onSelect(wallet.id)}
    >
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${tier.bg}`}>
              <Brain size={20} className={tier.color} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">{wallet.label || formatAddress(wallet.address)}</span>
                {wallet.isVerified && (
                  <Shield size={14} className="text-blue-400" title="Verified" />
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-slate-500 font-mono">{formatAddress(wallet.address)}</span>
                <CopyButton text={wallet.address} />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); onToggleFollow(wallet.id) }}
              className={`p-1.5 rounded hover:bg-white/10 ${wallet.isFollowing ? 'text-yellow-400' : 'text-slate-500'}`}
              title={wallet.isFollowing ? 'Unfollow' : 'Follow'}
            >
              {wallet.isFollowing ? <Star size={16} /> : <StarOff size={16} />}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onToggleAlerts(wallet.id) }}
              className={`p-1.5 rounded hover:bg-white/10 ${wallet.hasAlerts ? 'text-green-400' : 'text-slate-500'}`}
              title={wallet.hasAlerts ? 'Disable alerts' : 'Enable alerts'}
            >
              {wallet.hasAlerts ? <Bell size={16} /> : <BellOff size={16} />}
            </button>
          </div>
        </div>

        {/* Badges */}
        <div className="flex items-center gap-2 mb-4">
          <CategoryBadge category={wallet.category} />
          <PerformanceBadge winRate={wallet.stats.winRate} />
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-4 gap-3">
          <div className="text-center">
            <div className="text-lg font-bold text-green-400">{wallet.stats.winRate}%</div>
            <div className="text-xs text-slate-500">Win Rate</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-blue-400">{wallet.stats.avgRoi}%</div>
            <div className="text-xs text-slate-500">Avg ROI</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-white">{wallet.stats.totalTrades.toLocaleString()}</div>
            <div className="text-xs text-slate-500">Trades</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-purple-400">{formatNumber(wallet.stats.totalPnl)}</div>
            <div className="text-xs text-slate-500">Total PnL</div>
          </div>
        </div>
      </div>

      {/* Expandable section */}
      <div
        className="px-4 py-2 border-t border-white/5 flex items-center justify-between text-sm text-slate-400 hover:bg-white/5"
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
      >
        <span>{wallet.trades.length} recent trades</span>
        {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </div>

      {expanded && wallet.trades.length > 0 && (
        <div className="px-4 pb-4">
          {wallet.trades.slice(0, 5).map((trade, idx) => (
            <TradeRow key={idx} trade={trade} />
          ))}
        </div>
      )}
    </div>
  )
}

// Live feed component
const LiveFeed = ({ wallets }) => {
  const allTrades = useMemo(() => {
    return wallets
      .flatMap(w => w.trades.map(t => ({ ...t, wallet: w })))
      .sort((a, b) => b.time - a.time)
      .slice(0, 20)
  }, [wallets])

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="font-medium text-white">Live Smart Money Feed</span>
        </div>
        <span className="text-xs text-slate-500">{allTrades.length} recent trades</span>
      </div>

      <div className="max-h-[400px] overflow-y-auto">
        {allTrades.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            No recent trades from followed wallets
          </div>
        ) : (
          allTrades.map((trade, idx) => {
            const tradeType = TRADE_TYPES[trade.type]
            const IconComponent = tradeType.icon
            const tier = getPerformanceTier(trade.wallet.stats.winRate)

            return (
              <div
                key={idx}
                className="p-3 border-b border-white/5 hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-1.5 rounded ${tradeType.color === 'text-green-400' ? 'bg-green-400/10' : tradeType.color === 'text-red-400' ? 'bg-red-400/10' : 'bg-blue-400/10'}`}>
                    <IconComponent size={14} className={tradeType.color} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${tier.color}`}>
                        {trade.wallet.label || formatAddress(trade.wallet.address)}
                      </span>
                      <span className="text-slate-500">{tradeType.label.toLowerCase()}ed</span>
                      <span className="font-medium text-white">{trade.token}</span>
                    </div>
                    <div className="text-xs text-slate-500">{formatTime(trade.time)}</div>
                  </div>

                  <div className="text-right">
                    <div className={`font-medium ${tradeType.color}`}>
                      {formatNumber(trade.value)}
                    </div>
                    <div className="text-xs text-slate-500">
                      {trade.wallet.stats.winRate}% win rate
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

// Stats overview
const StatsOverview = ({ wallets }) => {
  const stats = useMemo(() => {
    const followed = wallets.filter(w => w.isFollowing)
    const avgWinRate = followed.length > 0
      ? followed.reduce((sum, w) => sum + w.stats.winRate, 0) / followed.length
      : 0
    const totalPnl = wallets.reduce((sum, w) => sum + w.stats.totalPnl, 0)
    const recentTrades = wallets.flatMap(w => w.trades).filter(t => Date.now() - t.time < 3600000).length

    return {
      totalWallets: wallets.length,
      followedWallets: followed.length,
      avgWinRate,
      totalPnl,
      recentTrades
    }
  }, [wallets])

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Users size={16} />
          <span className="text-xs">Total Wallets</span>
        </div>
        <div className="text-2xl font-bold text-white">{stats.totalWallets}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Star size={16} />
          <span className="text-xs">Following</span>
        </div>
        <div className="text-2xl font-bold text-yellow-400">{stats.followedWallets}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Target size={16} />
          <span className="text-xs">Avg Win Rate</span>
        </div>
        <div className="text-2xl font-bold text-green-400">{stats.avgWinRate.toFixed(1)}%</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <DollarSign size={16} />
          <span className="text-xs">Total PnL</span>
        </div>
        <div className="text-2xl font-bold text-purple-400">{formatNumber(stats.totalPnl)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="flex items-center gap-2 text-slate-400 mb-2">
          <Zap size={16} />
          <span className="text-xs">Trades (1h)</span>
        </div>
        <div className="text-2xl font-bold text-blue-400">{stats.recentTrades}</div>
      </div>
    </div>
  )
}

// Wallet detail panel
const WalletDetailPanel = ({ wallet, onClose }) => {
  if (!wallet) return null

  const tier = getPerformanceTier(wallet.stats.winRate)

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 className="font-semibold text-white">Wallet Details</h3>
        <button onClick={onClose} className="p-1 hover:bg-white/10 rounded">
          <X size={18} className="text-slate-400" />
        </button>
      </div>

      <div className="p-4 space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-xl ${tier.bg}`}>
            <Brain size={24} className={tier.color} />
          </div>
          <div>
            <div className="font-semibold text-white text-lg">
              {wallet.label || formatAddress(wallet.address)}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500 font-mono">{formatAddress(wallet.address)}</span>
              <CopyButton text={wallet.address} />
              <a
                href={`https://solscan.io/account/${wallet.address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300"
              >
                <ExternalLink size={14} />
              </a>
            </div>
          </div>
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2">
          <CategoryBadge category={wallet.category} />
          <PerformanceBadge winRate={wallet.stats.winRate} />
          {wallet.isVerified && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-400/10 text-blue-400">
              <Shield size={12} />
              Verified
            </span>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Win Rate</div>
            <div className="text-xl font-bold text-green-400">{wallet.stats.winRate}%</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Avg ROI</div>
            <div className="text-xl font-bold text-blue-400">{wallet.stats.avgRoi}%</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Total Trades</div>
            <div className="text-xl font-bold text-white">{wallet.stats.totalTrades.toLocaleString()}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Total PnL</div>
            <div className="text-xl font-bold text-purple-400">{formatNumber(wallet.stats.totalPnl)}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Avg Hold Time</div>
            <div className="text-xl font-bold text-white">{wallet.stats.avgHoldTime}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Recent Accuracy</div>
            <div className="text-xl font-bold text-yellow-400">{wallet.stats.recentAccuracy}%</div>
          </div>
        </div>

        {/* Best trade */}
        <div className="bg-gradient-to-r from-yellow-400/10 to-orange-400/10 rounded-lg p-3 border border-yellow-400/20">
          <div className="text-xs text-slate-400 mb-1">Best Trade</div>
          <div className="flex items-center justify-between">
            <span className="font-medium text-white">{wallet.stats.bestTrade.token}</span>
            <span className="text-green-400 font-bold">+{wallet.stats.bestTrade.roi}%</span>
          </div>
        </div>

        {/* Recent trades */}
        {wallet.trades.length > 0 && (
          <div>
            <div className="text-sm font-medium text-slate-400 mb-2">Recent Trades</div>
            <div className="space-y-2">
              {wallet.trades.map((trade, idx) => (
                <TradeRow key={idx} trade={trade} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Main SmartMoneyTracker component
export const SmartMoneyTracker = () => {
  const [wallets, setWallets] = useState(mockSmartWallets)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('ALL')
  const [sortBy, setSortBy] = useState('winRate')
  const [showFollowedOnly, setShowFollowedOnly] = useState(false)
  const [selectedWalletId, setSelectedWalletId] = useState(null)

  // Filter and sort wallets
  const filteredWallets = useMemo(() => {
    let result = [...wallets]

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(w =>
        w.address.toLowerCase().includes(query) ||
        w.label?.toLowerCase().includes(query) ||
        WALLET_CATEGORIES[w.category]?.label.toLowerCase().includes(query)
      )
    }

    // Category filter
    if (selectedCategory !== 'ALL') {
      result = result.filter(w => w.category === selectedCategory)
    }

    // Following filter
    if (showFollowedOnly) {
      result = result.filter(w => w.isFollowing)
    }

    // Sort
    result.sort((a, b) => {
      switch (sortBy) {
        case 'winRate':
          return b.stats.winRate - a.stats.winRate
        case 'pnl':
          return b.stats.totalPnl - a.stats.totalPnl
        case 'roi':
          return b.stats.avgRoi - a.stats.avgRoi
        case 'trades':
          return b.stats.totalTrades - a.stats.totalTrades
        case 'recent':
          const aTime = a.trades[0]?.time || 0
          const bTime = b.trades[0]?.time || 0
          return bTime - aTime
        default:
          return b.stats.winRate - a.stats.winRate
      }
    })

    return result
  }, [wallets, searchQuery, selectedCategory, sortBy, showFollowedOnly])

  const selectedWallet = useMemo(() =>
    wallets.find(w => w.id === selectedWalletId),
    [wallets, selectedWalletId]
  )

  const handleToggleFollow = useCallback((walletId) => {
    setWallets(prev => prev.map(w =>
      w.id === walletId ? { ...w, isFollowing: !w.isFollowing } : w
    ))
  }, [])

  const handleToggleAlerts = useCallback((walletId) => {
    setWallets(prev => prev.map(w =>
      w.id === walletId ? { ...w, hasAlerts: !w.hasAlerts } : w
    ))
  }, [])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Brain className="text-purple-400" />
              Smart Money Tracker
            </h1>
            <p className="text-slate-400">Track and copy the smartest wallets on Solana</p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowFollowedOnly(!showFollowedOnly)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                showFollowedOnly
                  ? 'bg-yellow-400/20 text-yellow-400 border border-yellow-400'
                  : 'bg-white/5 hover:bg-white/10 border border-white/10'
              }`}
            >
              <Star size={18} />
              <span>Following</span>
            </button>
            <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Stats overview */}
        <StatsOverview wallets={wallets} />

        {/* Filters */}
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search wallets..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Category filter */}
          <div className="flex gap-2 overflow-x-auto pb-2">
            <button
              onClick={() => setSelectedCategory('ALL')}
              className={`px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
                selectedCategory === 'ALL'
                  ? 'bg-blue-500 text-white'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10'
              }`}
            >
              All
            </button>
            {Object.entries(WALLET_CATEGORIES).map(([key, value]) => (
              <button
                key={key}
                onClick={() => setSelectedCategory(key)}
                className={`px-4 py-2 rounded-lg whitespace-nowrap transition-colors ${
                  selectedCategory === key
                    ? `${value.bg} ${value.color} border border-current`
                    : 'bg-white/5 text-slate-400 hover:bg-white/10'
                }`}
              >
                {value.label}
              </button>
            ))}
          </div>

          {/* Sort */}
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white appearance-none cursor-pointer"
          >
            <option value="winRate">Win Rate</option>
            <option value="pnl">Total PnL</option>
            <option value="roi">Avg ROI</option>
            <option value="trades">Trade Count</option>
            <option value="recent">Recent Activity</option>
          </select>
        </div>

        {/* Main content */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Wallet grid */}
          <div className="lg:col-span-2 space-y-4">
            {filteredWallets.length === 0 ? (
              <div className="bg-white/5 rounded-xl p-12 text-center border border-white/10">
                <Users size={48} className="mx-auto mb-4 text-slate-600" />
                <div className="text-lg text-slate-400 mb-2">No wallets found</div>
                <div className="text-sm text-slate-500">
                  Try adjusting your search or filters
                </div>
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                {filteredWallets.map(wallet => (
                  <WalletCard
                    key={wallet.id}
                    wallet={wallet}
                    onToggleFollow={handleToggleFollow}
                    onToggleAlerts={handleToggleAlerts}
                    onSelect={setSelectedWalletId}
                    isSelected={selectedWalletId === wallet.id}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Wallet detail or live feed */}
            {selectedWallet ? (
              <WalletDetailPanel
                wallet={selectedWallet}
                onClose={() => setSelectedWalletId(null)}
              />
            ) : (
              <LiveFeed wallets={wallets.filter(w => w.isFollowing)} />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SmartMoneyTracker
