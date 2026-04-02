import React, { useState, useMemo, useEffect } from 'react'
import {
  AlertCircle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Clock,
  ExternalLink,
  Bell,
  BellOff,
  Filter,
  Search,
  RefreshCw,
  Wallet,
  Building2,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  ChevronDown,
  ChevronUp,
  Eye,
  Star,
  Volume2,
  VolumeX
} from 'lucide-react'

export function WhaleAlert() {
  const [viewMode, setViewMode] = useState('feed') // feed, watchlist, analytics
  const [filterToken, setFilterToken] = useState('all')
  const [filterType, setFilterType] = useState('all')
  const [minValue, setMinValue] = useState(100000)
  const [soundEnabled, setSoundEnabled] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['all', 'SOL', 'ETH', 'BTC', 'USDC', 'USDT', 'BONK', 'WIF', 'JUP', 'RNDR']

  const transactionTypes = [
    { id: 'all', label: 'All Types' },
    { id: 'transfer', label: 'Transfers' },
    { id: 'exchange_deposit', label: 'Exchange Deposit' },
    { id: 'exchange_withdraw', label: 'Exchange Withdraw' },
    { id: 'stake', label: 'Stake' },
    { id: 'unstake', label: 'Unstake' },
    { id: 'swap', label: 'Swap' }
  ]

  // Generate mock whale transactions
  const whaleTransactions = useMemo(() => {
    const types = ['transfer', 'exchange_deposit', 'exchange_withdraw', 'stake', 'unstake', 'swap']
    const exchanges = ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit', 'Unknown']

    return Array.from({ length: 50 }, (_, i) => {
      const token = tokens[Math.floor(Math.random() * (tokens.length - 1)) + 1]
      const type = types[Math.floor(Math.random() * types.length)]
      const value = Math.floor(Math.random() * 10000000) + 100000
      const amount = value / (Math.random() * 100 + 50)

      return {
        id: i + 1,
        txHash: `0x${Math.random().toString(36).substring(2, 10)}...${Math.random().toString(36).substring(2, 6)}`,
        type,
        token,
        amount,
        value,
        from: type === 'exchange_withdraw' ? exchanges[Math.floor(Math.random() * exchanges.length)] :
              `${Math.random().toString(36).substring(2, 8)}...${Math.random().toString(36).substring(2, 6)}`,
        to: type === 'exchange_deposit' ? exchanges[Math.floor(Math.random() * exchanges.length)] :
            `${Math.random().toString(36).substring(2, 8)}...${Math.random().toString(36).substring(2, 6)}`,
        isFromExchange: type === 'exchange_withdraw' || Math.random() > 0.7,
        isToExchange: type === 'exchange_deposit' || Math.random() > 0.7,
        timestamp: new Date(Date.now() - i * 60000 * Math.random() * 30),
        priceImpact: Math.random() * 2,
        isWatched: Math.random() > 0.8,
        label: Math.random() > 0.6 ? ['Smart Money', 'Known Whale', 'Market Maker', 'Institution'][Math.floor(Math.random() * 4)] : null
      }
    }).sort((a, b) => b.timestamp - a.timestamp)
  }, [])

  // Filter transactions
  const filteredTransactions = useMemo(() => {
    return whaleTransactions.filter(tx => {
      if (filterToken !== 'all' && tx.token !== filterToken) return false
      if (filterType !== 'all' && tx.type !== filterType) return false
      if (tx.value < minValue) return false
      return true
    })
  }, [whaleTransactions, filterToken, filterType, minValue])

  // Watchlist
  const watchedAddresses = useMemo(() => {
    return Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      address: `${Math.random().toString(36).substring(2, 8)}...${Math.random().toString(36).substring(2, 6)}`,
      label: ['Smart Money', 'Known Whale', 'Market Maker', 'Institution', 'Exchange'][Math.floor(Math.random() * 5)],
      lastActivity: `${Math.floor(Math.random() * 24) + 1}h ago`,
      totalValue: Math.floor(Math.random() * 100000000) + 1000000,
      recentTxs: Math.floor(Math.random() * 20) + 1,
      avgTxValue: Math.floor(Math.random() * 1000000) + 100000
    }))
  }, [])

  // Analytics
  const analytics = useMemo(() => {
    const totalVolume = whaleTransactions.reduce((sum, tx) => sum + tx.value, 0)
    const depositVolume = whaleTransactions.filter(tx => tx.type === 'exchange_deposit').reduce((sum, tx) => sum + tx.value, 0)
    const withdrawVolume = whaleTransactions.filter(tx => tx.type === 'exchange_withdraw').reduce((sum, tx) => sum + tx.value, 0)

    const byToken = {}
    whaleTransactions.forEach(tx => {
      if (!byToken[tx.token]) byToken[tx.token] = { count: 0, volume: 0 }
      byToken[tx.token].count++
      byToken[tx.token].volume += tx.value
    })

    return {
      totalVolume,
      totalTxs: whaleTransactions.length,
      depositVolume,
      withdrawVolume,
      netFlow: withdrawVolume - depositVolume,
      avgTxValue: totalVolume / whaleTransactions.length,
      byToken: Object.entries(byToken)
        .map(([token, data]) => ({ token, ...data }))
        .sort((a, b) => b.volume - a.volume)
    }
  }, [whaleTransactions])

  useEffect(() => {
    const interval = setInterval(() => {
      // Simulate new transactions
    }, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(2)
  }

  const formatTime = (date) => {
    const diff = Date.now() - date.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 60) return `${mins}m ago`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.floor(hours / 24)}d ago`
  }

  const getTypeIcon = (type) => {
    switch(type) {
      case 'exchange_deposit':
        return <ArrowDownRight className="w-4 h-4 text-red-400" />
      case 'exchange_withdraw':
        return <ArrowUpRight className="w-4 h-4 text-green-400" />
      case 'stake':
        return <TrendingUp className="w-4 h-4 text-blue-400" />
      case 'unstake':
        return <TrendingDown className="w-4 h-4 text-orange-400" />
      case 'swap':
        return <Activity className="w-4 h-4 text-purple-400" />
      default:
        return <ArrowRight className="w-4 h-4 text-gray-400" />
    }
  }

  const getTypeColor = (type) => {
    switch(type) {
      case 'exchange_deposit': return 'bg-red-500/20 text-red-400'
      case 'exchange_withdraw': return 'bg-green-500/20 text-green-400'
      case 'stake': return 'bg-blue-500/20 text-blue-400'
      case 'unstake': return 'bg-orange-500/20 text-orange-400'
      case 'swap': return 'bg-purple-500/20 text-purple-400'
      default: return 'bg-gray-500/20 text-gray-400'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <AlertCircle className="w-6 h-6 text-yellow-400" />
          <h2 className="text-xl font-bold text-white">Whale Alert</h2>
          <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded animate-pulse">
            LIVE
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSoundEnabled(!soundEnabled)}
            className={`p-2 rounded-lg transition-colors ${soundEnabled ? 'bg-yellow-500/20 text-yellow-400' : 'bg-white/5 text-gray-400'}`}
          >
            {soundEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
          </button>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'feed', label: 'Live Feed' },
          { id: 'watchlist', label: 'Watchlist' },
          { id: 'analytics', label: 'Analytics' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              viewMode === mode.id
                ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Feed Mode */}
      {viewMode === 'feed' && (
        <div className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-3">
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
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
            >
              {transactionTypes.map(t => (
                <option key={t.id} value={t.id}>{t.label}</option>
              ))}
            </select>
            <div className="flex items-center gap-2">
              <span className="text-gray-400 text-sm">Min:</span>
              <select
                value={minValue}
                onChange={(e) => setMinValue(Number(e.target.value))}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
              >
                <option value={100000}>$100K</option>
                <option value={500000}>$500K</option>
                <option value={1000000}>$1M</option>
                <option value={5000000}>$5M</option>
                <option value={10000000}>$10M</option>
              </select>
            </div>
          </div>

          {/* Transactions Feed */}
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {filteredTransactions.map(tx => (
              <div
                key={tx.id}
                className={`p-4 rounded-lg border transition-colors ${
                  tx.value >= 5000000
                    ? 'bg-yellow-500/10 border-yellow-500/30'
                    : 'bg-white/5 border-white/10'
                } hover:bg-white/10`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-2 rounded-lg ${getTypeColor(tx.type)}`}>
                      {getTypeIcon(tx.type)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{formatNumber(tx.amount)} {tx.token}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${getTypeColor(tx.type)}`}>
                          {tx.type.replace('_', ' ').toUpperCase()}
                        </span>
                        {tx.label && (
                          <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">
                            {tx.label}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-400 mt-1">
                        <span className={tx.isFromExchange ? 'text-yellow-400' : ''}>
                          {tx.from}
                        </span>
                        <ArrowRight className="w-3 h-3" />
                        <span className={tx.isToExchange ? 'text-yellow-400' : ''}>
                          {tx.to}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-white font-medium">${formatNumber(tx.value)}</div>
                    <div className="text-xs text-gray-500 flex items-center gap-1 justify-end">
                      <Clock className="w-3 h-3" />
                      {formatTime(tx.timestamp)}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Watchlist Mode */}
      {viewMode === 'watchlist' && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-sm">{watchedAddresses.length} addresses watched</span>
            <button className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm hover:bg-yellow-500/30">
              Add Address
            </button>
          </div>

          <div className="space-y-2">
            {watchedAddresses.map(address => (
              <div key={address.id} className="p-4 bg-white/5 rounded-lg border border-white/10 hover:bg-white/10">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-yellow-500/20 rounded-lg">
                      <Wallet className="w-5 h-5 text-yellow-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-mono">{address.address}</span>
                        <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">
                          {address.label}
                        </span>
                      </div>
                      <div className="text-sm text-gray-500 mt-1">
                        Last active: {address.lastActivity}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-white font-medium">${formatNumber(address.totalValue)}</div>
                    <div className="text-xs text-gray-500">{address.recentTxs} recent txs</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analytics Mode */}
      {viewMode === 'analytics' && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Total Volume (24h)</div>
              <div className="text-2xl font-bold text-white">${formatNumber(analytics.totalVolume)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Transactions</div>
              <div className="text-2xl font-bold text-white">{analytics.totalTxs}</div>
            </div>
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <div className="text-gray-400 text-sm mb-1">Exchange Withdrawals</div>
              <div className="text-2xl font-bold text-green-400">${formatNumber(analytics.withdrawVolume)}</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <div className="text-gray-400 text-sm mb-1">Exchange Deposits</div>
              <div className="text-2xl font-bold text-red-400">${formatNumber(analytics.depositVolume)}</div>
            </div>
          </div>

          {/* Net Flow */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Net Flow (Exchange)</h3>
            <div className={`text-3xl font-bold ${analytics.netFlow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {analytics.netFlow >= 0 ? '+' : ''}{formatNumber(analytics.netFlow)}
            </div>
            <div className="text-sm text-gray-500 mt-1">
              {analytics.netFlow >= 0 ? 'Net outflow from exchanges (bullish)' : 'Net inflow to exchanges (bearish)'}
            </div>
          </div>

          {/* Volume by Token */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Volume by Token</h3>
            <div className="space-y-3">
              {analytics.byToken.slice(0, 8).map((item, i) => (
                <div key={item.token}>
                  <div className="flex justify-between mb-1">
                    <span className="text-white">{item.token}</span>
                    <span className="text-gray-400">${formatNumber(item.volume)}</span>
                  </div>
                  <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-yellow-500 to-orange-400 rounded-full"
                      style={{ width: `${(item.volume / analytics.byToken[0].volume) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default WhaleAlert
