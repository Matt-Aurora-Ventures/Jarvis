import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  BookOpen,
  Plus,
  Edit3,
  Trash2,
  Calendar,
  Clock,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Target,
  AlertCircle,
  CheckCircle,
  XCircle,
  Tag,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  BarChart3,
  PieChart,
  Activity,
  Percent,
  ArrowUpRight,
  ArrowDownRight,
  Image,
  Paperclip,
  MessageSquare,
  Star,
  StarOff,
  Eye,
  EyeOff,
  Download,
  Upload,
  RefreshCw,
  Lightbulb,
  Brain,
  Zap,
  Award,
  Trophy,
  Flame,
  ThumbsUp,
  ThumbsDown,
  Hash,
  Layers,
  Settings,
  FileText
} from 'lucide-react'

// Trade outcome types
const TRADE_OUTCOMES = {
  WIN: { label: 'Win', color: 'green', icon: ThumbsUp },
  LOSS: { label: 'Loss', color: 'red', icon: ThumbsDown },
  BREAKEVEN: { label: 'Breakeven', color: 'gray', icon: Target },
}

// Trade setups
const TRADE_SETUPS = {
  BREAKOUT: 'Breakout',
  PULLBACK: 'Pullback',
  REVERSAL: 'Reversal',
  MOMENTUM: 'Momentum',
  RANGE: 'Range Trade',
  NEWS: 'News Play',
  SCALP: 'Scalp',
  SWING: 'Swing',
  DEGEN: 'Degen',
  OTHER: 'Other',
}

// Emotion states
const EMOTIONS = {
  CALM: { label: 'Calm', color: 'blue', emoji: '😌' },
  CONFIDENT: { label: 'Confident', color: 'green', emoji: '😎' },
  FOMO: { label: 'FOMO', color: 'orange', emoji: '😰' },
  FEAR: { label: 'Fear', color: 'red', emoji: '😨' },
  GREED: { label: 'Greed', color: 'yellow', emoji: '🤑' },
  REVENGE: { label: 'Revenge', color: 'purple', emoji: '😤' },
  BORED: { label: 'Bored', color: 'gray', emoji: '😐' },
}

// Mistake types
const MISTAKES = {
  FOMO_ENTRY: 'FOMO Entry',
  EARLY_EXIT: 'Exited Too Early',
  LATE_EXIT: 'Exited Too Late',
  OVERSIZED: 'Position Too Large',
  NO_STOP: 'No Stop Loss',
  MOVED_STOP: 'Moved Stop Loss',
  REVENGE_TRADE: 'Revenge Trade',
  IGNORED_PLAN: 'Ignored Trade Plan',
  POOR_RR: 'Poor Risk/Reward',
  BAD_TIMING: 'Bad Entry Timing',
}

// Format number
function formatNumber(num, decimals = 2) {
  if (num >= 1000000) return (num / 1000000).toFixed(decimals) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(decimals) + 'K'
  return num.toFixed(decimals)
}

// Format percentage
function formatPercent(num) {
  const sign = num >= 0 ? '+' : ''
  return `${sign}${num.toFixed(2)}%`
}

// Trade Entry/Edit Modal
function TradeModal({ trade, isOpen, onClose, onSave }) {
  const [formData, setFormData] = useState({
    date: new Date().toISOString().split('T')[0],
    time: new Date().toTimeString().slice(0, 5),
    token: '',
    direction: 'LONG',
    entryPrice: '',
    exitPrice: '',
    positionSize: '',
    outcome: 'WIN',
    setup: 'BREAKOUT',
    emotion: 'CALM',
    plannedRR: '',
    actualRR: '',
    notes: '',
    lessons: '',
    mistakes: [],
    tags: [],
    screenshots: [],
    rating: 3,
  })

  useEffect(() => {
    if (trade) {
      setFormData({
        ...trade,
        date: trade.date || new Date().toISOString().split('T')[0],
        time: trade.time || new Date().toTimeString().slice(0, 5),
        mistakes: trade.mistakes || [],
        tags: trade.tags || [],
        screenshots: trade.screenshots || [],
      })
    }
  }, [trade])

  if (!isOpen) return null

  const handleSubmit = e => {
    e.preventDefault()

    // Calculate P&L
    const entry = Number(formData.entryPrice)
    const exit = Number(formData.exitPrice)
    const size = Number(formData.positionSize)

    let pnl = 0
    let pnlPercent = 0

    if (entry && exit && size) {
      if (formData.direction === 'LONG') {
        pnl = (exit - entry) * size
        pnlPercent = ((exit - entry) / entry) * 100
      } else {
        pnl = (entry - exit) * size
        pnlPercent = ((entry - exit) / entry) * 100
      }
    }

    onSave({
      ...formData,
      pnl,
      pnlPercent,
      id: trade?.id || Date.now().toString(),
    })
    onClose()
  }

  const toggleMistake = mistake => {
    setFormData(prev => ({
      ...prev,
      mistakes: prev.mistakes.includes(mistake)
        ? prev.mistakes.filter(m => m !== mistake)
        : [...prev.mistakes, mistake]
    }))
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto border border-gray-700">
        <form onSubmit={handleSubmit} className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h3 className="text-xl font-semibold flex items-center gap-2">
              <Edit3 className="w-5 h-5 text-blue-400" />
              {trade ? 'Edit Trade' : 'Log New Trade'}
            </h3>
            <button type="button" onClick={onClose} className="text-gray-400 hover:text-white">
              <XCircle className="w-6 h-6" />
            </button>
          </div>

          <div className="space-y-6">
            {/* Date/Time & Token */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Date</label>
                <input
                  type="date"
                  value={formData.date}
                  onChange={e => setFormData({ ...formData, date: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Time</label>
                <input
                  type="time"
                  value={formData.time}
                  onChange={e => setFormData({ ...formData, time: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Token</label>
                <input
                  type="text"
                  value={formData.token}
                  onChange={e => setFormData({ ...formData, token: e.target.value.toUpperCase() })}
                  placeholder="SOL, BONK, etc"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                  required
                />
              </div>
            </div>

            {/* Direction & Setup */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Direction</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, direction: 'LONG' })}
                    className={`flex-1 py-2 rounded-lg ${
                      formData.direction === 'LONG'
                        ? 'bg-green-500/20 text-green-400 border border-green-500'
                        : 'bg-gray-700 text-gray-400 border border-gray-600'
                    }`}
                  >
                    Long
                  </button>
                  <button
                    type="button"
                    onClick={() => setFormData({ ...formData, direction: 'SHORT' })}
                    className={`flex-1 py-2 rounded-lg ${
                      formData.direction === 'SHORT'
                        ? 'bg-red-500/20 text-red-400 border border-red-500'
                        : 'bg-gray-700 text-gray-400 border border-gray-600'
                    }`}
                  >
                    Short
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Setup</label>
                <select
                  value={formData.setup}
                  onChange={e => setFormData({ ...formData, setup: e.target.value })}
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                >
                  {Object.entries(TRADE_SETUPS).map(([key, label]) => (
                    <option key={key} value={key}>{label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Prices & Size */}
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Entry Price</label>
                <input
                  type="number"
                  step="any"
                  value={formData.entryPrice}
                  onChange={e => setFormData({ ...formData, entryPrice: e.target.value })}
                  placeholder="0.00"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Exit Price</label>
                <input
                  type="number"
                  step="any"
                  value={formData.exitPrice}
                  onChange={e => setFormData({ ...formData, exitPrice: e.target.value })}
                  placeholder="0.00"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Position Size</label>
                <input
                  type="number"
                  step="any"
                  value={formData.positionSize}
                  onChange={e => setFormData({ ...formData, positionSize: e.target.value })}
                  placeholder="0.00"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                />
              </div>
            </div>

            {/* Outcome */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Outcome</label>
              <div className="flex gap-2">
                {Object.entries(TRADE_OUTCOMES).map(([key, { label, color }]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setFormData({ ...formData, outcome: key })}
                    className={`flex-1 py-2 rounded-lg ${
                      formData.outcome === key
                        ? `bg-${color}-500/20 text-${color}-400 border border-${color}-500`
                        : 'bg-gray-700 text-gray-400 border border-gray-600'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Emotion */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Emotional State</label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(EMOTIONS).map(([key, { label, emoji }]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => setFormData({ ...formData, emotion: key })}
                    className={`px-3 py-1.5 rounded-lg text-sm ${
                      formData.emotion === key
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500'
                        : 'bg-gray-700 text-gray-400 border border-gray-600'
                    }`}
                  >
                    {emoji} {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Mistakes */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Mistakes Made</label>
              <div className="flex flex-wrap gap-2">
                {Object.entries(MISTAKES).map(([key, label]) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => toggleMistake(key)}
                    className={`px-2 py-1 rounded text-xs ${
                      formData.mistakes.includes(key)
                        ? 'bg-red-500/20 text-red-400 border border-red-500'
                        : 'bg-gray-700 text-gray-400 border border-gray-600'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* Rating */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Trade Rating</label>
              <div className="flex gap-1">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    type="button"
                    onClick={() => setFormData({ ...formData, rating: star })}
                    className="p-1"
                  >
                    <Star
                      className={`w-6 h-6 ${
                        star <= formData.rating
                          ? 'fill-yellow-400 text-yellow-400'
                          : 'text-gray-600'
                      }`}
                    />
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm text-gray-400 mb-1">Trade Notes</label>
              <textarea
                value={formData.notes}
                onChange={e => setFormData({ ...formData, notes: e.target.value })}
                placeholder="What happened? Why did you take this trade?"
                rows={3}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg resize-none"
              />
            </div>

            {/* Lessons */}
            <div>
              <label className="block text-sm text-gray-400 mb-1 flex items-center gap-1">
                <Lightbulb className="w-4 h-4 text-yellow-400" />
                Lessons Learned
              </label>
              <textarea
                value={formData.lessons}
                onChange={e => setFormData({ ...formData, lessons: e.target.value })}
                placeholder="What did you learn from this trade?"
                rows={2}
                className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg resize-none"
              />
            </div>

            {/* Submit */}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex-1 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
              >
                {trade ? 'Update Trade' : 'Log Trade'}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}

// Trade Card Component
function TradeCard({ trade, onEdit, onDelete, onView }) {
  const outcome = TRADE_OUTCOMES[trade.outcome] || TRADE_OUTCOMES.WIN
  const OutcomeIcon = outcome.icon

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 hover:border-gray-600 transition-colors p-4">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${
            trade.outcome === 'WIN' ? 'bg-green-500/20' :
            trade.outcome === 'LOSS' ? 'bg-red-500/20' : 'bg-gray-700'
          }`}>
            <OutcomeIcon className={`w-5 h-5 ${
              trade.outcome === 'WIN' ? 'text-green-400' :
              trade.outcome === 'LOSS' ? 'text-red-400' : 'text-gray-400'
            }`} />
          </div>
          <div>
            <div className="font-semibold flex items-center gap-2">
              {trade.token}
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
              }`}>
                {trade.direction}
              </span>
            </div>
            <div className="text-sm text-gray-400 flex items-center gap-2">
              <Calendar className="w-3 h-3" />
              {trade.date}
              {trade.time && (
                <>
                  <Clock className="w-3 h-3 ml-1" />
                  {trade.time}
                </>
              )}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-lg font-bold ${
            (trade.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {(trade.pnl || 0) >= 0 ? '+' : ''}{formatNumber(trade.pnl || 0)}
          </div>
          <div className={`text-sm ${
            (trade.pnlPercent || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {formatPercent(trade.pnlPercent || 0)}
          </div>
        </div>
      </div>

      {/* Trade Details */}
      <div className="grid grid-cols-4 gap-2 mb-3 text-sm">
        <div>
          <div className="text-gray-500 text-xs">Entry</div>
          <div className="font-medium">${trade.entryPrice}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Exit</div>
          <div className="font-medium">${trade.exitPrice || '-'}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Size</div>
          <div className="font-medium">{formatNumber(trade.positionSize || 0)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Setup</div>
          <div className="font-medium">{TRADE_SETUPS[trade.setup] || trade.setup}</div>
        </div>
      </div>

      {/* Emotion & Mistakes */}
      <div className="flex items-center gap-2 mb-3">
        {trade.emotion && EMOTIONS[trade.emotion] && (
          <span className="text-sm">{EMOTIONS[trade.emotion].emoji}</span>
        )}
        {trade.mistakes && trade.mistakes.length > 0 && (
          <span className="px-2 py-0.5 bg-red-500/10 text-red-400 rounded text-xs">
            {trade.mistakes.length} mistake(s)
          </span>
        )}
        {trade.rating && (
          <div className="flex items-center gap-0.5 ml-auto">
            {[1, 2, 3, 4, 5].map(star => (
              <Star
                key={star}
                className={`w-3 h-3 ${
                  star <= trade.rating ? 'fill-yellow-400 text-yellow-400' : 'text-gray-600'
                }`}
              />
            ))}
          </div>
        )}
      </div>

      {/* Notes Preview */}
      {trade.notes && (
        <div className="text-sm text-gray-400 mb-3 line-clamp-2">
          {trade.notes}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={() => onView?.(trade)}
          className="flex-1 py-1.5 bg-gray-700 text-gray-300 rounded text-sm hover:bg-gray-600 transition-colors flex items-center justify-center gap-1"
        >
          <Eye className="w-3 h-3" />
          View
        </button>
        <button
          onClick={() => onEdit?.(trade)}
          className="flex-1 py-1.5 bg-blue-500/20 text-blue-400 rounded text-sm hover:bg-blue-500/30 transition-colors flex items-center justify-center gap-1"
        >
          <Edit3 className="w-3 h-3" />
          Edit
        </button>
        <button
          onClick={() => onDelete?.(trade.id)}
          className="px-3 py-1.5 bg-red-500/20 text-red-400 rounded text-sm hover:bg-red-500/30 transition-colors"
        >
          <Trash2 className="w-3 h-3" />
        </button>
      </div>
    </div>
  )
}

// Analytics Dashboard Component
function AnalyticsDashboard({ trades }) {
  const stats = useMemo(() => {
    if (!trades.length) return null

    const wins = trades.filter(t => t.outcome === 'WIN')
    const losses = trades.filter(t => t.outcome === 'LOSS')
    const totalPnL = trades.reduce((sum, t) => sum + (t.pnl || 0), 0)

    const winRate = (wins.length / trades.length) * 100
    const avgWin = wins.length ? wins.reduce((sum, t) => sum + (t.pnl || 0), 0) / wins.length : 0
    const avgLoss = losses.length ? Math.abs(losses.reduce((sum, t) => sum + (t.pnl || 0), 0) / losses.length) : 0
    const profitFactor = avgLoss ? avgWin / avgLoss : avgWin

    // Streak calculation
    let currentStreak = 0
    let maxWinStreak = 0
    let maxLossStreak = 0
    let tempStreak = 0

    trades.forEach((trade, i) => {
      if (i === 0 || trade.outcome === trades[i-1].outcome) {
        tempStreak++
      } else {
        if (trades[i-1].outcome === 'WIN') {
          maxWinStreak = Math.max(maxWinStreak, tempStreak)
        } else if (trades[i-1].outcome === 'LOSS') {
          maxLossStreak = Math.max(maxLossStreak, tempStreak)
        }
        tempStreak = 1
      }
      currentStreak = tempStreak
    })

    // Check last streak
    if (trades[trades.length - 1]?.outcome === 'WIN') {
      maxWinStreak = Math.max(maxWinStreak, tempStreak)
    } else if (trades[trades.length - 1]?.outcome === 'LOSS') {
      maxLossStreak = Math.max(maxLossStreak, tempStreak)
    }

    // Setup analysis
    const setupStats = {}
    trades.forEach(trade => {
      if (!setupStats[trade.setup]) {
        setupStats[trade.setup] = { wins: 0, losses: 0, pnl: 0 }
      }
      setupStats[trade.setup].pnl += trade.pnl || 0
      if (trade.outcome === 'WIN') setupStats[trade.setup].wins++
      else if (trade.outcome === 'LOSS') setupStats[trade.setup].losses++
    })

    // Emotion analysis
    const emotionStats = {}
    trades.forEach(trade => {
      if (!emotionStats[trade.emotion]) {
        emotionStats[trade.emotion] = { wins: 0, losses: 0, pnl: 0 }
      }
      emotionStats[trade.emotion].pnl += trade.pnl || 0
      if (trade.outcome === 'WIN') emotionStats[trade.emotion].wins++
      else if (trade.outcome === 'LOSS') emotionStats[trade.emotion].losses++
    })

    // Mistake frequency
    const mistakeFreq = {}
    trades.forEach(trade => {
      (trade.mistakes || []).forEach(m => {
        mistakeFreq[m] = (mistakeFreq[m] || 0) + 1
      })
    })

    return {
      totalTrades: trades.length,
      wins: wins.length,
      losses: losses.length,
      winRate,
      totalPnL,
      avgWin,
      avgLoss,
      profitFactor,
      currentStreak,
      currentStreakType: trades[trades.length - 1]?.outcome || 'WIN',
      maxWinStreak,
      maxLossStreak,
      bestTrade: Math.max(...trades.map(t => t.pnl || 0)),
      worstTrade: Math.min(...trades.map(t => t.pnl || 0)),
      setupStats,
      emotionStats,
      mistakeFreq,
    }
  }, [trades])

  if (!stats) {
    return (
      <div className="text-center py-12 text-gray-400">
        <BarChart3 className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>No trades logged yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Total P&L</div>
          <div className={`text-2xl font-bold ${stats.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.totalPnL >= 0 ? '+' : ''}{formatNumber(stats.totalPnL)}
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Win Rate</div>
          <div className="text-2xl font-bold text-blue-400">{stats.winRate.toFixed(1)}%</div>
          <div className="text-xs text-gray-500">{stats.wins}W / {stats.losses}L</div>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Profit Factor</div>
          <div className={`text-2xl font-bold ${stats.profitFactor >= 1 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.profitFactor.toFixed(2)}
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Current Streak</div>
          <div className={`text-2xl font-bold flex items-center gap-1 ${
            stats.currentStreakType === 'WIN' ? 'text-green-400' : 'text-red-400'
          }`}>
            <Flame className="w-5 h-5" />
            {stats.currentStreak}
          </div>
        </div>
      </div>

      {/* Best/Worst & Avg */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Best Trade</div>
          <div className="text-xl font-bold text-green-400">+{formatNumber(stats.bestTrade)}</div>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Worst Trade</div>
          <div className="text-xl font-bold text-red-400">{formatNumber(stats.worstTrade)}</div>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Avg Win</div>
          <div className="text-xl font-bold text-green-400">+{formatNumber(stats.avgWin)}</div>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <div className="text-sm text-gray-400 mb-1">Avg Loss</div>
          <div className="text-xl font-bold text-red-400">-{formatNumber(stats.avgLoss)}</div>
        </div>
      </div>

      {/* Setup Performance */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <h3 className="font-semibold mb-4 flex items-center gap-2">
          <Target className="w-5 h-5 text-purple-400" />
          Setup Performance
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {Object.entries(stats.setupStats)
            .sort((a, b) => b[1].pnl - a[1].pnl)
            .map(([setup, data]) => {
              const total = data.wins + data.losses
              const wr = total ? (data.wins / total) * 100 : 0
              return (
                <div key={setup} className="bg-gray-900 rounded-lg p-3">
                  <div className="font-medium text-sm">{TRADE_SETUPS[setup] || setup}</div>
                  <div className={`text-lg font-bold ${data.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {data.pnl >= 0 ? '+' : ''}{formatNumber(data.pnl)}
                  </div>
                  <div className="text-xs text-gray-400">{wr.toFixed(0)}% WR ({total} trades)</div>
                </div>
              )
            })}
        </div>
      </div>

      {/* Top Mistakes */}
      {Object.keys(stats.mistakeFreq).length > 0 && (
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-400" />
            Common Mistakes
          </h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.mistakeFreq)
              .sort((a, b) => b[1] - a[1])
              .map(([mistake, count]) => (
                <div key={mistake} className="px-3 py-1.5 bg-red-500/10 text-red-400 rounded-lg text-sm">
                  {MISTAKES[mistake] || mistake} ({count}x)
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Main Trading Journal Component
export function TradingJournal({
  trades = [],
  onSaveTrade,
  onDeleteTrade,
  onExport,
  onImport,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedOutcome, setSelectedOutcome] = useState('all')
  const [selectedSetup, setSelectedSetup] = useState('all')
  const [dateRange, setDateRange] = useState('all')
  const [sortBy, setSortBy] = useState('date')
  const [sortOrder, setSortOrder] = useState('desc')
  const [viewMode, setViewMode] = useState('list') // list, analytics
  const [editingTrade, setEditingTrade] = useState(null)
  const [showModal, setShowModal] = useState(false)

  // Filter trades
  const filteredTrades = useMemo(() => {
    let result = [...trades]

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(t =>
        t.token.toLowerCase().includes(query) ||
        (t.notes || '').toLowerCase().includes(query)
      )
    }

    // Outcome filter
    if (selectedOutcome !== 'all') {
      result = result.filter(t => t.outcome === selectedOutcome)
    }

    // Setup filter
    if (selectedSetup !== 'all') {
      result = result.filter(t => t.setup === selectedSetup)
    }

    // Date range filter
    if (dateRange !== 'all') {
      const now = new Date()
      const cutoff = new Date()
      switch (dateRange) {
        case 'today': cutoff.setHours(0, 0, 0, 0); break
        case 'week': cutoff.setDate(now.getDate() - 7); break
        case 'month': cutoff.setMonth(now.getMonth() - 1); break
        case 'year': cutoff.setFullYear(now.getFullYear() - 1); break
      }
      result = result.filter(t => new Date(t.date) >= cutoff)
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'date': comparison = new Date(a.date) - new Date(b.date); break
        case 'pnl': comparison = (a.pnl || 0) - (b.pnl || 0); break
        case 'token': comparison = a.token.localeCompare(b.token); break
        default: comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [trades, searchQuery, selectedOutcome, selectedSetup, dateRange, sortBy, sortOrder])

  const handleSave = trade => {
    onSaveTrade?.(trade)
    setShowModal(false)
    setEditingTrade(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <BookOpen className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Trading Journal</h1>
            <p className="text-sm text-gray-400">Track, analyze, and improve your trading</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { setEditingTrade(null); setShowModal(true) }}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Log Trade
          </button>
        </div>
      </div>

      {/* View Toggle */}
      <div className="flex gap-2">
        <button
          onClick={() => setViewMode('list')}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
            viewMode === 'list'
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
              : 'bg-gray-800 text-gray-400 border border-gray-700'
          }`}
        >
          <FileText className="w-4 h-4" />
          Trade Log
        </button>
        <button
          onClick={() => setViewMode('analytics')}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
            viewMode === 'analytics'
              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
              : 'bg-gray-800 text-gray-400 border border-gray-700'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          Analytics
        </button>
      </div>

      {viewMode === 'analytics' ? (
        <AnalyticsDashboard trades={trades} />
      ) : (
        <>
          {/* Filters */}
          <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search trades..."
                  className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
                />
              </div>

              <select
                value={selectedOutcome}
                onChange={e => setSelectedOutcome(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
              >
                <option value="all">All Outcomes</option>
                {Object.entries(TRADE_OUTCOMES).map(([key, { label }]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>

              <select
                value={selectedSetup}
                onChange={e => setSelectedSetup(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
              >
                <option value="all">All Setups</option>
                {Object.entries(TRADE_SETUPS).map(([key, label]) => (
                  <option key={key} value={key}>{label}</option>
                ))}
              </select>

              <select
                value={dateRange}
                onChange={e => setDateRange(e.target.value)}
                className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
              >
                <option value="all">All Time</option>
                <option value="today">Today</option>
                <option value="week">This Week</option>
                <option value="month">This Month</option>
                <option value="year">This Year</option>
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
                  <option value="date">Date</option>
                  <option value="pnl">P&L</option>
                  <option value="token">Token</option>
                </select>
                <button
                  onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
                  className="p-1 bg-gray-700 rounded"
                >
                  {sortOrder === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
                </button>
              </div>

              <div className="text-sm text-gray-400">
                {filteredTrades.length} trades
              </div>
            </div>
          </div>

          {/* Trade List */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredTrades.map(trade => (
              <TradeCard
                key={trade.id}
                trade={trade}
                onEdit={t => { setEditingTrade(t); setShowModal(true) }}
                onDelete={onDeleteTrade}
              />
            ))}
          </div>

          {filteredTrades.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No trades found</p>
              <button
                onClick={() => setShowModal(true)}
                className="mt-4 px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30"
              >
                Log your first trade
              </button>
            </div>
          )}
        </>
      )}

      {/* Trade Modal */}
      <TradeModal
        trade={editingTrade}
        isOpen={showModal}
        onClose={() => { setShowModal(false); setEditingTrade(null) }}
        onSave={handleSave}
      />
    </div>
  )
}

export default TradingJournal
