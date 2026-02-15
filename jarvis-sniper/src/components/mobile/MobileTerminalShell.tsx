'use client';

import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { BarChart3, Crosshair, Layers, ScrollText, SlidersHorizontal } from 'lucide-react';
import { GraduationFeed } from '@/components/GraduationFeed';
import { TokenChart } from '@/components/TokenChart';
import { SniperControls } from '@/components/SniperControls';
import { PositionsPanel } from '@/components/PositionsPanel';
import { WatchlistPanel } from '@/components/WatchlistPanel';
import { ExecutionLog } from '@/components/ExecutionLog';
import { PerformanceSummary } from '@/components/PerformanceSummary';

type TabKey = 'scan' | 'chart' | 'trade' | 'positions' | 'log';
type PositionsView = 'positions' | 'watchlist';

const TABS: Array<{ key: TabKey; label: string; icon: ReactNode }> = [
  { key: 'scan', label: 'Scan', icon: <Crosshair className="w-4 h-4" /> },
  { key: 'chart', label: 'Chart', icon: <BarChart3 className="w-4 h-4" /> },
  { key: 'trade', label: 'Trade', icon: <SlidersHorizontal className="w-4 h-4" /> },
  { key: 'positions', label: 'Positions', icon: <Layers className="w-4 h-4" /> },
  { key: 'log', label: 'Log', icon: <ScrollText className="w-4 h-4" /> },
];

function storageKey(routeKey?: string) {
  return `jarvis-sniper:mobile-tab:${routeKey || 'default'}`;
}

export function MobileTerminalShell(props: { routeKey?: string }) {
  const routeKey = props.routeKey || 'sniper';
  const [tab, setTab] = useState<TabKey>('scan');
  const [positionsView, setPositionsView] = useState<PositionsView>('positions');

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(storageKey(routeKey));
      const next = (raw || '') as TabKey;
      if (TABS.some((t) => t.key === next)) setTab(next);
    } catch {
      // ignore
    }
  }, [routeKey]);

  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey(routeKey), tab);
    } catch {
      // ignore
    }
  }, [routeKey, tab]);

  const content = useMemo(() => {
    switch (tab) {
      case 'scan':
        return (
          <div className="h-full min-h-0 overflow-hidden">
            <GraduationFeed />
          </div>
        );
      case 'chart':
        return (
          <div className="h-full min-h-0 overflow-hidden">
            <TokenChart fitParent />
          </div>
        );
      case 'trade':
        return (
          <div className="h-full min-h-0 overflow-y-auto custom-scrollbar pb-28">
            <SniperControls />
          </div>
        );
      case 'positions':
        return (
          <div className="h-full min-h-0 flex flex-col">
            <div className="mb-2 flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setPositionsView('positions')}
                className={`flex-1 px-3 py-2 rounded-lg text-[11px] font-mono font-semibold uppercase tracking-wider border transition-colors ${
                  positionsView === 'positions'
                    ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/25'
                    : 'bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover'
                }`}
              >
                Positions
              </button>
              <button
                type="button"
                onClick={() => setPositionsView('watchlist')}
                className={`flex-1 px-3 py-2 rounded-lg text-[11px] font-mono font-semibold uppercase tracking-wider border transition-colors ${
                  positionsView === 'watchlist'
                    ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/25'
                    : 'bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover'
                }`}
              >
                Watchlist
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar pb-28">
              {positionsView === 'positions' ? <PositionsPanel /> : <WatchlistPanel />}
            </div>
          </div>
        );
      case 'log':
        return (
          <div className="h-full min-h-0 flex flex-col gap-3 pb-28">
            <div className="card-glass p-3">
              <PerformanceSummary />
            </div>
            <div className="flex-1 min-h-0 overflow-hidden">
              <ExecutionLog fitParent />
            </div>
          </div>
        );
      default:
        return null;
    }
  }, [positionsView, tab]);

  return (
    <div className="flex flex-col min-h-0 h-full">
      <div className="flex-1 min-h-0 overflow-hidden">
        {content}
      </div>

      <nav
        className="border-t border-border-primary bg-bg-secondary/95"
        role="tablist"
        aria-label="Mobile terminal tabs"
      >
        <div className="grid grid-cols-5 gap-1 px-2 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))]">
          {TABS.map((t) => {
            const active = t.key === tab;
            return (
              <button
                key={t.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setTab(t.key)}
                className={`flex flex-col items-center justify-center gap-1 rounded-lg py-2 border transition-colors ${
                  active
                    ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/25'
                    : 'bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover hover:text-text-primary'
                }`}
              >
                {t.icon}
                <span className="text-[10px] font-mono font-semibold uppercase tracking-wider">
                  {t.label}
                </span>
              </button>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
