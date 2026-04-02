import React, { useState, useMemo, useCallback } from 'react'
import {
  Calculator,
  DollarSign,
  Percent,
  Target,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Shield,
  Scale,
  PieChart,
  Info,
  RefreshCw,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Settings,
  Wallet,
  Minus,
  Plus,
  X,
  Zap
} from 'lucide-react'

// Risk levels
const RISK_LEVELS = {
  CONSERVATIVE: { label: 'Conservative', maxRisk: 1, color: 'text-green-400', bg: 'bg-green-400/10' },
  MODERATE: { label: 'Moderate', maxRisk: 2, color: 'text-blue-400', bg: 'bg-blue-400/10' },
  AGGRESSIVE: { label: 'Aggressive', maxRisk: 5, color: 'text-orange-400', bg: 'bg-orange-400/10' },
  DEGEN: { label: 'Degen', maxRisk: 10, color: 'text-red-400', bg: 'bg-red-400/10' }
}

// Position sizing methods
const SIZING_METHODS = {
  FIXED_RISK: { label: 'Fixed Risk %', description: 'Risk a fixed percentage of portfolio per trade' },
  FIXED_AMOUNT: { label: 'Fixed Amount', description: 'Risk a fixed dollar amount per trade' },
  KELLY: { label: 'Kelly Criterion', description: 'Optimal bet sizing based on edge and odds' },
  VOLATILITY: { label: 'Volatility Adjusted', description: 'Size based on asset volatility (ATR)' }
}

// Format helpers
const formatCurrency = (value) => {
  if (value >= 1000000) return `$${(value / 1000000).toFixed(2)}M`
  if (value >= 1000) return `$${(value / 1000).toFixed(2)}K`
  return `$${value.toFixed(2)}`
}

const formatPercent = (value) => `${value.toFixed(2)}%`

// Input component with label
const InputField = ({ label, value, onChange, prefix, suffix, min, max, step = 1, info, disabled = false }) => {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <label className="text-sm text-slate-400">{label}</label>
        {info && (
          <div className="group relative">
            <Info size={14} className="text-slate-500 cursor-help" />
            <div className="absolute right-0 bottom-full mb-2 w-48 p-2 bg-slate-800 rounded-lg text-xs text-slate-300 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
              {info}
            </div>
          </div>
        )}
      </div>
      <div className="relative">
        {prefix && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">{prefix}</span>
        )}
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          min={min}
          max={max}
          step={step}
          disabled={disabled}
          className={`w-full bg-white/5 border border-white/10 rounded-lg py-2.5 text-white focus:outline-none focus:border-blue-500 ${
            prefix ? 'pl-8' : 'pl-4'
          } ${suffix ? 'pr-12' : 'pr-4'} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        />
        {suffix && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">{suffix}</span>
        )}
      </div>
    </div>
  )
}

// Quick adjust buttons
const QuickAdjust = ({ value, onChange, presets, suffix = '' }) => {
  return (
    <div className="flex gap-2 mt-2">
      {presets.map(preset => (
        <button
          key={preset}
          onClick={() => onChange(preset)}
          className={`px-3 py-1 rounded text-xs transition-colors ${
            value === preset
              ? 'bg-blue-500 text-white'
              : 'bg-white/5 text-slate-400 hover:bg-white/10'
          }`}
        >
          {preset}{suffix}
        </button>
      ))}
    </div>
  )
}

// Risk level selector
const RiskLevelSelector = ({ selected, onChange }) => {
  return (
    <div className="grid grid-cols-4 gap-2">
      {Object.entries(RISK_LEVELS).map(([key, level]) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`p-3 rounded-lg text-center transition-colors ${
            selected === key
              ? `${level.bg} ${level.color} border border-current`
              : 'bg-white/5 text-slate-400 hover:bg-white/10'
          }`}
        >
          <div className="text-sm font-medium">{level.label}</div>
          <div className="text-xs opacity-70">{level.maxRisk}% max</div>
        </button>
      ))}
    </div>
  )
}

// Result card
const ResultCard = ({ label, value, sublabel, icon: Icon, color = 'text-white', highlight = false }) => {
  return (
    <div className={`p-4 rounded-xl ${highlight ? 'bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30' : 'bg-white/5 border border-white/10'}`}>
      <div className="flex items-center gap-2 text-slate-400 mb-2">
        {Icon && <Icon size={16} />}
        <span className="text-xs">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sublabel && <div className="text-xs text-slate-500 mt-1">{sublabel}</div>}
    </div>
  )
}

// Risk/Reward visualizer
const RiskRewardVisualizer = ({ riskAmount, rewardAmount, riskPercent }) => {
  const ratio = rewardAmount / riskAmount
  const riskWidth = 100 / (1 + ratio)
  const rewardWidth = 100 - riskWidth

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-400">Risk/Reward Visualization</span>
        <span className={`text-sm font-medium ${ratio >= 2 ? 'text-green-400' : ratio >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
          {ratio.toFixed(2)}R
        </span>
      </div>

      <div className="flex h-8 rounded-lg overflow-hidden mb-2">
        <div
          style={{ width: `${riskWidth}%` }}
          className="bg-red-500/50 flex items-center justify-center"
        >
          <span className="text-xs text-white font-medium">
            -{formatCurrency(riskAmount)}
          </span>
        </div>
        <div
          style={{ width: `${rewardWidth}%` }}
          className="bg-green-500/50 flex items-center justify-center"
        >
          <span className="text-xs text-white font-medium">
            +{formatCurrency(rewardAmount)}
          </span>
        </div>
      </div>

      <div className="flex justify-between text-xs text-slate-500">
        <span>Risk: {riskPercent.toFixed(2)}%</span>
        <span>Reward: {(riskPercent * ratio).toFixed(2)}%</span>
      </div>
    </div>
  )
}

// Kelly Criterion calculator
const KellyCalculator = ({ winRate, avgWin, avgLoss, onChange }) => {
  const [localWinRate, setLocalWinRate] = useState(winRate)
  const [localAvgWin, setLocalAvgWin] = useState(avgWin)
  const [localAvgLoss, setLocalAvgLoss] = useState(avgLoss)

  // Kelly formula: f* = (bp - q) / b
  // where b = odds received on the wager (avg_win/avg_loss)
  // p = probability of winning (win_rate)
  // q = probability of losing (1 - p)
  const calculateKelly = useCallback(() => {
    const p = localWinRate / 100
    const q = 1 - p
    const b = localAvgWin / localAvgLoss

    const kelly = (b * p - q) / b
    return Math.max(0, kelly * 100) // Convert to percentage
  }, [localWinRate, localAvgWin, localAvgLoss])

  const kellyPercent = calculateKelly()
  const halfKelly = kellyPercent / 2
  const quarterKelly = kellyPercent / 4

  const handleApply = () => {
    onChange(halfKelly) // Use half Kelly as recommended
  }

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-white flex items-center gap-2">
          <Scale size={18} className="text-purple-400" />
          Kelly Criterion Calculator
        </h3>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <InputField
          label="Win Rate"
          value={localWinRate}
          onChange={setLocalWinRate}
          suffix="%"
          min={1}
          max={99}
          step={1}
        />
        <InputField
          label="Avg Win"
          value={localAvgWin}
          onChange={setLocalAvgWin}
          prefix="$"
          min={1}
          step={10}
        />
        <InputField
          label="Avg Loss"
          value={localAvgLoss}
          onChange={setLocalAvgLoss}
          prefix="$"
          min={1}
          step={10}
        />
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500 mb-1">Full Kelly</div>
          <div className="text-lg font-bold text-red-400">{kellyPercent.toFixed(2)}%</div>
          <div className="text-xs text-slate-500">High risk</div>
        </div>
        <div className="bg-green-400/10 rounded-lg p-3 text-center border border-green-400/30">
          <div className="text-xs text-slate-500 mb-1">Half Kelly</div>
          <div className="text-lg font-bold text-green-400">{halfKelly.toFixed(2)}%</div>
          <div className="text-xs text-green-400">Recommended</div>
        </div>
        <div className="bg-white/5 rounded-lg p-3 text-center">
          <div className="text-xs text-slate-500 mb-1">Quarter Kelly</div>
          <div className="text-lg font-bold text-blue-400">{quarterKelly.toFixed(2)}%</div>
          <div className="text-xs text-slate-500">Conservative</div>
        </div>
      </div>

      <button
        onClick={handleApply}
        className="w-full py-2 bg-purple-500/20 text-purple-400 rounded-lg hover:bg-purple-500/30 transition-colors"
      >
        Apply Half Kelly ({halfKelly.toFixed(2)}%)
      </button>
    </div>
  )
}

// Position breakdown
const PositionBreakdown = ({ positionSize, entries }) => {
  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <PieChart size={18} className="text-cyan-400" />
        Position Breakdown
      </h3>

      <div className="space-y-3">
        {entries.map((entry, idx) => (
          <div key={idx} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
            <div className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                idx === 0 ? 'bg-green-400/20 text-green-400' :
                idx === 1 ? 'bg-blue-400/20 text-blue-400' :
                'bg-purple-400/20 text-purple-400'
              }`}>
                {idx + 1}
              </div>
              <div>
                <div className="text-sm text-white">Entry {idx + 1}</div>
                <div className="text-xs text-slate-500">{entry.percent}% of position</div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-sm font-medium text-white">{formatCurrency(positionSize * entry.percent / 100)}</div>
              <div className="text-xs text-slate-500">@ ${entry.price.toFixed(4)}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-white/10 flex justify-between items-center">
        <span className="text-sm text-slate-400">Total Position</span>
        <span className="text-lg font-bold text-white">{formatCurrency(positionSize)}</span>
      </div>
    </div>
  )
}

// Multi-position planner
const MultiPositionPlanner = ({ portfolioSize, maxPositions, riskPerTrade, currentPositions }) => {
  const availableRisk = 100 - (currentPositions * riskPerTrade)
  const remainingPositions = maxPositions - currentPositions
  const capitalPerPosition = portfolioSize / maxPositions

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="font-medium text-white mb-4 flex items-center gap-2">
        <Wallet size={18} className="text-orange-400" />
        Position Allocation
      </h3>

      <div className="space-y-3">
        <div className="flex justify-between items-center">
          <span className="text-sm text-slate-400">Current Positions</span>
          <span className="text-white font-medium">{currentPositions} / {maxPositions}</span>
        </div>

        <div className="w-full bg-white/10 rounded-full h-3 overflow-hidden">
          {Array.from({ length: maxPositions }).map((_, idx) => (
            <div
              key={idx}
              className={`h-full ${idx < currentPositions ? 'bg-blue-500' : 'bg-white/5'}`}
              style={{ width: `${100 / maxPositions}%`, display: 'inline-block' }}
            />
          ))}
        </div>

        <div className="grid grid-cols-2 gap-3 mt-4">
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Available Risk</div>
            <div className={`text-lg font-bold ${availableRisk > 50 ? 'text-green-400' : availableRisk > 20 ? 'text-yellow-400' : 'text-red-400'}`}>
              {availableRisk.toFixed(1)}%
            </div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Remaining Slots</div>
            <div className="text-lg font-bold text-white">{remainingPositions}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Capital/Position</div>
            <div className="text-lg font-bold text-cyan-400">{formatCurrency(capitalPerPosition)}</div>
          </div>
          <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-slate-500 mb-1">Total at Risk</div>
            <div className="text-lg font-bold text-red-400">
              {formatCurrency(portfolioSize * (currentPositions * riskPerTrade) / 100)}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// Main PositionCalculator component
export const PositionCalculator = () => {
  // Portfolio settings
  const [portfolioSize, setPortfolioSize] = useState(10000)
  const [riskLevel, setRiskLevel] = useState('MODERATE')
  const [riskPercent, setRiskPercent] = useState(2)

  // Trade inputs
  const [entryPrice, setEntryPrice] = useState(180)
  const [stopLoss, setStopLoss] = useState(170)
  const [takeProfit, setTakeProfit] = useState(220)

  // Advanced settings
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [numEntries, setNumEntries] = useState(1)
  const [maxPositions, setMaxPositions] = useState(5)
  const [currentPositions, setCurrentPositions] = useState(2)

  // Kelly inputs
  const [kellyWinRate, setKellyWinRate] = useState(55)
  const [kellyAvgWin, setKellyAvgWin] = useState(200)
  const [kellyAvgLoss, setKellyAvgLoss] = useState(100)

  // Calculations
  const calculations = useMemo(() => {
    // Risk amount in dollars
    const riskAmount = portfolioSize * (riskPercent / 100)

    // Stop loss percentage
    const stopLossPercent = ((entryPrice - stopLoss) / entryPrice) * 100

    // Position size based on stop loss
    const positionSize = riskAmount / (stopLossPercent / 100)

    // Number of units/tokens
    const units = positionSize / entryPrice

    // Take profit calculations
    const takeProfitPercent = ((takeProfit - entryPrice) / entryPrice) * 100
    const potentialProfit = positionSize * (takeProfitPercent / 100)

    // Risk/Reward ratio
    const riskRewardRatio = takeProfitPercent / stopLossPercent

    // Leverage (if position > portfolio)
    const leverage = positionSize / portfolioSize

    // Entry breakdown for DCA
    const entries = []
    const priceStep = (entryPrice - stopLoss) / (numEntries + 1)
    for (let i = 0; i < numEntries; i++) {
      entries.push({
        price: entryPrice - (priceStep * i),
        percent: 100 / numEntries
      })
    }

    // Win rate needed for breakeven
    const breakEvenWinRate = 100 / (1 + riskRewardRatio)

    return {
      riskAmount,
      stopLossPercent,
      positionSize,
      units,
      takeProfitPercent,
      potentialProfit,
      riskRewardRatio,
      leverage,
      entries,
      breakEvenWinRate
    }
  }, [portfolioSize, riskPercent, entryPrice, stopLoss, takeProfit, numEntries])

  const handleKellyApply = (kellyRisk) => {
    setRiskPercent(Math.min(kellyRisk, RISK_LEVELS[riskLevel].maxRisk))
  }

  // Check if position size exceeds portfolio
  const isOverLeveraged = calculations.positionSize > portfolioSize

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white mb-1 flex items-center gap-2">
              <Calculator className="text-blue-400" />
              Position Size Calculator
            </h1>
            <p className="text-slate-400">Calculate optimal position sizes for risk-adjusted trading</p>
          </div>

          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors"
          >
            <Settings size={18} />
            <span>Advanced</span>
            {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>

        {/* Main grid */}
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left column - Inputs */}
          <div className="lg:col-span-2 space-y-6">
            {/* Portfolio Settings */}
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <h2 className="font-semibold text-white mb-4 flex items-center gap-2">
                <Wallet size={18} className="text-green-400" />
                Portfolio Settings
              </h2>

              <div className="space-y-4">
                <InputField
                  label="Portfolio Size"
                  value={portfolioSize}
                  onChange={setPortfolioSize}
                  prefix="$"
                  min={100}
                  step={100}
                  info="Your total trading capital"
                />
                <QuickAdjust
                  value={portfolioSize}
                  onChange={setPortfolioSize}
                  presets={[1000, 5000, 10000, 25000, 50000, 100000]}
                />

                <div className="pt-4">
                  <label className="text-sm text-slate-400 mb-2 block">Risk Tolerance</label>
                  <RiskLevelSelector selected={riskLevel} onChange={setRiskLevel} />
                </div>

                <InputField
                  label="Risk Per Trade"
                  value={riskPercent}
                  onChange={(v) => setRiskPercent(Math.min(v, RISK_LEVELS[riskLevel].maxRisk))}
                  suffix="%"
                  min={0.1}
                  max={RISK_LEVELS[riskLevel].maxRisk}
                  step={0.1}
                  info={`Maximum ${RISK_LEVELS[riskLevel].maxRisk}% for ${RISK_LEVELS[riskLevel].label} level`}
                />
                <QuickAdjust
                  value={riskPercent}
                  onChange={(v) => setRiskPercent(Math.min(v, RISK_LEVELS[riskLevel].maxRisk))}
                  presets={[0.5, 1, 2, 3, 5]}
                  suffix="%"
                />
              </div>
            </div>

            {/* Trade Parameters */}
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <h2 className="font-semibold text-white mb-4 flex items-center gap-2">
                <Target size={18} className="text-blue-400" />
                Trade Parameters
              </h2>

              <div className="grid md:grid-cols-3 gap-4">
                <InputField
                  label="Entry Price"
                  value={entryPrice}
                  onChange={setEntryPrice}
                  prefix="$"
                  min={0.000001}
                  step={0.01}
                />
                <InputField
                  label="Stop Loss"
                  value={stopLoss}
                  onChange={setStopLoss}
                  prefix="$"
                  min={0.000001}
                  step={0.01}
                />
                <InputField
                  label="Take Profit"
                  value={takeProfit}
                  onChange={setTakeProfit}
                  prefix="$"
                  min={0.000001}
                  step={0.01}
                />
              </div>

              {/* Price validation warning */}
              {stopLoss >= entryPrice && (
                <div className="mt-4 p-3 bg-red-400/10 border border-red-400/30 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                  <AlertTriangle size={16} />
                  Stop loss must be below entry price for long positions
                </div>
              )}

              {takeProfit <= entryPrice && (
                <div className="mt-4 p-3 bg-yellow-400/10 border border-yellow-400/30 rounded-lg flex items-center gap-2 text-yellow-400 text-sm">
                  <AlertTriangle size={16} />
                  Take profit should be above entry price for long positions
                </div>
              )}
            </div>

            {/* Advanced Settings */}
            {showAdvanced && (
              <>
                <div className="bg-white/5 rounded-xl p-6 border border-white/10">
                  <h2 className="font-semibold text-white mb-4 flex items-center gap-2">
                    <Zap size={18} className="text-yellow-400" />
                    Entry Strategy
                  </h2>

                  <InputField
                    label="Number of Entries (DCA)"
                    value={numEntries}
                    onChange={setNumEntries}
                    min={1}
                    max={5}
                    step={1}
                    info="Split position into multiple entries"
                  />
                  <QuickAdjust
                    value={numEntries}
                    onChange={setNumEntries}
                    presets={[1, 2, 3, 4, 5]}
                  />
                </div>

                <KellyCalculator
                  winRate={kellyWinRate}
                  avgWin={kellyAvgWin}
                  avgLoss={kellyAvgLoss}
                  onChange={handleKellyApply}
                />

                <div className="bg-white/5 rounded-xl p-6 border border-white/10">
                  <h2 className="font-semibold text-white mb-4">Portfolio Allocation</h2>
                  <div className="grid md:grid-cols-2 gap-4">
                    <InputField
                      label="Max Concurrent Positions"
                      value={maxPositions}
                      onChange={setMaxPositions}
                      min={1}
                      max={20}
                      step={1}
                    />
                    <InputField
                      label="Current Open Positions"
                      value={currentPositions}
                      onChange={setCurrentPositions}
                      min={0}
                      max={maxPositions}
                      step={1}
                    />
                  </div>
                </div>
              </>
            )}
          </div>

          {/* Right column - Results */}
          <div className="space-y-6">
            {/* Main results */}
            <div className="bg-gradient-to-br from-blue-500/10 to-purple-500/10 rounded-xl p-6 border border-blue-500/20">
              <h2 className="font-semibold text-white mb-4">Calculated Position</h2>

              <div className="space-y-4">
                <ResultCard
                  label="Position Size"
                  value={formatCurrency(calculations.positionSize)}
                  sublabel={`${calculations.units.toFixed(4)} units`}
                  icon={DollarSign}
                  color="text-white"
                  highlight={true}
                />

                <div className="grid grid-cols-2 gap-3">
                  <ResultCard
                    label="Risk Amount"
                    value={formatCurrency(calculations.riskAmount)}
                    sublabel={`${riskPercent}% of portfolio`}
                    icon={AlertTriangle}
                    color="text-red-400"
                  />
                  <ResultCard
                    label="Potential Profit"
                    value={formatCurrency(calculations.potentialProfit)}
                    sublabel={`${calculations.takeProfitPercent.toFixed(2)}% gain`}
                    icon={TrendingUp}
                    color="text-green-400"
                  />
                </div>

                {isOverLeveraged && (
                  <div className="p-3 bg-red-400/10 border border-red-400/30 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                    <AlertTriangle size={16} />
                    Position exceeds portfolio ({calculations.leverage.toFixed(1)}x leverage required)
                  </div>
                )}
              </div>
            </div>

            {/* Risk/Reward */}
            <RiskRewardVisualizer
              riskAmount={calculations.riskAmount}
              rewardAmount={calculations.potentialProfit}
              riskPercent={riskPercent}
            />

            {/* Key metrics */}
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <h3 className="font-medium text-white mb-4">Key Metrics</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-sm text-slate-400">Risk/Reward Ratio</span>
                  <span className={`font-medium ${
                    calculations.riskRewardRatio >= 2 ? 'text-green-400' :
                    calculations.riskRewardRatio >= 1 ? 'text-yellow-400' : 'text-red-400'
                  }`}>
                    1:{calculations.riskRewardRatio.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-slate-400">Stop Loss %</span>
                  <span className="text-red-400 font-medium">-{calculations.stopLossPercent.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-slate-400">Take Profit %</span>
                  <span className="text-green-400 font-medium">+{calculations.takeProfitPercent.toFixed(2)}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-sm text-slate-400">Breakeven Win Rate</span>
                  <span className="text-white font-medium">{calculations.breakEvenWinRate.toFixed(1)}%</span>
                </div>
              </div>
            </div>

            {/* Position breakdown */}
            {numEntries > 1 && (
              <PositionBreakdown
                positionSize={calculations.positionSize}
                entries={calculations.entries}
              />
            )}

            {/* Multi-position planner */}
            {showAdvanced && (
              <MultiPositionPlanner
                portfolioSize={portfolioSize}
                maxPositions={maxPositions}
                riskPerTrade={riskPercent}
                currentPositions={currentPositions}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default PositionCalculator
