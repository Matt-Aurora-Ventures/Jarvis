'use client';

import { useCallback, useRef } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore, getRecommendedSlTp, getConvictionMultiplier, type Position, type ExecutionEvent } from '@/stores/useSniperStore';
import { executeSwap, SOL_MINT, type SwapResult } from '@/lib/bags-trading';
import { loadSessionWalletFromStorage } from '@/lib/session-wallet';
import type { BagsGraduation } from '@/lib/bags-api';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';

let execCounter = 0;

/**
 * Hook that wires real on-chain swap execution to the sniper store.
 * Call `snipe(grad)` to: get quote → sign (Phantom or Session Wallet) → send tx → track position.
 */
export function useSnipeExecutor() {
  const { address, connected, signTransaction, signAllTransactions } = usePhantomWallet();
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
    const signerMode = useSniperStore.getState().tradeSignerMode;
    const sessionPubkey = useSniperStore.getState().sessionWalletPubkey;

    const session = signerMode === 'session' ? loadSessionWalletFromStorage() : null;
    const canUseSession = signerMode === 'session' && !!sessionPubkey && !!session && session.publicKey === sessionPubkey;

    const signerAddress = canUseSession ? sessionPubkey! : address;
    const signerSignTransaction = canUseSession
      ? (async (tx: VersionedTransaction) => {
          tx.sign([session!.keypair]);
          return tx;
        })
      : (signTransaction as ((tx: VersionedTransaction) => Promise<VersionedTransaction>) | undefined);

    if (!signerAddress || !signerSignTransaction) {
      addExecution(makeExecEvent(
        grad,
        'error',
        0,
        signerMode === 'session'
          ? 'Session wallet not ready (create + fund it in controls)'
          : 'Wallet not connected',
      ));
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
    // TOD note: removed hard block — OHLCV backtest had too few samples (16/200 tokens).
    // TOD is now handled as a soft penalty in getConvictionMultiplier() instead.
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
        signerAddress,
        SOL_MINT,
        grad.mint,
        positionSol,
        config.slippageBps,
        signerSignTransaction,
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
        walletAddress: signerAddress,
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
        recommendedTrail: rec.trail,
        highWaterMarkPct: 0,
      };

      addPosition(newPosition);

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

      // CRITICAL: if entry price is 0, SL/TP won't trigger. Schedule background retries.
      if (entryPrice <= 0) {
        addExecution(makeExecEvent(
          grad,
          'error',
          0,
          'Entry price unknown — SL/TP PAUSED. Retrying price lookup...',
        ));
        scheduleDeferredPriceResolution(posId, grad.mint);
      }

      // Immediately confirm SL/TP monitoring is active for this position.
      // The risk worker (useAutomatedRiskManagement) polls every 1.5s and will
      // auto-execute in session-wallet mode, or mark exitPending in Phantom mode.
      const sigMode = useSniperStore.getState().tradeSignerMode;
      const isAutoMode = sigMode === 'session';
      addExecution(makeExecEvent(
        grad,
        'info',
        0,
        `SL/TP ACTIVE: SL -${rec.sl}% | TP +${rec.tp}% | Trail ${rec.trail}% | ${
          isAutoMode ? 'AUTO-SELL enabled (session wallet)' : 'Manual mode — approve exits in Positions'
        }`,
      ));
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
  }, [connected, address, signTransaction, signAllTransactions]);

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

async function fetchDexScreenerPrice(mint: string): Promise<number> {
  try {
    const res = await fetch(`${DEXSCREENER_TOKENS}/${mint}`, {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return 0;
    const pairs: any[] = await res.json();

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

async function resolveEntryPriceUsd(mint: string, fallback?: number): Promise<number> {
  if (typeof fallback === 'number' && fallback > 0) return fallback;

  // Try DexScreener immediately
  const price = await fetchDexScreenerPrice(mint);
  if (price > 0) return price;

  // Retry after 2s — pair may not be indexed yet right after graduation
  await new Promise((r) => setTimeout(r, 2000));
  return fetchDexScreenerPrice(mint);
}

/**
 * If a position was created with entryPrice=0, keep retrying in the background
 * until we get a real price. SL/TP monitoring is skipped while entryPrice=0,
 * so this is critical to prevent silent risk management failure.
 */
function scheduleDeferredPriceResolution(posId: string, mint: string) {
  const delays = [5000, 10000, 20000, 40000]; // retry at 5s, 10s, 20s, 40s
  let attempt = 0;

  const tryResolve = async () => {
    const pos = useSniperStore.getState().positions.find((p) => p.id === posId);
    if (!pos || pos.status !== 'open') return; // closed or removed
    if (pos.entryPrice > 0) return; // already resolved

    const price = await fetchDexScreenerPrice(mint);
    if (price > 0) {
      useSniperStore.getState().updatePosition(posId, {
        entryPrice: price,
        currentPrice: price,
      });
      useSniperStore.getState().addExecution({
        id: `price-resolved-${Date.now()}-${posId.slice(-4)}`,
        type: 'info',
        symbol: pos.symbol,
        mint,
        amount: 0,
        reason: `Entry price resolved: $${price.toFixed(8)} — SL/TP now active`,
        timestamp: Date.now(),
      });
      return;
    }

    attempt++;
    if (attempt < delays.length) {
      setTimeout(tryResolve, delays[attempt]);
    } else {
      useSniperStore.getState().addExecution({
        id: `price-fail-${Date.now()}-${posId.slice(-4)}`,
        type: 'error',
        symbol: pos.symbol,
        mint,
        amount: 0,
        reason: 'Could not resolve entry price after 4 retries — SL/TP INACTIVE. Close manually.',
        timestamp: Date.now(),
      });
    }
  };

  setTimeout(tryResolve, delays[0]);
}
