import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Anchor,
  TrendingUp,
  TrendingDown,
  DollarSign,
  AlertTriangle,
  Bell,
  BellOff,
  Eye,
  EyeOff,
  ExternalLink,
  RefreshCw,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Clock,
  Wallet,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
  Zap,
  Shield,
  Crown,
  Star,
  Target,
  BarChart3,
  Waves,
  Settings,
  Plus,
  Minus,
  X
} from 'lucide-react'

// Whale tier thresholds (in USD)
const WHALE_TIERS = {
  MEGA: { label: 'Mega Whale', threshold: 10000000, color: '#fbbf24', icon: Crown },
  LARGE: { label: 'Large Whale', threshold: 1000000, color: '#a855f7', icon: Anchor },
  MEDIUM: { label: 'Whale', threshold: 100000, color: '#3b82f6', icon: Waves },
  SMALL: { label: 'Dolphin', threshold: 10000, color: '#22c55e', icon: Activity },
}

// Transaction types
const TX_TYPES = {
  BUY: { label: 'Buy', color: 'green', icon: ArrowUpRight },
  SELL: { label: 'Sell', color: 'red', icon: ArrowDownRight },
  TRANSFER: { label: 'Transfer', color: 'blue', icon: ArrowRight },
  SWAP: { label: 'Swap', color: 'purple', icon: RefreshCw },
  STAKE: { label: 'Stake', color: 'yellow', icon: Shield },
  UNSTAKE: { label: 'Unstake', color: 'orange', icon: Zap },
}

// Helper functions
function formatAddress(address) {
  if (!address) return ''
  return `${address.slice(0, 4)}...${address.slice(-4)}`
}

function formatUSD(amount) {
  if (amount >= 1000000000) return `$${(amount / 1000000000).toFixed(2)}B`
  if (amount >= 1000000) return `$${(amount / 1000000).toFixed(2)}M`
  if (amount >= 1000) return `$${(amount / 1000).toFixed(2)}K`
  return `$${amount.toFixed(2)}`
}

function formatTimeAgo(timestamp) {
  const seconds = Math.floor((Date.now() - new Date(timestamp)) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function getWhaleTier(valueUSD) {
  if (valueUSD >= WHALE_TIERS.MEGA.threshold) return 'MEGA'
  if (valueUSD >= WHALE_TIERS.LARGE.threshold) return 'LARGE'
  if (valueUSD >= WHALE_TIERS.MEDIUM.threshold) return 'MEDIUM'
  if (valueUSD >= WHALE_TIERS.SMALL.threshold) return 'SMALL'
  return null
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

// Whale Badge Component
function WhaleBadge({ tier, size = 'md' }) {
  const tierInfo = WHALE_TIERS[tier]
  if (!tierInfo) return null

  const Icon = tierInfo.icon
  const sizeClasses = {
    sm: 'px-1.5 py-0.5 text-xs',
    md: 'px-2 py-1 text-sm',
    lg: 'px-3 py-1.5 text-base',
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md font-medium ${sizeClasses[size]}`}
      style={{ backgroundColor: `${tierInfo.color}20`, color: tierInfo.color }}
    >
      <Icon className="w-3 h-3" />
      {tierInfo.label}
    </span>
  )
}

// Transaction Card Component
function TransactionCard({ tx, onWatchAddress, watchedAddresses }) {
  const tier = getWhaleTier(tx.valueUSD)
  const tierInfo = tier ? WHALE_TIERS[tier] : null
  const txType = TX_TYPES[tx.type] || TX_TYPES.TRANSFER
  const TxIcon = txType.icon

  const isWatched = watchedAddresses.has(tx.from) || watchedAddresses.has(tx.to)

  return (
    <div
      className="bg-gray-800 rounded-xl border border-gray-700 p-4 hover:border-gray-600 transition-colors"
      style={tierInfo ? { borderLeftWidth: 3, borderLeftColor: tierInfo.color } : {}}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`p-2 rounded-lg`}
            style={{ backgroundColor: `${TX_TYPES[tx.type]?.color === 'green' ? '#22c55e' : TX_TYPES[tx.type]?.color === 'red' ? '#ef4444' : '#6366f1'}20` }}
          >
            <TxIcon className={`w-5 h-5 ${
              txType.color === 'green' ? 'text-green-400' :
              txType.color === 'red' ? 'text-red-400' : 'text-blue-400'
            }`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold">{txType.label}</span>
              {tier && <WhaleBadge tier={tier} size="sm" />}
            </div>
            <div className="text-sm text-gray-400 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTimeAgo(tx.timestamp)}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold">{formatUSD(tx.valueUSD)}</div>
          <div className="text-sm text-gray-400">{tx.amount} {tx.token}</div>
        </div>
      </div>

      {/* Addresses */}
      <div className="bg-gray-900 rounded-lg p-3 mb-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500">From</span>
          <div className="flex items-center gap-2">
            <code className="text-sm font-mono">{formatAddress(tx.from)}</code>
            <CopyButton text={tx.from} />
            <button
              onClick={() => onWatchAddress(tx.from)}
              className={`p-1 rounded ${watchedAddresses.has(tx.from) ? 'text-yellow-400' : 'text-gray-400 hover:text-yellow-400'}`}
            >
              {watchedAddresses.has(tx.from) ? <Star className="w-3 h-3 fill-yellow-400" /> : <Star className="w-3 h-3" />}
            </button>
            <a
              href={`https://solscan.io/account/${tx.from}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-white"
            >
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">To</span>
          <div className="flex items-center gap-2">
            <code className="text-sm font-mono">{formatAddress(tx.to)}</code>
            <CopyButton text={tx.to} />
            <button
              onClick={() => onWatchAddress(tx.to)}
              className={`p-1 rounded ${watchedAddresses.has(tx.to) ? 'text-yellow-400' : 'text-gray-400 hover:text-yellow-400'}`}
            >
              {watchedAddresses.has(tx.to) ? <Star className="w-3 h-3 fill-yellow-400" /> : <Star className="w-3 h-3" />}
            </button>
            <a
              href={`https://solscan.io/account/${tx.to}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-400 hover:text-white"
            >
              <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      </div>

      {/* Transaction hash */}
      <div className="flex items-center justify-between text-sm">
        <a
          href={`https://solscan.io/tx/${tx.signature}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-gray-400 hover:text-white flex items-center gap-1"
        >
          View Transaction <ExternalLink className="w-3 h-3" />
        </a>
        {tx.token && (
          <span className="px-2 py-0.5 bg-gray-700 rounded text-gray-300">
            {tx.token}
          </span>
        )}
      </div>
    </div>
  )
}

// Whale Wallet Card Component
function WhaleWalletCard({ wallet, onWatch, isWatched, onViewHistory }) {
  const tier = getWhaleTier(wallet.totalValueUSD)

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 p-4 hover:border-gray-600 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Wallet className="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <code className="font-mono text-sm">{formatAddress(wallet.address)}</code>
              <CopyButton text={wallet.address} />
            </div>
            {wallet.label && (
              <div className="text-sm text-gray-400">{wallet.label}</div>
            )}
          </div>
        </div>
        {tier && <WhaleBadge tier={tier} />}
      </div>

      {/* Holdings */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div className="bg-gray-900 rounded-lg p-2">
          <div className="text-xs text-gray-500">Portfolio Value</div>
          <div className="text-lg font-bold">{formatUSD(wallet.totalValueUSD)}</div>
        </div>
        <div className="bg-gray-900 rounded-lg p-2">
          <div className="text-xs text-gray-500">24h Activity</div>
          <div className={`text-lg font-bold ${
            wallet.activity24h > 0 ? 'text-green-400' : 'text-gray-400'
          }`}>
            {wallet.activity24h} txs
          </div>
        </div>
      </div>

      {/* Top holdings */}
      {wallet.holdings && wallet.holdings.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-gray-500 mb-2">Top Holdings</div>
          <div className="flex flex-wrap gap-1">
            {wallet.holdings.slice(0, 5).map((holding, i) => (
              <span
                key={i}
                className="px-2 py-0.5 bg-gray-700 rounded text-xs text-gray-300"
              >
                {holding.symbol}: {formatUSD(holding.valueUSD)}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => onWatch(wallet.address)}
          className={`flex-1 py-1.5 rounded text-sm flex items-center justify-center gap-1 ${
            isWatched
              ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
          }`}
        >
          {isWatched ? <Bell className="w-3 h-3" /> : <BellOff className="w-3 h-3" />}
          {isWatched ? 'Watching' : 'Watch'}
        </button>
        <button
          onClick={() => onViewHistory(wallet)}
          className="flex-1 py-1.5 bg-blue-500/20 text-blue-400 rounded text-sm flex items-center justify-center gap-1 hover:bg-blue-500/30"
        >
          <Activity className="w-3 h-3" />
          History
        </button>
        <a
          href={`https://solscan.io/account/${wallet.address}`}
          target="_blank"
          rel="noopener noreferrer"
          className="px-3 py-1.5 bg-gray-700 text-gray-300 rounded text-sm flex items-center justify-center hover:bg-gray-600"
        >
          <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </div>
  )
}

// Alert Settings Modal
function AlertSettingsModal({ isOpen, onClose, settings, onSave }) {
  const [localSettings, setLocalSettings] = useState(settings)

  useEffect(() => {
    setLocalSettings(settings)
  }, [settings])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl p-6 max-w-md w-full border border-gray-700">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Bell className="w-5 h-5 text-yellow-400" />
            Alert Settings
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Minimum value threshold */}
          <div>
            <label className="text-sm text-gray-400 mb-2 block">
              Minimum Transaction Value (USD)
            </label>
            <input
              type="number"
              value={localSettings.minValueUSD}
              onChange={e => setLocalSettings({ ...localSettings, minValueUSD: Number(e.target.value) })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
            <div className="flex gap-2 mt-2">
              {[10000, 50000, 100000, 500000, 1000000].map(val => (
                <button
                  key={val}
                  onClick={() => setLocalSettings({ ...localSettings, minValueUSD: val })}
                  className={`px-2 py-1 text-xs rounded ${
                    localSettings.minValueUSD === val
                      ? 'bg-purple-500/20 text-purple-400'
                      : 'bg-gray-700 text-gray-400'
                  }`}
                >
                  {formatUSD(val)}
                </button>
              ))}
            </div>
          </div>

          {/* Transaction types */}
          <div>
            <label className="text-sm text-gray-400 mb-2 block">
              Alert on Transaction Types
            </label>
            <div className="flex flex-wrap gap-2">
              {Object.entries(TX_TYPES).map(([key, { label }]) => (
                <button
                  key={key}
                  onClick={() => {
                    const types = new Set(localSettings.txTypes || [])
                    if (types.has(key)) types.delete(key)
                    else types.add(key)
                    setLocalSettings({ ...localSettings, txTypes: Array.from(types) })
                  }}
                  className={`px-2 py-1 text-xs rounded ${
                    (localSettings.txTypes || []).includes(key)
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                      : 'bg-gray-700 text-gray-400 border border-gray-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Token filter */}
          <div>
            <label className="text-sm text-gray-400 mb-2 block">
              Watch Specific Tokens (comma-separated)
            </label>
            <input
              type="text"
              value={(localSettings.watchTokens || []).join(', ')}
              onChange={e => setLocalSettings({
                ...localSettings,
                watchTokens: e.target.value.split(',').map(t => t.trim().toUpperCase()).filter(Boolean)
              })}
              placeholder="SOL, BONK, JUP..."
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          {/* Sound alerts */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Sound Alerts</span>
            <button
              onClick={() => setLocalSettings({ ...localSettings, soundEnabled: !localSettings.soundEnabled })}
              className={`w-12 h-6 rounded-full transition-colors ${
                localSettings.soundEnabled ? 'bg-green-500' : 'bg-gray-600'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                localSettings.soundEnabled ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>

          {/* Desktop notifications */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-400">Desktop Notifications</span>
            <button
              onClick={() => setLocalSettings({ ...localSettings, desktopNotifications: !localSettings.desktopNotifications })}
              className={`w-12 h-6 rounded-full transition-colors ${
                localSettings.desktopNotifications ? 'bg-green-500' : 'bg-gray-600'
              }`}
            >
              <div className={`w-5 h-5 bg-white rounded-full transition-transform ${
                localSettings.desktopNotifications ? 'translate-x-6' : 'translate-x-0.5'
              }`} />
            </button>
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <button
            onClick={onClose}
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600"
          >
            Cancel
          </button>
          <button
            onClick={() => { onSave(localSettings); onClose() }}
            className="flex-1 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
          >
            Save Settings
          </button>
        </div>
      </div>
    </div>
  )
}

// Stats Summary Component
function StatsSummary({ transactions }) {
  const stats = useMemo(() => {
    if (!transactions.length) return null

    const totalVolume = transactions.reduce((sum, tx) => sum + tx.valueUSD, 0)
    const buys = transactions.filter(tx => tx.type === 'BUY')
    const sells = transactions.filter(tx => tx.type === 'SELL')
    const buyVolume = buys.reduce((sum, tx) => sum + tx.valueUSD, 0)
    const sellVolume = sells.reduce((sum, tx) => sum + tx.valueUSD, 0)

    const megaWhales = transactions.filter(tx => getWhaleTier(tx.valueUSD) === 'MEGA')
    const largeWhales = transactions.filter(tx => getWhaleTier(tx.valueUSD) === 'LARGE')

    return {
      totalVolume,
      totalTxs: transactions.length,
      buyVolume,
      sellVolume,
      buyCount: buys.length,
      sellCount: sells.length,
      megaWhaleCount: megaWhales.length,
      largeWhaleCount: largeWhales.length,
      netFlow: buyVolume - sellVolume,
    }
  }, [transactions])

  if (!stats) return null

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">24h Whale Volume</div>
        <div className="text-2xl font-bold">{formatUSD(stats.totalVolume)}</div>
        <div className="text-xs text-gray-500">{stats.totalTxs} transactions</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Buy Volume</div>
        <div className="text-2xl font-bold text-green-400">{formatUSD(stats.buyVolume)}</div>
        <div className="text-xs text-gray-500">{stats.buyCount} buys</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Sell Volume</div>
        <div className="text-2xl font-bold text-red-400">{formatUSD(stats.sellVolume)}</div>
        <div className="text-xs text-gray-500">{stats.sellCount} sells</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Net Flow</div>
        <div className={`text-2xl font-bold ${stats.netFlow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {stats.netFlow >= 0 ? '+' : ''}{formatUSD(stats.netFlow)}
        </div>
        <div className="text-xs text-gray-500">
          {stats.megaWhaleCount} mega, {stats.largeWhaleCount} large whales
        </div>
      </div>
    </div>
  )
}

// Main Whale Tracker Component
export function WhaleTracker({
  transactions = [],
  knownWhales = [],
  onRefresh,
  onAddWatchlist,
  onRemoveWatchlist,
  watchlist = [],
  isLoading = false,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState('all')
  const [selectedTier, setSelectedTier] = useState('all')
  const [minValue, setMinValue] = useState(10000)
  const [sortBy, setSortBy] = useState('time')
  const [sortOrder, setSortOrder] = useState('desc')
  const [viewMode, setViewMode] = useState('transactions') // transactions, whales
  const [showSettings, setShowSettings] = useState(false)
  const [watchedAddresses, setWatchedAddresses] = useState(new Set(watchlist))
  const [alertSettings, setAlertSettings] = useState({
    minValueUSD: 100000,
    txTypes: ['BUY', 'SELL'],
    watchTokens: [],
    soundEnabled: true,
    desktopNotifications: true,
  })

  // Update watched addresses when watchlist prop changes
  useEffect(() => {
    setWatchedAddresses(new Set(watchlist))
  }, [watchlist])

  // Filter transactions
  const filteredTransactions = useMemo(() => {
    let result = [...transactions]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(tx =>
        tx.from.toLowerCase().includes(query) ||
        tx.to.toLowerCase().includes(query) ||
        tx.token?.toLowerCase().includes(query)
      )
    }

    // Type filter
    if (selectedType !== 'all') {
      result = result.filter(tx => tx.type === selectedType)
    }

    // Tier filter
    if (selectedTier !== 'all') {
      result = result.filter(tx => getWhaleTier(tx.valueUSD) === selectedTier)
    }

    // Min value filter
    result = result.filter(tx => tx.valueUSD >= minValue)

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'time': comparison = new Date(a.timestamp) - new Date(b.timestamp); break
        case 'value': comparison = a.valueUSD - b.valueUSD; break
        default: comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [transactions, searchQuery, selectedType, selectedTier, minValue, sortBy, sortOrder])

  const toggleWatch = useCallback((address) => {
    setWatchedAddresses(prev => {
      const newSet = new Set(prev)
      if (newSet.has(address)) {
        newSet.delete(address)
        onRemoveWatchlist?.(address)
      } else {
        newSet.add(address)
        onAddWatchlist?.(address)
      }
      return newSet
    })
  }, [onAddWatchlist, onRemoveWatchlist])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Anchor className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Whale Tracker</h1>
            <p className="text-sm text-gray-400">Track large transactions and whale wallets</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowSettings(true)}
            className="p-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600"
          >
            <Bell className="w-5 h-5" />
          </button>
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Summary */}
      <StatsSummary transactions={transactions} />

      {/* View Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setViewMode('transactions')}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
            viewMode === 'transactions'
              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
              : 'bg-gray-800 text-gray-400 border border-gray-700'
          }`}
        >
          <Activity className="w-4 h-4" />
          Live Transactions
        </button>
        <button
          onClick={() => setViewMode('whales')}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
            viewMode === 'whales'
              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
              : 'bg-gray-800 text-gray-400 border border-gray-700'
          }`}
        >
          <Wallet className="w-4 h-4" />
          Known Whales
        </button>
      </div>

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search address or token..."
              className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          {viewMode === 'transactions' && (
            <>
              <select
                value={selectedType}
                onChange={e => setSelectedType(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
              >
                <option value="all">All Types</option>
                {Object.entries(TX_TYPES).map(([key, { label }]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>

              <select
                value={selectedTier}
                onChange={e => setSelectedTier(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
              >
                <option value="all">All Tiers</option>
                {Object.entries(WHALE_TIERS).map(([key, { label }]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>

              <select
                value={minValue}
                onChange={e => setMinValue(Number(e.target.value))}
                className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
              >
                <option value={10000}>Min $10K</option>
                <option value={50000}>Min $50K</option>
                <option value={100000}>Min $100K</option>
                <option value={500000}>Min $500K</option>
                <option value={1000000}>Min $1M</option>
              </select>
            </>
          )}
        </div>

        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Sort:</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-sm"
            >
              <option value="time">Time</option>
              <option value="value">Value</option>
            </select>
            <button
              onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
              className="p-1 bg-gray-700 rounded"
            >
              {sortOrder === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex items-center gap-2">
            {watchedAddresses.size > 0 && (
              <span className="px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded text-sm">
                {watchedAddresses.size} watched
              </span>
            )}
            <span className="text-sm text-gray-400">
              {viewMode === 'transactions' ? filteredTransactions.length : knownWhales.length} results
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      {viewMode === 'transactions' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filteredTransactions.map((tx, i) => (
            <TransactionCard
              key={tx.signature || i}
              tx={tx}
              onWatchAddress={toggleWatch}
              watchedAddresses={watchedAddresses}
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {knownWhales.map((wallet, i) => (
            <WhaleWalletCard
              key={wallet.address || i}
              wallet={wallet}
              onWatch={toggleWatch}
              isWatched={watchedAddresses.has(wallet.address)}
              onViewHistory={() => {}}
            />
          ))}
        </div>
      )}

      {/* Empty State */}
      {((viewMode === 'transactions' && filteredTransactions.length === 0) ||
        (viewMode === 'whales' && knownWhales.length === 0)) && (
        <div className="text-center py-12 text-gray-400">
          <Anchor className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No whale activity found</p>
        </div>
      )}

      {/* Settings Modal */}
      <AlertSettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        settings={alertSettings}
        onSave={setAlertSettings}
      />
    </div>
  )
}

export default WhaleTracker
