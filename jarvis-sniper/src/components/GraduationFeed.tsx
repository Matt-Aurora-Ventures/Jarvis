'use client';

import { useEffect, useRef } from 'react';
import { Sparkles, Clock, Droplets, BarChart3, ExternalLink, Crosshair, TrendingUp, TrendingDown, Shield, Target, Check, ArrowRightLeft, Timer, Zap } from 'lucide-react';
import { useSniperStore } from '@/stores/useSniperStore';
import { getScoreTier, TIER_CONFIG, type BagsGraduation } from '@/lib/bags-api';
import { getRecommendedSlTp, getConvictionMultiplier } from '@/stores/useSniperStore';
import { useSnipeExecutor } from '@/hooks/useSnipeExecutor';

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
            return (
              <TokenCard
                key={grad.mint}
                grad={grad}
                isNew={newMintsRef.current.has(grad.mint)}
                meetsThreshold={grad.score >= config.minScore && hybrid.passesAll}
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

function TokenCard({ grad, isNew, meetsThreshold, isSniped, onSnipe, onChart, budgetAuthorized, walletReady, minLiquidityUsd, strategyMode }: {
  grad: BagsGraduation;
  isNew: boolean;
  meetsThreshold: boolean;
  isSniped: boolean;
  onSnipe: () => void;
  onChart: () => void;
  budgetAuthorized: boolean;
  walletReady: boolean;
  minLiquidityUsd: number;
  strategyMode: 'conservative' | 'aggressive';
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

  // Insight filter checks (HYBRID_B v4 criteria)
  const passesLiq = (grad.liquidity || 0) >= minLiquidityUsd;
  // Mirror executor logic: only enforce B/S gate when there's enough activity.
  const passesBSRatio = totalTxns <= 10 ? true : (bsRatio >= 1.0 && bsRatio <= 3.0);
  const passesAge = ageH <= 500;
  const passesMomentum = priceChange >= 0;
  // Time-of-day filter (928-token OHLCV backtest)
  const nowUtcHour = new Date().getUTCHours();
  const BAD_HOURS = [1, 3, 5, 9, 17, 23];
  const GOOD_HOURS = [4, 8, 11, 21];
  const passesTod = !BAD_HOURS.includes(nowUtcHour);
  const isGoodHour = GOOD_HOURS.includes(nowUtcHour);
  // Vol/Liq filter (8x edge: 40.6% upside ≥0.5 vs 4.9% <0.5)
  const vol24h = grad.volume_24h || 0;
  const gradLiq = grad.liquidity || 0;
  const volLiq = gradLiq > 0 ? vol24h / gradLiq : 0;
  const passesVolLiq = vol24h === 0 || volLiq >= 0.5; // skip filter when no vol data
  const passesAll = passesLiq && passesBSRatio && passesAge && passesMomentum && passesTod && passesVolLiq;
  // Conviction-weighted sizing preview
  const { multiplier: conviction, factors: convFactors } = getConvictionMultiplier(grad as BagsGraduation & Record<string, any>);
  const convLabel = conviction >= 1.5 ? 'HIGH' : conviction >= 1.0 ? 'MED' : 'LOW';
  const convColor = conviction >= 1.5 ? 'text-accent-neon' : conviction >= 1.0 ? 'text-accent-warning' : 'text-text-muted';

  return (
    <div className={`
      group relative rounded-lg border p-3 transition-all duration-300
      ${isNew ? 'animate-new-grad border-accent-neon/40 bg-accent-neon/[0.04]' : 'border-border-primary bg-bg-secondary/60 hover:border-border-hover hover:bg-bg-tertiary/60'}
      ${meetsThreshold ? '' : 'opacity-40'}
      ${isSniped ? 'border-accent-neon/30 bg-accent-neon/[0.02]' : ''}
    `}>
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {grad.logo_uri ? (
            <img src={grad.logo_uri} alt="" className="w-6 h-6 rounded-full bg-bg-tertiary" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
          ) : (
            <div className="w-6 h-6 rounded-full bg-bg-tertiary flex items-center justify-center text-[10px] font-bold text-text-muted">
              {grad.symbol.slice(0, 2)}
            </div>
          )}
          <div>
            <span className="text-sm font-bold text-text-primary">{grad.symbol}</span>
            <span className="text-[10px] text-text-muted ml-1.5 truncate max-w-[100px] inline-block align-middle">
              {grad.name}
            </span>
          </div>
        </div>
        <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${tierCfg.badgeClass}`}>
          {grad.score.toFixed(0)}
        </span>
      </div>

      {/* Metrics row */}
      <div className="flex items-center gap-3 text-[10px] text-text-muted font-mono mb-2">
        <span className="flex items-center gap-1">
          <Clock className="w-3 h-3" /> {ageLabel}
        </span>
        <span className="flex items-center gap-1">
          <Droplets className="w-3 h-3" /> ${(grad.liquidity || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </span>
        {volume > 0 && (
          <span className="flex items-center gap-1">
            <BarChart3 className="w-3 h-3" /> ${volume.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        )}
        {priceChange != null && priceChange !== 0 && (
          <span className={`flex items-center gap-0.5 ${priceChange >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
            {priceChange >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(1)}%
          </span>
        )}
      </div>

      {/* Insight filters row */}
      <div className="flex items-center gap-2 text-[9px] font-mono mb-1.5">
        <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded ${passesLiq ? 'bg-accent-neon/10 text-accent-neon' : 'bg-accent-error/10 text-accent-error'}`}>
          <Droplets className="w-2.5 h-2.5" /> Liq{passesLiq ? '✓' : '✗'}
        </span>
        {bsRatio > 0 && (
          <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded ${passesBSRatio ? 'bg-accent-neon/10 text-accent-neon' : 'bg-accent-error/10 text-accent-error'}`}>
            <ArrowRightLeft className="w-2.5 h-2.5" /> B/S {bsRatio.toFixed(1)}{passesBSRatio ? '✓' : '✗'}
          </span>
        )}
        {ageH > 0 && (
          <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded ${passesAge ? 'bg-accent-neon/10 text-accent-neon' : 'bg-accent-error/10 text-accent-error'}`}>
            <Timer className="w-2.5 h-2.5" /> {ageH < 24 ? `${ageH.toFixed(0)}h` : `${Math.round(ageH / 24)}d`}{passesAge ? '✓' : '✗'}
          </span>
        )}
        <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded ${passesMomentum ? 'bg-accent-neon/10 text-accent-neon' : 'bg-accent-error/10 text-accent-error'}`}>
          <Zap className="w-2.5 h-2.5" /> Mom{passesMomentum ? '✓' : '✗'}
        </span>
        <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded ${isGoodHour ? 'bg-accent-neon/10 text-accent-neon' : passesTod ? 'bg-bg-tertiary text-text-muted' : 'bg-accent-error/10 text-accent-error'}`}>
          <Clock className="w-2.5 h-2.5" /> {nowUtcHour}h{passesTod ? (isGoodHour ? '++' : '') : '✗'}
        </span>
        {vol24h > 0 && (
          <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded ${passesVolLiq ? 'bg-accent-neon/10 text-accent-neon' : 'bg-accent-error/10 text-accent-error'}`}>
            V/L {volLiq.toFixed(1)}{passesVolLiq ? '✓' : '✗'}
          </span>
        )}
        {passesAll && (
          <span className={`flex items-center gap-0.5 px-1 py-0.5 rounded bg-bg-tertiary ${convColor}`} title={convFactors.join(', ')}>
            {conviction.toFixed(1)}x {convLabel}
          </span>
        )}
        {passesAll && (
          <span className={`ml-auto font-bold text-[9px] ${strategyMode === 'aggressive' ? 'text-accent-warning' : 'text-accent-neon'}`}>
            {strategyMode === 'aggressive' ? 'LET IT RIDE ✓' : 'HYBRID-B v5 ✓'}
          </span>
        )}
      </div>

      {/* Recommended SL/TP row */}
      <div className="flex items-center gap-3 text-[10px] font-mono">
        <span className="flex items-center gap-1 text-accent-error">
          <Shield className="w-3 h-3" /> SL {rec.sl}%
        </span>
        <span className="flex items-center gap-1 text-accent-neon">
          <Target className="w-3 h-3" /> TP {rec.tp}%
        </span>
        <span className="text-text-muted/60 truncate flex-1 text-[9px]">{rec.reasoning}</span>
      </div>

      {/* Action overlay on hover */}
      <div className="absolute inset-0 rounded-lg flex items-center justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity bg-bg-primary/70 backdrop-blur-sm">
        {isSniped ? (
          <span className="flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-full bg-accent-neon/15 text-accent-neon border border-accent-neon/30">
            <Check className="w-3.5 h-3.5" /> Sniped
          </span>
        ) : !walletReady ? (
          <span className="flex items-center gap-1.5 text-[10px] font-medium px-3 py-1.5 rounded-full bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            <Shield className="w-3 h-3" /> Connect wallet first
          </span>
        ) : !budgetAuthorized ? (
          <span className="flex items-center gap-1.5 text-[10px] font-medium px-3 py-1.5 rounded-full bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            <Shield className="w-3 h-3" /> Authorize budget first
          </span>
        ) : !meetsThreshold ? (
          <span className="flex items-center gap-1.5 text-[10px] font-medium px-3 py-1.5 rounded-full bg-bg-tertiary text-text-secondary border border-border-primary">
            <Shield className="w-3 h-3" /> Filtered (HYBRID-B)
          </span>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onSnipe(); }}
            className="flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-full bg-accent-neon text-black hover:shadow-lg transition-all cursor-pointer"
          >
            <Crosshair className="w-3.5 h-3.5" /> Snipe
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onChart(); }}
          className="flex items-center gap-1 text-[11px] font-medium px-3 py-1.5 rounded-full bg-bg-tertiary text-text-secondary border border-border-primary hover:border-border-hover transition-all cursor-pointer"
        >
          <ExternalLink className="w-3 h-3" /> Chart
        </button>
      </div>
    </div>
  );
}

function computeHybridB(grad: BagsGraduation, minLiquidityUsd: number): { passesAll: boolean } {
  const liq = grad.liquidity || 0;
  const buys = grad.txn_buys_1h || 0;
  const sells = grad.txn_sells_1h || 0;
  const totalTxns = grad.total_txns_1h ?? (buys + sells);
  const bsRatio = grad.buy_sell_ratio ?? (sells > 0 ? buys / sells : buys);
  const ageH = grad.age_hours ?? 0;
  const change1h = grad.price_change_1h ?? 0;

  const passesLiq = liq >= minLiquidityUsd;
  const passesBSRatio = totalTxns <= 10 ? true : (bsRatio >= 1.0 && bsRatio <= 3.0);
  const passesAge = ageH <= 500;
  const passesMomentum = change1h >= 0;

  return { passesAll: passesLiq && passesBSRatio && passesAge && passesMomentum };
}
