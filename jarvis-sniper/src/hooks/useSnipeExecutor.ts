'use client';

import { useCallback, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore, getRecommendedSlTp, type Position, type ExecutionEvent } from '@/stores/useSniperStore';
import { executeSwap, SOL_MINT, type SwapResult } from '@/lib/bags-trading';
import type { BagsGraduation } from '@/lib/bags-api';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';

let execCounter = 0;

/**
 * Hook that wires real on-chain swap execution to the sniper store.
 * Call `snipe(grad)` to: get quote → sign with Phantom → send tx → track position.
 */
export function useSnipeExecutor() {
  const { address, connected, signTransaction } = usePhantomWallet();
  const store = useSniperStore();
  const connectionRef = useRef<Connection | null>(null);
  const pendingRef = useRef<Set<string>>(new Set());

  // Lazy-init connection
  function getConnection(): Connection {
    if (!connectionRef.current) {
      connectionRef.current = new Connection(RPC_URL, 'confirmed');
    }
    return connectionRef.current;
  }

  const snipe = useCallback(async (grad: BagsGraduation & Record<string, any>) => {
    const { config, positions, snipedMints, budget, addPosition, addExecution } = useSniperStore.getState();

    // --- Pre-flight guards ---
    if (!connected || !address) {
      addExecution(makeExecEvent(grad, 'error', 0, 'Wallet not connected'));
      return;
    }
    if (!budget.authorized) {
      addExecution(makeExecEvent(grad, 'error', 0, 'Budget not authorized'));
      return;
    }
    if (snipedMints.has(grad.mint)) return;
    if (pendingRef.current.has(grad.mint)) return; // already in-flight

    const openCount = positions.filter(p => p.status === 'open').length;
    if (openCount >= config.maxConcurrentPositions) {
      addExecution(makeExecEvent(grad, 'skip', 0, 'At max positions'));
      return;
    }

    const remaining = budget.budgetSol - budget.spent;
    const positionSol = Math.min(config.maxPositionSol, remaining);
    if (positionSol < 0.001) {
      addExecution(makeExecEvent(grad, 'skip', 0, 'Insufficient budget'));
      return;
    }

    // Mark as pending to prevent double-snipe
    pendingRef.current.add(grad.mint);

    // Mark sniped immediately in store to block duplicates
    const newSniped = new Set(useSniperStore.getState().snipedMints);
    newSniped.add(grad.mint);
    useSniperStore.setState({ snipedMints: newSniped });

    const rec = getRecommendedSlTp(grad);

    // Log that we're attempting
    addExecution(makeExecEvent(grad, 'snipe', positionSol,
      `Executing swap... ${positionSol.toFixed(3)} SOL → ${grad.symbol} | Score ${grad.score} | SL ${rec.sl}% TP ${rec.tp}%`));

    try {
      const connection = getConnection();

      const result: SwapResult = await executeSwap(
        connection,
        address,
        SOL_MINT,
        grad.mint,
        positionSol,
        config.slippageBps,
        signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
        config.useJito,
      );

      if (!result.success) {
        addExecution(makeExecEvent(grad, 'error', positionSol, `Swap failed: ${result.error}`));
        // Un-mark sniped so user can retry
        const revert = new Set(useSniperStore.getState().snipedMints);
        revert.delete(grad.mint);
        useSniperStore.setState({ snipedMints: revert });
        return;
      }

      // Success — create real position
      const posId = `pos-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const entryPrice = grad.price_usd || (positionSol / Math.max(result.outputAmount, 0.000001));

      const newPosition: Position = {
        id: posId,
        mint: grad.mint,
        symbol: grad.symbol,
        name: grad.name,
        entryPrice,
        currentPrice: entryPrice,
        amount: result.outputAmount,
        solInvested: positionSol,
        pnlPercent: 0,
        pnlSol: 0,
        entryTime: Date.now(),
        txHash: result.txHash,
        status: 'open',
        score: grad.score,
        recommendedSl: rec.sl,
        recommendedTp: rec.tp,
      };

      addPosition(newPosition);

      // Update budget spent
      useSniperStore.setState((s) => ({
        budget: { ...s.budget, spent: s.budget.spent + positionSol },
      }));

      // Log success
      addExecution({
        ...makeExecEvent(grad, 'snipe', positionSol,
          `Sniped ${grad.symbol} for ${positionSol.toFixed(3)} SOL | Got ${result.outputAmount.toFixed(2)} tokens | SL ${rec.sl}% TP ${rec.tp}%`),
        txHash: result.txHash,
        price: entryPrice,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      addExecution(makeExecEvent(grad, 'error', positionSol, `Exception: ${msg}`));
      // Un-mark sniped
      const revert = new Set(useSniperStore.getState().snipedMints);
      revert.delete(grad.mint);
      useSniperStore.setState({ snipedMints: revert });
    } finally {
      pendingRef.current.delete(grad.mint);
    }
  }, [connected, address, signTransaction]);

  return { snipe, ready: connected && !!address };
}

function makeExecEvent(
  grad: BagsGraduation & Record<string, any>,
  type: ExecutionEvent['type'],
  amount: number,
  reason: string,
): ExecutionEvent {
  execCounter++;
  return {
    id: `exec-${Date.now()}-${execCounter}`,
    type,
    symbol: grad.symbol,
    mint: grad.mint,
    amount,
    price: grad.price_usd,
    reason,
    timestamp: Date.now(),
  };
}
