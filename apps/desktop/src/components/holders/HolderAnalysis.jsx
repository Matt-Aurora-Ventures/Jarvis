import React, { useState, useMemo, useEffect } from 'react'
import {
  Users,
  PieChart,
  TrendingUp,
  TrendingDown,
  Wallet,
  Building2,
  Bot,
  UserCheck,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Search,
  RefreshCw,
  Eye,
  ExternalLink,
  Activity,
  BarChart3,
  Clock,
  Shield,
  Zap
} from 'lucide-react'

export function HolderAnalysis() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('overview') // overview, topHolders, changes, concentration
  const [timeframe, setTimeframe] = useState('24h')
  const [holderType, setHolderType] = useState('all')
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'RAY']

  const holderTypes = [
    { id: 'all', label: 'All Holders', icon: Users },
    { id: 'whale', label: 'Whales', icon: Wallet },
    { id: 'exchange', label: 'Exchanges', icon: Building2 },
    { id: 'smart', label: 'Smart Money', icon: Bot },
    { id: 'retail', label: 'Retail', icon: UserCheck }
  ]

  // Generate mock token data
  const tokenData = useMemo(() => {
    return {
      totalHolders: Math.floor(Math.random() * 500000) + 100000,
      holdersChange24h: (Math.random() - 0.3) * 10,
      avgHolding: Math.floor(Math.random() * 10000) + 100,
      medianHolding: Math.floor(Math.random() * 1000) + 50,
      giniCoefficient: 0.7 + Math.random() * 0.25,
      top10Concentration: 30 + Math.random() * 40,
      top100Concentration: 50 + Math.random() * 35,
      circulatingSupply: Math.floor(Math.random() * 1000000000) + 100000000
    }
  }, [selectedToken])

  // Generate mock top holders
  const topHolders = useMemo(() => {
    const types = ['exchange', 'whale', 'smart', 'contract', 'unknown']
    const exchanges = ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit']

    return Array.from({ length: 50 }, (_, i) => {
      const type = types[Math.floor(Math.random() * types.length)]
      const balance = Math.floor((50 - i) * Math.random() * 10000000 + 1000000)
      const percentage = (balance / tokenData.circulatingSupply) * 100

      return {
        rank: i + 1,
        address: `${['0x', ''][Math.floor(Math.random() * 2)]}${Math.random().toString(36).substring(2, 8)}...${Math.random().toString(36).substring(2, 6)}`,
        label: type === 'exchange' ? exchanges[Math.floor(Math.random() * exchanges.length)] :
               type === 'smart' ? 'Smart Money' :
               type === 'contract' ? 'Contract' : null,
        type,
        balance,
        percentage,
        value: balance * (Math.random() * 100 + 10),
        change24h: (Math.random() - 0.5) * 20,
        lastActive: Math.floor(Math.random() * 72) + 1,
        txCount30d: Math.floor(Math.random() * 100) + 1,
        isWatched: Math.random() > 0.8
      }
    })
  }, [selectedToken, tokenData.circulatingSupply])

  // Generate holder distribution
  const distribution = useMemo(() => {
    return [
      { range: '0-100', count: Math.floor(Math.random() * 200000) + 50000, percentage: 40 + Math.random() * 10 },
      { range: '100-1K', count: Math.floor(Math.random() * 100000) + 30000, percentage: 25 + Math.random() * 5 },
      { range: '1K-10K', count: Math.floor(Math.random() * 50000) + 10000, percentage: 15 + Math.random() * 5 },
      { range: '10K-100K', count: Math.floor(Math.random() * 10000) + 2000, percentage: 8 + Math.random() * 3 },
      { range: '100K-1M', count: Math.floor(Math.random() * 2000) + 500, percentage: 4 + Math.random() * 2 },
      { range: '1M+', count: Math.floor(Math.random() * 500) + 100, percentage: 2 + Math.random() * 1 }
    ]
  }, [selectedToken])

  // Generate holder changes
  const holderChanges = useMemo(() => {
    return Array.from({ length: 20 }, (_, i) => {
      const isInflow = Math.random() > 0.4
      const amount = Math.floor(Math.random() * 5000000) + 100000
      const types = ['whale', 'exchange', 'smart', 'retail']

      return {
        id: i,
        address: `${Math.random().toString(36).substring(2, 8)}...${Math.random().toString(36).substring(2, 6)}`,
        type: types[Math.floor(Math.random() * types.length)],
        action: isInflow ? 'accumulate' : 'distribute',
        amount,
        value: amount * (Math.random() * 100 + 10),
        previousBalance: Math.floor(Math.random() * 10000000),
        newBalance: Math.floor(Math.random() * 10000000),
        time: `${Math.floor(Math.random() * 24)}h ago`,
        txHash: `0x${Math.random().toString(36).substring(2, 10)}`
      }
    })
  }, [selectedToken, timeframe])

  // Concentration metrics
  const concentrationMetrics = useMemo(() => {
    return {
      herfindahl: (Math.random() * 0.3 + 0.1).toFixed(4),
      nakamotoCoeff: Math.floor(Math.random() * 20) + 5,
      whaleRatio: (Math.random() * 30 + 20).toFixed(2),
      exchangeRatio: (Math.random() * 25 + 15).toFixed(2),
      retailRatio: (Math.random() * 40 + 30).toFixed(2),
      smartMoneyRatio: (Math.random() * 15 + 5).toFixed(2)
    }
  }, [selectedToken])

  useEffect(() => {
    const interval = setInterval(() => {
      // Auto refresh simulation
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const getTypeIcon = (type) => {
    switch(type) {
      case 'whale': return <Wallet className="w-4 h-4 text-purple-400" />
      case 'exchange': return <Building2 className="w-4 h-4 text-blue-400" />
      case 'smart': return <Bot className="w-4 h-4 text-green-400" />
      case 'contract': return <Shield className="w-4 h-4 text-yellow-400" />
      default: return <UserCheck className="w-4 h-4 text-gray-400" />
    }
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(2)
  }

  const formatAddress = (addr) => addr

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Users className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold text-white">Holder Analysis</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedToken}
            onChange={(e) => setSelectedToken(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {tokens.map(token => (
              <option key={token} value={token}>{token}</option>
            ))}
          </select>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition-colors ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>

      {/* View Mode Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'topHolders', label: 'Top Holders' },
          { id: 'changes', label: 'Changes' },
          { id: 'concentration', label: 'Concentration' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
              viewMode === mode.id
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Overview Mode */}
      {viewMode === 'overview' && (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Total Holders</div>
              <div className="text-2xl font-bold text-white">{formatNumber(tokenData.totalHolders)}</div>
              <div className={`text-sm flex items-center gap-1 ${tokenData.holdersChange24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {tokenData.holdersChange24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {Math.abs(tokenData.holdersChange24h).toFixed(2)}% (24h)
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Avg Holding</div>
              <div className="text-2xl font-bold text-white">{formatNumber(tokenData.avgHolding)}</div>
              <div className="text-sm text-gray-500">{selectedToken}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Top 10 Concentration</div>
              <div className="text-2xl font-bold text-white">{tokenData.top10Concentration.toFixed(1)}%</div>
              <div className="text-sm text-yellow-400">High concentration</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Gini Coefficient</div>
              <div className="text-2xl font-bold text-white">{tokenData.giniCoefficient.toFixed(3)}</div>
              <div className="text-sm text-gray-500">Wealth inequality</div>
            </div>
          </div>

          {/* Distribution Chart */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Holder Distribution</h3>
            <div className="space-y-3">
              {distribution.map((tier, i) => (
                <div key={i} className="flex items-center gap-4">
                  <div className="w-24 text-sm text-gray-400">{tier.range}</div>
                  <div className="flex-1 h-6 bg-white/5 rounded overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-blue-500 rounded"
                      style={{ width: `${tier.percentage}%` }}
                    />
                  </div>
                  <div className="w-20 text-right text-sm text-white">{formatNumber(tier.count)}</div>
                  <div className="w-16 text-right text-sm text-gray-400">{tier.percentage.toFixed(1)}%</div>
                </div>
              ))}
            </div>
          </div>

          {/* Holder Types Breakdown */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <Wallet className="w-4 h-4 text-purple-400" />
                <span className="text-gray-400 text-sm">Whales</span>
              </div>
              <div className="text-xl font-bold text-white">{concentrationMetrics.whaleRatio}%</div>
              <div className="text-xs text-gray-500">of supply</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <Building2 className="w-4 h-4 text-blue-400" />
                <span className="text-gray-400 text-sm">Exchanges</span>
              </div>
              <div className="text-xl font-bold text-white">{concentrationMetrics.exchangeRatio}%</div>
              <div className="text-xs text-gray-500">of supply</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <Bot className="w-4 h-4 text-green-400" />
                <span className="text-gray-400 text-sm">Smart Money</span>
              </div>
              <div className="text-xl font-bold text-white">{concentrationMetrics.smartMoneyRatio}%</div>
              <div className="text-xs text-gray-500">of supply</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <UserCheck className="w-4 h-4 text-yellow-400" />
                <span className="text-gray-400 text-sm">Retail</span>
              </div>
              <div className="text-xl font-bold text-white">{concentrationMetrics.retailRatio}%</div>
              <div className="text-xs text-gray-500">of supply</div>
            </div>
          </div>
        </div>
      )}

      {/* Top Holders Mode */}
      {viewMode === 'topHolders' && (
        <div className="space-y-4">
          {/* Holder Type Filter */}
          <div className="flex gap-2 overflow-x-auto pb-2">
            {holderTypes.map(type => (
              <button
                key={type.id}
                onClick={() => setHolderType(type.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-colors ${
                  holderType === type.id
                    ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
                }`}
              >
                <type.icon className="w-4 h-4" />
                {type.label}
              </button>
            ))}
          </div>

          {/* Holders Table */}
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-gray-400 text-sm border-b border-white/10">
                  <th className="pb-3 pr-4">#</th>
                  <th className="pb-3 pr-4">Address</th>
                  <th className="pb-3 pr-4">Type</th>
                  <th className="pb-3 pr-4 text-right">Balance</th>
                  <th className="pb-3 pr-4 text-right">% Supply</th>
                  <th className="pb-3 pr-4 text-right">24h Change</th>
                  <th className="pb-3 text-right">Last Active</th>
                </tr>
              </thead>
              <tbody>
                {topHolders
                  .filter(h => holderType === 'all' || h.type === holderType)
                  .slice(0, 25)
                  .map(holder => (
                    <tr key={holder.rank} className="border-b border-white/5 hover:bg-white/5">
                      <td className="py-3 pr-4 text-gray-400">{holder.rank}</td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-mono text-sm">{holder.address}</span>
                          {holder.label && (
                            <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">
                              {holder.label}
                            </span>
                          )}
                          {holder.isWatched && <Eye className="w-3 h-3 text-yellow-400" />}
                        </div>
                      </td>
                      <td className="py-3 pr-4">
                        <div className="flex items-center gap-1">
                          {getTypeIcon(holder.type)}
                          <span className="text-gray-400 text-sm capitalize">{holder.type}</span>
                        </div>
                      </td>
                      <td className="py-3 pr-4 text-right">
                        <div className="text-white">{formatNumber(holder.balance)}</div>
                        <div className="text-xs text-gray-500">${formatNumber(holder.value)}</div>
                      </td>
                      <td className="py-3 pr-4 text-right text-white">{holder.percentage.toFixed(2)}%</td>
                      <td className={`py-3 pr-4 text-right ${holder.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {holder.change24h >= 0 ? '+' : ''}{holder.change24h.toFixed(2)}%
                      </td>
                      <td className="py-3 text-right text-gray-400">{holder.lastActive}h ago</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Changes Mode */}
      {viewMode === 'changes' && (
        <div className="space-y-4">
          {/* Timeframe Selector */}
          <div className="flex gap-2">
            {['1h', '4h', '24h', '7d', '30d'].map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                  timeframe === tf
                    ? 'bg-purple-500/20 text-purple-400'
                    : 'bg-white/5 text-gray-400 hover:bg-white/10'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <div className="text-green-400 text-sm mb-1">Accumulating</div>
              <div className="text-2xl font-bold text-white">
                {holderChanges.filter(c => c.action === 'accumulate').length}
              </div>
              <div className="text-xs text-gray-400">addresses</div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <div className="text-red-400 text-sm mb-1">Distributing</div>
              <div className="text-2xl font-bold text-white">
                {holderChanges.filter(c => c.action === 'distribute').length}
              </div>
              <div className="text-xs text-gray-400">addresses</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Net Inflow</div>
              <div className="text-2xl font-bold text-green-400">
                +{formatNumber(holderChanges.filter(c => c.action === 'accumulate').reduce((sum, c) => sum + c.amount, 0))}
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="text-gray-400 text-sm mb-1">Net Outflow</div>
              <div className="text-2xl font-bold text-red-400">
                -{formatNumber(holderChanges.filter(c => c.action === 'distribute').reduce((sum, c) => sum + c.amount, 0))}
              </div>
            </div>
          </div>

          {/* Changes Feed */}
          <div className="space-y-2">
            {holderChanges.map(change => (
              <div key={change.id} className="bg-white/5 rounded-lg p-4 border border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className={`p-2 rounded-lg ${change.action === 'accumulate' ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                    {change.action === 'accumulate' ? (
                      <TrendingUp className="w-5 h-5 text-green-400" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-mono text-sm">{change.address}</span>
                      {getTypeIcon(change.type)}
                    </div>
                    <div className="text-sm text-gray-400 mt-1">
                      {change.action === 'accumulate' ? 'Bought' : 'Sold'} {formatNumber(change.amount)} {selectedToken}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`font-medium ${change.action === 'accumulate' ? 'text-green-400' : 'text-red-400'}`}>
                    ${formatNumber(change.value)}
                  </div>
                  <div className="text-sm text-gray-500 flex items-center gap-1 justify-end">
                    <Clock className="w-3 h-3" />
                    {change.time}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Concentration Mode */}
      {viewMode === 'concentration' && (
        <div className="space-y-6">
          {/* Concentration Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <PieChart className="w-4 h-4 text-purple-400" />
                <span className="text-gray-400 text-sm">Herfindahl Index</span>
              </div>
              <div className="text-2xl font-bold text-white">{concentrationMetrics.herfindahl}</div>
              <div className="text-xs text-gray-500 mt-1">Market concentration measure</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-blue-400" />
                <span className="text-gray-400 text-sm">Nakamoto Coefficient</span>
              </div>
              <div className="text-2xl font-bold text-white">{concentrationMetrics.nakamotoCoeff}</div>
              <div className="text-xs text-gray-500 mt-1">Min entities for 51%</div>
            </div>
            <div className="bg-white/5 rounded-lg p-4 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-yellow-400" />
                <span className="text-gray-400 text-sm">Gini Coefficient</span>
              </div>
              <div className="text-2xl font-bold text-white">{tokenData.giniCoefficient.toFixed(3)}</div>
              <div className="text-xs text-gray-500 mt-1">Wealth inequality (0-1)</div>
            </div>
          </div>

          {/* Concentration Bars */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Supply Concentration</h3>
            <div className="space-y-4">
              {[
                { label: 'Top 1 Holder', value: tokenData.top10Concentration / 10 },
                { label: 'Top 10 Holders', value: tokenData.top10Concentration },
                { label: 'Top 50 Holders', value: tokenData.top10Concentration + 15 },
                { label: 'Top 100 Holders', value: tokenData.top100Concentration }
              ].map((item, i) => (
                <div key={i}>
                  <div className="flex justify-between mb-1">
                    <span className="text-gray-400 text-sm">{item.label}</span>
                    <span className="text-white font-medium">{item.value.toFixed(1)}%</span>
                  </div>
                  <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${
                        item.value > 70 ? 'bg-red-500' :
                        item.value > 50 ? 'bg-yellow-500' :
                        'bg-green-500'
                      }`}
                      style={{ width: `${item.value}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Risk Assessment */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Concentration Risk Assessment</h3>
            <div className="space-y-3">
              {[
                {
                  risk: 'Whale Manipulation Risk',
                  level: tokenData.top10Concentration > 50 ? 'High' : tokenData.top10Concentration > 30 ? 'Medium' : 'Low',
                  description: 'Large holders could impact price significantly'
                },
                {
                  risk: 'Exchange Concentration',
                  level: parseFloat(concentrationMetrics.exchangeRatio) > 30 ? 'High' : 'Medium',
                  description: 'High exchange holdings may indicate selling pressure'
                },
                {
                  risk: 'Decentralization Score',
                  level: concentrationMetrics.nakamotoCoeff > 15 ? 'Good' : concentrationMetrics.nakamotoCoeff > 8 ? 'Medium' : 'Poor',
                  description: 'Based on Nakamoto coefficient'
                }
              ].map((item, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                  <div>
                    <div className="text-white font-medium">{item.risk}</div>
                    <div className="text-xs text-gray-500">{item.description}</div>
                  </div>
                  <span className={`px-3 py-1 rounded text-sm font-medium ${
                    item.level === 'High' || item.level === 'Poor' ? 'bg-red-500/20 text-red-400' :
                    item.level === 'Medium' ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-green-500/20 text-green-400'
                  }`}>
                    {item.level}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default HolderAnalysis
