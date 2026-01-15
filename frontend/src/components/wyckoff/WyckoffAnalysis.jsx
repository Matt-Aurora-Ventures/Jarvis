import React, { useState, useMemo, useEffect } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  BarChart3,
  Target,
  Layers,
  ArrowUp,
  ArrowDown,
  Circle,
  AlertTriangle,
  ChevronRight,
  Clock
} from 'lucide-react'

export function WyckoffAnalysis() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [viewMode, setViewMode] = useState('phases') // phases, events, accumulation, distribution
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '1d', '1w']

  // Wyckoff phases and events
  const wyckoffPhases = {
    accumulation: ['PS', 'SC', 'AR', 'ST', 'Spring', 'Test', 'SOS', 'LPS', 'BU'],
    distribution: ['PSY', 'BC', 'AR', 'ST', 'SOW', 'LPSY', 'UT', 'UTAD', 'LPSY']
  }

  // Generate mock Wyckoff data
  const wyckoffData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    const isAccumulation = Math.random() > 0.5
    const currentPhase = isAccumulation ? 'accumulation' : 'distribution'

    // Generate price range
    const rangeHigh = currentPrice * (1.05 + Math.random() * 0.1)
    const rangeLow = currentPrice * (0.85 + Math.random() * 0.1)

    // Detected events
    const events = [
      {
        id: 1,
        type: isAccumulation ? 'PS' : 'PSY',
        name: isAccumulation ? 'Preliminary Support' : 'Preliminary Supply',
        price: currentPrice * (isAccumulation ? 0.92 : 1.08),
        time: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000),
        confirmed: true,
        description: isAccumulation
          ? 'First evidence of demand entering after prolonged downtrend'
          : 'First evidence of supply entering after prolonged uptrend'
      },
      {
        id: 2,
        type: isAccumulation ? 'SC' : 'BC',
        name: isAccumulation ? 'Selling Climax' : 'Buying Climax',
        price: rangeLow,
        time: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000),
        confirmed: true,
        description: isAccumulation
          ? 'Panic selling with high volume, marks the bottom'
          : 'Euphoric buying with high volume, marks the top'
      },
      {
        id: 3,
        type: 'AR',
        name: 'Automatic Rally/Reaction',
        price: currentPrice * (isAccumulation ? 1.02 : 0.98),
        time: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000),
        confirmed: true,
        description: 'Sharp counter-move as selling/buying exhausts'
      },
      {
        id: 4,
        type: 'ST',
        name: 'Secondary Test',
        price: currentPrice * (isAccumulation ? 0.93 : 1.07),
        time: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000),
        confirmed: true,
        description: 'Test of support/resistance with lower volume'
      },
      {
        id: 5,
        type: isAccumulation ? 'Spring' : 'UT',
        name: isAccumulation ? 'Spring' : 'Upthrust',
        price: currentPrice * (isAccumulation ? 0.88 : 1.12),
        time: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000),
        confirmed: Math.random() > 0.5,
        description: isAccumulation
          ? 'Final shakeout below support to trap sellers'
          : 'Final shakeout above resistance to trap buyers'
      }
    ]

    // Volume analysis
    const volumeProfile = {
      averageVolume: Math.floor(Math.random() * 50000000) + 10000000,
      currentVolume: Math.floor(Math.random() * 80000000) + 5000000,
      volumeTrend: Math.random() > 0.5 ? 'increasing' : 'decreasing',
      effortVsResult: Math.random() > 0.5 ? 'confirming' : 'diverging'
    }

    // Phase progression
    const phases = isAccumulation ? [
      { phase: 'A', name: 'Stopping Action', progress: 100, events: ['PS', 'SC', 'AR', 'ST'] },
      { phase: 'B', name: 'Building Cause', progress: Math.floor(Math.random() * 100), events: ['ST', 'UA'] },
      { phase: 'C', name: 'Test', progress: Math.floor(Math.random() * 80), events: ['Spring', 'Test'] },
      { phase: 'D', name: 'Trend Within Range', progress: Math.floor(Math.random() * 60), events: ['SOS', 'LPS'] },
      { phase: 'E', name: 'Trending', progress: Math.floor(Math.random() * 40), events: ['BU', 'SOS'] }
    ] : [
      { phase: 'A', name: 'Stopping Action', progress: 100, events: ['PSY', 'BC', 'AR', 'ST'] },
      { phase: 'B', name: 'Building Cause', progress: Math.floor(Math.random() * 100), events: ['ST', 'UT'] },
      { phase: 'C', name: 'Test', progress: Math.floor(Math.random() * 80), events: ['UTAD', 'SOW'] },
      { phase: 'D', name: 'Trend Within Range', progress: Math.floor(Math.random() * 60), events: ['LPSY', 'SOW'] },
      { phase: 'E', name: 'Trending', progress: Math.floor(Math.random() * 40), events: ['LPSY'] }
    ]

    // Current phase detection
    const currentPhaseIndex = phases.findIndex(p => p.progress < 100)
    const activePhase = phases[currentPhaseIndex] || phases[phases.length - 1]

    // Composite Man analysis
    const compositeMan = {
      action: isAccumulation ? 'Accumulating' : 'Distributing',
      strength: Math.floor(Math.random() * 100),
      confidence: Math.floor(Math.random() * 100)
    }

    return {
      currentPrice,
      currentPhase,
      isAccumulation,
      rangeHigh,
      rangeLow,
      events,
      volumeProfile,
      phases,
      activePhase,
      compositeMan
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

  const formatDate = (date) => {
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  const formatNumber = (num) => {
    if (num >= 1e9) return (num / 1e9).toFixed(2) + 'B'
    if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
    if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
    return num.toFixed(0)
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-amber-400" />
          <h2 className="text-xl font-bold text-white">Wyckoff Analysis</h2>
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

      {/* Main Status */}
      <div className={`rounded-lg p-6 mb-6 border ${
        wyckoffData.isAccumulation ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
      }`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">Current Phase</div>
            <div className={`text-2xl font-bold capitalize ${
              wyckoffData.isAccumulation ? 'text-green-400' : 'text-red-400'
            }`}>
              {wyckoffData.currentPhase}
            </div>
            <div className="text-gray-500 text-sm">
              Phase {wyckoffData.activePhase.phase}: {wyckoffData.activePhase.name}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Range High</div>
            <div className="text-xl font-bold text-red-400">${formatPrice(wyckoffData.rangeHigh)}</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Range Low</div>
            <div className="text-xl font-bold text-green-400">${formatPrice(wyckoffData.rangeLow)}</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Current Price</div>
            <div className="text-xl font-bold text-white">${formatPrice(wyckoffData.currentPrice)}</div>
          </div>
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'phases', label: 'Phases' },
          { id: 'events', label: 'Events' },
          { id: 'accumulation', label: 'Accumulation' },
          { id: 'distribution', label: 'Distribution' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* Phases View */}
      {viewMode === 'phases' && (
        <div className="space-y-4">
          {/* Phase Progress */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">Phase Progression</h3>
            <div className="space-y-4">
              {wyckoffData.phases.map((phase, i) => (
                <div key={phase.phase} className="relative">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                      phase.progress === 100 ? 'bg-green-500 text-white' :
                      phase.progress > 0 ? 'bg-amber-500 text-white' :
                      'bg-white/10 text-gray-500'
                    }`}>
                      {phase.phase}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-white font-medium">{phase.name}</span>
                        <span className={`text-sm ${phase.progress === 100 ? 'text-green-400' : 'text-gray-400'}`}>
                          {phase.progress}%
                        </span>
                      </div>
                      <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${phase.progress === 100 ? 'bg-green-500' : 'bg-amber-500'}`}
                          style={{ width: `${phase.progress}%` }}
                        />
                      </div>
                      <div className="flex gap-2 mt-2">
                        {phase.events.map(event => (
                          <span key={event} className="text-xs px-2 py-0.5 bg-white/5 text-gray-400 rounded">
                            {event}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  {i < wyckoffData.phases.length - 1 && (
                    <div className="absolute left-5 top-12 h-8 w-0.5 bg-white/10" />
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Composite Man */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              Composite Man Analysis
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-gray-400 text-sm">Action</div>
                <div className={`text-lg font-medium ${
                  wyckoffData.compositeMan.action === 'Accumulating' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {wyckoffData.compositeMan.action}
                </div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Strength</div>
                <div className="text-lg font-medium text-white">{wyckoffData.compositeMan.strength}%</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Confidence</div>
                <div className="text-lg font-medium text-white">{wyckoffData.compositeMan.confidence}%</div>
              </div>
            </div>
          </div>

          {/* Volume Analysis */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-cyan-400" />
              Volume Analysis
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-gray-400 text-sm">Average Volume</div>
                <div className="text-white font-medium">${formatNumber(wyckoffData.volumeProfile.averageVolume)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Current Volume</div>
                <div className="text-white font-medium">${formatNumber(wyckoffData.volumeProfile.currentVolume)}</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Volume Trend</div>
                <div className={`font-medium capitalize ${
                  wyckoffData.volumeProfile.volumeTrend === 'increasing' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {wyckoffData.volumeProfile.volumeTrend}
                </div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Effort vs Result</div>
                <div className={`font-medium capitalize ${
                  wyckoffData.volumeProfile.effortVsResult === 'confirming' ? 'text-green-400' : 'text-yellow-400'
                }`}>
                  {wyckoffData.volumeProfile.effortVsResult}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Events View */}
      {viewMode === 'events' && (
        <div className="space-y-3">
          {wyckoffData.events.map((event, i) => (
            <div key={event.id} className={`rounded-lg p-4 border ${
              event.confirmed ? 'bg-white/5 border-white/10' : 'bg-yellow-500/10 border-yellow-500/20'
            }`}>
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold ${
                    event.confirmed ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'
                  }`}>
                    {event.type}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{event.name}</span>
                      {event.confirmed ? (
                        <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">Confirmed</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">Pending</span>
                      )}
                    </div>
                    <div className="text-gray-400 text-sm mt-1">{event.description}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-white font-medium">${formatPrice(event.price)}</div>
                  <div className="text-gray-500 text-sm">{formatDate(event.time)}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Accumulation Schematic */}
      {viewMode === 'accumulation' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-4">Accumulation Schematic</h3>
          <div className="relative h-64 bg-gradient-to-b from-white/5 to-transparent rounded-lg p-4">
            {/* Price levels */}
            <div className="absolute left-2 top-4 text-xs text-gray-500">Resistance</div>
            <div className="absolute left-2 bottom-4 text-xs text-gray-500">Support</div>

            {/* Schematic events */}
            <div className="flex justify-between items-end h-full px-8">
              {['PS', 'SC', 'AR', 'ST', 'Spring', 'Test', 'SOS', 'LPS', 'BU'].map((event, i) => {
                const heights = {
                  'PS': 60, 'SC': 20, 'AR': 70, 'ST': 25, 'Spring': 10,
                  'Test': 30, 'SOS': 80, 'LPS': 50, 'BU': 90
                }
                return (
                  <div key={event} className="flex flex-col items-center gap-2">
                    <div
                      className="w-2 bg-green-500/50 rounded-t"
                      style={{ height: `${heights[event]}%` }}
                    />
                    <span className="text-xs text-gray-400 -rotate-45 origin-top-left">{event}</span>
                  </div>
                )
              })}
            </div>

            {/* Range lines */}
            <div className="absolute top-8 left-0 right-0 border-t border-dashed border-red-500/30" />
            <div className="absolute bottom-16 left-0 right-0 border-t border-dashed border-green-500/30" />
          </div>

          <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">PS</span> - Preliminary Support
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">SC</span> - Selling Climax
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">AR</span> - Automatic Rally
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">ST</span> - Secondary Test
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">Spring</span> - Shakeout
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">SOS</span> - Sign of Strength
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">LPS</span> - Last Point Support
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">BU</span> - Back Up
            </div>
          </div>
        </div>
      )}

      {/* Distribution Schematic */}
      {viewMode === 'distribution' && (
        <div className="bg-white/5 rounded-lg p-4 border border-white/10">
          <h3 className="text-white font-medium mb-4">Distribution Schematic</h3>
          <div className="relative h-64 bg-gradient-to-b from-transparent to-white/5 rounded-lg p-4">
            {/* Price levels */}
            <div className="absolute left-2 top-4 text-xs text-gray-500">Resistance</div>
            <div className="absolute left-2 bottom-4 text-xs text-gray-500">Support</div>

            {/* Schematic events */}
            <div className="flex justify-between items-start h-full px-8">
              {['PSY', 'BC', 'AR', 'ST', 'SOW', 'UT', 'UTAD', 'LPSY', 'SOW'].map((event, i) => {
                const heights = {
                  'PSY': 60, 'BC': 90, 'AR': 50, 'ST': 85, 'SOW': 40,
                  'UT': 95, 'UTAD': 100, 'LPSY': 70, 'SOW2': 30
                }
                return (
                  <div key={`${event}-${i}`} className="flex flex-col items-center gap-2">
                    <div
                      className="w-2 bg-red-500/50 rounded-b"
                      style={{ height: `${heights[event] || heights.SOW}%` }}
                    />
                    <span className="text-xs text-gray-400 -rotate-45 origin-top-left">{event}</span>
                  </div>
                )
              })}
            </div>

            {/* Range lines */}
            <div className="absolute top-8 left-0 right-0 border-t border-dashed border-red-500/30" />
            <div className="absolute bottom-16 left-0 right-0 border-t border-dashed border-green-500/30" />
          </div>

          <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">PSY</span> - Preliminary Supply
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">BC</span> - Buying Climax
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">AR</span> - Automatic Reaction
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">ST</span> - Secondary Test
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">SOW</span> - Sign of Weakness
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">UT</span> - Upthrust
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">UTAD</span> - Upthrust After Dist.
            </div>
            <div className="p-2 bg-white/5 rounded">
              <span className="text-amber-400">LPSY</span> - Last Point Supply
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>Wyckoff Method analyzes supply/demand through price and volume</span>
          <span>Accumulation = Institutional buying</span>
          <span>Distribution = Institutional selling</span>
        </div>
      </div>
    </div>
  )
}

export default WyckoffAnalysis
