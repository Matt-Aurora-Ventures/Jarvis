import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Bot, TrendingUp, TrendingDown, Activity, DollarSign, Percent,
  Play, Pause, Settings, RefreshCw, AlertTriangle, Check, X,
  Clock, BarChart3, Target, Zap, Eye, ChevronDown, ChevronUp,
  Plus, Trash2, Edit3, Copy, Power, AlertCircle, History
} from 'lucide-react'

// Bot types
const BOT_TYPES = {
  DCA: { name: 'DCA Bot', color: '#00D4AA', description: 'Dollar cost averaging' },
  GRID: { name: 'Grid Bot', color: '#FF6B6B', description: 'Grid trading' },
  ARB: { name: 'Arbitrage', color: '#4D6EFF', description: 'Cross-exchange arbitrage' },
  SIGNAL: { name: 'Signal Bot', color: '#FFB800', description: 'Signal-based trading' },
  SNIPER: { name: 'Sniper', color: '#FF0420', description: 'Token launch sniper' },
  COPY: { name: 'Copy Trade', color: '#8B5CF6', description: 'Copy trading bot' }
}

// Bot statuses
const BOT_STATUSES = {
  RUNNING: { label: 'Running', color: 'text-green-400', bg: 'bg-green-500/20' },
  PAUSED: { label: 'Paused', color: 'text-yellow-400', bg: 'bg-yellow-500/20' },
  STOPPED: { label: 'Stopped', color: 'text-white/60', bg: 'bg-white/10' },
  ERROR: { label: 'Error', color: 'text-red-400', bg: 'bg-red-500/20' }
}

// Generate mock bot data
const generateBot = (id) => {
  const types = Object.keys(BOT_TYPES)
  const type = types[Math.floor(Math.random() * types.length)]
  const statuses = ['RUNNING', 'RUNNING', 'RUNNING', 'PAUSED', 'STOPPED', 'ERROR']
  const status = statuses[Math.floor(Math.random() * statuses.length)]

  const invested = Math.random() * 50000 + 1000
  const pnl = (Math.random() - 0.3) * invested * 0.5
  const pnlPercent = (pnl / invested) * 100

  return {
    id,
    name: `${BOT_TYPES[type].name} #${id}`,
    type,
    status,
    pair: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ARB/USDT'][Math.floor(Math.random() * 4)],
    exchange: ['Binance', 'Bybit', 'OKX', 'dYdX'][Math.floor(Math.random() * 4)],
    invested,
    currentValue: invested + pnl,
    pnl,
    pnlPercent,
    totalTrades: Math.floor(Math.random() * 500) + 50,
    winRate: 40 + Math.random() * 40,
    avgProfit: (Math.random() * 5 - 1).toFixed(2),
    maxDrawdown: Math.random() * 30 + 5,
    sharpeRatio: (Math.random() * 3).toFixed(2),
    runtime: Math.floor(Math.random() * 90) + 1,
    lastTrade: new Date(Date.now() - Math.random() * 24 * 60 * 60 * 1000),
    createdAt: new Date(Date.now() - Math.random() * 90 * 24 * 60 * 60 * 1000),
    settings: {
      takeProfit: Math.floor(Math.random() * 10) + 5,
      stopLoss: Math.floor(Math.random() * 10) + 3,
      maxPositionSize: Math.floor(Math.random() * 5000) + 500
    }
  }
}

// Generate trade history
const generateTradeHistory = (botId) => {
  return Array.from({ length: 20 }, (_, idx) => ({
    id: `trade-${idx}`,
    botId,
    pair: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT'][Math.floor(Math.random() * 3)],
    type: Math.random() > 0.5 ? 'BUY' : 'SELL',
    price: Math.random() * 10000 + 100,
    amount: Math.random() * 10 + 0.01,
    pnl: (Math.random() - 0.4) * 500,
    pnlPercent: (Math.random() - 0.4) * 10,
    timestamp: new Date(Date.now() - idx * Math.random() * 60 * 60 * 1000),
    status: 'FILLED'
  }))
}

export function BotPerformance() {
  const [bots, setBots] = useState([])
  const [selectedBot, setSelectedBot] = useState(null)
  const [tradeHistory, setTradeHistory] = useState([])
  const [activeTab, setActiveTab] = useState('overview')
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [filterStatus, setFilterStatus] = useState('ALL')
  const [filterType, setFilterType] = useState('ALL')

  useEffect(() => {
    const initialBots = Array.from({ length: 8 }, (_, idx) => generateBot(idx + 1))
    setBots(initialBots)
    if (initialBots.length > 0) {
      setSelectedBot(initialBots[0])
      setTradeHistory(generateTradeHistory(initialBots[0].id))
    }
  }, [])

  useEffect(() => {
    if (selectedBot) {
      setTradeHistory(generateTradeHistory(selectedBot.id))
    }
  }, [selectedBot])

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true)
    setTimeout(() => {
      setBots(prev => prev.map(bot => ({
        ...bot,
        pnl: bot.pnl + (Math.random() - 0.5) * 100,
        currentValue: bot.currentValue + (Math.random() - 0.5) * 100,
        totalTrades: bot.totalTrades + Math.floor(Math.random() * 5),
        lastTrade: new Date()
      })))
      setIsRefreshing(false)
    }, 1500)
  }, [])

  const handleToggleBot = useCallback((botId, action) => {
    setBots(prev => prev.map(bot => {
      if (bot.id === botId) {
        return {
          ...bot,
          status: action === 'start' ? 'RUNNING' :
                  action === 'pause' ? 'PAUSED' : 'STOPPED'
        }
      }
      return bot
    }))
  }, [])

  const handleDeleteBot = useCallback((botId) => {
    setBots(prev => prev.filter(bot => bot.id !== botId))
    if (selectedBot?.id === botId) {
      setSelectedBot(bots.find(b => b.id !== botId) || null)
    }
  }, [selectedBot, bots])

  // Aggregated metrics
  const totalInvested = useMemo(() =>
    bots.reduce((sum, bot) => sum + bot.invested, 0),
    [bots]
  )

  const totalPnl = useMemo(() =>
    bots.reduce((sum, bot) => sum + bot.pnl, 0),
    [bots]
  )

  const activeBots = useMemo(() =>
    bots.filter(bot => bot.status === 'RUNNING').length,
    [bots]
  )

  const avgWinRate = useMemo(() => {
    if (bots.length === 0) return 0
    return bots.reduce((sum, bot) => sum + bot.winRate, 0) / bots.length
  }, [bots])

  const filteredBots = useMemo(() => {
    return bots.filter(bot => {
      if (filterStatus !== 'ALL' && bot.status !== filterStatus) return false
      if (filterType !== 'ALL' && bot.type !== filterType) return false
      return true
    })
  }, [bots, filterStatus, filterType])

  const formatCurrency = (value) => {
    if (Math.abs(value) >= 1e6) return '$' + (value / 1e6).toFixed(2) + 'M'
    if (Math.abs(value) >= 1e3) return '$' + (value / 1e3).toFixed(2) + 'K'
    return '$' + value.toFixed(2)
  }

  const formatPercent = (value) => {
    const prefix = value >= 0 ? '+' : ''
    return prefix + value.toFixed(2) + '%'
  }

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
            <Bot className="w-8 h-8 text-cyan-400" />
            Bot Performance
          </h1>
          <p className="text-white/60">Monitor and manage your automated trading strategies</p>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Bot
          </button>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
          >
            <RefreshCw className={`w-5 h-5 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Global Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <DollarSign className="w-4 h-4" />
            Total Invested
          </div>
          <div className="text-2xl font-bold">{formatCurrency(totalInvested)}</div>
          <div className="text-sm text-white/60">across {bots.length} bots</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <TrendingUp className="w-4 h-4" />
            Total P&L
          </div>
          <div className={`text-2xl font-bold ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatCurrency(totalPnl)}
          </div>
          <div className={`text-sm ${totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {formatPercent((totalPnl / totalInvested) * 100)}
          </div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Activity className="w-4 h-4" />
            Active Bots
          </div>
          <div className="text-2xl font-bold text-green-400">{activeBots}</div>
          <div className="text-sm text-white/60">of {bots.length} total</div>
        </div>

        <div className="bg-white/5 rounded-xl border border-white/10 p-4">
          <div className="flex items-center gap-2 text-white/60 mb-2">
            <Target className="w-4 h-4" />
            Avg Win Rate
          </div>
          <div className="text-2xl font-bold">{avgWinRate.toFixed(1)}%</div>
          <div className="text-sm text-white/60">across all bots</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Bot List */}
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex gap-2">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none"
            >
              <option value="ALL" className="bg-[#0a0e14]">All Status</option>
              {Object.entries(BOT_STATUSES).map(([key, status]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">{status.label}</option>
              ))}
            </select>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm focus:outline-none"
            >
              <option value="ALL" className="bg-[#0a0e14]">All Types</option>
              {Object.entries(BOT_TYPES).map(([key, type]) => (
                <option key={key} value={key} className="bg-[#0a0e14]">{type.name}</option>
              ))}
            </select>
          </div>

          {/* Bot Cards */}
          {filteredBots.map((bot, idx) => (
            <div
              key={bot.id}
              className={`bg-white/5 rounded-xl border border-white/10 p-4 cursor-pointer transition-colors ${
                selectedBot?.id === bot.id ? 'border-cyan-500/50 bg-cyan-500/5' : 'hover:bg-white/10'
              }`}
              onClick={() => setSelectedBot(bot)}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: BOT_TYPES[bot.type].color + '20' }}
                  >
                    <Bot className="w-5 h-5" style={{ color: BOT_TYPES[bot.type].color }} />
                  </div>
                  <div>
                    <div className="font-medium">{bot.name}</div>
                    <div className="text-sm text-white/60">{bot.pair} | {bot.exchange}</div>
                  </div>
                </div>
                <span className={`px-2 py-1 rounded text-xs ${BOT_STATUSES[bot.status].bg} ${BOT_STATUSES[bot.status].color}`}>
                  {BOT_STATUSES[bot.status].label}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-white/60 text-xs">P&L</div>
                  <div className={`font-bold ${bot.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(bot.pnl)}
                  </div>
                </div>
                <div>
                  <div className="text-white/60 text-xs">Win Rate</div>
                  <div className="font-bold">{bot.winRate.toFixed(1)}%</div>
                </div>
              </div>

              <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/10">
                {bot.status === 'RUNNING' ? (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleToggleBot(bot.id, 'pause') }}
                    className="flex-1 py-1 bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 rounded text-sm flex items-center justify-center gap-1"
                  >
                    <Pause className="w-3 h-3" />
                    Pause
                  </button>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); handleToggleBot(bot.id, 'start') }}
                    className="flex-1 py-1 bg-green-500/20 text-green-400 hover:bg-green-500/30 rounded text-sm flex items-center justify-center gap-1"
                  >
                    <Play className="w-3 h-3" />
                    Start
                  </button>
                )}
                <button
                  onClick={(e) => { e.stopPropagation(); handleToggleBot(bot.id, 'stop') }}
                  className="flex-1 py-1 bg-white/10 hover:bg-white/20 rounded text-sm flex items-center justify-center gap-1"
                >
                  <Power className="w-3 h-3" />
                  Stop
                </button>
              </div>
            </div>
          ))}

          {filteredBots.length === 0 && (
            <div className="bg-white/5 rounded-xl border border-white/10 p-8 text-center">
              <Bot className="w-12 h-12 mx-auto mb-4 text-white/40" />
              <p className="text-white/60">No bots match your filters</p>
            </div>
          )}
        </div>

        {/* Bot Details */}
        <div className="lg:col-span-2">
          {selectedBot ? (
            <div className="space-y-4">
              {/* Bot Header */}
              <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-4">
                    <div
                      className="w-12 h-12 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: BOT_TYPES[selectedBot.type].color + '20' }}
                    >
                      <Bot className="w-6 h-6" style={{ color: BOT_TYPES[selectedBot.type].color }} />
                    </div>
                    <div>
                      <div className="text-xl font-bold">{selectedBot.name}</div>
                      <div className="text-white/60">{BOT_TYPES[selectedBot.type].description}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button className="p-2 bg-white/10 hover:bg-white/20 rounded-lg">
                      <Settings className="w-5 h-5" />
                    </button>
                    <button
                      onClick={() => handleDeleteBot(selectedBot.id)}
                      className="p-2 bg-red-500/20 text-red-400 hover:bg-red-500/30 rounded-lg"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-white/60 text-xs mb-1">Invested</div>
                    <div className="font-bold">{formatCurrency(selectedBot.invested)}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-white/60 text-xs mb-1">Current Value</div>
                    <div className="font-bold">{formatCurrency(selectedBot.currentValue)}</div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-white/60 text-xs mb-1">P&L</div>
                    <div className={`font-bold ${selectedBot.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatCurrency(selectedBot.pnl)} ({formatPercent(selectedBot.pnlPercent)})
                    </div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-white/60 text-xs mb-1">Runtime</div>
                    <div className="font-bold">{selectedBot.runtime} days</div>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex gap-4 border-b border-white/10">
                {['metrics', 'trades', 'settings'].map(tab => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`pb-3 px-2 font-medium capitalize transition-colors ${
                      activeTab === tab
                        ? 'text-cyan-400 border-b-2 border-cyan-400'
                        : 'text-white/60 hover:text-white'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              {activeTab === 'metrics' && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                    <div className="text-white/60 text-sm mb-1">Total Trades</div>
                    <div className="text-xl font-bold">{selectedBot.totalTrades}</div>
                  </div>
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                    <div className="text-white/60 text-sm mb-1">Win Rate</div>
                    <div className="text-xl font-bold">{selectedBot.winRate.toFixed(1)}%</div>
                  </div>
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                    <div className="text-white/60 text-sm mb-1">Avg Profit/Trade</div>
                    <div className={`text-xl font-bold ${parseFloat(selectedBot.avgProfit) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {selectedBot.avgProfit}%
                    </div>
                  </div>
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                    <div className="text-white/60 text-sm mb-1">Max Drawdown</div>
                    <div className="text-xl font-bold text-orange-400">{selectedBot.maxDrawdown.toFixed(1)}%</div>
                  </div>
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                    <div className="text-white/60 text-sm mb-1">Sharpe Ratio</div>
                    <div className="text-xl font-bold">{selectedBot.sharpeRatio}</div>
                  </div>
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                    <div className="text-white/60 text-sm mb-1">Last Trade</div>
                    <div className="text-lg font-bold">{selectedBot.lastTrade.toLocaleTimeString()}</div>
                  </div>
                  <div className="bg-white/5 rounded-xl border border-white/10 p-4 col-span-2">
                    <div className="text-white/60 text-sm mb-1">Exchange & Pair</div>
                    <div className="text-xl font-bold">{selectedBot.exchange} - {selectedBot.pair}</div>
                  </div>
                </div>
              )}

              {activeTab === 'trades' && (
                <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left p-4 text-white/60 font-medium">Time</th>
                        <th className="text-left p-4 text-white/60 font-medium">Pair</th>
                        <th className="text-left p-4 text-white/60 font-medium">Type</th>
                        <th className="text-right p-4 text-white/60 font-medium">Price</th>
                        <th className="text-right p-4 text-white/60 font-medium">Amount</th>
                        <th className="text-right p-4 text-white/60 font-medium">P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tradeHistory.map((trade, idx) => (
                        <tr key={trade.id} className="border-b border-white/5 hover:bg-white/5">
                          <td className="p-4 text-sm">{trade.timestamp.toLocaleTimeString()}</td>
                          <td className="p-4">{trade.pair}</td>
                          <td className="p-4">
                            <span className={`px-2 py-1 rounded text-xs ${
                              trade.type === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}>
                              {trade.type}
                            </span>
                          </td>
                          <td className="p-4 text-right">${trade.price.toFixed(2)}</td>
                          <td className="p-4 text-right">{trade.amount.toFixed(4)}</td>
                          <td className={`p-4 text-right ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatCurrency(trade.pnl)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'settings' && (
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-white/60 text-sm mb-2">Take Profit (%)</label>
                      <input
                        type="number"
                        defaultValue={selectedBot.settings.takeProfit}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-white/60 text-sm mb-2">Stop Loss (%)</label>
                      <input
                        type="number"
                        defaultValue={selectedBot.settings.stopLoss}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-white/60 text-sm mb-2">Max Position Size ($)</label>
                      <input
                        type="number"
                        defaultValue={selectedBot.settings.maxPositionSize}
                        className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 focus:outline-none"
                      />
                    </div>
                  </div>
                  <button className="mt-4 w-full py-3 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium">
                    Save Settings
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white/5 rounded-xl border border-white/10 p-12 text-center">
              <Bot className="w-16 h-16 mx-auto mb-4 text-white/40" />
              <p className="text-white/60">Select a bot to view details</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Bot Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#0a0e14] border border-white/10 rounded-xl max-w-md w-full">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h2 className="text-xl font-bold">Create New Bot</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-white/60 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-white/60 text-sm mb-2">Bot Type</label>
                <select className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none">
                  {Object.entries(BOT_TYPES).map(([key, type]) => (
                    <option key={key} value={key} className="bg-[#0a0e14]">{type.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-white/60 text-sm mb-2">Trading Pair</label>
                <input
                  type="text"
                  placeholder="BTC/USDT"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-white/60 text-sm mb-2">Investment Amount</label>
                <input
                  type="number"
                  placeholder="1000"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                />
              </div>
            </div>
            <div className="p-4 border-t border-white/10 flex gap-3">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 py-3 bg-white/10 hover:bg-white/20 rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setBots(prev => [...prev, generateBot(prev.length + 1)])
                  setShowCreateModal(false)
                }}
                className="flex-1 py-3 bg-cyan-500 hover:bg-cyan-600 rounded-lg font-medium"
              >
                Create Bot
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default BotPerformance
