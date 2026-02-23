'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ---------------------------------------------------------------------------
// AI Signal Input Type
// ---------------------------------------------------------------------------

export interface AISignalInput {
  consensus: 'BUY' | 'SELL' | 'HOLD';
  bestWinRate: number;
  signalStrength: string; // e.g. "3/4"
  suggestedTP: number;
  suggestedSL: number;
}

// ---------------------------------------------------------------------------
// Store Interface
// ---------------------------------------------------------------------------

interface SettingsState {
  // Existing fields
  slippageBps: number;
  defaultStopLoss: number;
  defaultTakeProfit: number;
  rpcEndpoint: string;
  autoRefreshInterval: number;

  // AI signal fields (from backtest engine consensus)
  aiConsensus: 'BUY' | 'SELL' | 'HOLD' | null;
  aiBestWinRate: number | null;
  aiSignalStrength: string | null;
  aiSuggestedTP: number | null;
  aiSuggestedSL: number | null;

  // Existing actions
  setSlippage: (bps: number) => void;
  setDefaultSLTP: (sl: number, tp: number) => void;
  setRpcEndpoint: (url: string) => void;
  setAutoRefreshInterval: (ms: number) => void;

  // AI signal actions
  setAISignal: (signal: AISignalInput) => void;
  clearAISignal: () => void;
  hasAISignal: () => boolean;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const DEFAULT_RPC =
  process.env.NEXT_PUBLIC_HELIUS_RPC || 'https://api.mainnet-beta.solana.com';

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      // Existing defaults
      slippageBps: 100,
      defaultStopLoss: 5,
      defaultTakeProfit: 20,
      rpcEndpoint: DEFAULT_RPC,
      autoRefreshInterval: 5000,

      // AI signal defaults
      aiConsensus: null,
      aiBestWinRate: null,
      aiSignalStrength: null,
      aiSuggestedTP: null,
      aiSuggestedSL: null,

      // Existing actions
      setSlippage: (bps) => set({ slippageBps: bps }),
      setDefaultSLTP: (sl, tp) =>
        set({ defaultStopLoss: sl, defaultTakeProfit: tp }),
      setRpcEndpoint: (url) => set({ rpcEndpoint: url }),
      setAutoRefreshInterval: (ms) => set({ autoRefreshInterval: ms }),

      // AI signal actions
      setAISignal: (signal: AISignalInput) =>
        set({
          aiConsensus: signal.consensus,
          aiBestWinRate: signal.bestWinRate,
          aiSignalStrength: signal.signalStrength,
          aiSuggestedTP: signal.suggestedTP,
          aiSuggestedSL: signal.suggestedSL,
          // Also auto-apply to default TP/SL
          defaultTakeProfit: signal.suggestedTP,
          defaultStopLoss: signal.suggestedSL,
        }),

      clearAISignal: () =>
        set({
          aiConsensus: null,
          aiBestWinRate: null,
          aiSignalStrength: null,
          aiSuggestedTP: null,
          aiSuggestedSL: null,
        }),

      hasAISignal: () => get().aiConsensus !== null,
    }),
    {
      name: 'jarvis-settings-store',
    }
  )
);
