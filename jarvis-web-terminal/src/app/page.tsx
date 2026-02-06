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
import { CollapsiblePanel } from '@/components/ui/CollapsiblePanel';
import { GrokLiveBar } from '@/components/features/GrokLiveBar';
import { useGrokLive } from '@/hooks/useGrokLive';
import {
  Brain,
  BarChart3,
  TrendingUp,
  Zap,
  Target,
  Newspaper,
  Activity,
  Crosshair,
  Rocket,
  LineChart,
} from 'lucide-react';

export default function Home() {
  const { data: marketData, loading } = useMarketData();
  const { marketRegime, stats } = useSentimentData({ autoRefresh: true, refreshInterval: 5 * 60 * 1000 });

  const {
    scores: grokScores,
    countdown,
    isRefreshing,
    lastRefreshed,
    budgetStatus,
    forceRefresh,
  } = useGrokLive({ enabled: true });

  return (
    <div className="min-h-screen flex flex-col relative overflow-hidden font-sans">
      <NeuralLattice />

      <main className="flex-1 flex flex-col pt-[68px] pb-2 gap-3 relative z-10 w-full px-3 lg:px-4">

        {/* Grok 4.1 Live Engine Bar */}
        <GrokLiveBar
          countdown={countdown}
          isRefreshing={isRefreshing}
          lastRefreshed={lastRefreshed}
          budgetStatus={budgetStatus}
          tokenCount={grokScores.size}
          onRefresh={forceRefresh}
        />

        {/* Stats Row - Compact Metrics */}
        <section className="w-full">
          <DashboardGrid />
        </section>

        {/* Main 3-Column Trading Layout */}
        <section className="grid grid-cols-1 xl:grid-cols-[280px_1fr_320px] gap-3 w-full flex-1">

          {/* LEFT COLUMN: Signals + Market Overview */}
          <div className="flex flex-col gap-3 max-h-[calc(100vh-220px)] overflow-y-auto custom-scrollbar pr-1">

            {/* Trading Guard */}
            <TradingGuard symbol="SOL" />

            {/* Live Signals */}
            <CollapsiblePanel
              title="LIVE SIGNALS"
              icon={<Activity className="w-4 h-4" />}
              badge="LIVE"
              defaultExpanded={true}
            >
              {loading ? (
                <div className="text-center py-8 font-mono text-text-muted animate-pulse text-sm">
                  INITIALIZING BAGS.FM UPLINK...
                </div>
              ) : (
                <SentimentHub data={marketData} />
              )}
            </CollapsiblePanel>

            {/* Market Sentiment */}
            <CollapsiblePanel
              title="SENTIMENT"
              icon={<Brain className="w-4 h-4" />}
              defaultExpanded={true}
            >
              <SentimentDisplay
                overall={Math.round(stats.avgBuySellRatio * 25)}
                social={Math.min(100, stats.bullishCount * 10)}
                market={marketRegime.solChange24h > 0 ? Math.min(100, 50 + marketRegime.solChange24h * 5) : Math.max(0, 50 + marketRegime.solChange24h * 5)}
                technical={Math.round(stats.avgBuySellRatio * 20)}
              />
            </CollapsiblePanel>

            {/* Quick Buy */}
            <CollapsiblePanel
              title="QUICK BUY"
              icon={<Zap className="w-4 h-4" />}
              defaultExpanded={false}
            >
              <QuickBuyTable />
            </CollapsiblePanel>

            {/* Sentiment Actions */}
            <CollapsiblePanel
              title="ACTIONS"
              icon={<Crosshair className="w-4 h-4" />}
              defaultExpanded={false}
            >
              <SentimentHubActions />
            </CollapsiblePanel>
          </div>

          {/* CENTER COLUMN: Chart + AI Intelligence */}
          <div className="flex flex-col gap-3">
            {/* Main Chart */}
            <div className="card-glass p-0 overflow-hidden min-h-[420px] relative">
              <div className="absolute top-3 left-3 z-10 flex gap-3 items-center">
                <div className="flex flex-col">
                  <span className="font-display font-bold text-xl text-text-primary">SOL/USDC</span>
                  <span className="font-mono text-[10px] text-text-muted">JUPITER AGGREGATOR</span>
                </div>
                <div className="h-8 w-[1px] bg-border-primary" />
                <div className="flex flex-col">
                  <span className="font-mono font-bold text-accent-neon text-sm">
                    {marketRegime.solPrice > 0 ? `$${marketRegime.solPrice.toFixed(2)}` : '...'}
                  </span>
                  <span className={`font-mono text-[10px] ${marketRegime.solChange24h >= 0 ? 'text-accent-success' : 'text-accent-error'}`}>
                    {marketRegime.solChange24h >= 0 ? '+' : ''}{marketRegime.solChange24h.toFixed(1)}%
                  </span>
                </div>
                <ConfidenceBadge symbol="SOL" />
              </div>
              <MarketChart />
            </div>

            {/* AI Intelligence Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <CollapsiblePanel
                title="AI MARKET REPORT"
                icon={<Newspaper className="w-4 h-4" />}
                badge="GROK"
                defaultExpanded={true}
              >
                <AIMarketReport />
              </CollapsiblePanel>

              <CollapsiblePanel
                title="CONVICTION PICKS"
                icon={<Target className="w-4 h-4" />}
                badge={`${grokScores.size}`}
                defaultExpanded={true}
              >
                <AIConvictionPicks />
              </CollapsiblePanel>
            </div>

            {/* Bags.fm + AI Picks Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <CollapsiblePanel
                title="BAGS.FM TOP LAUNCHES"
                icon={<Rocket className="w-4 h-4" />}
                badge="LIVE"
                defaultExpanded={false}
              >
                <BagsTop15 />
              </CollapsiblePanel>

              <CollapsiblePanel
                title="AI PICKS"
                icon={<LineChart className="w-4 h-4" />}
                defaultExpanded={false}
              >
                <AIPicks />
              </CollapsiblePanel>
            </div>
          </div>

          {/* RIGHT COLUMN: Trade Execution + Performance */}
          <div className="flex flex-col gap-3 max-h-[calc(100vh-220px)] overflow-y-auto custom-scrollbar pl-1">
            <TradePanel />
            <PerformanceTracker />
            <CollapsiblePanel
              title="AI MODEL"
              icon={<Brain className="w-4 h-4" />}
              defaultExpanded={false}
            >
              <ModelSwitcher />
            </CollapsiblePanel>
          </div>
        </section>
      </main>
    </div>
  );
}
