import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Brain,
  Building,
  Eye,
  RefreshCw,
  Search,
  Shield,
  Star,
  Target,
  Users,
  Wallet,
} from 'lucide-react'

const CATEGORY_META = {
  VC: { label: 'VC', icon: Building, color: 'text-purple-400' },
  WHALE: { label: 'Whale', icon: Wallet, color: 'text-blue-400' },
  DEV: { label: 'Dev', icon: Shield, color: 'text-green-400' },
  TRADER: { label: 'Trader', icon: Target, color: 'text-orange-400' },
  INSIDER: { label: 'Insider', icon: Eye, color: 'text-red-400' },
  MM: { label: 'MM', icon: Brain, color: 'text-cyan-400' },
}

function formatCompact(value) {
  if (!Number.isFinite(value)) return '--'
  if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`
  return `$${value.toFixed(0)}`
}

function formatAddress(address) {
  if (!address || address.length < 12) return address || '--'
  return `${address.slice(0, 6)}...${address.slice(-4)}`
}

function formatTradeTime(unixTs) {
  if (!unixTs) return '--'
  const diffSec = Math.max(0, Math.floor(Date.now() / 1000 - unixTs))
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return `${Math.floor(diffSec / 86400)}d ago`
}

export const SmartMoneyTracker = () => {
  const [wallets, setWallets] = useState([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('ALL')
  const [sortBy, setSortBy] = useState('win_rate')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [selectedWalletId, setSelectedWalletId] = useState(null)

  const fetchData = useCallback(async () => {
    setRefreshing(true)
    try {
      const response = await fetch('/api/intel/smart-money?limit=20')
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const payload = await response.json()
      setWallets(Array.isArray(payload.wallets) ? payload.wallets : [])
      setError(null)
    } catch (err) {
      setError(err?.message || 'Failed to load smart money feed')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
    const timer = setInterval(fetchData, 8000)
    return () => clearInterval(timer)
  }, [fetchData])

  const filteredWallets = useMemo(() => {
    let result = [...wallets]
    if (query.trim()) {
      const term = query.toLowerCase()
      result = result.filter(
        (wallet) =>
          (wallet.label || '').toLowerCase().includes(term) ||
          (wallet.address || '').toLowerCase().includes(term),
      )
    }
    if (category !== 'ALL') {
      result = result.filter((wallet) => wallet.category === category)
    }
    result.sort((left, right) => {
      const ls = left.stats || {}
      const rs = right.stats || {}
      if (sortBy === 'pnl') return (rs.total_pnl_usd || 0) - (ls.total_pnl_usd || 0)
      if (sortBy === 'trades') return (rs.total_trades || 0) - (ls.total_trades || 0)
      if (sortBy === 'roi') return (rs.avg_roi || 0) - (ls.avg_roi || 0)
      return (rs.win_rate || 0) - (ls.win_rate || 0)
    })
    return result
  }, [wallets, query, category, sortBy])

  const selectedWallet = useMemo(
    () => filteredWallets.find((wallet) => wallet.id === selectedWalletId) || null,
    [filteredWallets, selectedWalletId],
  )

  const summary = useMemo(() => {
    const followed = wallets.filter((wallet) => wallet.is_following).length
    const avgWinRate = wallets.length
      ? wallets.reduce((sum, wallet) => sum + (wallet.stats?.win_rate || 0), 0) / wallets.length
      : 0
    const totalPnl = wallets.reduce((sum, wallet) => sum + (wallet.stats?.total_pnl_usd || 0), 0)
    return { total: wallets.length, followed, avgWinRate, totalPnl }
  }, [wallets])

  const categories = useMemo(() => ['ALL', ...Object.keys(CATEGORY_META)], [])

  return (
    <div className="min-h-screen bg-[#0b1119] text-white p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Brain className="w-6 h-6 text-blue-400" />
              Smart Money Tracker
            </h1>
            <p className="text-sm text-slate-400">Live backend feed for wallet flow and trade conviction.</p>
          </div>
          <button
            onClick={fetchData}
            className={`p-2 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 ${refreshing ? 'animate-spin' : ''}`}
            title="Refresh"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </header>

        {error ? (
          <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-yellow-200 text-sm">
            {error}
          </div>
        ) : null}

        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SummaryCard icon={Users} label="Wallets" value={`${summary.total}`} />
          <SummaryCard icon={Star} label="Following" value={`${summary.followed}`} />
          <SummaryCard icon={Target} label="Avg Win Rate" value={`${summary.avgWinRate.toFixed(1)}%`} />
          <SummaryCard icon={Wallet} label="Total PnL" value={formatCompact(summary.totalPnl)} />
        </section>

        <section className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[260px] max-w-xl">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search wallets or addresses"
              className="w-full bg-white/5 border border-white/10 rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-blue-500/50"
            />
          </div>
          <select
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            {categories.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            <option value="win_rate">Win Rate</option>
            <option value="pnl">Total PnL</option>
            <option value="roi">Avg ROI</option>
            <option value="trades">Trade Count</option>
          </select>
        </section>

        {loading ? (
          <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-10 text-center text-slate-400">
            Loading smart money feed...
          </div>
        ) : (
          <section className="grid lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-3">
              {filteredWallets.map((wallet) => (
                <WalletRow
                  key={wallet.id}
                  wallet={wallet}
                  selected={wallet.id === selectedWalletId}
                  onSelect={() => setSelectedWalletId(wallet.id)}
                />
              ))}
              {filteredWallets.length === 0 ? (
                <div className="rounded-lg border border-white/10 bg-white/5 px-4 py-8 text-center text-slate-400">
                  No wallets match current filters.
                </div>
              ) : null}
            </div>
            <div>
              <WalletDetail wallet={selectedWallet} />
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

function SummaryCard({ icon: Icon, label, value }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-4">
      <div className="text-slate-500 text-xs flex items-center gap-2">
        <Icon className="w-4 h-4" />
        {label}
      </div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </div>
  )
}

function WalletRow({ wallet, selected, onSelect }) {
  const stats = wallet.stats || {}
  const category = CATEGORY_META[wallet.category] || { label: wallet.category || 'Unknown', color: 'text-slate-400', icon: Users }
  const CategoryIcon = category.icon
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-lg border p-4 transition-colors ${
        selected ? 'border-blue-500 bg-blue-500/10' : 'border-white/10 bg-white/5 hover:bg-white/10'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <CategoryIcon className={`w-4 h-4 ${category.color}`} />
            <span className="font-medium">{wallet.label || 'Wallet'}</span>
            {wallet.is_verified ? <Shield className="w-4 h-4 text-blue-400" /> : null}
          </div>
          <div className="text-xs text-slate-500 mt-1 font-mono">{formatAddress(wallet.address)}</div>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded bg-white/10 ${category.color}`}>{category.label}</span>
      </div>

      <div className="grid grid-cols-4 gap-3 mt-3 text-xs">
        <Metric label="Win" value={`${Number(stats.win_rate || 0).toFixed(1)}%`} className="text-green-400" />
        <Metric label="ROI" value={`${Number(stats.avg_roi || 0).toFixed(1)}%`} className="text-blue-400" />
        <Metric label="Trades" value={`${Math.round(stats.total_trades || 0)}`} />
        <Metric label="PnL" value={formatCompact(Number(stats.total_pnl_usd || 0))} className="text-purple-400" />
      </div>
    </button>
  )
}

function WalletDetail({ wallet }) {
  if (!wallet) {
    return (
      <div className="rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-slate-400">
        Select a wallet to inspect recent flow.
      </div>
    )
  }
  const trades = Array.isArray(wallet.recent_trades) ? wallet.recent_trades : []
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-4">
      <h3 className="font-semibold mb-2">{wallet.label}</h3>
      <p className="text-xs text-slate-500 font-mono mb-4">{wallet.address}</p>
      <div className="space-y-2">
        {trades.map((trade, idx) => (
          <div key={`${wallet.id}-trade-${idx}`} className="rounded border border-white/10 bg-white/5 p-2 text-xs">
            <div className="flex items-center justify-between">
              <span className={trade.type === 'SELL' ? 'text-red-400' : trade.type === 'BUY' ? 'text-green-400' : 'text-blue-400'}>
                {trade.type}
              </span>
              <span className="text-slate-500">{formatTradeTime(trade.timestamp)}</span>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <span>{trade.token}</span>
              <span className="font-medium">{formatCompact(Number(trade.notional_usd || 0))}</span>
            </div>
          </div>
        ))}
        {trades.length === 0 ? <div className="text-xs text-slate-500">No recent trades</div> : null}
      </div>
    </div>
  )
}

function Metric({ label, value, className = 'text-white' }) {
  return (
    <div>
      <div className="text-slate-500">{label}</div>
      <div className={`font-medium ${className}`}>{value}</div>
    </div>
  )
}

export default SmartMoneyTracker
