import React from 'react'
import type { BridgeJob } from './useInvestmentData'

// ---------------------------------------------------------------------------
// 6-state pipeline as specified in the revised PRD (Section D)
// Non-atomic DLN hook states are first-class:
//   Realized → BridgingRequested → Fulfilled → HookPending → Credited → Distributed
// ---------------------------------------------------------------------------

const PIPELINE_STATES = [
  'realized',
  'bridging_requested',
  'fulfilled',
  'hook_pending',
  'credited',
  'distributed',
] as const

type PipelineState = typeof PIPELINE_STATES[number]

// Map bridge job states to pipeline states
function jobToPipelineState(
  jobState: BridgeJob['state'] | 'hook_pending' | 'cancelled_fallback',
): PipelineState {
  switch (jobState) {
    case 'pending': return 'realized'
    case 'sending': return 'bridging_requested'
    case 'attesting': return 'bridging_requested'
    case 'claiming': return 'fulfilled'
    case 'hook_pending': return 'hook_pending'
    case 'completed': return 'credited'
    case 'failed':
    case 'cancelled_fallback':
    default:
      return 'realized'
  }
}

const STATE_LABELS: Record<PipelineState, string> = {
  realized: 'Realized',
  bridging_requested: 'Bridge Req.',
  fulfilled: 'Fulfilled',
  hook_pending: 'Hook Pending',
  credited: 'Credited',
  distributed: 'Distributed',
}

const STATE_DESCRIPTIONS: Record<PipelineState, string> = {
  realized: 'Profit realized on EVM basket',
  bridging_requested: 'CCTP/DLN transfer initiated',
  fulfilled: 'Bridge order filled',
  hook_pending: 'DLN hook awaiting Solana execution',
  credited: 'USDC arrived in reward vault',
  distributed: 'Staker rewards updated',
}

interface ProfitPipelineProps {
  jobs: BridgeJob[]
}

export function ProfitPipeline({ jobs }: ProfitPipelineProps) {
  // Show the most recent non-completed job, or most recent completed
  const activeJob = jobs.find(j => j.state !== 'completed' && j.state !== 'failed')
    ?? jobs[0]

  const currentPipelineState: PipelineState = activeJob
    ? jobToPipelineState(activeJob.state as BridgeJob['state'] | 'hook_pending' | 'cancelled_fallback')
    : 'realized'

  const activeIdx = PIPELINE_STATES.indexOf(currentPipelineState)

  function formatUSD(v: number) {
    if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`
    if (v >= 1_000) return `$${(v / 1_000).toFixed(2)}K`
    return `$${v.toFixed(2)}`
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-white">Profit Pipeline</h2>
        {activeJob && (
          <span className="text-xs text-gray-500">
            {formatUSD(activeJob.amount_usd)} USDC ·{' '}
            {new Date(activeJob.timestamp).toLocaleString()}
          </span>
        )}
      </div>

      {/* Pipeline steps */}
      <div className="flex items-center">
        {PIPELINE_STATES.map((state, idx) => {
          const isActive = idx === activeIdx && !!activeJob
          const isDone = idx < activeIdx
          const isHookPending = state === 'hook_pending' && isActive

          // Color logic
          let dotClass = 'bg-gray-700 border-gray-700'
          let labelClass = 'text-gray-600'
          if (isDone) { dotClass = 'bg-violet-500 border-violet-500'; labelClass = 'text-violet-400' }
          if (isActive && !isHookPending) { dotClass = 'bg-violet-400 border-violet-400 ring-2 ring-violet-400/30 animate-pulse'; labelClass = 'text-white' }
          if (isHookPending) { dotClass = 'bg-amber-400 border-amber-400 ring-2 ring-amber-400/30 animate-pulse'; labelClass = 'text-amber-300' }

          return (
            <React.Fragment key={state}>
              <div className="flex flex-col items-center flex-shrink-0" style={{ minWidth: 64 }}>
                {/* Dot */}
                <div className={`w-3 h-3 rounded-full border-2 ${dotClass} transition-all`} />
                {/* Label */}
                <span className={`text-xs mt-1.5 font-medium text-center leading-tight ${labelClass}`}>
                  {STATE_LABELS[state]}
                </span>
                {/* Tooltip */}
                {isActive && (
                  <span className="text-xs text-gray-600 text-center leading-tight mt-0.5" style={{ fontSize: 9 }}>
                    {STATE_DESCRIPTIONS[state]}
                  </span>
                )}
              </div>

              {/* Connector line */}
              {idx < PIPELINE_STATES.length - 1 && (
                <div className={`flex-1 h-0.5 mx-1 ${idx < activeIdx ? 'bg-violet-500' : 'bg-gray-700'}`} />
              )}
            </React.Fragment>
          )
        })}
      </div>

      {/* Hook pending warning */}
      {activeJob && (activeJob.state as string) === 'hook_pending' && (
        <div className="mt-4 p-3 bg-amber-900/20 border border-amber-700/30 rounded-lg text-xs text-amber-300">
          <span className="font-medium">DLN Hook Pending:</span> Bridge fulfilled on source chain but the
          Solana hook instruction has not yet executed. This is expected — DLN hooks on Solana are
          non-atomic. The system will retry automatically. Rewards will not be credited until the hook
          executes or fallback is triggered.
        </div>
      )}

      {/* No jobs placeholder */}
      {!activeJob && (
        <p className="text-xs text-gray-600 text-center mt-4">
          No active bridge operation. Profits flow here when the basket generates yield.
        </p>
      )}
    </div>
  )
}

export default ProfitPipeline
