import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, Layers, RefreshCw } from 'lucide-react'

const TOKENS = ['SOL', 'ETH', 'BTC', 'JUP', 'BONK', 'WIF', 'RNDR', 'PYTH']

function formatPrice(value, symbol) {
  if (!Number.isFinite(value)) return '--'
  if (symbol === 'BTC' || symbol === 'ETH') return value.toFixed(2)
  if (value >= 1) return value.toFixed(4)
  return value.toFixed(8)
}

function formatSize(value) {
  if (!Number.isFinite(value)) return '--'
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return value.toFixed(2)
}

export function DepthOfMarket() {
  const [symbol, setSymbol] = useState('SOL')
  const [levels, setLevels] = useState(20)
  const [snapshot, setSnapshot] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)

  const refresh = useCallback(async () => {
    setRefreshing(true)
    try {
      const response = await fetch(`/api/market/depth?symbol=${symbol}&levels=${levels}`)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setSnapshot(await response.json())
      setError(null)
    } catch (err) {
      setError(err?.message || 'Unable to fetch depth snapshot')
    } finally {
      setRefreshing(false)
    }
  }, [symbol, levels])

  useEffect(() => {
    refresh()
    const timer = setInterval(refresh, 3000)
    return () => clearInterval(timer)
  }, [refresh])

  const bids = useMemo(() => (snapshot?.bids || []).slice(0, levels), [snapshot, levels])
  const asks = useMemo(() => (snapshot?.asks || []).slice(0, levels), [snapshot, levels])
  const maxDepth = useMemo(() => Math.max(bids[bids.length - 1]?.cumulative || 1, asks[asks.length - 1]?.cumulative || 1), [bids, asks])

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Depth of Market</h2>
            <span className="text-xs text-gray-500">source: {snapshot?.source || 'unknown'}</span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm"
            >
              {TOKENS.map((token) => (
                <option key={token} value={token}>
                  {token}
                </option>
              ))}
            </select>
            <select
              value={levels}
              onChange={(e) => setLevels(Number(e.target.value))}
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm"
            >
              {[10, 20, 30].map((count) => (
                <option key={count} value={count}>
                  {count} levels
                </option>
              ))}
            </select>
            <button onClick={refresh} className={`p-1.5 bg-white/5 hover:bg-white/10 rounded-lg ${refreshing ? 'animate-spin' : ''}`}>
              <RefreshCw className="w-4 h-4 text-gray-300" />
            </button>
          </div>
        </div>

        {error ? (
          <div className="text-xs p-2 rounded bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 flex items-center gap-2">
            <AlertTriangle className="w-3 h-3" />
            {error}
          </div>
        ) : null}

        <div className="grid grid-cols-2 md:grid-cols-6 gap-4 mt-3 text-xs">
          <Metric title="Best Bid" value={`$${formatPrice(snapshot?.best_bid, symbol)}`} valueClass="text-green-400" />
          <Metric title="Best Ask" value={`$${formatPrice(snapshot?.best_ask, symbol)}`} valueClass="text-red-400" />
          <Metric title="Spread" value={`${Number(snapshot?.spread_pct || 0).toFixed(4)}%`} />
          <Metric title="Mid" value={`$${formatPrice(snapshot?.mid_price, symbol)}`} />
          <Metric title="Bid Size" value={formatSize(snapshot?.total_bid_size)} />
          <Metric
            title="Imbalance"
            value={`${Number(snapshot?.imbalance_pct || 0).toFixed(2)}%`}
            valueClass={Number(snapshot?.imbalance_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}
          />
        </div>
      </div>

      <div className="p-4">
        <div className="grid grid-cols-2 gap-4">
          <DepthSide title="ASKS" rows={[...asks].reverse()} symbol={symbol} maxDepth={maxDepth} side="ask" />
          <DepthSide title="BIDS" rows={bids} symbol={symbol} maxDepth={maxDepth} side="bid" />
        </div>
      </div>

      <div className="px-4 pb-4">
        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <div className="flex items-center gap-2 text-sm text-white mb-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            Cumulative Liquidity
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-gray-400">Bid cumulative</div>
              <div className="text-green-400 font-medium">
                {formatSize(bids[bids.length - 1]?.cumulative || 0)} {symbol}
              </div>
            </div>
            <div>
              <div className="text-gray-400">Ask cumulative</div>
              <div className="text-red-400 font-medium">
                {formatSize(asks[asks.length - 1]?.cumulative || 0)} {symbol}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Metric({ title, value, valueClass = 'text-white' }) {
  return (
    <div>
      <div className="text-gray-500">{title}</div>
      <div className={`font-medium ${valueClass}`}>{value}</div>
    </div>
  )
}

function DepthSide({ title, rows, symbol, maxDepth, side }) {
  const isBid = side === 'bid'
  const bgClass = isBid ? 'bg-green-500/20' : 'bg-red-500/20'
  const priceClass = isBid ? 'text-green-400' : 'text-red-400'

  return (
    <div>
      <div className={`text-xs mb-2 ${priceClass}`}>{title}</div>
      <div className="space-y-1">
        {rows.map((row, idx) => {
          const width = Math.max(3, Math.round((row.cumulative / maxDepth) * 100))
          return (
            <div key={`${side}-${idx}`} className="relative rounded px-2 py-1 text-xs flex justify-between overflow-hidden">
              <div className={`absolute inset-y-0 left-0 ${bgClass}`} style={{ width: `${width}%` }} />
              <span className={`relative font-mono ${priceClass}`}>${formatPrice(row.price, symbol)}</span>
              <span className="relative text-white">{formatSize(row.size)}</span>
              <span className="relative text-gray-400">{row.orders}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default DepthOfMarket
