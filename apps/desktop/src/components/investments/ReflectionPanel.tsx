import React from 'react'
import type { Reflection } from './useInvestmentData'

// ---------------------------------------------------------------------------
// Reflection Panel — surfaces memory / calibration data from the reflection
// module (PRD Section F: memory + reflection as a first-order feature)
// ---------------------------------------------------------------------------

interface ReflectionPanelProps {
  reflections: Reflection[]
  loading: boolean
}

function accuracyColor(pct: number) {
  if (pct >= 75) return 'text-green-400'
  if (pct >= 50) return 'text-yellow-400'
  return 'text-red-400'
}

function accuracyBar(pct: number) {
  if (pct >= 75) return 'bg-green-500'
  if (pct >= 50) return 'bg-yellow-500'
  return 'bg-red-500'
}

export function ReflectionPanel({ reflections, loading }: ReflectionPanelProps) {
  if (loading && reflections.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 animate-pulse">
        <div className="h-5 bg-gray-800 rounded w-48 mb-4" />
        <div className="space-y-3">
          {[1, 2].map(i => (
            <div key={i} className="h-20 bg-gray-800 rounded-lg" />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6">
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold text-white">Calibration &amp; Reflection</h2>
        <span className="text-xs text-gray-600 bg-gray-800 px-2 py-0.5 rounded-full">
          post-trade memory
        </span>
      </div>

      <p className="text-xs text-gray-600 mb-4">
        After each rebalance the system reflects on prediction accuracy and updates calibration hints
        fed into the next agent cycle. Lessons accumulate over time.
      </p>

      {reflections.length === 0 ? (
        <div className="text-sm text-gray-500 text-center py-8">
          No reflections yet — generated 24–72 hours after each rebalance.
        </div>
      ) : (
        <div className="space-y-3">
          {reflections.map(r => (
            <div
              key={r.id}
              className="bg-gray-800/40 border border-gray-700/50 rounded-lg p-4 space-y-3"
            >
              {/* Header row */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">
                  {new Date(r.timestamp).toLocaleDateString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })}
                </span>
                <div className="flex items-center gap-2">
                  <div className="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${accuracyBar(r.accuracy_pct)}`}
                      style={{ width: `${r.accuracy_pct}%` }}
                    />
                  </div>
                  <span className={`text-xs font-semibold ${accuracyColor(r.accuracy_pct)}`}>
                    {r.accuracy_pct.toFixed(0)}% accuracy
                  </span>
                </div>
              </div>

              {/* Lessons */}
              {r.lessons && r.lessons.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-gray-500 block mb-1.5">
                    Lessons learned
                  </span>
                  <ul className="space-y-1">
                    {r.lessons.map((lesson, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs text-gray-400">
                        <span className="text-violet-500 mt-0.5 flex-shrink-0">›</span>
                        {lesson}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Adjustments */}
              {r.adjustments && r.adjustments.length > 0 && (
                <div>
                  <span className="text-xs font-medium text-gray-500 block mb-1.5">
                    Calibration adjustments for next cycle
                  </span>
                  <ul className="space-y-1">
                    {r.adjustments.map((adj, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-xs text-gray-400">
                        <span className="text-blue-500 mt-0.5 flex-shrink-0">↻</span>
                        {adj}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ReflectionPanel
