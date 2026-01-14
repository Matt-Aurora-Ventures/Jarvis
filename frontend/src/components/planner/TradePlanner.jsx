import React, { useState, useMemo } from 'react'
import {
  Target, TrendingUp, TrendingDown, DollarSign, Percent, AlertTriangle,
  PlusCircle, Trash2, Save, Download, Upload, Copy, CheckCircle,
  ArrowUpRight, ArrowDownRight, Scale, Clock, BarChart3, Zap,
  ChevronDown, ChevronUp, Edit2, Eye, Share2, Bookmark
} from 'lucide-react'

const TOKENS = [
  { symbol: 'BTC', name: 'Bitcoin', price: 95420 },
  { symbol: 'ETH', name: 'Ethereum', price: 3280 },
  { symbol: 'SOL', name: 'Solana', price: 185 },
  { symbol: 'BNB', name: 'BNB', price: 680 },
  { symbol: 'XRP', name: 'Ripple', price: 2.45 },
  { symbol: 'AVAX', name: 'Avalanche', price: 38.50 },
  { symbol: 'DOGE', name: 'Dogecoin', price: 0.38 },
  { symbol: 'LINK', name: 'Chainlink', price: 22.40 },
  { symbol: 'DOT', name: 'Polkadot', price: 7.85 },
  { symbol: 'ADA', name: 'Cardano', price: 0.95 }
]

const ENTRY_CONDITIONS = [
  'Price breaks resistance',
  'Price bounces from support',
  'RSI oversold (<30)',
  'RSI overbought (>70)',
  'MACD crossover',
  'Volume spike',
  'Bullish divergence',
  'Bearish divergence',
  'Moving average cross',
  'Breakout with volume',
  'Pullback to EMA',
  'Double bottom pattern',
  'Head and shoulders',
  'Funding rate extreme'
]

export function TradePlanner() {
  const [mode, setMode] = useState('create') // create, saved, templates
  const [selectedToken, setSelectedToken] = useState('BTC')
  const [tradeDirection, setTradeDirection] = useState('long') // long, short
  const [accountSize, setAccountSize] = useState(10000)
  const [riskPercent, setRiskPercent] = useState(2)

  // Trade plan state
  const [entryPrice, setEntryPrice] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfits, setTakeProfits] = useState([{ price: '', percent: 50 }])
  const [entryConditions, setEntryConditions] = useState([])
  const [notes, setNotes] = useState('')
  const [scalingEntries, setScalingEntries] = useState([])

  // Saved plans
  const [savedPlans, setSavedPlans] = useState([
    {
      id: 1,
      name: 'BTC Breakout Play',
      token: 'BTC',
      direction: 'long',
      entry: 95000,
      stopLoss: 93500,
      takeProfits: [{ price: 98000, percent: 50 }, { price: 102000, percent: 50 }],
      status: 'pending',
      created: '2024-01-10'
    },
    {
      id: 2,
      name: 'ETH Support Bounce',
      token: 'ETH',
      direction: 'long',
      entry: 3200,
      stopLoss: 3100,
      takeProfits: [{ price: 3400, percent: 100 }],
      status: 'active',
      created: '2024-01-09'
    }
  ])

  const currentToken = TOKENS.find(t => t.symbol === selectedToken)
  const currentPrice = currentToken?.price || 0

  // Calculate trade metrics
  const tradeMetrics = useMemo(() => {
    const entry = parseFloat(entryPrice) || currentPrice
    const sl = parseFloat(stopLoss) || 0

    if (!entry || !sl) {
      return {
        riskAmount: 0,
        positionSize: 0,
        stopLossPercent: 0,
        riskReward: 0,
        breakEven: 0,
        avgTakeProfit: 0,
        potentialProfit: 0
      }
    }

    const riskAmount = accountSize * (riskPercent / 100)
    const stopLossPercent = Math.abs((sl - entry) / entry) * 100
    const stopLossDistance = Math.abs(entry - sl)
    const positionSize = stopLossDistance > 0 ? riskAmount / stopLossDistance : 0
    const positionValue = positionSize * entry

    // Calculate weighted average take profit
    const validTPs = takeProfits.filter(tp => tp.price)
    let weightedTP = 0
    let totalWeight = 0
    validTPs.forEach(tp => {
      weightedTP += parseFloat(tp.price) * (tp.percent / 100)
      totalWeight += tp.percent / 100
    })
    const avgTakeProfit = totalWeight > 0 ? weightedTP / totalWeight : 0

    // Calculate potential profit
    let potentialProfit = 0
    validTPs.forEach(tp => {
      const tpPrice = parseFloat(tp.price)
      const profit = tradeDirection === 'long'
        ? (tpPrice - entry) * positionSize * (tp.percent / 100)
        : (entry - tpPrice) * positionSize * (tp.percent / 100)
      potentialProfit += profit
    })

    // Risk/Reward ratio
    const avgProfitDistance = Math.abs(avgTakeProfit - entry)
    const riskReward = stopLossDistance > 0 ? avgProfitDistance / stopLossDistance : 0

    // Break-even price after fees (assuming 0.1% fee)
    const fees = positionValue * 0.001 * 2 // Entry + exit
    const breakEven = tradeDirection === 'long'
      ? entry + (fees / positionSize)
      : entry - (fees / positionSize)

    return {
      riskAmount,
      positionSize,
      positionValue,
      stopLossPercent,
      riskReward,
      breakEven,
      avgTakeProfit,
      potentialProfit
    }
  }, [entryPrice, stopLoss, takeProfits, accountSize, riskPercent, currentPrice, tradeDirection])

  const addTakeProfit = () => {
    if (takeProfits.length < 5) {
      const remainingPercent = 100 - takeProfits.reduce((sum, tp) => sum + tp.percent, 0)
      setTakeProfits([...takeProfits, { price: '', percent: Math.max(0, remainingPercent) }])
    }
  }

  const removeTakeProfit = (index) => {
    if (takeProfits.length > 1) {
      setTakeProfits(takeProfits.filter((_, i) => i !== index))
    }
  }

  const updateTakeProfit = (index, field, value) => {
    const newTPs = [...takeProfits]
    newTPs[index][field] = field === 'percent' ? Math.min(100, Math.max(0, value)) : value
    setTakeProfits(newTPs)
  }

  const addScalingEntry = () => {
    setScalingEntries([...scalingEntries, { price: '', percent: 25 }])
  }

  const savePlan = () => {
    const newPlan = {
      id: Date.now(),
      name: `${selectedToken} ${tradeDirection.toUpperCase()} Plan`,
      token: selectedToken,
      direction: tradeDirection,
      entry: parseFloat(entryPrice) || currentPrice,
      stopLoss: parseFloat(stopLoss),
      takeProfits: takeProfits.filter(tp => tp.price),
      conditions: entryConditions,
      notes,
      status: 'pending',
      created: new Date().toLocaleDateString()
    }
    setSavedPlans([newPlan, ...savedPlans])
  }

  const formatPrice = (price) => {
    if (!price) return '-'
    return price < 1 ? `$${price.toFixed(6)}` : `$${price.toLocaleString()}`
  }

  return (
    <div className="p-6 bg-[#0a0e14] min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-500/20 rounded-lg">
            <Target className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Trade Planner</h1>
            <p className="text-sm text-gray-400">Plan entries, exits, and risk management</p>
          </div>
        </div>
        <div className="flex gap-2">
          {['create', 'saved', 'templates'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
                mode === m ? 'bg-indigo-500 text-white' : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Create Mode */}
      {mode === 'create' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Trade Setup */}
          <div className="lg:col-span-2 space-y-6">
            {/* Basic Setup */}
            <div className="bg-white/5 rounded-xl border border-white/10 p-6">
              <h3 className="font-semibold text-white mb-4">Trade Setup</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Token</label>
                  <select
                    value={selectedToken}
                    onChange={(e) => setSelectedToken(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
                  >
                    {TOKENS.map(t => (
                      <option key={t.symbol} value={t.symbol}>{t.symbol}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Direction</label>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setTradeDirection('long')}
                      className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                        tradeDirection === 'long'
                          ? 'bg-green-500 text-white'
                          : 'bg-white/10 text-gray-400 hover:bg-white/20'
                      }`}
                    >
                      Long
                    </button>
                    <button
                      onClick={() => setTradeDirection('short')}
                      className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
                        tradeDirection === 'short'
                          ? 'bg-red-500 text-white'
                          : 'bg-white/10 text-gray-400 hover:bg-white/20'
                      }`}
                    >
                      Short
                    </button>
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Current Price</label>
                  <div className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-white">
                    ${currentPrice.toLocaleString()}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Entry Price</label>
                  <input
                    type="number"
                    value={entryPrice}
                    onChange={(e) => setEntryPrice(e.target.value)}
                    placeholder={currentPrice.toString()}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
                  />
                </div>
              </div>
            </div>

            {/* Stop Loss */}
            <div className="bg-red-500/10 rounded-xl border border-red-500/30 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  Stop Loss
                </h3>
                <span className="text-sm text-red-400">
                  Risk: {tradeMetrics.stopLossPercent.toFixed(2)}%
                </span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Stop Loss Price</label>
                  <input
                    type="number"
                    value={stopLoss}
                    onChange={(e) => setStopLoss(e.target.value)}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
                    placeholder="Enter stop loss"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Quick Set</label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 5].map(pct => {
                      const entry = parseFloat(entryPrice) || currentPrice
                      const sl = tradeDirection === 'long'
                        ? entry * (1 - pct / 100)
                        : entry * (1 + pct / 100)
                      return (
                        <button
                          key={pct}
                          onClick={() => setStopLoss(sl.toFixed(2))}
                          className="flex-1 py-2 bg-white/10 rounded text-sm text-gray-300 hover:bg-white/20"
                        >
                          {pct}%
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* Take Profits */}
            <div className="bg-green-500/10 rounded-xl border border-green-500/30 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-white flex items-center gap-2">
                  <Target className="w-5 h-5 text-green-400" />
                  Take Profit Targets
                </h3>
                <button
                  onClick={addTakeProfit}
                  disabled={takeProfits.length >= 5}
                  className="px-3 py-1 bg-green-500/20 text-green-400 rounded text-sm hover:bg-green-500/30 disabled:opacity-50"
                >
                  <PlusCircle className="w-4 h-4 inline mr-1" />
                  Add TP
                </button>
              </div>
              <div className="space-y-3">
                {takeProfits.map((tp, idx) => {
                  const entry = parseFloat(entryPrice) || currentPrice
                  const tpPrice = parseFloat(tp.price)
                  const profitPercent = tpPrice
                    ? tradeDirection === 'long'
                      ? ((tpPrice - entry) / entry) * 100
                      : ((entry - tpPrice) / entry) * 100
                    : 0

                  return (
                    <div key={idx} className="flex items-center gap-4 p-3 bg-white/5 rounded-lg">
                      <span className="text-green-400 font-semibold">TP{idx + 1}</span>
                      <div className="flex-1">
                        <input
                          type="number"
                          value={tp.price}
                          onChange={(e) => updateTakeProfit(idx, 'price', e.target.value)}
                          placeholder="Price"
                          className="w-full bg-white/10 border border-white/20 rounded px-3 py-1.5 text-white"
                        />
                      </div>
                      <div className="w-24">
                        <input
                          type="number"
                          value={tp.percent}
                          onChange={(e) => updateTakeProfit(idx, 'percent', Number(e.target.value))}
                          className="w-full bg-white/10 border border-white/20 rounded px-3 py-1.5 text-white text-center"
                        />
                        <span className="text-xs text-gray-500 block text-center">% of pos</span>
                      </div>
                      <div className="w-20 text-right">
                        <span className={profitPercent >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {profitPercent >= 0 ? '+' : ''}{profitPercent.toFixed(1)}%
                        </span>
                      </div>
                      {takeProfits.length > 1 && (
                        <button
                          onClick={() => removeTakeProfit(idx)}
                          className="p-1 text-red-400 hover:bg-red-500/20 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  )
                })}
              </div>
              <div className="mt-4 flex justify-between text-sm text-gray-400">
                <span>Total allocation: {takeProfits.reduce((sum, tp) => sum + tp.percent, 0)}%</span>
                {takeProfits.reduce((sum, tp) => sum + tp.percent, 0) !== 100 && (
                  <span className="text-yellow-400">Should equal 100%</span>
                )}
              </div>
            </div>

            {/* Entry Conditions */}
            <div className="bg-white/5 rounded-xl border border-white/10 p-6">
              <h3 className="font-semibold text-white mb-4 flex items-center gap-2">
                <Zap className="w-5 h-5 text-yellow-400" />
                Entry Conditions
              </h3>
              <div className="flex flex-wrap gap-2">
                {ENTRY_CONDITIONS.map(condition => (
                  <button
                    key={condition}
                    onClick={() => {
                      if (entryConditions.includes(condition)) {
                        setEntryConditions(entryConditions.filter(c => c !== condition))
                      } else {
                        setEntryConditions([...entryConditions, condition])
                      }
                    }}
                    className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      entryConditions.includes(condition)
                        ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                        : 'bg-white/10 text-gray-400 hover:bg-white/20'
                    }`}
                  >
                    {condition}
                  </button>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div className="bg-white/5 rounded-xl border border-white/10 p-6">
              <h3 className="font-semibold text-white mb-4">Trade Notes</h3>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Add your trade thesis, observations, or reminders..."
                className="w-full h-24 bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white resize-none"
              />
            </div>
          </div>

          {/* Right Column - Metrics & Actions */}
          <div className="space-y-6">
            {/* Account & Risk */}
            <div className="bg-white/5 rounded-xl border border-white/10 p-6">
              <h3 className="font-semibold text-white mb-4">Risk Management</h3>
              <div className="space-y-4">
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Account Size ($)</label>
                  <input
                    type="number"
                    value={accountSize}
                    onChange={(e) => setAccountSize(Number(e.target.value))}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white"
                  />
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-2">Risk per Trade (%)</label>
                  <div className="flex items-center gap-3">
                    <input
                      type="range"
                      min="0.5"
                      max="10"
                      step="0.5"
                      value={riskPercent}
                      onChange={(e) => setRiskPercent(Number(e.target.value))}
                      className="flex-1"
                    />
                    <span className="text-white font-semibold w-12">{riskPercent}%</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Trade Metrics */}
            <div className="bg-indigo-500/10 rounded-xl border border-indigo-500/30 p-6">
              <h3 className="font-semibold text-white mb-4">Trade Metrics</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-400">Risk Amount</span>
                  <span className="text-red-400 font-semibold">
                    ${tradeMetrics.riskAmount.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Position Size</span>
                  <span className="text-white font-semibold">
                    {tradeMetrics.positionSize.toFixed(4)} {selectedToken}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Position Value</span>
                  <span className="text-white font-semibold">
                    ${tradeMetrics.positionValue?.toFixed(2) || '0'}
                  </span>
                </div>
                <div className="border-t border-white/10 pt-3 flex justify-between">
                  <span className="text-gray-400">Risk/Reward</span>
                  <span className={`font-bold ${
                    tradeMetrics.riskReward >= 2 ? 'text-green-400' :
                    tradeMetrics.riskReward >= 1 ? 'text-yellow-400' : 'text-red-400'
                  }`}>
                    1:{tradeMetrics.riskReward.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Potential Profit</span>
                  <span className="text-green-400 font-semibold">
                    ${tradeMetrics.potentialProfit.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Break-Even</span>
                  <span className="text-white">
                    {formatPrice(tradeMetrics.breakEven)}
                  </span>
                </div>
              </div>
            </div>

            {/* R:R Visual */}
            <div className="bg-white/5 rounded-xl border border-white/10 p-6">
              <h3 className="font-semibold text-white mb-4">Risk/Reward Visual</h3>
              <div className="relative h-32">
                {/* Price scale */}
                <div className="absolute left-0 top-0 bottom-0 w-20 flex flex-col justify-between text-xs text-gray-400">
                  {takeProfits[0]?.price && (
                    <span className="text-green-400">{formatPrice(parseFloat(takeProfits[0].price))}</span>
                  )}
                  <span>{formatPrice(parseFloat(entryPrice) || currentPrice)}</span>
                  {stopLoss && (
                    <span className="text-red-400">{formatPrice(parseFloat(stopLoss))}</span>
                  )}
                </div>
                {/* Visual bars */}
                <div className="absolute left-24 right-0 top-0 bottom-0 flex flex-col justify-center gap-2">
                  {takeProfits.filter(tp => tp.price).map((tp, idx) => (
                    <div key={idx} className="flex items-center gap-2">
                      <div className="h-4 bg-green-500/50 rounded" style={{ width: `${Math.min(100, tradeMetrics.riskReward * 50)}%` }} />
                      <span className="text-xs text-green-400">TP{idx + 1}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-2">
                    <div className="h-4 bg-blue-500/50 rounded" style={{ width: '10px' }} />
                    <span className="text-xs text-blue-400">Entry</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="h-4 bg-red-500/50 rounded" style={{ width: '30%' }} />
                    <span className="text-xs text-red-400">SL</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-col gap-2">
              <button
                onClick={savePlan}
                className="w-full py-3 bg-indigo-500 text-white rounded-lg font-semibold hover:bg-indigo-400 flex items-center justify-center gap-2"
              >
                <Save className="w-5 h-5" />
                Save Trade Plan
              </button>
              <button className="w-full py-3 bg-white/10 text-white rounded-lg font-medium hover:bg-white/20 flex items-center justify-center gap-2">
                <Copy className="w-5 h-5" />
                Copy to Clipboard
              </button>
              <button className="w-full py-3 bg-white/10 text-white rounded-lg font-medium hover:bg-white/20 flex items-center justify-center gap-2">
                <Share2 className="w-5 h-5" />
                Share Plan
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Saved Plans Mode */}
      {mode === 'saved' && (
        <div className="space-y-4">
          {savedPlans.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No saved trade plans yet</p>
              <button
                onClick={() => setMode('create')}
                className="mt-4 px-4 py-2 bg-indigo-500 text-white rounded-lg"
              >
                Create Your First Plan
              </button>
            </div>
          ) : (
            savedPlans.map(plan => (
              <div key={plan.id} className="bg-white/5 rounded-xl border border-white/10 p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold text-white">{plan.name}</h3>
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        plan.status === 'active' ? 'bg-green-500/20 text-green-400' :
                        plan.status === 'completed' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>
                        {plan.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-sm text-gray-400">
                      <span>{plan.token}</span>
                      <span className={plan.direction === 'long' ? 'text-green-400' : 'text-red-400'}>
                        {plan.direction.toUpperCase()}
                      </span>
                      <span>{plan.created}</span>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
                      <Eye className="w-4 h-4 text-gray-400" />
                    </button>
                    <button className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
                      <Edit2 className="w-4 h-4 text-gray-400" />
                    </button>
                    <button className="p-2 bg-white/10 rounded-lg hover:bg-white/20">
                      <Trash2 className="w-4 h-4 text-red-400" />
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-4">
                  <div className="bg-white/5 rounded-lg p-3">
                    <div className="text-xs text-gray-400">Entry</div>
                    <div className="text-white font-semibold">${plan.entry.toLocaleString()}</div>
                  </div>
                  <div className="bg-red-500/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">Stop Loss</div>
                    <div className="text-red-400 font-semibold">${plan.stopLoss.toLocaleString()}</div>
                  </div>
                  <div className="bg-green-500/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">Take Profit</div>
                    <div className="text-green-400 font-semibold">
                      {plan.takeProfits.map(tp => `$${tp.price.toLocaleString()}`).join(' / ')}
                    </div>
                  </div>
                  <div className="bg-indigo-500/10 rounded-lg p-3">
                    <div className="text-xs text-gray-400">R:R</div>
                    <div className="text-indigo-400 font-semibold">
                      1:{(Math.abs(plan.takeProfits[0].price - plan.entry) / Math.abs(plan.entry - plan.stopLoss)).toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Templates Mode */}
      {mode === 'templates' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { name: 'Breakout Play', rr: '1:3', risk: '2%', desc: 'Entry on breakout, SL below resistance' },
            { name: 'Support Bounce', rr: '1:2', risk: '1%', desc: 'Entry at support with confirmation' },
            { name: 'Trend Continuation', rr: '1:2.5', risk: '1.5%', desc: 'Pullback entry in trending market' },
            { name: 'Reversal Trade', rr: '1:4', risk: '1%', desc: 'Counter-trend with tight stop' },
            { name: 'Scalp Setup', rr: '1:1.5', risk: '0.5%', desc: 'Quick in/out with defined levels' },
            { name: 'Swing Trade', rr: '1:3', risk: '2%', desc: 'Multi-day hold with wide stops' }
          ].map((template, idx) => (
            <div key={idx} className="bg-white/5 rounded-xl border border-white/10 p-6 hover:border-indigo-500/50 cursor-pointer transition-colors">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-white">{template.name}</h3>
                <Bookmark className="w-5 h-5 text-gray-400" />
              </div>
              <p className="text-sm text-gray-400 mb-4">{template.desc}</p>
              <div className="flex gap-4 text-sm">
                <span className="text-indigo-400">R:R {template.rr}</span>
                <span className="text-red-400">Risk {template.risk}</span>
              </div>
              <button className="mt-4 w-full py-2 bg-indigo-500/20 text-indigo-400 rounded-lg text-sm hover:bg-indigo-500/30">
                Use Template
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default TradePlanner
