import React, { useState, useEffect, useMemo } from 'react'
import {
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Settings,
  Zap,
  DollarSign,
  Percent,
  RefreshCw,
  CheckCircle,
  XCircle,
  Shield
} from 'lucide-react'

/**
 * Order types
 */
const ORDER_TYPES = [
  { value: 'market', label: 'Market', description: 'Execute immediately at current price' },
  { value: 'limit', label: 'Limit', description: 'Execute when price reaches your target' },
]

/**
 * Quick amount presets
 */
const AMOUNT_PRESETS = [
  { label: '25%', value: 0.25 },
  { label: '50%', value: 0.50 },
  { label: '75%', value: 0.75 },
  { label: '100%', value: 1.0 },
]

/**
 * Order Panel Component
 */
export default function OrderPanel({
  symbol = 'TOKEN',
  mint,
  currentPrice = 0,
  walletBalance = 0,
  isPaperMode = true,
  onTrade,
  onSettingsClick,
}) {
  // Order state
  const [side, setSide] = useState('buy') // 'buy' or 'sell'
  const [orderType, setOrderType] = useState('market')
  const [amount, setAmount] = useState('')
  const [limitPrice, setLimitPrice] = useState('')
  const [slippage, setSlippage] = useState(1) // 1%

  // TP/SL settings
  const [useTPSL, setUseTPSL] = useState(false)
  const [takeProfitPct, setTakeProfitPct] = useState(20)
  const [stopLossPct, setStopLossPct] = useState(10)

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [lastOrder, setLastOrder] = useState(null)
  const [error, setError] = useState('')

  // Reset limit price when current price changes
  useEffect(() => {
    if (orderType === 'limit' && !limitPrice && currentPrice > 0) {
      setLimitPrice(currentPrice.toFixed(6))
    }
  }, [currentPrice, orderType])

  // Calculate order details
  const orderDetails = useMemo(() => {
    const amountValue = parseFloat(amount) || 0
    const priceValue = orderType === 'limit' ? parseFloat(limitPrice) : currentPrice

    const total = amountValue * priceValue
    const slippageAmount = (total * slippage) / 100

    const tpPrice = priceValue * (1 + takeProfitPct / 100)
    const slPrice = priceValue * (1 - stopLossPct / 100)

    const potentialProfit = useTPSL ? amountValue * (tpPrice - priceValue) : 0
    const maxLoss = useTPSL ? amountValue * (priceValue - slPrice) : amountValue * priceValue

    return {
      amount: amountValue,
      price: priceValue,
      total,
      slippageAmount,
      maxTotal: total + slippageAmount,
      tpPrice,
      slPrice,
      potentialProfit,
      maxLoss,
    }
  }, [amount, limitPrice, currentPrice, orderType, slippage, useTPSL, takeProfitPct, stopLossPct])

  // Handle amount preset click
  const handlePresetClick = (pct) => {
    const maxAmount = side === 'buy'
      ? walletBalance / (currentPrice || 1)
      : walletBalance // For sell, use token balance
    setAmount((maxAmount * pct).toFixed(4))
  }

  // Validate order
  const validateOrder = () => {
    if (!orderDetails.amount || orderDetails.amount <= 0) {
      return 'Enter a valid amount'
    }

    if (orderType === 'limit' && (!orderDetails.price || orderDetails.price <= 0)) {
      return 'Enter a valid limit price'
    }

    if (side === 'buy' && orderDetails.maxTotal > walletBalance) {
      return 'Insufficient balance'
    }

    return null
  }

  // Submit order
  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    const validationError = validateOrder()
    if (validationError) {
      setError(validationError)
      return
    }

    setIsSubmitting(true)

    try {
      const order = {
        mint,
        symbol,
        side,
        orderType,
        amount: orderDetails.amount,
        price: orderDetails.price,
        slippage,
        takeProfit: useTPSL ? orderDetails.tpPrice : null,
        stopLoss: useTPSL ? orderDetails.slPrice : null,
        isPaperMode,
      }

      if (onTrade) {
        const result = await onTrade(order)
        setLastOrder({ ...order, ...result, timestamp: Date.now() })
        setAmount('')
      }
    } catch (err) {
      setError(err.message || 'Order failed')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-white flex items-center gap-2">
          <Zap size={18} className="text-cyan-400" />
          {isPaperMode ? 'Paper Trade' : 'Trade'} ${symbol}
        </h3>
        <div className="flex items-center gap-2">
          {isPaperMode && (
            <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">
              PAPER
            </span>
          )}
          {onSettingsClick && (
            <button
              onClick={onSettingsClick}
              className="p-1 text-gray-400 hover:text-white transition-colors"
            >
              <Settings size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Buy/Sell Toggle */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setSide('buy')}
          className={`flex-1 py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
            side === 'buy'
              ? 'bg-green-500 text-white'
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
          }`}
        >
          <TrendingUp size={18} />
          Buy
        </button>
        <button
          onClick={() => setSide('sell')}
          className={`flex-1 py-2 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
            side === 'sell'
              ? 'bg-red-500 text-white'
              : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
          }`}
        >
          <TrendingDown size={18} />
          Sell
        </button>
      </div>

      {/* Order Type */}
      <div className="flex gap-2 mb-4">
        {ORDER_TYPES.map(type => (
          <button
            key={type.value}
            onClick={() => setOrderType(type.value)}
            className={`flex-1 py-1.5 text-sm rounded transition-colors ${
              orderType === type.value
                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/50'
                : 'bg-gray-700 text-gray-400 border border-transparent hover:bg-gray-600'
            }`}
          >
            {type.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        {/* Price (for limit orders) */}
        {orderType === 'limit' && (
          <div className="mb-3">
            <label className="block text-sm text-gray-400 mb-1">Limit Price</label>
            <div className="relative">
              <DollarSign size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="number"
                step="0.000001"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                placeholder="0.000000"
                className="w-full pl-9 pr-4 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        )}

        {/* Amount */}
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <label className="text-sm text-gray-400">Amount ({symbol})</label>
            <span className="text-xs text-gray-500">
              Balance: {walletBalance.toFixed(4)} SOL
            </span>
          </div>
          <input
            type="number"
            step="0.0001"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.0000"
            className="w-full px-4 py-2 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
          <div className="flex gap-1 mt-2">
            {AMOUNT_PRESETS.map(preset => (
              <button
                key={preset.label}
                type="button"
                onClick={() => handlePresetClick(preset.value)}
                className="flex-1 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded transition-colors"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* TP/SL Toggle */}
        <div className="mb-3">
          <button
            type="button"
            onClick={() => setUseTPSL(!useTPSL)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            <div className={`w-4 h-4 rounded border ${
              useTPSL ? 'bg-cyan-500 border-cyan-500' : 'border-gray-500'
            }`}>
              {useTPSL && <CheckCircle size={14} className="text-white" />}
            </div>
            <Shield size={14} />
            Set TP/SL
          </button>

          {useTPSL && (
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <label className="block text-xs text-green-400 mb-1">Take Profit %</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="1"
                    value={takeProfitPct}
                    onChange={(e) => setTakeProfitPct(parseFloat(e.target.value) || 0)}
                    className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-green-500"
                  />
                  <Percent size={14} className="text-gray-500" />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  ${orderDetails.tpPrice.toFixed(6)}
                </p>
              </div>
              <div>
                <label className="block text-xs text-red-400 mb-1">Stop Loss %</label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="1"
                    value={stopLossPct}
                    onChange={(e) => setStopLossPct(parseFloat(e.target.value) || 0)}
                    className="flex-1 px-3 py-1.5 bg-gray-900 border border-gray-600 rounded text-white text-sm focus:outline-none focus:border-red-500"
                  />
                  <Percent size={14} className="text-gray-500" />
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  ${orderDetails.slPrice.toFixed(6)}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Slippage */}
        <div className="mb-4">
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced
          </button>

          {showAdvanced && (
            <div className="mt-2">
              <label className="block text-xs text-gray-400 mb-1">Slippage Tolerance</label>
              <div className="flex gap-2">
                {[0.5, 1, 2, 5].map(pct => (
                  <button
                    key={pct}
                    type="button"
                    onClick={() => setSlippage(pct)}
                    className={`px-3 py-1 text-xs rounded transition-colors ${
                      slippage === pct
                        ? 'bg-cyan-500/20 text-cyan-400'
                        : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                    }`}
                  >
                    {pct}%
                  </button>
                ))}
                <input
                  type="number"
                  step="0.1"
                  value={slippage}
                  onChange={(e) => setSlippage(parseFloat(e.target.value) || 0)}
                  className="w-16 px-2 py-1 bg-gray-900 border border-gray-600 rounded text-white text-xs focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>
          )}
        </div>

        {/* Order Summary */}
        <div className="p-3 bg-gray-900/50 rounded-lg mb-4 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Price</span>
            <span className="text-white font-mono">${orderDetails.price.toFixed(6)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Total</span>
            <span className="text-white font-mono">${orderDetails.total.toFixed(4)}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">Max (incl. slippage)</span>
            <span className="text-gray-400">${orderDetails.maxTotal.toFixed(4)}</span>
          </div>
          {useTPSL && (
            <>
              <div className="border-t border-gray-700 pt-2 flex justify-between">
                <span className="text-green-400">Potential Profit</span>
                <span className="text-green-400">+${orderDetails.potentialProfit.toFixed(4)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-400">Max Loss</span>
                <span className="text-red-400">-${orderDetails.maxLoss.toFixed(4)}</span>
              </div>
            </>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 p-2 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle size={14} />
            {error}
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={isSubmitting || !orderDetails.amount}
          className={`w-full py-3 rounded-lg font-semibold transition-colors flex items-center justify-center gap-2 ${
            side === 'buy'
              ? 'bg-green-500 hover:bg-green-400 text-white'
              : 'bg-red-500 hover:bg-red-400 text-white'
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {isSubmitting ? (
            <RefreshCw size={18} className="animate-spin" />
          ) : (
            <>
              {side === 'buy' ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
              {side === 'buy' ? 'Buy' : 'Sell'} ${symbol}
            </>
          )}
        </button>
      </form>

      {/* Last Order */}
      {lastOrder && (
        <div className="mt-4 p-3 bg-gray-900/50 rounded-lg">
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle size={16} className="text-green-400" />
            <span className="text-gray-400">Last order:</span>
            <span className={lastOrder.side === 'buy' ? 'text-green-400' : 'text-red-400'}>
              {lastOrder.side.toUpperCase()} {lastOrder.amount} {lastOrder.symbol}
            </span>
            <span className="text-gray-500">
              @ ${lastOrder.price.toFixed(6)}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}
