import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, BarChart3, Eye, EyeOff, RefreshCw } from 'lucide-react'

const TOKENS = ['SOL', 'ETH', 'BTC', 'JUP', 'BONK', 'WIF', 'RNDR', 'PYTH']

function formatPrice(value) {
  if (!Number.isFinite(value)) return '--'
  if (value >= 1000) return value.toFixed(2)
  if (value >= 1) return value.toFixed(4)
  return value.toFixed(8)
}

function formatSize(value) {
  if (!Number.isFinite(value)) return '--'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)}K`
  return value.toFixed(2)
}

export function DepthChart() {
  const [symbol, setSymbol] = useState('SOL')
  const [levels, setLevels] = useState(20)
  const [showBook, setShowBook] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [snapshot, setSnapshot] = useState(null)
  const [error, setError] = useState(null)

  const fetchDepth = useCallback(async () => {
    setIsRefreshing(true)
    try {
      const response = await fetch(`/api/market/depth?symbol=${symbol}&levels=${levels}`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const payload = await response.json()
      setSnapshot(payload)
      setError(null)
    } catch (err) {
      setError(err?.message || 'Failed to load market depth')
    } finally {
      setIsRefreshing(false)
    }
  }, [symbol, levels])

  useEffect(() => {
    fetchDepth()
    const timer = setInterval(fetchDepth, 5000)
    return () => clearInterval(timer)
  }, [fetchDepth])

  const visibleBids = useMemo(() => (snapshot?.bids || []).slice(0, 15), [snapshot])
  const visibleAsks = useMemo(() => (snapshot?.asks || []).slice(0, 15), [snapshot])
  const maxVisibleSize = useMemo(() => {
    const firstBid = visibleBids[0]?.size || 0
    const firstAsk = visibleAsks[0]?.size || 0
    return Math.max(firstBid, firstAsk, 1)
  }, [visibleBids, visibleAsks])

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-6 h-6 text-cyan-400" />
          <div>
            <h2 className="text-xl font-bold text-white">Depth Chart</h2>
            <p className="text-xs text-gray-500">Source: {snapshot?.source || 'unknown'}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {TOKENS.map((token) => (
              <option key={token} value={token}>
                {token}/USDC
              </option>
            ))}
          </select>
          <select
            value={levels}
            onChange={(e) => setLevels(Number(e.target.value))}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {[10, 20, 30, 40].map((count) => (
              <option key={count} value={count}>
                {count} levels
              </option>
            ))}
          </select>
          <button
            onClick={fetchDepth}
            className={`p-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
          <button
            onClick={() => setShowBook((current) => !current)}
            className="p-2 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10"
            title={showBook ? 'Hide order book' : 'Show order book'}
          >
            {showBook ? <Eye className="w-4 h-4 text-cyan-400" /> : <EyeOff className="w-4 h-4 text-gray-400" />}
          </button>
        </div>
      </div>

      {error ? (
        <div className="mb-4 p-3 rounded-lg border border-yellow-500/30 bg-yellow-500/10 text-yellow-300 text-sm flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
        <StatCard label="Mid Price" value={`$${formatPrice(snapshot?.mid_price)}`} />
        <StatCard label="Best Bid" value={`$${formatPrice(snapshot?.best_bid)}`} color="text-green-400" />
        <StatCard label="Best Ask" value={`$${formatPrice(snapshot?.best_ask)}`} color="text-red-400" />
        <StatCard label="Spread %" value={`${Number(snapshot?.spread_pct || 0).toFixed(4)}%`} />
        <StatCard
          label="Imbalance"
          value={`${Number(snapshot?.imbalance_pct || 0).toFixed(2)}%`}
          color={Number(snapshot?.imbalance_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}
        />
      </div>

      {showBook ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <BookColumn
            title="Bids"
            titleColor="text-green-400"
            rows={visibleBids}
            maxSize={maxVisibleSize}
            side="bid"
          />
          <BookColumn
            title="Asks"
            titleColor="text-red-400"
            rows={visibleAsks}
            maxSize={maxVisibleSize}
            side="ask"
          />
        </div>
      ) : null}
    </div>
  )
}

function StatCard({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-white/5 rounded-lg p-3 border border-white/10">
      <div className="text-gray-400 text-xs">{label}</div>
      <div className={`text-lg font-bold ${color}`}>{value}</div>
    </div>
  )
}

function BookColumn({ title, titleColor, rows, maxSize, side }) {
  const backgroundColor = side === 'bid' ? 'bg-green-500/10' : 'bg-red-500/10'
  const valueColor = side === 'bid' ? 'text-green-400' : 'text-red-400'
  return (
    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
      <h3 className={`font-medium mb-3 ${titleColor}`}>{title}</h3>
      <div className="space-y-1">
        <div className="text-xs text-gray-500 flex justify-between px-1">
          <span>Price</span>
          <span>Size</span>
          <span>Orders</span>
        </div>
        {rows.map((row, idx) => {
          const barWidth = Math.max(3, Math.round((row.size / maxSize) * 100))
          return (
            <div key={`${side}-${idx}`} className="relative flex justify-between text-xs px-1 py-1 rounded overflow-hidden">
              <div className={`absolute inset-y-0 left-0 ${backgroundColor}`} style={{ width: `${barWidth}%` }} />
              <span className={`relative font-mono ${valueColor}`}>${formatPrice(row.price)}</span>
              <span className="relative text-white">{formatSize(row.size)}</span>
              <span className="relative text-gray-400">{row.orders}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default DepthChart
