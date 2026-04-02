import React, { useState, useMemo, useEffect } from 'react'
import {
  Filter,
  TrendingUp,
  TrendingDown,
  Activity,
  ChevronDown,
  Settings,
  Download,
  Pause,
  Play,
  Search,
  X
} from 'lucide-react'

export function TimeSalesFilter() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [isPlaying, setIsPlaying] = useState(true)
  const [trades, setTrades] = useState([])

  // Filter states
  const [filters, setFilters] = useState({
    minSize: 0,
    maxSize: Infinity,
    side: 'all', // all, buy, sell
    exchange: 'all',
    showLargeOnly: false,
    minValue: 0,
    priceRange: { min: 0, max: Infinity }
  })

  const [activeFilters, setActiveFilters] = useState([])

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const exchanges = ['Binance', 'Coinbase', 'Kraken', 'Jupiter', 'Raydium']

  // Generate trades
  useEffect(() => {
    const generateTrade = () => {
      const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : selectedToken === 'BTC' ? 95000 : 0.05
      const isBuy = Math.random() > 0.5
      const size = Math.floor(Math.random() * 10000) + 10
      const price = basePrice + (Math.random() - 0.5) * basePrice * 0.002

      return {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }),
        price,
        size,
        side: isBuy ? 'buy' : 'sell',
        value: price * size,
        exchange: exchanges[Math.floor(Math.random() * exchanges.length)],
        isLarge: size > 2000,
        aggressor: isBuy ? 'buyer' : 'seller'
      }
    }

    setTrades(Array.from({ length: 100 }, generateTrade))
  }, [selectedToken])

  // Add new trades
  useEffect(() => {
    if (!isPlaying) return

    const interval = setInterval(() => {
      const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : selectedToken === 'BTC' ? 95000 : 0.05
      const isBuy = Math.random() > 0.5
      const size = Math.floor(Math.random() * 10000) + 10
      const price = basePrice + (Math.random() - 0.5) * basePrice * 0.002

      const newTrade = {
        id: Date.now() + Math.random(),
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }),
        price,
        size,
        side: isBuy ? 'buy' : 'sell',
        value: price * size,
        exchange: exchanges[Math.floor(Math.random() * exchanges.length)],
        isLarge: size > 2000,
        aggressor: isBuy ? 'buyer' : 'seller'
      }

      setTrades(prev => [newTrade, ...prev.slice(0, 199)])
    }, Math.random() * 300 + 100)

    return () => clearInterval(interval)
  }, [isPlaying, selectedToken])

  // Apply filters
  const filteredTrades = useMemo(() => {
    return trades.filter(trade => {
      if (trade.size < filters.minSize) return false
      if (trade.size > filters.maxSize) return false
      if (filters.side !== 'all' && trade.side !== filters.side) return false
      if (filters.exchange !== 'all' && trade.exchange !== filters.exchange) return false
      if (filters.showLargeOnly && !trade.isLarge) return false
      if (trade.value < filters.minValue) return false
      if (trade.price < filters.priceRange.min || trade.price > filters.priceRange.max) return false
      return true
    })
  }, [trades, filters])

  // Update active filters display
  useEffect(() => {
    const active = []
    if (filters.minSize > 0) active.push({ key: 'minSize', label: `Min Size: ${filters.minSize}` })
    if (filters.maxSize < Infinity) active.push({ key: 'maxSize', label: `Max Size: ${filters.maxSize}` })
    if (filters.side !== 'all') active.push({ key: 'side', label: `Side: ${filters.side}` })
    if (filters.exchange !== 'all') active.push({ key: 'exchange', label: `Exchange: ${filters.exchange}` })
    if (filters.showLargeOnly) active.push({ key: 'large', label: 'Large Only' })
    if (filters.minValue > 0) active.push({ key: 'minValue', label: `Min Value: $${filters.minValue}` })
    setActiveFilters(active)
  }, [filters])

  // Clear single filter
  const clearFilter = (key) => {
    setFilters(prev => {
      const newFilters = { ...prev }
      switch (key) {
        case 'minSize': newFilters.minSize = 0; break
        case 'maxSize': newFilters.maxSize = Infinity; break
        case 'side': newFilters.side = 'all'; break
        case 'exchange': newFilters.exchange = 'all'; break
        case 'large': newFilters.showLargeOnly = false; break
        case 'minValue': newFilters.minValue = 0; break
        default: break
      }
      return newFilters
    })
  }

  // Clear all filters
  const clearAllFilters = () => {
    setFilters({
      minSize: 0,
      maxSize: Infinity,
      side: 'all',
      exchange: 'all',
      showLargeOnly: false,
      minValue: 0,
      priceRange: { min: 0, max: Infinity }
    })
  }

  // Statistics
  const stats = useMemo(() => {
    const buys = filteredTrades.filter(t => t.side === 'buy')
    const sells = filteredTrades.filter(t => t.side === 'sell')

    const buyVolume = buys.reduce((sum, t) => sum + t.size, 0)
    const sellVolume = sells.reduce((sum, t) => sum + t.size, 0)
    const totalVolume = buyVolume + sellVolume

    const buyValue = buys.reduce((sum, t) => sum + t.value, 0)
    const sellValue = sells.reduce((sum, t) => sum + t.value, 0)

    const largeTrades = filteredTrades.filter(t => t.isLarge)

    return {
      totalTrades: filteredTrades.length,
      buyVolume,
      sellVolume,
      totalVolume,
      buyValue,
      sellValue,
      buyPct: totalVolume > 0 ? (buyVolume / totalVolume) * 100 : 50,
      largeTrades: largeTrades.length
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
            <Filter className="w-5 h-5 text-teal-400" />
            <h2 className="text-lg font-semibold text-white">Time &amp; Sales Filter</h2>
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

        {/* Filter Controls */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
          {/* Min Size */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">Min Size</label>
            <select
              value={filters.minSize}
              onChange={(e) => setFilters(prev => ({ ...prev, minSize: Number(e.target.value) }))}
              className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-xs text-white"
            >
              <option value={0}>Any</option>
              <option value={100}>100+</option>
              <option value={500}>500+</option>
              <option value={1000}>1K+</option>
              <option value={5000}>5K+</option>
              <option value={10000}>10K+</option>
            </select>
          </div>

          {/* Side */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">Side</label>
            <select
              value={filters.side}
              onChange={(e) => setFilters(prev => ({ ...prev, side: e.target.value }))}
              className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-xs text-white"
            >
              <option value="all">All</option>
              <option value="buy">Buys Only</option>
              <option value="sell">Sells Only</option>
            </select>
          </div>

          {/* Exchange */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">Exchange</label>
            <select
              value={filters.exchange}
              onChange={(e) => setFilters(prev => ({ ...prev, exchange: e.target.value }))}
              className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-xs text-white"
            >
              <option value="all">All</option>
              {exchanges.map(ex => (
                <option key={ex} value={ex}>{ex}</option>
              ))}
            </select>
          </div>

          {/* Min Value */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">Min Value</label>
            <select
              value={filters.minValue}
              onChange={(e) => setFilters(prev => ({ ...prev, minValue: Number(e.target.value) }))}
              className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-xs text-white"
            >
              <option value={0}>Any</option>
              <option value={1000}>$1K+</option>
              <option value={5000}>$5K+</option>
              <option value={10000}>$10K+</option>
              <option value={50000}>$50K+</option>
              <option value={100000}>$100K+</option>
            </select>
          </div>

          {/* Large Only Toggle */}
          <div>
            <label className="text-xs text-gray-500 block mb-1">Type</label>
            <button
              onClick={() => setFilters(prev => ({ ...prev, showLargeOnly: !prev.showLargeOnly }))}
              className={`w-full px-3 py-1.5 text-xs rounded transition-colors ${
                filters.showLargeOnly
                  ? 'bg-teal-500/30 text-teal-400 border border-teal-500/50'
                  : 'bg-white/5 text-gray-400 border border-white/10'
              }`}
            >
              {filters.showLargeOnly ? 'Large Only' : 'All Types'}
            </button>
          </div>

          {/* Clear All */}
          <div className="flex items-end">
            <button
              onClick={clearAllFilters}
              className="w-full px-3 py-1.5 text-xs bg-white/5 text-gray-400 rounded hover:bg-white/10 transition-colors"
            >
              Clear All
            </button>
          </div>
        </div>

        {/* Active Filters */}
        {activeFilters.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {activeFilters.map(filter => (
              <span
                key={filter.key}
                className="flex items-center gap-1 px-2 py-1 text-xs bg-teal-500/20 text-teal-400 rounded"
              >
                {filter.label}
                <button onClick={() => clearFilter(filter.key)} className="hover:text-white">
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Showing</div>
            <div className="text-sm font-medium text-white">
              {filteredTrades.length} / {trades.length}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Buy Volume</div>
            <div className="text-sm font-medium text-green-400">
              {formatSize(stats.buyVolume)} ({stats.buyPct.toFixed(1)}%)
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Sell Volume</div>
            <div className="text-sm font-medium text-red-400">
              {formatSize(stats.sellVolume)} ({(100 - stats.buyPct).toFixed(1)}%)
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Buy Value</div>
            <div className="text-sm font-medium text-green-400">
              {formatValue(stats.buyValue)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Sell Value</div>
            <div className="text-sm font-medium text-red-400">
              {formatValue(stats.sellValue)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Large Trades</div>
            <div className="text-sm font-medium text-yellow-400">
              {stats.largeTrades}
            </div>
          </div>
        </div>

        {/* Volume Bar */}
        <div className="mt-3 h-2 bg-white/10 rounded-full overflow-hidden flex">
          <div
            className="h-full bg-green-500 transition-all duration-300"
            style={{ width: `${stats.buyPct}%` }}
          />
          <div
            className="h-full bg-red-500 transition-all duration-300"
            style={{ width: `${100 - stats.buyPct}%` }}
          />
        </div>
      </div>

      {/* Filtered Trade List */}
      <div className="p-4">
        <div className="h-80 overflow-y-auto">
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

          {filteredTrades.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No trades match current filters
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default TimeSalesFilter
