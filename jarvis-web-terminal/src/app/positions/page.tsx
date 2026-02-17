'use client';

import { useState, useEffect } from 'react';
import { PositionManager } from '@/components/features/PositionManager';
import { getHeliusClient } from '@/lib/helius-client';
import {
    Wallet,
    TrendingUp,
    TrendingDown,
    DollarSign,
    Activity,
    PieChart,
    BarChart3,
    RefreshCw,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    Target,
    Percent
} from 'lucide-react';

interface PortfolioStats {
    totalValue: number;
    totalPnL: number;
    totalPnLPercent: number;
    winRate: number;
    totalTrades: number;
    winners: number;
    losers: number;
    avgWin: number;
    avgLoss: number;
    bestTrade: number;
    worstTrade: number;
    openPositions: number;
}

export default function PositionsPage() {
    const [stats, setStats] = useState<PortfolioStats>({
        totalValue: 0,
        totalPnL: 0,
        totalPnLPercent: 0,
        winRate: 0,
        totalTrades: 0,
        winners: 0,
        losers: 0,
        avgWin: 0,
        avgLoss: 0,
        bestTrade: 0,
        worstTrade: 0,
        openPositions: 0,
    });
    const [loading, setLoading] = useState(true);

    // Load stats from localStorage
    useEffect(() => {
        const loadStats = () => {
            try {
                // Load positions
                const positions = JSON.parse(localStorage.getItem('jarvis_positions') || '[]');

                // Load trade history
                const history = JSON.parse(localStorage.getItem('jarvis_trade_history') || '[]');

                // Calculate current portfolio value and P&L
                let totalValue = 0;
                let totalCost = 0;

                positions.forEach((pos: any) => {
                    const currentValue = pos.amount * pos.currentPrice;
                    const costBasis = pos.amount * pos.entryPrice;
                    totalValue += currentValue;
                    totalCost += costBasis;
                });

                const totalPnL = totalValue - totalCost;
                const totalPnLPercent = totalCost > 0 ? (totalPnL / totalCost) * 100 : 0;

                // Calculate historical stats
                const closedTrades = history.filter((t: any) => t.type === 'sell');
                const winners = closedTrades.filter((t: any) => t.pnl > 0);
                const losers = closedTrades.filter((t: any) => t.pnl < 0);

                const avgWin = winners.length > 0
                    ? winners.reduce((sum: number, t: any) => sum + t.pnl, 0) / winners.length
                    : 0;
                const avgLoss = losers.length > 0
                    ? losers.reduce((sum: number, t: any) => sum + t.pnl, 0) / losers.length
                    : 0;

                const allPnLs = closedTrades.map((t: any) => t.pnl || 0);
                const bestTrade = allPnLs.length > 0 ? Math.max(...allPnLs) : 0;
                const worstTrade = allPnLs.length > 0 ? Math.min(...allPnLs) : 0;

                setStats({
                    totalValue,
                    totalPnL,
                    totalPnLPercent,
                    winRate: closedTrades.length > 0 ? (winners.length / closedTrades.length) * 100 : 0,
                    totalTrades: closedTrades.length,
                    winners: winners.length,
                    losers: losers.length,
                    avgWin,
                    avgLoss,
                    bestTrade,
                    worstTrade,
                    openPositions: positions.length,
                });
            } catch (error) {
                console.error('Failed to load stats:', error);
            } finally {
                setLoading(false);
            }
        };

        loadStats();

        // Refresh every 30 seconds
        const interval = setInterval(loadStats, 30000);
        return () => clearInterval(interval);
    }, []);

    return (
        <>
            {/* Ambient Background */}
            <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
                <div className="ambient-orb absolute top-1/4 left-1/4 w-96 h-96 bg-accent-neon/[0.04] rounded-full blur-[128px]" />
                <div className="ambient-orb-2 absolute bottom-1/3 right-1/4 w-80 h-80 bg-accent-neon/[0.03] rounded-full blur-[128px]" />
                <div className="ambient-orb-3 absolute top-2/3 left-1/2 w-64 h-64 bg-accent-success/[0.02] rounded-full blur-[128px]" />
            </div>

            <div className="pt-[100px] pb-4 px-3 lg:px-6 max-w-[1920px] mx-auto w-full">
                {/* Header */}
                <section className="flex items-center justify-between mb-6">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <Wallet className="w-5 h-5 text-accent-neon" />
                            <span className="text-sm text-accent-neon font-mono">PORTFOLIO</span>
                        </div>
                        <h1 className="font-display text-3xl font-bold text-text-primary">
                            Position Management
                        </h1>
                    </div>

                    <button
                        onClick={() => window.location.reload()}
                        className="p-2 rounded-lg bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary transition-colors"
                    >
                        <RefreshCw className="w-5 h-5" />
                    </button>
                </section>

                {/* Portfolio Stats Grid */}
                <section className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
                    {/* Total Value */}
                    <div className="card-glass p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <DollarSign className="w-4 h-4 text-accent-neon" />
                            <span className="text-xs text-text-muted">Portfolio Value</span>
                        </div>
                        <p className="font-mono font-bold text-xl text-text-primary">
                            ${stats.totalValue.toFixed(2)}
                        </p>
                    </div>

                    {/* Total P&L */}
                    <div className="card-glass p-4">
                        <div className="flex items-center gap-2 mb-2">
                            {stats.totalPnL >= 0 ? (
                                <TrendingUp className="w-4 h-4 text-accent-success" />
                            ) : (
                                <TrendingDown className="w-4 h-4 text-accent-danger" />
                            )}
                            <span className="text-xs text-text-muted">Total P&L</span>
                        </div>
                        <p className={`font-mono font-bold text-xl ${
                            stats.totalPnL >= 0 ? 'text-accent-success' : 'text-accent-danger'
                        }`}>
                            {stats.totalPnL >= 0 ? '+' : ''}${stats.totalPnL.toFixed(2)}
                        </p>
                        <p className={`text-xs font-mono ${
                            stats.totalPnLPercent >= 0 ? 'text-accent-success' : 'text-accent-danger'
                        }`}>
                            {stats.totalPnLPercent >= 0 ? '+' : ''}{stats.totalPnLPercent.toFixed(2)}%
                        </p>
                    </div>

                    {/* Win Rate */}
                    <div className="card-glass p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <Target className="w-4 h-4 text-accent-neon" />
                            <span className="text-xs text-text-muted">Win Rate</span>
                        </div>
                        <p className={`font-mono font-bold text-xl ${
                            stats.winRate >= 50 ? 'text-accent-success' : 'text-accent-danger'
                        }`}>
                            {stats.winRate.toFixed(1)}%
                        </p>
                        <p className="text-xs text-text-muted">
                            {stats.winners}W / {stats.losers}L
                        </p>
                    </div>

                    {/* Total Trades */}
                    <div className="card-glass p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <Activity className="w-4 h-4 text-accent-neon" />
                            <span className="text-xs text-text-muted">Total Trades</span>
                        </div>
                        <p className="font-mono font-bold text-xl text-text-primary">
                            {stats.totalTrades}
                        </p>
                        <p className="text-xs text-text-muted">
                            {stats.openPositions} open
                        </p>
                    </div>

                    {/* Avg Win */}
                    <div className="card-glass p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <CheckCircle2 className="w-4 h-4 text-accent-success" />
                            <span className="text-xs text-text-muted">Avg Win</span>
                        </div>
                        <p className="font-mono font-bold text-xl text-accent-success">
                            +${stats.avgWin.toFixed(2)}
                        </p>
                    </div>

                    {/* Avg Loss */}
                    <div className="card-glass p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <XCircle className="w-4 h-4 text-accent-danger" />
                            <span className="text-xs text-text-muted">Avg Loss</span>
                        </div>
                        <p className="font-mono font-bold text-xl text-accent-danger">
                            ${stats.avgLoss.toFixed(2)}
                        </p>
                    </div>
                </section>

                {/* Best/Worst Trade Banner */}
                {stats.totalTrades > 0 && (
                    <section className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                        <div className="card-glass p-4 border border-accent-success/30 bg-accent-success/5">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-lg bg-accent-success/20 flex items-center justify-center">
                                        <TrendingUp className="w-5 h-5 text-accent-success" />
                                    </div>
                                    <div>
                                        <p className="text-xs text-text-muted">Best Trade</p>
                                        <p className="font-mono font-bold text-lg text-accent-success">
                                            +${stats.bestTrade.toFixed(2)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="card-glass p-4 border border-accent-danger/30 bg-accent-danger/5">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-lg bg-accent-danger/20 flex items-center justify-center">
                                        <TrendingDown className="w-5 h-5 text-accent-danger" />
                                    </div>
                                    <div>
                                        <p className="text-xs text-text-muted">Worst Trade</p>
                                        <p className="font-mono font-bold text-lg text-accent-danger">
                                            ${stats.worstTrade.toFixed(2)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </section>
                )}

                {/* Empty State for New Users */}
                {stats.totalTrades === 0 && stats.openPositions === 0 && !loading && (
                    <section className="card-glass p-8 text-center mb-6">
                        <AlertTriangle className="w-12 h-12 text-text-muted mx-auto mb-4" />
                        <h3 className="font-display font-bold text-xl text-text-primary mb-2">
                            No Trading History Yet
                        </h3>
                        <p className="text-text-muted mb-4">
                            Start trading to track your performance here. Your win rate, P&L, and portfolio stats will appear automatically.
                        </p>
                        <a
                            href="/trade"
                            className="inline-flex items-center gap-2 px-4 py-2 bg-accent-neon text-black font-bold rounded-lg hover:bg-accent-neon/80 transition-colors"
                        >
                            <TrendingUp className="w-4 h-4" />
                            Start Trading
                        </a>
                    </section>
                )}

                {/* Position Manager */}
                <section>
                    <PositionManager />
                </section>

                {/* Performance Tips */}
                <section className="mt-6 card-glass p-4">
                    <h3 className="font-display font-bold text-lg text-text-primary mb-3 flex items-center gap-2">
                        <BarChart3 className="w-5 h-5 text-accent-neon" />
                        Performance Insights
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {stats.winRate < 50 && stats.totalTrades >= 5 && (
                            <div className="p-3 rounded-lg bg-accent-warning/10 border border-accent-warning/30">
                                <p className="text-sm text-text-muted font-mono mb-1">Win Rate Below 50%</p>
                                <p className="text-xs text-text-muted">
                                    Consider tightening your entry criteria or adjusting position sizes.
                                </p>
                            </div>
                        )}

                        {Math.abs(stats.avgLoss) > stats.avgWin && stats.totalTrades >= 5 && (
                            <div className="p-3 rounded-lg bg-accent-danger/10 border border-accent-danger/30">
                                <p className="text-sm text-accent-danger font-mono mb-1">Losses Exceed Wins</p>
                                <p className="text-xs text-text-muted">
                                    Your average loss is larger than your average win. Use tighter stop losses.
                                </p>
                            </div>
                        )}

                        {stats.winRate >= 60 && stats.totalTrades >= 5 && (
                            <div className="p-3 rounded-lg bg-accent-success/10 border border-accent-success/30">
                                <p className="text-sm text-accent-success font-mono mb-1">Strong Win Rate</p>
                                <p className="text-xs text-text-muted">
                                    You're performing well! Consider slightly increasing position sizes.
                                </p>
                            </div>
                        )}

                        {stats.totalTrades < 5 && (
                            <div className="p-3 rounded-lg bg-bg-secondary/50 border border-border-primary/30">
                                <p className="text-sm text-text-primary font-mono mb-1">Building History</p>
                                <p className="text-xs text-text-muted">
                                    Complete at least 5 trades to see performance insights.
                                </p>
                            </div>
                        )}
                    </div>
                </section>
            </div>
        </>
    );
}
