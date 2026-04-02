import React, { useState, useMemo, useCallback } from 'react'
import {
  Users, Trophy, Copy, Eye, EyeOff, TrendingUp, TrendingDown, Star,
  Crown, Medal, Award, UserPlus, UserMinus, Activity, Target, Shield,
  Clock, ChevronRight, ExternalLink, Check, X, Filter, Search,
  BarChart3, Zap, AlertCircle, Settings
} from 'lucide-react'

/**
 * SocialTrading - Copy trading and leaderboard features
 *
 * Features:
 * - Trader leaderboards
 * - Copy trading setup
 * - Trader profiles
 * - Performance tracking
 * - Follow/Unfollow traders
 */

// Rank icons
const RANK_ICONS = {
  1: { icon: Crown, color: 'yellow' },
  2: { icon: Medal, color: 'gray' },
  3: { icon: Award, color: 'orange' },
}

// Performance badges
const BADGES = {
  TOP_TRADER: { label: 'Top Trader', color: 'yellow', icon: Trophy },
  CONSISTENT: { label: 'Consistent', color: 'green', icon: Target },
  HIGH_ROI: { label: 'High ROI', color: 'purple', icon: TrendingUp },
  LOW_RISK: { label: 'Low Risk', color: 'blue', icon: Shield },
  VETERAN: { label: 'Veteran', color: 'cyan', icon: Star },
}

/**
 * TraderCard - Display trader profile with stats
 */
function TraderCard({
  trader,
  rank,
  onFollow,
  onCopy,
  onViewProfile,
  isFollowing = false,
  isCopying = false,
  compact = false,
  className = '',
}) {
  const RankIcon = RANK_ICONS[rank]

  const formatPercent = (value) => {
    if (value === undefined || value === null) return '-'
    return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
  }

  const formatNumber = (num) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  return (
    <div className={`bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden hover:border-gray-700 transition-colors ${className}`}>
      <div className="p-4">
        {/* Header */}
        <div className="flex items-start gap-4">
          {/* Rank badge */}
          {rank && rank <= 3 && RankIcon && (
            <div className={`w-10 h-10 rounded-full bg-${RankIcon.color}-500/10 flex items-center justify-center`}>
              <RankIcon.icon className={`w-5 h-5 text-${RankIcon.color}-400`} />
            </div>
          )}
          {rank && rank > 3 && (
            <div className="w-10 h-10 rounded-full bg-gray-800 flex items-center justify-center">
              <span className="text-sm font-medium text-gray-400">#{rank}</span>
            </div>
          )}

          {/* Trader info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <button
                onClick={() => onViewProfile?.(trader)}
                className="font-semibold text-white hover:text-purple-400 transition-colors truncate"
              >
                {trader.displayName || trader.address?.slice(0, 8)}
              </button>
              {trader.isVerified && (
                <Check className="w-4 h-4 text-blue-400" />
              )}
            </div>
            <div className="text-sm text-gray-400 truncate">
              {trader.address?.slice(0, 6)}...{trader.address?.slice(-4)}
            </div>

            {/* Badges */}
            {trader.badges && trader.badges.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {trader.badges.slice(0, 3).map((badgeId, i) => {
                  const badge = BADGES[badgeId]
                  if (!badge) return null
                  return (
                    <span
                      key={i}
                      className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-xs bg-${badge.color}-500/10 text-${badge.color}-400`}
                    >
                      <badge.icon className="w-3 h-3" />
                      {badge.label}
                    </span>
                  )
                })}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2">
            <button
              onClick={() => onFollow?.(trader.id)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                isFollowing
                  ? 'bg-purple-500/20 text-purple-400'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {isFollowing ? (
                <>
                  <UserMinus className="w-4 h-4" />
                  Following
                </>
              ) : (
                <>
                  <UserPlus className="w-4 h-4" />
                  Follow
                </>
              )}
            </button>

            <button
              onClick={() => onCopy?.(trader.id)}
              className={`flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                isCopying
                  ? 'bg-green-500/20 text-green-400'
                  : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
              }`}
            >
              {isCopying ? (
                <>
                  <Check className="w-4 h-4" />
                  Copying
                </>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  Copy
                </>
              )}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mt-4 pt-4 border-t border-gray-800">
          <div className="text-center">
            <div className={`text-lg font-semibold ${trader.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {formatPercent(trader.pnlPercent)}
            </div>
            <div className="text-xs text-gray-500">30d PnL</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-white">{trader.winRate?.toFixed(0) || 0}%</div>
            <div className="text-xs text-gray-500">Win Rate</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-white">{trader.totalTrades || 0}</div>
            <div className="text-xs text-gray-500">Trades</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-white">{formatNumber(trader.followers || 0)}</div>
            <div className="text-xs text-gray-500">Followers</div>
          </div>
        </div>

        {/* Additional stats */}
        {!compact && (
          <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-gray-800/50">
            <div className="text-center">
              <div className="text-sm text-white">{formatPercent(trader.avgReturn)}</div>
              <div className="text-xs text-gray-500">Avg Return</div>
            </div>
            <div className="text-center">
              <div className="text-sm text-white">{trader.sharpRatio?.toFixed(2) || '-'}</div>
              <div className="text-xs text-gray-500">Sharpe</div>
            </div>
            <div className="text-center">
              <div className="text-sm text-red-400">{formatPercent(trader.maxDrawdown ? -trader.maxDrawdown : 0)}</div>
              <div className="text-xs text-gray-500">Max DD</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * CopyTradeSettings - Configure copy trade parameters
 */
function CopyTradeSettings({ trader, onSave, onClose }) {
  const [settings, setSettings] = useState({
    enabled: true,
    maxPosition: 100, // USD per trade
    stopLossPercent: 20,
    copyRatio: 100, // percent of trader's position
    maxDailyTrades: 10,
    excludeTokens: [],
    autoStopLoss: true,
  })

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-white">Copy Trade Settings</h3>
            <p className="text-sm text-gray-400">
              Configure how to copy {trader?.displayName || 'trader'}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Max position */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Max Position Size (USD)</label>
            <input
              type="number"
              value={settings.maxPosition}
              onChange={(e) => setSettings({ ...settings, maxPosition: parseFloat(e.target.value) || 0 })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white"
              min="1"
            />
            <p className="text-xs text-gray-500 mt-1">Maximum amount per copied trade</p>
          </div>

          {/* Copy ratio */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Copy Ratio (%)</label>
            <input
              type="number"
              value={settings.copyRatio}
              onChange={(e) => setSettings({ ...settings, copyRatio: parseFloat(e.target.value) || 0 })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white"
              min="1"
              max="200"
            />
            <p className="text-xs text-gray-500 mt-1">Percentage of trader's position to copy</p>
          </div>

          {/* Stop loss */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Stop Loss (%)</label>
            <input
              type="number"
              value={settings.stopLossPercent}
              onChange={(e) => setSettings({ ...settings, stopLossPercent: parseFloat(e.target.value) || 0 })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white"
              min="1"
              max="100"
            />
            <p className="text-xs text-gray-500 mt-1">Auto-close position if loss exceeds this</p>
          </div>

          {/* Max daily trades */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Max Daily Trades</label>
            <input
              type="number"
              value={settings.maxDailyTrades}
              onChange={(e) => setSettings({ ...settings, maxDailyTrades: parseInt(e.target.value) || 1 })}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white"
              min="1"
              max="100"
            />
            <p className="text-xs text-gray-500 mt-1">Maximum trades to copy per day</p>
          </div>

          {/* Enable toggle */}
          <div className="flex items-center justify-between py-2">
            <div>
              <div className="text-sm text-white">Auto Stop Loss</div>
              <div className="text-xs text-gray-500">Apply stop loss to copied trades</div>
            </div>
            <button
              onClick={() => setSettings({ ...settings, autoStopLoss: !settings.autoStopLoss })}
              className={`relative w-12 h-6 rounded-full transition-colors ${
                settings.autoStopLoss ? 'bg-green-500' : 'bg-gray-700'
              }`}
            >
              <span
                className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                  settings.autoStopLoss ? 'left-7' : 'left-1'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Warning */}
        <div className="flex items-start gap-3 p-3 bg-yellow-500/5 border border-yellow-500/20 rounded-lg mt-4">
          <AlertCircle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-gray-400">
            <p className="font-medium text-yellow-400 mb-1">Risk Warning</p>
            <p>
              Copy trading involves risk. Past performance does not guarantee future results.
              Only invest what you can afford to lose.
            </p>
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={() => {
              onSave?.(settings)
              onClose?.()
            }}
            className="flex-1 px-4 py-2.5 bg-green-500 rounded-lg text-white hover:bg-green-600"
          >
            Start Copying
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * LeaderboardTable - Ranked trader leaderboard
 */
function LeaderboardTable({ traders, onFollow, onCopy, onViewProfile, following = [], copying = [] }) {
  return (
    <div className="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-900/50">
            <tr className="text-left text-xs text-gray-500 uppercase">
              <th className="px-4 py-3">Rank</th>
              <th className="px-4 py-3">Trader</th>
              <th className="px-4 py-3 text-right">30d PnL</th>
              <th className="px-4 py-3 text-right">Win Rate</th>
              <th className="px-4 py-3 text-right">Trades</th>
              <th className="px-4 py-3 text-right">Followers</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {traders.map((trader, index) => {
              const rank = index + 1
              const RankIcon = RANK_ICONS[rank]
              const isFollowing = following.includes(trader.id)
              const isCopying = copying.includes(trader.id)

              return (
                <tr key={trader.id} className="hover:bg-gray-800/30">
                  <td className="px-4 py-3">
                    {RankIcon ? (
                      <div className={`w-8 h-8 rounded-full bg-${RankIcon.color}-500/10 flex items-center justify-center`}>
                        <RankIcon.icon className={`w-4 h-4 text-${RankIcon.color}-400`} />
                      </div>
                    ) : (
                      <span className="text-gray-400">{rank}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onViewProfile?.(trader)}
                        className="font-medium text-white hover:text-purple-400"
                      >
                        {trader.displayName || trader.address?.slice(0, 8)}
                      </button>
                      {trader.isVerified && <Check className="w-4 h-4 text-blue-400" />}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={trader.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {trader.pnlPercent >= 0 ? '+' : ''}{trader.pnlPercent?.toFixed(2) || 0}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-white">
                    {trader.winRate?.toFixed(0) || 0}%
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400">
                    {trader.totalTrades || 0}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-400">
                    {(trader.followers || 0).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => onFollow?.(trader.id)}
                        className={`p-1.5 rounded ${
                          isFollowing ? 'text-purple-400' : 'text-gray-500 hover:text-white'
                        }`}
                      >
                        {isFollowing ? <UserMinus className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => onCopy?.(trader.id)}
                        className={`p-1.5 rounded ${
                          isCopying ? 'text-green-400' : 'text-gray-500 hover:text-white'
                        }`}
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * Main SocialTrading Component
 */
export function SocialTrading({
  traders = [],
  onFollow,
  onCopy,
  onViewProfile,
  isLoading = false,
  className = '',
}) {
  const [following, setFollowing] = useState([])
  const [copying, setCopying] = useState([])
  const [copySettingsTrader, setCopySettingsTrader] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [timeframe, setTimeframe] = useState('30d')
  const [sortBy, setSortBy] = useState('pnl')
  const [viewMode, setViewMode] = useState('table') // table, cards

  // Filter and sort traders
  const filteredTraders = useMemo(() => {
    let filtered = traders

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(t =>
        t.displayName?.toLowerCase().includes(query) ||
        t.address?.toLowerCase().includes(query)
      )
    }

    // Sort
    switch (sortBy) {
      case 'pnl':
        filtered.sort((a, b) => (b.pnlPercent || 0) - (a.pnlPercent || 0))
        break
      case 'winRate':
        filtered.sort((a, b) => (b.winRate || 0) - (a.winRate || 0))
        break
      case 'followers':
        filtered.sort((a, b) => (b.followers || 0) - (a.followers || 0))
        break
      case 'trades':
        filtered.sort((a, b) => (b.totalTrades || 0) - (a.totalTrades || 0))
        break
    }

    return filtered
  }, [traders, searchQuery, sortBy])

  // Handle follow
  const handleFollow = useCallback((traderId) => {
    setFollowing(prev =>
      prev.includes(traderId)
        ? prev.filter(id => id !== traderId)
        : [...prev, traderId]
    )
    onFollow?.(traderId)
  }, [onFollow])

  // Handle copy setup
  const handleCopySetup = useCallback((traderId) => {
    const trader = traders.find(t => t.id === traderId)
    if (copying.includes(traderId)) {
      // Stop copying
      setCopying(prev => prev.filter(id => id !== traderId))
      onCopy?.(traderId, null)
    } else {
      // Open settings modal
      setCopySettingsTrader(trader)
    }
  }, [traders, copying, onCopy])

  // Handle copy start
  const handleCopyStart = useCallback((settings) => {
    if (copySettingsTrader) {
      setCopying(prev => [...prev, copySettingsTrader.id])
      onCopy?.(copySettingsTrader.id, settings)
    }
  }, [copySettingsTrader, onCopy])

  // Stats
  const stats = useMemo(() => ({
    totalTraders: traders.length,
    following: following.length,
    copying: copying.length,
    avgPnl: traders.length > 0
      ? traders.reduce((sum, t) => sum + (t.pnlPercent || 0), 0) / traders.length
      : 0,
  }), [traders, following, copying])

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/10 rounded-lg">
            <Users className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Social Trading</h2>
            <p className="text-sm text-gray-400">
              {stats.totalTraders} traders | Following {stats.following} | Copying {stats.copying}
            </p>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-6">
        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search traders..."
            className="w-full pl-10 pr-4 py-2.5 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
          />
        </div>

        {/* Timeframe */}
        <select
          value={timeframe}
          onChange={(e) => setTimeframe(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white"
        >
          <option value="7d">7 Days</option>
          <option value="30d">30 Days</option>
          <option value="90d">90 Days</option>
          <option value="all">All Time</option>
        </select>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white"
        >
          <option value="pnl">Sort by PnL</option>
          <option value="winRate">Sort by Win Rate</option>
          <option value="followers">Sort by Followers</option>
          <option value="trades">Sort by Trades</option>
        </select>

        {/* View toggle */}
        <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => setViewMode('table')}
            className={`p-2 rounded ${viewMode === 'table' ? 'bg-gray-700 text-white' : 'text-gray-500'}`}
          >
            <BarChart3 className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('cards')}
            className={`p-2 rounded ${viewMode === 'cards' ? 'bg-gray-700 text-white' : 'text-gray-500'}`}
          >
            <Users className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      {filteredTraders.length === 0 ? (
        <div className="text-center py-16 bg-gray-900/50 rounded-xl border border-gray-800">
          <Trophy className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-400 mb-2">No Traders Found</h3>
          <p className="text-sm text-gray-500">
            {traders.length === 0
              ? 'Trader leaderboard is loading...'
              : 'Try adjusting your search'}
          </p>
        </div>
      ) : viewMode === 'table' ? (
        <LeaderboardTable
          traders={filteredTraders}
          onFollow={handleFollow}
          onCopy={handleCopySetup}
          onViewProfile={onViewProfile}
          following={following}
          copying={copying}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTraders.map((trader, index) => (
            <TraderCard
              key={trader.id}
              trader={trader}
              rank={index + 1}
              onFollow={() => handleFollow(trader.id)}
              onCopy={() => handleCopySetup(trader.id)}
              onViewProfile={onViewProfile}
              isFollowing={following.includes(trader.id)}
              isCopying={copying.includes(trader.id)}
            />
          ))}
        </div>
      )}

      {/* Copy Settings Modal */}
      {copySettingsTrader && (
        <CopyTradeSettings
          trader={copySettingsTrader}
          onSave={handleCopyStart}
          onClose={() => setCopySettingsTrader(null)}
        />
      )}
    </div>
  )
}

export default SocialTrading
