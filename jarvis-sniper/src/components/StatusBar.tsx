'use client';

import { Crosshair, Zap, Shield, TrendingUp, Wifi, WifiOff } from 'lucide-react';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';

export function StatusBar() {
  const { connected, connecting, address, phantomInstalled, connect, disconnect } = usePhantomWallet();
  const { config, totalPnl, winCount, lossCount, totalTrades, positions } = useSniperStore();
  const winRate = totalTrades > 0 ? ((winCount / totalTrades) * 100).toFixed(1) : '--';

  const shortAddr = address ? `${address.slice(0, 4)}...${address.slice(-4)}` : null;

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
        </div>

        {/* Center: Stats */}
        <div className="hidden md:flex items-center gap-6">
          <StatChip
            icon={<TrendingUp className="w-3.5 h-3.5" />}
            label="PnL"
            value={`${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)} SOL`}
            color={totalPnl >= 0 ? 'text-accent-neon' : 'text-accent-error'}
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
            value={`${winCount}/${lossCount}`}
            color="text-text-secondary"
          />
          <StatChip
            icon={positions.length > 0 ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            label="Positions"
            value={`${positions.filter(p => p.status === 'open').length}/${config.maxConcurrentPositions}`}
            color="text-text-secondary"
          />
        </div>

        {/* Right: Wallet */}
        <div className="flex items-center gap-3">
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
