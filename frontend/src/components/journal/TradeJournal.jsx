import React, { useState, useMemo } from 'react'
import {
  BookOpen,
  Plus,
  Search,
  Filter,
  Calendar,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  Clock,
  Tag,
  Edit3,
  Trash2,
  ChevronDown,
  ChevronUp,
  BarChart3,
  Camera,
  FileText,
  Save,
  X,
  Star,
  AlertTriangle,
  CheckCircle,
  Image,
  MessageSquare
} from 'lucide-react'

export function TradeJournal() {
  const [viewMode, setViewMode] = useState('list') // list, calendar, analytics, add
  const [filterToken, setFilterToken] = useState('all')
  const [filterResult, setFilterResult] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTrade, setSelectedTrade] = useState(null)
  const [showAddModal, setShowAddModal] = useState(false)

  const tokens = ['all', 'SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Mock trade journal entries
  const trades = useMemo(() => {
    const strategies = ['Momentum', 'Breakout', 'Mean Reversion', 'Scalp', 'Swing', 'DCA']
    const emotions = ['Confident', 'Anxious', 'FOMO', 'Calm', 'Greedy', 'Fearful']
    const mistakes = ['Overtraded', 'Early exit', 'Late entry', 'No stop loss', 'Revenge trade', null]
    const lessons = [
      'Wait for confirmation before entering',
      'Stick to the plan no matter what',
      'Position size was too large',
      'Should have taken partial profits',
      'Entry timing was good but exit was poor',
      'Market conditions were not ideal for this setup'
    ]

    return Array.from({ length: 30 }, (_, i) => {
      const isWin = Math.random() > 0.45
      const entryPrice = Math.random() * 200 + 20
      const exitPrice = isWin
        ? entryPrice * (1 + Math.random() * 0.25)
        : entryPrice * (1 - Math.random() * 0.12)
      const size = Math.floor(Math.random() * 5000) + 500
      const pnl = (exitPrice - entryPrice) / entryPrice * size
      const pnlPercent = ((exitPrice - entryPrice) / entryPrice * 100)

      return {
        id: i + 1,
        date: new Date(Date.now() - i * 24 * 60 * 60 * 1000 * Math.random() * 3).toISOString().split('T')[0],
        token: tokens[Math.floor(Math.random() * (tokens.length - 1)) + 1],
        type: Math.random() > 0.5 ? 'long' : 'short',
        entryPrice,
        exitPrice,
        size,
        pnl,
        pnlPercent,
        isWin,
        strategy: strategies[Math.floor(Math.random() * strategies.length)],
        timeframe: ['1m', '5m', '15m', '1h', '4h', '1D'][Math.floor(Math.random() * 6)],
        entryReason: 'Breakout above resistance with strong volume',
        exitReason: isWin ? 'Hit take profit target' : 'Stop loss triggered',
        emotion: emotions[Math.floor(Math.random() * emotions.length)],
        mistake: mistakes[Math.floor(Math.random() * mistakes.length)],
        lesson: lessons[Math.floor(Math.random() * lessons.length)],
        rating: Math.floor(Math.random() * 5) + 1,
        tags: ['trending', 'high-volume', 'earnings'].slice(0, Math.floor(Math.random() * 3) + 1),
        screenshots: Math.random() > 0.7 ? ['entry.png', 'exit.png'] : [],
        notes: 'Market was showing strength across the board. Entry was clean with good R:R setup.'
      }
    }).sort((a, b) => new Date(b.date) - new Date(a.date))
  }, [])

  // Filter trades
  const filteredTrades = useMemo(() => {
    return trades.filter(trade => {
      if (filterToken !== 'all' && trade.token !== filterToken) return false
      if (filterResult === 'wins' && !trade.isWin) return false
      if (filterResult === 'losses' && trade.isWin) return false
      if (searchQuery && !trade.token.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !trade.strategy.toLowerCase().includes(searchQuery.toLowerCase())) return false
      return true
    })
  }, [trades, filterToken, filterResult, searchQuery])

  // Analytics
  const analytics = useMemo(() => {
    const wins = trades.filter(t => t.isWin)
    const losses = trades.filter(t => !t.isWin)
    const totalPnl = trades.reduce((sum, t) => sum + t.pnl, 0)
    const avgWin = wins.length ? wins.reduce((sum, t) => sum + t.pnl, 0) / wins.length : 0
    const avgLoss = losses.length ? Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0) / losses.length) : 0

    const byStrategy = {}
    trades.forEach(t => {
      if (!byStrategy[t.strategy]) {
        byStrategy[t.strategy] = { wins: 0, losses: 0, pnl: 0 }
      }
      byStrategy[t.strategy][t.isWin ? 'wins' : 'losses']++
      byStrategy[t.strategy].pnl += t.pnl
    })

    const byToken = {}
    trades.forEach(t => {
      if (!byToken[t.token]) {
        byToken[t.token] = { wins: 0, losses: 0, pnl: 0 }
      }
      byToken[t.token][t.isWin ? 'wins' : 'losses']++
      byToken[t.token].pnl += t.pnl
    })

    const byEmotion = {}
    trades.forEach(t => {
      if (!byEmotion[t.emotion]) {
        byEmotion[t.emotion] = { wins: 0, losses: 0 }
      }
      byEmotion[t.emotion][t.isWin ? 'wins' : 'losses']++
    })

    return {
      totalTrades: trades.length,
      wins: wins.length,
      losses: losses.length,
      winRate: (wins.length / trades.length * 100).toFixed(1),
      totalPnl,
      avgWin,
      avgLoss,
      profitFactor: avgLoss > 0 ? (avgWin * wins.length) / (avgLoss * losses.length) : 0,
      avgRating: (trades.reduce((sum, t) => sum + t.rating, 0) / trades.length).toFixed(1),
      byStrategy: Object.entries(byStrategy).map(([name, data]) => ({
        name,
        ...data,
        winRate: ((data.wins / (data.wins + data.losses)) * 100).toFixed(1)
      })).sort((a, b) => b.pnl - a.pnl),
      byToken: Object.entries(byToken).map(([name, data]) => ({
        name,
        ...data,
        winRate: ((data.wins / (data.wins + data.losses)) * 100).toFixed(1)
      })).sort((a, b) => b.pnl - a.pnl),
      byEmotion: Object.entries(byEmotion).map(([name, data]) => ({
        name,
        ...data,
        winRate: ((data.wins / (data.wins + data.losses)) * 100).toFixed(1)
      }))
    }
  }, [trades])

  const formatCurrency = (value) => {
    const prefix = value >= 0 ? '+$' : '-$'
    return prefix + Math.abs(value).toFixed(2)
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BookOpen className="w-6 h-6 text-amber-400" />
          <h2 className="text-xl font-bold text-white">Trade Journal</h2>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg flex items-center gap-2 text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Entry
        </button>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'list', label: 'Trade List' },
          { id: 'calendar', label: 'Calendar' },
          { id: 'analytics', label: 'Analytics' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              viewMode === mode.id
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* List Mode */}
      {viewMode === 'list' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search trades..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm w-48"
              />
            </div>
            <select
              value={filterToken}
              onChange={(e) => setFilterToken(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
            >
              {tokens.map(t => (
                <option key={t} value={t}>{t === 'all' ? 'All Tokens' : t}</option>
              ))}
            </select>
            <select
              value={filterResult}
              onChange={(e) => setFilterResult(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
            >
              <option value="all">All Results</option>
              <option value="wins">Wins Only</option>
              <option value="losses">Losses Only</option>
            </select>
          </div>

          {/* Summary Bar */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-xs">Total Trades</div>
              <div className="text-lg font-bold text-white">{filteredTrades.length}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-xs">Win Rate</div>
              <div className="text-lg font-bold text-white">{analytics.winRate}%</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-xs">Total P&L</div>
              <div className={`text-lg font-bold ${analytics.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatCurrency(analytics.totalPnl)}
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-xs">Profit Factor</div>
              <div className="text-lg font-bold text-white">{analytics.profitFactor.toFixed(2)}</div>
            </div>
          </div>

          {/* Trade List */}
          <div className="space-y-2">
            {filteredTrades.map(trade => (
              <div
                key={trade.id}
                onClick={() => setSelectedTrade(selectedTrade?.id === trade.id ? null : trade)}
                className="bg-white/5 rounded-lg border border-white/10 overflow-hidden cursor-pointer hover:bg-white/10 transition-colors"
              >
                <div className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg ${trade.isWin ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                      {trade.isWin ? (
                        <TrendingUp className="w-5 h-5 text-green-400" />
                      ) : (
                        <TrendingDown className="w-5 h-5 text-red-400" />
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{trade.token}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          trade.type === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {trade.type.toUpperCase()}
                        </span>
                        <span className="text-gray-500 text-xs">{trade.strategy}</span>
                      </div>
                      <div className="text-sm text-gray-400">
                        {trade.date} | ${trade.entryPrice.toFixed(2)} → ${trade.exitPrice.toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <div className="text-right flex items-center gap-4">
                    <div>
                      <div className={`font-medium ${trade.isWin ? 'text-green-400' : 'text-red-400'}`}>
                        {formatCurrency(trade.pnl)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {trade.pnlPercent >= 0 ? '+' : ''}{trade.pnlPercent.toFixed(2)}%
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Star
                          key={i}
                          className={`w-3 h-3 ${i < trade.rating ? 'text-amber-400 fill-amber-400' : 'text-gray-600'}`}
                        />
                      ))}
                    </div>
                    <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${
                      selectedTrade?.id === trade.id ? 'rotate-180' : ''
                    }`} />
                  </div>
                </div>

                {/* Expanded Details */}
                {selectedTrade?.id === trade.id && (
                  <div className="px-4 pb-4 border-t border-white/10 pt-4">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                      <div>
                        <div className="text-gray-400 text-xs mb-1">Entry Reason</div>
                        <div className="text-white text-sm">{trade.entryReason}</div>
                      </div>
                      <div>
                        <div className="text-gray-400 text-xs mb-1">Exit Reason</div>
                        <div className="text-white text-sm">{trade.exitReason}</div>
                      </div>
                      <div>
                        <div className="text-gray-400 text-xs mb-1">Emotion</div>
                        <div className="text-white text-sm">{trade.emotion}</div>
                      </div>
                      <div>
                        <div className="text-gray-400 text-xs mb-1">Timeframe</div>
                        <div className="text-white text-sm">{trade.timeframe}</div>
                      </div>
                    </div>
                    {trade.mistake && (
                      <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
                        <div className="flex items-center gap-2 text-red-400 text-sm">
                          <AlertTriangle className="w-4 h-4" />
                          Mistake: {trade.mistake}
                        </div>
                      </div>
                    )}
                    <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg mb-4">
                      <div className="text-blue-400 text-sm">
                        <strong>Lesson:</strong> {trade.lesson}
                      </div>
                    </div>
                    {trade.notes && (
                      <div className="text-gray-400 text-sm">
                        <strong className="text-gray-300">Notes:</strong> {trade.notes}
                      </div>
                    )}
                    {trade.tags.length > 0 && (
                      <div className="flex gap-2 mt-3">
                        {trade.tags.map(tag => (
                          <span key={tag} className="px-2 py-1 bg-white/10 rounded text-xs text-gray-300">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Calendar Mode */}
      {viewMode === 'calendar' && (
        <div className="space-y-4">
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <div className="text-center text-white font-medium mb-4">
              {new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </div>
            <div className="grid grid-cols-7 gap-2 mb-2">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                <div key={day} className="text-center text-gray-500 text-xs py-2">{day}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-2">
              {Array.from({ length: 35 }, (_, i) => {
                const day = i - new Date(new Date().getFullYear(), new Date().getMonth(), 1).getDay() + 1
                const isCurrentMonth = day > 0 && day <= 31
                const dateStr = `${new Date().getFullYear()}-${String(new Date().getMonth() + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                const dayTrades = trades.filter(t => t.date === dateStr)
                const dayPnl = dayTrades.reduce((sum, t) => sum + t.pnl, 0)

                return (
                  <div
                    key={i}
                    className={`aspect-square rounded-lg p-1 text-center ${
                      isCurrentMonth ? 'bg-white/5 border border-white/10' : 'opacity-30'
                    }`}
                  >
                    {isCurrentMonth && (
                      <>
                        <div className="text-xs text-gray-400">{day}</div>
                        {dayTrades.length > 0 && (
                          <div className={`text-xs font-medium mt-1 ${dayPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {dayTrades.length}t
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Analytics Mode */}
      {viewMode === 'analytics' && (
        <div className="space-y-6">
          {/* Performance by Strategy */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Performance by Strategy</h3>
            <div className="space-y-3">
              {analytics.byStrategy.map(strat => (
                <div key={strat.name} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div>
                    <div className="text-white font-medium">{strat.name}</div>
                    <div className="text-xs text-gray-500">{strat.wins}W / {strat.losses}L</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-medium ${strat.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatCurrency(strat.pnl)}
                    </div>
                    <div className="text-xs text-gray-500">{strat.winRate}% WR</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Performance by Token */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Performance by Token</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {analytics.byToken.map(token => (
                <div key={token.name} className="p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-medium">{token.name}</span>
                    <span className="text-xs text-gray-500">{token.winRate}%</span>
                  </div>
                  <div className={`text-lg font-bold ${token.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(token.pnl)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Emotion Analysis */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Performance by Emotion</h3>
            <div className="space-y-3">
              {analytics.byEmotion.map(emotion => (
                <div key={emotion.name}>
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-400">{emotion.name}</span>
                    <span className={parseFloat(emotion.winRate) >= 50 ? 'text-green-400' : 'text-red-400'}>
                      {emotion.winRate}% win rate
                    </span>
                  </div>
                  <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${parseFloat(emotion.winRate) >= 50 ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{ width: `${emotion.winRate}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Add Trade Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-white">New Trade Entry</h3>
              <button onClick={() => setShowAddModal(false)} className="p-2 hover:bg-white/10 rounded-lg">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Token</label>
                  <select className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white">
                    {tokens.slice(1).map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Type</label>
                  <select className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white">
                    <option value="long">Long</option>
                    <option value="short">Short</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Entry Price</label>
                  <input type="number" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white" />
                </div>
                <div>
                  <label className="text-gray-400 text-sm block mb-2">Exit Price</label>
                  <input type="number" className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white" />
                </div>
              </div>
              <div>
                <label className="text-gray-400 text-sm block mb-2">Entry Reason</label>
                <textarea className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white h-20" />
              </div>
              <div>
                <label className="text-gray-400 text-sm block mb-2">Exit Reason</label>
                <textarea className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white h-20" />
              </div>
              <div>
                <label className="text-gray-400 text-sm block mb-2">Lessons Learned</label>
                <textarea className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white h-20" />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 bg-white/5 text-gray-400 rounded-lg hover:bg-white/10"
                >
                  Cancel
                </button>
                <button className="px-4 py-2 bg-amber-500 text-white rounded-lg hover:bg-amber-600 flex items-center gap-2">
                  <Save className="w-4 h-4" />
                  Save Entry
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default TradeJournal
