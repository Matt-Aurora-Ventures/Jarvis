import React, { useState, useMemo, useCallback, useEffect } from 'react'
import {
  Wallet, Plus, RefreshCw, Eye, EyeOff, Copy, ExternalLink, Trash2, Edit2,
  TrendingUp, TrendingDown, Activity, Shield, Zap, ChevronDown, ChevronRight,
  Clock, Search, Filter, Check, X, AlertCircle, DollarSign, Coins, PieChart
} from 'lucide-react'

/**
 * MultiWalletPortfolio - Track multiple wallets and aggregate portfolio
 *
 * Features:
 * - Multiple wallet management
 * - Aggregate portfolio view
 * - Per-wallet breakdown
 * - Token holdings across wallets
 * - Transaction history
 * - P&L tracking
 * - Role-based organization
 */

// Wallet roles
const WALLET_ROLES = {
  treasury: { label: 'Treasury', color: 'yellow', icon: Shield },
  trading: { label: 'Trading', color: 'green', icon: TrendingUp },
  cold: { label: 'Cold Storage', color: 'blue', icon: Shield },
  hot: { label: 'Hot Wallet', color: 'orange', icon: Zap },
  monitoring: { label: 'Watch Only', color: 'gray', icon: Eye },
}

/**
 * AddWalletModal - Modal for adding new wallet
 */
function AddWalletModal({ isOpen, onClose, onAdd }) {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [role, setRole] = useState('trading')
  const [error, setError] = useState('')

  const handleSubmit = useCallback((e) => {
    e.preventDefault()

    if (!name.trim()) {
      setError('Name is required')
      return
    }
    if (!address.trim()) {
      setError('Address is required')
      return
    }
    // Basic Solana address validation
    if (address.length < 32 || address.length > 44) {
      setError('Invalid Solana address')
      return
    }

    onAdd({ name: name.trim(), address: address.trim(), role })
    setName('')
    setAddress('')
    setRole('trading')
    setError('')
    onClose()
  }, [name, address, role, onAdd, onClose])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl border border-gray-800 w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-white">Add Wallet</h3>
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
            <label className="block text-sm text-gray-400 mb-1">Wallet Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
              placeholder="My Trading Wallet"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Wallet Address</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 font-mono text-sm focus:outline-none focus:border-purple-500"
              placeholder="Enter Solana address..."
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Wallet Role</label>
            <div className="grid grid-cols-3 gap-2">
              {Object.entries(WALLET_ROLES).map(([id, role]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setRole(id)}
                  className={`flex flex-col items-center gap-1 p-3 rounded-lg border transition-colors ${
                    id === role
                      ? `border-${role.color}-500 bg-${role.color}-500/10`
                      : 'border-gray-700 hover:border-gray-600'
                  }`}
                >
                  <role.icon className={`w-4 h-4 text-${role.color}-400`} />
                  <span className="text-xs text-gray-300">{role.label}</span>
                </button>
              ))}
            </div>
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
              Add Wallet
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

/**
 * WalletCard - Display single wallet with balance
 */
function WalletCard({
  wallet,
  onSelect,
  onRemove,
  onEdit,
  isSelected,
  showAddress = false,
}) {
  const [addressVisible, setAddressVisible] = useState(showAddress)

  const role = WALLET_ROLES[wallet.role] || WALLET_ROLES.trading

  const formatAddress = (addr) => {
    if (!addr) return ''
    return addressVisible ? addr : `${addr.slice(0, 4)}...${addr.slice(-4)}`
  }

  const copyAddress = useCallback((e) => {
    e.stopPropagation()
    navigator.clipboard.writeText(wallet.address)
  }, [wallet.address])

  const totalUsdValue = wallet.solBalance * wallet.solPrice + (wallet.tokensUsdValue || 0)
  const change24h = wallet.change24h || 0

  return (
    <div
      onClick={() => onSelect?.(wallet)}
      className={`bg-gray-900/50 rounded-lg border p-4 cursor-pointer transition-all ${
        isSelected ? 'border-purple-500 bg-purple-500/5' : 'border-gray-800 hover:border-gray-700'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg bg-${role.color}-500/10`}>
            <role.icon className={`w-5 h-5 text-${role.color}-400`} />
          </div>
          <div>
            <h3 className="font-medium text-white">{wallet.name}</h3>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400 font-mono">{formatAddress(wallet.address)}</span>
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  setAddressVisible(!addressVisible)
                }}
                className="p-0.5 hover:bg-gray-700 rounded"
              >
                {addressVisible ? (
                  <EyeOff className="w-3 h-3 text-gray-500" />
                ) : (
                  <Eye className="w-3 h-3 text-gray-500" />
                )}
              </button>
              <button onClick={copyAddress} className="p-0.5 hover:bg-gray-700 rounded">
                <Copy className="w-3 h-3 text-gray-500" />
              </button>
              <a
                href={`https://solscan.io/account/${wallet.address}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="p-0.5 hover:bg-gray-700 rounded"
              >
                <ExternalLink className="w-3 h-3 text-gray-500" />
              </a>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onEdit?.(wallet)
            }}
            className="p-1.5 rounded hover:bg-gray-800 text-gray-400"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onRemove?.(wallet)
            }}
            className="p-1.5 rounded hover:bg-red-500/20 text-gray-400 hover:text-red-400"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Balance */}
      <div className="flex items-end justify-between">
        <div>
          <div className="text-2xl font-semibold text-white">
            ${totalUsdValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-400">{wallet.solBalance?.toFixed(4) || 0} SOL</span>
            {wallet.tokenCount > 0 && (
              <span className="text-gray-500">+ {wallet.tokenCount} tokens</span>
            )}
          </div>
        </div>

        {/* 24h Change */}
        <div className={`flex items-center gap-1 ${change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          {change24h >= 0 ? (
            <TrendingUp className="w-4 h-4" />
          ) : (
            <TrendingDown className="w-4 h-4" />
          )}
          <span className="text-sm font-medium">
            {change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Role tag */}
      <div className="mt-3 pt-3 border-t border-gray-800">
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-${role.color}-500/10 text-${role.color}-400`}>
          <role.icon className="w-3 h-3" />
          {role.label}
        </span>
      </div>
    </div>
  )
}

/**
 * PortfolioSummary - Aggregate portfolio view
 */
function PortfolioSummary({ wallets, solPrice = 0 }) {
  const summary = useMemo(() => {
    let totalSol = 0
    let totalUsd = 0
    let totalTokens = {}
    let totalChange = 0
    let prevTotal = 0

    wallets.forEach(wallet => {
      totalSol += wallet.solBalance || 0
      const walletUsd = (wallet.solBalance || 0) * solPrice + (wallet.tokensUsdValue || 0)
      totalUsd += walletUsd

      // Aggregate token holdings
      if (wallet.tokens) {
        wallet.tokens.forEach(token => {
          if (!totalTokens[token.mint]) {
            totalTokens[token.mint] = {
              symbol: token.symbol,
              name: token.name,
              amount: 0,
              usdValue: 0,
            }
          }
          totalTokens[token.mint].amount += token.amount
          totalTokens[token.mint].usdValue += token.usdValue || 0
        })
      }

      // Calculate change
      if (wallet.change24h !== undefined) {
        const walletPrevUsd = walletUsd / (1 + wallet.change24h / 100)
        prevTotal += walletPrevUsd
        totalChange += walletUsd - walletPrevUsd
      }
    })

    const change24hPercent = prevTotal > 0 ? (totalChange / prevTotal) * 100 : 0

    return {
      totalSol,
      totalUsd,
      totalTokens: Object.values(totalTokens),
      change24h: totalChange,
      change24hPercent,
      walletCount: wallets.length,
    }
  }, [wallets, solPrice])

  return (
    <div className="bg-gradient-to-br from-purple-500/10 to-cyan-500/10 rounded-xl border border-purple-500/30 p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">Total Portfolio</h2>
        <span className="text-sm text-gray-400">{summary.walletCount} wallets</span>
      </div>

      <div className="flex items-end justify-between mb-6">
        <div>
          <div className="text-4xl font-bold text-white">
            ${summary.totalUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-gray-400 mt-1">
            {summary.totalSol.toFixed(4)} SOL
          </div>
        </div>

        <div className={`text-right ${summary.change24hPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
          <div className="flex items-center gap-1 justify-end">
            {summary.change24hPercent >= 0 ? (
              <TrendingUp className="w-5 h-5" />
            ) : (
              <TrendingDown className="w-5 h-5" />
            )}
            <span className="text-xl font-semibold">
              {summary.change24hPercent >= 0 ? '+' : ''}{summary.change24hPercent.toFixed(2)}%
            </span>
          </div>
          <div className="text-sm opacity-80">
            {summary.change24h >= 0 ? '+' : ''}${Math.abs(summary.change24h).toFixed(2)} (24h)
          </div>
        </div>
      </div>

      {/* Top holdings */}
      {summary.totalTokens.length > 0 && (
        <div className="pt-4 border-t border-purple-500/20">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-gray-400">Top Holdings</span>
            <Coins className="w-4 h-4 text-gray-500" />
          </div>
          <div className="flex flex-wrap gap-2">
            {summary.totalTokens
              .sort((a, b) => b.usdValue - a.usdValue)
              .slice(0, 5)
              .map((token, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 px-3 py-1.5 bg-gray-800/50 rounded-lg"
                >
                  <span className="font-medium text-white">{token.symbol}</span>
                  <span className="text-sm text-gray-400">
                    ${token.usdValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * TokenHoldings - Aggregated token holdings across wallets
 */
function TokenHoldings({ wallets, className = '' }) {
  const [sortBy, setSortBy] = useState('value') // value, name, change

  const aggregatedTokens = useMemo(() => {
    const tokens = {}

    wallets.forEach(wallet => {
      if (wallet.tokens) {
        wallet.tokens.forEach(token => {
          if (!tokens[token.mint]) {
            tokens[token.mint] = {
              symbol: token.symbol,
              name: token.name,
              mint: token.mint,
              amount: 0,
              usdValue: 0,
              wallets: [],
              price: token.price || 0,
              change24h: token.change24h || 0,
            }
          }
          tokens[token.mint].amount += token.amount
          tokens[token.mint].usdValue += token.usdValue || 0
          tokens[token.mint].wallets.push(wallet.name)
        })
      }
    })

    let tokenList = Object.values(tokens)

    // Sort
    if (sortBy === 'value') {
      tokenList.sort((a, b) => b.usdValue - a.usdValue)
    } else if (sortBy === 'name') {
      tokenList.sort((a, b) => a.symbol.localeCompare(b.symbol))
    } else if (sortBy === 'change') {
      tokenList.sort((a, b) => b.change24h - a.change24h)
    }

    return tokenList
  }, [wallets, sortBy])

  if (aggregatedTokens.length === 0) {
    return (
      <div className={`bg-gray-900/50 rounded-lg border border-gray-800 p-6 text-center ${className}`}>
        <Coins className="w-12 h-12 text-gray-600 mx-auto mb-4" />
        <p className="text-gray-400">No token holdings found</p>
      </div>
    )
  }

  return (
    <div className={`bg-gray-900/50 rounded-lg border border-gray-800 ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <Coins className="w-4 h-4 text-purple-400" />
          <span className="font-medium text-white">Token Holdings</span>
          <span className="text-sm text-gray-500">({aggregatedTokens.length})</span>
        </div>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-white"
        >
          <option value="value">By Value</option>
          <option value="name">By Name</option>
          <option value="change">By Change</option>
        </select>
      </div>

      <div className="divide-y divide-gray-800 max-h-96 overflow-y-auto">
        {aggregatedTokens.map((token, i) => (
          <div key={i} className="flex items-center justify-between px-4 py-3 hover:bg-gray-800/50">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-gray-800 rounded-full flex items-center justify-center">
                <span className="text-xs font-medium text-gray-300">
                  {token.symbol?.slice(0, 2)}
                </span>
              </div>
              <div>
                <div className="font-medium text-white">{token.symbol}</div>
                <div className="text-sm text-gray-400">
                  {token.amount.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                </div>
              </div>
            </div>

            <div className="text-right">
              <div className="font-medium text-white">
                ${token.usdValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
              <div className={`text-sm ${token.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {token.change24h >= 0 ? '+' : ''}{token.change24h.toFixed(2)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Main MultiWalletPortfolio Component
 */
export function MultiWalletPortfolio({
  initialWallets = [],
  solPrice = 200,
  onWalletAdd,
  onWalletRemove,
  onWalletEdit,
  onRefresh,
  className = '',
}) {
  const [wallets, setWallets] = useState(initialWallets)
  const [selectedWallet, setSelectedWallet] = useState(null)
  const [isAddModalOpen, setIsAddModalOpen] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterRole, setFilterRole] = useState('all')
  const [viewMode, setViewMode] = useState('grid') // grid, list

  // Filter wallets
  const filteredWallets = useMemo(() => {
    return wallets.filter(wallet => {
      const matchesSearch = searchQuery === '' ||
        wallet.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        wallet.address.toLowerCase().includes(searchQuery.toLowerCase())

      const matchesRole = filterRole === 'all' || wallet.role === filterRole

      return matchesSearch && matchesRole
    })
  }, [wallets, searchQuery, filterRole])

  // Handle add wallet
  const handleAddWallet = useCallback((walletData) => {
    const newWallet = {
      id: `wallet_${Date.now()}`,
      ...walletData,
      solBalance: 0,
      tokensUsdValue: 0,
      tokenCount: 0,
      change24h: 0,
      tokens: [],
      createdAt: new Date().toISOString(),
    }

    setWallets(prev => [...prev, newWallet])
    onWalletAdd?.(newWallet)
  }, [onWalletAdd])

  // Handle remove wallet
  const handleRemoveWallet = useCallback((wallet) => {
    if (confirm(`Remove wallet "${wallet.name}"?`)) {
      setWallets(prev => prev.filter(w => w.id !== wallet.id))
      onWalletRemove?.(wallet)
      if (selectedWallet?.id === wallet.id) {
        setSelectedWallet(null)
      }
    }
  }, [selectedWallet, onWalletRemove])

  // Handle refresh
  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true)
    try {
      if (onRefresh) {
        const updated = await onRefresh(wallets)
        if (updated) {
          setWallets(updated)
        }
      }
    } finally {
      setIsRefreshing(false)
    }
  }, [wallets, onRefresh])

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Multi-Wallet Portfolio</h1>
          <p className="text-gray-400">Track and manage all your wallets in one place</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 rounded-lg text-gray-300 hover:bg-gray-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={() => setIsAddModalOpen(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
          >
            <Plus className="w-4 h-4" />
            Add Wallet
          </button>
        </div>
      </div>

      {/* Portfolio Summary */}
      <PortfolioSummary wallets={wallets} solPrice={solPrice} />

      {/* Filters */}
      <div className="flex items-center gap-4 my-6">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search wallets..."
            className="w-full pl-10 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500"
          />
        </div>

        <select
          value={filterRole}
          onChange={(e) => setFilterRole(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white"
        >
          <option value="all">All Roles</option>
          {Object.entries(WALLET_ROLES).map(([id, role]) => (
            <option key={id} value={id}>{role.label}</option>
          ))}
        </select>

        <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-gray-700 text-white' : 'text-gray-400'}`}
          >
            <PieChart className="w-4 h-4" />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2 rounded ${viewMode === 'list' ? 'bg-gray-700 text-white' : 'text-gray-400'}`}
          >
            <Activity className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Wallet List */}
        <div className="lg:col-span-2">
          {filteredWallets.length === 0 ? (
            <div className="text-center py-12">
              <Wallet className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-400 mb-2">No Wallets Found</h3>
              <p className="text-sm text-gray-500 mb-4">
                {wallets.length === 0
                  ? 'Add your first wallet to start tracking'
                  : 'No wallets match your search'}
              </p>
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-purple-500 rounded-lg text-white hover:bg-purple-600"
              >
                <Plus className="w-4 h-4" />
                Add Wallet
              </button>
            </div>
          ) : (
            <div className={viewMode === 'grid' ? 'grid grid-cols-1 md:grid-cols-2 gap-4' : 'space-y-3'}>
              {filteredWallets.map(wallet => (
                <WalletCard
                  key={wallet.id}
                  wallet={wallet}
                  solPrice={solPrice}
                  onSelect={setSelectedWallet}
                  onRemove={handleRemoveWallet}
                  onEdit={onWalletEdit}
                  isSelected={selectedWallet?.id === wallet.id}
                />
              ))}
            </div>
          )}
        </div>

        {/* Token Holdings Sidebar */}
        <div>
          <TokenHoldings wallets={wallets} />
        </div>
      </div>

      {/* Add Wallet Modal */}
      <AddWalletModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddWallet}
      />
    </div>
  )
}

export default MultiWalletPortfolio
