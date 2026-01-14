import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Rocket,
  TrendingUp,
  TrendingDown,
  Clock,
  DollarSign,
  AlertTriangle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Zap,
  RefreshCw,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Copy,
  Check,
  Eye,
  EyeOff,
  Bell,
  BellOff,
  Twitter,
  Globe,
  FileText,
  Users,
  Lock,
  Unlock,
  Activity,
  BarChart3,
  AlertCircle,
  CheckCircle,
  XCircle,
  Star,
  StarOff,
  Flame,
  Target,
  Droplets,
  ArrowUpRight,
  ArrowDownRight,
  Timer,
  Play,
  Pause,
  X
} from 'lucide-react'

// Launch status types
const LAUNCH_STATUS = {
  UPCOMING: { label: 'Upcoming', color: 'blue', icon: Timer },
  LIVE: { label: 'Live', color: 'green', icon: Play },
  ENDED: { label: 'Ended', color: 'gray', icon: Pause },
  RUGGED: { label: 'Rugged', color: 'red', icon: AlertTriangle },
}

// Launch platforms
const PLATFORMS = {
  PUMP_FUN: { name: 'Pump.fun', color: '#00ff00' },
  RAYDIUM: { name: 'Raydium', color: '#58c7e3' },
  ORCA: { name: 'Orca', color: '#ff6b00' },
  METEORA: { name: 'Meteora', color: '#8b5cf6' },
  JUPITER_LFG: { name: 'Jupiter LFG', color: '#c7f284' },
}

// Risk indicators
const RISK_FLAGS = {
  NO_SOCIALS: { label: 'No Socials', severity: 'warning' },
  NO_WEBSITE: { label: 'No Website', severity: 'warning' },
  MINT_ENABLED: { label: 'Mint Enabled', severity: 'danger' },
  FREEZE_ENABLED: { label: 'Freeze Enabled', severity: 'danger' },
  LP_NOT_BURNED: { label: 'LP Not Burned', severity: 'warning' },
  LOW_LIQUIDITY: { label: 'Low Liquidity', severity: 'warning' },
  HIGH_TAX: { label: 'High Tax', severity: 'danger' },
  HONEYPOT: { label: 'Honeypot', severity: 'danger' },
  COPY_CAT: { label: 'Copy/Derivative', severity: 'info' },
  DEV_HOLDS_SUPPLY: { label: 'Dev Holds Supply', severity: 'danger' },
  RECENT_DEPLOY: { label: 'Just Deployed', severity: 'info' },
}

// Helper functions
function formatNumber(num, decimals = 2) {
  if (num >= 1000000000) return `${(num / 1000000000).toFixed(decimals)}B`
  if (num >= 1000000) return `${(num / 1000000).toFixed(decimals)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(decimals)}K`
  return num.toFixed(decimals)
}

function formatTimeAgo(timestamp) {
  const seconds = Math.floor((Date.now() - new Date(timestamp)) / 1000)
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

function formatCountdown(timestamp) {
  const seconds = Math.floor((new Date(timestamp) - Date.now()) / 1000)
  if (seconds < 0) return 'Started'
  const hours = Math.floor(seconds / 3600)
  const mins = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60
  if (hours > 0) return `${hours}h ${mins}m`
  if (mins > 0) return `${mins}m ${secs}s`
  return `${secs}s`
}

function formatAddress(address) {
  if (!address) return ''
  return `${address.slice(0, 4)}...${address.slice(-4)}`
}

// Copy Button Component
function CopyButton({ text, className = '' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className={`p-1 hover:bg-gray-700 rounded transition-colors ${className}`}
    >
      {copied ? (
        <Check className="w-3 h-3 text-green-400" />
      ) : (
        <Copy className="w-3 h-3 text-gray-400" />
      )}
    </button>
  )
}

// Risk Score Badge
function RiskScoreBadge({ score }) {
  const getColor = (s) => {
    if (s >= 80) return { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Safe' }
    if (s >= 60) return { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'Caution' }
    if (s >= 40) return { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Risky' }
    return { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Danger' }
  }

  const style = getColor(score)

  return (
    <div className={`px-2 py-1 rounded-md ${style.bg}`}>
      <div className={`text-xs font-medium ${style.text}`}>{score}/100</div>
      <div className="text-xs text-gray-400">{style.label}</div>
    </div>
  )
}

// Risk Flags Display
function RiskFlags({ flags = [] }) {
  if (!flags.length) return null

  return (
    <div className="flex flex-wrap gap-1">
      {flags.map((flag, i) => {
        const flagInfo = RISK_FLAGS[flag] || { label: flag, severity: 'info' }
        const severityColors = {
          danger: 'bg-red-500/10 text-red-400 border-red-500/30',
          warning: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
          info: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
        }
        return (
          <span
            key={i}
            className={`px-1.5 py-0.5 text-xs rounded border ${severityColors[flagInfo.severity]}`}
          >
            {flagInfo.label}
          </span>
        )
      })}
    </div>
  )
}

// Token Launch Card
function LaunchCard({ token, onWatch, isWatched, onQuickBuy }) {
  const [expanded, setExpanded] = useState(false)
  const status = LAUNCH_STATUS[token.status] || LAUNCH_STATUS.LIVE
  const StatusIcon = status.icon
  const platform = PLATFORMS[token.platform] || { name: token.platform, color: '#888' }

  const priceChange = token.priceChange24h || 0

  return (
    <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden hover:border-gray-600 transition-colors">
      {/* Header */}
      <div className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            {token.image ? (
              <img src={token.image} alt={token.symbol} className="w-10 h-10 rounded-lg" />
            ) : (
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center font-bold">
                {token.symbol?.[0] || '?'}
              </div>
            )}
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold">{token.name}</h3>
                <span className="text-gray-400 text-sm">${token.symbol}</span>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span
                  className="px-1.5 py-0.5 rounded text-xs"
                  style={{ backgroundColor: `${platform.color}20`, color: platform.color }}
                >
                  {platform.name}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-xs flex items-center gap-1`}
                  style={{ backgroundColor: `${status.color === 'green' ? '#22c55e' : status.color === 'blue' ? '#3b82f6' : status.color === 'red' ? '#ef4444' : '#6b7280'}20` }}
                >
                  <StatusIcon className="w-3 h-3" style={{ color: status.color === 'green' ? '#22c55e' : status.color === 'blue' ? '#3b82f6' : status.color === 'red' ? '#ef4444' : '#6b7280' }} />
                  {status.label}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <RiskScoreBadge score={token.riskScore || 50} />
            <button
              onClick={() => onWatch?.(token.mint)}
              className={`p-1.5 rounded ${isWatched ? 'text-yellow-400' : 'text-gray-400 hover:text-yellow-400'}`}
            >
              {isWatched ? <Star className="w-4 h-4 fill-yellow-400" /> : <StarOff className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-3 mb-3">
          <div>
            <div className="text-xs text-gray-500">Price</div>
            <div className="font-medium">${token.price?.toFixed(8) || '0.00'}</div>
            <div className={`text-xs flex items-center gap-0.5 ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {priceChange >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {Math.abs(priceChange).toFixed(1)}%
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Market Cap</div>
            <div className="font-medium">${formatNumber(token.marketCap || 0)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Liquidity</div>
            <div className="font-medium">${formatNumber(token.liquidity || 0)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Volume 24h</div>
            <div className="font-medium">${formatNumber(token.volume24h || 0)}</div>
          </div>
        </div>

        {/* Launch Time */}
        <div className="flex items-center justify-between mb-3 text-sm">
          <div className="flex items-center gap-2 text-gray-400">
            <Clock className="w-4 h-4" />
            {token.status === 'UPCOMING' ? (
              <span>Launches in {formatCountdown(token.launchTime)}</span>
            ) : (
              <span>Launched {formatTimeAgo(token.launchTime)}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-gray-400">{token.holders || 0} holders</span>
            <span className="text-gray-600">|</span>
            <span className="text-gray-400">{token.txCount || 0} txs</span>
          </div>
        </div>

        {/* Risk Flags */}
        {token.riskFlags && token.riskFlags.length > 0 && (
          <div className="mb-3">
            <RiskFlags flags={token.riskFlags} />
          </div>
        )}

        {/* Social Links */}
        <div className="flex items-center gap-2 mb-3">
          {token.twitter && (
            <a
              href={token.twitter}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <Twitter className="w-4 h-4 text-blue-400" />
            </a>
          )}
          {token.website && (
            <a
              href={token.website}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <Globe className="w-4 h-4 text-gray-400" />
            </a>
          )}
          {token.telegram && (
            <a
              href={token.telegram}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 bg-gray-700 rounded hover:bg-gray-600"
            >
              <Users className="w-4 h-4 text-blue-400" />
            </a>
          )}
          <div className="flex-1 flex items-center gap-1 ml-auto">
            <code className="text-xs text-gray-400 font-mono">{formatAddress(token.mint)}</code>
            <CopyButton text={token.mint} />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => onQuickBuy?.(token)}
            className="flex-1 py-2 bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-colors flex items-center justify-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Quick Buy
          </button>
          <a
            href={`https://dexscreener.com/solana/${token.mint}`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors flex items-center justify-center gap-2"
          >
            <BarChart3 className="w-4 h-4" />
            Chart
          </a>
          <button
            onClick={() => setExpanded(!expanded)}
            className="px-3 py-2 bg-gray-700 text-gray-400 rounded-lg hover:bg-gray-600 transition-colors"
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t border-gray-700 p-4 bg-gray-900/50">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <div className="text-xs text-gray-500 mb-1">Total Supply</div>
              <div className="font-medium">{formatNumber(token.totalSupply || 0)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Circulating</div>
              <div className="font-medium">{formatNumber(token.circulatingSupply || 0)}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">LP Burned</div>
              <div className={`font-medium ${token.lpBurned ? 'text-green-400' : 'text-red-400'}`}>
                {token.lpBurned ? 'Yes' : 'No'}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Mint Auth</div>
              <div className={`font-medium ${token.mintDisabled ? 'text-green-400' : 'text-red-400'}`}>
                {token.mintDisabled ? 'Disabled' : 'Enabled'}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Freeze Auth</div>
              <div className={`font-medium ${token.freezeDisabled ? 'text-green-400' : 'text-red-400'}`}>
                {token.freezeDisabled ? 'Disabled' : 'Enabled'}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 mb-1">Top 10 Hold %</div>
              <div className={`font-medium ${(token.top10HoldPercent || 0) > 50 ? 'text-red-400' : 'text-green-400'}`}>
                {token.top10HoldPercent || 0}%
              </div>
            </div>
          </div>

          {/* Description */}
          {token.description && (
            <div className="mb-4">
              <div className="text-xs text-gray-500 mb-1">Description</div>
              <p className="text-sm text-gray-300">{token.description}</p>
            </div>
          )}

          {/* External Links */}
          <div className="flex gap-2">
            <a
              href={`https://solscan.io/token/${token.mint}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg flex items-center justify-center gap-1 hover:border-gray-600"
            >
              Solscan <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href={`https://birdeye.so/token/${token.mint}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg flex items-center justify-center gap-1 hover:border-gray-600"
            >
              Birdeye <ExternalLink className="w-3 h-3" />
            </a>
            <a
              href={`https://rugcheck.xyz/tokens/${token.mint}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex-1 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg flex items-center justify-center gap-1 hover:border-gray-600"
            >
              RugCheck <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      )}
    </div>
  )
}

// Stats Summary Component
function ScannerStats({ tokens }) {
  const stats = useMemo(() => {
    const live = tokens.filter(t => t.status === 'LIVE')
    const upcoming = tokens.filter(t => t.status === 'UPCOMING')
    const safe = tokens.filter(t => (t.riskScore || 0) >= 70)
    const totalMcap = live.reduce((sum, t) => sum + (t.marketCap || 0), 0)
    const totalLiquidity = live.reduce((sum, t) => sum + (t.liquidity || 0), 0)

    return {
      total: tokens.length,
      live: live.length,
      upcoming: upcoming.length,
      safe: safe.length,
      totalMcap,
      totalLiquidity,
    }
  }, [tokens])

  return (
    <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total Scanned</div>
        <div className="text-2xl font-bold">{stats.total}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Live Now</div>
        <div className="text-2xl font-bold text-green-400">{stats.live}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Upcoming</div>
        <div className="text-2xl font-bold text-blue-400">{stats.upcoming}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Safe Score 70+</div>
        <div className="text-2xl font-bold text-green-400">{stats.safe}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total MCap</div>
        <div className="text-2xl font-bold">${formatNumber(stats.totalMcap)}</div>
      </div>
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="text-sm text-gray-400 mb-1">Total Liquidity</div>
        <div className="text-2xl font-bold">${formatNumber(stats.totalLiquidity)}</div>
      </div>
    </div>
  )
}

// Quick Buy Modal
function QuickBuyModal({ token, isOpen, onClose, onConfirm }) {
  const [amount, setAmount] = useState('')
  const [slippage, setSlippage] = useState(10)

  if (!isOpen || !token) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-xl p-6 max-w-md w-full border border-gray-700">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <Zap className="w-5 h-5 text-green-400" />
            Quick Buy {token.symbol}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Token Info */}
        <div className="bg-gray-900 rounded-lg p-3 mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {token.image ? (
              <img src={token.image} alt={token.symbol} className="w-8 h-8 rounded" />
            ) : (
              <div className="w-8 h-8 rounded bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center font-bold text-sm">
                {token.symbol?.[0]}
              </div>
            )}
            <div>
              <div className="font-medium">{token.name}</div>
              <div className="text-xs text-gray-400">${token.symbol}</div>
            </div>
          </div>
          <div className="text-right">
            <div className="font-medium">${token.price?.toFixed(8)}</div>
            <RiskScoreBadge score={token.riskScore || 50} />
          </div>
        </div>

        {/* Warning for low risk score */}
        {(token.riskScore || 0) < 60 && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 mb-4 flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-red-400">
              This token has a low safety score. Trade with extreme caution. DYOR.
            </div>
          </div>
        )}

        {/* Amount Input */}
        <div className="mb-4">
          <label className="text-sm text-gray-400 mb-1 block">Amount (SOL)</label>
          <div className="relative">
            <input
              type="number"
              value={amount}
              onChange={e => setAmount(e.target.value)}
              placeholder="0.00"
              className="w-full px-3 py-3 bg-gray-900 border border-gray-700 rounded-lg pr-20"
            />
            <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
              {[0.1, 0.5, 1].map(val => (
                <button
                  key={val}
                  onClick={() => setAmount(String(val))}
                  className="px-2 py-1 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600"
                >
                  {val}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Slippage */}
        <div className="mb-4">
          <label className="text-sm text-gray-400 mb-1 block">Slippage Tolerance</label>
          <div className="flex gap-2">
            {[5, 10, 15, 25, 50].map(s => (
              <button
                key={s}
                onClick={() => setSlippage(s)}
                className={`flex-1 py-2 rounded-lg text-sm ${
                  slippage === s
                    ? 'bg-green-500/20 border-green-500 text-green-400'
                    : 'bg-gray-700 border-gray-600 text-gray-400'
                } border`}
              >
                {s}%
              </button>
            ))}
          </div>
        </div>

        {/* Estimated Output */}
        {amount && (
          <div className="bg-gray-900 rounded-lg p-3 mb-4">
            <div className="text-sm text-gray-400 mb-1">Estimated Output</div>
            <div className="text-xl font-bold">
              {formatNumber((Number(amount) * 200) / (token.price || 1))} {token.symbol}
            </div>
            <div className="text-xs text-gray-500">
              Price impact: ~{((Number(amount) / (token.liquidity || 1)) * 100).toFixed(2)}%
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600"
          >
            Cancel
          </button>
          <button
            onClick={() => { onConfirm?.(token, Number(amount), slippage); onClose() }}
            disabled={!amount || Number(amount) <= 0}
            className="flex-1 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <Zap className="w-4 h-4" />
            Buy Now
          </button>
        </div>
      </div>
    </div>
  )
}

// Main Token Launch Scanner Component
export function TokenLaunchScanner({
  tokens = [],
  onRefresh,
  onWatch,
  onQuickBuy,
  watchlist = [],
  isLoading = false,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedPlatform, setSelectedPlatform] = useState('all')
  const [selectedStatus, setSelectedStatus] = useState('all')
  const [minRiskScore, setMinRiskScore] = useState(0)
  const [sortBy, setSortBy] = useState('time')
  const [sortOrder, setSortOrder] = useState('desc')
  const [showWatchlistOnly, setShowWatchlistOnly] = useState(false)
  const [watchedTokens, setWatchedTokens] = useState(new Set(watchlist))
  const [buyingToken, setBuyingToken] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  // Update watched tokens when watchlist prop changes
  useEffect(() => {
    setWatchedTokens(new Set(watchlist))
  }, [watchlist])

  // Auto-refresh interval
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      onRefresh?.()
    }, 30000) // 30 seconds
    return () => clearInterval(interval)
  }, [autoRefresh, onRefresh])

  // Filter and sort tokens
  const filteredTokens = useMemo(() => {
    let result = [...tokens]

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      result = result.filter(t =>
        t.name?.toLowerCase().includes(query) ||
        t.symbol?.toLowerCase().includes(query) ||
        t.mint?.toLowerCase().includes(query)
      )
    }

    // Platform filter
    if (selectedPlatform !== 'all') {
      result = result.filter(t => t.platform === selectedPlatform)
    }

    // Status filter
    if (selectedStatus !== 'all') {
      result = result.filter(t => t.status === selectedStatus)
    }

    // Risk score filter
    if (minRiskScore > 0) {
      result = result.filter(t => (t.riskScore || 0) >= minRiskScore)
    }

    // Watchlist filter
    if (showWatchlistOnly) {
      result = result.filter(t => watchedTokens.has(t.mint))
    }

    // Sort
    result.sort((a, b) => {
      let comparison = 0
      switch (sortBy) {
        case 'time': comparison = new Date(a.launchTime) - new Date(b.launchTime); break
        case 'mcap': comparison = (a.marketCap || 0) - (b.marketCap || 0); break
        case 'liquidity': comparison = (a.liquidity || 0) - (b.liquidity || 0); break
        case 'risk': comparison = (a.riskScore || 0) - (b.riskScore || 0); break
        case 'volume': comparison = (a.volume24h || 0) - (b.volume24h || 0); break
        default: comparison = 0
      }
      return sortOrder === 'desc' ? -comparison : comparison
    })

    return result
  }, [tokens, searchQuery, selectedPlatform, selectedStatus, minRiskScore, sortBy, sortOrder, showWatchlistOnly, watchedTokens])

  const toggleWatch = useCallback((mint) => {
    setWatchedTokens(prev => {
      const newSet = new Set(prev)
      if (newSet.has(mint)) {
        newSet.delete(mint)
      } else {
        newSet.add(mint)
      }
      onWatch?.(mint, !prev.has(mint))
      return newSet
    })
  }, [onWatch])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-orange-500/20 rounded-lg">
            <Rocket className="w-6 h-6 text-orange-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Token Launch Scanner</h1>
            <p className="text-sm text-gray-400">Discover new token launches on Solana</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`p-2 rounded-lg ${
              autoRefresh ? 'bg-green-500/20 text-green-400' : 'bg-gray-700 text-gray-400'
            }`}
          >
            <RefreshCw className={`w-5 h-5 ${autoRefresh && isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 flex items-center gap-2"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <ScannerStats tokens={tokens} />

      {/* Filters */}
      <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Search by name, symbol, or address..."
              className="w-full pl-10 pr-4 py-2 bg-gray-900 border border-gray-700 rounded-lg"
            />
          </div>

          <select
            value={selectedPlatform}
            onChange={e => setSelectedPlatform(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Platforms</option>
            {Object.entries(PLATFORMS).map(([key, { name }]) => (
              <option key={key} value={key}>{name}</option>
            ))}
          </select>

          <select
            value={selectedStatus}
            onChange={e => setSelectedStatus(e.target.value)}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value="all">All Status</option>
            {Object.entries(LAUNCH_STATUS).map(([key, { label }]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>

          <select
            value={minRiskScore}
            onChange={e => setMinRiskScore(Number(e.target.value))}
            className="px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg"
          >
            <option value={0}>Any Risk Score</option>
            <option value={40}>40+ (Risky)</option>
            <option value={60}>60+ (Caution)</option>
            <option value={80}>80+ (Safe)</option>
          </select>
        </div>

        <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-700">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Sort:</span>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="px-2 py-1 bg-gray-900 border border-gray-700 rounded text-sm"
              >
                <option value="time">Launch Time</option>
                <option value="mcap">Market Cap</option>
                <option value="liquidity">Liquidity</option>
                <option value="volume">Volume</option>
                <option value="risk">Risk Score</option>
              </select>
              <button
                onClick={() => setSortOrder(o => o === 'desc' ? 'asc' : 'desc')}
                className="p-1 bg-gray-700 rounded"
              >
                {sortOrder === 'desc' ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
              </button>
            </div>

            <button
              onClick={() => setShowWatchlistOnly(!showWatchlistOnly)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-sm ${
                showWatchlistOnly ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-700 text-gray-400'
              }`}
            >
              <Star className="w-4 h-4" />
              Watchlist
            </button>
          </div>

          <div className="text-sm text-gray-400">
            {filteredTokens.length} tokens found
          </div>
        </div>
      </div>

      {/* Token Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {filteredTokens.map(token => (
          <LaunchCard
            key={token.mint}
            token={token}
            onWatch={toggleWatch}
            isWatched={watchedTokens.has(token.mint)}
            onQuickBuy={setBuyingToken}
          />
        ))}
      </div>

      {filteredTokens.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <Rocket className="w-12 h-12 mx-auto mb-4 opacity-50" />
          <p>No token launches found</p>
        </div>
      )}

      {/* Quick Buy Modal */}
      <QuickBuyModal
        token={buyingToken}
        isOpen={!!buyingToken}
        onClose={() => setBuyingToken(null)}
        onConfirm={onQuickBuy}
      />
    </div>
  )
}

export default TokenLaunchScanner
