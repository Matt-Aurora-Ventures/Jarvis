import React, { useState, useCallback, useMemo, useEffect } from 'react'
import {
  Star, Plus, Trash2, Bell, BellOff, Search, Filter, RefreshCw,
  TrendingUp, TrendingDown, ExternalLink, Copy, Eye, EyeOff,
  ChevronDown, ChevronUp, Clock, Activity, AlertCircle, Settings,
  ArrowUpRight, ArrowDownRight, Zap, MoreVertical, Edit2, Check, X
} from 'lucide-react'

/**
 * TokenWatchlist - Track favorite tokens with alerts
 *
 * Features:
 * - Add/Remove tokens
 * - Real-time price updates
 * - Price alerts per token
 * - Notes and tags
 * - Sort and filter
 * - Groups/Categories
 * - Export watchlist
 */

// Default alert types
const ALERT_TYPES = {
  PRICE_ABOVE: { label: 'Price Above', icon: TrendingUp, color: 'green' },
  PRICE_BELOW: { label: 'Price Below', icon: TrendingDown, color: 'red' },
  CHANGE_UP: { label: 'Change > %', icon: ArrowUpRight, color: 'green' },
  CHANGE_DOWN: { label: 'Change < %', icon: ArrowDownRight, color: 'red' },
  VOLUME_SPIKE: { label: 'Volume Spike', icon: Activity, color: 'blue' },
}

/**
 * AddTokenModal - Modal for adding new token
 */
function AddTokenModal({ isOpen, onClose, onAdd }) {
  const [address, setAddress] = useState('')
  const [notes, setNotes] = useState('')
  const [group, setGroup] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = useCallback((e) => {
    e.preventDefault()

    if (!address.trim()) {
      setError('Token address is required')
      return
    }

    onAdd({
      address: address.trim(),
      notes: notes.trim(),
      group: group.trim() || 'Default',
    })

    setAddress('')
    setNotes('')
    setGroup('')
    setError('')
    onClose()
  }, [address, notes, group, onAdd, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-white">Add to Watchlist</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm text-gray-400 mb-1">Token Address / Symbol</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 font-mono text-sm focus:outline-none focus:border-purple-500"
              placeholder="Enter contract address or symbol..."
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Group (Optional)</label>
            <input
              type="text"
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              placeholder="e.g., Memecoins, DeFi, AI..."
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Notes (Optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
              placeholder="Add notes about this token..."
            />
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2.5 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2.5 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
            >
              Add Token
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/**
 * AlertSettingsModal - Configure alerts for a token
 */
function AlertSettingsModal({ isOpen, onClose, token, onSave }) {
  const [alerts, setAlerts] = useState(token?.alerts || [])

  const addAlert = useCallback(() => {
    setAlerts(prev => [...prev, {
      id: `alert_${Date.now()}`,
      type: 'PRICE_ABOVE',
      value: 0,
      enabled: true,
    }])
  }, [])

  const updateAlert = useCallback((index, updates) => {
    setAlerts(prev => {
      const newAlerts = [...prev]
      newAlerts[index] = { ...newAlerts[index], ...updates }
      return newAlerts
    })
  }, [])

  const removeAlert = useCallback((index) => {
    setAlerts(prev => prev.filter((_, i) => i !== index))
  }, [])

  const handleSave = useCallback(() => {
    onSave(alerts)
    onClose()
  }, [alerts, onSave, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-semibold text-white">Alert Settings</h3>
            <p className="text-sm text-gray-400">{token?.symbol || 'Token'}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="space-y-3 max-h-64 overflow-y-auto mb-4">
          {alerts.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">No alerts configured</p>
            </div>
          ) : (
            alerts.map((alert, index) => (
              <div
                key={alert.id}
                className="flex items-center gap-3 p-3 bg-gray-800/50 rounded-lg"
              >
                <button
                  onClick={() => updateAlert(index, { enabled: !alert.enabled })}
                  className={`p-1.5 rounded ${
                    alert.enabled ? 'text-green-400' : 'text-gray-500'
                  }`}
                >
                  {alert.enabled ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
                </button>

                <select
                  value={alert.type}
                  onChange={(e) => updateAlert(index, { type: e.target.value })}
                  className="bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
                >
                  {Object.entries(ALERT_TYPES).map(([key, type]) => (
                    <option key={key} value={key}>{type.label}</option>
                  ))}
                </select>

                <input
                  type="number"
                  value={alert.value}
                  onChange={(e) => updateAlert(index, { value: parseFloat(e.target.value) || 0 })}
                  className="w-24 bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
                  step="any"
                />

                <button
                  onClick={() => removeAlert(index)}
                  className="p-1.5 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>

        <button
          onClick={addAlert}
          className="w-full flex items-center justify-center gap-2 py-2 border border-dashed border-gray-700 rounded-lg text-gray-400 hover:text-white hover:border-gray-600 mb-4"
        >
          <Plus className="w-4 h-4" />
          Add Alert
        </button>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2.5 border border-gray-700 rounded-lg text-gray-300 hover:bg-gray-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex-1 px-4 py-2.5 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
          >
            Save Alerts
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * WatchlistItem - Single watchlist item row
 */
function WatchlistItem({
  token,
  onRemove,
  onAlertSettings,
  onToggleFavorite,
  onUpdateNotes,
  compact = false,
}) {
  const [showNotes, setShowNotes] = useState(false)
  const [editingNotes, setEditingNotes] = useState(false)
  const [notesValue, setNotesValue] = useState(token.notes || '')

  const saveNotes = useCallback(() => {
    onUpdateNotes?.(token.id, notesValue)
    setEditingNotes(false)
  }, [token.id, notesValue, onUpdateNotes])

  const change24h = token.priceChange24h || 0
  const hasAlerts = token.alerts && token.alerts.length > 0
  const activeAlerts = token.alerts?.filter(a => a.enabled).length || 0

  const formatPrice = (price) => {
    if (!price) return '-'
    if (price >= 1) return `$${price.toFixed(4)}`
    if (price >= 0.01) return `$${price.toFixed(6)}`
    return `$${price.toFixed(10)}`
  }

  const copyAddress = useCallback(() => {
    navigator.clipboard.writeText(token.address)
  }, [token.address])

  return (
    <div className="bg-gray-900/50 rounded-lg border border-gray-800 overflow-hidden">
      {/* Main row */}
      <div className="flex items-center gap-4 p-4">
        {/* Favorite star */}
        <button
          onClick={() => onToggleFavorite?.(token.id)}
          className={token.isFavorite ? 'text-yellow-400' : 'text-gray-600 hover:text-yellow-400'}
        >
          <Star className={`w-5 h-5 ${token.isFavorite ? 'fill-current' : ''}`} />
        </button>

        {/* Token info */}
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className="w-10 h-10 bg-gray-800 rounded-full flex items-center justify-center">
            <span className="text-sm font-medium text-gray-300">
              {token.symbol?.slice(0, 2) || '??'}
            </span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-white truncate">{token.symbol || 'Unknown'}</span>
              {token.group && token.group !== 'Default' && (
                <span className="px-1.5 py-0.5 bg-gray-800 rounded text-xs text-gray-400">
                  {token.group}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <span className="font-mono truncate max-w-32">
                {token.address?.slice(0, 6)}...{token.address?.slice(-4)}
              </span>
              <button onClick={copyAddress} className="p-0.5 hover:text-gray-300">
                <Copy className="w-3 h-3" />
              </button>
              <a
                href={`https://dexscreener.com/solana/${token.address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="p-0.5 hover:text-gray-300"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>

        {/* Price */}
        <div className="text-right">
          <div className="font-medium text-white">
            {formatPrice(token.price)}
          </div>
          <div className={`text-sm flex items-center justify-end gap-1 ${
            change24h >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {change24h >= 0 ? (
              <TrendingUp className="w-3 h-3" />
            ) : (
              <TrendingDown className="w-3 h-3" />
            )}
            {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
          </div>
        </div>

        {/* Volume */}
        {!compact && (
          <div className="text-right w-24">
            <div className="text-sm text-gray-400">Vol 24h</div>
            <div className="text-sm text-white font-medium">
              ${(token.volume24h / 1000000)?.toFixed(2) || 0}M
            </div>
          </div>
        )}

        {/* Liquidity */}
        {!compact && (
          <div className="text-right w-24">
            <div className="text-sm text-gray-400">Liquidity</div>
            <div className="text-sm text-white font-medium">
              ${(token.liquidity / 1000)?.toFixed(1) || 0}K
            </div>
          </div>
        )}

        {/* Alerts indicator */}
        <button
          onClick={() => onAlertSettings?.(token)}
          className={`p-2 rounded-lg transition-colors ${
            hasAlerts
              ? 'bg-yellow-500/10 text-yellow-400'
              : 'hover:bg-gray-800 text-gray-500'
          }`}
          title={hasAlerts ? `${activeAlerts} active alerts` : 'Set alerts'}
        >
          {hasAlerts ? <Bell className="w-4 h-4" /> : <BellOff className="w-4 h-4" />}
        </button>

        {/* Notes toggle */}
        <button
          onClick={() => setShowNotes(!showNotes)}
          className={`p-2 rounded-lg transition-colors ${
            token.notes ? 'text-purple-400' : 'text-gray-500'
          } hover:bg-gray-800`}
        >
          {showNotes ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {/* Remove */}
        <button
          onClick={() => onRemove?.(token.id)}
          className="p-2 rounded-lg hover:bg-red-500/20 text-gray-500 hover:text-red-400"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      </div>

      {/* Notes section */}
      {showNotes && (
        <div className="px-4 pb-4 pt-0">
          <div className="bg-gray-800/50 rounded-lg p-3">
            {editingNotes ? (
              <div className="space-y-2">
                <textarea
                  value={notesValue}
                  onChange={(e) => setNotesValue(e.target.value)}
                  rows={2}
                  className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
                  placeholder="Add notes..."
                  autoFocus
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => {
                      setNotesValue(token.notes || '')
                      setEditingNotes(false)
                    }}
                    className="px-3 py-1 text-sm text-gray-400 hover:text-white"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={saveNotes}
                    className="px-3 py-1 bg-purple-500 rounded text-sm text-white hover:bg-purple-600"
                  >
                    Save
                  </button>
                </div>
              </div>
            ) : (
              <div
                onClick={() => setEditingNotes(true)}
                className="cursor-pointer min-h-[2rem]"
              >
                {token.notes ? (
                  <p className="text-sm text-gray-300">{token.notes}</p>
                ) : (
                  <p className="text-sm text-gray-500 italic">Click to add notes...</p>
                )}
              </div>
            )}
          </div>

          {/* Last updated */}
          <div className="flex items-center gap-1 text-xs text-gray-500 mt-2">
            <Clock className="w-3 h-3" />
            Added {new Date(token.addedAt).toLocaleDateString()}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * Main TokenWatchlist Component
 */
export function TokenWatchlist({
  initialTokens = [],
  onTokenAdd,
  onTokenRemove,
  onTokenUpdate,
  onRefresh,
  isLoading = false,
  className = '',
}) {
  const [tokens, setTokens] = useState(initialTokens)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [alertSettingsToken, setAlertSettingsToken] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterGroup, setFilterGroup] = useState('all')
  const [sortBy, setSortBy] = useState('addedAt') // addedAt, price, change, name
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)

  // Get unique groups
  const groups = useMemo(() => {
    const groupSet = new Set(tokens.map(t => t.group || 'Default'))
    return ['all', ...Array.from(groupSet)]
  }, [tokens])

  // Filter and sort tokens
  const filteredTokens = useMemo(() => {
    let filtered = tokens

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(t =>
        t.symbol?.toLowerCase().includes(query) ||
        t.name?.toLowerCase().includes(query) ||
        t.address?.toLowerCase().includes(query) ||
        t.notes?.toLowerCase().includes(query)
      )
    }

    // Filter by group
    if (filterGroup !== 'all') {
      filtered = filtered.filter(t => (t.group || 'Default') === filterGroup)
    }

    // Favorites only
    if (showFavoritesOnly) {
      filtered = filtered.filter(t => t.isFavorite)
    }

    // Sort
    switch (sortBy) {
      case 'price':
        filtered.sort((a, b) => (b.price || 0) - (a.price || 0))
        break
      case 'change':
        filtered.sort((a, b) => (b.priceChange24h || 0) - (a.priceChange24h || 0))
        break
      case 'name':
        filtered.sort((a, b) => (a.symbol || '').localeCompare(b.symbol || ''))
        break
      default:
        filtered.sort((a, b) => new Date(b.addedAt) - new Date(a.addedAt))
    }

    return filtered
  }, [tokens, searchQuery, filterGroup, sortBy, showFavoritesOnly])

  // Handle add token
  const handleAddToken = useCallback((tokenData) => {
    const newToken = {
      id: `token_${Date.now()}`,
      ...tokenData,
      addedAt: new Date().toISOString(),
      isFavorite: false,
      alerts: [],
      // Mock data - would be fetched from API
      symbol: tokenData.address.slice(0, 6),
      name: 'Loading...',
      price: 0,
      priceChange24h: 0,
      volume24h: 0,
      liquidity: 0,
    }

    setTokens(prev => [newToken, ...prev])
    onTokenAdd?.(newToken)
  }, [onTokenAdd])

  // Handle remove token
  const handleRemoveToken = useCallback((tokenId) => {
    if (confirm('Remove this token from watchlist?')) {
      setTokens(prev => prev.filter(t => t.id !== tokenId))
      onTokenRemove?.(tokenId)
    }
  }, [onTokenRemove])

  // Toggle favorite
  const handleToggleFavorite = useCallback((tokenId) => {
    setTokens(prev => prev.map(t =>
      t.id === tokenId ? { ...t, isFavorite: !t.isFavorite } : t
    ))
  }, [])

  // Update notes
  const handleUpdateNotes = useCallback((tokenId, notes) => {
    setTokens(prev => prev.map(t =>
      t.id === tokenId ? { ...t, notes } : t
    ))
  }, [])

  // Save alert settings
  const handleSaveAlerts = useCallback((alerts) => {
    if (alertSettingsToken) {
      setTokens(prev => prev.map(t =>
        t.id === alertSettingsToken.id ? { ...t, alerts } : t
      ))
    }
  }, [alertSettingsToken])

  // Stats
  const stats = useMemo(() => {
    const favorites = tokens.filter(t => t.isFavorite).length
    const withAlerts = tokens.filter(t => t.alerts?.length > 0).length
    const totalAlerts = tokens.reduce((sum, t) => sum + (t.alerts?.length || 0), 0)
    return { total: tokens.length, favorites, withAlerts, totalAlerts }
  }, [tokens])

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-white">Token Watchlist</h2>
          <p className="text-sm text-gray-400">
            {stats.total} tokens | {stats.favorites} favorites | {stats.totalAlerts} alerts
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 rounded-lg text-gray-300 hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
          >
            <Plus className="w-4 h-4" />
            Add Token
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4 mb-4">
        {/* Search */}
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tokens..."
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
          />
        </div>

        {/* Group filter */}
        <select
          value={filterGroup}
          onChange={(e) => setFilterGroup(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white"
        >
          {groups.map(group => (
            <option key={group} value={group}>
              {group === 'all' ? 'All Groups' : group}
            </option>
          ))}
        </select>

        {/* Sort */}
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white"
        >
          <option value="addedAt">Recently Added</option>
          <option value="price">By Price</option>
          <option value="change">By Change</option>
          <option value="name">By Name</option>
        </select>

        {/* Favorites toggle */}
        <button
          onClick={() => setShowFavoritesOnly(!showFavoritesOnly)}
          className={`p-2 rounded-lg transition-colors ${
            showFavoritesOnly
              ? 'bg-yellow-500/20 text-yellow-400'
              : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          <Star className={`w-5 h-5 ${showFavoritesOnly ? 'fill-current' : ''}`} />
        </button>
      </div>

      {/* Token list */}
      {filteredTokens.length === 0 ? (
        <div className="text-center py-16 bg-gray-900/50 rounded-xl border border-gray-800">
          <Star className="w-12 h-12 text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-400 mb-2">
            {tokens.length === 0 ? 'Your Watchlist is Empty' : 'No Tokens Match Your Filter'}
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            {tokens.length === 0
              ? 'Add tokens to start tracking them'
              : 'Try adjusting your search or filters'}
          </p>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
          >
            <Plus className="w-4 h-4" />
            Add Token
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTokens.map(token => (
            <WatchlistItem
              key={token.id}
              token={token}
              onRemove={handleRemoveToken}
              onAlertSettings={setAlertSettingsToken}
              onToggleFavorite={handleToggleFavorite}
              onUpdateNotes={handleUpdateNotes}
            />
          ))}
        </div>
      )}

      {/* Add Token Modal */}
      <AddTokenModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddToken}
      />

      {/* Alert Settings Modal */}
      <AlertSettingsModal
        isOpen={alertSettingsToken !== null}
        onClose={() => setAlertSettingsToken(null)}
        token={alertSettingsToken}
        onSave={handleSaveAlerts}
      />
    </div>
  )
}

export default TokenWatchlist
