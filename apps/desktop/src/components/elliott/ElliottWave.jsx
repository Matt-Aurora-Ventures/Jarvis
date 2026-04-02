import React, { useState, useMemo, useEffect } from 'react'
import {
  Waves,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  Target,
  ChevronUp,
  ChevronDown,
  AlertTriangle,
  Info,
  Zap,
  ArrowRight
} from 'lucide-react'

export function ElliottWave() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [viewMode, setViewMode] = useState('waves') // waves, fibonacci, forecast
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '1d', '1w']

  // Generate mock Elliott Wave data
  const elliottData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    const isImpulsive = Math.random() > 0.3
    const trendDirection = Math.random() > 0.5 ? 'bullish' : 'bearish'

    // Wave structure
    const waveStart = currentPrice * 0.7
    const wave1End = waveStart * 1.15
    const wave2End = wave1End * 0.95
    const wave3End = wave2End * 1.25
    const wave4End = wave3End * 0.92
    const wave5End = wave4End * 1.12

    const waves = isImpulsive ? [
      {
        wave: '1',
        type: 'impulse',
        start: waveStart,
        end: wave1End,
        retracement: null,
        extension: ((wave1End - waveStart) / waveStart * 100).toFixed(1),
        complete: true,
        current: false
      },
      {
        wave: '2',
        type: 'corrective',
        start: wave1End,
        end: wave2End,
        retracement: 50 + Math.random() * 12,
        extension: null,
        complete: true,
        current: false
      },
      {
        wave: '3',
        type: 'impulse',
        start: wave2End,
        end: wave3End,
        retracement: null,
        extension: 161.8 + Math.random() * 50,
        complete: true,
        current: false
      },
      {
        wave: '4',
        type: 'corrective',
        start: wave3End,
        end: wave4End,
        retracement: 23.6 + Math.random() * 15,
        extension: null,
        complete: Math.random() > 0.5,
        current: Math.random() > 0.7
      },
      {
        wave: '5',
        type: 'impulse',
        start: wave4End,
        end: wave5End,
        retracement: null,
        extension: 100 + Math.random() * 61.8,
        complete: false,
        current: Math.random() > 0.5
      }
    ] : [
      {
        wave: 'A',
        type: 'impulse',
        start: currentPrice * 1.1,
        end: currentPrice * 0.95,
        retracement: null,
        extension: -15,
        complete: true,
        current: false
      },
      {
        wave: 'B',
        type: 'corrective',
        start: currentPrice * 0.95,
        end: currentPrice * 1.02,
        retracement: 50 + Math.random() * 28,
        extension: null,
        complete: true,
        current: false
      },
      {
        wave: 'C',
        type: 'impulse',
        start: currentPrice * 1.02,
        end: currentPrice * 0.88,
        retracement: null,
        extension: 100 + Math.random() * 61.8,
        complete: false,
        current: true
      }
    ]

    // Current wave detection
    const currentWave = waves.find(w => w.current) || waves[waves.length - 1]

    // Fibonacci levels
    const fibLevels = {
      retracements: [
        { level: 0.236, price: currentPrice * (1 - 0.236 * 0.15), name: '23.6%' },
        { level: 0.382, price: currentPrice * (1 - 0.382 * 0.15), name: '38.2%' },
        { level: 0.5, price: currentPrice * (1 - 0.5 * 0.15), name: '50%' },
        { level: 0.618, price: currentPrice * (1 - 0.618 * 0.15), name: '61.8%' },
        { level: 0.786, price: currentPrice * (1 - 0.786 * 0.15), name: '78.6%' }
      ],
      extensions: [
        { level: 1.0, price: currentPrice * 1.1, name: '100%' },
        { level: 1.272, price: currentPrice * 1.127, name: '127.2%' },
        { level: 1.618, price: currentPrice * 1.162, name: '161.8%' },
        { level: 2.0, price: currentPrice * 1.2, name: '200%' },
        { level: 2.618, price: currentPrice * 1.262, name: '261.8%' }
      ]
    }

    // Wave rules validation
    const rules = [
      {
        name: 'Wave 2 never retraces more than 100% of Wave 1',
        valid: waves[1]?.retracement ? waves[1].retracement < 100 : true,
        description: 'Wave 2 retracement must be less than 100%'
      },
      {
        name: 'Wave 3 is never the shortest impulse wave',
        valid: true, // Simplified
        description: 'Wave 3 typically extends 161.8% of Wave 1'
      },
      {
        name: 'Wave 4 does not overlap Wave 1 territory',
        valid: waves[3]?.end > waves[0]?.end,
        description: 'Wave 4 low must be above Wave 1 high'
      }
    ]

    // Forecast targets
    const targets = isImpulsive ? [
      {
        name: 'Wave 5 Target (100%)',
        price: wave4End * 1.1,
        probability: 70
      },
      {
        name: 'Wave 5 Target (161.8%)',
        price: wave4End * 1.162,
        probability: 50
      },
      {
        name: 'Wave 5 Extended (261.8%)',
        price: wave4End * 1.262,
        probability: 25
      }
    ] : [
      {
        name: 'Wave C Target (100%)',
        price: currentPrice * 0.9,
        probability: 65
      },
      {
        name: 'Wave C Extended (161.8%)',
        price: currentPrice * 0.84,
        probability: 35
      }
    ]

    // Degree labels
    const degrees = ['Grand Supercycle', 'Supercycle', 'Cycle', 'Primary', 'Intermediate', 'Minor', 'Minute', 'Minuette', 'Subminuette']
    const currentDegree = degrees[Math.floor(Math.random() * 4) + 3]

    return {
      currentPrice,
      isImpulsive,
      trendDirection,
      waves,
      currentWave,
      fibLevels,
      rules,
      targets,
      currentDegree,
      waveCount: isImpulsive ? '5-wave impulse' : '3-wave correction'
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

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Waves className="w-6 h-6 text-teal-400" />
          <h2 className="text-xl font-bold text-white">Elliott Wave Analysis</h2>
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

      {/* Wave Summary */}
      <div className={`rounded-lg p-4 mb-6 border ${
        elliottData.isImpulsive ? 'bg-blue-500/10 border-blue-500/20' : 'bg-orange-500/10 border-orange-500/20'
      }`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">Wave Structure</div>
            <div className={`text-xl font-bold ${elliottData.isImpulsive ? 'text-blue-400' : 'text-orange-400'}`}>
              {elliottData.waveCount}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Current Wave</div>
            <div className="text-xl font-bold text-white">
              Wave {elliottData.currentWave.wave}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Wave Degree</div>
            <div className="text-lg font-medium text-gray-300">{elliottData.currentDegree}</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Trend</div>
            <div className={`text-lg font-medium capitalize flex items-center gap-2 ${
              elliottData.trendDirection === 'bullish' ? 'text-green-400' : 'text-red-400'
            }`}>
              {elliottData.trendDirection === 'bullish' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
              {elliottData.trendDirection}
            </div>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'waves', label: 'Wave Count' },
          { id: 'fibonacci', label: 'Fibonacci' },
          { id: 'forecast', label: 'Forecast' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Waves View */}
      {viewMode === 'waves' && (
        <div className="space-y-4">
          {/* Wave Visualization */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Wave Structure</h3>
            <div className="relative h-48">
              {elliottData.isImpulsive ? (
                // 5-wave impulse pattern visualization
                <svg viewBox="0 0 400 150" className="w-full h-full">
                  {/* Wave 1 */}
                  <line x1="20" y1="120" x2="80" y2="60" stroke="#22c55e" strokeWidth="2" />
                  <text x="50" y="80" fill="#22c55e" fontSize="12">1</text>

                  {/* Wave 2 */}
                  <line x1="80" y1="60" x2="120" y2="90" stroke="#ef4444" strokeWidth="2" />
                  <text x="100" y="85" fill="#ef4444" fontSize="12">2</text>

                  {/* Wave 3 */}
                  <line x1="120" y1="90" x2="220" y2="20" stroke="#22c55e" strokeWidth="3" />
                  <text x="170" y="45" fill="#22c55e" fontSize="12">3</text>

                  {/* Wave 4 */}
                  <line x1="220" y1="20" x2="280" y2="50" stroke="#ef4444" strokeWidth="2" />
                  <text x="250" y="45" fill="#ef4444" fontSize="12">4</text>

                  {/* Wave 5 */}
                  <line x1="280" y1="50" x2="380" y2="10" stroke="#22c55e" strokeWidth="2" strokeDasharray={elliottData.currentWave.wave === '5' ? '5,5' : ''} />
                  <text x="330" y="25" fill="#22c55e" fontSize="12">5</text>

                  {/* Current price indicator */}
                  <circle cx={elliottData.currentWave.wave === '5' ? 330 : elliottData.currentWave.wave === '4' ? 250 : 200} cy="35" r="5" fill="#eab308" />
                </svg>
              ) : (
                // 3-wave correction pattern visualization
                <svg viewBox="0 0 400 150" className="w-full h-full">
                  {/* Wave A */}
                  <line x1="20" y1="30" x2="130" y2="100" stroke="#ef4444" strokeWidth="2" />
                  <text x="75" y="75" fill="#ef4444" fontSize="12">A</text>

                  {/* Wave B */}
                  <line x1="130" y1="100" x2="220" y2="50" stroke="#22c55e" strokeWidth="2" />
                  <text x="175" y="65" fill="#22c55e" fontSize="12">B</text>

                  {/* Wave C */}
                  <line x1="220" y1="50" x2="380" y2="130" stroke="#ef4444" strokeWidth="2" strokeDasharray={elliottData.currentWave.wave === 'C' ? '5,5' : ''} />
                  <text x="300" y="100" fill="#ef4444" fontSize="12">C</text>

                  {/* Current price indicator */}
                  <circle cx="300" cy="90" r="5" fill="#eab308" />
                </svg>
              )}
            </div>
          </div>

          {/* Wave Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {elliottData.waves.map(wave => (
              <div key={wave.wave} className={`p-3 rounded-lg border ${
                wave.current ? 'bg-yellow-500/10 border-yellow-500/20' :
                wave.complete ? 'bg-white/5 border-white/10' :
                'bg-white/5 border-white/10 opacity-50'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-lg font-bold ${
                    wave.type === 'impulse' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    Wave {wave.wave}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500 capitalize">{wave.type}</span>
                    {wave.current && <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">Current</span>}
                  </div>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Start</span>
                    <span className="text-white">${formatPrice(wave.start)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">End</span>
                    <span className="text-white">${formatPrice(wave.end)}</span>
                  </div>
                  {wave.retracement && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Retracement</span>
                      <span className="text-orange-400">{wave.retracement.toFixed(1)}%</span>
                    </div>
                  )}
                  {wave.extension && (
                    <div className="flex justify-between">
                      <span className="text-gray-400">Extension</span>
                      <span className="text-cyan-400">{wave.extension}%</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Wave Rules */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-400" />
              Elliott Wave Rules
            </h3>
            <div className="space-y-2">
              {elliottData.rules.map((rule, i) => (
                <div key={i} className="flex items-center justify-between p-2 bg-white/5 rounded">
                  <div className="flex items-center gap-2">
                    {rule.valid ? (
                      <div className="w-2 h-2 bg-green-500 rounded-full" />
                    ) : (
                      <div className="w-2 h-2 bg-red-500 rounded-full" />
                    )}
                    <span className="text-gray-300 text-sm">{rule.name}</span>
                  </div>
                  <span className={rule.valid ? 'text-green-400 text-sm' : 'text-red-400 text-sm'}>
                    {rule.valid ? 'Valid' : 'Invalid'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Fibonacci View */}
      {viewMode === 'fibonacci' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Retracements */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <ChevronDown className="w-4 h-4 text-red-400" />
              Fibonacci Retracements
            </h3>
            <div className="space-y-2">
              {elliottData.fibLevels.retracements.map((fib, i) => (
                <div key={i} className="flex items-center justify-between p-2 hover:bg-white/5 rounded">
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded ${
                      fib.level === 0.618 ? 'bg-yellow-500' :
                      fib.level === 0.5 ? 'bg-cyan-500' : 'bg-gray-500'
                    }`} />
                    <span className="text-white">{fib.name}</span>
                  </div>
                  <span className="text-gray-400">${formatPrice(fib.price)}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 p-2 bg-yellow-500/10 rounded border border-yellow-500/20 text-sm text-yellow-400">
              61.8% is the golden ratio - most reliable retracement level
            </div>
          </div>

          {/* Extensions */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <ChevronUp className="w-4 h-4 text-green-400" />
              Fibonacci Extensions
            </h3>
            <div className="space-y-2">
              {elliottData.fibLevels.extensions.map((fib, i) => (
                <div key={i} className="flex items-center justify-between p-2 hover:bg-white/5 rounded">
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded ${
                      fib.level === 1.618 ? 'bg-yellow-500' :
                      fib.level === 1.0 ? 'bg-cyan-500' : 'bg-gray-500'
                    }`} />
                    <span className="text-white">{fib.name}</span>
                  </div>
                  <span className="text-gray-400">${formatPrice(fib.price)}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 p-2 bg-cyan-500/10 rounded border border-cyan-500/20 text-sm text-cyan-400">
              161.8% is common for Wave 3 extension targets
            </div>
          </div>

          {/* Fib Confluence */}
          <div className="md:col-span-2 bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              Fibonacci Confluence Zones
            </h3>
            <div className="relative h-32 bg-gradient-to-b from-red-500/10 via-transparent to-green-500/10 rounded-lg">
              {/* Current price line */}
              <div className="absolute left-0 right-0 top-1/2 h-0.5 bg-white">
                <span className="absolute left-2 -top-5 text-xs text-white bg-white/10 px-2 py-0.5 rounded">
                  ${formatPrice(elliottData.currentPrice)}
                </span>
              </div>
              {/* Key levels */}
              <div className="absolute left-0 right-0 top-1/4 h-0.5 bg-yellow-500/50 border-dashed">
                <span className="absolute right-2 -top-5 text-xs text-yellow-400">61.8% ext</span>
              </div>
              <div className="absolute left-0 right-0 top-3/4 h-0.5 bg-cyan-500/50 border-dashed">
                <span className="absolute right-2 -top-5 text-xs text-cyan-400">61.8% ret</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Forecast View */}
      {viewMode === 'forecast' && (
        <div className="space-y-4">
          {/* Price Targets */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4 flex items-center gap-2">
              <Target className="w-4 h-4 text-green-400" />
              Price Targets
            </h3>
            <div className="space-y-3">
              {elliottData.targets.map((target, i) => (
                <div key={i} className="p-3 bg-white/5 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-medium">{target.name}</span>
                    <span className={`text-lg font-bold ${
                      target.price > elliottData.currentPrice ? 'text-green-400' : 'text-red-400'
                    }`}>
                      ${formatPrice(target.price)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Probability</span>
                    <div className="flex items-center gap-2">
                      <div className="w-24 h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            target.probability > 60 ? 'bg-green-500' :
                            target.probability > 40 ? 'bg-yellow-500' : 'bg-red-500'
                          }`}
                          style={{ width: `${target.probability}%` }}
                        />
                      </div>
                      <span className="text-gray-400 text-sm">{target.probability}%</span>
                    </div>
                  </div>
                  <div className="mt-2 text-sm text-gray-500">
                    {((target.price - elliottData.currentPrice) / elliottData.currentPrice * 100).toFixed(1)}% from current price
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Wave Forecast */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-400" />
              Next Expected Move
            </h3>
            <div className={`p-4 rounded-lg border ${
              elliottData.isImpulsive && elliottData.currentWave.type === 'impulse'
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-red-500/10 border-red-500/20'
            }`}>
              <div className="flex items-center gap-3 mb-2">
                {elliottData.isImpulsive && elliottData.currentWave.type === 'impulse' ? (
                  <TrendingUp className="w-6 h-6 text-green-400" />
                ) : (
                  <TrendingDown className="w-6 h-6 text-red-400" />
                )}
                <div>
                  <div className="text-white font-medium">
                    {elliottData.isImpulsive
                      ? `Wave ${elliottData.currentWave.wave} ${elliottData.currentWave.complete ? 'Complete' : 'In Progress'}`
                      : `Correction Wave ${elliottData.currentWave.wave}`
                    }
                  </div>
                  <div className="text-gray-400 text-sm">
                    {elliottData.isImpulsive
                      ? 'Expecting continued upward momentum'
                      : 'Expecting continued correction'
                    }
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <ArrowRight className="w-4 h-4 text-gray-400" />
                <span className="text-gray-400">
                  After this wave: {elliottData.isImpulsive ? 'ABC Correction' : 'New Impulse Wave'}
                </span>
              </div>
            </div>
          </div>

          {/* Wave Guide */}
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
            <h3 className="text-blue-400 font-medium mb-2 flex items-center gap-2">
              <Info className="w-4 h-4" />
              Elliott Wave Guide
            </h3>
            <div className="text-gray-400 text-sm space-y-1">
              <p>1. Markets move in 5-wave impulses in the direction of the trend</p>
              <p>2. Corrections occur in 3 waves (ABC) against the trend</p>
              <p>3. Wave 3 is typically the strongest and longest wave</p>
              <p>4. Use Fibonacci levels to identify potential reversal points</p>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>Impulse = Trending waves (1,3,5 or A,C)</span>
          <span>Corrective = Counter-trend waves (2,4 or B)</span>
          <span>Golden Ratio = 61.8%</span>
        </div>
      </div>
    </div>
  )
}

export default ElliottWave
