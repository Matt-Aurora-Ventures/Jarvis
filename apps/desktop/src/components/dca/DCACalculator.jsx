import React, { useState, useMemo, useEffect, useCallback } from 'react'
import {
  Calculator, TrendingUp, TrendingDown, DollarSign, Calendar,
  RefreshCw, Settings, BarChart3, Target, Percent, Clock,
  ArrowUpRight, ArrowDownRight, AlertTriangle, Info, Zap,
  ChevronDown, ChevronUp, Play, Pause, Plus
} from 'lucide-react'

// Supported assets for DCA
const ASSETS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 65000 },
  { symbol: 'ETH', name: 'Ethereum', price: 3500 },
  { symbol: 'SOL', name: 'Solana', price: 150 },
  { symbol: 'AVAX', name: 'Avalanche', price: 35 },
  { symbol: 'ARB', name: 'Arbitrum', price: 1.2 },
  { symbol: 'OP', name: 'Optimism', price: 2.5 },
  { symbol: 'LINK', name: 'Chainlink', price: 15 },
  { symbol: 'UNI', name: 'Uniswap', price: 10 },
  { symbol: 'AAVE', name: 'Aave', price: 90 },
  { symbol: 'MATIC', name: 'Polygon', price: 0.8 }
]

// DCA frequencies
const FREQUENCIES = {
  DAILY: { label: 'Daily', days: 1 },
  WEEKLY: { label: 'Weekly', days: 7 },
  BIWEEKLY: { label: 'Bi-weekly', days: 14 },
  MONTHLY: { label: 'Monthly', days: 30 }
}

// Historical price simulation (simplified)
const generateHistoricalPrices = (currentPrice, days, volatility = 0.3) => {
  const prices = []
  let price = currentPrice * (0.5 + Math.random() * 0.5) // Start at random point in the past

  for (let i = 0; i < days; i++) {
    const change = (Math.random() - 0.5) * volatility * price / 30
    price = Math.max(price * 0.5, Math.min(price * 1.5, price + change))

    // Trend towards current price as we approach today
    const trendWeight = i / days
    price = price * (1 - trendWeight * 0.1) + currentPrice * trendWeight * 0.1

    prices.push({
      date: new Date(Date.now() - (days - i) * 24 * 60 * 60 * 1000),
      price
    })
  }

  // Make sure last price is current price
  prices[prices.length - 1].price = currentPrice

  return prices
}

// Calculate DCA results
const calculateDCA = (historicalPrices, amount, frequencyDays, startDate, endDate) => {
  const purchases = []
  let totalInvested = 0
  let totalCoins = 0

  const start = new Date(startDate)
  const end = new Date(endDate)

  let currentDate = new Date(start)

  while (currentDate <= end) {
    const priceData = historicalPrices.find(p =>
      p.date.toDateString() === currentDate.toDateString()
    )

    if (priceData) {
      const coins = amount / priceData.price
      totalInvested += amount
      totalCoins += coins

      purchases.push({
        date: new Date(currentDate),
        price: priceData.price,
        amount,
        coins,
        totalInvested,
        totalCoins,
        avgPrice: totalInvested / totalCoins,
        currentValue: totalCoins * historicalPrices[historicalPrices.length - 1].price
      })
    }

    currentDate.setDate(currentDate.getDate() + frequencyDays)
  }

  const currentPrice = historicalPrices[historicalPrices.length - 1].price
  const currentValue = totalCoins * currentPrice
  const avgPrice = totalInvested / totalCoins
  const pnl = currentValue - totalInvested
  const pnlPercent = (pnl / totalInvested) * 100

  return {
    purchases,
    totalInvested,
    totalCoins,
    avgPrice,
    currentPrice,
    currentValue,
    pnl,
    pnlPercent,
    numPurchases: purchases.length
  }
}

// Calculate lump sum for comparison
const calculateLumpSum = (historicalPrices, totalAmount, startDate) => {
  const start = new Date(startDate)
  const priceAtStart = historicalPrices.find(p =>
    p.date.toDateString() === start.toDateString()
  )?.price || historicalPrices[0].price

  const currentPrice = historicalPrices[historicalPrices.length - 1].price
  const coins = totalAmount / priceAtStart
  const currentValue = coins * currentPrice
  const pnl = currentValue - totalAmount
  const pnlPercent = (pnl / totalAmount) * 100

  return {
    invested: totalAmount,
    coins,
    buyPrice: priceAtStart,
    currentPrice,
    currentValue,
    pnl,
    pnlPercent
  }
}

export function DCACalculator() {
  const [selectedAsset, setSelectedAsset] = useState('BTC')
  const [dcaAmount, setDcaAmount] = useState(100)
  const [frequency, setFrequency] = useState('WEEKLY')
  const [duration, setDuration] = useState(365)
  const [historicalPrices, setHistoricalPrices] = useState([])
  const [isCalculating, setIsCalculating] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [futureProjection, setFutureProjection] = useState(10) // Expected annual return %

  const asset = ASSETS.find(a => a.symbol === selectedAsset)

  useEffect(() => {
    if (asset) {
      setHistoricalPrices(generateHistoricalPrices(asset.price, duration + 30))
    }
  }, [selectedAsset, duration])

  const startDate = useMemo(() => {
    const date = new Date()
    date.setDate(date.getDate() - duration)
    return date
  }, [duration])

  const endDate = new Date()

  const dcaResults = useMemo(() => {
    if (historicalPrices.length === 0) return null
    return calculateDCA(
      historicalPrices,
      dcaAmount,
      FREQUENCIES[frequency].days,
      startDate,
      endDate
    )
  }, [historicalPrices, dcaAmount, frequency, startDate, endDate])

  const lumpSumResults = useMemo(() => {
    if (historicalPrices.length === 0 || !dcaResults) return null
    return calculateLumpSum(historicalPrices, dcaResults.totalInvested, startDate)
  }, [historicalPrices, dcaResults, startDate])

  const handleRecalculate = useCallback(() => {
    setIsCalculating(true)
    setTimeout(() => {
      setHistoricalPrices(generateHistoricalPrices(asset.price, duration + 30))
      setIsCalculating(false)
    }, 1000)
  }, [asset, duration])

  const formatCurrency = (value) => {
    if (Math.abs(value) >= 1e6) return '$' + (value / 1e6).toFixed(2) + 'M'
    if (Math.abs(value) >= 1e3) return '$' + (value / 1e3).toFixed(2) + 'K'
    return '$' + value.toFixed(2)
  }

  const formatPercent = (value) => {
    const prefix = value >= 0 ? '+' : ''
    return prefix + value.toFixed(2) + '%'
  }

  // Future projection calculation
  const futureValue = useMemo(() => {
    if (!dcaResults) return null

    const years = 5
    const monthlyContribution = dcaAmount * (30 / FREQUENCIES[frequency].days)
    const monthlyRate = futureProjection / 100 / 12

    let fv = dcaResults.currentValue
    const projections = []

    for (let year = 1; year <= years; year++) {
      for (let month = 0; month < 12; month++) {
        fv = fv * (1 + monthlyRate) + monthlyContribution
      }
      projections.push({
        year,
        value: fv,
        invested: dcaResults.totalInvested + (year * 12 * monthlyContribution)
      })
    }

    return projections
  }, [dcaResults, dcaAmount, frequency, futureProjection])

  return (
    <div className="min-h-screen bg-[#0a0e14] text-white p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2 flex items-center gap-3">
          <Calculator className="w-8 h-8 text-cyan-400" />
          DCA Calculator
        </h1>
        <p className="text-white/60">Calculate and visualize dollar-cost averaging strategies</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Settings Panel */}
        <div className="space-y-4">
          <div className="bg-white/5 rounded-xl border border-white/10 p-4">
            <h3 className="font-medium mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5 text-cyan-400" />
              DCA Settings
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm text-white/60 mb-2">Asset</label>
                <select
                  value={selectedAsset}
                  onChange={(e) => setSelectedAsset(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                >
                  {ASSETS.map(a => (
                    <option key={a.symbol} value={a.symbol} className="bg-[#0a0e14]">
                      {a.symbol} - {a.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Investment Amount ($)</label>
                <input
                  type="number"
                  value={dcaAmount}
                  onChange={(e) => setDcaAmount(parseFloat(e.target.value) || 0)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Frequency</label>
                <select
                  value={frequency}
                  onChange={(e) => setFrequency(e.target.value)}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                >
                  {Object.entries(FREQUENCIES).map(([key, freq]) => (
                    <option key={key} value={key} className="bg-[#0a0e14]">{freq.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-white/60 mb-2">Backtest Period (Days)</label>
                <select
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value))}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                >
                  <option value={90} className="bg-[#0a0e14]">3 Months</option>
                  <option value={180} className="bg-[#0a0e14]">6 Months</option>
                  <option value={365} className="bg-[#0a0e14]">1 Year</option>
                  <option value={730} className="bg-[#0a0e14]">2 Years</option>
                  <option value={1095} className="bg-[#0a0e14]">3 Years</option>
                </select>
              </div>

              <button
                onClick={handleRecalculate}
                disabled={isCalculating}
                className="w-full py-3 bg-cyan-500 hover:bg-cyan-600 disabled:bg-white/10 rounded-lg font-medium flex items-center justify-center gap-2"
              >
                {isCalculating ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Calculating...
                  </>
                ) : (
                  <>
                    <Calculator className="w-5 h-5" />
                    Recalculate
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Advanced Settings */}
          <div className="bg-white/5 rounded-xl border border-white/10 overflow-hidden">
            <button
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="w-full p-4 flex items-center justify-between hover:bg-white/5"
            >
              <span className="font-medium">Future Projection Settings</span>
              {showAdvanced ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
            </button>
            {showAdvanced && (
              <div className="p-4 pt-0">
                <div>
                  <label className="block text-sm text-white/60 mb-2">
                    Expected Annual Return (%)
                  </label>
                  <input
                    type="number"
                    value={futureProjection}
                    onChange={(e) => setFutureProjection(parseFloat(e.target.value) || 0)}
                    className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 focus:outline-none"
                  />
                </div>
                <p className="text-xs text-white/40 mt-2">
                  Used for projecting future portfolio value. Historical crypto returns have varied significantly.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Results */}
        <div className="lg:col-span-2 space-y-6">
          {dcaResults && (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <div className="text-white/60 text-sm mb-1">Total Invested</div>
                  <div className="text-xl font-bold">{formatCurrency(dcaResults.totalInvested)}</div>
                  <div className="text-sm text-white/60">{dcaResults.numPurchases} purchases</div>
                </div>

                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <div className="text-white/60 text-sm mb-1">Current Value</div>
                  <div className="text-xl font-bold">{formatCurrency(dcaResults.currentValue)}</div>
                  <div className="text-sm text-white/60">{dcaResults.totalCoins.toFixed(6)} {selectedAsset}</div>
                </div>

                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <div className="text-white/60 text-sm mb-1">Total P&L</div>
                  <div className={`text-xl font-bold ${dcaResults.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(dcaResults.pnl)}
                  </div>
                  <div className={`text-sm ${dcaResults.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatPercent(dcaResults.pnlPercent)}
                  </div>
                </div>

                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <div className="text-white/60 text-sm mb-1">Avg Buy Price</div>
                  <div className="text-xl font-bold">${dcaResults.avgPrice.toFixed(2)}</div>
                  <div className="text-sm text-white/60">Current: ${dcaResults.currentPrice.toFixed(2)}</div>
                </div>
              </div>

              {/* DCA vs Lump Sum Comparison */}
              {lumpSumResults && (
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <h3 className="font-medium mb-4 flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-cyan-400" />
                    DCA vs Lump Sum Comparison
                  </h3>

                  <div className="grid grid-cols-2 gap-6">
                    <div className="bg-cyan-500/10 rounded-lg p-4 border border-cyan-500/20">
                      <div className="text-cyan-400 font-medium mb-3">DCA Strategy</div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-white/60">Invested</span>
                          <span>{formatCurrency(dcaResults.totalInvested)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-white/60">Avg Price</span>
                          <span>${dcaResults.avgPrice.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-white/60">Current Value</span>
                          <span>{formatCurrency(dcaResults.currentValue)}</span>
                        </div>
                        <div className="flex justify-between border-t border-white/10 pt-2">
                          <span className="text-white/60">Return</span>
                          <span className={dcaResults.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                            {formatPercent(dcaResults.pnlPercent)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <div className="text-white/60 font-medium mb-3">Lump Sum (Same Amount)</div>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-white/60">Invested</span>
                          <span>{formatCurrency(lumpSumResults.invested)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-white/60">Buy Price</span>
                          <span>${lumpSumResults.buyPrice.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-white/60">Current Value</span>
                          <span>{formatCurrency(lumpSumResults.currentValue)}</span>
                        </div>
                        <div className="flex justify-between border-t border-white/10 pt-2">
                          <span className="text-white/60">Return</span>
                          <span className={lumpSumResults.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                            {formatPercent(lumpSumResults.pnlPercent)}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className={`mt-4 p-3 rounded-lg ${dcaResults.pnlPercent > lumpSumResults.pnlPercent ? 'bg-green-500/10 border border-green-500/20' : 'bg-yellow-500/10 border border-yellow-500/20'}`}>
                    <div className="flex items-center gap-2">
                      {dcaResults.pnlPercent > lumpSumResults.pnlPercent ? (
                        <>
                          <ArrowUpRight className="w-5 h-5 text-green-400" />
                          <span className="text-green-400 font-medium">
                            DCA outperformed by {(dcaResults.pnlPercent - lumpSumResults.pnlPercent).toFixed(2)}%
                          </span>
                        </>
                      ) : (
                        <>
                          <ArrowDownRight className="w-5 h-5 text-yellow-400" />
                          <span className="text-yellow-400 font-medium">
                            Lump Sum outperformed by {(lumpSumResults.pnlPercent - dcaResults.pnlPercent).toFixed(2)}%
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Future Projection */}
              {futureValue && (
                <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                  <h3 className="font-medium mb-4 flex items-center gap-2">
                    <Target className="w-5 h-5 text-cyan-400" />
                    5-Year Projection ({futureProjection}% annual return)
                  </h3>

                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-white/10">
                          <th className="text-left p-3 text-white/60 font-medium">Year</th>
                          <th className="text-right p-3 text-white/60 font-medium">Total Invested</th>
                          <th className="text-right p-3 text-white/60 font-medium">Projected Value</th>
                          <th className="text-right p-3 text-white/60 font-medium">Gain</th>
                        </tr>
                      </thead>
                      <tbody>
                        {futureValue.map((proj, idx) => (
                          <tr key={idx} className="border-b border-white/5">
                            <td className="p-3">Year {proj.year}</td>
                            <td className="p-3 text-right">{formatCurrency(proj.invested)}</td>
                            <td className="p-3 text-right font-medium">{formatCurrency(proj.value)}</td>
                            <td className="p-3 text-right text-green-400">
                              {formatCurrency(proj.value - proj.invested)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Purchase History */}
              <div className="bg-white/5 rounded-xl border border-white/10 p-4">
                <h3 className="font-medium mb-4 flex items-center gap-2">
                  <Clock className="w-5 h-5 text-cyan-400" />
                  Purchase History (Last 10)
                </h3>

                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-white/10">
                        <th className="text-left p-3 text-white/60 font-medium">Date</th>
                        <th className="text-right p-3 text-white/60 font-medium">Price</th>
                        <th className="text-right p-3 text-white/60 font-medium">Amount</th>
                        <th className="text-right p-3 text-white/60 font-medium">Coins</th>
                        <th className="text-right p-3 text-white/60 font-medium">Avg Price</th>
                        <th className="text-right p-3 text-white/60 font-medium">Total Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dcaResults.purchases.slice(-10).reverse().map((purchase, idx) => (
                        <tr key={idx} className="border-b border-white/5 hover:bg-white/5">
                          <td className="p-3">{purchase.date.toLocaleDateString()}</td>
                          <td className="p-3 text-right">${purchase.price.toFixed(2)}</td>
                          <td className="p-3 text-right">{formatCurrency(purchase.amount)}</td>
                          <td className="p-3 text-right">{purchase.coins.toFixed(6)}</td>
                          <td className="p-3 text-right">${purchase.avgPrice.toFixed(2)}</td>
                          <td className="p-3 text-right">{formatCurrency(purchase.currentValue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Info Banner */}
      <div className="mt-6 p-4 bg-white/5 rounded-xl border border-white/10">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-cyan-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <div className="font-medium text-white mb-1">About Dollar-Cost Averaging</div>
            <p>
              DCA is an investment strategy where you invest a fixed amount at regular intervals,
              regardless of price. This approach reduces the impact of volatility and removes the
              pressure of timing the market. Historical simulations use simplified price models -
              actual results may vary.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DCACalculator
