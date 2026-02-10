'use client';

import { useEffect, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { executeSwapFromQuote, getSellQuote } from '@/lib/bags-trading';
import { getOwnerTokenBalanceLamports, minLamportsString } from '@/lib/solana-tokens';
import { loadSessionWalletFromStorage, sweepExcessToMainWallet } from '@/lib/session-wallet';
import { isBlueChipLongConvictionSymbol } from '@/lib/trade-plan';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const WORKER_INTERVAL_MS = 1500;

type TriggerType = 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired';

/**
 * Automated risk management (SL/TP/Trail/Expiry).
 *
 * Design goals:
 * - Hosted-safe for many users: do NOT spam Bags quotes every tick.
 * - Fast + reliable: price polling and trigger detection runs in a Web Worker.
 * - Self-custody: we never touch user keys on the server.
 *
 * Execution modes:
 * - Phantom mode: when a trigger hits, we mark `exitPending` and the user clicks Approve.
 * - Session wallet mode: we auto-sign and execute the sell immediately via Bags (no popup).
 */
export function useAutomatedRiskManagement() {
  const { connected, address, signTransaction } = usePhantomWallet();
  const positions = useSniperStore((s) => s.positions);
  const config = useSniperStore((s) => s.config);
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const setPositionClosing = useSniperStore((s) => s.setPositionClosing);
  const updatePosition = useSniperStore((s) => s.updatePosition);
  const closePosition = useSniperStore((s) => s.closePosition);
  const addExecution = useSniperStore((s) => s.addExecution);

  const connectionRef = useRef<Connection | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const inFlightRef = useRef<Set<string>>(new Set());
  const sweepInFlightRef = useRef<Promise<string | null> | null>(null);
  const handleTriggerRef = useRef<(id: string, trigger: TriggerType, pnlPct: number) => Promise<void>>(
    async () => {},
  );

  function getConnection(): Connection {
    if (!connectionRef.current) {
      connectionRef.current = new Connection(RPC_URL, 'confirmed');
    }
    return connectionRef.current;
  }

  // Boot the risk worker once.
  useEffect(() => {
    if (workerRef.current) return;

    const worker = new Worker(new URL('../workers/risk.worker.ts', import.meta.url), { type: 'module' });
    workerRef.current = worker;

    worker.onmessage = (event: MessageEvent<any>) => {
      const msg = event.data;
      if (!msg || typeof msg !== 'object') return;

      if (msg.type === 'PRICE_UPDATE' && Array.isArray(msg.updates)) {
        const updates: Array<{ id: string; priceUsd: number; pnlPct: number; hwmPct: number }> = msg.updates;
        const byId = new Map(updates.map((u) => [u.id, u]));

        // Batch-apply to the store to keep UI + trailing state in sync.
        useSniperStore.setState((s) => ({
          positions: s.positions.map((p) => {
            const u = byId.get(p.id);
            if (!u || p.status !== 'open' || p.isClosing) return p;
            // SOL-denominated P&L: use actual token holdings + SOL price for real positions
            const solPrice = s.lastSolPriceUsd;
            const pnlSol = solPrice > 0 && p.amountLamports && p.amount > 0
              ? (p.amount * u.priceUsd) / solPrice - p.solInvested
              : p.solInvested * (u.pnlPct / 100);
            return {
              ...p,
              currentPrice: u.priceUsd,
              pnlPercent: u.pnlPct,
              pnlSol,
              highWaterMarkPct: Math.max(p.highWaterMarkPct ?? 0, u.hwmPct),
            };
          }),
        }));
        return;
      }

      if (msg.type === 'TRIGGER' && msg.id && msg.trigger) {
        void handleTriggerRef.current(msg.id as string, msg.trigger as TriggerType, msg.pnlPct as number);
      }
    };

    return () => {
      worker.terminate();
      workerRef.current = null;
    };
  }, []);

  // Keep worker synced with the current open positions + thresholds.
  useEffect(() => {
    const worker = workerRef.current;
    if (!worker) return;

    const useRec = config.useRecommendedExits !== false;

    const open = positions.filter((p) => p.status === 'open' && !p.isClosing);
    const workerPositions = open.map((p) => {
      const isBlueChip = isBlueChipLongConvictionSymbol(p.symbol);

      // Blue-chip "long conviction" positions should still get price/PnL updates,
      // but never trigger automated exits.
      const sl = isBlueChip ? 0 : (useRec ? (p.recommendedSl ?? config.stopLossPct) : config.stopLossPct);
      const tp = isBlueChip ? 0 : (useRec ? (p.recommendedTp ?? config.takeProfitPct) : config.takeProfitPct);
      const trail = isBlueChip ? 0 : (p.recommendedTrail ?? config.trailingStopPct);
      const maxAgeHours = isBlueChip ? 0 : (config.maxPositionAgeHours ?? 0);

      return {
        id: p.id,
        mint: p.mint,
        entryPriceUsd: p.entryPrice,
        slPct: sl,
        tpPct: tp,
        trailPct: trail,
        hwmPct: p.highWaterMarkPct ?? 0,
        entryTime: p.entryTime,
        maxAgeHours,
      };
    });

    if (workerPositions.length === 0) {
      worker.postMessage({ type: 'STOP' });
      return;
    }

    worker.postMessage({
      type: 'SYNC',
      positions: workerPositions,
      intervalMs: WORKER_INTERVAL_MS,
    });
  }, [positions, config, tradeSignerMode, sessionWalletPubkey]);

  async function handleTrigger(id: string, trigger: TriggerType, pnlPct: number) {
    const state = useSniperStore.getState();
    const pos = state.positions.find((p) => p.id === id);
    if (!pos || pos.status !== 'open') return;
    if (pos.isClosing) return;
    if (inFlightRef.current.has(id)) return;

    if (isBlueChipLongConvictionSymbol(pos.symbol)) return;

    const useRec = state.config.useRecommendedExits !== false;
    const sl = useRec ? (pos.recommendedSl ?? state.config.stopLossPct) : state.config.stopLossPct;
    const tp = useRec ? (pos.recommendedTp ?? state.config.takeProfitPct) : state.config.takeProfitPct;
    const trailPct = pos.recommendedTrail ?? state.config.trailingStopPct;

    // If we're not using session wallet signing, we can't auto-execute: mark exit pending.
    const session = tradeSignerMode === 'session' ? loadSessionWalletFromStorage() : null;
    const canAuto =
      tradeSignerMode === 'session' &&
      !!sessionWalletPubkey &&
      !!session &&
      session.publicKey === sessionWalletPubkey &&
      pos.walletAddress === sessionWalletPubkey;

    if (!canAuto) {
      // Manual mode: show activation clearly, but avoid spamming the store/log every tick.
      const now = Date.now();
      const existing = pos.exitPending;
      const sameTrigger = !!existing && existing.trigger === trigger;
      const recentlyUpdated = sameTrigger && now - existing.updatedAt < 5_000;

      if (!recentlyUpdated) {
        updatePosition(id, {
          exitPending: {
            trigger,
            pnlPercent: pnlPct,
            quoteAvailable: false,
            reason: 'Auto-exec requires Session Wallet mode. Click Approve to sell with Phantom.',
            updatedAt: now,
          },
        });
      }

      if (!sameTrigger) {
        addExecution({
          id: `risk-${Date.now()}-${id.slice(-4)}`,
          type: 'exit_pending',
          symbol: pos.symbol,
          mint: pos.mint,
          amount: pos.solInvested,
          pnlPercent: pnlPct,
          reason: `${triggerLabel(trigger, trailPct, pos.highWaterMarkPct)} hit at ${pnlPct.toFixed(1)}% — click Approve in Positions to sell`,
          timestamp: Date.now(),
        });
      }
      return;
    }

    // Auto-execute via Bags (session wallet signs).
    inFlightRef.current.add(id);
    setPositionClosing(id, true);
    updatePosition(id, { exitPending: undefined });

    try {
      const connection = getConnection();

      // Determine token amount (prefer recorded out amount, clamp to wallet balance).
      let amountLamports = pos.amountLamports;
      const bal = await getOwnerTokenBalanceLamports(connection, sessionWalletPubkey!, pos.mint);
      if (!amountLamports || amountLamports === '0') {
        if (!bal || bal.amountLamports === '0') throw new Error('No token balance found to sell');
        amountLamports = bal.amountLamports;
        updatePosition(id, { amountLamports });
      } else if (bal && bal.amountLamports !== '0') {
        const clamped = minLamportsString(amountLamports, bal.amountLamports);
        if (clamped !== amountLamports) {
          amountLamports = clamped;
          updatePosition(id, { amountLamports });
        }
      }

      // Fetch a realizable sell quote (slippage waterfall).
      // For SL/Trail/Expiry, we allow more slippage to maximize exit probability on micro-caps.
      const slippageBase = state.config.slippageBps;
      const waterfall = [
        slippageBase,
        Math.max(slippageBase, 300),
        Math.max(slippageBase, 500),
        Math.max(slippageBase, 1000),
        1500,
        ...(trigger === 'sl_hit' || trigger === 'trail_stop' || trigger === 'expired'
          ? [3000, 5000, 10_000]
          : []),
      ]
        .filter((n, i, arr) => Number.isFinite(n) && n > 0 && arr.indexOf(n) === i)
        .sort((a, b) => a - b);

      let quote = null as Awaited<ReturnType<typeof getSellQuote>>;
      for (const bps of waterfall) {
        quote = await getSellQuote(pos.mint, amountLamports, bps);
        if (quote) break;
      }

      if (!quote) {
        updatePosition(id, {
          exitPending: {
            trigger,
            pnlPercent: pnlPct,
            quoteAvailable: false,
            reason: 'Quote unavailable (no route / liquidity pulled). Try Write Off or manual exit.',
            updatedAt: Date.now(),
          },
          isClosing: false,
        });
        addExecution({
          id: `auto-quote-${Date.now()}-${id.slice(-4)}`,
          type: 'error',
          symbol: pos.symbol,
          mint: pos.mint,
          amount: pos.solInvested,
          reason: `${triggerLabel(trigger, trailPct, pos.highWaterMarkPct)} reached but no sell quote found (liquidity may be gone).`,
          timestamp: Date.now(),
        });
        return;
      }

      const exitValueSol = Number(BigInt(quote.outAmount)) / 1e9;

      const signWithSession = async (tx: VersionedTransaction) => {
        tx.sign([session!.keypair]);
        return tx;
      };

      // Priority fee: small bump on emergency exits to reduce timeout risk.
      const priorityFeeMicroLamports =
        trigger === 'tp_hit' ? 200_000 : 350_000;

      const result = await executeSwapFromQuote(
        connection,
        sessionWalletPubkey!,
        quote,
        signWithSession,
        state.config.useJito,
        priorityFeeMicroLamports,
      );

      if (!result.success) throw new Error(result.error || 'Sell failed');

      closePosition(id, trigger, result.txHash, exitValueSol);

      // Auto-sweep profits back to the main wallet (banks gains, limits blast radius).
      // We leave enough SOL behind for remaining budget + fees.
      if (!sweepInFlightRef.current) {
        const s = useSniperStore.getState();
        const remaining = typeof s.budgetRemaining === 'function'
          ? s.budgetRemaining()
          : Math.round((s.budget.budgetSol - s.budget.spent) * 1000) / 1000;
        const reserve = Math.max(0.01, remaining + 0.002);

        sweepInFlightRef.current = sweepExcessToMainWallet(session!.keypair, session!.mainWallet, reserve)
          .then((sig) => {
            if (sig) {
              addExecution({
                id: `sweep-${Date.now()}-${id.slice(-4)}`,
                type: 'info',
                symbol: pos.symbol,
                mint: pos.mint,
                amount: 0,
                reason: `Auto-swept excess SOL to main wallet (reserve ${reserve.toFixed(3)} SOL)`,
                txHash: sig,
                timestamp: Date.now(),
              });
            }
            return sig;
          })
          .catch(() => null)
          .finally(() => {
            sweepInFlightRef.current = null;
          });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setPositionClosing(id, false);
      updatePosition(id, {
        exitPending: {
          trigger,
          pnlPercent: pnlPct,
          quoteAvailable: false,
          reason: `Auto-exit failed: ${msg}`,
          updatedAt: Date.now(),
        },
      });
      addExecution({
        id: `auto-fail-${Date.now()}-${id.slice(-4)}`,
        type: 'error',
        symbol: pos.symbol,
        mint: pos.mint,
        amount: pos.solInvested,
        reason: `Auto-exit failed: ${msg}`,
        timestamp: Date.now(),
      });
    } finally {
      inFlightRef.current.delete(id);
    }
  }

  // Ensure the worker always calls the latest trigger handler (avoids stale-closure bugs).
  useEffect(() => {
    handleTriggerRef.current = handleTrigger;
  });
}

function triggerLabel(trigger: TriggerType, trailPct: number, hwm: number | undefined): string {
  if (trigger === 'tp_hit') return 'TP';
  if (trigger === 'sl_hit') return 'SL';
  if (trigger === 'expired') return 'EXPIRED';
  return `TRAIL (HWM ${(hwm ?? 0).toFixed(1)}%)`;
}
