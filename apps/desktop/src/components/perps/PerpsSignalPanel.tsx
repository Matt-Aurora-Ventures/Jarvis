import React from 'react'
import type { PerpsSignal } from './usePerpsData'

interface Props {
  signal: PerpsSignal | null
}

function directionStyle(d: string) {
  if (d === 'LONG') return 'bg-green-500/15 text-green-400 border border-green-500/30'
  if (d === 'SHORT') return 'bg-red-500/15 text-red-400 border border-red-500/30'
  return 'bg-gray-500/15 text-gray-400 border border-gray-500/30'
}

function confidenceColor(c: number) {
  if (c >= 0.85) return 'bg-green-500'
  if (c >= 0.75) return 'bg-yellow-500'
  return 'bg-red-500'
}

function SourceBar({ label, weight, confidence }: { label: string; weight: number; confidence?: number }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-gray-500 w-20 flex-shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-violet-500 rounded-full"
          style={{ width: `${weight * 100}%` }}
        />
      </div>
      <span className="text-gray-400 w-8 text-right">{(weight * 100).toFixed(0)}%</span>
      {confidence !== undefined && (
        <span className="text-gray-500 w-10 text-right">
          {(confidence * 100).toFixed(0)}%↑
        </span>
      )}
    </div>
  )
}

export function PerpsSignalPanel({ signal }: Props) {
  if (!signal) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 flex flex-col gap-3">
        <h3 className="text-sm font-semibold text-gray-400">AI Signal</h3>
        <div className="flex items-center justify-center h-20 text-gray-600 text-sm">
          No signal data — runner offline or mode=disabled
        </div>
      </div>
    )
  }

  const confPct = (signal.confidence * 100).toFixed(1)

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white">AI Signal</h3>
        {signal.generated_at && (
          <span className="text-xs text-gray-600">
            {new Date(signal.generated_at).toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Direction + Market */}
      <div className="flex items-center gap-3">
        <span className={`text-lg font-bold px-3 py-1 rounded-lg ${directionStyle(signal.direction)}`}>
          {signal.direction}
        </span>
        <span className="text-gray-300 font-medium">{signal.market}</span>
      </div>

      {/* Confidence bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500">Confidence</span>
          <span className="text-xs font-medium text-white">{confPct}%</span>
        </div>
        <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${confidenceColor(signal.confidence)}`}
            style={{ width: `${confPct}%` }}
          />
        </div>
      </div>

      {/* Source breakdown */}
      <div className="space-y-1.5">
        <span className="text-xs font-medium text-gray-500">Source Weights</span>
        <SourceBar
          label="Grok"
          weight={signal.sources.grok_weight}
          confidence={signal.sources.grok_confidence}
        />
        <SourceBar
          label="Momentum"
          weight={signal.sources.momentum_weight}
          confidence={signal.sources.momentum_confidence}
        />
        <SourceBar
          label="Ecosystem"
          weight={signal.sources.ecosystem_weight}
          confidence={signal.sources.ecosystem_confidence}
        />
      </div>

      {/* Cooldown */}
      {signal.cooldown_remaining_m !== undefined && signal.cooldown_remaining_m > 0 && (
        <div className="text-xs text-amber-400 bg-amber-400/10 rounded px-2 py-1">
          Cooldown: {signal.cooldown_remaining_m.toFixed(0)}m remaining
        </div>
      )}

      {/* Reasoning */}
      {signal.reasoning && (
        <p className="text-xs text-gray-500 leading-relaxed border-t border-gray-800 pt-3">
          {signal.reasoning}
        </p>
      )}
    </div>
  )
}

export default PerpsSignalPanel
