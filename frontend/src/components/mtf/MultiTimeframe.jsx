import React, { useState, useMemo, useEffect } from 'react'
import {
  Layers,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Target,
  BarChart3
} from 'lucide-react'

export function MultiTimeframe() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('matrix') // matrix, trends, confluence
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['5m', '15m', '1h', '4h', '1d', '1w']

  // Generate mock MTF data
  const mtfData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    // Generate data for each timeframe
    const timeframeData = timeframes.map(tf => {
      const trend = Math.random() > 0.5 ? 'bullish' : Math.random() > 0.3 ? 'bearish' : 'neutral'
      const rsi = Math.floor(Math.random() * 100)
      const macd = (Math.random() - 0.5) * 10
      const ema20 = currentPrice * (0.95 + Math.random() * 0.1)
      const ema50 = currentPrice * (0.92 + Math.random() * 0.16)
      const ema200 = currentPrice * (0.85 + Math.random() * 0.3)
      const sma20 = currentPrice * (0.95 + Math.random() * 0.1)
      const sma50 = currentPrice * (0.92 + Math.random() * 0.16)

      const priceVsEma20 = ((currentPrice - ema20) / ema20) * 100
      const priceVsEma50 = ((currentPrice - ema50) / ema50) * 100
      const priceVsEma200 = ((currentPrice - ema200) / ema200) * 100

      const adx = Math.floor(Math.random() * 60) + 10
      const stochK = Math.floor(Math.random() * 100)
      const atr = currentPrice * 0.02 * (0.5 + Math.random())
      const volume = Math.floor(Math.random() * 100000000) + 10000000
      const volumeChange = (Math.random() - 0.5) * 100

      // Structure analysis
      const structureBias = trend === 'bullish' ? 'HH/HL' :
                           trend === 'bearish' ? 'LH/LL' : 'Range'

      // Support/Resistance
      const support = currentPrice * (0.92 + Math.random() * 0.05)
      const resistance = currentPrice * (1.03 + Math.random() * 0.05)

      return {
        timeframe: tf,
        trend,
        rsi,
        macd,
        ema20,
        ema50,
        ema200,
        sma20,
        sma50,
        priceVsEma20,
        priceVsEma50,
        priceVsEma200,
        adx,
        stochK,
        atr,
        volume,
        volumeChange,
        structureBias,
        support,
        resistance,
        aboveEma20: currentPrice > ema20,
        aboveEma50: currentPrice > ema50,
        aboveEma200: currentPrice > ema200,
        emaCrossover: ema20 > ema50 ? 'golden' : ema20 < ema50 ? 'death' : 'none',
        rsiZone: rsi > 70 ? 'overbought' : rsi < 30 ? 'oversold' : 'neutral',
        macdSignal: macd > 0 ? 'bullish' : 'bearish',
        trendStrength: adx > 40 ? 'strong' : adx > 25 ? 'moderate' : 'weak'
      }
    })

    // Calculate confluence
    const bullishCount = timeframeData.filter(t => t.trend === 'bullish').length
    const bearishCount = timeframeData.filter(t => t.trend === 'bearish').length
    const neutralCount = timeframeData.filter(t => t.trend === 'neutral').length

    const overallBias = bullishCount > bearishCount + 1 ? 'bullish' :
                       bearishCount > bullishCount + 1 ? 'bearish' : 'mixed'

    const confluenceScore = Math.max(bullishCount, bearishCount) / timeframes.length * 100

    // Calculate trend alignment
    const higherTFTrend = timeframeData.slice(-3).map(t => t.trend) // 4h, 1d, 1w
    const lowerTFTrend = timeframeData.slice(0, 3).map(t => t.trend) // 5m, 15m, 1h

    const higherBullish = higherTFTrend.filter(t => t === 'bullish').length
    const higherBearish = higherTFTrend.filter(t => t === 'bearish').length
    const lowerBullish = lowerTFTrend.filter(t => t === 'bullish').length
    const lowerBearish = lowerTFTrend.filter(t => t === 'bearish').length

    const trendAlignment = (higherBullish >= 2 && lowerBullish >= 2) ? 'aligned_bullish' :
                          (higherBearish >= 2 && lowerBearish >= 2) ? 'aligned_bearish' : 'divergent'

    // Key levels across timeframes
    const allSupports = timeframeData.map(t => t.support).sort((a, b) => b - a)
    const allResistances = timeframeData.map(t => t.resistance).sort((a, b) => a - b)

    return {
      currentPrice,
      timeframeData,
      bullishCount,
      bearishCount,
      neutralCount,
      overallBias,
      confluenceScore,
      trendAlignment,
      keySupport: allSupports[0],
      keyResistance: allResistances[0]
    }
  }, [selectedToken])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(2)
  }

  const getTrendIcon = (trend) => {
    switch(trend) {
      case 'bullish': return <ArrowUpRight className="w-4 h-4 text-green-400" />
      case 'bearish': return <ArrowDownRight className="w-4 h-4 text-red-400" />
      default: return <Minus className="w-4 h-4 text-yellow-400" />
    }
  }

  const getTrendColor = (trend) => {
    switch(trend) {
      case 'bullish': return 'text-green-400'
      case 'bearish': return 'text-red-400'
      default: return 'text-yellow-400'
    }
  }

  const getTrendBg = (trend) => {
    switch(trend) {
      case 'bullish': return 'bg-green-500/20 border-green-500/30'
      case 'bearish': return 'bg-red-500/20 border-red-500/30'
      default: return 'bg-yellow-500/20 border-yellow-500/30'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Layers className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold text-white">Multi-Timeframe Analysis</h2>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedToken}
            onChange={(e) => setSelectedToken(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white text-sm"
          >
            {tokens.map(token => (
              <option key={token} value={token}>{token}</option>
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

      {/* Overall Confluence Summary */}
      <div className={`rounded-lg p-6 mb-6 border ${getTrendBg(mtfData.overallBias)}`}>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="text-gray-400 text-sm mb-2">Overall Bias</div>
            <div className={`text-3xl font-bold capitalize ${getTrendColor(mtfData.overallBias)}`}>
              {mtfData.overallBias}
            </div>
            <div className="text-gray-400 text-sm mt-1">
              {mtfData.bullishCount} bullish / {mtfData.bearishCount} bearish / {mtfData.neutralCount} neutral
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-400 text-sm mb-2">Confluence Score</div>
            <div className="text-3xl font-bold text-white">
              {mtfData.confluenceScore.toFixed(0)}%
            </div>
            <div className="w-full h-2 bg-white/10 rounded-full mt-2 overflow-hidden">
              <div
                className={`h-full ${mtfData.overallBias === 'bullish' ? 'bg-green-500' : mtfData.overallBias === 'bearish' ? 'bg-red-500' : 'bg-yellow-500'}`}
                style={{ width: `${mtfData.confluenceScore}%` }}
              />
            </div>
          </div>
          <div className="text-center">
            <div className="text-gray-400 text-sm mb-2">Trend Alignment</div>
            <div className={`text-lg font-bold flex items-center justify-center gap-2 ${
              mtfData.trendAlignment === 'aligned_bullish' ? 'text-green-400' :
              mtfData.trendAlignment === 'aligned_bearish' ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {mtfData.trendAlignment === 'aligned_bullish' ? (
                <><CheckCircle className="w-5 h-5" /> Aligned Bullish</>
              ) : mtfData.trendAlignment === 'aligned_bearish' ? (
                <><CheckCircle className="w-5 h-5" /> Aligned Bearish</>
              ) : (
                <><AlertTriangle className="w-5 h-5" /> Divergent</>
              )}
            </div>
            <div className="text-gray-400 text-sm mt-1">
              Higher TF vs Lower TF
            </div>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'matrix', label: 'Matrix View' },
          { id: 'trends', label: 'Trend Analysis' },
          { id: 'confluence', label: 'Confluence' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Matrix View */}
      {viewMode === 'matrix' && (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-gray-400 text-sm border-b border-white/10">
                <th className="text-left py-3 px-2">TF</th>
                <th className="text-center py-3 px-2">Trend</th>
                <th className="text-center py-3 px-2">RSI</th>
                <th className="text-center py-3 px-2">MACD</th>
                <th className="text-center py-3 px-2">EMA Cross</th>
                <th className="text-center py-3 px-2">Above EMAs</th>
                <th className="text-center py-3 px-2">ADX</th>
                <th className="text-center py-3 px-2">Structure</th>
              </tr>
            </thead>
            <tbody>
              {mtfData.timeframeData.map(tf => (
                <tr key={tf.timeframe} className="border-b border-white/5 hover:bg-white/5">
                  <td className="py-3 px-2">
                    <span className="text-white font-medium">{tf.timeframe}</span>
                  </td>
                  <td className="text-center py-3 px-2">
                    <div className="flex items-center justify-center gap-1">
                      {getTrendIcon(tf.trend)}
                      <span className={`capitalize ${getTrendColor(tf.trend)}`}>{tf.trend}</span>
                    </div>
                  </td>
                  <td className="text-center py-3 px-2">
                    <span className={
                      tf.rsiZone === 'overbought' ? 'text-red-400' :
                      tf.rsiZone === 'oversold' ? 'text-green-400' : 'text-gray-400'
                    }>
                      {tf.rsi}
                    </span>
                  </td>
                  <td className="text-center py-3 px-2">
                    <span className={tf.macd > 0 ? 'text-green-400' : 'text-red-400'}>
                      {tf.macd > 0 ? '+' : ''}{tf.macd.toFixed(2)}
                    </span>
                  </td>
                  <td className="text-center py-3 px-2">
                    <span className={
                      tf.emaCrossover === 'golden' ? 'text-green-400' :
                      tf.emaCrossover === 'death' ? 'text-red-400' : 'text-gray-500'
                    }>
                      {tf.emaCrossover === 'golden' ? 'Golden' :
                       tf.emaCrossover === 'death' ? 'Death' : '-'}
                    </span>
                  </td>
                  <td className="text-center py-3 px-2">
                    <div className="flex items-center justify-center gap-1">
                      <span className={tf.aboveEma20 ? 'text-green-400' : 'text-red-400'}>20</span>
                      <span className={tf.aboveEma50 ? 'text-green-400' : 'text-red-400'}>50</span>
                      <span className={tf.aboveEma200 ? 'text-green-400' : 'text-red-400'}>200</span>
                    </div>
                  </td>
                  <td className="text-center py-3 px-2">
                    <span className={
                      tf.trendStrength === 'strong' ? 'text-purple-400' :
                      tf.trendStrength === 'moderate' ? 'text-blue-400' : 'text-gray-500'
                    }>
                      {tf.adx} ({tf.trendStrength})
                    </span>
                  </td>
                  <td className="text-center py-3 px-2">
                    <span className={
                      tf.structureBias === 'HH/HL' ? 'text-green-400' :
                      tf.structureBias === 'LH/LL' ? 'text-red-400' : 'text-yellow-400'
                    }>
                      {tf.structureBias}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Trends View */}
      {viewMode === 'trends' && (
        <div className="space-y-4">
          {mtfData.timeframeData.map(tf => (
            <div key={tf.timeframe} className={`rounded-lg p-4 border ${getTrendBg(tf.trend)}`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-gray-400" />
                  <span className="text-white font-medium text-lg">{tf.timeframe}</span>
                  <span className={`px-2 py-1 rounded text-sm capitalize ${getTrendColor(tf.trend)} bg-white/5`}>
                    {tf.trend}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {getTrendIcon(tf.trend)}
                  <span className={`text-lg font-bold ${getTrendColor(tf.trend)}`}>
                    {tf.structureBias}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-gray-400 text-xs">RSI ({tf.rsiZone})</div>
                  <div className={`font-medium ${
                    tf.rsiZone === 'overbought' ? 'text-red-400' :
                    tf.rsiZone === 'oversold' ? 'text-green-400' : 'text-white'
                  }`}>
                    {tf.rsi}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs">MACD Signal</div>
                  <div className={`font-medium ${tf.macd > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {tf.macdSignal}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs">ADX Strength</div>
                  <div className="text-white font-medium">{tf.adx} - {tf.trendStrength}</div>
                </div>
                <div>
                  <div className="text-gray-400 text-xs">EMA Position</div>
                  <div className="text-white font-medium">
                    {tf.aboveEma20 && tf.aboveEma50 && tf.aboveEma200 ? 'All Above' :
                     !tf.aboveEma20 && !tf.aboveEma50 && !tf.aboveEma200 ? 'All Below' : 'Mixed'}
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-3 border-t border-white/10 flex items-center justify-between text-sm">
                <span className="text-gray-400">
                  Support: <span className="text-green-400">${formatPrice(tf.support)}</span>
                </span>
                <span className="text-gray-400">
                  Price: <span className="text-white">${formatPrice(mtfData.currentPrice)}</span>
                </span>
                <span className="text-gray-400">
                  Resistance: <span className="text-red-400">${formatPrice(tf.resistance)}</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Confluence View */}
      {viewMode === 'confluence' && (
        <div className="space-y-6">
          {/* Indicator Confluence */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Indicator Confluence Across Timeframes</h3>

            <div className="space-y-4">
              {/* RSI */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-400">RSI Signals</span>
                  <div className="flex gap-4 text-sm">
                    <span className="text-green-400">
                      {mtfData.timeframeData.filter(t => t.rsi < 50).length} Bullish
                    </span>
                    <span className="text-red-400">
                      {mtfData.timeframeData.filter(t => t.rsi > 50).length} Bearish
                    </span>
                  </div>
                </div>
                <div className="flex gap-1">
                  {mtfData.timeframeData.map(tf => (
                    <div
                      key={tf.timeframe}
                      className={`flex-1 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        tf.rsi < 30 ? 'bg-green-500 text-white' :
                        tf.rsi > 70 ? 'bg-red-500 text-white' :
                        tf.rsi < 50 ? 'bg-green-500/30 text-green-400' :
                        'bg-red-500/30 text-red-400'
                      }`}
                      title={`${tf.timeframe}: RSI ${tf.rsi}`}
                    >
                      {tf.timeframe}
                    </div>
                  ))}
                </div>
              </div>

              {/* MACD */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-400">MACD Signals</span>
                  <div className="flex gap-4 text-sm">
                    <span className="text-green-400">
                      {mtfData.timeframeData.filter(t => t.macd > 0).length} Bullish
                    </span>
                    <span className="text-red-400">
                      {mtfData.timeframeData.filter(t => t.macd < 0).length} Bearish
                    </span>
                  </div>
                </div>
                <div className="flex gap-1">
                  {mtfData.timeframeData.map(tf => (
                    <div
                      key={tf.timeframe}
                      className={`flex-1 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        tf.macd > 0 ? 'bg-green-500/50 text-green-400' : 'bg-red-500/50 text-red-400'
                      }`}
                      title={`${tf.timeframe}: MACD ${tf.macd.toFixed(2)}`}
                    >
                      {tf.timeframe}
                    </div>
                  ))}
                </div>
              </div>

              {/* EMA Position */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-400">Price vs EMA200</span>
                  <div className="flex gap-4 text-sm">
                    <span className="text-green-400">
                      {mtfData.timeframeData.filter(t => t.aboveEma200).length} Above
                    </span>
                    <span className="text-red-400">
                      {mtfData.timeframeData.filter(t => !t.aboveEma200).length} Below
                    </span>
                  </div>
                </div>
                <div className="flex gap-1">
                  {mtfData.timeframeData.map(tf => (
                    <div
                      key={tf.timeframe}
                      className={`flex-1 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        tf.aboveEma200 ? 'bg-green-500/50 text-green-400' : 'bg-red-500/50 text-red-400'
                      }`}
                      title={`${tf.timeframe}: ${tf.aboveEma200 ? 'Above' : 'Below'} EMA200`}
                    >
                      {tf.timeframe}
                    </div>
                  ))}
                </div>
              </div>

              {/* Trend */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-gray-400">Overall Trend</span>
                </div>
                <div className="flex gap-1">
                  {mtfData.timeframeData.map(tf => (
                    <div
                      key={tf.timeframe}
                      className={`flex-1 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        tf.trend === 'bullish' ? 'bg-green-500 text-white' :
                        tf.trend === 'bearish' ? 'bg-red-500 text-white' :
                        'bg-yellow-500 text-white'
                      }`}
                      title={`${tf.timeframe}: ${tf.trend}`}
                    >
                      {tf.timeframe}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Key Levels */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <h3 className="text-green-400 font-medium mb-3 flex items-center gap-2">
                <Target className="w-4 h-4" />
                Key Support Level
              </h3>
              <div className="text-2xl font-bold text-white mb-1">
                ${formatPrice(mtfData.keySupport)}
              </div>
              <div className="text-gray-400 text-sm">
                {((mtfData.currentPrice - mtfData.keySupport) / mtfData.keySupport * 100).toFixed(2)}% above current price
              </div>
            </div>
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <h3 className="text-red-400 font-medium mb-3 flex items-center gap-2">
                <Target className="w-4 h-4" />
                Key Resistance Level
              </h3>
              <div className="text-2xl font-bold text-white mb-1">
                ${formatPrice(mtfData.keyResistance)}
              </div>
              <div className="text-gray-400 text-sm">
                {((mtfData.keyResistance - mtfData.currentPrice) / mtfData.currentPrice * 100).toFixed(2)}% from current price
              </div>
            </div>
          </div>

          {/* Trading Recommendation */}
          <div className={`rounded-lg p-4 border ${
            mtfData.trendAlignment === 'aligned_bullish' ? 'bg-green-500/10 border-green-500/20' :
            mtfData.trendAlignment === 'aligned_bearish' ? 'bg-red-500/10 border-red-500/20' :
            'bg-yellow-500/10 border-yellow-500/20'
          }`}>
            <h3 className="text-white font-medium mb-2">MTF Analysis Summary</h3>
            <p className="text-gray-400">
              {mtfData.trendAlignment === 'aligned_bullish' ? (
                'Strong bullish alignment across timeframes. Higher and lower timeframes agree on upward direction. Consider long positions with stops below key support.'
              ) : mtfData.trendAlignment === 'aligned_bearish' ? (
                'Strong bearish alignment across timeframes. Higher and lower timeframes agree on downward direction. Consider short positions with stops above key resistance.'
              ) : (
                'Mixed signals across timeframes. Higher and lower timeframes show divergent trends. Consider waiting for alignment or trading range-bound strategies.'
              )}
            </p>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>TF = Timeframe</span>
          <span>EMA Cross: Golden (20 &gt; 50), Death (20 &lt; 50)</span>
          <span>Structure: HH/HL = Uptrend, LH/LL = Downtrend</span>
        </div>
      </div>
    </div>
  )
}

export default MultiTimeframe
