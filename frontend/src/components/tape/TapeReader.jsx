import React, { useState, useMemo, useEffect, useRef } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Zap,
  Filter,
  ChevronDown,
  Pause,
  Play,
  Settings,
  AlertTriangle,
  Eye,
  Volume2
} from 'lucide-react'

export function TapeReader() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [isPlaying, setIsPlaying] = useState(true)
  const [filterSize, setFilterSize] = useState(0) // Minimum size filter
  const [showBuys, setShowBuys] = useState(true)
  const [showSells, setShowSells] = useState(true)
  const [trades, setTrades] = useState([])
  const [viewMode, setViewMode] = useState('tape') // tape, analysis, alerts
  const tapeRef = useRef(null)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate initial trades
  useEffect(() => {
    const initialTrades = generateTrades(50)
    setTrades(initialTrades)
  }, [selectedToken])

  // Simulate live trades
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      const newTrade = generateTrades(1)[0]
      setTrades(prev => [newTrade, ...prev.slice(0, 199)])
    }, Math.random() * 500 + 100)

    return () => clearInterval(interval)
  }, [isPlaying, selectedToken])

  function generateTrades(count) {
    const basePrice = selectedToken === 'SOL' ? 150.25 : selectedToken === 'ETH' ? 3205.50 : 95250.00

    return Array.from({ length: count }, (_, i) => {
      const isBuy = Math.random() > 0.5
      const size = Math.floor(Math.random() * 5000) + 10
      const price = basePrice + (Math.random() - 0.5) * basePrice * 0.001
      const isLarge = size > 2000
      const isIceberg = Math.random() < 0.05
      const aggressor = isBuy ? 'buyer' : 'seller'

      return {
        id: Date.now() + i + Math.random(),
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }),
        price,
        size,
        side: isBuy ? 'buy' : 'sell',
        value: price * size,
        isLarge,
        isIceberg,
        aggressor,
        exchange: ['Binance', 'Coinbase', 'Kraken', 'Jupiter'][Math.floor(Math.random() * 4)]
      }
    })
  }

  // Filter trades
  const filteredTrades = useMemo(() => {
    return trades.filter(trade => {
      if (trade.size < filterSize) return false
      if (!showBuys && trade.side === 'buy') return false
      if (!showSells && trade.side === 'sell') return false
      return true
    })
  }, [trades, filterSize, showBuys, showSells])

  // Statistics
  const stats = useMemo(() => {
    const recentTrades = filteredTrades.slice(0, 100)
    const buys = recentTrades.filter(t => t.side === 'buy')
    const sells = recentTrades.filter(t => t.side === 'sell')

    const buyVolume = buys.reduce((sum, t) => sum + t.size, 0)
    const sellVolume = sells.reduce((sum, t) => sum + t.size, 0)
    const totalVolume = buyVolume + sellVolume

    const buyValue = buys.reduce((sum, t) => sum + t.value, 0)
    const sellValue = sells.reduce((sum, t) => sum + t.value, 0)

    const largeTrades = recentTrades.filter(t => t.isLarge)
    const avgSize = totalVolume / recentTrades.length || 0

    const vwap = recentTrades.reduce((sum, t) => sum + t.price * t.size, 0) / totalVolume || 0

    return {
      buyVolume,
      sellVolume,
      totalVolume,
      buyValue,
      sellValue,
      buyPct: (buyVolume / totalVolume) * 100 || 50,
      sellPct: (sellVolume / totalVolume) * 100 || 50,
      largeTrades: largeTrades.length,
      avgSize,
      vwap,
      tradesPerMinute: Math.floor(Math.random() * 200) + 100
    }
  }, [filteredTrades])

  const formatSize = (size) => {
    if (size >= 1000000) return `${(size / 1000000).toFixed(2)}M`
    if (size >= 1000) return `${(size / 1000).toFixed(1)}K`
    return size.toString()
  }

  const formatPrice = (price) => {
    if (selectedToken === 'BTC') return price.toFixed(2)
    if (selectedToken === 'ETH') return price.toFixed(2)
    return price.toFixed(4)
  }

  const formatValue = (value) => {
    if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
    if (value >= 1000) return `$${(value / 1000).toFixed(1)}K`
    return `$${value.toFixed(0)}`
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-white">Tape Reader</h2>
            <div className="flex items-center gap-1 ml-2">
              {isPlaying ? (
                <>
                  <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="text-xs text-gray-400">Live</span>
                </>
              ) : (
                <>
                  <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                  <span className="text-xs text-gray-400">Paused</span>
                </>
              )}
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

            {/* Play/Pause */}
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className={`p-1.5 rounded-lg transition-colors ${
                isPlaying ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
              }`}
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* View Mode & Filters */}
        <div className="flex items-center justify-between">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {[
              { id: 'tape', label: 'Time & Sales', icon: Activity },
              { id: 'analysis', label: 'Analysis', icon: TrendingUp },
              { id: 'alerts', label: 'Large Prints', icon: AlertTriangle }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setViewMode(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                  viewMode === id
                    ? 'bg-emerald-500/30 text-emerald-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Quick Filters */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowBuys(!showBuys)}
              className={`px-2 py-1 text-xs rounded ${
                showBuys ? 'bg-green-500/20 text-green-400' : 'bg-white/5 text-gray-500'
              }`}
            >
              Buys
            </button>
            <button
              onClick={() => setShowSells(!showSells)}
              className={`px-2 py-1 text-xs rounded ${
                showSells ? 'bg-red-500/20 text-red-400' : 'bg-white/5 text-gray-500'
              }`}
            >
              Sells
            </button>
            <select
              value={filterSize}
              onChange={(e) => setFilterSize(Number(e.target.value))}
              className="bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white"
            >
              <option value={0}>All sizes</option>
              <option value={100}>100+</option>
              <option value={500}>500+</option>
              <option value={1000}>1K+</option>
              <option value={5000}>5K+</option>
            </select>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Buy Volume</div>
            <div className="text-sm font-medium text-green-400">
              {formatSize(stats.buyVolume)} ({stats.buyPct.toFixed(1)}%)
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Sell Volume</div>
            <div className="text-sm font-medium text-red-400">
              {formatSize(stats.sellVolume)} ({stats.sellPct.toFixed(1)}%)
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Large Trades</div>
            <div className="text-sm font-medium text-yellow-400">
              {stats.largeTrades}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Avg Size</div>
            <div className="text-sm font-medium text-white">
              {formatSize(Math.round(stats.avgSize))}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">VWAP</div>
            <div className="text-sm font-medium text-purple-400">
              ${formatPrice(stats.vwap)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Trades/min</div>
            <div className="text-sm font-medium text-white">
              {stats.tradesPerMinute}
            </div>
          </div>
        </div>

        {/* Buy/Sell Bar */}
        <div className="mt-3 h-2 bg-white/10 rounded-full overflow-hidden flex">
          <div
            className="h-full bg-green-500 transition-all duration-300"
            style={{ width: `${stats.buyPct}%` }}
          />
          <div
            className="h-full bg-red-500 transition-all duration-300"
            style={{ width: `${stats.sellPct}%` }}
          />
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'tape' && (
          <div className="space-y-2">
            {/* Time & Sales Table */}
            <div
              ref={tapeRef}
              className="h-96 overflow-y-auto"
              style={{ scrollBehavior: 'smooth' }}
            >
              <table className="w-full">
                <thead className="sticky top-0 bg-[#0a0e14] z-10">
                  <tr className="text-xs text-gray-500">
                    <th className="text-left py-2 px-2">Time</th>
                    <th className="text-right py-2 px-2">Price</th>
                    <th className="text-right py-2 px-2">Size</th>
                    <th className="text-right py-2 px-2">Value</th>
                    <th className="text-center py-2 px-2">Side</th>
                    <th className="text-left py-2 px-2">Exchange</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades.slice(0, 50).map((trade) => (
                    <tr
                      key={trade.id}
                      className={`text-xs border-t border-white/5 transition-colors ${
                        trade.isLarge ? 'bg-yellow-500/5' : ''
                      } hover:bg-white/5`}
                    >
                      <td className="py-1.5 px-2 text-gray-400 font-mono">
                        {trade.time}
                      </td>
                      <td className={`py-1.5 px-2 text-right font-mono ${
                        trade.side === 'buy' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        ${formatPrice(trade.price)}
                      </td>
                      <td className={`py-1.5 px-2 text-right font-medium ${
                        trade.isLarge ? 'text-yellow-400' : 'text-white'
                      }`}>
                        {formatSize(trade.size)}
                        {trade.isIceberg && <span className="ml-1 text-blue-400">*</span>}
                      </td>
                      <td className="py-1.5 px-2 text-right text-gray-400">
                        {formatValue(trade.value)}
                      </td>
                      <td className="py-1.5 px-2 text-center">
                        <span className={`px-2 py-0.5 rounded text-[10px] ${
                          trade.side === 'buy'
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
                        }`}>
                          {trade.side.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-1.5 px-2 text-gray-500">
                        {trade.exchange}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 text-xs text-gray-500 pt-2">
              <span className="flex items-center gap-1">
                <div className="w-3 h-3 bg-yellow-500/20 rounded"></div>
                Large Print (2K+)
              </span>
              <span className="flex items-center gap-1">
                <span className="text-blue-400">*</span>
                Iceberg Order
              </span>
            </div>
          </div>
        )}

        {viewMode === 'analysis' && (
          <div className="space-y-4">
            {/* Volume by Price */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Recent Trade Distribution</h3>
              <div className="space-y-2">
                {Array.from({ length: 10 }, (_, i) => {
                  const buyVol = Math.floor(Math.random() * 10000) + 1000
                  const sellVol = Math.floor(Math.random() * 10000) + 1000
                  const total = buyVol + sellVol
                  const maxTotal = 20000

                  return (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-16">
                        ${(150 + (9 - i) * 0.1).toFixed(2)}
                      </span>
                      <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden flex">
                        <div
                          className="h-full bg-green-500/60"
                          style={{ width: `${(buyVol / maxTotal) * 100}%` }}
                        />
                        <div
                          className="h-full bg-red-500/60"
                          style={{ width: `${(sellVol / maxTotal) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-12 text-right">
                        {formatSize(total)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Trade Size Distribution */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">Size Buckets</h3>
                <div className="space-y-2">
                  {[
                    { label: '0-100', count: 45, pct: 45 },
                    { label: '100-500', count: 28, pct: 28 },
                    { label: '500-1K', count: 15, pct: 15 },
                    { label: '1K-5K', count: 10, pct: 10 },
                    { label: '5K+', count: 2, pct: 2 }
                  ].map((bucket) => (
                    <div key={bucket.label} className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 w-16">{bucket.label}</span>
                      <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-emerald-500/60 rounded-full"
                          style={{ width: `${bucket.pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-12 text-right">{bucket.count}%</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">Exchange Flow</h3>
                <div className="space-y-2">
                  {[
                    { exchange: 'Binance', volume: 45, color: 'bg-yellow-500' },
                    { exchange: 'Coinbase', volume: 30, color: 'bg-blue-500' },
                    { exchange: 'Kraken', volume: 15, color: 'bg-purple-500' },
                    { exchange: 'Jupiter', volume: 10, color: 'bg-green-500' }
                  ].map((ex) => (
                    <div key={ex.exchange} className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 w-16">{ex.exchange}</span>
                      <div className="flex-1 h-3 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${ex.color}/60 rounded-full`}
                          style={{ width: `${ex.volume}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-12 text-right">{ex.volume}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Trade Velocity */}
            <div className="bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 rounded-lg p-4 border border-emerald-500/20">
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-emerald-400" />
                <h3 className="text-sm font-medium text-white">Trade Flow Analysis</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">Aggressor Bias</div>
                  <div className={`text-sm font-medium ${stats.buyPct > 55 ? 'text-green-400' : stats.sellPct > 55 ? 'text-red-400' : 'text-gray-400'}`}>
                    {stats.buyPct > 55 ? 'Buyers aggressive' : stats.sellPct > 55 ? 'Sellers aggressive' : 'Balanced'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">Flow Quality</div>
                  <div className="text-sm font-medium text-blue-400">
                    {stats.largeTrades > 5 ? 'Institutional activity detected' : 'Retail dominated'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'alerts' && (
          <div className="space-y-4">
            {/* Large Print Alerts */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Large Print Alerts (2K+ Size)</h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {filteredTrades.filter(t => t.isLarge).slice(0, 20).map((trade) => (
                  <div
                    key={trade.id}
                    className={`flex items-center justify-between p-3 rounded-lg ${
                      trade.side === 'buy'
                        ? 'bg-green-500/10 border border-green-500/20'
                        : 'bg-red-500/10 border border-red-500/20'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {trade.side === 'buy' ? (
                        <TrendingUp className="w-5 h-5 text-green-400" />
                      ) : (
                        <TrendingDown className="w-5 h-5 text-red-400" />
                      )}
                      <div>
                        <div className="text-sm font-medium text-white">
                          {formatSize(trade.size)} @ ${formatPrice(trade.price)}
                        </div>
                        <div className="text-xs text-gray-400">
                          {trade.time} via {trade.exchange}
                        </div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-sm font-bold ${trade.side === 'buy' ? 'text-green-400' : 'text-red-400'}`}>
                        {formatValue(trade.value)}
                      </div>
                      <div className="text-xs text-gray-500">
                        {trade.side === 'buy' ? 'BUY' : 'SELL'}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Alert Summary */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-green-500/10 rounded-lg p-4 text-center border border-green-500/20">
                <div className="text-2xl font-bold text-green-400">
                  {filteredTrades.filter(t => t.isLarge && t.side === 'buy').length}
                </div>
                <div className="text-xs text-gray-400 mt-1">Large Buys</div>
              </div>
              <div className="bg-red-500/10 rounded-lg p-4 text-center border border-red-500/20">
                <div className="text-2xl font-bold text-red-400">
                  {filteredTrades.filter(t => t.isLarge && t.side === 'sell').length}
                </div>
                <div className="text-xs text-gray-400 mt-1">Large Sells</div>
              </div>
              <div className="bg-blue-500/10 rounded-lg p-4 text-center border border-blue-500/20">
                <div className="text-2xl font-bold text-blue-400">
                  {filteredTrades.filter(t => t.isIceberg).length}
                </div>
                <div className="text-xs text-gray-400 mt-1">Iceberg Orders</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TapeReader
