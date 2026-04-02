import React, { useState, useMemo } from 'react'
import {
  Calculator, TrendingUp, TrendingDown, AlertTriangle, DollarSign,
  Percent, Target, Shield, Zap, BarChart2, ArrowUp, ArrowDown,
  Info, Scale, AlertOctagon, Activity, Sliders, RefreshCw
} from 'lucide-react'

const SUPPORTED_TOKENS = [
  { symbol: 'BTC', price: 67500, maxLeverage: 125 },
  { symbol: 'ETH', price: 3450, maxLeverage: 100 },
  { symbol: 'SOL', price: 145, maxLeverage: 75 },
  { symbol: 'BNB', price: 580, maxLeverage: 75 },
  { symbol: 'XRP', price: 0.52, maxLeverage: 75 },
  { symbol: 'AVAX', price: 35, maxLeverage: 50 },
  { symbol: 'DOGE', price: 0.12, maxLeverage: 50 },
  { symbol: 'LINK', price: 14.5, maxLeverage: 50 },
  { symbol: 'ARB', price: 1.15, maxLeverage: 50 },
  { symbol: 'OP', price: 2.45, maxLeverage: 50 }
]

const LEVERAGE_PRESETS = [2, 3, 5, 10, 20, 50, 100]

const MARGIN_MODES = [
  { value: 'isolated', label: 'Isolated', description: 'Only allocated margin at risk' },
  { value: 'cross', label: 'Cross', description: 'Entire account balance at risk' }
]

export function LeverageCalculator() {
  const [selectedToken, setSelectedToken] = useState('BTC')
  const [positionType, setPositionType] = useState('long')
  const [leverage, setLeverage] = useState(10)
  const [collateral, setCollateral] = useState(1000)
  const [entryPrice, setEntryPrice] = useState(67500)
  const [marginMode, setMarginMode] = useState('isolated')
  const [maintenanceMargin, setMaintenanceMargin] = useState(0.5)
  const [tradingFee, setTradingFee] = useState(0.04)
  const [fundingRate, setFundingRate] = useState(0.01)
  const [holdingHours, setHoldingHours] = useState(24)

  // Get token info
  const tokenInfo = useMemo(() => {
    return SUPPORTED_TOKENS.find(t => t.symbol === selectedToken) || SUPPORTED_TOKENS[0]
  }, [selectedToken])

  // Update entry price when token changes
  React.useEffect(() => {
    setEntryPrice(tokenInfo.price)
  }, [tokenInfo])

  // Calculate all values
  const results = useMemo(() => {
    // Position value
    const positionValue = collateral * leverage
    const positionSize = positionValue / entryPrice

    // Initial margin
    const initialMargin = collateral
    const initialMarginPercent = (1 / leverage) * 100

    // Maintenance margin
    const maintenanceMarginValue = positionValue * (maintenanceMargin / 100)

    // Liquidation price calculation
    let liquidationPrice
    if (positionType === 'long') {
      // Long: Liquidation when position value - losses = maintenance margin
      // entry - (entry * (1 - 1/leverage - maintenance_margin%))
      liquidationPrice = entryPrice * (1 - (1 / leverage) + (maintenanceMargin / 100))
    } else {
      // Short: entry + (entry * (1 - 1/leverage - maintenance_margin%))
      liquidationPrice = entryPrice * (1 + (1 / leverage) - (maintenanceMargin / 100))
    }

    // Distance to liquidation
    const distanceToLiq = Math.abs((entryPrice - liquidationPrice) / entryPrice) * 100

    // Trading fees
    const openFee = positionValue * (tradingFee / 100)
    const closeFee = positionValue * (tradingFee / 100)
    const totalFees = openFee + closeFee

    // Funding fees (8h intervals)
    const fundingIntervals = holdingHours / 8
    const totalFunding = positionValue * (fundingRate / 100) * fundingIntervals

    // Break-even price (including fees)
    const totalCosts = totalFees + totalFunding
    const breakEvenMove = (totalCosts / positionValue) * 100
    let breakEvenPrice
    if (positionType === 'long') {
      breakEvenPrice = entryPrice * (1 + breakEvenMove / 100)
    } else {
      breakEvenPrice = entryPrice * (1 - breakEvenMove / 100)
    }

    // P&L scenarios
    const scenarios = [
      { move: -50, label: '-50%' },
      { move: -20, label: '-20%' },
      { move: -10, label: '-10%' },
      { move: -5, label: '-5%' },
      { move: 5, label: '+5%' },
      { move: 10, label: '+10%' },
      { move: 20, label: '+20%' },
      { move: 50, label: '+50%' }
    ].map(s => {
      const priceAtMove = entryPrice * (1 + s.move / 100)
      let pnl
      if (positionType === 'long') {
        pnl = (priceAtMove - entryPrice) / entryPrice * positionValue
      } else {
        pnl = (entryPrice - priceAtMove) / entryPrice * positionValue
      }
      const netPnl = pnl - totalFees - totalFunding
      const roe = (netPnl / collateral) * 100

      // Check if liquidated
      const isLiquidated = positionType === 'long'
        ? priceAtMove <= liquidationPrice
        : priceAtMove >= liquidationPrice

      return {
        ...s,
        price: priceAtMove,
        pnl: netPnl,
        roe,
        isLiquidated
      }
    })

    // Max profit (theoretical)
    const maxProfitLong = positionValue - collateral // Can't exceed position value for shorts
    const maxLossLong = collateral // Can't lose more than margin in isolated

    // Effective leverage after fees
    const effectiveLeverage = positionValue / (collateral - totalFees)

    return {
      positionValue,
      positionSize,
      initialMargin,
      initialMarginPercent,
      maintenanceMarginValue,
      liquidationPrice,
      distanceToLiq,
      openFee,
      closeFee,
      totalFees,
      totalFunding,
      breakEvenPrice,
      breakEvenMove,
      scenarios,
      maxProfitLong,
      maxLossLong,
      effectiveLeverage
    }
  }, [selectedToken, positionType, leverage, collateral, entryPrice, maintenanceMargin, tradingFee, fundingRate, holdingHours, tokenInfo])

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value)
  }

  const formatPrice = (price) => {
    if (price < 1) return `$${price.toFixed(4)}`
    if (price < 100) return `$${price.toFixed(2)}`
    return `$${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Scale className="w-6 h-6 text-orange-400" />
          <h2 className="text-xl font-bold">Leverage Calculator</h2>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Inputs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Position Setup */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Position Setup</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              {/* Token */}
              <div>
                <label className="block text-sm text-white/60 mb-2">Token</label>
                <select
                  value={selectedToken}
                  onChange={(e) => setSelectedToken(e.target.value)}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                >
                  {SUPPORTED_TOKENS.map(token => (
                    <option key={token.symbol} value={token.symbol} className="bg-[#0a0e14]">
                      {token.symbol} (Max {token.maxLeverage}x)
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
                    onChange={(e) => setEntryPrice(parseFloat(e.target.value) || 0)}
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
            </div>

            {/* Position Type */}
            <div className="mb-4">
              <label className="block text-sm text-white/60 mb-2">Position Type</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setPositionType('long')}
                  className={`py-3 rounded-lg font-medium transition flex items-center justify-center gap-2 ${
                    positionType === 'long'
                      ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <ArrowUp className="w-4 h-4" />
                  Long
                </button>
                <button
                  onClick={() => setPositionType('short')}
                  className={`py-3 rounded-lg font-medium transition flex items-center justify-center gap-2 ${
                    positionType === 'short'
                      ? 'bg-red-500/20 text-red-400 border border-red-500/50'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  <ArrowDown className="w-4 h-4" />
                  Short
                </button>
              </div>
            </div>

            {/* Margin Mode */}
            <div className="mb-4">
              <label className="block text-sm text-white/60 mb-2">Margin Mode</label>
              <div className="grid grid-cols-2 gap-2">
                {MARGIN_MODES.map(mode => (
                  <button
                    key={mode.value}
                    onClick={() => setMarginMode(mode.value)}
                    className={`p-3 rounded-lg text-left transition ${
                      marginMode === mode.value
                        ? 'bg-orange-500/20 border border-orange-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    <div className="font-medium">{mode.label}</div>
                    <div className="text-xs text-white/40">{mode.description}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Collateral */}
            <div className="mb-4">
              <label className="block text-sm text-white/60 mb-2">Collateral (Margin)</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <input
                  type="number"
                  value={collateral}
                  onChange={(e) => setCollateral(parseFloat(e.target.value) || 0)}
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>

            {/* Leverage */}
            <div>
              <div className="flex justify-between mb-2">
                <label className="text-sm text-white/60">Leverage</label>
                <span className="text-lg font-bold text-orange-400">{leverage}x</span>
              </div>
              <input
                type="range"
                min="1"
                max={tokenInfo.maxLeverage}
                value={leverage}
                onChange={(e) => setLeverage(parseInt(e.target.value))}
                className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
              />
              <div className="flex justify-between text-xs text-white/40 mt-1">
                <span>1x</span>
                <span>{tokenInfo.maxLeverage}x</span>
              </div>
              <div className="flex flex-wrap gap-2 mt-3">
                {LEVERAGE_PRESETS.filter(l => l <= tokenInfo.maxLeverage).map(preset => (
                  <button
                    key={preset}
                    onClick={() => setLeverage(preset)}
                    className={`px-3 py-1 rounded text-sm transition ${
                      leverage === preset
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'bg-white/5 hover:bg-white/10'
                    }`}
                  >
                    {preset}x
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Advanced Settings */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <Sliders className="w-5 h-5" />
              Fee Settings
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-white/60 mb-1">Maintenance Margin %</label>
                <input
                  type="number"
                  step="0.1"
                  value={maintenanceMargin}
                  onChange={(e) => setMaintenanceMargin(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-white/60 mb-1">Trading Fee %</label>
                <input
                  type="number"
                  step="0.01"
                  value={tradingFee}
                  onChange={(e) => setTradingFee(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-white/60 mb-1">Funding Rate % (8h)</label>
                <input
                  type="number"
                  step="0.001"
                  value={fundingRate}
                  onChange={(e) => setFundingRate(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-white/60 mb-1">Holding Period (hours)</label>
                <input
                  type="number"
                  value={holdingHours}
                  onChange={(e) => setHoldingHours(parseInt(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none text-sm"
                />
              </div>
            </div>
          </div>

          {/* P&L Scenarios */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">P&L Scenarios</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-white/60">
                    <th className="pb-2">Price Move</th>
                    <th className="pb-2">Exit Price</th>
                    <th className="pb-2">P&L</th>
                    <th className="pb-2">ROE</th>
                  </tr>
                </thead>
                <tbody>
                  {results.scenarios.map((s, idx) => (
                    <tr key={idx} className={`border-t border-white/5 ${s.isLiquidated ? 'opacity-40' : ''}`}>
                      <td className="py-2">{s.label}</td>
                      <td className="py-2">{formatPrice(s.price)}</td>
                      <td className={`py-2 font-medium ${s.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {s.isLiquidated ? (
                          <span className="text-red-400">LIQUIDATED</span>
                        ) : (
                          formatCurrency(s.pnl)
                        )}
                      </td>
                      <td className={`py-2 ${s.roe >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {s.isLiquidated ? '-' : `${s.roe.toFixed(1)}%`}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right: Results */}
        <div className="space-y-6">
          {/* Position Summary */}
          <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Position Summary</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-white/60">Position Size</span>
                <span className="font-medium">{results.positionSize.toFixed(6)} {selectedToken}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Position Value</span>
                <span className="font-medium">{formatCurrency(results.positionValue)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Initial Margin</span>
                <span className="font-medium">{formatCurrency(results.initialMargin)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Effective Leverage</span>
                <span className="font-medium text-orange-400">{results.effectiveLeverage.toFixed(2)}x</span>
              </div>
            </div>
          </div>

          {/* Liquidation */}
          <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-4">
              <AlertOctagon className="w-5 h-5 text-red-400" />
              <h3 className="text-lg font-semibold text-red-400">Liquidation</h3>
            </div>
            <div className="text-3xl font-bold mb-2">{formatPrice(results.liquidationPrice)}</div>
            <div className="text-sm text-white/60 mb-4">
              {results.distanceToLiq.toFixed(2)}% from entry
            </div>
            <div className="h-3 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-500 via-yellow-500 to-red-500"
                style={{ width: `${100 - Math.min(results.distanceToLiq, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-xs text-white/40 mt-1">
              <span>Safe</span>
              <span>Liquidation</span>
            </div>
          </div>

          {/* Break-even */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Break-Even Analysis</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-white/60">Break-even Price</span>
                <span className="font-medium">{formatPrice(results.breakEvenPrice)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Required Move</span>
                <span className={positionType === 'long' ? 'text-green-400' : 'text-red-400'}>
                  {positionType === 'long' ? '+' : '-'}{results.breakEvenMove.toFixed(3)}%
                </span>
              </div>
            </div>
          </div>

          {/* Fees */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Estimated Fees</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-white/60">Open Fee</span>
                <span>{formatCurrency(results.openFee)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Close Fee</span>
                <span>{formatCurrency(results.closeFee)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">Funding ({holdingHours}h)</span>
                <span>{formatCurrency(results.totalFunding)}</span>
              </div>
              <div className="pt-2 border-t border-white/10 flex justify-between font-medium">
                <span>Total Fees</span>
                <span className="text-red-400">{formatCurrency(results.totalFees + results.totalFunding)}</span>
              </div>
            </div>
          </div>

          {/* Risk Warning */}
          <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-yellow-400 mb-1">High Risk Warning</p>
                <p className="text-white/60">
                  {leverage}x leverage means a {(100 / leverage).toFixed(1)}% price move against you will liquidate your position.
                  Only risk what you can afford to lose.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <p className="font-medium text-blue-400 mb-1">Understanding Leverage Trading</p>
            <ul className="list-disc list-inside space-y-1 text-white/60">
              <li>Higher leverage amplifies both gains AND losses</li>
              <li>Liquidation occurs when your margin can no longer cover losses</li>
              <li>Isolated margin limits risk to the position; cross margin uses full balance</li>
              <li>Funding rates are charged every 8 hours on perpetual contracts</li>
              <li>Always use stop-losses to manage risk</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LeverageCalculator
