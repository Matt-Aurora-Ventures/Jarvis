'use client';

/**
 * Market Regime Indicator
 * 
 * Displays BTC/SOL trend indicators with 24h changes
 * and overall market risk assessment.
 */

import { MarketRegime, REGIME_COLORS } from '@/types/sentiment-types';
import { TrendingUp, TrendingDown, Minus, Shield, AlertTriangle, Activity } from 'lucide-react';

interface MarketRegimeIndicatorProps {
    regime: MarketRegime;
    isLoading?: boolean;
}

export function MarketRegimeIndicator({ regime, isLoading }: MarketRegimeIndicatorProps) {
    if (isLoading) {
        return (
            <div className="sentiment-panel sentiment-panel-compact">
                <div className="animate-pulse text-text-muted text-center py-4">
                    Loading market regime...
                </div>
            </div>
        );
    }

    const regimeColor = regime.regime === 'BULL'
        ? 'text-emerald-400'
        : regime.regime === 'BEAR'
            ? 'text-accent-error'
            : 'text-text-muted';

    const regimeBg = regime.regime === 'BULL'
        ? 'bg-emerald-500/10 border-emerald-500/30'
        : regime.regime === 'BEAR'
            ? 'bg-accent-error/10 border-accent-error/30'
            : 'bg-accent-warning/10 border-accent-warning/30';

    const RiskIcon = regime.riskLevel === 'HIGH'
        ? AlertTriangle
        : regime.riskLevel === 'LOW'
            ? Shield
            : Activity;

    const riskColor = regime.riskLevel === 'HIGH'
        ? 'text-accent-error'
        : regime.riskLevel === 'LOW'
            ? 'text-emerald-400'
            : 'text-text-muted';

    return (
        <div className={`sentiment-panel sentiment-panel-compact border ${regimeBg}`}>
            {/* Regime Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <div className={`text-2xl font-bold ${regimeColor}`}>
                        {regime.regime === 'BULL' ? '🐂' : regime.regime === 'BEAR' ? '🐻' : '⚖️'}
                    </div>
                    <div>
                        <div className={`text-lg font-semibold ${regimeColor}`}>
                            {regime.regime} Market
                        </div>
                        <div className="text-xs text-text-muted">Current Regime</div>
                    </div>
                </div>

                <div className={`flex items-center gap-1 px-2 py-1 rounded ${riskColor} bg-bg-tertiary`}>
                    <RiskIcon className="w-4 h-4" />
                    <span className="text-xs font-medium">{regime.riskLevel} Risk</span>
                </div>
            </div>

            {/* BTC/SOL Indicators */}
            <div className="grid grid-cols-2 gap-3">
                <TrendCard
                    symbol="BTC"
                    icon="₿"
                    trend={regime.btcTrend}
                    change24h={regime.btcChange24h}
                />
                <TrendCard
                    symbol="SOL"
                    icon="◎"
                    trend={regime.solTrend}
                    change24h={regime.solChange24h}
                />
            </div>
        </div>
    );
}

interface TrendCardProps {
    symbol: string;
    icon: string;
    trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    change24h: number;
}

function TrendCard({ symbol, icon, trend, change24h }: TrendCardProps) {
    const colors = REGIME_COLORS[trend];
    const TrendIcon = trend === 'BULLISH'
        ? TrendingUp
        : trend === 'BEARISH'
            ? TrendingDown
            : Minus;

    const isPositive = change24h > 0;

    return (
        <div className={`p-3 rounded-lg ${colors.bg} border border-white/5`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span className="text-lg">{icon}</span>
                    <span className="font-semibold text-text-primary">{symbol}</span>
                </div>
                <TrendIcon className={`w-4 h-4 ${colors.text}`} />
            </div>

            <div className={`text-xl font-bold ${isPositive ? 'text-emerald-400' : change24h < 0 ? 'text-accent-error' : 'text-text-muted'}`}>
                {isPositive ? '+' : ''}{change24h.toFixed(2)}%
            </div>

            <div className={`text-xs mt-1 ${colors.text}`}>
                {trend}
            </div>
        </div>
    );
}
