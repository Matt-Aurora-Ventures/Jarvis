import React, { useState, useMemo } from 'react'
import {
  Map,
  TrendingUp,
  TrendingDown,
  Zap,
  Target,
  ChevronDown,
  Activity,
  AlertTriangle,
  Eye,
  Layers,
  DollarSign
} from 'lucide-react'

export function LiquidityMap() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('map') // map, levels, analysis
  const [leverage, setLeverage] = useState('all') // all, 5x, 10x, 25x, 50x, 100x

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']

  // Generate liquidity data
  const liquidityData = useMemo(() => {
    const basePrice = selectedToken === 'SOL' ? 150 : selectedToken === 'ETH' ? 3200 : 95000
    const priceRange = basePrice * 0.1 // 10% range

    const zones = []
    const numZones = 30

    for (let i = 0; i < numZones; i++) {
      const price = basePrice - priceRange / 2 + (i / numZones) * priceRange

      // Simulate liquidation clusters at different leverage levels
      const liq5x = Math.floor(Math.random() * 1000000)
      const liq10x = Math.floor(Math.random() * 2000000)
      const liq25x = Math.floor(Math.random() * 5000000)
      const liq50x = Math.floor(Math.random() * 8000000)
      const liq100x = Math.floor(Math.random() * 3000000)

      const totalLiquidity = liq5x + liq10x + liq25x + liq50x + liq100x
      const isLongLiq = price < basePrice
      const isHotZone = totalLiquidity > 10000000

      zones.push({
        price,
        liq5x,
        liq10x,
        liq25x,
        liq50x,
        liq100x,
        totalLiquidity,
        isLongLiq,
        isHotZone,
        percentFromCurrent: ((price - basePrice) / basePrice) * 100
      })
    }

    // Calculate statistics
    const currentPrice = basePrice
    const nearestLongLiq = zones.filter(z => z.isLongLiq && z.isHotZone).sort((a, b) => b.price - a.price)[0]
    const nearestShortLiq = zones.filter(z => !z.isLongLiq && z.isHotZone).sort((a, b) => a.price - b.price)[0]

    const totalLongLiq = zones.filter(z => z.isLongLiq).reduce((sum, z) => sum + z.totalLiquidity, 0)
    const totalShortLiq = zones.filter(z => !z.isLongLiq).reduce((sum, z) => sum + z.totalLiquidity, 0)

    return {
      zones,
      currentPrice,
      nearestLongLiq: nearestLongLiq?.price,
      nearestShortLiq: nearestShortLiq?.price,
      totalLongLiq,
      totalShortLiq,
      imbalance: ((totalShortLiq - totalLongLiq) / (totalShortLiq + totalLongLiq)) * 100,
      hotZones: zones.filter(z => z.isHotZone)
    }
  }, [selectedToken])

  // Filter by leverage
  const filteredZones = useMemo(() => {
    return liquidityData.zones.map(zone => {
      let filteredLiq = zone.totalLiquidity

      if (leverage === '5x') filteredLiq = zone.liq5x
      else if (leverage === '10x') filteredLiq = zone.liq10x
      else if (leverage === '25x') filteredLiq = zone.liq25x
      else if (leverage === '50x') filteredLiq = zone.liq50x
      else if (leverage === '100x') filteredLiq = zone.liq100x

      return {
        ...zone,
        displayLiquidity: filteredLiq
      }
    })
  }, [liquidityData, leverage])

  const maxLiquidity = Math.max(...filteredZones.map(z => z.displayLiquidity))

  const formatValue = (val) => {
    if (val >= 1000000) return `$${(val / 1000000).toFixed(1)}M`
    if (val >= 1000) return `$${(val / 1000).toFixed(0)}K`
    return `$${val}`
  }

  const formatPrice = (price) => {
    if (selectedToken === 'BTC') return price.toFixed(0)
    return price.toFixed(2)
  }

  const getHeatIntensity = (liq, max) => {
    const pct = (liq / max) * 100
    if (pct > 80) return 'bg-red-500'
    if (pct > 60) return 'bg-orange-500'
    if (pct > 40) return 'bg-yellow-500'
    if (pct > 20) return 'bg-yellow-500/50'
    return 'bg-yellow-500/20'
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Map className="w-5 h-5 text-rose-400" />
            <h2 className="text-lg font-semibold text-white">Liquidity Map</h2>
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

            {/* Leverage Filter */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['all', '5x', '10x', '25x', '50x', '100x'].map((lev) => (
                <button
                  key={lev}
                  onClick={() => setLeverage(lev)}
                  className={`px-2 py-1 text-xs rounded-md transition-colors ${
                    leverage === lev
                      ? 'bg-rose-500/30 text-rose-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {lev}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex bg-white/5 rounded-lg p-0.5 w-fit">
          {[
            { id: 'map', label: 'Liquidity Map', icon: Map },
            { id: 'levels', label: 'Key Levels', icon: Target },
            { id: 'analysis', label: 'Analysis', icon: Activity }
          ].map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setViewMode(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                viewMode === id
                  ? 'bg-rose-500/30 text-rose-400'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Current Price</div>
            <div className="text-sm font-medium text-white">
              ${formatPrice(liquidityData.currentPrice)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Long Liquidations</div>
            <div className="text-sm font-medium text-red-400">
              {formatValue(liquidityData.totalLongLiq)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Short Liquidations</div>
            <div className="text-sm font-medium text-green-400">
              {formatValue(liquidityData.totalShortLiq)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Nearest Long Liq</div>
            <div className="text-sm font-medium text-red-400">
              ${formatPrice(liquidityData.nearestLongLiq || 0)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Nearest Short Liq</div>
            <div className="text-sm font-medium text-green-400">
              ${formatPrice(liquidityData.nearestShortLiq || 0)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Hot Zones</div>
            <div className="text-sm font-medium text-yellow-400">
              {liquidityData.hotZones.length}
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'map' && (
          <div className="space-y-4">
            {/* Liquidity Heatmap */}
            <div className="bg-white/5 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-white">Liquidation Heatmap</h3>
                <div className="flex items-center gap-2 text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <TrendingDown className="w-3 h-3 text-red-400" />
                    Long Liquidations
                  </span>
                  <span className="flex items-center gap-1">
                    <TrendingUp className="w-3 h-3 text-green-400" />
                    Short Liquidations
                  </span>
                </div>
              </div>

              <div className="space-y-1">
                {filteredZones.map((zone, idx) => {
                  const isCurrent = Math.abs(zone.percentFromCurrent) < 0.5
                  const barWidth = (zone.displayLiquidity / maxLiquidity) * 100

                  return (
                    <div
                      key={idx}
                      className={`flex items-center gap-2 ${isCurrent ? 'bg-white/10 rounded py-1' : ''}`}
                    >
                      {/* Price */}
                      <div className={`w-20 text-right text-xs font-mono ${
                        isCurrent ? 'text-yellow-400 font-bold' :
                        zone.isLongLiq ? 'text-red-400/70' : 'text-green-400/70'
                      }`}>
                        ${formatPrice(zone.price)}
                      </div>

                      {/* Percentage */}
                      <div className={`w-14 text-right text-[10px] ${
                        zone.percentFromCurrent >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {zone.percentFromCurrent >= 0 ? '+' : ''}{zone.percentFromCurrent.toFixed(1)}%
                      </div>

                      {/* Liquidity Bar */}
                      <div className="flex-1 h-4 bg-white/5 rounded overflow-hidden">
                        <div
                          className={`h-full rounded ${
                            zone.isLongLiq
                              ? getHeatIntensity(zone.displayLiquidity, maxLiquidity)
                              : getHeatIntensity(zone.displayLiquidity, maxLiquidity)
                          }`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>

                      {/* Value */}
                      <div className="w-16 text-right text-xs text-gray-400">
                        {formatValue(zone.displayLiquidity)}
                      </div>

                      {/* Hot Zone Indicator */}
                      {zone.isHotZone && (
                        <AlertTriangle className="w-3 h-3 text-yellow-400" />
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Legend */}
            <div className="flex items-center justify-center gap-4 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-12 h-3 rounded" style={{
                  background: 'linear-gradient(to right, rgba(234,179,8,0.2), rgba(234,179,8,0.5), rgba(249,115,22,1), rgba(239,68,68,1))'
                }}></div>
                <span className="text-gray-400">Low to High Liquidity</span>
              </div>
              <div className="flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-yellow-400" />
                <span className="text-gray-400">Hot Zone (&gt;$10M)</span>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'levels' && (
          <div className="space-y-4">
            {/* Hot Zone Cards */}
            <div className="grid grid-cols-2 gap-4">
              {/* Long Liquidation Clusters */}
              <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown className="w-4 h-4 text-red-400" />
                  <h3 className="text-sm font-medium text-red-400">Long Liquidation Clusters</h3>
                </div>
                <div className="space-y-2">
                  {liquidityData.hotZones
                    .filter(z => z.isLongLiq)
                    .sort((a, b) => b.totalLiquidity - a.totalLiquidity)
                    .slice(0, 5)
                    .map((zone, idx) => (
                      <div key={idx} className="flex items-center justify-between">
                        <span className="text-sm text-gray-300">
                          ${formatPrice(zone.price)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">
                            {zone.percentFromCurrent.toFixed(1)}%
                          </span>
                          <span className="text-sm text-red-400 font-medium">
                            {formatValue(zone.totalLiquidity)}
                          </span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Short Liquidation Clusters */}
              <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-green-400" />
                  <h3 className="text-sm font-medium text-green-400">Short Liquidation Clusters</h3>
                </div>
                <div className="space-y-2">
                  {liquidityData.hotZones
                    .filter(z => !z.isLongLiq)
                    .sort((a, b) => b.totalLiquidity - a.totalLiquidity)
                    .slice(0, 5)
                    .map((zone, idx) => (
                      <div key={idx} className="flex items-center justify-between">
                        <span className="text-sm text-gray-300">
                          ${formatPrice(zone.price)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-500">
                            +{zone.percentFromCurrent.toFixed(1)}%
                          </span>
                          <span className="text-sm text-green-400 font-medium">
                            {formatValue(zone.totalLiquidity)}
                          </span>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            {/* Leverage Breakdown */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Liquidity by Leverage</h3>
              <div className="space-y-2">
                {[
                  { label: '5x', key: 'liq5x', color: 'bg-blue-500' },
                  { label: '10x', key: 'liq10x', color: 'bg-cyan-500' },
                  { label: '25x', key: 'liq25x', color: 'bg-green-500' },
                  { label: '50x', key: 'liq50x', color: 'bg-yellow-500' },
                  { label: '100x', key: 'liq100x', color: 'bg-red-500' }
                ].map(({ label, key, color }) => {
                  const total = liquidityData.zones.reduce((sum, z) => sum + z[key], 0)
                  const maxTotal = Math.max(...['liq5x', 'liq10x', 'liq25x', 'liq50x', 'liq100x'].map(
                    k => liquidityData.zones.reduce((sum, z) => sum + z[k], 0)
                  ))

                  return (
                    <div key={label} className="flex items-center gap-3">
                      <span className="text-xs text-gray-400 w-12">{label}</span>
                      <div className="flex-1 h-4 bg-white/5 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${color}/60 rounded-full`}
                          style={{ width: `${(total / maxTotal) * 100}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-400 w-16 text-right">
                        {formatValue(total)}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}

        {viewMode === 'analysis' && (
          <div className="space-y-4">
            {/* Liquidity Balance */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-red-500/10 rounded-lg p-4 text-center border border-red-500/20">
                <div className="text-2xl font-bold text-red-400">
                  {formatValue(liquidityData.totalLongLiq)}
                </div>
                <div className="text-xs text-gray-400 mt-1">Long Liquidations</div>
                <div className="text-xs text-gray-500 mt-1">
                  Below current price
                </div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className={`text-2xl font-bold ${
                  liquidityData.imbalance > 0 ? 'text-green-400' : 'text-red-400'
                }`}>
                  {liquidityData.imbalance > 0 ? '+' : ''}{liquidityData.imbalance.toFixed(1)}%
                </div>
                <div className="text-xs text-gray-400 mt-1">Imbalance</div>
                <div className="text-xs text-gray-500 mt-1">
                  {liquidityData.imbalance > 0 ? 'More short liqs above' : 'More long liqs below'}
                </div>
              </div>
              <div className="bg-green-500/10 rounded-lg p-4 text-center border border-green-500/20">
                <div className="text-2xl font-bold text-green-400">
                  {formatValue(liquidityData.totalShortLiq)}
                </div>
                <div className="text-xs text-gray-400 mt-1">Short Liquidations</div>
                <div className="text-xs text-gray-500 mt-1">
                  Above current price
                </div>
              </div>
            </div>

            {/* Magnet Analysis */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Liquidity Magnet Analysis</h3>
              <p className="text-sm text-gray-300 mb-4">
                Price tends to &quot;hunt&quot; liquidity clusters as market makers seek to trigger stops and liquidations.
                Large clusters act as price magnets.
              </p>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-red-500/10 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Downside Target</div>
                  <div className="text-lg font-medium text-red-400">
                    ${formatPrice(liquidityData.nearestLongLiq || 0)}
                  </div>
                  <div className="text-xs text-gray-500">
                    Nearest long liquidation cluster
                  </div>
                </div>
                <div className="bg-green-500/10 rounded-lg p-3">
                  <div className="text-xs text-gray-400 mb-1">Upside Target</div>
                  <div className="text-lg font-medium text-green-400">
                    ${formatPrice(liquidityData.nearestShortLiq || 0)}
                  </div>
                  <div className="text-xs text-gray-500">
                    Nearest short liquidation cluster
                  </div>
                </div>
              </div>
            </div>

            {/* Trading Signal */}
            <div className={`rounded-lg p-4 border ${
              Math.abs(liquidityData.imbalance) > 30
                ? liquidityData.imbalance > 0
                  ? 'bg-green-500/10 border-green-500/20'
                  : 'bg-red-500/10 border-red-500/20'
                : 'bg-white/5 border-white/10'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Zap className={`w-4 h-4 ${
                  Math.abs(liquidityData.imbalance) > 30
                    ? liquidityData.imbalance > 0 ? 'text-green-400' : 'text-red-400'
                    : 'text-gray-400'
                }`} />
                <h3 className="text-sm font-medium text-white">Liquidity Signal</h3>
              </div>
              <p className="text-sm text-gray-300">
                {Math.abs(liquidityData.imbalance) > 30
                  ? liquidityData.imbalance > 0
                    ? 'Heavy short liquidations above - price likely to squeeze upward to hunt stops'
                    : 'Heavy long liquidations below - price likely to cascade down to trigger stops'
                  : 'Balanced liquidation levels - no strong directional liquidity magnet'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default LiquidityMap
