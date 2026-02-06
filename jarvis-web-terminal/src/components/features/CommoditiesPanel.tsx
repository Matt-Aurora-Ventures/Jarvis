'use client';

/**
 * Commodities Panel
 * 
 * Displays commodity movers and precious metals outlook.
 */

import { CommodityMover, PreciousMetalsOutlook, REGIME_COLORS } from '@/types/sentiment-types';
import { Gem, Fuel, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface CommoditiesPanelProps {
    commodities: CommodityMover[];
    preciousMetals: PreciousMetalsOutlook;
    isLoading?: boolean;
}

export function CommoditiesPanel({ commodities, preciousMetals, isLoading }: CommoditiesPanelProps) {
    if (isLoading) {
        return (
            <div className="sentiment-panel">
                <div className="sentiment-panel-header">
                    <Gem className="w-5 h-5 text-accent-primary" />
                    <h3>Commodities</h3>
                </div>
                <div className="animate-pulse text-text-muted text-center py-6">
                    Loading commodities...
                </div>
            </div>
        );
    }

    return (
        <div className="sentiment-panel">
            <div className="sentiment-panel-header">
                <Gem className="w-5 h-5 text-amber-400" />
                <h3>💎 Commodities & Metals</h3>
            </div>

            {/* Precious Metals */}
            <div className="mb-4">
                <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Precious Metals</div>
                <div className="grid grid-cols-3 gap-2">
                    <MetalCard
                        name="Gold"
                        emoji="🥇"
                        direction={preciousMetals.goldDirection}
                        outlook={preciousMetals.goldOutlook}
                    />
                    <MetalCard
                        name="Silver"
                        emoji="🥈"
                        direction={preciousMetals.silverDirection}
                        outlook={preciousMetals.silverOutlook}
                    />
                    <MetalCard
                        name="Platinum"
                        emoji="⚪"
                        direction={preciousMetals.platinumDirection}
                        outlook={preciousMetals.platinumOutlook}
                    />
                </div>
            </div>

            {/* Commodity Movers */}
            <div>
                <div className="text-xs text-text-muted uppercase tracking-wider mb-2">Top Movers</div>
                <div className="space-y-2">
                    {commodities.map((commodity, i) => (
                        <div
                            key={commodity.name}
                            className="flex items-center gap-3 p-2 rounded-lg bg-bg-secondary/30 border border-white/5"
                        >
                            <Fuel className="w-4 h-4 text-text-muted" />
                            <span className="font-medium text-text-primary">{commodity.name}</span>

                            <span className={`ml-auto text-sm ${commodity.direction === 'LONG' ? 'text-emerald-400' : 'text-red-400'}`}>
                                {commodity.change}
                            </span>

                            <span className={`px-1.5 py-0.5 text-xs rounded ${commodity.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                                {commodity.direction}
                            </span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

interface MetalCardProps {
    name: string;
    emoji: string;
    direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    outlook: string;
}

function MetalCard({ name, emoji, direction, outlook }: MetalCardProps) {
    const colors = REGIME_COLORS[direction];
    const Icon = direction === 'BULLISH' ? TrendingUp : direction === 'BEARISH' ? TrendingDown : Minus;

    return (
        <div className={`p-2 rounded-lg ${colors.bg} text-center border border-white/5`}>
            <div className="text-lg mb-1">{emoji}</div>
            <div className="text-xs font-medium text-text-primary">{name}</div>
            <div className={`flex items-center justify-center gap-1 mt-1 ${colors.text}`}>
                <Icon className="w-3 h-3" />
                <span className="text-xs">{direction}</span>
            </div>
        </div>
    );
}
