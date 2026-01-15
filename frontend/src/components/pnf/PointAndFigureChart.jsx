import React, { useState, useMemo, useEffect } from 'react'
import { TrendingUp, TrendingDown, Settings, Maximize2, Grid3X3, Target, ArrowUpCircle, ArrowDownCircle, Calculator, History, Layers } from 'lucide-react'

export function PointAndFigureChart({
  symbol = 'BTC/USDT',
  priceData = [],
  boxSize = 'auto',
  reversalAmount = 3,
  onPatternDetected,
  onBreakout
}) {
  const [selectedBoxSize, setSelectedBoxSize] = useState(boxSize)
  const [selectedReversal, setSelectedReversal] = useState(reversalAmount)
  const [showPatterns, setShowPatterns] = useState(true)
  const [showTargets, setShowTargets] = useState(true)
  const [chartMethod, setChartMethod] = useState('close') // close, high-low
  const [isExpanded, setIsExpanded] = useState(false)

  // Generate sample P&F data if none provided
  const sampleData = useMemo(() => {
    if (priceData.length > 0) return priceData

    const data = []
    let basePrice = 45000
    const movements = [
      { dir: 'X', boxes: 5 }, { dir: 'O', boxes: 3 }, { dir: 'X', boxes: 7 },
      { dir: 'O', boxes: 4 }, { dir: 'X', boxes: 6 }, { dir: 'O', boxes: 5 },
      { dir: 'X', boxes: 8 }, { dir: 'O', boxes: 3 }, { dir: 'X', boxes: 4 },
      { dir: 'O', boxes: 6 }, { dir: 'X', boxes: 9 }, { dir: 'O', boxes: 4 },
      { dir: 'X', boxes: 5 }, { dir: 'O', boxes: 7 }, { dir: 'X', boxes: 6 },
      { dir: 'O', boxes: 3 }, { dir: 'X', boxes: 8 }, { dir: 'O', boxes: 5 },
      { dir: 'X', boxes: 4 }, { dir: 'O', boxes: 6 }
    ]

    movements.forEach((move, colIdx) => {
      const column = {
        type: move.dir,
        startPrice: basePrice,
        boxes: move.boxes,
        colIndex: colIdx
      }
      data.push(column)

      if (move.dir === 'X') {
        basePrice += move.boxes * 100
      } else {
        basePrice -= move.boxes * 100
      }
    })

    return data
  }, [priceData])

  // Calculate P&F chart metrics
  const chartMetrics = useMemo(() => {
    const columns = sampleData
    const totalColumns = columns.length
    const xColumns = columns.filter(c => c.type === 'X').length
    const oColumns = columns.filter(c => c.type === 'O').length

    // Find highest and lowest points
    let highestPrice = 0
    let lowestPrice = Infinity
    let currentPrice = 45000

    columns.forEach(col => {
      const colHigh = col.type === 'X'
        ? col.startPrice + (col.boxes * 100)
        : col.startPrice
      const colLow = col.type === 'X'
        ? col.startPrice
        : col.startPrice - (col.boxes * 100)

      highestPrice = Math.max(highestPrice, colHigh)
      lowestPrice = Math.min(lowestPrice, colLow)
      currentPrice = col.type === 'X' ? colHigh : colLow
    })

    // Calculate trend
    const recentColumns = columns.slice(-5)
    const avgRecentBoxes = recentColumns.reduce((sum, c) => sum + c.boxes, 0) / recentColumns.length
    const lastColumn = columns[columns.length - 1]
    const trend = lastColumn?.type === 'X' ? 'bullish' : 'bearish'

    return {
      totalColumns,
      xColumns,
      oColumns,
      highestPrice,
      lowestPrice,
      currentPrice,
      trend,
      avgBoxesPerColumn: avgRecentBoxes.toFixed(1),
      priceRange: highestPrice - lowestPrice
    }
  }, [sampleData])

  // Detect P&F patterns
  const patterns = useMemo(() => {
    const detected = []
    const columns = sampleData

    // Double Top (bullish breakout)
    for (let i = 2; i < columns.length; i++) {
      if (columns[i].type === 'X' && columns[i-2].type === 'X') {
        const currentHigh = columns[i].startPrice + (columns[i].boxes * 100)
        const prevHigh = columns[i-2].startPrice + (columns[i-2].boxes * 100)
        if (Math.abs(currentHigh - prevHigh) < 200 && columns[i].boxes > columns[i-2].boxes) {
          detected.push({
            type: 'Double Top Breakout',
            signal: 'bullish',
            column: i,
            price: currentHigh,
            target: currentHigh + (columns[i].boxes * 100)
          })
        }
      }
    }

    // Double Bottom (bearish breakout)
    for (let i = 2; i < columns.length; i++) {
      if (columns[i].type === 'O' && columns[i-2].type === 'O') {
        const currentLow = columns[i].startPrice - (columns[i].boxes * 100)
        const prevLow = columns[i-2].startPrice - (columns[i-2].boxes * 100)
        if (Math.abs(currentLow - prevLow) < 200 && columns[i].boxes > columns[i-2].boxes) {
          detected.push({
            type: 'Double Bottom Breakdown',
            signal: 'bearish',
            column: i,
            price: currentLow,
            target: currentLow - (columns[i].boxes * 100)
          })
        }
      }
    }

    // Triple Top
    for (let i = 4; i < columns.length; i++) {
      if (columns[i].type === 'X' && columns[i-2].type === 'X' && columns[i-4].type === 'X') {
        const h1 = columns[i].startPrice + (columns[i].boxes * 100)
        const h2 = columns[i-2].startPrice + (columns[i-2].boxes * 100)
        const h3 = columns[i-4].startPrice + (columns[i-4].boxes * 100)
        if (Math.abs(h1 - h2) < 200 && Math.abs(h2 - h3) < 200 && columns[i].boxes > columns[i-2].boxes) {
          detected.push({
            type: 'Triple Top Breakout',
            signal: 'bullish',
            strength: 'strong',
            column: i,
            price: h1,
            target: h1 + (columns[i].boxes * 150)
          })
        }
      }
    }

    // Ascending Triple Bottom
    for (let i = 4; i < columns.length; i++) {
      if (columns[i].type === 'O' && columns[i-2].type === 'O' && columns[i-4].type === 'O') {
        const l1 = columns[i].startPrice - (columns[i].boxes * 100)
        const l2 = columns[i-2].startPrice - (columns[i-2].boxes * 100)
        const l3 = columns[i-4].startPrice - (columns[i-4].boxes * 100)
        if (l1 > l2 && l2 > l3) {
          detected.push({
            type: 'Ascending Triple Bottom',
            signal: 'bullish',
            strength: 'moderate',
            column: i,
            price: l1
          })
        }
      }
    }

    return detected
  }, [sampleData])

  // Calculate price targets
  const priceTargets = useMemo(() => {
    const targets = []
    const lastColumn = sampleData[sampleData.length - 1]
    const boxSizeValue = 100

    if (lastColumn) {
      // Vertical count method
      const verticalTarget = lastColumn.type === 'X'
        ? lastColumn.startPrice + (lastColumn.boxes * boxSizeValue * selectedReversal)
        : lastColumn.startPrice - (lastColumn.boxes * boxSizeValue * selectedReversal)

      targets.push({
        method: 'Vertical Count',
        target: verticalTarget,
        type: lastColumn.type === 'X' ? 'bullish' : 'bearish'
      })

      // Horizontal count method (simplified)
      const horizontalBoxes = Math.min(sampleData.length, 10)
      const horizontalTarget = lastColumn.type === 'X'
        ? chartMetrics.currentPrice + (horizontalBoxes * boxSizeValue)
        : chartMetrics.currentPrice - (horizontalBoxes * boxSizeValue)

      targets.push({
        method: 'Horizontal Count',
        target: horizontalTarget,
        type: lastColumn.type === 'X' ? 'bullish' : 'bearish'
      })
    }

    return targets
  }, [sampleData, selectedReversal, chartMetrics])

  // Render P&F chart grid
  const renderChart = () => {
    const boxSizeValue = 100
    const rows = Math.ceil(chartMetrics.priceRange / boxSizeValue) + 5
    const priceStart = Math.floor(chartMetrics.lowestPrice / boxSizeValue) * boxSizeValue - (boxSizeValue * 2)

    return (
      <div className="relative overflow-x-auto">
        <div className="flex">
          {/* Price axis */}
          <div className="flex flex-col justify-between text-[10px] text-white/40 pr-2 min-w-[60px]">
            {Array.from({ length: Math.min(rows, 15) }, (_, i) => (
              <div key={i} className="h-4">
                ${((priceStart + (rows - i) * boxSizeValue) / 1000).toFixed(1)}k
              </div>
            ))}
          </div>

          {/* Chart columns */}
          <div className="flex gap-0.5">
            {sampleData.slice(-20).map((column, colIdx) => (
              <div key={colIdx} className="flex flex-col-reverse">
                {Array.from({ length: Math.min(rows, 15) }, (_, rowIdx) => {
                  const rowPrice = priceStart + rowIdx * boxSizeValue
                  const colStart = column.type === 'X' ? column.startPrice : column.startPrice - (column.boxes * boxSizeValue)
                  const colEnd = column.type === 'X' ? column.startPrice + (column.boxes * boxSizeValue) : column.startPrice

                  const isInColumn = rowPrice >= colStart && rowPrice < colEnd
                  const isPattern = patterns.some(p => p.column === colIdx + sampleData.length - 20)

                  return (
                    <div
                      key={rowIdx}
                      className={`w-4 h-4 flex items-center justify-center text-[10px] font-bold rounded-sm ${
                        isInColumn
                          ? column.type === 'X'
                            ? isPattern && showPatterns
                              ? 'bg-emerald-500/40 text-emerald-300'
                              : 'bg-emerald-500/20 text-emerald-400'
                            : isPattern && showPatterns
                              ? 'bg-red-500/40 text-red-300'
                              : 'bg-red-500/20 text-red-400'
                          : 'bg-white/5'
                      }`}
                    >
                      {isInColumn ? column.type : ''}
                    </div>
                  )
                })}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // Auto box size options
  const boxSizeOptions = [
    { label: 'Auto', value: 'auto' },
    { label: '$50', value: 50 },
    { label: '$100', value: 100 },
    { label: '$200', value: 200 },
    { label: '$500', value: 500 },
    { label: '1%', value: 'percent' }
  ]

  return (
    <div className={`bg-[#0a0e14] rounded-lg border border-white/10 ${isExpanded ? 'fixed inset-4 z-50' : ''}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-500/20 rounded-lg">
            <Grid3X3 className="w-4 h-4 text-purple-400" />
          </div>
          <div>
            <h3 className="font-medium text-white">Point & Figure Chart</h3>
            <p className="text-xs text-white/50">{symbol} • Box: ${selectedBoxSize === 'auto' ? 'Auto' : selectedBoxSize} • {selectedReversal}-Box Reversal</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={selectedBoxSize}
            onChange={(e) => setSelectedBoxSize(e.target.value)}
            className="bg-white/5 text-xs text-white rounded px-2 py-1 border border-white/10"
          >
            {boxSizeOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <select
            value={selectedReversal}
            onChange={(e) => setSelectedReversal(Number(e.target.value))}
            className="bg-white/5 text-xs text-white rounded px-2 py-1 border border-white/10"
          >
            <option value={1}>1-Box</option>
            <option value={2}>2-Box</option>
            <option value={3}>3-Box</option>
            <option value={5}>5-Box</option>
          </select>

          <button
            onClick={() => setShowPatterns(!showPatterns)}
            className={`p-1.5 rounded ${showPatterns ? 'bg-purple-500/20 text-purple-400' : 'bg-white/5 text-white/40'}`}
          >
            <Layers className="w-4 h-4" />
          </button>

          <button
            onClick={() => setShowTargets(!showTargets)}
            className={`p-1.5 rounded ${showTargets ? 'bg-blue-500/20 text-blue-400' : 'bg-white/5 text-white/40'}`}
          >
            <Target className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="p-1.5 bg-white/5 rounded hover:bg-white/10"
          >
            <Maximize2 className="w-4 h-4 text-white/60" />
          </button>
        </div>
      </div>

      {/* Chart Stats */}
      <div className="grid grid-cols-6 gap-2 p-3 border-b border-white/10">
        <div className="text-center">
          <div className="text-lg font-bold text-white">{chartMetrics.totalColumns}</div>
          <div className="text-[10px] text-white/40">Columns</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-emerald-400">{chartMetrics.xColumns}</div>
          <div className="text-[10px] text-white/40">X (Up)</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-red-400">{chartMetrics.oColumns}</div>
          <div className="text-[10px] text-white/40">O (Down)</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-white">${(chartMetrics.highestPrice / 1000).toFixed(1)}k</div>
          <div className="text-[10px] text-white/40">Highest</div>
        </div>
        <div className="text-center">
          <div className="text-lg font-bold text-white">${(chartMetrics.lowestPrice / 1000).toFixed(1)}k</div>
          <div className="text-[10px] text-white/40">Lowest</div>
        </div>
        <div className="text-center">
          <div className={`text-lg font-bold ${chartMetrics.trend === 'bullish' ? 'text-emerald-400' : 'text-red-400'}`}>
            {chartMetrics.trend === 'bullish' ? '↑' : '↓'} {chartMetrics.avgBoxesPerColumn}
          </div>
          <div className="text-[10px] text-white/40">Avg Boxes</div>
        </div>
      </div>

      {/* Main Chart */}
      <div className="p-3 border-b border-white/10 min-h-[250px]">
        {renderChart()}
      </div>

      {/* Detected Patterns */}
      {showPatterns && patterns.length > 0 && (
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <Layers className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-white">Detected Patterns</span>
            <span className="text-xs text-white/40">({patterns.length})</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {patterns.slice(0, 4).map((pattern, idx) => (
              <div
                key={idx}
                className={`p-2 rounded-lg ${
                  pattern.signal === 'bullish' ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-red-500/10 border border-red-500/20'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-xs font-medium ${pattern.signal === 'bullish' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {pattern.type}
                  </span>
                  {pattern.signal === 'bullish' ? (
                    <ArrowUpCircle className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <ArrowDownCircle className="w-3 h-3 text-red-400" />
                  )}
                </div>
                <div className="text-[10px] text-white/50 mt-1">
                  Column {pattern.column} • ${(pattern.price / 1000).toFixed(2)}k
                  {pattern.target && ` → Target: $${(pattern.target / 1000).toFixed(2)}k`}
                </div>
                {pattern.strength && (
                  <div className={`text-[10px] mt-1 ${
                    pattern.strength === 'strong' ? 'text-yellow-400' : 'text-white/40'
                  }`}>
                    Strength: {pattern.strength}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Price Targets */}
      {showTargets && (
        <div className="p-3 border-b border-white/10">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-blue-400" />
            <span className="text-sm font-medium text-white">Price Targets</span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {priceTargets.map((target, idx) => (
              <div
                key={idx}
                className={`p-2 rounded-lg ${
                  target.type === 'bullish' ? 'bg-emerald-500/10' : 'bg-red-500/10'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-white/60">{target.method}</span>
                  <Calculator className="w-3 h-3 text-white/40" />
                </div>
                <div className={`text-sm font-bold mt-1 ${
                  target.type === 'bullish' ? 'text-emerald-400' : 'text-red-400'
                }`}>
                  ${(target.target / 1000).toFixed(2)}k
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Chart Method & Settings */}
      <div className="p-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-white/40" />
          <span className="text-xs text-white/40">Method:</span>
          <select
            value={chartMethod}
            onChange={(e) => setChartMethod(e.target.value)}
            className="bg-white/5 text-xs text-white rounded px-2 py-1 border border-white/10"
          >
            <option value="close">Close Only</option>
            <option value="high-low">High-Low</option>
          </select>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-emerald-500/20 rounded flex items-center justify-center text-[8px] text-emerald-400">X</div>
            <span className="text-white/40">Bullish</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-500/20 rounded flex items-center justify-center text-[8px] text-red-400">O</div>
            <span className="text-white/40">Bearish</span>
          </div>
        </div>
      </div>

      {/* Trend Summary */}
      <div className="p-3 border-t border-white/10 bg-white/5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {chartMetrics.trend === 'bullish' ? (
              <TrendingUp className="w-5 h-5 text-emerald-400" />
            ) : (
              <TrendingDown className="w-5 h-5 text-red-400" />
            )}
            <span className={`text-sm font-medium ${
              chartMetrics.trend === 'bullish' ? 'text-emerald-400' : 'text-red-400'
            }`}>
              {chartMetrics.trend === 'bullish' ? 'Bullish' : 'Bearish'} Trend
            </span>
          </div>
          <div className="text-xs text-white/40">
            Last Column: <span className={sampleData[sampleData.length - 1]?.type === 'X' ? 'text-emerald-400' : 'text-red-400'}>
              {sampleData[sampleData.length - 1]?.type === 'X' ? 'Rising X' : 'Falling O'}
            </span> ({sampleData[sampleData.length - 1]?.boxes} boxes)
          </div>
        </div>
      </div>
    </div>
  )
}

export default PointAndFigureChart
