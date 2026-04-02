import React, { useState, useMemo, useCallback } from 'react'
import {
  Wallet, RefreshCw, Plus, Trash2, Copy, Check, ExternalLink,
  TrendingUp, TrendingDown, PieChart, BarChart3, ArrowUpRight,
  ArrowDownRight, Layers, Link2, Settings, Eye, EyeOff, Search,
  ChevronDown, ChevronUp, Sparkles, Coins, Activity, Globe
} from 'lucide-react'

// Supported chains
const CHAINS = {
  SOLANA: {
    name: 'Solana',
    symbol: 'SOL',
    color: '#9945FF',
    icon: 'S',
    explorer: 'https://solscan.io',
    nativePrice: 198
  },
  ETHEREUM: {
    name: 'Ethereum',
    symbol: 'ETH',
    color: '#627EEA',
    icon: 'E',
    explorer: 'https://etherscan.io',
    nativePrice: 3450
  },
  ARBITRUM: {
    name: 'Arbitrum',
    symbol: 'ARB',
    color: '#28A0F0',
    icon: 'A',
    explorer: 'https://arbiscan.io',
    nativePrice: 3450
  },
  BASE: {
    name: 'Base',
    symbol: 'ETH',
    color: '#0052FF',
    icon: 'B',
    explorer: 'https://basescan.org',
    nativePrice: 3450
  },
  POLYGON: {
    name: 'Polygon',
    symbol: 'MATIC',
    color: '#8247E5',
    icon: 'P',
    explorer: 'https://polygonscan.com',
    nativePrice: 0.95
  },
  BSC: {
    name: 'BNB Chain',
    symbol: 'BNB',
    color: '#F0B90B',
    icon: 'B',
    explorer: 'https://bscscan.com',
    nativePrice: 715
  },
  AVALANCHE: {
    name: 'Avalanche',
    symbol: 'AVAX',
    color: '#E84142',
    icon: 'A',
    explorer: 'https://snowtrace.io',
    nativePrice: 42.50
  },
  OPTIMISM: {
    name: 'Optimism',
    symbol: 'OP',
    color: '#FF0420',
    icon: 'O',
    explorer: 'https://optimistic.etherscan.io',
    nativePrice: 3450
  }
}

// Mock wallet data
const MOCK_WALLETS = [
  {
    id: '1',
    name: 'Main Wallet',
    address: '7xKX...9dR4',
    chain: 'SOLANA',
    holdings: [
      { symbol: 'SOL', name: 'Solana', amount: 125.5, price: 198, change24h: 3.2, logo: null },
      { symbol: 'BONK', name: 'Bonk', amount: 15000000, price: 0.000032, change24h: -5.1, logo: null },
      { symbol: 'JUP', name: 'Jupiter', amount: 850, price: 1.25, change24h: 8.5, logo: null },
      { symbol: 'RAY', name: 'Raydium', amount: 420, price: 5.80, change24h: 2.1, logo: null }
    ]
  },
  {
    id: '2',
    name: 'DeFi Wallet',
    address: '0x8f3...a21b',
    chain: 'ETHEREUM',
    holdings: [
      { symbol: 'ETH', name: 'Ethereum', amount: 5.2, price: 3450, change24h: 1.8, logo: null },
      { symbol: 'USDC', name: 'USD Coin', amount: 15000, price: 1.00, change24h: 0, logo: null },
      { symbol: 'LINK', name: 'Chainlink', amount: 200, price: 18.50, change24h: -2.3, logo: null },
      { symbol: 'UNI', name: 'Uniswap', amount: 150, price: 12.80, change24h: 4.2, logo: null }
    ]
  },
  {
    id: '3',
    name: 'L2 Trading',
    address: '0x4d2...b89c',
    chain: 'ARBITRUM',
    holdings: [
      { symbol: 'ETH', name: 'Ethereum', amount: 2.8, price: 3450, change24h: 1.8, logo: null },
      { symbol: 'ARB', name: 'Arbitrum', amount: 5000, price: 1.15, change24h: -1.2, logo: null },
      { symbol: 'GMX', name: 'GMX', amount: 45, price: 48.50, change24h: 5.8, logo: null },
      { symbol: 'MAGIC', name: 'Magic', amount: 1200, price: 0.85, change24h: -3.5, logo: null }
    ]
  },
  {
    id: '4',
    name: 'Base Portfolio',
    address: '0x9a1...c45d',
    chain: 'BASE',
    holdings: [
      { symbol: 'ETH', name: 'Ethereum', amount: 1.5, price: 3450, change24h: 1.8, logo: null },
      { symbol: 'AERO', name: 'Aerodrome', amount: 8500, price: 1.42, change24h: 12.5, logo: null },
      { symbol: 'BRETT', name: 'Brett', amount: 25000, price: 0.18, change24h: -8.2, logo: null }
    ]
  }
]

// Token category for coloring
const getTokenCategory = (symbol) => {
  const stables = ['USDC', 'USDT', 'DAI', 'BUSD']
  const majors = ['BTC', 'ETH', 'SOL', 'BNB', 'AVAX', 'MATIC']
  const defi = ['UNI', 'AAVE', 'LINK', 'GMX', 'JUP', 'RAY']
  const meme = ['BONK', 'PEPE', 'WIF', 'DOGE', 'SHIB', 'BRETT']

  if (stables.includes(symbol)) return 'stable'
  if (majors.includes(symbol)) return 'major'
  if (defi.includes(symbol)) return 'defi'
  if (meme.includes(symbol)) return 'meme'
  return 'other'
}

const categoryColors = {
  stable: '#22C55E',
  major: '#3B82F6',
  defi: '#8B5CF6',
  meme: '#F59E0B',
  other: '#6B7280'
}

// Chain badge component
const ChainBadge = ({ chain, size = 'md' }) => {
  const chainData = CHAINS[chain]
  const sizeClasses = size === 'sm' ? 'w-5 h-5 text-xs' : 'w-6 h-6 text-sm'

  return (
    <div
      className={`${sizeClasses} rounded-full flex items-center justify-center font-bold`}
      style={{ backgroundColor: chainData.color, color: '#000' }}
      title={chainData.name}
    >
      {chainData.icon}
    </div>
  )
}

// Token row in wallet
const TokenRow = ({ token, showValue = true }) => {
  const value = token.amount * token.price
  const category = getTokenCategory(token.symbol)

  return (
    <div className="flex items-center justify-between py-2 px-3 hover:bg-white/5 rounded-lg transition-colors">
      <div className="flex items-center gap-3">
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
          style={{ backgroundColor: `${categoryColors[category]}30`, color: categoryColors[category] }}
        >
          {token.symbol.slice(0, 2)}
        </div>
        <div>
          <div className="font-medium">{token.symbol}</div>
          <div className="text-xs text-gray-500">{token.name}</div>
        </div>
      </div>

      <div className="text-right">
        {showValue && (
          <div className="font-medium">
            ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
        )}
        <div className="text-xs text-gray-400">
          {token.amount.toLocaleString(undefined, { maximumFractionDigits: token.amount < 1 ? 8 : 2 })} {token.symbol}
        </div>
      </div>

      <div className={`flex items-center gap-1 text-sm min-w-[70px] justify-end ${
        token.change24h > 0 ? 'text-green-400' : token.change24h < 0 ? 'text-red-400' : 'text-gray-400'
      }`}>
        {token.change24h > 0 ? <ArrowUpRight className="w-4 h-4" /> : token.change24h < 0 ? <ArrowDownRight className="w-4 h-4" /> : null}
        {Math.abs(token.change24h).toFixed(1)}%
      </div>
    </div>
  )
}

// Wallet card component
const WalletCard = ({ wallet, expanded, onExpand, onRemove, hideBalances }) => {
  const chainData = CHAINS[wallet.chain]
  const totalValue = wallet.holdings.reduce((sum, t) => sum + t.amount * t.price, 0)
  const totalChange = wallet.holdings.reduce((sum, t) => {
    const value = t.amount * t.price
    return sum + (value * t.change24h / 100)
  }, 0)
  const changePercent = (totalChange / (totalValue - totalChange)) * 100

  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(wallet.address)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
      <div
        className="p-4 cursor-pointer hover:bg-white/[0.02] transition-colors"
        onClick={() => onExpand(expanded ? null : wallet.id)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <ChainBadge chain={wallet.chain} />
            <div>
              <div className="font-medium flex items-center gap-2">
                {wallet.name}
                <span className="text-xs px-2 py-0.5 rounded-full bg-white/10 text-gray-400">
                  {chainData.name}
                </span>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <span className="font-mono">{wallet.address}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); handleCopy() }}
                  className="hover:text-white transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <a
                  href={`${chainData.explorer}/address/${wallet.address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  className="hover:text-white transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <div className="text-lg font-bold">
                {hideBalances ? '****' : `$${totalValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}`}
              </div>
              <div className={`text-sm flex items-center justify-end gap-1 ${
                changePercent > 0 ? 'text-green-400' : changePercent < 0 ? 'text-red-400' : 'text-gray-400'
              }`}>
                {changePercent > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                {hideBalances ? '**' : `${changePercent > 0 ? '+' : ''}${changePercent.toFixed(2)}%`}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={(e) => { e.stopPropagation(); onRemove(wallet.id) }}
                className="p-1.5 hover:bg-white/10 rounded-lg text-gray-500 hover:text-red-400 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
              {expanded ? <ChevronUp className="w-5 h-5 text-gray-400" /> : <ChevronDown className="w-5 h-5 text-gray-400" />}
            </div>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-white/10 p-4 bg-white/[0.02]">
          <div className="space-y-1">
            {wallet.holdings.map((token, idx) => (
              <TokenRow key={idx} token={token} showValue={!hideBalances} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// Portfolio allocation chart
const AllocationChart = ({ wallets, hideBalances }) => {
  const allocations = useMemo(() => {
    const byCategory = {}

    wallets.forEach(wallet => {
      wallet.holdings.forEach(token => {
        const category = getTokenCategory(token.symbol)
        const value = token.amount * token.price
        byCategory[category] = (byCategory[category] || 0) + value
      })
    })

    const total = Object.values(byCategory).reduce((a, b) => a + b, 0)

    return Object.entries(byCategory)
      .map(([category, value]) => ({
        category,
        value,
        percent: (value / total) * 100
      }))
      .sort((a, b) => b.value - a.value)
  }, [wallets])

  const categoryLabels = {
    stable: 'Stablecoins',
    major: 'Major Assets',
    defi: 'DeFi Tokens',
    meme: 'Meme Coins',
    other: 'Other'
  }

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <PieChart className="w-4 h-4" />
        Portfolio Allocation
      </h3>

      <div className="space-y-3">
        {allocations.map(alloc => (
          <div key={alloc.category}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="text-gray-400">{categoryLabels[alloc.category]}</span>
              <span className="font-medium">
                {hideBalances ? '**%' : `${alloc.percent.toFixed(1)}%`}
              </span>
            </div>
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: hideBalances ? '0%' : `${alloc.percent}%`,
                  backgroundColor: categoryColors[alloc.category]
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Chain distribution
const ChainDistribution = ({ wallets, hideBalances }) => {
  const distribution = useMemo(() => {
    const byChain = {}

    wallets.forEach(wallet => {
      const chainValue = wallet.holdings.reduce((sum, t) => sum + t.amount * t.price, 0)
      byChain[wallet.chain] = (byChain[wallet.chain] || 0) + chainValue
    })

    const total = Object.values(byChain).reduce((a, b) => a + b, 0)

    return Object.entries(byChain)
      .map(([chain, value]) => ({
        chain,
        value,
        percent: (value / total) * 100
      }))
      .sort((a, b) => b.value - a.value)
  }, [wallets])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Layers className="w-4 h-4" />
        Chain Distribution
      </h3>

      <div className="space-y-3">
        {distribution.map(({ chain, value, percent }) => (
          <div key={chain} className="flex items-center gap-3">
            <ChainBadge chain={chain} size="sm" />
            <div className="flex-1">
              <div className="flex items-center justify-between text-sm mb-1">
                <span>{CHAINS[chain].name}</span>
                <span className="font-medium">
                  {hideBalances ? '****' : `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
                </span>
              </div>
              <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: hideBalances ? '0%' : `${percent}%`,
                    backgroundColor: CHAINS[chain].color
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Portfolio summary stats
const PortfolioStats = ({ wallets, hideBalances }) => {
  const stats = useMemo(() => {
    let totalValue = 0
    let totalChange = 0
    let tokenCount = 0
    const uniqueTokens = new Set()

    wallets.forEach(wallet => {
      wallet.holdings.forEach(token => {
        const value = token.amount * token.price
        totalValue += value
        totalChange += value * token.change24h / 100
        uniqueTokens.add(token.symbol)
        tokenCount++
      })
    })

    return {
      totalValue,
      totalChange,
      changePercent: (totalChange / (totalValue - totalChange)) * 100,
      walletCount: wallets.length,
      uniqueTokens: uniqueTokens.size,
      chainCount: new Set(wallets.map(w => w.chain)).size
    }
  }, [wallets])

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Total Portfolio</div>
        <div className="text-2xl font-bold">
          {hideBalances ? '********' : `$${stats.totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
        </div>
        <div className={`text-sm flex items-center gap-1 ${
          stats.changePercent > 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {stats.changePercent > 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {hideBalances ? '**' : `${stats.changePercent > 0 ? '+' : ''}${stats.changePercent.toFixed(2)}%`} (24h)
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">24h Change</div>
        <div className={`text-2xl font-bold ${
          stats.totalChange > 0 ? 'text-green-400' : 'text-red-400'
        }`}>
          {hideBalances ? '****' : `${stats.totalChange > 0 ? '+' : ''}$${stats.totalChange.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
        </div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Wallets</div>
        <div className="text-2xl font-bold">{stats.walletCount}</div>
        <div className="text-sm text-gray-500">{stats.chainCount} chains</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Unique Tokens</div>
        <div className="text-2xl font-bold">{stats.uniqueTokens}</div>
        <div className="text-sm text-gray-500">across all wallets</div>
      </div>
    </div>
  )
}

// Add wallet modal
const AddWalletModal = ({ isOpen, onClose, onAdd }) => {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [chain, setChain] = useState('SOLANA')

  const handleSubmit = () => {
    if (!name || !address) return
    onAdd({ name, address, chain })
    setName('')
    setAddress('')
    setChain('SOLANA')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#0a0e14] border border-white/10 rounded-xl p-6 w-full max-w-md">
        <h3 className="text-lg font-semibold mb-4">Add Wallet</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-2">Wallet Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Main Trading Wallet"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Chain</label>
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(CHAINS).slice(0, 8).map(([key, chainData]) => (
                <button
                  key={key}
                  onClick={() => setChain(key)}
                  className={`p-2 rounded-lg flex flex-col items-center gap-1 transition-colors ${
                    chain === key
                      ? 'bg-white/10 border border-white/30'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <ChainBadge chain={key} size="sm" />
                  <span className="text-xs">{chainData.name.split(' ')[0]}</span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-2">Wallet Address</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Enter wallet address"
              className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 font-mono text-sm"
            />
          </div>
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name || !address}
            className="flex-1 px-4 py-2 bg-blue-500 hover:bg-blue-600 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            Add Wallet
          </button>
        </div>
      </div>
    </div>
  )
}

// Top movers
const TopMovers = ({ wallets }) => {
  const allTokens = useMemo(() => {
    const tokens = []
    wallets.forEach(wallet => {
      wallet.holdings.forEach(token => {
        const existing = tokens.find(t => t.symbol === token.symbol)
        if (existing) {
          existing.totalValue += token.amount * token.price
        } else {
          tokens.push({
            ...token,
            totalValue: token.amount * token.price
          })
        }
      })
    })
    return tokens
  }, [wallets])

  const gainers = [...allTokens].sort((a, b) => b.change24h - a.change24h).slice(0, 3)
  const losers = [...allTokens].sort((a, b) => a.change24h - b.change24h).slice(0, 3)

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4" />
        Top Movers (24h)
      </h3>

      <div className="space-y-4">
        <div>
          <div className="text-xs text-green-400 mb-2">TOP GAINERS</div>
          {gainers.map((token, idx) => (
            <div key={idx} className="flex items-center justify-between py-1.5">
              <span className="font-medium">{token.symbol}</span>
              <span className="text-green-400">+{token.change24h.toFixed(1)}%</span>
            </div>
          ))}
        </div>

        <div>
          <div className="text-xs text-red-400 mb-2">TOP LOSERS</div>
          {losers.filter(t => t.change24h < 0).map((token, idx) => (
            <div key={idx} className="flex items-center justify-between py-1.5">
              <span className="font-medium">{token.symbol}</span>
              <span className="text-red-400">{token.change24h.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Main component
export const MultiChainPortfolio = () => {
  const [wallets, setWallets] = useState(MOCK_WALLETS)
  const [expandedWallet, setExpandedWallet] = useState(null)
  const [hideBalances, setHideBalances] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedChain, setSelectedChain] = useState('ALL')
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 1500)
  }, [])

  const handleAddWallet = useCallback((wallet) => {
    setWallets(prev => [...prev, {
      id: Date.now().toString(),
      ...wallet,
      holdings: []
    }])
  }, [])

  const handleRemoveWallet = useCallback((id) => {
    setWallets(prev => prev.filter(w => w.id !== id))
  }, [])

  const filteredWallets = useMemo(() => {
    let result = [...wallets]

    if (selectedChain !== 'ALL') {
      result = result.filter(w => w.chain === selectedChain)
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(w =>
        w.name.toLowerCase().includes(query) ||
        w.address.toLowerCase().includes(query) ||
        w.holdings.some(h => h.symbol.toLowerCase().includes(query))
      )
    }

    return result
  }, [wallets, selectedChain, searchQuery])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Globe className="w-7 h-7 text-blue-400" />
              Multi-Chain Portfolio
            </h1>
            <p className="text-gray-400 mt-1">Track your assets across all chains in one place</p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setHideBalances(!hideBalances)}
              className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
              title={hideBalances ? 'Show balances' : 'Hide balances'}
            >
              {hideBalances ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
            </button>

            <button
              onClick={handleRefresh}
              className={`p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors ${
                refreshing ? 'animate-spin' : ''
              }`}
            >
              <RefreshCw className="w-5 h-5" />
            </button>

            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg font-medium transition-colors"
            >
              <Plus className="w-5 h-5" />
              Add Wallet
            </button>
          </div>
        </div>

        {/* Stats */}
        <PortfolioStats wallets={wallets} hideBalances={hideBalances} />

        {/* Filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search wallets or tokens..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>

          <div className="flex bg-white/5 rounded-lg p-1">
            <button
              onClick={() => setSelectedChain('ALL')}
              className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                selectedChain === 'ALL'
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              All Chains
            </button>
            {Object.entries(CHAINS).slice(0, 5).map(([key, chain]) => (
              <button
                key={key}
                onClick={() => setSelectedChain(key)}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors flex items-center gap-1.5 ${
                  selectedChain === key
                    ? 'bg-white/10 text-white'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <ChainBadge chain={key} size="sm" />
              </button>
            ))}
          </div>
        </div>

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Wallet list */}
          <div className="lg:col-span-2 space-y-4">
            {filteredWallets.map(wallet => (
              <WalletCard
                key={wallet.id}
                wallet={wallet}
                expanded={expandedWallet === wallet.id}
                onExpand={setExpandedWallet}
                onRemove={handleRemoveWallet}
                hideBalances={hideBalances}
              />
            ))}

            {filteredWallets.length === 0 && (
              <div className="text-center py-12 bg-white/5 rounded-xl border border-white/10">
                <Wallet className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                <p className="text-gray-400 mb-4">No wallets found</p>
                <button
                  onClick={() => setShowAddModal(true)}
                  className="px-4 py-2 bg-blue-500 hover:bg-blue-600 rounded-lg font-medium transition-colors"
                >
                  Add Your First Wallet
                </button>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <AllocationChart wallets={wallets} hideBalances={hideBalances} />
            <ChainDistribution wallets={wallets} hideBalances={hideBalances} />
            <TopMovers wallets={wallets} />
          </div>
        </div>

        {/* Add Wallet Modal */}
        <AddWalletModal
          isOpen={showAddModal}
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddWallet}
        />
      </div>
    </div>
  )
}

export default MultiChainPortfolio
