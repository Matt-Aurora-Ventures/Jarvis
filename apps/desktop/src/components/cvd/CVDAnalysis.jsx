import React, { useState, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  ArrowUp,
  ArrowDown,
  Zap,
  Target,
  AlertTriangle,
  RefreshCw,
  Eye,
  Filter,
  ChevronRight,
  Layers,
  Volume2
} from 'lucide-react'

export function CVDAnalysis() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('chart') // chart, divergence, scanner
  const [timeframe, setTimeframe] = useState('4h')

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']
  const timeframes = ['15m', '1h', '4h', '1d']

  // Generate CVD data for tokens
  const cvdData = useMemo(() => {
    return tokens.map(token => {
      const currentPrice = 50 + Math.random() * 150
      const priceChange = (Math.random() - 0.5) * 10

      // CVD is cumulative buy volume - sell volume
      const cvdValue = (Math.random() - 0.5) * 100 // in millions
      const cvdChange1h = (Math.random() - 0.5) * 5
      const cvdChange24h = (Math.random() - 0.5) * 15

      // CVD trend (slope)
      const cvdTrend = cvdChange24h > 2 ? 'rising' : cvdChange24h < -2 ? 'falling' : 'flat'

      // Detect divergences
      let divergence = null
      if (cvdChange24h > 5 && priceChange < -3) {
        divergence = 'hidden_bullish' // CVD up, price down = accumulation
      } else if (cvdChange24h < -5 && priceChange > 3) {
        divergence = 'hidden_bearish' // CVD down, price up = distribution
      } else if (cvdTrend === 'rising' && priceChange > 3) {
        divergence = 'confirmation_bullish'
      } else if (cvdTrend === 'falling' && priceChange < -3) {
        divergence = 'confirmation_bearish'
      }

      // Delta per candle
      const deltaPerCandle = (Math.random() - 0.5) * 2

      // Aggressive buying/selling
      const buyPressure = 30 + Math.random() * 40
      const sellPressure = 100 - buyPressure

      return {
        token,
        currentPrice,
        priceChange,
        cvdValue,
        cvdChange1h,
        cvdChange24h,
        cvdTrend,
        divergence,
        deltaPerCandle,
        buyPressure,
        sellPressure,
        volume24h: (Math.random() * 500).toFixed(1)
      }
    })
  }, [])

  // CVD history for chart
  const cvdHistory = useMemo(() => {
    const data = []
    let cvd = 0
    let price = 100

    for (let i = 50; i >= 0; i--) {
      const delta = (Math.random() - 0.48) * 5 // Slight buy bias
      cvd += delta
      price = Math.max(50, price * (1 + (Math.random() - 0.5) * 0.02))

      data.push({
        time: i === 0 ? 'Now' : `-${i}`,
        cvd,
        price,
        delta,
        isPositive: delta > 0
      })
    }
    return data
  }, [selectedToken])

  // Stats
  const bullishDivergences = cvdData.filter(d => d.divergence?.includes('bullish')).length
  const bearishDivergences = cvdData.filter(d => d.divergence?.includes('bearish')).length
  const risingCVD = cvdData.filter(d => d.cvdTrend === 'rising').length
  const avgBuyPressure = (cvdData.reduce((sum, d) => sum + d.buyPressure, 0) / cvdData.length)

  const getDivergenceColor = (div) => {
    if (div?.includes('bullish')) return 'text-green-400'
    if (div?.includes('bearish')) return 'text-red-400'
    return 'text-white/40'
  }

  const getDivergenceBg = (div) => {
    if (div?.includes('bullish')) return 'bg-green-500/10'
    if (div?.includes('bearish')) return 'bg-red-500/10'
    return 'bg-white/5'
  }

  const getDivergenceLabel = (div) => {
    switch (div) {
      case 'hidden_bullish': return 'Hidden Bullish'
      case 'hidden_bearish': return 'Hidden Bearish'
      case 'confirmation_bullish': return 'Confirm Bullish'
      case 'confirmation_bearish': return 'Confirm Bearish'
      default: return '-'
    }
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-500/20 rounded-lg">
            <Activity className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Cumulative Volume Delta</h1>
            <p className="text-white/60 text-sm">Track aggressive buying vs selling pressure</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Timeframe */}
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['chart', 'divergence', 'scanner'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-cyan-500 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-white/60 text-sm">Bullish Divergences</span>
          </div>
          <p className="text-2xl font-bold text-green-400">{bullishDivergences}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-4 h-4 text-red-400" />
            <span className="text-white/60 text-sm">Bearish Divergences</span>
          </div>
          <p className="text-2xl font-bold text-red-400">{bearishDivergences}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <ArrowUp className="w-4 h-4 text-cyan-400" />
            <span className="text-white/60 text-sm">Rising CVD</span>
          </div>
          <p className="text-2xl font-bold text-cyan-400">{risingCVD}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Volume2 className="w-4 h-4 text-purple-400" />
            <span className="text-white/60 text-sm">Avg Buy Pressure</span>
          </div>
          <p className="text-2xl font-bold">{avgBuyPressure.toFixed(1)}%</p>
        </div>
      </div>

      {viewMode === 'chart' && (
        <div className="grid grid-cols-3 gap-6">
          {/* CVD Chart */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            {/* Token Selector */}
            <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2">
              {tokens.slice(0, 6).map(token => (
                <button
                  key={token}
                  onClick={() => setSelectedToken(token)}
                  className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap ${
                    selectedToken === token
                      ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                      : 'bg-white/5 text-white/60 hover:text-white'
                  }`}
                >
                  {token}
                </button>
              ))}
            </div>

            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-cyan-400" />
              {selectedToken} CVD Chart
            </h2>

            {/* Delta Bars */}
            <div className="h-32 flex items-center gap-0.5 mb-4">
              {cvdHistory.map((d, idx) => {
                const maxDelta = Math.max(...cvdHistory.map(h => Math.abs(h.delta)))
                const height = (Math.abs(d.delta) / maxDelta) * 100

                return (
                  <div
                    key={idx}
                    className="flex-1 flex flex-col items-center justify-center"
                    style={{ height: '100%' }}
                  >
                    <div
                      className={`w-full ${d.isPositive ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{
                        height: `${height}%`,
                        marginTop: d.isPositive ? 'auto' : 0,
                        marginBottom: d.isPositive ? 0 : 'auto'
                      }}
                    />
                  </div>
                )
              })}
            </div>

            {/* CVD Line */}
            <div className="h-32 relative border border-white/10 rounded-lg bg-white/[0.02]">
              {/* Zero line */}
              <div className="absolute left-0 right-0 top-1/2 border-t border-dashed border-white/20" />

              {/* CVD curve */}
              <svg className="w-full h-full">
                <polyline
                  fill="none"
                  stroke="#06b6d4"
                  strokeWidth="2"
                  points={cvdHistory.map((d, i) => {
                    const x = (i / (cvdHistory.length - 1)) * 100
                    const minCVD = Math.min(...cvdHistory.map(h => h.cvd))
                    const maxCVD = Math.max(...cvdHistory.map(h => h.cvd))
                    const range = maxCVD - minCVD || 1
                    const y = 100 - ((d.cvd - minCVD) / range) * 100
                    return `${x}%,${y}%`
                  }).join(' ')}
                />
              </svg>

              {/* Labels */}
              <div className="absolute top-1 right-2 text-xs text-cyan-400">CVD</div>
              <div className="absolute bottom-1 left-2 text-xs text-white/40">-50</div>
              <div className="absolute bottom-1 right-2 text-xs text-white/40">Now</div>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-6 mt-4 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-500 rounded" />
                <span className="text-white/60">Buy Delta</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-500 rounded" />
                <span className="text-white/60">Sell Delta</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-1 bg-cyan-500 rounded" />
                <span className="text-white/60">Cumulative CVD</span>
              </div>
            </div>
          </div>

          {/* Token Details */}
          <div className="space-y-4">
            {(() => {
              const tokenData = cvdData.find(d => d.token === selectedToken)
              return (
                <>
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-cyan-400" />
                      {selectedToken} CVD Stats
                    </h3>

                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-white/60">CVD Value</span>
                        <span className={`font-bold ${tokenData.cvdValue >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {tokenData.cvdValue >= 0 ? '+' : ''}{tokenData.cvdValue.toFixed(2)}M
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">1h Change</span>
                        <span className={tokenData.cvdChange1h >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {tokenData.cvdChange1h >= 0 ? '+' : ''}{tokenData.cvdChange1h.toFixed(2)}M
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">24h Change</span>
                        <span className={tokenData.cvdChange24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {tokenData.cvdChange24h >= 0 ? '+' : ''}{tokenData.cvdChange24h.toFixed(2)}M
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">CVD Trend</span>
                        <span className={`font-medium ${
                          tokenData.cvdTrend === 'rising' ? 'text-green-400' :
                          tokenData.cvdTrend === 'falling' ? 'text-red-400' : 'text-white/60'
                        }`}>
                          {tokenData.cvdTrend}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Target className="w-4 h-4 text-purple-400" />
                      Buy/Sell Pressure
                    </h3>

                    <div className="relative h-8 rounded-full overflow-hidden bg-red-500/30 mb-2">
                      <div
                        className="absolute left-0 top-0 bottom-0 bg-green-500 flex items-center justify-center"
                        style={{ width: `${tokenData.buyPressure}%` }}
                      >
                        {tokenData.buyPressure > 30 && (
                          <span className="text-xs font-medium">{tokenData.buyPressure.toFixed(0)}%</span>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-between text-sm">
                      <span className="text-green-400">Aggressive Buyers</span>
                      <span className="text-red-400">Aggressive Sellers</span>
                    </div>
                  </div>

                  {tokenData.divergence && (
                    <div className={`border rounded-xl p-4 ${getDivergenceBg(tokenData.divergence)}`}>
                      <h3 className="font-semibold mb-2 flex items-center gap-2">
                        <Zap className={`w-4 h-4 ${getDivergenceColor(tokenData.divergence)}`} />
                        Divergence Detected
                      </h3>
                      <p className={`font-medium ${getDivergenceColor(tokenData.divergence)}`}>
                        {getDivergenceLabel(tokenData.divergence)}
                      </p>
                      <p className="text-white/60 text-xs mt-2">
                        {tokenData.divergence.includes('bullish')
                          ? 'Accumulation detected - potential reversal'
                          : 'Distribution detected - potential reversal'}
                      </p>
                    </div>
                  )}
                </>
              )
            })()}
          </div>
        </div>
      )}

      {viewMode === 'divergence' && (
        <div className="grid grid-cols-2 gap-6">
          {/* CVD Divergences */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              Active CVD Divergences
            </h2>

            <div className="space-y-3">
              {cvdData.filter(d => d.divergence).map(d => (
                <div
                  key={d.token}
                  className={`p-4 rounded-xl border ${getDivergenceBg(d.divergence)}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-lg">{d.token}</span>
                      <span className={`px-2 py-1 rounded text-xs ${getDivergenceColor(d.divergence)}`}>
                        {getDivergenceLabel(d.divergence)}
                      </span>
                    </div>
                    <span className="text-white/60">${d.currentPrice.toFixed(2)}</span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-white/60">CVD Change (24h)</p>
                      <p className={d.cvdChange24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {d.cvdChange24h >= 0 ? '+' : ''}{d.cvdChange24h.toFixed(2)}M
                      </p>
                    </div>
                    <div>
                      <p className="text-white/60">Price Change (24h)</p>
                      <p className={d.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {d.priceChange >= 0 ? '+' : ''}{d.priceChange.toFixed(2)}%
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {cvdData.filter(d => d.divergence).length === 0 && (
                <p className="text-center py-8 text-white/40">No divergences detected</p>
              )}
            </div>
          </div>

          {/* Divergence Guide */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-400" />
                CVD Divergence Types
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/30">
                  <p className="text-green-400 font-medium">Hidden Bullish</p>
                  <p className="text-white/60 text-xs mt-1">CVD rising + Price falling</p>
                  <p className="text-white/40 text-xs">Smart money accumulating on dips</p>
                </div>

                <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/30">
                  <p className="text-red-400 font-medium">Hidden Bearish</p>
                  <p className="text-white/60 text-xs mt-1">CVD falling + Price rising</p>
                  <p className="text-white/40 text-xs">Distribution into strength</p>
                </div>

                <div className="p-3 bg-cyan-500/10 rounded-lg border border-cyan-500/30">
                  <p className="text-cyan-400 font-medium">Confirmation</p>
                  <p className="text-white/60 text-xs mt-1">CVD and Price moving together</p>
                  <p className="text-white/40 text-xs">Trend strength confirmation</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-purple-400" />
                Trading CVD
              </h3>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Rising CVD = Net buying pressure</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <span>Falling CVD = Net selling pressure</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-cyan-400 mt-0.5 flex-shrink-0" />
                  <span>Divergence often precedes reversal</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  <span>Use with support/resistance levels</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'scanner' && (
        <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Price</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">CVD Value</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">1h Delta</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">24h Delta</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Trend</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Buy Pressure</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Signal</th>
              </tr>
            </thead>
            <tbody>
              {cvdData.map((item, idx) => (
                <tr
                  key={item.token}
                  className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                    idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                  }`}
                  onClick={() => {
                    setSelectedToken(item.token)
                    setViewMode('chart')
                  }}
                >
                  <td className="py-3 px-4 font-medium">{item.token}</td>
                  <td className="py-3 px-4 text-right">
                    <div>
                      <span>${item.currentPrice.toFixed(2)}</span>
                      <span className={`ml-2 text-xs ${item.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {item.priceChange >= 0 ? '+' : ''}{item.priceChange.toFixed(2)}%
                      </span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={item.cvdValue >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {item.cvdValue >= 0 ? '+' : ''}{item.cvdValue.toFixed(2)}M
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={item.cvdChange1h >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {item.cvdChange1h >= 0 ? '+' : ''}{item.cvdChange1h.toFixed(2)}M
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={item.cvdChange24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {item.cvdChange24h >= 0 ? '+' : ''}{item.cvdChange24h.toFixed(2)}M
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`px-2 py-1 rounded text-xs ${
                      item.cvdTrend === 'rising' ? 'bg-green-500/10 text-green-400' :
                      item.cvdTrend === 'falling' ? 'bg-red-500/10 text-red-400' :
                      'bg-white/5 text-white/60'
                    }`}>
                      {item.cvdTrend}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex items-center justify-center gap-1">
                      <div className="w-12 h-2 bg-red-500/30 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-green-500"
                          style={{ width: `${item.buyPressure}%` }}
                        />
                      </div>
                      <span className="text-xs text-white/60">{item.buyPressure.toFixed(0)}%</span>
                    </div>
                  </td>
                  <td className="py-3 px-4 text-center">
                    {item.divergence ? (
                      <span className={`px-2 py-1 rounded text-xs ${getDivergenceBg(item.divergence)} ${getDivergenceColor(item.divergence)}`}>
                        {getDivergenceLabel(item.divergence).split(' ')[0]}
                      </span>
                    ) : (
                      <span className="text-white/30">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default CVDAnalysis
