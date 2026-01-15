import React, { useState, useMemo } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Zap,
  Search,
  ChevronDown,
  ArrowUpRight,
  ArrowDownRight,
  Target,
  Eye,
  Bell
} from 'lucide-react'

export function DeltaDivergenceScanner() {
  const [viewMode, setViewMode] = useState('scanner') // scanner, alerts, education
  const [timeframe, setTimeframe] = useState('4h')
  const [minStrength, setMinStrength] = useState(50)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'RAY', 'ORCA']

  // Generate divergence data
  const divergenceData = useMemo(() => {
    return tokens.map(token => {
      const priceChange = (Math.random() - 0.5) * 10
      const deltaChange = (Math.random() - 0.5) * 20
      const cvdChange = (Math.random() - 0.5) * 15

      // Detect divergences
      const priceDeltaDivergence = (priceChange > 0 && deltaChange < -5) || (priceChange < 0 && deltaChange > 5)
      const priceCvdDivergence = (priceChange > 0 && cvdChange < -5) || (priceChange < 0 && cvdChange > 5)

      const divergenceType = priceDeltaDivergence
        ? priceChange > 0 ? 'bearish' : 'bullish'
        : priceCvdDivergence
        ? priceChange > 0 ? 'bearish' : 'bullish'
        : 'none'

      const strength = priceDeltaDivergence || priceCvdDivergence
        ? Math.abs(priceChange - deltaChange) * 5
        : 0

      const price = token === 'SOL' ? 150 + priceChange : token === 'ETH' ? 3200 + priceChange * 20 : token === 'BTC' ? 95000 + priceChange * 100 : 0.5 + priceChange * 0.01

      return {
        token,
        price,
        priceChange,
        deltaChange,
        cvdChange,
        divergenceType,
        divergenceSignal: priceDeltaDivergence ? 'Price-Delta' : priceCvdDivergence ? 'Price-CVD' : 'None',
        strength: Math.min(strength, 100),
        volume24h: Math.floor(Math.random() * 50000000) + 5000000,
        openInterest: Math.floor(Math.random() * 100000000) + 10000000,
        cumDelta: (Math.random() - 0.5) * 1000000,
        timestamp: new Date(Date.now() - Math.random() * 3600000).toLocaleTimeString()
      }
    })
  }, [timeframe])

  // Filter by strength
  const filteredData = useMemo(() => {
    return divergenceData
      .filter(d => d.strength >= minStrength || d.divergenceType !== 'none')
      .sort((a, b) => b.strength - a.strength)
  }, [divergenceData, minStrength])

  // Active alerts
  const activeAlerts = useMemo(() => {
    return filteredData
      .filter(d => d.divergenceType !== 'none' && d.strength >= 60)
      .map(d => ({
        ...d,
        confidence: d.strength >= 80 ? 'High' : d.strength >= 60 ? 'Medium' : 'Low',
        action: d.divergenceType === 'bullish' ? 'Watch for bounce' : 'Watch for rejection'
      }))
  }, [filteredData])

  const formatVolume = (vol) => {
    if (vol >= 1000000) return `$${(vol / 1000000).toFixed(1)}M`
    if (vol >= 1000) return `$${(vol / 1000).toFixed(0)}K`
    return `$${vol}`
  }

  const formatPrice = (token, price) => {
    if (token === 'BTC') return `$${price.toFixed(0)}`
    if (token === 'ETH') return `$${price.toFixed(0)}`
    if (token === 'SOL') return `$${price.toFixed(2)}`
    return `$${price.toFixed(4)}`
  }

  return (
    <div className="bg-[#0a0e14] rounded-lg border border-white/10">
      {/* Header */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-white">Delta Divergence Scanner</h2>
          </div>

          <div className="flex items-center gap-2">
            {/* Timeframe */}
            <div className="flex bg-white/5 rounded-lg p-0.5">
              {['1h', '4h', '1D', '1W'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className={`px-3 py-1 text-xs rounded-md transition-colors ${
                    timeframe === tf
                      ? 'bg-amber-500/30 text-amber-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* View Mode */}
        <div className="flex items-center justify-between">
          <div className="flex bg-white/5 rounded-lg p-0.5">
            {[
              { id: 'scanner', label: 'Scanner', icon: Search },
              { id: 'alerts', label: 'Active Alerts', icon: Bell },
              { id: 'education', label: 'Learn', icon: Eye }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setViewMode(id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md transition-colors ${
                  viewMode === id
                    ? 'bg-amber-500/30 text-amber-400'
                    : 'text-gray-400 hover:text-white'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Strength Filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Min Strength:</span>
            <select
              value={minStrength}
              onChange={(e) => setMinStrength(Number(e.target.value))}
              className="bg-white/5 border border-white/10 rounded px-2 py-1 text-xs text-white"
            >
              <option value={0}>All</option>
              <option value={30}>30+</option>
              <option value={50}>50+</option>
              <option value={70}>70+</option>
            </select>
          </div>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="px-4 py-3 border-b border-white/10 bg-white/[0.02]">
        <div className="grid grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-gray-500 mb-1">Bullish Divergences</div>
            <div className="text-sm font-medium text-green-400">
              {filteredData.filter(d => d.divergenceType === 'bullish').length}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Bearish Divergences</div>
            <div className="text-sm font-medium text-red-400">
              {filteredData.filter(d => d.divergenceType === 'bearish').length}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">High Confidence</div>
            <div className="text-sm font-medium text-yellow-400">
              {activeAlerts.filter(a => a.confidence === 'High').length}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500 mb-1">Scanning</div>
            <div className="text-sm font-medium text-white">
              {tokens.length} tokens
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="p-4">
        {viewMode === 'scanner' && (
          <div className="space-y-4">
            {/* Scanner Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-xs text-gray-500">
                    <th className="text-left py-2">Token</th>
                    <th className="text-right py-2">Price Change</th>
                    <th className="text-right py-2">Delta Change</th>
                    <th className="text-right py-2">CVD Change</th>
                    <th className="text-center py-2">Signal</th>
                    <th className="text-center py-2">Type</th>
                    <th className="text-right py-2">Strength</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredData.map((item) => (
                    <tr key={item.token} className="border-t border-white/5 hover:bg-white/5">
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{item.token}</span>
                          <span className="text-xs text-gray-500">{formatPrice(item.token, item.price)}</span>
                        </div>
                      </td>
                      <td className={`py-3 text-right text-sm ${item.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {item.priceChange >= 0 ? '+' : ''}{item.priceChange.toFixed(2)}%
                      </td>
                      <td className={`py-3 text-right text-sm ${item.deltaChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {item.deltaChange >= 0 ? '+' : ''}{item.deltaChange.toFixed(2)}%
                      </td>
                      <td className={`py-3 text-right text-sm ${item.cvdChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {item.cvdChange >= 0 ? '+' : ''}{item.cvdChange.toFixed(2)}%
                      </td>
                      <td className="py-3 text-center">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          item.divergenceSignal !== 'None'
                            ? 'bg-amber-500/20 text-amber-400'
                            : 'bg-gray-500/20 text-gray-400'
                        }`}>
                          {item.divergenceSignal}
                        </span>
                      </td>
                      <td className="py-3 text-center">
                        {item.divergenceType === 'bullish' && (
                          <span className="flex items-center justify-center gap-1 text-green-400 text-xs">
                            <ArrowUpRight className="w-3 h-3" />
                            Bullish
                          </span>
                        )}
                        {item.divergenceType === 'bearish' && (
                          <span className="flex items-center justify-center gap-1 text-red-400 text-xs">
                            <ArrowDownRight className="w-3 h-3" />
                            Bearish
                          </span>
                        )}
                        {item.divergenceType === 'none' && (
                          <span className="text-gray-500 text-xs">-</span>
                        )}
                      </td>
                      <td className="py-3 text-right">
                        {item.strength > 0 && (
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-20 h-2 bg-white/10 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  item.strength >= 70 ? 'bg-green-500' :
                                  item.strength >= 40 ? 'bg-yellow-500' : 'bg-gray-500'
                                }`}
                                style={{ width: `${item.strength}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-400 w-8">{item.strength.toFixed(0)}</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {viewMode === 'alerts' && (
          <div className="space-y-4">
            {/* Active Alert Cards */}
            {activeAlerts.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                No active divergence alerts at current thresholds
              </div>
            ) : (
              <div className="space-y-3">
                {activeAlerts.map((alert) => (
                  <div
                    key={alert.token}
                    className={`p-4 rounded-lg border ${
                      alert.divergenceType === 'bullish'
                        ? 'bg-green-500/10 border-green-500/20'
                        : 'bg-red-500/10 border-red-500/20'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        {alert.divergenceType === 'bullish' ? (
                          <ArrowUpRight className="w-6 h-6 text-green-400" />
                        ) : (
                          <ArrowDownRight className="w-6 h-6 text-red-400" />
                        )}
                        <div>
                          <div className="text-lg font-medium text-white">{alert.token}</div>
                          <div className="text-xs text-gray-400">{formatPrice(alert.token, alert.price)}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-sm font-medium ${
                          alert.confidence === 'High' ? 'text-green-400' :
                          alert.confidence === 'Medium' ? 'text-yellow-400' : 'text-gray-400'
                        }`}>
                          {alert.confidence} Confidence
                        </div>
                        <div className="text-xs text-gray-500">{alert.timestamp}</div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mb-3">
                      <div>
                        <div className="text-xs text-gray-500">Price</div>
                        <div className={`text-sm ${alert.priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {alert.priceChange >= 0 ? '+' : ''}{alert.priceChange.toFixed(2)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Delta</div>
                        <div className={`text-sm ${alert.deltaChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {alert.deltaChange >= 0 ? '+' : ''}{alert.deltaChange.toFixed(2)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Signal</div>
                        <div className="text-sm text-amber-400">{alert.divergenceSignal}</div>
                      </div>
                    </div>

                    <div className={`p-2 rounded ${
                      alert.divergenceType === 'bullish' ? 'bg-green-500/10' : 'bg-red-500/10'
                    }`}>
                      <div className="flex items-center gap-2">
                        <Zap className={`w-4 h-4 ${alert.divergenceType === 'bullish' ? 'text-green-400' : 'text-red-400'}`} />
                        <span className="text-sm text-white">{alert.action}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {viewMode === 'education' && (
          <div className="space-y-4">
            {/* What is Delta Divergence */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">What is Delta Divergence?</h3>
              <p className="text-sm text-gray-300 mb-4">
                Delta divergence occurs when price movement disagrees with order flow (delta).
                This often signals upcoming reversals as the &quot;smart money&quot; positions ahead of retail.
              </p>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-green-500/10 rounded-lg p-3 border border-green-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <ArrowUpRight className="w-4 h-4 text-green-400" />
                    <span className="text-sm font-medium text-green-400">Bullish Divergence</span>
                  </div>
                  <p className="text-xs text-gray-300">
                    Price making lower lows while delta makes higher lows.
                    Sellers exhausted, buyers accumulating.
                  </p>
                </div>

                <div className="bg-red-500/10 rounded-lg p-3 border border-red-500/20">
                  <div className="flex items-center gap-2 mb-2">
                    <ArrowDownRight className="w-4 h-4 text-red-400" />
                    <span className="text-sm font-medium text-red-400">Bearish Divergence</span>
                  </div>
                  <p className="text-xs text-gray-300">
                    Price making higher highs while delta makes lower highs.
                    Buyers exhausted, sellers distributing.
                  </p>
                </div>
              </div>
            </div>

            {/* How to Trade */}
            <div className="bg-white/5 rounded-lg p-4">
              <h3 className="text-sm font-medium text-white mb-3">Trading Delta Divergences</h3>
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-xs font-medium">1</div>
                  <div>
                    <div className="text-sm text-white">Wait for Confirmation</div>
                    <div className="text-xs text-gray-400">Don&apos;t trade divergence alone - wait for price to show reversal signs</div>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-xs font-medium">2</div>
                  <div>
                    <div className="text-sm text-white">Check Multiple Timeframes</div>
                    <div className="text-xs text-gray-400">Higher timeframe divergences are more reliable</div>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-xs font-medium">3</div>
                  <div>
                    <div className="text-sm text-white">Use Tight Stops</div>
                    <div className="text-xs text-gray-400">Divergences can fail - protect capital with stops below/above recent swing</div>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center text-amber-400 text-xs font-medium">4</div>
                  <div>
                    <div className="text-sm text-white">Scale Into Position</div>
                    <div className="text-xs text-gray-400">Don&apos;t FOMO - build position as confirmation develops</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Warning */}
            <div className="bg-yellow-500/10 rounded-lg p-4 border border-yellow-500/20">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-yellow-400" />
                <span className="text-sm font-medium text-yellow-400">Important Warning</span>
              </div>
              <p className="text-sm text-gray-300">
                Divergences are not guaranteed signals. They indicate potential reversals but can persist
                for extended periods. Always use proper risk management and don&apos;t rely solely on divergence signals.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default DeltaDivergenceScanner
