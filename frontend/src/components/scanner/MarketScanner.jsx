import React, { useState, useMemo, useEffect } from 'react'
import {
  Radar, TrendingUp, TrendingDown, Volume2, Zap, AlertTriangle,
  Filter, RefreshCw, Download, Bell, Eye, Star, Clock, Target,
  ArrowUpRight, ArrowDownRight, BarChart3, Activity, Flame,
  ChevronDown, Search, Settings, Play, Pause
} from 'lucide-react'

const SCAN_TYPES = [
  { id: 'gainers', name: 'Top Gainers', icon: TrendingUp, color: 'text-green-400' },
  { id: 'losers', name: 'Top Losers', icon: TrendingDown, color: 'text-red-400' },
  { id: 'volume', name: 'Volume Spike', icon: Volume2, color: 'text-blue-400' },
  { id: 'momentum', name: 'Momentum', icon: Zap, color: 'text-yellow-400' },
  { id: 'breakout', name: 'Breakouts', icon: Target, color: 'text-purple-400' },
  { id: 'oversold', name: 'Oversold', icon: ArrowDownRight, color: 'text-cyan-400' },
  { id: 'overbought', name: 'Overbought', icon: ArrowUpRight, color: 'text-orange-400' },
  { id: 'unusual', name: 'Unusual Activity', icon: AlertTriangle, color: 'text-pink-400' }
]

const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d']

const CATEGORIES = ['All', 'Layer 1', 'Layer 2', 'DeFi', 'Meme', 'AI', 'Gaming', 'Exchange']

// Generate mock scan results
const generateScanResults = (scanType) => {
  const tokens = [
    { symbol: 'BTC', name: 'Bitcoin', price: 95420, marketCap: 1890000000000 },
    { symbol: 'ETH', name: 'Ethereum', price: 3280, marketCap: 394000000000 },
    { symbol: 'SOL', name: 'Solana', price: 185, marketCap: 85000000000 },
    { symbol: 'BNB', name: 'BNB', price: 680, marketCap: 98000000000 },
    { symbol: 'XRP', name: 'Ripple', price: 2.45, marketCap: 135000000000 },
    { symbol: 'DOGE', name: 'Dogecoin', price: 0.38, marketCap: 55000000000 },
    { symbol: 'AVAX', name: 'Avalanche', price: 38.50, marketCap: 15000000000 },
    { symbol: 'LINK', name: 'Chainlink', price: 22.40, marketCap: 13500000000 },
    { symbol: 'DOT', name: 'Polkadot', price: 7.85, marketCap: 11000000000 },
    { symbol: 'ADA', name: 'Cardano', price: 0.95, marketCap: 33000000000 },
    { symbol: 'PEPE', name: 'Pepe', price: 0.000018, marketCap: 7500000000 },
    { symbol: 'UNI', name: 'Uniswap', price: 13.20, marketCap: 9900000000 },
    { symbol: 'AAVE', name: 'Aave', price: 285, marketCap: 4200000000 },
    { symbol: 'FET', name: 'Fetch.ai', price: 2.15, marketCap: 5400000000 },
    { symbol: 'RENDER', name: 'Render', price: 8.50, marketCap: 4400000000 }
  ]

  return tokens.slice(0, Math.floor(Math.random() * 5) + 5).map((token, idx) => {
    let change, volume, signal, strength

    switch (scanType) {
      case 'gainers':
        change = 5 + Math.random() * 20
        volume = 100 + Math.random() * 400
        signal = 'Price surge detected'
        strength = change > 10 ? 'strong' : 'moderate'
        break
      case 'losers':
        change = -(5 + Math.random() * 15)
        volume = 100 + Math.random() * 200
        signal = 'Sharp decline'
        strength = change < -10 ? 'strong' : 'moderate'
        break
      case 'volume':
        change = (Math.random() - 0.5) * 10
        volume = 200 + Math.random() * 800
        signal = 'Volume spike ' + volume.toFixed(0) + '%'
        strength = volume > 500 ? 'strong' : 'moderate'
        break
      case 'momentum':
        change = 2 + Math.random() * 12
        volume = 100 + Math.random() * 200
        signal = 'Strong momentum'
        strength = change > 8 ? 'strong' : 'moderate'
        break
      case 'breakout':
        change = 3 + Math.random() * 15
        volume = 150 + Math.random() * 350
        signal = 'Resistance breakout'
        strength = change > 8 && volume > 300 ? 'strong' : 'moderate'
        break
      case 'oversold':
        change = -(8 + Math.random() * 12)
        volume = 80 + Math.random() * 150
        signal = 'RSI < 30'
        strength = change < -15 ? 'strong' : 'moderate'
        break
      case 'overbought':
        change = 8 + Math.random() * 15
        volume = 100 + Math.random() * 200
        signal = 'RSI > 70'
        strength = change > 15 ? 'strong' : 'moderate'
        break
      case 'unusual':
        change = (Math.random() - 0.5) * 20
        volume = 300 + Math.random() * 700
        signal = 'Unusual activity detected'
        strength = Math.abs(change) > 10 || volume > 500 ? 'strong' : 'moderate'
        break
      default:
        change = (Math.random() - 0.5) * 10
        volume = 100 + Math.random() * 100
        signal = 'Signal detected'
        strength = 'moderate'
    }

    return {
      ...token,
      change,
      volume,
      signal,
      strength,
      time: new Date(Date.now() - Math.random() * 3600000).toLocaleTimeString(),
      rsi: 30 + Math.random() * 40,
      macd: Math.random() > 0.5 ? 'bullish' : 'bearish'
    }
  }).sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
}

export function MarketScanner() {
  const [activeScan, setActiveScan] = useState('gainers')
  const [timeframe, setTimeframe] = useState('1h')
  const [category, setCategory] = useState('All')
  const [isScanning, setIsScanning] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [minVolume, setMinVolume] = useState(0)
  const [minMarketCap, setMinMarketCap] = useState(0)
  const [showFilters, setShowFilters] = useState(false)

  const [scanResults, setScanResults] = useState(() => generateScanResults('gainers'))
  const [watchlist, setWatchlist] = useState([])

  // Simulate live scanning
  useEffect(() => {
    if (!isScanning) return

    const interval = setInterval(() => {
      setScanResults(generateScanResults(activeScan))
    }, 10000)

    return () => clearInterval(interval)
  }, [isScanning, activeScan])

  // Update results when scan type changes
  useEffect(() => {
    setScanResults(generateScanResults(activeScan))
  }, [activeScan])

  // Filter results
  const filteredResults = useMemo(() => {
    return scanResults.filter(result => {
      if (searchQuery && !result.symbol.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !result.name.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false
      }
      if (minVolume && result.volume < minVolume) return false
      if (minMarketCap && result.marketCap < minMarketCap) return false
      return true
    })
  }, [scanResults, searchQuery, minVolume, minMarketCap])

  const toggleWatchlist = (symbol) => {
    if (watchlist.includes(symbol)) {
      setWatchlist(watchlist.filter(s => s !== symbol))
    } else {
      setWatchlist([...watchlist, symbol])
    }
  }

  const activeScanType = SCAN_TYPES.find(s => s.id === activeScan)
  const ActiveIcon = activeScanType?.icon || Radar

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Radar className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Market Scanner</h1>
            <p className="text-sm text-gray-400">Real-time market scanning and alerts</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsScanning(!isScanning)}
            className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 ${
              isScanning ? 'bg-green-500 text-black' : 'bg-white/10 text-white'
            }`}
          >
            {isScanning ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            {isScanning ? 'Scanning' : 'Paused'}
          </button>
          <button className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
            <RefreshCw className={`w-5 h-5 text-gray-400 ${isScanning ? 'animate-spin' : ''}`} />
          </button>
          <button className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
            <Download className="w-5 h-5 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Scan Type Selector */}
      <div className="flex flex-wrap gap-2 mb-6">
        {SCAN_TYPES.map(scan => {
          const Icon = scan.icon
          return (
            <button
              key={scan.id}
              onClick={() => setActiveScan(scan.id)}
              className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors ${
                activeScan === scan.id
                  ? 'bg-purple-500 text-white'
                  : 'bg-white/10 text-gray-300 hover:bg-white/20'
              }`}
            >
              <Icon className={`w-4 h-4 ${activeScan === scan.id ? 'text-white' : scan.color}`} />
              {scan.name}
            </button>
          )
        })}
      </div>

      {/* Controls Row */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-gray-400" />
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1 rounded text-sm ${
                timeframe === tf ? 'bg-purple-500 text-white' : 'bg-white/10 text-gray-300 hover:bg-white/20'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>

        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search tokens..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-white/10 border border-white/20 rounded-lg text-white"
          />
        </div>

        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
            showFilters ? 'bg-purple-500 text-white' : 'bg-white/10 text-gray-300'
          }`}
        >
          <Filter className="w-4 h-4" />
          Filters
          <ChevronDown className={`w-4 h-4 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
        </button>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-white/5 rounded-xl border border-white/10 p-4 mb-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-gray-400 block mb-2">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
              >
                {CATEGORIES.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-2">Min Volume Change %</label>
              <input
                type="number"
                value={minVolume}
                onChange={(e) => setMinVolume(Number(e.target.value))}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
                placeholder="0"
              />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-2">Min Market Cap</label>
              <select
                value={minMarketCap}
                onChange={(e) => setMinMarketCap(Number(e.target.value))}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
              >
                <option value={0}>Any</option>
                <option value={1000000000}>$1B+</option>
                <option value={10000000000}>$10B+</option>
                <option value={50000000000}>$50B+</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-2">Signal Strength</label>
              <select className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white">
                <option value="all">All</option>
                <option value="strong">Strong Only</option>
                <option value="moderate">Moderate+</option>
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Results Summary */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-4">
          <div className={`flex items-center gap-2 ${activeScanType?.color}`}>
            <ActiveIcon className="w-5 h-5" />
            <span className="font-semibold text-white">{activeScanType?.name}</span>
          </div>
          <span className="text-gray-400">|</span>
          <span className="text-gray-400">{filteredResults.length} results</span>
          <span className="text-gray-400">|</span>
          <span className="text-gray-400">{timeframe} timeframe</span>
        </div>
        {isScanning && (
          <div className="flex items-center gap-2 text-sm text-green-400">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            Live scanning
          </div>
        )}
      </div>

      {/* Results Table */}
      <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-white/10 bg-white/5">
              <th className="p-4 w-8"></th>
              <th className="p-4">Token</th>
              <th className="p-4">Price</th>
              <th className="p-4">Change</th>
              <th className="p-4">Volume</th>
              <th className="p-4">Signal</th>
              <th className="p-4">Strength</th>
              <th className="p-4">RSI</th>
              <th className="p-4">Time</th>
              <th className="p-4">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredResults.map((result, idx) => (
              <tr key={result.symbol} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                <td className="p-4">
                  <button
                    onClick={() => toggleWatchlist(result.symbol)}
                    className={watchlist.includes(result.symbol) ? 'text-yellow-400' : 'text-gray-500 hover:text-yellow-400'}
                  >
                    <Star className={`w-4 h-4 ${watchlist.includes(result.symbol) ? 'fill-current' : ''}`} />
                  </button>
                </td>
                <td className="p-4">
                  <div className="flex items-center gap-2">
                    <div>
                      <div className="font-semibold text-white">{result.symbol}</div>
                      <div className="text-xs text-gray-500">{result.name}</div>
                    </div>
                  </div>
                </td>
                <td className="p-4 text-white font-mono">
                  ${result.price < 1 ? result.price.toFixed(6) : result.price.toLocaleString()}
                </td>
                <td className="p-4">
                  <span className={`flex items-center gap-1 font-semibold ${
                    result.change >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {result.change >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                    {result.change >= 0 ? '+' : ''}{result.change.toFixed(2)}%
                  </span>
                </td>
                <td className="p-4">
                  <span className={`font-medium ${result.volume > 200 ? 'text-blue-400' : 'text-gray-300'}`}>
                    {result.volume.toFixed(0)}%
                  </span>
                </td>
                <td className="p-4">
                  <span className="text-gray-300 text-sm">{result.signal}</span>
                </td>
                <td className="p-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    result.strength === 'strong'
                      ? 'bg-green-500/20 text-green-400'
                      : 'bg-yellow-500/20 text-yellow-400'
                  }`}>
                    {result.strength.toUpperCase()}
                  </span>
                </td>
                <td className="p-4">
                  <span className={`font-mono text-sm ${
                    result.rsi < 30 ? 'text-green-400' :
                    result.rsi > 70 ? 'text-red-400' : 'text-gray-300'
                  }`}>
                    {result.rsi.toFixed(1)}
                  </span>
                </td>
                <td className="p-4 text-gray-400 text-sm">{result.time}</td>
                <td className="p-4">
                  <div className="flex gap-2">
                    <button className="p-1.5 bg-white/10 rounded hover:bg-white/20" title="View Chart">
                      <Eye className="w-4 h-4 text-gray-400" />
                    </button>
                    <button className="p-1.5 bg-white/10 rounded hover:bg-white/20" title="Set Alert">
                      <Bell className="w-4 h-4 text-gray-400" />
                    </button>
                    <button className="p-1.5 bg-purple-500/20 rounded hover:bg-purple-500/30" title="Trade">
                      <Zap className="w-4 h-4 text-purple-400" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Watchlist Summary */}
      {watchlist.length > 0 && (
        <div className="mt-6 bg-yellow-500/10 rounded-xl border border-yellow-500/30 p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Star className="w-5 h-5 text-yellow-400 fill-current" />
              Watchlist ({watchlist.length})
            </h3>
            <button className="text-sm text-yellow-400 hover:text-yellow-300">
              Clear All
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {watchlist.map(symbol => (
              <span
                key={symbol}
                className="px-3 py-1.5 bg-yellow-500/20 text-yellow-400 rounded-lg text-sm flex items-center gap-2"
              >
                {symbol}
                <button onClick={() => toggleWatchlist(symbol)} className="hover:text-white">
                  &times;
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Quick Stats */}
      <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <span className="text-sm text-gray-400">Strong Bullish</span>
          </div>
          <div className="text-2xl font-bold text-green-400">
            {filteredResults.filter(r => r.change > 5 && r.strength === 'strong').length}
          </div>
        </div>
        <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-5 h-5 text-red-400" />
            <span className="text-sm text-gray-400">Strong Bearish</span>
          </div>
          <div className="text-2xl font-bold text-red-400">
            {filteredResults.filter(r => r.change < -5 && r.strength === 'strong').length}
          </div>
        </div>
        <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Volume2 className="w-5 h-5 text-blue-400" />
            <span className="text-sm text-gray-400">High Volume</span>
          </div>
          <div className="text-2xl font-bold text-blue-400">
            {filteredResults.filter(r => r.volume > 200).length}
          </div>
        </div>
        <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
          <div className="flex items-center gap-2 mb-2">
            <Flame className="w-5 h-5 text-purple-400" />
            <span className="text-sm text-gray-400">Hot Signals</span>
          </div>
          <div className="text-2xl font-bold text-purple-400">
            {filteredResults.filter(r => r.strength === 'strong').length}
          </div>
        </div>
      </div>
    </div>
  )
}

export default MarketScanner
