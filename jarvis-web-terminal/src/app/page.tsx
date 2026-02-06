'use client';

import { SentimentHub } from '@/components/features/SentimentHub';
import { useMarketData } from '@/hooks/useMarketData';
import { useSentimentData } from '@/hooks/useSentimentData';
import { MarketChart } from '@/components/features/MarketChart';
import { TradePanel } from '@/components/features/TradePanel';
import { DashboardGrid } from '@/components/features/DashboardGrid';
import { NeuralLattice } from '@/components/visuals/NeuralLattice';
import { TradingGuard, ConfidenceBadge } from '@/components/features/TradingGuard';
import { SentimentDisplay } from '@/components/features/StatGlyph';
import { AIPicks } from '@/components/features/AIPicks';
import { PerformanceTracker } from '@/components/features/PerformanceTracker';
import { QuickBuyTable } from '@/components/features/QuickBuyTable';
import { AIMarketReport } from '@/components/features/AIMarketReport';
import { AIConvictionPicks } from '@/components/features/AIConvictionPicks';
import { BagsTop15 } from '@/components/features/BagsTop15';
import { SentimentHubActions } from '@/components/features/SentimentHubActions';
import { ModelSwitcher } from '@/components/features/ModelSwitcher';

export default function Home() {
  const { data: marketData, loading } = useMarketData();
  const { marketRegime, stats } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden font-sans">
      <NeuralLattice />

      {/* Main Content */}
      <main className="flex-1 flex flex-col pt-24 gap-6 relative z-10 w-full">

        {/* Top: Metrics Dashboard */}
        <section className="w-full">
          <DashboardGrid />
        </section>

        {/* Middle: Main Trading Interface */}
        <section className="grid grid-cols-1 xl:grid-cols-12 gap-6 w-full min-h-[600px]">

          {/* Left: Signal Feed + Sentiment */}
          <div className="xl:col-span-3 flex flex-col gap-4 max-h-[800px] overflow-y-auto pr-2 custom-scrollbar">
            {/* Trading Safety Status */}
            <TradingGuard symbol="SOL" className="mb-2" />

            <div className="flex items-center justify-between mb-2">
              <h3 className="font-display font-bold text-lg text-text-primary">LIVE SIGNALS</h3>
              <div className="flex gap-2 items-center">
                <span className="w-2 h-2 rounded-full bg-accent-neon animate-pulse" />
                <span className="text-xs font-mono text-text-muted">SCANNING</span>
              </div>
            </div>
            <div className="space-y-4">
              {loading ? (
                <div className="text-center py-12 font-mono text-text-muted animate-pulse">
                  INITIALIZING BAGS.FM UPLINK...
                </div>
              ) : (
                <SentimentHub data={marketData} />
              )}
            </div>

            {/* Sentiment Overview */}
            <div className="card-glass p-4 mt-4">
              <h4 className="text-xs font-mono text-text-muted mb-3 uppercase">Market Sentiment</h4>
              <SentimentDisplay
                overall={Math.round(stats.avgBuySellRatio * 25)}
                social={Math.min(100, stats.bullishCount * 10)}
                market={marketRegime.solChange24h > 0 ? Math.min(100, 50 + marketRegime.solChange24h * 5) : Math.max(0, 50 + marketRegime.solChange24h * 5)}
                technical={Math.round(stats.avgBuySellRatio * 20)}
              />
            </div>
          </div>

          {/* Center: Charting Engine */}
          <div className="xl:col-span-6 flex flex-col gap-4">
            <div className="card-glass p-0 overflow-hidden h-full min-h-[500px] relative">
              <div className="absolute top-4 left-4 z-10 flex gap-4 items-center">
                <div className="flex flex-col">
                  <span className="font-display font-bold text-2xl text-text-primary">SOL/USDC</span>
                  <span className="font-mono text-xs text-text-muted">JUPITER AGGREGATOR</span>
                </div>
                <div className="h-10 w-[1px] bg-border-primary" />
                <div className="flex flex-col">
                  <span className="font-mono font-bold text-accent-neon">
                    {marketRegime.solPrice > 0 ? `$${marketRegime.solPrice.toFixed(2)}` : '...'}
                  </span>
                  <span className={`font-mono text-xs ${marketRegime.solChange24h >= 0 ? 'text-accent-success' : 'text-red-400'}`}>
                    {marketRegime.solChange24h >= 0 ? '+' : ''}{marketRegime.solChange24h.toFixed(1)}%
                  </span>
                </div>
                {/* Confidence Badge */}
                <ConfidenceBadge symbol="SOL" />
              </div>
              <MarketChart />
            </div>
          </div>

          {/* Right: Execution Panel */}
          <div className="xl:col-span-3 flex flex-col gap-4">
            <TradePanel />

            {/* Performance Summary */}
            <PerformanceTracker />
          </div>

        </section>

        {/* AI Intelligence Section - Market Report + Conviction Picks */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 w-full">
          <AIMarketReport />
          <AIConvictionPicks />
        </section>

        {/* Bags.fm Launches + Quick Buy Table */}
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">
          <BagsTop15 />
          <div className="space-y-6">
            <QuickBuyTable />
          </div>
        </section>

        {/* Sentiment Hub Actions - Full /demo Menu */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 w-full pb-8">
          <div className="lg:col-span-2">
            <AIPicks />
          </div>
          <div className="space-y-6">
            <SentimentHubActions />
            <ModelSwitcher />
          </div>
        </section>

      </main>
    </div>
  );
}

