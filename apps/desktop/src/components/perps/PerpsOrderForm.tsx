import React, { useState, useCallback } from 'react'

interface Props {
  onSubmit: (params: {
    market: string
    side: 'long' | 'short'
    collateral_usd: number
    leverage: number
    tp_pct?: number
    sl_pct?: number
  }) => Promise<void>
  disabled?: boolean
}

const MARKETS = ['SOL-USD', 'BTC-USD', 'ETH-USD']
const LEVERAGE_STEPS = [2, 3, 5, 7, 10]

export function PerpsOrderForm({ onSubmit, disabled }: Props) {
  const [market, setMarket] = useState('SOL-USD')
  const [side, setSide] = useState<'long' | 'short'>('long')
  const [collateral, setCollateral] = useState(100)
  const [leverage, setLeverage] = useState(3)
  const [tp, setTp] = useState('')
  const [sl, setSl] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [feedback, setFeedback] = useState<{ ok: boolean; msg: string } | null>(null)

  const handleSubmit = useCallback(async () => {
    setSubmitting(true)
    setFeedback(null)
    try {
      await onSubmit({
        market,
        side,
        collateral_usd: collateral,
        leverage,
        tp_pct: tp ? parseFloat(tp) : undefined,
        sl_pct: sl ? parseFloat(sl) : undefined,
      })
      setFeedback({ ok: true, msg: 'Intent queued.' })
      setTimeout(() => setFeedback(null), 3000)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setFeedback({ ok: false, msg })
    } finally {
      setSubmitting(false)
    }
  }, [market, side, collateral, leverage, tp, sl, onSubmit])

  const sizeUsd = collateral * leverage

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-white">Open Position</h3>

      <div>
        <label className="text-xs text-gray-500 block mb-1">Market</label>
        <div className="flex gap-1.5">
          {MARKETS.map((m) => (
            <button
              key={m}
              onClick={() => setMarket(m)}
              disabled={disabled}
              className={`flex-1 py-1.5 text-xs rounded-lg border font-medium transition-colors ${
                market === m
                  ? 'bg-violet-600 border-violet-500 text-white'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {m.split('-')[0]}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="text-xs text-gray-500 block mb-1">Direction</label>
        <div className="flex gap-1.5">
          <button
            onClick={() => setSide('long')}
            disabled={disabled}
            className={`flex-1 py-2 text-xs rounded-lg border font-bold transition-colors ${
              side === 'long'
                ? 'bg-green-600/30 border-green-500 text-green-300'
                : 'bg-gray-800 border-gray-700 text-gray-500 hover:bg-gray-700'
            }`}
          >
            LONG
          </button>
          <button
            onClick={() => setSide('short')}
            disabled={disabled}
            className={`flex-1 py-2 text-xs rounded-lg border font-bold transition-colors ${
              side === 'short'
                ? 'bg-red-600/30 border-red-500 text-red-300'
                : 'bg-gray-800 border-gray-700 text-gray-500 hover:bg-gray-700'
            }`}
          >
            SHORT
          </button>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-gray-500">Collateral</label>
          <span className="text-xs text-white font-medium">${collateral}</span>
        </div>
        <input
          type="range"
          min={10}
          max={500}
          step={10}
          value={collateral}
          onChange={(e) => setCollateral(Number(e.target.value))}
          disabled={disabled}
          className="w-full accent-violet-500"
        />
        <div className="flex justify-between text-xs text-gray-600 mt-0.5">
          <span>$10</span><span>$500</span>
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-gray-500">Leverage</label>
          <span className="text-xs text-white font-medium">{leverage}x -> ${sizeUsd.toLocaleString()} notional</span>
        </div>
        <div className="flex gap-1.5">
          {LEVERAGE_STEPS.map((l) => (
            <button
              key={l}
              onClick={() => setLeverage(l)}
              disabled={disabled}
              className={`flex-1 py-1.5 text-xs rounded-lg border font-medium transition-colors ${
                leverage === l
                  ? 'bg-violet-600 border-violet-500 text-white'
                  : 'bg-gray-800 border-gray-700 text-gray-400 hover:bg-gray-700'
              }`}
            >
              {l}x
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-500 block mb-1">Take Profit % (optional)</label>
          <input
            type="number"
            placeholder="10"
            value={tp}
            onChange={(e) => setTp(e.target.value)}
            disabled={disabled}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-green-300 placeholder-gray-600 focus:outline-none focus:border-green-600"
          />
        </div>
        <div>
          <label className="text-xs text-gray-500 block mb-1">Stop Loss % (optional)</label>
          <input
            type="number"
            placeholder="5"
            value={sl}
            onChange={(e) => setSl(e.target.value)}
            disabled={disabled}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-red-300 placeholder-gray-600 focus:outline-none focus:border-red-600"
          />
        </div>
      </div>

      <button
        onClick={handleSubmit}
        disabled={disabled || submitting}
        className="w-full py-2.5 text-sm font-bold rounded-lg transition-all disabled:opacity-40 disabled:cursor-not-allowed bg-violet-600 hover:bg-violet-500 text-white"
      >
        {submitting ? 'Queuing...' : `Open ${side.toUpperCase()} ${leverage}x ${market}`}
      </button>

      {feedback && (
        <div className={`text-xs rounded px-3 py-1.5 ${feedback.ok ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
          {feedback.msg}
        </div>
      )}

      {disabled && (
        <p className="text-xs text-amber-400 text-center">
          Arm live trading to submit orders
        </p>
      )}
    </div>
  )
}

export default PerpsOrderForm
