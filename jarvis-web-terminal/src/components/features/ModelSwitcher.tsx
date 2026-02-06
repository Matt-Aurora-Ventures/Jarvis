'use client';

import { useState } from 'react';
import {
    Brain,
    Zap,
    Copy,
    Check,
    Terminal,
    ExternalLink,
    Sparkles,
    Clock,
    Activity,
    ChevronDown,
    ChevronUp,
    Settings
} from 'lucide-react';

interface ModelInfo {
    id: string;
    name: string;
    alias: string;
    contextWindow: string;
    outputTokens: string;
    features: string[];
    isNew?: boolean;
    isCurrent?: boolean;
}

const AVAILABLE_MODELS: ModelInfo[] = [
    {
        id: 'claude-opus-4-6',
        name: 'Claude Opus 4.6',
        alias: 'opus',
        contextWindow: '1M tokens (beta)',
        outputTokens: '128K',
        features: ['Agent Teams', 'Adaptive Thinking', '1M Context', '+190 Elo vs 4.5'],
        isNew: true,
        isCurrent: false
    },
    {
        id: 'claude-opus-4-5-20251101',
        name: 'Claude Opus 4.5',
        alias: 'opus',
        contextWindow: '200K tokens',
        outputTokens: '32K',
        features: ['Most Capable', 'Best for Complex Tasks', 'Deep Reasoning'],
        isCurrent: true // Currently running in VS Code
    },
    {
        id: 'claude-sonnet-4-5-20250929',
        name: 'Claude Sonnet 4.5',
        alias: 'sonnet',
        contextWindow: '200K tokens',
        outputTokens: '64K',
        features: ['Fast', 'Cost-effective', 'Great for coding'],
        isCurrent: false
    },
    {
        id: 'claude-haiku',
        name: 'Claude Haiku',
        alias: 'haiku',
        contextWindow: '200K tokens',
        outputTokens: '16K',
        features: ['Fastest', 'Cheapest', 'Simple tasks']
    }
];

export function ModelSwitcher() {
    const [expanded, setExpanded] = useState(false);
    const [copied, setCopied] = useState<string | null>(null);

    const copyToClipboard = async (text: string, id: string) => {
        await navigator.clipboard.writeText(text);
        setCopied(id);
        setTimeout(() => setCopied(null), 2000);
    };

    const currentModel = AVAILABLE_MODELS.find(m => m.isCurrent);
    const opus46 = AVAILABLE_MODELS.find(m => m.id === 'claude-opus-4-6');

    return (
        <div className="card-glass p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-purple-500/20">
                        <Brain className="w-5 h-5 text-purple-400" />
                    </div>
                    <div>
                        <h2 className="font-display font-bold text-lg text-text-primary">AI Model</h2>
                        <p className="text-[10px] font-mono text-text-muted">Claude Code Integration</p>
                    </div>
                </div>
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="p-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary transition-all"
                >
                    {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </button>
            </div>

            {/* Current Model Status */}
            <div className="p-3 rounded-lg bg-bg-tertiary/50 border border-border-primary">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-text-muted">Current Session</span>
                    <span className="flex items-center gap-1 text-xs text-green-400">
                        <Activity className="w-3 h-3 animate-pulse" />
                        ACTIVE
                    </span>
                </div>
                <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-text-primary">{currentModel?.name}</span>
                    <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px] font-mono">
                        {currentModel?.alias}
                    </span>
                </div>
            </div>

            {/* Opus 4.6 Upgrade Banner */}
            {opus46 && !opus46.isCurrent && (
                <div className="p-3 rounded-lg bg-accent-neon/10 border border-accent-neon/30">
                    <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="w-4 h-4 text-accent-neon" />
                        <span className="font-mono font-bold text-accent-neon">Opus 4.6 Available!</span>
                        <span className="px-1.5 py-0.5 rounded bg-accent-neon/20 text-accent-neon text-[10px] font-mono animate-pulse">
                            NEW TODAY
                        </span>
                    </div>
                    <p className="text-xs text-text-secondary mb-3">
                        1M token context, Agent Teams, +190 Elo improvement
                    </p>

                    {/* CLI Command */}
                    <div className="space-y-2">
                        <p className="text-[10px] text-text-muted uppercase">Run in Terminal:</p>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 px-3 py-2 rounded bg-bg-primary border border-border-primary font-mono text-xs text-text-primary">
                                cd "c:\Users\lucid\OneDrive\Desktop\Projects\Jarvis" && claude --model opus
                            </code>
                            <button
                                onClick={() => copyToClipboard('cd "c:\\Users\\lucid\\OneDrive\\Desktop\\Projects\\Jarvis" && claude --model opus', 'opus-cmd')}
                                className="p-2 rounded-lg bg-accent-neon text-theme-dark hover:bg-accent-neon/80 transition-all"
                            >
                                {copied === 'opus-cmd' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Expanded Model List */}
            {expanded && (
                <div className="space-y-2 pt-2 border-t border-border-primary">
                    <p className="text-xs text-text-muted mb-2">Available Models:</p>
                    {AVAILABLE_MODELS.map(model => (
                        <div
                            key={model.id}
                            className={`p-3 rounded-lg border ${
                                model.isCurrent
                                    ? 'bg-blue-500/10 border-blue-500/30'
                                    : model.isNew
                                    ? 'bg-accent-neon/5 border-accent-neon/20'
                                    : 'bg-bg-tertiary/50 border-border-primary'
                            }`}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                    <span className="font-mono font-bold text-text-primary text-sm">{model.name}</span>
                                    {model.isNew && (
                                        <span className="px-1.5 py-0.5 rounded bg-accent-neon/20 text-accent-neon text-[10px] font-mono">
                                            NEW
                                        </span>
                                    )}
                                    {model.isCurrent && (
                                        <span className="px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 text-[10px] font-mono">
                                            CURRENT
                                        </span>
                                    )}
                                </div>
                                <button
                                    onClick={() => copyToClipboard(`claude --model ${model.alias}`, model.id)}
                                    className="p-1.5 rounded bg-bg-tertiary hover:bg-bg-secondary transition-all"
                                    title="Copy CLI command"
                                >
                                    {copied === model.id ? (
                                        <Check className="w-3 h-3 text-green-400" />
                                    ) : (
                                        <Terminal className="w-3 h-3 text-text-muted" />
                                    )}
                                </button>
                            </div>
                            <div className="flex gap-3 text-[10px] text-text-muted mb-2">
                                <span>Context: {model.contextWindow}</span>
                                <span>Output: {model.outputTokens}</span>
                            </div>
                            <div className="flex flex-wrap gap-1">
                                {model.features.map(feature => (
                                    <span
                                        key={feature}
                                        className="px-1.5 py-0.5 rounded bg-bg-tertiary text-[10px] text-text-secondary"
                                    >
                                        {feature}
                                    </span>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Quick Commands */}
            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border-primary">
                <button
                    onClick={() => copyToClipboard('claude --model opus', 'quick-opus')}
                    className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-accent-neon/20 text-accent-neon text-xs font-mono hover:bg-accent-neon/30 transition-all"
                >
                    {copied === 'quick-opus' ? <Check className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
                    Opus 4.6
                </button>
                <button
                    onClick={() => copyToClipboard('claude --model sonnet', 'quick-sonnet')}
                    className="flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-500/20 text-blue-400 text-xs font-mono hover:bg-blue-500/30 transition-all"
                >
                    {copied === 'quick-sonnet' ? <Check className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
                    Sonnet 4.5
                </button>
            </div>

            {/* Footer */}
            <div className="text-center text-[10px] text-text-muted pt-2">
                <p>Open terminal and paste command to switch models</p>
            </div>
        </div>
    );
}
