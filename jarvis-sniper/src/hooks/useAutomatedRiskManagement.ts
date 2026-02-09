'use client';

import { useEffect, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { getSellQuote, executeSwapFromQuote, SOL_MINT } from '@/lib/bags-trading';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const CHECK_INTERVAL_MS = 2000;

/**
 * Automated SL/TP execution loop.
 *
 * Strategy: "Quote-Based Monitoring"
 * Instead of relying on chart prices (which don't account for slippage),
 * we fetch a Jupiter sell quote to determine the *realizable* exit value.
 * If the P&L hits the SL or TP threshold, we execute the sell immediately
 * using that exact quote.
 *
 * Semi-automated: Phantom will still pop up for user approval.
 * The loop detects the trigger and initiates the transaction.
 */
export function useAutomatedRiskManagement() {
  const { connected, address, signTransaction } = usePhantomWallet();
  const positions = useSniperStore((s) => s.positions);
  const config = useSniperStore((s) => s.config);
  const setPositionClosing = useSniperStore((s) => s.setPositionClosing);
  const closePosition = useSniperStore((s) => s.closePosition);
  const addExecution = useSniperStore((s) => s.addExecution);

  const isCheckingRef = useRef(false);
  const connectionRef = useRef<Connection | null>(null);

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
        const activePositions = currentState.positions.filter(
          (p) => p.status === 'open' && !p.isClosing
        );

        if (activePositions.length === 0) return;

        for (const pos of activePositions) {
          // Use per-position recommended SL/TP, falling back to global config
          const slThreshold = pos.recommendedSl ?? currentState.config.stopLossPct;
          const tpThreshold = pos.recommendedTp ?? currentState.config.takeProfitPct;

          // Skip if no amount data to sell
          if (!pos.amountLamports && pos.amount <= 0) continue;

          // Check using current price from DexScreener (set by usePnlTracker)
          // This is a fast preliminary check before doing the expensive quote
          const quickPnl = pos.pnlPercent;
          const nearSl = quickPnl <= -(slThreshold * 0.8); // within 80% of SL
          const nearTp = quickPnl >= (tpThreshold * 0.8); // within 80% of TP

          // Only fetch expensive sell quote when close to triggers
          if (!nearSl && !nearTp) continue;

          // Fetch a real sell quote to get realizable value
          const amountStr = pos.amountLamports || Math.floor(pos.amount * 1e9).toString();
          const sellQuote = await getSellQuote(pos.mint, amountStr, config.slippageBps);

          if (!sellQuote) {
            // No route — token may have lost liquidity
            if (quickPnl <= -slThreshold) {
              // Flag in execution log but don't close (can't sell)
              addExecution({
                id: `risk-${Date.now()}-${pos.id.slice(-4)}`,
                type: 'error',
                symbol: pos.symbol,
                mint: pos.mint,
                amount: pos.solInvested,
                reason: `SL triggered but no sell route — liquidity may be pulled`,
                timestamp: Date.now(),
              });
            }
            continue;
          }

          // Calculate real P&L from quote
          const exitValueSol = parseInt(sellQuote.outAmount) / 1e9;
          const realPnlPct = ((exitValueSol - pos.solInvested) / pos.solInvested) * 100;

          const hitSl = realPnlPct <= -slThreshold;
          const hitTp = realPnlPct >= tpThreshold;

          if (!hitSl && !hitTp) continue;

          const triggerType = hitTp ? 'tp_hit' : 'sl_hit';
          console.log(
            `[Risk] ${triggerType.toUpperCase()} ${pos.symbol}: ${realPnlPct.toFixed(1)}% (threshold: ${hitTp ? tpThreshold : slThreshold}%)`
          );

          // Lock position to prevent duplicate sell attempts
          setPositionClosing(pos.id, true);

          // Log the trigger
          addExecution({
            id: `risk-${Date.now()}-${pos.id.slice(-4)}`,
            type: hitTp ? 'tp_exit' : 'sl_exit',
            symbol: pos.symbol,
            mint: pos.mint,
            amount: pos.solInvested,
            pnlPercent: realPnlPct,
            reason: `${hitTp ? 'TP' : 'SL'} triggered at ${realPnlPct.toFixed(1)}% — executing sell (${exitValueSol.toFixed(4)} SOL)`,
            timestamp: Date.now(),
          });

          try {
            const connection = getConnection();
            const result = await executeSwapFromQuote(
              connection,
              address,
              sellQuote,
              signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
              config.useJito,
            );

            if (result.success) {
              closePosition(pos.id, triggerType, result.txHash);
              console.log(`[Risk] Sold ${pos.symbol} — tx: ${result.txHash}`);
            } else {
              // Release lock so it can retry
              setPositionClosing(pos.id, false);
              addExecution({
                id: `risk-fail-${Date.now()}-${pos.id.slice(-4)}`,
                type: 'error',
                symbol: pos.symbol,
                mint: pos.mint,
                amount: pos.solInvested,
                reason: `Auto-sell failed: ${result.error}`,
                timestamp: Date.now(),
              });
            }
          } catch (err) {
            setPositionClosing(pos.id, false);
            const msg = err instanceof Error ? err.message : 'Unknown error';
            console.error(`[Risk] Sell error for ${pos.symbol}:`, msg);
          }
        }
      } finally {
        isCheckingRef.current = false;
      }
    };

    const interval = setInterval(checkRisk, CHECK_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [connected, address, signTransaction, positions, config, setPositionClosing, closePosition, addExecution]);
}
