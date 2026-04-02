import React, { useState, useMemo } from 'react'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  Layers,
  ChevronDown,
  Calendar,
  Zap,
  Eye,
  ArrowUp,
  ArrowDown
} from 'lucide-react'

export function VolumeProfile() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('session') // session, visible, fixed
  const [timeRange, setTimeRange] = useState('1D')
  const [showDelta, setShowDelta] = useState(true)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate volume profile data
  const volumeProfile = useMemo(() => {
    const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000
    const priceStep = basePrice * 0.002
    const numLevels = 40

    const levels = []
    let maxVolume = 0

    for (let i = 0; i < numLevels; i++) {
      const price = basePrice + (i - numLevels / 2) * priceStep
      const totalVolume = Math.floor(Math.random() * 15000000) + 500000
      const buyVolume = totalVolume * (0.4 + Math.random() * 0.2)
      const sellVolume = totalVolume - buyVolume
      const delta = buyVolume - sellVolume

      if (totalVolume > maxVolume) maxVolume = totalVolume

      levels.push({
        price,
        totalVolume,
        buyVolume,
        sellVolume,
        delta,
        isPOC: false,
        isVAH: false,
        isVAL: false,
        isNaked: Math.random() < 0.1,
        isHVN: false,
        isLVN: false
      })
    }

    // Find POC
    const pocIdx = levels.reduce((maxIdx, level, idx, arr) =>
      level.totalVolume > arr[maxIdx].totalVolume ? idx : maxIdx, 0)
    levels[pocIdx].isPOC = true

    // Calculate value area (70%)
    const totalVolSum = levels.reduce((sum, l) => sum + l.totalVolume, 0)
    const targetVolume = totalVolSum * 0.7
    let currentVolume = levels[pocIdx].totalVolume
    let upper = pocIdx
    let lower = pocIdx

    while (currentVolume < targetVolume && (upper < levels.length - 1 || lower > 0)) {
      const upperVol = upper < levels.length - 1 ? levels[upper + 1].totalVolume : 0
      const lowerVol = lower > 0 ? levels[lower - 1].totalVolume : 0

      if (upperVol >= lowerVol && upper < levels.length - 1) {
        upper++
        currentVolume += upperVol
      } else if (lower > 0) {
        lower--
        currentVolume += lowerVol
      }
    }

    levels[upper].isVAH = true
    levels[lower].isVAL = true

    // Mark HVN/LVN
    const avgVolume = totalVolSum / numLevels
    levels.forEach(level => {
      if (level.totalVolume > avgVolume * 1.5) level.isHVN = true
      if (level.totalVolume < avgVolume * 0.5) level.isLVN = true
    })

    const poc = levels[pocIdx]
    const vah = levels[upper]
    const val = levels[lower]
    const currentPrice = basePrice + (Math.random() - 0.5) * basePrice * 0.01

    return {
      levels: levels.reverse(),
      maxVolume,
      poc: poc.price,
      vah: vah.price,
      val: val.price,
      totalVolume: totalVolSum,
      currentPrice,
      priceLocation: currentPrice > poc.price ? 'Above POC' : 'Below POC',
      inValueArea: currentPrice <= vah.price && currentPrice >= val.price,
      totalDelta: levels.reduce((sum, l) => sum + l.delta, 0),
      hvnLevels: levels.filter(l => l.isHVN).map(l => l.price),
      lvnLevels: levels.filter(l => l.isLVN).map(l => l.price),
      nakedPOCs: levels.filter(l => l.isNaked).map(l => l.price)
    }
  }, [selectedToken])

  // Session profiles
  const sessionProfiles = useMemo(() => {
    return [
      { name: 'Asian', start: '00:00', end: '08:00', poc: 149.85, vah: 150.20, val: 149.50, volume: 12500000 },
      { name: 'London', start: '08:00', end: '14:00', poc: 150.15, vah: 150.45, val: 149.85, volume: 28000000 },
      { name: 'New York', start: '14:00', end: '21:00', poc: 150.35, vah: 150.65, val: 150.05, volume: 35000000 },
      { name: 'After Hours', start: '21:00', end: '00:00', poc: 150.25, vah: 150.40, val: 150.10, volume: 8000000 }
    ]
  }, [])

  const formatVolume = (vol) => {
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(1)}M`
    if (vol >= 1000) return `${(vol / 1000).toFixed(0)}K`
    return vol.toString()
  }

  const formatPrice = (price) => {
    return price.toFixed(2)
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold text-white">Volume Profile</h2>
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

            {/* Time Range */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['1D', '1W', '1M', 'Custom'].map((range) => (
                <button
                  key={range}
                  onClick={() => setTimeRange(range)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    timeRange === range
                      ? 'bg-indigo-500/30 text-indigo-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {range}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex items-center justify-between">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {[
              { id: 'session', label: 'Session VP', icon: Calendar },
              { id: 'visible', label: 'Visible Range', icon: Eye },
              { id: 'fixed', label: 'Fixed Range', icon: Target }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setViewMode(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                  viewMode === id
                    ? 'bg-indigo-500/30 text-indigo-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          <button
            onClick={() => setShowDelta(!showDelta)}
            className={`px-3 py-1.5 text-xs rounded-lg transition-colors ${
              showDelta ? 'bg-purple-500/20 text-purple-400' : 'bg-white/5 text-gray-400'
            }`}
          >
            Show Delta
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">POC</div>
            <div className="text-sm font-medium text-yellow-400">
              ${formatPrice(volumeProfile.poc)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">VAH</div>
            <div className="text-sm font-medium text-green-400">
              ${formatPrice(volumeProfile.vah)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">VAL</div>
            <div className="text-sm font-medium text-red-400">
              ${formatPrice(volumeProfile.val)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Total Volume</div>
            <div className="text-sm font-medium text-white">
              {formatVolume(volumeProfile.totalVolume)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Net Delta</div>
            <div className={`text-sm font-medium ${volumeProfile.totalDelta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {volumeProfile.totalDelta >= 0 ? '+' : ''}{formatVolume(volumeProfile.totalDelta)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Price Location</div>
            <div className={`text-sm font-medium ${
              volumeProfile.inValueArea ? 'text-blue-400' : 'text-orange-400'
            }`}>
              {volumeProfile.inValueArea ? 'In Value' : volumeProfile.priceLocation}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'session' && (
          <div className="space-y-4">
            {/* Session Volume Profiles */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {sessionProfiles.map((session) => (
                <div key={session.name} className="bg-white/5 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-medium text-white">{session.name}</h3>
                    <span className="text-xs text-gray-500">
                      {session.start}-{session.end}
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-400">POC</span>
                      <span className="text-sm text-yellow-400">${session.poc}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-400">VAH</span>
                      <span className="text-sm text-green-400">${session.vah}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-400">VAL</span>
                      <span className="text-sm text-red-400">${session.val}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-xs text-gray-400">Volume</span>
                      <span className="text-sm text-white">{formatVolume(session.volume)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Session Comparison */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Session Volume Comparison</h3>
              <div className="space-y-2">
                {sessionProfiles.map((session) => {
                  const maxVol = Math.max(...sessionProfiles.map(s => s.volume))
                  const pct = (session.volume / maxVol) * 100

                  return (
                    <div key={session.name} className="flex items-center gap-3">
                      <span className="text-xs text-gray-400 w-20">{session.name}</span>
                      <div className="flex-1 h-4 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-indigo-500/60 rounded-full"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-16 text-right">
                        {formatVolume(session.volume)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {viewMode === 'visible' && (
          <div className="space-y-4">
            {/* Volume Profile Chart */}
            <div className="bg-white/5 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-white">Volume at Price</h3>
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                    Buy
                  </span>
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                    Sell
                  </span>
                </div>
              </div>

              <div className="space-y-0.5 max-h-96 overflow-y-auto">
                {volumeProfile.levels.map((level, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    {/* Price */}
                    <div className={`w-16 text-right text-xs font-mono ${
                      level.isPOC ? 'text-yellow-400 font-bold' :
                      level.isVAH ? 'text-green-400' :
                      level.isVAL ? 'text-red-400' :
                      'text-gray-500'
                    }`}>
                      ${formatPrice(level.price)}
                    </div>

                    {/* Volume Bars */}
                    <div className="flex-1 h-4 flex">
                      {showDelta ? (
                        <>
                          <div
                            className="h-full bg-green-500/60"
                            style={{ width: `${(level.buyVolume / volumeProfile.maxVolume) * 100}%` }}
                          />
                          <div
                            className="h-full bg-red-500/60"
                            style={{ width: `${(level.sellVolume / volumeProfile.maxVolume) * 100}%` }}
                          />
                        </>
                      ) : (
                        <div
                          className={`h-full rounded ${
                            level.isPOC ? 'bg-yellow-500/60' :
                            level.isHVN ? 'bg-indigo-500/60' :
                            level.isLVN ? 'bg-gray-500/40' :
                            'bg-blue-500/40'
                          }`}
                          style={{ width: `${(level.totalVolume / volumeProfile.maxVolume) * 100}%` }}
                        />
                      )}
                    </div>

                    {/* Labels */}
                    <div className="w-24 flex items-center gap-1">
                      {level.isPOC && (
                        <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-1 rounded">POC</span>
                      )}
                      {level.isVAH && (
                        <span className="text-[10px] bg-green-500/20 text-green-400 px-1 rounded">VAH</span>
                      )}
                      {level.isVAL && (
                        <span className="text-[10px] bg-red-500/20 text-red-400 px-1 rounded">VAL</span>
                      )}
                      {level.isNaked && (
                        <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1 rounded">N</span>
                      )}
                    </div>

                    {/* Volume */}
                    <div className="w-14 text-right text-xs text-gray-400">
                      {formatVolume(level.totalVolume)}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Key Levels */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">High Volume Nodes</h3>
                <div className="space-y-2">
                  {volumeProfile.hvnLevels.slice(0, 5).map((price, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">HVN {idx + 1}</span>
                      <span className="text-sm text-indigo-400">${formatPrice(price)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Strong support/resistance where heavy volume traded
                </p>
              </div>

              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">Low Volume Nodes</h3>
                <div className="space-y-2">
                  {volumeProfile.lvnLevels.slice(0, 5).map((price, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">LVN {idx + 1}</span>
                      <span className="text-sm text-gray-400">${formatPrice(price)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Price tends to move quickly through these levels
                </p>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'fixed' && (
          <div className="space-y-4">
            {/* Naked POC Levels */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Naked POC Levels (Unfilled)</h3>
              <p className="text-xs text-gray-400 mb-3">
                POCs from previous sessions that price hasn&apos;t revisited - strong magnets
              </p>
              <div className="grid grid-cols-3 gap-3">
                {volumeProfile.nakedPOCs.slice(0, 6).map((price, idx) => (
                  <div
                    key={idx}
                    className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3 text-center"
                  >
                    <div className="text-sm font-medium text-purple-400">
                      ${formatPrice(price)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {Math.floor(Math.random() * 5) + 1} days ago
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Volume Delta Profile */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Volume Delta by Price</h3>
              <div className="space-y-1">
                {volumeProfile.levels.slice(0, 15).map((level, idx) => {
                  const maxDelta = Math.max(...volumeProfile.levels.map(l => Math.abs(l.delta)))
                  const deltaWidth = (Math.abs(level.delta) / maxDelta) * 100

                  return (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 w-16 text-right">
                        ${formatPrice(level.price)}
                      </span>
                      <div className="flex-1 h-3 flex items-center">
                        {level.delta >= 0 ? (
                          <>
                            <div className="w-1/2"></div>
                            <div
                              className="h-full bg-green-500/60 rounded-r"
                              style={{ width: `${deltaWidth / 2}%` }}
                            />
                          </>
                        ) : (
                          <>
                            <div className="w-1/2 flex justify-end">
                              <div
                                className="h-full bg-red-500/60 rounded-l"
                                style={{ width: `${deltaWidth}%` }}
                              />
                            </div>
                            <div className="w-1/2"></div>
                          </>
                        )}
                      </div>
                      <span className={`text-xs w-14 text-right ${level.delta >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatVolume(Math.abs(level.delta))}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Trading Strategy */}
            <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 rounded-lg p-4 border border-indigo-500/20">
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-indigo-400" />
                <h3 className="text-sm font-medium text-white">Volume Profile Strategy</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">Value Area Play</div>
                  <div className={`text-sm ${volumeProfile.inValueArea ? 'text-green-400' : 'text-yellow-400'}`}>
                    {volumeProfile.inValueArea
                      ? 'Mean reversion: Fade moves to VA extremes'
                      : 'Trend: Look for continuation outside value'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">POC Target</div>
                  <div className="text-sm text-blue-400">
                    Price tends to return to POC at ${formatPrice(volumeProfile.poc)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default VolumeProfile
