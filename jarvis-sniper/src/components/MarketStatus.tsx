'use client';

import type { MarketPhase } from '@/lib/tv-screener';

interface MarketStatusProps {
  marketPhase: MarketPhase;
  lastUpdated: Date | null;
}

const PHASE_CONFIG: Record<
  MarketPhase,
  { label: string; dotClass: string; textClass: string }
> = {
  PRE_MARKET: {
    label: 'Pre-Market',
    dotClass: 'bg-amber-400',
    textClass: 'text-amber-400',
  },
  REGULAR: {
    label: 'Market Open',
    dotClass: 'bg-[var(--accent-neon)]',
    textClass: 'text-[var(--accent-neon)]',
  },
  AFTER_HOURS: {
    label: 'After-Hours',
    dotClass: 'bg-blue-400',
    textClass: 'text-blue-400',
  },
  CLOSED: {
    label: 'Market Closed',
    dotClass: 'bg-[var(--text-muted)]',
    textClass: 'text-[var(--text-muted)]',
  },
};

/**
 * Format the time elapsed since `date` as a human-friendly relative string.
 */
function formatRelativeTime(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

/**
 * Compact market phase indicator for the header bar.
 *
 * Shows a colored dot, the market phase label, and a relative
 * timestamp of the last data update.
 *
 * Uses CSS variables from globals.css to respect the app theme system.
 */
export function MarketStatus({ marketPhase, lastUpdated }: MarketStatusProps) {
  const cfg = PHASE_CONFIG[marketPhase];

  return (
    <div
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border"
      style={{
        background: 'var(--bg-tertiary)',
        borderColor: 'var(--border-primary)',
      }}
    >
      {/* Animated dot for active phases */}
      <span className="relative flex h-2 w-2">
        {marketPhase !== 'CLOSED' && (
          <span
            className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-40 ${cfg.dotClass}`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${cfg.dotClass}`} />
      </span>

      <span className={`text-[10px] font-mono font-semibold ${cfg.textClass}`}>
        {cfg.label}
      </span>

      {lastUpdated && (
        <span
          className="text-[9px] font-mono"
          style={{ color: 'var(--text-muted)' }}
        >
          {formatRelativeTime(lastUpdated)}
        </span>
      )}
    </div>
  );
}
