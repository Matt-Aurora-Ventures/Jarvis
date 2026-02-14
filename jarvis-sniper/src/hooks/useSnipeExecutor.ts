'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore, getRecommendedSlTp, getConvictionMultiplier, type Position, type ExecutionEvent, buildMintCooldownKey } from '@/stores/useSniperStore';
import { executeSwap, SOL_MINT, type SwapResult } from '@/lib/bags-trading';
import { loadSessionWalletByPublicKey, loadSessionWalletFromStorage } from '@/lib/session-wallet';
import { fetchTokenInfo, type BagsGraduation } from '@/lib/bags-api';
import { filterTradeManagedOpenPositionsForActiveWallet } from '@/lib/position-scope';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { getOwnerTokenBalanceLamportsWithRetry } from '@/lib/solana-tokens';
import { checkSignerSolBalance } from '@/lib/solana-balance-guard';
import { mergeRuntimeConfigWithStrategyOverride } from '@/lib/autonomy/override-policy';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const POST_BUY_VERIFY_DELAY_MS = 20_000;
const POST_BUY_VERIFY_ATTEMPTS = 4;
const SIGNER_SOL_RESERVE_LAMPORTS = 3_000_000;
const MAX_SLIPPAGE_BPS = 1200;
const AUTO_MINT_LOCK_PREFIX = 'jarvis-sniper:auto-mint-lock:';
const AUTO_MINT_LOCK_TTL_MS = 90_000;

let execCounter = 0;

// Track failed snipe attempts per mint to prevent infinite retry loops.
// After MAX_RETRIES failures within RETRY_WINDOW_MS, the mint is blocked until the window expires.
const MAX_RETRIES = 2;
const RETRY_WINDOW_MS = 5 * 60 * 1000; // 5-minute cooldown
const mintFailures = new Map<string, { count: number; firstFail: number }>();

function isMintCoolingDown(mint: string): boolean {
  const record = mintFailures.get(mint);
  if (!record) return false;
  // Window expired — reset
  if (Date.now() - record.firstFail > RETRY_WINDOW_MS) {
    mintFailures.delete(mint);
    return false;
  }
  return record.count >= MAX_RETRIES;
}

function recordMintFailure(mint: string): void {
  const now = Date.now();
  const record = mintFailures.get(mint);
  if (!record || now - record.firstFail > RETRY_WINDOW_MS) {
    mintFailures.set(mint, { count: 1, firstFail: now });
  } else {
    record.count++;
  }
}

/**
 * Hook that wires real on-chain swap execution to the sniper store.
 * Call `snipe(grad)` to: get quote → sign (Phantom or Session Wallet) → send tx → track position.
 */
export function useSnipeExecutor() {
  const { address, connected, signTransaction } = usePhantomWallet();
  const connectionRef = useRef<Connection | null>(null);
  const pendingRef = useRef<Set<string>>(new Set());
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const executionPaused = useSniperStore((s) => s.executionPaused);

  // Lazy-init connection (WS-disabled for proxy compatibility)
  function getConnection(): Connection {
    if (!connectionRef.current) {
      connectionRef.current = getSharedConnection();
    }
    return connectionRef.current;
  }

  const snipe = useCallback(async (grad: BagsGraduation & Record<string, any>, expectedStrategyEpoch?: number): Promise<boolean> => {
    const {
      config: rawConfig,
      activePreset,
      strategyOverrideSnapshot,
      positions,
      budget,
      addPosition,
      addExecution,
      circuitBreaker,
      assetFilter,
      operationLock,
      clearExpiredMintCooldowns,
    } = useSniperStore.getState();
    const config = mergeRuntimeConfigWithStrategyOverride(rawConfig, activePreset, strategyOverrideSnapshot);
    const strategyEpochAtStart = useSniperStore.getState().strategyEpoch;
    const entrySource: Position['entrySource'] = typeof expectedStrategyEpoch === 'number' ? 'auto' : 'manual';
    const isAutoEntry = entrySource === 'auto';
    const autoLockOwner = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    let autoLockKey: string | null = null;

    if (typeof expectedStrategyEpoch === 'number' && strategyEpochAtStart !== expectedStrategyEpoch) {
      addExecution(makeExecEvent(grad, 'skip', 0, 'AUTO_STOP_STRATEGY_SWITCH: Strategy changed before execution; retrying with latest algorithm'));
      return false;
    }

    // --- Pre-flight guards ---
    const signerMode = useSniperStore.getState().tradeSignerMode;
    const sessionPubkey = useSniperStore.getState().sessionWalletPubkey;

    const session = signerMode === 'session'
      ? (
          sessionPubkey
            ? await loadSessionWalletByPublicKey(sessionPubkey, { mainWallet: address || undefined })
            : await loadSessionWalletFromStorage({ mainWallet: address || undefined })
        )
      : null;
    const canUseSession = signerMode === 'session' && !!sessionPubkey && !!session && session.publicKey === sessionPubkey;

    const signerAddress = canUseSession ? sessionPubkey! : address;
    const signerSignTransaction = canUseSession
      ? (async (tx: VersionedTransaction) => {
          tx.sign([session!.keypair]);
          return tx;
        })
      : (signTransaction as ((tx: VersionedTransaction) => Promise<VersionedTransaction>) | undefined);

    if (signerMode === 'session' && !canUseSession) {
      addExecution(makeExecEvent(
        grad,
        'error',
        0,
        'Session wallet selected but key is unavailable in this browser. Re-upload key file or switch to Phantom.',
      ));
      return false;
    }

    if (!signerAddress || !signerSignTransaction) {
      addExecution(makeExecEvent(
        grad,
        'error',
        0,
        signerMode === 'session'
          ? 'Session wallet not ready (create + fund it in controls)'
          : 'Wallet not connected',
      ));
      return false;
    }
    if (!budget.authorized) {
      addExecution(makeExecEvent(grad, 'error', 0, 'Budget not authorized'));
      return false;
    }
    if (operationLock.active) {
      addExecution(makeExecEvent(grad, 'skip', 0, `Execution locked: ${operationLock.reason || operationLock.mode}`));
      return false;
    }
    if (useSniperStore.getState().executionPaused) {
      addExecution(makeExecEvent(grad, 'skip', 0, 'AUTO_STOP_EXECUTION_PAUSED: Close All / safety lock active'));
      return false;
    }
    if (circuitBreaker.tripped) {
      addExecution(makeExecEvent(grad, 'skip', 0, `Circuit breaker active: ${circuitBreaker.reason || 'global halt'}`));
      return false;
    }
    const assetBreaker = circuitBreaker.perAsset[assetFilter];
    if (assetBreaker?.tripped) {
      const now = Date.now();
      if (assetBreaker.cooldownUntil > 0 && now >= assetBreaker.cooldownUntil) {
        useSniperStore.setState((s) => {
          const cb = { ...s.circuitBreaker, perAsset: { ...s.circuitBreaker.perAsset } };
          cb.perAsset[s.assetFilter] = {
            ...cb.perAsset[s.assetFilter],
            tripped: false,
            reason: '',
            trippedAt: 0,
            consecutiveLosses: 0,
            cooldownUntil: 0,
          };
          return { circuitBreaker: cb };
        });
      } else {
        addExecution(makeExecEvent(grad, 'skip', 0, `Circuit breaker (${assetFilter}) active: ${assetBreaker.reason || 'cooldown'}`));
        return false;
      }
    }
    clearExpiredMintCooldowns();
    const cooldownKey = buildMintCooldownKey(assetFilter, signerAddress, grad.mint);
    const cooldownUntil = Number(useSniperStore.getState().mintCooldowns[cooldownKey] || 0);
    if (cooldownUntil > Date.now()) {
      const remainingSec = Math.ceil((cooldownUntil - Date.now()) / 1000);
      addExecution(makeExecEvent(grad, 'skip', 0, `Mint cooldown active (${remainingSec}s left)`));
      return false;
    }
    if (pendingRef.current.has(grad.mint)) {
      if (isAutoEntry) {
        addExecution(makeExecEvent(grad, 'skip', 0, 'AUTO_STOP_DUPLICATE_MINT: mint already in-flight in this tab'));
      }
      return false;
    }
    if (isMintCoolingDown(grad.mint)) return false; // too many recent failures

    const managedOpen = filterTradeManagedOpenPositionsForActiveWallet(positions, signerAddress);
    if (isAutoEntry) {
      const duplicate = positions.find((p) => (
        p.walletAddress === signerAddress
        && p.mint === grad.mint
        && p.status === 'open'
      ));
      if (duplicate) {
        addExecution(makeExecEvent(
          grad,
          'skip',
          0,
          `AUTO_STOP_DUPLICATE_MINT: existing open/closing position for ${grad.mint.slice(0, 6)}...`,
        ));
        return false;
      }
    }
    const openCount = managedOpen.length;
    if (openCount >= config.maxConcurrentPositions) {
      addExecution(makeExecEvent(grad, 'skip', 0, `At max managed positions (${openCount}/${config.maxConcurrentPositions})`));
      return false;
    }

    const remaining = budget.budgetSol - budget.spent;
    // Auto safety cap: never let auto mode size a single entry too large relative to the user's
    // total budget (prevents accidental "all-in" buys from misconfigured slots/presets).
    const autoHardCapSol = config.autoSnipe ? Math.max(0.005, budget.budgetSol * 0.25) : Number.POSITIVE_INFINITY;
    // Conviction-weighted sizing (hard cap):
    // `maxPositionSol` is treated as the user's maximum per trade.
    // Conviction can scale the size DOWN, but never above the max.
    const { multiplier: conviction, factors: convFactors } = getConvictionMultiplier(grad);
    const sizeFactor = Math.min(1, conviction);
    const desiredSol = config.maxPositionSol * sizeFactor;
    const positionSol = Math.min(desiredSol, config.maxPositionSol, remaining, autoHardCapSol);
    if (positionSol < 0.001) {
      addExecution(makeExecEvent(grad, 'skip', 0, 'Insufficient budget'));
      return false;
    }

    // ??? INSIGHT-DRIVEN FILTERS ???
    const source = ((grad as any).source || '').toLowerCase();
    const isTraditional = source === 'xstock' || source === 'prestock' || source === 'index' || source === 'commodity';

    const liq = grad.liquidity || 0;
    if (!isTraditional && liq < config.minLiquidityUsd) {
      addExecution(makeExecEvent(
        grad,
        'skip',
        0,
        `Low liquidity: $${Math.round(liq).toLocaleString()} < $${Math.round(config.minLiquidityUsd).toLocaleString()}`,
      ));
      return false;
    }

    // Memecoin-specific filters ? do NOT apply to blue chips, xStocks, indexes, prestocks, or commodities.
    // Traditional/established assets have fundamentally different B/S patterns, age, and momentum.
    const isMemecoin = !source || source === 'pumpswap' || source === 'raydium' || source === 'memecoin';

    if (isMemecoin) {
      const buys = grad.txn_buys_1h || 0;
      const sells = grad.txn_sells_1h || 0;
      const bsRatio = sells > 0 ? buys / sells : buys;
      if (buys + sells > 10 && (bsRatio < 1.0 || bsRatio > 3.0)) {
        addExecution(makeExecEvent(grad, 'skip', 0, `B/S ratio ${bsRatio.toFixed(1)} outside 1.0-3.0`));
        return false;
      }
      const ageHours = grad.age_hours || 0;
      if (config.maxTokenAgeHours > 0 && ageHours > config.maxTokenAgeHours) {
        addExecution(makeExecEvent(grad, 'skip', 0, `Too old: ${Math.round(ageHours)}h > ${config.maxTokenAgeHours}h`));
        return false;
      }
      const change1h = grad.price_change_1h || 0;
      if (change1h < config.minMomentum1h) {
        addExecution(makeExecEvent(grad, 'skip', 0, `Momentum ${change1h.toFixed(1)}% < ${config.minMomentum1h}%`));
        return false;
      }
      const vol24h = grad.volume_24h || 0;
      const volLiqRatio = liq > 0 ? vol24h / liq : 0;
      if (vol24h > 0 && volLiqRatio < config.minVolLiqRatio) {
        addExecution(makeExecEvent(grad, 'skip', 0, `Low Vol/Liq: ${volLiqRatio.toFixed(2)} < ${config.minVolLiqRatio}`));
        return false;
      }
    }
    // ═══ All filters passed ═══

    const rec = getRecommendedSlTp(grad, config.strategyMode);
    const displaySymbol = normalizeDisplaySymbol(grad.symbol, grad.mint);
    const displayName = normalizeDisplayName(grad.name, displaySymbol, grad.mint);

    const connection = getConnection();
    const signerBalance = await checkSignerSolBalance(
      connection,
      signerAddress,
      Math.floor(positionSol * 1e9),
      SIGNER_SOL_RESERVE_LAMPORTS,
    );
    if (!signerBalance.ok) {
      const reason = `Insufficient signer SOL (${signerBalance.availableSol.toFixed(4)} < ${signerBalance.requiredSol.toFixed(4)} required incl. fee reserve)`;
      addExecution({
        ...makeExecEvent(grad, 'error', positionSol, reason),
        phase: 'failed',
      });
      return false;
    }

    if (isAutoEntry) {
      autoLockKey = buildAutoMintLockKey(signerAddress, grad.mint);
      const lockOk = acquireAutoMintLock(autoLockKey, autoLockOwner, AUTO_MINT_LOCK_TTL_MS);
      if (!lockOk) {
        addExecution(makeExecEvent(grad, 'skip', 0, 'AUTO_STOP_DUPLICATE_MINT: cross-tab auto lock active for this mint'));
        return false;
      }
    }

    // Mark as pending to prevent double-snipe
    pendingRef.current.add(grad.mint);

    // Mark sniped immediately in store to block duplicates
    const newSniped = new Set(useSniperStore.getState().snipedMints);
    newSniped.add(grad.mint);
    useSniperStore.setState({ snipedMints: newSniped });

    addExecution({
      ...makeExecEvent(
        grad,
        'info',
        positionSol,
        `Attempting swap ${positionSol.toFixed(3)} SOL → ${displaySymbol} | ${conviction.toFixed(1)}x [${convFactors.join(',')}] | base slippage ${config.slippageBps}bps`,
      ),
      phase: 'attempt',
    });

    try {
      if (typeof expectedStrategyEpoch === 'number') {
        const liveEpoch = useSniperStore.getState().strategyEpoch;
        if (liveEpoch !== expectedStrategyEpoch) {
          addExecution(makeExecEvent(grad, 'skip', 0, 'AUTO_STOP_STRATEGY_SWITCH: strategy changed mid-cycle; aborted stale auto-snipe'));
          const revertEarly = new Set(useSniperStore.getState().snipedMints);
          revertEarly.delete(grad.mint);
          useSniperStore.setState({ snipedMints: revertEarly });
          return false;
        }
      }

      const slippageLadder = buildSlippageLadder(config.slippageBps);
      let result: SwapResult | null = null;
      for (let i = 0; i < slippageLadder.length; i++) {
        const slippageBps = slippageLadder[i];
        result = await executeSwap(
          connection,
          signerAddress,
          SOL_MINT,
          grad.mint,
          positionSol,
          slippageBps,
          signerSignTransaction,
          config.useJito,
        );
        if (result?.txHash) {
          addExecution({
            ...makeExecEvent(grad, 'info', positionSol, `Swap submitted at ${slippageBps}bps slippage`),
            phase: 'submitted',
            txHash: result.txHash,
          });
        }
        if (result.success) break;

        const shouldRetrySlippage =
          result.failureCode === 'slippage_limit' &&
          i < slippageLadder.length - 1;
        if (!shouldRetrySlippage) break;

        const nextBps = slippageLadder[i + 1];
        addExecution({
          ...makeExecEvent(
            grad,
            'info',
            positionSol,
            `Retrying swap due to slippage limit (${slippageBps} → ${nextBps} bps)`,
          ),
          phase: 'attempt',
        });
      }

      if (!result) {
        result = {
          success: false,
          inputAmount: positionSol,
          outputAmount: 0,
          priceImpact: 0,
          error: 'Swap failed without result payload',
          failureCode: 'rpc_error',
          failureDetail: 'Swap failed without result payload',
          timestamp: Date.now(),
        };
      }

      if (!result.success) {
        recordMintFailure(grad.mint);
        const failures = mintFailures.get(grad.mint);
        const attemptsLeft = MAX_RETRIES - (failures?.count ?? 0);
        const normalizedCode = result.failureCode ? `[${result.failureCode}] ` : '';
        addExecution({
          ...makeExecEvent(
            grad,
            'error',
            positionSol,
            `Swap failed: ${normalizedCode}${result.error || result.failureDetail || 'Unknown error'}${attemptsLeft > 0 ? ` (${attemptsLeft} retries left)` : ' — cooldown 5m'}`,
          ),
          phase: 'failed',
          txHash: result.txHash,
        });
        // Un-mark sniped so scanner can retry (if not in cooldown)
        const revert = new Set(useSniperStore.getState().snipedMints);
        revert.delete(grad.mint);
        useSniperStore.setState({ snipedMints: revert });
        return false;
      }

      // Success — create real position
      const posId = `pos-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      const entryPrice = await resolveEntryPriceUsd(grad.mint, grad.price_usd, positionSol, result.outputAmount);

      const newPosition: Position = {
        id: posId,
        mint: grad.mint,
        symbol: displaySymbol,
        name: displayName,
        assetType: useSniperStore.getState().assetFilter,
        walletAddress: signerAddress,
        strategyId: useSniperStore.getState().activePreset,
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
        entrySource,
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
          `Sniped ${displaySymbol} for ${positionSol.toFixed(3)} SOL (${conviction.toFixed(1)}x) | Got ${result.outputAmount.toFixed(2)} tokens | SL ${rec.sl}% TP ${rec.tp}%`),
        phase: 'confirmed',
        txHash: result.txHash,
        price: entryPrice,
      });

      schedulePostBuyVerification({
        positionId: posId,
        mint: grad.mint,
        symbol: displaySymbol,
        walletAddress: signerAddress,
        txHash: result.txHash,
      });

      if (!hasReliableTokenIdentity(displaySymbol, displayName)) {
        scheduleTokenIdentityEnrichment(posId, grad.mint);
      }

      // Keep snipedMints as in-flight dedupe only.
      const clearSniped = new Set(useSniperStore.getState().snipedMints);
      clearSniped.delete(grad.mint);
      useSniperStore.setState({ snipedMints: clearSniped });

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
      return true;
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      recordMintFailure(grad.mint);
      addExecution({
        ...makeExecEvent(grad, 'error', positionSol, `Exception: ${msg}`),
        phase: 'failed',
      });
      // Un-mark sniped (cooldown guard prevents infinite retries)
      const revert = new Set(useSniperStore.getState().snipedMints);
      revert.delete(grad.mint);
      useSniperStore.setState({ snipedMints: revert });
      return false;
    } finally {
      pendingRef.current.delete(grad.mint);
      if (isAutoEntry && autoLockKey) {
        releaseAutoMintLock(autoLockKey, autoLockOwner);
      }
    }
  }, [address, signTransaction, executionPaused]);

  const [sessionReady, setSessionReady] = useState(false);
  useEffect(() => {
    if (tradeSignerMode !== 'session' || !sessionWalletPubkey) {
      setSessionReady(false);
      return;
    }
    let cancelled = false;
    (async () => {
      const session =
        await loadSessionWalletByPublicKey(sessionWalletPubkey, { mainWallet: address || undefined }) ||
        await loadSessionWalletFromStorage({ mainWallet: address || undefined });
      if (!cancelled) {
        setSessionReady(!!session && session.publicKey === sessionWalletPubkey);
      }
    })();
    return () => { cancelled = true; };
  }, [tradeSignerMode, sessionWalletPubkey, address]);

  return { snipe, ready: tradeSignerMode === 'session' ? sessionReady : connected && !!address };
}

function makeExecEvent(
  grad: BagsGraduation & Record<string, any>,
  type: ExecutionEvent['type'],
  amount: number,
  reason: string,
): ExecutionEvent {
  execCounter++;
  const symbol = normalizeDisplaySymbol(grad.symbol, grad.mint);
  return {
    id: `exec-${Date.now()}-${execCounter}`,
    type,
    symbol,
    mint: grad.mint,
    amount,
    price: grad.price_usd,
    reason,
    timestamp: Date.now(),
  };
}

function buildSlippageLadder(baseBps: number): number[] {
  const base = Math.max(50, Math.floor(baseBps || 0));
  const ladder = [base, base + 150, base + 300]
    .map((bps) => Math.min(MAX_SLIPPAGE_BPS, bps))
    .filter((bps, idx, arr) => Number.isFinite(bps) && bps > 0 && arr.indexOf(bps) === idx)
    .sort((a, b) => a - b);
  return ladder.length > 0 ? ladder : [300, 450, 600];
}

function normalizeDisplaySymbol(raw: string | undefined | null, mint: string): string {
  const value = String(raw || '').trim();
  const normalized = value.toUpperCase();
  if (!value || normalized === 'UNKNOWN' || normalized === '???' || normalized === 'N/A') {
    return String(mint || '').slice(0, 6).toUpperCase() || 'UNKNOWN';
  }
  return value;
}

function normalizeDisplayName(raw: string | undefined | null, symbol: string, mint: string): string {
  const value = String(raw || '').trim();
  if (!value || value.toLowerCase() === 'unknown') {
    return symbol || `Token ${String(mint || '').slice(0, 6)}`;
  }
  return value;
}

function buildAutoMintLockKey(walletAddress: string, mint: string): string {
  return `${AUTO_MINT_LOCK_PREFIX}${String(walletAddress || '').toLowerCase()}:${String(mint || '').toLowerCase()}`;
}

function acquireAutoMintLock(key: string, owner: string, ttlMs: number): boolean {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') return true;
  const now = Date.now();
  try {
    const raw = localStorage.getItem(key);
    if (raw) {
      const parsed = JSON.parse(raw) as { owner?: string; expiresAt?: number };
      const expiresAt = Number(parsed?.expiresAt || 0);
      const existingOwner = String(parsed?.owner || '');
      if (expiresAt > now && existingOwner && existingOwner !== owner) {
        return false;
      }
    }
    localStorage.setItem(
      key,
      JSON.stringify({
        owner,
        expiresAt: now + Math.max(10_000, Math.floor(ttlMs || AUTO_MINT_LOCK_TTL_MS)),
      }),
    );
    return true;
  } catch {
    return true;
  }
}

function releaseAutoMintLock(key: string, owner: string): void {
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') return;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return;
    const parsed = JSON.parse(raw) as { owner?: string; expiresAt?: number };
    if (String(parsed?.owner || '') === owner) {
      localStorage.removeItem(key);
    }
  } catch {
    // ignore
  }
}

function hasReliableTokenIdentity(symbol: string, name: string): boolean {
  const s = String(symbol || '').trim().toUpperCase();
  const n = String(name || '').trim().toLowerCase();
  return !!s && s !== 'UNKNOWN' && s !== '???' && !!n && n !== 'unknown';
}

function scheduleTokenIdentityEnrichment(posId: string, mint: string) {
  setTimeout(async () => {
    const state = useSniperStore.getState();
    const pos = state.positions.find((p) => p.id === posId);
    if (!pos || pos.status !== 'open') return;
    if (hasReliableTokenIdentity(pos.symbol, pos.name)) return;

    const info = await fetchTokenInfo(mint);
    if (!info) return;

    const symbol = normalizeDisplaySymbol(info.symbol, mint);
    const name = normalizeDisplayName(info.name, symbol, mint);

    useSniperStore.getState().updatePosition(posId, { symbol, name });
    useSniperStore.getState().addExecution({
      id: `symbol-enrich-${Date.now()}-${posId.slice(-4)}`,
      type: 'info',
      symbol,
      mint,
      amount: 0,
      reason: `Token identity enriched: ${symbol}`,
      timestamp: Date.now(),
    });
  }, 15_000);
}

function schedulePostBuyVerification(args: {
  positionId: string;
  mint: string;
  symbol: string;
  walletAddress: string;
  txHash?: string;
}) {
  setTimeout(async () => {
    const current = useSniperStore.getState().positions.find((p) => p.id === args.positionId);
    if (!current || current.status !== 'open') return;

    const connection = getSharedConnection();
    const bal = await getOwnerTokenBalanceLamportsWithRetry(
      connection,
      args.walletAddress,
      args.mint,
      {
        attempts: POST_BUY_VERIFY_ATTEMPTS,
        delayMs: 1000,
        requireNonZero: false,
      },
    );

    if (!bal || bal.amountLamports === '0') {
      useSniperStore.getState().reconcilePosition(args.positionId, 'buy_tx_unresolved');
      useSniperStore.getState().addExecution({
        id: `buy-verify-fail-${Date.now()}-${args.positionId.slice(-4)}`,
        type: 'error',
        symbol: args.symbol,
        mint: args.mint,
        amount: Math.max(0, Number(current.solInvested || 0)),
        txHash: args.txHash,
        reason: 'Post-buy verification failed: no on-chain token balance detected',
        timestamp: Date.now(),
      });
      return;
    }

    useSniperStore.getState().addExecution({
      id: `buy-verify-ok-${Date.now()}-${args.positionId.slice(-4)}`,
      type: 'info',
      symbol: args.symbol,
      mint: args.mint,
      amount: 0,
      txHash: args.txHash,
      reason: 'Post-buy verification confirmed on-chain token balance',
      timestamp: Date.now(),
    });
  }, POST_BUY_VERIFY_DELAY_MS);
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

async function fetchSolUsdPrice(): Promise<number> {
  // Prefer our server-cached macro endpoint (avoids hammering public APIs per snipe).
  try {
    const res = await fetch('/api/macro');
    if (res.ok) {
      const json = await res.json();
      const p = typeof json?.solPrice === 'number' ? json.solPrice : 0;
      if (Number.isFinite(p) && p > 0) return p;
    }
  } catch {
    // ignore
  }

  // Fallback: Jupiter lite price endpoint (no API key required).
  try {
    const res = await fetch('https://lite-api.jup.ag/price/v3?ids=So11111111111111111111111111111111111111112', {
      headers: { Accept: 'application/json' },
    });
    if (!res.ok) return 0;
    const json = await res.json();
    const node = json?.data?.So11111111111111111111111111111111111111112 ?? json?.So11111111111111111111111111111111111111112;
    const p = node?.usdPrice ?? node?.price;
    const num = typeof p === 'string' ? Number.parseFloat(p) : typeof p === 'number' ? p : 0;
    return Number.isFinite(num) && num > 0 ? num : 0;
  } catch {
    return 0;
  }
}

async function resolveEntryPriceUsd(
  mint: string,
  fallback: number | undefined,
  solInvested?: number,
  tokenOutAmount?: number,
): Promise<number> {
  // Best: compute cost-basis entry from the executed trade (works even before DEX indexing).
  if (
    typeof solInvested === 'number' &&
    typeof tokenOutAmount === 'number' &&
    Number.isFinite(solInvested) &&
    Number.isFinite(tokenOutAmount) &&
    solInvested > 0 &&
    tokenOutAmount > 0
  ) {
    const solUsd = await fetchSolUsdPrice();
    if (solUsd > 0) {
      const entry = (solInvested * solUsd) / tokenOutAmount;
      if (Number.isFinite(entry) && entry > 0) return entry;
    }
  }

  // Fallback: use feed-provided price if present.
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
