import React, { useState, useMemo, useEffect } from 'react'
import {
  Zap,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Filter,
  Star,
  AlertTriangle,
  BarChart3,
  Target
} from 'lucide-react'

export function MomentumScanner() {
  const [selectedTimeframe, setSelectedTimeframe] = useState('1h')
  const [sortBy, setSortBy] = useState('momentum')
  const [filterType, setFilterType] = useState('all') // all, bullish, bearish
  const [viewMode, setViewMode] = useState('scanner') // scanner, heatmap, rankings
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [watchlist, setWatchlist] = useState(['SOL', 'ETH'])

  const timeframes = ['5m', '15m', '1h', '4h', '1d']

  const tokens = [
    'SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH',
    'RAY', 'ORCA', 'MNGO', 'SRM', 'FIDA', 'STEP', 'COPE', 'ATLAS'
  ]

  // Generate mock momentum data
  const momentumData = useMemo(() => {
    return tokens.map(token => {
      const rsi = Math.floor(Math.random() * 100)
      const macdHistogram = (Math.random() - 0.5) * 10
      const adx = Math.floor(Math.random() * 60) + 10
      const mfi = Math.floor(Math.random() * 100)
      const stochK = Math.floor(Math.random() * 100)
      const stochD = Math.floor(Math.random() * 100)
      const cci = Math.floor(Math.random() * 400) - 200
      const williams = -Math.floor(Math.random() * 100)
      const roc = (Math.random() - 0.5) * 20
      const momentum = (Math.random() - 0.5) * 30

      const price = token === 'BTC' ? 95000 + Math.random() * 5000 :
                   token === 'ETH' ? 3200 + Math.random() * 300 :
                   token === 'SOL' ? 175 + Math.random() * 15 :
                   Math.random() * 50

      const priceChange = (Math.random() - 0.5) * 20
      const volume24h = Math.floor(Math.random() * 500000000) + 10000000
      const volumeChange = (Math.random() - 0.5) * 100

      // Calculate composite score
      const bullishSignals = [
        rsi < 30, rsi > 50 && rsi < 70,
        macdHistogram > 0,
        adx > 25,
        mfi < 20, mfi > 50 && mfi < 80,
        stochK > stochD && stochK < 80,
        cci > 0 && cci < 100,
        williams > -50,
        roc > 0,
        momentum > 0
      ].filter(Boolean).length

      const bearishSignals = [
        rsi > 70, rsi < 50 && rsi > 30,
        macdHistogram < 0,
        adx > 25,
        mfi > 80, mfi < 50 && mfi > 20,
        stochK < stochD && stochK > 20,
        cci < 0 && cci > -100,
        williams < -50,
        roc < 0,
        momentum < 0
      ].filter(Boolean).length

      const bias = bullishSignals > bearishSignals ? 'bullish' :
                   bearishSignals > bullishSignals ? 'bearish' : 'neutral'

      const strength = Math.abs(bullishSignals - bearishSignals) / 10 * 100

      return {
        token,
        price,
        priceChange,
        volume24h,
        volumeChange,
        rsi,
        macdHistogram,
        adx,
        mfi,
        stochK,
        stochD,
        cci,
        williams,
        roc,
        momentum,
        bullishSignals,
        bearishSignals,
        bias,
        strength,
        inWatchlist: watchlist.includes(token)
      }
    }).sort((a, b) => {
      switch(sortBy) {
        case 'momentum': return Math.abs(b.momentum) - Math.abs(a.momentum)
        case 'strength': return b.strength - a.strength
        case 'rsi': return b.rsi - a.rsi
        case 'volume': return b.volume24h - a.volume24h
        case 'change': return b.priceChange - a.priceChange
        default: return 0
      }
    }).filter(item => {
      if (filterType === 'bullish') return item.bias === 'bullish'
      if (filterType === 'bearish') return item.bias === 'bearish'
      return true
    })
  }, [selectedTimeframe, sortBy, filterType, watchlist])

  // Top movers
  const topBullish = useMemo(() =>
    [...momentumData].filter(t => t.bias === 'bullish').sort((a, b) => b.strength - a.strength).slice(0, 5),
    [momentumData]
  )

  const topBearish = useMemo(() =>
    [...momentumData].filter(t => t.bias === 'bearish').sort((a, b) => b.strength - a.strength).slice(0, 5),
    [momentumData]
  )

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const toggleWatchlist = (token) => {
    setWatchlist(prev =>
      prev.includes(token)
        ? prev.filter(t => t !== token)
        : [...prev, token]
    )
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(2)
  }

  const getIndicatorColor = (value, type) => {
    switch(type) {
      case 'rsi':
        if (value > 70) return 'text-red-400'
        if (value < 30) return 'text-green-400'
        return 'text-gray-400'
      case 'macd':
        return value > 0 ? 'text-green-400' : 'text-red-400'
      case 'adx':
        if (value > 40) return 'text-yellow-400'
        if (value > 25) return 'text-green-400'
        return 'text-gray-400'
      case 'mfi':
        if (value > 80) return 'text-red-400'
        if (value < 20) return 'text-green-400'
        return 'text-gray-400'
      default:
        return 'text-gray-400'
    }
  }

  const getBiasIcon = (bias) => {
    switch(bias) {
      case 'bullish': return <ArrowUpRight className="w-4 h-4 text-green-400" />
      case 'bearish': return <ArrowDownRight className="w-4 h-4 text-red-400" />
      default: return <Activity className="w-4 h-4 text-yellow-400" />
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Zap className="w-6 h-6 text-yellow-400" />
          <h2 className="text-xl font-bold text-white">Momentum Scanner</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
          <button
            onClick={handleRefresh}
            className={`p-2 bg-white/5 rounded-lg hover:bg-white/10 ${isRefreshing ? 'animate-spin' : ''}`}
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>
      </div>

      {/* Top Movers Summary */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <span className="text-green-400 font-medium">Top Bullish</span>
          </div>
          <div className="space-y-2">
            {topBullish.map(item => (
              <div key={item.token} className="flex items-center justify-between text-sm">
                <span className="text-white">{item.token}</span>
                <span className="text-green-400">{item.strength.toFixed(0)}% strength</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
          <div className="flex items-center gap-2 mb-3">
            <TrendingDown className="w-5 h-5 text-red-400" />
            <span className="text-red-400 font-medium">Top Bearish</span>
          </div>
          <div className="space-y-2">
            {topBearish.map(item => (
              <div key={item.token} className="flex items-center justify-between text-sm">
                <span className="text-white">{item.token}</span>
                <span className="text-red-400">{item.strength.toFixed(0)}% strength</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Filters and View Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div className="flex gap-2">
          {['scanner', 'heatmap', 'rankings'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                viewMode === mode
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                  : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
              }`}
            >
              {mode}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            <option value="all">All</option>
            <option value="bullish">Bullish Only</option>
            <option value="bearish">Bearish Only</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            <option value="momentum">Sort: Momentum</option>
            <option value="strength">Sort: Strength</option>
            <option value="rsi">Sort: RSI</option>
            <option value="volume">Sort: Volume</option>
            <option value="change">Sort: Price Change</option>
          </select>
        </div>
      </div>

      {/* Scanner View */}
      {viewMode === 'scanner' && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-gray-400 text-sm border-b border-white/10">
                <th className="text-left py-3 px-2">Token</th>
                <th className="text-right py-3 px-2">Price</th>
                <th className="text-right py-3 px-2">24h</th>
                <th className="text-center py-3 px-2">RSI</th>
                <th className="text-center py-3 px-2">MACD</th>
                <th className="text-center py-3 px-2">ADX</th>
                <th className="text-center py-3 px-2">MFI</th>
                <th className="text-center py-3 px-2">Bias</th>
                <th className="text-center py-3 px-2">Strength</th>
                <th className="text-center py-3 px-2"></th>
              </tr>
            </thead>
            <tbody>
              {momentumData.map(item => (
                <tr key={item.token} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-3 px-2">
                    <span className="text-white font-medium">{item.token}</span>
                  </td>
                  <td className="text-right py-3 px-2 text-white">
                    ${item.price < 1 ? item.price.toFixed(6) : item.price.toFixed(2)}
                  </td>
                  <td className={`text-right py-3 px-2 ${item.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {item.priceChange >= 0 ? '+' : ''}{item.priceChange.toFixed(2)}%
                  </td>
                  <td className={`text-center py-3 px-2 ${getIndicatorColor(item.rsi, 'rsi')}`}>
                    {item.rsi}
                  </td>
                  <td className={`text-center py-3 px-2 ${getIndicatorColor(item.macdHistogram, 'macd')}`}>
                    {item.macdHistogram.toFixed(2)}
                  </td>
                  <td className={`text-center py-3 px-2 ${getIndicatorColor(item.adx, 'adx')}`}>
                    {item.adx}
                  </td>
                  <td className={`text-center py-3 px-2 ${getIndicatorColor(item.mfi, 'mfi')}`}>
                    {item.mfi}
                  </td>
                  <td className="text-center py-3 px-2">
                    <div className="flex items-center justify-center gap-1">
                      {getBiasIcon(item.bias)}
                      <span className={`text-sm capitalize ${
                        item.bias === 'bullish' ? 'text-green-400' :
                        item.bias === 'bearish' ? 'text-red-400' : 'text-yellow-400'
                      }`}>
                        {item.bias}
                      </span>
                    </div>
                  </td>
                  <td className="text-center py-3 px-2">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-16 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            item.bias === 'bullish' ? 'bg-green-500' :
                            item.bias === 'bearish' ? 'bg-red-500' : 'bg-yellow-500'
                          }`}
                          style={{ width: `${item.strength}%` }}
                        />
                      </div>
                      <span className="text-gray-400 text-sm">{item.strength.toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="text-center py-3 px-2">
                    <button
                      onClick={() => toggleWatchlist(item.token)}
                      className={`p-1 rounded ${item.inWatchlist ? 'text-yellow-400' : 'text-gray-500 hover:text-gray-300'}`}
                    >
                      <Star className="w-4 h-4" fill={item.inWatchlist ? 'currentColor' : 'none'} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Heatmap View */}
      {viewMode === 'heatmap' && (
        <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
          {momentumData.map(item => {
            const intensity = item.strength / 100
            const bgColor = item.bias === 'bullish'
              ? `rgba(34, 197, 94, ${0.2 + intensity * 0.5})`
              : item.bias === 'bearish'
              ? `rgba(239, 68, 68, ${0.2 + intensity * 0.5})`
              : `rgba(234, 179, 8, ${0.2 + intensity * 0.3})`

            return (
              <div
                key={item.token}
                className="p-3 rounded-lg border border-white/10 text-center"
                style={{ backgroundColor: bgColor }}
              >
                <div className="text-white font-medium text-sm">{item.token}</div>
                <div className={`text-lg font-bold ${
                  item.priceChange >= 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {item.priceChange >= 0 ? '+' : ''}{item.priceChange.toFixed(1)}%
                </div>
                <div className="text-gray-400 text-xs mt-1">
                  RSI: {item.rsi}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Rankings View */}
      {viewMode === 'rankings' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* RSI Rankings */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              RSI Extremes
            </h3>
            <div className="space-y-2">
              {[...momentumData]
                .sort((a, b) => Math.abs(50 - a.rsi) > Math.abs(50 - b.rsi) ? -1 : 1)
                .slice(0, 5)
                .map(item => (
                  <div key={item.token} className="flex items-center justify-between text-sm">
                    <span className="text-white">{item.token}</span>
                    <span className={getIndicatorColor(item.rsi, 'rsi')}>
                      RSI: {item.rsi}
                      {item.rsi > 70 && ' (OB)'}
                      {item.rsi < 30 && ' (OS)'}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* ADX Rankings */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              Strongest Trends (ADX)
            </h3>
            <div className="space-y-2">
              {[...momentumData]
                .sort((a, b) => b.adx - a.adx)
                .slice(0, 5)
                .map(item => (
                  <div key={item.token} className="flex items-center justify-between text-sm">
                    <span className="text-white">{item.token}</span>
                    <span className={getIndicatorColor(item.adx, 'adx')}>
                      ADX: {item.adx}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* Volume Rankings */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-blue-400" />
              Top Volume
            </h3>
            <div className="space-y-2">
              {[...momentumData]
                .sort((a, b) => b.volume24h - a.volume24h)
                .slice(0, 5)
                .map(item => (
                  <div key={item.token} className="flex items-center justify-between text-sm">
                    <span className="text-white">{item.token}</span>
                    <span className="text-gray-400">
                      ${formatNumber(item.volume24h)}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* MACD Rankings */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-green-400" />
              MACD Bullish
            </h3>
            <div className="space-y-2">
              {[...momentumData]
                .filter(t => t.macdHistogram > 0)
                .sort((a, b) => b.macdHistogram - a.macdHistogram)
                .slice(0, 5)
                .map(item => (
                  <div key={item.token} className="flex items-center justify-between text-sm">
                    <span className="text-white">{item.token}</span>
                    <span className="text-green-400">
                      +{item.macdHistogram.toFixed(2)}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* MFI Rankings */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-400" />
              MFI Extremes
            </h3>
            <div className="space-y-2">
              {[...momentumData]
                .sort((a, b) => Math.abs(50 - a.mfi) > Math.abs(50 - b.mfi) ? -1 : 1)
                .slice(0, 5)
                .map(item => (
                  <div key={item.token} className="flex items-center justify-between text-sm">
                    <span className="text-white">{item.token}</span>
                    <span className={getIndicatorColor(item.mfi, 'mfi')}>
                      MFI: {item.mfi}
                      {item.mfi > 80 && ' (OB)'}
                      {item.mfi < 20 && ' (OS)'}
                    </span>
                  </div>
                ))}
            </div>
          </div>

          {/* Stochastic Rankings */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-orange-400" />
              Stochastic Signals
            </h3>
            <div className="space-y-2">
              {[...momentumData]
                .filter(t => (t.stochK > 80 || t.stochK < 20))
                .slice(0, 5)
                .map(item => (
                  <div key={item.token} className="flex items-center justify-between text-sm">
                    <span className="text-white">{item.token}</span>
                    <span className={item.stochK > 80 ? 'text-red-400' : 'text-green-400'}>
                      %K: {item.stochK} / %D: {item.stochD}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>RSI: &lt;30 Oversold, &gt;70 Overbought</span>
          <span>ADX: &gt;25 Strong Trend</span>
          <span>MFI: &lt;20 Oversold, &gt;80 Overbought</span>
          <span>MACD: +ve Bullish, -ve Bearish</span>
        </div>
      </div>
    </div>
  )
}

export default MomentumScanner
