import React, { useState, useMemo, useEffect } from 'react'
import {
  Cloud,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  Target,
  ChevronUp,
  ChevronDown,
  AlertTriangle,
  Info,
  Eye,
  Minus
} from 'lucide-react'

export function IchimokuCloud() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [viewMode, setViewMode] = useState('overview') // overview, signals, components
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '1d', '1w']

  // Generate mock Ichimoku data
  const ichimokuData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    // Tenkan-sen (Conversion Line) - 9 period
    const tenkanSen = currentPrice * (0.98 + Math.random() * 0.04)

    // Kijun-sen (Base Line) - 26 period
    const kijunSen = currentPrice * (0.96 + Math.random() * 0.08)

    // Senkou Span A (Leading Span A) - (Tenkan + Kijun) / 2, displaced 26 periods
    const senkouSpanA = (tenkanSen + kijunSen) / 2

    // Senkou Span B (Leading Span B) - 52 period midpoint, displaced 26 periods
    const senkouSpanB = currentPrice * (0.92 + Math.random() * 0.16)

    // Chikou Span (Lagging Span) - current price displaced 26 periods back
    const chikouSpan = currentPrice

    // Cloud color
    const cloudBullish = senkouSpanA > senkouSpanB
    const cloudTop = Math.max(senkouSpanA, senkouSpanB)
    const cloudBottom = Math.min(senkouSpanA, senkouSpanB)
    const cloudThickness = ((cloudTop - cloudBottom) / currentPrice) * 100

    // Price position relative to cloud
    const aboveCloud = currentPrice > cloudTop
    const belowCloud = currentPrice < cloudBottom
    const inCloud = !aboveCloud && !belowCloud

    // TK Cross (Tenkan/Kijun)
    const tkCross = tenkanSen > kijunSen ? 'bullish' : tenkanSen < kijunSen ? 'bearish' : 'neutral'

    // Kumo Twist (future cloud color change)
    const kumoTwist = Math.random() > 0.7

    // Generate signals
    const signals = []

    // TK Cross Signal
    if (tkCross === 'bullish') {
      signals.push({
        type: 'TK Cross',
        signal: 'bullish',
        strength: aboveCloud ? 'strong' : inCloud ? 'neutral' : 'weak',
        description: 'Tenkan above Kijun (bullish crossover)'
      })
    } else if (tkCross === 'bearish') {
      signals.push({
        type: 'TK Cross',
        signal: 'bearish',
        strength: belowCloud ? 'strong' : inCloud ? 'neutral' : 'weak',
        description: 'Tenkan below Kijun (bearish crossover)'
      })
    }

    // Price/Cloud Signal
    if (aboveCloud) {
      signals.push({
        type: 'Price/Cloud',
        signal: 'bullish',
        strength: cloudBullish ? 'strong' : 'neutral',
        description: 'Price above the Kumo cloud'
      })
    } else if (belowCloud) {
      signals.push({
        type: 'Price/Cloud',
        signal: 'bearish',
        strength: !cloudBullish ? 'strong' : 'neutral',
        description: 'Price below the Kumo cloud'
      })
    } else {
      signals.push({
        type: 'Price/Cloud',
        signal: 'neutral',
        strength: 'weak',
        description: 'Price inside the Kumo (consolidation)'
      })
    }

    // Chikou Span Signal
    const chikouAbovePrice = chikouSpan > currentPrice * 0.98
    signals.push({
      type: 'Chikou Span',
      signal: chikouAbovePrice ? 'bullish' : 'bearish',
      strength: 'neutral',
      description: chikouAbovePrice ? 'Chikou above price 26 periods ago' : 'Chikou below price 26 periods ago'
    })

    // Future Cloud Signal
    signals.push({
      type: 'Future Cloud',
      signal: cloudBullish ? 'bullish' : 'bearish',
      strength: 'neutral',
      description: cloudBullish ? 'Future cloud is bullish (Span A > Span B)' : 'Future cloud is bearish (Span B > Span A)'
    })

    // Overall bias
    const bullishSignals = signals.filter(s => s.signal === 'bullish').length
    const bearishSignals = signals.filter(s => s.signal === 'bearish').length
    const overallBias = bullishSignals > bearishSignals ? 'bullish' :
                       bearishSignals > bullishSignals ? 'bearish' : 'neutral'

    // Support/Resistance from cloud
    const support = belowCloud ? cloudBottom : cloudBottom
    const resistance = aboveCloud ? cloudTop : cloudTop

    // Generate historical cloud data for visualization
    const cloudHistory = Array.from({ length: 52 }, (_, i) => {
      const spanA = currentPrice * (0.95 + Math.random() * 0.1)
      const spanB = currentPrice * (0.93 + Math.random() * 0.14)
      return {
        period: i - 26,
        spanA,
        spanB,
        bullish: spanA > spanB
      }
    })

    return {
      currentPrice,
      tenkanSen,
      kijunSen,
      senkouSpanA,
      senkouSpanB,
      chikouSpan,
      cloudBullish,
      cloudTop,
      cloudBottom,
      cloudThickness,
      aboveCloud,
      belowCloud,
      inCloud,
      tkCross,
      kumoTwist,
      signals,
      overallBias,
      bullishSignals,
      bearishSignals,
      support,
      resistance,
      cloudHistory
    }
  }, [selectedToken, timeframe])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const getBiasColor = (bias) => {
    switch(bias) {
      case 'bullish': return 'text-green-400'
      case 'bearish': return 'text-red-400'
      default: return 'text-yellow-400'
    }
  }

  const getBiasBg = (bias) => {
    switch(bias) {
      case 'bullish': return 'bg-green-500/10 border-green-500/20'
      case 'bearish': return 'bg-red-500/10 border-red-500/20'
      default: return 'bg-yellow-500/10 border-yellow-500/20'
    }
  }

  const getStrengthColor = (strength) => {
    switch(strength) {
      case 'strong': return 'text-green-400'
      case 'weak': return 'text-red-400'
      default: return 'text-yellow-400'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Cloud className="w-6 h-6 text-sky-400" />
          <h2 className="text-xl font-bold text-white">Ichimoku Cloud</h2>
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
          <select
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
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

      {/* Overall Bias */}
      <div className={`rounded-lg p-4 mb-6 border ${getBiasBg(ichimokuData.overallBias)}`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">Overall Bias</div>
            <div className={`text-2xl font-bold capitalize flex items-center gap-2 ${getBiasColor(ichimokuData.overallBias)}`}>
              {ichimokuData.overallBias === 'bullish' ? <TrendingUp className="w-5 h-5" /> :
               ichimokuData.overallBias === 'bearish' ? <TrendingDown className="w-5 h-5" /> :
               <Minus className="w-5 h-5" />}
              {ichimokuData.overallBias}
            </div>
            <div className="text-gray-500 text-sm">
              {ichimokuData.bullishSignals} bullish / {ichimokuData.bearishSignals} bearish
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Price Position</div>
            <div className={`text-lg font-medium ${
              ichimokuData.aboveCloud ? 'text-green-400' :
              ichimokuData.belowCloud ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {ichimokuData.aboveCloud ? 'Above Cloud' :
               ichimokuData.belowCloud ? 'Below Cloud' : 'Inside Cloud'}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">TK Cross</div>
            <div className={`text-lg font-medium capitalize ${getBiasColor(ichimokuData.tkCross)}`}>
              {ichimokuData.tkCross}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Cloud Thickness</div>
            <div className="text-lg font-medium text-white">{ichimokuData.cloudThickness.toFixed(2)}%</div>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'overview', label: 'Overview' },
          { id: 'signals', label: 'Signals' },
          { id: 'components', label: 'Components' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Overview */}
      {viewMode === 'overview' && (
        <div className="space-y-4">
          {/* Cloud Visualization */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Kumo Cloud</h3>
            <div className="relative h-48">
              {/* Cloud area */}
              <div className="absolute inset-0 flex items-end">
                {ichimokuData.cloudHistory.map((point, i) => {
                  const height = 100
                  const spanAPos = ((point.spanA - ichimokuData.currentPrice * 0.85) / (ichimokuData.currentPrice * 0.3)) * height
                  const spanBPos = ((point.spanB - ichimokuData.currentPrice * 0.85) / (ichimokuData.currentPrice * 0.3)) * height
                  const top = Math.max(spanAPos, spanBPos)
                  const bottom = Math.min(spanAPos, spanBPos)

                  return (
                    <div key={i} className="flex-1 relative h-full">
                      <div
                        className={`absolute left-0 right-0 ${point.bullish ? 'bg-green-500/30' : 'bg-red-500/30'}`}
                        style={{
                          bottom: `${bottom}%`,
                          height: `${top - bottom}%`
                        }}
                      />
                    </div>
                  )
                })}
              </div>

              {/* Current price line */}
              <div className="absolute left-0 right-0 top-1/2 h-0.5 bg-white z-10">
                <span className="absolute right-0 -top-5 text-xs text-white bg-white/20 px-2 py-0.5 rounded">
                  ${formatPrice(ichimokuData.currentPrice)}
                </span>
              </div>

              {/* Tenkan-sen */}
              <div
                className="absolute left-0 right-0 h-0.5 bg-cyan-400 z-10"
                style={{
                  top: `${50 - ((ichimokuData.tenkanSen - ichimokuData.currentPrice) / ichimokuData.currentPrice * 200)}%`
                }}
              >
                <span className="absolute left-0 -top-4 text-xs text-cyan-400">Tenkan</span>
              </div>

              {/* Kijun-sen */}
              <div
                className="absolute left-0 right-0 h-0.5 bg-red-400 z-10"
                style={{
                  top: `${50 - ((ichimokuData.kijunSen - ichimokuData.currentPrice) / ichimokuData.currentPrice * 200)}%`
                }}
              >
                <span className="absolute left-0 -top-4 text-xs text-red-400">Kijun</span>
              </div>

              {/* Legend */}
              <div className="absolute bottom-0 right-0 flex gap-4 text-xs">
                <span className="text-cyan-400">Tenkan (9)</span>
                <span className="text-red-400">Kijun (26)</span>
                <span className="text-green-400">Bullish Cloud</span>
                <span className="text-red-400">Bearish Cloud</span>
              </div>
            </div>
          </div>

          {/* Key Levels */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Cloud Top</div>
              <div className="text-white font-medium">${formatPrice(ichimokuData.cloudTop)}</div>
              <div className="text-red-400 text-xs">Resistance</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Cloud Bottom</div>
              <div className="text-white font-medium">${formatPrice(ichimokuData.cloudBottom)}</div>
              <div className="text-green-400 text-xs">Support</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Tenkan-sen</div>
              <div className="text-cyan-400 font-medium">${formatPrice(ichimokuData.tenkanSen)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Kijun-sen</div>
              <div className="text-red-400 font-medium">${formatPrice(ichimokuData.kijunSen)}</div>
            </div>
          </div>

          {/* Trading Setup */}
          <div className={`rounded-lg p-4 border ${getBiasBg(ichimokuData.overallBias)}`}>
            <h3 className="text-white font-medium mb-2">Trading Setup</h3>
            <div className="text-gray-400 text-sm space-y-1">
              {ichimokuData.aboveCloud && ichimokuData.tkCross === 'bullish' && (
                <p>Strong bullish setup: Price above cloud with bullish TK cross. Look for long entries on pullbacks to Tenkan or Kijun.</p>
              )}
              {ichimokuData.belowCloud && ichimokuData.tkCross === 'bearish' && (
                <p>Strong bearish setup: Price below cloud with bearish TK cross. Look for short entries on rallies to Tenkan or Kijun.</p>
              )}
              {ichimokuData.inCloud && (
                <p>Consolidation: Price inside the cloud indicates indecision. Wait for a clear break above or below the cloud.</p>
              )}
              {ichimokuData.aboveCloud && ichimokuData.tkCross === 'bearish' && (
                <p>Mixed signals: Price above cloud but bearish TK cross. Potential reversal forming - watch for confirmation.</p>
              )}
              {ichimokuData.belowCloud && ichimokuData.tkCross === 'bullish' && (
                <p>Mixed signals: Price below cloud but bullish TK cross. Potential reversal forming - watch for confirmation.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Signals View */}
      {viewMode === 'signals' && (
        <div className="space-y-3">
          {ichimokuData.signals.map((signal, i) => (
            <div key={i} className={`rounded-lg p-4 border ${getBiasBg(signal.signal)}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  {signal.signal === 'bullish' ? (
                    <ChevronUp className="w-5 h-5 text-green-400" />
                  ) : signal.signal === 'bearish' ? (
                    <ChevronDown className="w-5 h-5 text-red-400" />
                  ) : (
                    <Minus className="w-5 h-5 text-yellow-400" />
                  )}
                  <span className="text-white font-medium">{signal.type}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`capitalize ${getBiasColor(signal.signal)}`}>{signal.signal}</span>
                  <span className={`text-xs px-2 py-0.5 rounded bg-white/10 ${getStrengthColor(signal.strength)}`}>
                    {signal.strength}
                  </span>
                </div>
              </div>
              <p className="text-gray-400 text-sm">{signal.description}</p>
            </div>
          ))}

          {/* Kumo Twist Alert */}
          {ichimokuData.kumoTwist && (
            <div className="bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-5 h-5 text-purple-400" />
                <span className="text-purple-400 font-medium">Kumo Twist Detected</span>
              </div>
              <p className="text-gray-400 text-sm">
                The future cloud is about to change color, indicating a potential trend change. Watch for price confirmation.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Components View */}
      {viewMode === 'components' && (
        <div className="space-y-4">
          {/* Component Descriptions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-cyan-500/10 rounded-lg p-4 border border-cyan-500/20">
              <h3 className="text-cyan-400 font-medium mb-2">Tenkan-sen (Conversion Line)</h3>
              <div className="text-2xl font-bold text-white mb-2">${formatPrice(ichimokuData.tenkanSen)}</div>
              <p className="text-gray-400 text-sm">
                9-period midpoint. Fast-moving signal line. Represents short-term momentum.
              </p>
              <div className="mt-2 text-sm">
                <span className="text-gray-500">vs Price: </span>
                <span className={ichimokuData.currentPrice > ichimokuData.tenkanSen ? 'text-green-400' : 'text-red-400'}>
                  {((ichimokuData.currentPrice - ichimokuData.tenkanSen) / ichimokuData.tenkanSen * 100).toFixed(2)}%
                </span>
              </div>
            </div>

            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <h3 className="text-red-400 font-medium mb-2">Kijun-sen (Base Line)</h3>
              <div className="text-2xl font-bold text-white mb-2">${formatPrice(ichimokuData.kijunSen)}</div>
              <p className="text-gray-400 text-sm">
                26-period midpoint. Slower signal line and key support/resistance level.
              </p>
              <div className="mt-2 text-sm">
                <span className="text-gray-500">vs Price: </span>
                <span className={ichimokuData.currentPrice > ichimokuData.kijunSen ? 'text-green-400' : 'text-red-400'}>
                  {((ichimokuData.currentPrice - ichimokuData.kijunSen) / ichimokuData.kijunSen * 100).toFixed(2)}%
                </span>
              </div>
            </div>

            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <h3 className="text-green-400 font-medium mb-2">Senkou Span A (Leading Span A)</h3>
              <div className="text-2xl font-bold text-white mb-2">${formatPrice(ichimokuData.senkouSpanA)}</div>
              <p className="text-gray-400 text-sm">
                Average of Tenkan and Kijun, plotted 26 periods ahead. Forms one edge of the cloud.
              </p>
            </div>

            <div className="bg-orange-500/10 rounded-lg p-4 border border-orange-500/20">
              <h3 className="text-orange-400 font-medium mb-2">Senkou Span B (Leading Span B)</h3>
              <div className="text-2xl font-bold text-white mb-2">${formatPrice(ichimokuData.senkouSpanB)}</div>
              <p className="text-gray-400 text-sm">
                52-period midpoint, plotted 26 periods ahead. Forms the other edge of the cloud.
              </p>
            </div>

            <div className="md:col-span-2 bg-purple-500/10 rounded-lg p-4 border border-purple-500/20">
              <h3 className="text-purple-400 font-medium mb-2">Chikou Span (Lagging Span)</h3>
              <div className="text-2xl font-bold text-white mb-2">${formatPrice(ichimokuData.chikouSpan)}</div>
              <p className="text-gray-400 text-sm">
                Current closing price plotted 26 periods behind. Used to confirm trend direction by comparing to historical price.
              </p>
            </div>
          </div>

          {/* Ichimoku Guide */}
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
            <h3 className="text-blue-400 font-medium mb-2 flex items-center gap-2">
              <Info className="w-4 h-4" />
              Ichimoku Trading Rules
            </h3>
            <div className="text-gray-400 text-sm space-y-2">
              <p><span className="text-green-400">Bullish:</span> Price above cloud, Tenkan above Kijun, Chikou above price</p>
              <p><span className="text-red-400">Bearish:</span> Price below cloud, Tenkan below Kijun, Chikou below price</p>
              <p><span className="text-yellow-400">Neutral:</span> Price inside cloud - wait for breakout</p>
              <p><span className="text-purple-400">Strong signals:</span> All 5 components aligned in same direction</p>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>Tenkan = 9-period</span>
          <span>Kijun = 26-period</span>
          <span>Senkou B = 52-period</span>
          <span>Displacement = 26 periods</span>
        </div>
      </div>
    </div>
  )
}

export default IchimokuCloud
