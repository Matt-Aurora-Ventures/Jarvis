'use client';

/**
 * TradingGuard - Visual safety indicator for the trading terminal
 * 
 * Displays:  
 * - Real-time confidence status
 * - Volatility warnings
 * - Circuit breaker alerts
 * - Trade safety recommendations
 */

import { useConfidence } from '@/hooks/useConfidence';
import { AlertTriangle, Shield, ShieldCheck, ShieldAlert, Activity, Zap } from 'lucide-react';

interface TradingGuardProps {
    symbol?: string;
    mint?: string;
    className?: string;
    compact?: boolean;
}

export function TradingGuard({
    symbol = 'SOL',
    mint,
    className = '',
    compact = false
}: TradingGuardProps) {
    const {
        price,
        confidence,
        confidenceRatio,
        confidenceScore,
        tier,
        source,
        isSafeToTrade,
        isVolatile,
        circuitBreaker,
        safetyStatus,
        isLoading,
        reason,
    } = useConfidence({ symbol, mint });

    // Circuit breaker alert (highest priority)
    if (circuitBreaker.isTripped) {
        return (
            <div className={`trading-guard trading-guard--critical ${className}`}>
                <div className="trading-guard__icon">
                    <ShieldAlert className="w-5 h-5 animate-pulse" />
                </div>
                <div className="trading-guard__content">
                    <span className="trading-guard__title">🛡️ Circuit Breaker Active</span>
                    {!compact && (
                        <span className="trading-guard__reason">
                            {circuitBreaker.reason || 'Market conditions unsafe'}
                        </span>
                    )}
                </div>
            </div>
        );
    }

    // Loading state
    if (isLoading) {
        return (
            <div className={`trading-guard trading-guard--loading ${className}`}>
                <Activity className="w-4 h-4 animate-pulse" />
                <span>Checking market confidence...</span>
            </div>
        );
    }

    // High volatility warning
    if (isVolatile || !isSafeToTrade) {
        return (
            <div className={`trading-guard trading-guard--warning ${className}`}>
                <div className="trading-guard__icon">
                    <AlertTriangle className="w-5 h-5" />
                </div>
                <div className="trading-guard__content">
                    <span className="trading-guard__title">
                        ⚠️ {isVolatile ? 'High Volatility' : 'Trade Blocked'}
                    </span>
                    {!compact && (
                        <>
                            <span className="trading-guard__metric">
                                Confidence: ±{(confidenceRatio * 100).toFixed(3)}%
                            </span>
                            {reason && (
                                <span className="trading-guard__reason">{reason}</span>
                            )}
                        </>
                    )}
                </div>
                <div className="trading-guard__score">
                    <span className="text-xs opacity-70">Score</span>
                    <span className="text-lg font-bold">
                        {(confidenceScore * 100).toFixed(0)}
                    </span>
                </div>
            </div>
        );
    }

    // Safe to trade
    return (
        <div className={`trading-guard trading-guard--safe ${className}`}>
            <div className="trading-guard__icon">
                <ShieldCheck className="w-5 h-5" />
            </div>
            <div className="trading-guard__content">
                <span className="trading-guard__title">✅ Safe to Trade</span>
                {!compact && (
                    <div className="trading-guard__details">
                        <span className="trading-guard__metric">
                            <Zap className="w-3 h-3" />
                            {tier.toUpperCase()} via {source.toUpperCase()}
                        </span>
                        <span className="trading-guard__metric">
                            σ: ±{(confidenceRatio * 100).toFixed(4)}%
                        </span>
                    </div>
                )}
            </div>
            {!compact && (
                <div className="trading-guard__score trading-guard__score--good">
                    <span className="text-xs opacity-70">Confidence</span>
                    <span className="text-lg font-bold text-[var(--accent-green)]">
                        {(confidenceScore * 100).toFixed(0)}%
                    </span>
                </div>
            )}
        </div>
    );
}

/**
 * Compact confidence badge for inline use
 */
export function ConfidenceBadge({
    symbol = 'SOL',
    mint,
    showScore = true
}: {
    symbol?: string;
    mint?: string;
    showScore?: boolean;
}) {
    const { confidenceScore, safetyStatus, isLoading } = useConfidence({ symbol, mint });

    if (isLoading) {
        return (
            <span className="confidence-badge confidence-badge--loading">
                <Activity className="w-3 h-3 animate-spin" />
            </span>
        );
    }

    const Icon = safetyStatus.level === 'safe' ? ShieldCheck :
        safetyStatus.level === 'critical' ? ShieldAlert : Shield;

    return (
        <span
            className={`confidence-badge confidence-badge--${safetyStatus.level}`}
            style={{ '--badge-color': safetyStatus.color } as React.CSSProperties}
            title={safetyStatus.label}
        >
            <Icon className="w-3 h-3" />
            {showScore && (
                <span className="confidence-badge__score">
                    {(confidenceScore * 100).toFixed(0)}
                </span>
            )}
        </span>
    );
}

// Add styles to globals.css
const guardStyles = `
.trading-guard {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    border-radius: 0.75rem;
    border: 1px solid;
    transition: all 0.2s ease;
}

.trading-guard--safe {
    background: rgba(57, 255, 20, 0.05);
    border-color: rgba(57, 255, 20, 0.2);
}

.trading-guard--warning {
    background: rgba(251, 191, 36, 0.1);
    border-color: rgba(251, 191, 36, 0.3);
}

.trading-guard--critical {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    animation: pulse-critical 2s infinite;
}

.trading-guard--loading {
    background: var(--bg-secondary);
    border-color: var(--border-primary);
    color: var(--text-muted);
}

.trading-guard__icon {
    flex-shrink: 0;
}

.trading-guard--safe .trading-guard__icon {
    color: var(--accent-green);
}

.trading-guard--warning .trading-guard__icon {
    color: var(--accent-yellow);
}

.trading-guard--critical .trading-guard__icon {
    color: var(--accent-red);
}

.trading-guard__content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
}

.trading-guard__title {
    font-weight: 600;
    font-size: 0.875rem;
}

.trading-guard__details {
    display: flex;
    gap: 1rem;
}

.trading-guard__metric {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.75rem;
    color: var(--text-muted);
    font-family: var(--font-mono);
}

.trading-guard__reason {
    font-size: 0.75rem;
    color: var(--text-muted);
}

.trading-guard__score {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 0.5rem 0.75rem;
    background: var(--bg-tertiary);
    border-radius: 0.5rem;
}

.trading-guard__score--good {
    background: rgba(57, 255, 20, 0.1);
}

.confidence-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.25rem 0.5rem;
    border-radius: 9999px;
    font-size: 0.75rem;
    font-weight: 500;
    background: color-mix(in srgb, var(--badge-color) 15%, transparent);
    color: var(--badge-color);
    border: 1px solid color-mix(in srgb, var(--badge-color) 30%, transparent);
}

.confidence-badge--loading {
    background: var(--bg-tertiary);
    color: var(--text-muted);
}

@keyframes pulse-critical {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
}
`;
