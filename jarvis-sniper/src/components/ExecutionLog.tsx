'use client';

import { ScrollText, Crosshair, TrendingUp, TrendingDown, XCircle, SkipForward, AlertCircle } from 'lucide-react';
import { useSniperStore, type ExecutionEvent } from '@/stores/useSniperStore';

const TYPE_CONFIG: Record<ExecutionEvent['type'], { icon: any; color: string; label: string }> = {
  snipe:       { icon: Crosshair,    color: 'text-accent-neon',    label: 'SNIPE' },
  tp_exit:     { icon: TrendingUp,   color: 'text-accent-neon',    label: 'TP HIT' },
  sl_exit:     { icon: TrendingDown,  color: 'text-accent-error',   label: 'SL HIT' },
  manual_exit: { icon: XCircle,       color: 'text-accent-warning',  label: 'CLOSE' },
  error:       { icon: AlertCircle,   color: 'text-accent-error',   label: 'ERROR' },
  skip:        { icon: SkipForward,   color: 'text-text-muted',     label: 'SKIP' },
};

export function ExecutionLog() {
  const { executionLog } = useSniperStore();

  return (
    <div className="card-glass p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Execution Log</h2>
        </div>
        <span className="text-[10px] font-mono text-text-muted">{executionLog.length} events</span>
      </div>

      <div className="max-h-[300px] overflow-y-auto custom-scrollbar space-y-1.5">
        {executionLog.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-6 gap-2">
            <ScrollText className="w-5 h-5 text-text-muted" />
            <p className="text-[11px] text-text-muted">No executions yet</p>
          </div>
        ) : (
          executionLog.map((event) => {
            const cfg = TYPE_CONFIG[event.type];
            const Icon = cfg.icon;
            const time = new Date(event.timestamp);
            const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

            return (
              <div
                key={event.id}
                className="flex items-center gap-3 p-2 rounded-lg bg-bg-secondary/40 animate-slide-in"
              >
                <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${cfg.color}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[9px] font-mono font-bold uppercase ${cfg.color}`}>{cfg.label}</span>
                    <span className="text-xs font-bold text-text-primary">{event.symbol}</span>
                    {event.amount != null && (
                      <span className="text-[10px] font-mono text-text-muted">{event.amount.toFixed(3)} SOL</span>
                    )}
                  </div>
                  {event.reason && (
                    <p className="text-[9px] text-text-muted truncate">{event.reason}</p>
                  )}
                </div>
                <div className="flex flex-col items-end flex-shrink-0">
                  {event.pnlPercent != null && (
                    <span className={`text-[10px] font-mono font-bold ${event.pnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                      {event.pnlPercent >= 0 ? '+' : ''}{event.pnlPercent.toFixed(1)}%
                    </span>
                  )}
                  <span className="text-[9px] font-mono text-text-muted">{timeStr}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
