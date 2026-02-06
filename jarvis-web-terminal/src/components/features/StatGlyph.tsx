'use client';

/**
 * StatGlyph - Circular progress ring components for sentiment visualization
 * 
 * Displays:
 * - Real-time sentiment scores
 * - Animated progress rings
 * - Color-coded severity levels
 * - Optional breakdown metrics
 */

import { useEffect, useState, useMemo } from 'react';
import { TrendingUp, TrendingDown, Minus, Activity, Zap, Users, MessageCircle } from 'lucide-react';

interface StatGlyphProps {
    value: number; // 0-100
    label: string;
    size?: 'sm' | 'md' | 'lg';
    icon?: React.ReactNode;
    showValue?: boolean;
    animated?: boolean;
    color?: string;
    className?: string;
}

// Size configurations
const SIZES = {
    sm: { diameter: 48, strokeWidth: 4, fontSize: '0.75rem', iconSize: 14 },
    md: { diameter: 72, strokeWidth: 5, fontSize: '1rem', iconSize: 18 },
    lg: { diameter: 96, strokeWidth: 6, fontSize: '1.25rem', iconSize: 24 },
};

// Color thresholds
function getColorForValue(value: number): string {
    if (value >= 70) return 'var(--accent-neon)';
    if (value >= 50) return 'var(--accent-cyan)';
    if (value >= 30) return 'var(--accent-warning)';
    return 'var(--accent-error)';
}

export function StatGlyph({
    value,
    label,
    size = 'md',
    icon,
    showValue = true,
    animated = true,
    color,
    className = '',
}: StatGlyphProps) {
    const [displayValue, setDisplayValue] = useState(animated ? 0 : value);
    const config = SIZES[size];

    // Animate value on mount
    useEffect(() => {
        if (!animated) {
            setDisplayValue(value);
            return;
        }

        const duration = 1000;
        const steps = 60;
        const increment = value / steps;
        let current = 0;

        const interval = setInterval(() => {
            current += increment;
            if (current >= value) {
                setDisplayValue(value);
                clearInterval(interval);
            } else {
                setDisplayValue(current);
            }
        }, duration / steps);

        return () => clearInterval(interval);
    }, [value, animated]);

    // SVG calculations
    const radius = (config.diameter - config.strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const strokeDashoffset = circumference - (displayValue / 100) * circumference;
    const resolvedColor = color || getColorForValue(value);

    return (
        <div className={`stat-glyph stat-glyph--${size} ${className}`}>
            <div className="stat-glyph__ring">
                <svg
                    width={config.diameter}
                    height={config.diameter}
                    viewBox={`0 0 ${config.diameter} ${config.diameter}`}
                >
                    {/* Background ring */}
                    <circle
                        cx={config.diameter / 2}
                        cy={config.diameter / 2}
                        r={radius}
                        fill="none"
                        stroke="var(--border-primary)"
                        strokeWidth={config.strokeWidth}
                    />
                    {/* Progress ring */}
                    <circle
                        cx={config.diameter / 2}
                        cy={config.diameter / 2}
                        r={radius}
                        fill="none"
                        stroke={resolvedColor}
                        strokeWidth={config.strokeWidth}
                        strokeLinecap="round"
                        strokeDasharray={circumference}
                        strokeDashoffset={strokeDashoffset}
                        transform={`rotate(-90 ${config.diameter / 2} ${config.diameter / 2})`}
                        style={{
                            transition: animated ? 'stroke-dashoffset 0.5s ease-out' : 'none',
                            filter: `drop-shadow(0 0 6px ${resolvedColor})`,
                        }}
                    />
                </svg>
                {/* Center content */}
                <div className="stat-glyph__center">
                    {icon ? (
                        <span style={{ color: resolvedColor }}>{icon}</span>
                    ) : showValue ? (
                        <span
                            className="stat-glyph__value"
                            style={{ fontSize: config.fontSize, color: resolvedColor }}
                        >
                            {Math.round(displayValue)}
                        </span>
                    ) : null}
                </div>
            </div>
            <span className="stat-glyph__label">{label}</span>
        </div>
    );
}

/**
 * SentimentGlyphGroup - Display multiple sentiment metrics together
 */
interface SentimentMetric {
    key: string;
    label: string;
    value: number;
    icon?: React.ReactNode;
}

interface SentimentGlyphGroupProps {
    metrics: SentimentMetric[];
    size?: 'sm' | 'md' | 'lg';
    className?: string;
}

export function SentimentGlyphGroup({
    metrics,
    size = 'sm',
    className = ''
}: SentimentGlyphGroupProps) {
    return (
        <div className={`sentiment-glyph-group ${className}`}>
            {metrics.map((metric) => (
                <StatGlyph
                    key={metric.key}
                    value={metric.value}
                    label={metric.label}
                    icon={metric.icon}
                    size={size}
                />
            ))}
        </div>
    );
}

/**
 * Pre-configured sentiment display with common metrics
 */
interface SentimentDisplayProps {
    overall: number;
    social?: number;
    market?: number;
    technical?: number;
    className?: string;
}

export function SentimentDisplay({
    overall,
    social = 0,
    market = 0,
    technical = 0,
    className = '',
}: SentimentDisplayProps) {
    const trend = useMemo(() => {
        if (overall >= 60) return { icon: <TrendingUp className="w-4 h-4" />, label: 'Bullish' };
        if (overall <= 40) return { icon: <TrendingDown className="w-4 h-4" />, label: 'Bearish' };
        return { icon: <Minus className="w-4 h-4" />, label: 'Neutral' };
    }, [overall]);

    return (
        <div className={`sentiment-display ${className}`}>
            {/* Main sentiment ring */}
            <div className="sentiment-display__main">
                <StatGlyph
                    value={overall}
                    label="Sentiment"
                    size="lg"
                    showValue
                />
                <div className="sentiment-display__trend" style={{ color: getColorForValue(overall) }}>
                    {trend.icon}
                    <span>{trend.label}</span>
                </div>
            </div>

            {/* Breakdown metrics */}
            <div className="sentiment-display__breakdown">
                <StatGlyph
                    value={social}
                    label="Social"
                    size="sm"
                    icon={<MessageCircle className="w-3 h-3" />}
                />
                <StatGlyph
                    value={market}
                    label="Market"
                    size="sm"
                    icon={<Activity className="w-3 h-3" />}
                />
                <StatGlyph
                    value={technical}
                    label="Technical"
                    size="sm"
                    icon={<Zap className="w-3 h-3" />}
                />
            </div>
        </div>
    );
}

/**
 * Compact inline sentiment indicator
 */
export function SentimentBadge({
    value,
    showLabel = true,
    className = ''
}: {
    value: number;
    showLabel?: boolean;
    className?: string;
}) {
    const color = getColorForValue(value);
    const Icon = value >= 60 ? TrendingUp : value <= 40 ? TrendingDown : Minus;

    return (
        <span
            className={`sentiment-badge ${className}`}
            style={{ '--sentiment-color': color } as React.CSSProperties}
        >
            <Icon className="w-3 h-3" />
            <span className="sentiment-badge__value">{value}</span>
            {showLabel && (
                <span className="sentiment-badge__label">
                    {value >= 60 ? 'Bullish' : value <= 40 ? 'Bearish' : 'Neutral'}
                </span>
            )}
        </span>
    );
}
