'use client';

import { useState, useEffect } from 'react';
import { Settings, Zap, Shield, Target, TrendingUp, ChevronDown, ChevronUp, Crosshair, AlertTriangle, Wallet, Lock, Unlock, DollarSign, Loader2, Send, Flame, ShieldCheck, Info, AlertCircle, BarChart3 } from 'lucide-react';
import { useSniperStore, type SniperConfig, type StrategyMode, STRATEGY_PRESETS } from '@/stores/useSniperStore';
import type { BagsGraduation } from '@/lib/bags-api';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { useSnipeExecutor } from '@/hooks/useSnipeExecutor';
import { buildFundSessionTx, createSessionWallet, destroySessionWallet, getSessionBalance, isLikelyFunded, loadSessionWalletFromStorage, sweepToMainWallet } from '@/lib/session-wallet';

/**
 * Analyze the current scanner feed and suggest the best strategy preset.
 * Pure function — no side effects, no store writes.
 */
function suggestStrategy(graduations: BagsGraduation[]): { presetId: string; reason: string } | null {
  if (graduations.length < 3) return null; // need enough data to decide

  // Compute market statistics from the feed
  const liqs = graduations.map(g => g.liquidity || 0).filter(l => l > 0);
  const avgLiq = liqs.length > 0 ? liqs.reduce((a, b) => a + b, 0) / liqs.length : 0;
  const medianLiq = liqs.length > 0 ? liqs.sort((a, b) => a - b)[Math.floor(liqs.length / 2)] : 0;

  const momPositive = graduations.filter(g => (g.price_change_1h ?? 0) > 0).length;
  const momPct = momPositive / graduations.length;

  const vols = graduations.map(g => g.volume_24h || 0).filter(v => v > 0);
  const avgVol = vols.length > 0 ? vols.reduce((a, b) => a + b, 0) / vols.length : 0;
  const highVolCount = graduations.filter(g => {
    const l = g.liquidity || 0;
    const v = g.volume_24h || 0;
    return l > 0 && v / l >= 3;
  }).length;

  // Count tokens passing each preset's minimum liquidity gate
  const countAbove = (usd: number) => liqs.filter(l => l >= usd).length;
  const above10k = countAbove(10000);
  const above25k = countAbove(25000);
  const above40k = countAbove(40000);
  const above50k = countAbove(50000);

  // Decision tree (simple, interpretable)
  // 1. Strong bull momentum + high volume → LET IT RIDE
  if (momPct >= 0.6 && highVolCount >= 3 && above40k >= 3) {
    return { presetId: 'let_it_ride', reason: `${Math.round(momPct * 100)}% momentum + high vol activity` };
  }

  // 2. Many high-vol tokens but mixed momentum → MOMENTUM (wide net)
  if (highVolCount >= 4 && above10k >= 5) {
    return { presetId: 'momentum', reason: `${highVolCount} high Vol/Liq tokens in feed` };
  }

  // 3. Plenty of tokens above $40K but not wild momentum → HYBRID-B (balanced default)
  if (above40k >= 4) {
    return { presetId: 'hybrid_b', reason: `${above40k} tokens above $40K liq` };
  }

  // 4. Decent liquidity, young tokens, positive momentum → INSIGHT-J
  if (above25k >= 3 && momPct >= 0.4) {
    return { presetId: 'insight_j', reason: `${above25k} tokens with $25K+ liq & ${Math.round(momPct * 100)}% momentum` };
  }

  // 5. Very high liquidity cluster → INSIGHT-I (institutional)
  if (above50k >= 3) {
    return { presetId: 'insight_i', reason: `${above50k} tokens with $50K+ liq` };
  }

  // 6. Lots of tokens passing lax filters → HOT (high volume of trades)
  if (above10k >= 6) {
    return { presetId: 'hot', reason: `Active feed: ${above10k} tokens above $10K` };
  }

  // 7. Thin market → MOMENTUM (cast widest net)
  if (graduations.length >= 3) {
    return { presetId: 'momentum', reason: 'Thin market — wide net is safest' };
  }

  return null;
}

const BUDGET_PRESETS = [0.1, 0.2, 0.5, 1.0];
const LIQUIDITY_PRESETS_USD = [10000, 25000, 40000, 50000];

/** Rich strategy descriptions shown in the breakdown panel */
const STRATEGY_INFO: Record<string, { summary: string; optimal: string; risk: string; params: string }> = {
  momentum: {
    summary: 'Targets high-conviction tokens with strong volume activity and decent scores. Casts a wider net with no liquidity floor.',
    optimal: 'Best in active markets with many new graduates. High volume-to-liquidity ratios signal organic demand, not wash trading.',
    risk: 'No minimum liquidity means higher slippage risk on entry/exit. Use smaller position sizes.',
    params: 'SL 20% | TP 60% | Trail 8% | Score 50+ | Vol/Liq 3+',
  },
  insight_j: {
    summary: 'Strict quality filter requiring $25K+ liquidity, young tokens (<100h), and positive momentum. High selectivity = fewer but better trades.',
    optimal: 'Works best when you want quality over quantity. The 86% win rate comes from only touching tokens with real market depth.',
    risk: 'Very selective — may go long periods without a trade. Requires patience for the right setup.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $25K+ | Age <100h',
  },
  hot: {
    summary: 'Balanced approach: requires both a minimum score (60+) and liquidity ($10K+). Generates the most trades of any strategy.',
    optimal: 'Ideal for active trading sessions. More opportunities but a wider spread of outcomes. Volume-weighted for real activity.',
    risk: 'Lower win rate (49%) means you need discipline with stop losses. The volume of trades smooths returns over time.',
    params: 'SL 20% | TP 60% | Trail 8% | Score 60+ | Liq $10K+',
  },
  hybrid_b: {
    summary: 'The battle-tested default. Combines all HYBRID-B insight filters with a $40K liquidity floor. 100% WR in OHLCV validation.',
    optimal: 'The go-to for most sessions. Strong enough filters to avoid rugs, loose enough to still find trades regularly.',
    risk: 'Small sample size (10 trades in backtest). Performance may regress to mean, but the filter logic is sound.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $40K+ | All filters on',
  },
  let_it_ride: {
    summary: 'Aggressive mode with 100% take-profit and tight 5% trailing stop. Designed to capture large moves while protecting gains.',
    optimal: 'Perfect for bull markets or when scanning shows strong momentum. The tight trail locks in gains on any pullback.',
    risk: 'The 5% trail means early exits on normal volatility. Best when conviction is very high on a specific token.',
    params: 'SL 20% | TP 100% | Trail 5% | Liq $40K+ | Aggressive mode',
  },
  insight_i: {
    summary: 'The strictest preset: $50K liquidity, age under 200h, and B/S ratio in the 1-3 sweet spot. Maximum quality filter.',
    optimal: 'When you want to be extremely selective. Only trades tokens with institutional-grade liquidity and balanced order flow.',
    risk: 'Very few tokens pass all gates. You may see 0 trades for hours. Best combined with patience and larger position sizes.',
    params: 'SL 20% | TP 60% | Trail 8% | Liq $50K+ | B/S 1-3 | Age <200h',
  },
};

export function SniperControls() {
  const { config, setConfig, setStrategyMode, loadPreset, activePreset, loadBestEver, positions, budget, setBudgetSol, authorizeBudget, deauthorizeBudget, budgetRemaining, graduations, tradeSignerMode, setTradeSignerMode, sessionWalletPubkey, setSessionWalletPubkey } = useSniperStore();
  const { connected, address, signTransaction, publicKey } = usePhantomWallet();
  const { snipe, ready: walletReady } = useSnipeExecutor();
  const [expanded, setExpanded] = useState(true);
  const [bestEverLoaded, setBestEverLoaded] = useState(false);
  const [customBudget, setCustomBudget] = useState('');
  const [budgetFocused, setBudgetFocused] = useState(false);
  const [snipeMint, setSnipeMint] = useState('');
  const [snipeLoading, setSnipeLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);

  // Session wallet (auto-signing) state
  const [sessionBalanceSol, setSessionBalanceSol] = useState<number | null>(null);
  const [sessionBusy, setSessionBusy] = useState(false);
  const [sessionFundSol, setSessionFundSol] = useState('');
  const [confirmSweep, setConfirmSweep] = useState(false);
  const [activateOpen, setActivateOpen] = useState(false);
  const [activateBudget, setActivateBudget] = useState('');
  const [activateMaxTrades, setActivateMaxTrades] = useState('');
  const [activatePerTrade, setActivatePerTrade] = useState('');
  const [activateAutoSnipe, setActivateAutoSnipe] = useState(true);
  const [activateError, setActivateError] = useState<string | null>(null);

  // Load BEST_EVER on mount
  useEffect(() => {
    loadBestEverConfig();
  }, []);

  // Sync session wallet pubkey from sessionStorage on mount (tab refresh safe)
  useEffect(() => {
    try {
      const stored = loadSessionWalletFromStorage();
      if (stored && !sessionWalletPubkey) {
        setSessionWalletPubkey(stored.publicKey);
      }
    } catch {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const openPositionCount = positions.filter(p => p.status === 'open').length;
  const atCapacity = openPositionCount >= config.maxConcurrentPositions;
  const remaining = budgetRemaining();
  const perSnipeSol = budget.budgetSol > 0
    ? Math.round((budget.budgetSol / config.maxConcurrentPositions) * 100) / 100
    : 0;
  const useRecommendedExits = config.useRecommendedExits !== false;
  const suggestion = suggestStrategy(graduations as BagsGraduation[]);

  const usingSession = tradeSignerMode === 'session';
  const storedSession = sessionWalletPubkey ? loadSessionWalletFromStorage() : null;
  const sessionKeyOk = !!storedSession && storedSession.publicKey === sessionWalletPubkey;
  // "Ready" should not depend on the budget setting; we validate exact amounts in the activate modal.
  const sessionReady = !!sessionWalletPubkey && sessionKeyOk && sessionBalanceSol != null && sessionBalanceSol > 0.005;
  const canTradeNow = budget.authorized && (usingSession ? sessionReady : connected);
  const autoWalletActive = usingSession && budget.authorized;

  function openActivate() {
    setActivateError(null);
    const bal = sessionBalanceSol ?? 0;
    const defaultBudget = bal > 0 ? Math.max(0.01, Math.min(budget.budgetSol || 0.1, Math.max(0, bal - 0.005))) : budget.budgetSol || 0.1;
    setActivateBudget(String(defaultBudget));
    setActivateMaxTrades(String(config.maxConcurrentPositions));
    setActivatePerTrade(String(config.maxPositionSol));
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
    return positions
      .filter((p) => p.status === 'open')
      .reduce((acc, p) => acc + (p.solInvested || 0), 0);
  }

  function commitSessionPlan() {
    const bal = sessionBalanceSol ?? 0;
    const budgetSol = Number.parseFloat(activateBudget);
    const maxTrades = Math.max(1, Math.floor(Number.parseFloat(activateMaxTrades)));
    const perTradeSol = Number.parseFloat(activatePerTrade);

    if (!sessionWalletPubkey) {
      setActivateError('No session wallet found. Create one first.');
      return;
    }
    if (!sessionKeyOk) {
      setActivateError('Session key not found in this tab. Create a new session wallet (the key is not recoverable after closing the tab).');
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

    // Keep a tiny buffer for fees/ATA creation.
    const feeBuffer = 0.005;
    if (bal > 0 && budgetSol > Math.max(0.01, bal - feeBuffer)) {
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
      const { Connection, SystemProgram, Transaction, PublicKey: PK } = await import('@solana/web3.js');
      const connection = new Connection(
        process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com',
        'confirmed',
      );
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
      await connection.confirmTransaction(txHash, 'confirmed');
      console.log('[Auth] On-chain authorization confirmed:', txHash);
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

  async function handleCreateSessionWallet() {
    if (!address) return;
    setSessionBusy(true);
    try {
      const { publicKey: pubkey } = createSessionWallet(address);
      setSessionWalletPubkey(pubkey);
      setTradeSignerMode('phantom'); // user toggles to session after funding
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleFundSessionWallet() {
    if (!connected || !address || !signTransaction || !sessionWalletPubkey) return;
    const amount = Math.max(0.001, Number.parseFloat(sessionFundSol || String(budget.budgetSol)) || budget.budgetSol || 0);
    if (!Number.isFinite(amount) || amount <= 0) return;

    setSessionBusy(true);
    try {
      const fundTx = await buildFundSessionTx(address, sessionWalletPubkey, amount);
      const signed = await signTransaction(fundTx);

      const { Connection } = await import('@solana/web3.js');
      const connection = new Connection(
        process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com',
        'confirmed',
      );

      const sig = await connection.sendRawTransaction(signed.serialize(), {
        skipPreflight: true,
        maxRetries: 3,
      });
      await connection.confirmTransaction(sig, 'confirmed');

      // Refresh balance
      const bal = await getSessionBalance(sessionWalletPubkey);
      setSessionBalanceSol(bal);
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleSweepSessionWallet() {
    if (!confirmSweep) {
      setConfirmSweep(true);
      setTimeout(() => setConfirmSweep(false), 3000);
      return;
    }
    setConfirmSweep(false);

    const stored = loadSessionWalletFromStorage();
    if (!stored) return;

    setSessionBusy(true);
    try {
      await sweepToMainWallet(stored.keypair, stored.mainWallet);
      if (sessionWalletPubkey) {
        const bal = await getSessionBalance(sessionWalletPubkey);
        setSessionBalanceSol(bal);
      }
    } finally {
      setSessionBusy(false);
    }
  }

  function handleDestroySessionWallet() {
    destroySessionWallet();
    setSessionWalletPubkey(null);
    setSessionBalanceSol(null);
    if (usingSession) setTradeSignerMode('phantom');
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
          {STRATEGY_PRESETS.find(p => p.id === activePreset)?.name ?? 'HYBRID-B v5'} {bestEverLoaded ? '+ BEST_EVER' : `${config.stopLossPct}/${config.takeProfitPct}+${config.trailingStopPct}t`}
        </span>
      </div>

      {/* ─── STRATEGY PRESET SELECTOR ─── */}
      <div className="grid grid-cols-2 gap-1.5 mb-4">
        {STRATEGY_PRESETS.map((preset) => {
          const isActive = activePreset === preset.id;
          const isAggressive = preset.config.strategyMode === 'aggressive';
          const isSuggested = suggestion?.presetId === preset.id && !isActive;
          return (
            <button
              key={preset.id}
              onClick={() => loadPreset(preset.id)}
              className={`flex flex-col p-2 rounded-lg border transition-all text-left relative ${
                isActive
                  ? isAggressive
                    ? 'bg-accent-warning/10 border-accent-warning/30 text-accent-warning'
                    : 'bg-accent-neon/10 border-accent-neon/30 text-accent-neon'
                  : isSuggested
                    ? 'bg-blue-500/[0.06] border-blue-400/30 text-text-muted hover:border-blue-400/50'
                    : 'bg-bg-secondary border-border-primary text-text-muted hover:border-border-hover'
              }`}
            >
              {isSuggested && (
                <span className="absolute -top-1.5 -right-1 text-[7px] font-bold uppercase tracking-wider bg-blue-500/90 text-white px-1.5 py-0.5 rounded-full leading-none">
                  Suggested
                </span>
              )}
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold">{preset.name}</span>
                <span className={`text-[8px] font-mono px-1 rounded ${
                  isActive ? 'bg-current/10' : 'bg-bg-tertiary'
                }`}>
                  {preset.winRate}
                </span>
              </div>
              <span className="text-[8px] opacity-60 mt-0.5">{preset.description}</span>
            </button>
          );
        })}
      </div>

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
              <span className={`ml-auto text-[9px] font-mono ${isAgg ? 'text-accent-warning/70' : 'text-accent-neon/70'}`}>{preset?.winRate}</span>
            </div>
            <div className="px-3 py-2.5 space-y-2.5">
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

        {/* Budget summary */}
        <div className="flex items-center justify-between text-[10px] font-mono mb-3 px-1">
          <div className="flex flex-col gap-0.5">
            <span className="text-text-muted">Total Budget</span>
            <span className="text-text-primary font-bold text-xs">{budget.budgetSol} SOL</span>
          </div>
          <div className="flex flex-col gap-0.5 text-center">
            <span className="text-text-muted">Per Snipe</span>
            <span className="text-text-primary font-bold text-xs">~{perSnipeSol} SOL</span>
          </div>
          <div className="flex flex-col gap-0.5 text-right">
            <span className="text-text-muted">Remaining</span>
            <span className={`font-bold text-xs ${remaining > 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
              {budget.authorized ? `${remaining} SOL` : '—'}
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

      {/* ─── AUTO-EXECUTE (SESSION WALLET) ─── */}
      <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Flame className="w-3.5 h-3.5 text-accent-warning" />
          <span className="text-xs font-semibold">Auto-Execute (Session Wallet)</span>
          <span className={`ml-auto text-[9px] font-mono px-1.5 py-0.5 rounded-full border ${
            usingSession ? 'text-accent-warning bg-accent-warning/10 border-accent-warning/20' : 'text-text-muted bg-bg-tertiary border-border-primary'
          }`}>
            {usingSession ? 'AUTO' : 'MANUAL'}
          </span>
        </div>

        <p className="text-[10px] text-text-muted/70 leading-relaxed mb-3">
          Optional burner wallet that can auto-sign buys and sells (no Phantom popups). This is the only way SL/TP can execute automatically.
          Fund it with a small amount you are willing to lose.
        </p>

        {!sessionWalletPubkey ? (
          <button
            onClick={handleCreateSessionWallet}
            disabled={!connected || sessionBusy}
            className={`w-full py-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
              connected ? 'bg-accent-warning text-black hover:bg-accent-warning/90' : 'bg-bg-tertiary text-text-muted border border-border-primary'
            } ${(!connected || sessionBusy) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            title={!connected ? 'Connect Phantom to create a session wallet' : 'Create a burner wallet for auto execution'}
          >
            {sessionBusy ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Working...</> : 'Create Session Wallet'}
          </button>
        ) : (
          <div className="space-y-3">
            {!sessionKeyOk && (
              <div className="flex items-start gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/20">
                <AlertTriangle className="w-4 h-4 text-accent-error flex-shrink-0 mt-0.5" />
                <div className="flex flex-col gap-1">
                  <span className="text-[11px] font-semibold text-accent-error">Session key missing</span>
                  <span className="text-[9px] text-text-muted/80">
                    This address is saved, but the private key is not in this tab anymore (sessionStorage is cleared when you close the tab).
                    Create a new session wallet to auto-sign trades.
                  </span>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between gap-2 p-2.5 rounded-lg bg-bg-tertiary border border-border-primary">
              <div className="flex flex-col">
                <span className="text-[9px] text-text-muted uppercase tracking-wider">Session Address</span>
                <span className="text-[10px] font-mono text-text-primary break-all">
                  {sessionWalletPubkey}
                </span>
              </div>
              <button
                onClick={async () => {
                  try { await navigator.clipboard.writeText(sessionWalletPubkey); } catch {}
                }}
                className="text-[10px] font-mono px-2 py-1 rounded border bg-bg-secondary text-text-muted border-border-primary hover:border-border-hover"
                title="Copy address"
              >
                Copy
              </button>
            </div>

            <div className="flex items-center justify-between text-[10px] font-mono px-1">
              <span className="text-text-muted">Balance</span>
              <span className={`font-bold ${sessionBalanceSol != null && sessionBalanceSol > 0 ? 'text-accent-warning' : 'text-text-muted'}`}>
                {sessionBalanceSol == null ? '—' : `${sessionBalanceSol.toFixed(4)} SOL`}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                inputMode="decimal"
                placeholder={`Fund (ex: ${budget.budgetSol} SOL)`}
                value={sessionFundSol}
                onChange={(e) => setSessionFundSol(e.target.value)}
                disabled={!connected || sessionBusy}
                className="flex-1 bg-bg-tertiary border border-border-primary rounded-lg px-3 py-2 text-xs font-mono text-text-primary outline-none placeholder:text-text-muted/40 focus:border-accent-warning/40 disabled:opacity-50 transition-all"
              />
              <button
                onClick={handleFundSessionWallet}
                disabled={!connected || sessionBusy}
                className={`px-4 py-2 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                  connected ? 'bg-accent-warning text-black hover:bg-accent-warning/90' : 'bg-bg-tertiary text-text-muted border border-border-primary'
                } ${(!connected || sessionBusy) ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
              >
                {sessionBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Fund'}
              </button>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-lg bg-bg-tertiary border border-border-primary">
              <div className="flex flex-col">
                <span className="text-xs font-semibold">Activate Auto Wallet</span>
                <span className="text-[9px] text-text-muted/70">
                  Set your budget + trade limits, then auto-snipe using the selected strategy.
                </span>
              </div>
              <button
                onClick={openActivate}
                disabled={!sessionReady || sessionBusy}
                className={`px-3 py-2 rounded-lg text-[11px] font-bold transition-all border flex items-center gap-1.5 ${
                  autoWalletActive
                    ? 'bg-accent-warning/15 text-accent-warning border-accent-warning/30 hover:bg-accent-warning/20'
                    : 'bg-accent-warning text-black border-accent-warning/30 hover:bg-accent-warning/90'
                } ${(!sessionReady || sessionBusy) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
                title={!sessionReady ? 'Fund the session wallet first' : autoWalletActive ? 'Adjust plan (budget / limits)' : 'Activate auto trading with session wallet'}
              >
                {autoWalletActive ? <><ShieldCheck className="w-3.5 h-3.5" /> Active</> : <><Flame className="w-3.5 h-3.5" /> Activate</>}
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={handleSweepSessionWallet}
                disabled={sessionBusy}
                className={`py-2 rounded-lg text-[11px] font-semibold transition-all border ${
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
                className={`py-2 rounded-lg text-[11px] font-semibold transition-all border bg-accent-error/[0.06] text-accent-error/80 border-accent-error/20 hover:border-accent-error/40 hover:text-accent-error ${
                  sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                }`}
                title="Deletes the session key from this tab (you cannot recover funds without the key)"
              >
                Delete Session
              </button>
            </div>

            {usingSession && (
              <button
                onClick={() => {
                  // Safety: stop auto-snipe when switching signing back to Phantom.
                  setConfig({ autoSnipe: false });
                  setTradeSignerMode('phantom');
                }}
                disabled={sessionBusy}
                className={`w-full py-2 rounded-lg text-[11px] font-semibold transition-all border bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover ${
                  sessionBusy ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
                }`}
                title="Switch signing back to Phantom (manual). Auto-Snipe will turn off."
              >
                Switch to Phantom
              </button>
            )}

            <p className="text-[9px] text-text-muted/60 leading-relaxed">
              Note: auto-execution still requires this page to stay open. If you close the tab, automation stops.
            </p>
          </div>
        )}
      </div>

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
            <p className="text-[10px] text-text-muted">
                {!budget.authorized
                  ? 'Authorize a budget to enable'
                  : config.autoSnipe
                  ? `${config.strategyMode === 'aggressive' ? 'LET IT RIDE' : 'HYBRID-B v5'}: Liq≥$${Math.round(config.minLiquidityUsd).toLocaleString('en-US')} + V/L≥0.5 + B/S 1-3 + Age<500h + Mom↑ + TOD | ${useRecommendedExits ? 'REC SL/TP' : `${config.stopLossPct}/${config.takeProfitPct}`}+${config.trailingStopPct}t${config.maxPositionAgeHours > 0 ? ` | ${config.maxPositionAgeHours}h expiry` : ''}`
                  : 'Manual mode — click to snipe'}
            </p>
          </div>
        </div>
        <button
          onClick={() => setConfig({ autoSnipe: !config.autoSnipe })}
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
            />
            <ConfigField
              icon={<Target className="w-3.5 h-3.5 text-accent-neon" />}
              label="Take Profit"
              value={config.takeProfitPct}
              suffix="%"
              onChange={(v) => setConfig({ takeProfitPct: v })}
              min={5}
              max={500}
            />
            <ConfigField
              icon={<TrendingUp className="w-3.5 h-3.5 text-accent-warning" />}
              label="Trailing Stop"
              value={config.trailingStopPct}
              suffix="%"
              onChange={(v) => setConfig({ trailingStopPct: v })}
              min={1}
              max={30}
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
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <ConfigField
              label="Min Score"
              value={config.minScore}
              onChange={(v) => setConfig({ minScore: v })}
              min={0}
              max={100}
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
}: {
  icon?: React.ReactNode;
  label: string;
  value: number;
  suffix?: string;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
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
