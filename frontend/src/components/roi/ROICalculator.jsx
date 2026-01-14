import React, { useState, useMemo } from 'react'
import {
  TrendingUp, Calculator, Clock, DollarSign, Percent, Calendar,
  BarChart3, ArrowRight, ArrowUpRight, ArrowDownRight, RefreshCw,
  Download, PlusCircle, Trash2, History, Target, Zap, Award,
  ChevronDown, Info, LineChart, PieChart, Scale, Coins
} from 'lucide-react'

const TIME_PERIODS = [
  { id: 'daily', label: 'Daily', days: 1 },
  { id: 'weekly', label: 'Weekly', days: 7 },
  { id: 'monthly', label: 'Monthly', days: 30 },
  { id: 'quarterly', label: 'Quarterly', days: 90 },
  { id: 'yearly', label: 'Yearly', days: 365 },
  { id: 'custom', label: 'Custom', days: 0 }
]

const COMPARISON_BENCHMARKS = [
  { id: 'btc', name: 'Bitcoin', roi: 45.2, color: 'text-orange-400' },
  { id: 'eth', name: 'Ethereum', roi: 32.8, color: 'text-blue-400' },
  { id: 'sp500', name: 'S&P 500', roi: 12.5, color: 'text-green-400' },
  { id: 'savings', name: 'Savings Account', roi: 4.5, color: 'text-gray-400' },
  { id: 'bonds', name: 'Treasury Bonds', roi: 5.2, color: 'text-purple-400' }
]

export function ROICalculator() {
  const [mode, setMode] = useState('simple') // simple, advanced, comparison, history
  const [initialInvestment, setInitialInvestment] = useState(10000)
  const [currentValue, setCurrentValue] = useState(15000)
  const [timePeriod, setTimePeriod] = useState('yearly')
  const [customDays, setCustomDays] = useState(180)
  const [compoundingFrequency, setCompoundingFrequency] = useState('monthly')

  // Advanced mode
  const [additionalInvestments, setAdditionalInvestments] = useState([])
  const [withdrawals, setWithdrawals] = useState([])

  // Comparison mode
  const [investments, setInvestments] = useState([
    { id: 1, name: 'BTC Trade', initial: 5000, current: 7500, days: 90 },
    { id: 2, name: 'ETH Staking', initial: 3000, current: 3600, days: 365 },
    { id: 3, name: 'SOL DeFi', initial: 2000, current: 4200, days: 60 }
  ])

  // Get days for selected period
  const getDays = () => {
    if (timePeriod === 'custom') return customDays
    return TIME_PERIODS.find(p => p.id === timePeriod)?.days || 365
  }

  // Simple ROI calculations
  const simpleResults = useMemo(() => {
    const totalGain = currentValue - initialInvestment
    const roi = ((currentValue - initialInvestment) / initialInvestment) * 100
    const days = getDays()

    // Annualized ROI
    const annualizedROI = (Math.pow(currentValue / initialInvestment, 365 / days) - 1) * 100

    // Daily/Monthly/Yearly rates
    const dailyRate = (Math.pow(1 + roi / 100, 1 / days) - 1) * 100
    const monthlyRate = (Math.pow(1 + roi / 100, 30 / days) - 1) * 100

    // Time to double
    const timeToDouble = roi > 0 ? (70 / annualizedROI) : null

    // Break-even analysis (if in loss)
    const percentToBreakeven = roi < 0 ? ((initialInvestment / currentValue) - 1) * 100 : 0

    // Projections
    const oneYearProjection = initialInvestment * Math.pow(1 + annualizedROI / 100, 1)
    const fiveYearProjection = initialInvestment * Math.pow(1 + annualizedROI / 100, 5)
    const tenYearProjection = initialInvestment * Math.pow(1 + annualizedROI / 100, 10)

    return {
      totalGain,
      roi,
      annualizedROI,
      dailyRate,
      monthlyRate,
      timeToDouble,
      percentToBreakeven,
      oneYearProjection,
      fiveYearProjection,
      tenYearProjection,
      days
    }
  }, [initialInvestment, currentValue, timePeriod, customDays])

  // Advanced ROI with multiple cash flows
  const advancedResults = useMemo(() => {
    // Money-weighted return calculation (simplified IRR approximation)
    let totalInvested = initialInvestment
    let weightedDays = initialInvestment * getDays()

    additionalInvestments.forEach(inv => {
      totalInvested += inv.amount
      weightedDays += inv.amount * (getDays() - inv.daysAgo)
    })

    let totalWithdrawn = 0
    withdrawals.forEach(w => {
      totalWithdrawn += w.amount
      weightedDays -= w.amount * (getDays() - w.daysAgo)
    })

    const netInvested = totalInvested - totalWithdrawn
    const avgDaysInvested = weightedDays / totalInvested

    const absoluteReturn = currentValue - netInvested
    const mwrr = (absoluteReturn / netInvested) * 100
    const annualizedMWRR = (Math.pow(1 + mwrr / 100, 365 / avgDaysInvested) - 1) * 100

    return {
      totalInvested,
      totalWithdrawn,
      netInvested,
      absoluteReturn,
      mwrr,
      annualizedMWRR,
      avgDaysInvested,
      cashFlowCount: additionalInvestments.length + withdrawals.length
    }
  }, [initialInvestment, currentValue, additionalInvestments, withdrawals, timePeriod, customDays])

  // Investment comparison
  const comparisonResults = useMemo(() => {
    return investments.map(inv => {
      const roi = ((inv.current - inv.initial) / inv.initial) * 100
      const annualized = (Math.pow(inv.current / inv.initial, 365 / inv.days) - 1) * 100
      const gain = inv.current - inv.initial

      return {
        ...inv,
        roi,
        annualized,
        gain
      }
    }).sort((a, b) => b.annualized - a.annualized)
  }, [investments])

  const addAdditionalInvestment = () => {
    setAdditionalInvestments([
      ...additionalInvestments,
      { id: Date.now(), amount: 1000, daysAgo: 30 }
    ])
  }

  const addWithdrawal = () => {
    setWithdrawals([
      ...withdrawals,
      { id: Date.now(), amount: 500, daysAgo: 15 }
    ])
  }

  const addInvestment = () => {
    setInvestments([
      ...investments,
      { id: Date.now(), name: 'New Investment', initial: 1000, current: 1000, days: 30 }
    ])
  }

  const removeInvestment = (id) => {
    setInvestments(investments.filter(inv => inv.id !== id))
  }

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value)
  }

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-500/20 rounded-lg">
            <TrendingUp className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">ROI Calculator</h1>
            <p className="text-sm text-gray-400">Calculate and compare returns</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['simple', 'advanced', 'comparison', 'history'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                mode === m ? 'bg-green-500 text-black' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Simple Mode */}
      {mode === 'simple' && (
        <div className="space-y-6">
          {/* Input Section */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <label className="text-xs text-gray-400 block mb-2">Initial Investment</label>
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={initialInvestment}
                  onChange={(e) => setInitialInvestment(Number(e.target.value))}
                  className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
                />
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <label className="text-xs text-gray-400 block mb-2">Current Value</label>
              <div className="flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-gray-400" />
                <input
                  type="number"
                  value={currentValue}
                  onChange={(e) => setCurrentValue(Number(e.target.value))}
                  className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
                />
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <label className="text-xs text-gray-400 block mb-2">Time Period</label>
              <select
                value={timePeriod}
                onChange={(e) => setTimePeriod(e.target.value)}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
              >
                {TIME_PERIODS.map(period => (
                  <option key={period.id} value={period.id}>{period.label}</option>
                ))}
              </select>
            </div>
            {timePeriod === 'custom' && (
              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <label className="text-xs text-gray-400 block mb-2">Days</label>
                <input
                  type="number"
                  value={customDays}
                  onChange={(e) => setCustomDays(Number(e.target.value))}
                  className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
                />
              </div>
            )}
          </div>

          {/* Results Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className={`rounded-xl p-6 border ${
              simpleResults.roi >= 0
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <Percent className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-400">Total ROI</span>
              </div>
              <div className={`text-3xl font-bold ${simpleResults.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {simpleResults.roi >= 0 ? '+' : ''}{simpleResults.roi.toFixed(2)}%
              </div>
              <div className="text-sm text-gray-400 mt-1">
                {simpleResults.days} days
              </div>
            </div>

            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="flex items-center gap-2 mb-2">
                <DollarSign className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-400">Total Gain/Loss</span>
              </div>
              <div className={`text-3xl font-bold ${simpleResults.totalGain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {formatCurrency(simpleResults.totalGain)}
              </div>
              <div className="text-sm text-gray-400 mt-1">
                Absolute return
              </div>
            </div>

            <div className="bg-blue-500/10 rounded-xl p-6 border border-blue-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Calendar className="w-5 h-5 text-blue-400" />
                <span className="text-sm text-gray-400">Annualized ROI</span>
              </div>
              <div className={`text-3xl font-bold ${simpleResults.annualizedROI >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                {simpleResults.annualizedROI >= 0 ? '+' : ''}{simpleResults.annualizedROI.toFixed(2)}%
              </div>
              <div className="text-sm text-gray-400 mt-1">
                APY equivalent
              </div>
            </div>

            <div className="bg-purple-500/10 rounded-xl p-6 border border-purple-500/30">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-5 h-5 text-purple-400" />
                <span className="text-sm text-gray-400">Time to 2x</span>
              </div>
              <div className="text-3xl font-bold text-purple-400">
                {simpleResults.timeToDouble
                  ? `${simpleResults.timeToDouble.toFixed(1)}y`
                  : 'N/A'
                }
              </div>
              <div className="text-sm text-gray-400 mt-1">
                At current rate
              </div>
            </div>
          </div>

          {/* Rate Breakdown */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-green-400" />
              Rate Breakdown
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-white">
                  {simpleResults.dailyRate >= 0 ? '+' : ''}{simpleResults.dailyRate.toFixed(4)}%
                </div>
                <div className="text-sm text-gray-400">Daily Rate</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-white">
                  {simpleResults.monthlyRate >= 0 ? '+' : ''}{simpleResults.monthlyRate.toFixed(2)}%
                </div>
                <div className="text-sm text-gray-400">Monthly Rate</div>
              </div>
              <div className="bg-white/5 rounded-lg p-4 text-center">
                <div className="text-2xl font-bold text-white">
                  {simpleResults.annualizedROI >= 0 ? '+' : ''}{simpleResults.annualizedROI.toFixed(2)}%
                </div>
                <div className="text-sm text-gray-400">Yearly Rate</div>
              </div>
            </div>
          </div>

          {/* Projections */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <LineChart className="w-5 h-5 text-blue-400" />
              Future Projections (at current rate)
            </h3>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-gradient-to-br from-green-500/20 to-green-600/10 rounded-lg p-4 border border-green-500/30">
                <div className="text-sm text-gray-400 mb-1">1 Year</div>
                <div className="text-2xl font-bold text-green-400">
                  {formatCurrency(simpleResults.oneYearProjection)}
                </div>
                <div className="text-sm text-green-400/70">
                  +{formatCurrency(simpleResults.oneYearProjection - initialInvestment)}
                </div>
              </div>
              <div className="bg-gradient-to-br from-blue-500/20 to-blue-600/10 rounded-lg p-4 border border-blue-500/30">
                <div className="text-sm text-gray-400 mb-1">5 Years</div>
                <div className="text-2xl font-bold text-blue-400">
                  {formatCurrency(simpleResults.fiveYearProjection)}
                </div>
                <div className="text-sm text-blue-400/70">
                  +{formatCurrency(simpleResults.fiveYearProjection - initialInvestment)}
                </div>
              </div>
              <div className="bg-gradient-to-br from-purple-500/20 to-purple-600/10 rounded-lg p-4 border border-purple-500/30">
                <div className="text-sm text-gray-400 mb-1">10 Years</div>
                <div className="text-2xl font-bold text-purple-400">
                  {formatCurrency(simpleResults.tenYearProjection)}
                </div>
                <div className="text-sm text-purple-400/70">
                  +{formatCurrency(simpleResults.tenYearProjection - initialInvestment)}
                </div>
              </div>
            </div>
          </div>

          {/* Benchmark Comparison */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
              <Scale className="w-5 h-5 text-yellow-400" />
              vs Benchmarks (Annual)
            </h3>
            <div className="space-y-3">
              {COMPARISON_BENCHMARKS.map(benchmark => {
                const diff = simpleResults.annualizedROI - benchmark.roi
                const outperforms = diff > 0
                return (
                  <div key={benchmark.id} className="flex items-center justify-between p-3 bg-white/5 rounded-lg">
                    <div className="flex items-center gap-3">
                      <span className={`font-medium ${benchmark.color}`}>{benchmark.name}</span>
                      <span className="text-gray-400">{benchmark.roi}% annual</span>
                    </div>
                    <div className={`flex items-center gap-2 ${outperforms ? 'text-green-400' : 'text-red-400'}`}>
                      {outperforms ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                      <span className="font-semibold">
                        {outperforms ? '+' : ''}{diff.toFixed(2)}%
                      </span>
                      <span className="text-sm text-gray-400">
                        ({outperforms ? 'outperforming' : 'underperforming'})
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}

      {/* Advanced Mode */}
      {mode === 'advanced' && (
        <div className="space-y-6">
          {/* Initial Investment */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <label className="text-xs text-gray-400 block mb-2">Initial Investment</label>
              <input
                type="number"
                value={initialInvestment}
                onChange={(e) => setInitialInvestment(Number(e.target.value))}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
              />
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <label className="text-xs text-gray-400 block mb-2">Current Portfolio Value</label>
              <input
                type="number"
                value={currentValue}
                onChange={(e) => setCurrentValue(Number(e.target.value))}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
              />
            </div>
            <div className="bg-white/5 rounded-xl p-4 border border-white/10">
              <label className="text-xs text-gray-400 block mb-2">Investment Period (Days)</label>
              <input
                type="number"
                value={customDays}
                onChange={(e) => setCustomDays(Number(e.target.value))}
                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white"
              />
            </div>
          </div>

          {/* Additional Investments */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <PlusCircle className="w-5 h-5 text-green-400" />
                Additional Investments
              </h3>
              <button
                onClick={addAdditionalInvestment}
                className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-sm hover:bg-green-500/30"
              >
                Add Investment
              </button>
            </div>
            {additionalInvestments.length === 0 ? (
              <div className="text-center py-4 text-gray-500">No additional investments added</div>
            ) : (
              <div className="space-y-2">
                {additionalInvestments.map((inv, idx) => (
                  <div key={inv.id} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg">
                    <span className="text-gray-400 w-8">#{idx + 1}</span>
                    <div className="flex-1">
                      <label className="text-xs text-gray-400">Amount</label>
                      <input
                        type="number"
                        value={inv.amount}
                        onChange={(e) => {
                          const newInv = [...additionalInvestments]
                          newInv[idx].amount = Number(e.target.value)
                          setAdditionalInvestments(newInv)
                        }}
                        className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-xs text-gray-400">Days Ago</label>
                      <input
                        type="number"
                        value={inv.daysAgo}
                        onChange={(e) => {
                          const newInv = [...additionalInvestments]
                          newInv[idx].daysAgo = Number(e.target.value)
                          setAdditionalInvestments(newInv)
                        }}
                        className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                      />
                    </div>
                    <button
                      onClick={() => setAdditionalInvestments(additionalInvestments.filter(i => i.id !== inv.id))}
                      className="p-2 text-red-400 hover:bg-red-500/20 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Withdrawals */}
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <ArrowDownRight className="w-5 h-5 text-red-400" />
                Withdrawals
              </h3>
              <button
                onClick={addWithdrawal}
                className="px-3 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-sm hover:bg-red-500/30"
              >
                Add Withdrawal
              </button>
            </div>
            {withdrawals.length === 0 ? (
              <div className="text-center py-4 text-gray-500">No withdrawals recorded</div>
            ) : (
              <div className="space-y-2">
                {withdrawals.map((w, idx) => (
                  <div key={w.id} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg">
                    <span className="text-gray-400 w-8">#{idx + 1}</span>
                    <div className="flex-1">
                      <label className="text-xs text-gray-400">Amount</label>
                      <input
                        type="number"
                        value={w.amount}
                        onChange={(e) => {
                          const newW = [...withdrawals]
                          newW[idx].amount = Number(e.target.value)
                          setWithdrawals(newW)
                        }}
                        className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="text-xs text-gray-400">Days Ago</label>
                      <input
                        type="number"
                        value={w.daysAgo}
                        onChange={(e) => {
                          const newW = [...withdrawals]
                          newW[idx].daysAgo = Number(e.target.value)
                          setWithdrawals(newW)
                        }}
                        className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                      />
                    </div>
                    <button
                      onClick={() => setWithdrawals(withdrawals.filter(i => i.id !== w.id))}
                      className="p-2 text-red-400 hover:bg-red-500/20 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Advanced Results */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="text-sm text-gray-400 mb-2">Total Invested</div>
              <div className="text-2xl font-bold text-white">
                {formatCurrency(advancedResults.totalInvested)}
              </div>
            </div>
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <div className="text-sm text-gray-400 mb-2">Total Withdrawn</div>
              <div className="text-2xl font-bold text-white">
                {formatCurrency(advancedResults.totalWithdrawn)}
              </div>
            </div>
            <div className={`rounded-xl p-6 border ${
              advancedResults.mwrr >= 0
                ? 'bg-green-500/10 border-green-500/30'
                : 'bg-red-500/10 border-red-500/30'
            }`}>
              <div className="text-sm text-gray-400 mb-2">Money-Weighted Return</div>
              <div className={`text-2xl font-bold ${advancedResults.mwrr >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {advancedResults.mwrr >= 0 ? '+' : ''}{advancedResults.mwrr.toFixed(2)}%
              </div>
            </div>
            <div className="bg-blue-500/10 rounded-xl p-6 border border-blue-500/30">
              <div className="text-sm text-gray-400 mb-2">Annualized MWRR</div>
              <div className={`text-2xl font-bold ${advancedResults.annualizedMWRR >= 0 ? 'text-blue-400' : 'text-red-400'}`}>
                {advancedResults.annualizedMWRR >= 0 ? '+' : ''}{advancedResults.annualizedMWRR.toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Summary Box */}
          <div className="bg-gradient-to-br from-green-500/10 to-blue-500/10 rounded-xl p-6 border border-green-500/30">
            <h3 className="font-semibold text-white mb-4">Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-400">Net Investment</div>
                <div className="text-white font-medium">{formatCurrency(advancedResults.netInvested)}</div>
              </div>
              <div>
                <div className="text-gray-400">Current Value</div>
                <div className="text-white font-medium">{formatCurrency(currentValue)}</div>
              </div>
              <div>
                <div className="text-gray-400">Absolute Return</div>
                <div className={advancedResults.absoluteReturn >= 0 ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
                  {formatCurrency(advancedResults.absoluteReturn)}
                </div>
              </div>
              <div>
                <div className="text-gray-400">Cash Flow Events</div>
                <div className="text-white font-medium">{advancedResults.cashFlowCount}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Comparison Mode */}
      {mode === 'comparison' && (
        <div className="space-y-6">
          {/* Add Investment Button */}
          <div className="flex justify-end">
            <button
              onClick={addInvestment}
              className="px-4 py-2 bg-green-500 text-black rounded-lg font-medium hover:bg-green-400 flex items-center gap-2"
            >
              <PlusCircle className="w-4 h-4" />
              Add Investment
            </button>
          </div>

          {/* Investment Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {comparisonResults.map((inv, idx) => (
              <div
                key={inv.id}
                className={`bg-white/5 rounded-xl border p-6 ${
                  idx === 0 ? 'border-yellow-500/50' : 'border-white/10'
                }`}
              >
                {idx === 0 && (
                  <div className="flex items-center gap-1 text-yellow-400 text-xs mb-3">
                    <Award className="w-3 h-3" />
                    BEST PERFORMER
                  </div>
                )}
                <div className="flex items-center justify-between mb-4">
                  <input
                    type="text"
                    value={inv.name}
                    onChange={(e) => {
                      const newInv = investments.map(i =>
                        i.id === inv.id ? { ...i, name: e.target.value } : i
                      )
                      setInvestments(newInv)
                    }}
                    className="bg-transparent text-white font-semibold text-lg border-b border-transparent hover:border-white/20 focus:border-white/40 outline-none"
                  />
                  <button
                    onClick={() => removeInvestment(inv.id)}
                    className="p-1 text-gray-400 hover:text-red-400"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="text-xs text-gray-400">Initial</label>
                    <input
                      type="number"
                      value={inv.initial}
                      onChange={(e) => {
                        const newInv = investments.map(i =>
                          i.id === inv.id ? { ...i, initial: Number(e.target.value) } : i
                        )
                        setInvestments(newInv)
                      }}
                      className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400">Current</label>
                    <input
                      type="number"
                      value={inv.current}
                      onChange={(e) => {
                        const newInv = investments.map(i =>
                          i.id === inv.id ? { ...i, current: Number(e.target.value) } : i
                        )
                        setInvestments(newInv)
                      }}
                      className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                    />
                  </div>
                </div>

                <div className="mb-4">
                  <label className="text-xs text-gray-400">Holding Period (Days)</label>
                  <input
                    type="number"
                    value={inv.days}
                    onChange={(e) => {
                      const newInv = investments.map(i =>
                        i.id === inv.id ? { ...i, days: Number(e.target.value) } : i
                      )
                      setInvestments(newInv)
                    }}
                    className="w-full bg-white/10 border border-white/20 rounded px-2 py-1 text-white"
                  />
                </div>

                <div className="pt-4 border-t border-white/10 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-gray-400">ROI</span>
                    <span className={inv.roi >= 0 ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
                      {inv.roi >= 0 ? '+' : ''}{inv.roi.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Annualized</span>
                    <span className={inv.annualized >= 0 ? 'text-blue-400 font-medium' : 'text-red-400 font-medium'}>
                      {inv.annualized >= 0 ? '+' : ''}{inv.annualized.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Gain/Loss</span>
                    <span className={inv.gain >= 0 ? 'text-green-400 font-medium' : 'text-red-400 font-medium'}>
                      {formatCurrency(inv.gain)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Comparison Summary */}
          {comparisonResults.length > 1 && (
            <div className="bg-white/5 rounded-xl border border-white/10 p-6">
              <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
                <PieChart className="w-5 h-5 text-purple-400" />
                Portfolio Summary
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400">Total Invested</div>
                  <div className="text-xl font-bold text-white">
                    {formatCurrency(comparisonResults.reduce((sum, i) => sum + i.initial, 0))}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400">Current Value</div>
                  <div className="text-xl font-bold text-white">
                    {formatCurrency(comparisonResults.reduce((sum, i) => sum + i.current, 0))}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400">Total Gain/Loss</div>
                  <div className={`text-xl font-bold ${
                    comparisonResults.reduce((sum, i) => sum + i.gain, 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {formatCurrency(comparisonResults.reduce((sum, i) => sum + i.gain, 0))}
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400">Avg ROI</div>
                  <div className="text-xl font-bold text-blue-400">
                    {(comparisonResults.reduce((sum, i) => sum + i.roi, 0) / comparisonResults.length).toFixed(2)}%
                  </div>
                </div>
                <div className="bg-white/5 rounded-lg p-4">
                  <div className="text-sm text-gray-400">Best Annualized</div>
                  <div className="text-xl font-bold text-yellow-400">
                    {comparisonResults[0]?.annualized.toFixed(2)}%
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* History Mode */}
      {mode === 'history' && (
        <div className="space-y-6">
          <div className="bg-white/5 rounded-xl border border-white/10 p-6">
            <div className="flex items-center gap-2 mb-6">
              <History className="w-5 h-5 text-purple-400" />
              <h3 className="font-semibold text-white">ROI History</h3>
            </div>

            {/* Mock Historical Data */}
            <div className="space-y-3">
              {[
                { date: '2024-01', roi: 15.2, value: 11520 },
                { date: '2024-02', roi: -3.5, value: 11117 },
                { date: '2024-03', roi: 8.7, value: 12084 },
                { date: '2024-04', roi: 12.1, value: 13547 },
                { date: '2024-05', roi: -1.2, value: 13385 },
                { date: '2024-06', roi: 5.4, value: 14108 },
                { date: '2024-07', roi: 7.8, value: 15208 },
                { date: '2024-08', roi: -4.2, value: 14569 },
                { date: '2024-09', roi: 9.3, value: 15924 },
                { date: '2024-10', roi: 3.1, value: 16418 },
                { date: '2024-11', roi: -2.8, value: 15958 },
                { date: '2024-12', roi: 6.2, value: 16948 }
              ].map((month, idx) => (
                <div key={month.date} className="flex items-center justify-between p-4 bg-white/5 rounded-lg">
                  <div className="flex items-center gap-4">
                    <span className="text-gray-400 font-mono">{month.date}</span>
                    <div className={`flex items-center gap-1 ${month.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {month.roi >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                      <span className="font-semibold">{month.roi >= 0 ? '+' : ''}{month.roi}%</span>
                    </div>
                  </div>
                  <div className="text-white font-medium">{formatCurrency(month.value)}</div>
                </div>
              ))}
            </div>

            {/* YTD Summary */}
            <div className="mt-6 p-4 bg-gradient-to-br from-purple-500/20 to-blue-500/20 rounded-lg border border-purple-500/30">
              <div className="flex justify-between items-center">
                <div>
                  <div className="text-sm text-gray-400">Year-to-Date Return</div>
                  <div className="text-2xl font-bold text-green-400">+69.48%</div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-400">Starting: $10,000</div>
                  <div className="text-xl font-semibold text-white">Current: $16,948</div>
                </div>
              </div>
            </div>
          </div>

          {/* Statistics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
              <div className="text-sm text-gray-400">Best Month</div>
              <div className="text-xl font-bold text-green-400">+15.2%</div>
              <div className="text-xs text-gray-500">January 2024</div>
            </div>
            <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
              <div className="text-sm text-gray-400">Worst Month</div>
              <div className="text-xl font-bold text-red-400">-4.2%</div>
              <div className="text-xs text-gray-500">August 2024</div>
            </div>
            <div className="bg-blue-500/10 rounded-xl p-4 border border-blue-500/30">
              <div className="text-sm text-gray-400">Winning Months</div>
              <div className="text-xl font-bold text-blue-400">8/12</div>
              <div className="text-xs text-gray-500">66.7% win rate</div>
            </div>
            <div className="bg-purple-500/10 rounded-xl p-4 border border-purple-500/30">
              <div className="text-sm text-gray-400">Avg Monthly</div>
              <div className="text-xl font-bold text-purple-400">+4.68%</div>
              <div className="text-xs text-gray-500">Consistent growth</div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ROICalculator
