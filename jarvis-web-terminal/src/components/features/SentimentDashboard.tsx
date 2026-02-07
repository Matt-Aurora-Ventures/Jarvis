'use client';

/**
 * Sentiment Dashboard
 * 
 * Main dashboard orchestrator that assembles all panels
 * into a premium responsive grid layout.
 */

import { useSentimentData } from '@/hooks/useSentimentData';
import { TrendingTokensPanel } from '@/components/features/TrendingTokensPanel';
import { MarketRegimeIndicator } from '@/components/features/MarketRegimeIndicator';
import { ConvictionPicksGrid } from '@/components/features/ConvictionPicksGrid';
import { MacroEventsTimeline } from '@/components/features/MacroEventsTimeline';
import { xStocksPanel as XStocksPanel } from '@/components/features/xStocksPanel';
import { CommoditiesPanel } from '@/components/features/CommoditiesPanel';
import { PerpetualsSection } from '@/components/features/PerpetualsSection';
import { RefreshCw, Clock, Zap, Brain } from 'lucide-react';

export function SentimentDashboard() {
    const data = useSentimentData({ autoRefresh: true, refreshInterval: 30 * 60 * 1000 });

    const formatLastUpdated = () => {
        if (data.timeSinceUpdate < 1) return 'Just now';
        if (data.timeSinceUpdate === 1) return '1 min ago';
        if (data.timeSinceUpdate < 60) return `${data.timeSinceUpdate} mins ago`;
        return `${Math.floor(data.timeSinceUpdate / 60)}h ago`;
    };

    return (
        <div className="sentiment-dashboard">
            {/* Dashboard Header */}
            <div className="sentiment-dashboard-header">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-xl bg-gradient-to-br from-accent-primary/20 to-purple-500/20 border border-accent-primary/30">
                        <Brain className="w-6 h-6 text-accent-primary" />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-text-primary">
                            Jarvis Intelligence
                        </h1>
                        <p className="text-sm text-text-muted">AI-Powered Market Sentiment</p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {/* Stats Summary */}
                    <div className="hidden md:flex items-center gap-4 px-4 py-2 rounded-xl bg-bg-secondary/50 border border-white/5">
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-emerald-400" />
                            <span className="text-sm text-text-secondary">{data.stats.bullishCount} Bullish</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-accent-warning" />
                            <span className="text-sm text-text-secondary">{data.stats.neutralCount} Neutral</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-accent-error" />
                            <span className="text-sm text-text-secondary">{data.stats.bearishCount} Bearish</span>
                        </div>
                    </div>

                    {/* Last Updated */}
                    <div className="flex items-center gap-2 text-text-muted">
                        <Clock className="w-4 h-4" />
                        <span className="text-sm">{formatLastUpdated()}</span>
                    </div>

                    {/* Refresh Button */}
                    <button
                        onClick={data.refresh}
                        disabled={data.isLoading}
                        className="p-2 rounded-lg bg-bg-secondary hover:bg-bg-tertiary border border-white/10 
                       transition-all disabled:opacity-50"
                    >
                        <RefreshCw className={`w-5 h-5 text-text-secondary ${data.isLoading ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Error Message */}
            {data.error && (
                <div className="mb-4 p-4 rounded-xl bg-accent-error/10 border border-accent-error/30 text-accent-error">
                    {data.error}
                </div>
            )}

            {/* Main Grid */}
            <div className="sentiment-dashboard-grid">
                {/* Left Column - Wide */}
                <div className="sentiment-col-wide space-y-4">
                    {/* Market Regime (top banner) */}
                    <MarketRegimeIndicator
                        regime={data.marketRegime}
                        isLoading={data.isLoading}
                    />

                    {/* Trending Tokens */}
                    <TrendingTokensPanel
                        tokens={data.trendingTokens}
                        isLoading={data.isLoading}
                    />

                    {/* Conviction Picks */}
                    <ConvictionPicksGrid
                        picks={data.convictionPicks}
                        isLoading={data.isLoading}
                    />
                </div>

                {/* Right Column - Narrow */}
                <div className="sentiment-col-narrow space-y-4">
                    {/* Macro Outlook */}
                    <MacroEventsTimeline
                        macro={data.macroAnalysis}
                        isLoading={data.isLoading}
                    />

                    {/* xStocks */}
                    <XStocksPanel
                        stocks={data.stockPicks}
                        isLoading={data.isLoading}
                    />

                    {/* Commodities */}
                    <CommoditiesPanel
                        commodities={data.commodityMovers}
                        preciousMetals={data.preciousMetals}
                        isLoading={data.isLoading}
                    />

                    {/* Perpetuals (Coming Soon) */}
                    <PerpetualsSection />
                </div>
            </div>
        </div>
    );
}
