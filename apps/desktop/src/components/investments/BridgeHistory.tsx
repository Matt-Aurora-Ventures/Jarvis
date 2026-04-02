import React from 'react'
import type { BridgeJob } from './useInvestmentData'

// Extended states beyond the base BridgeJob['state'] union
type ExtendedState = BridgeJob['state'] | 'hook_pending' | 'cancelled_fallback'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function stateColor(state: ExtendedState): string {
  switch (state) {
    case 'completed':
      return 'bg-green-400/15 text-green-400 border-green-500/30'
    case 'hook_pending':
      return 'bg-amber-400/15 text-amber-400 border-amber-500/30'
    case 'cancelled_fallback':
      return 'bg-orange-500/15 text-orange-400 border-orange-500/30'
    case 'pending':
    case 'sending':
    case 'attesting':
    case 'claiming':
      return 'bg-yellow-400/15 text-yellow-400 border-yellow-500/30'
    case 'failed':
      return 'bg-red-400/15 text-red-400 border-red-500/30'
    default:
      return 'bg-gray-400/15 text-gray-400 border-gray-500/30'
  }
}

function stateDot(state: ExtendedState): string {
  switch (state) {
    case 'completed':
      return 'bg-green-400'
    case 'hook_pending':
      return 'bg-amber-400 animate-pulse'
    case 'cancelled_fallback':
      return 'bg-orange-400'
    case 'pending':
    case 'sending':
    case 'attesting':
    case 'claiming':
      return 'bg-yellow-400'
    case 'failed':
      return 'bg-red-400'
    default:
      return 'bg-gray-400'
  }
}

function stateLabel(state: ExtendedState): string {
  if (state === 'hook_pending') return 'HOOK PENDING'
  if (state === 'cancelled_fallback') return 'CANCELLED (FALLBACK)'
  return state.toUpperCase()
}

function formatUSD(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(2)}K`
  return `$${val.toFixed(2)}`
}

function truncateHash(hash: string): string {
  if (!hash || hash.length < 12) return hash || '--'
  return `${hash.slice(0, 6)}...${hash.slice(-4)}`
}

function explorerLink(chain: string, tx: string): string {
  if (!tx) return '#'
  const lower = chain.toLowerCase()
  if (lower.includes('sol') || lower.includes('solana')) {
    return `https://solscan.io/tx/${tx}`
  }
  if (lower.includes('eth') || lower.includes('ethereum')) {
    return `https://etherscan.io/tx/${tx}`
  }
  if (lower.includes('arb') || lower.includes('arbitrum')) {
    return `https://arbiscan.io/tx/${tx}`
  }
  if (lower.includes('base')) {
    return `https://basescan.org/tx/${tx}`
  }
  // Fallback
  return `#${tx}`
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface BridgeHistoryProps {
  jobs: BridgeJob[]
  loading: boolean
}

export function BridgeHistory({ jobs, loading }: BridgeHistoryProps) {
  if (loading && jobs.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-40 mb-4" />
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-14 bg-gray-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Bridge History</h2>

      {jobs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-10 text-gray-500">
          <svg
            className="w-12 h-12 mb-3 text-gray-700"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"
            />
          </svg>
          <span className="text-sm">No bridge operations yet</span>
        </div>
      ) : (
        <div className="space-y-2">
          {jobs.map(job => {
            const extState = (job as Record<string, unknown>).state as ExtendedState
            const dlnOrderId = (job as Record<string, unknown>).dln_order_id as string | undefined
            const fallbackTx = (job as Record<string, unknown>).fallback_tx as string | undefined
            const hookAttempts = (job as Record<string, unknown>).hook_attempts as number | undefined

            return (
            <div
              key={job.id}
              className="bg-gray-800/40 border border-gray-700/50 rounded-lg px-4 py-3"
            >
              {/* Top row: state + amount + time */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded border ${stateColor(extState)}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${stateDot(extState)}`} />
                    {stateLabel(extState)}
                  </span>
                  <span className="text-sm font-medium text-white">
                    {formatUSD(job.amount_usd)}
                  </span>
                  <span className="text-xs text-gray-500">{job.token}</span>
                </div>
                <span className="text-xs text-gray-600">
                  {new Date(job.timestamp).toLocaleString()}
                </span>
              </div>

              {/* Bottom row: chain route + tx hashes */}
              <div className="flex items-center justify-between text-xs text-gray-400">
                <div className="flex items-center gap-1">
                  <span className="text-gray-300">{job.source_chain}</span>
                  <svg className="w-3 h-3 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                  <span className="text-gray-300">{job.dest_chain}</span>
                </div>

                <div className="flex items-center gap-3">
                  {job.source_tx && (
                    <a
                      href={explorerLink(job.source_chain, job.source_tx)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 transition-colors"
                      title={job.source_tx}
                    >
                      src: {truncateHash(job.source_tx)}
                    </a>
                  )}
                  {job.dest_tx && (
                    <a
                      href={explorerLink(job.dest_chain, job.dest_tx)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-400 hover:text-blue-300 transition-colors"
                      title={job.dest_tx}
                    >
                      dst: {truncateHash(job.dest_tx)}
                    </a>
                  )}
                </div>
              </div>

              {/* Hook pending info */}
              {extState === 'hook_pending' && (
                <div className="mt-2 text-xs text-amber-400 bg-amber-400/10 rounded px-2 py-1">
                  DLN hook awaiting Solana execution
                  {hookAttempts !== undefined && ` (${hookAttempts} attempt${hookAttempts !== 1 ? 's' : ''})`}
                  {dlnOrderId && (
                    <a
                      href={`https://app.debridge.finance/order?orderId=${dlnOrderId}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 underline hover:text-amber-300"
                    >
                      View order ↗
                    </a>
                  )}
                </div>
              )}

              {/* Cancelled fallback info */}
              {extState === 'cancelled_fallback' && (
                <div className="mt-2 text-xs text-orange-400 bg-orange-400/10 rounded px-2 py-1">
                  Hook failed — funds sent to fallback address.
                  {fallbackTx && (
                    <a
                      href={`https://solscan.io/tx/${fallbackTx}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-2 underline hover:text-orange-300"
                    >
                      Fallback tx ↗
                    </a>
                  )}
                </div>
              )}

              {/* Error message */}
              {job.error && extState !== 'hook_pending' && extState !== 'cancelled_fallback' && (
                <div className="mt-2 text-xs text-red-400 bg-red-400/10 rounded px-2 py-1">
                  {job.error}
                </div>
              )}
            </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default BridgeHistory
