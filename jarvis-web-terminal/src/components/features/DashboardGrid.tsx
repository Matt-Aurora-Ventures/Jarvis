'use client';

import { useTreasuryMetrics } from '@/hooks/useTreasuryMetrics';
import { AreaChart, Trophy, AlertTriangle, TrendingUp } from 'lucide-react';

export function DashboardGrid() {
    const { moodEmoji, winRate, sharpe, pnl, openPositionsCount } = useTreasuryMetrics();

    return (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
            <div className="card-glass p-3 border-l-4 border-l-accent-neon">
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <TrendingUp className="w-3 h-3" /> PNL (TOTAL)
                </div>
                <div className="text-xl font-display font-bold">{pnl}</div>
            </div>

            <div className="card-glass p-3 border-l-4 border-l-accent-success">
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <Trophy className="w-3 h-3" /> WIN RATE
                </div>
                <div className="text-xl font-display font-bold">{winRate}</div>
            </div>

            <div className="card-glass p-3 border-l-4 border-l-accent-neon/60">
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <AreaChart className="w-3 h-3" /> SHARPE RATIO
                </div>
                <div className="text-xl font-display font-bold">{sharpe}</div>
            </div>

            <div className="card-glass p-3 border-l-4 border-l-accent-warning">
                <div className="text-xs text-text-muted font-mono mb-1 flex items-center gap-2">
                    <AlertTriangle className="w-3 h-3" /> ACTIVE POSITIONS
                </div>
                <div className="text-xl font-display font-bold flex justify-between items-center">
                    {openPositionsCount}
                    <span className="text-2xl filter drop-shadow-lg grayscale opacity-50">{moodEmoji}</span>
                </div>
            </div>
        </div>
    );
}
