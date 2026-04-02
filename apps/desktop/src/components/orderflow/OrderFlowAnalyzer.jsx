import React, { useState, useMemo, useEffect } from 'react'
import {
  Activity, TrendingUp, TrendingDown, ArrowUpRight, ArrowDownRight,
  BarChart3, Zap, Clock, Filter, RefreshCw, Download, AlertTriangle,
  Target, Layers, ArrowUp, ArrowDown, Eye, Scale, Volume2, Gauge
} from 'lucide-react'

const TOKENS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 95420 },
  { symbol: 'ETH', name: 'Ethereum', price: 3280 },
  { symbol: 'SOL', name: 'Solana', price: 185 },
  { symbol: 'BNB', name: 'BNB', price: 680 },
  { symbol: 'XRP', name: 'Ripple', price: 2.45 },
  { symbol: 'DOGE', name: 'Dogecoin', price: 0.38 },
  { symbol: 'AVAX', name: 'Avalanche', price: 38.50 },
  { symbol: 'LINK', name: 'Chainlink', price: 22.40 }
]

const EXCHANGES = ['Binance', 'Coinbase', 'Kraken', 'OKX', 'Bybit', 'KuCoin']

export function OrderFlowAnalyzer() {
  const [mode, setMode] = useState('overview') // overview, tape, cvd, footprint
  const [selectedToken, setSelectedToken] = useState('BTC')
  const [selectedExchange, setSelectedExchange] = useState('Binance')
  const [minOrderSize, setMinOrderSize] = useState(50000)
  const [timeframe, setTimeframe] = useState('5m')

  // Generate mock order flow data
  const [orderFlow, setOrderFlow] = useState(() => generateOrderFlow())
  const [largeOrders, setLargeOrders] = useState(() => generateLargeOrders())

  function generateOrderFlow() {
    const flow = []
    for (let i = 0; i < 50; i++) {
      const isBuy = Math.random() > 0.48
      const size = Math.floor(Math.random() * 100000) + 1000
      flow.push({
        id: i,
        time: new Date(Date.now() - i * 2000).toLocaleTimeString(),
        side: isBuy ? 'buy' : 'sell',
        price: 95420 + (Math.random() - 0.5) * 200,
        size,
        value: size,
        exchange: EXCHANGES[Math.floor(Math.random() * EXCHANGES.length)],
        isLarge: size > 50000
      })
    }
    return flow
  }

  function generateLargeOrders() {
    const orders = []
    for (let i = 0; i < 20; i++) {
      const isBuy = Math.random() > 0.45
      const size = Math.floor(Math.random() * 500000) + 100000
      orders.push({
        id: i,
        time: new Date(Date.now() - i * 60000).toLocaleTimeString(),
        side: isBuy ? 'buy' : 'sell',
        price: 95420 + (Math.random() - 0.5) * 500,
        size,
        exchange: EXCHANGES[Math.floor(Math.random() * EXCHANGES.length)],
        type: Math.random() > 0.7 ? 'iceberg' : Math.random() > 0.5 ? 'market' : 'limit'
      })
    }
    return orders.sort((a, b) => b.size - a.size)
  }

  // Simulate live updates
  useEffect(() => {
    const interval = setInterval(() => {
      const isBuy = Math.random() > 0.48
      const size = Math.floor(Math.random() * 100000) + 1000
      const newOrder = {
        id: Date.now(),
        time: new Date().toLocaleTimeString(),
        side: isBuy ? 'buy' : 'sell',
        price: 95420 + (Math.random() - 0.5) * 200,
        size,
        value: size,
        exchange: EXCHANGES[Math.floor(Math.random() * EXCHANGES.length)],
        isLarge: size > 50000
      }
      setOrderFlow(prev => [newOrder, ...prev.slice(0, 49)])
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Calculate CVD (Cumulative Volume Delta)
  const cvdData = useMemo(() => {
    let cumulative = 0
    const data = []
    for (let i = orderFlow.length - 1; i >= 0; i--) {
      const order = orderFlow[i]
      cumulative += order.side === 'buy' ? order.size : -order.size
      data.push({
        time: order.time,
        cvd: cumulative,
        delta: order.side === 'buy' ? order.size : -order.size
      })
    }
    return data.reverse()
  }, [orderFlow])

  // Order flow statistics
  const stats = useMemo(() => {
    const buys = orderFlow.filter(o => o.side === 'buy')
    const sells = orderFlow.filter(o => o.side === 'sell')
    const buyVolume = buys.reduce((sum, o) => sum + o.size, 0)
    const sellVolume = sells.reduce((sum, o) => sum + o.size, 0)
    const totalVolume = buyVolume + sellVolume
    const buyPressure = (buyVolume / totalVolume) * 100
    const largeBuys = buys.filter(o => o.isLarge).length
    const largeSells = sells.filter(o => o.isLarge).length
    const avgBuySize = buys.length > 0 ? buyVolume / buys.length : 0
    const avgSellSize = sells.length > 0 ? sellVolume / sells.length : 0

    return {
      buyVolume,
      sellVolume,
      totalVolume,
      buyPressure,
      sellPressure: 100 - buyPressure,
      buyCount: buys.length,
      sellCount: sells.length,
      largeBuys,
      largeSells,
      avgBuySize,
      avgSellSize,
      netFlow: buyVolume - sellVolume,
      cvd: cvdData.length > 0 ? cvdData[cvdData.length - 1].cvd : 0
    }
  }, [orderFlow, cvdData])

  // Order book imbalance (mock)
  const [orderBook] = useState(() => {
    const bids = []
    const asks = []
    for (let i = 0; i < 10; i++) {
      bids.push({
        price: 95420 - (i + 1) * 10,
        size: Math.floor(Math.random() * 50) + 10,
        total: 0
      })
      asks.push({
        price: 95420 + (i + 1) * 10,
        size: Math.floor(Math.random() * 50) + 10,
        total: 0
      })
    }
    // Calculate totals
    let bidTotal = 0, askTotal = 0
    bids.forEach(b => { bidTotal += b.size; b.total = bidTotal })
    asks.forEach(a => { askTotal += a.size; a.total = askTotal })
    return { bids, asks, bidTotal, askTotal }
  })

  const imbalance = ((orderBook.bidTotal - orderBook.askTotal) / (orderBook.bidTotal + orderBook.askTotal)) * 100

  // Volume profile (mock)
  const [volumeProfile] = useState(() => {
    const profile = []
    for (let i = 0; i < 20; i++) {
      const price = 95000 + i * 50
      profile.push({
        price,
        buyVolume: Math.floor(Math.random() * 100) + 20,
        sellVolume: Math.floor(Math.random() * 100) + 20
      })
    }
    return profile
  })

  const poc = volumeProfile.reduce((max, p) =>
    (p.buyVolume + p.sellVolume) > (max.buyVolume + max.sellVolume) ? p : max
  )

  const formatValue = (value) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
    if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`
    return `$${value}`
  }

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/20 rounded-lg">
            <Activity className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Order Flow Analyzer</h1>
            <p className="text-sm text-gray-400">Track market order flow in real-time</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['overview', 'tape', 'cvd', 'footprint'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                mode === m ? 'bg-cyan-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {m === 'cvd' ? 'CVD' : m}
            </button>
          ))}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4 mb-6">
        <select
          value={selectedToken}
          onChange={(e) => setSelectedToken(e.target.value)}
          className="bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
        >
          {TOKENS.map(t => (
            <option key={t.symbol} value={t.symbol}>{t.symbol}/USDT</option>
          ))}
        </select>
        <select
          value={selectedExchange}
          onChange={(e) => setSelectedExchange(e.target.value)}
          className="bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
        >
          {EXCHANGES.map(e => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-400">Min Size:</span>
          <select
            value={minOrderSize}
            onChange={(e) => setMinOrderSize(Number(e.target.value))}
            className="bg-white/10 border border-white/20 rounded px-2 py-1 text-white text-sm"
          >
            <option value={10000}>$10K</option>
            <option value={50000}>$50K</option>
            <option value={100000}>$100K</option>
            <option value={500000}>$500K</option>
          </select>
        </div>
        <div className="ml-auto flex items-center gap-2 text-sm text-gray-400">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          Live
        </div>
      </div>

      {/* Overview Mode */}
      {mode === 'overview' && (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className={`rounded-xl p-6 border ${
              stats.netFlow >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Scale className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-400">Net Flow</span>
              </div>
              <div className={`text-2xl font-bold ${stats.netFlow >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.netFlow >= 0 ? '+' : ''}{formatValue(stats.netFlow)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                {stats.netFlow >= 0 ? 'Buy pressure' : 'Sell pressure'}
              </div>
            </div>

            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <Gauge className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-400">Buy/Sell Ratio</span>
              </div>
              <div className="text-2xl font-bold text-white">
                {stats.buyPressure.toFixed(1)}%
              </div>
              <div className="h-2 bg-white/10 rounded-full mt-2 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full"
                  style={{ width: `${stats.buyPressure}%` }}
                />
              </div>
            </div>

            <div className="bg-blue-500/10 rounded-xl p-6 border border-blue-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Volume2 className="w-5 h-5 text-blue-400" />
                <span className="text-sm text-gray-400">Total Volume</span>
              </div>
              <div className="text-2xl font-bold text-blue-400">
                {formatValue(stats.totalVolume)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Last 50 trades
              </div>
            </div>

            <div className={`rounded-xl p-6 border ${
              stats.cvd >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-400">CVD</span>
              </div>
              <div className={`text-2xl font-bold ${stats.cvd >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.cvd >= 0 ? '+' : ''}{formatValue(stats.cvd)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Cumulative delta
              </div>
            </div>
          </div>

          {/* Buy vs Sell Breakdown */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-green-500/10 rounded-xl p-6 border border-green-500/30">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <ArrowUp className="w-5 h-5 text-green-400" />
                  <span className="font-semibold text-white">Buy Orders</span>
                </div>
                <span className="text-2xl font-bold text-green-400">{stats.buyCount}</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-400">Volume</div>
                  <div className="text-white font-medium">{formatValue(stats.buyVolume)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Avg Size</div>
                  <div className="text-white font-medium">{formatValue(stats.avgBuySize)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Large Orders</div>
                  <div className="text-green-400 font-medium">{stats.largeBuys}</div>
                </div>
                <div>
                  <div className="text-gray-400">Pressure</div>
                  <div className="text-green-400 font-medium">{stats.buyPressure.toFixed(1)}%</div>
                </div>
              </div>
            </div>

            <div className="bg-red-500/10 rounded-xl p-6 border border-red-500/30">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <ArrowDown className="w-5 h-5 text-red-400" />
                  <span className="font-semibold text-white">Sell Orders</span>
                </div>
                <span className="text-2xl font-bold text-red-400">{stats.sellCount}</span>
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-400">Volume</div>
                  <div className="text-white font-medium">{formatValue(stats.sellVolume)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Avg Size</div>
                  <div className="text-white font-medium">{formatValue(stats.avgSellSize)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Large Orders</div>
                  <div className="text-red-400 font-medium">{stats.largeSells}</div>
                </div>
                <div>
                  <div className="text-gray-400">Pressure</div>
                  <div className="text-red-400 font-medium">{stats.sellPressure.toFixed(1)}%</div>
                </div>
              </div>
            </div>
          </div>

          {/* Order Book Imbalance */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-400" />
                Order Book Imbalance
              </h3>
              <span className={`text-lg font-bold ${imbalance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {imbalance >= 0 ? '+' : ''}{imbalance.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center gap-4 mb-4">
              <div className="flex-1">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-green-400">Bids: {orderBook.bidTotal} BTC</span>
                </div>
                <div className="h-6 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-green-600 to-green-400 rounded-full flex items-center justify-end pr-2"
                    style={{ width: `${(orderBook.bidTotal / (orderBook.bidTotal + orderBook.askTotal)) * 100}%` }}
                  >
                    <span className="text-xs text-white font-medium">{((orderBook.bidTotal / (orderBook.bidTotal + orderBook.askTotal)) * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
              <div className="flex-1">
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-red-400">Asks: {orderBook.askTotal} BTC</span>
                </div>
                <div className="h-6 bg-white/10 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-red-400 to-red-600 rounded-full flex items-center justify-end pr-2"
                    style={{ width: `${(orderBook.askTotal / (orderBook.bidTotal + orderBook.askTotal)) * 100}%` }}
                  >
                    <span className="text-xs text-white font-medium">{((orderBook.askTotal / (orderBook.bidTotal + orderBook.askTotal)) * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </div>
            <div className={`text-center p-3 rounded-lg ${
              imbalance > 10 ? 'bg-green-500/20 text-green-400' :
              imbalance < -10 ? 'bg-red-500/20 text-red-400' :
              'bg-white/10 text-gray-400'
            }`}>
              {imbalance > 10 ? 'Strong buy-side support' :
               imbalance < -10 ? 'Strong sell-side pressure' :
               'Relatively balanced book'}
            </div>
          </div>

          {/* Large Orders */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-yellow-400" />
                Large Orders (>{formatValue(minOrderSize)})
              </h3>
              <span className="text-sm text-gray-400">{largeOrders.length} orders</span>
            </div>
            <div className="max-h-64 overflow-y-auto">
              {largeOrders.slice(0, 10).map(order => (
                <div key={order.id} className="flex items-center justify-between p-3 border-b border-white/5 hover:bg-white/5">
                  <div className="flex items-center gap-3">
                    <span className={`p-1.5 rounded ${order.side === 'buy' ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                      {order.side === 'buy' ?
                        <ArrowUp className="w-4 h-4 text-green-400" /> :
                        <ArrowDown className="w-4 h-4 text-red-400" />
                      }
                    </span>
                    <div>
                      <div className="text-white font-medium">{formatValue(order.size)}</div>
                      <div className="text-xs text-gray-500">{order.exchange} - {order.type}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-white">${order.price.toLocaleString()}</div>
                    <div className="text-xs text-gray-500">{order.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tape Mode */}
      {mode === 'tape' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Eye className="w-5 h-5 text-cyan-400" />
                Time & Sales
              </h3>
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <RefreshCw className="w-4 h-4 animate-spin" />
                Streaming
              </div>
            </div>
            <div className="overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-gray-400 border-b border-white/10 bg-white/5">
                    <th className="p-3 text-left">Time</th>
                    <th className="p-3 text-left">Side</th>
                    <th className="p-3 text-right">Price</th>
                    <th className="p-3 text-right">Size</th>
                    <th className="p-3 text-right">Value</th>
                    <th className="p-3 text-left">Exchange</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {orderFlow.map((order, idx) => (
                    <tr
                      key={order.id}
                      className={`transition-colors ${
                        idx === 0 ? 'bg-white/10' : 'hover:bg-white/5'
                      } ${order.isLarge ? 'font-semibold' : ''}`}
                    >
                      <td className="p-3 text-gray-400 text-sm">{order.time}</td>
                      <td className="p-3">
                        <span className={`flex items-center gap-1 ${
                          order.side === 'buy' ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {order.side === 'buy' ?
                            <ArrowUpRight className="w-4 h-4" /> :
                            <ArrowDownRight className="w-4 h-4" />
                          }
                          {order.side.toUpperCase()}
                        </span>
                      </td>
                      <td className={`p-3 text-right font-mono ${
                        order.side === 'buy' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${order.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </td>
                      <td className="p-3 text-right text-white">
                        {order.isLarge && <Zap className="w-3 h-3 text-yellow-400 inline mr-1" />}
                        {formatValue(order.size)}
                      </td>
                      <td className="p-3 text-right text-gray-300">{formatValue(order.value)}</td>
                      <td className="p-3 text-gray-400 text-sm">{order.exchange}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* CVD Mode */}
      {mode === 'cvd' && (
        <div className="space-y-6">
          {/* CVD Summary */}
          <div className="grid grid-cols-3 gap-4">
            <div className={`rounded-xl p-6 border ${
              stats.cvd >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="text-sm text-gray-400 mb-2">Current CVD</div>
              <div className={`text-3xl font-bold ${stats.cvd >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.cvd >= 0 ? '+' : ''}{formatValue(stats.cvd)}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="text-sm text-gray-400 mb-2">CVD Trend</div>
              <div className="text-3xl font-bold text-white flex items-center gap-2">
                {cvdData.length > 1 && cvdData[cvdData.length - 1].cvd > cvdData[0].cvd ?
                  <TrendingUp className="w-8 h-8 text-green-400" /> :
                  <TrendingDown className="w-8 h-8 text-red-400" />
                }
                {cvdData.length > 1 && cvdData[cvdData.length - 1].cvd > cvdData[0].cvd ? 'Bullish' : 'Bearish'}
              </div>
            </div>
            <div className="bg-purple-500/10 rounded-xl p-6 border border-purple-500/30">
              <div className="text-sm text-gray-400 mb-2">Delta Divergence</div>
              <div className="text-3xl font-bold text-purple-400">
                {Math.abs(stats.cvd) > stats.totalVolume * 0.3 ? 'Strong' : 'Weak'}
              </div>
            </div>
          </div>

          {/* CVD Chart (simplified text visualization) */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-cyan-400" />
              CVD History
            </h3>
            <div className="space-y-2">
              {cvdData.slice(-20).map((point, idx) => {
                const maxCvd = Math.max(...cvdData.map(d => Math.abs(d.cvd)))
                const width = Math.abs(point.cvd) / maxCvd * 100
                return (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 w-16">{point.time}</span>
                    <div className="flex-1 h-4 bg-white/5 rounded relative">
                      <div
                        className={`absolute top-0 h-full rounded ${
                          point.cvd >= 0 ? 'bg-green-500/50 left-1/2' : 'bg-red-500/50 right-1/2'
                        }`}
                        style={{
                          width: `${width / 2}%`,
                          [point.cvd >= 0 ? 'left' : 'right']: '50%'
                        }}
                      />
                      <div className="absolute top-0 left-1/2 h-full w-px bg-white/20" />
                    </div>
                    <span className={`text-xs font-mono w-20 text-right ${
                      point.cvd >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {point.cvd >= 0 ? '+' : ''}{formatValue(point.cvd)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Delta Breakdown */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4">Recent Deltas</h3>
            <div className="grid grid-cols-5 gap-2">
              {cvdData.slice(-10).map((point, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded-lg text-center ${
                    point.delta >= 0 ? 'bg-green-500/20' : 'bg-red-500/20'
                  }`}
                >
                  <div className={`text-sm font-bold ${
                    point.delta >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {point.delta >= 0 ? '+' : ''}{formatValue(point.delta)}
                  </div>
                  <div className="text-xs text-gray-500">{point.time}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Footprint Mode */}
      {mode === 'footprint' && (
        <div className="space-y-6">
          {/* Volume Profile */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                Volume Profile
              </h3>
              <div className="text-sm">
                <span className="text-gray-400">POC: </span>
                <span className="text-purple-400 font-bold">${poc.price.toLocaleString()}</span>
              </div>
            </div>
            <div className="space-y-1">
              {volumeProfile.map((level, idx) => {
                const totalVol = level.buyVolume + level.sellVolume
                const maxVol = Math.max(...volumeProfile.map(p => p.buyVolume + p.sellVolume))
                const width = (totalVol / maxVol) * 100
                const isPoc = level.price === poc.price

                return (
                  <div
                    key={idx}
                    className={`flex items-center gap-2 ${isPoc ? 'bg-purple-500/20 rounded' : ''}`}
                  >
                    <span className={`text-xs w-20 text-right font-mono ${isPoc ? 'text-purple-400 font-bold' : 'text-gray-400'}`}>
                      ${level.price.toLocaleString()}
                    </span>
                    <div className="flex-1 flex h-5">
                      <div
                        className="bg-green-500/50 rounded-l"
                        style={{ width: `${(level.buyVolume / (level.buyVolume + level.sellVolume)) * width}%` }}
                      />
                      <div
                        className="bg-red-500/50 rounded-r"
                        style={{ width: `${(level.sellVolume / (level.buyVolume + level.sellVolume)) * width}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500 w-16">{totalVol}</span>
                  </div>
                )
              })}
            </div>
            <div className="flex justify-center gap-6 mt-4 text-xs">
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-green-500/50 rounded"></span> Buy Volume</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-red-500/50 rounded"></span> Sell Volume</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 bg-purple-500 rounded"></span> POC</span>
            </div>
          </div>

          {/* Value Areas */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="text-sm text-gray-400 mb-2">Value Area High</div>
              <div className="text-2xl font-bold text-green-400">$95,650</div>
            </div>
            <div className="bg-purple-500/10 rounded-xl p-6 border border-purple-500/30">
              <div className="text-sm text-gray-400 mb-2">Point of Control</div>
              <div className="text-2xl font-bold text-purple-400">${poc.price.toLocaleString()}</div>
            </div>
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="text-sm text-gray-400 mb-2">Value Area Low</div>
              <div className="text-2xl font-bold text-red-400">$95,150</div>
            </div>
          </div>

          {/* Absorption Detection */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-yellow-400" />
              Absorption Detection
            </h3>
            <div className="space-y-3">
              {[
                { level: '$95,400', type: 'buy', strength: 'strong', volume: '2.5M' },
                { level: '$95,200', type: 'sell', strength: 'moderate', volume: '1.8M' },
                { level: '$95,000', type: 'buy', strength: 'strong', volume: '3.2M' }
              ].map((absorption, idx) => (
                <div key={idx} className={`flex items-center justify-between p-4 rounded-lg ${
                  absorption.type === 'buy' ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'
                }`}>
                  <div className="flex items-center gap-3">
                    <span className={absorption.type === 'buy' ? 'text-green-400' : 'text-red-400'}>
                      {absorption.type === 'buy' ? <ArrowUp className="w-5 h-5" /> : <ArrowDown className="w-5 h-5" />}
                    </span>
                    <div>
                      <div className="text-white font-medium">{absorption.level}</div>
                      <div className="text-xs text-gray-400">{absorption.type.toUpperCase()} absorption</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`font-semibold ${
                      absorption.strength === 'strong' ? 'text-yellow-400' : 'text-gray-400'
                    }`}>
                      {absorption.strength.toUpperCase()}
                    </div>
                    <div className="text-sm text-gray-400">{absorption.volume} absorbed</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default OrderFlowAnalyzer
