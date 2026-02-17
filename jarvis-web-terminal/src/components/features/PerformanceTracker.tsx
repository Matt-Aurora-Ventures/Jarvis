'use client';

import { useState, useMemo, useCallback } from 'react';
import { useTradingData } from '@/context/TradingContext';
import { useToast } from '@/components/ui/Toast';
import {
    TrendingUp,
    TrendingDown,
    Activity,
    Target,
    AlertTriangle,
    ChevronDown,
    ChevronUp,
    BarChart3,
    Brain,
    Lightbulb,
    Download,
    RotateCcw
} from 'lucide-react';

interface PerformanceMetrics {
    totalTrades: number;
    winCount: number;
    lossCount: number;
    winRate: number;
    totalPnL: number;
    avgWin: number;
    avgLoss: number;
    profitFactor: number;
    bestTrade: { symbol: string; pnlPercent: number } | null;
    worstTrade: { symbol: string; pnlPercent: number } | null;
    sentimentCorrelation: {
        highSentimentWinRate: number;
        lowSentimentWinRate: number;
        optimalSentimentRange: { min: number; max: number };
    };
}

interface TradeWithSentiment {
    id: string;
    symbol: string;
    type: 'buy' | 'sell';
    entryPrice: number;
    exitPrice: number;
    amount: number;
    pnl: number;
    pnlPercent: number;
    sentimentAtEntry?: number;
    timestamp: number;
    txHash?: string;
}

const TIME_FILTERS = ['all', '24h', '7d', '30d'] as const;
type TimeFilter = typeof TIME_FILTERS[number];

const TIME_FILTER_LABELS: Record<TimeFilter, string> = {
    all: 'All',
    '24h': '24H',
    '7d': '7D',
    '30d': '30D',
};

export function PerformanceTracker() {
    const { state } = useTradingData();
    const { success, info } = useToast();
    const [expanded, setExpanded] = useState(true);
    const [timeFilter, setTimeFilter] = useState<TimeFilter>('all');

    // Calculate performance metrics
    const metrics = useMemo<PerformanceMetrics>(() => {
        const history = state.history || [];

        // Filter by time
        const now = Date.now();
        const filtered = history.filter(trade => {
            if (timeFilter === 'all') return true;
            const cutoff = {
                '24h': 24 * 60 * 60 * 1000,
                '7d': 7 * 24 * 60 * 60 * 1000,
                '30d': 30 * 24 * 60 * 60 * 1000,
            }[timeFilter];
            return (now - trade.timestamp) < cutoff;
        });

        if (filtered.length === 0) {
            return {
                totalTrades: 0,
                winCount: 0,
                lossCount: 0,
                winRate: 0,
                totalPnL: 0,
                avgWin: 0,
                avgLoss: 0,
                profitFactor: 0,
                bestTrade: null,
                worstTrade: null,
                sentimentCorrelation: {
                    highSentimentWinRate: 0,
                    lowSentimentWinRate: 0,
                    optimalSentimentRange: { min: 50, max: 80 },
                },
            };
        }

        const wins = filtered.filter(t => (t.pnl || 0) > 0);
        const losses = filtered.filter(t => (t.pnl || 0) < 0);

        const totalPnL = filtered.reduce((sum, t) => sum + (t.pnl || 0), 0);
        const totalWins = wins.reduce((sum, t) => sum + (t.pnl || 0), 0);
        const totalLosses = Math.abs(losses.reduce((sum, t) => sum + (t.pnl || 0), 0));

        // Sentiment correlation analysis
        const tradesWithSentiment = filtered.filter(t => (t as any).sentimentAtEntry !== undefined);
        const highSentimentTrades = tradesWithSentiment.filter(t => ((t as any).sentimentAtEntry || 0) >= 60);
        const lowSentimentTrades = tradesWithSentiment.filter(t => ((t as any).sentimentAtEntry || 0) < 60);

        const highSentimentWins = highSentimentTrades.filter(t => (t.pnl || 0) > 0);
        const lowSentimentWins = lowSentimentTrades.filter(t => (t.pnl || 0) > 0);

        // Find best performing sentiment ranges
        const sentimentBuckets: { [key: number]: { wins: number; total: number } } = {};
        for (const trade of tradesWithSentiment) {
            const sentiment = (trade as any).sentimentAtEntry || 50;
            const bucket = Math.floor(sentiment / 10) * 10;
            if (!sentimentBuckets[bucket]) sentimentBuckets[bucket] = { wins: 0, total: 0 };
            sentimentBuckets[bucket].total++;
            if ((trade.pnl || 0) > 0) sentimentBuckets[bucket].wins++;
        }

        let optimalMin = 50, optimalMax = 80;
        let bestWinRate = 0;
        for (const [bucket, data] of Object.entries(sentimentBuckets)) {
            const winRate = data.total > 0 ? data.wins / data.total : 0;
            if (winRate > bestWinRate && data.total >= 3) {
                bestWinRate = winRate;
                optimalMin = parseInt(bucket);
                optimalMax = optimalMin + 20;
            }
        }

        // Find best/worst trades
        const sortedByPnL = [...filtered].sort((a, b) => (b.pnl || 0) - (a.pnl || 0));
        const bestTrade = sortedByPnL[0] && (sortedByPnL[0].pnl || 0) > 0
            ? { symbol: sortedByPnL[0].symbol, pnlPercent: ((sortedByPnL[0].pnl || 0) / sortedByPnL[0].amount) * 100 }
            : null;
        const worstTrade = sortedByPnL[sortedByPnL.length - 1] && (sortedByPnL[sortedByPnL.length - 1].pnl || 0) < 0
            ? { symbol: sortedByPnL[sortedByPnL.length - 1].symbol, pnlPercent: ((sortedByPnL[sortedByPnL.length - 1].pnl || 0) / sortedByPnL[sortedByPnL.length - 1].amount) * 100 }
            : null;

        return {
            totalTrades: filtered.length,
            winCount: wins.length,
            lossCount: losses.length,
            winRate: filtered.length > 0 ? (wins.length / filtered.length) * 100 : 0,
            totalPnL,
            avgWin: wins.length > 0 ? totalWins / wins.length : 0,
            avgLoss: losses.length > 0 ? totalLosses / losses.length : 0,
            profitFactor: totalLosses > 0 ? totalWins / totalLosses : totalWins > 0 ? Infinity : 0,
            bestTrade,
            worstTrade,
            sentimentCorrelation: {
                highSentimentWinRate: highSentimentTrades.length > 0
                    ? (highSentimentWins.length / highSentimentTrades.length) * 100
                    : 0,
                lowSentimentWinRate: lowSentimentTrades.length > 0
                    ? (lowSentimentWins.length / lowSentimentTrades.length) * 100
                    : 0,
                optimalSentimentRange: { min: optimalMin, max: optimalMax },
            },
        };
    }, [state.history, timeFilter]);

    // Generate AI recommendations based on performance
    const recommendations = useMemo<string[]>(() => {
        const recs: string[] = [];

        if (metrics.totalTrades < 5) {
            return ['Execute more trades to generate meaningful insights'];
        }

        // Win rate recommendations
        if (metrics.winRate < 40) {
            recs.push('Consider increasing sentiment threshold before entering trades');
        } else if (metrics.winRate > 60) {
            recs.push('Strong win rate! Consider slightly increasing position sizes');
        }

        // Sentiment correlation recommendations
        const sentDiff = metrics.sentimentCorrelation.highSentimentWinRate - metrics.sentimentCorrelation.lowSentimentWinRate;
        if (sentDiff > 20) {
            recs.push(`Your high sentiment trades (60+) outperform by ${sentDiff.toFixed(0)}%. Focus on these signals`);
        }

        // Profit factor recommendations
        if (metrics.profitFactor < 1) {
            recs.push('Tighten stop losses - average losses exceed average wins');
        } else if (metrics.profitFactor > 2) {
            recs.push('Excellent risk/reward! Your strategy is working well');
        }

        // Optimal range recommendation
        const { min, max } = metrics.sentimentCorrelation.optimalSentimentRange;
        if (metrics.totalTrades >= 10) {
            recs.push(`Best results when sentiment is ${min}-${max}. Consider adjusting algo thresholds`);
        }

        return recs.length > 0 ? recs : ['Keep trading to build more performance data'];
    }, [metrics]);

    // Export handler -- defined after metrics so it can reference them
    const handleExport = useCallback(() => {
        const csv = [
            'Metric,Value',
            `Win Rate,${metrics.winRate.toFixed(1)}%`,
            `Total P&L,${metrics.totalPnL.toFixed(4)}`,
            `Profit Factor,${metrics.profitFactor === Infinity ? 'Infinity' : metrics.profitFactor.toFixed(2)}`,
            `Total Trades,${metrics.totalTrades}`,
            `Wins,${metrics.winCount}`,
            `Losses,${metrics.lossCount}`,
            `Avg Win,${metrics.avgWin.toFixed(4)}`,
            `Avg Loss,${metrics.avgLoss.toFixed(4)}`,
            `Best Trade,${metrics.bestTrade ? `${metrics.bestTrade.symbol} (${metrics.bestTrade.pnlPercent.toFixed(1)}%)` : 'N/A'}`,
            `Worst Trade,${metrics.worstTrade ? `${metrics.worstTrade.symbol} (${metrics.worstTrade.pnlPercent.toFixed(1)}%)` : 'N/A'}`,
            `Time Filter,${timeFilter}`,
        ].join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `jarvis-performance-${timeFilter}-${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        success('Performance data exported');
    }, [metrics, timeFilter, success]);

    const handleReset = useCallback(() => {
        setTimeFilter('all');
        info('Filters reset');
    }, [info]);

    return (
        <div className="card-glass p-3">
            {/* Header with expand/collapse toggle */}
            <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-accent-neon" />
                    <span className="text-xs font-mono uppercase tracking-wider text-text-muted">PERFORMANCE</span>
                </div>
                <div className="flex items-center gap-1">
                    {/* Export Button */}
                    <button
                        onClick={handleExport}
                        className="p-1.5 rounded-lg hover:bg-bg-tertiary transition-all"
                        title="Export performance data as CSV"
                    >
                        <Download className="w-3.5 h-3.5 text-text-muted hover:text-accent-neon transition-colors" />
                    </button>
                    {/* Reset Button */}
                    <button
                        onClick={handleReset}
                        className="p-1.5 rounded-lg hover:bg-bg-tertiary transition-all"
                        title="Reset filters"
                    >
                        <RotateCcw className="w-3.5 h-3.5 text-text-muted hover:text-accent-neon transition-colors" />
                    </button>
                    {/* Expand/Collapse */}
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1.5 rounded-lg hover:bg-bg-tertiary transition-all"
                        title={expanded ? 'Collapse' : 'Expand'}
                    >
                        {expanded ? (
                            <ChevronUp className="w-3.5 h-3.5 text-text-muted" />
                        ) : (
                            <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
                        )}
                    </button>
                </div>
            </div>

            {/* Time Filter Tabs */}
            <div className="flex items-center gap-1 mb-3">
                {TIME_FILTERS.map((filter) => (
                    <button
                        key={filter}
                        onClick={() => setTimeFilter(filter)}
                        className={`px-2.5 py-1 rounded-md text-[10px] font-mono font-bold uppercase transition-all ${
                            timeFilter === filter
                                ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30'
                                : 'bg-bg-tertiary/50 text-text-muted hover:text-text-primary hover:bg-bg-tertiary border border-transparent'
                        }`}
                    >
                        {TIME_FILTER_LABELS[filter]}
                    </button>
                ))}
            </div>

            {expanded && (
                <>
                    {/* Compact 2x2 Grid */}
                    <div className="grid grid-cols-2 gap-2">
                        {/* Win Rate */}
                        <div className="bg-bg-tertiary/50 rounded-lg p-2">
                            <div className="text-[10px] text-text-muted font-mono uppercase">Win Rate</div>
                            <div className={`text-sm font-mono font-bold ${
                                metrics.winRate >= 50 ? 'text-accent-success' : 'text-accent-error'
                            }`}>
                                {metrics.winRate.toFixed(1)}%
                            </div>
                        </div>

                        {/* Total P&L */}
                        <div className="bg-bg-tertiary/50 rounded-lg p-2">
                            <div className="text-[10px] text-text-muted font-mono uppercase">Total P&L</div>
                            <div className={`text-sm font-mono font-bold ${
                                metrics.totalPnL >= 0 ? 'text-accent-success' : 'text-accent-error'
                            }`}>
                                {metrics.totalPnL >= 0 ? '+' : ''}{metrics.totalPnL.toFixed(4)}
                            </div>
                        </div>

                        {/* Profit Factor */}
                        <div className="bg-bg-tertiary/50 rounded-lg p-2">
                            <div className="text-[10px] text-text-muted font-mono uppercase">Profit Factor</div>
                            <div className={`text-sm font-mono font-bold ${
                                metrics.profitFactor >= 1 ? 'text-accent-success' : 'text-accent-error'
                            }`}>
                                {metrics.profitFactor === Infinity ? '∞' : metrics.profitFactor.toFixed(2)}
                            </div>
                        </div>

                        {/* Trades */}
                        <div className="bg-bg-tertiary/50 rounded-lg p-2">
                            <div className="text-[10px] text-text-muted font-mono uppercase">Trades</div>
                            <div className="text-sm font-mono font-bold text-text-primary">
                                {metrics.totalTrades}
                            </div>
                        </div>
                    </div>

                    {/* Recommendations (shown if there are trades) */}
                    {recommendations.length > 0 && metrics.totalTrades > 0 && (
                        <div className="mt-3 p-2 rounded-lg bg-accent-neon/5 border border-accent-neon/10">
                            <div className="flex items-center gap-1.5 mb-1.5">
                                <Lightbulb className="w-3 h-3 text-accent-neon" />
                                <span className="text-[10px] font-mono text-accent-neon uppercase">AI Insight</span>
                            </div>
                            {recommendations.map((rec, i) => (
                                <p key={i} className="text-[11px] text-text-secondary leading-relaxed">
                                    {rec}
                                </p>
                            ))}
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
