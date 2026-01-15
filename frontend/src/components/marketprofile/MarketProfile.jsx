import React, { useState, useMemo } from 'react'
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Target,
  Activity,
  Layers,
  Clock,
  ChevronDown,
  AlertTriangle,
  Zap,
  Eye
} from 'lucide-react'

export function MarketProfile() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('tpo') // tpo, volume, composite
  const [timeframe, setTimeframe] = useState('daily')

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate TPO (Time Price Opportunity) data
  const tpoData = useMemo(() => {
    const priceStart = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000
    const priceStep = priceStart * 0.002
    const levels = []

    for (let i = 0; i < 30; i++) {
      const price = priceStart + (i - 15) * priceStep
      const tpoCount = Math.floor(Math.random() * 12) + 1
      const volumeAtPrice = Math.random() * 10000000
      const buyVolume = volumeAtPrice * (0.4 + Math.random() * 0.2)
      const sellVolume = volumeAtPrice - buyVolume

      levels.push({
        price,
        tpoCount,
        tpoLetters: generateTPOLetters(tpoCount),
        volumeAtPrice,
        buyVolume,
        sellVolume,
        isPOC: false,
        isVAH: false,
        isVAL: false,
        isHVN: volumeAtPrice > 7000000,
        isLVN: volumeAtPrice < 2000000
      })
    }

    // Find POC (Point of Control) - highest volume
    const maxVolIdx = levels.reduce((maxIdx, level, idx, arr) =>
      level.volumeAtPrice > arr[maxIdx].volumeAtPrice ? idx : maxIdx, 0)
    levels[maxVolIdx].isPOC = true

    // Calculate Value Area (70% of volume)
    const totalVolume = levels.reduce((sum, l) => sum + l.volumeAtPrice, 0)
    const targetVolume = totalVolume * 0.7
    let currentVolume = levels[maxVolIdx].volumeAtPrice
    let upper = maxVolIdx
    let lower = maxVolIdx

    while (currentVolume < targetVolume && (upper < levels.length - 1 || lower > 0)) {
      const upperVol = upper < levels.length - 1 ? levels[upper + 1].volumeAtPrice : 0
      const lowerVol = lower > 0 ? levels[lower - 1].volumeAtPrice : 0

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

    return levels.reverse()
  }, [selectedToken])

  function generateTPOLetters(count) {
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    return letters.slice(0, count)
  }

  // Profile statistics
  const profileStats = useMemo(() => {
    const poc = tpoData.find(l => l.isPOC)
    const vah = tpoData.find(l => l.isVAH)
    const val = tpoData.find(l => l.isVAL)
    const currentPrice = tpoData[Math.floor(tpoData.length / 2)].price

    const hvnLevels = tpoData.filter(l => l.isHVN).map(l => l.price)
    const lvnLevels = tpoData.filter(l => l.isLVN).map(l => l.price)

    return {
      poc: poc?.price || 0,
      vah: vah?.price || 0,
      val: val?.price || 0,
      valueAreaWidth: ((vah?.price || 0) - (val?.price || 0)) / (poc?.price || 1) * 100,
      currentPrice,
      priceLocation: currentPrice > (poc?.price || 0) ? 'Above POC' : 'Below POC',
      inValueArea: currentPrice <= (vah?.price || 0) && currentPrice >= (val?.price || 0),
      hvnLevels,
      lvnLevels,
      profileShape: determineProfileShape(tpoData),
      trendBias: Math.random() > 0.5 ? 'bullish' : 'bearish'
    }
  }, [tpoData])

  function determineProfileShape(data) {
    const midpoint = Math.floor(data.length / 2)
    const upperVolume = data.slice(0, midpoint).reduce((sum, l) => sum + l.volumeAtPrice, 0)
    const lowerVolume = data.slice(midpoint).reduce((sum, l) => sum + l.volumeAtPrice, 0)

    if (upperVolume > lowerVolume * 1.3) return 'P-Shape (Bullish)'
    if (lowerVolume > upperVolume * 1.3) return 'b-Shape (Bearish)'
    return 'D-Shape (Balanced)'
  }

  // Multi-day composite
  const compositeProfiles = useMemo(() => {
    return Array.from({ length: 5 }, (_, i) => {
      const date = new Date()
      date.setDate(date.getDate() - i)

      const priceStart = selectedToken === 'SOL' ? 148 + Math.random() * 4 : 3180 + Math.random() * 40

      return {
        date: date.toLocaleDateString(),
        poc: priceStart + (Math.random() - 0.5) * 2,
        vah: priceStart + Math.random() * 3,
        val: priceStart - Math.random() * 3,
        totalVolume: Math.floor(Math.random() * 50000000) + 10000000,
        shape: ['P-Shape', 'b-Shape', 'D-Shape'][Math.floor(Math.random() * 3)],
        ib: {
          high: priceStart + Math.random() * 2,
          low: priceStart - Math.random() * 2,
          range: Math.random() * 4
        }
      }
    })
  }, [selectedToken])

  const maxTPO = Math.max(...tpoData.map(l => l.tpoCount))
  const maxVolume = Math.max(...tpoData.map(l => l.volumeAtPrice))

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-purple-400" />
            <h2 className="text-lg font-semibold text-white">Market Profile</h2>
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

            {/* Timeframe */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['daily', 'weekly', 'monthly'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    timeframe === tf
                      ? 'bg-purple-500/30 text-purple-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {tf.charAt(0).toUpperCase() + tf.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'tpo', label: 'TPO Profile', icon: Layers },
            { id: 'volume', label: 'Volume Profile', icon: BarChart3 },
            { id: 'composite', label: 'Composite', icon: Activity }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-purple-500/30 text-purple-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Profile Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">POC</div>
            <div className="text-sm font-medium text-yellow-400">
              ${profileStats.poc.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">VAH</div>
            <div className="text-sm font-medium text-green-400">
              ${profileStats.vah.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">VAL</div>
            <div className="text-sm font-medium text-red-400">
              ${profileStats.val.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">VA Width</div>
            <div className="text-sm font-medium text-white">
              {profileStats.valueAreaWidth.toFixed(2)}%
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Shape</div>
            <div className={`text-sm font-medium ${
              profileStats.profileShape.includes('Bullish') ? 'text-green-400' :
              profileStats.profileShape.includes('Bearish') ? 'text-red-400' : 'text-gray-400'
            }`}>
              {profileStats.profileShape}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Location</div>
            <div className={`text-sm font-medium ${
              profileStats.inValueArea ? 'text-blue-400' : 'text-orange-400'
            }`}>
              {profileStats.inValueArea ? 'In Value Area' : profileStats.priceLocation}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'tpo' && (
          <div className="space-y-4">
            {/* TPO Chart */}
            <div className="bg-white/5 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-white">TPO Profile</h3>
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                    POC
                  </span>
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                    VAH
                  </span>
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                    VAL
                  </span>
                </div>
              </div>

              <div className="space-y-0.5">
                {tpoData.map((level, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    {/* Price Label */}
                    <div className={`w-20 text-right text-xs font-mono ${
                      level.isPOC ? 'text-yellow-400 font-bold' :
                      level.isVAH ? 'text-green-400' :
                      level.isVAL ? 'text-red-400' :
                      'text-gray-500'
                    }`}>
                      ${level.price.toFixed(2)}
                    </div>

                    {/* TPO Letters */}
                    <div className={`flex-1 h-5 flex items-center ${
                      level.isPOC ? 'bg-yellow-500/10 border border-yellow-500/30 rounded' :
                      level.isVAH || level.isVAL ? 'bg-white/5' : ''
                    }`}>
                      <div className="flex">
                        {level.tpoLetters.split('').map((letter, i) => (
                          <span
                            key={i}
                            className={`w-3 text-center text-xs font-mono ${
                              level.isPOC ? 'text-yellow-400' :
                              level.isHVN ? 'text-purple-400' :
                              level.isLVN ? 'text-gray-600' :
                              'text-blue-400'
                            }`}
                          >
                            {letter}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Indicators */}
                    <div className="w-16 flex items-center gap-1">
                      {level.isPOC && (
                        <span className="text-[10px] bg-yellow-500/20 text-yellow-400 px-1 rounded">POC</span>
                      )}
                      {level.isVAH && (
                        <span className="text-[10px] bg-green-500/20 text-green-400 px-1 rounded">VAH</span>
                      )}
                      {level.isVAL && (
                        <span className="text-[10px] bg-red-500/20 text-red-400 px-1 rounded">VAL</span>
                      )}
                      {level.isHVN && !level.isPOC && (
                        <span className="text-[10px] bg-purple-500/20 text-purple-400 px-1 rounded">HVN</span>
                      )}
                      {level.isLVN && (
                        <span className="text-[10px] bg-gray-500/20 text-gray-400 px-1 rounded">LVN</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Profile Analysis */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">High Volume Nodes</h3>
                <div className="space-y-2">
                  {profileStats.hvnLevels.slice(0, 3).map((price, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">HVN {idx + 1}</span>
                      <span className="text-sm text-purple-400">${price.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Support/resistance where significant trading occurred
                </p>
              </div>

              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">Low Volume Nodes</h3>
                <div className="space-y-2">
                  {profileStats.lvnLevels.slice(0, 3).map((price, idx) => (
                    <div key={idx} className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">LVN {idx + 1}</span>
                      <span className="text-sm text-gray-400">${price.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  Price likely to move quickly through these levels
                </p>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'volume' && (
          <div className="space-y-4">
            {/* Volume Profile */}
            <div className="bg-white/5 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-white">Volume at Price</h3>
                <div className="flex items-center gap-4 text-xs">
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                    Buy Volume
                  </span>
                  <span className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                    Sell Volume
                  </span>
                </div>
              </div>

              <div className="space-y-0.5">
                {tpoData.map((level, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    {/* Price */}
                    <div className={`w-20 text-right text-xs font-mono ${
                      level.isPOC ? 'text-yellow-400 font-bold' : 'text-gray-500'
                    }`}>
                      ${level.price.toFixed(2)}
                    </div>

                    {/* Volume Bar */}
                    <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden flex">
                      <div
                        className="h-full bg-green-500/60"
                        style={{ width: `${(level.buyVolume / maxVolume) * 100}%` }}
                      />
                      <div
                        className="h-full bg-red-500/60"
                        style={{ width: `${(level.sellVolume / maxVolume) * 100}%` }}
                      />
                    </div>

                    {/* Volume Value */}
                    <div className="w-20 text-right text-xs text-gray-400">
                      {(level.volumeAtPrice / 1000000).toFixed(1)}M
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Volume Distribution */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-green-400">
                  {((tpoData.reduce((sum, l) => sum + l.buyVolume, 0) /
                    tpoData.reduce((sum, l) => sum + l.volumeAtPrice, 0)) * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-gray-400 mt-1">Buy Volume</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-red-400">
                  {((tpoData.reduce((sum, l) => sum + l.sellVolume, 0) /
                    tpoData.reduce((sum, l) => sum + l.volumeAtPrice, 0)) * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-gray-400 mt-1">Sell Volume</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-white">
                  ${(tpoData.reduce((sum, l) => sum + l.volumeAtPrice, 0) / 1000000).toFixed(1)}M
                </div>
                <div className="text-xs text-gray-400 mt-1">Total Volume</div>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'composite' && (
          <div className="space-y-4">
            {/* Multi-Day Composite */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Multi-Day Profile Analysis</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-xs text-gray-500">
                      <th className="text-left py-2">Date</th>
                      <th className="text-right py-2">POC</th>
                      <th className="text-right py-2">VAH</th>
                      <th className="text-right py-2">VAL</th>
                      <th className="text-right py-2">Volume</th>
                      <th className="text-right py-2">Shape</th>
                      <th className="text-right py-2">IB Range</th>
                    </tr>
                  </thead>
                  <tbody>
                    {compositeProfiles.map((profile, idx) => (
                      <tr key={idx} className="border-t border-white/5">
                        <td className="py-2 text-sm text-white">{profile.date}</td>
                        <td className="py-2 text-sm text-yellow-400 text-right">
                          ${profile.poc.toFixed(2)}
                        </td>
                        <td className="py-2 text-sm text-green-400 text-right">
                          ${profile.vah.toFixed(2)}
                        </td>
                        <td className="py-2 text-sm text-red-400 text-right">
                          ${profile.val.toFixed(2)}
                        </td>
                        <td className="py-2 text-sm text-gray-400 text-right">
                          ${(profile.totalVolume / 1000000).toFixed(1)}M
                        </td>
                        <td className={`py-2 text-sm text-right ${
                          profile.shape === 'P-Shape' ? 'text-green-400' :
                          profile.shape === 'b-Shape' ? 'text-red-400' : 'text-gray-400'
                        }`}>
                          {profile.shape}
                        </td>
                        <td className="py-2 text-sm text-gray-400 text-right">
                          ${profile.ib.range.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Developing POC */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">POC Migration</h3>
                <div className="space-y-2">
                  {compositeProfiles.slice(0, 4).map((profile, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <span className="text-xs text-gray-400 w-20">{profile.date}</span>
                      <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-yellow-500"
                          style={{
                            width: `${((profile.poc - 145) / 10) * 100}%`,
                            marginLeft: `${Math.min(Math.max(((profile.poc - 145) / 10) * 100 - 10, 0), 80)}%`
                          }}
                        />
                      </div>
                      <span className="text-xs text-yellow-400">${profile.poc.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-gray-500 mt-3">
                  POC trending {compositeProfiles[0].poc > compositeProfiles[3].poc ? 'higher' : 'lower'} over sessions
                </p>
              </div>

              <div className="bg-white/5 rounded-lg p-4">
                <h3 className="text-sm font-medium text-white mb-3">Initial Balance</h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-400">Today IB High</span>
                    <span className="text-sm text-green-400">
                      ${compositeProfiles[0].ib.high.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-400">Today IB Low</span>
                    <span className="text-sm text-red-400">
                      ${compositeProfiles[0].ib.low.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-400">IB Range</span>
                    <span className="text-sm text-white">
                      ${compositeProfiles[0].ib.range.toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-xs text-gray-400">IB Extension Target</span>
                    <span className="text-sm text-purple-400">
                      ${(compositeProfiles[0].ib.high + compositeProfiles[0].ib.range).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* Trading Signals */}
            <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-lg p-4 border border-purple-500/20">
              <div className="flex items-center gap-2 mb-3">
                <Zap className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-medium text-white">Profile-Based Signals</h3>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-xs text-gray-400 mb-1">Value Area Play</div>
                  <div className={`text-sm ${profileStats.inValueArea ? 'text-green-400' : 'text-yellow-400'}`}>
                    {profileStats.inValueArea
                      ? 'Price in value - fade extremes'
                      : 'Price outside value - trend continuation likely'}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-gray-400 mb-1">POC Magnet</div>
                  <div className="text-sm text-blue-400">
                    Price tends to return to POC at ${profileStats.poc.toFixed(2)}
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

export default MarketProfile
