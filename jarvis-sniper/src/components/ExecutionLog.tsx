'use client';

import { useState } from 'react';
import { ScrollText, Crosshair, TrendingUp, TrendingDown, XCircle, SkipForward, AlertCircle, Loader2, ShieldCheck, List, Activity } from 'lucide-react';
import { useSniperStore, type ExecutionEvent } from '@/stores/useSniperStore';

const TYPE_CONFIG: Record<ExecutionEvent['type'], { icon: any; color: string; label: string }> = {
  snipe:       { icon: Crosshair,    color: 'text-accent-neon',    label: 'SNIPE' },
  exit_pending:{ icon: Loader2,      color: 'text-accent-warning', label: 'PENDING' },
  tp_exit:     { icon: TrendingUp,   color: 'text-accent-neon',    label: 'TP HIT' },
  sl_exit:     { icon: TrendingDown,  color: 'text-accent-error',   label: 'SL HIT' },
  manual_exit: { icon: XCircle,       color: 'text-accent-warning',  label: 'CLOSE' },
  error:       { icon: AlertCircle,   color: 'text-accent-error',   label: 'ERROR' },
  skip:        { icon: SkipForward,   color: 'text-text-muted',     label: 'SKIP' },
  info:        { icon: ShieldCheck,   color: 'text-blue-400',       label: 'INFO' },
};

/* ---------- dot color by event type ---------- */
function dotColorClass(type: ExecutionEvent['type']): string {
  switch (type) {
    case 'snipe':
    case 'tp_exit':
      return 'border-green-400 bg-green-400/30';
    case 'sl_exit':
    case 'error':
      return 'border-red-400 bg-red-400/30';
    case 'exit_pending':
      return 'border-yellow-400 bg-yellow-400/30';
    case 'skip':
    case 'info':
    default:
      return 'border-gray-500 bg-gray-500/30';
  }
}

/* ---------- glow ring for exit types ---------- */
function glowRing(type: ExecutionEvent['type']): string {
  if (type === 'tp_exit') return 'ring-2 ring-green-400/40';
  if (type === 'sl_exit') return 'ring-2 ring-red-400/40';
  return '';
}

/* ---------- group related events (snipe -> exit for same symbol) ---------- */
function isGroupedWithPrev(events: ExecutionEvent[], idx: number): boolean {
  if (idx === 0) return false;
  const cur = events[idx];
  const prev = events[idx - 1];
  // same symbol + one is an entry and the other is an exit
  if (cur.symbol !== prev.symbol) return false;
  const entryTypes: ExecutionEvent['type'][] = ['snipe'];
  const exitTypes: ExecutionEvent['type'][] = ['tp_exit', 'sl_exit', 'manual_exit'];
  const curIsEntry = entryTypes.includes(cur.type);
  const curIsExit = exitTypes.includes(cur.type);
  const prevIsEntry = entryTypes.includes(prev.type);
  const prevIsExit = exitTypes.includes(prev.type);
  return (curIsEntry && prevIsExit) || (curIsExit && prevIsEntry);
}

/* ---------- Cumulative P&L Sparkline ---------- */
function PnlSparkline({ events }: { events: ExecutionEvent[] }) {
  const pnlEvents = events.filter(e => e.pnlPercent != null).reverse(); // chronological
  if (pnlEvents.length < 2) return null;

  let cumulative = 0;
  const points = pnlEvents.map((e, i) => {
    cumulative += e.pnlPercent!;
    return { x: i, y: cumulative };
  });

  const maxAbs = Math.max(...points.map(p => Math.abs(p.y)), 1);
  const width = 100;
  const height = 60;
  const midY = height / 2;

  const pathD = points.map((p, i) => {
    const x = (p.x / Math.max(points.length - 1, 1)) * width;
    const y = midY - (p.y / maxAbs) * (midY - 4);
    return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  const fillD = pathD + ` L ${width} ${midY} L 0 ${midY} Z`;
  const lastPnl = points[points.length - 1]?.y ?? 0;
  const color = lastPnl >= 0 ? '#00ff88' : '#ff4466';

  const lastX = ((points.length - 1) / Math.max(points.length - 1, 1)) * width;
  const lastY = midY - (lastPnl / maxAbs) * (midY - 4);

  return (
    <div className="mt-2 px-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[8px] font-mono text-text-muted uppercase">Cumulative P&amp;L</span>
        <span className={`text-[10px] font-mono font-bold ${lastPnl >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
          {lastPnl >= 0 ? '+' : ''}{lastPnl.toFixed(1)}%
        </span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[60px]" preserveAspectRatio="none">
        {/* Zero line */}
        <line x1="0" y1={midY} x2={width} y2={midY} stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
        {/* Fill */}
        <path d={fillD} fill={color} opacity="0.1" />
        {/* Line */}
        <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        {/* End dot */}
        <circle cx={lastX} cy={lastY} r="2" fill={color} />
      </svg>
    </div>
  );
}

/* ---------- Timeline View ---------- */
function TimelineView({ events }: { events: ExecutionEvent[] }) {
  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-6 gap-2">
        <ScrollText className="w-5 h-5 text-text-muted" />
        <p className="text-[11px] text-text-muted">No executions yet</p>
      </div>
    );
  }

  return (
    <>
      <div className="max-h-[240px] overflow-y-auto custom-scrollbar">
        {events.map((event, idx) => {
          const cfg = TYPE_CONFIG[event.type];
          const time = new Date(event.timestamp);
          const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
          const isLast = idx === events.length - 1;
          const grouped = isGroupedWithPrev(events, idx);

          return (
            <div
              key={event.id}
              className={`flex gap-3 ${grouped ? 'bg-white/[0.02] -mt-px rounded-md' : ''}`}
            >
              {/* Time column */}
              <span className="text-[9px] font-mono text-text-muted w-14 text-right pt-1.5 flex-shrink-0">
                {timeStr}
              </span>

              {/* Timeline dot + line */}
              <div className="flex flex-col items-center flex-shrink-0">
                <div className={`w-2.5 h-2.5 rounded-full border-2 ${dotColorClass(event.type)} ${glowRing(event.type)}`} />
                {!isLast && <div className="w-px flex-1 bg-border-primary/50 min-h-[16px]" />}
              </div>

              {/* Content */}
              <div className="flex-1 pb-3 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-[9px] font-mono font-bold ${cfg.color}`}>{cfg.label}</span>
                  <span className="text-xs font-bold text-text-primary">{event.symbol}</span>
                  {event.amount != null && (
                    <span className="text-[10px] font-mono text-text-muted">{event.amount.toFixed(3)} SOL</span>
                  )}
                  {event.pnlPercent != null && (
                    <span className={`text-[10px] font-mono font-bold ${event.pnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                      {event.pnlPercent >= 0 ? '+' : ''}{event.pnlPercent.toFixed(1)}%
                    </span>
                  )}
                </div>
                {event.reason && <p className="text-[9px] text-text-muted truncate">{event.reason}</p>}
              </div>
            </div>
          );
        })}
      </div>

      {/* Sparkline */}
      <PnlSparkline events={events} />
    </>
  );
}

/* ---------- Main Component ---------- */
export function ExecutionLog() {
  const { executionLog } = useSniperStore();
  const [view, setView] = useState<'list' | 'timeline'>('list');

  return (
    <div className="card-glass p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Execution Log</h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-text-muted">{executionLog.length} events</span>
          <div className="flex items-center gap-0.5 bg-bg-tertiary rounded-md p-0.5">
            <button
              onClick={() => setView('list')}
              className={`p-1 rounded transition-colors ${view === 'list' ? 'bg-bg-secondary text-text-primary' : 'text-text-muted hover:text-text-secondary'}`}
              title="List view"
            >
              <List className="w-3 h-3" />
            </button>
            <button
              onClick={() => setView('timeline')}
              className={`p-1 rounded transition-colors ${view === 'timeline' ? 'bg-bg-secondary text-text-primary' : 'text-text-muted hover:text-text-secondary'}`}
              title="Timeline view"
            >
              <Activity className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {view === 'timeline' ? (
        <TimelineView events={executionLog} />
      ) : (
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
                  <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${cfg.color} ${event.type === 'exit_pending' ? 'animate-spin' : ''}`} />
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
      )}
    </div>
  );
}
