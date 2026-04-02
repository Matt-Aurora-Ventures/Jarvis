import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Wallet, Search, DollarSign, TrendingUp, TrendingDown, Activity,
  Clock, ExternalLink, Copy, Check, RefreshCw, PieChart,
  BarChart3, ArrowUpRight, ArrowDownRight, ArrowRight, Filter,
  Shield, Zap, Target, Star, Calendar, Layers, AlertTriangle
} from 'lucide-react'

// Chains
const CHAINS = [
  { id: 'ethereum', name: 'Ethereum', symbol: 'ETH', color: '#627EEA', explorer: 'etherscan.io' },
  { id: 'arbitrum', name: 'Arbitrum', symbol: 'ARB', color: '#28A0F0', explorer: 'arbiscan.io' },
  { id: 'optimism', name: 'Optimism', symbol: 'OP', color: '#FF0420', explorer: 'optimistic.etherscan.io' },
  { id: 'polygon', name: 'Polygon', symbol: 'MATIC', color: '#8247E5', explorer: 'polygonscan.com' },
  { id: 'base', name: 'Base', symbol: 'BASE', color: '#0052FF', explorer: 'basescan.org' },
  { id: 'solana', name: 'Solana', symbol: 'SOL', color: '#14F195', explorer: 'solscan.io' }
]

// Generate wallet profile
const generateWalletProfile = (address) => {
  const chain = CHAINS[Math.floor(Math.random() * CHAINS.length)]
  const isWhale = Math.random() > 0.7
  const totalValue = isWhale ? Math.random() * 50000000 + 1000000 : Math.random() * 500000 + 1000

  // Generate holdings
  const tokens = [
    { symbol: 'ETH', name: 'Ethereum', price: 3200 + Math.random() * 100 },
    { symbol: 'USDC', name: 'USD Coin', price: 1 },
    { symbol: 'USDT', name: 'Tether', price: 1 },
    { symbol: 'WBTC', name: 'Wrapped BTC', price: 95000 + Math.random() * 1000 },
    { symbol: 'ARB', name: 'Arbitrum', price: 1.2 + Math.random() * 0.3 },
    { symbol: 'OP', name: 'Optimism', price: 2.5 + Math.random() * 0.5 },
    { symbol: 'LINK', name: 'Chainlink', price: 15 + Math.random() * 3 },
    { symbol: 'UNI', name: 'Uniswap', price: 8 + Math.random() * 2 },
    { symbol: 'AAVE', name: 'Aave', price: 180 + Math.random() * 30 },
    { symbol: 'PEPE', name: 'Pepe', price: 0.00001 + Math.random() * 0.00001 }
  ]

  const holdings = tokens.slice(0, 5 + Math.floor(Math.random() * 5)).map(token => {
    const value = totalValue * (Math.random() * 0.4 + 0.05)
    const amount = value / token.price
    return {
      ...token,
      amount,
      value,
      allocation: 0, // Calculate after
      change24h: (Math.random() - 0.4) * 20,
      avgBuyPrice: token.price * (0.8 + Math.random() * 0.4),
      pnl: 0 // Calculate after
    }
  })

  // Calculate allocations and PnL
  const holdingsTotal = holdings.reduce((sum, h) => sum + h.value, 0)
  holdings.forEach(h => {
    h.allocation = (h.value / holdingsTotal) * 100
    h.pnl = ((h.price - h.avgBuyPrice) / h.avgBuyPrice) * 100
  })
  holdings.sort((a, b) => b.value - a.value)

  // Generate transactions
  const transactions = []
  const txTypes = ['swap', 'transfer_in', 'transfer_out', 'stake', 'unstake', 'bridge']
  for (let i = 0; i < 20; i++) {
    const type = txTypes[Math.floor(Math.random() * txTypes.length)]
    const token = tokens[Math.floor(Math.random() * tokens.length)]
    transactions.push({
      id: `tx-${i}`,
      type,
      token: token.symbol,
      amount: Math.random() * 10000 + 100,
      value: Math.random() * 50000 + 100,
      timestamp: Date.now() - Math.random() * 86400000 * 30,
      txHash: `0x${Math.random().toString(16).substring(2, 18)}`,
      status: Math.random() > 0.05 ? 'success' : 'failed',
      gasCost: Math.random() * 30 + 2
    })
  }
  transactions.sort((a, b) => b.timestamp - a.timestamp)

  // Generate DeFi positions
  const protocols = ['Aave', 'Compound', 'Uniswap', 'Lido', 'Curve', 'GMX']
  const defiPositions = protocols.slice(0, 3 + Math.floor(Math.random() * 3)).map(protocol => ({
    protocol,
    type: ['lending', 'liquidity', 'staking'][Math.floor(Math.random() * 3)],
    value: totalValue * (0.05 + Math.random() * 0.2),
    apy: Math.random() * 20 + 2,
    healthFactor: Math.random() > 0.7 ? 1.5 + Math.random() : null
  }))

  // Stats
  const totalPnl = holdings.reduce((sum, h) => sum + (h.value * h.pnl / 100), 0)
  const winRate = Math.random() * 30 + 50
  const avgTradeSize = transactions.reduce((sum, t) => sum + t.value, 0) / transactions.length
  const firstTx = Math.min(...transactions.map(t => t.timestamp))
  const accountAge = Math.floor((Date.now() - firstTx) / 86400000)

  return {
    address,
    chain,
    label: isWhale ? 'Whale Wallet' : Math.random() > 0.7 ? 'Smart Money' : null,
    totalValue: holdingsTotal,
    totalPnl,
    pnlPercent: (totalPnl / (holdingsTotal - totalPnl)) * 100,
    holdings,
    transactions,
    defiPositions,
    stats: {
      winRate,
      avgTradeSize,
      totalTrades: transactions.length,
      accountAge,
      lastActive: Math.max(...transactions.map(t => t.timestamp)),
      nftCount: Math.floor(Math.random() * 50),
      uniqueTokens: holdings.length,
      riskScore: Math.floor(Math.random() * 100)
    },
    tags: generateTags(isWhale)
  }
}

const generateTags = (isWhale) => {
  const allTags = ['DeFi Power User', 'NFT Collector', 'Yield Farmer', 'Active Trader', 'HODLer', 'Airdrop Hunter', 'Smart Money']
  if (isWhale) allTags.push('Whale')
  return allTags.sort(() => Math.random() - 0.5).slice(0, 2 + Math.floor(Math.random() * 3))
}

// Sample addresses
const SAMPLE_ADDRESSES = [
  { address: '0x742d35Cc6634C0532925a3b844Bc9e7595f0AB4c', label: 'Sample Whale 1' },
  { address: '0x8ba1f109551bD432803012645Ac136ddd64DBA72', label: 'Sample Smart Money' },
  { address: 'HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH', label: 'Solana Whale' }
]

export function WalletProfiler() {
  const [searchAddress, setSearchAddress] = useState('')
  const [profile, setProfile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [viewMode, setViewMode] = useState('overview') // overview, holdings, activity, defi
  const [copiedAddress, setCopiedAddress] = useState(false)

  // Search wallet
  const searchWallet = useCallback((address) => {
    if (!address) return
    setIsLoading(true)
    // Simulate API call
    setTimeout(() => {
      setProfile(generateWalletProfile(address))
      setIsLoading(false)
    }, 1000)
  }, [])

  const handleSearch = (e) => {
    e.preventDefault()
    searchWallet(searchAddress)
  }

  const copyAddress = () => {
    if (profile) {
      navigator.clipboard.writeText(profile.address)
      setCopiedAddress(true)
      setTimeout(() => setCopiedAddress(false), 2000)
    }
  }

  const formatNumber = (num) => {
    if (num >= 1000000000) return `$${(num / 1000000000).toFixed(2)}B`
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `$${(num / 1000).toFixed(1)}K`
    return `$${num.toFixed(2)}`
  }

  const formatTime = (timestamp) => {
    const diff = Date.now() - timestamp
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  const formatDate = (timestamp) => {
    return new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const getTxTypeStyle = (type) => {
    const styles = {
      swap: { label: 'Swap', color: 'text-purple-400', bg: 'bg-purple-500/20' },
      transfer_in: { label: 'In', color: 'text-green-400', bg: 'bg-green-500/20' },
      transfer_out: { label: 'Out', color: 'text-red-400', bg: 'bg-red-500/20' },
      stake: { label: 'Stake', color: 'text-cyan-400', bg: 'bg-cyan-500/20' },
      unstake: { label: 'Unstake', color: 'text-orange-400', bg: 'bg-orange-500/20' },
      bridge: { label: 'Bridge', color: 'text-blue-400', bg: 'bg-blue-500/20' }
    }
    return styles[type] || styles.swap
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="w-6 h-6 text-cyan-400" />
          <h2 className="text-xl font-bold text-white">Wallet Profiler</h2>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white/5 rounded-xl p-6 border border-white/10">
        <form onSubmit={handleSearch} className="flex gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              placeholder="Enter wallet address (0x... or Solana address)"
              value={searchAddress}
              onChange={(e) => setSearchAddress(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 rounded-lg text-white placeholder:text-white/40 focus:outline-none focus:border-cyan-500"
            />
          </div>
          <button
            type="submit"
            disabled={!searchAddress || isLoading}
            className={`px-6 py-3 rounded-lg font-medium transition-all ${
              searchAddress && !isLoading
                ? 'bg-cyan-500 hover:bg-cyan-600 text-white'
                : 'bg-white/10 text-white/40 cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : (
              'Analyze'
            )}
          </button>
        </form>

        {/* Sample addresses */}
        <div className="mt-4 flex items-center gap-2">
          <span className="text-white/40 text-sm">Try:</span>
          {SAMPLE_ADDRESSES.map(sample => (
            <button
              key={sample.address}
              onClick={() => {
                setSearchAddress(sample.address)
                searchWallet(sample.address)
              }}
              className="px-3 py-1 bg-white/5 hover:bg-white/10 text-white/60 hover:text-white text-sm rounded-lg transition-all"
            >
              {sample.label}
            </button>
          ))}
        </div>
      </div>

      {/* Profile */}
      {profile && (
        <>
          {/* Wallet Header */}
          <div className="bg-white/5 rounded-xl p-6 border border-white/10">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div
                  className="w-14 h-14 rounded-xl flex items-center justify-center"
                  style={{ backgroundColor: `${profile.chain.color}20` }}
                >
                  <Wallet className="w-7 h-7" style={{ color: profile.chain.color }} />
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    {profile.label && (
                      <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                        {profile.label}
                      </span>
                    )}
                    <span className="text-white font-mono text-lg">
                      {profile.address.slice(0, 6)}...{profile.address.slice(-4)}
                    </span>
                    <button onClick={copyAddress} className="text-white/40 hover:text-white">
                      {copiedAddress ? (
                        <Check className="w-4 h-4 text-green-400" />
                      ) : (
                        <Copy className="w-4 h-4" />
                      )}
                    </button>
                    <a href="#" className="text-white/40 hover:text-white">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <div
                      className="px-2 py-0.5 rounded text-xs"
                      style={{ backgroundColor: `${profile.chain.color}20`, color: profile.chain.color }}
                    >
                      {profile.chain.name}
                    </div>
                    {profile.tags.map(tag => (
                      <span key={tag} className="px-2 py-0.5 bg-white/10 text-white/60 text-xs rounded">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-6">
                <div className="text-right">
                  <div className="text-3xl font-bold text-white">{formatNumber(profile.totalValue)}</div>
                  <div className={`text-sm ${profile.pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {profile.pnlPercent >= 0 ? '+' : ''}{profile.pnlPercent.toFixed(2)}% ({formatNumber(profile.totalPnl)})
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-6 gap-4">
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
                <Target className="w-4 h-4" />
                <span>Win Rate</span>
              </div>
              <div className="text-xl font-bold text-green-400">{profile.stats.winRate.toFixed(1)}%</div>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
                <Activity className="w-4 h-4" />
                <span>Trades</span>
              </div>
              <div className="text-xl font-bold text-white">{profile.stats.totalTrades}</div>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
                <DollarSign className="w-4 h-4" />
                <span>Avg Size</span>
              </div>
              <div className="text-xl font-bold text-white">{formatNumber(profile.stats.avgTradeSize)}</div>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
                <Calendar className="w-4 h-4" />
                <span>Age</span>
              </div>
              <div className="text-xl font-bold text-white">{profile.stats.accountAge}d</div>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
                <Layers className="w-4 h-4" />
                <span>Tokens</span>
              </div>
              <div className="text-xl font-bold text-cyan-400">{profile.stats.uniqueTokens}</div>
            </div>

            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <div className="flex items-center gap-2 text-white/60 text-sm mb-2">
                <Shield className="w-4 h-4" />
                <span>Risk</span>
              </div>
              <div className={`text-xl font-bold ${
                profile.stats.riskScore > 70 ? 'text-red-400' :
                profile.stats.riskScore > 40 ? 'text-yellow-400' : 'text-green-400'
              }`}>
                {profile.stats.riskScore}/100
              </div>
            </div>
          </div>

          {/* View Tabs */}
          <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
            {['overview', 'holdings', 'activity', 'defi'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-4 py-2 text-sm rounded-md transition-all capitalize ${
                  viewMode === mode
                    ? 'bg-cyan-500 text-white'
                    : 'text-white/60 hover:text-white'
                }`}
              >
                {mode}
              </button>
            ))}
          </div>

          {/* Overview */}
          {viewMode === 'overview' && (
            <div className="grid grid-cols-2 gap-4">
              {/* Top Holdings */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-white font-medium mb-4">Top Holdings</h3>
                <div className="space-y-3">
                  {profile.holdings.slice(0, 5).map(holding => (
                    <div key={holding.symbol} className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center text-xs font-bold text-white">
                          {holding.symbol.substring(0, 2)}
                        </div>
                        <div>
                          <div className="text-white text-sm">{holding.symbol}</div>
                          <div className="text-white/40 text-xs">{holding.allocation.toFixed(1)}%</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-white text-sm">{formatNumber(holding.value)}</div>
                        <div className={`text-xs ${holding.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {holding.pnl >= 0 ? '+' : ''}{holding.pnl.toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recent Activity */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h3 className="text-white font-medium mb-4">Recent Activity</h3>
                <div className="space-y-3">
                  {profile.transactions.slice(0, 5).map(tx => {
                    const style = getTxTypeStyle(tx.type)
                    return (
                      <div key={tx.id} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className={`px-2 py-1 text-xs rounded ${style.bg} ${style.color}`}>
                            {style.label}
                          </span>
                          <span className="text-white text-sm">{tx.token}</span>
                        </div>
                        <div className="text-right">
                          <div className="text-white text-sm">{formatNumber(tx.value)}</div>
                          <div className="text-white/40 text-xs">{formatTime(tx.timestamp)}</div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* DeFi Positions */}
              <div className="bg-white/5 rounded-xl p-4 border border-white/10 col-span-2">
                <h3 className="text-white font-medium mb-4">DeFi Positions</h3>
                <div className="grid grid-cols-3 gap-4">
                  {profile.defiPositions.map((pos, i) => (
                    <div key={i} className="p-3 bg-white/5 rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-white font-medium">{pos.protocol}</span>
                        <span className="text-white/40 text-xs capitalize">{pos.type}</span>
                      </div>
                      <div className="text-cyan-400 font-medium">{formatNumber(pos.value)}</div>
                      <div className="flex items-center justify-between mt-2 text-xs">
                        <span className="text-green-400">{pos.apy.toFixed(1)}% APY</span>
                        {pos.healthFactor && (
                          <span className={pos.healthFactor < 1.5 ? 'text-yellow-400' : 'text-white/40'}>
                            HF: {pos.healthFactor.toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Holdings */}
          {viewMode === 'holdings' && (
            <div className="bg-white/5 rounded-xl border border-white/10">
              <div className="p-4 border-b border-white/10">
                <h3 className="text-white font-medium">All Holdings</h3>
              </div>
              <div className="divide-y divide-white/10">
                {profile.holdings.map(holding => (
                  <div key={holding.symbol} className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-white/10 flex items-center justify-center text-sm font-bold text-white">
                        {holding.symbol.substring(0, 2)}
                      </div>
                      <div>
                        <div className="text-white font-medium">{holding.symbol}</div>
                        <div className="text-white/40 text-sm">{holding.name}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-8">
                      <div className="text-right">
                        <div className="text-white">{holding.amount.toLocaleString(undefined, { maximumFractionDigits: 4 })}</div>
                        <div className="text-white/40 text-xs">Balance</div>
                      </div>

                      <div className="text-right w-24">
                        <div className="text-white">${holding.price.toFixed(2)}</div>
                        <div className={`text-xs ${holding.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {holding.change24h >= 0 ? '+' : ''}{holding.change24h.toFixed(2)}%
                        </div>
                      </div>

                      <div className="text-right w-28">
                        <div className="text-white font-medium">{formatNumber(holding.value)}</div>
                        <div className="text-white/40 text-xs">{holding.allocation.toFixed(1)}%</div>
                      </div>

                      <div className="text-right w-24">
                        <div className={holding.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {holding.pnl >= 0 ? '+' : ''}{holding.pnl.toFixed(1)}%
                        </div>
                        <div className="text-white/40 text-xs">PnL</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Activity */}
          {viewMode === 'activity' && (
            <div className="bg-white/5 rounded-xl border border-white/10">
              <div className="p-4 border-b border-white/10">
                <h3 className="text-white font-medium">Transaction History</h3>
              </div>
              <div className="divide-y divide-white/10">
                {profile.transactions.map(tx => {
                  const style = getTxTypeStyle(tx.type)
                  return (
                    <div key={tx.id} className="p-4 flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <span className={`px-3 py-1.5 text-xs rounded ${style.bg} ${style.color}`}>
                          {style.label}
                        </span>
                        <div>
                          <div className="text-white font-medium">{tx.token}</div>
                          <div className="text-white/40 text-xs">{tx.amount.toFixed(4)} tokens</div>
                        </div>
                      </div>

                      <div className="flex items-center gap-6">
                        <div className="text-right">
                          <div className="text-white">{formatNumber(tx.value)}</div>
                          <div className="text-white/40 text-xs">Value</div>
                        </div>

                        <div className="text-right w-24">
                          <div className="text-white/60">${tx.gasCost.toFixed(2)}</div>
                          <div className="text-white/40 text-xs">Gas</div>
                        </div>

                        <div className="text-white/40 text-sm w-20 text-right">
                          {formatDate(tx.timestamp)}
                        </div>

                        <span className={`px-2 py-0.5 text-xs rounded ${
                          tx.status === 'success' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                        }`}>
                          {tx.status}
                        </span>

                        <a href="#" className="text-white/40 hover:text-white">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* DeFi */}
          {viewMode === 'defi' && (
            <div className="space-y-4">
              {profile.defiPositions.map((pos, i) => (
                <div key={i} className="bg-white/5 rounded-xl p-4 border border-white/10">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center">
                        <Layers className="w-6 h-6 text-white/60" />
                      </div>
                      <div>
                        <div className="text-white font-medium">{pos.protocol}</div>
                        <div className="text-white/40 text-sm capitalize">{pos.type}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-8">
                      <div className="text-right">
                        <div className="text-cyan-400 font-medium text-lg">{formatNumber(pos.value)}</div>
                        <div className="text-white/40 text-xs">Position Value</div>
                      </div>

                      <div className="text-right">
                        <div className="text-green-400 font-medium">{pos.apy.toFixed(2)}%</div>
                        <div className="text-white/40 text-xs">APY</div>
                      </div>

                      {pos.healthFactor && (
                        <div className="text-right">
                          <div className={`font-medium ${
                            pos.healthFactor < 1.3 ? 'text-red-400' :
                            pos.healthFactor < 1.5 ? 'text-yellow-400' : 'text-green-400'
                          }`}>
                            {pos.healthFactor.toFixed(2)}
                          </div>
                          <div className="text-white/40 text-xs">Health Factor</div>
                        </div>
                      )}

                      <a href="#" className="text-white/40 hover:text-white">
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Empty state */}
      {!profile && !isLoading && (
        <div className="bg-white/5 rounded-xl p-12 border border-white/10 text-center">
          <Wallet className="w-12 h-12 text-white/20 mx-auto mb-4" />
          <h3 className="text-white font-medium mb-2">Enter a wallet address to analyze</h3>
          <p className="text-white/40 text-sm">
            Get detailed insights including holdings, PnL, transaction history, and DeFi positions
          </p>
        </div>
      )}
    </div>
  )
}

export default WalletProfiler
