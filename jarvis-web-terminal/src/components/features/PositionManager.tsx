'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { LAMPORTS_PER_SOL } from '@solana/web3.js';
import { getBagsTradingClient } from '@/lib/bags-trading';
import { useToast } from '@/components/ui/Toast';
import { bagsClient } from '@/lib/bags-api';
import { getGrokSentimentClient, TokenSentiment } from '@/lib/grok-sentiment';
import {
    Briefcase,
    TrendingUp,
    TrendingDown,
    Percent,
    DollarSign,
    X,
    ChevronDown,
    ChevronUp,
    BarChart3,
    Shield,
    AlertTriangle,
    Settings2,
    Trash2,
    RefreshCw,
    Target,
    Activity,
    Zap,
    ArrowUpRight,
    ArrowDownRight,
    Clock,
    CheckCircle,
    Loader2
} from 'lucide-react';

// SOL and USDC mints
const SOL_MINT = 'So11111111111111111111111111111111111111112';

interface Position {
    id: string;
    mint: string;
    symbol: string;
    name: string;
    entryPrice: number;
    currentPrice: number;
    quantity: number;
    entrySol: number;
    entryTimestamp: number;
    tp: number;
    sl: number;
    sentiment: number;
    pnl: number;
    pnlPercent: number;
}

interface BulkAction {
    type: 'close_all' | 'set_tp' | 'set_sl';
    value?: number;
}

// localStorage key
const POSITIONS_KEY = 'jarvis_positions';

// Load positions from localStorage
function loadPositions(): Position[] {
    if (typeof window === 'undefined') return [];
    try {
        const stored = localStorage.getItem(POSITIONS_KEY);
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

// Save positions to localStorage
function savePositions(positions: Position[]) {
    if (typeof window !== 'undefined') {
        localStorage.setItem(POSITIONS_KEY, JSON.stringify(positions));
    }
}

export function PositionManager() {
    const { connection } = useConnection();
    const { publicKey, signTransaction, connected } = useWallet();
    const { success: toastSuccess } = useToast();

    // State
    const [positions, setPositions] = useState<Position[]>([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [expandedId, setExpandedId] = useState<string | null>(null);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [showBulkActions, setShowBulkActions] = useState(false);
    const [executingAction, setExecutingAction] = useState<string | null>(null);
    const [sortBy, setSortBy] = useState<'pnl' | 'value' | 'time'>('pnl');
    const [filterProfit, setFilterProfit] = useState<'all' | 'profit' | 'loss'>('all');

    // Load positions on mount
    useEffect(() => {
        const loaded = loadPositions();
        setPositions(loaded);
        setLoading(false);
    }, []);

    // Refresh prices periodically
    useEffect(() => {
        const refreshPrices = async () => {
            if (positions.length === 0) return;

            const updated = await Promise.all(
                positions.map(async (pos) => {
                    const tokenInfo = await bagsClient.getTokenInfo(pos.mint);
                    if (tokenInfo) {
                        const currentPrice = tokenInfo.price_usd;
                        const pnl = (currentPrice - pos.entryPrice) * pos.quantity;
                        const pnlPercent = ((currentPrice - pos.entryPrice) / pos.entryPrice) * 100;
                        return { ...pos, currentPrice, pnl, pnlPercent };
                    }
                    return pos;
                })
            );

            setPositions(updated);
            savePositions(updated);
        };

        refreshPrices();
        const interval = setInterval(refreshPrices, 30000); // 30s refresh
        return () => clearInterval(interval);
    }, [positions.length]);

    // Manual refresh
    const handleRefresh = useCallback(async () => {
        setRefreshing(true);
        // Trigger price update
        const updated = await Promise.all(
            positions.map(async (pos) => {
                const tokenInfo = await bagsClient.getTokenInfo(pos.mint);
                if (tokenInfo) {
                    const currentPrice = tokenInfo.price_usd;
                    const pnl = (currentPrice - pos.entryPrice) * pos.quantity;
                    const pnlPercent = ((currentPrice - pos.entryPrice) / pos.entryPrice) * 100;
                    return { ...pos, currentPrice, pnl, pnlPercent };
                }
                return pos;
            })
        );
        setPositions(updated);
        savePositions(updated);
        setRefreshing(false);
    }, [positions]);

    // Sell position
    const sellPosition = useCallback(async (positionId: string, percent: number) => {
        if (!publicKey || !signTransaction || !connected) return;

        const position = positions.find(p => p.id === positionId);
        if (!position) return;

        setExecutingAction(positionId);

        try {
            const sellQuantity = position.quantity * (percent / 100);
            const tradingClient = getBagsTradingClient(connection);

            // Convert quantity to SOL value estimate
            const sellValueSol = (sellQuantity * position.currentPrice) / 150; // Rough SOL/USD

            const result = await tradingClient.executeSwap(
                publicKey.toBase58(),
                position.mint,
                SOL_MINT,
                sellValueSol,
                500, // 5% slippage
                signTransaction,
                true // Jito
            );

            // Update position
            if (percent >= 100) {
                // Remove position
                setPositions(prev => {
                    const updated = prev.filter(p => p.id !== positionId);
                    savePositions(updated);
                    return updated;
                });
            } else {
                // Reduce quantity
                setPositions(prev => {
                    const updated = prev.map(p =>
                        p.id === positionId
                            ? { ...p, quantity: p.quantity * (1 - percent / 100) }
                            : p
                    );
                    savePositions(updated);
                    return updated;
                });
            }

            toastSuccess('Sell executed!', result.txHash);
        } catch (error) {
            console.error('Sell failed:', error);
        } finally {
            setExecutingAction(null);
        }
    }, [publicKey, signTransaction, connected, positions, connection]);

    // Bulk close all
    const closeAllPositions = useCallback(async () => {
        if (!connected) return;

        for (const pos of positions) {
            await sellPosition(pos.id, 100);
        }
    }, [positions, sellPosition, connected]);

    // Bulk set TP/SL
    const bulkSetTPSL = useCallback((type: 'tp' | 'sl', value: number) => {
        const idsToUpdate = selectedIds.size > 0 ? selectedIds : new Set(positions.map(p => p.id));

        setPositions(prev => {
            const updated = prev.map(p =>
                idsToUpdate.has(p.id)
                    ? { ...p, [type]: value }
                    : p
            );
            savePositions(updated);
            return updated;
        });
    }, [selectedIds, positions]);

    // Toggle selection
    const toggleSelection = useCallback((id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) {
                next.delete(id);
            } else {
                next.add(id);
            }
            return next;
        });
    }, []);

    // Select all
    const selectAll = useCallback(() => {
        if (selectedIds.size === positions.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(positions.map(p => p.id)));
        }
    }, [selectedIds.size, positions]);

    // Sorted and filtered positions
    const displayPositions = useMemo(() => {
        let filtered = positions;

        // Filter
        if (filterProfit === 'profit') {
            filtered = filtered.filter(p => p.pnlPercent >= 0);
        } else if (filterProfit === 'loss') {
            filtered = filtered.filter(p => p.pnlPercent < 0);
        }

        // Sort
        return filtered.sort((a, b) => {
            switch (sortBy) {
                case 'pnl':
                    return b.pnlPercent - a.pnlPercent;
                case 'value':
                    return (b.quantity * b.currentPrice) - (a.quantity * a.currentPrice);
                case 'time':
                    return b.entryTimestamp - a.entryTimestamp;
                default:
                    return 0;
            }
        });
    }, [positions, sortBy, filterProfit]);

    // Portfolio stats
    const stats = useMemo(() => {
        const totalValue = positions.reduce((sum, p) => sum + p.quantity * p.currentPrice, 0);
        const totalPnl = positions.reduce((sum, p) => sum + p.pnl, 0);
        const winners = positions.filter(p => p.pnlPercent > 0).length;
        const losers = positions.filter(p => p.pnlPercent < 0).length;
        const avgPnl = positions.length > 0
            ? positions.reduce((sum, p) => sum + p.pnlPercent, 0) / positions.length
            : 0;

        return { totalValue, totalPnl, winners, losers, avgPnl };
    }, [positions]);

    return (
        <div className="card-glass overflow-hidden">
            {/* Header */}
            <div className="p-4 border-b border-theme-border/30">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-theme-cyan/20 flex items-center justify-center">
                            <Briefcase className="w-5 h-5 text-theme-cyan" />
                        </div>
                        <div>
                            <h3 className="font-display font-bold text-lg text-text-primary">
                                Positions
                            </h3>
                            <p className="text-xs text-text-muted">
                                {positions.length} open • ${stats.totalValue.toFixed(2)} value
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Refresh */}
                        <button
                            onClick={handleRefresh}
                            disabled={refreshing}
                            className="p-2 rounded-lg hover:bg-theme-dark/50 transition-colors"
                        >
                            <RefreshCw className={`w-4 h-4 text-text-muted ${refreshing ? 'animate-spin' : ''}`} />
                        </button>

                        {/* Bulk Actions Toggle */}
                        <button
                            onClick={() => setShowBulkActions(!showBulkActions)}
                            className={`
                                p-2 rounded-lg transition-colors
                                ${showBulkActions ? 'bg-accent-neon/20 text-accent-neon' : 'hover:bg-theme-dark/50 text-text-muted'}
                            `}
                        >
                            <Settings2 className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Portfolio Stats */}
                <div className="grid grid-cols-4 gap-2 mt-4">
                    <div className="p-2 rounded-lg bg-theme-dark/30 text-center">
                        <p className="text-[10px] text-text-muted">TOTAL P&L</p>
                        <p className={`font-mono font-bold ${stats.totalPnl >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                            {stats.totalPnl >= 0 ? '+' : ''}{stats.totalPnl.toFixed(2)}
                        </p>
                    </div>
                    <div className="p-2 rounded-lg bg-theme-dark/30 text-center">
                        <p className="text-[10px] text-text-muted">AVG P&L</p>
                        <p className={`font-mono font-bold ${stats.avgPnl >= 0 ? 'text-accent-success' : 'text-accent-danger'}`}>
                            {stats.avgPnl >= 0 ? '+' : ''}{stats.avgPnl.toFixed(1)}%
                        </p>
                    </div>
                    <div className="p-2 rounded-lg bg-theme-dark/30 text-center">
                        <p className="text-[10px] text-text-muted">WINNERS</p>
                        <p className="font-mono font-bold text-accent-success">{stats.winners}</p>
                    </div>
                    <div className="p-2 rounded-lg bg-theme-dark/30 text-center">
                        <p className="text-[10px] text-text-muted">LOSERS</p>
                        <p className="font-mono font-bold text-accent-danger">{stats.losers}</p>
                    </div>
                </div>

                {/* Bulk Actions Panel */}
                {showBulkActions && (
                    <div className="mt-4 p-3 rounded-lg bg-theme-dark/50 border border-theme-border/30">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={selectAll}
                                    className="text-xs text-accent-neon hover:underline"
                                >
                                    {selectedIds.size === positions.length ? 'Deselect All' : 'Select All'}
                                </button>
                                <span className="text-xs text-text-muted">
                                    ({selectedIds.size} selected)
                                </span>
                            </div>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {/* Bulk TP */}
                            {[20, 50, 100].map(pct => (
                                <button
                                    key={`tp-${pct}`}
                                    onClick={() => bulkSetTPSL('tp', pct)}
                                    className="px-3 py-1.5 rounded text-xs font-mono bg-accent-success/10 text-accent-success border border-accent-success/30 hover:bg-accent-success/20"
                                >
                                    Set TP +{pct}%
                                </button>
                            ))}

                            {/* Bulk SL */}
                            {[10, 20, 30].map(pct => (
                                <button
                                    key={`sl-${pct}`}
                                    onClick={() => bulkSetTPSL('sl', pct)}
                                    className="px-3 py-1.5 rounded text-xs font-mono bg-accent-danger/10 text-accent-danger border border-accent-danger/30 hover:bg-accent-danger/20"
                                >
                                    Set SL -{pct}%
                                </button>
                            ))}

                            {/* Close All */}
                            <button
                                onClick={closeAllPositions}
                                disabled={!connected}
                                className="px-3 py-1.5 rounded text-xs font-mono bg-red-500/10 text-red-400 border border-red-500/30 hover:bg-red-500/20 flex items-center gap-1"
                            >
                                <Trash2 className="w-3 h-3" />
                                Close All
                            </button>
                        </div>
                    </div>
                )}

                {/* Filters */}
                <div className="flex items-center justify-between mt-4">
                    <div className="flex gap-1">
                        {(['all', 'profit', 'loss'] as const).map(filter => (
                            <button
                                key={filter}
                                onClick={() => setFilterProfit(filter)}
                                className={`
                                    px-3 py-1 rounded text-xs font-mono transition-all
                                    ${filterProfit === filter
                                        ? 'bg-accent-neon/20 text-accent-neon'
                                        : 'bg-theme-dark/30 text-text-muted hover:bg-theme-dark/50'}
                                `}
                            >
                                {filter.charAt(0).toUpperCase() + filter.slice(1)}
                            </button>
                        ))}
                    </div>

                    <div className="flex gap-1">
                        {(['pnl', 'value', 'time'] as const).map(sort => (
                            <button
                                key={sort}
                                onClick={() => setSortBy(sort)}
                                className={`
                                    px-3 py-1 rounded text-xs font-mono transition-all
                                    ${sortBy === sort
                                        ? 'bg-theme-cyan/20 text-theme-cyan'
                                        : 'bg-theme-dark/30 text-text-muted hover:bg-theme-dark/50'}
                                `}
                            >
                                {sort.toUpperCase()}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* Positions List */}
            <div className="max-h-[500px] overflow-y-auto">
                {loading ? (
                    <div className="text-center py-12">
                        <Loader2 className="w-8 h-8 text-accent-neon animate-spin mx-auto mb-2" />
                        <p className="text-sm text-text-muted">Loading positions...</p>
                    </div>
                ) : displayPositions.length === 0 ? (
                    <div className="text-center py-12">
                        <Briefcase className="w-12 h-12 text-text-muted mx-auto mb-3 opacity-30" />
                        <p className="text-text-muted">No open positions</p>
                        <p className="text-xs text-text-muted mt-1">Execute a trade to get started</p>
                    </div>
                ) : (
                    displayPositions.map((pos) => (
                        <PositionCard
                            key={pos.id}
                            position={pos}
                            expanded={expandedId === pos.id}
                            selected={selectedIds.has(pos.id)}
                            executing={executingAction === pos.id}
                            onToggleExpand={() => setExpandedId(expandedId === pos.id ? null : pos.id)}
                            onToggleSelect={() => toggleSelection(pos.id)}
                            onSell={(pct) => sellPosition(pos.id, pct)}
                            onUpdateTPSL={(tp, sl) => {
                                setPositions(prev => {
                                    const updated = prev.map(p =>
                                        p.id === pos.id ? { ...p, tp, sl } : p
                                    );
                                    savePositions(updated);
                                    return updated;
                                });
                            }}
                            connected={connected}
                        />
                    ))
                )}
            </div>
        </div>
    );
}

interface PositionCardProps {
    position: Position;
    expanded: boolean;
    selected: boolean;
    executing: boolean;
    onToggleExpand: () => void;
    onToggleSelect: () => void;
    onSell: (percent: number) => void;
    onUpdateTPSL: (tp: number, sl: number) => void;
    connected: boolean;
}

function PositionCard({
    position,
    expanded,
    selected,
    executing,
    onToggleExpand,
    onToggleSelect,
    onSell,
    onUpdateTPSL,
    connected
}: PositionCardProps) {
    const isProfit = position.pnlPercent >= 0;
    const valueUsd = position.quantity * position.currentPrice;
    const timeSinceEntry = Date.now() - position.entryTimestamp;
    const hoursHeld = Math.floor(timeSinceEntry / (1000 * 60 * 60));

    // TP/SL status
    const tpReached = position.pnlPercent >= position.tp;
    const slReached = position.pnlPercent <= -position.sl;

    return (
        <div className={`
            border-b border-theme-border/20 transition-all
            ${selected ? 'bg-accent-neon/5' : 'hover:bg-theme-dark/20'}
            ${tpReached ? 'bg-accent-success/5' : ''}
            ${slReached ? 'bg-accent-danger/5' : ''}
        `}>
            {/* Main Row */}
            <div
                className="p-4 flex items-center gap-3 cursor-pointer"
                onClick={onToggleExpand}
            >
                {/* Selection Checkbox */}
                <button
                    onClick={(e) => {
                        e.stopPropagation();
                        onToggleSelect();
                    }}
                    className={`
                        w-5 h-5 rounded border-2 flex items-center justify-center transition-all
                        ${selected
                            ? 'bg-accent-neon border-accent-neon'
                            : 'border-theme-border hover:border-accent-neon/50'}
                    `}
                >
                    {selected && <CheckCircle className="w-3 h-3 text-black" />}
                </button>

                {/* Token Info */}
                <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-theme-dark flex items-center justify-center shrink-0">
                        <span className="font-bold">{position.symbol[0]}</span>
                    </div>
                    <div className="min-w-0">
                        <p className="font-display font-bold text-text-primary truncate">{position.symbol}</p>
                        <p className="text-xs text-text-muted flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {hoursHeld}h
                        </p>
                    </div>
                </div>

                {/* Value */}
                <div className="text-right">
                    <p className="font-mono font-bold text-text-primary">${valueUsd.toFixed(2)}</p>
                    <p className="text-xs text-text-muted">{position.quantity.toFixed(4)}</p>
                </div>

                {/* P&L */}
                <div className="text-right w-24">
                    <p className={`font-mono font-bold ${isProfit ? 'text-accent-success' : 'text-accent-danger'}`}>
                        {isProfit ? '+' : ''}{position.pnlPercent.toFixed(2)}%
                    </p>
                    <p className={`text-xs ${isProfit ? 'text-accent-success/70' : 'text-accent-danger/70'}`}>
                        {isProfit ? '+' : ''}${position.pnl.toFixed(2)}
                    </p>
                </div>

                {/* Alerts */}
                <div className="flex items-center gap-1 w-16 justify-end">
                    {tpReached && (
                        <span className="w-6 h-6 rounded-full bg-accent-success/20 flex items-center justify-center" title="TP Reached">
                            <ArrowUpRight className="w-3 h-3 text-accent-success" />
                        </span>
                    )}
                    {slReached && (
                        <span className="w-6 h-6 rounded-full bg-accent-danger/20 flex items-center justify-center" title="SL Reached">
                            <ArrowDownRight className="w-3 h-3 text-accent-danger" />
                        </span>
                    )}
                </div>

                {/* Expand */}
                {expanded ? (
                    <ChevronUp className="w-4 h-4 text-text-muted" />
                ) : (
                    <ChevronDown className="w-4 h-4 text-text-muted" />
                )}
            </div>

            {/* Expanded Details */}
            {expanded && (
                <div className="px-4 pb-4 space-y-3">
                    {/* Entry vs Current */}
                    <div className="grid grid-cols-2 gap-3">
                        <div className="p-2 rounded bg-theme-dark/30">
                            <p className="text-[10px] text-text-muted">ENTRY</p>
                            <p className="font-mono text-sm text-text-primary">${position.entryPrice.toFixed(6)}</p>
                        </div>
                        <div className="p-2 rounded bg-theme-dark/30">
                            <p className="text-[10px] text-text-muted">CURRENT</p>
                            <p className="font-mono text-sm text-text-primary">${position.currentPrice.toFixed(6)}</p>
                        </div>
                    </div>

                    {/* TP/SL Settings */}
                    <div className="grid grid-cols-2 gap-3">
                        <div className="p-2 rounded bg-accent-success/10 border border-accent-success/30">
                            <p className="text-[10px] text-accent-success">TAKE PROFIT</p>
                            <div className="flex items-center gap-2 mt-1">
                                <input
                                    type="number"
                                    value={position.tp}
                                    onChange={(e) => onUpdateTPSL(parseInt(e.target.value) || 0, position.sl)}
                                    className="w-16 px-2 py-1 rounded bg-theme-dark/50 text-accent-success font-mono text-sm border-none outline-none"
                                />
                                <span className="text-xs text-accent-success">%</span>
                                {tpReached && <CheckCircle className="w-4 h-4 text-accent-success" />}
                            </div>
                        </div>
                        <div className="p-2 rounded bg-accent-danger/10 border border-accent-danger/30">
                            <p className="text-[10px] text-accent-danger">STOP LOSS</p>
                            <div className="flex items-center gap-2 mt-1">
                                <input
                                    type="number"
                                    value={position.sl}
                                    onChange={(e) => onUpdateTPSL(position.tp, parseInt(e.target.value) || 0)}
                                    className="w-16 px-2 py-1 rounded bg-theme-dark/50 text-accent-danger font-mono text-sm border-none outline-none"
                                />
                                <span className="text-xs text-accent-danger">%</span>
                                {slReached && <AlertTriangle className="w-4 h-4 text-accent-danger" />}
                            </div>
                        </div>
                    </div>

                    {/* Sentiment at Entry */}
                    <div className="flex items-center justify-between p-2 rounded bg-theme-dark/30">
                        <span className="text-xs text-text-muted">Entry Sentiment</span>
                        <span className={`font-mono text-sm ${position.sentiment >= 60 ? 'text-accent-success' : position.sentiment >= 40 ? 'text-yellow-400' : 'text-accent-danger'}`}>
                            {position.sentiment}
                        </span>
                    </div>

                    {/* Sell Actions */}
                    <div className="flex gap-2">
                        {[25, 50, 100].map(pct => (
                            <button
                                key={pct}
                                onClick={() => onSell(pct)}
                                disabled={!connected || executing}
                                className={`
                                    flex-1 py-2 rounded-lg font-mono text-sm font-bold transition-all
                                    ${executing
                                        ? 'bg-theme-dark/50 text-text-muted'
                                        : pct === 100
                                            ? 'bg-accent-danger/20 text-accent-danger hover:bg-accent-danger/30'
                                            : 'bg-theme-dark/50 text-text-primary hover:bg-theme-dark'}
                                `}
                            >
                                {executing ? (
                                    <Loader2 className="w-4 h-4 animate-spin mx-auto" />
                                ) : (
                                    `SELL ${pct}%`
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

export default PositionManager;
