'use client';

import { useEffect, useMemo } from 'react';
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
import { FeatureDisabledOverlay } from '@/components/ui/FeatureDisabledOverlay';
import { isSurfaceEnabled, resolveSurfaceAvailability } from '@/lib/surface-availability';
const TRADFI_PRESETS = ['xstock_intraday', 'xstock_swing', 'prestock_speculative', 'index_intraday', 'index_leveraged'];

const TRADFI_STRATEGIES = [
  {
    id: 'xstock_intraday',
    name: 'xStock Intraday',
    description: 'Tight intraday strategy for tokenized equities. Calibrated for smaller, steadier moves.',
    icon: '\u{1F4C8}',
  },
  {
    id: 'xstock_swing',
    name: 'xStock Swing',
    description: 'Multi-session momentum setup for stronger trend continuation on tokenized US stocks.',
    icon: '\u{1F3AF}',
  },
  {
    id: 'prestock_speculative',
    name: 'PreStock Speculative',
    description: 'Higher-volatility pre-IPO setup with risk-managed entries and wider target ranges.',
    icon: '\u{1F680}',
  },
  {
    id: 'index_intraday',
    name: 'Index Intraday',
    description: 'Index proxy scalping for repeated smaller edges across SPY/QQQ-style instruments.',
    icon: '\u{1F4CA}',
  },
  {
    id: 'index_leveraged',
    name: 'Index Leveraged',
    description: 'Wider risk/reward profile for leveraged index tokens (TQQQ-style).',
    icon: '\u26A1',
  },
] as const;

export default function TradFiSniperDashboard() {
  // Keep this page scoped to TradFi assets/presets (xstocks/prestocks/indexes).
  // Use loadPreset so SL/TP/filter config actually updates (not just the label).
  useEffect(() => {
    const state = useSniperStore.getState();
    const preset = String(state.activePreset || '');
    const nextPreset = TRADFI_PRESETS.includes(preset) ? preset : 'xstock_intraday';
    const expectedAsset = nextPreset.startsWith('xstock_')
      ? 'xstock'
      : nextPreset.startsWith('prestock_')
      ? 'prestock'
      : 'index';
    if (state.activePreset !== nextPreset || state.assetFilter !== expectedAsset) {
      state.loadPreset(nextPreset);
    }
  }, []);

  useAutomatedRiskManagement();
  useTabNotifications();
  const availability = useMemo(() => resolveSurfaceAvailability(), []);
  const tradfiSurface = availability.tradfi;
  const tradfiEnabled = isSurfaceEnabled(tradfiSurface);

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />
      <FundRecoveryBanner />

      <main className="app-shell relative flex-1 min-h-0 py-2 lg:py-4 overflow-hidden flex flex-col">
        <div className={tradfiEnabled ? '' : 'pointer-events-none select-none opacity-70'}>
        {/* Desktop-only: TradFi Strategy Presets Info Card (mobile uses the tabbed terminal) */}
          <div className="hidden lg:grid mb-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-2">
            {TRADFI_STRATEGIES.map((strategy) => (
              <div
                key={strategy.id}
                className="px-3 py-2.5 rounded-lg border border-border-subtle bg-bg-secondary/60 hover:border-blue-400/30 transition-colors flex flex-col"
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
            <MobileTerminalShell routeKey="tradfi-sniper" />
          </div>

          {/* Desktop: 3-column layout */}
          <div className="hidden lg:grid flex-1 min-h-0 grid-cols-[320px_1fr_minmax(0,360px)] 2xl:grid-cols-[390px_1fr_minmax(0,460px)] gap-4">
            <div className="flex flex-col min-h-0 min-w-0">
              <ErrorBoundary panelName="Token Scanner">
                <GraduationFeed />
              </ErrorBoundary>
            </div>

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
        </div>

        {!tradfiEnabled && (
          <FeatureDisabledOverlay
            testId="tradfi-disabled-overlay"
            title="TradFi Sniper Surface Disabled"
            reason={tradfiSurface.reason}
          />
        )}
      </main>
    </div>
  );
}
