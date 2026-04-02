import React, { useState, useMemo } from 'react'
import {
  Radar,
  TrendingUp,
  TrendingDown,
  Activity,
  Target,
  Layers,
  BarChart3,
  Zap,
  Filter,
  Search,
  Star,
  Bell,
  Eye,
  ChevronDown,
  ChevronUp,
  Settings,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Gauge,
  Grid3X3
} from 'lucide-react'

// Indicator categories
const INDICATOR_GROUPS = {
  trend: ['EMA', 'SMA', 'Ichimoku', 'ADX'],
  momentum: ['RSI', 'MACD', 'Stochastic', 'CCI'],
  volatility: ['Bollinger', 'Keltner', 'ATR', 'StdDev'],
  volume: ['VWAP', 'OBV', 'MFI', 'VPVR'],
  levels: ['Pivots', 'Fibonacci', 'Support/Res', 'LiqLevels']
}

export function UnifiedScanner() {
  const [viewMode, setViewMode] = useState('overview') // overview, heatmap, signals, screener
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [sortBy, setSortBy] = useState('score')
  const [sortDir, setSortDir] = useState('desc')
  const [filterBias, setFilterBias] = useState('all') // all, bullish, bearish, neutral

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']

  // Generate unified scanner data for all tokens
  const scannerData = useMemo(() => {
    return tokens.map(token => {
      // Generate random indicator values
      const rsi = 20 + Math.random() * 60
      const macd = (Math.random() - 0.5) * 2
      const macdSignal = macd > 0 ? 'bullish' : 'bearish'
      const stochK = 10 + Math.random() * 80
      const stochD = 10 + Math.random() * 80
      const cci = -100 + Math.random() * 200
      const adx = 15 + Math.random() * 40
      const mfi = 20 + Math.random() * 60

      // Trend indicators
      const ema20 = 100 + Math.random() * 50
      const ema50 = 95 + Math.random() * 50
      const ema200 = 90 + Math.random() * 50
      const currentPrice = 100 + Math.random() * 50
      const emaCross = ema20 > ema50 ? 'golden' : 'death'
      const trendStrength = adx > 25 ? 'strong' : adx > 20 ? 'moderate' : 'weak'

      // Volatility
      const bbPosition = Math.random() // 0-1, 0.5 = middle
      const inBBSqueeze = Math.random() > 0.7
      const inKeltnerSqueeze = Math.random() > 0.8
      const atrPercent = 2 + Math.random() * 4

      // Volume
      const vwapPosition = currentPrice > (currentPrice * (0.95 + Math.random() * 0.1)) ? 'above' : 'below'
      const volumeSpike = Math.random() > 0.8
      const obvTrend = Math.random() > 0.5 ? 'up' : 'down'

      // Calculate scores
      let trendScore = 0
      let momentumScore = 0
      let volatilityScore = 0
      let volumeScore = 0

      // Trend scoring
      if (currentPrice > ema20) trendScore += 25
      if (currentPrice > ema50) trendScore += 25
      if (emaCross === 'golden') trendScore += 25
      if (adx > 25) trendScore += 25

      // Momentum scoring
      if (rsi > 50 && rsi < 70) momentumScore += 25
      if (macd > 0) momentumScore += 25
      if (stochK > stochD) momentumScore += 25
      if (mfi > 50) momentumScore += 25

      // Volatility scoring (squeeze = opportunity)
      if (inBBSqueeze || inKeltnerSqueeze) volatilityScore += 50
      if (atrPercent < 4) volatilityScore += 25
      if (bbPosition > 0.3 && bbPosition < 0.7) volatilityScore += 25

      // Volume scoring
      if (vwapPosition === 'above') volumeScore += 35
      if (volumeSpike) volumeScore += 35
      if (obvTrend === 'up') volumeScore += 30

      const overallScore = (trendScore + momentumScore + volatilityScore + volumeScore) / 4

      // Determine bias
      let bias = 'neutral'
      if (overallScore > 65 && trendScore > 50 && momentumScore > 50) bias = 'bullish'
      else if (overallScore < 35 && trendScore < 50 && momentumScore < 50) bias = 'bearish'

      // RSI divergence detection
      const rsiDivergence = Math.random() > 0.8
        ? (rsi < 35 ? 'bullish' : rsi > 65 ? 'bearish' : null)
        : null

      // Key levels
      const nearSupport = Math.random() > 0.7
      const nearResistance = Math.random() > 0.7
      const nearPivot = Math.random() > 0.8

      // Signals count
      const bullishSignals = [
        rsi < 35 && rsi > 30,
        macd > 0,
        stochK > stochD && stochK < 80,
        emaCross === 'golden',
        vwapPosition === 'above',
        nearSupport,
        rsiDivergence === 'bullish'
      ].filter(Boolean).length

      const bearishSignals = [
        rsi > 65,
        macd < 0,
        stochK < stochD && stochK > 20,
        emaCross === 'death',
        vwapPosition === 'below',
        nearResistance,
        rsiDivergence === 'bearish'
      ].filter(Boolean).length

      return {
        token,
        currentPrice,

        // Trend
        ema20,
        ema50,
        ema200,
        emaCross,
        adx,
        trendStrength,
        trendScore,

        // Momentum
        rsi,
        macd,
        macdSignal,
        stochK,
        stochD,
        cci,
        mfi,
        momentumScore,

        // Volatility
        bbPosition,
        inBBSqueeze,
        inKeltnerSqueeze,
        atrPercent,
        volatilityScore,

        // Volume
        vwapPosition,
        volumeSpike,
        obvTrend,
        volumeScore,

        // Overall
        overallScore,
        bias,
        rsiDivergence,
        nearSupport,
        nearResistance,
        nearPivot,
        bullishSignals,
        bearishSignals
      }
    })
  }, [])

  // Filtered and sorted data
  const filteredData = useMemo(() => {
    let data = [...scannerData]

    // Filter by bias
    if (filterBias !== 'all') {
      data = data.filter(d => d.bias === filterBias)
    }

    // Sort
    data.sort((a, b) => {
      let aVal, bVal
      switch (sortBy) {
        case 'score': aVal = a.overallScore; bVal = b.overallScore; break
        case 'trend': aVal = a.trendScore; bVal = b.trendScore; break
        case 'momentum': aVal = a.momentumScore; bVal = b.momentumScore; break
        case 'rsi': aVal = a.rsi; bVal = b.rsi; break
        default: aVal = a.overallScore; bVal = b.overallScore
      }
      return sortDir === 'desc' ? bVal - aVal : aVal - bVal
    })

    return data
  }, [scannerData, filterBias, sortBy, sortDir])

  // Stats
  const bullishCount = scannerData.filter(d => d.bias === 'bullish').length
  const bearishCount = scannerData.filter(d => d.bias === 'bearish').length
  const squeezeCount = scannerData.filter(d => d.inBBSqueeze || d.inKeltnerSqueeze).length
  const avgScore = (scannerData.reduce((acc, d) => acc + d.overallScore, 0) / scannerData.length).toFixed(0)

  const getScoreColor = (score) => {
    if (score >= 70) return 'text-green-400'
    if (score >= 50) return 'text-yellow-400'
    if (score >= 30) return 'text-orange-400'
    return 'text-red-400'
  }

  const getScoreBg = (score) => {
    if (score >= 70) return 'bg-green-500'
    if (score >= 50) return 'bg-yellow-500'
    if (score >= 30) return 'bg-orange-500'
    return 'bg-red-500'
  }

  const getBiasIcon = (bias) => {
    if (bias === 'bullish') return <TrendingUp className="w-4 h-4 text-green-400" />
    if (bias === 'bearish') return <TrendingDown className="w-4 h-4 text-red-400" />
    return <Activity className="w-4 h-4 text-white/40" />
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Radar className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Unified Technical Scanner</h1>
            <p className="text-white/60 text-sm">Multi-indicator analysis across all assets</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Filter Bias */}
          <div className="flex items-center gap-2 bg-white/5 rounded-lg px-3 py-2">
            <Filter className="w-4 h-4 text-white/40" />
            <select
              value={filterBias}
              onChange={(e) => setFilterBias(e.target.value)}
              className="bg-transparent text-white text-sm outline-none"
            >
              <option value="all">All</option>
              <option value="bullish">Bullish</option>
              <option value="bearish">Bearish</option>
              <option value="neutral">Neutral</option>
            </select>
          </div>

          {/* View Mode */}
          <div className="flex bg-white/5 rounded-lg p-1">
            {['overview', 'heatmap', 'signals', 'screener'].map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                  viewMode === mode ? 'bg-purple-500 text-white' : 'text-white/60 hover:text-white'
                }`}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>

          <button className="p-2 bg-white/5 rounded-lg hover:bg-white/10">
            <RefreshCw className="w-4 h-4 text-white/60" />
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-5 gap-4 mb-6">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-white/60 text-sm">Bullish</span>
          </div>
          <p className="text-2xl font-bold text-green-400">{bullishCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-4 h-4 text-red-400" />
            <span className="text-white/60 text-sm">Bearish</span>
          </div>
          <p className="text-2xl font-bold text-red-400">{bearishCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-white/60" />
            <span className="text-white/60 text-sm">Neutral</span>
          </div>
          <p className="text-2xl font-bold">{scannerData.length - bullishCount - bearishCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-yellow-400" />
            <span className="text-white/60 text-sm">In Squeeze</span>
          </div>
          <p className="text-2xl font-bold text-yellow-400">{squeezeCount}</p>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Gauge className="w-4 h-4 text-purple-400" />
            <span className="text-white/60 text-sm">Avg Score</span>
          </div>
          <p className="text-2xl font-bold">{avgScore}%</p>
        </div>
      </div>

      {viewMode === 'overview' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Main Scanner Table */}
          <div className="col-span-2 bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <h2 className="font-semibold">Technical Overview</h2>
              <div className="flex items-center gap-2">
                <span className="text-white/60 text-sm">Sort by:</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value)}
                  className="bg-white/5 border border-white/10 rounded px-2 py-1 text-sm"
                >
                  <option value="score">Overall Score</option>
                  <option value="trend">Trend Score</option>
                  <option value="momentum">Momentum</option>
                  <option value="rsi">RSI</option>
                </select>
              </div>
            </div>

            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10 text-xs">
                  <th className="text-left py-3 px-4 text-white/60 font-medium">Token</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">Bias</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">Score</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">Trend</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">Momentum</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">RSI</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">Squeeze</th>
                  <th className="text-center py-3 px-4 text-white/60 font-medium">Signals</th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map((item, idx) => (
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
                        <span className="text-white/40 text-xs">${item.currentPrice.toFixed(2)}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center items-center gap-1">
                        {getBiasIcon(item.bias)}
                        <span className={`text-xs ${
                          item.bias === 'bullish' ? 'text-green-400' :
                          item.bias === 'bearish' ? 'text-red-400' : 'text-white/40'
                        }`}>
                          {item.bias}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center">
                        <div className="w-16">
                          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${getScoreBg(item.overallScore)}`}
                              style={{ width: `${item.overallScore}%` }}
                            />
                          </div>
                          <p className={`text-xs text-center mt-1 ${getScoreColor(item.overallScore)}`}>
                            {item.overallScore.toFixed(0)}%
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`text-xs ${
                        item.trendScore >= 60 ? 'text-green-400' :
                        item.trendScore >= 40 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {item.trendScore}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`text-xs ${
                        item.momentumScore >= 60 ? 'text-green-400' :
                        item.momentumScore >= 40 ? 'text-yellow-400' : 'text-red-400'
                      }`}>
                        {item.momentumScore}%
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className={`text-xs font-medium ${
                        item.rsi > 70 ? 'text-red-400' :
                        item.rsi < 30 ? 'text-green-400' : 'text-white/60'
                      }`}>
                        {item.rsi.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {(item.inBBSqueeze || item.inKeltnerSqueeze) ? (
                        <span className="px-2 py-0.5 rounded text-xs bg-yellow-500/10 text-yellow-400">
                          Active
                        </span>
                      ) : (
                        <span className="text-white/30">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex justify-center items-center gap-2">
                        <div className="flex items-center gap-1">
                          <ArrowUpRight className="w-3 h-3 text-green-400" />
                          <span className="text-xs text-green-400">{item.bullishSignals}</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <ArrowDownRight className="w-3 h-3 text-red-400" />
                          <span className="text-xs text-red-400">{item.bearishSignals}</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Selected Token Details */}
          <div className="space-y-4">
            {(() => {
              const tokenData = scannerData.find(d => d.token === selectedToken)
              return (
                <>
                  {/* Score Breakdown */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <Gauge className="w-4 h-4 text-purple-400" />
                      {selectedToken} Score Breakdown
                    </h3>

                    <div className="space-y-3">
                      {[
                        { label: 'Trend', score: tokenData.trendScore, color: 'bg-blue-500' },
                        { label: 'Momentum', score: tokenData.momentumScore, color: 'bg-purple-500' },
                        { label: 'Volatility', score: tokenData.volatilityScore, color: 'bg-orange-500' },
                        { label: 'Volume', score: tokenData.volumeScore, color: 'bg-cyan-500' }
                      ].map(item => (
                        <div key={item.label}>
                          <div className="flex justify-between text-sm mb-1">
                            <span className="text-white/60">{item.label}</span>
                            <span className={getScoreColor(item.score)}>{item.score}%</span>
                          </div>
                          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${item.color}`}
                              style={{ width: `${item.score}%` }}
                            />
                          </div>
                        </div>
                      ))}

                      <div className="pt-2 border-t border-white/10">
                        <div className="flex justify-between text-sm mb-1">
                          <span className="font-medium">Overall</span>
                          <span className={`font-bold ${getScoreColor(tokenData.overallScore)}`}>
                            {tokenData.overallScore.toFixed(0)}%
                          </span>
                        </div>
                        <div className="h-3 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${getScoreBg(tokenData.overallScore)}`}
                            style={{ width: `${tokenData.overallScore}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Key Indicators */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <BarChart3 className="w-4 h-4 text-cyan-400" />
                      Key Indicators
                    </h3>

                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div className="p-2 bg-white/5 rounded">
                        <p className="text-white/60 text-xs">RSI</p>
                        <p className={`font-medium ${
                          tokenData.rsi > 70 ? 'text-red-400' :
                          tokenData.rsi < 30 ? 'text-green-400' : 'text-white'
                        }`}>
                          {tokenData.rsi.toFixed(1)}
                        </p>
                      </div>
                      <div className="p-2 bg-white/5 rounded">
                        <p className="text-white/60 text-xs">MACD</p>
                        <p className={`font-medium ${
                          tokenData.macd > 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {tokenData.macdSignal}
                        </p>
                      </div>
                      <div className="p-2 bg-white/5 rounded">
                        <p className="text-white/60 text-xs">ADX</p>
                        <p className="font-medium">{tokenData.adx.toFixed(1)}</p>
                      </div>
                      <div className="p-2 bg-white/5 rounded">
                        <p className="text-white/60 text-xs">EMA Cross</p>
                        <p className={`font-medium ${
                          tokenData.emaCross === 'golden' ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {tokenData.emaCross}
                        </p>
                      </div>
                      <div className="p-2 bg-white/5 rounded">
                        <p className="text-white/60 text-xs">VWAP</p>
                        <p className={`font-medium ${
                          tokenData.vwapPosition === 'above' ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {tokenData.vwapPosition}
                        </p>
                      </div>
                      <div className="p-2 bg-white/5 rounded">
                        <p className="text-white/60 text-xs">ATR %</p>
                        <p className="font-medium">{tokenData.atrPercent.toFixed(2)}%</p>
                      </div>
                    </div>
                  </div>

                  {/* Alerts */}
                  <div className="bg-white/5 border border-white/10 rounded-xl p-4">
                    <h3 className="font-semibold mb-3 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                      Alerts
                    </h3>

                    <div className="space-y-2 text-sm">
                      {tokenData.rsiDivergence && (
                        <div className={`p-2 rounded-lg flex items-center gap-2 ${
                          tokenData.rsiDivergence === 'bullish' ? 'bg-green-500/10' : 'bg-red-500/10'
                        }`}>
                          <Zap className={`w-4 h-4 ${
                            tokenData.rsiDivergence === 'bullish' ? 'text-green-400' : 'text-red-400'
                          }`} />
                          <span>RSI {tokenData.rsiDivergence} divergence</span>
                        </div>
                      )}
                      {(tokenData.inBBSqueeze || tokenData.inKeltnerSqueeze) && (
                        <div className="p-2 rounded-lg bg-yellow-500/10 flex items-center gap-2">
                          <Target className="w-4 h-4 text-yellow-400" />
                          <span>Volatility squeeze active</span>
                        </div>
                      )}
                      {tokenData.nearSupport && (
                        <div className="p-2 rounded-lg bg-green-500/10 flex items-center gap-2">
                          <CheckCircle className="w-4 h-4 text-green-400" />
                          <span>Near support level</span>
                        </div>
                      )}
                      {tokenData.nearResistance && (
                        <div className="p-2 rounded-lg bg-red-500/10 flex items-center gap-2">
                          <XCircle className="w-4 h-4 text-red-400" />
                          <span>Near resistance level</span>
                        </div>
                      )}
                      {!tokenData.rsiDivergence && !tokenData.inBBSqueeze && !tokenData.inKeltnerSqueeze && !tokenData.nearSupport && !tokenData.nearResistance && (
                        <p className="text-white/40 text-center py-2">No active alerts</p>
                      )}
                    </div>
                  </div>
                </>
              )
            })()}
          </div>
        </div>
      )}

      {viewMode === 'heatmap' && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <Grid3X3 className="w-5 h-5 text-purple-400" />
            Indicator Heatmap
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="text-left py-2 px-3 text-white/60 text-sm font-medium">Token</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">RSI</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">MACD</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">Stoch</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">MFI</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">ADX</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">EMA</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">BB</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">VWAP</th>
                  <th className="text-center py-2 px-3 text-white/60 text-xs font-medium">OBV</th>
                </tr>
              </thead>
              <tbody>
                {scannerData.map(item => (
                  <tr key={item.token} className="border-b border-white/5 hover:bg-white/5">
                    <td className="py-2 px-3 font-medium">{item.token}</td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        item.rsi > 70 ? 'bg-red-500/30 text-red-400' :
                        item.rsi > 60 ? 'bg-orange-500/30 text-orange-400' :
                        item.rsi > 40 ? 'bg-white/10 text-white/60' :
                        item.rsi > 30 ? 'bg-cyan-500/30 text-cyan-400' :
                        'bg-green-500/30 text-green-400'
                      }`}>
                        {item.rsi.toFixed(0)}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center ${
                        item.macd > 0 ? 'bg-green-500/30' : 'bg-red-500/30'
                      }`}>
                        {item.macd > 0 ? (
                          <TrendingUp className="w-4 h-4 text-green-400" />
                        ) : (
                          <TrendingDown className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        item.stochK > 80 ? 'bg-red-500/30 text-red-400' :
                        item.stochK < 20 ? 'bg-green-500/30 text-green-400' :
                        'bg-white/10 text-white/60'
                      }`}>
                        {item.stochK.toFixed(0)}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        item.mfi > 80 ? 'bg-red-500/30 text-red-400' :
                        item.mfi < 20 ? 'bg-green-500/30 text-green-400' :
                        'bg-white/10 text-white/60'
                      }`}>
                        {item.mfi.toFixed(0)}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center text-xs font-medium ${
                        item.adx > 25 ? 'bg-purple-500/30 text-purple-400' :
                        'bg-white/10 text-white/60'
                      }`}>
                        {item.adx.toFixed(0)}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center ${
                        item.emaCross === 'golden' ? 'bg-green-500/30' : 'bg-red-500/30'
                      }`}>
                        {item.emaCross === 'golden' ? (
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center ${
                        item.inBBSqueeze ? 'bg-yellow-500/30' : 'bg-white/10'
                      }`}>
                        {item.inBBSqueeze ? (
                          <Target className="w-4 h-4 text-yellow-400" />
                        ) : (
                          <Activity className="w-4 h-4 text-white/40" />
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center ${
                        item.vwapPosition === 'above' ? 'bg-green-500/30' : 'bg-red-500/30'
                      }`}>
                        {item.vwapPosition === 'above' ? (
                          <ArrowUpRight className="w-4 h-4 text-green-400" />
                        ) : (
                          <ArrowDownRight className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-3">
                      <div className={`w-8 h-8 rounded flex items-center justify-center ${
                        item.obvTrend === 'up' ? 'bg-green-500/30' : 'bg-red-500/30'
                      }`}>
                        {item.obvTrend === 'up' ? (
                          <TrendingUp className="w-4 h-4 text-green-400" />
                        ) : (
                          <TrendingDown className="w-4 h-4 text-red-400" />
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-4 mt-4 pt-4 border-t border-white/10 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-green-500/30" />
              <span className="text-white/60">Bullish</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-red-500/30" />
              <span className="text-white/60">Bearish</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-yellow-500/30" />
              <span className="text-white/60">Squeeze</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-purple-500/30" />
              <span className="text-white/60">Strong Trend</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-white/10" />
              <span className="text-white/60">Neutral</span>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'signals' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Bullish Signals */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-400" />
              Bullish Signals
            </h2>

            <div className="space-y-3">
              {scannerData.filter(d => d.bias === 'bullish' || d.bullishSignals >= 3).map(item => (
                <div key={item.token} className="p-3 bg-green-500/10 rounded-xl border border-green-500/30">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold">{item.token}</span>
                    <span className="text-green-400 text-sm">{item.bullishSignals} signals</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {item.rsi < 35 && (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">RSI Oversold</span>
                    )}
                    {item.macd > 0 && (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">MACD+</span>
                    )}
                    {item.emaCross === 'golden' && (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">Golden Cross</span>
                    )}
                    {item.vwapPosition === 'above' && (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">Above VWAP</span>
                    )}
                    {item.rsiDivergence === 'bullish' && (
                      <span className="px-2 py-0.5 rounded text-xs bg-green-500/20 text-green-400">RSI Div</span>
                    )}
                  </div>
                </div>
              ))}
              {scannerData.filter(d => d.bias === 'bullish' || d.bullishSignals >= 3).length === 0 && (
                <p className="text-center py-8 text-white/40">No bullish signals</p>
              )}
            </div>
          </div>

          {/* Bearish Signals */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <TrendingDown className="w-5 h-5 text-red-400" />
              Bearish Signals
            </h2>

            <div className="space-y-3">
              {scannerData.filter(d => d.bias === 'bearish' || d.bearishSignals >= 3).map(item => (
                <div key={item.token} className="p-3 bg-red-500/10 rounded-xl border border-red-500/30">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold">{item.token}</span>
                    <span className="text-red-400 text-sm">{item.bearishSignals} signals</span>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {item.rsi > 65 && (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">RSI Overbought</span>
                    )}
                    {item.macd < 0 && (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">MACD-</span>
                    )}
                    {item.emaCross === 'death' && (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">Death Cross</span>
                    )}
                    {item.vwapPosition === 'below' && (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">Below VWAP</span>
                    )}
                    {item.rsiDivergence === 'bearish' && (
                      <span className="px-2 py-0.5 rounded text-xs bg-red-500/20 text-red-400">RSI Div</span>
                    )}
                  </div>
                </div>
              ))}
              {scannerData.filter(d => d.bias === 'bearish' || d.bearishSignals >= 3).length === 0 && (
                <p className="text-center py-8 text-white/40">No bearish signals</p>
              )}
            </div>
          </div>
        </div>
      )}

      {viewMode === 'screener' && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <Search className="w-5 h-5 text-cyan-400" />
            Custom Screener
          </h2>

          {/* Filter Controls */}
          <div className="grid grid-cols-4 gap-4 mb-4 p-4 bg-white/5 rounded-lg">
            <div>
              <label className="text-white/60 text-xs block mb-1">RSI Range</label>
              <div className="flex gap-2">
                <input type="number" placeholder="Min" className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-sm" defaultValue="30" />
                <input type="number" placeholder="Max" className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-sm" defaultValue="70" />
              </div>
            </div>
            <div>
              <label className="text-white/60 text-xs block mb-1">MACD</label>
              <select className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-sm">
                <option value="all">Any</option>
                <option value="bullish">Bullish</option>
                <option value="bearish">Bearish</option>
              </select>
            </div>
            <div>
              <label className="text-white/60 text-xs block mb-1">VWAP Position</label>
              <select className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-sm">
                <option value="all">Any</option>
                <option value="above">Above</option>
                <option value="below">Below</option>
              </select>
            </div>
            <div>
              <label className="text-white/60 text-xs block mb-1">Squeeze</label>
              <select className="w-full px-2 py-1 bg-white/5 border border-white/10 rounded text-sm">
                <option value="all">Any</option>
                <option value="active">Active</option>
                <option value="none">None</option>
              </select>
            </div>
          </div>

          <div className="flex justify-between items-center mb-4">
            <p className="text-white/60 text-sm">{scannerData.length} results</p>
            <button className="px-4 py-2 bg-purple-500 rounded-lg text-sm hover:bg-purple-600">
              Apply Filters
            </button>
          </div>

          {/* Results Table */}
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left py-2 px-3 text-white/60 text-sm font-medium">Token</th>
                <th className="text-right py-2 px-3 text-white/60 text-sm font-medium">Price</th>
                <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">RSI</th>
                <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">MACD</th>
                <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">Stoch</th>
                <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">ADX</th>
                <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">VWAP</th>
                <th className="text-center py-2 px-3 text-white/60 text-sm font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {scannerData.map((item, idx) => (
                <tr key={item.token} className={`border-b border-white/5 hover:bg-white/5 ${idx % 2 === 0 ? 'bg-white/[0.02]' : ''}`}>
                  <td className="py-2 px-3 font-medium">{item.token}</td>
                  <td className="py-2 px-3 text-right">${item.currentPrice.toFixed(2)}</td>
                  <td className="py-2 px-3 text-center">
                    <span className={item.rsi > 70 ? 'text-red-400' : item.rsi < 30 ? 'text-green-400' : ''}>
                      {item.rsi.toFixed(1)}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className={item.macd > 0 ? 'text-green-400' : 'text-red-400'}>
                      {item.macdSignal}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">{item.stochK.toFixed(0)}/{item.stochD.toFixed(0)}</td>
                  <td className="py-2 px-3 text-center">{item.adx.toFixed(1)}</td>
                  <td className="py-2 px-3 text-center">
                    <span className={item.vwapPosition === 'above' ? 'text-green-400' : 'text-red-400'}>
                      {item.vwapPosition}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-center">
                    <span className={getScoreColor(item.overallScore)}>{item.overallScore.toFixed(0)}%</span>
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

export default UnifiedScanner
