import React, { useState, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  DollarSign,
  Layers,
  ArrowUp,
  ArrowDown,
  RefreshCw,
  AlertTriangle,
  Zap,
  Target,
  Clock,
  ChevronRight,
  Eye,
  Filter
} from 'lucide-react'

export function OpenInterestTracker() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('overview') // overview, changes, divergence, lsratio
  const [timeframe, setTimeframe] = useState('4h')

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'DOGE']
  const timeframes = ['15m', '1h', '4h', '1d']

  // Generate OI data for tokens
  const oiData = useMemo(() => {
    return tokens.map(token => {
      const currentOI = 50 + Math.random() * 500 // in millions
      const change1h = (Math.random() - 0.5) * 10
      const change4h = (Math.random() - 0.5) * 20
      const change24h = (Math.random() - 0.5) * 30

      const currentPrice = 50 + Math.random() * 150
      const priceChange24h = (Math.random() - 0.5) * 15

      // Long/Short ratio
      const longRatio = 45 + Math.random() * 20
      const shortRatio = 100 - longRatio

      // Determine divergence
      let divergence = null
      if (change24h > 10 && priceChange24h < -5) {
        divergence = 'bearish' // OI up, price down = shorts opening
      } else if (change24h < -10 && priceChange24h > 5) {
        divergence = 'bullish' // OI down, price up = shorts closing
      } else if (change24h > 10 && priceChange24h > 5) {
        divergence = 'momentum' // Both up = longs opening
      }

      // Liquidation levels
      const longLiq = currentPrice * (0.92 + Math.random() * 0.04)
      const shortLiq = currentPrice * (1.04 + Math.random() * 0.06)

      return {
        token,
        currentOI,
        change1h,
        change4h,
        change24h,
        currentPrice,
        priceChange24h,
        longRatio,
        shortRatio,
        divergence,
        longLiq,
        shortLiq,
        volume24h: currentOI * (0.3 + Math.random() * 0.5)
      }
    }).sort((a, b) => b.currentOI - a.currentOI)
  }, [])

  // OI history for selected token
  const oiHistory = useMemo(() => {
    const data = []
    let oi = 100 + Math.random() * 200
    let price = 100

    for (let i = 48; i >= 0; i--) {
      oi = Math.max(50, oi * (1 + (Math.random() - 0.5) * 0.05))
      price = Math.max(50, price * (1 + (Math.random() - 0.5) * 0.03))

      data.push({
        time: i === 0 ? 'Now' : `-${i}h`,
        oi,
        price,
        oiChange: (Math.random() - 0.5) * 5
      })
    }
    return data
  }, [selectedToken])

  // Stats
  const totalOI = oiData.reduce((sum, d) => sum + d.currentOI, 0)
  const avgLongRatio = (oiData.reduce((sum, d) => sum + d.longRatio, 0) / oiData.length)
  const oiIncreasing = oiData.filter(d => d.change24h > 0).length
  const divergenceCount = oiData.filter(d => d.divergence).length

  const getDivergenceColor = (div) => {
    if (div === 'bullish') return 'text-green-400'
    if (div === 'bearish') return 'text-red-400'
    if (div === 'momentum') return 'text-purple-400'
    return 'text-white/40'
  }

  const getDivergenceBg = (div) => {
    if (div === 'bullish') return 'bg-green-500/10'
    if (div === 'bearish') return 'bg-red-500/10'
    if (div === 'momentum') return 'bg-purple-500/10'
    return 'bg-white/5'
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Layers className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Open Interest Tracker</h1>
            <p className="text-white/60 text-sm">Track derivatives positioning and OI changes</p>
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
            {['overview', 'changes', 'divergence', 'lsratio'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-purple-500 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {mode === 'lsratio' ? 'L/S Ratio' : mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-purple-400" />
            <span className="text-white/60 text-sm">Total OI</span>
          </div>
          <p className="text-2xl font-bold">${totalOI.toFixed(1)}M</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-white/60 text-sm">OI Increasing</span>
          </div>
          <p className="text-2xl font-bold text-green-400">{oiIncreasing}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <span className="text-white/60 text-sm">Avg Long Ratio</span>
          </div>
          <p className="text-2xl font-bold">{avgLongRatio.toFixed(1)}%</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            <span className="text-white/60 text-sm">Divergences</span>
          </div>
          <p className="text-2xl font-bold text-yellow-400">{divergenceCount}</p>
        </div>
      </div>

      {viewMode === 'overview' && (
        <div className="grid grid-cols-3 gap-6">
          {/* OI Table */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Open Interest</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">1h Change</th>
                  <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">24h Change</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">L/S Ratio</th>
                  <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Signal</th>
                </tr>
              </thead>
              <tbody>
                {oiData.map((item, idx) => (
                  <tr
                    key={item.token}
                    className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                      selectedToken === item.token ? 'bg-purple-500/10' : idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                    }`}
                    onClick={() => setSelectedToken(item.token)}
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{item.token}</span>
                        {item.divergence && (
                          <AlertTriangle className={`w-3 h-3 ${getDivergenceColor(item.divergence)}`} />
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-right font-medium">
                      ${item.currentOI.toFixed(2)}M
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={item.change1h >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {item.change1h >= 0 ? '+' : ''}{item.change1h.toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className={item.change24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {item.change24h >= 0 ? '+' : ''}{item.change24h.toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-center gap-1">
                        <div className="w-16 h-2 bg-red-500/30 rounded-full overflow-hidden flex">
                          <div
                            className="h-full bg-green-500"
                            style={{ width: `${item.longRatio}%` }}
                          />
                        </div>
                        <span className="text-xs text-white/60">{item.longRatio.toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {item.divergence ? (
                        <span className={`px-2 py-1 rounded text-xs ${getDivergenceBg(item.divergence)} ${getDivergenceColor(item.divergence)}`}>
                          {item.divergence}
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

          {/* Selected Token Details */}
          <div className="space-y-4">
            {(() => {
              const tokenData = oiData.find(d => d.token === selectedToken)
              return (
                <>
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-purple-400" />
                      {selectedToken} Open Interest
                    </h3>

                    <div className="space-y-3">
                      <div className="flex justify-between">
                        <span className="text-white/60">Current OI</span>
                        <span className="font-bold">${tokenData.currentOI.toFixed(2)}M</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">24h Volume</span>
                        <span className="font-medium">${tokenData.volume24h.toFixed(2)}M</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-white/60">OI/Volume</span>
                        <span className="font-medium">
                          {(tokenData.currentOI / tokenData.volume24h).toFixed(2)}x
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Target className="w-4 h-4 text-yellow-400" />
                      Liquidation Clusters
                    </h3>

                    <div className="space-y-3">
                      <div className="p-2 bg-green-500/10 rounded-lg">
                        <p className="text-green-400 text-sm font-medium">Long Liquidations</p>
                        <p className="text-white/60 text-xs">${tokenData.longLiq.toFixed(2)}</p>
                      </div>
                      <div className="p-2 bg-red-500/10 rounded-lg">
                        <p className="text-red-400 text-sm font-medium">Short Liquidations</p>
                        <p className="text-white/60 text-xs">${tokenData.shortLiq.toFixed(2)}</p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Activity className="w-4 h-4 text-cyan-400" />
                      Position Bias
                    </h3>

                    <div className="relative h-6 rounded-full overflow-hidden bg-red-500/30">
                      <div
                        className="absolute left-0 top-0 bottom-0 bg-green-500"
                        style={{ width: `${tokenData.longRatio}%` }}
                      />
                    </div>
                    <div className="flex justify-between mt-2 text-sm">
                      <span className="text-green-400">Longs: {tokenData.longRatio.toFixed(1)}%</span>
                      <span className="text-red-400">Shorts: {tokenData.shortRatio.toFixed(1)}%</span>
                    </div>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {viewMode === 'changes' && (
        <div className="grid grid-cols-3 gap-6">
          {/* OI Changes Chart */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-purple-400" />
              {selectedToken} OI History
            </h2>

            <div className="h-64 flex items-end gap-1">
              {oiHistory.map((d, idx) => {
                const maxOI = Math.max(...oiHistory.map(h => h.oi))
                const height = (d.oi / maxOI) * 100

                return (
                  <div
                    key={idx}
                    className="flex-1 flex flex-col items-center justify-end"
                  >
                    <div
                      className={`w-full rounded-t ${d.oiChange >= 0 ? 'bg-purple-500' : 'bg-purple-500/50'}`}
                      style={{ height: `${height}%` }}
                    />
                  </div>
                )
              })}
            </div>

            <div className="flex justify-between mt-2 text-xs text-white/40">
              <span>-48h</span>
              <span>Now</span>
            </div>
          </div>

          {/* Top OI Changes */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <ArrowUp className="w-4 h-4 text-green-400" />
                Biggest OI Increase (24h)
              </h3>

              <div className="space-y-2">
                {[...oiData].sort((a, b) => b.change24h - a.change24h).slice(0, 5).map(d => (
                  <div key={d.token} className="flex items-center justify-between p-2 bg-green-500/10 rounded-lg">
                    <span className="font-medium">{d.token}</span>
                    <span className="text-green-400">+{d.change24h.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <ArrowDown className="w-4 h-4 text-red-400" />
                Biggest OI Decrease (24h)
              </h3>

              <div className="space-y-2">
                {[...oiData].sort((a, b) => a.change24h - b.change24h).slice(0, 5).map(d => (
                  <div key={d.token} className="flex items-center justify-between p-2 bg-red-500/10 rounded-lg">
                    <span className="font-medium">{d.token}</span>
                    <span className="text-red-400">{d.change24h.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'divergence' && (
        <div className="grid grid-cols-2 gap-6">
          {/* OI/Price Divergences */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              OI/Price Divergences
            </h2>

            <div className="space-y-3">
              {oiData.filter(d => d.divergence).map(d => (
                <div
                  key={d.token}
                  className={`p-4 rounded-xl border ${getDivergenceBg(d.divergence)}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-lg">{d.token}</span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getDivergenceBg(d.divergence)} ${getDivergenceColor(d.divergence)}`}>
                      {d.divergence?.toUpperCase()}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <p className="text-white/60">OI Change (24h)</p>
                      <p className={d.change24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {d.change24h >= 0 ? '+' : ''}{d.change24h.toFixed(2)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-white/60">Price Change (24h)</p>
                      <p className={d.priceChange24h >= 0 ? 'text-green-400' : 'text-red-400'}>
                        {d.priceChange24h >= 0 ? '+' : ''}{d.priceChange24h.toFixed(2)}%
                      </p>
                    </div>
                  </div>
                </div>
              ))}
              {oiData.filter(d => d.divergence).length === 0 && (
                <p className="text-center py-8 text-white/40">No divergences detected</p>
              )}
            </div>
          </div>

          {/* Divergence Guide */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Eye className="w-4 h-4 text-blue-400" />
                Divergence Types
              </h3>

              <div className="space-y-3 text-sm">
                <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/30">
                  <p className="text-green-400 font-medium">Bullish Divergence</p>
                  <p className="text-white/60 text-xs mt-1">OI decreasing + Price increasing</p>
                  <p className="text-white/40 text-xs">Shorts closing, potential squeeze</p>
                </div>

                <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/30">
                  <p className="text-red-400 font-medium">Bearish Divergence</p>
                  <p className="text-white/60 text-xs mt-1">OI increasing + Price decreasing</p>
                  <p className="text-white/40 text-xs">Shorts opening, expecting further drop</p>
                </div>

                <div className="p-3 bg-purple-500/10 rounded-lg border border-purple-500/30">
                  <p className="text-purple-400 font-medium">Momentum</p>
                  <p className="text-white/60 text-xs mt-1">OI increasing + Price increasing</p>
                  <p className="text-white/40 text-xs">Longs opening, trend continuation</p>
                </div>
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <ChevronRight className="w-4 h-4 text-cyan-400" />
                Trading Strategy
              </h3>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Bullish divergence = Look for long entries</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                  <span>Bearish divergence = Avoid longs, consider shorts</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-purple-400 mt-0.5 flex-shrink-0" />
                  <span>Momentum = Trend likely to continue</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                  <span>Combine with price action for confirmation</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'lsratio' && (
        <div className="grid grid-cols-3 gap-6">
          {/* L/S Ratio Chart */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-cyan-400" />
              Long/Short Ratios
            </h2>

            <div className="space-y-3">
              {oiData.map(d => (
                <div key={d.token} className="flex items-center gap-4">
                  <span className="w-16 font-medium">{d.token}</span>
                  <div className="flex-1 h-8 relative rounded-lg overflow-hidden bg-red-500/30">
                    <div
                      className="absolute left-0 top-0 bottom-0 bg-green-500 flex items-center justify-end pr-2"
                      style={{ width: `${d.longRatio}%` }}
                    >
                      {d.longRatio > 30 && (
                        <span className="text-xs font-medium text-white/80">{d.longRatio.toFixed(0)}%</span>
                      )}
                    </div>
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-medium text-white/80">
                      {d.shortRatio.toFixed(0)}%
                    </div>
                  </div>
                  <span className={`w-16 text-sm ${
                    d.longRatio > 60 ? 'text-green-400' :
                    d.longRatio < 40 ? 'text-red-400' : 'text-white/60'
                  }`}>
                    {d.longRatio > 60 ? 'Long Heavy' :
                     d.longRatio < 40 ? 'Short Heavy' : 'Balanced'}
                  </span>
                </div>
              ))}
            </div>

            {/* Legend */}
            <div className="flex items-center gap-6 mt-4 pt-4 border-t border-white/10 text-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-green-500" />
                <span className="text-white/60">Longs</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 rounded bg-red-500/50" />
                <span className="text-white/60">Shorts</span>
              </div>
            </div>
          </div>

          {/* Extremes */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                Most Long Heavy
              </h3>

              <div className="space-y-2">
                {[...oiData].sort((a, b) => b.longRatio - a.longRatio).slice(0, 3).map(d => (
                  <div key={d.token} className="flex items-center justify-between p-2 bg-green-500/10 rounded-lg">
                    <span className="font-medium">{d.token}</span>
                    <span className="text-green-400">{d.longRatio.toFixed(1)}% long</span>
                  </div>
                ))}
              </div>

              <p className="text-white/40 text-xs mt-3">
                Crowded longs = potential squeeze risk
              </p>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-red-400" />
                Most Short Heavy
              </h3>

              <div className="space-y-2">
                {[...oiData].sort((a, b) => a.longRatio - b.longRatio).slice(0, 3).map(d => (
                  <div key={d.token} className="flex items-center justify-between p-2 bg-red-500/10 rounded-lg">
                    <span className="font-medium">{d.token}</span>
                    <span className="text-red-400">{d.shortRatio.toFixed(1)}% short</span>
                  </div>
                ))}
              </div>

              <p className="text-white/40 text-xs mt-3">
                Crowded shorts = potential short squeeze
              </p>
            </div>

            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-4">
              <h3 className="font-semibold mb-2 text-yellow-400">Contrarian Signal</h3>
              <p className="text-white/60 text-sm">
                Extreme positioning often precedes reversals. Watch for L/S ratios above 70% or below 30%.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default OpenInterestTracker
