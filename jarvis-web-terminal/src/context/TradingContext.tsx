'use client';

import React, { createContext, useContext, useEffect, useReducer, ReactNode, useCallback, useRef } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { getHeliusClient } from '@/lib/helius-client';

// --- Types ---

export interface Position {
    id: string;
    tokenAddress: string;
    symbol: string;
    type: 'long' | 'short';
    entryPrice: number;
    amount: number;
    entryTime: number;
    tpPrice?: number;
    slPrice?: number;
    pnl?: number; // Calculated live
    pnlPercent?: number; // Calculated live
}

export interface TradeHistoryItem {
    id: string;
    symbol: string;
    type: 'buy' | 'sell';
    price: number;
    amount: number;
    timestamp: number;
    txHash: string;
    pnl?: number;
}

export interface TradingState {
    portfolioValue: number;
    solBalance: number;
    positions: Position[];
    history: TradeHistoryItem[];
    metrics: {
        winRate: number;
        sharpeRatio: number;
        maxDrawdown: number;
        totalPnL: number;
    };
}

type Action =
    | { type: 'SET_SOL_BALANCE'; payload: number }
    | { type: 'ADD_POSITION'; payload: Position }
    | { type: 'CLOSE_POSITION'; payload: { id: string; price: number; pnl: number } }
    | { type: 'UPDATE_METRICS'; payload: TradingState['metrics'] }
    | { type: 'LOAD_STATE'; payload: Partial<TradingState> };

// --- Initial State ---

const initialState: TradingState = {
    portfolioValue: 0,
    solBalance: 0,
    positions: [],
    history: [],
    metrics: {
        winRate: 0,
        sharpeRatio: 0,
        maxDrawdown: 0,
        totalPnL: 0,
    },
};

// --- Reducer ---

function tradingReducer(state: TradingState, action: Action): TradingState {
    switch (action.type) {
        case 'SET_SOL_BALANCE':
            return { ...state, solBalance: action.payload };
        case 'ADD_POSITION':
            return { ...state, positions: [action.payload, ...state.positions] };
        case 'CLOSE_POSITION': {
            const position = state.positions.find((p) => p.id === action.payload.id);
            if (!position) return state;

            const closedTrade: TradeHistoryItem = {
                id: `close-${position.id}`,
                symbol: position.symbol,
                type: 'sell', // Assuming long close
                price: action.payload.price,
                amount: position.amount,
                timestamp: Date.now(),
                txHash: 'mock-tx-hash', // Replace with real
                pnl: action.payload.pnl,
            };

            return {
                ...state,
                positions: state.positions.filter((p) => p.id !== action.payload.id),
                history: [closedTrade, ...state.history],
            };
        }
        case 'UPDATE_METRICS':
            return { ...state, metrics: action.payload };
        case 'LOAD_STATE':
            return { ...state, ...action.payload };
        default:
            return state;
    }
}

// --- Context ---

const TradingContext = createContext<{
    state: TradingState;
    addPosition: (pos: Position) => void;
    closePosition: (id: string, price: number) => void;
    refreshBalance: () => void;
} | null>(null);

export const TradingProvider = ({ children }: { children: ReactNode }) => {
    const [state, dispatch] = useReducer(tradingReducer, initialState);
    const { publicKey } = useWallet();
    const heliusClientRef = useRef(getHeliusClient());

    // 1. Load from LocalStorage on mount
    useEffect(() => {
        const saved = localStorage.getItem('jarvis_trading_state');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                dispatch({ type: 'LOAD_STATE', payload: parsed });
            } catch (e) {
                console.error("Failed to load trading state", e);
            }
        }
    }, []);

    // 2. Persist to LocalStorage on change
    useEffect(() => {
        localStorage.setItem('jarvis_trading_state', JSON.stringify({
            positions: state.positions,
            history: state.history,
            metrics: state.metrics // Persist calculated metrics too
        }));
    }, [state.positions, state.history, state.metrics]);

    // 3. Live Balance Updates - Using Helius client with smart fallback
    const refreshBalance = useCallback(async () => {
        if (!publicKey) return;
        try {
            // Uses Helius with automatic fallback to Ankr on 403 errors
            const balance = await heliusClientRef.current.getBalance(publicKey);
            dispatch({ type: 'SET_SOL_BALANCE', payload: balance });

            // Log endpoint info for debugging
            const endpointInfo = heliusClientRef.current.getEndpointInfo();
            if (endpointInfo.fallbackUsed) {
                console.log('[Trading] Using fallback RPC (Helius 403 detected)');
            }
        } catch (e) {
            console.error("Failed to fetch balance:", e);
        }
    }, [publicKey]);

    useEffect(() => {
        refreshBalance();
        const interval = setInterval(refreshBalance, 10000); // Poll every 10s
        return () => clearInterval(interval);
    }, [refreshBalance]);

    // 4. Metric Calculation (The "Heavy Math")
    useEffect(() => {
        // Re-calculate metrics whenever history changes
        if (state.history.length === 0) return;

        const wins = state.history.filter(t => (t.pnl || 0) > 0).length;
        const totalTrades = state.history.length;
        const winRate = (wins / totalTrades) * 100;

        const totalPnL = state.history.reduce((acc, t) => acc + (t.pnl || 0), 0);

        // Simple Sharpe (needs more complex history series properly, but approximation:)
        // Avg return / StdDev of returns
        const returns = state.history.map(t => t.pnl || 0);
        const avgReturn = totalPnL / totalTrades;
        const variance = returns.reduce((acc, val) => acc + Math.pow(val - avgReturn, 2), 0) / totalTrades;
        const stdDev = Math.sqrt(variance);
        const sharpeRatio = stdDev === 0 ? 0 : avgReturn / stdDev;

        dispatch({
            type: 'UPDATE_METRICS',
            payload: {
                winRate,
                sharpeRatio,
                maxDrawdown: 0, // TODO: Implement drawdown calc
                totalPnL
            }
        });

    }, [state.history]);


    const addPosition = (pos: Position) => {
        dispatch({ type: 'ADD_POSITION', payload: pos });
    };

    const closePosition = (id: string, price: number) => {
        const position = state.positions.find(p => p.id === id);
        if (!position) return;
        const pnl = (price - position.entryPrice) * position.amount;
        dispatch({ type: 'CLOSE_POSITION', payload: { id, price, pnl } });
    };

    return (
        <TradingContext.Provider value={{ state, addPosition, closePosition, refreshBalance }}>
            {children}
        </TradingContext.Provider>
    );
};

export const useTradingData = () => {
    const context = useContext(TradingContext);
    if (!context) throw new Error("useTradingData must be used within a TradingProvider");
    return context;
};
