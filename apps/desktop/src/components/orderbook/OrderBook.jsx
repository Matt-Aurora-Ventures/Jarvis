import React, { useState, useMemo, useCallback, useEffect } from 'react'
import {
  BookOpen, RefreshCw, TrendingUp, TrendingDown, Layers, Activity,
  ArrowUpRight, ArrowDownRight, Settings, Maximize2, BarChart3,
  DollarSign, Percent, Clock, Zap, Filter, ChevronDown
} from 'lucide-react'

// Market pairs
const PAIRS = {
  'BTC-USDT': { base: 'BTC', quote: 'USDT', price: 97542.50, change24h: 2.85 },
  'ETH-USDT': { base: 'ETH', quote: 'USDT', price: 3458.75, change24h: 1.92 },
  'SOL-USDT': { base: 'SOL', quote: 'USDT', price: 198.42, change24h: 4.25 },
  'BTC-USDC': { base: 'BTC', quote: 'USDC', price: 97540.00, change24h: 2.84 },
  'ETH-BTC': { base: 'ETH', quote: 'BTC', price: 0.03548, change24h: -0.92 }
}

// Exchanges
const EXCHANGES = {
  BINANCE: { name: 'Binance', color: '#F0B90B' },
  BYBIT: { name: 'Bybit', color: '#F7A600' },
  OKX: { name: 'OKX', color: '#FFFFFF' },
  KRAKEN: { name: 'Kraken', color: '#5741D9' }
}

// Generate mock order book data
const generateOrderBook = (midPrice, spread = 0.01, depth = 25) => {
  const bids = []
  const asks = []

  let bidPrice = midPrice * (1 - spread / 2)
  let askPrice = midPrice * (1 + spread / 2)

  for (let i = 0; i < depth; i++) {
    // Random size with decay from mid price
    const bidSize = (Math.random() * 5 + 0.5) * Math.pow(0.95, i)
    const askSize = (Math.random() * 5 + 0.5) * Math.pow(0.95, i)

    bids.push({
      price: bidPrice,
      size: bidSize,
      total: bidSize * bidPrice,
      count: Math.floor(Math.random() * 20) + 1
    })

    asks.push({
      price: askPrice,
      size: askSize,
      total: askSize * askPrice,
      count: Math.floor(Math.random() * 20) + 1
    })

    // Move prices away from mid
    bidPrice *= (1 - (0.0002 + Math.random() * 0.0003))
    askPrice *= (1 + (0.0002 + Math.random() * 0.0003))
  }

  return { bids, asks }
}

// Generate mock recent trades
const generateTrades = (midPrice, count = 30) => {
  const trades = []
  let timestamp = Date.now()

  for (let i = 0; i < count; i++) {
    const isBuy = Math.random() > 0.5
    const price = midPrice * (1 + (Math.random() - 0.5) * 0.001)
    const size = Math.random() * 2 + 0.01

    trades.push({
      id: `t${i}`,
      price,
      size,
      side: isBuy ? 'buy' : 'sell',
      timestamp
    })

    timestamp -= Math.floor(Math.random() * 5000) + 500
  }

  return trades
}

// Order book row
const OrderRow = ({ order, side, maxTotal, precision, showCumulative, cumulativeTotal }) => {
  const barWidth = (order.total / maxTotal) * 100
  const cumulativeWidth = (cumulativeTotal / maxTotal) * 100

  return (
    <div className={`relative flex items-center py-1 px-2 text-sm font-mono hover:bg-white/5 ${
      side === 'bid' ? 'flex-row' : 'flex-row-reverse'
    }`}>
      {/* Depth bar */}
      <div
        className={`absolute inset-y-0 ${side === 'bid' ? 'right-0' : 'left-0'} ${
          side === 'bid' ? 'bg-green-500/20' : 'bg-red-500/20'
        }`}
        style={{ width: `${barWidth}%` }}
      />

      {/* Cumulative depth bar */}
      {showCumulative && (
        <div
          className={`absolute inset-y-0 ${side === 'bid' ? 'right-0' : 'left-0'} ${
            side === 'bid' ? 'bg-green-500/10' : 'bg-red-500/10'
          }`}
          style={{ width: `${cumulativeWidth}%` }}
        />
      )}

      <div className={`flex-1 grid grid-cols-3 gap-2 relative z-10 ${
        side === 'ask' ? 'text-right' : ''
      }`}>
        <span className={side === 'bid' ? 'text-green-400' : 'text-red-400'}>
          {order.price.toFixed(precision)}
        </span>
        <span className="text-gray-300">{order.size.toFixed(4)}</span>
        <span className="text-gray-500">{order.total.toFixed(2)}</span>
      </div>
    </div>
  )
}

// Spread indicator
const SpreadIndicator = ({ bid, ask, midPrice }) => {
  const spread = ask - bid
  const spreadPercent = (spread / midPrice) * 100

  return (
    <div className="flex items-center justify-center gap-4 py-2 px-4 bg-white/5 border-y border-white/10">
      <div className="text-sm">
        <span className="text-gray-500">Spread: </span>
        <span className="text-white font-mono">{spread.toFixed(2)}</span>
        <span className="text-gray-500 ml-2">({spreadPercent.toFixed(4)}%)</span>
      </div>
      <div className="text-sm">
        <span className="text-gray-500">Mid: </span>
        <span className="text-white font-mono">{midPrice.toFixed(2)}</span>
      </div>
    </div>
  )
}

// Depth chart
const DepthChart = ({ bids, asks, midPrice }) => {
  const chartData = useMemo(() => {
    const bidData = []
    const askData = []

    let bidCumulative = 0
    let askCumulative = 0

    bids.forEach(b => {
      bidCumulative += b.size
      bidData.push({ price: b.price, cumulative: bidCumulative })
    })

    asks.forEach(a => {
      askCumulative += a.size
      askData.push({ price: a.price, cumulative: askCumulative })
    })

    return { bidData, askData, maxCumulative: Math.max(bidCumulative, askCumulative) }
  }, [bids, asks])

  const { bidData, askData, maxCumulative } = chartData

  return (
    <div className="h-40 flex items-end relative px-2">
      {/* Bid side */}
      <div className="flex-1 flex items-end justify-end gap-0.5 h-full">
        {bidData.slice(0, 20).reverse().map((point, idx) => (
          <div
            key={`bid-${idx}`}
            className="flex-1 bg-green-500/40 rounded-t"
            style={{ height: `${(point.cumulative / maxCumulative) * 100}%` }}
          />
        ))}
      </div>

      {/* Center line */}
      <div className="w-px bg-white/20 h-full mx-1" />

      {/* Ask side */}
      <div className="flex-1 flex items-end justify-start gap-0.5 h-full">
        {askData.slice(0, 20).map((point, idx) => (
          <div
            key={`ask-${idx}`}
            className="flex-1 bg-red-500/40 rounded-t"
            style={{ height: `${(point.cumulative / maxCumulative) * 100}%` }}
          />
        ))}
      </div>
    </div>
  )
}

// Recent trades
const RecentTrades = ({ trades, precision }) => {
  return (
    <div className="h-64 overflow-y-auto">
      <div className="grid grid-cols-3 text-xs text-gray-500 px-2 py-1 border-b border-white/10 sticky top-0 bg-[#0a0e14]">
        <span>Price</span>
        <span className="text-center">Size</span>
        <span className="text-right">Time</span>
      </div>

      {trades.map(trade => {
        const time = new Date(trade.timestamp)
        const timeStr = `${time.getHours().toString().padStart(2, '0')}:${time.getMinutes().toString().padStart(2, '0')}:${time.getSeconds().toString().padStart(2, '0')}`

        return (
          <div
            key={trade.id}
            className="grid grid-cols-3 text-sm font-mono px-2 py-1 hover:bg-white/5"
          >
            <span className={trade.side === 'buy' ? 'text-green-400' : 'text-red-400'}>
              {trade.price.toFixed(precision)}
            </span>
            <span className="text-center text-gray-300">{trade.size.toFixed(4)}</span>
            <span className="text-right text-gray-500">{timeStr}</span>
          </div>
        )
      })}
    </div>
  )
}

// Order book stats
const OrderBookStats = ({ bids, asks, trades }) => {
  const stats = useMemo(() => {
    const totalBidVolume = bids.reduce((sum, b) => sum + b.size, 0)
    const totalAskVolume = asks.reduce((sum, a) => sum + a.size, 0)
    const bidAskRatio = totalBidVolume / totalAskVolume

    const buyTrades = trades.filter(t => t.side === 'buy')
    const sellTrades = trades.filter(t => t.side === 'sell')
    const buyVolume = buyTrades.reduce((sum, t) => sum + t.size, 0)
    const sellVolume = sellTrades.reduce((sum, t) => sum + t.size, 0)

    return {
      totalBidVolume,
      totalAskVolume,
      bidAskRatio,
      buyVolume,
      sellVolume,
      buyCount: buyTrades.length,
      sellCount: sellTrades.length
    }
  }, [bids, asks, trades])

  return (
    <div className="grid grid-cols-4 gap-4 mb-4">
      <div className="bg-white/5 rounded-lg p-3 border border-white/10">
        <div className="text-xs text-gray-500">Bid Volume</div>
        <div className="text-lg font-bold text-green-400">{stats.totalBidVolume.toFixed(2)}</div>
      </div>
      <div className="bg-white/5 rounded-lg p-3 border border-white/10">
        <div className="text-xs text-gray-500">Ask Volume</div>
        <div className="text-lg font-bold text-red-400">{stats.totalAskVolume.toFixed(2)}</div>
      </div>
      <div className="bg-white/5 rounded-lg p-3 border border-white/10">
        <div className="text-xs text-gray-500">Bid/Ask Ratio</div>
        <div className={`text-lg font-bold ${stats.bidAskRatio > 1 ? 'text-green-400' : 'text-red-400'}`}>
          {stats.bidAskRatio.toFixed(2)}
        </div>
      </div>
      <div className="bg-white/5 rounded-lg p-3 border border-white/10">
        <div className="text-xs text-gray-500">Trade Ratio</div>
        <div className={`text-lg font-bold ${stats.buyCount > stats.sellCount ? 'text-green-400' : 'text-red-400'}`}>
          {stats.buyCount}B / {stats.sellCount}S
        </div>
      </div>
    </div>
  )
}

// Main component
export const OrderBook = () => {
  const [selectedPair, setSelectedPair] = useState('BTC-USDT')
  const [selectedExchange, setSelectedExchange] = useState('BINANCE')
  const [depth, setDepth] = useState(15)
  const [showCumulative, setShowCumulative] = useState(true)
  const [viewMode, setViewMode] = useState('both') // 'both', 'bids', 'asks'
  const [refreshing, setRefreshing] = useState(false)

  const pair = PAIRS[selectedPair]
  const precision = pair.price > 100 ? 2 : pair.price > 1 ? 4 : 8

  // Generate order book data
  const [orderBookData, setOrderBookData] = useState(() => generateOrderBook(pair.price, 0.001, 25))
  const [trades, setTrades] = useState(() => generateTrades(pair.price))

  // Refresh data periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setOrderBookData(generateOrderBook(pair.price * (1 + (Math.random() - 0.5) * 0.0001), 0.001, 25))
      setTrades(prev => {
        const newTrade = {
          id: `t${Date.now()}`,
          price: pair.price * (1 + (Math.random() - 0.5) * 0.001),
          size: Math.random() * 2 + 0.01,
          side: Math.random() > 0.5 ? 'buy' : 'sell',
          timestamp: Date.now()
        }
        return [newTrade, ...prev.slice(0, 29)]
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [pair.price])

  const handleRefresh = useCallback(() => {
    setRefreshing(true)
    setOrderBookData(generateOrderBook(pair.price, 0.001, 25))
    setTrades(generateTrades(pair.price))
    setTimeout(() => setRefreshing(false), 500)
  }, [pair.price])

  // Calculate cumulative totals
  const processedBids = useMemo(() => {
    let cumulative = 0
    return orderBookData.bids.slice(0, depth).map(bid => {
      cumulative += bid.total
      return { ...bid, cumulative }
    })
  }, [orderBookData.bids, depth])

  const processedAsks = useMemo(() => {
    let cumulative = 0
    return orderBookData.asks.slice(0, depth).map(ask => {
      cumulative += ask.total
      return { ...ask, cumulative }
    })
  }, [orderBookData.asks, depth])

  const maxTotal = Math.max(
    processedBids[processedBids.length - 1]?.cumulative || 0,
    processedAsks[processedAsks.length - 1]?.cumulative || 0
  )

  const topBid = orderBookData.bids[0]?.price || 0
  const topAsk = orderBookData.asks[0]?.price || 0
  const midPrice = (topBid + topAsk) / 2

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <BookOpen className="w-7 h-7 text-blue-400" />
              Order Book
            </h1>
            <p className="text-gray-400 mt-1">Real-time market depth and recent trades</p>
          </div>

          <div className="flex items-center gap-3">
            {/* Pair selector */}
            <select
              value={selectedPair}
              onChange={(e) => setSelectedPair(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
            >
              {Object.keys(PAIRS).map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>

            {/* Exchange selector */}
            <select
              value={selectedExchange}
              onChange={(e) => setSelectedExchange(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
            >
              {Object.entries(EXCHANGES).map(([key, ex]) => (
                <option key={key} value={key}>{ex.name}</option>
              ))}
            </select>

            <button
              onClick={handleRefresh}
              className={`p-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors ${
                refreshing ? 'animate-spin' : ''
              }`}
            >
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Price ticker */}
        <div className="bg-white/5 rounded-xl p-4 border border-white/10 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div>
                <div className="text-sm text-gray-500">{selectedPair}</div>
                <div className="text-3xl font-bold font-mono">{pair.price.toFixed(precision)}</div>
              </div>
              <div className={`flex items-center gap-1 ${
                pair.change24h > 0 ? 'text-green-400' : 'text-red-400'
              }`}>
                {pair.change24h > 0 ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                <span className="text-lg font-medium">
                  {pair.change24h > 0 ? '+' : ''}{pair.change24h}%
                </span>
              </div>
            </div>

            {/* View mode */}
            <div className="flex bg-white/5 rounded-lg p-1">
              {['both', 'bids', 'asks'].map(mode => (
                <button
                  key={mode}
                  onClick={() => setViewMode(mode)}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    viewMode === mode
                      ? mode === 'bids' ? 'bg-green-500/20 text-green-400' :
                        mode === 'asks' ? 'bg-red-500/20 text-red-400' :
                        'bg-white/10 text-white'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {mode.charAt(0).toUpperCase() + mode.slice(1)}
                </button>
              ))}
            </div>

            {/* Depth selector */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Depth:</span>
              <select
                value={depth}
                onChange={(e) => setDepth(parseInt(e.target.value))}
                className="bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
              >
                {[10, 15, 20, 25].map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Stats */}
        <OrderBookStats bids={orderBookData.bids} asks={orderBookData.asks} trades={trades} />

        {/* Main content */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Order book */}
          <div className="lg:col-span-2 bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            {/* Headers */}
            <div className="grid grid-cols-2 text-xs text-gray-500 px-2 py-2 border-b border-white/10">
              <div className="grid grid-cols-3 gap-2">
                <span>Price ({pair.quote})</span>
                <span>Size ({pair.base})</span>
                <span>Total</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-right">
                <span>Total</span>
                <span>Size ({pair.base})</span>
                <span>Price ({pair.quote})</span>
              </div>
            </div>

            <div className="grid grid-cols-2">
              {/* Bids */}
              {(viewMode === 'both' || viewMode === 'bids') && (
                <div className={viewMode === 'bids' ? 'col-span-2' : ''}>
                  {processedBids.map((bid, idx) => (
                    <OrderRow
                      key={`bid-${idx}`}
                      order={bid}
                      side="bid"
                      maxTotal={maxTotal}
                      precision={precision}
                      showCumulative={showCumulative}
                      cumulativeTotal={bid.cumulative}
                    />
                  ))}
                </div>
              )}

              {/* Asks */}
              {(viewMode === 'both' || viewMode === 'asks') && (
                <div className={viewMode === 'asks' ? 'col-span-2' : ''}>
                  {processedAsks.map((ask, idx) => (
                    <OrderRow
                      key={`ask-${idx}`}
                      order={ask}
                      side="ask"
                      maxTotal={maxTotal}
                      precision={precision}
                      showCumulative={showCumulative}
                      cumulativeTotal={ask.cumulative}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Spread */}
            {viewMode === 'both' && (
              <SpreadIndicator bid={topBid} ask={topAsk} midPrice={midPrice} />
            )}

            {/* Depth chart */}
            <div className="p-4 border-t border-white/10">
              <h3 className="text-sm text-gray-400 mb-2">Market Depth</h3>
              <DepthChart bids={orderBookData.bids} asks={orderBookData.asks} midPrice={midPrice} />
            </div>
          </div>

          {/* Recent trades */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-3 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-medium flex items-center gap-2">
                <Activity className="w-4 h-4" />
                Recent Trades
              </h3>
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" title="Live" />
            </div>
            <RecentTrades trades={trades} precision={precision} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default OrderBook
