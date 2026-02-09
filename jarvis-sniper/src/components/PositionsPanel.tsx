'use client';

import { useRef, useState } from 'react';
import { X, DollarSign, Clock, ExternalLink, Shield, Target, BarChart3, RotateCcw, Loader2, TrendingUp } from 'lucide-react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { useSniperStore } from '@/stores/useSniperStore';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { closePositionOnServer, executeSwapFromQuote, getSellQuote } from '@/lib/bags-trading';
import { getOwnerTokenBalanceLamports, minLamportsString } from '@/lib/solana-tokens';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';

export function PositionsPanel() {
  const { positions, setSelectedMint, selectedMint, resetSession, totalPnl, winCount, lossCount, totalTrades } = useSniperStore();
  const config = useSniperStore((s) => s.config);
  const setPositionClosing = useSniperStore((s) => s.setPositionClosing);
  const updatePosition = useSniperStore((s) => s.updatePosition);
  const closePosition = useSniperStore((s) => s.closePosition);
  const addExecution = useSniperStore((s) => s.addExecution);
  const { connected, address, signTransaction } = usePhantomWallet();
  const connectionRef = useRef<Connection | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const openPositions = positions.filter(p => p.status === 'open');
  const closedPositions = positions.filter(p => p.status !== 'open').slice(0, 10);

  const totalOpen = openPositions.reduce((sum, p) => sum + p.solInvested, 0);
  const unrealizedPnl = openPositions.reduce((sum, p) => sum + p.pnlSol, 0);

  function getConnection(): Connection {
    if (!connectionRef.current) {
      connectionRef.current = new Connection(RPC_URL, 'confirmed');
    }
    return connectionRef.current;
  }

  type CloseStatus = 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed';
  async function handleClose(id: string, status: CloseStatus = 'closed') {
    const pos = positions.find(p => p.id === id);
    if (!pos || pos.isClosing) return;

    // Manual close = real sell. Never "close the record" without swapping out.
    if (!connected || !address) {
      addExecution({
        id: `close-${Date.now()}-${id.slice(-4)}`,
        type: 'error',
        symbol: pos.symbol,
        mint: pos.mint,
        amount: pos.solInvested,
        reason: 'Connect wallet to close (sell) this position',
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
      const bal = await getOwnerTokenBalanceLamports(connection, address, pos.mint);
      if (!amountLamports || amountLamports === '0') {
        if (!bal || bal.amountLamports === '0') throw new Error('No token balance found to sell');
        amountLamports = bal.amountLamports;
        updatePosition(id, { amountLamports });
      } else if (bal && bal.amountLamports !== '0') {
        const clamped = minLamportsString(amountLamports, bal.amountLamports);
        if (clamped !== amountLamports) {
          amountLamports = clamped;
          updatePosition(id, { amountLamports });
        }
      }

      const slippageBase = config.slippageBps;
      const quote =
        (await getSellQuote(pos.mint, amountLamports, slippageBase)) ??
        (await getSellQuote(pos.mint, amountLamports, Math.max(slippageBase, 300))) ??
        (await getSellQuote(pos.mint, amountLamports, Math.max(slippageBase, 500)));
      if (!quote) throw new Error('No sell quote found — try higher slippage or liquidity may be pulled');

      // Realizable exit value from the quote (better than chart prices for low-liquidity tokens).
      const exitValueSol = Number(BigInt(quote.outAmount)) / 1e9;
      const realPnlPct = ((exitValueSol - pos.solInvested) / pos.solInvested) * 100;
      const realPnlSol = pos.solInvested * (realPnlPct / 100);

      const result = await executeSwapFromQuote(
        connection,
        address,
        quote,
        signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
        config.useJito,
      );

      if (!result.success) throw new Error(result.error || 'Sell failed');

      // Update final P&L in the store before closing, so stats/logs reflect realizable value.
      updatePosition(id, {
        pnlPercent: realPnlPct,
        pnlSol: realPnlSol,
        highWaterMarkPct: Math.max(pos.highWaterMarkPct ?? 0, realPnlPct),
      });
      closePosition(id, status, result.txHash);
      closePositionOnServer({ mint: pos.mint, status, txHash: result.txHash });
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

  const hasRecord = totalTrades > 0 || positions.length > 0;
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
          {confirmReset ? 'Click again to confirm reset' : `Reset Record (${totalTrades} trades, ${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(3)} SOL)`}
        </button>
      )}

      {/* Open Positions */}
      {openPositions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 gap-2">
          <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center">
            <DollarSign className="w-4 h-4 text-text-muted" />
          </div>
          <p className="text-[11px] text-text-muted">No open positions</p>
        </div>
      ) : (
        <div className="space-y-2 mb-4">
          {openPositions.map((pos) => (
            <PositionRow
              key={pos.id}
              pos={pos}
              isSelected={selectedMint === pos.mint}
              onClose={handleClose}
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
                <span className={`font-mono font-bold ${pos.pnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                  {pos.pnlPercent >= 0 ? '+' : ''}{pos.pnlPercent.toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function PositionRow({ pos, isSelected, onClose, onSelect }: {
  pos: any;
  isSelected: boolean;
  onClose: (id: string, status?: 'tp_hit' | 'sl_hit' | 'trail_stop' | 'expired' | 'closed') => void | Promise<void>;
  onSelect: () => void;
}) {
  const { connected, connecting, connect } = usePhantomWallet();
  const ageMin = Math.floor((Date.now() - pos.entryTime) / 60000);
  const ageLabel = ageMin < 1 ? '<1m' : ageMin < 60 ? `${ageMin}m` : `${(ageMin / 60).toFixed(1)}h`;
  const maxAgeHours = useSniperStore.getState().config.maxPositionAgeHours ?? 4;
  const ageHours = ageMin / 60;
  const nearExpiry = maxAgeHours > 0 && ageHours >= maxAgeHours * 0.75; // warn at 75% of max age
  const ageColor = nearExpiry ? 'text-accent-warning' : 'text-text-muted';

  const cfg = useSniperStore.getState().config;
  const useRecommendedExits = cfg.useRecommendedExits !== false;

  // Exits: either per-position recommended or forced global values.
  const sl = useRecommendedExits ? (pos.recommendedSl ?? cfg.stopLossPct) : cfg.stopLossPct;
  const tp = useRecommendedExits ? (pos.recommendedTp ?? cfg.takeProfitPct) : cfg.takeProfitPct;
  const trailPct = cfg.trailingStopPct;
  const hwm = pos.highWaterMarkPct ?? 0;

  // Trigger proximity detection
  const nearSl = pos.pnlPercent <= -(sl * 0.8);
  const nearTp = pos.pnlPercent >= (tp * 0.8);
  const trailDrop = trailPct > 0 && hwm > 0 ? hwm - pos.pnlPercent : 0;
  const nearTrail = trailPct > 0 && hwm > 0 && trailDrop >= (trailPct * 0.8);
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
                : pos.pnlPercent >= 0
                  ? 'bg-accent-neon/[0.03] border-accent-neon/20 hover:border-accent-neon/30'
                  : 'bg-accent-error/[0.03] border-accent-error/20 hover:border-accent-error/30'
      }`}
    >
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold">{pos.symbol}</span>
          <span className="text-[9px] font-mono text-text-muted bg-bg-tertiary px-1.5 py-0.5 rounded">
            {pos.solInvested.toFixed(2)} SOL
          </span>
          {isSelected && (
            <BarChart3 className="w-3 h-3 text-accent-neon" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className={`text-sm font-mono font-bold ${pos.pnlPercent >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
            {pos.pnlPercent >= 0 ? '+' : ''}{pos.pnlPercent.toFixed(1)}%
          </span>
          {pending && !pos.isClosing && pendingLabel && (
            <span className={`text-[9px] font-mono font-semibold px-2 py-0.5 rounded-full border ${pendingColor}`}>
              {pendingLabel} pending
            </span>
          )}
          {pos.isClosing && (
            <span className="text-[9px] font-mono font-semibold px-2 py-0.5 rounded-full bg-accent-warning/10 text-accent-warning border border-accent-warning/25">
              Signing...
            </span>
          )}
          {pending && !pos.isClosing && pendingLabel && (
            connected ? (
              <button
                onClick={(e) => { e.stopPropagation(); void onClose(pos.id, pending.trigger); }}
                className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border transition-colors ${pendingColor} hover:opacity-90`}
                title={pending.quoteAvailable === false ? 'Quote unavailable — will attempt sell with higher slippage' : 'Opens Phantom to approve the sell'}
              >
                Approve
              </button>
            ) : (
              <button
                onClick={(e) => { e.stopPropagation(); void connect(); }}
                disabled={connecting}
                className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border transition-colors bg-bg-tertiary text-text-muted border-border-primary hover:border-border-hover disabled:opacity-60"
                title="Connect Phantom to approve the sell"
              >
                {connecting ? 'Connecting...' : 'Sign in Phantom'}
              </button>
            )
          )}
          <button
            onClick={(e) => { e.stopPropagation(); void onClose(pos.id, 'closed'); }}
            disabled={pos.isClosing}
            className={`w-6 h-6 rounded-full flex items-center justify-center transition-all ${
              pos.isClosing
                ? 'bg-bg-tertiary text-text-muted cursor-not-allowed'
                : 'bg-accent-error/10 text-accent-error hover:bg-accent-error/20'
            }`}
          >
            {pos.isClosing ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
          </button>
        </div>
      </div>

      {/* Per-position SL/TP + age */}
      <div className="flex items-center gap-2 text-[9px] font-mono text-text-muted">
        <Clock className={`w-3 h-3 ${ageColor}`} />
        <span className={ageColor}>{ageLabel}{nearExpiry ? ' ⏳' : ''}</span>
        <span className="text-text-muted/50">|</span>
        <span className="flex items-center gap-0.5 text-accent-error">
          <Shield className="w-2.5 h-2.5" /> SL -{sl}%
        </span>
        <span className="text-text-muted/50">|</span>
        <span className="flex items-center gap-0.5 text-accent-neon">
          <Target className="w-2.5 h-2.5" /> TP +{tp}%
        </span>
        <span className="text-text-muted/50">|</span>
        <span className="text-[8px] font-mono text-text-muted/70 uppercase tracking-wider">
          {useRecommendedExits ? 'REC' : 'GLOBAL'}
        </span>
        {trailPct > 0 && hwm > 0 && (
          <>
            <span className="text-text-muted/50">|</span>
            <span className="flex items-center gap-0.5 text-accent-warning">
              <TrendingUp className="w-2.5 h-2.5" /> HWM +{hwm.toFixed(1)}%
            </span>
          </>
        )}
        {pos.score != null && (
          <>
            <span className="text-text-muted/50">|</span>
            <span className="text-text-muted">Score {pos.score}</span>
          </>
        )}
        {pos.txHash && (
          <>
            <span className="text-text-muted/50">|</span>
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
