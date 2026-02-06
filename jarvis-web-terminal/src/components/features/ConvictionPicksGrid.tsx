'use client';

/**
 * Conviction Picks Grid
 * 
 * Displays the unified Top 10 picks across tokens, stocks, and indexes
 * with risk-tiered TP/SL targets.
 */

import { ConvictionPick, GRADE_COLORS, ASSET_TYPE_LABELS } from '@/types/sentiment-types';
import { Target, Shield, Flame, TrendingUp, Award, Zap } from 'lucide-react';
import { useState } from 'react';

interface ConvictionPicksGridProps {
    picks: ConvictionPick[];
    isLoading?: boolean;
}

type RiskTab = 'safe' | 'medium' | 'degen';

export function ConvictionPicksGrid({ picks, isLoading }: ConvictionPicksGridProps) {
    const [activeRisk, setActiveRisk] = useState<RiskTab>('medium');

    if (isLoading) {
        return (
            <div className="sentiment-panel">
                <div className="sentiment-panel-header">
                    <Award className="w-5 h-5 text-accent-primary" />
                    <h3>Top Conviction Picks</h3>
                </div>
                <div className="flex items-center justify-center h-48">
                    <div className="animate-pulse text-text-muted">Loading picks...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="sentiment-panel">
            <div className="sentiment-panel-header">
                <Award className="w-5 h-5 text-amber-400" />
                <h3>🎯 Top 10 Conviction Picks</h3>
            </div>

            {/* Risk Profile Tabs */}
            <div className="flex gap-2 mb-4">
                <RiskTab
                    active={activeRisk === 'safe'}
                    onClick={() => setActiveRisk('safe')}
                    icon={Shield}
                    label="Safe"
                    color="text-emerald-400"
                />
                <RiskTab
                    active={activeRisk === 'medium'}
                    onClick={() => setActiveRisk('medium')}
                    icon={Target}
                    label="Medium"
                    color="text-yellow-400"
                />
                <RiskTab
                    active={activeRisk === 'degen'}
                    onClick={() => setActiveRisk('degen')}
                    icon={Flame}
                    label="Degen"
                    color="text-orange-400"
                />
            </div>

            {/* Picks Grid */}
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
                {picks.map((pick) => (
                    <PickCard key={`${pick.symbol}-${pick.rank}`} pick={pick} riskLevel={activeRisk} />
                ))}

                {picks.length === 0 && (
                    <div className="text-center text-text-muted py-8">
                        No conviction picks available
                    </div>
                )}
            </div>
        </div>
    );
}

interface RiskTabProps {
    active: boolean;
    onClick: () => void;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    color: string;
}

function RiskTab({ active, onClick, icon: Icon, label, color }: RiskTabProps) {
    return (
        <button
            onClick={onClick}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
        ${active
                    ? `bg-bg-tertiary ${color} border border-white/10`
                    : 'text-text-muted hover:text-text-secondary hover:bg-bg-secondary'
                }`}
        >
            <Icon className="w-4 h-4" />
            {label}
        </button>
    );
}

interface PickCardProps {
    pick: ConvictionPick;
    riskLevel: RiskTab;
}

function PickCard({ pick, riskLevel }: PickCardProps) {
    const gradeColor = GRADE_COLORS[pick.grade];
    const targets = pick.targets[riskLevel];

    const tpPercent = ((targets.takeProfit - pick.entryPrice) / pick.entryPrice * 100).toFixed(1);
    const slPercent = ((targets.stopLoss - pick.entryPrice) / pick.entryPrice * 100).toFixed(1);

    // Conviction score bar
    const convictionWidth = Math.min(100, Math.max(0, pick.convictionScore));
    const convictionColor = pick.convictionScore >= 70
        ? 'bg-emerald-500'
        : pick.convictionScore >= 50
            ? 'bg-yellow-500'
            : 'bg-orange-500';

    return (
        <div className="conviction-pick-card group">
            {/* Rank & Symbol */}
            <div className="flex items-center gap-3">
                <div className="conviction-rank">
                    #{pick.rank}
                </div>
                <div>
                    <div className="flex items-center gap-2">
                        <span className="font-semibold text-text-primary">{pick.symbol}</span>
                        <span className={`sentiment-grade ${gradeColor.bg} ${gradeColor.text} ${gradeColor.border}`}>
                            {pick.grade}
                        </span>
                    </div>
                    <div className="text-xs text-text-muted">
                        {ASSET_TYPE_LABELS[pick.assetType]}
                    </div>
                </div>
            </div>

            {/* Direction Badge */}
            <div className={`px-2 py-0.5 rounded text-xs font-medium
        ${pick.direction === 'LONG'
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-red-500/20 text-red-400'
                }`}
            >
                {pick.direction}
            </div>

            {/* Conviction Score Bar */}
            <div className="flex-1 mx-4 hidden md:block">
                <div className="text-xs text-text-muted mb-1">
                    Conviction: {pick.convictionScore}%
                </div>
                <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
                    <div
                        className={`h-full ${convictionColor} transition-all duration-500`}
                        style={{ width: `${convictionWidth}%` }}
                    />
                </div>
            </div>

            {/* TP/SL Targets */}
            <div className="text-right">
                <div className="flex items-center gap-2 text-xs">
                    <span className="text-emerald-400">TP: +{tpPercent}%</span>
                    <span className="text-text-muted">|</span>
                    <span className="text-red-400">SL: {slPercent}%</span>
                </div>
                <div className="text-xs text-text-muted mt-0.5 truncate max-w-[200px]">
                    {pick.reasoning}
                </div>
            </div>
        </div>
    );
}
