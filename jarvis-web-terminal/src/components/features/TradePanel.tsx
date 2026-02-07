'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTradingData } from '@/context/TradingContext';
import { useConnection, useWallet } from '@solana/wallet-adapter-react';
import { ArrowUpRight, ArrowDownRight, Activity, Shield, Loader2, Check, AlertTriangle } from 'lucide-react';
import { bagsClient } from '@/lib/bags-api';
import { getBagsTradingClient, SOL_MINT, USDC_MINT } from '@/lib/bags-trading';
import { getGrokSentimentClient, TokenSentiment } from '@/lib/grok-sentiment';
import { PriorityFeeSelector, FeeLevel, FeeBadge } from './PriorityFeeSelector';
import { useConfidence } from '@/hooks/useConfidence';
import { getPerpsDeepLink, PERPS_MARKETS, type PerpsMarket } from '@/lib/jupiter-perps';
import { useToast } from '@/components/ui/Toast';

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
type TradeMode = 'spot' | 'perps';

export function TradePanel() {
    const { addPosition, state } = useTradingData();
    const { connection } = useConnection();
    const { publicKey, signTransaction, connected } = useWallet();

    // Trade mode
    const [tradeMode, setTradeMode] = useState<TradeMode>('spot');
    const [leverage, setLeverage] = useState<number>(1);
    const [perpsMarket, setPerpsMarket] = useState<PerpsMarket>('SOL');
    const { info } = useToast();

    // Trade inputs
    const [amount, setAmount] = useState<string>('0.1');
    const [tp, setTp] = useState<number>(20);
    const [sl, setSl] = useState<number>(10);
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
    }, [publicKey, signTransaction, connected, price, amount, tp, sl, tokenMint, tokenSymbol, slippageBps, shieldReactor, connection, sentiment, circuitBreaker.isTripped, addPosition]);

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

            {/* Spot / Perps Toggle */}
            <div className="flex items-center gap-1 p-1 rounded-lg bg-bg-secondary/50 border border-border-primary/30">
                <button
                    onClick={() => { setTradeMode('spot'); setLeverage(1); }}
                    className={`flex-1 py-1.5 text-xs font-mono font-bold rounded-md transition-all ${
                        tradeMode === 'spot'
                            ? 'bg-accent-neon text-black shadow-sm'
                            : 'text-text-muted hover:text-text-primary'
                    }`}
                >
                    SPOT
                </button>
                <button
                    onClick={() => setTradeMode('perps')}
                    className={`flex-1 py-1.5 text-xs font-mono font-bold rounded-md transition-all ${
                        tradeMode === 'perps'
                            ? 'bg-accent-neon text-black shadow-sm'
                            : 'text-text-muted hover:text-text-primary'
                    }`}
                >
                    PERPS
                </button>
            </div>

            {/* Perps Market Selector + Leverage */}
            {tradeMode === 'perps' && (
                <div className="space-y-2">
                    {/* Market Selector */}
                    <div className="flex gap-1">
                        {(Object.keys(PERPS_MARKETS) as PerpsMarket[]).map((m) => (
                            <button
                                key={m}
                                onClick={() => setPerpsMarket(m)}
                                className={`flex-1 py-1.5 text-xs font-mono font-bold rounded transition-all ${
                                    perpsMarket === m
                                        ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/40'
                                        : 'bg-bg-secondary/30 border border-border-primary/50 text-text-muted hover:border-accent-neon/30'
                                }`}
                            >
                                {PERPS_MARKETS[m].label}
                            </button>
                        ))}
                    </div>

                    {/* Leverage */}
                    <div className="flex justify-between text-xs font-mono">
                        <span className="text-text-muted">LEVERAGE</span>
                        <span className="text-accent-neon font-bold">{leverage}x</span>
                    </div>
                    <div className="flex gap-1">
                        {[2, 5, 10, 20, 50].map((lev) => (
                            <button
                                key={lev}
                                onClick={() => setLeverage(lev)}
                                className={`flex-1 py-1.5 text-xs font-mono rounded transition-all ${
                                    leverage === lev
                                        ? 'bg-accent-neon text-black font-bold'
                                        : 'bg-bg-secondary/30 border border-border-primary/50 hover:border-accent-neon/50'
                                }`}
                            >
                                {lev}x
                            </button>
                        ))}
                    </div>
                    <input
                        type="range" min="1" max="100" value={leverage}
                        onChange={(e) => setLeverage(parseInt(e.target.value))}
                        className="w-full accent-accent-neon h-1 bg-bg-secondary/50 rounded-lg appearance-none cursor-pointer"
                    />
                    {leverage > 20 && (
                        <div className="flex items-center gap-1 text-[10px] text-accent-error font-mono">
                            <AlertTriangle className="w-3 h-3" />
                            HIGH RISK - LIQUIDATION LIKELY
                        </div>
                    )}
                </div>
            )}

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
                {/* Quick amount buttons */}
                <div className="flex gap-2">
                    {[0.1, 0.5, 1, 5].map((val) => (
                        <button
                            key={val}
                            onClick={() => setAmount(val.toString())}
                            disabled={isTrading}
                            className="flex-1 py-1 text-xs font-mono bg-bg-secondary/30 border border-border-primary/50 rounded hover:border-accent-neon transition-colors disabled:opacity-50"
                        >
                            {val} SOL
                        </button>
                    ))}
                </div>
            </div>

            {/* Easy TP/SL Presets */}
            <div className="grid grid-cols-2 gap-4">
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
                                    flex-1 py-1.5 text-xs font-mono rounded transition-all
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
                                    flex-1 py-1.5 text-xs font-mono rounded transition-all
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
                {tradeMode === 'perps' && (
                    <div className="flex justify-between text-xs font-mono">
                        <span className="text-accent-neon">Position Size</span>
                        <span className="text-accent-neon">{(parseFloat(amount || '0') * leverage).toFixed(2)} SOL ({leverage}x)</span>
                    </div>
                )}
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-accent-success">TP Target</span>
                    <span className="text-accent-success">${(price * (1 + tp / 100)).toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-accent-error">SL Target</span>
                    <span className="text-accent-error">${(price * (1 - sl / 100)).toFixed(4)}</span>
                </div>
                {tradeMode === 'perps' && leverage > 1 && (
                    <div className="flex justify-between text-xs font-mono pt-1 border-t border-border-primary/20">
                        <span className="text-accent-warning">Liq. Price</span>
                        <span className="text-accent-warning">${(price * (1 - 100 / leverage / 100)).toFixed(4)}</span>
                    </div>
                )}
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
            {tradeMode === 'perps' ? (
                <div className="grid grid-cols-2 gap-4">
                    <button
                        onClick={() => {
                            info(`Opening Jupiter Perps for ${perpsMarket}...`);
                            window.open(getPerpsDeepLink(perpsMarket), '_blank');
                        }}
                        className="bg-accent-success/10 border border-accent-success text-accent-success py-4 rounded-lg font-bold hover:bg-accent-success/20 transition-all flex items-center justify-center gap-2 group"
                    >
                        LONG <ArrowUpRight className="group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                    <button
                        onClick={() => {
                            info(`Opening Jupiter Perps for ${perpsMarket}...`);
                            window.open(getPerpsDeepLink(perpsMarket), '_blank');
                        }}
                        className="bg-accent-error/10 border border-accent-error text-accent-error py-4 rounded-lg font-bold hover:bg-accent-error/20 transition-all flex items-center justify-center gap-2 group"
                    >
                        SHORT <ArrowDownRight className="group-hover:translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                    </button>
                </div>
            ) : (
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
                                LONG <ArrowUpRight className="group-hover:-translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
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
                                SHORT <ArrowDownRight className="group-hover:translate-y-0.5 group-hover:translate-x-0.5 transition-transform" />
                            </>
                        )}
                    </button>
                </div>
            )}

            {/* Circuit Breaker Warning */}
            {circuitBreaker.isTripped && (
                <div className="text-center text-xs text-accent-error font-mono py-2">
                    🛡️ CIRCUIT BREAKER ACTIVE - TRADING PAUSED
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
                        View on Solscan →
                    </a>
                </div>
            )}
        </div>
    );
}
