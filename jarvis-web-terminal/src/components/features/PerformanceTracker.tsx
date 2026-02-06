'use client';

import { useState, useMemo } from 'react';
import { useTradingData } from '@/context/TradingContext';
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
    Lightbulb
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

export function PerformanceTracker() {
    const { state } = useTradingData();
    const [expanded, setExpanded] = useState(true);
    const [timeFilter, setTimeFilter] = useState<'all' | '24h' | '7d' | '30d'>('all');

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

    return (
        <div className="card-glass p-4">
            {/* Header */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-center justify-between pb-3 border-b border-theme-border/30"
            >
                <div className="flex items-center gap-2">
                    <BarChart3 className="w-4 h-4 text-theme-cyan" />
                    <span className="font-display font-bold">PERFORMANCE</span>
                </div>
                {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {expanded && (
                <div className="pt-4 space-y-4">
                    {/* Time Filter */}
                    <div className="flex gap-2">
                        {(['all', '24h', '7d', '30d'] as const).map((filter) => (
                            <button
                                key={filter}
                                onClick={() => setTimeFilter(filter)}
                                className={`
                                    px-3 py-1 text-xs font-mono rounded transition-all
                                    ${timeFilter === filter
                                        ? 'bg-theme-cyan text-black'
                                        : 'bg-theme-dark/30 border border-theme-border/50 hover:border-theme-cyan'}
                                `}
                            >
                                {filter.toUpperCase()}
                            </button>
                        ))}
                    </div>

                    {/* Main Stats Grid */}
                    <div className="grid grid-cols-2 gap-3">
                        {/* Win Rate */}
                        <div className="bg-theme-dark/30 rounded-lg p-3">
                            <div className="flex items-center gap-1 text-xs text-theme-muted mb-1">
                                <Target className="w-3 h-3" />
                                WIN RATE
                            </div>
                            <div className={`text-xl font-bold ${
                                metrics.winRate >= 50 ? 'text-theme-green' : 'text-theme-red'
                            }`}>
                                {metrics.winRate.toFixed(1)}%
                            </div>
                            <div className="text-xs text-theme-muted">
                                {metrics.winCount}W / {metrics.lossCount}L
                            </div>
                        </div>

                        {/* Total P&L */}
                        <div className="bg-theme-dark/30 rounded-lg p-3">
                            <div className="flex items-center gap-1 text-xs text-theme-muted mb-1">
                                {metrics.totalPnL >= 0 ? (
                                    <TrendingUp className="w-3 h-3 text-theme-green" />
                                ) : (
                                    <TrendingDown className="w-3 h-3 text-theme-red" />
                                )}
                                TOTAL P&L
                            </div>
                            <div className={`text-xl font-bold ${
                                metrics.totalPnL >= 0 ? 'text-theme-green' : 'text-theme-red'
                            }`}>
                                {metrics.totalPnL >= 0 ? '+' : ''}{metrics.totalPnL.toFixed(4)} SOL
                            </div>
                            <div className="text-xs text-theme-muted">
                                {metrics.totalTrades} trades
                            </div>
                        </div>

                        {/* Profit Factor */}
                        <div className="bg-theme-dark/30 rounded-lg p-3">
                            <div className="flex items-center gap-1 text-xs text-theme-muted mb-1">
                                <Activity className="w-3 h-3" />
                                PROFIT FACTOR
                            </div>
                            <div className={`text-xl font-bold ${
                                metrics.profitFactor >= 1 ? 'text-theme-green' : 'text-theme-red'
                            }`}>
                                {metrics.profitFactor === Infinity ? '∞' : metrics.profitFactor.toFixed(2)}
                            </div>
                            <div className="text-xs text-theme-muted">
                                Avg Win: {metrics.avgWin.toFixed(4)}
                            </div>
                        </div>

                        {/* Best/Worst */}
                        <div className="bg-theme-dark/30 rounded-lg p-3">
                            <div className="flex items-center gap-1 text-xs text-theme-muted mb-1">
                                <AlertTriangle className="w-3 h-3" />
                                EXTREMES
                            </div>
                            {metrics.bestTrade ? (
                                <div className="text-sm">
                                    <span className="text-theme-green">
                                        Best: +{metrics.bestTrade.pnlPercent.toFixed(1)}%
                                    </span>
                                    <span className="text-theme-muted"> ({metrics.bestTrade.symbol})</span>
                                </div>
                            ) : (
                                <div className="text-sm text-theme-muted">No winning trades</div>
                            )}
                            {metrics.worstTrade ? (
                                <div className="text-sm">
                                    <span className="text-theme-red">
                                        Worst: {metrics.worstTrade.pnlPercent.toFixed(1)}%
                                    </span>
                                    <span className="text-theme-muted"> ({metrics.worstTrade.symbol})</span>
                                </div>
                            ) : (
                                <div className="text-sm text-theme-muted">No losing trades</div>
                            )}
                        </div>
                    </div>

                    {/* Sentiment Correlation */}
                    <div className="bg-theme-dark/30 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-3">
                            <Brain className="w-4 h-4 text-theme-cyan" />
                            <span className="text-xs font-mono text-theme-muted">SENTIMENT CORRELATION</span>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-xs text-theme-muted mb-1">High Sentiment (60+)</div>
                                <div className={`text-lg font-bold ${
                                    metrics.sentimentCorrelation.highSentimentWinRate >= 50
                                        ? 'text-theme-green' : 'text-theme-red'
                                }`}>
                                    {metrics.sentimentCorrelation.highSentimentWinRate.toFixed(1)}% win
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-theme-muted mb-1">Low Sentiment (&lt;60)</div>
                                <div className={`text-lg font-bold ${
                                    metrics.sentimentCorrelation.lowSentimentWinRate >= 50
                                        ? 'text-theme-green' : 'text-theme-red'
                                }`}>
                                    {metrics.sentimentCorrelation.lowSentimentWinRate.toFixed(1)}% win
                                </div>
                            </div>
                        </div>

                        <div className="mt-3 pt-3 border-t border-theme-border/30">
                            <div className="text-xs text-theme-muted">Optimal Sentiment Range</div>
                            <div className="text-sm font-bold text-theme-cyan">
                                {metrics.sentimentCorrelation.optimalSentimentRange.min} - {metrics.sentimentCorrelation.optimalSentimentRange.max}
                            </div>
                        </div>
                    </div>

                    {/* AI Recommendations */}
                    <div className="bg-gradient-to-r from-theme-cyan/10 to-accent-neon/10 rounded-lg p-3 border border-theme-cyan/30">
                        <div className="flex items-center gap-2 mb-2">
                            <Lightbulb className="w-4 h-4 text-accent-neon" />
                            <span className="text-xs font-mono text-accent-neon">AI RECOMMENDATIONS</span>
                        </div>
                        <ul className="space-y-1">
                            {recommendations.map((rec, i) => (
                                <li key={i} className="text-sm text-theme-muted flex items-start gap-2">
                                    <span className="text-accent-neon">•</span>
                                    {rec}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
        </div>
    );
}
