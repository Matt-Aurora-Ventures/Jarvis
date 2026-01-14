import React, { useState, useMemo, useCallback } from 'react'
import {
  Calculator, RefreshCw, DollarSign, Percent, Clock, TrendingUp,
  Coins, Lock, Calendar, Info, ChevronDown, ChevronUp, Layers,
  Target, Zap, PieChart, ArrowRight, Plus, Minus, ExternalLink
} from 'lucide-react'

// Staking protocols
const PROTOCOLS = {
  LIDO: { name: 'Lido', chain: 'Ethereum', asset: 'ETH', apy: 3.85, minStake: 0, lockPeriod: 0, color: '#00A3FF' },
  ROCKETPOOL: { name: 'Rocket Pool', chain: 'Ethereum', asset: 'ETH', apy: 3.65, minStake: 0.01, lockPeriod: 0, color: '#FF7044' },
  MARINADE: { name: 'Marinade', chain: 'Solana', asset: 'SOL', apy: 7.85, minStake: 0, lockPeriod: 0, color: '#C0B3F0' },
  JITO: { name: 'Jito', chain: 'Solana', asset: 'SOL', apy: 8.12, minStake: 0, lockPeriod: 0, color: '#00FFA3' },
  COINBASE: { name: 'Coinbase', chain: 'Ethereum', asset: 'ETH', apy: 3.28, minStake: 0, lockPeriod: 0, color: '#0052FF' },
  BINANCE: { name: 'Binance', chain: 'Multiple', asset: 'Multiple', apy: 4.5, minStake: 0.0001, lockPeriod: 0, color: '#F0B90B' },
  KRAKEN: { name: 'Kraken', chain: 'Multiple', asset: 'Multiple', apy: 4.0, minStake: 0.0001, lockPeriod: 0, color: '#5741D9' },
  EIGENLAYER: { name: 'EigenLayer', chain: 'Ethereum', asset: 'ETH', apy: 5.5, minStake: 0.01, lockPeriod: 7, color: '#7B3FE4' }
}

// Time periods for calculation
const TIME_PERIODS = [
  { key: '1M', label: '1 Month', days: 30 },
  { key: '3M', label: '3 Months', days: 90 },
  { key: '6M', label: '6 Months', days: 180 },
  { key: '1Y', label: '1 Year', days: 365 },
  { key: '2Y', label: '2 Years', days: 730 },
  { key: '5Y', label: '5 Years', days: 1825 }
]

// Compounding frequencies
const COMPOUND_FREQ = [
  { key: 'daily', label: 'Daily', periods: 365 },
  { key: 'weekly', label: 'Weekly', periods: 52 },
  { key: 'monthly', label: 'Monthly', periods: 12 },
  { key: 'quarterly', label: 'Quarterly', periods: 4 },
  { key: 'yearly', label: 'Yearly', periods: 1 },
  { key: 'none', label: 'No Compound', periods: 0 }
]

// Calculate staking rewards
const calculateRewards = (principal, apy, days, compoundFreq) => {
  const rate = apy / 100
  const years = days / 365

  if (compoundFreq === 0) {
    // Simple interest
    return principal * rate * years
  }

  // Compound interest
  const n = compoundFreq
  const finalValue = principal * Math.pow(1 + rate / n, n * years)
  return finalValue - principal
}

// Calculate APY to APR conversion
const apyToApr = (apy, compoundPeriods) => {
  if (compoundPeriods <= 1) return apy
  const r = apy / 100
  return ((Math.pow(1 + r, 1 / compoundPeriods) - 1) * compoundPeriods * 100)
}

// Input field component
const InputField = ({ label, value, onChange, suffix, prefix, step = 1, min = 0, max, info }) => (
  <div className="space-y-1">
    <div className="flex items-center justify-between">
      <label className="text-sm text-gray-400">{label}</label>
      {info && (
        <div className="group relative">
          <Info className="w-4 h-4 text-gray-500 cursor-help" />
          <div className="absolute right-0 bottom-full mb-2 w-48 p-2 bg-gray-900 text-xs rounded hidden group-hover:block z-10">
            {info}
          </div>
        </div>
      )}
    </div>
    <div className="relative">
      {prefix && (
        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500">{prefix}</span>
      )}
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
        step={step}
        min={min}
        max={max}
        className={`w-full bg-white/5 border border-white/10 rounded-lg py-2 text-white focus:outline-none focus:border-blue-500/50 ${
          prefix ? 'pl-8' : 'pl-4'
        } ${suffix ? 'pr-16' : 'pr-4'}`}
      />
      {suffix && (
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500">{suffix}</span>
      )}
    </div>
  </div>
)

// Protocol selector
const ProtocolSelector = ({ selected, onSelect }) => (
  <div className="space-y-2">
    <label className="text-sm text-gray-400">Select Protocol (Optional)</label>
    <div className="grid grid-cols-4 gap-2">
      {Object.entries(PROTOCOLS).map(([key, protocol]) => (
        <button
          key={key}
          onClick={() => onSelect(selected === key ? null : key)}
          className={`p-2 rounded-lg text-xs font-medium transition-colors ${
            selected === key
              ? 'border-2'
              : 'bg-white/5 border border-white/10 hover:bg-white/10'
          }`}
          style={selected === key ? {
            backgroundColor: `${protocol.color}20`,
            borderColor: protocol.color,
            color: protocol.color
          } : {}}
        >
          {protocol.name}
        </button>
      ))}
    </div>
  </div>
)

// Results display
const RewardsResults = ({ results, asset, assetPrice }) => (
  <div className="bg-white/5 rounded-xl p-6 border border-white/10">
    <h3 className="text-lg font-medium mb-4 flex items-center gap-2">
      <Target className="w-5 h-5 text-green-400" />
      Projected Rewards
    </h3>

    <div className="grid grid-cols-2 gap-4">
      {results.map((result, idx) => (
        <div key={idx} className="bg-white/5 rounded-lg p-4">
          <div className="text-sm text-gray-500 mb-2">{result.period}</div>
          <div className="text-2xl font-bold text-green-400">
            {result.rewards.toLocaleString(undefined, { maximumFractionDigits: 4 })} {asset}
          </div>
          <div className="text-sm text-gray-400">
            ~${(result.rewards * assetPrice).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-gray-500 mt-2">
            Final Value: {result.finalValue.toLocaleString(undefined, { maximumFractionDigits: 4 })} {asset}
          </div>
        </div>
      ))}
    </div>
  </div>
)

// Comparison table
const ComparisonTable = ({ principal, days }) => {
  const comparisons = useMemo(() => {
    return Object.entries(PROTOCOLS).map(([key, protocol]) => {
      const rewards = calculateRewards(principal, protocol.apy, days, 365)
      return {
        key,
        ...protocol,
        rewards,
        finalValue: principal + rewards
      }
    }).sort((a, b) => b.rewards - a.rewards)
  }, [principal, days])

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <Layers className="w-4 h-4" />
        Protocol Comparison
      </h3>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-gray-500 text-xs">
              <th className="text-left pb-2">Protocol</th>
              <th className="text-right pb-2">APY</th>
              <th className="text-right pb-2">Rewards</th>
              <th className="text-right pb-2">Final Value</th>
            </tr>
          </thead>
          <tbody>
            {comparisons.slice(0, 6).map((comp, idx) => (
              <tr key={comp.key} className="border-t border-white/5">
                <td className="py-2">
                  <span style={{ color: comp.color }}>{comp.name}</span>
                </td>
                <td className="text-right text-green-400">{comp.apy}%</td>
                <td className="text-right font-mono">{comp.rewards.toFixed(4)}</td>
                <td className="text-right font-mono">{comp.finalValue.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Growth chart (simplified)
const GrowthChart = ({ principal, apy, compoundPeriods }) => {
  const dataPoints = useMemo(() => {
    const points = []
    for (let month = 0; month <= 12; month++) {
      const days = month * 30
      const value = principal + calculateRewards(principal, apy, days, compoundPeriods)
      points.push({ month, value })
    }
    return points
  }, [principal, apy, compoundPeriods])

  const maxValue = Math.max(...dataPoints.map(p => p.value))
  const minValue = principal

  return (
    <div className="bg-white/5 rounded-xl p-4 border border-white/10">
      <h3 className="text-sm font-medium text-gray-300 mb-4 flex items-center gap-2">
        <TrendingUp className="w-4 h-4 text-green-400" />
        1 Year Growth Projection
      </h3>

      <div className="h-40 flex items-end gap-1">
        {dataPoints.map((point, idx) => {
          const height = ((point.value - minValue) / (maxValue - minValue)) * 100 + 10
          return (
            <div
              key={idx}
              className="flex-1 bg-gradient-to-t from-green-500/60 to-green-400/40 rounded-t transition-all duration-300 hover:from-green-500/80 hover:to-green-400/60"
              style={{ height: `${height}%` }}
              title={`Month ${point.month}: ${point.value.toFixed(4)}`}
            />
          )
        })}
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-2">
        <span>Now</span>
        <span>6 months</span>
        <span>12 months</span>
      </div>
    </div>
  )
}

// Quick stats
const QuickStats = ({ principal, apy, rewards, compoundPeriods }) => {
  const apr = apyToApr(apy, compoundPeriods)
  const dailyRewards = calculateRewards(principal, apy, 1, compoundPeriods)
  const weeklyRewards = calculateRewards(principal, apy, 7, compoundPeriods)
  const monthlyRewards = calculateRewards(principal, apy, 30, compoundPeriods)

  return (
    <div className="grid grid-cols-4 gap-4 mb-6">
      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1 flex items-center gap-2">
          <Zap className="w-4 h-4" />
          APY
        </div>
        <div className="text-2xl font-bold text-green-400">{apy}%</div>
        <div className="text-xs text-gray-500">APR: {apr.toFixed(2)}%</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Daily</div>
        <div className="text-xl font-bold">{dailyRewards.toFixed(6)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Weekly</div>
        <div className="text-xl font-bold">{weeklyRewards.toFixed(5)}</div>
      </div>

      <div className="bg-white/5 rounded-xl p-4 border border-white/10">
        <div className="text-sm text-gray-400 mb-1">Monthly</div>
        <div className="text-xl font-bold">{monthlyRewards.toFixed(4)}</div>
      </div>
    </div>
  )
}

// Main component
export const StakingCalculator = () => {
  const [principal, setPrincipal] = useState(10)
  const [apy, setApy] = useState(7.85)
  const [asset, setAsset] = useState('SOL')
  const [assetPrice, setAssetPrice] = useState(198)
  const [selectedPeriod, setSelectedPeriod] = useState('1Y')
  const [compoundFreq, setCompoundFreq] = useState('daily')
  const [selectedProtocol, setSelectedProtocol] = useState(null)

  // Update values when protocol selected
  const handleProtocolSelect = useCallback((protocol) => {
    setSelectedProtocol(protocol)
    if (protocol) {
      const p = PROTOCOLS[protocol]
      setApy(p.apy)
      setAsset(p.asset)
      // Update price based on asset
      if (p.asset === 'ETH') setAssetPrice(3450)
      else if (p.asset === 'SOL') setAssetPrice(198)
    }
  }, [])

  // Get compound periods
  const compoundPeriods = COMPOUND_FREQ.find(c => c.key === compoundFreq)?.periods || 365

  // Calculate results for all time periods
  const results = useMemo(() => {
    return TIME_PERIODS.map(period => {
      const rewards = calculateRewards(principal, apy, period.days, compoundPeriods)
      return {
        period: period.label,
        days: period.days,
        rewards,
        finalValue: principal + rewards
      }
    })
  }, [principal, apy, compoundPeriods])

  const selectedDays = TIME_PERIODS.find(p => p.key === selectedPeriod)?.days || 365

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-3">
              <Calculator className="w-7 h-7 text-blue-400" />
              Staking Rewards Calculator
            </h1>
            <p className="text-gray-400 mt-1">Calculate and compare staking rewards across protocols</p>
          </div>
        </div>

        {/* Quick Stats */}
        <QuickStats
          principal={principal}
          apy={apy}
          rewards={calculateRewards(principal, apy, 365, compoundPeriods)}
          compoundPeriods={compoundPeriods}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Calculator inputs */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white/5 rounded-xl p-6 border border-white/10">
              <h3 className="text-lg font-medium mb-4">Calculate Rewards</h3>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <InputField
                  label="Stake Amount"
                  value={principal}
                  onChange={setPrincipal}
                  suffix={asset}
                  step={0.1}
                  min={0}
                />
                <InputField
                  label="APY"
                  value={apy}
                  onChange={setApy}
                  suffix="%"
                  step={0.1}
                  min={0}
                  max={100}
                />
              </div>

              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="space-y-1">
                  <label className="text-sm text-gray-400">Asset</label>
                  <div className="flex gap-2">
                    {['ETH', 'SOL', 'BTC', 'MATIC'].map(a => (
                      <button
                        key={a}
                        onClick={() => {
                          setAsset(a)
                          if (a === 'ETH') setAssetPrice(3450)
                          else if (a === 'SOL') setAssetPrice(198)
                          else if (a === 'BTC') setAssetPrice(97500)
                          else if (a === 'MATIC') setAssetPrice(0.95)
                        }}
                        className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                          asset === a
                            ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                            : 'bg-white/5 border border-white/10 hover:bg-white/10'
                        }`}
                      >
                        {a}
                      </button>
                    ))}
                  </div>
                </div>

                <InputField
                  label="Asset Price (USD)"
                  value={assetPrice}
                  onChange={setAssetPrice}
                  prefix="$"
                  step={1}
                  min={0}
                />
              </div>

              <div className="space-y-1 mb-6">
                <label className="text-sm text-gray-400">Compounding Frequency</label>
                <div className="flex gap-2">
                  {COMPOUND_FREQ.map(freq => (
                    <button
                      key={freq.key}
                      onClick={() => setCompoundFreq(freq.key)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                        compoundFreq === freq.key
                          ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                          : 'bg-white/5 border border-white/10 hover:bg-white/10'
                      }`}
                    >
                      {freq.label}
                    </button>
                  ))}
                </div>
              </div>

              <ProtocolSelector
                selected={selectedProtocol}
                onSelect={handleProtocolSelect}
              />
            </div>

            {/* Results */}
            <RewardsResults
              results={results}
              asset={asset}
              assetPrice={assetPrice}
            />
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <GrowthChart
              principal={principal}
              apy={apy}
              compoundPeriods={compoundPeriods}
            />
            <ComparisonTable
              principal={principal}
              days={selectedDays}
            />
          </div>
        </div>

        {/* USD Value Summary */}
        <div className="mt-6 bg-gradient-to-r from-green-500/10 to-blue-500/10 rounded-xl p-6 border border-white/10">
          <h3 className="text-lg font-medium mb-4">USD Value Summary</h3>
          <div className="grid grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-gray-500">Initial Investment</div>
              <div className="text-xl font-bold">${(principal * assetPrice).toLocaleString()}</div>
            </div>
            <div>
              <div className="text-sm text-gray-500">1 Year Rewards</div>
              <div className="text-xl font-bold text-green-400">
                +${(results.find(r => r.period === '1 Year')?.rewards * assetPrice || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">1 Year Final Value</div>
              <div className="text-xl font-bold">
                ${(results.find(r => r.period === '1 Year')?.finalValue * assetPrice || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-500">5 Year Final Value</div>
              <div className="text-xl font-bold">
                ${(results.find(r => r.period === '5 Years')?.finalValue * assetPrice || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default StakingCalculator
