'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface Position {
  id: string;
  tokenMint: string;
  tokenSymbol: string;
  entryPrice: number;
  amount: number;
  solAmount: number;
  stopLossPercent: number | null;
  takeProfitPercent: number | null;
  timestamp: number;
  status: 'open' | 'closed' | 'sl_triggered' | 'tp_triggered';
}

export interface TradeRecord {
  id: string;
  tokenMint: string;
  tokenSymbol: string;
  side: 'buy' | 'sell';
  price: number;
  amount: number;
  txSignature: string;
  timestamp: number;
}

interface TradeState {
  positions: Position[];
  tradeHistory: TradeRecord[];
  addPosition: (pos: Omit<Position, 'id' | 'status'>) => void;
  closePosition: (id: string, txSignature: string, exitPrice: number) => void;
  updatePositionSLTP: (id: string, sl: number | null, tp: number | null) => void;
  addTradeRecord: (trade: Omit<TradeRecord, 'id'>) => void;
  getOpenPositions: () => Position[];
}

export const useTradeStore = create<TradeState>()(
  persist(
    (set, get) => ({
      positions: [],
      tradeHistory: [],

      addPosition: (pos) =>
        set((state) => ({
          positions: [
            ...state.positions,
            {
              ...pos,
              id: crypto.randomUUID(),
              status: 'open' as const,
            },
          ],
        })),

      closePosition: (id, txSignature, exitPrice) =>
        set((state) => {
          const position = state.positions.find((p) => p.id === id);
          if (!position) return state;

          const updatedPositions = state.positions.map((p) =>
            p.id === id ? { ...p, status: 'closed' as const } : p
          );

          const sellRecord: TradeRecord = {
            id: crypto.randomUUID(),
            tokenMint: position.tokenMint,
            tokenSymbol: position.tokenSymbol,
            side: 'sell',
            price: exitPrice,
            amount: position.amount,
            txSignature,
            timestamp: Date.now(),
          };

          return {
            positions: updatedPositions,
            tradeHistory: [...state.tradeHistory, sellRecord],
          };
        }),

      updatePositionSLTP: (id, sl, tp) =>
        set((state) => ({
          positions: state.positions.map((p) =>
            p.id === id
              ? { ...p, stopLossPercent: sl, takeProfitPercent: tp }
              : p
          ),
        })),

      addTradeRecord: (trade) =>
        set((state) => ({
          tradeHistory: [
            ...state.tradeHistory,
            { ...trade, id: crypto.randomUUID() },
          ],
        })),

      getOpenPositions: () =>
        get().positions.filter((p) => p.status === 'open'),
    }),
    {
      name: 'jarvis-trade-store',
    }
  )
);
