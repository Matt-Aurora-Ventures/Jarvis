'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { X, DollarSign, Clock, ExternalLink, Shield, ShieldCheck, Target, BarChart3, RotateCcw, Loader2, TrendingUp, Trash2, RefreshCw, AlertTriangle, Wallet } from 'lucide-react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { useSniperStore } from '@/stores/useSniperStore';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { executeSwapFromQuote, getSellQuote } from '@/lib/bags-trading';
import { withTimeout } from '@/lib/async-timeout';
import { getOwnerTokenBalanceLamports, minLamportsString } from '@/lib/solana-tokens';
import { computeTargetsFromEntryUsd, formatUsdPrice, isBlueChipLongConvictionSymbol } from '@/lib/trade-plan';
import { closeEmptyTokenAccountsForMint, loadSessionWalletByPublicKey, loadSessionWalletFromStorage, sweepExcessToMainWallet } from '@/lib/session-wallet';
import { filterOpenPositionsForActiveWallet, filterTradeManagedOpenPositionsForActiveWallet, isPositionInActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { DUST_VALUE_USD, isHoldingDustRecentlyClosed, partitionDustHoldings, type DustAwarePosition, type RecentlyClosedMintMemo } from '@/lib/dust-policy';
import { MIN_RELIABLE_SOL_INVESTED, isOperatorManagedPositionMeta, isReliableTradeForStats, resolvePositionPnlPercent } from '@/lib/position-reliability';

const RECONCILE_GRACE_MS = 5 * 60 * 1000; // Keep freshly-opened positions out of auto-reconcile.
const IMPORT_MATERIAL_CHANGE_NUM = BigInt(110); // +10%
const IMPORT_MATERIAL_CHANGE_DEN = BigInt(100);

function safeLamports(value: string | undefined | null): bigint {
  try {
    const text = String(value || '0').trim();
    if (!/^\d+$/.test(text)) return BigInt(0);
    return BigInt(text);
  } catch {
    return BigInt(0);
  }
}

type OnchainHolding = {
  mint: string;
  symbol: string;
  name: string;
  icon?: string;
  decimals: number;
  amountLamports: string;
  uiAmount: number;
  priceUsd: number;
  valueUsd: number;
  sources?: string[];
  accountCount?: number;
  accounts?: Array<{ tokenAccount: string; amountLamports: string; decimals: number }>;
  riskTags?: string[];
};

export function PositionsPanel() {
  const { positions, setSelectedMint, selectedMint, resetSession } = useSniperStore();
  const config = useSniperStore((s) => s.config);
  const setConfig = useSniperStore((s) => s.setConfig);
  const addPosition = useSniperStore((s) => s.addPosition);
  const importedHoldingsMemo = useSniperStore((s) => s.importedHoldingsMemo);
  const recordImportedHolding = useSniperStore((s) => s.recordImportedHolding);
  const updateImportedHoldingSeen = useSniperStore((s) => s.updateImportedHoldingSeen);
  const pruneImportedHoldingMemo = useSniperStore((s) => s.pruneImportedHoldingMemo);
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const assetFilter = useSniperStore((s) => s.assetFilter);
  const lastSolPriceUsd = useSniperStore((s) => s.lastSolPriceUsd);
  const setExecutionPaused = useSniperStore((s) => s.setExecutionPaused);
  const setPositionClosing = useSniperStore((s) => s.setPositionClosing);
  const updatePosition = useSniperStore((s) => s.updatePosition);
  const closePosition = useSniperStore((s) => s.closePosition);
  const reconcilePosition = useSniperStore((s) => s.reconcilePosition);
  const addExecution = useSniperStore((s) => s.addExecution);
  const acquireOperationLock = useSniperStore((s) => s.acquireOperationLock);
  const releaseOperationLock = useSniperStore((s) => s.releaseOperationLock);
  const setAutomationState = useSniperStore((s) => s.setAutomationState);
  const { address, signTransaction } = usePhantomWallet();
  const connectionRef = useRef<Connection | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [confirmCloseAll, setConfirmCloseAll] = useState(false);
  const [closingAllCount, setClosingAllCount] = useState<{ done: number; total: number } | null>(null);
  const [onchainHoldings, setOnchainHoldings] = useState<OnchainHolding[]>([]);
  const [onchainLoading, setOnchainLoading] = useState(false);
  const [onchainError, setOnchainError] = useState<string | null>(null);
  const [onchainLastSync, setOnchainLastSync] = useState<number>(0);
  const [onchainSource, setOnchainSource] = useState<'solscan' | 'rpc' | 'hybrid' | 'unknown'>('unknown');
  const [onchainWarnings, setOnchainWarnings] = useState<string[]>([]);
  const [onchainDiagnostics, setOnchainDiagnostics] = useState<any | null>(null);
  const [showSyncEvidence, setShowSyncEvidence] = useState(false);
  const [showAllUntracked, setShowAllUntracked] = useState(false);
  const suppressedPromptLogRef = useRef<number>(0);
  const recentlyClosedMints = useSniperStore((s) => s.recentlyClosedMints);
  const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
  const activeSessionWallet = tradeSignerMode === 'session' ? sessionWalletPubkey : null;
  const openPositions = filterOpenPositionsForActiveWallet(positions, activeWallet);
  const managedOpenPositions = useMemo(
    () =>
      openPositions.filter(
        (p) => isOperatorManagedPositionMeta(p) && Number(p.solInvested || 0) >= MIN_RELIABLE_SOL_INVESTED,
      ),
    [openPositions],
  );
  const closedPositions = positions
    .filter(
      (p) =>
        p.status !== 'open' &&
        isPositionInActiveWallet(p, activeWallet) &&
        isReliableTradeForStats(p),
    )
    .slice(0, 10);

  const totalOpen = managedOpenPositions.reduce((sum, p) => sum + p.solInvested, 0);
  const unrealizedPnl = managedOpenPositions.reduce((sum, p) => sum + p.pnlSol, 0);
  const openPositionsByMint = useMemo(() => {
    // For dust classification/reconciliation, only consider trade-managed opens.
    // Manual/recovered rows can otherwise "protect" post-sell crumbs from being classified as dust.
    const tradeManaged = filterTradeManagedOpenPositionsForActiveWallet(positions, activeWallet, { excludeClosing: false });
    const map = new Map<string, DustAwarePosition>();
    for (const p of tradeManaged) {
      if (p.status !== 'open') continue;
      if (!p.mint) continue;
      const prev = map.get(p.mint);
      if (!prev || (Number(p.amount || 0) > Number(prev.amount || 0))) {
        map.set(p.mint, {
          mint: p.mint,
          amount: Number(p.amount || 0),
          walletAddress: p.walletAddress,
          status: p.status,
          manualOnly: false,
        });
      }
    }
    return map;
  }, [activeWallet, positions]);

  const dustPartition = useMemo(() => {
    const base = partitionDustHoldings(onchainHoldings, openPositionsByMint);
    if (!activeSessionWallet) return base;

    const walletKey = String(activeSessionWallet).trim().toLowerCase();
    const recents = Object.values(recentlyClosedMints || {}).filter(
      (e: any) => String(e?.wallet || '').trim().toLowerCase() === walletKey,
    ) as Array<any>;
    if (recents.length === 0) return base;

    const recentByMint = new Map<string, RecentlyClosedMintMemo>();
    for (const e of recents) {
      const mintKey = String(e?.mint || '').trim().toLowerCase();
      if (!mintKey) continue;
      recentByMint.set(mintKey, {
        mint: mintKey,
        closedAt: Number(e?.closedAt || 0),
        amountLamportsAtClose: e?.amountLamports ? String(e.amountLamports) : undefined,
        uiAmountAtClose: Number.isFinite(Number(e?.uiAmount)) ? Number(e.uiAmount) : undefined,
      });
    }
    if (recentByMint.size === 0) return base;

    const now = Date.now();
    const visible: OnchainHolding[] = [];
    const suppressed: OnchainHolding[] = [];
    for (const h of base.visibleHoldings) {
      const mintKey = String(h?.mint || '').trim().toLowerCase();
      const memo = recentByMint.get(mintKey);
      if (memo && isHoldingDustRecentlyClosed(h, memo, now)) {
        suppressed.push(h);
      } else {
        visible.push(h);
      }
    }

    if (suppressed.length === 0) return base;

    const dustHoldings = [...base.dustHoldings, ...suppressed];
    const dustValueUsd = Number(
      dustHoldings
        .reduce((sum, hh) => sum + Math.max(0, Number(hh?.valueUsd || 0) || 0), 0)
        .toFixed(4),
    );
    return {
      visibleHoldings: visible,
      dustHoldings,
      dustCount: dustHoldings.length,
      dustValueUsd,
    };
  }, [activeSessionWallet, onchainHoldings, openPositionsByMint, recentlyClosedMints]);

  const onchainHoldingsVisible = dustPartition.visibleHoldings;
  const onchainHoldingsDust = dustPartition.dustHoldings;
  const dustCount = dustPartition.dustCount;
  const dustValueUsd = dustPartition.dustValueUsd;

  const trackedMints = useMemo(() => new Set(openPositions.map((p) => p.mint)), [openPositions]);
  const untrackedHoldingsAll = useMemo(
    () => onchainHoldingsVisible.filter((h) => !trackedMints.has(h.mint)),
    [onchainHoldingsVisible, trackedMints],
  );
  const untrackedPartition = useMemo(() => {
    if (!activeSessionWallet) {
      return {
        promptable: [] as OnchainHolding[],
        suppressed: [] as OnchainHolding[],
      };
    }
    const promptable: OnchainHolding[] = [];
    const suppressed: OnchainHolding[] = [];

    for (const holding of untrackedHoldingsAll) {
      const memoKey = `${String(activeSessionWallet).trim().toLowerCase()}:${String(holding.mint || '').trim().toLowerCase()}`;
      const memo = importedHoldingsMemo[memoKey];
      if (!memo) {
        promptable.push(holding);
        continue;
      }
      const prev = safeLamports(memo.amountLamports);
      const current = safeLamports(holding.amountLamports);
      if (prev === BigInt(0) && current > BigInt(0)) {
        promptable.push(holding);
        continue;
      }
      const materiallyHigher = prev > BigInt(0) && (current * IMPORT_MATERIAL_CHANGE_DEN) >= (prev * IMPORT_MATERIAL_CHANGE_NUM);
      if (materiallyHigher) {
        promptable.push(holding);
      } else {
        suppressed.push(holding);
      }
    }

    if (showAllUntracked) {
      return {
        promptable: untrackedHoldingsAll,
        suppressed: [] as OnchainHolding[],
      };
    }
    return { promptable, suppressed };
  }, [activeSessionWallet, importedHoldingsMemo, showAllUntracked, untrackedHoldingsAll]);
  const untrackedHoldings = untrackedPartition.promptable;
  const suppressedUntrackedHoldings = untrackedPartition.suppressed;
  const mismatchCount = (() => {
    const only = onchainDiagnostics?.tokensOnlyIn || {};
    return ['rpcParsed', 'rpcRaw', 'heliusDas', 'solscan']
      .map((k) => (Array.isArray(only?.[k]) ? only[k].length : 0))
      .reduce((a, b) => a + b, 0);
  })();
  const closedScoped = positions.filter(
    (p) =>
      p.status !== 'open' &&
      isPositionInActiveWallet(p, activeWallet) &&
      isReliableTradeForStats(p),
  );
  const scopedTotalTrades = closedScoped.length;
  const scopedWinCount = closedScoped.filter((p) => {
    if (p.status === 'tp_hit') return true;
    if (p.status === 'sl_hit') return false;
    return resolvePositionPnlPercent(p) >= 0;
  }).length;
  const scopedLossCount = Math.max(0, scopedTotalTrades - scopedWinCount);
  const scopedRealizedPnl = closedScoped.reduce((sum, p) => {
    if (typeof p.realPnlSol === 'number') return sum + p.realPnlSol;
    return sum + (typeof p.pnlSol === 'number' ? p.pnlSol : 0);
  }, 0);

  useEffect(() => {
    if (suppressedUntrackedHoldings.length > 0 && suppressedUntrackedHoldings.length !== suppressedPromptLogRef.current) {
      addExecution({
        id: `import-suppress-${Date.now()}`,
        type: 'info',
        symbol: 'SYNC',
        mint: '',
        amount: 0,
        reason: `Import prompt suppressed for unchanged holding(s): ${suppressedUntrackedHoldings.length}`,
        timestamp: Date.now(),
      });
    }
    suppressedPromptLogRef.current = suppressedUntrackedHoldings.length;
  }, [addExecution, suppressedUntrackedHoldings.length]);

  function importUntrackedOnchainHoldings() {
    if (!activeSessionWallet) return;

    let imported = 0;
    for (const h of untrackedHoldings) {
      const alreadyTracked = useSniperStore
        .getState()
        .positions
        .some((p) => p.status === 'open' && p.mint === h.mint && p.walletAddress === activeSessionWallet);
      if (alreadyTracked) continue;

      const derivedPriceUsd = h.uiAmount > 0 && h.valueUsd > 0 ? h.valueUsd / h.uiAmount : 0;
      const safePriceUsd = h.priceUsd > 0 ? h.priceUsd : derivedPriceUsd;
      const valueUsd = h.valueUsd > 0 ? h.valueUsd : (safePriceUsd > 0 ? h.uiAmount * safePriceUsd : 0);
      const estimatedSol = valueUsd > 0 && lastSolPriceUsd > 0
        ? (valueUsd / lastSolPriceUsd)
        : 0.000001;

      addPosition({
        id: `recovered-${h.mint}-${Date.now()}-${imported}`,
        mint: h.mint,
        symbol: h.symbol || h.mint.slice(0, 6),
        name: h.name || h.symbol || `Recovered ${h.mint.slice(0, 6)}`,
        walletAddress: activeSessionWallet,
        entryPrice: safePriceUsd > 0 ? safePriceUsd : 0,
        currentPrice: safePriceUsd > 0 ? safePriceUsd : 0,
        amount: Math.max(0, h.uiAmount),
        amountLamports: h.amountLamports,
        solInvested: Math.max(0.000001, estimatedSol),
        pnlPercent: 0,
        pnlSol: 0,
        entryTime: Date.now(),
        status: 'open',
        manualOnly: true,
        recoveredFrom: 'onchain-sync',
        score: 50,
        recommendedSl: config.stopLossPct,
        recommendedTp: config.takeProfitPct,
        recommendedTrail: config.trailingStopPct,
        highWaterMarkPct: 0,
        assetType: assetFilter,
      });
      recordImportedHolding(activeSessionWallet, h.mint, h.amountLamports);
      imported++;
    }

    addExecution({
      id: `recovery-import-${Date.now()}`,
      type: 'info',
      symbol: 'RECOVERY',
      mint: '',
      amount: 0,
      reason:
        imported > 0
          ? `Imported ${imported} on-chain holding${imported === 1 ? '' : 's'} (manual-only, no auto-exit)`
          : 'No new on-chain holdings to import',
      timestamp: Date.now(),
    });
    setShowAllUntracked(false);
  }

  function getConnection(): Connection {
    if (!connectionRef.current) {
      connectionRef.current = getSharedConnection();
    }
    return connectionRef.current;
  }

  const syncOnchainHoldings = useCallback(async (showSpinner = false, forceFullScan = false) => {
    if (!activeSessionWallet) {
      setOnchainHoldings([]);
      setOnchainError(null);
      setOnchainWarnings([]);
      setOnchainDiagnostics(null);
      setShowAllUntracked(false);
      return;
    }
    if (!forceFullScan) {
      setShowAllUntracked(false);
    }
    if (showSpinner) setOnchainLoading(true);
    try {
      const res = await fetch(`/api/session-wallet/portfolio?wallet=${encodeURIComponent(activeSessionWallet)}${forceFullScan ? '&fullScan=1' : ''}`, {
        cache: 'no-store',
      });
      const json = await res.json().catch(() => ({} as any));
      if (!res.ok) {
        throw new Error(json?.error || `HTTP ${res.status}`);
      }

      const holdings: OnchainHolding[] = Array.isArray(json?.holdings) ? json.holdings : [];
      setOnchainHoldings(holdings);
      setOnchainLastSync(typeof json?.fetchedAt === 'number' ? json.fetchedAt : Date.now());
      setOnchainSource(
        json?.source === 'solscan' || json?.source === 'rpc' || json?.source === 'hybrid'
          ? json.source
          : 'unknown',
      );
      setOnchainWarnings(Array.isArray(json?.warnings) ? json.warnings.map((w: unknown) => String(w)) : []);
      setOnchainDiagnostics(json?.diagnostics || null);
      setOnchainError(null);

      // Reconcile stale local opens only when we have at least one healthy source in this snapshot.
      // This avoids false "no holdings" reconciliation during upstream outages / auth failures.
      const sourceStatus = json?.diagnostics?.sourceStatus || {};
      const hasHealthySource = ['rpcParsed', 'rpcRaw', 'heliusDas', 'solscan'].some(
        (k) => !!sourceStatus?.[k]?.ok,
      );

      // Only prune / update import-suppression memo when we trust this snapshot.
      // Otherwise transient RPC/DAS/Solscan failures can cause repeated "Import Missing Holdings"
      // prompts even though the user already imported the same holdings.
      if (hasHealthySource) {
        const liveMints = holdings
          .filter((h) => String(h?.amountLamports || '0') !== '0')
          .map((h) => String(h?.mint || '').trim())
          .filter(Boolean);
        pruneImportedHoldingMemo(activeSessionWallet, liveMints);

        const memoSnapshot = useSniperStore.getState().importedHoldingsMemo;
        for (const holding of holdings) {
          if (!holding?.mint) continue;
          const memoKey = `${String(activeSessionWallet).trim().toLowerCase()}:${String(holding.mint).trim().toLowerCase()}`;
          if (memoSnapshot[memoKey]) {
            updateImportedHoldingSeen(activeSessionWallet, holding.mint, holding.amountLamports);
          }
        }
      }
      if (hasHealthySource) {
        const state = useSniperStore.getState();
        const openByMint = new Map<string, DustAwarePosition>();
        const managedOpen = filterTradeManagedOpenPositionsForActiveWallet(state.positions, activeSessionWallet, { excludeClosing: false });
        for (const p of managedOpen) {
          if (p.status !== 'open') continue;
          if (!p.mint) continue;
          const prev = openByMint.get(p.mint);
          if (!prev || Number(p.amount || 0) > Number(prev.amount || 0)) {
            openByMint.set(p.mint, {
              mint: p.mint,
              amount: Number(p.amount || 0),
              walletAddress: p.walletAddress,
              status: p.status,
              manualOnly: false,
            });
          }
        }
        let visible = partitionDustHoldings(holdings, openByMint).visibleHoldings;
        // Also suppress recently-closed post-sell residues (price often missing) so they don't
        // re-trigger import prompts or block reconciliation.
        try {
          const walletKey = String(activeSessionWallet).trim().toLowerCase();
          const recents = Object.values(useSniperStore.getState().recentlyClosedMints || {}).filter(
            (e: any) => String(e?.wallet || '').trim().toLowerCase() === walletKey,
          ) as Array<any>;
          if (recents.length > 0) {
            const recentByMint = new Map<string, RecentlyClosedMintMemo>();
            for (const e of recents) {
              const mintKey = String(e?.mint || '').trim().toLowerCase();
              if (!mintKey) continue;
              recentByMint.set(mintKey, {
                mint: mintKey,
                closedAt: Number(e?.closedAt || 0),
                amountLamportsAtClose: e?.amountLamports ? String(e.amountLamports) : undefined,
                uiAmountAtClose: Number.isFinite(Number(e?.uiAmount)) ? Number(e.uiAmount) : undefined,
              });
            }
            if (recentByMint.size > 0) {
              const nowMs = Date.now();
              visible = visible.filter((h: any) => {
                const mintKey = String(h?.mint || '').trim().toLowerCase();
                const memo = recentByMint.get(mintKey);
                return !(memo && isHoldingDustRecentlyClosed(h, memo, nowMs));
              });
            }
          }
        } catch {
          // ignore
        }
        const onchainMints = new Set(
          visible
            .filter((h: any) => String(h?.amountLamports || '0') !== '0')
            .map((h: any) => String(h?.mint || '').trim())
            .filter(Boolean),
        );
        const now = Date.now();
        const stale = state.positions.filter(
          (p) =>
            p.status === 'open' &&
            p.walletAddress === activeSessionWallet &&
            !onchainMints.has(p.mint) &&
            !p.manualOnly &&
            !p.isClosing &&
            now - Number(p.entryTime || 0) >= RECONCILE_GRACE_MS,
        );
        if (stale.length > 0) {
          const staleMints = [...new Set(stale.map((p) => p.symbol || p.mint.slice(0, 6)))].slice(0, 6);
          for (const row of stale) {
            reconcilePosition(row.id, 'no_onchain_balance');
          }
          addExecution({
            id: `reconcile-${Date.now()}`,
            type: 'info',
            symbol: 'SYNC',
            mint: '',
            amount: 0,
            reason: `Reconciled ${stale.length} stale local position${stale.length === 1 ? '' : 's'} (no on-chain balance): ${staleMints.join(', ')}`,
            timestamp: Date.now(),
          });
        }

        // Also reconcile/close recovered manual-only rows when the on-chain balance is now
        // effectively zero (including dust-suppressed residues). This prevents "ghost" open
        // positions that keep reappearing after sells due to tiny remnants.
        const staleRecovered = state.positions.filter(
          (p) =>
            p.status === 'open' &&
            p.walletAddress === activeSessionWallet &&
            p.manualOnly &&
            p.recoveredFrom === 'onchain-sync' &&
            !onchainMints.has(p.mint) &&
            !p.isClosing &&
            now - Number(p.entryTime || 0) >= RECONCILE_GRACE_MS,
        );
        if (staleRecovered.length > 0) {
          const staleMints = [...new Set(staleRecovered.map((p) => p.symbol || p.mint.slice(0, 6)))].slice(0, 6);
          for (const row of staleRecovered) {
            reconcilePosition(row.id, 'no_onchain_balance');
          }
          addExecution({
            id: `reconcile-recovered-${Date.now()}`,
            type: 'info',
            symbol: 'SYNC',
            mint: '',
            amount: 0,
            reason: `Archived ${staleRecovered.length} recovered dust/zero holding${staleRecovered.length === 1 ? '' : 's'}: ${staleMints.join(', ')}`,
            timestamp: Date.now(),
          });
        }
      } else if (showSpinner) {
        addExecution({
          id: `sync-degraded-${Date.now()}`,
          type: 'info',
          symbol: 'SYNC',
          mint: '',
          amount: 0,
          reason: 'On-chain sync degraded (no healthy source); skipped reconciliation this cycle.',
          timestamp: Date.now(),
        });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Sync failed';
      setOnchainError(msg);
      setOnchainSource('unknown');
    } finally {
      if (showSpinner) setOnchainLoading(false);
    }
  }, [activeSessionWallet, addExecution, pruneImportedHoldingMemo, reconcilePosition, updateImportedHoldingSeen]);

  useEffect(() => {
    if (!activeSessionWallet) {
      setOnchainHoldings([]);
      setOnchainError(null);
      setOnchainLastSync(0);
      setOnchainSource('unknown');
      setOnchainWarnings([]);
      setOnchainDiagnostics(null);
      setShowAllUntracked(false);
      return;
    }

    let cancelled = false;
    const run = async (showSpinner: boolean) => {
      if (cancelled) return;
      await syncOnchainHoldings(showSpinner);
    };

    void run(true);
    const timer = setInterval(() => { void run(false); }, 45_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [activeSessionWallet, syncOnchainHoldings]);

  type CloseStatus = 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed';
  async function handleClose(id: string, status: CloseStatus = 'closed') {
    const pos = positions.find(p => p.id === id);
    if (!pos || pos.isClosing) return;

    // Manual close = real sell. Never "close the record" without swapping out.
    const session = tradeSignerMode === 'session'
      ? (
          sessionWalletPubkey
            ? await loadSessionWalletByPublicKey(sessionWalletPubkey, { mainWallet: address || undefined })
            : await loadSessionWalletFromStorage({ mainWallet: address || undefined })
        )
      : null;
    const canUseSession =
      tradeSignerMode === 'session' &&
      !!sessionWalletPubkey &&
      !!session &&
      session.publicKey === sessionWalletPubkey &&
      pos.walletAddress === sessionWalletPubkey;

    const signerAddress = canUseSession ? sessionWalletPubkey! : address;
    const signerSignTransaction = canUseSession
      ? (async (tx: VersionedTransaction) => {
          tx.sign([session!.keypair]);
          return tx;
        })
      : (signTransaction as ((tx: VersionedTransaction) => Promise<VersionedTransaction>) | undefined);

    if (!signerAddress || !signerSignTransaction) {
      addExecution({
        id: `close-${Date.now()}-${id.slice(-4)}`,
        type: 'error',
        symbol: pos.symbol,
        mint: pos.mint,
        amount: pos.solInvested,
        reason: canUseSession ? 'Session wallet not ready' : 'Connect Phantom to sell this position',
        timestamp: Date.now(),
      });
      return;
    }

    // Clear any stale "exit pending" marker once user chooses to act.
    updatePosition(id, { exitPending: undefined });
    setPositionClosing(id, true);

    try {
      const connection = getConnection();

      // Prefer the exact swap output amount recorded at entry, but clamp to wallet balance if needed.
      let amountLamports = pos.amountLamports;
      const bal = await getOwnerTokenBalanceLamports(connection, signerAddress, pos.mint);
      if (!amountLamports || amountLamports === '0') {
        if (!bal || bal.amountLamports === '0') throw new Error('No token balance found to sell');
        amountLamports = bal.amountLamports;
        updatePosition(id, { amountLamports });
      } else if (bal && bal.amountLamports !== '0') {
        // For auto-managed entries in the session wallet, sell the full wallet balance so we can
        // reclaim rent by closing the token account.
        if (canUseSession && pos.entrySource === 'auto') {
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
      // Slippage waterfall:
      // - Normal manual closes cap at 15%
      // - Emergency exits (SL / TRAIL / EXPIRED) allow up to 100% to maximize exit probability on micro-caps
      const slippageBase = config.slippageBps;
      const isEmergencyExit = status === 'sl_hit' || status === 'trail_stop' || status === 'expired';
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

      let quote = null as Awaited<ReturnType<typeof getSellQuote>>;
      for (const bps of waterfall) {
        quote = await getSellQuote(pos.mint, amountLamports, bps);
        if (quote) break;
      }

      if (!quote) {
        throw new Error(
          `No sell route found at up to ${isEmergencyExit ? '100%' : '15%'} slippage - token may have no liquidity. Use Write Off to remove.`,
        );
      }

      // Realizable exit value from the quote (better than chart prices for low-liquidity tokens).
      const exitValueSol = Number(BigInt(quote.outAmount)) / 1e9;
      const realPnlPct = ((exitValueSol - pos.solInvested) / pos.solInvested) * 100;
      const realPnlSol = pos.solInvested * (realPnlPct / 100);

      const result = await executeSwapFromQuote(
        connection,
        signerAddress,
        quote,
        signerSignTransaction,
        config.useJito,
      );

      if (!result.success) throw new Error(result.error || 'Sell failed');

      // Update final P&L in the store before closing, so stats/logs reflect realizable value.
      updatePosition(id, {
        pnlPercent: realPnlPct,
        pnlSol: realPnlSol,
        highWaterMarkPct: Math.max(pos.highWaterMarkPct ?? 0, realPnlPct),
      });
      closePosition(id, status, result.txHash, exitValueSol);

      // If this position lives in the session wallet, reclaim rent immediately by closing the empty
      // token account(s) for this mint (best-effort).
      if (canUseSession) {
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
      }
      // Best-effort post-close resync so post-sell dust gets hidden/reconciled quickly.
      void syncOnchainHoldings(false, true);

      // If this position lives in the session wallet, bank excess SOL back to the main wallet.
      // Leaves remaining budget + fee buffer inside the session wallet.
      if (canUseSession) {
        try {
          const s = useSniperStore.getState();
          const remaining = typeof s.budgetRemaining === 'function'
            ? s.budgetRemaining()
            : Math.round((s.budget.budgetSol - s.budget.spent) * 1000) / 1000;
          const reserve = Math.max(0.01, remaining + 0.002);
          const sweepSig = await sweepExcessToMainWallet(session!.keypair, session!.mainWallet, reserve);
          if (sweepSig) {
            addExecution({
              id: `sweep-${Date.now()}-${id.slice(-4)}`,
              type: 'info',
              symbol: pos.symbol,
              mint: pos.mint,
              amount: 0,
              txHash: sweepSig,
              reason: `Auto-swept excess SOL to main wallet (reserve ${reserve.toFixed(3)} SOL)`,
              timestamp: Date.now(),
            });
          }
        } catch {
          // ignore sweep errors
        }
      }
    } catch (err) {
      setPositionClosing(id, false);
      const msg = err instanceof Error ? err.message : 'Unknown error';
      addExecution({
        id: `close-fail-${Date.now()}-${id.slice(-4)}`,
        type: 'error',
        symbol: pos.symbol,
        mint: pos.mint,
        amount: pos.solInvested,
        reason: `Manual close failed: ${msg}`,
        timestamp: Date.now(),
      });
    }
  }

  const hasRecord = scopedTotalTrades > 0 || openPositions.length > 0;
  const canReset = openPositions.length === 0 && hasRecord;

  function handleReset() {
    if (!confirmReset) {
      setConfirmReset(true);
      setTimeout(() => setConfirmReset(false), 3000);
      return;
    }
    resetSession();
    setConfirmReset(false);
  }

  function handleWriteOff(id: string) {
    const pos = positions.find(p => p.id === id);
    if (!pos) return;
    updatePosition(id, { pnlPercent: -100, pnlSol: -pos.solInvested, exitPending: undefined });
    closePosition(id, 'sl_hit');
    addExecution({
      id: `writeoff-${Date.now()}-${id.slice(-4)}`,
      type: 'sl_exit',
      symbol: pos.symbol,
      mint: pos.mint,
      amount: pos.solInvested,
      pnlPercent: -100,
      reason: `Written off (no liquidity) — ${pos.solInvested.toFixed(3)} SOL lost`,
      timestamp: Date.now(),
    });
  }

  async function handleCloseAll() {
    if (!confirmCloseAll) {
      setConfirmCloseAll(true);
      setTimeout(() => setConfirmCloseAll(false), 3000);
      return;
    }
    setConfirmCloseAll(false);
    const toClose = openPositions.filter(p => !p.isClosing);
    if (toClose.length === 0) return;
    const autoWasOn = useSniperStore.getState().config.autoSnipe;
    acquireOperationLock(`Close All in progress (${toClose.length} positions)`, 'close_all');
    setAutomationState('closing_all');
    addExecution({
      id: `close-all-start-${Date.now()}`,
      type: 'info',
      symbol: 'SYSTEM',
      mint: '',
      amount: 0,
      reason: `Close All initiated — buys paused while closing ${toClose.length} position${toClose.length === 1 ? '' : 's'}${autoWasOn ? '; auto will resume after completion' : ''}`,
      timestamp: Date.now(),
    });
    setClosingAllCount({ done: 0, total: toClose.length });

    let doneCount = 0;
    let failCount = 0;
    const CLOSE_ONE_TIMEOUT_MS = 120_000;
    try {
      // IMPORTANT: close sequentially to avoid Phantom popup contention/timeouts.
      for (const p of toClose) {
        try {
          await withTimeout(
            handleClose(p.id, 'closed'),
            CLOSE_ONE_TIMEOUT_MS,
            `Close timeout for ${p.symbol}`,
          );
          const after = useSniperStore.getState().positions.find(pos => pos.id === p.id);
          if (after && after.status === 'open') failCount++;
        } catch (err) {
          failCount++;
          setPositionClosing(p.id, false);
          const reason = err instanceof Error ? err.message : `Close timeout for ${p.symbol}`;
          addExecution({
            id: `close-all-fail-${Date.now()}-${p.id.slice(-4)}`,
            type: 'error',
            symbol: p.symbol,
            mint: p.mint,
            amount: p.solInvested,
            reason: `Close All failed for ${p.symbol}: ${reason}`,
            timestamp: Date.now(),
          });
        } finally {
          doneCount++;
          setClosingAllCount({ done: doneCount, total: toClose.length });
        }
      }

      if (failCount > 0) {
        addExecution({
          id: `close-all-${Date.now()}`,
          type: 'error',
          symbol: 'ALL',
          mint: '',
          amount: 0,
          reason: `Close All: ${doneCount - failCount}/${toClose.length} succeeded, ${failCount} failed`,
          timestamp: Date.now(),
        });
      }
    } finally {
      setClosingAllCount(null);
      releaseOperationLock();
      setAutomationState('idle');
      addExecution({
        id: `close-all-done-${Date.now()}`,
        type: 'info',
        symbol: 'SYSTEM',
        mint: '',
        amount: 0,
        reason: `Close All complete — execution lock released${autoWasOn ? '; auto resumed' : ''}`,
        timestamp: Date.now(),
      });
    }
  }

  return (
    <div className="card-glass p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Positions</h2>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono">
          <span className="text-text-muted">Open: <span className="text-text-primary font-bold">{totalOpen.toFixed(2)} SOL</span></span>
          <span className={unrealizedPnl >= 0 ? 'text-accent-neon' : 'text-accent-error'}>
            {unrealizedPnl >= 0 ? '+' : ''}{unrealizedPnl.toFixed(3)} SOL
          </span>
        </div>
      </div>

      {/* ─── SESSION STATS BAR ─── */}
      {(scopedTotalTrades > 0 || managedOpenPositions.length > 0) && (
        <div className="grid grid-cols-4 gap-2 mb-3 p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-text-muted uppercase tracking-wider">Trades</span>
            <span className="text-xs font-bold font-mono text-text-primary">
              {scopedTotalTrades + managedOpenPositions.length}
              {managedOpenPositions.length > 0 && (
                <span className="text-[8px] text-text-muted font-normal ml-0.5">({managedOpenPositions.length} open)</span>
              )}
            </span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-text-muted uppercase tracking-wider">Win Rate</span>
            {(() => {
              const totalClosed = scopedTotalTrades;
              const openWins = managedOpenPositions.filter((p) => resolvePositionPnlPercent(p) > 0).length;
              const allWins = scopedWinCount + openWins;
              const allTotal = totalClosed + managedOpenPositions.length;
              const rate = allTotal > 0 ? Math.round((allWins / allTotal) * 100) : 0;
              return (
                <span className={`text-xs font-bold font-mono ${allTotal > 0 && rate >= 50 ? 'text-accent-neon' : 'text-accent-error'}`}>
                  {allTotal > 0 ? `${rate}%` : '—'}
                </span>
              );
            })()}
          </div>
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-text-muted uppercase tracking-wider">W / L</span>
            {(() => {
              const openWins = managedOpenPositions.filter((p) => resolvePositionPnlPercent(p) > 0).length;
              const openLosses = managedOpenPositions.filter((p) => resolvePositionPnlPercent(p) <= 0).length;
              return (
                <span className="text-xs font-bold font-mono">
                  <span className="text-accent-neon">{scopedWinCount + openWins}</span>
                  <span className="text-text-muted/50"> / </span>
                  <span className="text-accent-error">{scopedLossCount + openLosses}</span>
                </span>
              );
            })()}
          </div>
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-text-muted uppercase tracking-wider">Net PnL</span>
            {(() => {
              const combinedPnl = scopedRealizedPnl + unrealizedPnl;
              return (
                <span className={`text-xs font-bold font-mono ${combinedPnl >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                  {combinedPnl >= 0 ? '+' : ''}{combinedPnl.toFixed(3)}
                </span>
              );
            })()}
          </div>
        </div>
      )}

      {activeSessionWallet && (
        <div className="mb-3 rounded-lg border border-border-primary bg-bg-secondary/40 p-2.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 min-w-0">
              <Wallet className="w-3.5 h-3.5 text-accent-neon flex-shrink-0" />
              <span className="text-[10px] font-semibold text-text-primary truncate">
                Session Wallet On-chain Sync
              </span>
              <span className="text-[9px] font-mono text-text-muted uppercase">
                {onchainSource}
              </span>
              {mismatchCount > 0 && (
                <span className="text-[9px] font-mono text-accent-warning uppercase">
                  mismatch {mismatchCount}
                </span>
              )}
              {onchainLastSync > 0 && (
                <span className="text-[9px] text-text-muted font-mono whitespace-nowrap">
                  {new Date(onchainLastSync).toLocaleTimeString()}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowSyncEvidence((v) => !v)}
                className="inline-flex items-center gap-1 text-[9px] font-mono px-2 py-1 rounded border border-border-primary bg-bg-tertiary text-text-secondary hover:text-text-primary hover:border-border-hover"
                title="Show per-source sync evidence"
              >
                {showSyncEvidence ? 'Hide Evidence' : 'View Evidence'}
              </button>
              <button
                onClick={() => void syncOnchainHoldings(true)}
                disabled={onchainLoading}
                className="inline-flex items-center gap-1 text-[9px] font-mono px-2 py-1 rounded border border-border-primary bg-bg-tertiary text-text-secondary hover:text-text-primary hover:border-border-hover disabled:opacity-60"
                title="Refresh on-chain token balances from wallet portfolio APIs"
              >
                <RefreshCw className={`w-3 h-3 ${onchainLoading ? 'animate-spin' : ''}`} />
                Sync
              </button>
              <button
                onClick={() => {
                  setShowAllUntracked(true);
                  void syncOnchainHoldings(true, true);
                }}
                disabled={onchainLoading}
                className="inline-flex items-center gap-1 text-[9px] font-mono px-2 py-1 rounded border border-accent-warning/30 bg-accent-warning/10 text-accent-warning hover:bg-accent-warning/15 disabled:opacity-60"
                title="Bypass normal caches and run a full source scan"
              >
                Full Scan
              </button>
            </div>
          </div>

          {onchainError && (
            <div className="mt-2 text-[10px] text-accent-warning flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" />
              {onchainError}
            </div>
          )}
          {onchainWarnings.length > 0 && (
            <div className="mt-2 space-y-1">
              {onchainWarnings.slice(0, 3).map((warn, idx) => (
                <div key={`warn-${idx}`} className="text-[10px] text-accent-warning flex items-start gap-1.5">
                  <AlertTriangle className="w-3 h-3 mt-[1px]" />
                  <span>{warn}</span>
                </div>
              ))}
            </div>
          )}

          {onchainDiagnostics?.sourceStatus && (
            <div className="mt-2 flex flex-wrap gap-1">
              {(['rpcParsed', 'rpcRaw', 'heliusDas', 'solscan'] as const).map((sourceKey) => {
                const status = onchainDiagnostics.sourceStatus?.[sourceKey];
                const ok = !!status?.ok;
                return (
                  <span
                    key={sourceKey}
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                      ok
                        ? 'bg-accent-neon/10 border-accent-neon/20 text-accent-neon'
                        : 'bg-accent-error/10 border-accent-error/20 text-accent-error'
                    }`}
                    title={ok ? `${sourceKey}: ok` : `${sourceKey}: ${status?.error || 'unavailable'}`}
                  >
                    {sourceKey}
                  </span>
                );
              })}
            </div>
          )}

          <div className="mt-2 text-[10px] text-text-muted">
            {onchainHoldings.length > 0
              ? `${onchainHoldings.length} token holding${onchainHoldings.length === 1 ? '' : 's'} detected on-chain`
              : 'No token holdings detected on-chain'}
          </div>

          {showSyncEvidence && (
            <div className="mt-2 rounded border border-border-primary bg-bg-tertiary/40 p-2 space-y-2">
              <div className="text-[10px] font-semibold text-text-primary">Source Evidence</div>
              <div className="text-[10px] text-text-muted">
                Consensus tokens: {onchainDiagnostics?.consensusTokenCount ?? onchainHoldings.length}
              </div>
              {onchainDiagnostics?.countsBySource && (
                <div className="grid grid-cols-2 gap-1 text-[10px] font-mono text-text-muted">
                  <div>rpcParsed: {onchainDiagnostics.countsBySource.rpcParsed ?? 0}</div>
                  <div>rpcRaw: {onchainDiagnostics.countsBySource.rpcRaw ?? 0}</div>
                  <div>heliusDas: {onchainDiagnostics.countsBySource.heliusDas ?? 0}</div>
                  <div>solscan: {onchainDiagnostics.countsBySource.solscan ?? 0}</div>
                </div>
              )}
              {onchainHoldings.length > 0 && (
                <div className="max-h-40 overflow-y-auto custom-scrollbar space-y-1">
                  {onchainHoldings.slice(0, 12).map((h) => (
                    <div key={`evidence-${h.mint}`} className="text-[10px] rounded border border-border-primary/70 px-2 py-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-semibold text-text-primary truncate">{h.symbol || h.mint.slice(0, 6)}</span>
                        <span className="font-mono text-text-muted">{h.accountCount ?? h.accounts?.length ?? 1} accts</span>
                      </div>
                      <div className="font-mono text-text-muted truncate">
                        {(h.sources || []).join(', ') || 'unknown'}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {(untrackedHoldings.length > 0 || suppressedUntrackedHoldings.length > 0) && (
            <div className="mt-2 p-2 rounded border border-accent-warning/30 bg-accent-warning/[0.06]">
              {untrackedHoldings.length > 0 && (
                <>
                  <div className="text-[10px] text-accent-warning font-semibold mb-1">
                    {untrackedHoldings.length} holding{untrackedHoldings.length === 1 ? '' : 's'} not tracked locally
                  </div>
                  <button
                    onClick={importUntrackedOnchainHoldings}
                    className="w-full text-[10px] py-1.5 rounded bg-accent-warning/15 border border-accent-warning/35 text-accent-warning hover:bg-accent-warning/20"
                    title="Import missing holdings as recoverable positions so you can close them in one place"
                  >
                    Import Missing Holdings
                  </button>
                </>
              )}
              {suppressedUntrackedHoldings.length > 0 && (
                <div className={`${untrackedHoldings.length > 0 ? 'mt-2' : ''} text-[10px] text-text-muted`}>
                  {suppressedUntrackedHoldings.length} previously imported holding{suppressedUntrackedHoldings.length === 1 ? '' : 's'} suppressed (unchanged balance)
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Reset Record button — only visible when no open positions and there's data */}
      {canReset && (
        <button
          onClick={handleReset}
          className={`w-full mb-3 py-2 rounded-lg text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5 ${
            confirmReset
              ? 'bg-accent-error/20 text-accent-error border border-accent-error/40'
              : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-accent-warning/40 hover:text-accent-warning'
          }`}
        >
          <RotateCcw className="w-3 h-3" />
          {confirmReset ? 'Click again to confirm reset' : `Reset Record (${scopedTotalTrades} trades, ${scopedRealizedPnl >= 0 ? '+' : ''}${scopedRealizedPnl.toFixed(3)} SOL)`}
        </button>
      )}

      {/* Close All button — visible when 2+ open positions */}
      {openPositions.length >= 2 && (
        <button
          onClick={handleCloseAll}
          disabled={!!closingAllCount}
          className={`w-full mb-3 py-2 rounded-lg text-[11px] font-semibold transition-all flex items-center justify-center gap-1.5 ${
            closingAllCount
              ? 'bg-accent-warning/15 text-accent-warning border border-accent-warning/30 cursor-wait'
              : confirmCloseAll
                ? 'bg-accent-error/20 text-accent-error border border-accent-error/40 animate-pulse'
                : 'bg-accent-error/[0.06] text-accent-error/80 border border-accent-error/20 hover:border-accent-error/40 hover:text-accent-error'
          }`}
        >
          {closingAllCount ? (
            <>
              <Loader2 className="w-3 h-3 animate-spin" />
              Closing {Math.min(closingAllCount.done + 1, closingAllCount.total)}/{closingAllCount.total}...
            </>
          ) : confirmCloseAll ? (
            <>
              <X className="w-3 h-3" />
              Click again to close all {openPositions.length} positions
            </>
          ) : (
            <>
              <X className="w-3 h-3" />
              Close All ({openPositions.length})
            </>
          )}
        </button>
      )}

      {/* Open Positions */}
      {openPositions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 gap-2">
          <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center">
            <DollarSign className="w-4 h-4 text-text-muted" />
          </div>
          <p className="text-[11px] text-text-muted">
            {(untrackedHoldings.length > 0 || suppressedUntrackedHoldings.length > 0) ? 'No local positions (on-chain holdings found above)' : 'No open positions'}
          </p>
        </div>
      ) : (
        <div className="space-y-2 mb-4">
          {openPositions.map((pos) => (
            <PositionRow
              key={pos.id}
              pos={pos}
              isSelected={selectedMint === pos.mint}
              onClose={handleClose}
              onWriteOff={handleWriteOff}
              onSelect={() => setSelectedMint(pos.mint)}
            />
          ))}
        </div>
      )}

      {/* Closed Positions (recent) */}
      {closedPositions.length > 0 && (
        <>
          <div className="flex items-center gap-2 mb-2 mt-4 pt-3 border-t border-border-primary">
            <span className="text-[10px] text-text-muted uppercase tracking-wider font-medium">Recent Closes</span>
          </div>
          <div className="space-y-1.5">
            {closedPositions.map((pos) => (
              <div key={pos.id} className="flex items-center justify-between p-2 rounded-lg bg-bg-secondary/40 text-[11px]">
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    pos.status === 'tp_hit' ? 'bg-accent-neon' : pos.status === 'trail_stop' ? 'bg-accent-warning' : pos.status === 'expired' ? 'bg-accent-warning' : pos.status === 'sl_hit' ? 'bg-accent-error' : 'bg-text-muted'
                  }`} />
                  <span className="font-bold">{pos.symbol}</span>
                  <span className="text-[9px] text-text-muted font-mono uppercase">{pos.status.replace('_', ' ')}</span>
                </div>
                {(() => {
                  const closePct = resolvePositionPnlPercent(pos);
                  return (
                    <span className={`font-mono font-bold ${closePct >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                      {closePct >= 0 ? '+' : ''}{closePct.toFixed(1)}%
                    </span>
                  );
                })()}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function PositionRow({ pos, isSelected, onClose, onWriteOff, onSelect }: {
  pos: any;
  isSelected: boolean;
  onClose: (id: string, status?: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed') => void | Promise<void>;
  onWriteOff: (id: string) => void;
  onSelect: () => void;
}) {
  const { connected, connecting, connect, address } = usePhantomWallet();
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const [canAutoRetry, setCanAutoRetry] = useState(false);
  useEffect(() => {
    if (tradeSignerMode !== 'session' || !sessionWalletPubkey || pos.walletAddress !== sessionWalletPubkey) {
      setCanAutoRetry(false);
      return;
    }
    let cancelled = false;
    (async () => {
      const session =
        await loadSessionWalletByPublicKey(sessionWalletPubkey, { mainWallet: address || undefined }) ||
        await loadSessionWalletFromStorage({ mainWallet: address || undefined });
      if (!cancelled) setCanAutoRetry(!!session);
    })();
    return () => { cancelled = true; };
  }, [tradeSignerMode, sessionWalletPubkey, pos.walletAddress, address]);
  const [, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 30_000);
    return () => clearInterval(t);
  }, []);
  const ageMin = Math.floor((Date.now() - pos.entryTime) / 60000);
  const ageLabel = ageMin < 1 ? '<1m' : ageMin < 60 ? `${ageMin}m` : `${(ageMin / 60).toFixed(1)}h`;
  const maxAgeHours = useSniperStore.getState().config.maxPositionAgeHours ?? 4;
  const ageHours = ageMin / 60;
  const nearExpiry = maxAgeHours > 0 && ageHours >= maxAgeHours * 0.75;
  const ageColor = nearExpiry ? 'text-accent-warning' : 'text-text-muted';
  // Countdown to expiry
  const remainingMin = maxAgeHours > 0 ? Math.max(0, maxAgeHours * 60 - ageMin) : -1;
  const countdownLabel = remainingMin < 0 ? '' : remainingMin === 0 ? 'EXPIRED' : remainingMin < 60 ? `${remainingMin}m left` : `${(remainingMin / 60).toFixed(1)}h left`;

  const cfg = useSniperStore.getState().config;
  const useRecommendedExits = cfg.useRecommendedExits !== false;
  const displayPnlPercent = resolvePositionPnlPercent(pos);

  // Exits: either per-position recommended or forced global values.
  const sl = useRecommendedExits ? (pos.recommendedSl ?? cfg.stopLossPct) : cfg.stopLossPct;
  const tp = useRecommendedExits ? (pos.recommendedTp ?? cfg.takeProfitPct) : cfg.takeProfitPct;
  const isBlueChip = isBlueChipLongConvictionSymbol(pos.symbol);
  const targets = computeTargetsFromEntryUsd(pos.entryPrice, sl, tp);
  // Per-position adaptive trailing stop — matches risk management hook logic
  const trailPct = pos.recommendedTrail ?? cfg.trailingStopPct;
  const hwm = pos.highWaterMarkPct ?? 0;

  // Trigger proximity detection (trail only arms when HWM >= trail%, matching risk manager fix)
  const nearSl = displayPnlPercent <= -(sl * 0.8);
  const nearTp = displayPnlPercent >= (tp * 0.8);
  const trailDrop = trailPct > 0 && hwm >= trailPct ? hwm - displayPnlPercent : 0;
  const nearTrail = trailPct > 0 && hwm >= trailPct && trailDrop >= (trailPct * 0.8);
  const hasExitPending = !!pos.exitPending;
  const nearTrigger = nearSl || nearTp || nearTrail || nearExpiry || hasExitPending;

  const pending = pos.exitPending as undefined | {
    trigger: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired';
    pnlPercent: number;
    exitValueSol?: number;
    quoteAvailable?: boolean;
    reason?: string;
    updatedAt: number;
  };
  const pendingLabel = pending?.trigger === 'tp_hit' ? 'TP'
    : pending?.trigger === 'trail_stop' ? 'TRAIL'
      : pending?.trigger === 'expired' ? 'EXPIRED'
        : pending?.trigger === 'sl_hit' ? 'SL'
          : null;
  const pendingColor = pending?.trigger === 'tp_hit'
    ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/25'
    : pending?.trigger === 'sl_hit'
      ? 'bg-accent-error/10 text-accent-error border-accent-error/25'
      : 'bg-accent-warning/10 text-accent-warning border-accent-warning/25';

  const closeTitle = canAutoRetry ? 'Sell now (Session Wallet)' : 'Sell via Phantom';

  return (
    <div
      onClick={onSelect}
      className={`relative p-3 rounded-lg border transition-all cursor-pointer ${
        nearTrigger ? 'animate-pulse' : ''
      } ${
        isSelected
          ? 'bg-accent-neon/[0.06] border-accent-neon/40 ring-1 ring-accent-neon/20'
          : nearSl
            ? 'bg-accent-error/[0.08] border-accent-error/40 ring-1 ring-accent-error/20'
            : nearTp
              ? 'bg-accent-neon/[0.08] border-accent-neon/40 ring-1 ring-accent-neon/20'
              : nearTrail
                ? 'bg-accent-warning/[0.08] border-accent-warning/40 ring-1 ring-accent-warning/20'
                : displayPnlPercent >= 0
                  ? 'bg-accent-neon/[0.03] border-accent-neon/20 hover:border-accent-neon/30'
                  : 'bg-accent-error/[0.03] border-accent-error/20 hover:border-accent-error/30'
      }`}
    >
      {/* Row 1: Symbol + SOL | P&L + action icons */}
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm font-bold truncate">{pos.symbol}</span>
          <span className="text-[9px] font-mono text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded flex-shrink-0">
            {pos.solInvested.toFixed(2)} SOL
          </span>
          {isSelected && <BarChart3 className="w-3 h-3 text-accent-neon flex-shrink-0" />}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <span className={`text-sm font-mono font-bold ${displayPnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
            {displayPnlPercent >= 0 ? '+' : ''}{displayPnlPercent.toFixed(1)}%
          </span>
          <button
            onClick={(e) => { e.stopPropagation(); onWriteOff(pos.id); }}
            disabled={pos.isClosing}
            className="w-6 h-6 rounded-full flex items-center justify-center transition-all bg-text-muted/5 text-text-muted/50 hover:bg-accent-error/10 hover:text-accent-error flex-shrink-0"
            title="Write off (mark as -100% loss, no sell)"
          >
            <Trash2 className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); void onClose(pos.id, 'closed'); }}
            disabled={pos.isClosing}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
              pos.isClosing
                ? 'bg-bg-tertiary text-text-muted cursor-not-allowed'
                : 'bg-accent-error/10 text-accent-error hover:bg-accent-error/20'
            }`}
            title={closeTitle}
          >
            {pos.isClosing ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {/* Row 2: Exit pending — FULL WIDTH action button (never gets cut off) */}
      {pending && !pos.isClosing && pendingLabel && (
        <div className="mb-1.5">
          {canAutoRetry ? (
            <button
              onClick={(e) => { e.stopPropagation(); void onClose(pos.id, pending.trigger); }}
              className={`w-full py-1.5 rounded-lg text-[10px] font-mono font-bold border transition-all flex items-center justify-center gap-1.5 ${pendingColor} hover:opacity-90`}
              title="Retry sell with Session Wallet auto-signing"
            >
              <Shield className="w-3 h-3" />
              {pendingLabel} triggered — tap to retry sell
            </button>
          ) : connected ? (
            <button
              onClick={(e) => { e.stopPropagation(); void onClose(pos.id, pending.trigger); }}
              className={`w-full py-1.5 rounded-lg text-[10px] font-mono font-bold border transition-all flex items-center justify-center gap-1.5 ${pendingColor} hover:opacity-90`}
              title={pending.quoteAvailable === false ? 'Quote unavailable — will attempt sell with higher slippage' : 'Click to approve the sell'}
            >
              <Shield className="w-3 h-3" />
              {pendingLabel} triggered — tap to sell
            </button>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); void connect(); }}
              disabled={connecting}
              className="w-full py-1.5 rounded-lg text-[10px] font-mono font-bold border transition-all bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover disabled:opacity-60 flex items-center justify-center gap-1.5"
              title="Connect Phantom to approve the sell"
            >
              <Shield className="w-3 h-3" />
              {connecting ? 'Connecting...' : `${pendingLabel} triggered — connect wallet to sell`}
            </button>
          )}
        </div>
      )}
      {pos.isClosing && (
        <div className="mb-1.5">
          <div className="w-full py-1.5 rounded-lg text-[10px] font-mono font-bold border bg-accent-warning/10 text-accent-warning border-accent-warning/25 flex items-center justify-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" />
            Signing sell transaction...
          </div>
        </div>
      )}

      {/* Row 3: SL/TP + age info — wraps naturally */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9px] font-mono text-text-muted">
        <span className={`flex items-center gap-0.5 ${ageColor}`}>
          <Clock className="w-3 h-3" />
          {ageLabel}
          {countdownLabel && (
            <span className={`ml-0.5 ${nearExpiry ? 'text-accent-warning font-semibold' : 'text-text-muted/60'}`}>
              ({countdownLabel})
            </span>
          )}
        </span>
        <span className="text-text-muted/30">|</span>
        <span>Entry {formatUsdPrice(targets.entryUsd)}</span>
        {isBlueChip ? (
          <>
            <span className="text-text-muted/30">|</span>
            <span className="text-[8px] font-semibold uppercase tracking-wider text-accent-warning">
              Long conviction
            </span>
          </>
        ) : (
          <>
            <span className="text-text-muted/30">|</span>
            <span className="flex items-center gap-0.5 text-accent-error">
              <Shield className="w-2.5 h-2.5" /> SL -{sl}%
            </span>
            <span className="text-text-muted/30">|</span>
            <span className="flex items-center gap-0.5 text-accent-neon">
              <Target className="w-2.5 h-2.5" /> TP +{tp}%
            </span>
            <span className="text-text-muted/30">|</span>
            {canAutoRetry ? (
              <span className="flex items-center gap-0.5 px-1.5 py-px rounded bg-accent-neon/10 text-accent-neon font-semibold">
                <ShieldCheck className="w-2.5 h-2.5" /> AUTO
              </span>
            ) : (
              <span className="flex items-center gap-0.5 px-1.5 py-px rounded bg-text-muted/10 text-text-muted/70">
                MANUAL
              </span>
            )}
          </>
        )}
        {trailPct > 0 && (
          <>
            <span className="text-text-muted/30">|</span>
            <span className={`flex items-center gap-0.5 ${hwm >= trailPct ? 'text-accent-warning' : 'text-text-muted/70'}`}>
              <TrendingUp className="w-2.5 h-2.5" />
              Trail {trailPct}%
              {hwm > 0 && hwm >= trailPct && <span className="ml-0.5 font-semibold">ARMED</span>}
            </span>
          </>
        )}
        {pos.txHash && (
          <>
            <span className="text-text-muted/30">|</span>
            <a
              href={`https://solscan.io/tx/${pos.txHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-0.5 text-text-muted hover:text-accent-neon transition-colors"
              onClick={(e) => e.stopPropagation()}
            >
              <ExternalLink className="w-2.5 h-2.5" /> Tx
            </a>
          </>
        )}
      </div>
    </div>
  );
}
