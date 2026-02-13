'use client';

import { useEffect, useMemo, useRef } from 'react';
import {
  useSniperStore,
  type AssetType,
  buildMintCooldownKey,
  STRATEGY_PRESETS,
} from '@/stores/useSniperStore';
import { useSnipeExecutor } from '@/hooks/useSnipeExecutor';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { usePnlTracker } from '@/hooks/usePnlTracker';
import { usePositionReconciliation } from '@/hooks/usePositionReconciliation';
import { filterTradeManagedOpenPositionsForActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import type { BagsGraduation } from '@/lib/bags-api';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { checkSignerSolBalance } from '@/lib/solana-balance-guard';
import {
  buildWrGateCandidates,
  scopeAllowsAsset,
  selectBestWrGateStrategy,
} from '@/lib/auto-wr-gate';

const SIGNER_SOL_RESERVE_LAMPORTS = 3_000_000;
const BALANCE_GATE_CACHE_MS = 10_000;

async function fetchFromApi(assetFilter: AssetType): Promise<BagsGraduation[]> {
  try {
    if (assetFilter === 'memecoin') {
      const res = await fetch('/api/graduations', { cache: 'no-store' });
      if (!res.ok) return [];
      const data = await res.json();
      return data.graduations || [];
    }
    if (assetFilter === 'bags') {
      const res = await fetch('/api/bags/graduations', { cache: 'no-store' });
      if (!res.ok) return [];
      const data = await res.json();
      return data.graduations || [];
    }
    if (assetFilter === 'bluechip') {
      const res = await fetch('/api/bluechips', { cache: 'no-store' });
      if (!res.ok) return [];
      const data = await res.json();
      return data.graduations || [];
    }

    // TradFi scope (xstock/prestock/index): ingest all 3 categories so none disappear.
    const categories = ['XSTOCK', 'PRESTOCK', 'INDEX'];
    const settled = await Promise.allSettled(
      categories.map(async (category) => {
        const res = await fetch(`/api/xstocks?category=${category}`, { cache: 'no-store' });
        if (!res.ok) return [];
        const data = await res.json();
        return (data.graduations || []) as BagsGraduation[];
      }),
    );

    const merged: BagsGraduation[] = [];
    for (const result of settled) {
      if (result.status === 'fulfilled' && Array.isArray(result.value)) {
        merged.push(...result.value);
      }
    }
    if (merged.length === 0) return [];

    const byMint = new Map<string, BagsGraduation>();
    for (const g of merged) {
      if (!g?.mint) continue;
      const prev = byMint.get(g.mint);
      if (!prev || (g.score || 0) >= (prev.score || 0)) byMint.set(g.mint, g);
    }
    return [...byMint.values()];
  } catch {
    return [];
  }
}

export function SniperAutomationOrchestrator() {
  const { address } = usePhantomWallet();
  const {
    graduations,
    setGraduations,
    selectedMint,
    setSelectedMint,
    config,
    activePreset,
    backtestMeta,
    loadPreset,
    mintCooldowns,
    clearExpiredMintCooldowns,
    positions,
    budget,
    assetFilter,
    executionPaused,
    autoResetRequired,
    circuitBreaker,
    tradeSignerMode,
    sessionWalletPubkey,
    operationLock,
    strategyEpoch,
    setAutomationState,
    touchAutomationHeartbeat,
    releaseOperationLock,
    addExecution,
  } = useSniperStore();
  const { snipe, ready: walletReady } = useSnipeExecutor();

  // Keep live prices + SOL price updated for accurate PnL, dust filtering, and session reports.
  usePnlTracker();
  // Reconcile stale/phantom local positions against on-chain state, route-independently.
  usePositionReconciliation();

  const autoCycleInFlightRef = useRef(false);
  const nextAutoAllowedAtRef = useRef(0);
  const lastWalletNotReadyLogAtRef = useRef(0);
  const lastNoCandidateLogAtRef = useRef(0);
  const lastFallbackLogAtRef = useRef(0);
  const lastNoSolLogAtRef = useRef(0);
  const lastResetGateLogAtRef = useRef(0);
  const lastWrGatePrimaryLogAtRef = useRef(0);
  const lastWrGateFallbackLogAtRef = useRef(0);
  const lastWrGateNoEligibleLogAtRef = useRef(0);
  const wrGateSelectionSigRef = useRef('');
  const activeFeedAssetRef = useRef<AssetType | null>(null);
  const balanceGateRef = useRef<{
    wallet: string;
    checkedAt: number;
    ok: boolean;
    availableSol: number;
    requiredSol: number;
  } | null>(null);

  const dedupedGraduations = useMemo(() => {
    const byMint = new Map<string, BagsGraduation>();
    for (const g of graduations) {
      if (!g?.mint) continue;
      const prev = byMint.get(g.mint);
      if (!prev || (g.score || 0) >= (prev.score || 0)) byMint.set(g.mint, g);
    }
    return [...byMint.values()];
  }, [graduations]);

  const wrGateSelection = useMemo(() => {
    if (!config.autoWrGateEnabled) return null;
    const candidates = buildWrGateCandidates(STRATEGY_PRESETS, backtestMeta, config.autoWrScope);
    return selectBestWrGateStrategy(candidates, config);
  }, [
    backtestMeta,
    config.autoWrFallbackPct,
    config.autoWrGateEnabled,
    config.autoWrMethod,
    config.autoWrMinTrades,
    config.autoWrPrimaryPct,
    config.autoWrScope,
  ]);

  // Persistent feed refresh — decoupled from page components so automation survives route switches.
  useEffect(() => {
    let cancelled = false;
    const FEED_REFRESH_MS = 30_000;
    const switchedAsset = activeFeedAssetRef.current !== assetFilter;
    let firstRefreshAfterSwitch = switchedAsset;
    activeFeedAssetRef.current = assetFilter;

    if (switchedAsset) {
      // Prevent stale cross-asset bleed (xStocks/degen feed shown while in bags mode, etc.).
      setGraduations([]);
      setSelectedMint(null);
    }

    const refresh = async () => {
      if (cancelled) return;
      touchAutomationHeartbeat();
      const grads = await fetchFromApi(assetFilter);
      if (cancelled) return;
      if (grads.length > 0) {
        setGraduations(grads);
        const currentSelectedMint = useSniperStore.getState().selectedMint;
        const stillExists = !!currentSelectedMint && grads.some((g) => g.mint === currentSelectedMint);
        if (!stillExists) {
          setSelectedMint(grads[0]?.mint || null);
        }
      } else {
        // Keep previous feed only when we are still in the same asset scope.
        // On scope switch, always clear to avoid stale targets from another market.
        const stillSameScope = useSniperStore.getState().assetFilter === assetFilter;
        if (firstRefreshAfterSwitch || !stillSameScope) {
          setGraduations([]);
          setSelectedMint(null);
        }
      }
      firstRefreshAfterSwitch = false;
    };

    void refresh();
    const timer = setInterval(() => { void refresh(); }, FEED_REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [assetFilter, setGraduations, setSelectedMint, touchAutomationHeartbeat]);

  // Persistent auto-snipe loop.
  useEffect(() => {
    // IMPORTANT: do NOT gate the loop on walletReady here.
    // When the wallet isn't ready (missing session key, Phantom disconnected, etc.)
    // we still want the tick loop to run so it can surface the pause reason in the
    // execution log instead of silently going idle.
    if (!config.autoSnipe || !budget.authorized) {
      setAutomationState('idle');
      return;
    }

    let cancelled = false;
    const AUTO_SCAN_INTERVAL_MS = 3000;
    const AUTO_MIN_GAP_SUCCESS_MS = 42_000;
    const AUTO_MIN_GAP_FAIL_MS = 60_000;

    const tick = async () => {
      if (cancelled) return;
      touchAutomationHeartbeat();

      if (!walletReady) {
        setAutomationState('paused');
        const nowLog = Date.now();
        if (nowLog - lastWalletNotReadyLogAtRef.current > 60_000) {
          const signerMode = useSniperStore.getState().tradeSignerMode;
          const sessionPk = useSniperStore.getState().sessionWalletPubkey;
          addExecution({
            id: `auto-wallet-not-ready-${nowLog}`,
            type: 'info',
            symbol: 'AUTO',
            mint: '',
            amount: 0,
            reason:
              signerMode === 'session'
                ? `AUTO_STOP_WALLET_NOT_READY: session signer key not available for ${sessionPk ? `${sessionPk.slice(0, 6)}...` : 'session wallet'}`
                : 'AUTO_STOP_WALLET_NOT_READY: Phantom signer not connected',
            timestamp: nowLog,
          });
          lastWalletNotReadyLogAtRef.current = nowLog;
        }
        return;
      }

      if (autoResetRequired) {
        setAutomationState('paused');
        const nowLog = Date.now();
        if (nowLog - lastResetGateLogAtRef.current > 60_000) {
          addExecution({
            id: `auto-reset-required-${nowLog}`,
            type: 'info',
            symbol: 'AUTO',
            mint: '',
            amount: 0,
            reason: 'AUTO_STOP_RESET_AUTO: Re-arm required. Set fresh budget/max settings in Activate Auto Wallet before enabling auto.',
            timestamp: nowLog,
          });
          lastResetGateLogAtRef.current = nowLog;
        }
        return;
      }

      if (operationLock.active) {
        if (operationLock.mode === 'close_all' && !positions.some((p) => p.status === 'open' && p.isClosing)) {
          releaseOperationLock();
          addExecution({
            id: `lock-auto-release-${Date.now()}`,
            type: 'info',
            symbol: 'SYSTEM',
            mint: '',
            amount: 0,
            reason: 'Auto-released stale close-all lock (no positions currently closing)',
            timestamp: Date.now(),
          });
        }
        setAutomationState(operationLock.mode === 'close_all' ? 'closing_all' : 'paused');
        return;
      }
      if (circuitBreaker.tripped) {
        setAutomationState('tripped');
        return;
      }
      const assetBreaker = circuitBreaker.perAsset[assetFilter];
      if (assetBreaker?.tripped) {
        const nowBreaker = Date.now();
        const inCooldown = assetBreaker.cooldownUntil > 0 && nowBreaker < assetBreaker.cooldownUntil;
        if (inCooldown) {
          setAutomationState('tripped');
          return;
        }
        // Auto-release stale/legacy tripped states with no cooldown window.
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
      }

      if (autoCycleInFlightRef.current) return;
      const epochAtScanStart = strategyEpoch;
      const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
      clearExpiredMintCooldowns();
      const scopedOpen = filterTradeManagedOpenPositionsForActiveWallet(positions, activeWallet);
      const managedSpent = Math.round(
        scopedOpen.reduce((sum, p) => sum + Math.max(0, Number(p.solInvested || 0)), 0) * 1000,
      ) / 1000;
      if (Math.abs(Number(budget.spent || 0) - managedSpent) > 0.002) {
        useSniperStore.setState((s) => ({
          budget: {
            ...s.budget,
            spent: managedSpent,
          },
        }));
      }
      const remaining = budget.budgetSol - managedSpent;
      if (remaining < 0.001) return;

      if (scopedOpen.length >= config.maxConcurrentPositions) return;
      if (scopedOpen.some((p) => p.isClosing)) return;

      if (activeWallet) {
        const nowBalance = Date.now();
        const cached = balanceGateRef.current;
        const plannedPositionSol = Math.max(0.001, Math.min(config.maxPositionSol, remaining));
        if (
          !cached ||
          cached.wallet !== activeWallet ||
          nowBalance - cached.checkedAt >= BALANCE_GATE_CACHE_MS
        ) {
          const bal = await checkSignerSolBalance(
            getSharedConnection(),
            activeWallet,
            Math.floor(plannedPositionSol * 1e9),
            SIGNER_SOL_RESERVE_LAMPORTS,
          );
          balanceGateRef.current = {
            wallet: activeWallet,
            checkedAt: nowBalance,
            ok: bal.ok,
            availableSol: bal.availableSol,
            requiredSol: bal.requiredSol,
          };
        }

        const gate = balanceGateRef.current;
        if (gate && !gate.ok) {
          setAutomationState('paused');
          const nowLog = Date.now();
          if (nowLog - lastNoSolLogAtRef.current > 60_000) {
            const reason = `Auto paused: signer SOL low (${gate.availableSol.toFixed(4)} < ${gate.requiredSol.toFixed(4)} required incl. fee reserve)`;
            addExecution({
              id: `auto-no-sol-${nowLog}`,
              type: 'info',
              symbol: 'AUTO',
              mint: '',
              amount: 0,
              reason: `AUTO_STOP_LOW_SOL: ${reason}`,
              timestamp: nowLog,
            });
            lastNoSolLogAtRef.current = nowLog;
          }
          return;
        }
      }

      // Release legacy/stale execution pause once preflight checks pass.
      // Low-SOL protection is enforced directly by the balance gate above.
      if (executionPaused) {
        useSniperStore.getState().setExecutionPaused(false, 'Auto resumed: cleared stale execution pause');
      }

      const wrGateApplies =
        config.autoWrGateEnabled &&
        scopeAllowsAsset(config.autoWrScope, assetFilter) &&
        (assetFilter === 'memecoin' || assetFilter === 'bags');
      if (wrGateApplies) {
        const selection = wrGateSelection;
        const selected = selection?.selected;
        const resolution = selection?.resolution;

        if (!selected || !resolution) {
          setAutomationState('paused');
          const nowLog = Date.now();
          if (nowLog - lastWrGateNoEligibleLogAtRef.current > 60_000) {
            addExecution({
              id: `auto-wr-gate-none-${nowLog}`,
              type: 'info',
              symbol: 'AUTO',
              mint: '',
              amount: 0,
              reason: `AUTO_STOP_WR_GATE_NO_ELIGIBLE: no strategy passed WR gate (${config.autoWrMethod === 'wilson95_lower' ? 'Wilson95 lower' : 'point WR'} ${config.autoWrPrimaryPct}% -> ${config.autoWrFallbackPct}%, min ${config.autoWrMinTrades} trades)`,
              timestamp: nowLog,
            });
            lastWrGateNoEligibleLogAtRef.current = nowLog;
          }
          return;
        }

        const selectionSig = `${selected.strategyId}:${resolution.mode}:${resolution.usedThreshold}:${resolution.eligibleCount}`;
        const shouldLogSelection = selectionSig !== wrGateSelectionSigRef.current;
        const logSelectionEvent = () => {
          const nowLog = Date.now();
          if (resolution.mode === 'fallback') {
            if (
              shouldLogSelection ||
              nowLog - lastWrGateFallbackLogAtRef.current > 120_000
            ) {
              addExecution({
                id: `auto-wr-gate-fallback-${nowLog}`,
                type: 'info',
                symbol: 'AUTO',
                mint: '',
                amount: 0,
                reason: `AUTO_INFO_WR_GATE_FALLBACK: selected ${selected.strategyId} @ ${selection.selectedThresholdPct ?? resolution.usedThreshold}% (source=${selection.selectedThresholdSource || 'fallback'}, eligible=${resolution.eligibleCount}, rank=max net P&L)`,
                timestamp: nowLog,
              });
              lastWrGateFallbackLogAtRef.current = nowLog;
              wrGateSelectionSigRef.current = selectionSig;
            }
            return;
          }
          if (
            shouldLogSelection ||
            nowLog - lastWrGatePrimaryLogAtRef.current > 120_000
          ) {
            addExecution({
              id: `auto-wr-gate-primary-${nowLog}`,
              type: 'info',
              symbol: 'AUTO',
              mint: '',
              amount: 0,
              reason: `AUTO_INFO_WR_GATE_PRIMARY: selected ${selected.strategyId} @ ${selection.selectedThresholdPct ?? resolution.usedThreshold}% (source=${selection.selectedThresholdSource || 'global_primary'}, eligible=${resolution.eligibleCount}, rank=max net P&L)`,
              timestamp: nowLog,
            });
            lastWrGatePrimaryLogAtRef.current = nowLog;
            wrGateSelectionSigRef.current = selectionSig;
          }
        };

        if (activePreset !== selected.strategyId) {
          logSelectionEvent();
          loadPreset(selected.strategyId);
          setAutomationState('scanning');
          return;
        }

        logSelectionEvent();
      } else {
        wrGateSelectionSigRef.current = '';
      }

      const now = Date.now();
      if (now < nextAutoAllowedAtRef.current) {
        setAutomationState('cooldown');
        return;
      }

      setAutomationState('scanning');
      const strictCandidate = dedupedGraduations.find((grad) => {
        if (activeWallet) {
          const cooldownKey = buildMintCooldownKey(assetFilter, activeWallet, grad.mint);
          const cooldownUntil = Number(mintCooldowns[cooldownKey] || 0);
          if (cooldownUntil > Date.now()) return false;
        }
        if (scopedOpen.some((p) => p.mint === grad.mint)) return false;
        if (grad.score < config.minScore) return false;
        const liq = grad.liquidity || 0;
        const vol24h = grad.volume_24h || 0;
        const volLiqRatio = liq > 0 ? vol24h / liq : 0;
        const ageHours = grad.age_hours || 0;
        const mom1h = grad.price_change_1h || 0;
        return (
          liq >= config.minLiquidityUsd &&
          volLiqRatio >= config.minVolLiqRatio &&
          ageHours <= config.maxTokenAgeHours &&
          mom1h >= config.minMomentum1h
        );
      });
      const candidate = strictCandidate || dedupedGraduations.find((grad) => {
        if (activeWallet) {
          const cooldownKey = buildMintCooldownKey(assetFilter, activeWallet, grad.mint);
          const cooldownUntil = Number(mintCooldowns[cooldownKey] || 0);
          if (cooldownUntil > Date.now()) return false;
        }
        if (scopedOpen.some((p) => p.mint === grad.mint)) return false;
        if (grad.score < config.minScore) return false;
        return (grad.liquidity || 0) >= config.minLiquidityUsd;
      });
      const fallbackMinScore = Math.max(25, Math.floor(config.minScore * 0.8));
      const fallbackCandidate = !candidate
        ? dedupedGraduations.find((grad) => {
            if (activeWallet) {
              const cooldownKey = buildMintCooldownKey(assetFilter, activeWallet, grad.mint);
              const cooldownUntil = Number(mintCooldowns[cooldownKey] || 0);
              if (cooldownUntil > Date.now()) return false;
            }
            if (scopedOpen.some((p) => p.mint === grad.mint)) return false;
            return (grad.score || 0) >= fallbackMinScore;
          })
        : null;
      const resolvedCandidate = candidate || fallbackCandidate;
      if (!resolvedCandidate) {
        const nowLog = Date.now();
        if (nowLog - lastNoCandidateLogAtRef.current > 60_000) {
          addExecution({
            id: `auto-no-candidate-${nowLog}`,
            type: 'info',
            symbol: 'AUTO',
            mint: '',
            amount: 0,
            reason: `No eligible targets after filters (feed=${dedupedGraduations.length}, open=${scopedOpen.length}, minScore=${config.minScore})`,
            timestamp: nowLog,
          });
          lastNoCandidateLogAtRef.current = nowLog;
        }
        return;
      }
      if (!candidate) {
        const nowLog = Date.now();
        if (nowLog - lastFallbackLogAtRef.current > 60_000) {
          addExecution({
            id: `auto-fallback-candidate-${nowLog}`,
            type: 'info',
            symbol: resolvedCandidate.symbol || 'AUTO',
            mint: resolvedCandidate.mint || '',
            amount: 0,
            reason: `Using relaxed fallback filter (score >= ${fallbackMinScore})`,
            timestamp: nowLog,
          });
          lastFallbackLogAtRef.current = nowLog;
        }
      }
      if (epochAtScanStart !== useSniperStore.getState().strategyEpoch) {
        // Strategy changed during scan. Discard stale candidate and let next tick rescan.
        setAutomationState('scanning');
        return;
      }

      autoCycleInFlightRef.current = true;
      setAutomationState('executing_buy');
      try {
        const ok = await snipe(resolvedCandidate as any, epochAtScanStart);
        await new Promise((resolve) => setTimeout(resolve, 2500));
        const staleEpochAbort = !ok && useSniperStore.getState().strategyEpoch !== epochAtScanStart;
        nextAutoAllowedAtRef.current = Date.now() + (
          ok
            ? AUTO_MIN_GAP_SUCCESS_MS
            : staleEpochAbort
              ? 1_500
              : AUTO_MIN_GAP_FAIL_MS
        );
        setAutomationState('cooldown');
      } finally {
        autoCycleInFlightRef.current = false;
      }
    };

    void tick();
    const interval = setInterval(() => { void tick(); }, AUTO_SCAN_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
      setAutomationState('idle');
    };
  }, [
    dedupedGraduations,
    config.autoSnipe,
    config.maxConcurrentPositions,
    config.maxTokenAgeHours,
    config.minLiquidityUsd,
    config.minMomentum1h,
    config.minScore,
    config.minVolLiqRatio,
    graduations.length,
    walletReady,
    budget.authorized,
    budget.budgetSol,
    budget.spent,
    positions,
    mintCooldowns,
    clearExpiredMintCooldowns,
    assetFilter,
    executionPaused,
    autoResetRequired,
    circuitBreaker,
    tradeSignerMode,
    sessionWalletPubkey,
    address,
    operationLock,
    strategyEpoch,
    activePreset,
    backtestMeta,
    loadPreset,
    wrGateSelection,
    snipe,
    releaseOperationLock,
    addExecution,
    setAutomationState,
    touchAutomationHeartbeat,
  ]);

  return null;
}
