import React, { useState, useEffect, useMemo } from 'react'
import {
  Bell,
  Plus,
  Trash2,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Volume2,
  Droplets,
  ToggleLeft,
  ToggleRight,
  AlertTriangle,
  Check,
  X,
  RefreshCw,
  Search,
  Filter,
  Clock,
  Zap
} from 'lucide-react'

/**
 * Alert Types
 */
const ALERT_TYPES = {
  PRICE_ABOVE: { label: 'Price Above', icon: TrendingUp, color: 'text-green-400' },
  PRICE_BELOW: { label: 'Price Below', icon: TrendingDown, color: 'text-red-400' },
  PERCENT_CHANGE_UP: { label: 'Pump Alert', icon: Zap, color: 'text-green-400' },
  PERCENT_CHANGE_DOWN: { label: 'Dump Alert', icon: AlertTriangle, color: 'text-red-400' },
  VOLUME_SPIKE: { label: 'Volume Spike', icon: Volume2, color: 'text-purple-400' },
  LIQUIDITY_CHANGE: { label: 'Liquidity Change', icon: Droplets, color: 'text-blue-400' },
}

/**
 * Alert Card Component
 */
function AlertCard({ alert, onToggle, onDelete }) {
  const typeConfig = ALERT_TYPES[alert.type] || ALERT_TYPES.PRICE_ABOVE
  const Icon = typeConfig.icon

  return (
    <div className={`
      relative p-4 rounded-lg border transition-all duration-200
      ${alert.enabled
        ? 'bg-gray-800/50 border-gray-700 hover:border-gray-600'
        : 'bg-gray-900/50 border-gray-800 opacity-60'}
    `}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg bg-gray-700/50 ${typeConfig.color}`}>
            <Icon size={16} />
          </div>
          <div>
            <h4 className="font-medium text-white">{alert.symbol}</h4>
            <p className="text-xs text-gray-400">{typeConfig.label}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggle(alert.id)}
            className={`p-1.5 rounded transition-colors ${
              alert.enabled ? 'text-green-400 hover:bg-green-900/30' : 'text-gray-500 hover:bg-gray-700'
            }`}
          >
            {alert.enabled ? <ToggleRight size={20} /> : <ToggleLeft size={20} />}
          </button>
          <button
            onClick={() => onDelete(alert.id)}
            className="p-1.5 rounded text-gray-400 hover:text-red-400 hover:bg-red-900/30 transition-colors"
          >
            <Trash2 size={16} />
          </button>
        </div>
      </div>

      {/* Alert Details */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Target:</span>
          <span className={`font-mono ${typeConfig.color}`}>
            {alert.type.includes('PERCENT') ? `${alert.threshold}%` : `$${alert.threshold.toFixed(6)}`}
          </span>
        </div>

        {alert.currentPrice && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Current:</span>
            <span className="font-mono text-white">${alert.currentPrice.toFixed(6)}</span>
          </div>
        )}

        {alert.lastTriggered && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Last triggered:</span>
            <span className="text-gray-300 text-xs">
              {new Date(alert.lastTriggered).toLocaleString()}
            </span>
          </div>
        )}
      </div>

      {/* Triggered Badge */}
      {alert.triggered && (
        <div className="absolute top-2 right-2">
          <span className="px-2 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded-full">
            Triggered
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * Create Alert Modal
 */
function CreateAlertModal({ isOpen, onClose, onCreate }) {
  const [formData, setFormData] = useState({
    symbol: '',
    mint: '',
    type: 'PRICE_ABOVE',
    threshold: '',
    repeatInterval: 300,
    notifyTelegram: true,
    notifyWebhook: true,
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Validate
      if (!formData.symbol.trim()) throw new Error('Token symbol is required')
      if (!formData.threshold || isNaN(formData.threshold)) throw new Error('Valid threshold is required')

      await onCreate({
        ...formData,
        threshold: parseFloat(formData.threshold),
        repeatInterval: parseInt(formData.repeatInterval),
      })

      onClose()
      setFormData({
        symbol: '',
        mint: '',
        type: 'PRICE_ABOVE',
        threshold: '',
        repeatInterval: 300,
        notifyTelegram: true,
        notifyWebhook: true,
      })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl border border-gray-700 w-full max-w-md shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Bell className="text-cyan-400" size={20} />
            Create Price Alert
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Token Symbol */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Token Symbol</label>
            <input
              type="text"
              value={formData.symbol}
              onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase() })}
              placeholder="e.g., SOL, BONK, WIF"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Token Mint (Optional) */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Token Mint Address (Optional)</label>
            <input
              type="text"
              value={formData.mint}
              onChange={(e) => setFormData({ ...formData, mint: e.target.value })}
              placeholder="Solana token mint address"
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 font-mono text-sm"
            />
          </div>

          {/* Alert Type */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Alert Type</label>
            <select
              value={formData.type}
              onChange={(e) => setFormData({ ...formData, type: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-cyan-500"
            >
              {Object.entries(ALERT_TYPES).map(([key, { label }]) => (
                <option key={key} value={key}>{label}</option>
              ))}
            </select>
          </div>

          {/* Threshold */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">
              {formData.type.includes('PERCENT') ? 'Percentage Change (%)' : 'Price Target ($)'}
            </label>
            <input
              type="number"
              step={formData.type.includes('PERCENT') ? '1' : '0.000001'}
              value={formData.threshold}
              onChange={(e) => setFormData({ ...formData, threshold: e.target.value })}
              placeholder={formData.type.includes('PERCENT') ? 'e.g., 10' : 'e.g., 0.001234'}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Repeat Interval */}
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Cooldown (seconds)</label>
            <select
              value={formData.repeatInterval}
              onChange={(e) => setFormData({ ...formData, repeatInterval: e.target.value })}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-cyan-500"
            >
              <option value={60}>1 minute</option>
              <option value={300}>5 minutes</option>
              <option value={900}>15 minutes</option>
              <option value={1800}>30 minutes</option>
              <option value={3600}>1 hour</option>
              <option value={0}>No repeat (one-time)</option>
            </select>
          </div>

          {/* Notification Options */}
          <div className="space-y-2">
            <label className="block text-sm text-gray-400 mb-1.5">Notifications</label>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.notifyTelegram}
                  onChange={(e) => setFormData({ ...formData, notifyTelegram: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-cyan-500 focus:ring-cyan-500"
                />
                <span className="text-sm text-gray-300">Telegram</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.notifyWebhook}
                  onChange={(e) => setFormData({ ...formData, notifyWebhook: e.target.checked })}
                  className="w-4 h-4 rounded border-gray-600 bg-gray-900 text-cyan-500 focus:ring-cyan-500"
                />
                <span className="text-sm text-gray-300">Webhooks</span>
              </label>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <RefreshCw size={16} className="animate-spin" />
              ) : (
                <Plus size={16} />
              )}
              Create Alert
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/**
 * Alert History Item
 */
function AlertHistoryItem({ event }) {
  const typeConfig = ALERT_TYPES[event.alertType] || ALERT_TYPES.PRICE_ABOVE
  const Icon = typeConfig.icon

  return (
    <div className="flex items-center gap-3 p-3 bg-gray-800/30 rounded-lg">
      <div className={`p-2 rounded-lg bg-gray-700/50 ${typeConfig.color}`}>
        <Icon size={14} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-white">{event.symbol}</span>
          <span className="text-xs text-gray-400">{typeConfig.label}</span>
        </div>
        <p className="text-sm text-gray-400 truncate">{event.message}</p>
      </div>
      <div className="text-xs text-gray-500 whitespace-nowrap">
        {new Date(event.timestamp).toLocaleTimeString()}
      </div>
    </div>
  )
}

/**
 * Price Alerts Main Component
 */
export default function PriceAlerts() {
  const [alerts, setAlerts] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [filter, setFilter] = useState('all') // all, active, triggered
  const [searchQuery, setSearchQuery] = useState('')

  // Fetch alerts
  const fetchAlerts = async () => {
    try {
      const response = await fetch('/api/alerts')
      if (response.ok) {
        const data = await response.json()
        setAlerts(data.alerts || [])
        setHistory(data.history || [])
      }
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  // Create alert
  const handleCreateAlert = async (alertData) => {
    const response = await fetch('/api/alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(alertData),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || 'Failed to create alert')
    }

    await fetchAlerts()
  }

  // Toggle alert
  const handleToggleAlert = async (alertId) => {
    const alert = alerts.find(a => a.id === alertId)
    if (!alert) return

    const response = await fetch(`/api/alerts/${alertId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !alert.enabled }),
    })

    if (response.ok) {
      setAlerts(alerts.map(a =>
        a.id === alertId ? { ...a, enabled: !a.enabled } : a
      ))
    }
  }

  // Delete alert
  const handleDeleteAlert = async (alertId) => {
    const response = await fetch(`/api/alerts/${alertId}`, {
      method: 'DELETE',
    })

    if (response.ok) {
      setAlerts(alerts.filter(a => a.id !== alertId))
    }
  }

  // Filter alerts
  const filteredAlerts = useMemo(() => {
    return alerts.filter(alert => {
      // Apply status filter
      if (filter === 'active' && !alert.enabled) return false
      if (filter === 'triggered' && !alert.triggered) return false

      // Apply search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return alert.symbol.toLowerCase().includes(query) ||
               alert.type.toLowerCase().includes(query)
      }

      return true
    })
  }, [alerts, filter, searchQuery])

  // Stats
  const stats = useMemo(() => ({
    total: alerts.length,
    active: alerts.filter(a => a.enabled).length,
    triggered: alerts.filter(a => a.triggered).length,
    todayTriggers: history.filter(h =>
      new Date(h.timestamp).toDateString() === new Date().toDateString()
    ).length,
  }), [alerts, history])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="animate-spin text-cyan-400" size={32} />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Bell className="text-cyan-400" />
            Price Alerts
          </h2>
          <p className="text-gray-400 mt-1">Get notified when tokens hit your targets</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors flex items-center gap-2"
        >
          <Plus size={18} />
          New Alert
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center gap-2 text-gray-400 mb-1">
            <Bell size={16} />
            <span className="text-sm">Total Alerts</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.total}</p>
        </div>
        <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center gap-2 text-green-400 mb-1">
            <Activity size={16} />
            <span className="text-sm">Active</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.active}</p>
        </div>
        <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center gap-2 text-yellow-400 mb-1">
            <Zap size={16} />
            <span className="text-sm">Triggered</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.triggered}</p>
        </div>
        <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center gap-2 text-purple-400 mb-1">
            <Clock size={16} />
            <span className="text-sm">Today</span>
          </div>
          <p className="text-2xl font-bold text-white">{stats.todayTriggers}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search alerts..."
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter size={16} className="text-gray-400" />
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Alerts</option>
            <option value="active">Active Only</option>
            <option value="triggered">Triggered</option>
          </select>
        </div>

        <button
          onClick={fetchAlerts}
          className="p-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors"
        >
          <RefreshCw size={18} />
        </button>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        {/* Alerts Grid */}
        <div className="md:col-span-2">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Bell size={18} className="text-cyan-400" />
            Your Alerts
          </h3>

          {filteredAlerts.length === 0 ? (
            <div className="p-8 bg-gray-800/30 rounded-lg border border-gray-700 text-center">
              <Bell size={48} className="mx-auto text-gray-600 mb-4" />
              <h4 className="text-lg font-medium text-gray-400 mb-2">No alerts yet</h4>
              <p className="text-gray-500 mb-4">
                Create your first price alert to get notified when tokens hit your targets
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg transition-colors inline-flex items-center gap-2"
              >
                <Plus size={18} />
                Create Alert
              </button>
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 gap-4">
              {filteredAlerts.map(alert => (
                <AlertCard
                  key={alert.id}
                  alert={alert}
                  onToggle={handleToggleAlert}
                  onDelete={handleDeleteAlert}
                />
              ))}
            </div>
          )}
        </div>

        {/* Alert History */}
        <div>
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Clock size={18} className="text-purple-400" />
            Recent Triggers
          </h3>

          {history.length === 0 ? (
            <div className="p-6 bg-gray-800/30 rounded-lg border border-gray-700 text-center">
              <Clock size={32} className="mx-auto text-gray-600 mb-2" />
              <p className="text-gray-500 text-sm">No triggers yet</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {history.slice(0, 20).map((event, idx) => (
                <AlertHistoryItem key={idx} event={event} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Alert Modal */}
      <CreateAlertModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateAlert}
      />
    </div>
  )
}
