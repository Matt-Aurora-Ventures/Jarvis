'use client';

import { useState, useEffect, useMemo, useRef, type ChangeEvent } from 'react';
import { Buffer } from 'buffer';
import { Settings, Zap, Shield, Target, TrendingUp, ChevronDown, ChevronUp, Crosshair, AlertTriangle, Wallet, Lock, Unlock, DollarSign, Loader2, Send, Flame, ShieldCheck, Info, AlertCircle, BarChart3, Trophy, Check, Gem, Rocket, Clock, HelpCircle, Package, X } from 'lucide-react';
import { useSniperStore, makeDefaultAssetBreaker, type SniperConfig, type StrategyMode, type AssetType, type PerAssetBreakerConfig, STRATEGY_PRESETS } from '@/stores/useSniperStore';
import type { BagsGraduation } from '@/lib/bags-api';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { useSnipeExecutor } from '@/hooks/useSnipeExecutor';
import {
  buildFundSessionTx,
  createSessionWallet,
  destroySessionWallet,
  deriveDeterministicSessionWallet,
  downloadSessionKeyByPubkey,
  exportSessionKeyAsFile,
  getDeterministicSessionWalletMessage,
  getSessionBalance,
  importSessionWalletSecretKey,
  isLikelyFunded,
  listStoredSessionWallets,
  loadSessionWalletByPublicKey,
  loadSessionWalletFromStorage,
  recoverSessionWalletFromAnyStorage,
  sweepToMainWalletAndCloseTokenAccounts,
} from '@/lib/session-wallet';
import { STRATEGY_CATEGORIES } from '@/components/strategy-categories';
import { STRATEGY_INFO } from '@/components/strategy-info';
import { filterOpenPositionsForActiveWallet, filterTradeManagedOpenPositionsForActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { waitForSignatureStatus } from '@/lib/tx-confirmation';
import {
  buildWrGateCandidates,
  gateStatusBadge,
  scopeAllowsAsset,
  selectBestWrGateStrategy,
} from '@/lib/auto-wr-gate';

/**
 * Analyze the current scanner feed and suggest the best strategy preset.
 * Pure function — no side effects, no store writes.
 */
function suggestStrategy(graduations: BagsGraduation[], assetType: AssetType = 'memecoin'): { presetId: string; reason: string } | null {
  if (graduations.length < 3) return null; // need enough data to decide

  // ── Bags.fm-specific suggestion logic ──
  if (assetType === 'bags') {
    const freshCount = graduations.filter(g => (g.age_hours ?? 999) < 48).length;
    const highScoreCount = graduations.filter(g => g.score >= 55).length;
    const momPositive = graduations.filter(g => (g.price_change_1h ?? 0) > 0).length;
    const momPct = momPositive / graduations.length;

    // Many high-score established tokens → value play
    if (highScoreCount >= 5) {
      return { presetId: 'bags_value', reason: `${highScoreCount} high-score (55+) bags tokens — value hunting` };
    }
    // Strong momentum across the board → momentum play
    if (momPct >= 0.4 && graduations.length >= 10) {
      return { presetId: 'bags_momentum', reason: `${Math.round(momPct * 100)}% positive momentum across ${graduations.length} tokens` };
    }
    // Fresh launches available → snipe them
    if (freshCount >= 3) {
      return { presetId: 'bags_fresh_snipe', reason: `${freshCount} fresh bags launches (<48h)` };
    }
    // Default for bags
    return { presetId: 'bags_bluechip', reason: 'Default safe bags strategy — established tokens' };
  }

  // ── Memecoin / general suggestion logic ──
  const liqs = graduations.map(g => g.liquidity || 0).filter(l => l > 0);

  const momPositive = graduations.filter(g => (g.price_change_1h ?? 0) > 0).length;
  const momPct = momPositive / graduations.length;

  const highVolCount = graduations.filter(g => {
    const l = g.liquidity || 0;
    const v = g.volume_24h || 0;
    return l > 0 && v / l >= 3;
  }).length;

  const freshCount = graduations.filter(g => (g.age_hours ?? 999) < 24).length;

  // Count tokens passing each preset's minimum liquidity gate
  const countAbove = (usd: number) => liqs.filter(l => l >= usd).length;
  const above10k = countAbove(10000);
  const above25k = countAbove(25000);
  const above40k = countAbove(40000);
  const above100k = countAbove(100000);

  // Decision tree — ranked by backtest win rate, with realistic thresholds
  // 1. Elite conditions: high-liq tokens with strong momentum (81.8% WR)
  if (above100k >= 2 && momPct >= 0.4) {
    return { presetId: 'elite', reason: `${above100k} tokens above $100K liq + ${Math.round(momPct * 100)}% momentum` };
  }

  // 2. Strong bull momentum + volume → LET IT RIDE (82.4% WR)
  if (momPct >= 0.45 && highVolCount >= 2 && above40k >= 2) {
    return { presetId: 'let_it_ride', reason: `${Math.round(momPct * 100)}% momentum + ${highVolCount} high-vol tokens` };
  }

  // 3. Many fresh tokens + decent liquidity → GENETIC V2 (88.1% WR)
  if (freshCount >= 3 && above10k >= 3) {
    return { presetId: 'genetic_v2', reason: `${freshCount} fresh tokens + active market` };
  }

  // 4. Good liquidity cluster with momentum → INSIGHT-J (73% WR)
  if (above25k >= 3 && momPct >= 0.3) {
    return { presetId: 'insight_j', reason: `${above25k} tokens with $25K+ liq & ${Math.round(momPct * 100)}% momentum` };
  }

  // 5. Moderate liquidity → HYBRID-B (balanced)
  if (above40k >= 2) {
    return { presetId: 'hybrid_b', reason: `${above40k} tokens above $40K liq — balanced approach` };
  }

  // 6. Lots of fresh micro-cap activity → MICRO CAP SURGE (78.8% WR)
  if (freshCount >= 4 && above10k >= 2) {
    return { presetId: 'micro_cap_surge', reason: `${freshCount} fresh micro-caps detected` };
  }

  // 7. Default: PUMP FRESH TIGHT (81% WR) — proven safe default, NOT momentum (20.9% WR)
  return { presetId: 'pump_fresh_tight', reason: 'Default safe strategy — 81% backtest WR' };
}

const BUDGET_PRESETS = [0.1, 0.2, 0.5, 1.0];
const LIQUIDITY_PRESETS_USD = [10000, 25000, 40000, 50000];

/** Icon lookup for strategy categories */
const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Trophy: <Trophy className="w-3 h-3" />,
  Shield: <Shield className="w-3 h-3" />,
  Zap: <Zap className="w-3 h-3" />,
  BarChart3: <BarChart3 className="w-3 h-3" />,
  Gem: <Gem className="w-3 h-3" />,
  Package: <Package className="w-3 h-3" />,
};

/** Map asset filter to visible strategy categories */
const ASSET_CATEGORY_MAP: Record<AssetType, string[]> = {
  memecoin: ['TOP PERFORMERS', 'BALANCED', 'AGGRESSIVE'],
  bags: ['DEGEN'],
  bluechip: ['BLUE CHIP SOLANA'],
  xstock: ['XSTOCK & INDEX'],
  prestock: ['XSTOCK & INDEX'],
  index: ['XSTOCK & INDEX'],
};

/** Risk level badge colors */
const RISK_COLORS: Record<string, string> = {
  LOW: 'text-accent-success bg-accent-success/10 border-accent-success/20',
  MEDIUM: 'text-accent-warning bg-accent-warning/10 border-accent-warning/20',
  HIGH: 'text-accent-error/80 bg-accent-error/10 border-accent-error/20',
  EXTREME: 'text-accent-error bg-accent-error/15 border-accent-error/30',
};

/** Small info tooltip component — hover to see explanation */
function InfoTip({ text }: { text: string }) {
  return (
    <span className="relative group inline-flex items-center ml-1 cursor-help">
      <HelpCircle className="w-3 h-3 text-text-muted/50 group-hover:text-text-muted transition-colors" />
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2.5 py-1.5 rounded-lg bg-bg-primary border border-border-primary text-[10px] text-text-secondary leading-relaxed whitespace-normal w-48 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-150 shadow-lg z-50 pointer-events-none">
        {text}
      </span>
    </span>
  );
}

export function SniperControls() {
  const { config, setConfig, setStrategyMode, loadPreset, activePreset, loadBestEver, positions, budget, setBudgetSol, authorizeBudget, deauthorizeBudget, budgetRemaining, graduations, tradeSignerMode, setTradeSignerMode, sessionWalletPubkey, setSessionWalletPubkey, assetFilter, backtestMeta, addExecution, autoResetRequired } = useSniperStore();
  const { connected, connecting, connect, address, signTransaction, signMessage, publicKey } = usePhantomWallet();
  const { snipe, ready: walletReady } = useSnipeExecutor();
  const [isHydrated, setIsHydrated] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [strategyOpen, setStrategyOpen] = useState(false);
  const [bestEverLoaded, setBestEverLoaded] = useState(false);
  const [customBudget, setCustomBudget] = useState('');
  const [budgetFocused, setBudgetFocused] = useState(false);
  const [snipeMint, setSnipeMint] = useState('');
  const [snipeLoading, setSnipeLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);

  // Session wallet (auto-signing) state
  const [sessionBalanceSol, setSessionBalanceSol] = useState<number | null>(null);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [confirmForceUnlock, setConfirmForceUnlock] = useState(false);
  const [sessionFundSol, setSessionFundSol] = useState('');
  const [confirmSweep, setConfirmSweep] = useState(false);
  const [confirmDeleteSession, setConfirmDeleteSession] = useState(false);
  const [sweepError, setSweepError] = useState<string | null>(null);
  const [storedSessionWallets, setStoredSessionWallets] = useState<Array<{ publicKey: string; mainWallet: string; createdAt: number; balanceSol?: number }>>([]);
  const [keyPendingSave, setKeyPendingSave] = useState(false);
  const [importKeyOpen, setImportKeyOpen] = useState(false);
  const [importKeyText, setImportKeyText] = useState('');
  const importFileInputRef = useRef<HTMLInputElement | null>(null);
  const [sessionWalletModalOpen, setSessionWalletModalOpen] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  const [activateBudget, setActivateBudget] = useState('');
  const [activateMaxTrades, setActivateMaxTrades] = useState('');
  const [activatePerTrade, setActivatePerTrade] = useState('');
  const [activateAutoSnipe, setActivateAutoSnipe] = useState(true);
  const [activateError, setActivateError] = useState<string | null>(null);

  // Safety watchdog: if Phantom/signature flows hang (popup blocked, route switch, extension bug),
  // sessionBusy can remain stuck and lock the entire session wallet UI. Auto-clear after 90s.
  useEffect(() => {
    if (!sessionBusy) return;
    const timer = window.setTimeout(() => {
      setSessionBusy(false);
      setSweepError((prev) => prev || 'Session wallet action timed out. Please try again.');
    }, 90_000);
    return () => window.clearTimeout(timer);
  }, [sessionBusy]);

  // Load BEST_EVER on mount
  useEffect(() => {
    loadBestEverConfig();
  }, []);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Sync session wallet pubkey scoped to the currently connected main wallet.
  useEffect(() => {
    if (!address) return;
    (async () => {
      try {
        const stored = await loadSessionWalletFromStorage({ mainWallet: address });
        if (stored && !sessionWalletPubkey) {
          setSessionWalletPubkey(stored.publicKey);
        }
      } catch {
        // ignore
      }
    })();
  }, [address, sessionWalletPubkey, setSessionWalletPubkey]);

  // Refresh session wallet balance periodically
  useEffect(() => {
    let cancelled = false;

    async function refresh() {
      if (!sessionWalletPubkey) {
        setSessionBalanceSol(null);
        return;
      }
      try {
        const bal = await getSessionBalance(sessionWalletPubkey);
        if (!cancelled) setSessionBalanceSol(bal);
      } catch {
        // ignore
      }
    }

    refresh();
    const t = setInterval(refresh, 10_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [sessionWalletPubkey]);

  // Discover any recoverable session wallets stored on this device (helps sweep "expired" wallets).
  useEffect(() => {
    let cancelled = false;

    async function refreshWalletIndex() {
      try {
        const wallets = listStoredSessionWallets().slice(0, 6).map((w) => ({ ...w }));
        if (cancelled) return;
        setStoredSessionWallets(wallets);

        // Fetch balances (best-effort, sequential to avoid RPC spikes).
        for (const w of wallets) {
          try {
            const bal = await getSessionBalance(w.publicKey);
            if (cancelled) return;
            setStoredSessionWallets((prev) =>
              prev.map((p) => (p.publicKey === w.publicKey ? { ...p, balanceSol: bal } : p)),
            );
          } catch {
            // ignore
          }
        }
      } catch {
        // ignore
      }
    }

    refreshWalletIndex();
    return () => {
      cancelled = true;
    };
  }, [sessionWalletPubkey]);

  async function loadBestEverConfig() {
    try {
      const res = await fetch('/api/best-ever');
      if (res.ok) {
        const data = await res.json();
        if (data.config) {
          loadBestEver(data.config);
          setBestEverLoaded(true);
        }
      }
    } catch {
      // Fallback — use defaults
    }
  }

  const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
  const openPositionCount = filterTradeManagedOpenPositionsForActiveWallet(positions, activeWallet).length;
  const atCapacity = openPositionCount >= config.maxConcurrentPositions;
  const remaining = budgetRemaining();
  const safeBudgetAuthorized = isHydrated ? budget.authorized : false;
  const safeRemaining = isHydrated ? remaining : 0;
  const perSnipeSol = budget.budgetSol > 0
    ? Math.round((budget.budgetSol / config.maxConcurrentPositions) * 100) / 100
    : 0;
  const useRecommendedExits = config.useRecommendedExits !== false;
  const suggestion = suggestStrategy(graduations as BagsGraduation[], assetFilter);
  const activePresetDef = STRATEGY_PRESETS.find((p) => p.id === activePreset);
  const activePresetLabel = activePresetDef?.name || activePreset?.toUpperCase() || 'CUSTOM';
  const wrGatePolicy = `WR Gate: ${Math.round(config.autoWrPrimaryPct)}→${Math.round(config.autoWrFallbackPct)} | ${config.autoWrMethod === 'wilson95_lower' ? 'Wilson95' : 'Point'} | Min ${Math.max(0, Math.floor(config.autoWrMinTrades))}T | PFT primary 50`;
  const wrGateScopeActive =
    config.autoWrGateEnabled &&
    scopeAllowsAsset(config.autoWrScope, assetFilter) &&
    (assetFilter === 'memecoin' || assetFilter === 'bags');
  const wrGateUiSelection = useMemo(() => {
    if (!wrGateScopeActive) return null;
    const candidates = buildWrGateCandidates(
      STRATEGY_PRESETS,
      backtestMeta as Record<string, any>,
      config.autoWrScope,
    );
    return selectBestWrGateStrategy(candidates, config);
  }, [
    backtestMeta,
    config.autoWrFallbackPct,
    config.autoWrMethod,
    config.autoWrMinTrades,
    config.autoWrPrimaryPct,
    config.autoWrScope,
    wrGateScopeActive,
  ]);

  const usingSession = tradeSignerMode === 'session';
  const [sessionKeyOk, setSessionKeyOk] = useState(false);
  useEffect(() => {
    if (!sessionWalletPubkey) { setSessionKeyOk(false); return; }
    let cancelled = false;
    (async () => {
      const storedSession = await loadSessionWalletByPublicKey(
        sessionWalletPubkey,
        { mainWallet: address || undefined },
      );
      if (!cancelled) {
        setSessionKeyOk(!!storedSession && storedSession.publicKey === sessionWalletPubkey);
        if (!storedSession && address) {
          setSweepError(
            'Selected session wallet does not match the connected main wallet. Choose a wallet from this profile or import a matching key backup.',
          );
        }
      }
    })();
    return () => { cancelled = true; };
  }, [sessionWalletPubkey, address]);
  // "Ready" should not depend on the budget setting; we validate exact amounts in the activate modal.
  const sessionReady = !!sessionWalletPubkey && sessionKeyOk;
  const canTradeNow = budget.authorized && (usingSession ? sessionReady : connected);
  const autoWalletActive = usingSession && budget.authorized;

  function openActivate() {
    setActivateError(null);
    const bal = sessionBalanceSol ?? 0;
    const defaultBudget = bal > 0 ? Math.max(0.01, Math.min(budget.budgetSol || 0.1, Math.max(0, bal - 0.002))) : budget.budgetSol || 0.1;
    setActivateBudget(autoResetRequired ? '' : String(defaultBudget));
    setActivateMaxTrades(autoResetRequired ? '' : String(config.maxConcurrentPositions));
    setActivatePerTrade(autoResetRequired ? '' : String(config.maxPositionSol));
    setActivateAutoSnipe(true);
    setActivateOpen(true);
  }

  function closeActivate() {
    setActivateOpen(false);
    setActivateError(null);
  }

  // Allow StatusBar (top wallet chip) to open the activation modal.
  // This keeps the "auto wallet" flow discoverable and avoids adding global UI state.
  useEffect(() => {
    const onOpen = () => openActivate();
    window.addEventListener('jarvis-sniper:open-activate', onOpen as EventListener);
    return () => window.removeEventListener('jarvis-sniper:open-activate', onOpen as EventListener);
  }, [openPositionCount, sessionBalanceSol, budget.budgetSol, config.maxConcurrentPositions, config.maxPositionSol]);

  function sumOpenSpentSol(): number {
    return filterTradeManagedOpenPositionsForActiveWallet(positions, activeWallet)
      .reduce((acc, p) => acc + (p.solInvested || 0), 0);
  }

  async function commitSessionPlan() {
    let bal = sessionBalanceSol ?? 0;
    const budgetSol = Number.parseFloat(activateBudget);
    const maxTrades = Math.max(1, Math.floor(Number.parseFloat(activateMaxTrades)));
    const perTradeSol = Number.parseFloat(activatePerTrade);

    if (!sessionWalletPubkey) {
      setActivateError('No session wallet found. Create one first.');
      return;
    }
    if (!sessionKeyOk) {
      setActivateError('Session key not found in this browser storage. Click "Sweep Back" to attempt recovery. If the key truly was not saved anywhere, it cannot be recovered.');
      return;
    }
    if (!Number.isFinite(budgetSol) || budgetSol <= 0) {
      setActivateError('Enter a valid total budget (SOL).');
      return;
    }
    if (!Number.isFinite(perTradeSol) || perTradeSol <= 0) {
      setActivateError('Enter a valid max SOL per trade.');
      return;
    }
    if (!Number.isFinite(maxTrades) || maxTrades < 1) {
      setActivateError('Enter a valid max trades value.');
      return;
    }
    if (perTradeSol > budgetSol) {
      setActivateError('Max SOL per trade cannot exceed total budget.');
      return;
    }

    // Ensure we have the freshest session balance (UI can be stale under RPC throttling).
    let fetchedBal: number | null = null;
    try {
      if (sessionWalletPubkey) {
        fetchedBal = await getSessionBalance(sessionWalletPubkey);
        bal = fetchedBal;
        setSessionBalanceSol(fetchedBal);
      }
    } catch {
      fetchedBal = null;
    }

    // Fail-safe: if we can't read balance, don't "activate" a plan that can't execute.
    if (fetchedBal == null) {
      setActivateError('Could not fetch session wallet balance. Check your RPC / internet and try again.');
      return;
    }
    if (bal < 0.002) {
      setActivateError('Session wallet balance is too low. Fund it first (ex: 0.02 SOL)');
      return;
    }

    // Keep a small buffer for fees/ATA creation. (We do NOT need 0.005 SOL.)
    const feeBuffer = 0.002;
    if (budgetSol > Math.max(0.01, bal - feeBuffer)) {
      setActivateError(`Budget too high for session balance. Balance=${bal.toFixed(4)} SOL. Leave ~${feeBuffer} SOL for fees.`);
      return;
    }

    // Apply in a predictable order.
    setConfig({
      maxConcurrentPositions: maxTrades,
      maxPositionSol: Math.round(perTradeSol * 1000) / 1000,
      autoSnipe: !!activateAutoSnipe,
    });
    setBudgetSol(budgetSol);

    // Mark budget authorized (session mode doesn't require Phantom approvals).
    // Also set spent to the sum of open positions so remaining is correct.
    const spent = Math.round(sumOpenSpentSol() * 1000) / 1000;
    useSniperStore.setState((s) => ({
      budget: { ...s.budget, authorized: true, spent },
      autoResetRequired: false,
    }));

    // Switch signing to session wallet for trading.
    setTradeSignerMode('session');
    closeActivate();
  }

  function handleBudgetPreset(sol: number) {
    setBudgetSol(sol);
    setCustomBudget('');
  }

  function commitCustomBudget() {
    const v = parseFloat(customBudget);
    if (!isNaN(v) && v > 0 && v <= 100) {
      setBudgetSol(v);
    }
    setBudgetFocused(false);
  }

  async function handleAuthorize() {
    if (budget.authorized) {
      deauthorizeBudget();
      return;
    }
    if (!connected || !publicKey || !signTransaction) return;
    setAuthLoading(true);
    try {
      // Build a real on-chain memo transaction to prove wallet ownership
      const { SystemProgram, Transaction, PublicKey: PK } = await import('@solana/web3.js');
      const connection = getSharedConnection();
      const tx = new Transaction();
      // 0-lamport self-transfer + memo to mark session start on-chain
      tx.add(
        SystemProgram.transfer({
          fromPubkey: publicKey,
          toPubkey: publicKey,
          lamports: 0,
        }),
      );
      // Memo instruction — records authorization on-chain
      const MEMO_PROGRAM = new PK('MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr');
      tx.add({
        keys: [{ pubkey: publicKey, isSigner: true, isWritable: false }],
        programId: MEMO_PROGRAM,
        data: Buffer.from(`Jarvis Sniper | Authorize ${budget.budgetSol} SOL | ${new Date().toISOString()}`),
      });
      const { blockhash } = await connection.getLatestBlockhash('confirmed');
      tx.recentBlockhash = blockhash;
      tx.feePayer = publicKey;
      const signed = await signTransaction(tx);
      const txHash = await connection.sendRawTransaction(signed.serialize(), { skipPreflight: true });
      const status = await waitForSignatureStatus(connection, txHash, { maxWaitMs: 45_000, pollMs: 2500 });
      if (status.state === 'failed') throw new Error(`Authorization transaction failed: ${status.error || 'on-chain error'}`);
      if (status.state !== 'confirmed') {
        console.info('[Auth] Transaction settling in background:', txHash);
      } else {
        console.log('[Auth] On-chain authorization confirmed:', txHash);
      }
      authorizeBudget();
    } catch (err: any) {
      const msg = err?.message || '';
      if (msg.includes('User rejected') || msg.includes('user rejected')) {
        console.log('[Auth] User cancelled');
      } else {
        console.error('[Auth] Failed:', err);
      }
    } finally {
      setAuthLoading(false);
    }
  }

  function parseSecretKeyArrayText(raw: string): Uint8Array | null {
    const text = String(raw || '').trim();
    if (!text) return null;

    const parseArray = (arr: unknown): Uint8Array | null => {
      if (!Array.isArray(arr)) return null;
      const nums = arr
        .map((n: any) => Number(n))
        .filter((n: any) => Number.isFinite(n) && n >= 0 && n <= 255);
      // Solana Keypair.secretKey is typically 64 bytes, but accept 32-byte seed too.
      if (nums.length !== 64 && nums.length !== 32) return null;
      return Uint8Array.from(nums);
    };

    // 1) Direct JSON parse (user pasted raw JSON array)
    try {
      const parsed = JSON.parse(text);
      const out = parseArray(parsed);
      if (out) return out;
    } catch {
      // fall through
    }

    // 2) User pasted the entire exported backup file: extract the first [...] block
    const start = text.indexOf('[');
    const end = text.lastIndexOf(']');
    if (start >= 0 && end > start) {
      try {
        const parsed = JSON.parse(text.slice(start, end + 1));
        const out = parseArray(parsed);
        if (out) return out;
      } catch {
        // fall through
      }
    }

    // 3) Regex fallback (best effort)
    const m = text.match(/\[[0-9,\s]+\]/);
    if (m) {
      try {
        const parsed = JSON.parse(m[0]);
        return parseArray(parsed);
      } catch {
        return null;
      }
    }

    return null;
  }

  function extractBackupPublicKey(raw: string): string | null {
    const text = String(raw || '');
    const m = text.match(/Public Key:\s*([1-9A-HJ-NP-Za-km-z]{32,44})/i);
    return m?.[1] || null;
  }

  async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
    const ms = Math.max(1000, Math.floor(timeoutMs || 0));
    const name = label || 'operation';
    return await new Promise<T>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        reject(new Error(`Timeout (${ms}ms): ${name}`));
      }, ms);
      promise.then(
        (val) => {
          window.clearTimeout(timer);
          resolve(val);
        },
        (err) => {
          window.clearTimeout(timer);
          reject(err);
        },
      );
    });
  }

  async function handleCreateSessionWallet() {
    if (sessionBusy) return;
    setSessionBusy(true);
    setSweepError(null);
    try {
      let mainAddress = address;
      if (!mainAddress) {
        if (!connected && !connecting) {
          await withTimeout(connect(), 45_000, 'Phantom connect');
        }
        // Give wallet state a short moment to hydrate after connect().
        for (let i = 0; i < 8 && !mainAddress; i++) {
          await new Promise((resolve) => setTimeout(resolve, 200));
          mainAddress =
            address ||
            (typeof window !== 'undefined'
              ? (window as any)?.phantom?.solana?.publicKey?.toBase58?.() ||
                (window as any)?.solana?.publicKey?.toBase58?.() ||
                null
              : null);
        }
      }

      if (!mainAddress) {
        setSweepError('Connect Phantom first, then click Create Session Wallet again.');
        return;
      }

      let pubkey: string | null = null;
      let keypair: any = null;
      let shouldAutoDownload = true;

      // Prefer deterministic (recoverable) session wallet when Phantom supports signMessage.
      // If browser storage is cleared or pointers are overwritten, users can still recover by signing again.
      try {
        const message = getDeterministicSessionWalletMessage(mainAddress);
        const signature = await withTimeout(signMessage(message), 60_000, 'Phantom sign message');
        const derived = await deriveDeterministicSessionWallet(mainAddress, signature);

        const existed = !!(await loadSessionWalletByPublicKey(derived.publicKey, { mainWallet: mainAddress }));
        const imported = await importSessionWalletSecretKey(
          derived.keypair.secretKey,
          mainAddress,
          Date.now(),
          'phantom_signMessage_v1',
        );

        pubkey = imported.publicKey;
        keypair = imported.keypair;

        // Avoid spamming downloads if this deterministic wallet already existed on this device.
        shouldAutoDownload = !existed;
      } catch {
        // Fallback to legacy random wallet creation.
        const created = await createSessionWallet(mainAddress);
        pubkey = created.publicKey;
        keypair = created.keypair;
        shouldAutoDownload = true;
      }

      if (pubkey) {
        setSessionWalletPubkey(pubkey);
        setTradeSignerMode('phantom'); // user toggles to session after funding
        setSweepError(null);
      }

      // Auto-download the private key as a backup file — users must NEVER lose their key.
      // (For deterministic wallets, users can also recover via Phantom signMessage.)
      if (pubkey && keypair && shouldAutoDownload) {
        // After await signMessage(), user gesture context is lost in Firefox.
        // Use setTimeout(0) to give the browser a tick, then attempt download.
        // If it still fails (popup blocker), the keyPendingSave banner will show.
        setTimeout(() => {
          try {
            exportSessionKeyAsFile(keypair, pubkey);
          } catch (dlErr) {
            console.warn('[SessionWallet] Key file download failed (popup blocker?)', dlErr);
          }
        }, 100);
        // Always show the save prompt after creation — auto-download is best-effort
        setKeyPendingSave(true);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setSweepError(`Session wallet creation failed: ${msg}`);
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleRecoverSessionWalletViaSignature() {
    if (!address) {
      setSweepError('Connect Phantom to recover a deterministic Session Wallet.');
      return;
    }
    setSessionBusy(true);
    setSweepError(null);
    try {
      const message = getDeterministicSessionWalletMessage(address);
      const signature = await signMessage(message);
      const derived = await deriveDeterministicSessionWallet(address, signature);

      if (sessionWalletPubkey && derived.publicKey !== sessionWalletPubkey) {
        setSweepError(
          `Signature recovery did not match the selected session wallet (${sessionWalletPubkey.slice(0, 4)}...${sessionWalletPubkey.slice(-4)}). ` +
          'This wallet was likely created in legacy random mode (not recoverable without its private key).',
        );
        return;
      }

      const imported = await importSessionWalletSecretKey(
        derived.keypair.secretKey,
        address,
        Date.now(),
        'phantom_signMessage_v1',
      );
      setSessionWalletPubkey(imported.publicKey);

      try {
        const bal = await getSessionBalance(imported.publicKey);
        setSessionBalanceSol(bal);
      } catch {
        // ignore
      }
    } catch (err) {
      setSweepError(`Signature recovery failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSessionBusy(false);
    }
  }

  async function importSessionWalletFromText(rawText: string) {
    const keyBytes = parseSecretKeyArrayText(rawText);
    if (!keyBytes) {
      setSweepError('Invalid key format. Paste the JSON array from your backup file.');
      return false;
    }

    const backupPublicKey = extractBackupPublicKey(rawText);
    const mainWallet =
      storedSessionWallets.find((w) => w.publicKey === sessionWalletPubkey)?.mainWallet ||
      address ||
      '';

    if (!mainWallet) {
      setSweepError('Connect Phantom (main wallet) to import this session key.');
      return false;
    }

    try {
      const { Keypair } = await import('@solana/web3.js');
      const kp = keyBytes.length === 32 ? Keypair.fromSeed(keyBytes) : Keypair.fromSecretKey(keyBytes);
      const pk = kp.publicKey.toBase58();
      if (backupPublicKey && backupPublicKey !== pk) {
        setSweepError(
          `Backup file mismatch. File says ${backupPublicKey.slice(0, 4)}...${backupPublicKey.slice(-4)}, key resolves to ${pk.slice(0, 4)}...${pk.slice(-4)}.`,
        );
        return false;
      }
      if (sessionWalletPubkey && pk !== sessionWalletPubkey) {
        setSweepError(
          `Imported key pubkey mismatch. Imported=${pk.slice(0, 4)}...${pk.slice(-4)} ` +
          `Selected=${sessionWalletPubkey.slice(0, 4)}...${sessionWalletPubkey.slice(-4)}`,
        );
        return false;
      }

      await importSessionWalletSecretKey(kp.secretKey, mainWallet, Date.now(), 'random');
      setSessionWalletPubkey(pk);
      setImportKeyText('');
      setImportKeyOpen(false);
      setSweepError(null);

      try {
        const bal = await getSessionBalance(pk);
        setSessionBalanceSol(bal);
      } catch {
        // ignore
      }
      try {
        const wallets = listStoredSessionWallets().slice(0, 6).map((w) => ({ ...w }));
        setStoredSessionWallets(wallets);
      } catch {
        // ignore
      }
      return true;
    } catch (err) {
      setSweepError(`Import failed: ${err instanceof Error ? err.message : String(err)}`);
      return false;
    }
  }

  async function handleImportSessionWalletKey() {
    await importSessionWalletFromText(importKeyText);
  }

  async function handleImportSessionWalletFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      await importSessionWalletFromText(text);
    } catch (err) {
      setSweepError(`Failed to read file: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      if (importFileInputRef.current) {
        importFileInputRef.current.value = '';
      }
    }
  }

  async function handleFundSessionWallet() {
    if (!sessionWalletPubkey) {
      setSweepError('Create a Session Wallet first, then fund it.');
      return;
    }

    // Ensure Phantom signer is available. Some environments briefly report
    // signTransaction as undefined; fall back to window.phantom when possible.
    if (!connected && !connecting) {
      try {
        await withTimeout(connect(), 45_000, 'Phantom connect');
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setSweepError(`Connect Phantom first: ${msg}`);
        return;
      }
    }

    const phantomSignTx =
      typeof window !== 'undefined'
        ? (window as any)?.phantom?.solana?.signTransaction ||
          (window as any)?.solana?.signTransaction ||
          null
        : null;
    const signer: ((tx: any) => Promise<any>) | null =
      signTransaction || (typeof phantomSignTx === 'function' ? phantomSignTx : null);
    if (!signer) {
      setSweepError('Phantom signing is unavailable. Reconnect Phantom and try again.');
      return;
    }
    let mainAddress = address;
    if (!mainAddress) {
      if (!connected && !connecting) {
        try {
          await withTimeout(connect(), 45_000, 'Phantom connect');
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          setSweepError(`Connect Phantom first: ${msg}`);
          return;
        }
      }
      for (let i = 0; i < 8 && !mainAddress; i++) {
        await new Promise((resolve) => setTimeout(resolve, 200));
        mainAddress =
          address ||
          (typeof window !== 'undefined'
            ? (window as any)?.phantom?.solana?.publicKey?.toBase58?.() ||
              (window as any)?.solana?.publicKey?.toBase58?.() ||
              null
            : null);
      }
    }
    if (!mainAddress) {
      setSweepError('Connect Phantom first, then click Fund again.');
      return;
    }

    const amount = Math.max(0.001, Number.parseFloat(sessionFundSol || String(budget.budgetSol)) || budget.budgetSol || 0);
    if (!Number.isFinite(amount) || amount <= 0) return;

    setSessionBusy(true);
    setSweepError(null);
    try {
      const fundTx = await withTimeout(
        buildFundSessionTx(mainAddress, sessionWalletPubkey, amount),
        20_000,
        'Build funding transaction',
      );
      const signed = await withTimeout(signer(fundTx), 60_000, 'Phantom sign funding transaction');

      const connection = getSharedConnection();

      const sig = await connection.sendRawTransaction(signed.serialize(), {
        skipPreflight: false,
        preflightCommitment: 'confirmed',
        maxRetries: 5,
      });

      // Bound confirmation so funding can't hang forever in UI.
      const confirm = await waitForSignatureStatus(connection, sig, { maxWaitMs: 45_000, pollMs: 2500 });
      if (confirm.state === 'failed') {
        throw new Error(confirm.error || 'Funding transaction failed on-chain');
      }
      if (confirm.state !== 'confirmed') {
        // Silent retry policy: do not surface as hard error while chain finality is still catching up.
        console.warn('[SessionWallet] Funding still settling; checking balance anyway', sig);
      }

      // Refresh balance
      const bal = await getSessionBalance(sessionWalletPubkey);
      setSessionBalanceSol(bal);

      // Make activation discoverable immediately after funding.
      if (!activateOpen && !autoWalletActive) {
        openActivate();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.toLowerCase().includes('user rejected')) {
        console.info('[SessionWallet] Funding cancelled by user');
        setSweepError('Funding request cancelled.');
      } else {
        console.error('[SessionWallet] Funding failed:', err);
        setSweepError(`Funding failed: ${message}`);
      }
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleSweepSessionWallet() {
    if (!confirmSweep) {
      setConfirmSweep(true);
      setSweepError(null);
      setTimeout(() => setConfirmSweep(false), 3000);
      return;
    }
    setConfirmSweep(false);

    setSessionBusy(true);
    setSweepError(null);
    try {
      const targetPubkey = sessionWalletPubkey || null;
      console.log('[Sweep] Starting sweep. Target pubkey:', targetPubkey, 'Connected wallet:', address);

      let stored = targetPubkey
        ? ((await loadSessionWalletByPublicKey(targetPubkey)) || (await recoverSessionWalletFromAnyStorage(targetPubkey)))
        : ((await loadSessionWalletFromStorage()) || (await recoverSessionWalletFromAnyStorage()));

      console.log('[Sweep] Storage lookup result:', stored ? `found (pubkey: ${stored.publicKey})` : 'not found');

      // If storage recovery fails, attempt deterministic recovery (Phantom signMessage) as a last resort.
      if (!stored && address) {
        try {
          const message = getDeterministicSessionWalletMessage(address);
          const signature = await signMessage(message);
          const derived = await deriveDeterministicSessionWallet(address, signature);

          if (targetPubkey && derived.publicKey !== targetPubkey) {
            setSweepError(
              `Signature recovery did not match the selected session wallet (${targetPubkey.slice(0, 4)}...${targetPubkey.slice(-4)}). ` +
              'This wallet was likely created in legacy random mode (not recoverable without its private key).',
            );
            return;
          }

          const imported = await importSessionWalletSecretKey(
            derived.keypair.secretKey,
            address,
            Date.now(),
            'phantom_signMessage_v1',
          );

          // Ensure UI/store points at the recovered wallet.
          if (!targetPubkey) {
            setSessionWalletPubkey(imported.publicKey);
          }

          stored = (await loadSessionWalletByPublicKey(imported.publicKey)) || (await recoverSessionWalletFromAnyStorage(imported.publicKey));
        } catch {
          // Ignore and fall through to error below.
        }
      }

      if (!stored) {
        setSweepError(
          'Session key not found in any storage. The private key was lost - funds cannot be swept without it. ' +
          'Try Recover via Signature (if this wallet was created with deterministic mode), or Import Key from your backup file.',
        );
        return;
      }

      // Prefer sweeping to the currently connected Phantom address, otherwise sweep to the wallet bound to this session key.
      const recipient = address || stored.mainWallet;
      console.log('[Sweep] Calling sweepToMainWallet. Recipient:', recipient);
      const sweepResult = await sweepToMainWalletAndCloseTokenAccounts(stored.keypair, recipient);
      const sig = sweepResult.sweepSignature;
      console.log('[Sweep] Result:', sig ? `Success (sig: ${sig.slice(0, 16)}...)` : 'null (balance too low)');
      if (!sig && sweepResult.closedTokenAccounts === 0) {
        setSweepError('Balance too low to cover transaction fees.');
      } else if (sessionWalletPubkey) {
        const bal = await getSessionBalance(sessionWalletPubkey);
        setSessionBalanceSol(bal);
      }

      if (sweepResult.closedTokenAccounts > 0) {
        addExecution({
          id: `sweep-close-accounts-${Date.now()}`,
          type: 'info',
          symbol: 'SWEEP',
          mint: '',
          amount: 0,
          reason: `Sweep closed ${sweepResult.closedTokenAccounts} empty token account${sweepResult.closedTokenAccounts === 1 ? '' : 's'} and reclaimed ${(sweepResult.reclaimedLamports / 1e9).toFixed(6)} SOL rent`,
          timestamp: Date.now(),
        });
      }

      if (sweepResult.skippedNonZeroTokenAccounts > 0) {
        addExecution({
          id: `sweep-nonzero-token-accounts-${Date.now()}`,
          type: 'info',
          symbol: 'SWEEP',
          mint: '',
          amount: 0,
          reason: `Sweep skipped ${sweepResult.skippedNonZeroTokenAccounts} token account${sweepResult.skippedNonZeroTokenAccounts === 1 ? '' : 's'} with non-zero balances. Close those positions/holdings before deleting this wallet.`,
          timestamp: Date.now(),
        });
      }

      if (sweepResult.failedToCloseTokenAccounts > 0) {
        setSweepError(
          `Sweep completed, but ${sweepResult.failedToCloseTokenAccounts} empty token account${sweepResult.failedToCloseTokenAccounts === 1 ? '' : 's'} could not be closed right now. Retry Sweep Back in a few seconds.`,
        );
      }
    } catch (err) {
      setSweepError(`Sweep failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleDestroySessionWallet() {
    if (!confirmDeleteSession) {
      setConfirmDeleteSession(true);
      setSweepError(null);
      setTimeout(() => setConfirmDeleteSession(false), 3000);
      return;
    }
    setConfirmDeleteSession(false);

    setSessionBusy(true);
    setSweepError(null);
    try {
      const targetPubkey = sessionWalletPubkey || null;
      const stored = targetPubkey
        ? ((await loadSessionWalletByPublicKey(targetPubkey)) || (await recoverSessionWalletFromAnyStorage(targetPubkey)))
        : ((await loadSessionWalletFromStorage()) || (await recoverSessionWalletFromAnyStorage()));

      // If there are funds and we don't have a key, refuse to delete (it makes recovery harder).
      let balanceSol: number | null = null;
      if (targetPubkey) {
        try { balanceSol = await getSessionBalance(targetPubkey); } catch {}
      }
      if (!stored && balanceSol != null && balanceSol > 0.001) {
        setSweepError(
          'Cannot delete: this Session Wallet has funds but the private key is missing in this browser. ' +
          'Use Import Key or Recover via Signature first, then Sweep Back.',
        );
        return;
      }

      // Best-effort: sweep funds before deleting.
      if (stored) {
        const recipient = address || stored.mainWallet;
        const sweepResult = await sweepToMainWalletAndCloseTokenAccounts(stored.keypair, recipient);
        if (sweepResult.skippedNonZeroTokenAccounts > 0) {
          setSweepError(
            `Cannot delete: this session wallet still has ${sweepResult.skippedNonZeroTokenAccounts} token account${sweepResult.skippedNonZeroTokenAccounts === 1 ? '' : 's'} with balances. Close positions first, then delete.`,
          );
          return;
        }
      }

      destroySessionWallet();
      setSessionWalletPubkey(null);
      setSessionBalanceSol(null);
      if (usingSession) setTradeSignerMode('phantom');
    } catch (err) {
      setSweepError(`Delete failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleManualSnipe() {
    const mint = snipeMint.trim();
    if (!mint || mint.length < 32 || !walletReady || !budget.authorized) return;
    setSnipeLoading(true);
    try {
      // Build a grad object that bypasses insight filters for manual snipes
      // (user explicitly chose this token — set values to pass all gates)
      const grad = {
        mint,
        symbol: mint.slice(0, 6).toUpperCase(),
        name: `Token ${mint.slice(0, 8)}`,
        score: 0,
        graduation_time: Math.floor(Date.now() / 1000),
        liquidity: Math.max(config.minLiquidityUsd, 100000), // Pass liq gate even if user raised threshold
        price_usd: 0,
        logo_uri: '',
        price_change_1h: 1,     // Pass momentum gate
        volume_24h: 0,
        age_hours: 1,           // Pass age gate
        buy_sell_ratio: 1.5,    // Pass B/S gate
        txn_buys_1h: 10,
        txn_sells_1h: 7,
        total_txns_1h: 17,
      };
      await snipe(grad as any);
      setSnipeMint('');
    } catch (err) {
      console.error('[ManualSnipe] Failed:', err);
    } finally {
      setSnipeLoading(false);
    }
  }

  return (
    <div className="card-glass p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Sniper Strategy</h2>
        </div>
        <span className={`text-[9px] font-mono px-2 py-0.5 rounded-full border ${
          config.strategyMode === 'aggressive'
            ? 'text-accent-warning bg-accent-warning/10 border-accent-warning/20'
            : 'text-accent-neon bg-accent-neon/10 border-accent-neon/20'
        }`}>
          {config.stopLossPct}/{config.takeProfitPct}+{config.trailingStopPct}t
        </span>
      </div>

      {/* ─── QUICK START — One-click setup for new users ─── */}
      {!config.autoSnipe && !budget.authorized && (
        <div className="mb-4 p-3 rounded-lg border border-accent-neon/20 bg-accent-neon/[0.03]">
          <div className="flex items-center gap-2 mb-2">
            <Rocket className="w-4 h-4 text-accent-neon" />
            <span className="text-xs font-bold text-accent-neon tracking-wide">QUICK START</span>
          </div>
          <p className="text-[10px] text-text-secondary leading-relaxed mb-3">
            New here? One click sets up the best strategy, a safe budget, and gets you ready to trade. You still need to connect your wallet and authorize before trades execute.
          </p>
          <button
            onClick={() => {
              // 1. Set a recommended starter preset (real win rate is shown after Strategy Validation runs)
              loadPreset('pump_fresh_tight');
              // 2. Set conservative budget (0.1 SOL per trade)
              setBudgetSol(0.5);
              setConfig({ maxPositionSol: 0.1, maxConcurrentPositions: 5 });
            }}
            className="w-full py-2.5 rounded-lg text-xs font-bold bg-accent-neon text-black hover:bg-accent-neon/90 transition-all flex items-center justify-center gap-2 cursor-pointer"
          >
            <Zap className="w-3.5 h-3.5" />
            Set Up Recommended Defaults
          </button>
          <p className="text-[9px] text-text-muted/60 mt-2 text-center">
            Sets a safe starter budget and preset. Run Strategy Validation for real, timestamped results.
          </p>
        </div>
      )}

      {/* ─── STRATEGY PRESET SELECTOR (Grouped Dropdown) ─── */}
      <div className="relative mb-4">
        {/* Dropdown trigger button */}
        <button
          onClick={() => setStrategyOpen(!strategyOpen)}
          className={`w-full flex items-start justify-between gap-2 p-3 rounded-lg border transition-all ${
            strategyOpen
              ? 'border-accent-neon/40 bg-accent-neon/[0.04]'
              : 'border-border-primary bg-bg-secondary hover:border-border-hover'
          }`}
        >
          <div className="flex items-start gap-2 min-w-0 flex-1 pr-1">
            <Crosshair className="w-3.5 h-3.5 text-accent-neon flex-shrink-0" />
            <div className="flex flex-col items-start min-w-0">
              <span className="text-[11px] font-bold text-text-primary break-words leading-tight">
                {STRATEGY_PRESETS.find(p => p.id === activePreset)?.name ?? 'Select Strategy'}
              </span>
              <span className="text-[9px] text-text-muted leading-tight line-clamp-2">
                {STRATEGY_PRESETS.find(p => p.id === activePreset)?.description ?? 'Choose a strategy preset'}
              </span>
            </div>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center items-end gap-1.5 flex-shrink-0 max-w-[52%]">
            {(() => {
              const meta: any = (backtestMeta as any)?.[activePreset];
              const wr = meta?.backtested ? String(meta.winRate || '').trim() : '';
              const trades = meta?.backtested ? Number(meta.trades || 0) : 0;
              const under = !!meta?.underperformer;
              const stageTag =
                meta?.stage === 'promotion' ? 'S3' :
                meta?.stage === 'stability' ? 'S2' :
                meta?.stage === 'sanity' ? 'S1' :
                '';
              const promo = !!meta?.promotionEligible;
              return (
                <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                  under
                    ? 'bg-accent-error/10 text-accent-error border-accent-error/20'
                    : wr
                      ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/20'
                      : 'bg-bg-tertiary text-text-muted border-border-primary text-[8px]'
                } max-w-[220px] leading-tight text-right break-words whitespace-normal`}>
                  {wr ? `${wr}${trades > 0 ? ` (${trades}T${stageTag ? ` ${stageTag}` : ''}${promo ? ' PROMO' : ''})` : ''}` : 'Unverified'}
                </span>
              );
            })()}
            <ChevronDown className={`w-3.5 h-3.5 text-text-muted transition-transform ${strategyOpen ? 'rotate-180' : ''}`} />
          </div>
        </button>

        {/* Dropdown panel with categories */}
        {strategyOpen && (
          <div className="mt-1.5 rounded-lg border border-border-primary bg-bg-secondary overflow-hidden animate-fade-in">
            {STRATEGY_CATEGORIES.filter(c => {
              const allowed = ASSET_CATEGORY_MAP[assetFilter];
              return allowed ? allowed.includes(c.label) : true;
            }).map((category) => (
              <div key={category.label}>
                {/* Category header */}
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-tertiary/50 border-b border-border-primary/50">
                  <span className="text-text-muted/60">{CATEGORY_ICONS[category.icon]}</span>
                  <span className="text-[8px] font-bold uppercase tracking-[0.12em] text-text-muted/60">{category.label}</span>
                </div>
                {/* Strategy rows */}
                {category.presetIds.map((presetId) => {
                  const preset = STRATEGY_PRESETS.find(p => p.id === presetId);
                  if (!preset) return null;
                  const isActive = activePreset === preset.id;
                  const isAggressive = preset.config.strategyMode === 'aggressive';
                  const isSuggested = suggestion?.presetId === preset.id && !isActive;
                  return (
                    <button
                      key={preset.id}
                      onClick={() => { loadPreset(preset.id); setStrategyOpen(false); }}
                      className={`w-full flex items-center gap-2 px-3 py-2 text-left transition-all border-b border-border-primary/30 last:border-b-0 ${
                        isActive
                          ? isAggressive
                            ? 'bg-accent-warning/[0.08] text-accent-warning'
                            : 'bg-accent-neon/[0.08] text-accent-neon'
                          : isSuggested
                            ? 'bg-blue-500/[0.04] text-text-secondary hover:bg-blue-500/[0.08]'
                            : 'text-text-secondary hover:bg-bg-tertiary/60'
                      }`}
                    >
                      {/* Active indicator */}
                      <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 ${
                        isActive
                          ? isAggressive
                            ? 'bg-accent-warning/20 border border-accent-warning/40'
                            : 'bg-accent-neon/20 border border-accent-neon/40'
                          : 'border border-border-primary/50'
                      }`}>
                        {isActive && <Check className="w-2.5 h-2.5" />}
                      </div>
                      {/* Name + description */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] font-bold truncate ${isActive ? '' : 'text-text-primary'}`}>{preset.name}</span>
                          {isSuggested && (
                            <span className="text-[7px] font-bold uppercase tracking-wider bg-blue-500/90 text-white px-1 py-0.5 rounded-full leading-none flex-shrink-0">
                              Suggested
                            </span>
                          )}
                        </div>
                        <span className="text-[8px] opacity-50 line-clamp-1">{preset.description}</span>
                      </div>
                      {/* Win rate badge */}
                      {(() => {
                        const meta: any = (backtestMeta as any)?.[preset.id];
                        const wr = meta?.backtested ? String(meta.winRate || '').trim() : '';
                        const trades = meta?.backtested ? Number(meta.trades || 0) : 0;
                        const under = !!meta?.underperformer;
                        const gateBadge = gateStatusBadge(meta, config, preset.autoWrPrimaryOverridePct);
                        const stageTag =
                          meta?.stage === 'promotion' ? 'S3' :
                          meta?.stage === 'stability' ? 'S2' :
                          meta?.stage === 'sanity' ? 'S1' :
                          '';
                        const promo = !!meta?.promotionEligible;

                        const style = under
                          ? 'bg-accent-error/10 text-accent-error'
                          : isActive
                            ? isAggressive
                              ? 'bg-accent-warning/10 text-accent-warning'
                              : 'bg-accent-neon/10 text-accent-neon'
                            : 'bg-bg-tertiary text-text-muted';

                        return (
                          <div className="flex flex-col items-end gap-1 max-w-[180px] flex-shrink-0">
                            <span className={`text-[8px] font-mono px-1.5 py-0.5 rounded leading-tight break-words whitespace-normal text-right ${style}`}>
                              {wr ? `${wr}${trades > 0 ? ` (${trades}T${stageTag ? ` ${stageTag}` : ''}${promo ? ' PROMO' : ''})` : ''}` : 'Unverified'}
                            </span>
                            {wrGateScopeActive && gateBadge && (
                              <span className={`text-[7px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border ${
                                gateBadge === 'Insufficient Sample'
                                  ? 'text-accent-warning bg-accent-warning/10 border-accent-warning/20'
                                  : gateBadge === 'Gate Pass @70'
                                    ? 'text-accent-neon bg-accent-neon/10 border-accent-neon/20'
                                    : 'text-blue-300 bg-blue-500/10 border-blue-400/20'
                              }`}>
                                {gateBadge}
                              </span>
                            )}
                          </div>
                        );
                      })()}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        )}
      </div>

      {wrGateScopeActive && wrGateUiSelection?.selected && (
        <div className="flex items-center gap-2 px-3 py-2 mb-3 rounded-lg bg-accent-neon/10 border border-accent-neon/20">
          <ShieldCheck className="w-3 h-3 text-accent-neon flex-shrink-0" />
          <span className="text-[10px] text-accent-neon/90">
            WR gate ({wrGateUiSelection.resolution.mode === 'fallback' ? 'fallback' : wrGateUiSelection.selectedThresholdSource === 'primary_override' ? 'primary override' : 'primary'}) currently prefers{' '}
            <span className="font-bold">
              {STRATEGY_PRESETS.find((p) => p.id === wrGateUiSelection.selected?.strategyId)?.name || wrGateUiSelection.selected.strategyId}
            </span>
            {' '}@ {wrGateUiSelection.selectedThresholdPct ?? wrGateUiSelection.resolution.usedThreshold}%.
          </span>
        </div>
      )}
      {wrGateScopeActive && wrGateUiSelection && !wrGateUiSelection.selected && (
        <div className="flex items-center gap-2 px-3 py-2 mb-3 rounded-lg bg-accent-warning/10 border border-accent-warning/20">
          <AlertTriangle className="w-3 h-3 text-accent-warning flex-shrink-0" />
          <span className="text-[10px] text-accent-warning/90">
            WR gate found no eligible strategy (70→50, min {config.autoWrMinTrades} trades).
          </span>
        </div>
      )}

      {/* ─── STRATEGY SUGGESTION REASON ─── */}
      {suggestion && suggestion.presetId !== activePreset && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 rounded-lg bg-blue-500/[0.06] border border-blue-400/20">
          <Zap className="w-3 h-3 text-blue-400 flex-shrink-0" />
          <span className="text-[10px] text-blue-300/90">
            <span className="font-bold">{STRATEGY_PRESETS.find(p => p.id === suggestion.presetId)?.name}</span>
            {' '}may fit current conditions — {suggestion.reason}
          </span>
        </div>
      )}

      {/* ─── STRATEGY BREAKDOWN BOX ─── */}
      {STRATEGY_INFO[activePreset] && (() => {
        const info = STRATEGY_INFO[activePreset];
        const preset = STRATEGY_PRESETS.find(p => p.id === activePreset);
        const isAgg = preset?.config.strategyMode === 'aggressive';
        return (
          <div className={`mb-4 rounded-lg border overflow-hidden ${isAgg ? 'border-accent-warning/20 bg-accent-warning/[0.03]' : 'border-accent-neon/20 bg-accent-neon/[0.03]'}`}>
            <div className={`flex items-center gap-2 px-3 py-2 border-b ${isAgg ? 'border-accent-warning/10' : 'border-accent-neon/10'}`}>
              <Info className={`w-3.5 h-3.5 ${isAgg ? 'text-accent-warning' : 'text-accent-neon'}`} />
              <span className={`text-[11px] font-bold ${isAgg ? 'text-accent-warning' : 'text-accent-neon'}`}>{preset?.name}</span>
              <span className={`ml-auto text-[9px] font-mono max-w-[220px] leading-tight break-words whitespace-normal text-right ${isAgg ? 'text-accent-warning/70' : 'text-accent-neon/70'}`}>
                {(() => {
                  const meta: any = (backtestMeta as any)?.[activePreset];
                  const wr = meta?.backtested ? String(meta.winRate || '').trim() : '';
                  const trades = meta?.backtested ? Number(meta.trades || 0) : 0;
                  const stageTag =
                    meta?.stage === 'promotion' ? 'S3' :
                    meta?.stage === 'stability' ? 'S2' :
                    meta?.stage === 'sanity' ? 'S1' :
                    '';
                  const promo = !!meta?.promotionEligible;
                  return wr ? `${wr}${trades > 0 ? ` (${trades}T${stageTag ? ` ${stageTag}` : ''}${promo ? ' PROMO' : ''})` : ''}` : 'Unverified';
                })()}
              </span>
            </div>
            <div className="px-3 py-2.5 space-y-2.5">
              {/* Risk Level + Hold Time badges */}
              <div className="flex flex-wrap items-center gap-1.5">
                {info.riskLevel && (
                  <span className={`text-[8px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${RISK_COLORS[info.riskLevel] || 'text-text-muted bg-bg-tertiary border-border-primary'}`}>
                    {info.riskLevel} RISK
                  </span>
                )}
                {info.holdTime && (
                  <span className="text-[8px] font-mono text-text-muted/70 flex items-center gap-0.5">
                    <Clock className="w-2.5 h-2.5" />
                    {info.holdTime}
                  </span>
                )}
              </div>
              {/* Best For line */}
              {info.bestFor && (
                <div className="flex items-start gap-1.5">
                  <Target className="w-3 h-3 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <span className="text-[9px] font-bold text-blue-400 uppercase tracking-wide">Best for</span>
                    <p className="text-[10px] text-text-secondary leading-relaxed mt-0.5">{info.bestFor}</p>
                  </div>
                </div>
              )}
              <p className="text-[10px] text-text-secondary leading-relaxed">{info.summary}</p>
              <div className="flex items-start gap-1.5">
                <BarChart3 className="w-3 h-3 text-accent-neon flex-shrink-0 mt-0.5" />
                <div>
                  <span className="text-[9px] font-bold text-accent-neon uppercase tracking-wide">Best when</span>
                  <p className="text-[10px] text-text-muted leading-relaxed mt-0.5">{info.optimal}</p>
                </div>
              </div>
              <div className="flex items-start gap-1.5">
                <AlertCircle className="w-3 h-3 text-accent-warning flex-shrink-0 mt-0.5" />
                <div>
                  <span className="text-[9px] font-bold text-accent-warning uppercase tracking-wide">Watch out</span>
                  <p className="text-[10px] text-text-muted leading-relaxed mt-0.5">{info.risk}</p>
                </div>
              </div>
              <div className="pt-1.5 border-t border-border-primary/50">
                <span className="text-[9px] font-mono text-text-muted/70">{info.params}</span>
              </div>
            </div>
          </div>
        );
      })()}

      {!connected && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-warning/10 border border-accent-warning/20 mb-4">
          <AlertTriangle className="w-4 h-4 text-accent-warning flex-shrink-0" />
          <span className="text-[11px] text-accent-warning">Connect wallet to enable trading</span>
        </div>
      )}

      {/* ─── SOL BUDGET SECTION ─── */}
      <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Wallet className="w-3.5 h-3.5 text-accent-neon" />
          <span className="text-xs font-semibold">Snipe Budget</span>
          <InfoTip text="Maximum SOL to spend in this session. Start small! You can always add more later." />
          {budget.authorized && (
            <span className="ml-auto text-[9px] font-mono text-accent-neon bg-accent-neon/10 px-1.5 py-0.5 rounded-full border border-accent-neon/20 flex items-center gap-1">
              <Unlock className="w-2.5 h-2.5" /> AUTHORIZED
            </span>
          )}
        </div>

        {/* Quick-select buttons */}
        <div className="flex gap-1.5 mb-3">
          {BUDGET_PRESETS.map((sol) => (
            <button
              key={sol}
              onClick={() => handleBudgetPreset(sol)}
              disabled={budget.authorized}
              className={`flex-1 text-[11px] font-mono font-bold py-2 rounded-lg transition-all ${
                budget.budgetSol === sol && !budgetFocused
                  ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
                  : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
              } ${budget.authorized ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              {sol} SOL
            </button>
          ))}
        </div>

        {/* Custom amount input */}
        <div className="flex items-center gap-2 mb-3">
          <div className={`flex-1 flex items-center gap-2 p-2 rounded-lg bg-bg-tertiary border transition-all ${
            budgetFocused ? 'border-accent-neon/40' : 'border-border-primary'
          }`}>
            <DollarSign className="w-3 h-3 text-text-muted" />
            <input
              type="text"
              inputMode="decimal"
              placeholder="Custom amount..."
              value={budgetFocused ? customBudget : (customBudget || '')}
              disabled={budget.authorized}
              onFocus={() => setBudgetFocused(true)}
              onBlur={() => commitCustomBudget()}
              onChange={(e) => setCustomBudget(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') commitCustomBudget(); }}
              className="flex-1 bg-transparent text-xs font-mono text-text-primary outline-none placeholder:text-text-muted/40 disabled:opacity-50"
            />
            <span className="text-[10px] text-text-muted font-mono">SOL</span>
          </div>
        </div>

        {/* Budget summary — suppressHydrationWarning on store-dependent spans
             to avoid SSR/client mismatch from Zustand persist rehydration */}
        <div className="flex items-center justify-between text-[10px] font-mono mb-3 px-1">
          <div className="flex flex-col gap-0.5">
            <span className="text-text-muted">Total Budget</span>
            <span suppressHydrationWarning className="text-text-primary font-bold text-xs">{budget.budgetSol} SOL</span>
          </div>
          <div className="flex flex-col gap-0.5 text-center">
            <span className="text-text-muted">Per Snipe</span>
            <span suppressHydrationWarning className="text-text-primary font-bold text-xs">~{perSnipeSol} SOL</span>
          </div>
          <div className="flex flex-col gap-0.5 text-right">
            <span className="text-text-muted">Remaining</span>
            <span suppressHydrationWarning className={`font-bold text-xs ${safeRemaining > 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
              {safeBudgetAuthorized ? `${safeRemaining} SOL` : '—'}
            </span>
          </div>
        </div>

        {/* Recommended note */}
        <div className="text-[9px] text-text-muted/60 mb-3 px-1">
          Recommended: 0.5 SOL for testing, 1-2 SOL for active sniping
        </div>

        {/* Authorize / Deauthorize button */}
        <button
          onClick={handleAuthorize}
          disabled={!connected || budget.budgetSol <= 0 || authLoading}
          className={`w-full py-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            budget.authorized
              ? 'bg-accent-error/15 text-accent-error border border-accent-error/30 hover:bg-accent-error/25'
              : 'bg-accent-neon text-black hover:bg-accent-neon/90'
          } ${(!connected || budget.budgetSol <= 0 || authLoading) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          {authLoading ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Signing with Phantom...</>
          ) : budget.authorized ? (
            <><Lock className="w-3.5 h-3.5" /> Revoke Authorization</>
          ) : (
            <><Unlock className="w-3.5 h-3.5" /> Authorize {budget.budgetSol} SOL</>
          )}
        </button>
      </div>

      {/* ─── AUTO-EXECUTE (SESSION WALLET) — compact trigger ─── */}
      <button
        onClick={() => setSessionWalletModalOpen(true)}
        className="w-full p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4 hover:border-border-hover transition-all cursor-pointer text-left flex items-center gap-3"
      >
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
          autoWalletActive ? 'bg-accent-warning/15 text-accent-warning' : 'bg-bg-tertiary text-text-muted'
        }`}>
          <Flame className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold">Session Wallet</span>
            <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border ${
              usingSession ? 'text-accent-warning bg-accent-warning/10 border-accent-warning/20' : 'text-text-muted bg-bg-tertiary border-border-primary'
            }`}>
              {usingSession ? 'AUTO' : 'MANUAL'}
            </span>
          </div>
          <p className="text-[10px] text-text-muted mt-0.5 truncate">
            {sessionWalletPubkey
              ? `${sessionWalletPubkey.slice(0, 6)}...${sessionWalletPubkey.slice(-4)} — ${sessionBalanceSol != null ? `${sessionBalanceSol.toFixed(4)} SOL` : '...'}`
              : 'Create a burner wallet for auto-signing'}
          </p>
        </div>
        <ChevronUp className="w-4 h-4 text-text-muted flex-shrink-0 rotate-90" />
      </button>

      {/* ─── SESSION WALLET POPUP MODAL ─── */}
      {sessionWalletModalOpen && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setSessionWalletModalOpen(false)} />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="session-wallet-modal-title"
            className="relative w-full max-w-[540px] max-h-[85vh] overflow-y-auto card-glass p-5 border border-accent-warning/25 shadow-xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-accent-warning/15 border border-accent-warning/25 flex items-center justify-center">
                  <Flame className="w-4.5 h-4.5 text-accent-warning" />
                </div>
                <div>
                  <h2 id="session-wallet-modal-title" className="font-display text-base font-semibold">Session Wallet</h2>
                  <span className={`text-[9px] font-mono px-1.5 py-0.5 rounded-full border ${
                    usingSession ? 'text-accent-warning bg-accent-warning/10 border-accent-warning/20' : 'text-text-muted bg-bg-tertiary border-border-primary'
                  }`}>
                    {usingSession ? 'AUTO-SIGNING' : 'MANUAL'}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSessionWalletModalOpen(false)}
                className="w-8 h-8 rounded-lg bg-bg-tertiary border border-border-primary flex items-center justify-center hover:border-border-hover transition-colors"
              >
                <X className="w-4 h-4 text-text-muted" />
              </button>
            </div>

            {/* Info banner */}
            <div className="p-3 rounded-lg bg-accent-warning/[0.06] border border-accent-warning/20 mb-4 space-y-1.5">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-accent-warning flex-shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <p className="text-[11px] text-text-primary leading-relaxed">
                    <span className="font-bold text-accent-warning">Session Wallet</span> — a burner wallet that auto-signs buys and sells without Phantom popups. Required for automatic SL/TP execution.
                  </p>
                  <p className="text-[11px] text-text-muted/80 leading-relaxed">
                    Fund it with only what you can afford to lose. Jarvis auto-sweeps excess SOL back to your main wallet after exits, but this is <span className="font-semibold text-accent-warning">best-effort</span>.
                  </p>
                  <p className="text-[11px] text-accent-error/90 leading-relaxed font-semibold">
                    ALWAYS click &quot;Save Key&quot; after creating your wallet. The downloaded key file is the ONLY backup.
                  </p>
                </div>
              </div>
            </div>

            {/* Key pending save alert */}
            {keyPendingSave && sessionWalletPubkey && (
              <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/30 mb-4 animate-pulse">
                <Shield className="w-4 h-4 text-accent-error flex-shrink-0" />
                <span className="text-[11px] text-accent-error font-bold flex-1">
                  Your key was just created — download it NOW before you do anything else!
                </span>
                <button
                  onClick={async () => {
                    const ok = await downloadSessionKeyByPubkey(sessionWalletPubkey);
                    if (ok) setKeyPendingSave(false);
                    else setSweepError('Cannot download key — private key not found in browser storage.');
                  }}
                  className="text-[11px] font-bold px-3 py-1.5 rounded bg-accent-error text-white hover:bg-accent-error/80 transition-colors flex-shrink-0"
                >
                  Save Key
                </button>
              </div>
            )}

            <input
              ref={importFileInputRef}
              type="file"
              accept=".txt,.json,text/plain,application/json"
              className="hidden"
              onChange={(e) => { void handleImportSessionWalletFile(e); }}
            />

            {/* Content */}
            {!sessionWalletPubkey ? (
              <div className="space-y-3">
                {sweepError && (
                  <div className="flex items-start gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/20">
                    <AlertTriangle className="w-3.5 h-3.5 text-accent-error flex-shrink-0 mt-0.5" />
                    <span className="text-[10px] text-accent-error/90">{sweepError}</span>
                  </div>
                )}
                <button
                  onClick={handleCreateSessionWallet}
                  disabled={sessionBusy}
                  className={`w-full py-3 rounded-lg text-sm font-bold transition-all flex items-center justify-center gap-2 ${
                    connected || connecting ? 'bg-accent-warning text-black hover:bg-accent-warning/90' : 'bg-accent-warning/80 text-black hover:bg-accent-warning'
                  } ${sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                  title={connected ? 'Create a burner wallet for auto execution' : 'Connect Phantom and create a session wallet'}
                >
                  {sessionBusy ? (
                    <><Loader2 className="w-4 h-4 animate-spin" /> Working...</>
                  ) : connecting ? (
                    'Connecting Phantom...'
                  ) : connected ? (
                    'Create Session Wallet'
                  ) : (
                    'Connect Phantom + Create Session Wallet'
                  )}
                </button>

                {sessionBusy && (
                  <button
                    onClick={() => {
                      if (!confirmForceUnlock) {
                        setConfirmForceUnlock(true);
                        setTimeout(() => setConfirmForceUnlock(false), 3000);
                        return;
                      }
                      setConfirmForceUnlock(false);
                      setSessionBusy(false);
                      setSweepError('Session wallet UI unlocked. If a transaction was in-flight, check explorer for finality.');
                    }}
                    className="w-full py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover"
                    title="If the session wallet UI gets stuck, force-unlock it (does not cancel on-chain transactions)"
                  >
                    {confirmForceUnlock ? 'Click again to unlock' : 'Force Unlock'}
                  </button>
                )}

                <button
                  onClick={() => importFileInputRef.current?.click()}
                  disabled={sessionBusy}
                  className={`w-full py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover ${
                    sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                  }`}
                  title="Re-upload a saved session wallet backup file"
                >
                  Re-upload Key File
                </button>

                {storedSessionWallets.length > 0 && (
                  <div className="p-3 rounded-lg bg-bg-tertiary border border-border-primary">
                    <div className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">Recover / Sweep Existing Wallets (This Device)</div>
                    <div className="mt-2 space-y-1.5">
                      {storedSessionWallets.slice(0, 4).map((w) => (
                        <button
                          key={w.publicKey}
                          onClick={() => {
                            setSweepError(null);
                            setSessionWalletPubkey(w.publicKey);
                          }}
                          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border bg-bg-secondary text-text-muted border-border-primary hover:border-border-hover transition-colors"
                          title="Select this wallet to sweep funds or activate auto execution"
                        >
                          <span className="text-[11px] font-mono text-text-primary">
                            {w.publicKey.slice(0, 6)}...{w.publicKey.slice(-4)}
                          </span>
                          <span className="ml-auto text-[11px] font-mono font-semibold">
                            {typeof w.balanceSol === 'number' ? `${w.balanceSol.toFixed(4)} SOL` : '—'}
                          </span>
                        </button>
                      ))}
                    </div>
                    <div className="mt-2 text-[10px] text-text-muted/70">
                      Tip: click a wallet above, then use Sweep Back to recover funds.
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                {/* Session key missing warning */}
                {!sessionKeyOk && (
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-accent-error/10 border border-accent-error/20">
                    <AlertTriangle className="w-4 h-4 text-accent-error flex-shrink-0 mt-0.5" />
                    <div className="flex flex-col gap-1">
                      <span className="text-[12px] font-semibold text-accent-error">Session key missing</span>
                      <span className="text-[10px] text-text-muted/80">
                        Private key not found in this browser storage. Use Recover via Signature (recommended), Import Key, or Sweep Back.
                      </span>
                    </div>
                  </div>
                )}

                {/* Recovery buttons */}
                {!sessionKeyOk && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    <button
                      onClick={() => {
                        if (!connected && !connecting) {
                          void connect();
                          return;
                        }
                        void handleRecoverSessionWalletViaSignature();
                      }}
                      disabled={sessionBusy || (!!connecting && !connected)}
                      className={`py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-accent-warning/10 text-accent-warning border-accent-warning/20 hover:border-accent-warning/40 ${
                        sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                      }`}
                      title={!connected ? 'Connect Phantom, then sign to recover' : 'Recover deterministic session wallet via Phantom signature'}
                    >
                      Recover via Signature
                    </button>
                    <button
                      onClick={() => setImportKeyOpen(v => !v)}
                      disabled={sessionBusy}
                      className={`py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover ${
                        sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                      }`}
                      title="Paste a saved session key backup file to recover funds"
                    >
                      {importKeyOpen ? 'Hide Import' : 'Import Key'}
                    </button>
                    <button
                      onClick={() => importFileInputRef.current?.click()}
                      disabled={sessionBusy}
                      className={`py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover ${
                        sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                      }`}
                      title="One-click import from a saved session wallet file"
                    >
                      Re-upload File
                    </button>
                  </div>
                )}

                {/* Import key area */}
                {!sessionKeyOk && importKeyOpen && (
                  <div className="p-3 rounded-lg bg-bg-tertiary border border-border-primary space-y-2">
                    <textarea
                      value={importKeyText}
                      onChange={(e) => setImportKeyText(e.target.value)}
                      placeholder="Paste JSON array (e.g. [12,34,...]) from your jarvis-session-wallet-*.txt backup file"
                      rows={4}
                      className="w-full bg-bg-secondary border border-border-primary rounded-lg px-3 py-2 text-[11px] font-mono text-text-primary outline-none placeholder:text-text-muted/40 focus:border-accent-warning/40 transition-all"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => void handleImportSessionWalletKey()}
                        className="flex-1 py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-accent-warning text-black border-accent-warning/30 hover:bg-accent-warning/90"
                      >
                        Import
                      </button>
                      <button
                        onClick={() => {
                          setImportKeyText('');
                          setImportKeyOpen(false);
                        }}
                        className="py-2.5 px-3 rounded-lg text-[11px] font-semibold transition-all border bg-bg-secondary text-text-muted border-border-primary hover:border-border-hover"
                      >
                        Cancel
                      </button>
                    </div>
                    <div className="text-[10px] text-text-muted/70 leading-relaxed">
                      If you never saved the backup file and this wallet wasn&apos;t created in deterministic mode, it cannot be recovered.
                    </div>
                  </div>
                )}

                {/* Sweep error */}
                {sweepError && (
                  <div className="flex items-start gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/20">
                    <AlertTriangle className="w-3.5 h-3.5 text-accent-error flex-shrink-0 mt-0.5" />
                    <span className="text-[10px] text-accent-error/90">{sweepError}</span>
                  </div>
                )}

                {/* Session address + actions */}
                <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-bg-tertiary border border-border-primary">
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-[10px] text-text-muted uppercase tracking-wider">Session Address</span>
                    <span className="text-[11px] font-mono text-text-primary break-all mt-0.5">
                      {sessionWalletPubkey}
                    </span>
                  </div>
                  <div className="flex flex-col gap-1.5 flex-shrink-0">
                    <button
                      onClick={async () => {
                        try { await navigator.clipboard.writeText(sessionWalletPubkey); } catch {}
                      }}
                      className="text-[10px] font-mono px-2.5 py-1.5 rounded-lg border bg-bg-secondary text-text-muted border-border-primary hover:border-border-hover"
                      title="Copy address"
                    >
                      Copy
                    </button>
                    <button
                      onClick={async () => {
                        const ok = await downloadSessionKeyByPubkey(sessionWalletPubkey);
                        if (ok) {
                          setKeyPendingSave(false);
                        } else {
                          setSweepError('Cannot download key — private key not found in browser storage.');
                        }
                      }}
                      className="text-[10px] font-mono px-2.5 py-1.5 rounded-lg border bg-accent-warning/10 text-accent-warning border-accent-warning/20 hover:border-accent-warning/40"
                      title="Download private key backup file"
                    >
                      Save Key
                    </button>
                  </div>
                </div>

                {/* Other session wallets */}
                {storedSessionWallets.length > 1 && (
                  <div className="p-3 rounded-lg bg-bg-tertiary border border-border-primary">
                    <div className="text-[10px] text-text-muted uppercase tracking-wider font-semibold">Other Session Wallets (This Device)</div>
                    <div className="mt-2 space-y-1.5">
                      {storedSessionWallets
                        .filter((w) => w.publicKey !== sessionWalletPubkey)
                        .slice(0, 4)
                        .map((w) => (
                          <button
                            key={w.publicKey}
                            onClick={() => {
                              setSweepError(null);
                              setSessionWalletPubkey(w.publicKey);
                            }}
                            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg border bg-bg-secondary text-text-muted border-border-primary hover:border-border-hover transition-colors"
                            title="Switch the controls to this session wallet (useful for sweeping old funds)"
                          >
                            <span className="text-[11px] font-mono text-text-primary">
                              {w.publicKey.slice(0, 6)}...{w.publicKey.slice(-4)}
                            </span>
                            <span className="ml-auto text-[11px] font-mono font-semibold">
                              {typeof w.balanceSol === 'number' ? `${w.balanceSol.toFixed(4)} SOL` : '—'}
                            </span>
                          </button>
                        ))}
                    </div>
                    <div className="mt-2 text-[10px] text-text-muted/70">
                      Tip: switch to a wallet above, then click Sweep Back.
                    </div>
                  </div>
                )}

                {/* Balance display */}
                <div className="flex items-center justify-between text-[11px] font-mono px-1 py-1">
                  <span className="text-text-muted">Balance</span>
                  <span className={`font-bold text-sm ${sessionBalanceSol != null && sessionBalanceSol > 0 ? 'text-accent-warning' : 'text-text-muted'}`}>
                    {sessionBalanceSol == null ? '—' : `${sessionBalanceSol.toFixed(4)} SOL`}
                  </span>
                </div>

                {/* Fund input */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    inputMode="decimal"
                    placeholder={`Fund (ex: ${budget.budgetSol} SOL)`}
                    value={sessionFundSol}
                    onChange={(e) => setSessionFundSol(e.target.value)}
                    disabled={sessionBusy}
                    className="flex-1 bg-bg-tertiary border border-border-primary rounded-lg px-3 py-2.5 text-xs font-mono text-text-primary outline-none placeholder:text-text-muted/40 focus:border-accent-warning/40 disabled:opacity-50 transition-all"
                  />
                  <button
                    onClick={handleFundSessionWallet}
                    disabled={sessionBusy}
                    className={`px-5 py-2.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                      connected ? 'bg-accent-warning text-black hover:bg-accent-warning/90' : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
                    } ${(sessionBusy) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                  >
                    {sessionBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : connected ? 'Fund' : 'Connect + Fund'}
                  </button>
                </div>

                {/* Activate auto wallet */}
                <div className="flex items-center justify-between p-3 rounded-lg bg-bg-tertiary border border-border-primary">
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold">Activate Auto Wallet</span>
                    <span className="text-[10px] text-text-muted/70">
                      Set your budget + trade limits, then auto-snipe.
                    </span>
                  </div>
                  <button
                    onClick={openActivate}
                    disabled={!sessionReady || sessionBusy}
                    className={`px-4 py-2.5 rounded-lg text-[11px] font-bold transition-all border flex items-center gap-1.5 ${
                      autoWalletActive
                        ? 'bg-accent-warning/15 text-accent-warning border-accent-warning/30 hover:bg-accent-warning/20'
                        : 'bg-accent-warning text-black border-accent-warning/30 hover:bg-accent-warning/90'
                    } ${(!sessionReady || sessionBusy) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                    title={!sessionReady ? 'Session key missing in this browser' : autoWalletActive ? 'Adjust plan (budget / limits)' : 'Activate auto trading with session wallet'}
                  >
                    {autoWalletActive ? <><ShieldCheck className="w-3.5 h-3.5" /> Active</> : <><Flame className="w-3.5 h-3.5" /> Activate</>}
                  </button>
                </div>

                {/* Action buttons */}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={handleSweepSessionWallet}
                    disabled={sessionBusy}
                    className={`py-2.5 rounded-lg text-[11px] font-semibold transition-all border ${
                      confirmSweep
                        ? 'bg-accent-error/20 text-accent-error border-accent-error/40 animate-pulse'
                        : 'bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover'
                    } ${sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                    title="Send all SOL back to your main Phantom wallet (leaves tiny dust for fees)"
                  >
                    {confirmSweep ? 'Click again to sweep' : 'Sweep Back'}
                  </button>
                  <button
                    onClick={handleDestroySessionWallet}
                    disabled={sessionBusy}
                    className={`py-2.5 rounded-lg text-[11px] font-semibold transition-all border ${
                      confirmDeleteSession
                        ? 'bg-accent-error/20 text-accent-error border-accent-error/40 animate-pulse'
                        : 'bg-accent-error/[0.06] text-accent-error/80 border-accent-error/20 hover:border-accent-error/40 hover:text-accent-error'
                    } ${sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                    title="Deletes the active session key from this device. Will attempt to sweep funds first (if key is available)."
                  >
                    {confirmDeleteSession ? 'Click again to delete' : 'Delete Session'}
                  </button>
                </div>

                {/* Switch back to Phantom */}
                {usingSession && (
                  <button
                    onClick={() => {
                      setConfig({ autoSnipe: false });
                      setTradeSignerMode('phantom');
                    }}
                    disabled={sessionBusy}
                    className={`w-full py-2.5 rounded-lg text-[11px] font-semibold transition-all border bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover ${
                      sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                    }`}
                    title="Switch signing back to Phantom (manual). Auto-Snipe will turn off."
                  >
                    Switch to Phantom
                  </button>
                )}

                <p className="text-[10px] text-text-muted/60 leading-relaxed">
                  Note: auto-execution still requires this page to stay open. If you close the tab, automation stops.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {activateOpen && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={closeActivate} />
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="activate-auto-wallet-title"
            className="relative w-full max-w-[560px] card-glass p-5 border border-accent-warning/25 shadow-xl"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 w-9 h-9 rounded-full bg-accent-warning/15 border border-accent-warning/25 flex items-center justify-center">
                <Flame className="w-4.5 h-4.5 text-accent-warning" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between gap-3">
                  <h2 id="activate-auto-wallet-title" className="font-display text-base font-semibold">
                    Activate Auto Wallet
                  </h2>
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-accent-warning/10 text-accent-warning border border-accent-warning/25">
                    session
                  </span>
                </div>

                <p className="mt-2 text-[12px] text-text-secondary leading-relaxed">
                  This will switch trading to your Session Wallet and optionally turn on Auto-Snipe using the strategy you selected above.
                  Buys and sells execute through Bags. Keep this tab open for automation.
                </p>

                <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                    <div className="text-[9px] text-text-muted uppercase tracking-wider">Total Budget (SOL)</div>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={activateBudget}
                      onChange={(e) => setActivateBudget(e.target.value)}
                      className="mt-1 w-full bg-bg-secondary border border-border-primary rounded-lg px-3 py-2 text-xs font-mono text-text-primary outline-none focus:border-accent-warning/40"
                      placeholder="0.10"
                    />
                    <div className="mt-1 text-[9px] text-text-muted/70">
                      Balance: {sessionBalanceSol == null ? '—' : `${sessionBalanceSol.toFixed(4)} SOL`}
                    </div>
                  </div>

                  <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                    <div className="text-[9px] text-text-muted uppercase tracking-wider">Max Trades</div>
                    <input
                      type="text"
                      inputMode="numeric"
                      value={activateMaxTrades}
                      onChange={(e) => setActivateMaxTrades(e.target.value)}
                      className="mt-1 w-full bg-bg-secondary border border-border-primary rounded-lg px-3 py-2 text-xs font-mono text-text-primary outline-none focus:border-accent-warning/40"
                      placeholder="4"
                    />
                    <div className="mt-1 text-[9px] text-text-muted/70">
                      (Max open positions)
                    </div>
                  </div>

                  <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                    <div className="text-[9px] text-text-muted uppercase tracking-wider">Max / Trade (SOL)</div>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={activatePerTrade}
                      onChange={(e) => setActivatePerTrade(e.target.value)}
                      className="mt-1 w-full bg-bg-secondary border border-border-primary rounded-lg px-3 py-2 text-xs font-mono text-text-primary outline-none focus:border-accent-warning/40"
                      placeholder="0.03"
                    />
                    <div className="mt-1 text-[9px] text-text-muted/70">
                      (Hard cap per buy)
                    </div>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between p-2.5 rounded-lg bg-bg-tertiary border border-border-primary">
                  <div className="flex flex-col">
                    <span className="text-xs font-semibold">Enable Auto-Snipe</span>
                    <span className="text-[9px] text-text-muted/70">
                      Automatically buys new tokens that pass the active strategy filters.
                    </span>
                  </div>
                  <button
                    onClick={() => setActivateAutoSnipe(!activateAutoSnipe)}
                    className={`relative w-10 h-5 rounded-full transition-all ${
                      activateAutoSnipe ? 'bg-accent-warning' : 'bg-bg-secondary border border-border-primary'
                    }`}
                    title={activateAutoSnipe ? 'Auto-Snipe will turn ON' : 'Auto-Snipe will stay OFF'}
                  >
                    <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
                      activateAutoSnipe ? 'left-[22px] bg-black' : 'left-0.5 bg-text-muted'
                    }`} />
                  </button>
                </div>

                {activateError && (
                  <div className="mt-3 flex items-start gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/20">
                    <AlertCircle className="w-4 h-4 text-accent-error flex-shrink-0 mt-0.5" />
                    <span className="text-[11px] text-accent-error">{activateError}</span>
                  </div>
                )}

                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                  <button
                    onClick={commitSessionPlan}
                    className="btn-neon w-full sm:w-auto flex-1"
                  >
                    Activate
                  </button>
                  <button
                    onClick={closeActivate}
                    className="btn-secondary w-full sm:w-auto flex-1"
                  >
                    Cancel
                  </button>
                </div>

                <p className="mt-3 text-[9px] text-text-muted font-mono">
                  Safety: keep your session wallet small. You can lose 100% on illiquid tokens.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── QUICK SNIPE SECTION ─── */}
      <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Send className="w-3.5 h-3.5 text-accent-neon" />
          <span className="text-xs font-semibold">Quick Snipe</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="Paste token mint address..."
            value={snipeMint}
            onChange={(e) => setSnipeMint(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') handleManualSnipe(); }}
            disabled={!walletReady || !budget.authorized || snipeLoading}
            className="flex-1 bg-bg-tertiary border border-border-primary rounded-lg px-3 py-2 text-xs font-mono text-text-primary outline-none placeholder:text-text-muted/40 focus:border-accent-neon/40 disabled:opacity-50 transition-all"
          />
          <button
            onClick={handleManualSnipe}
            disabled={!walletReady || !budget.authorized || snipeLoading || snipeMint.trim().length < 32}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
              walletReady && budget.authorized && !snipeLoading && snipeMint.trim().length >= 32
                ? 'bg-accent-neon text-black hover:bg-accent-neon/90 cursor-pointer'
                : 'bg-bg-tertiary text-text-muted border border-border-primary opacity-50 cursor-not-allowed'
            }`}
          >
            {snipeLoading ? (
              <><Loader2 className="w-3 h-3 animate-spin" /> Sniping...</>
            ) : (
              <><Crosshair className="w-3 h-3" /> Snipe</>
            )}
          </button>
        </div>
        {!walletReady && (
          <p className="text-[9px] text-accent-warning mt-2">Connect wallet to enable</p>
        )}
        {walletReady && !budget.authorized && (
          <p className="text-[9px] text-accent-warning mt-2">Authorize budget first</p>
        )}
      </div>

      {/* Auto-Snipe Toggle */}
      <div className="flex items-center justify-between p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            config.autoSnipe ? 'bg-accent-neon/15 text-accent-neon' : 'bg-bg-tertiary text-text-muted'
          }`}>
            <Crosshair className="w-4 h-4" />
          </div>
          <div>
            <span className="text-sm font-semibold">Auto-Snipe</span>
              <InfoTip text="When enabled, AI automatically buys qualifying tokens based on your strategy. You can turn this off at any time." />
              <p className="text-[10px] text-text-muted">
                  {!budget.authorized
                    ? 'Authorize a budget to enable'
                    : autoResetRequired
                    ? 'Reset Auto active — re-arm budget/max settings in Activate Auto Wallet first'
                    : config.autoSnipe
                    ? `${activePresetLabel}: Liq≥$${Math.round(config.minLiquidityUsd).toLocaleString('en-US')} + V/L≥0.5 + B/S 1-3 + Age<500h + Mom↑ + TOD | ${useRecommendedExits ? 'REC SL/TP' : `${config.stopLossPct}/${config.takeProfitPct}`}+${config.trailingStopPct}t${config.maxPositionAgeHours > 0 ? ` | ${config.maxPositionAgeHours}h expiry` : ''}`
                    : 'Manual mode — click to snipe'}
              </p>
              <p className={`text-[9px] font-mono mt-1 ${
                wrGateScopeActive
                  ? 'text-accent-neon/80'
                  : 'text-text-muted/70'
              }`}>
                {config.autoWrGateEnabled
                  ? wrGateScopeActive
                    ? wrGatePolicy
                    : `${wrGatePolicy} (inactive for ${assetFilter})`
                  : 'WR Gate: OFF'}
              </p>
            </div>
          </div>
        <button
          onClick={() => {
            const next = !config.autoSnipe;
            if (next && autoResetRequired) {
              addExecution({
                id: `auto-rearm-required-${Date.now()}`,
                type: 'error',
                symbol: 'AUTO',
                mint: '',
                amount: 0,
                reason: 'AUTO_STOP_RESET_AUTO: Re-arm required. Open Activate Auto Wallet and set total budget, max trades, and max SOL per trade.',
                timestamp: Date.now(),
              });
              openActivate();
              return;
            }
            setConfig({ autoSnipe: next });
          }}
          disabled={!canTradeNow}
          className={`relative w-12 h-6 rounded-full transition-all duration-300 ${
            config.autoSnipe ? 'bg-accent-neon' : 'bg-bg-tertiary border border-border-primary'
          } ${!canTradeNow ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <span className={`absolute top-0.5 w-5 h-5 rounded-full transition-all duration-300 ${
            config.autoSnipe
              ? 'left-[26px] bg-black'
              : 'left-0.5 bg-text-muted'
          }`} />
        </button>
      </div>

      {atCapacity && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/20 mb-4">
          <AlertTriangle className="w-4 h-4 text-accent-error flex-shrink-0" />
          <span className="text-[11px] text-accent-error">
            At max capacity ({openPositionCount}/{config.maxConcurrentPositions})
          </span>
        </div>
      )}

      {/* Config Section */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-xs text-text-muted hover:text-text-secondary transition-colors mb-3"
      >
        <span className="font-medium uppercase tracking-wider">Parameters</span>
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {expanded && (
        <div className="space-y-3 animate-fade-in">
          <div className="grid grid-cols-2 gap-3">
            <ConfigField
              icon={<Shield className="w-3.5 h-3.5 text-accent-error" />}
              label="Stop Loss"
              value={config.stopLossPct}
              suffix="%"
              onChange={(v) => setConfig({ stopLossPct: v })}
              min={1}
              max={50}
              tooltip="Auto-sells if price drops this % from your entry. Protects you from big losses."
            />
            <ConfigField
              icon={<Target className="w-3.5 h-3.5 text-accent-neon" />}
              label="Take Profit"
              value={config.takeProfitPct}
              suffix="%"
              onChange={(v) => setConfig({ takeProfitPct: v })}
              min={5}
              max={500}
              tooltip="Auto-sells if price rises this % from your entry. Locks in your gains."
            />
            <ConfigField
              icon={<TrendingUp className="w-3.5 h-3.5 text-accent-warning" />}
              label="Trailing Stop"
              value={config.trailingStopPct}
              suffix="%"
              onChange={(v) => setConfig({ trailingStopPct: v })}
              min={1}
              max={30}
              tooltip="Locks in profits by selling if price drops this % from its highest point. Follows the price up but never down."
            />
            <ConfigField
              icon={<Zap className="w-3.5 h-3.5 text-accent-neon" />}
              label="Per-Snipe"
              value={config.maxPositionSol}
              suffix=" SOL"
              onChange={(v) => setConfig({ maxPositionSol: v })}
              min={0.01}
              max={50}
              step={0.01}
              tooltip="Maximum SOL to spend on each individual trade. Smaller = safer."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <ConfigField
              label="Min Score"
              value={config.minScore}
              onChange={(v) => setConfig({ minScore: v })}
              min={0}
              max={100}
              tooltip="Higher = stricter quality filter. 40+ recommended for beginners. Lower values let in more tokens but with higher risk."
            />
            <ConfigField
              label="Max Positions"
              value={config.maxConcurrentPositions}
              onChange={(v) => setConfig({ maxConcurrentPositions: v })}
              min={1}
              max={50}
            />
          </div>

          {/* Exits: recommended vs global */}
          <div className="flex items-center justify-between p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
            <div className="flex items-center gap-2">
              <Target className="w-3.5 h-3.5 text-accent-neon" />
              <div className="flex flex-col">
                <span className="text-xs font-medium">Use recommended exits</span>
                <span className="text-[9px] text-text-muted/70">Per-token backtested SL/TP. Turn off to force global SL/TP.</span>
              </div>
            </div>
            <button
              onClick={() => setConfig({ useRecommendedExits: !useRecommendedExits })}
              className={`relative w-10 h-5 rounded-full transition-all ${
                useRecommendedExits ? 'bg-accent-neon' : 'bg-bg-tertiary border border-border-primary'
              }`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
                useRecommendedExits ? 'left-[22px] bg-black' : 'left-0.5 bg-text-muted'
              }`} />
            </button>
          </div>

          {/* Liquidity gate (HYBRID-B) */}
          <div className="p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-text-muted uppercase tracking-wider">Min Liquidity (USD)</span>
              <span className="text-[10px] font-mono text-text-muted">${Math.round(config.minLiquidityUsd).toLocaleString('en-US')}</span>
            </div>
            <div className="flex gap-1">
              {LIQUIDITY_PRESETS_USD.map((usd) => (
                <button
                  key={usd}
                  onClick={() => setConfig({ minLiquidityUsd: usd })}
                  className={`flex-1 text-[10px] font-mono px-2 py-1 rounded transition-all ${
                    config.minLiquidityUsd === usd
                      ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
                      : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
                  }`}
                >
                  {usd >= 1000 ? `${Math.round(usd / 1000)}K` : String(usd)}
                </button>
              ))}
            </div>
            <p className="text-[9px] text-text-muted/60 mt-2">
              Lower = more trades, but higher rug/spread risk. Default 25K is practical; 50K matched the OHLCV backtest.
            </p>
          </div>

          {/* Jito Toggle */}
          <div className="flex items-center justify-between p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
            <div className="flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-accent-neon" />
              <span className="text-xs font-medium">Jito MEV Protection</span>
            </div>
            <button
              onClick={() => setConfig({ useJito: !config.useJito })}
              className={`relative w-10 h-5 rounded-full transition-all ${
                config.useJito ? 'bg-accent-neon' : 'bg-bg-tertiary border border-border-primary'
              }`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
                config.useJito ? 'left-[22px] bg-black' : 'left-0.5 bg-text-muted'
              }`} />
            </button>
          </div>

          {/* Position Age Expiry */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">Max Age (auto-close)</span>
            <div className="flex gap-1">
              {[2, 4, 8, 0].map((hrs) => (
                <button
                  key={hrs}
                  onClick={() => setConfig({ maxPositionAgeHours: hrs })}
                  className={`text-[10px] font-mono px-2 py-1 rounded transition-all ${
                    config.maxPositionAgeHours === hrs
                      ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
                      : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
                  }`}
                >
                  {hrs === 0 ? 'OFF' : `${hrs}h`}
                </button>
              ))}
            </div>
          </div>

          {/* Slippage */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">Slippage</span>
            <div className="flex gap-1">
              {[100, 150, 300, 500].map((bps) => (
                <button
                  key={bps}
                  onClick={() => setConfig({ slippageBps: bps })}
                  className={`text-[10px] font-mono px-2 py-1 rounded transition-all ${
                    config.slippageBps === bps
                      ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
                      : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
                  }`}
                >
                  {(bps / 100).toFixed(1)}%
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      <PerAssetBreakerPanel />
    </div>
  );
}

function PerAssetBreakerPanel() {
  const { config, setConfig, circuitBreaker } = useSniperStore();
  const [limitsOpen, setLimitsOpen] = useState(false);
  const [now, setNow] = useState(0);
  useEffect(() => {
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const AL: Record<AssetType, string> = { memecoin: 'Meme', bags: 'Bags', bluechip: 'Blue Chip', xstock: 'xStock', index: 'Index', prestock: 'PreStock' };
  const resetAB = (t: AssetType) => { useSniperStore.setState((s) => { const cb = { ...s.circuitBreaker, perAsset: { ...s.circuitBreaker.perAsset } }; cb.perAsset[t] = makeDefaultAssetBreaker(); return { circuitBreaker: cb }; }); };
  const updateAC = (t: AssetType, p: Partial<PerAssetBreakerConfig>) => { const c = config.perAssetBreakerConfig || ({} as Record<AssetType, PerAssetBreakerConfig>); setConfig({ perAssetBreakerConfig: { ...c, [t]: { ...c[t], ...p } } }); };
  if (!config.circuitBreakerEnabled) return null;
  const ats: AssetType[] = ['memecoin', 'bags', 'bluechip', 'xstock', 'index', 'prestock'];
  return (
    <div className="mt-4">
      <button onClick={() => setLimitsOpen(!limitsOpen)} className="flex items-center justify-between w-full text-xs text-text-muted hover:text-text-secondary transition-colors mb-3">
        <span className="font-medium uppercase tracking-wider">Circuit Breakers</span>
        {limitsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>
      <div className="grid grid-cols-5 gap-1 mb-2">
        {ats.map((at) => {
          const ab = circuitBreaker.perAsset[at]; const acfg = config.perAssetBreakerConfig?.[at]; const maxL = acfg?.maxConsecutiveLosses || config.maxConsecutiveLosses;
          const inCD = ab.tripped && ab.cooldownUntil > 0 && now < ab.cooldownUntil;
          let sc = 'bg-accent-success', sl = 'OK';
          if (ab.tripped) { if (inCD) { sc = 'bg-accent-warning'; sl = `${Math.ceil((ab.cooldownUntil - now) / 60_000)}m`; } else { sc = 'bg-accent-error'; sl = 'TRIP'; } }
          else if (ab.consecutiveLosses > 0 && maxL > 0 && ab.consecutiveLosses >= maxL - 1) { sc = 'bg-accent-warning'; sl = 'NEAR'; }
          return (<div key={at} className="flex flex-col items-center gap-0.5 p-1.5 rounded bg-bg-secondary border border-border-primary" title={ab.tripped ? ab.reason : `${ab.consecutiveLosses}/${maxL} losses`}>
            <div className={`w-2 h-2 rounded-full ${sc}`} />
            <span className="text-[8px] text-text-muted font-mono truncate w-full text-center">{AL[at]}</span>
            <span className="text-[8px] text-text-muted font-mono">{ab.consecutiveLosses}/{maxL}</span>
            <span className={`text-[7px] font-bold ${ab.tripped ? (inCD ? 'text-accent-warning' : 'text-accent-error') : 'text-accent-success'}`}>{sl}</span>
            {ab.tripped && <button onClick={() => resetAB(at)} className="text-[7px] text-accent-neon hover:underline mt-0.5">Reset</button>}
          </div>);
        })}
      </div>
      {circuitBreaker.tripped && (<div className="flex items-center gap-2 p-2 rounded-lg bg-accent-error/10 border border-accent-error/20 mb-2">
        <AlertTriangle className="w-3.5 h-3.5 text-accent-error flex-shrink-0" /><span className="text-[10px] text-accent-error flex-1">{circuitBreaker.reason}</span>
        <button onClick={() => useSniperStore.getState().resetCircuitBreaker()} className="text-[9px] text-accent-neon hover:underline">Reset All</button>
      </div>)}
      {limitsOpen && (<div className="space-y-2 animate-fade-in">
        <p className="text-[9px] text-text-muted/70 mb-1">Per-asset limits isolate losses: tripping memecoin breaker will not block blue chip trades.</p>
        <div className="overflow-x-auto"><table className="w-full text-[10px]">
          <thead><tr className="text-text-muted border-b border-border-primary"><th className="text-left py-1 pr-2">Asset</th><th className="text-center py-1 px-1">Losses</th><th className="text-center py-1 px-1">Daily</th><th className="text-center py-1 px-1">CD</th></tr></thead>
          <tbody>{ats.map((at) => { const ac = config.perAssetBreakerConfig?.[at] || { maxConsecutiveLosses: 0, maxDailyLossSol: 0, cooldownMinutes: 0 }; return (
            <tr key={at} className="border-b border-border-primary/50">
              <td className="py-1.5 pr-2 text-text-secondary font-medium">{AL[at]}</td>
              <td className="py-1.5 px-1 text-center"><input type="number" min={0} max={20} step={1} value={ac.maxConsecutiveLosses} onChange={(e) => updateAC(at, { maxConsecutiveLosses: parseInt(e.target.value) || 0 })} className="w-10 bg-bg-tertiary border border-border-primary rounded px-1 py-0.5 text-center text-text-primary font-mono text-[10px] outline-none focus:border-accent-neon/50" /></td>
              <td className="py-1.5 px-1 text-center"><div className="flex items-center justify-center gap-0.5"><input type="number" min={0} max={10} step={0.1} value={ac.maxDailyLossSol} onChange={(e) => updateAC(at, { maxDailyLossSol: parseFloat(e.target.value) || 0 })} className="w-12 bg-bg-tertiary border border-border-primary rounded px-1 py-0.5 text-center text-text-primary font-mono text-[10px] outline-none focus:border-accent-neon/50" /><span className="text-text-muted text-[8px]">S</span></div></td>
              <td className="py-1.5 px-1 text-center"><div className="flex items-center justify-center gap-0.5"><input type="number" min={0} max={120} step={5} value={ac.cooldownMinutes} onChange={(e) => updateAC(at, { cooldownMinutes: parseInt(e.target.value) || 0 })} className="w-10 bg-bg-tertiary border border-border-primary rounded px-1 py-0.5 text-center text-text-primary font-mono text-[10px] outline-none focus:border-accent-neon/50" /><span className="text-text-muted text-[8px]">m</span></div></td>
            </tr>); })}</tbody>
        </table></div>
        <div className="flex items-center justify-between pt-1"><span className="text-[9px] text-text-muted">Global: {config.maxConsecutiveLosses} losses / {config.maxDailyLossSol} SOL daily</span></div>
      </div>)}
    </div>
  );
}

function ConfigField({
  icon,
  label,
  value,
  suffix = '',
  onChange,
  min = 0,
  max = 100,
  step = 1,
  tooltip,
}: {
  icon?: React.ReactNode;
  label: string;
  value: number;
  suffix?: string;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
  tooltip?: string;
}) {
  // Display rounded to 2 decimal places
  const displayValue = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
  const [localValue, setLocalValue] = useState(displayValue);
  const [focused, setFocused] = useState(false);

  // Sync from parent when not focused
  useEffect(() => {
    if (!focused) {
      const dv = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
      setLocalValue(dv);
    }
  }, [value, focused]);

  const commit = (raw: string) => {
    const v = parseFloat(raw);
    if (!isNaN(v) && v >= min && v <= max) {
      onChange(Math.round(v * 100) / 100);
    } else {
      const dv = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
      setLocalValue(dv);
    }
  };

  return (
    <div className="flex flex-col gap-1.5 p-2.5 rounded-lg bg-bg-secondary border border-border-primary min-w-0 overflow-hidden">
      <div className="flex items-center gap-1.5 min-w-0">
        {icon && <span className="flex-shrink-0">{icon}</span>}
        <span className="text-[10px] text-text-muted uppercase tracking-wider truncate">{label}</span>
        {tooltip && <InfoTip text={tooltip} />}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          inputMode="decimal"
          value={localValue}
          onFocus={() => setFocused(true)}
          onBlur={() => { setFocused(false); commit(localValue); }}
          onChange={(e) => setLocalValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') commit(localValue); }}
          className="w-full bg-transparent text-sm font-mono font-bold text-text-primary outline-none"
        />
        {suffix && <span className="text-[10px] text-text-muted font-mono whitespace-nowrap">{suffix}</span>}
      </div>
    </div>
  );
}




