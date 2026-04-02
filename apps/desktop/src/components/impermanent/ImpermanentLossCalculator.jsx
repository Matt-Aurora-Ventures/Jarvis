import React, { useState, useMemo, useEffect } from 'react'
import {
  Calculator, TrendingUp, TrendingDown, AlertTriangle, Info, RefreshCw,
  DollarSign, Percent, ArrowRight, BarChart2, PieChart, HelpCircle,
  Sliders, Target, Shield, ChevronDown, Droplets, Coins
} from 'lucide-react'

const COMMON_PAIRS = [
  { token0: 'ETH', token1: 'USDC', price0: 3450, price1: 1 },
  { token0: 'BTC', token1: 'USDC', price0: 67500, price1: 1 },
  { token0: 'SOL', token1: 'USDC', price0: 145, price1: 1 },
  { token0: 'ETH', token1: 'BTC', price0: 3450, price1: 67500 },
  { token0: 'ETH', token1: 'WBTC', price0: 3450, price1: 67500 },
  { token0: 'SOL', token1: 'ETH', price0: 145, price1: 3450 },
  { token0: 'LINK', token1: 'ETH', price0: 14.5, price1: 3450 },
  { token0: 'UNI', token1: 'ETH', price0: 9.8, price1: 3450 }
]

const PRESET_SCENARIOS = [
  { label: 'Token doubles', priceChange: 100 },
  { label: 'Token +50%', priceChange: 50 },
  { label: 'Token +25%', priceChange: 25 },
  { label: 'Token -25%', priceChange: -25 },
  { label: 'Token -50%', priceChange: -50 },
  { label: 'Token -75%', priceChange: -75 }
]

export function ImpermanentLossCalculator() {
  // Input state
  const [token0Symbol, setToken0Symbol] = useState('ETH')
  const [token1Symbol, setToken1Symbol] = useState('USDC')
  const [initialPrice0, setInitialPrice0] = useState(3450)
  const [initialPrice1, setInitialPrice1] = useState(1)
  const [currentPrice0, setCurrentPrice0] = useState(3450)
  const [currentPrice1, setCurrentPrice1] = useState(1)
  const [initialInvestment, setInitialInvestment] = useState(10000)
  const [feeAPR, setFeeAPR] = useState(20)
  const [holdingDays, setHoldingDays] = useState(30)

  // Calculation modes
  const [usePreset, setUsePreset] = useState(false)
  const [presetChange, setPresetChange] = useState(50)

  // Apply preset
  useEffect(() => {
    if (usePreset) {
      const newPrice = initialPrice0 * (1 + presetChange / 100)
      setCurrentPrice0(newPrice)
    }
  }, [usePreset, presetChange, initialPrice0])

  // Load common pair
  const loadPair = (pair) => {
    setToken0Symbol(pair.token0)
    setToken1Symbol(pair.token1)
    setInitialPrice0(pair.price0)
    setInitialPrice1(pair.price1)
    setCurrentPrice0(pair.price0)
    setCurrentPrice1(pair.price1)
    setUsePreset(false)
  }

  // Calculate impermanent loss and results
  const results = useMemo(() => {
    // Price ratio
    const initialRatio = initialPrice0 / initialPrice1
    const currentRatio = currentPrice0 / currentPrice1

    // Price change multiplier (k)
    const k = currentRatio / initialRatio

    // Impermanent loss formula: IL = 2 * sqrt(k) / (1 + k) - 1
    const sqrtK = Math.sqrt(k)
    const ilMultiplier = (2 * sqrtK) / (1 + k)
    const impermanentLoss = (ilMultiplier - 1) * 100 // As percentage

    // Initial token amounts (50/50 split)
    const initialValue0 = initialInvestment / 2
    const initialValue1 = initialInvestment / 2
    const initialAmount0 = initialValue0 / initialPrice0
    const initialAmount1 = initialValue1 / initialPrice1

    // Value if held (no LP)
    const holdValue0 = initialAmount0 * currentPrice0
    const holdValue1 = initialAmount1 * currentPrice1
    const holdTotalValue = holdValue0 + holdValue1

    // LP value after impermanent loss
    const lpValueWithoutFees = holdTotalValue * ilMultiplier

    // Fee earnings (simplified calculation)
    const dailyFeeRate = feeAPR / 365 / 100
    const totalFeeEarnings = lpValueWithoutFees * dailyFeeRate * holdingDays

    // Final LP value with fees
    const lpValueWithFees = lpValueWithoutFees + totalFeeEarnings

    // Net result
    const netProfitVsHold = lpValueWithFees - holdTotalValue
    const netProfitVsInitial = lpValueWithFees - initialInvestment

    // Current token amounts in LP (after rebalancing)
    const lpTotalValueInTermsOf0 = lpValueWithoutFees / currentPrice0
    const currentAmount0InLP = lpTotalValueInTermsOf0 * sqrtK / (1 + sqrtK) / sqrtK * (1 + sqrtK) / 2
    const currentAmount1InLP = (lpValueWithoutFees - currentAmount0InLP * currentPrice0) / currentPrice1

    // Break-even fee APR
    const breakEvenAPR = Math.abs(impermanentLoss) / (holdingDays / 365) * 100

    return {
      impermanentLoss,
      ilMultiplier,
      k,
      holdTotalValue,
      lpValueWithoutFees,
      lpValueWithFees,
      totalFeeEarnings,
      netProfitVsHold,
      netProfitVsInitial,
      breakEvenAPR,
      initialAmount0,
      initialAmount1,
      priceChange0: ((currentPrice0 / initialPrice0) - 1) * 100,
      priceChange1: ((currentPrice1 / initialPrice1) - 1) * 100
    }
  }, [initialPrice0, initialPrice1, currentPrice0, currentPrice1, initialInvestment, feeAPR, holdingDays])

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value)
  }

  const formatNumber = (value, decimals = 4) => {
    if (Math.abs(value) < 0.0001) return value.toFixed(8)
    return value.toFixed(decimals)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Droplets className="w-6 h-6 text-blue-400" />
          <h2 className="text-xl font-bold">Impermanent Loss Calculator</h2>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Inputs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Pair Selection */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Common Pairs</h3>
            <div className="flex flex-wrap gap-2">
              {COMMON_PAIRS.map((pair, idx) => (
                <button
                  key={idx}
                  onClick={() => loadPair(pair)}
                  className={`px-3 py-2 rounded-lg text-sm transition ${
                    token0Symbol === pair.token0 && token1Symbol === pair.token1
                      ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  {pair.token0}/{pair.token1}
                </button>
              ))}
            </div>
          </div>

          {/* Token Inputs */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Pool Configuration</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Token 0 */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-white/60 mb-2">Token A Symbol</label>
                  <input
                    type="text"
                    value={token0Symbol}
                    onChange={(e) => setToken0Symbol(e.target.value.toUpperCase())}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-2">Initial Price</label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="number"
                      value={initialPrice0}
                      onChange={(e) => setInitialPrice0(parseFloat(e.target.value) || 0)}
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-2">Current Price</label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="number"
                      value={currentPrice0}
                      onChange={(e) => {
                        setCurrentPrice0(parseFloat(e.target.value) || 0)
                        setUsePreset(false)
                      }}
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                  <div className={`text-xs mt-1 ${results.priceChange0 >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {results.priceChange0 >= 0 ? '+' : ''}{results.priceChange0.toFixed(2)}% change
                  </div>
                </div>
              </div>

              {/* Token 1 */}
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-white/60 mb-2">Token B Symbol</label>
                  <input
                    type="text"
                    value={token1Symbol}
                    onChange={(e) => setToken1Symbol(e.target.value.toUpperCase())}
                    className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-2">Initial Price</label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="number"
                      value={initialPrice1}
                      onChange={(e) => setInitialPrice1(parseFloat(e.target.value) || 0)}
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm text-white/60 mb-2">Current Price</label>
                  <div className="relative">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="number"
                      value={currentPrice1}
                      onChange={(e) => setCurrentPrice1(parseFloat(e.target.value) || 0)}
                      className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                    />
                  </div>
                  <div className={`text-xs mt-1 ${results.priceChange1 >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {results.priceChange1 >= 0 ? '+' : ''}{results.priceChange1.toFixed(2)}% change
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Scenario Presets */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Quick Scenarios (Token A vs Token B)</h3>
            <div className="flex flex-wrap gap-2">
              {PRESET_SCENARIOS.map((scenario, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    setUsePreset(true)
                    setPresetChange(scenario.priceChange)
                  }}
                  className={`px-4 py-2 rounded-lg text-sm transition ${
                    usePreset && presetChange === scenario.priceChange
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
                      : 'bg-white/5 border border-white/10 hover:bg-white/10'
                  }`}
                >
                  {scenario.label}
                </button>
              ))}
            </div>
          </div>

          {/* Investment & Fees */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Investment Details</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm text-white/60 mb-2">Initial Investment</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="number"
                    value={initialInvestment}
                    onChange={(e) => setInitialInvestment(parseFloat(e.target.value) || 0)}
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-white/60 mb-2">Pool Fee APR %</label>
                <div className="relative">
                  <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="number"
                    value={feeAPR}
                    onChange={(e) => setFeeAPR(parseFloat(e.target.value) || 0)}
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-white/60 mb-2">Holding Period (days)</label>
                <input
                  type="number"
                  value={holdingDays}
                  onChange={(e) => setHoldingDays(parseInt(e.target.value) || 0)}
                  className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right: Results */}
        <div className="space-y-6">
          {/* IL Result */}
          <div className={`border rounded-xl p-6 ${
            results.impermanentLoss < -5
              ? 'bg-red-500/10 border-red-500/20'
              : results.impermanentLoss < 0
              ? 'bg-yellow-500/10 border-yellow-500/20'
              : 'bg-green-500/10 border-green-500/20'
          }`}>
            <h3 className="text-lg font-semibold mb-2">Impermanent Loss</h3>
            <div className={`text-4xl font-bold ${
              results.impermanentLoss < -5 ? 'text-red-400' : results.impermanentLoss < 0 ? 'text-yellow-400' : 'text-green-400'
            }`}>
              {results.impermanentLoss.toFixed(2)}%
            </div>
            <div className="text-sm text-white/60 mt-1">
              {results.impermanentLoss < 0 ? 'Loss vs just holding' : 'No loss (prices unchanged)'}
            </div>
          </div>

          {/* Value Comparison */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Value Comparison</h3>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-white/60">Initial Investment</span>
                <span className="font-medium">{formatCurrency(initialInvestment)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/60">If Held (No LP)</span>
                <span className="font-medium">{formatCurrency(results.holdTotalValue)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/60">LP Value (No Fees)</span>
                <span className={`font-medium ${results.lpValueWithoutFees < results.holdTotalValue ? 'text-red-400' : ''}`}>
                  {formatCurrency(results.lpValueWithoutFees)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/60">Fee Earnings</span>
                <span className="font-medium text-green-400">+{formatCurrency(results.totalFeeEarnings)}</span>
              </div>
              <div className="pt-4 border-t border-white/10 flex justify-between items-center">
                <span className="font-medium">LP Value (With Fees)</span>
                <span className="text-xl font-bold">{formatCurrency(results.lpValueWithFees)}</span>
              </div>
            </div>
          </div>

          {/* Net Profit */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Net Profit/Loss</h3>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-white/60">vs Holding</span>
                <span className={`font-medium ${results.netProfitVsHold >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {results.netProfitVsHold >= 0 ? '+' : ''}{formatCurrency(results.netProfitVsHold)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-white/60">vs Initial</span>
                <span className={`font-medium ${results.netProfitVsInitial >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {results.netProfitVsInitial >= 0 ? '+' : ''}{formatCurrency(results.netProfitVsInitial)}
                </span>
              </div>
            </div>
          </div>

          {/* Break-even */}
          <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-2 text-purple-400">Break-Even APR</h3>
            <div className="text-3xl font-bold">
              {results.breakEvenAPR.toFixed(2)}%
            </div>
            <div className="text-sm text-white/60 mt-1">
              Minimum fee APR needed to offset IL
            </div>
            <div className="mt-2 text-sm">
              {feeAPR >= results.breakEvenAPR ? (
                <span className="text-green-400">Your pool APR ({feeAPR}%) exceeds break-even</span>
              ) : (
                <span className="text-red-400">Your pool APR ({feeAPR}%) is below break-even</span>
              )}
            </div>
          </div>

          {/* Initial Amounts */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-semibold mb-4">Initial Pool Deposit</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-white/60">{token0Symbol}</span>
                <span>{formatNumber(results.initialAmount0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-white/60">{token1Symbol}</span>
                <span>{formatNumber(results.initialAmount1)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* IL Chart - Simplified visualization */}
      <div className="bg-white/5 border border-white/10 rounded-xl p-6">
        <h3 className="text-lg font-semibold mb-4">Impermanent Loss by Price Change</h3>
        <div className="grid grid-cols-7 gap-2 text-center text-xs">
          {[-75, -50, -25, 0, 25, 50, 100].map(change => {
            const k = (1 + change / 100)
            const sqrtK = Math.sqrt(k)
            const il = ((2 * sqrtK) / (1 + k) - 1) * 100

            return (
              <div key={change} className="space-y-2">
                <div className={`h-20 rounded flex items-end justify-center ${
                  change === Math.round(results.priceChange0) ? 'ring-2 ring-blue-400' : ''
                }`}>
                  <div
                    className={`w-full rounded-t ${Math.abs(il) > 5 ? 'bg-red-500' : Math.abs(il) > 2 ? 'bg-yellow-500' : 'bg-green-500'}`}
                    style={{ height: `${Math.abs(il) * 4}%` }}
                  />
                </div>
                <div className="text-white/40">{change > 0 ? '+' : ''}{change}%</div>
                <div className={`font-medium ${Math.abs(il) > 5 ? 'text-red-400' : Math.abs(il) > 2 ? 'text-yellow-400' : 'text-green-400'}`}>
                  {il.toFixed(2)}%
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <p className="font-medium text-blue-400 mb-1">Understanding Impermanent Loss</p>
            <ul className="list-disc list-inside space-y-1 text-white/60">
              <li>IL occurs when token prices in a pool diverge from their initial ratio</li>
              <li>The loss is "impermanent" because it can reduce if prices return to original ratio</li>
              <li>Fee earnings can offset IL - compare break-even APR with pool APR</li>
              <li>Greater price divergence = greater impermanent loss</li>
              <li>Volatile pairs carry higher IL risk than stable pairs</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ImpermanentLossCalculator
