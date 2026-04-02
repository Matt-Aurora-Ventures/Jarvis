import React, { useState } from 'react'
import type { PerpsPosition } from './usePerpsData'

interface Props {
  positions: PerpsPosition[]
  onClose: (pda: string) => Promise<void>
}

function pnlColor(pct: number) {
  if (pct > 0) return 'text-green-400'
  if (pct < 0) return 'text-red-400'
  return 'text-gray-400'
}

function sideStyle(side: string) {
  return side === 'long'
    ? 'bg-green-500/15 text-green-400 border border-green-500/30'
    : 'bg-red-500/15 text-red-400 border border-red-500/30'
}

function triggerBadge(trigger?: string) {
  if (!trigger) return null
  const colors: Record<string, string> = {
    stop_loss: 'bg-red-500/15 text-red-400',
    take_profit: 'bg-green-500/15 text-green-400',
    trailing_stop: 'bg-yellow-500/15 text-yellow-400',
    time_decay: 'bg-blue-500/15 text-blue-400',
    funding_bleed: 'bg-orange-500/15 text-orange-400',
    signal_reversal: 'bg-violet-500/15 text-violet-400',
    emergency_stop: 'bg-red-700/30 text-red-300',
  }
  const cls = colors[trigger] ?? 'bg-gray-500/15 text-gray-400'
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${cls}`}>
      {trigger.replace(/_/g, ' ')}
    </span>
  )
}

function fmt(v: number, prefix = '$') {
  return `${prefix}${Math.abs(v).toFixed(2)}`
}

function fmtPrice(v: number) {
  if (v >= 10000) return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
  return `$${v.toFixed(2)}`
}

export function PerpsPositionsTable({ positions, onClose }: Props) {
  const [closingPda, setClosingPda] = useState<string | null>(null)

  const handleClose = async (pda: string) => {
    setClosingPda(pda)
    try {
      await onClose(pda)
    } catch (e) {
      console.error('Close failed:', e)
    } finally {
      setClosingPda(null)
    }
  }

  if (positions.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
        <h3 className="text-sm font-semibold text-white mb-3">Open Positions</h3>
        <div className="flex flex-col items-center justify-center py-8 text-gray-600 text-sm gap-2">
          <svg className="w-10 h-10 text-gray-700" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
          </svg>
          No open positions
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">Open Positions</h3>
        <span className="text-xs text-gray-500">{positions.length} active</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-500 border-b border-gray-800">
              <th className="text-left pb-2 pr-4 font-medium">Market</th>
              <th className="text-left pb-2 pr-4 font-medium">Side</th>
              <th className="text-right pb-2 pr-4 font-medium">Collateral</th>
              <th className="text-right pb-2 pr-4 font-medium">Lev</th>
              <th className="text-right pb-2 pr-4 font-medium">Entry</th>
              <th className="text-right pb-2 pr-4 font-medium">Current</th>
              <th className="text-right pb-2 pr-4 font-medium">P&amp;L</th>
              <th className="text-left pb-2 pr-4 font-medium">TP / SL</th>
              <th className="text-left pb-2 font-medium">Trigger</th>
              <th className="pb-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {positions.map(pos => (
              <tr key={pos.pda} className="hover:bg-gray-800/30 transition-colors">
                <td className="py-2.5 pr-4 font-medium text-white">{pos.market}</td>
                <td className="py-2.5 pr-4">
                  <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${sideStyle(pos.side)}`}>
                    {pos.side.toUpperCase()}
                  </span>
                </td>
                <td className="py-2.5 pr-4 text-right text-gray-300">{fmt(pos.collateral_usd)}</td>
                <td className="py-2.5 pr-4 text-right text-gray-300">{pos.leverage}×</td>
                <td className="py-2.5 pr-4 text-right text-gray-400">{fmtPrice(pos.entry_price)}</td>
                <td className="py-2.5 pr-4 text-right text-gray-300">{fmtPrice(pos.current_price)}</td>
                <td className="py-2.5 pr-4 text-right">
                  <div className={`font-semibold ${pnlColor(pos.unrealized_pnl_pct)}`}>
                    {pos.unrealized_pnl_pct >= 0 ? '+' : ''}{pos.unrealized_pnl_pct.toFixed(2)}%
                  </div>
                  <div className={`text-xs ${pnlColor(pos.unrealized_pnl_usd)}`}>
                    {pos.unrealized_pnl_usd >= 0 ? '+' : '-'}{fmt(pos.unrealized_pnl_usd)}
                  </div>
                </td>
                <td className="py-2.5 pr-4 text-gray-500">
                  {pos.tp_price || pos.sl_price ? (
                    <span>
                      {pos.tp_price ? <span className="text-green-500/70">{fmtPrice(pos.tp_price)}</span> : '—'}
                      {' / '}
                      {pos.sl_price ? <span className="text-red-500/70">{fmtPrice(pos.sl_price)}</span> : '—'}
                    </span>
                  ) : '—'}
                </td>
                <td className="py-2.5 pr-4">{triggerBadge(pos.exit_trigger)}</td>
                <td className="py-2.5">
                  <button
                    onClick={() => handleClose(pos.pda)}
                    disabled={closingPda === pos.pda}
                    className="text-xs px-2 py-1 rounded bg-gray-800 hover:bg-red-900/40 text-gray-400 hover:text-red-300 border border-gray-700 hover:border-red-700/50 transition-colors disabled:opacity-50"
                  >
                    {closingPda === pos.pda ? '...' : 'Close'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default PerpsPositionsTable
