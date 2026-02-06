'use client';

/**
 * PriorityFeeSelector - Dynamic fee selection for trade execution
 * 
 * 3-Tier System:
 * - Eco: Lowest cost, standard priority
 * - Fast: Network-aware priority fees
 * - Turbo: Jito MEV protection + highest priority
 */

import { useState, useEffect } from 'react';
import { PRIORITY_FEE_TIERS, PriorityFeeLevel } from '@/lib/jito-client';
import { Zap, Leaf, Rocket, Shield, Info } from 'lucide-react';

export type FeeLevel = 'eco' | 'fast' | 'turbo';

interface PriorityFeeSelectorProps {
    value: FeeLevel;
    onChange: (level: FeeLevel) => void;
    shieldReactorActive?: boolean;
    compact?: boolean;
    className?: string;
}

const TIER_ICONS: Record<FeeLevel, React.ReactNode> = {
    eco: <Leaf className="w-4 h-4" />,
    fast: <Zap className="w-4 h-4" />,
    turbo: <Rocket className="w-4 h-4" />,
};

const TIER_COLORS: Record<FeeLevel, string> = {
    eco: 'var(--accent-success)',
    fast: 'var(--accent-warning)',
    turbo: 'var(--accent-neon)',
};

export function PriorityFeeSelector({
    value,
    onChange,
    shieldReactorActive = false,
    compact = false,
    className = '',
}: PriorityFeeSelectorProps) {
    const tiers = Object.entries(PRIORITY_FEE_TIERS) as [FeeLevel, PriorityFeeLevel][];

    return (
        <div className={`priority-fee-selector ${className}`}>
            {!compact && (
                <div className="priority-fee-selector__header">
                    <span className="text-sm font-medium text-[var(--text-secondary)]">
                        Priority Fee
                    </span>
                    {shieldReactorActive && (
                        <span className="shield-badge">
                            <Shield className="w-3 h-3" />
                            MEV Protected
                        </span>
                    )}
                </div>
            )}

            <div className="priority-fee-selector__options">
                {tiers.map(([level, tier]) => {
                    const isSelected = value === level;
                    const isTurbo = level === 'turbo';
                    const isLocked = isTurbo && !shieldReactorActive;

                    return (
                        <button
                            key={level}
                            onClick={() => !isLocked && onChange(level)}
                            disabled={isLocked}
                            className={`
                                priority-option
                                ${isSelected ? 'priority-option--selected' : ''}
                                ${isLocked ? 'priority-option--locked' : ''}
                            `}
                            style={{
                                '--tier-color': TIER_COLORS[level],
                            } as React.CSSProperties}
                        >
                            <div className="priority-option__icon">
                                {TIER_ICONS[level]}
                            </div>
                            <div className="priority-option__content">
                                <span className="priority-option__label">
                                    {tier.label}
                                    {isTurbo && shieldReactorActive && (
                                        <Shield className="w-3 h-3 inline ml-1" />
                                    )}
                                </span>
                                {!compact && (
                                    <span className="priority-option__desc">
                                        {isLocked ? 'Enable Shield Reactor' : tier.description}
                                    </span>
                                )}
                            </div>
                            {!compact && (
                                <div className="priority-option__time">
                                    ~{tier.estimatedTimeMs / 1000}s
                                </div>
                            )}
                        </button>
                    );
                })}
            </div>

            {value === 'turbo' && shieldReactorActive && !compact && (
                <div className="priority-fee-selector__note">
                    <Info className="w-3 h-3" />
                    <span>
                        Jito bundle will include 0.001 SOL tip for MEV protection
                    </span>
                </div>
            )}
        </div>
    );
}

/**
 * Compact inline fee badge showing current selection
 */
export function FeeBadge({
    level,
    onClick,
    className = ''
}: {
    level: FeeLevel;
    onClick?: () => void;
    className?: string;
}) {
    const tier = PRIORITY_FEE_TIERS[level];

    return (
        <button
            onClick={onClick}
            className={`fee-badge ${className}`}
            style={{ '--tier-color': TIER_COLORS[level] } as React.CSSProperties}
        >
            {TIER_ICONS[level]}
            <span>{tier.label}</span>
        </button>
    );
}
