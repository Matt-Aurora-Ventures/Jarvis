import React, { useState, useMemo, useCallback } from 'react'
import {
  ArrowUpRight,
  ArrowDownLeft,
  ArrowLeftRight,
  RefreshCw,
  Filter,
  Search,
  Calendar,
  Download,
  ExternalLink,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Wallet,
  Coins,
  TrendingUp,
  TrendingDown,
  Zap,
  Gift,
  Lock,
  Unlock,
  Droplets,
  X,
  FileText,
  BarChart3
} from 'lucide-react'

// Transaction types
const TX_TYPES = {
  SWAP: { label: 'Swap', icon: ArrowLeftRight, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  SEND: { label: 'Send', icon: ArrowUpRight, color: 'text-red-400', bg: 'bg-red-400/10' },
  RECEIVE: { label: 'Receive', icon: ArrowDownLeft, color: 'text-green-400', bg: 'bg-green-400/10' },
  STAKE: { label: 'Stake', icon: Lock, color: 'text-purple-400', bg: 'bg-purple-400/10' },
  UNSTAKE: { label: 'Unstake', icon: Unlock, color: 'text-orange-400', bg: 'bg-orange-400/10' },
  ADD_LIQUIDITY: { label: 'Add Liquidity', icon: Droplets, color: 'text-cyan-400', bg: 'bg-cyan-400/10' },
  REMOVE_LIQUIDITY: { label: 'Remove Liquidity', icon: Droplets, color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  CLAIM: { label: 'Claim', icon: Gift, color: 'text-pink-400', bg: 'bg-pink-400/10' },
  MINT: { label: 'Mint', icon: Coins, color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  BURN: { label: 'Burn', icon: Zap, color: 'text-amber-400', bg: 'bg-amber-400/10' },
  APPROVE: { label: 'Approve', icon: Check, color: 'text-slate-400', bg: 'bg-slate-400/10' },
  NFT_BUY: { label: 'NFT Buy', icon: ArrowDownLeft, color: 'text-violet-400', bg: 'bg-violet-400/10' },
  NFT_SELL: { label: 'NFT Sell', icon: ArrowUpRight, color: 'text-fuchsia-400', bg: 'bg-fuchsia-400/10' }
}

// Transaction status
const TX_STATUS = {
  SUCCESS: { label: 'Success', color: 'text-green-400', bg: 'bg-green-400/10' },
  PENDING: { label: 'Pending', color: 'text-yellow-400', bg: 'bg-yellow-400/10' },
  FAILED: { label: 'Failed', color: 'text-red-400', bg: 'bg-red-400/10' }
}

// Platforms
const PLATFORMS = {
  JUPITER: { name: 'Jupiter', color: 'text-green-400' },
  RAYDIUM: { name: 'Raydium', color: 'text-purple-400' },
  ORCA: { name: 'Orca', color: 'text-cyan-400' },
  PHANTOM: { name: 'Phantom', color: 'text-violet-400' },
  MAGIC_EDEN: { name: 'Magic Eden', color: 'text-pink-400' },
  TENSOR: { name: 'Tensor', color: 'text-blue-400' },
  MARINADE: { name: 'Marinade', color: 'text-teal-400' },
  SOLEND: { name: 'Solend', color: 'text-orange-400' },
  NATIVE: { name: 'Native', color: 'text-slate-400' }
}

// Mock transaction data
const mockTransactions = [
  {
    id: 'tx1',
    signature: '5UxV7nM...kP9r',
    fullSignature: '5UxV7nMaBC123456789abcdefghijklmnopqrstuvwxyzkP9r',
    type: 'SWAP',
    status: 'SUCCESS',
    platform: 'JUPITER',
    timestamp: Date.now() - 1000 * 60 * 5,
    tokenIn: { symbol: 'SOL', amount: 2.5, logo: null },
    tokenOut: { symbol: 'BONK', amount: 125000000, logo: null },
    valueUsd: 450.00,
    fee: 0.000005,
    feeUsd: 0.0009,
    from: 'Your Wallet',
    to: 'Jupiter Aggregator',
    slippage: 0.12,
    priceImpact: 0.05
  },
  {
    id: 'tx2',
    signature: '3KmL8xY...jQ2s',
    fullSignature: '3KmL8xYaBC123456789abcdefghijklmnopqrstuvwxyzjQ2s',
    type: 'RECEIVE',
    status: 'SUCCESS',
    platform: 'NATIVE',
    timestamp: Date.now() - 1000 * 60 * 30,
    tokenIn: null,
    tokenOut: { symbol: 'USDC', amount: 1000, logo: null },
    valueUsd: 1000.00,
    fee: 0,
    feeUsd: 0,
    from: '7xKq...mN3p',
    to: 'Your Wallet'
  },
  {
    id: 'tx3',
    signature: '9PqR4mN...hT5v',
    fullSignature: '9PqR4mNaBC123456789abcdefghijklmnopqrstuvwxyzhT5v',
    type: 'STAKE',
    status: 'SUCCESS',
    platform: 'MARINADE',
    timestamp: Date.now() - 1000 * 60 * 60 * 2,
    tokenIn: { symbol: 'SOL', amount: 10, logo: null },
    tokenOut: { symbol: 'mSOL', amount: 9.85, logo: null },
    valueUsd: 1800.00,
    fee: 0.00001,
    feeUsd: 0.0018,
    from: 'Your Wallet',
    to: 'Marinade Finance'
  },
  {
    id: 'tx4',
    signature: '2WxY6kL...pN8m',
    fullSignature: '2WxY6kLaBC123456789abcdefghijklmnopqrstuvwxyzpN8m',
    type: 'ADD_LIQUIDITY',
    status: 'SUCCESS',
    platform: 'RAYDIUM',
    timestamp: Date.now() - 1000 * 60 * 60 * 5,
    tokenIn: { symbol: 'SOL/USDC', amount: '5 + 900', logo: null },
    tokenOut: { symbol: 'LP Token', amount: 1, logo: null },
    valueUsd: 1800.00,
    fee: 0.00002,
    feeUsd: 0.0036,
    from: 'Your Wallet',
    to: 'Raydium AMM'
  },
  {
    id: 'tx5',
    signature: '8HjK3nP...qR4t',
    fullSignature: '8HjK3nPaBC123456789abcdefghijklmnopqrstuvwxyzqR4t',
    type: 'SWAP',
    status: 'FAILED',
    platform: 'JUPITER',
    timestamp: Date.now() - 1000 * 60 * 60 * 8,
    tokenIn: { symbol: 'USDC', amount: 500, logo: null },
    tokenOut: { symbol: 'WIF', amount: 0, logo: null },
    valueUsd: 500.00,
    fee: 0.000005,
    feeUsd: 0.0009,
    from: 'Your Wallet',
    to: 'Jupiter Aggregator',
    failReason: 'Slippage tolerance exceeded'
  },
  {
    id: 'tx6',
    signature: '4TyU9mK...wX2z',
    fullSignature: '4TyU9mKaBC123456789abcdefghijklmnopqrstuvwxyzwX2z',
    type: 'NFT_BUY',
    status: 'SUCCESS',
    platform: 'MAGIC_EDEN',
    timestamp: Date.now() - 1000 * 60 * 60 * 24,
    tokenIn: { symbol: 'SOL', amount: 5.5, logo: null },
    tokenOut: { symbol: 'Mad Lads #1234', amount: 1, logo: null },
    valueUsd: 990.00,
    fee: 0.11,
    feeUsd: 19.80,
    from: 'Your Wallet',
    to: 'Magic Eden'
  },
  {
    id: 'tx7',
    signature: '6VwX2nL...yZ3a',
    fullSignature: '6VwX2nLaBC123456789abcdefghijklmnopqrstuvwxyzyZ3a',
    type: 'CLAIM',
    status: 'SUCCESS',
    platform: 'JUPITER',
    timestamp: Date.now() - 1000 * 60 * 60 * 48,
    tokenIn: null,
    tokenOut: { symbol: 'JUP', amount: 500, logo: null },
    valueUsd: 450.00,
    fee: 0.000005,
    feeUsd: 0.0009,
    from: 'Jupiter Airdrop',
    to: 'Your Wallet'
  },
  {
    id: 'tx8',
    signature: '1AbC4dE...fG5h',
    fullSignature: '1AbC4dEaBC123456789abcdefghijklmnopqrstuvwxyzfG5h',
    type: 'SEND',
    status: 'SUCCESS',
    platform: 'PHANTOM',
    timestamp: Date.now() - 1000 * 60 * 60 * 72,
    tokenIn: { symbol: 'SOL', amount: 1.5, logo: null },
    tokenOut: null,
    valueUsd: 270.00,
    fee: 0.000005,
    feeUsd: 0.0009,
    from: 'Your Wallet',
    to: '9xPq...kM7n'
  },
  {
    id: 'tx9',
    signature: '7IjK8lM...nO9p',
    fullSignature: '7IjK8lMaBC123456789abcdefghijklmnopqrstuvwxyznO9p',
    type: 'UNSTAKE',
    status: 'PENDING',
    platform: 'MARINADE',
    timestamp: Date.now() - 1000 * 60 * 10,
    tokenIn: { symbol: 'mSOL', amount: 5, logo: null },
    tokenOut: { symbol: 'SOL', amount: 5.07, logo: null },
    valueUsd: 912.60,
    fee: 0.00001,
    feeUsd: 0.0018,
    from: 'Marinade Finance',
    to: 'Your Wallet',
    pendingUntil: Date.now() + 1000 * 60 * 60 * 24 * 2
  },
  {
    id: 'tx10',
    signature: '2QrS3tU...vW4x',
    fullSignature: '2QrS3tUaBC123456789abcdefghijklmnopqrstuvwxyzvW4x',
    type: 'SWAP',
    status: 'SUCCESS',
    platform: 'ORCA',
    timestamp: Date.now() - 1000 * 60 * 60 * 96,
    tokenIn: { symbol: 'USDC', amount: 200, logo: null },
    tokenOut: { symbol: 'RAY', amount: 50, logo: null },
    valueUsd: 200.00,
    fee: 0.000005,
    feeUsd: 0.0009,
    from: 'Your Wallet',
    to: 'Orca Whirlpool'
  }
]

// Format helpers
const formatAddress = (address) => {
  if (!address || address === 'Your Wallet') return address
  if (address.length <= 15) return address
  return `${address.slice(0, 6)}...${address.slice(-4)}`
}

const formatTime = (timestamp) => {
  const now = Date.now()
  const diff = now - timestamp

  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`

  return new Date(timestamp).toLocaleDateString()
}

const formatFullDate = (timestamp) => {
  return new Date(timestamp).toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const formatNumber = (num) => {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(2)}B`
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(2)}K`
  if (num >= 1) return num.toFixed(2)
  if (num >= 0.0001) return num.toFixed(4)
  return num.toFixed(8)
}

// Transaction type icon component
const TxTypeIcon = ({ type }) => {
  const txType = TX_TYPES[type] || TX_TYPES.SWAP
  const IconComponent = txType.icon

  return (
    <div className={`p-2 rounded-lg ${txType.bg}`}>
      <IconComponent size={18} className={txType.color} />
    </div>
  )
}

// Status badge
const StatusBadge = ({ status }) => {
  const statusInfo = TX_STATUS[status] || TX_STATUS.SUCCESS

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusInfo.bg} ${statusInfo.color}`}>
      {statusInfo.label}
    </span>
  )
}

// Platform badge
const PlatformBadge = ({ platform }) => {
  const platformInfo = PLATFORMS[platform] || PLATFORMS.NATIVE

  return (
    <span className={`text-xs ${platformInfo.color}`}>
      {platformInfo.name}
    </span>
  )
}

// Copy button with feedback
const CopyButton = ({ text, small = false }) => {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }

  return (
    <button
      onClick={handleCopy}
      className={`${small ? 'p-1' : 'p-1.5'} hover:bg-white/5 rounded transition-colors`}
      title="Copy"
    >
      {copied ? (
        <Check size={small ? 12 : 14} className="text-green-400" />
      ) : (
        <Copy size={small ? 12 : 14} className="text-slate-400" />
      )}
    </button>
  )
}

// Transaction row component
const TransactionRow = ({ tx, onClick, isExpanded }) => {
  const txType = TX_TYPES[tx.type] || TX_TYPES.SWAP

  return (
    <div
      className={`p-4 hover:bg-white/5 cursor-pointer transition-colors border-b border-white/5 ${isExpanded ? 'bg-white/5' : ''}`}
      onClick={() => onClick(tx.id)}
    >
      <div className="flex items-center gap-4">
        {/* Type icon */}
        <TxTypeIcon type={tx.type} />

        {/* Main info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-medium text-white">{txType.label}</span>
            <StatusBadge status={tx.status} />
            <PlatformBadge platform={tx.platform} />
          </div>

          <div className="flex items-center gap-2 text-sm text-slate-400">
            <span className="font-mono">{tx.signature}</span>
            <CopyButton text={tx.fullSignature} small />
          </div>
        </div>

        {/* Token flow */}
        <div className="text-right min-w-[200px]">
          {tx.tokenIn && (
            <div className="flex items-center justify-end gap-1 text-sm">
              <span className="text-red-400">-{formatNumber(tx.tokenIn.amount)}</span>
              <span className="text-slate-400">{tx.tokenIn.symbol}</span>
            </div>
          )}
          {tx.tokenOut && (
            <div className="flex items-center justify-end gap-1 text-sm">
              <span className="text-green-400">+{formatNumber(tx.tokenOut.amount)}</span>
              <span className="text-slate-400">{tx.tokenOut.symbol}</span>
            </div>
          )}
        </div>

        {/* Value and time */}
        <div className="text-right min-w-[100px]">
          <div className="text-white font-medium">${formatNumber(tx.valueUsd)}</div>
          <div className="text-xs text-slate-400">{formatTime(tx.timestamp)}</div>
        </div>

        {/* Expand indicator */}
        <div className="text-slate-400">
          {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </div>
      </div>

      {/* Expanded details */}
      {isExpanded && (
        <div className="mt-4 pt-4 border-t border-white/5 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-slate-500 mb-1">From</div>
            <div className="text-sm text-slate-300 flex items-center gap-1">
              {formatAddress(tx.from)}
              {tx.from !== 'Your Wallet' && <CopyButton text={tx.from} small />}
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-500 mb-1">To</div>
            <div className="text-sm text-slate-300 flex items-center gap-1">
              {formatAddress(tx.to)}
              {tx.to !== 'Your Wallet' && <CopyButton text={tx.to} small />}
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-500 mb-1">Network Fee</div>
            <div className="text-sm text-slate-300">
              {tx.fee} SOL (${tx.feeUsd.toFixed(4)})
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-500 mb-1">Time</div>
            <div className="text-sm text-slate-300">{formatFullDate(tx.timestamp)}</div>
          </div>

          {tx.slippage !== undefined && (
            <div>
              <div className="text-xs text-slate-500 mb-1">Slippage</div>
              <div className="text-sm text-slate-300">{tx.slippage}%</div>
            </div>
          )}

          {tx.priceImpact !== undefined && (
            <div>
              <div className="text-xs text-slate-500 mb-1">Price Impact</div>
              <div className="text-sm text-slate-300">{tx.priceImpact}%</div>
            </div>
          )}

          {tx.failReason && (
            <div className="col-span-2">
              <div className="text-xs text-slate-500 mb-1">Failure Reason</div>
              <div className="text-sm text-red-400">{tx.failReason}</div>
            </div>
          )}

          {tx.pendingUntil && (
            <div className="col-span-2">
              <div className="text-xs text-slate-500 mb-1">Estimated Completion</div>
              <div className="text-sm text-yellow-400">{formatFullDate(tx.pendingUntil)}</div>
            </div>
          )}

          {/* Explorer link */}
          <div className="col-span-2 md:col-span-4 pt-2">
            <a
              href={`https://solscan.io/tx/${tx.fullSignature}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-sm text-blue-400 hover:text-blue-300"
              onClick={(e) => e.stopPropagation()}
            >
              View on Solscan
              <ExternalLink size={14} />
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

// Filter panel
const FilterPanel = ({ filters, setFilters, onClose }) => {
  const [localFilters, setLocalFilters] = useState(filters)

  const handleApply = () => {
    setFilters(localFilters)
    onClose()
  }

  const handleReset = () => {
    const resetFilters = {
      types: [],
      statuses: [],
      platforms: [],
      dateFrom: '',
      dateTo: '',
      minValue: '',
      maxValue: ''
    }
    setLocalFilters(resetFilters)
    setFilters(resetFilters)
    onClose()
  }

  const toggleType = (type) => {
    setLocalFilters(prev => ({
      ...prev,
      types: prev.types.includes(type)
        ? prev.types.filter(t => t !== type)
        : [...prev.types, type]
    }))
  }

  const toggleStatus = (status) => {
    setLocalFilters(prev => ({
      ...prev,
      statuses: prev.statuses.includes(status)
        ? prev.statuses.filter(s => s !== status)
        : [...prev.statuses, status]
    }))
  }

  const togglePlatform = (platform) => {
    setLocalFilters(prev => ({
      ...prev,
      platforms: prev.platforms.includes(platform)
        ? prev.platforms.filter(p => p !== platform)
        : [...prev.platforms, platform]
    }))
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#0d1117] rounded-xl border border-white/10 w-full max-w-lg max-h-[90vh] overflow-hidden">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Filter Transactions</h3>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded">
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        <div className="p-4 space-y-6 max-h-[60vh] overflow-y-auto">
          {/* Transaction types */}
          <div>
            <div className="text-sm font-medium text-slate-300 mb-3">Transaction Type</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(TX_TYPES).map(([key, value]) => (
                <button
                  key={key}
                  onClick={() => toggleType(key)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    localFilters.types.includes(key)
                      ? `${value.bg} ${value.color} border border-current`
                      : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  {value.label}
                </button>
              ))}
            </div>
          </div>

          {/* Status */}
          <div>
            <div className="text-sm font-medium text-slate-300 mb-3">Status</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(TX_STATUS).map(([key, value]) => (
                <button
                  key={key}
                  onClick={() => toggleStatus(key)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    localFilters.statuses.includes(key)
                      ? `${value.bg} ${value.color} border border-current`
                      : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  {value.label}
                </button>
              ))}
            </div>
          </div>

          {/* Platforms */}
          <div>
            <div className="text-sm font-medium text-slate-300 mb-3">Platform</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(PLATFORMS).map(([key, value]) => (
                <button
                  key={key}
                  onClick={() => togglePlatform(key)}
                  className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                    localFilters.platforms.includes(key)
                      ? 'bg-blue-400/20 text-blue-400 border border-blue-400'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  {value.name}
                </button>
              ))}
            </div>
          </div>

          {/* Date range */}
          <div>
            <div className="text-sm font-medium text-slate-300 mb-3">Date Range</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">From</label>
                <input
                  type="date"
                  value={localFilters.dateFrom}
                  onChange={(e) => setLocalFilters(prev => ({ ...prev, dateFrom: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">To</label>
                <input
                  type="date"
                  value={localFilters.dateTo}
                  onChange={(e) => setLocalFilters(prev => ({ ...prev, dateTo: e.target.value }))}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
            </div>
          </div>

          {/* Value range */}
          <div>
            <div className="text-sm font-medium text-slate-300 mb-3">Value Range (USD)</div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-500 mb-1 block">Min</label>
                <input
                  type="number"
                  value={localFilters.minValue}
                  onChange={(e) => setLocalFilters(prev => ({ ...prev, minValue: e.target.value }))}
                  placeholder="0"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-slate-500 mb-1 block">Max</label>
                <input
                  type="number"
                  value={localFilters.maxValue}
                  onChange={(e) => setLocalFilters(prev => ({ ...prev, maxValue: e.target.value }))}
                  placeholder="999999"
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
                />
              </div>
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-white/10 flex gap-3">
          <button
            onClick={handleReset}
            className="flex-1 py-2 border border-white/20 rounded-lg text-slate-300 hover:bg-white/5 transition-colors"
          >
            Reset
          </button>
          <button
            onClick={handleApply}
            className="flex-1 py-2 bg-blue-500 rounded-lg text-white font-medium hover:bg-blue-600 transition-colors"
          >
            Apply Filters
          </button>
        </div>
      </div>
    </div>
  )
}

// Stats summary
const StatsSummary = ({ transactions }) => {
  const stats = useMemo(() => {
    const totalValue = transactions.reduce((sum, tx) => sum + tx.valueUsd, 0)
    const totalFees = transactions.reduce((sum, tx) => sum + tx.feeUsd, 0)
    const swapCount = transactions.filter(tx => tx.type === 'SWAP').length
    const successRate = transactions.length > 0
      ? (transactions.filter(tx => tx.status === 'SUCCESS').length / transactions.length) * 100
      : 0

    return { totalValue, totalFees, swapCount, successRate, count: transactions.length }
  }, [transactions])

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-4 bg-white/5 rounded-xl">
      <div>
        <div className="text-xs text-slate-500 mb-1">Total Transactions</div>
        <div className="text-xl font-bold text-white">{stats.count}</div>
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">Total Value</div>
        <div className="text-xl font-bold text-white">${formatNumber(stats.totalValue)}</div>
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">Total Fees</div>
        <div className="text-xl font-bold text-red-400">${stats.totalFees.toFixed(4)}</div>
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">Swap Count</div>
        <div className="text-xl font-bold text-blue-400">{stats.swapCount}</div>
      </div>
      <div>
        <div className="text-xs text-slate-500 mb-1">Success Rate</div>
        <div className="text-xl font-bold text-green-400">{stats.successRate.toFixed(1)}%</div>
      </div>
    </div>
  )
}

// Export modal
const ExportModal = ({ transactions, onClose }) => {
  const [format, setFormat] = useState('csv')
  const [dateRange, setDateRange] = useState('all')

  const handleExport = () => {
    let data = transactions

    // Filter by date if needed
    if (dateRange !== 'all') {
      const now = Date.now()
      const ranges = {
        '7d': 7 * 24 * 60 * 60 * 1000,
        '30d': 30 * 24 * 60 * 60 * 1000,
        '90d': 90 * 24 * 60 * 60 * 1000
      }
      data = transactions.filter(tx => now - tx.timestamp <= ranges[dateRange])
    }

    if (format === 'csv') {
      // Generate CSV
      const headers = ['Signature', 'Type', 'Status', 'Platform', 'Date', 'Token In', 'Amount In', 'Token Out', 'Amount Out', 'Value USD', 'Fee USD']
      const rows = data.map(tx => [
        tx.fullSignature,
        tx.type,
        tx.status,
        tx.platform,
        new Date(tx.timestamp).toISOString(),
        tx.tokenIn?.symbol || '',
        tx.tokenIn?.amount || '',
        tx.tokenOut?.symbol || '',
        tx.tokenOut?.amount || '',
        tx.valueUsd,
        tx.feeUsd
      ])

      const csv = [headers, ...rows].map(row => row.join(',')).join('\n')
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transactions_${new Date().toISOString().split('T')[0]}.csv`
      a.click()
    } else {
      // Generate JSON
      const json = JSON.stringify(data, null, 2)
      const blob = new Blob([json], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transactions_${new Date().toISOString().split('T')[0]}.json`
      a.click()
    }

    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#0d1117] rounded-xl border border-white/10 w-full max-w-md">
        <div className="p-4 border-b border-white/10 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Export Transactions</h3>
          <button onClick={onClose} className="p-1 hover:bg-white/10 rounded">
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          <div>
            <div className="text-sm font-medium text-slate-300 mb-2">Format</div>
            <div className="flex gap-2">
              <button
                onClick={() => setFormat('csv')}
                className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                  format === 'csv'
                    ? 'bg-blue-500 text-white'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10'
                }`}
              >
                CSV
              </button>
              <button
                onClick={() => setFormat('json')}
                className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                  format === 'json'
                    ? 'bg-blue-500 text-white'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10'
                }`}
              >
                JSON
              </button>
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-slate-300 mb-2">Date Range</div>
            <div className="flex gap-2">
              {[
                { value: 'all', label: 'All' },
                { value: '7d', label: '7 Days' },
                { value: '30d', label: '30 Days' },
                { value: '90d', label: '90 Days' }
              ].map(option => (
                <button
                  key={option.value}
                  onClick={() => setDateRange(option.value)}
                  className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                    dateRange === option.value
                      ? 'bg-blue-500 text-white'
                      : 'bg-white/5 text-slate-400 hover:bg-white/10'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          <div className="text-sm text-slate-500">
            {transactions.length} transactions will be exported
          </div>
        </div>

        <div className="p-4 border-t border-white/10">
          <button
            onClick={handleExport}
            className="w-full py-2 bg-green-500 rounded-lg text-white font-medium hover:bg-green-600 transition-colors flex items-center justify-center gap-2"
          >
            <Download size={18} />
            Export
          </button>
        </div>
      </div>
    </div>
  )
}

// Main TransactionExplorer component
export const TransactionExplorer = () => {
  const [transactions] = useState(mockTransactions)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedTx, setExpandedTx] = useState(null)
  const [showFilters, setShowFilters] = useState(false)
  const [showExport, setShowExport] = useState(false)
  const [sortBy, setSortBy] = useState('date')
  const [sortOrder, setSortOrder] = useState('desc')
  const [filters, setFilters] = useState({
    types: [],
    statuses: [],
    platforms: [],
    dateFrom: '',
    dateTo: '',
    minValue: '',
    maxValue: ''
  })

  // Filter and sort transactions
  const filteredTransactions = useMemo(() => {
    let result = [...transactions]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(tx =>
        tx.signature.toLowerCase().includes(query) ||
        tx.fullSignature.toLowerCase().includes(query) ||
        tx.tokenIn?.symbol.toLowerCase().includes(query) ||
        tx.tokenOut?.symbol.toLowerCase().includes(query) ||
        TX_TYPES[tx.type]?.label.toLowerCase().includes(query) ||
        tx.from.toLowerCase().includes(query) ||
        tx.to.toLowerCase().includes(query)
      )
    }

    // Type filter
    if (filters.types.length > 0) {
      result = result.filter(tx => filters.types.includes(tx.type))
    }

    // Status filter
    if (filters.statuses.length > 0) {
      result = result.filter(tx => filters.statuses.includes(tx.status))
    }

    // Platform filter
    if (filters.platforms.length > 0) {
      result = result.filter(tx => filters.platforms.includes(tx.platform))
    }

    // Date filter
    if (filters.dateFrom) {
      const fromDate = new Date(filters.dateFrom).getTime()
      result = result.filter(tx => tx.timestamp >= fromDate)
    }
    if (filters.dateTo) {
      const toDate = new Date(filters.dateTo).getTime() + 86400000
      result = result.filter(tx => tx.timestamp <= toDate)
    }

    // Value filter
    if (filters.minValue) {
      result = result.filter(tx => tx.valueUsd >= parseFloat(filters.minValue))
    }
    if (filters.maxValue) {
      result = result.filter(tx => tx.valueUsd <= parseFloat(filters.maxValue))
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'date':
          comparison = a.timestamp - b.timestamp
          break
        case 'value':
          comparison = a.valueUsd - b.valueUsd
          break
        case 'type':
          comparison = a.type.localeCompare(b.type)
          break
        default:
          comparison = a.timestamp - b.timestamp
      }
      return sortOrder === 'asc' ? comparison : -comparison
    })

    return result
  }, [transactions, searchQuery, filters, sortBy, sortOrder])

  const handleTxClick = useCallback((txId) => {
    setExpandedTx(expandedTx === txId ? null : txId)
  }, [expandedTx])

  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters.types.length > 0) count++
    if (filters.statuses.length > 0) count++
    if (filters.platforms.length > 0) count++
    if (filters.dateFrom || filters.dateTo) count++
    if (filters.minValue || filters.maxValue) count++
    return count
  }, [filters])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1">Transaction History</h1>
            <p className="text-slate-400">Explore and analyze your on-chain activity</p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowExport(true)}
              className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
            >
              <Download size={18} />
              <span>Export</span>
            </button>
            <button className="p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors">
              <RefreshCw size={18} />
            </button>
          </div>
        </div>

        {/* Stats */}
        <StatsSummary transactions={filteredTransactions} />

        {/* Search and filters */}
        <div className="flex flex-col md:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by signature, token, address..."
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Filter button */}
          <button
            onClick={() => setShowFilters(true)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg transition-colors ${
              activeFilterCount > 0
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500'
                : 'bg-white/5 hover:bg-white/10 border border-white/10'
            }`}
          >
            <Filter size={18} />
            <span>Filters</span>
            {activeFilterCount > 0 && (
              <span className="bg-blue-500 text-white text-xs px-1.5 py-0.5 rounded-full">
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* Sort dropdown */}
          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-white appearance-none cursor-pointer"
            >
              <option value="date">Sort by Date</option>
              <option value="value">Sort by Value</option>
              <option value="type">Sort by Type</option>
            </select>

            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="p-2.5 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg transition-colors"
            >
              {sortOrder === 'asc' ? (
                <TrendingUp size={18} className="text-slate-400" />
              ) : (
                <TrendingDown size={18} className="text-slate-400" />
              )}
            </button>
          </div>
        </div>

        {/* Transaction list */}
        <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
          {filteredTransactions.length === 0 ? (
            <div className="p-12 text-center">
              <FileText size={48} className="mx-auto mb-4 text-slate-600" />
              <div className="text-lg text-slate-400 mb-2">No transactions found</div>
              <div className="text-sm text-slate-500">
                {searchQuery || activeFilterCount > 0
                  ? 'Try adjusting your search or filters'
                  : 'Your transaction history will appear here'
                }
              </div>
            </div>
          ) : (
            <div>
              {/* List header */}
              <div className="px-4 py-3 bg-white/5 border-b border-white/10 text-xs font-medium text-slate-500 flex items-center gap-4">
                <div className="w-10"></div>
                <div className="flex-1">Transaction</div>
                <div className="min-w-[200px] text-right">Token Flow</div>
                <div className="min-w-[100px] text-right">Value</div>
                <div className="w-5"></div>
              </div>

              {/* Transaction rows */}
              {filteredTransactions.map(tx => (
                <TransactionRow
                  key={tx.id}
                  tx={tx}
                  onClick={handleTxClick}
                  isExpanded={expandedTx === tx.id}
                />
              ))}
            </div>
          )}
        </div>

        {/* Results count */}
        {filteredTransactions.length > 0 && (
          <div className="text-sm text-slate-500 text-center">
            Showing {filteredTransactions.length} of {transactions.length} transactions
          </div>
        )}
      </div>

      {/* Filter modal */}
      {showFilters && (
        <FilterPanel
          filters={filters}
          setFilters={setFilters}
          onClose={() => setShowFilters(false)}
        />
      )}

      {/* Export modal */}
      {showExport && (
        <ExportModal
          transactions={filteredTransactions}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  )
}

export default TransactionExplorer
