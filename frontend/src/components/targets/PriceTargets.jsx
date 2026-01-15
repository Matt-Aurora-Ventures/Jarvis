import React, { useState, useMemo } from 'react'
import {
  Target,
  TrendingUp,
  TrendingDown,
  Calculator,
  DollarSign,
  Percent,
  ArrowUp,
  ArrowDown,
  Shield,
  Zap,
  AlertTriangle,
  ChevronRight,
  Settings,
  RefreshCw,
  BarChart3,
  Layers
} from 'lucide-react'

export function PriceTargets() {
  const [selectedToken, setSelectedToken] = useState('SOL')
  const [viewMode, setViewMode] = useState('calculator') // calculator, scanner, planner

  // Trade input state
  const [entryPrice, setEntryPrice] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [targetPrice, setTargetPrice] = useState('')
  const [positionSize, setPositionSize] = useState('')
  const [accountBalance, setAccountBalance] = useState('10000')
  const [riskPercent, setRiskPercent] = useState('2')
  const [tradeDirection, setTradeDirection] = useState('long')

  const tokens = ['SOL', 'BTC', 'ETH', 'BONK', 'WIF', 'JUP', 'RNDR', 'PYTH', 'JTO', 'ORCA']

  // Current prices for tokens
  const tokenPrices = useMemo(() => ({
    SOL: 148.50,
    BTC: 67500,
    ETH: 2450,
    BONK: 0.000025,
    WIF: 2.85,
    JUP: 0.95,
    RNDR: 8.20,
    PYTH: 0.42,
    JTO: 3.15,
    ORCA: 4.50
  }), [])

  // Calculate trade metrics
  const tradeMetrics = useMemo(() => {
    const entry = parseFloat(entryPrice) || tokenPrices[selectedToken]
    const stop = parseFloat(stopLoss) || (tradeDirection === 'long' ? entry * 0.95 : entry * 1.05)
    const target = parseFloat(targetPrice) || (tradeDirection === 'long' ? entry * 1.10 : entry * 0.90)
    const balance = parseFloat(accountBalance) || 10000
    const riskPct = parseFloat(riskPercent) || 2

    const riskAmount = balance * (riskPct / 100)
    const stopDistance = Math.abs(entry - stop)
    const targetDistance = Math.abs(target - entry)
    const stopPercent = (stopDistance / entry) * 100
    const targetPercent = (targetDistance / entry) * 100

    const riskReward = targetDistance / stopDistance
    const optimalPosition = riskAmount / stopDistance
    const positionValue = optimalPosition * entry
    const potentialProfit = optimalPosition * targetDistance
    const potentialLoss = riskAmount

    // Multiple targets
    const tp1 = tradeDirection === 'long' ? entry * 1.03 : entry * 0.97
    const tp2 = tradeDirection === 'long' ? entry * 1.06 : entry * 0.94
    const tp3 = tradeDirection === 'long' ? entry * 1.10 : entry * 0.90

    return {
      entry,
      stop,
      target,
      stopDistance,
      targetDistance,
      stopPercent,
      targetPercent,
      riskReward,
      riskAmount,
      optimalPosition,
      positionValue,
      potentialProfit,
      potentialLoss,
      tp1,
      tp2,
      tp3
    }
  }, [entryPrice, stopLoss, targetPrice, accountBalance, riskPercent, selectedToken, tokenPrices, tradeDirection])

  // Token opportunities scanner
  const opportunities = useMemo(() => {
    return tokens.map(token => {
      const price = tokenPrices[token]
      const atr = price * (0.02 + Math.random() * 0.03)
      const support = price * (0.92 + Math.random() * 0.05)
      const resistance = price * (1.03 + Math.random() * 0.07)

      const longRR = (resistance - price) / (price - support)
      const shortRR = (price - support) / (resistance - price)

      const bestSetup = longRR > shortRR ? 'long' : 'short'
      const bestRR = Math.max(longRR, shortRR)

      const nearSupport = (price - support) / price < 0.03
      const nearResistance = (resistance - price) / price < 0.03

      return {
        token,
        price,
        support,
        resistance,
        atr,
        longRR,
        shortRR,
        bestSetup,
        bestRR,
        nearSupport,
        nearResistance,
        quality: bestRR > 3 ? 'A' : bestRR > 2 ? 'B' : 'C'
      }
    }).sort((a, b) => b.bestRR - a.bestRR)
  }, [tokens, tokenPrices])

  const getRRColor = (rr) => {
    if (rr >= 3) return 'text-green-400'
    if (rr >= 2) return 'text-yellow-400'
    if (rr >= 1) return 'text-orange-400'
    return 'text-red-400'
  }

  const getRRBg = (rr) => {
    if (rr >= 3) return 'bg-green-500/10'
    if (rr >= 2) return 'bg-yellow-500/10'
    if (rr >= 1) return 'bg-orange-500/10'
    return 'bg-red-500/10'
  }

  return (
    <div className="p-6 bg-[#0a0e14] text-white min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-lg">
            <Target className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold">Price Targets Calculator</h1>
            <p className="text-white/60 text-sm">Plan trades with R:R ratios and position sizing</p>
          </div>
        </div>

        <div className="flex bg-white/5 rounded-lg p-1">
          {['calculator', 'scanner', 'planner'].map(mode => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-1.5 text-sm rounded-md transition-all ${
                viewMode === mode ? 'bg-green-500 text-white' : 'text-white/60 hover:text-white'
              }`}
            >
              {mode.charAt(0).toUpperCase() + mode.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {viewMode === 'calculator' && (
        <div className="grid grid-cols-3 gap-6">
          {/* Trade Input */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Calculator className="w-5 h-5 text-green-400" />
              Trade Setup
            </h2>

            {/* Token Selector */}
            <div className="mb-4">
              <label className="text-white/60 text-sm block mb-2">Token</label>
              <select
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2"
              >
                {tokens.map(token => (
                  <option key={token} value={token}>
                    {token} - ${tokenPrices[token]}
                  </option>
                ))}
              </select>
            </div>

            {/* Direction Toggle */}
            <div className="mb-4">
              <label className="text-white/60 text-sm block mb-2">Direction</label>
              <div className="flex gap-2">
                <button
                  onClick={() => setTradeDirection('long')}
                  className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-2 ${
                    tradeDirection === 'long'
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-white/5 text-white/60'
                  }`}
                >
                  <ArrowUp className="w-4 h-4" />
                  Long
                </button>
                <button
                  onClick={() => setTradeDirection('short')}
                  className={`flex-1 py-2 rounded-lg flex items-center justify-center gap-2 ${
                    tradeDirection === 'short'
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                      : 'bg-white/5 text-white/60'
                  }`}
                >
                  <ArrowDown className="w-4 h-4" />
                  Short
                </button>
              </div>
            </div>

            {/* Price Inputs */}
            <div className="space-y-3">
              <div>
                <label className="text-white/60 text-sm block mb-1">Entry Price</label>
                <input
                  type="number"
                  value={entryPrice}
                  onChange={(e) => setEntryPrice(e.target.value)}
                  placeholder={tokenPrices[selectedToken].toString()}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2"
                />
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Stop Loss</label>
                <input
                  type="number"
                  value={stopLoss}
                  onChange={(e) => setStopLoss(e.target.value)}
                  placeholder={(tradeDirection === 'long' ? tokenPrices[selectedToken] * 0.95 : tokenPrices[selectedToken] * 1.05).toFixed(2)}
                  className="w-full bg-white/5 border border-red-500/30 rounded-lg px-3 py-2 text-red-400"
                />
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Target Price</label>
                <input
                  type="number"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                  placeholder={(tradeDirection === 'long' ? tokenPrices[selectedToken] * 1.10 : tokenPrices[selectedToken] * 0.90).toFixed(2)}
                  className="w-full bg-white/5 border border-green-500/30 rounded-lg px-3 py-2 text-green-400"
                />
              </div>
            </div>

            {/* Account Settings */}
            <div className="mt-4 pt-4 border-t border-white/10 space-y-3">
              <div>
                <label className="text-white/60 text-sm block mb-1">Account Balance ($)</label>
                <input
                  type="number"
                  value={accountBalance}
                  onChange={(e) => setAccountBalance(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2"
                />
              </div>

              <div>
                <label className="text-white/60 text-sm block mb-1">Risk per Trade (%)</label>
                <input
                  type="number"
                  value={riskPercent}
                  onChange={(e) => setRiskPercent(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2"
                />
              </div>
            </div>
          </div>

          {/* Trade Metrics */}
          <div className="space-y-4">
            {/* Risk:Reward */}
            <div className={`border rounded-xl p-4 ${getRRBg(tradeMetrics.riskReward)}`}>
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Percent className="w-5 h-5 text-yellow-400" />
                Risk : Reward
              </h3>

              <div className="text-center">
                <p className={`text-4xl font-bold ${getRRColor(tradeMetrics.riskReward)}`}>
                  1 : {tradeMetrics.riskReward.toFixed(2)}
                </p>
                <p className="text-white/60 text-sm mt-2">
                  {tradeMetrics.riskReward >= 3 ? 'Excellent setup' :
                   tradeMetrics.riskReward >= 2 ? 'Good setup' :
                   tradeMetrics.riskReward >= 1 ? 'Marginal setup' : 'Poor setup'}
                </p>
              </div>

              {/* Visual Bar */}
              <div className="mt-4 flex items-center gap-2">
                <div className="flex-1">
                  <div className="h-3 bg-red-500/30 rounded-l-full" />
                  <p className="text-xs text-red-400 mt-1">Risk: {tradeMetrics.stopPercent.toFixed(2)}%</p>
                </div>
                <div style={{ flex: tradeMetrics.riskReward }}>
                  <div className="h-3 bg-green-500/30 rounded-r-full" />
                  <p className="text-xs text-green-400 mt-1">Reward: {tradeMetrics.targetPercent.toFixed(2)}%</p>
                </div>
              </div>
            </div>

            {/* Position Sizing */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Shield className="w-5 h-5 text-blue-400" />
                Position Sizing
              </h3>

              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-white/60">Risk Amount</span>
                  <span className="text-red-400 font-medium">${tradeMetrics.riskAmount.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Optimal Size</span>
                  <span className="font-medium">{tradeMetrics.optimalPosition.toFixed(4)} {selectedToken}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-white/60">Position Value</span>
                  <span className="font-medium">${tradeMetrics.positionValue.toFixed(2)}</span>
                </div>
                <div className="flex justify-between pt-2 border-t border-white/10">
                  <span className="text-white/60">Leverage Needed</span>
                  <span className="font-medium">
                    {(tradeMetrics.positionValue / parseFloat(accountBalance) || 1).toFixed(2)}x
                  </span>
                </div>
              </div>
            </div>

            {/* P&L Preview */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-green-400" />
                P&L Preview
              </h3>

              <div className="space-y-2">
                <div className="flex justify-between items-center p-2 bg-green-500/10 rounded-lg">
                  <span className="text-green-400">If Target Hit</span>
                  <span className="text-green-400 font-bold">+${tradeMetrics.potentialProfit.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-red-500/10 rounded-lg">
                  <span className="text-red-400">If Stop Hit</span>
                  <span className="text-red-400 font-bold">-${tradeMetrics.potentialLoss.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Price Levels Visualization */}
          <div className="space-y-4">
            {/* Visual Chart */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                Price Levels
              </h3>

              <div className="relative h-64 border border-white/10 rounded-lg bg-white/[0.02]">
                {/* Target */}
                <div
                  className="absolute left-0 right-0 border-t-2 border-green-500"
                  style={{ top: '15%' }}
                >
                  <div className="flex justify-between px-2 -translate-y-3">
                    <span className="text-xs text-green-400">Target</span>
                    <span className="text-xs text-green-400">${tradeMetrics.target.toFixed(2)}</span>
                  </div>
                </div>

                {/* TP3 */}
                <div
                  className="absolute left-0 right-0 border-t border-dashed border-green-500/50"
                  style={{ top: '25%' }}
                >
                  <span className="absolute right-2 -top-3 text-xs text-green-400/60">TP3</span>
                </div>

                {/* TP2 */}
                <div
                  className="absolute left-0 right-0 border-t border-dashed border-green-500/50"
                  style={{ top: '35%' }}
                >
                  <span className="absolute right-2 -top-3 text-xs text-green-400/60">TP2</span>
                </div>

                {/* TP1 */}
                <div
                  className="absolute left-0 right-0 border-t border-dashed border-green-500/50"
                  style={{ top: '45%' }}
                >
                  <span className="absolute right-2 -top-3 text-xs text-green-400/60">TP1</span>
                </div>

                {/* Entry */}
                <div
                  className="absolute left-0 right-0 border-t-2 border-white"
                  style={{ top: '55%' }}
                >
                  <div className="flex justify-between px-2 -translate-y-3">
                    <span className="text-xs text-white">Entry</span>
                    <span className="text-xs text-white">${tradeMetrics.entry.toFixed(2)}</span>
                  </div>
                </div>

                {/* Stop Loss */}
                <div
                  className="absolute left-0 right-0 border-t-2 border-red-500"
                  style={{ top: '85%' }}
                >
                  <div className="flex justify-between px-2 -translate-y-3">
                    <span className="text-xs text-red-400">Stop Loss</span>
                    <span className="text-xs text-red-400">${tradeMetrics.stop.toFixed(2)}</span>
                  </div>
                </div>

                {/* Direction Arrow */}
                <div className="absolute inset-0 flex items-center justify-center">
                  {tradeDirection === 'long' ? (
                    <ArrowUp className="w-16 h-16 text-green-500/20" />
                  ) : (
                    <ArrowDown className="w-16 h-16 text-red-500/20" />
                  )}
                </div>
              </div>
            </div>

            {/* Multiple TPs */}
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h3 className="font-semibold mb-3 flex items-center gap-2">
                <Layers className="w-5 h-5 text-cyan-400" />
                Scaled Targets
              </h3>

              <div className="space-y-2">
                <div className="flex justify-between items-center p-2 bg-green-500/5 rounded">
                  <span className="text-white/60">TP1 (3%)</span>
                  <span className="text-green-400">${tradeMetrics.tp1.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-green-500/10 rounded">
                  <span className="text-white/60">TP2 (6%)</span>
                  <span className="text-green-400">${tradeMetrics.tp2.toFixed(2)}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-green-500/20 rounded">
                  <span className="text-white/60">TP3 (10%)</span>
                  <span className="text-green-400 font-medium">${tradeMetrics.tp3.toFixed(2)}</span>
                </div>
              </div>

              <p className="text-white/40 text-xs mt-3">
                Consider scaling out at each target level
              </p>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'scanner' && (
        <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-white/10">
            <h2 className="font-semibold flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              Best R:R Opportunities
            </h2>
          </div>

          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left py-3 px-4 text-white/60 text-sm font-medium">Token</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Price</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Support</th>
                <th className="text-right py-3 px-4 text-white/60 text-sm font-medium">Resistance</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Best Setup</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">R:R</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Grade</th>
                <th className="text-center py-3 px-4 text-white/60 text-sm font-medium">Notes</th>
              </tr>
            </thead>
            <tbody>
              {opportunities.map((opp, idx) => (
                <tr
                  key={opp.token}
                  className={`border-b border-white/5 hover:bg-white/5 cursor-pointer ${
                    idx % 2 === 0 ? 'bg-white/[0.02]' : ''
                  }`}
                  onClick={() => {
                    setSelectedToken(opp.token)
                    setViewMode('calculator')
                  }}
                >
                  <td className="py-3 px-4 font-medium">{opp.token}</td>
                  <td className="py-3 px-4 text-right">${opp.price.toFixed(2)}</td>
                  <td className="py-3 px-4 text-right text-green-400">${opp.support.toFixed(2)}</td>
                  <td className="py-3 px-4 text-right text-red-400">${opp.resistance.toFixed(2)}</td>
                  <td className="py-3 px-4 text-center">
                    <span className={`px-2 py-1 rounded text-xs ${
                      opp.bestSetup === 'long'
                        ? 'bg-green-500/10 text-green-400'
                        : 'bg-red-500/10 text-red-400'
                    }`}>
                      {opp.bestSetup.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`font-bold ${getRRColor(opp.bestRR)}`}>
                      {opp.bestRR.toFixed(2)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      opp.quality === 'A' ? 'bg-green-500/20 text-green-400' :
                      opp.quality === 'B' ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-white/10 text-white/60'
                    }`}>
                      {opp.quality}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-center">
                    <div className="flex justify-center gap-1">
                      {opp.nearSupport && (
                        <span className="px-1.5 py-0.5 rounded text-xs bg-green-500/10 text-green-400">
                          Near Support
                        </span>
                      )}
                      {opp.nearResistance && (
                        <span className="px-1.5 py-0.5 rounded text-xs bg-red-500/10 text-red-400">
                          Near Resist
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {viewMode === 'planner' && (
        <div className="grid grid-cols-2 gap-6">
          {/* Trade Plan Template */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <h2 className="font-semibold mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-green-400" />
              Trade Plan Template
            </h2>

            <div className="space-y-4">
              <div className="p-4 bg-white/5 rounded-lg">
                <h3 className="text-sm font-medium text-white/60 mb-2">1. Setup Identification</h3>
                <textarea
                  className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm"
                  rows={2}
                  placeholder="What pattern/signal am I trading?"
                />
              </div>

              <div className="p-4 bg-white/5 rounded-lg">
                <h3 className="text-sm font-medium text-white/60 mb-2">2. Entry Trigger</h3>
                <textarea
                  className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm"
                  rows={2}
                  placeholder="What price action confirms entry?"
                />
              </div>

              <div className="p-4 bg-white/5 rounded-lg">
                <h3 className="text-sm font-medium text-white/60 mb-2">3. Risk Management</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <label className="text-white/40 text-xs">Stop Loss</label>
                    <input
                      type="text"
                      className="w-full bg-white/5 border border-white/10 rounded p-2"
                      placeholder="$..."
                    />
                  </div>
                  <div>
                    <label className="text-white/40 text-xs">Position Size</label>
                    <input
                      type="text"
                      className="w-full bg-white/5 border border-white/10 rounded p-2"
                      placeholder="..."
                    />
                  </div>
                </div>
              </div>

              <div className="p-4 bg-white/5 rounded-lg">
                <h3 className="text-sm font-medium text-white/60 mb-2">4. Profit Targets</h3>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div>
                    <label className="text-white/40 text-xs">TP1 (33%)</label>
                    <input
                      type="text"
                      className="w-full bg-white/5 border border-white/10 rounded p-2"
                    />
                  </div>
                  <div>
                    <label className="text-white/40 text-xs">TP2 (33%)</label>
                    <input
                      type="text"
                      className="w-full bg-white/5 border border-white/10 rounded p-2"
                    />
                  </div>
                  <div>
                    <label className="text-white/40 text-xs">TP3 (34%)</label>
                    <input
                      type="text"
                      className="w-full bg-white/5 border border-white/10 rounded p-2"
                    />
                  </div>
                </div>
              </div>

              <div className="p-4 bg-white/5 rounded-lg">
                <h3 className="text-sm font-medium text-white/60 mb-2">5. Invalidation</h3>
                <textarea
                  className="w-full bg-white/5 border border-white/10 rounded p-2 text-sm"
                  rows={2}
                  placeholder="When is the trade idea invalid?"
                />
              </div>
            </div>
          </div>

          {/* Trade Checklist */}
          <div className="space-y-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h2 className="font-semibold mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-yellow-400" />
                Pre-Trade Checklist
              </h2>

              <div className="space-y-2">
                {[
                  'Clear entry trigger identified',
                  'Stop loss defined (max 2% account risk)',
                  'R:R ratio minimum 2:1',
                  'Position size calculated',
                  'Multiple timeframe alignment',
                  'Key news/events checked',
                  'Not revenge trading',
                  'Emotionally neutral'
                ].map((item, idx) => (
                  <label
                    key={idx}
                    className="flex items-center gap-3 p-2 bg-white/5 rounded-lg cursor-pointer hover:bg-white/10"
                  >
                    <input type="checkbox" className="rounded" />
                    <span className="text-sm">{item}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <h2 className="font-semibold mb-4 flex items-center gap-2">
                <ChevronRight className="w-5 h-5 text-cyan-400" />
                Quick Rules
              </h2>

              <div className="space-y-2 text-sm text-white/60">
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Never risk more than 2% per trade</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Minimum 2:1 R:R for all trades</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Scale out at predetermined levels</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>Move stop to breakeven after TP1</span>
                </p>
                <p className="flex items-start gap-2">
                  <ChevronRight className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                  <span>No trading after 3 consecutive losses</span>
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default PriceTargets
