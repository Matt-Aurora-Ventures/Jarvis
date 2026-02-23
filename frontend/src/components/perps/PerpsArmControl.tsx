import React, { useState, useCallback } from 'react'
import type { PerpsArmState } from './usePerpsData'

const ARM_PHRASE = 'ARM_LIVE_TRADING'

interface Props {
  arm: PerpsArmState | undefined
  onPrepare: () => Promise<{ challenge: string; expires_at: number }>
  onConfirm: (challenge: string, phrase: string) => Promise<void>
  onDisarm: () => Promise<void>
}

function stageBadge(stage: string) {
  if (stage === 'armed') return 'bg-green-500/15 text-green-400 border border-green-500/30'
  if (stage === 'prepared') return 'bg-yellow-500/15 text-yellow-400 border border-yellow-500/30'
  return 'bg-gray-500/15 text-gray-400 border border-gray-600/30'
}

function stageIcon(stage: string) {
  if (stage === 'armed') return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
  if (stage === 'prepared') return (
    <svg className="w-4 h-4 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
    </svg>
  )
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
    </svg>
  )
}

export function PerpsArmControl({ arm, onPrepare, onConfirm, onDisarm }: Props) {
  const [step, setStep] = useState<'idle' | 'challenge' | 'confirming' | 'disarming'>('idle')
  const [challenge, setChallenge] = useState('')
  const [phrase, setPhrase] = useState('')
  const [expiresAt, setExpiresAt] = useState<number>(0)
  const [err, setErr] = useState<string | null>(null)

  const stage = arm?.stage ?? 'disarmed'

  const handlePrepare = useCallback(async () => {
    setErr(null)
    setStep('challenge')
    try {
      const res = await onPrepare()
      setChallenge(res.challenge)
      setExpiresAt(res.expires_at)
      setPhrase('')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setErr(msg)
      setStep('idle')
    }
  }, [onPrepare])

  const handleConfirm = useCallback(async () => {
    setErr(null)
    setStep('confirming')
    try {
      await onConfirm(challenge, phrase)
      setStep('idle')
      setChallenge('')
      setPhrase('')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setErr(msg)
      setStep('challenge')
    }
  }, [challenge, phrase, onConfirm])

  const handleDisarm = useCallback(async () => {
    setErr(null)
    setStep('disarming')
    try {
      await onDisarm()
      setStep('idle')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setErr(msg)
      setStep('idle')
    }
  }, [onDisarm])

  const secondsLeft = expiresAt ? Math.max(0, Math.floor(expiresAt - Date.now() / 1000)) : 0

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white">Live Arm Control</h3>
        <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded ${stageBadge(stage)}`}>
          {stageIcon(stage)}
          {stage.toUpperCase()}
        </span>
      </div>

      {/* Armed info */}
      {stage === 'armed' && arm?.armed_at && (
        <p className="text-xs text-gray-500 mb-4">
          Armed by {arm.armed_by ?? 'user'} at {new Date(arm.armed_at * 1000).toLocaleTimeString()}
        </p>
      )}

      {/* Challenge modal */}
      {step === 'challenge' && (
        <div className="mb-4 p-3 bg-yellow-900/20 border border-yellow-700/40 rounded-lg space-y-3">
          <p className="text-xs text-yellow-300 font-medium">
            Step 2 — Confirm with phrase to arm live trading
          </p>
          <div className="bg-gray-950 border border-gray-700 rounded px-3 py-2 font-mono text-xs text-gray-300 break-all">
            Challenge: {challenge}
          </div>
          {secondsLeft > 0 && (
            <p className="text-xs text-gray-500">Expires in {secondsLeft}s</p>
          )}
          <div className="text-xs text-gray-500 mb-1">
            Type confirmation phrase: <code className="text-yellow-400">{ARM_PHRASE}</code>
          </div>
          <input
            type="text"
            value={phrase}
            onChange={e => setPhrase(e.target.value)}
            placeholder={ARM_PHRASE}
            className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono placeholder-gray-600 focus:outline-none focus:border-yellow-600"
          />
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={phrase !== ARM_PHRASE}
              className="flex-1 py-1.5 text-xs font-bold rounded-lg bg-yellow-600 hover:bg-yellow-500 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {step === 'confirming' ? 'Arming...' : 'Confirm & Arm'}
            </button>
            <button
              onClick={() => { setStep('idle'); setErr(null) }}
              className="px-3 py-1.5 text-xs rounded-lg bg-gray-800 text-gray-400 hover:bg-gray-700 border border-gray-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Buttons */}
      <div className="flex gap-2">
        {stage === 'disarmed' && step === 'idle' && (
          <button
            onClick={handlePrepare}
            className="flex-1 py-2 text-xs font-bold rounded-lg bg-yellow-700/30 hover:bg-yellow-700/50 text-yellow-300 border border-yellow-700/50 transition-colors"
          >
            Arm Live Trading →
          </button>
        )}
        {(stage === 'armed' || stage === 'prepared') && (
          <button
            onClick={handleDisarm}
            disabled={step === 'disarming'}
            className="flex-1 py-2 text-xs font-bold rounded-lg bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-600/40 transition-colors disabled:opacity-50"
          >
            {step === 'disarming' ? 'Disarming...' : 'Disarm'}
          </button>
        )}
      </div>

      {err && (
        <p className="text-xs text-red-400 bg-red-400/10 rounded px-2 py-1 mt-3">{err}</p>
      )}

      {arm?.last_reason && stage === 'disarmed' && (
        <p className="text-xs text-gray-600 mt-3">Last: {arm.last_reason}</p>
      )}
    </div>
  )
}

export default PerpsArmControl
