import React, { useState, useCallback } from 'react'
import { useInvestmentData } from './useInvestmentData'
import { BasketOverview } from './BasketOverview'
import { PerformanceChart } from './PerformanceChart'
import { AgentConsensusLog } from './AgentConsensusLog'
import { TokenTrajectories } from './TokenTrajectories'
import { BridgeHistory } from './BridgeHistory'
import { StakingPanel } from './StakingPanel'
import { ProfitPipeline } from './ProfitPipeline'
import { ReflectionPanel } from './ReflectionPanel'

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function InvestmentDashboard() {
  const {
    basket,
    performance,
    decisions,
    reflections,
    bridgeJobs,
    stakingPool,
    killSwitch,
    loading,
    error,
    wsConnected,
    refresh,
    fetchDecisionDetail,
    fetchPerformance,
    triggerCycle,
    activateKillSwitch,
    deactivateKillSwitch,
  } = useInvestmentData()

  const [triggerLoading, setTriggerLoading] = useState(false)
  const [killSwitchLoading, setKillSwitchLoading] = useState(false)
  const [confirmKillSwitch, setConfirmKillSwitch] = useState(false)

  // ---- Manual trigger ----
  const handleTriggerCycle = useCallback(async () => {
    setTriggerLoading(true)
    try {
      await triggerCycle()
    } catch (e) {
      console.error('Trigger cycle failed:', e)
    } finally {
      setTriggerLoading(false)
    }
  }, [triggerCycle])

  // ---- Kill switch ----
  const handleKillSwitchToggle = useCallback(async () => {
    if (killSwitch?.active) {
      // Deactivating -- no confirmation needed
      setKillSwitchLoading(true)
      try {
        await deactivateKillSwitch()
      } catch (e) {
        console.error('Deactivate kill switch failed:', e)
      } finally {
        setKillSwitchLoading(false)
      }
    } else {
      // Activating -- require confirmation
      if (!confirmKillSwitch) {
        setConfirmKillSwitch(true)
        // Auto-dismiss after 3 seconds
        setTimeout(() => setConfirmKillSwitch(false), 3000)
        return
      }
      setConfirmKillSwitch(false)
      setKillSwitchLoading(true)
      try {
        await activateKillSwitch()
      } catch (e) {
        console.error('Activate kill switch failed:', e)
      } finally {
        setKillSwitchLoading(false)
      }
    }
  }, [killSwitch, confirmKillSwitch, activateKillSwitch, deactivateKillSwitch])

  const isKillSwitchActive = killSwitch?.active ?? false

  return (
    <div className="bg-gray-950 text-white">
      {/* ====== TOP BAR ====== */}
      <div className="bg-gray-900 border-b border-gray-800 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between flex-wrap gap-4">
          {/* Title + connection status */}
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-white">Investment Service</h1>
            <span
              className={`flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full ${
                wsConnected
                  ? 'bg-green-500/15 text-green-400'
                  : 'bg-gray-700 text-gray-400'
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  wsConnected ? 'bg-green-400 animate-pulse' : 'bg-gray-500'
                }`}
              />
              {wsConnected ? 'Live' : 'Polling'}
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3">
            {/* Refresh */}
            <button
              onClick={refresh}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-300 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg transition-colors disabled:opacity-50"
            >
              <svg
                className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
              Refresh
            </button>

            {/* Manual Trigger */}
            <button
              onClick={handleTriggerCycle}
              disabled={triggerLoading || isKillSwitchActive}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-white bg-violet-600 hover:bg-violet-500 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {triggerLoading ? (
                <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="3"
                    strokeDasharray="32"
                    strokeLinecap="round"
                  />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
              Trigger Cycle
            </button>

            {/* Kill Switch */}
            <button
              onClick={handleKillSwitchToggle}
              disabled={killSwitchLoading}
              className={`flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg transition-all disabled:opacity-50 ${
                isKillSwitchActive
                  ? 'bg-red-600 text-white hover:bg-red-500 ring-2 ring-red-400/50'
                  : confirmKillSwitch
                  ? 'bg-red-700 text-white animate-pulse'
                  : 'bg-gray-800 text-red-400 hover:bg-red-900/50 border border-red-800/50'
              }`}
            >
              {/* Power icon */}
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 5.636a9 9 0 010 12.728M5.636 5.636a9 9 0 000 12.728M12 2v10" />
              </svg>
              {killSwitchLoading
                ? 'Processing...'
                : isKillSwitchActive
                ? 'KILL SWITCH ON'
                : confirmKillSwitch
                ? 'Click again to confirm'
                : 'Kill Switch'}
            </button>
          </div>
        </div>
      </div>

      {/* ====== ERROR BANNER ====== */}
      {error && (
        <div className="bg-red-900/30 border-b border-red-800 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center gap-2 text-sm text-red-300">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
            {error}
            <button
              onClick={refresh}
              className="ml-auto text-xs underline text-red-400 hover:text-red-300"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* ====== KILL SWITCH ACTIVE BANNER ====== */}
      {isKillSwitchActive && (
        <div className="bg-red-900/40 border-b border-red-700 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center gap-2 text-sm text-red-200">
            <svg className="w-5 h-5 flex-shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="font-semibold">Kill switch is active.</span>
            <span className="text-red-300/80">All autonomous trading is halted.</span>
            {killSwitch?.activated_at && (
              <span className="text-red-400/60 text-xs ml-auto">
                Since {new Date(killSwitch.activated_at).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      )}

      {/* ====== MAIN GRID ====== */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Row 1: Basket + Performance */}
          <BasketOverview basket={basket} loading={loading} />
          <PerformanceChart
            performance={performance}
            loading={loading}
            onTimeframeChange={fetchPerformance}
          />

          {/* Row 2: Profit Pipeline (full width) */}
          <div className="lg:col-span-2">
            <ProfitPipeline jobs={bridgeJobs} />
          </div>

          {/* Row 3: Token Trajectories + Staking */}
          <TokenTrajectories
            tokens={basket?.tokens ?? []}
            performance={performance}
            loading={loading}
          />
          <StakingPanel pool={stakingPool} loading={loading} />

          {/* Row 4: Agent Consensus Log (full width) */}
          <div className="lg:col-span-2">
            <AgentConsensusLog
              decisions={decisions}
              loading={loading}
              onFetchDetail={fetchDecisionDetail}
            />
          </div>

          {/* Row 5: Reflection Panel (full width) */}
          <div className="lg:col-span-2">
            <ReflectionPanel reflections={reflections ?? []} loading={loading} />
          </div>

          {/* Row 6: Bridge History (full width) */}
          <div className="lg:col-span-2">
            <BridgeHistory jobs={bridgeJobs} loading={loading} />
          </div>
        </div>
      </div>
    </div>
  )
}

export default InvestmentDashboard
