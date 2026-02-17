'use client';

import { useEffect, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { executeSwapFromQuote, getSellQuote, SOL_MINT } from '@/lib/bags-trading';
import { getOwnerTokenBalanceLamports, minLamportsString } from '@/lib/solana-tokens';
import { closeEmptyTokenAccountsForMint, loadSessionWalletByPublicKey, loadSessionWalletFromStorage } from '@/lib/session-wallet';
import { isBlueChipLongConvictionSymbol } from '@/lib/trade-plan';
import { filterOpenPositionsForActiveWallet, isPositionInActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { postTradeTelemetry } from '@/lib/autonomy/trade-telemetry-client';
const WORKER_INTERVAL_MS = 1500;
const EXIT_RETRY_BASE_MS = 1200;
const EXIT_RETRY_MAX_MS = 10_000;

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
  const registerPendingTx = useSniperStore((s) => s.registerPendingTx);
  const finalizePendingTx = useSniperStore((s) => s.finalizePendingTx);

  const connectionRef = useRef<Connection | null>(null);
  const workerRef = useRef<Worker | null>(null);
  const inFlightRef = useRef<Set<string>>(new Set());
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
      const trail = isBlueChip ? 0 : (useRec ? (p.recommendedTrail ?? config.trailingStopPct) : config.trailingStopPct);
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

  function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

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
    const trailPct = useRec ? (pos.recommendedTrail ?? state.config.trailingStopPct) : state.config.trailingStopPct;
    const triggerText = triggerLabel(trigger, trailPct, pos.highWaterMarkPct);
    const isEmergencyExit = trigger === 'sl_hit' || trigger === 'trail_stop' || trigger === 'expired';
    const maxAttempts = isEmergencyExit ? 3 : 2;

    const emitSellAttemptTelemetry = (args: {
      outcome: 'confirmed' | 'failed' | 'unresolved' | 'no_route';
      attempt: number;
      failureCode?: string | null;
      failureReason?: string | null;
      sellTxHash?: string | null;
    }) => {
      const s = useSniperStore.getState();
      postTradeTelemetry({
        schemaVersion: 1,
        eventType: 'sell_attempt',
        positionId: pos.id,
        mint: pos.mint,
        status: trigger,
        symbol: pos.symbol,
        walletAddress: pos.walletAddress ?? null,
        strategyId: pos.strategyId ?? null,
        entrySource: pos.entrySource ?? null,
        entryTime: pos.entryTime,
        exitTime: Date.now(),
        solInvested: pos.solInvested,
        executionOutcome: args.outcome,
        failureCode: args.failureCode || null,
        failureReason: args.failureReason || null,
        sellTxHash: args.sellTxHash || null,
        attemptIndex: args.attempt,
        includedInExecutionStats: true,
        tradeSignerMode: s.tradeSignerMode,
        sessionWalletPubkey: s.sessionWalletPubkey,
        activePreset: s.activePreset,
      });
    };

    const sessionOnlyAutoEnabled = String(
      process.env.NEXT_PUBLIC_SNIPER_SESSION_ONLY_AUTO || process.env.SNIPER_SESSION_ONLY_AUTO || 'true',
    ).toLowerCase() !== 'false';

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
      const now = Date.now();
      const existing = pos.exitPending;
      const sameTrigger = !!existing && existing.trigger === trigger;
      const recentlyUpdated = sameTrigger && now - existing.updatedAt < 5_000;
      const reason = sessionOnlyAutoEnabled
        ? 'Auto-exec requires Session Wallet mode with a valid session key. Click Approve to sell with Phantom.'
        : 'Auto-exec unavailable in current signer mode. Click Approve to sell with Phantom.';

      if (!recentlyUpdated) {
        updatePosition(id, {
          exitLifecycle: 'trigger_detected',
          lastExitAttemptAt: now,
          lastExitError: reason,
          exitPending: {
            trigger,
            pnlPercent: pnlPct,
            quoteAvailable: false,
            reason,
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
          reason: `${triggerText} hit at ${pnlPct.toFixed(1)}% — click Approve in Positions to sell`,
          timestamp: Date.now(),
        });
      }
      return;
    }

    inFlightRef.current.add(id);
    setPositionClosing(id, true);
    updatePosition(id, {
      exitPending: undefined,
      exitLifecycle: 'trigger_detected',
      lastExitError: undefined,
    });

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

      const slippageBase = state.config.slippageBps;
      const waterfall = [
        slippageBase,
        Math.max(slippageBase, 300),
        Math.max(slippageBase, 500),
        Math.max(slippageBase, 1000),
        1500,
        ...(isEmergencyExit ? [3000, 5000, 10_000] : []),
      ]
        .filter((n, i, arr) => Number.isFinite(n) && n > 0 && arr.indexOf(n) === i)
        .sort((a, b) => a - b);

      const signWithSession = async (tx: VersionedTransaction) => {
        tx.sign([session!.keypair]);
        return tx;
      };
      const priorityFeeMicroLamports = trigger === 'tp_hit' ? 200_000 : 350_000;
      let lastError = 'Auto-exit failed';

      for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        const attemptAt = Date.now();
        updatePosition(id, {
          exitLifecycle: 'quote_attempting',
          exitAttempts: attempt,
          lastExitAttemptAt: attemptAt,
          lastExitError: undefined,
        });

        let quote = null as Awaited<ReturnType<typeof getSellQuote>>;
        for (const bps of waterfall) {
          quote = await getSellQuote(pos.mint, amountLamports, bps);
          if (quote) break;
        }

        if (!quote) {
          lastError = 'Quote unavailable (no route / liquidity pulled).';
          emitSellAttemptTelemetry({
            outcome: 'no_route',
            attempt,
            failureCode: 'no_route',
            failureReason: lastError,
          });
          if (attempt < maxAttempts) {
            const delayMs = Math.min(EXIT_RETRY_MAX_MS, EXIT_RETRY_BASE_MS * (2 ** (attempt - 1)));
            addExecution({
              id: `auto-retry-${Date.now()}-${id.slice(-4)}`,
              type: 'info',
              symbol: pos.symbol,
              mint: pos.mint,
              amount: pos.solInvested,
              reason: `${triggerText}: no quote route on attempt ${attempt}/${maxAttempts}, retrying in ${(delayMs / 1000).toFixed(1)}s`,
              timestamp: Date.now(),
            });
            await sleep(delayMs);
            continue;
          }

          setPositionClosing(id, false);
          updatePosition(id, {
            exitLifecycle: 'swap_failed',
            lastExitError: lastError,
            pendingSellState: undefined,
            exitPending: {
              trigger,
              pnlPercent: pnlPct,
              quoteAvailable: false,
              reason: `${lastError} Try Write Off or manual exit.`,
              updatedAt: Date.now(),
            },
          });
          addExecution({
            id: `auto-quote-${Date.now()}-${id.slice(-4)}`,
            type: 'error',
            symbol: pos.symbol,
            mint: pos.mint,
            amount: pos.solInvested,
            reason: `${triggerText} reached but no sell quote found after ${attempt} attempt${attempt === 1 ? '' : 's'} (liquidity may be gone).`,
            timestamp: Date.now(),
          });
          return;
        }

        const exitValueSol = Number(BigInt(quote.outAmount)) / 1e9;
        const result = await executeSwapFromQuote(
          connection,
          sessionWalletPubkey!,
          quote,
          signWithSession,
          state.config.useJito,
          priorityFeeMicroLamports,
        );

        const txHash = String(result.txHash || '').trim();
        if (txHash) {
          registerPendingTx({
            signature: txHash,
            kind: 'sell',
            mint: pos.mint,
            positionId: id,
            submittedAt: Date.now(),
            status: 'submitted',
            sourcePage: 'risk:auto',
          });
          updatePosition(id, {
            exitLifecycle: 'swap_submitted',
            pendingSellTxHash: txHash,
            pendingSellSubmittedAt: Date.now(),
            pendingSellState: 'submitted',
            lastExitAttemptAt: Date.now(),
          });
        }

        if (result.success) {
          if (txHash) {
            finalizePendingTx(txHash, 'confirmed');
          }
          closePosition(id, trigger, result.txHash, exitValueSol);
          emitSellAttemptTelemetry({
            outcome: 'confirmed',
            attempt,
            sellTxHash: txHash || null,
          });

          // Reclaim rent by closing the now-empty token account(s) for this mint (session wallet only).
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

          // Also close any now-empty WSOL temp accounts.
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
              // ignore WSOL cleanup errors
            }
          }
          return;
        }

        lastError = result.error || result.failureDetail || 'Sell failed';
        const confirmationState = result.confirmationState || (result.failureCode === 'unresolved' ? 'unresolved' : undefined);

        if (txHash) {
          if (confirmationState === 'unresolved') {
            finalizePendingTx(txHash, 'unresolved', lastError);
            updatePosition(id, {
              exitLifecycle: 'swap_unresolved',
              pendingSellTxHash: txHash,
              pendingSellSubmittedAt: Date.now(),
              pendingSellState: 'unresolved',
              lastExitError: lastError,
              exitPending: {
                trigger,
                pnlPercent: pnlPct,
                quoteAvailable: true,
                reason: `Sell submitted (${txHash.slice(0, 8)}...) but unresolved. Awaiting reconciliation.`,
                updatedAt: Date.now(),
              },
            });
            setPositionClosing(id, false);
            emitSellAttemptTelemetry({
              outcome: 'unresolved',
              attempt,
              failureCode: result.failureCode || 'unresolved',
              failureReason: lastError,
              sellTxHash: txHash,
            });
            addExecution({
              id: `auto-unresolved-${Date.now()}-${id.slice(-4)}`,
              type: 'error',
              symbol: pos.symbol,
              mint: pos.mint,
              amount: pos.solInvested,
              txHash,
              reason: `${triggerText} sell unresolved; holding row open until balance reconciliation confirms exit.`,
              timestamp: Date.now(),
            });
            return;
          }
          finalizePendingTx(txHash, 'failed', lastError);
          updatePosition(id, {
            exitLifecycle: 'swap_failed',
            pendingSellTxHash: txHash,
            pendingSellSubmittedAt: Date.now(),
            pendingSellState: 'failed',
            lastExitError: lastError,
          });
        }

        emitSellAttemptTelemetry({
          outcome: 'failed',
          attempt,
          failureCode: result.failureCode || 'swap_failed',
          failureReason: lastError,
          sellTxHash: txHash || null,
        });

        if (attempt < maxAttempts) {
          const delayMs = Math.min(EXIT_RETRY_MAX_MS, EXIT_RETRY_BASE_MS * (2 ** (attempt - 1)));
          addExecution({
            id: `auto-retry-${Date.now()}-${id.slice(-4)}`,
            type: 'info',
            symbol: pos.symbol,
            mint: pos.mint,
            amount: pos.solInvested,
            txHash: txHash || undefined,
            reason: `${triggerText}: sell failed on attempt ${attempt}/${maxAttempts} (${lastError}). Retrying in ${(delayMs / 1000).toFixed(1)}s.`,
            timestamp: Date.now(),
          });
          await sleep(delayMs);
          continue;
        }

        setPositionClosing(id, false);
        updatePosition(id, {
          exitLifecycle: 'swap_failed',
          lastExitError: lastError,
          exitPending: {
            trigger,
            pnlPercent: pnlPct,
            quoteAvailable: true,
            reason: `Auto-exit failed after ${attempt} attempts: ${lastError}`,
            updatedAt: Date.now(),
          },
        });
        addExecution({
          id: `auto-fail-${Date.now()}-${id.slice(-4)}`,
          type: 'error',
          symbol: pos.symbol,
          mint: pos.mint,
          amount: pos.solInvested,
          reason: `Auto-exit failed after ${attempt} attempts: ${lastError}`,
          timestamp: Date.now(),
        });
        return;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setPositionClosing(id, false);
      updatePosition(id, {
        exitLifecycle: 'swap_failed',
        lastExitError: msg,
        exitPending: {
          trigger,
          pnlPercent: pnlPct,
          quoteAvailable: false,
          reason: `Auto-exit failed: ${msg}`,
          updatedAt: Date.now(),
        },
      });
      emitSellAttemptTelemetry({
        outcome: 'failed',
        attempt: Math.max(1, Number(pos.exitAttempts || 0)),
        failureCode: 'exception',
        failureReason: msg,
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
