'use client';

import { useState, useCallback, useEffect, useMemo } from 'react';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { LAMPORTS_PER_SOL } from '@solana/web3.js';
import { getBagsTradingClient } from '@/lib/bags-trading';
import { bagsClient, BagsGraduation, getScoreTier, TIER_COLORS } from '@/lib/bags-api';
import { getGrokSentimentClient, TokenSentiment } from '@/lib/grok-sentiment';
import { useToast } from '@/components/ui/Toast';
import { useAlgoParams } from '@/components/features/AlgoConfig';
import {
    Crosshair,
    Zap,
    Search,
    TrendingUp,
    Shield,
    AlertTriangle,
    Clock,
    Target,
    Rocket,
    ArrowRight,
    CheckCircle,
    XCircle,
    Loader2,
    Settings2,
    History,
    RefreshCw,
    DollarSign,
    Percent,
    Activity
} from 'lucide-react';

// SOL and USDC mints
const SOL_MINT = 'So11111111111111111111111111111111111111112';

interface SnipeTarget {
    mint: string;
    symbol: string;
    name: string;
    score?: number;
    sentiment?: number;
    price?: number;
    liquidity?: number;
    source: 'manual' | 'graduation' | 'trending' | 'search';
}

interface SnipeHistory {
    id: string;
    mint: string;
    symbol: string;
    amountSol: number;
    entryPrice: number;
    timestamp: number;
    status: 'pending' | 'success' | 'failed';
    txSignature?: string;
    error?: string;
}

// Load history from localStorage
function loadSnipeHistory(): SnipeHistory[] {
    if (typeof window === 'undefined') return [];
    try {
        const stored = localStorage.getItem('jarvis_snipe_history');
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

function saveSnipeHistory(history: SnipeHistory[]) {
    if (typeof window !== 'undefined') {
        localStorage.setItem('jarvis_snipe_history', JSON.stringify(history.slice(0, 50))); // Keep last 50
    }
}

export function SnipePanel() {
    const { connection } = useConnection();
    const { publicKey, signTransaction, connected } = useWallet();
    const { success: toastSuccess, info: toastInfo } = useToast();
    const algoParams = useAlgoParams();

    // State
    const [searchQuery, setSearchQuery] = useState('');
    const [target, setTarget] = useState<SnipeTarget | null>(null);
    const [snipeAmount, setSnipeAmount] = useState('0.1');
    const [useJito, setUseJito] = useState(true);
    const [autoTP, setAutoTP] = useState(algoParams.params.defaultTP);
    const [autoSL, setAutoSL] = useState(algoParams.params.defaultSL);
    const [slippageBps, setSlippageBps] = useState(500); // 5%
    const [isExecuting, setIsExecuting] = useState(false);
    const [history, setHistory] = useState<SnipeHistory[]>([]);
    const [sentiment, setSentiment] = useState<TokenSentiment | null>(null);
    const [recentGraduations, setRecentGraduations] = useState<BagsGraduation[]>([]);
    const [showHistory, setShowHistory] = useState(false);
    const [balance, setBalance] = useState<number | null>(null);

    // Load history on mount
    useEffect(() => {
        setHistory(loadSnipeHistory());
    }, []);

    // Fetch balance
    useEffect(() => {
        if (publicKey && connection) {
            connection.getBalance(publicKey).then(bal => {
                setBalance(bal / LAMPORTS_PER_SOL);
            });
        }
    }, [publicKey, connection]);

    // Fetch recent graduations for quick snipe
    useEffect(() => {
        const fetchGraduations = async () => {
            const grads = await bagsClient.getGraduations(10);
            setRecentGraduations(grads.filter(g => g.score >= algoParams.params.graduationScoreCutoff));
        };
        fetchGraduations();
        const interval = setInterval(fetchGraduations, 30000);
        return () => clearInterval(interval);
    }, [algoParams.params.graduationScoreCutoff]);

    // Handle search/address input
    const handleSearch = useCallback(async () => {
        if (!searchQuery.trim()) return;

        const query = searchQuery.trim();

        // Check if it's a valid Solana address (base58, ~44 chars)
        const isAddress = /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(query);

        if (isAddress) {
            // Fetch token info
            const tokenInfo = await bagsClient.getTokenInfo(query);
            if (tokenInfo) {
                setTarget({
                    mint: query,
                    symbol: tokenInfo.symbol,
                    name: tokenInfo.name,
                    price: tokenInfo.price_usd,
                    liquidity: tokenInfo.liquidity,
                    source: 'manual',
                });

                // Fetch sentiment
                const grok = getGrokSentimentClient();
                const sentimentResult = await grok.analyzeSingle(query, tokenInfo.symbol, {
                    price: tokenInfo.price_usd,
                    volume24h: tokenInfo.volume_24h,
                    liquidity: tokenInfo.liquidity,
                });
                setSentiment(sentimentResult);
            } else {
                // Still set target with address only
                setTarget({
                    mint: query,
                    symbol: 'UNKNOWN',
                    name: 'Unknown Token',
                    source: 'manual',
                });
            }
        } else {
            // Search by symbol/name (would need a search endpoint)
            // For now, show error
            toastInfo('Search by name coming soon — paste a contract address instead');
        }
    }, [searchQuery]);

    // Select graduation for snipe
    const selectGraduation = useCallback(async (grad: BagsGraduation) => {
        setTarget({
            mint: grad.mint,
            symbol: grad.symbol,
            name: grad.name,
            score: grad.score,
            price: grad.price_usd,
            liquidity: grad.market_cap,
            source: 'graduation',
        });

        // Fetch sentiment
        const grok = getGrokSentimentClient();
        const sentimentResult = await grok.analyzeSingle(grad.mint, grad.symbol, {
            price: grad.price_usd,
        });
        setSentiment(sentimentResult);
    }, []);

    // Execute snipe
    const executeSnipe = useCallback(async () => {
        if (!target || !publicKey || !signTransaction || !connected) {
            console.error('Missing requirements for snipe');
            return;
        }

        const amountNum = parseFloat(snipeAmount);
        if (isNaN(amountNum) || amountNum <= 0) {
            console.error('Invalid snipe amount');
            return;
        }

        setIsExecuting(true);

        // Create history entry
        const snipeEntry: SnipeHistory = {
            id: `snipe_${Date.now()}`,
            mint: target.mint,
            symbol: target.symbol,
            amountSol: amountNum,
            entryPrice: target.price || 0,
            timestamp: Date.now(),
            status: 'pending',
        };

        setHistory(prev => [snipeEntry, ...prev]);

        try {
            const tradingClient = getBagsTradingClient(connection);
            const result = await tradingClient.executeSwap(
                publicKey.toBase58(),
                SOL_MINT,
                target.mint,
                amountNum,
                slippageBps,
                signTransaction,
                useJito
            );

            // Update history with success
            setHistory(prev => {
                const updated = prev.map(h =>
                    h.id === snipeEntry.id
                        ? { ...h, status: 'success' as const, txSignature: result.signature }
                        : h
                );
                saveSnipeHistory(updated);
                return updated;
            });

            toastSuccess('Snipe executed!', result.signature);

        } catch (error) {
            // Update history with failure
            setHistory(prev => {
                const updated = prev.map(h =>
                    h.id === snipeEntry.id
                        ? { ...h, status: 'failed' as const, error: String(error) }
                        : h
                );
                saveSnipeHistory(updated);
                return updated;
            });

            console.error('Snipe failed:', error);
        } finally {
            setIsExecuting(false);
        }
    }, [target, publicKey, signTransaction, connected, snipeAmount, slippageBps, useJito, connection]);

    // Calculate position metrics
    const positionMetrics = useMemo(() => {
        const amountNum = parseFloat(snipeAmount) || 0;
        const tpPrice = target?.price ? target.price * (1 + autoTP / 100) : 0;
        const slPrice = target?.price ? target.price * (1 - autoSL / 100) : 0;
        const maxPositionSol = balance ? balance * (algoParams.params.maxPositionPct / 100) : 0;

        return {
            amount: amountNum,
            tpPrice,
            slPrice,
            maxPosition: maxPositionSol,
            withinLimits: amountNum <= maxPositionSol,
        };
    }, [snipeAmount, target, autoTP, autoSL, balance, algoParams.params.maxPositionPct]);

    // Score tier colors for target
    const tierInfo = target?.score ? {
        tier: getScoreTier(target.score),
        colors: TIER_COLORS[getScoreTier(target.score)],
    } : null;

    return (
        <div className="card-glass overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-border-primary/30">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-accent-neon/20 flex items-center justify-center">
                            <Crosshair className="w-5 h-5 text-accent-neon" />
                        </div>
                        <div>
                            <h3 className="font-display font-bold text-lg text-text-primary">
                                Token Sniper
                            </h3>
                            <p className="text-xs text-text-muted">
                                Fast execution with MEV protection
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* History Toggle */}
                        <button
                            onClick={() => setShowHistory(!showHistory)}
                            className={`
                                p-2 rounded-lg transition-colors
                                ${showHistory ? 'bg-accent-neon/20 text-accent-neon' : 'hover:bg-bg-secondary/50 text-text-muted'}
                            `}
                        >
                            <History className="w-4 h-4" />
                        </button>

                        {/* Jito Toggle */}
                        <button
                            onClick={() => setUseJito(!useJito)}
                            className={`
                                flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-all
                                ${useJito
                                    ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30'
                                    : 'bg-bg-secondary/50 text-text-muted border border-border-primary/30'}
                            `}
                        >
                            <Shield className="w-3 h-3" />
                            JITO
                        </button>
                    </div>
                </div>
            </div>

            {/* Content */}
            <div className="p-4">
                {showHistory ? (
                    // History View
                    <div className="space-y-2 max-h-[400px] overflow-y-auto">
                        <div className="flex items-center justify-between mb-3">
                            <h4 className="text-sm font-bold text-text-primary">Snipe History</h4>
                            <button
                                onClick={() => {
                                    setHistory([]);
                                    saveSnipeHistory([]);
                                }}
                                className="text-xs text-accent-danger hover:underline"
                            >
                                Clear
                            </button>
                        </div>
                        {history.length === 0 ? (
                            <p className="text-sm text-text-muted text-center py-8">No snipes yet</p>
                        ) : (
                            history.map((h) => (
                                <div
                                    key={h.id}
                                    className={`
                                        p-3 rounded-lg border flex items-center justify-between
                                        ${h.status === 'success'
                                            ? 'bg-accent-success/10 border-accent-success/30'
                                            : h.status === 'failed'
                                                ? 'bg-accent-danger/10 border-accent-danger/30'
                                                : 'bg-accent-warning/10 border-accent-warning/30'}
                                    `}
                                >
                                    <div>
                                        <p className="font-mono text-sm text-text-primary">{h.symbol}</p>
                                        <p className="text-xs text-text-muted">
                                            {h.amountSol} SOL • {new Date(h.timestamp).toLocaleTimeString()}
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {h.status === 'success' ? (
                                            <CheckCircle className="w-4 h-4 text-accent-success" />
                                        ) : h.status === 'failed' ? (
                                            <XCircle className="w-4 h-4 text-accent-danger" />
                                        ) : (
                                            <Loader2 className="w-4 h-4 text-text-muted animate-spin" />
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                ) : (
                    // Snipe View
                    <div className="space-y-4">
                        {/* Search / Address Input */}
                        <div className="relative">
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                                placeholder="Paste token address or search..."
                                className="w-full px-4 py-3 pl-10 rounded-lg bg-bg-secondary/50 border border-border-primary/30 text-text-primary placeholder-text-muted focus:border-accent-neon/50 focus:outline-none font-mono text-sm"
                            />
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                            <button
                                onClick={handleSearch}
                                className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 rounded bg-accent-neon/20 text-accent-neon text-xs font-bold hover:bg-accent-neon/30 transition-colors"
                            >
                                <ArrowRight className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Quick Snipe: Recent Graduations */}
                        {recentGraduations.length > 0 && !target && (
                            <div>
                                <p className="text-xs text-text-muted mb-2 flex items-center gap-1">
                                    <Rocket className="w-3 h-3" />
                                    QUICK SNIPE - Recent Graduations
                                </p>
                                <div className="flex flex-wrap gap-2">
                                    {recentGraduations.slice(0, 6).map((grad) => {
                                        const tier = getScoreTier(grad.score);
                                        const colors = TIER_COLORS[tier];
                                        return (
                                            <button
                                                key={grad.mint}
                                                onClick={() => selectGraduation(grad)}
                                                className={`
                                                    px-3 py-1.5 rounded-lg text-xs font-mono flex items-center gap-2 transition-all
                                                    ${colors.bg} ${colors.text} border ${colors.border}
                                                    hover:scale-105
                                                `}
                                            >
                                                <span className="font-bold">{grad.symbol}</span>
                                                <span className="opacity-60">{grad.score}</span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        )}

                        {/* Target Display */}
                        {target && (
                            <div className={`
                                p-4 rounded-xl border
                                ${tierInfo ? `${tierInfo.colors.bg} ${tierInfo.colors.border}` : 'bg-bg-secondary/50 border-border-primary/30'}
                            `}>
                                <div className="flex items-center justify-between mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-full bg-bg-secondary flex items-center justify-center">
                                            <span className="text-lg font-bold">{target.symbol[0]}</span>
                                        </div>
                                        <div>
                                            <p className="font-display font-bold text-text-primary">{target.symbol}</p>
                                            <p className="text-xs text-text-muted">{target.name}</p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => {
                                            setTarget(null);
                                            setSentiment(null);
                                            setSearchQuery('');
                                        }}
                                        className="p-1 rounded hover:bg-bg-secondary/50"
                                    >
                                        <XCircle className="w-4 h-4 text-text-muted" />
                                    </button>
                                </div>

                                {/* Metrics */}
                                <div className="grid grid-cols-3 gap-2 text-center">
                                    {target.score !== undefined && (
                                        <div className="p-2 rounded bg-bg-secondary/30">
                                            <p className="text-[10px] text-text-muted">SCORE</p>
                                            <p className={`font-mono font-bold ${tierInfo?.colors.text}`}>{target.score}</p>
                                        </div>
                                    )}
                                    {sentiment && (
                                        <div className="p-2 rounded bg-bg-secondary/30">
                                            <p className="text-[10px] text-text-muted">SENTIMENT</p>
                                            <p className={`font-mono font-bold ${sentiment.score >= 60 ? 'text-accent-success' : sentiment.score >= 40 ? 'text-text-muted' : 'text-accent-danger'}`}>
                                                {sentiment.score}
                                            </p>
                                        </div>
                                    )}
                                    {target.price && (
                                        <div className="p-2 rounded bg-bg-secondary/30">
                                            <p className="text-[10px] text-text-muted">PRICE</p>
                                            <p className="font-mono font-bold text-text-primary">${target.price.toFixed(6)}</p>
                                        </div>
                                    )}
                                </div>

                                {/* Warning if low score/sentiment */}
                                {((target.score && target.score < algoParams.params.graduationScoreCutoff) ||
                                    (sentiment && sentiment.score < algoParams.params.sentimentBuyThreshold)) && (
                                        <div className="mt-3 p-2 rounded bg-accent-warning/10 border border-accent-warning/30 flex items-center gap-2">
                                            <AlertTriangle className="w-4 h-4 text-text-muted" />
                                            <p className="text-xs text-text-muted">
                                                Below algo thresholds - proceed with caution
                                            </p>
                                        </div>
                                    )}
                            </div>
                        )}

                        {/* Snipe Configuration */}
                        {target && (
                            <div className="space-y-3">
                                {/* Amount */}
                                <div>
                                    <div className="flex justify-between text-xs mb-1">
                                        <span className="text-text-muted">Amount (SOL)</span>
                                        <span className="text-text-muted">
                                            Balance: {balance?.toFixed(3) || '...'} SOL
                                        </span>
                                    </div>
                                    <div className="relative">
                                        <input
                                            type="number"
                                            value={snipeAmount}
                                            onChange={(e) => setSnipeAmount(e.target.value)}
                                            step="0.1"
                                            min="0.01"
                                            className="w-full px-4 py-2 rounded-lg bg-bg-secondary/50 border border-border-primary/30 text-text-primary focus:border-accent-neon/50 focus:outline-none font-mono"
                                        />
                                        <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
                                            {[0.1, 0.5, 1].map(amt => (
                                                <button
                                                    key={amt}
                                                    onClick={() => setSnipeAmount(String(amt))}
                                                    className="px-2 py-0.5 rounded bg-bg-secondary text-text-muted text-xs hover:bg-accent-neon/20 hover:text-accent-neon"
                                                >
                                                    {amt}
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    {!positionMetrics.withinLimits && (
                                        <p className="text-xs text-accent-danger mt-1">
                                            Exceeds max position ({algoParams.params.maxPositionPct}% = {positionMetrics.maxPosition.toFixed(2)} SOL)
                                        </p>
                                    )}
                                </div>

                                {/* TP/SL Quick Settings */}
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <div className="flex justify-between text-xs mb-1">
                                            <span className="text-accent-success">Take Profit</span>
                                            <span className="font-mono text-accent-success">+{autoTP}%</span>
                                        </div>
                                        <div className="flex gap-1">
                                            {[20, 50, 100, 200].map(pct => (
                                                <button
                                                    key={pct}
                                                    onClick={() => setAutoTP(pct)}
                                                    className={`
                                                        flex-1 py-1.5 rounded text-xs font-mono transition-all
                                                        ${autoTP === pct
                                                            ? 'bg-accent-success/20 text-accent-success border border-accent-success/30'
                                                            : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary'}
                                                    `}
                                                >
                                                    {pct}%
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <div className="flex justify-between text-xs mb-1">
                                            <span className="text-accent-danger">Stop Loss</span>
                                            <span className="font-mono text-accent-danger">-{autoSL}%</span>
                                        </div>
                                        <div className="flex gap-1">
                                            {[10, 20, 30, 50].map(pct => (
                                                <button
                                                    key={pct}
                                                    onClick={() => setAutoSL(pct)}
                                                    className={`
                                                        flex-1 py-1.5 rounded text-xs font-mono transition-all
                                                        ${autoSL === pct
                                                            ? 'bg-accent-danger/20 text-accent-danger border border-accent-danger/30'
                                                            : 'bg-bg-secondary/50 text-text-muted hover:bg-bg-secondary'}
                                                    `}
                                                >
                                                    {pct}%
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                {/* Execute Button */}
                                <button
                                    onClick={executeSnipe}
                                    disabled={isExecuting || !connected || !positionMetrics.withinLimits}
                                    className={`
                                        w-full py-4 rounded-xl font-display font-bold text-lg flex items-center justify-center gap-2 transition-all
                                        ${isExecuting || !connected || !positionMetrics.withinLimits
                                            ? 'bg-bg-secondary/50 text-text-muted cursor-not-allowed'
                                            : 'bg-accent-neon text-black hover:brightness-110 hover:scale-[1.02]'}
                                    `}
                                >
                                    {isExecuting ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            EXECUTING...
                                        </>
                                    ) : !connected ? (
                                        <>
                                            <Shield className="w-5 h-5" />
                                            CONNECT WALLET
                                        </>
                                    ) : (
                                        <>
                                            <Zap className="w-5 h-5" />
                                            SNIPE {snipeAmount} SOL
                                        </>
                                    )}
                                </button>

                                {/* Info */}
                                <div className="flex items-center justify-center gap-4 text-[10px] text-text-muted">
                                    <span className="flex items-center gap-1">
                                        <Activity className="w-3 h-3" />
                                        Slippage: {slippageBps / 100}%
                                    </span>
                                    {useJito && (
                                        <span className="flex items-center gap-1 text-accent-neon">
                                            <Shield className="w-3 h-3" />
                                            Jito MEV Protection
                                        </span>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* No target selected */}
                        {!target && recentGraduations.length === 0 && (
                            <div className="text-center py-8">
                                <Target className="w-12 h-12 text-text-muted mx-auto mb-3 opacity-30" />
                                <p className="text-text-muted">
                                    Paste a token address or wait for graduations
                                </p>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

export default SnipePanel;
