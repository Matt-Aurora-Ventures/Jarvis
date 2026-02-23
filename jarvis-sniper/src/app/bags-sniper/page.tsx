'use client';

import { useEffect } from 'react';
import { StatusBar } from '@/components/StatusBar';
import { GraduationFeed } from '@/components/GraduationFeed';
import { SniperControls } from '@/components/SniperControls';
import { PositionsPanel } from '@/components/PositionsPanel';
import { WatchlistPanel } from '@/components/WatchlistPanel';
import { ExecutionLog } from '@/components/ExecutionLog';
import { PerformanceSummary } from '@/components/PerformanceSummary';
import { TokenChart } from '@/components/TokenChart';
import { EarlyBetaModal } from '@/components/EarlyBetaModal';
import { BacktestPanel } from '@/components/BacktestPanel';
import { FundRecoveryBanner } from '@/components/FundRecoveryBanner';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { MobileTerminalShell } from '@/components/mobile/MobileTerminalShell';
import { useSniperStore } from '@/stores/useSniperStore';
import { useAutomatedRiskManagement } from '@/hooks/useAutomatedRiskManagement';
import { useSpotProtectionLifecycle } from '@/hooks/useSpotProtectionLifecycle';
import { useTabNotifications } from '@/hooks/useTabNotifications';

/** Bags-specific strategy presets for the info card */
const BAGS_STRATEGIES = [
  {
    id: 'bags_fresh_snipe',
    name: 'Bags Fresh Snipe',
    description: 'Targets new bags.fm launches (<48h). Locked liquidity = safe entry. Tight SL, fast alpha.',
    icon: '\u26A1', // lightning
  },
  {
    id: 'bags_momentum',
    name: 'Bags Momentum',
    description: 'Catches momentum surges on bags tokens with active communities. 5%+ hourly momentum required.',
    icon: '\u{1F680}', // rocket
  },
  {
    id: 'bags_value',
    name: 'Bags Value Hunter',
    description: 'High-quality bags tokens (score 55+) with proven communities and active builders.',
    icon: '\u{1F48E}', // gem
  },
  {
    id: 'bags_dip_buyer',
    name: 'Bags Dip Buyer',
    description: 'Buys the typical post-launch dip. Targets the second pump cycle that many bags tokens exhibit.',
    icon: '\u{1F4C9}', // chart decreasing (dip signal)
  },
  {
    id: 'bags_bluechip',
    name: 'Bags Blue Chip',
    description: 'Established bags tokens (30d+) still trading. Proven projects, lowest risk, steady returns.',
    icon: '\u{1F451}', // crown
  },
] as const;

export default function BagsSniperDashboard() {
  // Keep this page in bags scope, but preserve the currently selected
  // bags strategy instead of always resetting to the default.
  useEffect(() => {
    const state = useSniperStore.getState();
    const preset = String(state.activePreset || '');
    const nextPreset = preset.startsWith('bags_') ? preset : 'bags_fresh_snipe';
    // Only switch when needed to avoid unnecessary strategy-epoch bumps on route changes.
    if (state.activePreset !== nextPreset || state.assetFilter !== 'bags') {
      state.loadPreset(nextPreset);
    }
  }, []);

  // Automated SL/TP: monitors positions and triggers sells when thresholds hit
  useAutomatedRiskManagement();
  useSpotProtectionLifecycle();

  // Tab title flashing for important events (snipes, TP/SL exits)
  useTabNotifications();

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />
      <FundRecoveryBanner />

      <main className="app-shell flex-1 min-h-0 py-2 lg:py-4 overflow-hidden flex flex-col">
        {/* Desktop-only: Bags Strategy Presets Info Card (mobile uses the tabbed terminal) */}
        <div className="hidden lg:grid mb-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2">
          {BAGS_STRATEGIES.map((strategy) => (
            <div
              key={strategy.id}
              className="px-3 py-2.5 rounded-lg border border-border-subtle bg-bg-secondary/60 hover:border-accent-neon/30 transition-colors flex flex-col"
            >
              <div className="flex items-center gap-2 mb-1.5 flex-shrink-0">
                <span className="text-sm">{strategy.icon}</span>
                <span className="text-xs font-semibold text-text-primary tracking-wide whitespace-nowrap">
                  {strategy.name}
                </span>
              </div>
              <p className="text-[10px] text-text-secondary leading-snug break-words">
                {strategy.description}
              </p>
            </div>
          ))}
        </div>

        {/* Mobile: bottom-tab terminal */}
        <div className="lg:hidden flex-1 min-h-0">
          <MobileTerminalShell routeKey="bags-sniper" />
        </div>

        {/* Desktop: 3-column layout */}
        <div className="hidden lg:grid flex-1 min-h-0 grid-cols-[320px_1fr_minmax(0,360px)] 2xl:grid-cols-[390px_1fr_minmax(0,460px)] gap-4">
          {/* Left: Token Scanner */}
          <div className="flex flex-col min-h-0 min-w-0">
            <ErrorBoundary panelName="Token Scanner">
              <GraduationFeed />
            </ErrorBoundary>
          </div>

          {/* Center: Performance + Backtest Validation + Chart + Execution Log */}
          <div className="flex flex-col gap-4 min-h-0 min-w-0">
            <ErrorBoundary panelName="Performance Summary">
              <PerformanceSummary />
            </ErrorBoundary>
            <ErrorBoundary panelName="Backtest Validation">
              <BacktestPanel />
            </ErrorBoundary>
            <ErrorBoundary panelName="Token Chart">
              <TokenChart />
            </ErrorBoundary>
            <div className="flex-1 min-h-0">
              <ErrorBoundary panelName="Execution Log">
                <ExecutionLog />
              </ErrorBoundary>
            </div>
          </div>

          {/* Right: Controls + Positions */}
          <div className="flex flex-col gap-4 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden custom-scrollbar">
            <ErrorBoundary panelName="Sniper Controls">
              <SniperControls />
            </ErrorBoundary>
            <ErrorBoundary panelName="Watchlist">
              <WatchlistPanel />
            </ErrorBoundary>
            <ErrorBoundary panelName="Positions">
              <PositionsPanel />
            </ErrorBoundary>
          </div>
        </div>
      </main>
    </div>
  );
}
