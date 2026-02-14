'use client';

import { useEffect, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { executeSwapFromQuote, getSellQuote, SOL_MINT } from '@/lib/bags-trading';
import { getOwnerTokenBalanceLamports, minLamportsString } from '@/lib/solana-tokens';
import { closeEmptyTokenAccountsForMint, loadSessionWalletByPublicKey, loadSessionWalletFromStorage, sweepExcessToMainWallet } from '@/lib/session-wallet';
import { isBlueChipLongConvictionSymbol } from '@/lib/trade-plan';
import { filterOpenPositionsForActiveWallet, isPositionInActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
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
      connectionRef.current = getSharedConnection();
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

    const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
    const open = filterOpenPositionsForActiveWallet(positions, activeWallet, { includeManualOnly: false }).filter((p) => !p.isClosing);
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
  }, [positions, config, tradeSignerMode, sessionWalletPubkey, address]);

  async function handleTrigger(id: string, trigger: TriggerType, pnlPct: number) {
    const state = useSniperStore.getState();
    if (state.operationLock.active && state.operationLock.mode === 'close_all') return;
    const pos = state.positions.find((p) => p.id === id);
    if (!pos || pos.status !== 'open') return;
    const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
    if (!isPositionInActiveWallet(pos, activeWallet)) return;
    if (pos.isClosing) return;
    if (pos.manualOnly) return;
    if (inFlightRef.current.has(id)) return;

    if (isBlueChipLongConvictionSymbol(pos.symbol)) return;

    const useRec = state.config.useRecommendedExits !== false;
    const sl = useRec ? (pos.recommendedSl ?? state.config.stopLossPct) : state.config.stopLossPct;
    const tp = useRec ? (pos.recommendedTp ?? state.config.takeProfitPct) : state.config.takeProfitPct;
    const trailPct = pos.recommendedTrail ?? state.config.trailingStopPct;

    // If we're not using session wallet signing, we can't auto-execute: mark exit pending.
    const session = tradeSignerMode === 'session'
      ? (
          sessionWalletPubkey
            ? await loadSessionWalletByPublicKey(sessionWalletPubkey, { mainWallet: address || undefined })
            : await loadSessionWalletFromStorage({ mainWallet: address || undefined })
        )
      : null;
    const canAuto =
      tradeSignerMode === 'session' &&
      !!sessionWalletPubkey &&
      !!session &&
      session.publicKey === sessionWalletPubkey &&
      pos.walletAddress === sessionWalletPubkey;

    if (canAuto) {
      const pending = pos.exitPending;
      if (pending && pending.trigger === trigger && Date.now() - pending.updatedAt < 45_000) {
        return;
      }
    }

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
        // For auto-managed entries, sell the full session-wallet balance so the token account can be closed.
        // Manual entries may represent multiple lots; keep the conservative clamp in that case.
        if (pos.entrySource === 'auto') {
          amountLamports = bal.amountLamports;
          updatePosition(id, { amountLamports });
        } else {
          const clamped = minLamportsString(amountLamports, bal.amountLamports);
          if (clamped !== amountLamports) {
            amountLamports = clamped;
            updatePosition(id, { amountLamports });
          }
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

      // Reclaim rent by closing the now-empty token account(s) for this mint (session wallet only).
      // Best-effort: if the wallet still has non-zero balance (dust/partial), it will be skipped.
      try {
        const cleanup = await closeEmptyTokenAccountsForMint(session!.keypair, pos.mint);
        if (cleanup.closedTokenAccounts > 0) {
          addExecution({
            id: `rent-${Date.now()}-${id.slice(-4)}`,
            type: 'info',
            symbol: pos.symbol,
            mint: pos.mint,
            amount: 0,
            txHash: cleanup.closeSignatures[0],
            reason: `Reclaimed ${(cleanup.reclaimedLamports / 1e9).toFixed(6)} SOL rent by closing ${cleanup.closedTokenAccounts} empty token account${cleanup.closedTokenAccounts === 1 ? '' : 's'}`,
            timestamp: Date.now(),
          });
        }
        if (cleanup.closedTokenAccounts === 0 && cleanup.skippedNonZeroTokenAccounts > 0) {
          addExecution({
            id: `rent-skip-${Date.now()}-${id.slice(-4)}`,
            type: 'info',
            symbol: pos.symbol,
            mint: pos.mint,
            amount: 0,
            reason: `Rent reclaim skipped: ${cleanup.skippedNonZeroTokenAccounts} token account${cleanup.skippedNonZeroTokenAccounts === 1 ? '' : 's'} still had non-zero balance (dust/partial exit).`,
            timestamp: Date.now(),
          });
        }
        if (cleanup.failedToCloseTokenAccounts > 0) {
          addExecution({
            id: `rent-fail-${Date.now()}-${id.slice(-4)}`,
            type: 'error',
            symbol: pos.symbol,
            mint: pos.mint,
            amount: 0,
            reason: `Rent reclaim incomplete: ${cleanup.failedToCloseTokenAccounts} empty token account${cleanup.failedToCloseTokenAccounts === 1 ? '' : 's'} failed to close; retry Sweep Back later.`,
            timestamp: Date.now(),
          });
        }
      } catch {
        // ignore rent reclaim errors (trade already closed)
      }

      // Also close any now-empty WSOL temp accounts. Some swap routes may touch WSOL as an
      // intermediate and leave behind a zero-balance account that can be closed for rent.
      if (pos.mint !== SOL_MINT) {
        try {
          const wsolCleanup = await closeEmptyTokenAccountsForMint(session!.keypair, SOL_MINT);
          if (wsolCleanup.closedTokenAccounts > 0) {
            addExecution({
              id: `rent-wsol-${Date.now()}-${id.slice(-4)}`,
              type: 'info',
              symbol: 'WSOL',
              mint: SOL_MINT,
              amount: 0,
              txHash: wsolCleanup.closeSignatures[0],
              reason: `Reclaimed ${(wsolCleanup.reclaimedLamports / 1e9).toFixed(6)} SOL rent by closing ${wsolCleanup.closedTokenAccounts} empty WSOL token account${wsolCleanup.closedTokenAccounts === 1 ? '' : 's'}`,
              timestamp: Date.now(),
            });
          }
          if (wsolCleanup.failedToCloseTokenAccounts > 0) {
            addExecution({
              id: `rent-wsol-fail-${Date.now()}-${id.slice(-4)}`,
              type: 'error',
              symbol: 'WSOL',
              mint: SOL_MINT,
              amount: 0,
              reason: `WSOL rent reclaim incomplete: ${wsolCleanup.failedToCloseTokenAccounts} empty token account${wsolCleanup.failedToCloseTokenAccounts === 1 ? '' : 's'} failed to close; retry Sweep Back later.`,
              timestamp: Date.now(),
            });
          }
        } catch {
          // ignore WSOL cleanup errors (trade already closed)
        }
      }

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
