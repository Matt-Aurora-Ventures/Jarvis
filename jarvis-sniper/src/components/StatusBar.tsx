'use client';

import { Crosshair, Zap, Shield, TrendingUp, Wifi, WifiOff, Flame, Sun, Moon } from 'lucide-react';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { useMacroData } from '@/hooks/useMacroData';
import { useTheme } from '@/hooks/useTheme';

export function StatusBar() {
  const { connected, connecting, address, phantomInstalled, connect, disconnect } = usePhantomWallet();
  const { config, totalPnl, winCount, lossCount, totalTrades, positions, tradeSignerMode, sessionWalletPubkey, budget } = useSniperStore();
  const openPositions = positions.filter((p) => p.status === 'open');
  const openCount = openPositions.length;
  const unrealizedPnl = openPositions.reduce((sum, p) => sum + p.pnlSol, 0);
  const combinedPnl = totalPnl + unrealizedPnl;
  const openWins = openPositions.filter(p => p.pnlPercent > 0).length;
  const openLosses = openPositions.filter(p => p.pnlPercent <= 0).length;
  const allTrades = totalTrades + openCount;
  const allWins = winCount + openWins;
  const winRate = allTrades > 0 ? ((allWins / allTrades) * 100).toFixed(1) : '--';
  const anyExitPending = positions.some((p) => p.status === 'open' && (!!p.isClosing || !!p.exitPending));

  const macro = useMacroData();
  const { theme, toggle: toggleTheme } = useTheme();

  const shortAddr = address ? `${address.slice(0, 4)}...${address.slice(-4)}` : null;
  const shortSession = sessionWalletPubkey ? `${sessionWalletPubkey.slice(0, 4)}...${sessionWalletPubkey.slice(-4)}` : null;
  const autoActive = tradeSignerMode === 'session' && !!sessionWalletPubkey && budget.authorized;
  const riskEngineOn = connected || autoActive;

  return (
    <header className="sticky top-0 z-50 border-b border-border-primary bg-bg-secondary/80 backdrop-blur-xl">
      <div className="max-w-[1920px] mx-auto px-4 py-3 flex items-center justify-between gap-4">
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
            value={`${allWins}/${lossCount + openLosses}`}
            color="text-text-secondary"
          />
          <StatChip
            icon={positions.length > 0 ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
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
            onClick={toggleTheme}
            className="flex items-center justify-center w-9 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-border-hover transition-colors cursor-pointer"
            title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-text-secondary" />
            ) : (
              <Moon className="w-4 h-4 text-text-secondary" />
            )}
          </button>
          {sessionWalletPubkey && (
            <button
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
              onClick={disconnect}
              className="flex items-center gap-2 px-4 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-accent-neon/40 transition-colors cursor-pointer"
            >
              <PhantomIcon />
              <span className="text-xs font-mono font-medium text-text-primary">{shortAddr}</span>
            </button>
          ) : (
            <button
              onClick={connect}
              disabled={connecting}
              className="flex items-center gap-2 px-4 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-accent-neon/40 transition-colors cursor-pointer disabled:opacity-50"
            >
              {phantomInstalled ? (
                <>
                  <PhantomIcon />
                  <span className="text-xs font-mono font-medium text-text-secondary">
                    {connecting ? 'Connecting...' : 'Connect Phantom'}
                  </span>
                </>
              ) : (
                <span className="text-xs font-mono font-medium text-accent-warning">
                  Get Phantom
                </span>
              )}
            </button>
          )}
        </div>
      </div>
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
