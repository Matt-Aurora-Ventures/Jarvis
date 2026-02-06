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

export function TradePanel() {
    const { addPosition, state } = useTradingData();
    const { connection } = useConnection();
    const { publicKey, signTransaction, connected } = useWallet();

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
        <div className="card-glass p-6 space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center border-b border-theme-border/30 pb-4">
                <h3 className="font-display font-bold text-lg flex items-center gap-2">
                    <Activity className="w-4 h-4 text-theme-cyan" />
                    EXECUTION
                </h3>
                <div className="flex items-center gap-2">
                    <FeeBadge level={feeLevel} onClick={() => setShowFeeSelector(!showFeeSelector)} />
                    <span className="text-xs font-mono text-theme-muted">
                        {state.solBalance.toFixed(2)} SOL
                    </span>
                </div>
            </div>

            {/* Wallet Connection Warning */}
            {!connected && (
                <div className="bg-theme-orange/10 border border-theme-orange/30 rounded-lg p-3 text-center">
                    <span className="text-sm text-theme-orange">Connect wallet to trade</span>
                </div>
            )}

            {/* Shield Reactor Toggle (Jito MEV Protection) */}
            <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-theme-dark/30 border border-theme-border/30">
                <div className="flex items-center gap-2">
                    <Shield className={`w-4 h-4 ${shieldReactor ? 'text-accent-neon' : 'text-text-muted'}`} />
                    <span className="text-sm font-medium">Shield Reactor</span>
                    <span className="text-xs text-text-muted">(Jito MEV)</span>
                </div>
                <button
                    onClick={() => setShieldReactor(!shieldReactor)}
                    className={`
                        relative w-12 h-6 rounded-full transition-colors duration-200
                        ${shieldReactor ? 'bg-accent-neon' : 'bg-theme-dark/50 border border-theme-border'}
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
                    ${sentiment.score >= 65 ? 'bg-theme-green/10 border-theme-green/30' :
                        sentiment.score >= 35 ? 'bg-theme-orange/10 border-theme-orange/30' :
                            'bg-theme-red/10 border-theme-red/30'}
                `}>
                    <span className="text-xs font-mono uppercase">AI SENTIMENT</span>
                    <div className="flex items-center gap-2">
                        <span className="font-bold">{sentiment.score}</span>
                        <span className={`text-xs px-2 py-0.5 rounded ${
                            sentiment.signal === 'strong_buy' || sentiment.signal === 'buy' ? 'bg-theme-green/20 text-theme-green' :
                                sentiment.signal === 'strong_sell' || sentiment.signal === 'sell' ? 'bg-theme-red/20 text-theme-red' :
                                    'bg-theme-muted/20 text-theme-muted'
                        }`}>
                            {sentiment.signal.toUpperCase().replace('_', ' ')}
                        </span>
                    </div>
                </div>
            )}

            {/* Amount Input */}
            <div className="space-y-2">
                <label className="text-xs font-mono text-theme-muted uppercase">Amount (SOL)</label>
                <div className="relative">
                    <input
                        type="number"
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        disabled={isTrading}
                        className="w-full bg-theme-dark/50 border border-theme-border rounded-lg px-4 py-3 font-mono text-lg focus:border-theme-cyan outline-none transition-colors disabled:opacity-50"
                    />
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm text-theme-muted font-bold">SOL</span>
                </div>
                {/* Quick amount buttons */}
                <div className="flex gap-2">
                    {[0.1, 0.5, 1, 5].map((val) => (
                        <button
                            key={val}
                            onClick={() => setAmount(val.toString())}
                            disabled={isTrading}
                            className="flex-1 py-1 text-xs font-mono bg-theme-dark/30 border border-theme-border/50 rounded hover:border-theme-cyan transition-colors disabled:opacity-50"
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
                        <span className="text-theme-green">TAKE PROFIT</span>
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
                                        ? 'bg-theme-green text-black'
                                        : 'bg-theme-dark/30 border border-theme-border/50 hover:border-theme-green'}
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
                        className="w-full accent-theme-green h-1 bg-theme-dark/50 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                    />
                </div>

                {/* Stop Loss */}
                <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                        <span className="text-theme-red">STOP LOSS</span>
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
                                        ? 'bg-theme-red text-black'
                                        : 'bg-theme-dark/30 border border-theme-border/50 hover:border-theme-red'}
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
                        className="w-full accent-theme-red h-1 bg-theme-dark/50 rounded-lg appearance-none cursor-pointer disabled:opacity-50"
                    />
                </div>
            </div>

            {/* Price Preview */}
            <div className="bg-theme-dark/30 rounded-lg p-3 space-y-1">
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-theme-muted">Entry Price</span>
                    <span>${price.toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-theme-green">TP Target</span>
                    <span className="text-theme-green">${(price * (1 + tp / 100)).toFixed(4)}</span>
                </div>
                <div className="flex justify-between text-xs font-mono">
                    <span className="text-theme-red">SL Target</span>
                    <span className="text-theme-red">${(price * (1 - sl / 100)).toFixed(4)}</span>
                </div>
            </div>

            {/* Trade Status */}
            {statusDisplay && (
                <div className={`
                    flex items-center justify-center gap-2 p-3 rounded-lg
                    ${tradeStatus === 'success' ? 'bg-theme-green/10 text-theme-green' :
                        tradeStatus === 'error' ? 'bg-theme-red/10 text-theme-red' :
                            'bg-theme-cyan/10 text-theme-cyan'}
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
                    className={`
                        bg-theme-green/10 border border-theme-green text-theme-green py-4 rounded-lg font-bold
                        hover:bg-theme-green/20 transition-all flex items-center justify-center gap-2 group
                        disabled:opacity-50 disabled:cursor-not-allowed
                    `}
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
                    className={`
                        bg-theme-red/10 border border-theme-red text-theme-red py-4 rounded-lg font-bold
                        hover:bg-theme-red/20 transition-all flex items-center justify-center gap-2 group
                        disabled:opacity-50 disabled:cursor-not-allowed
                    `}
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
                        className="text-xs text-theme-cyan hover:underline font-mono"
                    >
                        View on Solscan →
                    </a>
                </div>
            )}
        </div>
    );
}
