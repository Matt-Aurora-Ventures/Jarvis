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
import { useTabNotifications } from '@/hooks/useTabNotifications';

export default function SniperDashboard() {
  // Retarget the persistent automation engine to the main sniper scope when
  // navigating here. This must work even while auto is ON (no silent "dead"
  // bot after switching tabs/pages).
  useEffect(() => {
    const state = useSniperStore.getState();
    const preset = String(state.activePreset || '');
    const presetLooksNonMain =
      preset.startsWith('bags_') ||
      preset.startsWith('xstock_') ||
      preset.startsWith('prestock_') ||
      preset.startsWith('index_');

    // Main sniper supports memecoin + bluechip modes. If we're coming from Bags/TradFi
    // (or preset got out of sync), reset to a sane main preset without toggling auto off.
    if (presetLooksNonMain || (state.assetFilter !== 'memecoin' && state.assetFilter !== 'bluechip')) {
      state.loadPreset('pump_fresh_tight');
    }
  }, []);

  // Automated SL/TP: monitors positions and triggers sells when thresholds hit
  useAutomatedRiskManagement();

  // Tab title flashing for important events (snipes, TP/SL exits)
  useTabNotifications();

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />
      <FundRecoveryBanner />

      <main className="app-shell flex-1 min-h-0 py-2 lg:py-4 overflow-hidden flex flex-col">
        {/* Mobile: bottom-tab terminal (avoid stacked, congested UI) */}
        <div className="lg:hidden flex-1 min-h-0">
          <MobileTerminalShell routeKey="sniper" />
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
