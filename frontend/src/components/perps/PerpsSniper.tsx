import React from 'react'
import { usePerpsData } from './usePerpsData'
import { PerpsSignalPanel } from './PerpsSignalPanel'
import { PerpsPositionsTable } from './PerpsPositionsTable'
import { PerpsOrderForm } from './PerpsOrderForm'
import { PerpsArmControl } from './PerpsArmControl'
import { PerpsAuditLog } from './PerpsAuditLog'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtPrice(v: number, decimals = 2) {
  if (!v) return '--'
  if (v >= 10000) return `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
  return `$${v.toFixed(decimals)}`
}

function pnlColor(v: number) {
  if (v > 0) return 'text-green-400'
  if (v < 0) return 'text-red-400'
  return 'text-gray-400'
}

function RunnerDot({ healthy }: { healthy: boolean }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${healthy ? 'bg-green-400 animate-pulse' : 'bg-red-500'}`}
      title={healthy ? 'Runner online' : 'Runner offline'}
    />
  )
}

function ModeBadge({ mode }: { mode: string }) {
  const styles: Record<string, string> = {
    live: 'bg-green-500/15 text-green-400 border-green-500/30',
    alert: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    disabled: 'bg-gray-500/15 text-gray-500 border-gray-600/30',
  }
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded border ${styles[mode] ?? styles.disabled}`}>
      {mode.toUpperCase()}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PerpsSniper() {
  const {
    prices,
    status,
    positions,
    signal,
    audit,
    performance,
    error,
    openPosition,
    closePosition,
    prepareArm,
    confirmArm,
    disarm,
  } = usePerpsData()

  const isArmed = status?.arm?.stage === 'armed'
  const isLive = status?.mode === 'live'

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* ===== STATUS BAR ===== */}
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-3">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center gap-x-6 gap-y-2">

          {/* Runner health */}
          <div className="flex items-center gap-2">
            <RunnerDot healthy={status?.runner_healthy ?? false} />
            <span className="text-xs text-gray-400">
              {status?.runner_healthy ? 'Runner online' : 'Runner offline'}
              {status?.heartbeat_age_s !== undefined && (
                <span className="text-gray-600 ml-1">({status.heartbeat_age_s}s ago)</span>
              )}
            </span>
          </div>

          {/* Mode */}
          {status && <ModeBadge mode={status.mode} />}

          {/* Daily stats */}
          {status && (
            <>
              <div className="text-xs text-gray-500">
                Trades today:{' '}
                <span className="text-white font-medium">{status.daily.trades_today}</span>
                <span className="text-gray-700"> / {status.daily.max_trades_per_day}</span>
              </div>
              <div className={`text-xs font-medium ${pnlColor(status.daily.realized_pnl_today)}`}>
                P&L today:{' '}
                {status.daily.realized_pnl_today >= 0 ? '+' : ''}
                ${status.daily.realized_pnl_today.toFixed(2)}
              </div>
            </>
          )}

          {/* Performance */}
          {performance && (
            <div className="text-xs text-gray-500 ml-auto">
              Win rate:{' '}
              <span className="text-white">{performance.win_rate_pct.toFixed(1)}%</span>
              {' · '}
              All-time P&L:{' '}
              <span className={pnlColor(performance.total_pnl_usd)}>
                ${performance.total_pnl_usd.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* ===== ERROR BANNER ===== */}
      {error && (
        <div className="bg-red-900/20 border-b border-red-800/50 px-6 py-2">
          <div className="max-w-7xl mx-auto text-xs text-red-400">{error}</div>
        </div>
      )}

      {/* ===== MAIN CONTENT ===== */}
      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">

        {/* Price ticker row */}
        <div className="grid grid-cols-3 gap-4">
          {(
            [
              { label: 'SOL', value: prices?.sol },
              { label: 'BTC', value: prices?.btc },
              { label: 'ETH', value: prices?.eth },
            ] as const
          ).map(({ label, value }) => (
            <div key={label} className="bg-gray-900 border border-gray-700 rounded-xl px-5 py-3 flex items-center justify-between">
              <span className="text-sm font-medium text-gray-400">{label}</span>
              <span className="text-lg font-bold text-white font-mono">{fmtPrice(value ?? 0)}</span>
            </div>
          ))}
        </div>

        {/* Signal + Order Form */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PerpsSignalPanel signal={signal} />
          <PerpsOrderForm
            onSubmit={openPosition}
            disabled={!isArmed || !isLive}
          />
        </div>

        {/* Positions table (full width) */}
        <PerpsPositionsTable
          positions={positions}
          onClose={closePosition}
        />

        {/* Arm control + Audit log */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PerpsArmControl
            arm={status?.arm}
            onPrepare={prepareArm}
            onConfirm={confirmArm}
            onDisarm={disarm}
          />
          <PerpsAuditLog events={audit} />
        </div>

        {/* Safety note when disarmed */}
        {!isArmed && (
          <div className="text-center text-xs text-gray-600 pb-4">
            Order submission requires arming live trading above. Runner will execute intents only when armed.
          </div>
        )}
      </div>
    </div>
  )
}

export default PerpsSniper
