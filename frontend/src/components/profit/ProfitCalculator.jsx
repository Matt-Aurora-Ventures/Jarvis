import React, { useState, useMemo } from 'react'
import {
  Calculator, TrendingUp, TrendingDown, DollarSign, Percent, Target,
  ArrowRight, BarChart2, PieChart, Info, Plus, Trash2, Edit3,
  RefreshCw, Download, ChevronDown, Check
} from 'lucide-react'

const COMMON_TOKENS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'AVAX', 'DOT', 'MATIC', 'LINK', 'UNI', 'AAVE']

export function ProfitCalculator() {
  const [mode, setMode] = useState('simple') // simple, advanced, batch
  const [trades, setTrades] = useState([
    { id: 1, token: 'BTC', buyPrice: 65000, sellPrice: 70000, amount: 0.5, fees: 0.1 }
  ])

  // Simple mode state
  const [simpleToken, setSimpleToken] = useState('BTC')
  const [buyPrice, setBuyPrice] = useState('')
  const [sellPrice, setSellPrice] = useState('')
  const [investmentAmount, setInvestmentAmount] = useState('')
  const [feePercent, setFeePercent] = useState(0.1)

  // Target price mode
  const [targetMode, setTargetMode] = useState('price') // price, percent, profit
  const [targetValue, setTargetValue] = useState('')

  // Calculate simple mode results
  const simpleResults = useMemo(() => {
    const buy = parseFloat(buyPrice) || 0
    const sell = parseFloat(sellPrice) || 0
    const investment = parseFloat(investmentAmount) || 0

    if (!buy || !investment) return null

    const tokenAmount = investment / buy
    const grossProceeds = tokenAmount * sell
    const buyFee = investment * (feePercent / 100)
    const sellFee = grossProceeds * (feePercent / 100)
    const totalFees = buyFee + sellFee
    const netProfit = grossProceeds - investment - totalFees
    const percentGain = ((sell - buy) / buy) * 100
    const roi = (netProfit / investment) * 100

    // Break-even price
    const breakEvenPrice = buy * (1 + (feePercent * 2) / 100)

    return {
      tokenAmount,
      grossProceeds,
      buyFee,
      sellFee,
      totalFees,
      netProfit,
      percentGain,
      roi,
      breakEvenPrice
    }
  }, [buyPrice, sellPrice, investmentAmount, feePercent])

  // Calculate target based on mode
  const targetResults = useMemo(() => {
    const buy = parseFloat(buyPrice) || 0
    const investment = parseFloat(investmentAmount) || 0
    const target = parseFloat(targetValue) || 0

    if (!buy || !investment || !target) return null

    let targetPrice
    if (targetMode === 'price') {
      targetPrice = target
    } else if (targetMode === 'percent') {
      targetPrice = buy * (1 + target / 100)
    } else {
      // profit mode - solve for price that gives target profit
      // profit = (tokenAmount * price) - investment - fees
      // target = (investment/buy * price) - investment - fees
      const tokenAmount = investment / buy
      // Simplified: targetPrice = (target + investment + fees) / tokenAmount
      const estFees = investment * (feePercent / 100) * 2
      targetPrice = (target + investment + estFees) / tokenAmount
    }

    const tokenAmount = investment / buy
    const grossProceeds = tokenAmount * targetPrice
    const totalFees = (investment + grossProceeds) * (feePercent / 100)
    const netProfit = grossProceeds - investment - totalFees
    const percentGain = ((targetPrice - buy) / buy) * 100
    const roi = (netProfit / investment) * 100

    return {
      targetPrice,
      tokenAmount,
      grossProceeds,
      totalFees,
      netProfit,
      percentGain,
      roi
    }
  }, [buyPrice, investmentAmount, targetValue, targetMode, feePercent])

  // Batch mode calculations
  const batchResults = useMemo(() => {
    let totalInvested = 0
    let totalProceeds = 0
    let totalFees = 0
    let totalProfit = 0

    trades.forEach(trade => {
      const invested = trade.buyPrice * trade.amount
      const proceeds = trade.sellPrice * trade.amount
      const fees = (invested + proceeds) * (trade.fees / 100)
      const profit = proceeds - invested - fees

      totalInvested += invested
      totalProceeds += proceeds
      totalFees += fees
      totalProfit += profit
    })

    return {
      totalInvested,
      totalProceeds,
      totalFees,
      totalProfit,
      totalROI: totalInvested > 0 ? (totalProfit / totalInvested) * 100 : 0,
      tradeCount: trades.length
    }
  }, [trades])

  const addTrade = () => {
    setTrades(prev => [...prev, {
      id: Date.now(),
      token: 'ETH',
      buyPrice: 0,
      sellPrice: 0,
      amount: 0,
      fees: 0.1
    }])
  }

  const updateTrade = (id, field, value) => {
    setTrades(prev => prev.map(t =>
      t.id === id ? { ...t, [field]: value } : t
    ))
  }

  const removeTrade = (id) => {
    if (trades.length > 1) {
      setTrades(prev => prev.filter(t => t.id !== id))
    }
  }

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(value)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Calculator className="w-6 h-6 text-green-400" />
          <h2 className="text-xl font-bold">Profit Calculator</h2>
        </div>
      </div>

      {/* Mode Tabs */}
      <div className="flex items-center gap-2 bg-white/5 rounded-lg p-1">
        {[
          { key: 'simple', label: 'Simple' },
          { key: 'target', label: 'Target Price' },
          { key: 'batch', label: 'Batch Trades' }
        ].map(m => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`flex-1 py-2 px-4 rounded-lg transition ${
              mode === m.key
                ? 'bg-white/10 text-white'
                : 'text-white/60 hover:text-white'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Simple Mode */}
      {mode === 'simple' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Inputs */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-semibold">Trade Details</h3>

            <div>
              <label className="block text-sm text-white/60 mb-2">Token</label>
              <select
                value={simpleToken}
                onChange={(e) => setSimpleToken(e.target.value)}
                className="w-full px-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
              >
                {COMMON_TOKENS.map(t => (
                  <option key={t} value={t} className="bg-[#0a0e14]">{t}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-white/60 mb-2">Buy Price</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="number"
                    value={buyPrice}
                    onChange={(e) => setBuyPrice(e.target.value)}
                    placeholder="0.00"
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm text-white/60 mb-2">Sell Price</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  <input
                    type="number"
                    value={sellPrice}
                    onChange={(e) => setSellPrice(e.target.value)}
                    placeholder="0.00"
                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">Investment Amount</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <input
                  type="number"
                  value={investmentAmount}
                  onChange={(e) => setInvestmentAmount(e.target.value)}
                  placeholder="1000"
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">Trading Fee (%)</label>
              <div className="relative">
                <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <input
                  type="number"
                  step="0.01"
                  value={feePercent}
                  onChange={(e) => setFeePercent(parseFloat(e.target.value) || 0)}
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="space-y-4">
            {simpleResults ? (
              <>
                <div className={`border rounded-xl p-6 ${
                  simpleResults.netProfit >= 0
                    ? 'bg-green-500/10 border-green-500/20'
                    : 'bg-red-500/10 border-red-500/20'
                }`}>
                  <div className="text-sm text-white/60 mb-1">Net Profit/Loss</div>
                  <div className={`text-4xl font-bold ${
                    simpleResults.netProfit >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {simpleResults.netProfit >= 0 ? '+' : ''}{formatCurrency(simpleResults.netProfit)}
                  </div>
                  <div className={`text-lg ${simpleResults.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {simpleResults.roi >= 0 ? '+' : ''}{simpleResults.roi.toFixed(2)}% ROI
                  </div>
                </div>

                <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-3">
                  <div className="flex justify-between">
                    <span className="text-white/60">Tokens Purchased</span>
                    <span className="font-medium">{simpleResults.tokenAmount.toFixed(6)} {simpleToken}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Price Change</span>
                    <span className={`font-medium ${simpleResults.percentGain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {simpleResults.percentGain >= 0 ? '+' : ''}{simpleResults.percentGain.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Gross Proceeds</span>
                    <span className="font-medium">{formatCurrency(simpleResults.grossProceeds)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Total Fees</span>
                    <span className="font-medium text-red-400">-{formatCurrency(simpleResults.totalFees)}</span>
                  </div>
                  <div className="flex justify-between pt-3 border-t border-white/10">
                    <span className="text-white/60">Break-even Price</span>
                    <span className="font-medium">{formatCurrency(simpleResults.breakEvenPrice)}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-white/5 border border-white/10 rounded-xl p-12 text-center text-white/40">
                <Calculator className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Enter trade details to calculate profit</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Target Price Mode */}
      {mode === 'target' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Inputs */}
          <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-4">
            <h3 className="text-lg font-semibold">Set Your Target</h3>

            <div>
              <label className="block text-sm text-white/60 mb-2">Buy Price</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <input
                  type="number"
                  value={buyPrice}
                  onChange={(e) => setBuyPrice(e.target.value)}
                  placeholder="Current price"
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">Investment Amount</label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <input
                  type="number"
                  value={investmentAmount}
                  onChange={(e) => setInvestmentAmount(e.target.value)}
                  placeholder="1000"
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">Target Type</label>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { key: 'price', label: 'Target Price', icon: DollarSign },
                  { key: 'percent', label: 'Target %', icon: Percent },
                  { key: 'profit', label: 'Target Profit', icon: Target }
                ].map(t => (
                  <button
                    key={t.key}
                    onClick={() => setTargetMode(t.key)}
                    className={`p-3 rounded-lg text-sm transition ${
                      targetMode === t.key
                        ? 'bg-green-500/20 text-green-400 border border-green-500/50'
                        : 'bg-white/5 border border-white/10 hover:bg-white/10'
                    }`}
                  >
                    <t.icon className="w-4 h-4 mx-auto mb-1" />
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm text-white/60 mb-2">
                {targetMode === 'price' ? 'Target Sell Price' :
                 targetMode === 'percent' ? 'Target Gain (%)' :
                 'Target Profit ($)'}
              </label>
              <div className="relative">
                {targetMode === 'percent' ? (
                  <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                ) : (
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                )}
                <input
                  type="number"
                  value={targetValue}
                  onChange={(e) => setTargetValue(e.target.value)}
                  placeholder={targetMode === 'percent' ? '50' : '0.00'}
                  className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Results */}
          <div className="space-y-4">
            {targetResults ? (
              <>
                <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-6">
                  <div className="text-sm text-white/60 mb-1">Required Sell Price</div>
                  <div className="text-4xl font-bold text-green-400">
                    {formatCurrency(targetResults.targetPrice)}
                  </div>
                  <div className="text-lg text-green-400">
                    +{targetResults.percentGain.toFixed(2)}% from entry
                  </div>
                </div>

                <div className="bg-white/5 border border-white/10 rounded-xl p-6 space-y-3">
                  <div className="flex justify-between">
                    <span className="text-white/60">Expected Profit</span>
                    <span className="font-medium text-green-400">{formatCurrency(targetResults.netProfit)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Expected ROI</span>
                    <span className="font-medium text-green-400">+{targetResults.roi.toFixed(2)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Gross Proceeds</span>
                    <span className="font-medium">{formatCurrency(targetResults.grossProceeds)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-white/60">Est. Fees</span>
                    <span className="font-medium text-red-400">-{formatCurrency(targetResults.totalFees)}</span>
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-white/5 border border-white/10 rounded-xl p-12 text-center text-white/40">
                <Target className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>Set your target to see required price</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Batch Mode */}
      {mode === 'batch' && (
        <div className="space-y-6">
          {/* Trades List */}
          <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10 text-left text-sm text-white/60">
                  <th className="px-4 py-3">Token</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3">Buy Price</th>
                  <th className="px-4 py-3">Sell Price</th>
                  <th className="px-4 py-3">Fee %</th>
                  <th className="px-4 py-3">Profit</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {trades.map(trade => {
                  const invested = trade.buyPrice * trade.amount
                  const proceeds = trade.sellPrice * trade.amount
                  const fees = (invested + proceeds) * (trade.fees / 100)
                  const profit = proceeds - invested - fees

                  return (
                    <tr key={trade.id} className="border-b border-white/5">
                      <td className="px-4 py-3">
                        <select
                          value={trade.token}
                          onChange={(e) => updateTrade(trade.id, 'token', e.target.value)}
                          className="px-2 py-1 bg-white/5 border border-white/10 rounded focus:outline-none text-sm"
                        >
                          {COMMON_TOKENS.map(t => (
                            <option key={t} value={t} className="bg-[#0a0e14]">{t}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={trade.amount}
                          onChange={(e) => updateTrade(trade.id, 'amount', parseFloat(e.target.value) || 0)}
                          className="w-24 px-2 py-1 bg-white/5 border border-white/10 rounded focus:outline-none text-sm"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={trade.buyPrice}
                          onChange={(e) => updateTrade(trade.id, 'buyPrice', parseFloat(e.target.value) || 0)}
                          className="w-28 px-2 py-1 bg-white/5 border border-white/10 rounded focus:outline-none text-sm"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={trade.sellPrice}
                          onChange={(e) => updateTrade(trade.id, 'sellPrice', parseFloat(e.target.value) || 0)}
                          className="w-28 px-2 py-1 bg-white/5 border border-white/10 rounded focus:outline-none text-sm"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          step="0.01"
                          value={trade.fees}
                          onChange={(e) => updateTrade(trade.id, 'fees', parseFloat(e.target.value) || 0)}
                          className="w-16 px-2 py-1 bg-white/5 border border-white/10 rounded focus:outline-none text-sm"
                        />
                      </td>
                      <td className={`px-4 py-3 font-medium ${profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {profit >= 0 ? '+' : ''}{formatCurrency(profit)}
                      </td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => removeTrade(trade.id)}
                          className="p-1 text-white/40 hover:text-red-400 transition"
                          disabled={trades.length <= 1}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <button
            onClick={addTrade}
            className="w-full py-3 bg-white/5 border border-white/10 rounded-lg hover:bg-white/10 transition flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Trade
          </button>

          {/* Batch Summary */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="text-white/60 text-sm mb-1">Trades</div>
              <div className="text-2xl font-bold">{batchResults.tradeCount}</div>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="text-white/60 text-sm mb-1">Total Invested</div>
              <div className="text-xl font-bold">{formatCurrency(batchResults.totalInvested)}</div>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="text-white/60 text-sm mb-1">Total Proceeds</div>
              <div className="text-xl font-bold">{formatCurrency(batchResults.totalProceeds)}</div>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-xl p-4">
              <div className="text-white/60 text-sm mb-1">Total Fees</div>
              <div className="text-xl font-bold text-red-400">-{formatCurrency(batchResults.totalFees)}</div>
            </div>
            <div className={`border rounded-xl p-4 ${
              batchResults.totalProfit >= 0
                ? 'bg-green-500/10 border-green-500/20'
                : 'bg-red-500/10 border-red-500/20'
            }`}>
              <div className="text-white/60 text-sm mb-1">Net Profit</div>
              <div className={`text-xl font-bold ${batchResults.totalProfit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {batchResults.totalProfit >= 0 ? '+' : ''}{formatCurrency(batchResults.totalProfit)}
              </div>
              <div className={`text-sm ${batchResults.totalROI >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {batchResults.totalROI >= 0 ? '+' : ''}{batchResults.totalROI.toFixed(2)}% ROI
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Info */}
      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-white/70">
            <p className="font-medium text-blue-400 mb-1">Calculator Modes</p>
            <ul className="list-disc list-inside space-y-1 text-white/60">
              <li><strong>Simple:</strong> Calculate profit from a single buy/sell trade</li>
              <li><strong>Target Price:</strong> Find the sell price needed for your profit goal</li>
              <li><strong>Batch Trades:</strong> Calculate total P&L across multiple trades</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProfitCalculator
