'use client';

import { useState, useEffect } from 'react';
import { Sliders, Save, RotateCcw, Zap, Shield, Target, TrendingUp } from 'lucide-react';

export interface AlgoParameters {
    // Sentiment thresholds
    sentimentBuyThreshold: number; // Min sentiment score to trigger buy signal (0-100)
    sentimentSellThreshold: number; // Max sentiment score before triggering sell (0-100)

    // Volume/liquidity filters
    volumeSpikeMultiplier: number; // Volume spike sensitivity (1-10x)
    minLiquidityUsd: number; // Minimum liquidity to trade (1k-1M)

    // bags.fm graduation
    graduationScoreCutoff: number; // Min graduation score for snipes (0-100)
    holderDistributionWeight: number; // Weight for holder distribution (0-100)

    // Risk management
    defaultTP: number; // Default take profit % (5-200)
    defaultSL: number; // Default stop loss % (1-50)
    maxPositionPct: number; // Max position size % of portfolio (1-50)

    // AI confidence
    minConfidenceScore: number; // Min AI confidence to show signal (0-100)
}

const DEFAULT_PARAMS: AlgoParameters = {
    sentimentBuyThreshold: 60,
    sentimentSellThreshold: 40,
    volumeSpikeMultiplier: 3,
    minLiquidityUsd: 10000,
    graduationScoreCutoff: 65,
    holderDistributionWeight: 70,
    defaultTP: 20,
    defaultSL: 10,
    maxPositionPct: 10,
    minConfidenceScore: 60,
};

const PRESETS: { name: string; description: string; params: Partial<AlgoParameters> }[] = [
    {
        name: 'Conservative',
        description: 'Lower risk, higher thresholds',
        params: {
            sentimentBuyThreshold: 75,
            sentimentSellThreshold: 30,
            graduationScoreCutoff: 80,
            minLiquidityUsd: 50000,
            defaultTP: 15,
            defaultSL: 5,
            maxPositionPct: 5,
            minConfidenceScore: 75,
        },
    },
    {
        name: 'Balanced',
        description: 'Moderate risk/reward',
        params: DEFAULT_PARAMS,
    },
    {
        name: 'Aggressive',
        description: 'Higher risk, more signals',
        params: {
            sentimentBuyThreshold: 50,
            sentimentSellThreshold: 45,
            graduationScoreCutoff: 50,
            minLiquidityUsd: 5000,
            defaultTP: 50,
            defaultSL: 15,
            maxPositionPct: 20,
            minConfidenceScore: 40,
        },
    },
];

interface SliderInputProps {
    label: string;
    value: number;
    onChange: (value: number) => void;
    min: number;
    max: number;
    step?: number;
    unit?: string;
    icon?: React.ReactNode;
    description?: string;
}

function SliderInput({
    label,
    value,
    onChange,
    min,
    max,
    step = 1,
    unit = '',
    icon,
    description
}: SliderInputProps) {
    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm">
                    {icon}
                    <span className="font-medium">{label}</span>
                </div>
                <span className="text-sm font-mono text-accent-neon">
                    {unit === '$' ? `$${value.toLocaleString()}` : `${value}${unit}`}
                </span>
            </div>
            {description && (
                <p className="text-xs text-text-muted">{description}</p>
            )}
            <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={value}
                onChange={(e) => onChange(Number(e.target.value))}
                className="w-full h-1 bg-bg-secondary/50 rounded-lg appearance-none cursor-pointer accent-accent-neon"
            />
            <div className="flex justify-between text-xs text-text-muted">
                <span>{unit === '$' ? `$${min.toLocaleString()}` : `${min}${unit}`}</span>
                <span>{unit === '$' ? `$${max.toLocaleString()}` : `${max}${unit}`}</span>
            </div>
        </div>
    );
}

export function AlgoConfig() {
    const [params, setParams] = useState<AlgoParameters>(DEFAULT_PARAMS);
    const [activePreset, setActivePreset] = useState<string>('Balanced');
    const [hasChanges, setHasChanges] = useState(false);

    // Load from localStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem('algo_params');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                setParams({ ...DEFAULT_PARAMS, ...parsed });
                // Check which preset matches
                const matching = PRESETS.find(p =>
                    JSON.stringify({ ...DEFAULT_PARAMS, ...p.params }) === JSON.stringify(parsed)
                );
                setActivePreset(matching?.name || 'Custom');
            } catch (e) {
                console.error('Failed to load algo params', e);
            }
        }
    }, []);

    // Update single param
    const updateParam = <K extends keyof AlgoParameters>(key: K, value: AlgoParameters[K]) => {
        setParams(prev => ({ ...prev, [key]: value }));
        setActivePreset('Custom');
        setHasChanges(true);
    };

    // Apply preset
    const applyPreset = (presetName: string) => {
        const preset = PRESETS.find(p => p.name === presetName);
        if (preset) {
            setParams({ ...DEFAULT_PARAMS, ...preset.params });
            setActivePreset(presetName);
            setHasChanges(true);
        }
    };

    // Save params
    const saveParams = () => {
        localStorage.setItem('algo_params', JSON.stringify(params));
        setHasChanges(false);
        // Trigger event for other components to pick up changes
        window.dispatchEvent(new CustomEvent('algo-params-updated', { detail: params }));
    };

    // Reset to defaults
    const resetToDefaults = () => {
        setParams(DEFAULT_PARAMS);
        setActivePreset('Balanced');
        setHasChanges(true);
    };

    return (
        <div className="card-glass p-4 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between pb-3 border-b border-border-primary/30">
                <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-accent-neon" />
                    <span className="font-display font-bold">ALGO CONFIGURATION</span>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={resetToDefaults}
                        className="p-1.5 rounded hover:bg-bg-secondary/50 transition-colors"
                        title="Reset to defaults"
                    >
                        <RotateCcw className="w-4 h-4 text-text-muted" />
                    </button>
                    <button
                        onClick={saveParams}
                        disabled={!hasChanges}
                        className={`
                            flex items-center gap-1 px-3 py-1.5 rounded text-sm font-medium transition-all
                            ${hasChanges
                                ? 'bg-accent-neon text-black hover:bg-accent-neon/80'
                                : 'bg-bg-secondary/30 text-text-muted cursor-not-allowed'}
                        `}
                    >
                        <Save className="w-3 h-3" />
                        Save
                    </button>
                </div>
            </div>

            {/* Presets */}
            <div className="space-y-2">
                <label className="text-xs font-mono text-text-muted uppercase">Presets</label>
                <div className="flex gap-2">
                    {PRESETS.map((preset) => (
                        <button
                            key={preset.name}
                            onClick={() => applyPreset(preset.name)}
                            className={`
                                flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all
                                ${activePreset === preset.name
                                    ? 'bg-accent-neon text-black'
                                    : 'bg-bg-secondary/30 border border-border-primary/50 hover:border-accent-neon'}
                            `}
                        >
                            {preset.name}
                        </button>
                    ))}
                </div>
                {activePreset !== 'Custom' && (
                    <p className="text-xs text-text-muted">
                        {PRESETS.find(p => p.name === activePreset)?.description}
                    </p>
                )}
                {activePreset === 'Custom' && (
                    <p className="text-xs text-accent-neon">
                        Custom settings - don't forget to save!
                    </p>
                )}
            </div>

            {/* Sentiment Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-bold text-text-muted">
                    <Zap className="w-4 h-4" />
                    SENTIMENT THRESHOLDS
                </div>

                <SliderInput
                    label="Buy Signal Threshold"
                    value={params.sentimentBuyThreshold}
                    onChange={(v) => updateParam('sentimentBuyThreshold', v)}
                    min={30}
                    max={90}
                    unit=""
                    description="Minimum sentiment score to show buy signals"
                />

                <SliderInput
                    label="Sell Signal Threshold"
                    value={params.sentimentSellThreshold}
                    onChange={(v) => updateParam('sentimentSellThreshold', v)}
                    min={10}
                    max={60}
                    unit=""
                    description="Below this sentiment, show sell signals"
                />

                <SliderInput
                    label="Min AI Confidence"
                    value={params.minConfidenceScore}
                    onChange={(v) => updateParam('minConfidenceScore', v)}
                    min={30}
                    max={90}
                    unit=""
                    description="Minimum confidence score to display signals"
                />
            </div>

            {/* Liquidity/Volume Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-bold text-text-muted">
                    <TrendingUp className="w-4 h-4" />
                    VOLUME & LIQUIDITY
                </div>

                <SliderInput
                    label="Volume Spike Sensitivity"
                    value={params.volumeSpikeMultiplier}
                    onChange={(v) => updateParam('volumeSpikeMultiplier', v)}
                    min={1}
                    max={10}
                    step={0.5}
                    unit="x"
                    description="Multiplier for detecting volume spikes"
                />

                <SliderInput
                    label="Minimum Liquidity"
                    value={params.minLiquidityUsd}
                    onChange={(v) => updateParam('minLiquidityUsd', v)}
                    min={1000}
                    max={500000}
                    step={1000}
                    unit="$"
                    description="Filter out tokens with less liquidity"
                />
            </div>

            {/* Graduation Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-bold text-text-muted">
                    <Target className="w-4 h-4" />
                    DEGEN GRADUATION
                </div>

                <SliderInput
                    label="Graduation Score Cutoff"
                    value={params.graduationScoreCutoff}
                    onChange={(v) => updateParam('graduationScoreCutoff', v)}
                    min={30}
                    max={90}
                    unit=""
                    description="Minimum graduation score for snipe signals"
                />

                <SliderInput
                    label="Holder Distribution Weight"
                    value={params.holderDistributionWeight}
                    onChange={(v) => updateParam('holderDistributionWeight', v)}
                    min={0}
                    max={100}
                    unit="%"
                    description="How much to weight holder distribution in scoring"
                />
            </div>

            {/* Risk Management Section */}
            <div className="space-y-4">
                <div className="flex items-center gap-2 text-sm font-bold text-text-muted">
                    <Shield className="w-4 h-4" />
                    RISK MANAGEMENT
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <SliderInput
                        label="Default TP"
                        value={params.defaultTP}
                        onChange={(v) => updateParam('defaultTP', v)}
                        min={5}
                        max={200}
                        unit="%"
                    />

                    <SliderInput
                        label="Default SL"
                        value={params.defaultSL}
                        onChange={(v) => updateParam('defaultSL', v)}
                        min={1}
                        max={50}
                        unit="%"
                    />
                </div>

                <SliderInput
                    label="Max Position Size"
                    value={params.maxPositionPct}
                    onChange={(v) => updateParam('maxPositionPct', v)}
                    min={1}
                    max={50}
                    unit="%"
                    description="Maximum % of portfolio per position"
                />
            </div>

            {/* Live Preview */}
            <div className="bg-bg-secondary/30 rounded-lg p-4 border border-border-primary/30">
                <div className="text-xs font-mono text-text-muted mb-2">SIGNAL PREVIEW</div>
                <div className="text-sm space-y-1">
                    <p>
                        <span className="text-accent-success">BUY</span> when sentiment ≥ {params.sentimentBuyThreshold} and confidence ≥ {params.minConfidenceScore}
                    </p>
                    <p>
                        <span className="text-accent-error">SELL</span> when sentiment ≤ {params.sentimentSellThreshold}
                    </p>
                    <p>
                        <span className="text-accent-neon">SNIPE</span> graduations with score ≥ {params.graduationScoreCutoff} and liquidity ≥ ${params.minLiquidityUsd.toLocaleString()}
                    </p>
                </div>
            </div>
        </div>
    );
}

// Hook to get current algo params
export function useAlgoParams(): { params: AlgoParameters } {
    const [params, setParams] = useState<AlgoParameters>(DEFAULT_PARAMS);

    useEffect(() => {
        const saved = localStorage.getItem('algo_params');
        if (saved) {
            try {
                setParams({ ...DEFAULT_PARAMS, ...JSON.parse(saved) });
            } catch (e) {
                console.error('Failed to load algo params', e);
            }
        }

        const handleUpdate = (e: CustomEvent<AlgoParameters>) => {
            setParams(e.detail);
        };

        window.addEventListener('algo-params-updated', handleUpdate as EventListener);
        return () => window.removeEventListener('algo-params-updated', handleUpdate as EventListener);
    }, []);

    return { params };
}
