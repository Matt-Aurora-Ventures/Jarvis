import React, { useState, useMemo, useEffect } from 'react'
import {
  Grid3x3, RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Info,
  Calendar, ChevronDown, Download, Settings, Eye, BarChart2, PieChart,
  ArrowUpDown, Filter, Search, Maximize2, Minimize2
} from 'lucide-react'

const SUPPORTED_TOKENS = [
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT',
  'MATIC', 'LINK', 'UNI', 'AAVE', 'LDO', 'ARB', 'OP',
  'ATOM', 'NEAR', 'INJ', 'APT', 'SUI', 'DOGE', 'SHIB'
]

const TIME_PERIODS = [
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: '90d', label: '90 Days' },
  { value: '180d', label: '6 Months' },
  { value: '365d', label: '1 Year' }
]

const CORRELATION_THRESHOLDS = {
  veryStrong: 0.8,
  strong: 0.6,
  moderate: 0.4,
  weak: 0.2
}

export function CorrelationMatrix() {
  const [selectedTokens, setSelectedTokens] = useState(['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC', 'LINK'])
  const [timePeriod, setTimePeriod] = useState('30d')
  const [correlationData, setCorrelationData] = useState({})
  const [isLoading, setIsLoading] = useState(false)
  const [hoveredCell, setHoveredCell] = useState(null)
  const [showSettings, setShowSettings] = useState(false)
  const [colorScheme, setColorScheme] = useState('diverging')
  const [showValues, setShowValues] = useState(true)
  const [sortBy, setSortBy] = useState(null)

  // Generate mock correlation data
  useEffect(() => {
    const generateCorrelations = () => {
      setIsLoading(true)
      const data = {}

      // Generate correlation matrix
      selectedTokens.forEach((token1) => {
        data[token1] = {}
        selectedTokens.forEach((token2) => {
          if (token1 === token2) {
            data[token1][token2] = 1
          } else if (data[token2]?.[token1] !== undefined) {
            data[token1][token2] = data[token2][token1]
          } else {
            // Generate realistic correlations
            // BTC and ETH have high correlation
            if ((token1 === 'BTC' && token2 === 'ETH') || (token1 === 'ETH' && token2 === 'BTC')) {
              data[token1][token2] = 0.85 + (Math.random() * 0.1 - 0.05)
            }
            // Meme coins correlate with each other
            else if (['DOGE', 'SHIB'].includes(token1) && ['DOGE', 'SHIB'].includes(token2)) {
              data[token1][token2] = 0.75 + (Math.random() * 0.15 - 0.075)
            }
            // L1s correlate moderately
            else if (['SOL', 'AVAX', 'NEAR', 'APT', 'SUI'].includes(token1) &&
                     ['SOL', 'AVAX', 'NEAR', 'APT', 'SUI'].includes(token2)) {
              data[token1][token2] = 0.6 + (Math.random() * 0.2 - 0.1)
            }
            // DeFi tokens correlate with ETH
            else if (['UNI', 'AAVE', 'LDO'].includes(token1) && token2 === 'ETH') {
              data[token1][token2] = 0.7 + (Math.random() * 0.15 - 0.075)
            }
            else if (['UNI', 'AAVE', 'LDO'].includes(token2) && token1 === 'ETH') {
              data[token1][token2] = 0.7 + (Math.random() * 0.15 - 0.075)
            }
            // L2s correlate with ETH
            else if (['ARB', 'OP', 'MATIC'].includes(token1) && token2 === 'ETH') {
              data[token1][token2] = 0.75 + (Math.random() * 0.1 - 0.05)
            }
            else if (['ARB', 'OP', 'MATIC'].includes(token2) && token1 === 'ETH') {
              data[token1][token2] = 0.75 + (Math.random() * 0.1 - 0.05)
            }
            // Everything correlates with BTC to some degree
            else if (token1 === 'BTC' || token2 === 'BTC') {
              data[token1][token2] = 0.5 + (Math.random() * 0.3 - 0.15)
            }
            // General market correlation
            else {
              data[token1][token2] = 0.4 + (Math.random() * 0.4 - 0.2)
            }

            // Clamp to [-1, 1]
            data[token1][token2] = Math.max(-1, Math.min(1, data[token1][token2]))
          }
        })
      })

      setCorrelationData(data)
      setIsLoading(false)
    }

    generateCorrelations()
  }, [selectedTokens, timePeriod])

  // Calculate statistics
  const stats = useMemo(() => {
    let highestPair = { tokens: [], value: -1 }
    let lowestPair = { tokens: [], value: 1 }
    let avgCorrelation = 0
    let count = 0

    selectedTokens.forEach((token1, i) => {
      selectedTokens.forEach((token2, j) => {
        if (i < j) {
          const corr = correlationData[token1]?.[token2] || 0
          if (corr > highestPair.value) {
            highestPair = { tokens: [token1, token2], value: corr }
          }
          if (corr < lowestPair.value) {
            lowestPair = { tokens: [token1, token2], value: corr }
          }
          avgCorrelation += corr
          count++
        }
      })
    })

    return {
      highestPair,
      lowestPair,
      avgCorrelation: count > 0 ? avgCorrelation / count : 0,
      totalPairs: count
    }
  }, [correlationData, selectedTokens])

  // Get color for correlation value
  const getCorrelationColor = (value) => {
    if (colorScheme === 'diverging') {
      if (value >= CORRELATION_THRESHOLDS.veryStrong) return 'bg-green-500'
      if (value >= CORRELATION_THRESHOLDS.strong) return 'bg-green-400/80'
      if (value >= CORRELATION_THRESHOLDS.moderate) return 'bg-green-400/50'
      if (value >= CORRELATION_THRESHOLDS.weak) return 'bg-green-400/30'
      if (value >= 0) return 'bg-white/10'
      if (value >= -CORRELATION_THRESHOLDS.weak) return 'bg-white/10'
      if (value >= -CORRELATION_THRESHOLDS.moderate) return 'bg-red-400/30'
      if (value >= -CORRELATION_THRESHOLDS.strong) return 'bg-red-400/50'
      if (value >= -CORRELATION_THRESHOLDS.veryStrong) return 'bg-red-400/80'
      return 'bg-red-500'
    } else {
      // Heat map style
      const intensity = Math.abs(value)
      if (intensity >= 0.8) return 'bg-purple-500'
      if (intensity >= 0.6) return 'bg-purple-400/80'
      if (intensity >= 0.4) return 'bg-purple-400/50'
      if (intensity >= 0.2) return 'bg-purple-400/30'
      return 'bg-white/10'
    }
  }

  const getCorrelationLabel = (value) => {
    const absValue = Math.abs(value)
    if (absValue >= CORRELATION_THRESHOLDS.veryStrong) return 'Very Strong'
    if (absValue >= CORRELATION_THRESHOLDS.strong) return 'Strong'
    if (absValue >= CORRELATION_THRESHOLDS.moderate) return 'Moderate'
    if (absValue >= CORRELATION_THRESHOLDS.weak) return 'Weak'
    return 'Negligible'
  }

  const toggleToken = (token) => {
    setSelectedTokens(prev => {
      if (prev.includes(token)) {
        return prev.filter(t => t !== token)
      }
      return [...prev, token]
    })
  }

  const exportData = () => {
    const rows = ['Token,' + selectedTokens.join(',')]
    selectedTokens.forEach(token1 => {
      const row = [token1]
      selectedTokens.forEach(token2 => {
        row.push((correlationData[token1]?.[token2] || 0).toFixed(4))
      })
      rows.push(row.join(','))
    })

    const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `correlation_matrix_${timePeriod}.csv`
    a.click()
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Grid3x3 className="w-6 h-6 text-purple-400" />
          <h2 className="text-xl font-bold">Correlation Matrix</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="px-3 py-2 bg-white/5 rounded-lg hover:bg-white/10 transition flex items-center gap-2"
          >
            <Settings className="w-4 h-4" />
            Settings
          </button>
          <button
            onClick={exportData}
            className="px-3 py-2 bg-white/5 rounded-lg hover:bg-white/10 transition flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
          <select
            value={timePeriod}
            onChange={(e) => setTimePeriod(e.target.value)}
            className="px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
          >
            {TIME_PERIODS.map(p => (
              <option key={p.value} value={p.value} className="bg-[#0a0e14]">{p.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Highest Correlation</div>
          <div className="text-xl font-bold text-green-400">
            {stats.highestPair.value.toFixed(3)}
          </div>
          <div className="text-xs text-white/40">
            {stats.highestPair.tokens.join(' / ')}
          </div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Lowest Correlation</div>
          <div className="text-xl font-bold text-red-400">
            {stats.lowestPair.value.toFixed(3)}
          </div>
          <div className="text-xs text-white/40">
            {stats.lowestPair.tokens.join(' / ')}
          </div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Average Correlation</div>
          <div className="text-xl font-bold">
            {stats.avgCorrelation.toFixed(3)}
          </div>
          <div className="text-xs text-white/40">{getCorrelationLabel(stats.avgCorrelation)}</div>
        </div>
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="text-white/60 text-sm mb-1">Assets Analyzed</div>
          <div className="text-xl font-bold">{selectedTokens.length}</div>
          <div className="text-xs text-white/40">{stats.totalPairs} pairs</div>
        </div>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <h3 className="font-semibold mb-4">Matrix Settings</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm text-white/60 mb-2">Color Scheme</label>
              <select
                value={colorScheme}
                onChange={(e) => setColorScheme(e.target.value)}
                className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
              >
                <option value="diverging" className="bg-[#0a0e14]">Diverging (Red-Green)</option>
                <option value="heatmap" className="bg-[#0a0e14]">Heat Map (Purple)</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">Display Values</label>
              <button
                onClick={() => setShowValues(!showValues)}
                className={`w-full px-4 py-2 rounded-lg transition ${
                  showValues ? 'bg-purple-500/20 text-purple-400' : 'bg-white/5'
                }`}
              >
                {showValues ? 'Values Visible' : 'Values Hidden'}
              </button>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">Select Tokens</label>
              <div className="text-sm text-white/40">
                {selectedTokens.length} of {SUPPORTED_TOKENS.length} selected
              </div>
            </div>
          </div>

          {/* Token Selection */}
          <div className="mt-4">
            <label className="block text-sm text-white/60 mb-2">Tokens in Matrix</label>
            <div className="flex flex-wrap gap-2">
              {SUPPORTED_TOKENS.map(token => (
                <button
                  key={token}
                  onClick={() => toggleToken(token)}
                  className={`px-3 py-1 rounded-lg text-sm transition ${
                    selectedTokens.includes(token)
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  {token}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Correlation Matrix */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-4 overflow-x-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-white/40" />
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="p-2 text-left text-sm text-white/60 sticky left-0 bg-[#0a0e14] z-10"></th>
                {selectedTokens.map(token => (
                  <th key={token} className="p-2 text-center text-sm font-medium min-w-[60px]">
                    {token}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {selectedTokens.map((token1, i) => (
                <tr key={token1}>
                  <td className="p-2 text-sm font-medium sticky left-0 bg-[#0a0e14] z-10">{token1}</td>
                  {selectedTokens.map((token2, j) => {
                    const value = correlationData[token1]?.[token2] || 0
                    const isHovered = hoveredCell?.row === i && hoveredCell?.col === j
                    const isDiagonal = i === j

                    return (
                      <td
                        key={token2}
                        className="p-1"
                        onMouseEnter={() => setHoveredCell({ row: i, col: j })}
                        onMouseLeave={() => setHoveredCell(null)}
                      >
                        <div
                          className={`
                            w-full h-12 rounded flex items-center justify-center text-xs font-mono transition
                            ${getCorrelationColor(value)}
                            ${isDiagonal ? 'opacity-50' : ''}
                            ${isHovered ? 'ring-2 ring-white/50' : ''}
                          `}
                          title={`${token1}/${token2}: ${value.toFixed(4)}`}
                        >
                          {showValues && (
                            <span className={value >= 0.5 || value <= -0.5 ? 'text-white' : 'text-white/70'}>
                              {value.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Hovered Cell Info */}
      {hoveredCell && selectedTokens[hoveredCell.row] !== selectedTokens[hoveredCell.col] && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="font-bold">{selectedTokens[hoveredCell.row]}</span>
              <ArrowUpDown className="w-4 h-4 text-white/40" />
              <span className="font-bold">{selectedTokens[hoveredCell.col]}</span>
            </div>
            <div className="text-2xl font-bold">
              {(correlationData[selectedTokens[hoveredCell.row]]?.[selectedTokens[hoveredCell.col]] || 0).toFixed(4)}
            </div>
            <div className={`px-3 py-1 rounded-lg text-sm ${
              (correlationData[selectedTokens[hoveredCell.row]]?.[selectedTokens[hoveredCell.col]] || 0) >= 0
                ? 'bg-green-500/20 text-green-400'
                : 'bg-red-500/20 text-red-400'
            }`}>
              {getCorrelationLabel(correlationData[selectedTokens[hoveredCell.row]]?.[selectedTokens[hoveredCell.col]] || 0)}
              {' '}
              {(correlationData[selectedTokens[hoveredCell.row]]?.[selectedTokens[hoveredCell.col]] || 0) >= 0 ? 'Positive' : 'Negative'}
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-4">
        <h3 className="font-semibold mb-3">Correlation Guide</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center">
            <div className="h-8 bg-green-500 rounded mb-2"></div>
            <div className="text-xs text-white/60">Very Strong</div>
            <div className="text-xs text-white/40">0.8 to 1.0</div>
          </div>
          <div className="text-center">
            <div className="h-8 bg-green-400/50 rounded mb-2"></div>
            <div className="text-xs text-white/60">Strong</div>
            <div className="text-xs text-white/40">0.6 to 0.8</div>
          </div>
          <div className="text-center">
            <div className="h-8 bg-white/10 rounded mb-2"></div>
            <div className="text-xs text-white/60">Moderate/Weak</div>
            <div className="text-xs text-white/40">0.0 to 0.6</div>
          </div>
          <div className="text-center">
            <div className="h-8 bg-red-400/50 rounded mb-2"></div>
            <div className="text-xs text-white/60">Strong Negative</div>
            <div className="text-xs text-white/40">-0.6 to -0.8</div>
          </div>
          <div className="text-center">
            <div className="h-8 bg-red-500 rounded mb-2"></div>
            <div className="text-xs text-white/60">Very Strong Neg</div>
            <div className="text-xs text-white/40">-0.8 to -1.0</div>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <p className="font-medium text-blue-400 mb-1">About Correlation Analysis</p>
            <ul className="list-disc list-inside space-y-1 text-white/60">
              <li>Correlation ranges from -1 (perfect negative) to +1 (perfect positive)</li>
              <li>High correlation means assets move together; useful for understanding portfolio risk</li>
              <li>Low correlation pairs can help diversify and reduce overall portfolio volatility</li>
              <li>Correlations change over time, especially during market stress events</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default CorrelationMatrix
