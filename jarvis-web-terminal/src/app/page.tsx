'use client';

import { SentimentHub } from '@/components/features/SentimentHub';
import { useMarketData } from '@/hooks/useMarketData';
import { useSentimentData } from '@/hooks/useSentimentData';
import { SolChart } from '@/components/features/SolChart';
import { TradePanel } from '@/components/features/TradePanel';
import { DashboardGrid } from '@/components/features/DashboardGrid';
import { NeuralLattice } from '@/components/visuals/NeuralLattice';
import { TradingGuard, ConfidenceBadge } from '@/components/features/TradingGuard';
import { SentimentDisplay } from '@/components/features/StatGlyph';
import { PerformanceTracker } from '@/components/features/PerformanceTracker';
import { AIMarketReport } from '@/components/features/AIMarketReport';
import { AIConvictionPicks } from '@/components/features/AIConvictionPicks';
import { BagsTop15 } from '@/components/features/BagsTop15';
import { ModelSwitcher } from '@/components/features/ModelSwitcher';
import { GrokLiveBar } from '@/components/features/GrokLiveBar';
import { useGrokLive } from '@/hooks/useGrokLive';
import {
  Brain,
  Activity,
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
      <div className="opacity-[0.02]"><NeuralLattice /></div>

      <main className="flex-1 flex flex-col pt-[68px] pb-2 gap-3 relative z-10 w-full px-3 lg:px-4">

        {/* Grok Live Engine Bar */}
        <GrokLiveBar
          countdown={countdown}
          isRefreshing={isRefreshing}
          lastRefreshed={lastRefreshed}
          budgetStatus={budgetStatus}
          tokenCount={grokScores.size}
          onRefresh={forceRefresh}
        />

        {/* Stats Row */}
        <section className="w-full">
          <DashboardGrid />
        </section>

        {/* Main 3-Column Layout */}
        <section className="grid grid-cols-1 xl:grid-cols-[280px_1fr_320px] gap-3 w-full flex-1">

          {/* LEFT COLUMN — Always visible, no collapsibles */}
          <div className="flex flex-col gap-3 max-h-[calc(100vh-200px)] overflow-y-auto custom-scrollbar pr-1">
            <TradingGuard symbol="SOL" />

            {/* Market Sentiment — INLINE */}
            <div className="card-glass p-3">
              <div className="flex items-center gap-2 mb-3">
                <Brain className="w-4 h-4 text-accent-neon" />
                <span className="text-xs font-mono uppercase tracking-wider text-text-muted">SENTIMENT</span>
              </div>
              <SentimentDisplay
                overall={Math.round(stats.avgBuySellRatio * 25)}
                social={Math.min(100, stats.bullishCount * 10)}
                market={marketRegime.solChange24h > 0 ? Math.min(100, 50 + marketRegime.solChange24h * 5) : Math.max(0, 50 + marketRegime.solChange24h * 5)}
                technical={Math.round(stats.avgBuySellRatio * 20)}
              />
            </div>

            {/* Live Signals — INLINE */}
            <div className="card-glass p-3">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-accent-neon" />
                  <span className="text-xs font-mono uppercase tracking-wider text-text-muted">LIVE SIGNALS</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent-neon animate-pulse" />
                  <span className="text-[10px] font-mono text-text-muted">SCANNING</span>
                </div>
              </div>
              {loading ? (
                <div className="text-center py-6 font-mono text-text-muted animate-pulse text-xs">
                  INITIALIZING BAGS.FM UPLINK...
                </div>
              ) : (
                <SentimentHub data={marketData} />
              )}
            </div>
          </div>

          {/* CENTER COLUMN — Chart + AI Intelligence */}
          <div className="flex flex-col gap-3">
            {/* Chart Card */}
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
              <SolChart />
            </div>

            {/* AI Intelligence — 2 column, always visible */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <AIMarketReport />
              <AIConvictionPicks />
            </div>

            {/* Bags Top */}
            <BagsTop15 />
          </div>

          {/* RIGHT COLUMN — Execution + Performance */}
          <div className="flex flex-col gap-3 max-h-[calc(100vh-200px)] overflow-y-auto custom-scrollbar pl-1">
            <TradePanel />
            <PerformanceTracker />
          </div>

        </section>

        {/* AI Model Footer Bar — Flat, compact */}
        <div className="card-glass px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="w-2 h-2 rounded-full bg-accent-neon shadow-[0_0_6px_rgba(34,197,94,0.6)]" />
            <Brain className="w-3.5 h-3.5 text-accent-neon" />
            <span className="text-xs font-mono font-bold text-text-primary">AI Model</span>
            <span className="text-xs text-text-muted">Grok 4</span>
            <span className="px-1.5 py-0.5 text-[9px] font-mono font-bold uppercase rounded bg-accent-neon/15 text-accent-neon border border-accent-neon/30">ACTIVE</span>
          </div>
          <ModelSwitcher />
        </div>

      </main>
    </div>
  );
}
