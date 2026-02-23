import React from 'react'
import type { PerpsAuditEvent } from './usePerpsData'

interface Props {
  events: PerpsAuditEvent[]
}

function typeColor(type: string) {
  if (type.includes('arm')) return 'text-yellow-400'
  if (type.includes('disarm')) return 'text-orange-400'
  if (type.includes('open') || type.includes('long') || type.includes('buy')) return 'text-green-400'
  if (type.includes('close') || type.includes('short') || type.includes('exit')) return 'text-red-400'
  if (type.includes('error') || type.includes('fail')) return 'text-red-400'
  return 'text-gray-400'
}

export function PerpsAuditLog({ events }: Props) {
  const recent = events.slice(0, 20)

  return (
    <div className="bg-gray-900 border border-gray-700 rounded-xl p-5">
      <h3 className="text-sm font-semibold text-white mb-3">Audit Log</h3>

      {recent.length === 0 ? (
        <div className="text-xs text-gray-600 text-center py-6">No audit events yet</div>
      ) : (
        <div className="overflow-y-auto max-h-52 space-y-1 font-mono">
          {recent.map((ev, idx) => (
            <div key={idx} className="flex items-start gap-2 text-xs hover:bg-gray-800/30 px-1 py-0.5 rounded">
              <span className="text-gray-600 flex-shrink-0 w-20">
                {new Date(ev.ts * 1000).toLocaleTimeString()}
              </span>
              <span className={`flex-shrink-0 font-medium ${typeColor(ev.type)}`}>
                {ev.type}
              </span>
              {ev.ok === false && <span className="text-red-500 flex-shrink-0">✗</span>}
              {ev.ok === true && <span className="text-green-500/60 flex-shrink-0">✓</span>}
              {ev.detail && (
                <span className="text-gray-500 truncate">{ev.detail}</span>
              )}
              {ev.actor && (
                <span className="text-gray-700 ml-auto flex-shrink-0">{ev.actor}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default PerpsAuditLog
