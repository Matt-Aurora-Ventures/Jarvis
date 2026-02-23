'use client';

import { useEffect, useState, useRef } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';

interface FeedItem {
  id: string;
  event: string;
  message: string;
  detail?: string;
  timestamp: number;
  color: 'green' | 'red' | 'yellow' | 'blue' | 'muted';
}

const EVENT_CONFIG: Record<string, { icon: string; color: FeedItem['color']; label: string }> = {
  trade: { icon: '\u25B6', color: 'green', label: 'TRADE' },
  detection: { icon: '\u25C9', color: 'blue', label: 'DETECT' },
  safety_pass: { icon: '\u2713', color: 'green', label: 'SAFE' },
  safety_fail: { icon: '\u2717', color: 'red', label: 'REJECT' },
  exit: { icon: '\u25A0', color: 'yellow', label: 'EXIT' },
  circuit_breaker: { icon: '\u26A0', color: 'red', label: 'HALT' },
  error: { icon: '!', color: 'red', label: 'ERROR' },
  heartbeat: { icon: '\u2022', color: 'muted', label: 'PING' },
};

const COLOR_MAP = {
  green: 'text-[#22c55e]',
  red: 'text-[#ef4444]',
  yellow: 'text-[#eab308]',
  blue: 'text-[#3b82f6]',
  muted: 'text-[var(--text-muted)]',
};

const BG_MAP = {
  green: 'bg-[#22c55e11]',
  red: 'bg-[#ef444411]',
  yellow: 'bg-[#eab30811]',
  blue: 'bg-[#3b82f611]',
  muted: 'bg-[var(--bg-secondary)]',
};

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function buildFeedItem(event: string, data: Record<string, unknown>, ts: number): FeedItem {
  const cfg = EVENT_CONFIG[event] ?? { icon: '\u2022', color: 'muted' as const, label: event.toUpperCase() };
  let message = '';
  let detail: string | undefined;

  switch (event) {
    case 'trade':
      message = `Sniped ${data.symbol ?? 'unknown'}`;
      detail = data.mode === 'paper' ? 'PAPER' : 'LIVE';
      break;
    case 'detection':
      message = `New token: ${data.symbol ?? data.mint ?? 'unknown'}`;
      detail = `via ${data.source ?? '?'}`;
      break;
    case 'safety_pass':
      message = `${data.symbol ?? 'token'} passed safety`;
      detail = data.score ? `${((data.score as number) * 100).toFixed(0)}%` : undefined;
      break;
    case 'safety_fail':
      message = `${data.symbol ?? 'token'} rejected`;
      detail = (data.reason as string) ?? undefined;
      break;
    case 'exit':
      message = `Closed ${data.symbol ?? 'position'}`;
      detail = data.pnl_usd ? `${(data.pnl_usd as number) >= 0 ? '+' : ''}$${(data.pnl_usd as number).toFixed(2)}` : (data.reason as string) ?? undefined;
      break;
    case 'circuit_breaker':
      message = 'Circuit breaker tripped';
      detail = (data.reason as string) ?? undefined;
      break;
    default:
      message = (data.message as string) ?? event;
  }

  return {
    id: `${ts}-${Math.random().toString(36).slice(2, 7)}`,
    event,
    message,
    detail,
    timestamp: ts,
    color: cfg.color,
  };
}

const MAX_ITEMS = 50;

export function ActivityFeed() {
  const { connected, lastMessage } = useWebSocket();
  const [items, setItems] = useState<FeedItem[]>([]);
  const feedRef = useRef<HTMLDivElement>(null);

  // Process incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;
    const { event, data, timestamp } = lastMessage as { event: string; data: Record<string, unknown>; timestamp: number };

    // Skip heartbeats from the feed
    if (event === 'heartbeat') return;

    const item = buildFeedItem(event, data ?? {}, timestamp ?? Date.now());
    setItems(prev => [item, ...prev].slice(0, MAX_ITEMS));
  }, [lastMessage]);

  // Auto-scroll to top on new items (feed is newest-first)
  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = 0;
    }
  }, [items.length]);

  return (
    <div className="card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">
          Live Activity
        </h2>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-[#22c55e] pulse-green' : 'bg-[#ef4444]'}`} />
          <span className="text-[10px] text-[var(--text-muted)]">
            {connected ? 'CONNECTED' : 'OFFLINE'}
          </span>
        </div>
      </div>

      {/* Feed */}
      <div ref={feedRef} className="flex-1 overflow-y-auto space-y-1 min-h-[200px] max-h-[400px]">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[var(--text-muted)] text-xs gap-2">
            <div className="w-8 h-8 rounded-full border border-[var(--border)] flex items-center justify-center">
              <span className="text-sm">{connected ? '\u23F3' : '\u26A1'}</span>
            </div>
            <span>{connected ? 'Waiting for activity...' : 'Connecting to sniper...'}</span>
          </div>
        ) : (
          items.map((item) => {
            const cfg = EVENT_CONFIG[item.event] ?? { icon: '\u2022', label: item.event };
            return (
              <div
                key={item.id}
                className={`flex items-start gap-2 px-2 py-1.5 rounded-md ${BG_MAP[item.color]} fade-in`}
              >
                {/* Icon */}
                <span className={`text-xs mt-0.5 ${COLOR_MAP[item.color]} shrink-0 w-4 text-center`}>
                  {cfg.icon}
                </span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-[10px] font-bold ${COLOR_MAP[item.color]}`}>
                      {cfg.label}
                    </span>
                    <span className="text-xs text-[var(--text-primary)] truncate">
                      {item.message}
                    </span>
                  </div>
                  {item.detail && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {item.detail}
                    </span>
                  )}
                </div>

                {/* Timestamp */}
                <span className="text-[10px] text-[var(--text-muted)] shrink-0 mono">
                  {formatTime(item.timestamp)}
                </span>
              </div>
            );
          })
        )}
      </div>

      {/* Footer stats */}
      <div className="mt-3 pt-2 border-t border-[var(--border)] flex items-center justify-between text-[10px] text-[var(--text-muted)]">
        <span>{items.length} events</span>
        <span>{items.filter(i => i.event === 'trade').length} trades</span>
      </div>
    </div>
  );
}
