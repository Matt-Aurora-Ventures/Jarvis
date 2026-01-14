import React, { useState, useMemo, useEffect } from 'react'
import {
  Calculator, DollarSign, Percent, TrendingUp, TrendingDown, Shield,
  Target, AlertTriangle, Info, BarChart2, PieChart, Settings, RefreshCw,
  ChevronDown, Zap, Activity, Scale, Sliders, ArrowRight
} from 'lucide-react'

const SIZING_METHODS = [
  { value: 'fixed_risk', label: 'Fixed Risk %', description: 'Risk a fixed percentage of portfolio per trade' },
  { value: 'kelly', label: 'Kelly Criterion', description: 'Optimal sizing based on win rate and R:R' },
  { value: 'fixed_fractional', label: 'Fixed Fractional', description: 'Fixed portion of portfolio per trade' },
  { value: 'volatility', label: 'Volatility Adjusted', description: 'Size based on asset volatility (ATR)' },
  { value: 'equal_weight', label: 'Equal Weight', description: 'Divide capital equally across positions' }
]

const SUPPORTED_TOKENS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 67500, volatility: 3.2 },
  { symbol: 'ETH', name: 'Ethereum', price: 3450, volatility: 4.1 },
  { symbol: 'SOL', name: 'Solana', price: 145, volatility: 6.8 },
  { symbol: 'BNB', name: 'BNB Chain', price: 580, volatility: 3.5 },
  { symbol: 'XRP', name: 'Ripple', price: 0.52, volatility: 4.9 },
  { symbol: 'ADA', name: 'Cardano', price: 0.45, volatility: 5.2 },
  { symbol: 'AVAX', name: 'Avalanche', price: 35, volatility: 5.8 },
  { symbol: 'DOT', name: 'Polkadot', price: 7.2, volatility: 4.7 },
  { symbol: 'MATIC', name: 'Polygon', price: 0.72, volatility: 5.4 },
  { symbol: 'LINK', name: 'Chainlink', price: 14.5, volatility: 4.3 },
  { symbol: 'UNI', name: 'Uniswap', price: 9.8, volatility: 5.1 },
  { symbol: 'AAVE', name: 'Aave', price: 168, volatility: 4.6 }
]

const RISK_PROFILES = [
  { value: 'conservative', label: 'Conservative', maxRisk: 1, maxPosition: 5, description: '1% risk, 5% max position' },
  { value: 'moderate', label: 'Moderate', maxRisk: 2, maxPosition: 10, description: '2% risk, 10% max position' },
  { value: 'aggressive', label: 'Aggressive', maxRisk: 5, maxPosition: 20, description: '5% risk, 20% max position' },
  { value: 'custom', label: 'Custom', maxRisk: 0, maxPosition: 0, description: 'Set your own limits' }
]

export function PositionSizer() {
  const [portfolioValue, setPortfolioValue] = useState(100000)
  const [method, setMethod] = useState('fixed_risk')
  const [riskProfile, setRiskProfile] = useState('moderate')
  const [selectedToken, setSelectedToken] = useState('BTC')

  // Trade parameters
  const [entryPrice, setEntryPrice] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')
  const [riskPercent, setRiskPercent] = useState(2)
  const [winRate, setWinRate] = useState(55)
  const [avgWin, setAvgWin] = useState(2)
  const [avgLoss, setAvgLoss] = useState(1)
  const [numPositions, setNumPositions] = useState(5)
  const [targetVolatility, setTargetVolatility] = useState(15)

  // Calculated positions history
  const [positionHistory, setPositionHistory] = useState([])

  // Get current token data
  const tokenData = useMemo(() => {
    return SUPPORTED_TOKENS.find(t => t.symbol === selectedToken) || SUPPORTED_TOKENS[0]
  }, [selectedToken])

  // Auto-fill entry price
  useEffect(() => {
    setEntryPrice(tokenData.price.toString())
  }, [tokenData])

  // Calculate position size
  const calculation = useMemo(() => {
    const entry = parseFloat(entryPrice) || tokenData.price
    const stop = parseFloat(stopLoss) || 0
    const target = parseFloat(takeProfit) || 0

    let positionSize = 0
    let positionValue = 0
    let riskAmount = 0
    let rewardAmount = 0
    let riskRewardRatio = 0
    let stopPercent = 0
    let profitPercent = 0
    let kellyPercent = 0
    let numberOfUnits = 0

    // Get risk profile settings
    const profile = RISK_PROFILES.find(p => p.value === riskProfile) || RISK_PROFILES[1]
    const maxRiskPct = riskProfile === 'custom' ? riskPercent : profile.maxRisk
    const maxPositionPct = riskProfile === 'custom' ? 100 : profile.maxPosition

    if (method === 'fixed_risk' && stop > 0) {
      // Fixed Risk %: Position size based on risk amount and stop distance
      stopPercent = Math.abs((entry - stop) / entry) * 100
      riskAmount = portfolioValue * (maxRiskPct / 100)
      const riskPerUnit = Math.abs(entry - stop)
      numberOfUnits = riskAmount / riskPerUnit
      positionValue = numberOfUnits * entry
      positionSize = (positionValue / portfolioValue) * 100

      if (target > 0) {
        profitPercent = Math.abs((target - entry) / entry) * 100
        rewardAmount = numberOfUnits * Math.abs(target - entry)
        riskRewardRatio = rewardAmount / riskAmount
      }
    } else if (method === 'kelly') {
      // Kelly Criterion: f* = (p*b - q) / b
      // where p = win rate, q = 1-p, b = avg win/avg loss ratio
      const p = winRate / 100
      const q = 1 - p
      const b = avgWin / avgLoss
      kellyPercent = ((p * b - q) / b) * 100
      kellyPercent = Math.max(0, Math.min(kellyPercent, 100)) // Clamp 0-100

      // Use half Kelly for safety
      const halfKelly = kellyPercent / 2
      positionSize = Math.min(halfKelly, maxPositionPct)
      positionValue = portfolioValue * (positionSize / 100)
      numberOfUnits = positionValue / entry
      riskAmount = portfolioValue * (maxRiskPct / 100)
    } else if (method === 'fixed_fractional') {
      // Fixed Fractional: Simply allocate fixed % to position
      positionSize = Math.min(maxPositionPct, 10) // Default 10% or max
      positionValue = portfolioValue * (positionSize / 100)
      numberOfUnits = positionValue / entry

      if (stop > 0) {
        riskAmount = numberOfUnits * Math.abs(entry - stop)
      }
    } else if (method === 'volatility') {
      // Volatility Adjusted: Size inversely proportional to volatility
      const assetVol = tokenData.volatility
      const volMultiplier = targetVolatility / assetVol
      positionSize = Math.min(10 * volMultiplier, maxPositionPct)
      positionValue = portfolioValue * (positionSize / 100)
      numberOfUnits = positionValue / entry

      if (stop > 0) {
        riskAmount = numberOfUnits * Math.abs(entry - stop)
      }
    } else if (method === 'equal_weight') {
      // Equal Weight: Divide portfolio equally
      positionSize = 100 / numPositions
      positionSize = Math.min(positionSize, maxPositionPct)
      positionValue = portfolioValue * (positionSize / 100)
      numberOfUnits = positionValue / entry

      if (stop > 0) {
        riskAmount = numberOfUnits * Math.abs(entry - stop)
      }
    }

    // Apply max position constraint
    if (positionSize > maxPositionPct) {
      positionSize = maxPositionPct
      positionValue = portfolioValue * (positionSize / 100)
      numberOfUnits = positionValue / entry
    }

    return {
      positionSize,
      positionValue,
      riskAmount,
      rewardAmount,
      riskRewardRatio,
      stopPercent,
      profitPercent,
      kellyPercent,
      numberOfUnits,
      maxRiskPct,
      maxPositionPct
    }
  }, [portfolioValue, method, riskProfile, riskPercent, entryPrice, stopLoss, takeProfit,
      winRate, avgWin, avgLoss, numPositions, targetVolatility, tokenData])

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value)
  }

  const formatNumber = (value, decimals = 4) => {
    if (value < 0.0001) return value.toFixed(8)
    if (value < 1) return value.toFixed(decimals)
    if (value < 1000) return value.toFixed(2)
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  }

  const saveToHistory = () => {
    const newPosition = {
      id: Date.now(),
      token: selectedToken,
      method,
      entry: parseFloat(entryPrice),
      stop: parseFloat(stopLoss),
      target: parseFloat(takeProfit),
      size: calculation.positionSize,
      value: calculation.positionValue,
      risk: calculation.riskAmount,
      rr: calculation.riskRewardRatio,
      date: new Date()
    }
    setPositionHistory(prev => [newPosition, ...prev].slice(0, 10))
  }

  const getRiskColor = (riskPct) => {
    if (riskPct <= 1) return 'text-green-400'
    if (riskPct <= 2) return 'text-yellow-400'
    if (riskPct <= 5) return 'text-orange-400'
    return 'text-red-400'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calculator className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold">Position Sizing Calculator</h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={saveToHistory}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition flex items-center gap-2"
          >
            <Target className="w-4 h-4" />
            Save Position
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Input Parameters */}
        <div className="lg:col-span-2 space-y-6">
          {/* Portfolio & Method */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Configuration
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Portfolio Value */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Portfolio Value</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="number"
                    value={portfolioValue}
                    onChange={(e) => setPortfolioValue(parseFloat(e.target.value) || 0)}
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>

              {/* Risk Profile */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Risk Profile</label>
                <select
                  value={riskProfile}
                  onChange={(e) => setRiskProfile(e.target.value)}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                >
                  {RISK_PROFILES.map(profile => (
                    <option key={profile.value} value={profile.value} className="bg-[#0a0e14]">
                      {profile.label} - {profile.description}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Sizing Method */}
            <div className="mt-4">
              <label className="block text-sm text-white/60 mb-2">Sizing Method</label>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
                {SIZING_METHODS.map(m => (
                  <button
                    key={m.value}
                    onClick={() => setMethod(m.value)}
                    className={`p-3 rounded-lg text-left transition ${
                      method === m.value
                        ? 'bg-blue-500/20 border border-blue-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    <div className="font-medium text-sm">{m.label}</div>
                  </button>
                ))}
              </div>
              <div className="mt-2 text-sm text-white/40">
                {SIZING_METHODS.find(m => m.value === method)?.description}
              </div>
            </div>
          </div>

          {/* Trade Parameters */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Sliders className="w-5 h-5" />
              Trade Parameters
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Token Selection */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Token</label>
                <select
                  value={selectedToken}
                  onChange={(e) => setSelectedToken(e.target.value)}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                >
                  {SUPPORTED_TOKENS.map(token => (
                    <option key={token.symbol} value={token.symbol} className="bg-[#0a0e14]">
                      {token.symbol} - {token.name} (${formatNumber(token.price)})
                    </option>
                  ))}
                </select>
              </div>

              {/* Entry Price */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Entry Price</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="number"
                    value={entryPrice}
                    onChange={(e) => setEntryPrice(e.target.value)}
                    placeholder={tokenData.price.toString()}
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>

              {/* Stop Loss */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Stop Loss Price</label>
                <div className="relative">
                  <Shield className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-red-400" />
                  <input
                    type="number"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(e.target.value)}
                    placeholder="Enter stop loss"
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
                {calculation.stopPercent > 0 && (
                  <div className="text-xs text-red-400 mt-1">
                    -{calculation.stopPercent.toFixed(2)}% from entry
                  </div>
                )}
              </div>

              {/* Take Profit */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Take Profit Price</label>
                <div className="relative">
                  <Target className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-400" />
                  <input
                    type="number"
                    value={takeProfit}
                    onChange={(e) => setTakeProfit(e.target.value)}
                    placeholder="Enter take profit"
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
                {calculation.profitPercent > 0 && (
                  <div className="text-xs text-green-400 mt-1">
                    +{calculation.profitPercent.toFixed(2)}% from entry
                  </div>
                )}
              </div>
            </div>

            {/* Method-specific inputs */}
            {method === 'kelly' && (
              <div className="mt-4 p-4 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                <div className="text-sm font-medium text-purple-400 mb-3">Kelly Criterion Parameters</div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-white/60 mb-1">Win Rate %</label>
                    <input
                      type="number"
                      value={winRate}
                      onChange={(e) => setWinRate(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-white/60 mb-1">Avg Win (R)</label>
                    <input
                      type="number"
                      value={avgWin}
                      onChange={(e) => setAvgWin(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-white/60 mb-1">Avg Loss (R)</label>
                    <input
                      type="number"
                      value={avgLoss}
                      onChange={(e) => setAvgLoss(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                    />
                  </div>
                </div>
                <div className="mt-2 text-xs text-white/40">
                  Full Kelly: {calculation.kellyPercent.toFixed(1)}% | Half Kelly (recommended): {(calculation.kellyPercent / 2).toFixed(1)}%
                </div>
              </div>
            )}

            {method === 'volatility' && (
              <div className="mt-4 p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                <div className="text-sm font-medium text-yellow-400 mb-3">Volatility Parameters</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-white/60 mb-1">Target Portfolio Volatility %</label>
                    <input
                      type="number"
                      value={targetVolatility}
                      onChange={(e) => setTargetVolatility(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-white/60 mb-1">Asset Volatility (Daily %)</label>
                    <div className="px-3 py-2 bg-white/5 border border-white/10 rounded-lg text-sm">
                      {tokenData.volatility}%
                    </div>
                  </div>
                </div>
              </div>
            )}

            {method === 'equal_weight' && (
              <div className="mt-4 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                <div className="text-sm font-medium text-blue-400 mb-3">Equal Weight Parameters</div>
                <div>
                  <label className="block text-xs text-white/60 mb-1">Number of Positions</label>
                  <input
                    type="number"
                    value={numPositions}
                    onChange={(e) => setNumPositions(parseInt(e.target.value) || 1)}
                    min="1"
                    max="100"
                    className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                  />
                </div>
              </div>
            )}

            {riskProfile === 'custom' && (
              <div className="mt-4 p-4 bg-white/5 border border-white/10 rounded-lg">
                <div className="text-sm font-medium mb-3">Custom Risk Settings</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs text-white/60 mb-1">Max Risk Per Trade %</label>
                    <input
                      type="number"
                      value={riskPercent}
                      onChange={(e) => setRiskPercent(parseFloat(e.target.value) || 0)}
                      className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Results */}
        <div className="space-y-6">
          {/* Position Size Result */}
          <div className="bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Calculated Position</h3>

            <div className="space-y-4">
              <div className="text-center py-4">
                <div className="text-4xl font-bold text-blue-400">
                  {formatNumber(calculation.numberOfUnits)}
                </div>
                <div className="text-white/60">{selectedToken} units</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="text-xs text-white/40">Position Size</div>
                  <div className="text-lg font-bold">{calculation.positionSize.toFixed(2)}%</div>
                </div>
                <div className="bg-white/5 rounded-lg p-3 text-center">
                  <div className="text-xs text-white/40">Position Value</div>
                  <div className="text-lg font-bold">{formatCurrency(calculation.positionValue)}</div>
                </div>
              </div>
            </div>
          </div>

          {/* Risk Analysis */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Shield className="w-5 h-5" />
              Risk Analysis
            </h3>

            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-white/60">Risk Amount</span>
                <span className={`font-medium ${getRiskColor((calculation.riskAmount / portfolioValue) * 100)}`}>
                  {formatCurrency(calculation.riskAmount)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/60">Risk % of Portfolio</span>
                <span className={`font-medium ${getRiskColor((calculation.riskAmount / portfolioValue) * 100)}`}>
                  {((calculation.riskAmount / portfolioValue) * 100).toFixed(2)}%
                </span>
              </div>
              {calculation.riskRewardRatio > 0 && (
                <div className="flex justify-between items-center">
                  <span className="text-white/60">Reward Amount</span>
                  <span className="font-medium text-green-400">{formatCurrency(calculation.rewardAmount)}</span>
                </div>
              )}
              {calculation.riskRewardRatio > 0 && (
                <div className="flex justify-between items-center">
                  <span className="text-white/60">Risk:Reward Ratio</span>
                  <span className={`font-medium ${calculation.riskRewardRatio >= 2 ? 'text-green-400' : calculation.riskRewardRatio >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                    1:{calculation.riskRewardRatio.toFixed(2)}
                  </span>
                </div>
              )}
              <div className="flex justify-between items-center">
                <span className="text-white/60">Max Position Limit</span>
                <span className="text-white/40">{calculation.maxPositionPct}%</span>
              </div>
            </div>

            {/* Risk Gauge */}
            <div className="mt-4 pt-4 border-t border-white/10">
              <div className="flex justify-between text-xs text-white/40 mb-1">
                <span>Conservative</span>
                <span>Aggressive</span>
              </div>
              <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    calculation.positionSize <= 5 ? 'bg-green-500' :
                    calculation.positionSize <= 10 ? 'bg-yellow-500' :
                    calculation.positionSize <= 20 ? 'bg-orange-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${Math.min(calculation.positionSize, 100)}%` }}
                />
              </div>
            </div>
          </div>

          {/* Trade Summary */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <BarChart2 className="w-5 h-5" />
              Trade Summary
            </h3>

            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <ArrowRight className="w-4 h-4 text-white/40" />
                <span className="text-white/60">Buy</span>
                <span className="font-medium">{formatNumber(calculation.numberOfUnits)} {selectedToken}</span>
              </div>
              <div className="flex items-center gap-2">
                <ArrowRight className="w-4 h-4 text-white/40" />
                <span className="text-white/60">At</span>
                <span className="font-medium">${formatNumber(parseFloat(entryPrice) || tokenData.price)}</span>
              </div>
              {stopLoss && (
                <div className="flex items-center gap-2">
                  <ArrowRight className="w-4 h-4 text-red-400" />
                  <span className="text-white/60">Stop at</span>
                  <span className="font-medium text-red-400">${formatNumber(parseFloat(stopLoss))}</span>
                </div>
              )}
              {takeProfit && (
                <div className="flex items-center gap-2">
                  <ArrowRight className="w-4 h-4 text-green-400" />
                  <span className="text-white/60">Target</span>
                  <span className="font-medium text-green-400">${formatNumber(parseFloat(takeProfit))}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Position History */}
      {positionHistory.length > 0 && (
        <div className="bg-white/5 border border-white/10 rounded-xl p-6">
          <h3 className="text-lg font-semibold mb-4">Recent Calculations</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-sm text-white/60">
                  <th className="pb-2">Token</th>
                  <th className="pb-2">Method</th>
                  <th className="pb-2">Entry</th>
                  <th className="pb-2">Stop</th>
                  <th className="pb-2">Target</th>
                  <th className="pb-2">Size %</th>
                  <th className="pb-2">Value</th>
                  <th className="pb-2">R:R</th>
                </tr>
              </thead>
              <tbody>
                {positionHistory.map(pos => (
                  <tr key={pos.id} className="border-t border-white/5 text-sm">
                    <td className="py-2">{pos.token}</td>
                    <td className="py-2 capitalize">{pos.method.replace('_', ' ')}</td>
                    <td className="py-2">${formatNumber(pos.entry)}</td>
                    <td className="py-2 text-red-400">${formatNumber(pos.stop) || '-'}</td>
                    <td className="py-2 text-green-400">${formatNumber(pos.target) || '-'}</td>
                    <td className="py-2">{pos.size.toFixed(2)}%</td>
                    <td className="py-2">{formatCurrency(pos.value)}</td>
                    <td className="py-2">{pos.rr > 0 ? `1:${pos.rr.toFixed(2)}` : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Info Section */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <p className="font-medium text-blue-400 mb-1">Position Sizing Tips</p>
            <ul className="list-disc list-inside space-y-1 text-white/60">
              <li>Never risk more than 1-2% of your portfolio on a single trade</li>
              <li>Use the Kelly Criterion with caution - half Kelly is safer</li>
              <li>Volatility-adjusted sizing helps maintain consistent risk across different assets</li>
              <li>Always set a stop loss before entering a trade</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default PositionSizer
