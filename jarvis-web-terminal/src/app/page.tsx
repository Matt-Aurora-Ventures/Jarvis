'use client';

import { useMarketData } from '@/hooks/useMarketData';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { PriceChart } from '@/components/features/PriceChart';
import { TradePanel } from '@/components/features/TradePanel';
import { DashboardGrid } from '@/components/features/DashboardGrid';
import { PerformanceTracker } from '@/components/features/PerformanceTracker';
import { AIMarketReport } from '@/components/features/AIMarketReport';
import { AIConvictionPicks } from '@/components/features/AIConvictionPicks';
import { BagsTop15 } from '@/components/features/BagsTop15';
import { XStocksPanel } from '@/components/features/xStocksPanel';
import { GrokLiveBar } from '@/components/features/GrokLiveBar';
import { TokenSearch } from '@/components/features/TokenSearch';
import { SLTPMonitor } from '@/components/features/SLTPMonitor';
import { PositionsPanel } from '@/components/features/PositionsPanel';
import { AITradeSignals } from '@/components/features/AITradeSignals';
import { TrendingTokens } from '@/components/features/TrendingTokens';
import { WatchlistPanel } from '@/components/features/WatchlistPanel';
import { TokenDrawer } from '@/components/features/TokenDrawer';
import { TokenCompare } from '@/components/features/TokenCompare';
import { MarketNewsPanel } from '@/components/features/MarketNewsPanel';
import { useGrokLive } from '@/hooks/useGrokLive';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useTokenStore } from '@/stores/useTokenStore';
import { POOLS } from '@/lib/chart-data';

// Default SOL pool address used when no token is selected
const DEFAULT_POOL = POOLS.SOL;

export default function Home() {
  useMarketData();

  const {
    countdown,
    isRefreshing,
    lastRefreshed,
    budgetStatus,
    scores: grokScores,
    forceRefresh,
  } = useGrokLive({ enabled: true });

  // Global token selection from TokenSearch
  const selectedToken = useTokenStore((s) => s.selectedToken);

  // Derive pool address and symbol from selected token (default to SOL)
  const activePoolAddress = selectedToken?.poolAddress ?? DEFAULT_POOL;
  const activeTokenSymbol = selectedToken?.symbol ?? 'SOL';

  // Global keyboard shortcuts for power users
  useKeyboardShortcuts({
    onSearch: () => {
      document.getElementById('token-search-input')?.focus();
    },
  });

  return (
    <div className="min-h-screen flex flex-col">
      {/* Ambient Background */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="ambient-orb absolute top-1/4 left-1/4 w-96 h-96 bg-accent-neon/[0.04] rounded-full blur-[128px]" />
        <div className="ambient-orb-2 absolute bottom-1/3 right-1/4 w-80 h-80 bg-accent-neon/[0.03] rounded-full blur-[128px]" />
        <div className="ambient-orb-3 absolute top-2/3 left-1/2 w-64 h-64 bg-accent-success/[0.02] rounded-full blur-[128px]" />
      </div>

      <SLTPMonitor />

      <div className="flex-1 pt-[100px] pb-4 px-2 sm:px-3 lg:px-6 max-w-[1920px] mx-auto w-full">
        {/* Token Search */}
        <TokenSearch />

        {/* Grok Live Engine Bar */}
        <GrokLiveBar
          countdown={countdown}
          isRefreshing={isRefreshing}
          lastRefreshed={lastRefreshed}
          budgetStatus={budgetStatus}
          tokenCount={grokScores.size}
          onRefresh={forceRefresh}
        />

        {/* Main 2-column: Content + Trade */}
        <section className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 mt-4">
          {/* Left: Chart + Scrollable Content (buyable items up, strategies down) */}
          <div className="flex flex-col gap-4">
            <ErrorBoundary name="Price Chart">
              <PriceChart poolAddress={activePoolAddress} tokenSymbol={activeTokenSymbol} />
            </ErrorBoundary>
            <ErrorBoundary name="Trending Tokens">
              <TrendingTokens />
            </ErrorBoundary>
            <ErrorBoundary name="AI Conviction Picks">
              <AIConvictionPicks />
            </ErrorBoundary>
            <ErrorBoundary name="Market News">
              <MarketNewsPanel />
            </ErrorBoundary>
            <ErrorBoundary name="Bags Top 15">
              <BagsTop15 />
            </ErrorBoundary>
            <ErrorBoundary name="Dashboard">
              <DashboardGrid />
            </ErrorBoundary>
            <ErrorBoundary name="Positions">
              <PositionsPanel />
            </ErrorBoundary>
            <ErrorBoundary name="XStocks">
              <XStocksPanel />
            </ErrorBoundary>
            <ErrorBoundary name="AI Market Report">
              <AIMarketReport />
            </ErrorBoundary>
            <ErrorBoundary name="AI Trade Signals">
              <AITradeSignals poolAddress={activePoolAddress} tokenSymbol={activeTokenSymbol} />
            </ErrorBoundary>
            <ErrorBoundary name="Token Compare">
              <TokenCompare />
            </ErrorBoundary>
          </div>

          {/* Right: Trade Panel (sticky on desktop, max-width constrained on mobile) */}
          <div className="lg:sticky lg:top-[104px] lg:self-start flex flex-col gap-4 max-w-md lg:max-w-none mx-auto lg:mx-0 w-full">
            <ErrorBoundary name="Trade Panel">
              <TradePanel />
            </ErrorBoundary>
            <ErrorBoundary name="Performance Tracker">
              <PerformanceTracker />
            </ErrorBoundary>
            <ErrorBoundary name="Watchlist">
              <WatchlistPanel />
            </ErrorBoundary>
          </div>
        </section>
      </div>

      <TokenDrawer />
    </div>
  );
}
