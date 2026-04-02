import React, { useState, useMemo, useEffect } from 'react'
import {
  Layers,
  TrendingUp,
  TrendingDown,
  Zap,
  Activity,
  Target,
  ChevronDown,
  BarChart3,
  AlertTriangle,
  RefreshCw,
  Eye,
  Shield
} from 'lucide-react'

export function DepthOfMarket() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('ladder') // ladder, heatmap, aggregate
  const [spreadAlert, setSpreadAlert] = useState(false)
  const [refreshKey, setRefreshKey] = useState(0)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate order book data
  const orderBook = useMemo(() => {
    const basePrice = selectedToken === 'SOL' ? 150.25 : selectedToken === 'ETH' ? 3205.50 : 95250.00
    const tickSize = basePrice * 0.0001

    const bids = []
    const asks = []

    // Generate bids (below mid price)
    for (let i = 0; i < 20; i++) {
      const price = basePrice - (i + 1) * tickSize
      const size = Math.floor(Math.random() * 10000) + 100
      const orders = Math.floor(Math.random() * 20) + 1
      const isLarge = size > 7000
      const isSpoofing = Math.random() < 0.05

      bids.push({
        price,
        size,
        orders,
        total: 0,
        isLarge,
        isSpoofing,
        depth: 0
      })
    }

    // Generate asks (above mid price)
    for (let i = 0; i < 20; i++) {
      const price = basePrice + (i + 1) * tickSize
      const size = Math.floor(Math.random() * 10000) + 100
      const orders = Math.floor(Math.random() * 20) + 1
      const isLarge = size > 7000
      const isSpoofing = Math.random() < 0.05

      asks.push({
        price,
        size,
        orders,
        total: 0,
        isLarge,
        isSpoofing,
        depth: 0
      })
    }

    // Calculate cumulative totals
    let bidTotal = 0
    bids.forEach(bid => {
      bidTotal += bid.size
      bid.total = bidTotal
    })

    let askTotal = 0
    asks.forEach(ask => {
      askTotal += ask.size
      ask.total = askTotal
    })

    // Calculate depth percentages
    const maxTotal = Math.max(bidTotal, askTotal)
    bids.forEach(bid => bid.depth = (bid.total / maxTotal) * 100)
    asks.forEach(ask => ask.depth = (ask.total / maxTotal) * 100)

    const spread = asks[0].price - bids[0].price
    const spreadPct = (spread / basePrice) * 100
    const midPrice = (asks[0].price + bids[0].price) / 2

    return {
      bids,
      asks,
      spread,
      spreadPct,
      midPrice,
      bestBid: bids[0].price,
      bestAsk: asks[0].price,
      totalBidSize: bidTotal,
      totalAskSize: askTotal,
      imbalance: ((bidTotal - askTotal) / (bidTotal + askTotal)) * 100
    }
  }, [selectedToken, refreshKey])

  // Auto-refresh simulation
  useEffect(() => {
    const interval = setInterval(() => {
      setRefreshKey(k => k + 1)
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Check spread alert
  useEffect(() => {
    setSpreadAlert(orderBook.spreadPct > 0.1)
  }, [orderBook.spreadPct])

  const formatPrice = (price) => {
    if (selectedToken === 'BTC') return price.toFixed(2)
    if (selectedToken === 'ETH') return price.toFixed(2)
    return price.toFixed(4)
  }

  const formatSize = (size) => {
    if (size >= 1000000) return `${(size / 1000000).toFixed(2)}M`
    if (size >= 1000) return `${(size / 1000).toFixed(1)}K`
    return size.toString()
  }

  const maxSize = Math.max(
    ...orderBook.bids.map(b => b.size),
    ...orderBook.asks.map(a => a.size)
  )

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">Depth of Market</h2>
            <div className="flex items-center gap-1 ml-2">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-xs text-gray-400">Live</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Token Selector */}
            <div className="relative">
              <select
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
                className="bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-white text-sm appearance-none pr-8 cursor-pointer"
              >
                {tokens.map(token => (
                  <option key={token} value={token}>{token}</option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-gray-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
            </div>

            <button
              onClick={() => setRefreshKey(k => k + 1)}
              className="p-1.5 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
            >
              <RefreshCw className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'ladder', label: 'DOM Ladder', icon: Layers },
            { id: 'heatmap', label: 'Heatmap', icon: Activity },
            { id: 'aggregate', label: 'Aggregate', icon: BarChart3 }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-cyan-500/30 text-cyan-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Best Bid</div>
            <div className="text-sm font-medium text-green-400">
              ${formatPrice(orderBook.bestBid)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Best Ask</div>
            <div className="text-sm font-medium text-red-400">
              ${formatPrice(orderBook.bestAsk)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Spread</div>
            <div className={`text-sm font-medium flex items-center gap-1 ${spreadAlert ? 'text-yellow-400' : 'text-white'}`}>
              ${orderBook.spread.toFixed(4)}
              {spreadAlert && <AlertTriangle className="w-3 h-3" />}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Spread %</div>
            <div className={`text-sm font-medium ${spreadAlert ? 'text-yellow-400' : 'text-white'}`}>
              {orderBook.spreadPct.toFixed(4)}%
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Mid Price</div>
            <div className="text-sm font-medium text-white">
              ${formatPrice(orderBook.midPrice)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Imbalance</div>
            <div className={`text-sm font-medium ${orderBook.imbalance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {orderBook.imbalance >= 0 ? '+' : ''}{orderBook.imbalance.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'ladder' && (
          <div className="space-y-4">
            {/* DOM Ladder */}
            <div className="grid grid-cols-2 gap-2">
              {/* Asks (Sell side) - reversed to show lowest ask at bottom */}
              <div>
                <div className="text-xs text-red-400 mb-2 flex items-center justify-between">
                  <span>ASKS (Sell Orders)</span>
                  <span>{formatSize(orderBook.totalAskSize)}</span>
                </div>
                <div className="space-y-0.5">
                  {[...orderBook.asks].reverse().map((ask, idx) => (
                    <div
                      key={idx}
                      className="relative flex items-center justify-between py-1 px-2 rounded text-xs"
                    >
                      {/* Depth bar */}
                      <div
                        className="absolute inset-0 bg-red-500/20 rounded"
                        style={{ width: `${(ask.size / maxSize) * 100}%` }}
                      />

                      <div className="relative flex items-center gap-2">
                        <span className={`font-mono ${ask.isLarge ? 'text-red-300 font-bold' : 'text-red-400'}`}>
                          ${formatPrice(ask.price)}
                        </span>
                        {ask.isSpoofing && (
                          <Shield className="w-3 h-3 text-yellow-400" title="Possible spoofing" />
                        )}
                      </div>

                      <div className="relative flex items-center gap-3">
                        <span className={`${ask.isLarge ? 'text-white font-bold' : 'text-gray-400'}`}>
                          {formatSize(ask.size)}
                        </span>
                        <span className="text-gray-600 w-6 text-right">{ask.orders}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bids (Buy side) */}
              <div>
                <div className="text-xs text-green-400 mb-2 flex items-center justify-between">
                  <span>BIDS (Buy Orders)</span>
                  <span>{formatSize(orderBook.totalBidSize)}</span>
                </div>
                <div className="space-y-0.5">
                  {orderBook.bids.map((bid, idx) => (
                    <div
                      key={idx}
                      className="relative flex items-center justify-between py-1 px-2 rounded text-xs"
                    >
                      {/* Depth bar */}
                      <div
                        className="absolute inset-0 bg-green-500/20 rounded"
                        style={{ width: `${(bid.size / maxSize) * 100}%` }}
                      />

                      <div className="relative flex items-center gap-2">
                        <span className={`font-mono ${bid.isLarge ? 'text-green-300 font-bold' : 'text-green-400'}`}>
                          ${formatPrice(bid.price)}
                        </span>
                        {bid.isSpoofing && (
                          <Shield className="w-3 h-3 text-yellow-400" title="Possible spoofing" />
                        )}
                      </div>

                      <div className="relative flex items-center gap-3">
                        <span className={`${bid.isLarge ? 'text-white font-bold' : 'text-gray-400'}`}>
                          {formatSize(bid.size)}
                        </span>
                        <span className="text-gray-600 w-6 text-right">{bid.orders}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Large Orders */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Large Orders Detected</h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-green-400 mb-2">Buy Walls</div>
                  {orderBook.bids.filter(b => b.isLarge).slice(0, 3).map((bid, idx) => (
                    <div key={idx} className="flex justify-between text-xs mb-1">
                      <span className="text-gray-400">${formatPrice(bid.price)}</span>
                      <span className="text-green-400 font-medium">{formatSize(bid.size)}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div className="text-xs text-red-400 mb-2">Sell Walls</div>
                  {orderBook.asks.filter(a => a.isLarge).slice(0, 3).map((ask, idx) => (
                    <div key={idx} className="flex justify-between text-xs mb-1">
                      <span className="text-gray-400">${formatPrice(ask.price)}</span>
                      <span className="text-red-400 font-medium">{formatSize(ask.size)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'heatmap' && (
          <div className="space-y-4">
            {/* Depth Heatmap */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Order Book Heatmap</h3>
              <div className="flex h-64">
                {/* Bids Heatmap */}
                <div className="flex-1 flex flex-col">
                  {orderBook.bids.map((bid, idx) => {
                    const intensity = bid.size / maxSize
                    const bgOpacity = Math.min(intensity * 0.8, 0.6)

                    return (
                      <div
                        key={idx}
                        className="flex-1 flex items-center justify-between px-2 border-b border-white/5"
                        style={{
                          backgroundColor: `rgba(34, 197, 94, ${bgOpacity})`
                        }}
                      >
                        <span className="text-[10px] text-white/80">${formatPrice(bid.price)}</span>
                        <span className="text-[10px] text-white/80">{formatSize(bid.size)}</span>
                      </div>
                    )
                  })}
                </div>

                {/* Price Scale */}
                <div className="w-px bg-yellow-400 mx-2"></div>

                {/* Asks Heatmap */}
                <div className="flex-1 flex flex-col">
                  {orderBook.asks.map((ask, idx) => {
                    const intensity = ask.size / maxSize
                    const bgOpacity = Math.min(intensity * 0.8, 0.6)

                    return (
                      <div
                        key={idx}
                        className="flex-1 flex items-center justify-between px-2 border-b border-white/5"
                        style={{
                          backgroundColor: `rgba(239, 68, 68, ${bgOpacity})`
                        }}
                      >
                        <span className="text-[10px] text-white/80">${formatPrice(ask.price)}</span>
                        <span className="text-[10px] text-white/80">{formatSize(ask.size)}</span>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Legend */}
              <div className="flex justify-center gap-8 mt-3 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-16 h-3 rounded" style={{
                    background: 'linear-gradient(to right, rgba(34, 197, 94, 0.1), rgba(34, 197, 94, 0.6))'
                  }}></div>
                  <span className="text-gray-400">Bid Depth</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-3 rounded" style={{
                    background: 'linear-gradient(to right, rgba(239, 68, 68, 0.1), rgba(239, 68, 68, 0.6))'
                  }}></div>
                  <span className="text-gray-400">Ask Depth</span>
                </div>
              </div>
            </div>

            {/* Liquidity Clusters */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-green-400 mb-3">Bid Clusters</h3>
                <div className="space-y-2">
                  {orderBook.bids
                    .sort((a, b) => b.size - a.size)
                    .slice(0, 3)
                    .map((bid, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <div
                          className="h-2 bg-green-500/60 rounded"
                          style={{ width: `${(bid.size / maxSize) * 100}%` }}
                        />
                        <span className="text-xs text-gray-400">${formatPrice(bid.price)}</span>
                      </div>
                    ))}
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-red-400 mb-3">Ask Clusters</h3>
                <div className="space-y-2">
                  {orderBook.asks
                    .sort((a, b) => b.size - a.size)
                    .slice(0, 3)
                    .map((ask, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <div
                          className="h-2 bg-red-500/60 rounded"
                          style={{ width: `${(ask.size / maxSize) * 100}%` }}
                        />
                        <span className="text-xs text-gray-400">${formatPrice(ask.price)}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'aggregate' && (
          <div className="space-y-4">
            {/* Cumulative Depth Chart */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Cumulative Depth</h3>
              <div className="relative h-48">
                {/* Y-axis labels */}
                <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between text-xs text-gray-500">
                  <span>{formatSize(Math.max(orderBook.totalBidSize, orderBook.totalAskSize))}</span>
                  <span>{formatSize(Math.max(orderBook.totalBidSize, orderBook.totalAskSize) / 2)}</span>
                  <span>0</span>
                </div>

                {/* Chart area */}
                <div className="ml-14 h-full flex items-end">
                  {/* Bids (reversed for visual) */}
                  <div className="flex-1 flex items-end justify-end gap-0.5">
                    {[...orderBook.bids].reverse().map((bid, idx) => {
                      const maxTotal = Math.max(orderBook.totalBidSize, orderBook.totalAskSize)
                      const height = (bid.total / maxTotal) * 100

                      return (
                        <div
                          key={idx}
                          className="flex-1 bg-green-500/40 rounded-t hover:bg-green-500/60 transition-colors"
                          style={{ height: `${height}%` }}
                          title={`$${formatPrice(bid.price)}: ${formatSize(bid.total)} cumulative`}
                        />
                      )
                    })}
                  </div>

                  {/* Mid price divider */}
                  <div className="w-0.5 h-full bg-yellow-400 mx-1"></div>

                  {/* Asks */}
                  <div className="flex-1 flex items-end gap-0.5">
                    {orderBook.asks.map((ask, idx) => {
                      const maxTotal = Math.max(orderBook.totalBidSize, orderBook.totalAskSize)
                      const height = (ask.total / maxTotal) * 100

                      return (
                        <div
                          key={idx}
                          className="flex-1 bg-red-500/40 rounded-t hover:bg-red-500/60 transition-colors"
                          style={{ height: `${height}%` }}
                          title={`$${formatPrice(ask.price)}: ${formatSize(ask.total)} cumulative`}
                        />
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* X-axis labels */}
              <div className="ml-14 flex justify-between text-xs text-gray-500 mt-2">
                <span>-{((orderBook.bestBid - orderBook.bids[orderBook.bids.length - 1].price) / orderBook.bestBid * 100).toFixed(2)}%</span>
                <span className="text-yellow-400">Mid</span>
                <span>+{((orderBook.asks[orderBook.asks.length - 1].price - orderBook.bestAsk) / orderBook.bestAsk * 100).toFixed(2)}%</span>
              </div>
            </div>

            {/* Order Book Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-green-400">
                  {formatSize(orderBook.totalBidSize)}
                </div>
                <div className="text-xs text-gray-400 mt-1">Total Bids</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className={`text-2xl font-bold ${orderBook.imbalance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {orderBook.imbalance >= 0 ? '+' : ''}{orderBook.imbalance.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-400 mt-1">Book Imbalance</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-red-400">
                  {formatSize(orderBook.totalAskSize)}
                </div>
                <div className="text-xs text-gray-400 mt-1">Total Asks</div>
              </div>
            </div>

            {/* Trading Signal */}
            <div className={`rounded-lg p-4 border ${
              orderBook.imbalance > 20 ? 'bg-green-500/10 border-green-500/20' :
              orderBook.imbalance < -20 ? 'bg-red-500/10 border-red-500/20' :
              'bg-white/5 border-white/10'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Zap className={`w-4 h-4 ${
                  orderBook.imbalance > 20 ? 'text-green-400' :
                  orderBook.imbalance < -20 ? 'text-red-400' :
                  'text-gray-400'
                }`} />
                <h3 className="text-sm font-medium text-white">Order Flow Signal</h3>
              </div>
              <p className="text-sm text-gray-300">
                {orderBook.imbalance > 20
                  ? `Strong bid imbalance (+${orderBook.imbalance.toFixed(1)}%) - buyers stacking, potential upward pressure`
                  : orderBook.imbalance < -20
                  ? `Strong ask imbalance (${orderBook.imbalance.toFixed(1)}%) - sellers stacking, potential downward pressure`
                  : `Balanced order book (${orderBook.imbalance.toFixed(1)}%) - no clear directional bias`}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DepthOfMarket
