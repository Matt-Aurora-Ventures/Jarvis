import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  AlertTriangle, Shield, Zap, TrendingUp, TrendingDown,
  Search, Filter, RefreshCw, ExternalLink, Eye, EyeOff,
  Activity, DollarSign, Clock, Target, Layers, GitBranch,
  ArrowRight, ChevronDown, ChevronUp, Copy, Check, Bell, Settings
} from 'lucide-react'

// MEV Attack Types
const MEV_TYPES = {
  SANDWICH: {
    label: 'Sandwich Attack',
    description: 'Attacker front-runs and back-runs your trade',
    severity: 'HIGH',
    color: '#ef4444',
    icon: Layers
  },
  FRONTRUN: {
    label: 'Frontrunning',
    description: 'Transaction executed before yours at higher gas',
    severity: 'HIGH',
    color: '#f97316',
    icon: Zap
  },
  BACKRUN: {
    label: 'Backrunning',
    description: 'Arbitrage executed immediately after your trade',
    severity: 'MEDIUM',
    color: '#eab308',
    icon: GitBranch
  },
  LIQUIDATION: {
    label: 'Liquidation',
    description: 'MEV bot liquidated an undercollateralized position',
    severity: 'MEDIUM',
    color: '#8b5cf6',
    icon: Target
  },
  ARBITRAGE: {
    label: 'Arbitrage',
    description: 'Cross-DEX price exploitation',
    severity: 'LOW',
    color: '#3b82f6',
    icon: Activity
  },
  JIT_LIQUIDITY: {
    label: 'JIT Liquidity',
    description: 'Just-in-time liquidity provision',
    severity: 'LOW',
    color: '#22c55e',
    icon: TrendingUp
  }
}

// Chains with MEV activity
const CHAINS = [
  { id: 'ethereum', name: 'Ethereum', symbol: 'ETH', color: '#627EEA' },
  { id: 'arbitrum', name: 'Arbitrum', symbol: 'ARB', color: '#28A0F0' },
  { id: 'base', name: 'Base', symbol: 'BASE', color: '#0052FF' },
  { id: 'polygon', name: 'Polygon', symbol: 'MATIC', color: '#8247E5' },
  { id: 'bsc', name: 'BNB Chain', symbol: 'BNB', color: '#F0B90B' },
  { id: 'solana', name: 'Solana', symbol: 'SOL', color: '#14F195' }
]

// Known MEV Bots
const MEV_BOTS = [
  { address: '0x00...dead', label: 'Flashbots Builder', type: 'builder' },
  { address: '0x98...c3a1', label: 'jaredfromsubway.eth', type: 'sandwich' },
  { address: '0xae...7f3b', label: 'MEV Bot #1', type: 'arbitrage' },
  { address: '0x3f...9d2c', label: 'Wintermute MEV', type: 'market_maker' },
  { address: '0xb2...4e8a', label: 'Unknown Bot', type: 'unknown' }
]

// Generate mock MEV events
const generateMEVEvents = () => {
  const types = Object.keys(MEV_TYPES)
  const tokens = ['ETH', 'USDC', 'USDT', 'WBTC', 'ARB', 'OP', 'LINK', 'UNI', 'AAVE', 'PEPE']
  const dexes = ['Uniswap', 'SushiSwap', 'Curve', 'Balancer', 'PancakeSwap', 'GMX', 'Raydium']

  const events = []

  for (let i = 0; i < 50; i++) {
    const type = types[Math.floor(Math.random() * types.length)]
    const chain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
    const token = tokens[Math.floor(Math.random() * tokens.length)]
    const dex = dexes[Math.floor(Math.random() * dexes.length)]
    const bot = MEV_BOTS[Math.floor(Math.random() * MEV_BOTS.length)]
    const profit = Math.random() * 50000 + 100
    const victimLoss = type === 'SANDWICH' || type === 'FRONTRUN' ? profit * (0.5 + Math.random() * 0.5) : 0
    const gasUsed = Math.random() * 500000 + 100000
    const gasPrice = Math.random() * 50 + 10

    events.push({
      id: `mev-${i}`,
      type,
      typeData: MEV_TYPES[type],
      chain,
      token,
      dex,
      bot,
      profit,
      victimLoss,
      gasUsed,
      gasPrice,
      gasCost: (gasUsed * gasPrice) / 1e9 * (chain.id === 'ethereum' ? 3000 : 1),
      timestamp: Date.now() - Math.random() * 86400000,
      txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
      victimTx: type === 'SANDWICH' || type === 'FRONTRUN' ? `0x${Math.random().toString(16).substring(2, 18)}` : null,
      blockNumber: Math.floor(Math.random() * 1000000) + 18000000,
      bundleSize: type === 'SANDWICH' ? 3 : Math.floor(Math.random() * 3) + 1
    })
  }

  return events.sort((a, b) => b.timestamp - a.timestamp)
}

// Generate protection recommendations
const generateProtectionTips = () => [
  {
    id: 1,
    title: 'Use Private Mempools',
    description: 'Send transactions through Flashbots Protect or similar services to avoid public mempool exposure',
    effectiveness: 95,
    difficulty: 'Easy'
  },
  {
    id: 2,
    title: 'Set Tight Slippage',
    description: 'Use 0.1-0.5% slippage tolerance to make sandwich attacks unprofitable',
    effectiveness: 80,
    difficulty: 'Easy'
  },
  {
    id: 3,
    title: 'Split Large Trades',
    description: 'Break large swaps into smaller transactions over time',
    effectiveness: 70,
    difficulty: 'Medium'
  },
  {
    id: 4,
    title: 'Use DEX Aggregators',
    description: 'Route through 1inch, Paraswap, or Cowswap for MEV protection',
    effectiveness: 85,
    difficulty: 'Easy'
  },
  {
    id: 5,
    title: 'Trade During Low Activity',
    description: 'Execute trades during off-peak hours when MEV bots are less active',
    effectiveness: 40,
    difficulty: 'Easy'
  }
]

// Stats aggregation
const calculateStats = (events) => {
  const last24h = events.filter(e => Date.now() - e.timestamp < 86400000)
  const totalProfit = last24h.reduce((sum, e) => sum + e.profit, 0)
  const totalVictimLoss = last24h.reduce((sum, e) => sum + e.victimLoss, 0)
  const sandwichCount = last24h.filter(e => e.type === 'SANDWICH').length
  const avgProfit = totalProfit / last24h.length || 0

  return {
    totalEvents: last24h.length,
    totalProfit,
    totalVictimLoss,
    sandwichCount,
    avgProfit
  }
}

export function MEVDetector() {
  const [events, setEvents] = useState([])
  const [selectedChain, setSelectedChain] = useState('all')
  const [selectedType, setSelectedType] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedEvent, setExpandedEvent] = useState(null)
  const [viewMode, setViewMode] = useState('events') // events, stats, protection
  const [showAlerts, setShowAlerts] = useState(true)
  const [copiedTx, setCopiedTx] = useState(null)
  const [protectionTips] = useState(generateProtectionTips())

  // Initialize and simulate live data
  useEffect(() => {
    setEvents(generateMEVEvents())

    // Simulate live MEV events
    const interval = setInterval(() => {
      setEvents(prev => {
        const types = Object.keys(MEV_TYPES)
        const tokens = ['ETH', 'USDC', 'ARB', 'PEPE', 'WBTC']
        const dexes = ['Uniswap', 'SushiSwap', 'Curve']
        const type = types[Math.floor(Math.random() * types.length)]
        const chain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
        const profit = Math.random() * 20000 + 500

        const newEvent = {
          id: `mev-${Date.now()}`,
          type,
          typeData: MEV_TYPES[type],
          chain,
          token: tokens[Math.floor(Math.random() * tokens.length)],
          dex: dexes[Math.floor(Math.random() * dexes.length)],
          bot: MEV_BOTS[Math.floor(Math.random() * MEV_BOTS.length)],
          profit,
          victimLoss: type === 'SANDWICH' ? profit * 0.7 : 0,
          gasUsed: Math.random() * 300000 + 100000,
          gasPrice: Math.random() * 30 + 10,
          gasCost: Math.random() * 50 + 5,
          timestamp: Date.now(),
          txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
          victimTx: type === 'SANDWICH' ? `0x${Math.random().toString(16).substring(2, 18)}` : null,
          blockNumber: Math.floor(Math.random() * 100) + 19000000,
          bundleSize: type === 'SANDWICH' ? 3 : 1,
          isNew: true
        }

        // Remove isNew flag after animation
        setTimeout(() => {
          setEvents(e => e.map(ev => ev.id === newEvent.id ? { ...ev, isNew: false } : ev))
        }, 3000)

        return [newEvent, ...prev.slice(0, 49)]
      })
    }, 8000)

    return () => clearInterval(interval)
  }, [])

  // Filter events
  const filteredEvents = useMemo(() => {
    return events.filter(e => {
      if (selectedChain !== 'all' && e.chain.id !== selectedChain) return false
      if (selectedType !== 'all' && e.type !== selectedType) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          e.token.toLowerCase().includes(query) ||
          e.dex.toLowerCase().includes(query) ||
          e.txHash.toLowerCase().includes(query)
        )
      }
      return true
    })
  }, [events, selectedChain, selectedType, searchQuery])

  // Stats
  const stats = useMemo(() => calculateStats(events), [events])

  // Type distribution for chart
  const typeDistribution = useMemo(() => {
    const dist = {}
    Object.keys(MEV_TYPES).forEach(type => {
      dist[type] = events.filter(e => e.type === type).length
    })
    return dist
  }, [events])

  const copyTxHash = useCallback((hash) => {
    navigator.clipboard.writeText(hash)
    setCopiedTx(hash)
    setTimeout(() => setCopiedTx(null), 2000)
  }, [])

  const formatNumber = (num) => {
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

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-red-400" />
          <h2 className="text-xl font-bold text-white">MEV Detector</h2>
          <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded-full animate-pulse">
            LIVE
          </span>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode */}
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {['events', 'stats', 'protection'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-xs rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-red-500 text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowAlerts(!showAlerts)}
            className={`p-2 rounded-lg transition-all ${
              showAlerts ? 'bg-red-500/20 text-red-400' : 'bg-white/5 text-white/40'
            }`}
          >
            <Bell className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Activity className="w-4 h-4" />
            <span>24h Events</span>
          </div>
          <div className="text-2xl font-bold text-white">{stats.totalEvents}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <DollarSign className="w-4 h-4" />
            <span>MEV Profit</span>
          </div>
          <div className="text-2xl font-bold text-green-400">{formatNumber(stats.totalProfit)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <AlertTriangle className="w-4 h-4" />
            <span>Victim Loss</span>
          </div>
          <div className="text-2xl font-bold text-red-400">{formatNumber(stats.totalVictimLoss)}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Layers className="w-4 h-4" />
            <span>Sandwiches</span>
          </div>
          <div className="text-2xl font-bold text-yellow-400">{stats.sandwichCount}</div>
        </div>

        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
            <Target className="w-4 h-4" />
            <span>Avg Profit</span>
          </div>
          <div className="text-2xl font-bold text-purple-400">{formatNumber(stats.avgProfit)}</div>
        </div>
      </div>

      {/* Filters */}
      {viewMode === 'events' && (
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              placeholder="Search by token, DEX, or tx hash..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white text-sm placeholder:text-white/40 focus:outline-none focus:border-red-500"
            />
          </div>

          {/* Chain filter */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedChain('all')}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                selectedChain === 'all'
                  ? 'bg-red-500 text-white'
                  : 'bg-white/5 text-white/60 hover:text-white'
              }`}
            >
              All Chains
            </button>
            {CHAINS.slice(0, 4).map(chain => (
              <button
                key={chain.id}
                onClick={() => setSelectedChain(chain.id)}
                className={`px-3 py-1.5 text-xs rounded-lg transition-all flex items-center gap-1.5 ${
                  selectedChain === chain.id
                    ? 'bg-white/20 text-white'
                    : 'bg-white/5 text-white/60 hover:text-white'
                }`}
              >
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: chain.color }} />
                {chain.symbol}
              </button>
            ))}
          </div>

          {/* Type filter */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-white text-sm focus:outline-none"
          >
            <option value="all">All Types</option>
            {Object.entries(MEV_TYPES).map(([key, value]) => (
              <option key={key} value={key}>{value.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Events View */}
      {viewMode === 'events' && (
        <div className="space-y-2">
          {filteredEvents.map(event => (
            <div
              key={event.id}
              className={`bg-white/5 rounded-xl border transition-all ${
                event.isNew
                  ? 'border-red-500 animate-pulse'
                  : expandedEvent === event.id
                    ? 'border-red-500/50'
                    : 'border-white/10'
              }`}
            >
              <div
                className="p-4 cursor-pointer"
                onClick={() => setExpandedEvent(expandedEvent === event.id ? null : event.id)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    {/* Type indicator */}
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ backgroundColor: `${event.typeData.color}20` }}
                    >
                      {React.createElement(event.typeData.icon, {
                        className: 'w-5 h-5',
                        style: { color: event.typeData.color }
                      })}
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{event.typeData.label}</span>
                        <span
                          className="px-2 py-0.5 text-xs rounded"
                          style={{
                            backgroundColor: `${event.typeData.color}20`,
                            color: event.typeData.color
                          }}
                        >
                          {event.typeData.severity}
                        </span>
                        {event.isNew && (
                          <span className="px-2 py-0.5 bg-red-500 text-white text-xs rounded animate-pulse">
                            NEW
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-sm text-white/40">
                        <div className="flex items-center gap-1">
                          <div
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: event.chain.color }}
                          />
                          {event.chain.name}
                        </div>
                        <span>/</span>
                        <span>{event.dex}</span>
                        <span>/</span>
                        <span className="text-white/60">{event.token}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Profit */}
                    <div className="text-right">
                      <div className="text-green-400 font-medium">+{formatNumber(event.profit)}</div>
                      <div className="text-xs text-white/40">MEV Profit</div>
                    </div>

                    {/* Victim loss */}
                    {event.victimLoss > 0 && (
                      <div className="text-right">
                        <div className="text-red-400 font-medium">-{formatNumber(event.victimLoss)}</div>
                        <div className="text-xs text-white/40">Victim Loss</div>
                      </div>
                    )}

                    {/* Gas */}
                    <div className="text-right w-20">
                      <div className="text-white/60">{formatNumber(event.gasCost)}</div>
                      <div className="text-xs text-white/40">Gas Cost</div>
                    </div>

                    {/* Time */}
                    <div className="text-white/40 text-sm w-20 text-right">
                      {formatTime(event.timestamp)}
                    </div>

                    <ChevronDown
                      className={`w-4 h-4 text-white/40 transition-transform ${
                        expandedEvent === event.id ? 'rotate-180' : ''
                      }`}
                    />
                  </div>
                </div>
              </div>

              {/* Expanded details */}
              {expandedEvent === event.id && (
                <div className="px-4 pb-4 border-t border-white/10">
                  <div className="pt-4 grid grid-cols-3 gap-4">
                    {/* Transaction details */}
                    <div className="space-y-3">
                      <h4 className="text-white/60 text-sm font-medium">Transaction</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">TX Hash</span>
                          <div className="flex items-center gap-2">
                            <span className="text-white text-sm font-mono">
                              {event.txHash.slice(0, 10)}...
                            </span>
                            <button
                              onClick={() => copyTxHash(event.txHash)}
                              className="text-white/40 hover:text-white"
                            >
                              {copiedTx === event.txHash ? (
                                <Check className="w-3.5 h-3.5 text-green-400" />
                              ) : (
                                <Copy className="w-3.5 h-3.5" />
                              )}
                            </button>
                            <a href="#" className="text-white/40 hover:text-white">
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Block</span>
                          <span className="text-white text-sm">{event.blockNumber.toLocaleString()}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Bundle Size</span>
                          <span className="text-white text-sm">{event.bundleSize} txs</span>
                        </div>
                      </div>
                    </div>

                    {/* Bot details */}
                    <div className="space-y-3">
                      <h4 className="text-white/60 text-sm font-medium">MEV Bot</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Address</span>
                          <span className="text-white text-sm font-mono">{event.bot.address}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Label</span>
                          <span className="text-white text-sm">{event.bot.label}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Type</span>
                          <span className="text-white text-sm capitalize">{event.bot.type.replace('_', ' ')}</span>
                        </div>
                      </div>
                    </div>

                    {/* Gas details */}
                    <div className="space-y-3">
                      <h4 className="text-white/60 text-sm font-medium">Gas Details</h4>
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Gas Used</span>
                          <span className="text-white text-sm">{event.gasUsed.toLocaleString()}</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Gas Price</span>
                          <span className="text-white text-sm">{event.gasPrice.toFixed(1)} gwei</span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-white/40 text-sm">Net Profit</span>
                          <span className="text-green-400 text-sm font-medium">
                            {formatNumber(event.profit - event.gasCost)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Victim TX */}
                  {event.victimTx && (
                    <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-red-400" />
                          <span className="text-red-400 text-sm font-medium">Victim Transaction</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-white/60 text-sm font-mono">{event.victimTx}</span>
                          <a href="#" className="text-white/40 hover:text-white">
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Stats View */}
      {viewMode === 'stats' && (
        <div className="grid grid-cols-2 gap-4">
          {/* Type distribution */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <h3 className="text-white font-medium mb-4">Attack Type Distribution</h3>
            <div className="space-y-3">
              {Object.entries(MEV_TYPES).map(([key, value]) => {
                const count = typeDistribution[key] || 0
                const percentage = (count / events.length) * 100 || 0

                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded"
                          style={{ backgroundColor: value.color }}
                        />
                        <span className="text-white/80 text-sm">{value.label}</span>
                      </div>
                      <span className="text-white/60 text-sm">{count} ({percentage.toFixed(1)}%)</span>
                    </div>
                    <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${percentage}%`,
                          backgroundColor: value.color
                        }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Chain distribution */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <h3 className="text-white font-medium mb-4">Chain Activity</h3>
            <div className="space-y-3">
              {CHAINS.map(chain => {
                const count = events.filter(e => e.chain.id === chain.id).length
                const percentage = (count / events.length) * 100 || 0
                const profit = events
                  .filter(e => e.chain.id === chain.id)
                  .reduce((sum, e) => sum + e.profit, 0)

                return (
                  <div key={chain.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center"
                        style={{ backgroundColor: `${chain.color}20` }}
                      >
                        <span
                          className="text-xs font-bold"
                          style={{ color: chain.color }}
                        >
                          {chain.symbol}
                        </span>
                      </div>
                      <div>
                        <div className="text-white text-sm">{chain.name}</div>
                        <div className="text-white/40 text-xs">{count} events</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-green-400 text-sm">{formatNumber(profit)}</div>
                      <div className="text-white/40 text-xs">{percentage.toFixed(1)}%</div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Top MEV bots */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10 col-span-2">
            <h3 className="text-white font-medium mb-4">Top MEV Bots (24h)</h3>
            <div className="grid grid-cols-5 gap-4">
              {MEV_BOTS.map(bot => {
                const botEvents = events.filter(e => e.bot.address === bot.address)
                const profit = botEvents.reduce((sum, e) => sum + e.profit, 0)

                return (
                  <div key={bot.address} className="p-4 bg-white/5 rounded-lg">
                    <div className="text-white font-medium text-sm mb-1">{bot.label}</div>
                    <div className="text-white/40 text-xs font-mono mb-2">{bot.address}</div>
                    <div className="text-green-400 font-medium">{formatNumber(profit)}</div>
                    <div className="text-white/40 text-xs">{botEvents.length} txs</div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Protection View */}
      {viewMode === 'protection' && (
        <div className="space-y-4">
          <div className="bg-gradient-to-r from-red-500/10 to-orange-500/10 rounded-xl p-6 border border-red-500/30">
            <div className="flex items-center gap-3 mb-4">
              <Shield className="w-8 h-8 text-red-400" />
              <div>
                <h3 className="text-white font-bold text-lg">MEV Protection Guide</h3>
                <p className="text-white/60 text-sm">Strategies to protect your trades from MEV extraction</p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {protectionTips.map(tip => (
                <div key={tip.id} className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-white font-medium">{tip.title}</h4>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 text-xs rounded ${
                        tip.difficulty === 'Easy'
                          ? 'bg-green-500/20 text-green-400'
                          : tip.difficulty === 'Medium'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-red-500/20 text-red-400'
                      }`}>
                        {tip.difficulty}
                      </span>
                      <div className="flex items-center gap-1">
                        <span className="text-green-400 font-medium">{tip.effectiveness}%</span>
                        <span className="text-white/40 text-xs">effective</span>
                      </div>
                    </div>
                  </div>
                  <p className="text-white/60 text-sm">{tip.description}</p>

                  {/* Effectiveness bar */}
                  <div className="mt-3 h-1.5 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full"
                      style={{ width: `${tip.effectiveness}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick actions */}
          <div className="grid grid-cols-3 gap-4">
            <a
              href="https://protect.flashbots.net"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-purple-500/50 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-purple-400" />
                </div>
                <div>
                  <div className="text-white font-medium group-hover:text-purple-400 transition-colors">
                    Flashbots Protect
                  </div>
                  <div className="text-white/40 text-xs">Private transaction relay</div>
                </div>
              </div>
            </a>

            <a
              href="https://swap.cow.fi"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-green-500/50 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                  <RefreshCw className="w-5 h-5 text-green-400" />
                </div>
                <div>
                  <div className="text-white font-medium group-hover:text-green-400 transition-colors">
                    CoW Swap
                  </div>
                  <div className="text-white/40 text-xs">MEV-protected swaps</div>
                </div>
              </div>
            </a>

            <a
              href="https://1inch.io"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white/5 rounded-xl p-4 border border-white/10 hover:border-blue-500/50 transition-all group"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <div className="text-white font-medium group-hover:text-blue-400 transition-colors">
                    1inch Fusion
                  </div>
                  <div className="text-white/40 text-xs">Gasless MEV-protected</div>
                </div>
              </div>
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

export default MEVDetector
