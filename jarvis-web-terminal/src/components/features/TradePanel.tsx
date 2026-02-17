'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTradingData } from '@/context/TradingContext';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { ArrowUpRight, ArrowDownRight, Activity, Shield, Loader2, Check, AlertTriangle, Zap, Bot, Crosshair, Layers } from 'lucide-react';
import { bagsClient } from '@/lib/bags-api';
import { getBagsTradingClient, SOL_MINT, USDC_MINT } from '@/lib/bags-trading';
import { getGrokSentimentClient, TokenSentiment } from '@/lib/grok-sentiment';
import { PriorityFeeSelector, FeeLevel, FeeBadge } from './PriorityFeeSelector';
import { useConfidence } from '@/hooks/useConfidence';
import { useToast } from '@/components/ui/Toast';
import { WIN_COMMISSION_RATE } from '@/lib/bags-trading';
import { useSettingsStore } from '@/stores/useSettingsStore';
import { useTokenStore } from '@/stores/useTokenStore';

// TP/SL Presets for easy selection
const TP_PRESETS = [
    { label: '10%', value: 10 },
    { label: '20%', value: 20 },
    { label: '50%', value: 50 },
    { label: '100%', value: 100 },
];

const SL_PRESETS = [
    { label: '5%', value: 5 },
    { label: '10%', value: 10 },
    { label: '15%', value: 15 },
    { label: '25%', value: 25 },
];

type TradeStatus = 'idle' | 'quoting' | 'signing' | 'sending' | 'confirming' | 'success' | 'error';
// ---------------------------------------------------------------------------
// AI Confidence Badge Sub-Component
// ---------------------------------------------------------------------------

function AIConfidenceBadge({
    consensus,
    signalStrength,
    bestWinRate,
}: {
    consensus: 'BUY' | 'SELL' | 'HOLD';
    signalStrength: string;
    bestWinRate: number;
}) {
    const labelMap = {
        BUY: 'STRONG BUY',
        SELL: 'SELL SIGNAL',
        HOLD: 'HOLD',
    };

    const colorMap = {
        BUY: {
            border: 'border-accent-success/40',
            bg: 'bg-accent-success/5',
            text: 'text-accent-success',
            glow: 'shadow-[0_0_12px_rgba(34,197,94,0.15)]',
        },
        SELL: {
            border: 'border-accent-error/40',
            bg: 'bg-accent-error/5',
            text: 'text-accent-error',
            glow: 'shadow-[0_0_12px_rgba(239,68,68,0.15)]',
        },
        HOLD: {
            border: 'border-accent-warning/40',
            bg: 'bg-accent-warning/5',
            text: 'text-accent-warning',
            glow: '',
        },
    };

    const colors = colorMap[consensus];

    return (
        <div
            className={`
                rounded-lg border p-3 space-y-1 transition-all duration-300
                ${colors.border} ${colors.bg} ${colors.glow}
            `}
            data-testid="ai-confidence-badge"
        >
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                    <Bot className={`w-4 h-4 ${colors.text}`} />
                    <span className={`text-xs font-mono font-bold ${colors.text}`}>
                        AI: {labelMap[consensus]}
                    </span>
                </div>
                <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${colors.bg} ${colors.text} border ${colors.border}`}>
                    {bestWinRate}% WR
                </span>
            </div>
            <div className="flex items-center justify-between text-[10px] font-mono text-text-muted">
                <span>{signalStrength} strategies agree</span>
                <span>Best WR: {bestWinRate}%</span>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main TradePanel Component
// ---------------------------------------------------------------------------

export function TradePanel() {
    const { addPosition, state } = useTradingData();
    const { connection } = useConnection();
    const { publicKey, signTransaction, connected } = useWallet();

    // AI signal data from settings store
    const {
        defaultTakeProfit,
        defaultStopLoss,
        aiConsensus,
        aiBestWinRate,
        aiSignalStrength,
        aiSuggestedTP,
        aiSuggestedSL,
        clearAISignal,
    } = useSettingsStore();

    const { info, success: toastSuccess } = useToast();

    // Trade inputs
    const [amount, setAmount] = useState<string>('0.1');
    const [tp, setTp] = useState<number>(defaultTakeProfit);
    const [sl, setSl] = useState<number>(defaultStopLoss);
    const [tokenMint, setTokenMint] = useState<string>(SOL_MINT);
    const [tokenSymbol, setTokenSymbol] = useState<string>('SOL');
    const [slippageBps, setSlippageBps] = useState<number>(100); // 1%

    // UI state
    const [price, setPrice] = useState<number>(0);
    const [feeLevel, setFeeLevel] = useState<FeeLevel>('fast');
    const [shieldReactor, setShieldReactor] = useState<boolean>(true); // Default ON for MEV protection
    const [showFeeSelector, setShowFeeSelector] = useState<boolean>(false);
    const [tradeStatus, setTradeStatus] = useState<TradeStatus>('idle');
    const [errorMessage, setErrorMessage] = useState<string>('');
    const [lastTxHash, setLastTxHash] = useState<string>('');

    // Sentiment data
    const [sentiment, setSentiment] = useState<TokenSentiment | null>(null);

    // Get confidence data for trading safety check
    const { isSafeToTrade, circuitBreaker } = useConfidence({ symbol: tokenSymbol });

    // Sync with global token selection from TokenSearch
    const selectedToken = useTokenStore((s) => s.selectedToken);
    useEffect(() => {
        if (selectedToken) {
            setTokenMint(selectedToken.address);
            setTokenSymbol(selectedToken.symbol);
        } else {
            // Default back to SOL when no token is selected
            setTokenMint(SOL_MINT);
            setTokenSymbol('SOL');
        }
    }, [selectedToken]);

    // Track whether AI values are currently applied
    const hasAI = aiConsensus !== null;

    // Auto-apply AI-suggested TP/SL when they change
    useEffect(() => {
        if (aiSuggestedTP !== null) setTp(aiSuggestedTP);
        if (aiSuggestedSL !== null) setSl(aiSuggestedSL);
    }, [aiSuggestedTP, aiSuggestedSL]);

    // Apply AI values to TP/SL
    const applyAIValues = useCallback(() => {
        if (aiSuggestedTP !== null) setTp(aiSuggestedTP);
        if (aiSuggestedSL !== null) setSl(aiSuggestedSL);
    }, [aiSuggestedTP, aiSuggestedSL]);

    // Fetch Live Price
    useEffect(() => {
        const fetchPrice = async () => {
            const info = await bagsClient.getTokenInfo(tokenMint);
            if (info) setPrice(info.price_usd);
        };
        fetchPrice();
        const interval = setInterval(fetchPrice, 10000);
        return () => clearInterval(interval);
    }, [tokenMint]);

    // Fetch Sentiment (batch efficient)
    useEffect(() => {
        const fetchSentiment = async () => {
            const grok = getGrokSentimentClient();
            const result = await grok.analyzeSingle(tokenMint, tokenSymbol, {
                price,
                volume24h: 0, // Would fetch from API
            });
            if (result) setSentiment(result);
        };

        if (price > 0) {
            fetchSentiment();
        }
    }, [tokenMint, tokenSymbol, price]);

    // Execute real trade
    const executeTrade = useCallback(async (type: 'buy' | 'sell') => {
        if (!publicKey || !signTransaction || !connected) {
            setErrorMessage('Please connect your wallet');
            setTradeStatus('error');
            return;
        }

        if (price === 0) {
            setErrorMessage('Waiting for price data');
            setTradeStatus('error');
            return;
        }

        if (circuitBreaker.isTripped) {
            setErrorMessage('Circuit breaker active - trading paused');
            setTradeStatus('error');
            return;
        }

        const amountNum = parseFloat(amount);
        if (isNaN(amountNum) || amountNum <= 0) {
            setErrorMessage('Invalid amount');
            setTradeStatus('error');
            return;
        }

        setTradeStatus('quoting');
        setErrorMessage('');

        try {
            const tradingClient = getBagsTradingClient(connection);

            // Determine input/output based on buy/sell
            const inputMint = type === 'buy' ? SOL_MINT : tokenMint;
            const outputMint = type === 'buy' ? tokenMint : SOL_MINT;

            setTradeStatus('signing');

            // Execute swap
            const result = await tradingClient.executeSwap(
                publicKey.toBase58(),
                inputMint,
                outputMint,
                amountNum,
                slippageBps,
                signTransaction as any, // TypeScript workaround
                shieldReactor // Use Jito if Shield Reactor is ON
            );

            if (result.success) {
                setTradeStatus('success');
                setLastTxHash(result.txHash || '');

                // Track position entry/exit for staker commission
                if (type === 'buy') {
                    // Record entry price for win/loss tracking on future sells
                    tradingClient.recordPositionEntry(tokenMint, price, amountNum);
                } else {
                    // Calculate win commission on sell
                    const { commission, isWin, pnlPercent } = tradingClient.calculateWinCommission(
                        tokenMint, price, amountNum
                    );
                    if (isWin && commission > 0) {
                        toastSuccess(
                            `Winning trade! +${pnlPercent.toFixed(1)}% | ${(WIN_COMMISSION_RATE * 100).toFixed(1)}% staker fee: $${commission.toFixed(4)}`
                        );
                    }
                }

                // Add position to state
                const position = {
                    id: crypto.randomUUID(),
                    tokenAddress: tokenMint,
                    symbol: tokenSymbol,
                    type: type === 'buy' ? 'long' as const : 'short' as const,
                    entryPrice: price,
                    amount: amountNum,
                    entryTime: Date.now(),
                    tpPrice: price * (1 + tp / 100),
                    slPrice: price * (1 - sl / 100),
                    // Track sentiment at entry for win/loss correlation
                    sentimentAtEntry: sentiment?.score,
                    txHash: result.txHash,
                };

                addPosition(position);

                // Reset status after 3 seconds
                setTimeout(() => setTradeStatus('idle'), 3000);
            } else {
                setTradeStatus('error');
                setErrorMessage(result.error || 'Trade failed');
            }
        } catch (error) {
            setTradeStatus('error');
            setErrorMessage(error instanceof Error ? error.message : 'Unknown error');
        }
    }, [publicKey, signTransaction, connected, price, amount, tp, sl, tokenMint, tokenSymbol, slippageBps, shieldReactor, connection, sentiment, circuitBreaker.isTripped, addPosition, toastSuccess]);

    // Quick trade: snipe (0.1 SOL with AI TP/SL)
    const handleSnipe = useCallback(() => {
        setAmount('0.1');
        if (hasAI) applyAIValues();
        executeTrade('buy');
    }, [hasAI, applyAIValues, executeTrade]);

    // Quick trade: scale in (split amount into 3 tiers)
    const handleScaleIn = useCallback(() => {
        const totalAmount = parseFloat(amount) || 0.3;
        const tierAmount = (totalAmount / 3).toFixed(4);
        setAmount(tierAmount);
        if (hasAI) applyAIValues();
        info(`Scale-in: ${tierAmount} SOL x 3 tiers. Execute 3 buys at different levels.`);
        executeTrade('buy');
    }, [amount, hasAI, applyAIValues, info, executeTrade]);

    // Get status display
    const getStatusDisplay = () => {
        switch (tradeStatus) {
            case 'quoting': return { text: 'Getting quote...', icon: <Loader2 className="w-4 h-4 animate-spin" /> };
            case 'signing': return { text: 'Sign in wallet...', icon: <Loader2 className="w-4 h-4 animate-spin" /> };
            case 'sending': return { text: 'Sending...', icon: <Loader2 className="w-4 h-4 animate-spin" /> };
            case 'confirming': return { text: 'Confirming...', icon: <Loader2 className="w-4 h-4 animate-spin" /> };
            case 'success': return { text: 'Success!', icon: <Check className="w-4 h-4" /> };
            case 'error': return { text: errorMessage || 'Failed', icon: <AlertTriangle className="w-4 h-4" /> };
            default: return null;
        }
    };

    const isTrading = ['quoting', 'signing', 'sending', 'confirming'].includes(tradeStatus);
    const statusDisplay = getStatusDisplay();

    return (
        <div className="card-glass p-4 space-y-4">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-border-primary/30 pb-3">
                <h3 className="font-display font-bold text-sm flex items-center gap-2">
                    <Activity className="w-4 h-4 text-accent-neon" />
                    EXECUTION
                </h3>
                <div className="flex items-center gap-2">
                    <FeeBadge level={feeLevel} onClick={() => setShowFeeSelector(!showFeeSelector)} />
                    <span className="text-xs font-mono text-text-muted">
                        {state.solBalance.toFixed(2)} SOL
                    </span>
                </div>
            </div>

            {/* AI Confidence Badge (when AI signal is active) */}
            {hasAI && aiConsensus && aiSignalStrength && aiBestWinRate !== null && (
                <AIConfidenceBadge
                    consensus={aiConsensus}
                    signalStrength={aiSignalStrength}
                    bestWinRate={aiBestWinRate}
                />
            )}

            {/* QUICK TRADE Section */}
            {connected && (
                <div className="space-y-2">
                    <div className="flex items-center gap-1.5">
                        <Zap className="w-3.5 h-3.5 text-accent-neon" />
                        <span className="text-[10px] font-mono font-bold text-text-muted uppercase tracking-wider">
                            Quick Trade
                        </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <button
                            onClick={handleSnipe}
                            disabled={isTrading || circuitBreaker.isTripped || price === 0}
                            className="
                                flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-mono font-bold
                                bg-accent-neon/10 text-accent-neon border border-accent-neon/30
                                hover:bg-accent-neon/20 hover:border-accent-neon/50 transition-all
                                disabled:opacity-40 disabled:cursor-not-allowed
                            "
                        >
                            <Crosshair className="w-3.5 h-3.5" />
                            SNIPE 0.1 SOL
                        </button>
                        <button
                            onClick={handleScaleIn}
                            disabled={isTrading || circuitBreaker.isTripped || price === 0}
                            className="
                                flex items-center justify-center gap-1.5 py-2.5 rounded-lg text-xs font-mono font-bold
                                bg-bg-secondary/40 text-text-primary border border-border-primary/40
                                hover:bg-bg-secondary/60 hover:border-accent-neon/30 transition-all
                                disabled:opacity-40 disabled:cursor-not-allowed
                            "
                        >
                            <Layers className="w-3.5 h-3.5" />
                            SCALE IN x3
                        </button>
                    </div>
                </div>
            )}

            {/* Trade Mode Label */}
            <div className="flex items-center justify-center p-1 rounded-lg bg-bg-secondary/50 border border-border-primary/30">
                <span className="py-1.5 text-xs font-mono font-bold text-accent-neon">SPOT TRADING</span>
            </div>


            {/* Wallet Connection Warning */}
            {!connected && (
                <div className="bg-accent-warning/10 border border-accent-warning/30 rounded-lg p-3 text-center">
                    <span className="text-sm text-accent-warning">Connect wallet to trade</span>
                </div>
            )}

            {/* Shield Reactor Toggle (Jito MEV Protection) */}
            <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-bg-secondary/30 border border-border-primary/30">
                <div className="flex items-center gap-2">
                    <Shield className={`w-4 h-4 ${shieldReactor ? 'text-accent-neon' : 'text-text-muted'}`} />
                    <span className="text-sm font-medium">Shield Reactor</span>
                    <span className="text-xs text-text-muted">(Jito MEV)</span>
                </div>
                <button
                    onClick={() => setShieldReactor(!shieldReactor)}
                    className={`
                        relative w-12 h-6 rounded-full transition-colors duration-200
                        ${shieldReactor ? 'bg-accent-neon' : 'bg-bg-secondary/50 border border-border-primary'}
                    `}
                >
                    <span
                        className={`
                            absolute top-1 w-4 h-4 rounded-full transition-all duration-200
                            ${shieldReactor ? 'right-1 bg-black' : 'left-1 bg-text-muted'}
                        `}
                    />
                </button>
            </div>

            {/* Fee Selector */}
            {showFeeSelector && (
                <PriorityFeeSelector
                    value={feeLevel}
                    onChange={(level) => {
                        setFeeLevel(level);
                        setShowFeeSelector(false);
                    }}
                    shieldReactorActive={shieldReactor}
                />
            )}

            {/* Sentiment Display */}
            {sentiment && (
                <div className={`
                    flex items-center justify-between p-3 rounded-lg border
                    ${sentiment.score >= 65 ? 'bg-accent-success/10 border-accent-success/30' :
                        sentiment.score >= 35 ? 'bg-accent-warning/10 border-accent-warning/30' :
                            'bg-accent-error/10 border-accent-error/30'}
                `}>
                    <span className="text-xs font-mono uppercase">AI SENTIMENT</span>
                    <div className="flex items-center gap-2">
                        <span className="font-bold">{sentiment.score}</span>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                            sentiment.signal === 'strong_buy' || sentiment.signal === 'buy' ? 'bg-accent-success/20 text-accent-success' :
                                sentiment.signal === 'strong_sell' || sentiment.signal === 'sell' ? 'bg-accent-error/20 text-accent-error' :
                                    'bg-text-muted/20 text-text-muted'
                        }`}>
                            {sentiment.signal.toUpperCase().replace('_', ' ')}
                        </span>
                    </div>
                </div>
            )}

            {/* Amount Input */}
            <div className="space-y-2">
                <label className="text-xs font-mono text-text-muted uppercase">Amount (SOL)</label>
                <div className="relative">
                    <input
                        type="number"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        disabled={isTrading}
                        className="w-full bg-bg-secondary/50 border border-border-primary rounded-lg px-4 py-3 font-mono text-lg focus:border-accent-neon outline-none transition-colors disabled:opacity-50"
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-text-muted font-bold">SOL</span>
                </div>
                {/* Quick Amount Presets */}
                <div className="flex gap-1.5">
                    {[0.1, 0.25, 0.5, 1, 2, 5].map((preset) => (
                        <button
                            key={preset}
                            onClick={() => setAmount(preset.toString())}
                            disabled={isTrading}
                            className={`flex-1 py-1 text-[10px] font-mono rounded transition-colors ${
                                parseFloat(amount) === preset
                                    ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/40'
                                    : 'bg-bg-tertiary text-text-muted hover:text-text-primary border border-transparent'
                            }`}
                        >
                            {preset} SOL
                        </button>
                    ))}
                </div>
                {/* Percentage of Balance Buttons */}
                <div className="flex gap-1.5">
                    {[25, 50, 75, 100].map((pct) => (
                        <button
                            key={pct}
                            onClick={() => {
                                if (state.solBalance > 0) {
                                    const amt = (state.solBalance * pct / 100).toFixed(4);
                                    setAmount(amt);
                                }
                            }}
                            disabled={isTrading || state.solBalance <= 0}
                            className="flex-1 py-1 text-[10px] font-mono rounded bg-bg-tertiary text-text-muted hover:text-text-primary border border-transparent transition-colors disabled:opacity-30"
                        >
                            {pct}%
                        </button>
                    ))}
                </div>
            </div>

            {/* AI SUGGESTED TP/SL (when AI signal is active) */}
            {hasAI && aiSuggestedTP !== null && aiSuggestedSL !== null && (
                <div className="rounded-lg border border-accent-neon/30 bg-accent-neon/5 p-3 space-y-2"
                     data-testid="ai-suggested-section">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                            <Bot className="w-3.5 h-3.5 text-accent-neon" />
                            <span className="text-[10px] font-mono font-bold text-accent-neon uppercase tracking-wider">
                                AI Suggested
                            </span>
                        </div>
                        <div className="flex items-center gap-2">
                            <button
                                onClick={applyAIValues}
                                disabled={isTrading}
                                className="
                                    text-[10px] font-mono font-bold px-2 py-1 rounded
                                    bg-accent-neon/20 text-accent-neon border border-accent-neon/40
                                    hover:bg-accent-neon/30 transition-all
                                    disabled:opacity-50
                                "
                            >
                                USE AI
                            </button>
                            <button
                                onClick={clearAISignal}
                                className="text-[10px] font-mono text-text-muted hover:text-accent-error transition-colors"
                            >
                                CLEAR
                            </button>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="flex items-center justify-between bg-accent-success/10 rounded px-2 py-1.5">
                            <span className="text-[10px] font-mono text-accent-success">TP</span>
                            <span className="text-xs font-mono font-bold text-accent-success">+{aiSuggestedTP}%</span>
                        </div>
                        <div className="flex items-center justify-between bg-accent-error/10 rounded px-2 py-1.5">
                            <span className="text-[10px] font-mono text-accent-error">SL</span>
                            <span className="text-xs font-mono font-bold text-accent-error">-{aiSuggestedSL}%</span>
                        </div>
                    </div>
                </div>
            )}

            {/* Easy TP/SL Presets -- stacks on very small screens */}
            <div className="grid grid-cols-1 xs:grid-cols-2 gap-4">
                {/* Take Profit */}
                <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                        <span className="text-accent-success">TAKE PROFIT</span>
                        <span>{tp}%</span>
                    </div>
                    <div className="flex gap-1">
                        {TP_PRESETS.map((preset) => (
                            <button
                                key={preset.value}
                                onClick={() => setTp(preset.value)}
                                disabled={isTrading}
                                className={`
                                    flex-1 py-1.5 text-[10px] sm:text-xs font-mono rounded transition-all
                                    ${tp === preset.value
                                        ? 'bg-accent-success text-black'
                                        : 'bg-bg-secondary/30 border border-border-primary/50 hover:border-accent-success'}
                                `}
                            >
                                {preset.label}
                            </button>
                        ))}
                    </div>
                    <input
                        type="range" min="1" max="200" value={tp}
                        onChange={(e) => setTp(parseInt(e.target.value))}
                        disabled={isTrading}
                        className="w-full accent-accent-success h-1 bg-bg-secondary/50 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                    />
                </div>

                {/* Stop Loss */}
                <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                        <span className="text-accent-error">STOP LOSS</span>
                        <span>{sl}%</span>
                    </div>
                    <div className="flex gap-1">
                        {SL_PRESETS.map((preset) => (
                            <button
                                key={preset.value}
                                onClick={() => setSl(preset.value)}
                                disabled={isTrading}
                                className={`
                                    flex-1 py-1.5 text-[10px] sm:text-xs font-mono rounded transition-all
                                    ${sl === preset.value
                                        ? 'bg-accent-error text-black'
                                        : 'bg-bg-secondary/30 border border-border-primary/50 hover:border-accent-error'}
                                `}
                            >
                                {preset.label}
                            </button>
                        ))}
                    </div>
                    <input
                        type="range" min="1" max="50" value={sl}
                        onChange={(e) => setSl(parseInt(e.target.value))}
                        disabled={isTrading}
                        className="w-full accent-accent-error h-1 bg-bg-secondary/50 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                    />
                </div>
            </div>

            {/* Price Preview */}
            <div className="bg-bg-secondary/30 rounded-lg p-3 space-y-1">
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-text-muted">Entry Price</span>
                    <span>${price.toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-accent-success">TP Target</span>
                    <span className="text-accent-success">${(price * (1 + tp / 100)).toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-accent-error">SL Target</span>
                    <span className="text-accent-error">${(price * (1 - sl / 100)).toFixed(4)}</span>
                </div>
            </div>

            {/* Trade Status */}
            {statusDisplay && (
                <div className={`
                    flex items-center justify-center gap-2 p-3 rounded-lg
                    ${tradeStatus === 'success' ? 'bg-accent-success/10 text-accent-success' :
                        tradeStatus === 'error' ? 'bg-accent-error/10 text-accent-error' :
                            'bg-accent-neon/10 text-accent-neon'}
                `}>
                    {statusDisplay.icon}
                    <span className="text-sm font-mono">{statusDisplay.text}</span>
                </div>
            )}

            {/* Trade Buttons */}
            <div className="grid grid-cols-2 gap-4">
                <button
                    onClick={() => executeTrade('buy')}
                    disabled={isTrading || circuitBreaker.isTripped || !connected}
                    className="bg-accent-success/10 border border-accent-success text-accent-success py-4 rounded-lg font-bold hover:bg-accent-success/20 transition-all flex items-center justify-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isTrading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <>
                            BUY <ArrowUpRight className="group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                        </>
                    )}
                </button>
                <button
                    onClick={() => executeTrade('sell')}
                    disabled={isTrading || circuitBreaker.isTripped || !connected}
                    className="bg-accent-error/10 border border-accent-error text-accent-error py-4 rounded-lg font-bold hover:bg-accent-error/20 transition-all flex items-center justify-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isTrading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                        <>
                            SELL <ArrowDownRight className="group-hover:translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                        </>
                    )}
                </button>
            </div>

            {/* Staker Fee Note */}
            <p className="text-[10px] text-text-muted text-center">
                0.5% commission on winning trades supports stakers
            </p>

            {/* Circuit Breaker Warning */}
            {circuitBreaker.isTripped && (
                <div className="text-center text-xs text-accent-error font-mono py-2">
                    CIRCUIT BREAKER ACTIVE - TRADING PAUSED
                </div>
            )}

            {/* Last Transaction Link */}
            {lastTxHash && tradeStatus === 'success' && (
                <div className="text-center">
                    <a
                        href={`https://solscan.io/tx/${lastTxHash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-accent-neon hover:underline font-mono"
                    >
                        View on Solscan
                    </a>
                </div>
            )}
        </div>
    );
}
