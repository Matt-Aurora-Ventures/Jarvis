'use client';

import { useEffect, useRef } from 'react';
import { Connection } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { getSellQuote } from '@/lib/bags-trading';
import { getOwnerTokenBalanceLamports, minLamportsString } from '@/lib/solana-tokens';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const CHECK_INTERVAL_MS = 2000;
// Background quote cadence: ensures SL/TP still works even if DexScreener prices are missing/stale.
const QUOTE_BG_INTERVAL_MS = 12_000;
const QUOTE_BG_INTERVAL_NO_PRICE_MS = 5_000;
const MAX_BG_QUOTES_PER_TICK = 2;
const QUOTE_ERROR_LOG_TTL_MS = 60_000;

/**
 * Automated SL/TP execution loop.
 *
 * Strategy: "Quote-Based Monitoring"
 * Instead of relying on chart prices (which don't account for slippage),
 * we fetch a Bags sell quote (via server proxy) to determine the *realizable* exit value.
 * If the P&L hits the SL/TP/trailing threshold, we mark the position as "Exit Pending".
 * The UI then prompts the user to click Approve to open Phantom (reliable user gesture).
 *
 * Non-custodial: we never auto-sign or custody keys. This tab just monitors and alerts.
 */
export function useAutomatedRiskManagement() {
  const { connected, address } = usePhantomWallet();

  const isCheckingRef = useRef(false);
  const connectionRef = useRef<Connection | null>(null);
  const lastQuoteAtRef = useRef<Map<string, number>>(new Map());
  const lastQuoteErrAtRef = useRef<Map<string, number>>(new Map());

  function getConnection(): Connection {
    if (!connectionRef.current) {
      connectionRef.current = new Connection(RPC_URL, 'confirmed');
    }
    return connectionRef.current;
  }

  useEffect(() => {
    if (!connected || !address) return;

    const checkRisk = async () => {
      if (isCheckingRef.current) return;
      isCheckingRef.current = true;

      try {
        const currentState = useSniperStore.getState();
        const { config, addExecution, updatePosition } = currentState;
        const useRecommendedExits = config.useRecommendedExits !== false;
        const activePositions = currentState.positions.filter(
          (p) => p.status === 'open' && !p.isClosing
        );

        if (activePositions.length === 0) return;

        const now = Date.now();

        // Decide which positions get quoted this tick:
        // 1) Any position "near" a trigger (based on fast DexScreener PnL).
        // 2) A small number of stale positions (quote heartbeat) so we don't miss stops when price feeds fail.
        const urgent = new Set<string>();
        const stale: Array<{ pos: typeof activePositions[number]; last: number; desired: number }> = [];

        for (const pos of activePositions) {
          // Use per-position recommended SL/TP, or force global exits when disabled.
          const slThreshold = useRecommendedExits ? (pos.recommendedSl ?? config.stopLossPct) : config.stopLossPct;
          const tpThreshold = useRecommendedExits ? (pos.recommendedTp ?? config.takeProfitPct) : config.takeProfitPct;
          const trailingStopPct = currentState.config.trailingStopPct;

          // Skip if no amount data to sell
          if (!pos.amountLamports && pos.amount <= 0) continue;

          // Check using current price from DexScreener (set by usePnlTracker)
          // This is a fast preliminary check before doing the expensive quote
          const quickPnl = pos.pnlPercent;
          const hwm = pos.highWaterMarkPct ?? 0;
          const nearSl = quickPnl <= -(slThreshold * 0.8); // within 80% of SL
          const nearTp = quickPnl >= (tpThreshold * 0.8); // within 80% of TP

          // Trailing stop: activated only when position has been in profit
          // Triggers when P&L drops trailingStopPct from the high water mark
          const trailActive = trailingStopPct > 0 && hwm > 0;
          const trailDrop = trailActive ? hwm - quickPnl : 0;
          const nearTrail = trailActive && trailDrop >= (trailingStopPct * 0.8);

          const id = pos.id;
          const lastQuoteAt = lastQuoteAtRef.current.get(id) ?? 0;
          const hasUsefulQuickPnl = pos.entryPrice > 0;
          const desiredInterval = hasUsefulQuickPnl ? QUOTE_BG_INTERVAL_MS : QUOTE_BG_INTERVAL_NO_PRICE_MS;
          const quoteStale = now - lastQuoteAt >= desiredInterval;

          // Position age expiry: treat as urgent when past max age
          const maxAgeMs = (config.maxPositionAgeHours ?? 4) * 3600_000;
          const posAgeMs = now - pos.entryTime;
          const nearExpiry = maxAgeMs > 0 && posAgeMs >= maxAgeMs;

          const hasExitPending = !!pos.exitPending;
          if (nearSl || nearTp || nearTrail || nearExpiry || hasExitPending) {
            urgent.add(id);
          }
          if (quoteStale) {
            stale.push({ pos, last: lastQuoteAt, desired: desiredInterval });
          }
        }

        // Stale positions: oldest first, capped per tick (non-urgent).
        stale.sort((a, b) => a.last - b.last);
        const bgQueue = stale
          .filter((x) => !urgent.has(x.pos.id))
          .slice(0, Math.max(0, MAX_BG_QUOTES_PER_TICK));

        // Process: urgent first, then background.
        const ordered = [
          ...activePositions.filter((p) => urgent.has(p.id)),
          ...bgQueue.map((x) => x.pos),
        ];

        if (ordered.length === 0) return;

        for (const pos of ordered) {
          const connection = getConnection();

          // Use per-position recommended SL/TP, or force global exits when disabled.
          const slThreshold = useRecommendedExits ? (pos.recommendedSl ?? config.stopLossPct) : config.stopLossPct;
          const tpThreshold = useRecommendedExits ? (pos.recommendedTp ?? config.takeProfitPct) : config.takeProfitPct;
          const trailingStopPct = currentState.config.trailingStopPct;

          // Track quote attempt so we don't spam Bags when DexScreener is missing.
          lastQuoteAtRef.current.set(pos.id, now);

          // Fetch a real sell quote to get realizable value
          let amountStr = pos.amountLamports;

          // If we don't have a reliable raw token amount, fetch from chain.
          // Also clamp to wallet balance to avoid "insufficient funds" if the recorded amount is stale.
          const bal = await getOwnerTokenBalanceLamports(connection, address, pos.mint);
          if (!amountStr || amountStr === '0') {
            if (!bal || bal.amountLamports === '0') continue;
            amountStr = bal.amountLamports;
            updatePosition(pos.id, { amountLamports: amountStr });
          } else if (bal && bal.amountLamports !== '0') {
            const clamped = minLamportsString(amountStr, bal.amountLamports);
            if (clamped !== amountStr) {
              amountStr = clamped;
              updatePosition(pos.id, { amountLamports: amountStr });
            }
          }

          const sellQuote = await getSellQuote(pos.mint, amountStr, config.slippageBps);

          if (!sellQuote) {
            // No route (or quote error). Token may have lost liquidity, or slippage may be too tight.
            const lastErr = lastQuoteErrAtRef.current.get(pos.id) ?? 0;
            if (now - lastErr >= QUOTE_ERROR_LOG_TTL_MS) {
              lastQuoteErrAtRef.current.set(pos.id, now);
              addExecution({
                id: `risk-quote-${Date.now()}-${pos.id.slice(-4)}`,
                type: 'error',
                symbol: pos.symbol,
                mint: pos.mint,
                amount: pos.solInvested,
                reason: `Could not get a sell quote (no route / slippage too low / liquidity pulled). Try higher slippage.`,
                timestamp: Date.now(),
              });
            }
            continue;
          }

          // Calculate real P&L from quote
          const exitValueSol = Number(BigInt(sellQuote.outAmount)) / 1e9;
          const realPnlPct = ((exitValueSol - pos.solInvested) / pos.solInvested) * 100;

          // Keep store P&L aligned with the realizable (quote-based) exit.
          const nextHwm = Math.max(pos.highWaterMarkPct ?? 0, realPnlPct);
          updatePosition(pos.id, {
            pnlPercent: realPnlPct,
            pnlSol: pos.solInvested * (realPnlPct / 100),
            highWaterMarkPct: nextHwm,
          });

          const hitSl = realPnlPct <= -slThreshold;
          const hitTp = realPnlPct >= tpThreshold;

          // Trailing stop: recalculate with real P&L and high water mark
          const realTrailDrop = trailingStopPct > 0 && nextHwm > 0 ? nextHwm - realPnlPct : 0;
          const hitTrail = trailingStopPct > 0 && nextHwm > 0 && realTrailDrop >= trailingStopPct;

          // Position age expiry: auto-close stale positions to free capital
          const maxAgeMs = (config.maxPositionAgeHours ?? 4) * 3600_000;
          const posAge = now - pos.entryTime;
          const hitExpiry = maxAgeMs > 0 && posAge >= maxAgeMs;

          if (!hitSl && !hitTp && !hitTrail && !hitExpiry) {
            // Clear any stale pending marker when the trigger is no longer met.
            if (pos.exitPending) updatePosition(pos.id, { exitPending: undefined });
            continue;
          }

          // Priority: TP > Trailing Stop > Expiry > SL
          const triggerType: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' = hitTp ? 'tp_hit' : hitTrail ? 'trail_stop' : hitExpiry ? 'expired' : 'sl_hit';
          const ageStr = `${(posAge / 3600_000).toFixed(1)}h`;
          console.log(
            `[Risk] ${triggerType.toUpperCase()} ${pos.symbol}: ${realPnlPct.toFixed(1)}% (${
              hitTp ? `TP ${tpThreshold}%` : hitTrail ? `trail ${trailingStopPct}% from HWM ${nextHwm.toFixed(1)}%` : hitExpiry ? `expired after ${ageStr}` : `SL ${slThreshold}%`
            })`
          );

          // Mark pending (user must click Approve to open Phantom reliably).
          const triggerLabel = hitTp ? 'TP' : hitTrail ? `TRAIL (HWM ${nextHwm.toFixed(1)}%)` : hitExpiry ? `EXPIRED (${ageStr})` : 'SL';
          updatePosition(pos.id, {
            exitPending: {
              trigger: triggerType,
              pnlPercent: realPnlPct,
              exitValueSol,
              updatedAt: now,
            },
          });

          // Log once per trigger transition to avoid spamming the execution log.
          if (!pos.exitPending || pos.exitPending.trigger !== triggerType) {
            addExecution({
              id: `risk-${Date.now()}-${pos.id.slice(-4)}`,
              type: 'exit_pending',
              symbol: pos.symbol,
              mint: pos.mint,
              amount: pos.solInvested,
              pnlPercent: realPnlPct,
              reason: `${triggerLabel} hit at ${realPnlPct.toFixed(1)}% — click Approve in Positions to sell (${exitValueSol.toFixed(4)} SOL quote)`,
              timestamp: Date.now(),
            });
          }
        }
      } finally {
        isCheckingRef.current = false;
      }
    };

    const interval = setInterval(checkRisk, CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [connected, address]);
}
