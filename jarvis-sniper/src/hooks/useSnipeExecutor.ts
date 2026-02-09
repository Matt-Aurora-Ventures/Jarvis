'use client';

import { useCallback, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore, getRecommendedSlTp, getConvictionMultiplier, type Position, type ExecutionEvent } from '@/stores/useSniperStore';
import { executeSwap, SOL_MINT, type SwapResult, savePositionToServer } from '@/lib/bags-trading';
import type { BagsGraduation } from '@/lib/bags-api';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';

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
    // Conviction-weighted sizing: scale by signal quality (0.5x – 2.0x)
    const { multiplier: conviction, factors: convFactors } = getConvictionMultiplier(grad);
    const positionSol = Math.min(config.maxPositionSol * conviction, remaining);
    if (positionSol < 0.001) {
      addExecution(makeExecEvent(grad, 'skip', 0, 'Insufficient budget'));
      return;
    }

    // ═══ INSIGHT-DRIVEN FILTERS (928-token OHLCV: TRAIL_8 94.1% WR) ═══
    const liq = grad.liquidity || 0;
    if (liq < config.minLiquidityUsd) {
      addExecution(makeExecEvent(
        grad,
        'skip',
        0,
        `Low liquidity: $${Math.round(liq).toLocaleString()} < $${Math.round(config.minLiquidityUsd).toLocaleString()}`,
      ));
      return;
    }
    const buys = grad.txn_buys_1h || 0;
    const sells = grad.txn_sells_1h || 0;
    const bsRatio = sells > 0 ? buys / sells : buys;
    if (buys + sells > 10 && (bsRatio < 1.0 || bsRatio > 3.0)) {
      addExecution(makeExecEvent(grad, 'skip', 0, `B/S ratio ${bsRatio.toFixed(1)} outside 1.0-3.0`));
      return;
    }
    const ageHours = grad.age_hours || 0;
    if (ageHours > 500) {
      addExecution(makeExecEvent(grad, 'skip', 0, `Too old: ${Math.round(ageHours)}h > 500h`));
      return;
    }
    const change1h = grad.price_change_1h || 0;
    if (change1h < 0) {
      addExecution(makeExecEvent(grad, 'skip', 0, `Negative momentum: ${change1h.toFixed(1)}%`));
      return;
    }
    // Filter 5: Time-of-day (928-token OHLCV backtest — block hours with <18% WR)
    // Best: 4:00 (60%), 11:00 (57%), 21:00 (52%) | Worst: 3,5 (0%), 9 (8%), 23 (6%), 17 (15%), 1 (18%)
    const nowUtcHour = new Date().getUTCHours();
    const BAD_HOURS = [1, 3, 5, 9, 17, 23];
    if (BAD_HOURS.includes(nowUtcHour)) {
      addExecution(makeExecEvent(grad, 'skip', 0, `Bad hour: ${nowUtcHour}:00 UTC (928-token backtest <18% WR)`));
      return;
    }
    // Filter 6: Vol/Liq ratio ≥ 0.5 (8x edge: 40.6% upside vs 4.9% for <0.5)
    const vol24h = grad.volume_24h || 0;
    const volLiqRatio = liq > 0 ? vol24h / liq : 0;
    if (vol24h > 0 && volLiqRatio < 0.5) {
      addExecution(makeExecEvent(grad, 'skip', 0, `Low Vol/Liq: ${volLiqRatio.toFixed(2)} < 0.5 (8x edge)`));
      return;
    }
    // ═══ All insight filters passed ═══

    // Mark as pending to prevent double-snipe
    pendingRef.current.add(grad.mint);

    // Mark sniped immediately in store to block duplicates
    const newSniped = new Set(useSniperStore.getState().snipedMints);
    newSniped.add(grad.mint);
    useSniperStore.setState({ snipedMints: newSniped });

    const rec = getRecommendedSlTp(grad, config.strategyMode);

    // Log that we're attempting
    addExecution(makeExecEvent(grad, 'snipe', positionSol,
      `Executing swap... ${positionSol.toFixed(3)} SOL → ${grad.symbol} | ${conviction.toFixed(1)}x [${convFactors.join(',')}] | SL ${rec.sl}% TP ${rec.tp}%`));

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
      const entryPrice = await resolveEntryPriceUsd(grad.mint, grad.price_usd);

      const newPosition: Position = {
        id: posId,
        mint: grad.mint,
        symbol: grad.symbol,
        name: grad.name,
        entryPrice,
        currentPrice: entryPrice,
        amount: result.outputAmount,
        amountLamports: result.outputAmountLamports,
        solInvested: positionSol,
        pnlPercent: 0,
        pnlSol: 0,
        entryTime: Date.now(),
        txHash: result.txHash,
        status: 'open',
        score: grad.score,
        recommendedSl: rec.sl,
        recommendedTp: rec.tp,
        highWaterMarkPct: 0,
      };

      addPosition(newPosition);

      // Persist to server for 24/7 risk worker
      savePositionToServer({
        mint: grad.mint,
        symbol: grad.symbol,
        amount: result.outputAmount,
        amountLamports: result.outputAmountLamports,
        solInvested: positionSol,
        entryPrice,
        stopLossPct: rec.sl,
        takeProfitPct: rec.tp,
        txHash: result.txHash,
        walletAddress: address,
      });

      // Update budget spent
      useSniperStore.setState((s) => ({
        budget: { ...s.budget, spent: s.budget.spent + positionSol },
      }));

      // Log success
      addExecution({
        ...makeExecEvent(grad, 'snipe', positionSol,
          `Sniped ${grad.symbol} for ${positionSol.toFixed(3)} SOL (${conviction.toFixed(1)}x) | Got ${result.outputAmount.toFixed(2)} tokens | SL ${rec.sl}% TP ${rec.tp}%`),
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

async function resolveEntryPriceUsd(mint: string, fallback?: number): Promise<number> {
  if (typeof fallback === 'number' && fallback > 0) return fallback;

  try {
    const res = await fetch(`${DEXSCREENER_TOKENS}/${mint}`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return 0;
    const pairs: any[] = await res.json();

    // Pick the pair with the highest liquidity for price stability.
    let best: any | null = null;
    for (const p of pairs) {
      const liq = parseFloat(p?.liquidity?.usd || '0');
      if (!best || liq > (best._liq || 0)) best = { ...p, _liq: liq };
    }

    const price = parseFloat(best?.priceUsd || '0');
    return price > 0 ? price : 0;
  } catch {
    return 0;
  }
}
