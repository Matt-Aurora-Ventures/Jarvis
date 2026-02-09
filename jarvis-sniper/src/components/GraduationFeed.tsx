'use client';

import { useEffect, useRef, useState } from 'react';
import { Sparkles, Clock, Droplets, BarChart3, ExternalLink, Crosshair, Shield, Target, Check, Ban, Copy } from 'lucide-react';
import { useSniperStore, type StrategyMode } from '@/stores/useSniperStore';
import { getScoreTier, TIER_CONFIG, type BagsGraduation } from '@/lib/bags-api';
import { getRecommendedSlTp, getConvictionMultiplier } from '@/stores/useSniperStore';
import { useSnipeExecutor } from '@/hooks/useSnipeExecutor';
import { computeTargetsFromEntryUsd, formatUsdPrice, isBlueChipLongConviction } from '@/lib/trade-plan';

async function fetchFromApi(): Promise<BagsGraduation[]> {
  try {
    const res = await fetch('/api/graduations');
    if (!res.ok) return [];
    const data = await res.json();
    return data.graduations || [];
  } catch {
    return [];
  }
}

export function GraduationFeed() {
  const { graduations, setGraduations, addGraduation, config, snipedMints, positions, setSelectedMint, budget, budgetRemaining } = useSniperStore();
  const { snipe, ready: walletReady } = useSnipeExecutor();
  const prevMintsRef = useRef<Set<string>>(new Set());
  const newMintsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    fetchFromApi().then((grads) => {
      if (grads.length > 0) {
        setGraduations(grads);
        prevMintsRef.current = new Set(grads.map(g => g.mint));
      }
    });

    const interval = setInterval(async () => {
      const grads = await fetchFromApi();
      if (grads.length > 0) {
        const newOnes = grads.filter(g => !prevMintsRef.current.has(g.mint));
        newOnes.forEach(g => {
          addGraduation(g);
          newMintsRef.current.add(g.mint);
          setTimeout(() => newMintsRef.current.delete(g.mint), 30000);
        });
        prevMintsRef.current = new Set(grads.map(g => g.mint));
        if (newOnes.length === 0) {
          setGraduations(grads);
        }
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [setGraduations, addGraduation]);

  // Auto-snipe: when enabled AND budget authorized AND wallet connected, auto-snipe qualifying tokens
  useEffect(() => {
    if (!config.autoSnipe) return;
    if (!budget.authorized) return;
    if (!walletReady) return;

    const remaining = budgetRemaining();
    if (remaining < 0.001) return;

    const openCount = positions.filter(p => p.status === 'open').length;
    if (openCount >= config.maxConcurrentPositions) return;

    for (const grad of graduations) {
      const hybrid = computeHybridB(grad, config.minLiquidityUsd);
      if (grad.score >= config.minScore && hybrid.passesAll && !snipedMints.has(grad.mint)) {
        const currentOpen = positions.filter(p => p.status === 'open').length;
        if (currentOpen >= config.maxConcurrentPositions) break;
        snipe(grad as any);
      }
    }
  }, [graduations, config.autoSnipe, config.minScore, config.maxConcurrentPositions, positions, snipedMints, snipe, budget.authorized, budgetRemaining, walletReady]);

  return (
    <div className="card-glass p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Token Scanner</h2>
        </div>
        <span className="text-[10px] font-mono text-text-muted">
          {graduations.length} targets
        </span>
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar space-y-2 max-h-[calc(100vh-260px)]">
        {graduations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-text-muted animate-pulse" />
            </div>
            <p className="text-xs text-text-muted">Scanning for targets...</p>
            <div className="skeleton w-48 h-2" />
          </div>
        ) : (
          graduations.map((grad) => {
            const hybrid = computeHybridB(grad, config.minLiquidityUsd);
            const meetsAll = grad.score >= config.minScore && hybrid.passesAll;
            return (
              <TokenCard
                key={grad.mint}
                grad={grad}
                isNew={newMintsRef.current.has(grad.mint)}
                meetsThreshold={meetsAll}
                rejectReason={meetsAll ? null : (hybrid.rejectReason || (grad.score < config.minScore ? `Score ${grad.score.toFixed(0)} < ${config.minScore}` : null))}
                isSniped={snipedMints.has(grad.mint)}
                onSnipe={() => snipe(grad as any)}
                onChart={() => setSelectedMint(grad.mint)}
                budgetAuthorized={budget.authorized}
                walletReady={walletReady}
                minLiquidityUsd={config.minLiquidityUsd}
                strategyMode={config.strategyMode}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

function CopyableAddress({ mint }: { mint: string }) {
  const [copied, setCopied] = useState(false);
  const truncated = `${mint.slice(0, 4)}...${mint.slice(-4)}`;

  async function handleCopy(e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(mint);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Fallback for non-HTTPS or blocked clipboard
    }
  }

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1 text-[9px] font-mono text-text-muted/60 hover:text-text-muted transition-colors mb-1.5 group/addr"
      title={mint}
    >
      {copied ? (
        <Check className="w-2.5 h-2.5 text-accent-neon" />
      ) : (
        <Copy className="w-2.5 h-2.5 opacity-40 group-hover/addr:opacity-100 transition-opacity" />
      )}
      <span className={copied ? 'text-accent-neon' : ''}>{copied ? 'Copied!' : truncated}</span>
    </button>
  );
}

function TokenCard({ grad, isNew, meetsThreshold, rejectReason, isSniped, onSnipe, onChart, budgetAuthorized, walletReady, minLiquidityUsd, strategyMode }: {
  grad: BagsGraduation;
  isNew: boolean;
  meetsThreshold: boolean;
  rejectReason: string | null;
  isSniped: boolean;
  onSnipe: () => void;
  onChart: () => void;
  budgetAuthorized: boolean;
  walletReady: boolean;
  minLiquidityUsd: number;
  strategyMode: StrategyMode;
}) {
  const tier = getScoreTier(grad.score);
  const tierCfg = TIER_CONFIG[tier];
  const age = Math.floor((Date.now() / 1000 - grad.graduation_time) / 60);
  const ageLabel = age < 1 ? 'JUST NOW' : age < 60 ? `${age}m ago` : age < 1440 ? `${Math.floor(age / 60)}h ago` : `${Math.floor(age / 1440)}d ago`;

  const priceChange = grad.price_change_1h ?? 0;
  const volume = grad.volume_24h || 0;
  const bsRatio = grad.buy_sell_ratio ?? 0;
  const ageH = grad.age_hours ?? 0;
  const totalTxns = grad.total_txns_1h ?? 0;
  const rec = getRecommendedSlTp(grad as any, strategyMode);
  const isBlueChip = isBlueChipLongConviction(grad);
  const targets = computeTargetsFromEntryUsd(grad.price_usd, rec.sl, rec.tp);

  // Insight filter checks (HYBRID_B v4 criteria)
  const passesLiq = (grad.liquidity || 0) >= minLiquidityUsd;
  // Mirror executor logic: only enforce B/S gate when there's enough activity.
  const passesBSRatio = totalTxns <= 10 ? true : (bsRatio >= 1.0 && bsRatio <= 3.0);
  const passesAge = ageH <= 500;
  const passesMomentum = priceChange >= 0;
  // Vol/Liq filter (8x edge: 40.6% upside ≥0.5 vs 4.9% <0.5)
  const vol24h = grad.volume_24h || 0;
  const gradLiq = grad.liquidity || 0;
  const volLiq = gradLiq > 0 ? vol24h / gradLiq : 0;
  const passesVolLiq = vol24h === 0 || volLiq >= 0.5; // skip filter when no vol data
  const passesAll = passesLiq && passesBSRatio && passesAge && passesMomentum && passesVolLiq;
  // Conviction-weighted sizing preview
  const { multiplier: conviction, factors: convFactors } = getConvictionMultiplier(grad as BagsGraduation & Record<string, any>);
  const convLabel = conviction >= 1.5 ? 'HIGH' : conviction >= 1.0 ? 'MED' : 'LOW';
  const convColor = conviction >= 1.5 ? 'text-accent-neon' : conviction >= 1.0 ? 'text-accent-warning' : 'text-text-muted';

  // Compact filter summary: count passes vs total
  const filterChecks = [
    { key: 'Liq', pass: passesLiq },
    ...(bsRatio > 0 ? [{ key: `B/S ${bsRatio.toFixed(1)}`, pass: passesBSRatio }] : []),
    ...(ageH > 0 ? [{ key: ageH < 24 ? `${ageH.toFixed(0)}h` : `${Math.round(ageH / 24)}d`, pass: passesAge }] : []),
    { key: 'Mom', pass: passesMomentum },
    ...(vol24h > 0 ? [{ key: `V/L ${volLiq.toFixed(1)}`, pass: passesVolLiq }] : []),
  ];
  const passCount = filterChecks.filter(f => f.pass).length;

  return (
    <div className={`
      group relative rounded-lg border p-3 transition-all duration-300
      ${isNew ? 'animate-new-grad border-accent-neon/40 bg-accent-neon/[0.04]' : 'border-border-primary bg-bg-secondary/60 hover:border-border-hover hover:bg-bg-tertiary/60'}
      ${!meetsThreshold ? 'opacity-40' : ''}
      ${isSniped ? 'border-accent-neon/30 bg-accent-neon/[0.02]' : ''}
    `}>
      {/* Header: logo + name + score */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {grad.logo_uri ? (
            <img src={grad.logo_uri} alt="" className="w-7 h-7 rounded-full bg-bg-tertiary shrink-0" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          ) : (
            <div className="w-7 h-7 rounded-full bg-bg-tertiary flex items-center justify-center text-[10px] font-bold text-text-muted shrink-0">
              {grad.symbol.slice(0, 2)}
            </div>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-text-primary">{grad.symbol}</span>
              <span className="text-[10px] text-text-muted/60 truncate">{grad.name}</span>
            </div>
            <CopyableAddress mint={grad.mint} />
          </div>
        </div>
        <span className={`text-xs font-mono font-bold px-2.5 py-1 rounded-full shrink-0 ${tierCfg.badgeClass}`}>
          {grad.score.toFixed(0)}
        </span>
      </div>

      {/* Key metrics: single clean row */}
      <div className="flex items-center gap-2 text-[10px] font-mono text-text-muted mb-2">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3 opacity-50" /> {ageLabel}
        </span>
        <span className="text-border-primary">|</span>
        <span className="flex items-center gap-1">
          <Droplets className="w-3 h-3 opacity-50" /> ${(grad.liquidity || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </span>
        {volume > 0 && (
          <>
            <span className="text-border-primary">|</span>
            <span className="flex items-center gap-1">
              <BarChart3 className="w-3 h-3 opacity-50" /> ${volume.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </span>
          </>
        )}
        {priceChange != null && priceChange !== 0 && (
          <>
            <span className="text-border-primary">|</span>
            <span className={`font-semibold ${priceChange >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
              {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(1)}%
            </span>
          </>
        )}
      </div>

      {/* Filter dots — compact inline summary instead of wrapping pills */}
      <div className="flex items-center gap-1.5 text-[9px] font-mono mb-2">
        {filterChecks.map((f) => (
          <span
            key={f.key}
            className={`inline-flex items-center gap-0.5 px-1.5 py-px rounded ${f.pass ? 'bg-accent-neon/8 text-accent-neon/80' : 'bg-accent-error/8 text-accent-error/80'}`}
          >
            <span className={`inline-block w-1 h-1 rounded-full ${f.pass ? 'bg-accent-neon' : 'bg-accent-error'}`} />
            {f.key}
          </span>
        ))}
        {passesAll && (
          <span className={`ml-auto inline-flex items-center gap-1 px-1.5 py-px rounded bg-bg-tertiary ${convColor}`} title={convFactors.join(', ')}>
            {conviction.toFixed(1)}x
          </span>
        )}
      </div>

      {/* Trade plan: Entry / SL / TP */}
      <div className="flex items-center text-[10px] font-mono">
        <span className="text-text-muted/60 mr-2">
          Entry <span className="text-text-secondary">{formatUsdPrice(targets.entryUsd)}</span>
        </span>
        {isBlueChip ? (
          <span className="ml-auto text-[9px] font-semibold uppercase tracking-wider text-accent-warning">
            Long conviction
          </span>
        ) : (
          <div className="flex items-center gap-3 ml-auto">
            <span className="flex items-center gap-1 text-accent-error">
              <Shield className="w-3 h-3" />
              <span>{rec.sl}%</span>
              <span className="text-text-muted/40">({formatUsdPrice(targets.slUsd)})</span>
            </span>
            <span className="flex items-center gap-1 text-accent-neon">
              <Target className="w-3 h-3" />
              <span>{rec.tp}%</span>
              <span className="text-text-muted/40">({formatUsdPrice(targets.tpUsd)})</span>
            </span>
          </div>
        )}
      </div>

      {/* Reject reason (shown inline below card content, not as overlay) */}
      {!meetsThreshold && rejectReason && (
        <div className="flex items-center gap-1.5 mt-2 px-2 py-1 rounded bg-accent-error/8 border border-accent-error/15">
          <Ban className="w-3 h-3 text-accent-error/70 shrink-0" />
          <span className="text-[9px] font-mono text-accent-error/80">{rejectReason}</span>
        </div>
      )}

      {/* Action overlay on hover */}
      <div className="absolute inset-0 rounded-lg flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity bg-bg-primary/80 backdrop-blur-sm">
        {isSniped ? (
          <span className="flex items-center gap-1.5 text-[11px] font-semibold px-4 py-2 rounded-full bg-accent-neon/15 text-accent-neon border border-accent-neon/30">
            <Check className="w-3.5 h-3.5" /> Sniped
          </span>
        ) : !walletReady ? (
          <span className="flex items-center gap-1.5 text-[11px] font-medium px-4 py-2 rounded-full bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            Connect wallet
          </span>
        ) : !budgetAuthorized ? (
          <span className="flex items-center gap-1.5 text-[11px] font-medium px-4 py-2 rounded-full bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            Authorize budget
          </span>
        ) : !meetsThreshold ? (
          <span className="flex items-center gap-1.5 text-[11px] font-medium px-4 py-2 rounded-full bg-bg-tertiary text-text-secondary border border-border-primary">
            Filtered
          </span>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onSnipe(); }}
            className="flex items-center gap-1.5 text-[11px] font-semibold px-4 py-2 rounded-full bg-accent-neon text-black hover:shadow-lg transition-all cursor-pointer"
          >
            <Crosshair className="w-3.5 h-3.5" /> Snipe
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onChart(); }}
          className="flex items-center gap-1 text-[11px] font-medium px-4 py-2 rounded-full bg-bg-tertiary text-text-secondary border border-border-primary hover:border-border-hover transition-all cursor-pointer"
        >
          <ExternalLink className="w-3 h-3" /> Chart
        </button>
      </div>
    </div>
  );
}

function computeHybridB(grad: BagsGraduation, minLiquidityUsd: number): { passesAll: boolean; rejectReason: string | null } {
  const liq = grad.liquidity || 0;
  const buys = grad.txn_buys_1h || 0;
  const sells = grad.txn_sells_1h || 0;
  const totalTxns = grad.total_txns_1h ?? (buys + sells);
  const bsRatio = grad.buy_sell_ratio ?? (sells > 0 ? buys / sells : buys);
  const ageH = grad.age_hours ?? 0;
  const change1h = grad.price_change_1h ?? 0;
  const vol24h = grad.volume_24h || 0;
  const volLiq = liq > 0 ? vol24h / liq : 0;

  if (liq < minLiquidityUsd) return { passesAll: false, rejectReason: `Liq $${(liq / 1000).toFixed(0)}K < $${(minLiquidityUsd / 1000).toFixed(0)}K` };
  if (totalTxns > 10 && (bsRatio < 1.0 || bsRatio > 3.0)) return { passesAll: false, rejectReason: `B/S ${bsRatio.toFixed(1)} outside range` };
  if (ageH > 500) return { passesAll: false, rejectReason: `Age ${Math.round(ageH)}h > 500h` };
  if (change1h < 0) return { passesAll: false, rejectReason: `Momentum ${change1h.toFixed(1)}%` };
  if (vol24h > 0 && volLiq < 0.5) return { passesAll: false, rejectReason: `Vol/Liq ${volLiq.toFixed(2)} < 0.5` };

  return { passesAll: true, rejectReason: null };
}
