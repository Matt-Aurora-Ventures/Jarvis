'use client';

import { useMemo, useState } from 'react';
import { Crosshair, Zap, Shield, TrendingUp, Wifi, WifiOff, Flame, Sun, Moon, ExternalLink, Download, Package, Rocket, Building2, RotateCcw } from 'lucide-react';
import { downloadSessionReport } from '@/lib/session-export';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const KR8TIV_LINKS = [
  { label: 'Help Beta Test - Join Here', href: 'https://t.me/kr8tivaisystems' },
  { label: 'Jarvis Web', href: 'https://jarvislife.io' },
  { label: 'GitHub', href: 'https://github.com/kr8tivai' },
  { label: '@kr8tivai', href: 'https://x.com/kr8tivai' },
  { label: '@jarvis_lifeos', href: 'https://x.com/jarvis_lifeos' },
  { label: 'Telegram', href: 'https://t.me/kr8tivai' },
];
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { useMacroData } from '@/hooks/useMacroData';
import { useTheme } from '@/hooks/useTheme';
import { clearActiveSessionPointer, listStoredSessionWallets } from '@/lib/session-wallet';
import { filterOpenPositionsForActiveWallet, isPositionInActiveWallet, resolveActiveWallet } from '@/lib/position-scope';
import { isOperatorManagedPositionMeta, isReliableTradeForStats, resolvePositionPnlPercent } from '@/lib/position-reliability';

export function StatusBar() {
  const { connected, connecting, address, walletInstalled, walletKind, connect, disconnect } = usePhantomWallet();
  const { config, positions, totalPnl, winCount, lossCount, totalTrades, tradeSignerMode, sessionWalletPubkey, budget, executionLog, circuitBreaker, activePreset, assetFilter, lastSolPriceUsd, autoResetRequired } = useSniperStore();
  const activeWallet = resolveActiveWallet(tradeSignerMode, sessionWalletPubkey, address);
  const openPositions = filterOpenPositionsForActiveWallet(positions, activeWallet).filter(
    (p) => isOperatorManagedPositionMeta(p),
  );
  const closedScoped = positions.filter(
    (p) =>
      p.status !== 'open' &&
      isPositionInActiveWallet(p, activeWallet) &&
      isReliableTradeForStats(p),
  );
  const closedWins = closedScoped.filter((p) => {
    if (p.status === 'tp_hit') return true;
    if (p.status === 'sl_hit') return false;
    return resolvePositionPnlPercent(p) >= 0;
  }).length;
  const closedLosses = Math.max(0, closedScoped.length - closedWins);
  const realizedScopedPnl = closedScoped.reduce((sum, p) => {
    if (typeof p.realPnlSol === 'number') return sum + p.realPnlSol;
    return sum + (typeof p.pnlSol === 'number' ? p.pnlSol : 0);
  }, 0);
  const openCount = openPositions.length;
  const unrealizedPnl = openPositions.reduce((sum, p) => sum + p.pnlSol, 0);
  const combinedPnl = realizedScopedPnl + unrealizedPnl;
  const openWins = openPositions.filter((p) => resolvePositionPnlPercent(p) > 0).length;
  const openLosses = openPositions.filter((p) => resolvePositionPnlPercent(p) <= 0).length;
  const allTrades = closedScoped.length + openCount;
  const allWins = closedWins + openWins;
  const allLosses = closedLosses + openLosses;
  const winRate = allTrades > 0 ? ((allWins / allTrades) * 100).toFixed(1) : '--';
  const anyExitPending = openPositions.some((p) => !!p.isClosing || !!p.exitPending);

  const macro = useMacroData();
  const { theme, toggle: toggleTheme } = useTheme();
  const pathname = usePathname();

  const [parseOpen, setParseOpen] = useState(false);
  const [wipeWalletBackups, setWipeWalletBackups] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [resetAutoOpen, setResetAutoOpen] = useState(false);
  const [resettingAuto, setResettingAuto] = useState(false);

  const storedSessionWalletCount = useMemo(() => {
    try {
      return listStoredSessionWallets().length;
    } catch {
      return 0;
    }
  }, [parseOpen]);

  const shortAddr = address ? `${address.slice(0, 4)}...${address.slice(-4)}` : null;
  const shortSession = sessionWalletPubkey ? `${sessionWalletPubkey.slice(0, 4)}...${sessionWalletPubkey.slice(-4)}` : null;
  const autoActive = tradeSignerMode === 'session' && !!sessionWalletPubkey && budget.authorized;
  const riskEngineOn = connected || autoActive;

  const parseData = async () => {
    if (parsing) return;

    setParsing(true);
    try {
      // Best-effort: disconnect Phantom session so UI reflects a fresh wallet state.
      try { await disconnect(); } catch {}

      // Reset in-memory store state.
      try { useSniperStore.getState().resetSession(); } catch {}

      // Clear persisted Zustand state (config, stats, logs, etc.).
      try { (useSniperStore as any).persist?.clearStorage?.(); } catch {}

      // Preserve purely cosmetic prefs so the UI doesn't feel "broken" after reset.
      const preserveKeys = new Set([
        'jarvis-sniper-theme',
        'jarvis-sniper:early-beta-ack:v2',
      ]);
      const preserved: Record<string, string> = {};
      try {
        for (const k of preserveKeys) {
          const v = localStorage.getItem(k);
          if (v != null) preserved[k] = v;
        }
      } catch {
        // ignore
      }

      // Remove Jarvis Sniper-owned localStorage keys (best-effort, safe defaults).
      try {
        const keys: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (!k) continue;
          if (preserveKeys.has(k)) continue;

          const isSessionWalletBackup = k === '__jarvis_wallet_persistent' || k.startsWith('__jarvis_session_wallet_by_pubkey:');
          if (!wipeWalletBackups && isSessionWalletBackup) continue;

          const owned =
            k === 'jarvis-sniper-store' ||
            k === 'jarvis_backtest_results' ||
            k === 'sniper-data-cleared-v' ||
            k.startsWith('jarvis_ohlcv_') ||
            k.startsWith('jarvis-sniper:') ||
            // Wallet-adapter persistence keys (force a truly fresh wallet connect flow)
            k === 'walletName' ||
            k.startsWith('wallet-adapter') ||
            k.startsWith('solana-wallet-adapter') ||
            k === '__jarvis_wallet_persistent' ||
            k.startsWith('__jarvis_session_wallet') ||
            k.startsWith('__jarvis_session_wallet_by_pubkey:');

          if (owned) keys.push(k);
        }
        for (const k of keys) {
          try { localStorage.removeItem(k); } catch {}
        }
      } catch {
        // ignore
      }

      // Session storage: always clear the active session-wallet pointer (auto trading off).
      try { sessionStorage.removeItem('__jarvis_session_wallet'); } catch {}
      if (wipeWalletBackups) {
        try {
          const keys: string[] = [];
          for (let i = 0; i < sessionStorage.length; i++) {
            const k = sessionStorage.key(i);
            if (!k) continue;
            if (k.startsWith('__jarvis_session_wallet_by_pubkey:')) keys.push(k);
          }
          for (const k of keys) {
            try { sessionStorage.removeItem(k); } catch {}
          }
        } catch {
          // ignore
        }
      }

      // Restore preserved cosmetic prefs.
      try {
        for (const [k, v] of Object.entries(preserved)) {
          try { localStorage.setItem(k, v); } catch {}
        }
      } catch {
        // ignore
      }

      // Best-effort cache + service worker wipe (mainly useful in PWA/service-worker setups).
      // Kept "best-effort" to avoid breaking reload if a browser blocks any of these APIs.
      if (typeof caches !== 'undefined') {
        try {
          const cks = await caches.keys();
          await Promise.allSettled(cks.map((k) => caches.delete(k)));
        } catch {
          // ignore
        }
      }
      try {
        if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
          const regs = await navigator.serviceWorker.getRegistrations();
          await Promise.allSettled(regs.map((r) => r.unregister()));
        }
      } catch {
        // ignore
      }

      // Deep wipe: IndexedDB is occasionally used by wallet extensions/adapters. Only do this
      // when the user explicitly enables the "wipe backups" danger toggle.
      if (wipeWalletBackups && typeof indexedDB !== 'undefined') {
        try {
          const dbs: Array<{ name?: string | null }> =
            typeof (indexedDB as any).databases === 'function'
              ? await (indexedDB as any).databases()
              : [];
          await Promise.allSettled(
            (dbs || [])
              .map((d) => (d?.name ? String(d.name) : ''))
              .filter(Boolean)
              .map((name) => new Promise<void>((resolve) => {
                try {
                  const req = indexedDB.deleteDatabase(name);
                  req.onsuccess = () => resolve();
                  req.onerror = () => resolve();
                  req.onblocked = () => resolve();
                } catch {
                  resolve();
                }
              })),
          );
        } catch {
          // ignore
        }
      }

      // Skip Phantom eager reconnect on the next page load so the user gets a truly "fresh" connect flow.
      try { sessionStorage.setItem('jarvis-sniper:skip-eager-connect', '1'); } catch {}

      // Hard refresh to guarantee a clean runtime.
      window.location.assign(`${window.location.pathname}?fresh=${Date.now()}`);
    } finally {
      setParsing(false);
    }
  };

  const handleResetAuto = async () => {
    if (resettingAuto) return;
    setResettingAuto(true);
    try {
      try {
        clearActiveSessionPointer();
      } catch {
        // ignore
      }
      try {
        useSniperStore.getState().resetAutoForRecovery();
      } catch {
        // ignore
      }
      setResetAutoOpen(false);
    } finally {
      setResettingAuto(false);
    }
  };

  return (
    <header className="sticky top-0 z-50 border-b border-border-primary bg-bg-secondary/80 backdrop-blur-xl">
      {/* KR8TIV Links Top Bar */}
      <div className="hidden sm:flex items-center justify-center gap-3 px-4 py-1.5 bg-bg-tertiary/40 border-b border-border-primary/30">
        <button
          type="button"
          onClick={async () => {
            await downloadSessionReport({
              config, positions, executionLog, totalPnl, winCount, lossCount,
              totalTrades, budget, circuitBreaker, activePreset, assetFilter,
              tradeSignerMode, sessionWalletPubkey, lastSolPriceUsd,
            });
          }}
          className="flex items-center gap-1 text-[9px] font-mono font-semibold uppercase tracking-wider text-text-muted hover:text-accent-neon transition-colors cursor-pointer"
          title="Download session trading report (.md)"
        >
          <Download className="w-2.5 h-2.5" />
          Session Report
        </button>
        <span className="text-border-primary/50 select-none">|</span>
        {KR8TIV_LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[9px] font-mono font-semibold uppercase tracking-wider text-text-muted hover:text-accent-neon transition-colors"
          >
            {link.label}
            <ExternalLink className="w-2.5 h-2.5" />
          </a>
        ))}
      </div>

      <div className="app-shell py-3 flex items-center justify-between gap-4">
        {/* Left: Branding */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Crosshair className="w-5 h-5 text-accent-neon" />
            <h1 className="font-display text-lg font-bold tracking-tight text-text-primary">
              JARVIS <span className="text-accent-neon">SNIPER</span>
            </h1>
          </div>
          {config.autoSnipe ? (
            <span className="flex items-center gap-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full bg-accent-neon/15 text-accent-neon border border-accent-neon/30">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-neon sniper-dot" />
              AUTO
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full bg-bg-tertiary text-text-muted border border-border-primary">
              MANUAL
            </span>
          )}
          {macro.regime && (
            <span className={`flex items-center gap-1.5 text-[10px] font-mono font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full border ${
              macro.regime === 'risk_on' ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/20' :
              macro.regime === 'risk_off' ? 'bg-accent-error/10 text-accent-error border-accent-error/20' :
              'bg-bg-tertiary text-text-muted border-border-primary'
            }`}>
              {macro.regime === 'risk_on' ? '\u2191 RISK ON' : macro.regime === 'risk_off' ? '\u2193 RISK OFF' : '\u2014 NEUTRAL'}
            </span>
          )}
        </div>

        {/* Center: Stats */}
        <div className="hidden md:flex items-center gap-6">
          {macro.btcPrice != null && (
            <StatChip
              icon={<span className="text-[10px] font-bold">BTC</span>}
              label="BTC"
              value={`$${macro.btcPrice.toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
              color={(macro.btcChange24h ?? 0) >= 0 ? 'text-accent-neon' : 'text-accent-error'}
            />
          )}
          {macro.solPrice != null && (
            <StatChip
              icon={<span className="text-[10px] font-bold">SOL</span>}
              label="SOL"
              value={`$${macro.solPrice.toFixed(2)}`}
              color={(macro.solChange24h ?? 0) >= 0 ? 'text-accent-neon' : 'text-accent-error'}
            />
          )}
          {(macro.btcPrice != null || macro.solPrice != null) && (
            <span className="text-border-primary select-none">|</span>
          )}
          <StatChip
            icon={<TrendingUp className="w-3.5 h-3.5" />}
            label="PnL"
            value={`${combinedPnl >= 0 ? '+' : ''}${combinedPnl.toFixed(2)} SOL`}
            color={combinedPnl >= 0 ? 'text-accent-neon' : 'text-accent-error'}
          />
          <StatChip
            icon={<Zap className="w-3.5 h-3.5" />}
            label="Win Rate"
            value={`${winRate}%`}
            color="text-text-primary"
          />
          <StatChip
            icon={<Shield className="w-3.5 h-3.5" />}
            label="W/L"
            value={`${allWins}/${allLosses}`}
            color="text-text-secondary"
          />
          <StatChip
            icon={openCount > 0 ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            label="Positions"
            value={`${openCount}/${config.maxConcurrentPositions}`}
            color="text-text-secondary"
          />
          <StatChip
            icon={<Shield className="w-3.5 h-3.5" />}
            label="Risk"
            value={openCount === 0 ? '--' : anyExitPending ? 'SIGN' : riskEngineOn ? 'ON' : 'OFF'}
            color={openCount === 0 ? 'text-text-muted' : anyExitPending ? 'text-accent-warning' : riskEngineOn ? 'text-accent-neon' : 'text-accent-error'}
          />
        </div>

        {/* Right: Theme + Wallet */}
        <div className="flex items-center gap-3">
          {/* Theme toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            className="flex items-center justify-center w-9 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-border-hover transition-colors cursor-pointer"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-text-secondary" />
            ) : (
              <Moon className="w-4 h-4 text-text-secondary" />
            )}
          </button>
          <button
            type="button"
            onClick={() => setResetAutoOpen(true)}
            className={`flex items-center justify-center gap-2 h-9 px-3 rounded-full border transition-colors cursor-pointer ${
              autoResetRequired
                ? 'bg-accent-warning/12 text-accent-warning border-accent-warning/35 hover:border-accent-warning/50'
                : 'bg-bg-tertiary text-text-secondary border-border-primary hover:border-accent-warning/35'
            }`}
            title="Reset Auto: debug recovery reset (turns off auto + session mode)"
            aria-label="Reset Auto"
          >
            <RotateCcw className="w-4 h-4" />
            <span className="text-[10px] font-mono font-semibold uppercase tracking-wider">
              Reset Auto
            </span>
          </button>
          {/* Parse Data (local reset) */}
          <button
            type="button"
            onClick={() => setParseOpen(true)}
            className="flex items-center justify-center gap-2 w-9 h-9 sm:w-auto sm:px-3 rounded-full bg-bg-tertiary border border-border-primary hover:border-accent-neon/40 transition-colors cursor-pointer"
            title="Parse Data: clears local Jarvis Sniper data (wallet + session) and reloads"
            aria-label="Open parse data dialog"
          >
            <Package className="w-4 h-4 text-text-secondary" />
            <span className="hidden sm:inline text-[10px] font-mono font-semibold uppercase tracking-wider text-text-secondary">
              Parse Data
            </span>
          </button>
          {sessionWalletPubkey && (
            <button
              type="button"
              onClick={async () => {
                // Make session wallet activation discoverable:
                // - If auto wallet isn't active yet, jump to the Activate modal in SniperControls.
                // - If active, clicking copies the session wallet address (useful for funding/verification).
                if (!autoActive) {
                  try {
                    window.dispatchEvent(new CustomEvent('jarvis-sniper:open-activate'));
                  } catch {
                    // ignore
                  }
                  return;
                }

                try { await navigator.clipboard.writeText(sessionWalletPubkey); } catch {}
              }}
              className={`flex items-center gap-2 px-2.5 sm:px-3 h-9 rounded-full border transition-colors cursor-pointer ${
                autoActive
                  ? 'bg-accent-warning/10 text-accent-warning border-accent-warning/25 hover:border-accent-warning/40'
                  : 'bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover'
              }`}
              title={autoActive ? 'Auto Wallet ACTIVE (click to copy address)' : 'Session wallet ready (click to activate auto trading)'}
            >
              <Flame className="w-4 h-4" />
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider">
                <span className="hidden sm:inline">{autoActive ? 'AUTO' : 'ACTIVATE'}</span>
                <span className="sm:hidden">{autoActive ? 'AUTO' : 'ACT'}</span>
              </span>
              {shortSession && (
                <span className="hidden md:inline text-xs font-mono font-medium">{shortSession}</span>
              )}
            </button>
          )}
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-accent-neon' : 'bg-accent-error'}`} />
          {connected ? (
            <button
              type="button"
              onClick={disconnect}
              className="flex items-center gap-2 px-4 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-accent-neon/40 transition-colors cursor-pointer"
            >
              <PhantomIcon />
              <span className="text-xs font-mono font-medium text-text-primary">{shortAddr}</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={connect}
              disabled={connecting}
              className="flex items-center gap-2 px-4 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-accent-neon/40 transition-colors cursor-pointer disabled:opacity-50"
            >
              {walletInstalled ? (
                <>
                  <PhantomIcon />
                  <span className="text-xs font-mono font-medium text-text-secondary">
                    {connecting
                      ? 'Connecting...'
                      : walletKind === 'phantom'
                        ? 'Connect Phantom'
                        : walletKind === 'solflare'
                          ? 'Connect Solflare'
                          : 'Connect Wallet'}
                  </span>
                </>
              ) : (
                <span className="text-xs font-mono font-medium text-accent-warning">
                  Install Wallet
                </span>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Parse Data Modal */}
      {parseOpen && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-pointer"
            onClick={() => !parsing && setParseOpen(false)}
            aria-label="Close parse data dialog"
          />

          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="parse-data-title"
            className="relative w-full max-w-[560px] card-glass p-5 border border-border-primary shadow-xl"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 w-9 h-9 rounded-full bg-accent-neon/10 border border-accent-neon/25 flex items-center justify-center">
                <Package className="w-4.5 h-4.5 text-accent-neon" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between gap-3">
                  <h2 id="parse-data-title" className="font-display text-base font-semibold">
                    Parse Data (reset this browser instance)
                  </h2>
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-bg-tertiary text-text-muted border border-border-primary">
                    local
                  </span>
                </div>

                <p className="mt-2 text-[12px] text-text-secondary leading-relaxed">
                  This clears local Jarvis Sniper state in this browser, disconnects Phantom, and reloads the app.
                  Use it when the wallet UI gets stuck or you want a fresh session.
                </p>

                <div className="mt-4 rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-[11px] font-semibold text-text-primary">
                      Session Wallet backups
                    </div>
                    <div className="text-[10px] font-mono text-text-muted">
                      found: {storedSessionWalletCount}
                    </div>
                  </div>
                  <label className="mt-2 flex items-center justify-between gap-3 cursor-pointer select-none">
                    <div className="flex flex-col">
                      <span className="text-[10px] text-text-secondary font-mono font-semibold uppercase tracking-wider">
                        Also wipe backups (danger)
                      </span>
                      <span className="text-[10px] text-text-muted leading-relaxed">
                        If a session wallet holds funds, wiping backups may strand them. Only do this if you know it&apos;s empty.
                      </span>
                    </div>
                    <input
                      type="checkbox"
                      checked={wipeWalletBackups}
                      onChange={(e) => setWipeWalletBackups(e.target.checked)}
                      disabled={parsing}
                      className="accent-accent-error w-4 h-4"
                    />
                  </label>
                </div>

                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                  <button
                    type="button"
                    onClick={() => setParseOpen(false)}
                    disabled={parsing}
                    className="btn-secondary w-full sm:w-auto text-center flex-1 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={async () => {
                      if (wipeWalletBackups && storedSessionWalletCount > 0) {
                        const ok = window.confirm(
                          `Full wipe is enabled and ${storedSessionWalletCount} session-wallet backup(s) exist.\\n\\nIf any of those wallets hold funds, wiping can strand them.\\n\\nContinue?`,
                        );
                        if (!ok) return;
                      }
                      await parseData();
                    }}
                    disabled={parsing}
                    className="btn-neon w-full sm:w-auto flex-1 disabled:opacity-50"
                  >
                    {parsing ? 'Parsing...' : 'Parse & Reload'}
                  </button>
                </div>

                <p className="mt-3 text-[9px] text-text-muted font-mono">
                  Tip: If no wallet is detected, install Phantom or Solflare (Chrome/Brave/Edge), then reload.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reset Auto Modal */}
      {resetAutoOpen && (
        <div className="fixed inset-0 z-[999] flex items-start justify-center p-4 pt-16 sm:pt-20">
          <button
            type="button"
            className="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-pointer"
            onClick={() => !resettingAuto && setResetAutoOpen(false)}
            aria-label="Close reset auto dialog"
          />

          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="reset-auto-title"
            className="relative w-full max-w-[540px] card-glass p-5 border border-border-primary shadow-xl"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 w-9 h-9 rounded-full bg-accent-warning/10 border border-accent-warning/25 flex items-center justify-center">
                <RotateCcw className="w-4.5 h-4.5 text-accent-warning" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between gap-3">
                  <h2 id="reset-auto-title" className="font-display text-base font-semibold">
                    Reset Auto (debug recovery)
                  </h2>
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-bg-tertiary text-text-muted border border-border-primary">
                    temp
                  </span>
                </div>

                <p className="mt-2 text-[12px] text-text-secondary leading-relaxed">
                  Debug reset only. This turns off auto + session mode and requires fresh budget/max settings before re-enabling auto.
                </p>
                <p className="mt-2 text-[12px] text-text-muted leading-relaxed">
                  Open positions stay open. This does not wipe wallet backups.
                </p>

                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                  <button
                    type="button"
                    onClick={() => setResetAutoOpen(false)}
                    disabled={resettingAuto}
                    className="btn-secondary w-full sm:w-auto text-center flex-1 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleResetAuto}
                    disabled={resettingAuto}
                    className="w-full sm:w-auto flex-1 px-4 py-2.5 rounded-lg text-xs font-semibold border border-accent-warning/40 bg-accent-warning/15 text-accent-warning hover:bg-accent-warning/20 transition-colors disabled:opacity-50"
                  >
                    {resettingAuto ? 'Resetting...' : 'Reset Auto'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Desktop navigation — dedicated row */}
      <nav className="hidden lg:flex items-center justify-center gap-2 px-4 py-1.5 border-t border-border-primary/40 bg-bg-tertiary/30">
        <Link href="/" className={`px-3.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/' ? 'bg-accent-neon/15 text-accent-neon' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
        }`}>
          <span className="flex items-center gap-1.5"><Crosshair className="w-3 h-3" />Sniper</span>
        </Link>
        <Link href="/bags-sniper" className={`px-3.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/bags-sniper' ? 'bg-purple-500/15 text-purple-400' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
        }`}>
          <span className="flex items-center gap-1.5"><Package className="w-3 h-3" />Bags Sniper</span>
        </Link>
        <Link href="/tradfi-sniper" className={`px-3.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/tradfi-sniper' ? 'bg-blue-500/15 text-blue-400' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
        }`}>
          <span className="flex items-center gap-1.5"><Building2 className="w-3 h-3" />TradFi Sniper</span>
        </Link>
        <Link href="/bags-intel" className={`px-3.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/bags-intel' ? 'bg-purple-500/15 text-purple-400' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
        }`}>
          <span className="flex items-center gap-1.5"><Package className="w-3 h-3" />Bags Intel</span>
        </Link>
        <Link href="/bags-graduations" className={`px-3.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/bags-graduations' ? 'bg-amber-500/15 text-amber-400' : 'text-text-muted hover:text-text-primary hover:bg-bg-tertiary'
        }`}>
          <span className="flex items-center gap-1.5"><Rocket className="w-3 h-3" />DeGen Launches</span>
        </Link>
      </nav>

      {/* Mobile stats strip — visible only on small screens */}
      {(allTrades > 0) && (
        <div className="md:hidden flex items-center justify-between px-4 py-1.5 border-t border-border-primary/50 text-[10px] font-mono">
          <span className={combinedPnl >= 0 ? 'text-accent-neon font-bold' : 'text-accent-error font-bold'}>
            PnL: {combinedPnl >= 0 ? '+' : ''}{combinedPnl.toFixed(3)} SOL
          </span>
          <span className="text-text-muted">
            W/L: <span className="text-accent-neon">{allWins}</span>/<span className="text-accent-error">{allLosses}</span>
          </span>
          <span className="text-text-muted">
            {openCount}/{config.maxConcurrentPositions} open
          </span>
          {anyExitPending && (
            <span className="text-accent-warning font-bold animate-pulse">SIGN</span>
          )}
        </div>
      )}

      {/* Mobile navigation — visible only on small screens */}
      <nav className="lg:hidden flex items-center justify-center gap-1 px-4 py-1.5 border-t border-border-primary/50">
        <Link href="/" className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/' ? 'bg-accent-neon/15 text-accent-neon' : 'text-text-muted'
        }`}>
          <Crosshair className="w-3 h-3" />Sniper
        </Link>
        <Link href="/bags-sniper" className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/bags-sniper' ? 'bg-purple-500/15 text-purple-400' : 'text-text-muted'
        }`}>
          <Package className="w-3 h-3" />Bags
        </Link>
        <Link href="/tradfi-sniper" className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/tradfi-sniper' ? 'bg-blue-500/15 text-blue-400' : 'text-text-muted'
        }`}>
          <Building2 className="w-3 h-3" />TradFi
        </Link>
        <Link href="/bags-intel" className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/bags-intel' ? 'bg-purple-500/15 text-purple-400' : 'text-text-muted'
        }`}>
          <Package className="w-3 h-3" />Intel
        </Link>
        <Link href="/bags-graduations" className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md text-[10px] font-mono font-semibold uppercase tracking-wider transition-colors ${
          pathname === '/bags-graduations' ? 'bg-amber-500/15 text-amber-400' : 'text-text-muted'
        }`}>
          <Rocket className="w-3 h-3" />Launches
        </Link>
      </nav>
    </header>
  );
}

function PhantomIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 128 128" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="64" cy="64" r="64" fill="#AB9FF2"/>
      <path d="M110.584 64.914H99.142C99.142 41.097 79.859 21.814 56.042 21.814C32.603 21.814 13.55 40.467 13.014 63.744C12.467 87.488 32.188 108.186 55.937 108.186H60.089C81.58 108.186 110.584 88.04 110.584 64.914Z" fill="url(#phantom_gradient)"/>
      <circle cx="45.5" cy="57.5" r="6.5" fill="white"/>
      <circle cx="72.5" cy="57.5" r="6.5" fill="white"/>
      <defs>
        <linearGradient id="phantom_gradient" x1="62" y1="22" x2="62" y2="108" gradientUnits="userSpaceOnUse">
          <stop stopColor="#534BB1"/>
          <stop offset="1" stopColor="#551BF9"/>
        </linearGradient>
      </defs>
    </svg>
  );
}

function StatChip({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-text-muted">{icon}</span>
      <div className="flex flex-col">
        <span className="text-[9px] uppercase tracking-wider text-text-muted font-medium">{label}</span>
        <span className={`text-xs font-mono font-bold ${color}`}>{value}</span>
      </div>
    </div>
  );
}
