import React, { useState, useMemo, useEffect } from 'react'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Target,
  AlertTriangle,
  ArrowUp,
  ArrowDown,
  Settings,
  BarChart3
} from 'lucide-react'

export function ATRBands() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [timeframe, setTimeframe] = useState('4h')
  const [atrPeriod, setAtrPeriod] = useState(14)
  const [multiplier, setMultiplier] = useState(2)
  const [viewMode, setViewMode] = useState('bands') // bands, levels, volatility
  const [isRefreshing, setIsRefreshing] = useState(false)

  const tokens = ['SOL', 'ETH', 'BTC', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH']
  const timeframes = ['1h', '4h', '1d', '1w']

  // Generate mock ATR data
  const atrData = useMemo(() => {
    const currentPrice = selectedToken === 'BTC' ? 97500 :
                        selectedToken === 'ETH' ? 3350 :
                        selectedToken === 'SOL' ? 182 :
                        Math.random() * 50

    // Calculate ATR (mock)
    const atr = currentPrice * (0.02 + Math.random() * 0.03)
    const atrPercent = (atr / currentPrice) * 100

    // ATR Bands
    const upperBand1 = currentPrice + atr * multiplier
    const upperBand2 = currentPrice + atr * multiplier * 1.5
    const upperBand3 = currentPrice + atr * multiplier * 2
    const lowerBand1 = currentPrice - atr * multiplier
    const lowerBand2 = currentPrice - atr * multiplier * 1.5
    const lowerBand3 = currentPrice - atr * multiplier * 2

    // Volatility assessment
    const avgATR = currentPrice * 0.025
    const volatilityRatio = atr / avgATR
    const volatilityLevel = volatilityRatio > 1.5 ? 'high' :
                           volatilityRatio > 1.0 ? 'normal' : 'low'

    // Historical ATR
    const atrHistory = Array.from({ length: 20 }, (_, i) => ({
      period: i + 1,
      atr: currentPrice * (0.015 + Math.random() * 0.035),
      date: new Date(Date.now() - (19 - i) * 24 * 60 * 60 * 1000)
    }))

    // Calculate ATR expansion/contraction
    const recentATR = atrHistory.slice(-5).reduce((sum, h) => sum + h.atr, 0) / 5
    const olderATR = atrHistory.slice(0, 5).reduce((sum, h) => sum + h.atr, 0) / 5
    const atrTrend = recentATR > olderATR ? 'expanding' : 'contracting'

    // Stop loss and take profit levels based on ATR
    const stopLoss = {
      tight: currentPrice - atr * 1,
      normal: currentPrice - atr * 1.5,
      wide: currentPrice - atr * 2
    }

    const takeProfit = {
      conservative: currentPrice + atr * 1.5,
      normal: currentPrice + atr * 2,
      aggressive: currentPrice + atr * 3
    }

    // Risk/Reward ratios
    const riskReward = {
      tight: (takeProfit.normal - currentPrice) / (currentPrice - stopLoss.tight),
      normal: (takeProfit.normal - currentPrice) / (currentPrice - stopLoss.normal),
      wide: (takeProfit.normal - currentPrice) / (currentPrice - stopLoss.wide)
    }

    // Position sizing based on ATR
    const accountSize = 10000
    const riskPercent = 2
    const riskAmount = accountSize * (riskPercent / 100)
    const positionSize = riskAmount / atr

    // Breakout levels
    const breakoutUp = currentPrice + atr * 1.5
    const breakoutDown = currentPrice - atr * 1.5

    return {
      currentPrice,
      atr,
      atrPercent,
      upperBand1,
      upperBand2,
      upperBand3,
      lowerBand1,
      lowerBand2,
      lowerBand3,
      volatilityLevel,
      volatilityRatio,
      atrHistory,
      atrTrend,
      stopLoss,
      takeProfit,
      riskReward,
      positionSize,
      breakoutUp,
      breakoutDown
    }
  }, [selectedToken, timeframe, atrPeriod, multiplier])

  const handleRefresh = () => {
    setIsRefreshing(true)
    setTimeout(() => setIsRefreshing(false), 1000)
  }

  const formatPrice = (price) => {
    if (price >= 1000) return price.toFixed(0)
    if (price >= 1) return price.toFixed(2)
    return price.toFixed(6)
  }

  const getVolatilityColor = (level) => {
    switch(level) {
      case 'high': return 'text-red-400'
      case 'low': return 'text-green-400'
      default: return 'text-yellow-400'
    }
  }

  const getVolatilityBg = (level) => {
    switch(level) {
      case 'high': return 'bg-red-500/10 border-red-500/20'
      case 'low': return 'bg-green-500/10 border-green-500/20'
      default: return 'bg-yellow-500/10 border-yellow-500/20'
    }
  }

  return (
    <div className="bg-[#0a0e14] rounded-xl border border-white/10 p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Activity className="w-6 h-6 text-orange-400" />
          <h2 className="text-xl font-bold text-white">ATR Bands & Volatility</h2>
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

      {/* ATR Summary */}
      <div className={`rounded-lg p-4 mb-6 border ${getVolatilityBg(atrData.volatilityLevel)}`}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <div className="text-gray-400 text-sm mb-1">ATR ({atrPeriod})</div>
            <div className="text-2xl font-bold text-white">${formatPrice(atrData.atr)}</div>
            <div className="text-gray-500 text-sm">{atrData.atrPercent.toFixed(2)}% of price</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Volatility</div>
            <div className={`text-xl font-bold capitalize ${getVolatilityColor(atrData.volatilityLevel)}`}>
              {atrData.volatilityLevel}
            </div>
            <div className="text-gray-500 text-sm">Ratio: {atrData.volatilityRatio.toFixed(2)}x</div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">ATR Trend</div>
            <div className={`text-lg font-medium capitalize flex items-center gap-2 ${
              atrData.atrTrend === 'expanding' ? 'text-red-400' : 'text-green-400'
            }`}>
              {atrData.atrTrend === 'expanding' ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
              {atrData.atrTrend}
            </div>
          </div>
          <div>
            <div className="text-gray-400 text-sm mb-1">Position Size</div>
            <div className="text-lg font-bold text-white">
              {atrData.positionSize.toFixed(2)} units
            </div>
            <div className="text-gray-500 text-sm">Based on 2% risk</div>
          </div>
        </div>
      </div>

      {/* Settings */}
      <div className="flex items-center gap-4 mb-6 p-3 bg-white/5 rounded-lg border border-white/10">
        <Settings className="w-4 h-4 text-gray-400" />
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm">ATR Period:</span>
          <input
            type="number"
            value={atrPeriod}
            onChange={(e) => setAtrPeriod(parseInt(e.target.value) || 14)}
            className="w-16 bg-white/10 border border-white/10 rounded px-2 py-1 text-white text-sm"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-gray-400 text-sm">Multiplier:</span>
          <input
            type="number"
            step="0.5"
            value={multiplier}
            onChange={(e) => setMultiplier(parseFloat(e.target.value) || 2)}
            className="w-16 bg-white/10 border border-white/10 rounded px-2 py-1 text-white text-sm"
          />
        </div>
      </div>

      {/* View Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: 'bands', label: 'ATR Bands' },
          { id: 'levels', label: 'Trading Levels' },
          { id: 'volatility', label: 'Volatility' }
        ].map(mode => (
          <button
            key={mode.id}
            onClick={() => setViewMode(mode.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              viewMode === mode.id
                ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                : 'bg-white/5 text-gray-400 border border-white/10 hover:bg-white/10'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>

      {/* ATR Bands View */}
      {viewMode === 'bands' && (
        <div className="space-y-4">
          {/* Band Visualization */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">ATR Band Levels</h3>
            <div className="relative h-64">
              {/* Price scale */}
              <div className="absolute left-0 top-0 bottom-0 w-20 flex flex-col justify-between text-right pr-2 text-xs text-gray-500">
                <span>${formatPrice(atrData.upperBand3)}</span>
                <span>${formatPrice(atrData.upperBand2)}</span>
                <span>${formatPrice(atrData.upperBand1)}</span>
                <span className="text-white font-medium">${formatPrice(atrData.currentPrice)}</span>
                <span>${formatPrice(atrData.lowerBand1)}</span>
                <span>${formatPrice(atrData.lowerBand2)}</span>
                <span>${formatPrice(atrData.lowerBand3)}</span>
              </div>

              {/* Bands */}
              <div className="absolute left-24 right-0 top-0 bottom-0">
                {/* Upper bands */}
                <div className="absolute top-0 left-0 right-0 h-[14%] bg-red-500/10 border-b border-red-500/30 flex items-center justify-end pr-2">
                  <span className="text-red-400 text-xs">+3 ATR</span>
                </div>
                <div className="absolute top-[14%] left-0 right-0 h-[14%] bg-red-500/20 border-b border-red-500/40 flex items-center justify-end pr-2">
                  <span className="text-red-400 text-xs">+2 ATR</span>
                </div>
                <div className="absolute top-[28%] left-0 right-0 h-[14%] bg-orange-500/20 border-b border-orange-500/40 flex items-center justify-end pr-2">
                  <span className="text-orange-400 text-xs">+1 ATR</span>
                </div>

                {/* Center */}
                <div className="absolute top-[42%] left-0 right-0 h-[16%] bg-white/10 flex items-center justify-center border-y border-white/30">
                  <span className="text-white font-medium">Current Price</span>
                </div>

                {/* Lower bands */}
                <div className="absolute top-[58%] left-0 right-0 h-[14%] bg-green-500/20 border-b border-green-500/40 flex items-center justify-end pr-2">
                  <span className="text-green-400 text-xs">-1 ATR</span>
                </div>
                <div className="absolute top-[72%] left-0 right-0 h-[14%] bg-green-500/30 border-b border-green-500/50 flex items-center justify-end pr-2">
                  <span className="text-green-400 text-xs">-2 ATR</span>
                </div>
                <div className="absolute top-[86%] left-0 right-0 h-[14%] bg-green-500/10 flex items-center justify-end pr-2">
                  <span className="text-green-400 text-xs">-3 ATR</span>
                </div>
              </div>
            </div>
          </div>

          {/* Band Levels Table */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-red-500/10 rounded-lg p-4 border border-red-500/20">
              <h3 className="text-red-400 font-medium mb-3">Upper Bands (Resistance)</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-400">+1 ATR ({multiplier}x)</span>
                  <span className="text-white">${formatPrice(atrData.upperBand1)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">+1.5 ATR</span>
                  <span className="text-white">${formatPrice(atrData.upperBand2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">+2 ATR</span>
                  <span className="text-white">${formatPrice(atrData.upperBand3)}</span>
                </div>
              </div>
            </div>
            <div className="bg-green-500/10 rounded-lg p-4 border border-green-500/20">
              <h3 className="text-green-400 font-medium mb-3">Lower Bands (Support)</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-400">-1 ATR ({multiplier}x)</span>
                  <span className="text-white">${formatPrice(atrData.lowerBand1)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">-1.5 ATR</span>
                  <span className="text-white">${formatPrice(atrData.lowerBand2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">-2 ATR</span>
                  <span className="text-white">${formatPrice(atrData.lowerBand3)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Trading Levels View */}
      {viewMode === 'levels' && (
        <div className="space-y-4">
          {/* Stop Loss Levels */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-red-400" />
              Stop Loss Levels
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                <div className="text-gray-400 text-sm">Tight (1 ATR)</div>
                <div className="text-red-400 font-bold">${formatPrice(atrData.stopLoss.tight)}</div>
                <div className="text-gray-500 text-xs">R:R {atrData.riskReward.tight.toFixed(2)}</div>
              </div>
              <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                <div className="text-gray-400 text-sm">Normal (1.5 ATR)</div>
                <div className="text-red-400 font-bold">${formatPrice(atrData.stopLoss.normal)}</div>
                <div className="text-gray-500 text-xs">R:R {atrData.riskReward.normal.toFixed(2)}</div>
              </div>
              <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                <div className="text-gray-400 text-sm">Wide (2 ATR)</div>
                <div className="text-red-400 font-bold">${formatPrice(atrData.stopLoss.wide)}</div>
                <div className="text-gray-500 text-xs">R:R {atrData.riskReward.wide.toFixed(2)}</div>
              </div>
            </div>
          </div>

          {/* Take Profit Levels */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-green-400" />
              Take Profit Levels
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                <div className="text-gray-400 text-sm">Conservative (1.5 ATR)</div>
                <div className="text-green-400 font-bold">${formatPrice(atrData.takeProfit.conservative)}</div>
              </div>
              <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                <div className="text-gray-400 text-sm">Normal (2 ATR)</div>
                <div className="text-green-400 font-bold">${formatPrice(atrData.takeProfit.normal)}</div>
              </div>
              <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                <div className="text-gray-400 text-sm">Aggressive (3 ATR)</div>
                <div className="text-green-400 font-bold">${formatPrice(atrData.takeProfit.aggressive)}</div>
              </div>
            </div>
          </div>

          {/* Breakout Levels */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-yellow-400" />
              Breakout Levels (1.5 ATR)
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 bg-green-500/10 rounded-lg border border-green-500/20">
                <div className="text-gray-400 text-sm">Bullish Breakout Above</div>
                <div className="text-green-400 font-bold text-xl">${formatPrice(atrData.breakoutUp)}</div>
              </div>
              <div className="p-3 bg-red-500/10 rounded-lg border border-red-500/20">
                <div className="text-gray-400 text-sm">Bearish Breakout Below</div>
                <div className="text-red-400 font-bold text-xl">${formatPrice(atrData.breakoutDown)}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Volatility View */}
      {viewMode === 'volatility' && (
        <div className="space-y-4">
          {/* ATR History Chart */}
          <div className="bg-white/5 rounded-lg p-4 border border-white/10">
            <h3 className="text-white font-medium mb-4">ATR History</h3>
            <div className="h-48 flex items-end gap-1">
              {atrData.atrHistory.map((point, i) => {
                const maxATR = Math.max(...atrData.atrHistory.map(h => h.atr))
                const height = (point.atr / maxATR) * 100

                return (
                  <div key={i} className="flex-1 group relative">
                    <div
                      className={`w-full rounded-t ${
                        point.atr > atrData.atr * 1.2 ? 'bg-red-500' :
                        point.atr < atrData.atr * 0.8 ? 'bg-green-500' : 'bg-orange-500'
                      }`}
                      style={{ height: `${height}%` }}
                    />
                    <div className="absolute bottom-full mb-2 hidden group-hover:block bg-black/90 p-2 rounded text-xs text-white whitespace-nowrap z-10 left-1/2 -translate-x-1/2">
                      <div>ATR: ${formatPrice(point.atr)}</div>
                      <div className="text-gray-400">{point.date.toLocaleDateString()}</div>
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="flex justify-center gap-4 mt-4 text-xs">
              <span className="flex items-center gap-1"><div className="w-3 h-3 bg-red-500 rounded" /> High Vol</span>
              <span className="flex items-center gap-1"><div className="w-3 h-3 bg-orange-500 rounded" /> Normal</span>
              <span className="flex items-center gap-1"><div className="w-3 h-3 bg-green-500 rounded" /> Low Vol</span>
            </div>
          </div>

          {/* Volatility Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Current ATR</div>
              <div className="text-white font-bold">${formatPrice(atrData.atr)}</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">ATR %</div>
              <div className="text-white font-bold">{atrData.atrPercent.toFixed(2)}%</div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Vol Ratio</div>
              <div className={`font-bold ${getVolatilityColor(atrData.volatilityLevel)}`}>
                {atrData.volatilityRatio.toFixed(2)}x
              </div>
            </div>
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <div className="text-gray-400 text-sm">Trend</div>
              <div className={`font-bold capitalize ${
                atrData.atrTrend === 'expanding' ? 'text-red-400' : 'text-green-400'
              }`}>
                {atrData.atrTrend}
              </div>
            </div>
          </div>

          {/* Volatility Guide */}
          <div className="bg-blue-500/10 rounded-lg p-4 border border-blue-500/20">
            <h3 className="text-blue-400 font-medium mb-2">Volatility Trading Tips</h3>
            <ul className="text-gray-400 text-sm space-y-1 list-disc list-inside">
              <li>High ATR = wider stops needed, more profit potential</li>
              <li>Low ATR = tighter stops, potential breakout setup</li>
              <li>Expanding ATR = trend strengthening</li>
              <li>Contracting ATR = consolidation, prepare for breakout</li>
            </ul>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 pt-4 border-t border-white/10">
        <div className="flex flex-wrap gap-4 text-xs text-gray-500">
          <span>ATR = Average True Range</span>
          <span>Measures market volatility</span>
          <span>Used for stop loss and position sizing</span>
        </div>
      </div>
    </div>
  )
}

export default ATRBands
