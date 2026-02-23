'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Sparkles, Clock, Droplets, BarChart3, ExternalLink, Crosshair, Shield, Target, Check, Ban, Copy, Eye } from 'lucide-react';
import { useSniperStore, type StrategyMode, type AssetType, type SniperConfig } from '@/stores/useSniperStore';
import { getScoreTier, TIER_CONFIG, type BagsGraduation } from '@/lib/bags-api';
import { getRecommendedSlTp, getConvictionMultiplier } from '@/stores/useSniperStore';
import { useSnipeExecutor } from '@/hooks/useSnipeExecutor';
import { useTVScreener } from '@/hooks/useTVScreener';
import { MarketStatus } from '@/components/MarketStatus';
import { computeTargetsFromEntryUsd, formatUsdPrice, isBlueChipLongConviction } from '@/lib/trade-plan';
import { safeImageUrl } from '@/lib/safe-url';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';

const FILTER_LABELS: Record<string, { label: string; color: string }> = {
  memecoin: { label: 'MEME', color: 'bg-accent-neon/15 text-accent-neon' },
  bags: { label: 'DEGEN', color: 'bg-emerald-500/15 text-emerald-400' },
  xstock: { label: 'xSTOCK', color: 'bg-blue-500/15 text-blue-400' },
  prestock: { label: 'PRE-IPO', color: 'bg-purple-500/15 text-purple-400' },
  index: { label: 'INDEX', color: 'bg-amber-500/15 text-amber-400' },
  bluechip: { label: 'BLUE CHIP', color: 'bg-cyan-500/15 text-cyan-400' },
};

export function GraduationFeed() {
  const { graduations, config, snipedMints, setSelectedMint, budget, watchlist, addToWatchlist, removeFromWatchlist, assetFilter } = useSniperStore();
  const { snipe, ready: walletReady } = useSnipeExecutor();
  const { marketPhase, lastUpdated: tvLastUpdated } = useTVScreener();
  const prevMintsRef = useRef<Set<string>>(new Set());
  const newMintsRef = useRef<Set<string>>(new Set());
  const dedupedGraduations = useMemo(() => {
    const byMint = new Map<string, BagsGraduation>();
    for (const g of graduations) {
      if (!g?.mint) continue;
      const prev = byMint.get(g.mint);
      if (!prev || (g.score || 0) >= (prev.score || 0)) byMint.set(g.mint, g);
    }
    return [...byMint.values()];
  }, [graduations]);

  // UI-only "new token" pulse; feed refresh/auto-exec is now handled by the global orchestrator.
  useEffect(() => {
    const prev = prevMintsRef.current;
    const curr = new Set(dedupedGraduations.map((g) => g.mint));
    for (const g of dedupedGraduations) {
      if (!prev.has(g.mint)) {
        newMintsRef.current.add(g.mint);
        setTimeout(() => newMintsRef.current.delete(g.mint), 30000);
      }
    }
    prevMintsRef.current = curr;
  }, [dedupedGraduations]);

  return (
    <div className="card-glass p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Token Scanner</h2>
          {(() => {
            const filterInfo = FILTER_LABELS[assetFilter] || FILTER_LABELS.memecoin;
            return (
              <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded ${filterInfo.color}`}>
                {filterInfo.label}
              </span>
            );
          })()}
        </div>
        <div className="flex items-center gap-2">
          {/* Solana-native assets (memes, xstocks, prestocks, indexes) trade 24/7 on DEXes.
              Only show US equity market hours for bluechip (traditional stock) assets. */}
          {assetFilter === 'bluechip' ? (
            <MarketStatus marketPhase={marketPhase} lastUpdated={tvLastUpdated} />
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-bg-tertiary border border-border-primary">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-40 bg-accent-neon" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent-neon" />
              </span>
              <span className="text-[10px] font-mono font-semibold text-accent-neon">24/7</span>
            </span>
          )}
          <span className="text-[10px] font-mono text-text-muted">
            {dedupedGraduations.length} targets
          </span>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar space-y-2">
        {dedupedGraduations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-text-muted animate-pulse" />
            </div>
            <p className="text-xs text-text-muted">Scanning for targets...</p>
            <div className="skeleton w-48 h-2" />
          </div>
        ) : (
          dedupedGraduations.map((grad, idx) => {
            const hybrid = computeHybridB(grad, config, assetFilter);
            const meetsAll = grad.score >= config.minScore && hybrid.passesAll;
            return (
              <TokenCard
                key={`${grad.mint}:${grad.source || 'src'}:${grad.symbol || 'sym'}:${idx}`}
                grad={grad}
                isNew={newMintsRef.current.has(grad.mint)}
                meetsThreshold={meetsAll}
                rejectReason={meetsAll ? null : (hybrid.rejectReason || (grad.score < config.minScore ? `Score ${grad.score.toFixed(0)} < ${config.minScore}` : null))}
                isSniped={snipedMints.has(grad.mint)}
                onSnipe={() => snipe(grad as any)}
                onChart={() => setSelectedMint(grad.mint)}
                isWatched={watchlist.includes(grad.mint)}
                onWatch={() => watchlist.includes(grad.mint) ? removeFromWatchlist(grad.mint) : addToWatchlist(grad.mint)}
                budgetAuthorized={budget.authorized}
                walletReady={walletReady}
                minLiquidityUsd={config.minLiquidityUsd}
                minMomentum1h={config.minMomentum1h}
                maxTokenAgeHours={config.maxTokenAgeHours}
                minVolLiqRatio={config.minVolLiqRatio}
                stopLossPct={config.stopLossPct}
                takeProfitPct={config.takeProfitPct}
                strategyMode={config.strategyMode}
                assetFilter={assetFilter}
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

function TokenCard({ grad, isNew, meetsThreshold, rejectReason, isSniped, onSnipe, onChart, isWatched, onWatch, budgetAuthorized, walletReady, minLiquidityUsd, minMomentum1h, maxTokenAgeHours, minVolLiqRatio, stopLossPct, takeProfitPct, strategyMode, assetFilter }: {
  grad: BagsGraduation;
  isNew: boolean;
  meetsThreshold: boolean;
  rejectReason: string | null;
  isSniped: boolean;
  onSnipe: () => void;
  onChart: () => void;
  isWatched: boolean;
  onWatch: () => void;
  budgetAuthorized: boolean;
  walletReady: boolean;
  minLiquidityUsd: number;
  minMomentum1h: number;
  maxTokenAgeHours: number;
  minVolLiqRatio: number;
  stopLossPct: number;
  takeProfitPct: number;
  strategyMode: StrategyMode;
  assetFilter: string;
}) {
  const { connect, connecting } = usePhantomWallet();
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const tier = getScoreTier(grad.score);
  const tierCfg = TIER_CONFIG[tier];
  const age = Math.floor((Date.now() / 1000 - grad.graduation_time) / 60);
  const ageLabel = age < 1 ? 'JUST NOW' : age < 60 ? `${age}m ago` : age < 1440 ? `${Math.floor(age / 60)}h ago` : `${Math.floor(age / 1440)}d ago`;

  const priceChange = grad.price_change_1h ?? 0;
  const volume = grad.volume_24h || 0;
  const bsRatio = grad.buy_sell_ratio ?? 0;
  const ageH = grad.age_hours ?? 0;
  const ageCategory = ageH < 24 ? 'FRESH' : ageH < 168 ? 'YOUNG' : ageH < 2160 ? 'EST' : 'VET';
  const ageCatColor = ageH < 24 ? 'text-accent-neon' : ageH < 168 ? 'text-blue-400' : ageH < 2160 ? 'text-text-muted' : 'text-text-muted/50';
  // For equities, override age display with sector/category info
  const isEquity = assetFilter !== 'memecoin';
  const totalTxns = grad.total_txns_1h ?? 0;
  const rec = getRecommendedSlTp(grad as any, strategyMode, { stopLossPct, takeProfitPct });
  const isBlueChip = isBlueChipLongConviction(grad);
  const targets = computeTargetsFromEntryUsd(grad.price_usd, rec.sl, rec.tp);

  const isTraditional = assetFilter === 'xstock' || assetFilter === 'prestock' || assetFilter === 'index';
  // Insight filter checks (HYBRID_B v4 criteria)
  const passesLiq = isTraditional ? true : (grad.liquidity || 0) >= minLiquidityUsd;
  // Mirror executor logic: only enforce B/S gate when there's enough activity.
  const passesBSRatio = isEquity || totalTxns <= 10 ? true : (bsRatio >= 1.0 && bsRatio <= 3.0);
  const passesAge = isEquity || maxTokenAgeHours <= 0 || ageH <= maxTokenAgeHours;
  const passesMomentum = isEquity || priceChange >= minMomentum1h;
  // Vol/Liq filter (8x edge: 40.6% upside ≥0.5 vs 4.9% <0.5)
  const vol24h = grad.volume_24h || 0;
  const gradLiq = grad.liquidity || 0;
  const volLiq = gradLiq > 0 ? vol24h / gradLiq : 0;
  const passesVolLiq = isTraditional ? true : (vol24h === 0 || volLiq >= minVolLiqRatio); // skip filter when no vol data
  const passesAll = passesLiq && passesBSRatio && passesAge && passesMomentum && passesVolLiq;
  const logoUrl = safeImageUrl((grad as any).logo_uri);
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
    <div
      onClick={onChart}
      className={`
      group relative rounded-lg border p-3 transition-all duration-300 cursor-pointer
      ${isNew ? 'animate-new-grad border-accent-neon/40 bg-accent-neon/[0.04]' : 'border-border-primary bg-bg-secondary/60 hover:border-border-hover hover:bg-bg-tertiary/60'}
      ${!meetsThreshold ? 'opacity-40' : ''}
      ${isSniped ? 'border-accent-neon/30 bg-accent-neon/[0.02]' : ''}
    `}>
      {/* Header: logo + name + score */}
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {logoUrl ? (
            <img
              src={logoUrl}
              alt=""
              loading="lazy"
              decoding="async"
              referrerPolicy="no-referrer"
              className="w-7 h-7 rounded-full bg-bg-tertiary shrink-0"
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
          ) : (
            <div className="w-7 h-7 rounded-full bg-bg-tertiary flex items-center justify-center text-[10px] font-bold text-text-muted shrink-0">
              {grad.symbol.slice(0, 2)}
            </div>
          )}
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-bold text-text-primary">{grad.symbol}</span>
              {grad.dex_id && grad.dex_id !== 'unknown' && (
                <span className={`text-[8px] font-mono font-semibold uppercase px-1 py-px rounded ${
                  grad.dex_id === 'pumpswap' ? 'bg-purple-500/15 text-purple-400' :
                  grad.dex_id === 'raydium' ? 'bg-blue-500/15 text-blue-400' :
                  'bg-bg-tertiary text-text-muted'
                }`}>{grad.dex_id === 'raydium_clmm' ? 'RAY' : grad.dex_id.slice(0, 4).toUpperCase()}</span>
              )}
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
        {!isEquity && <span className={`text-[8px] font-bold ${ageCatColor}`}>{ageCategory}</span>}
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

      {/* Mobile action row (touch devices have no hover) */}
      <div className="mt-2 flex md:hidden items-center gap-1.5">
        {isSniped ? (
          <span className="flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold px-2.5 py-2 rounded-md bg-accent-neon/15 text-accent-neon border border-accent-neon/30">
            <Check className="w-3 h-3" /> Sniped
          </span>
        ) : !walletReady ? (
          tradeSignerMode === 'session' ? (
            <span className="flex-1 flex items-center justify-center gap-1 text-[10px] font-medium px-2.5 py-2 rounded-md bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
              Session not ready
            </span>
          ) : (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); void connect(); }}
              disabled={connecting}
              className="flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold px-2.5 py-2 rounded-md bg-accent-warning/15 text-accent-warning border border-accent-warning/30 disabled:opacity-60"
            >
              {connecting ? 'Connecting...' : 'Connect wallet'}
            </button>
          )
        ) : !budgetAuthorized ? (
          <span className="flex-1 flex items-center justify-center gap-1 text-[10px] font-medium px-2.5 py-2 rounded-md bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            Authorize budget
          </span>
        ) : !meetsThreshold ? (
          <span className="flex-1 flex items-center justify-center gap-1 text-[10px] font-medium px-2.5 py-2 rounded-md bg-bg-tertiary text-text-secondary border border-border-primary">
            Filtered
          </span>
        ) : (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onSnipe(); }}
            className="flex-1 flex items-center justify-center gap-1 text-[10px] font-semibold px-2.5 py-2 rounded-md bg-accent-neon text-black hover:shadow-lg transition-all cursor-pointer"
          >
            <Crosshair className="w-3 h-3" /> Snipe
          </button>
        )}

        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onChart(); }}
          className="flex items-center justify-center gap-1 text-[10px] font-medium px-2.5 py-2 rounded-md bg-bg-tertiary text-text-secondary border border-border-primary hover:border-border-hover transition-all cursor-pointer"
        >
          <ExternalLink className="w-3 h-3" /> Chart
        </button>
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onWatch(); }}
          className={`flex items-center justify-center gap-1 text-[10px] font-medium px-2.5 py-2 rounded-md border transition-all cursor-pointer ${
            isWatched
              ? 'bg-accent-warning/15 text-accent-warning border-accent-warning/30'
              : 'bg-bg-tertiary text-text-secondary border-border-primary hover:border-border-hover'
          }`}
        >
          <Eye className="w-3 h-3" /> {isWatched ? 'Watching' : 'Watch'}
        </button>
      </div>

      {/* Action overlay on hover */}
      <div className="hidden md:flex absolute inset-0 rounded-lg items-center justify-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity bg-bg-primary/90">
        {isSniped ? (
          <span className="flex items-center gap-1 text-[10px] font-semibold px-2.5 py-1.5 rounded-md bg-accent-neon/15 text-accent-neon border border-accent-neon/30">
            <Check className="w-3 h-3" /> Sniped
          </span>
        ) : !walletReady ? (
          <span className="flex items-center gap-1 text-[10px] font-medium px-2.5 py-1.5 rounded-md bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            Connect wallet
          </span>
        ) : !budgetAuthorized ? (
          <span className="flex items-center gap-1 text-[10px] font-medium px-2.5 py-1.5 rounded-md bg-accent-warning/15 text-accent-warning border border-accent-warning/30">
            Authorize budget
          </span>
        ) : !meetsThreshold ? (
          <span className="flex items-center gap-1 text-[10px] font-medium px-2.5 py-1.5 rounded-md bg-bg-tertiary text-text-secondary border border-border-primary">
            Filtered
          </span>
        ) : (
          <button
            onClick={(e) => { e.stopPropagation(); onSnipe(); }}
            className="flex items-center gap-1 text-[10px] font-semibold px-2.5 py-1.5 rounded-md bg-accent-neon text-black hover:shadow-lg transition-all cursor-pointer"
          >
            <Crosshair className="w-3 h-3" /> Snipe
          </button>
        )}
        <button
          onClick={(e) => { e.stopPropagation(); onChart(); }}
          className="flex items-center gap-1 text-[10px] font-medium px-2.5 py-1.5 rounded-md bg-bg-tertiary text-text-secondary border border-border-primary hover:border-border-hover transition-all cursor-pointer"
        >
          <ExternalLink className="w-3 h-3" /> Chart
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onWatch(); }}
          className={`flex items-center gap-1 text-[10px] font-medium px-2.5 py-1.5 rounded-md border transition-all cursor-pointer ${
            isWatched
              ? 'bg-accent-warning/15 text-accent-warning border-accent-warning/30'
              : 'bg-bg-tertiary text-text-secondary border-border-primary hover:border-border-hover'
          }`}
        >
          <Eye className="w-3 h-3" /> {isWatched ? 'Watching' : 'Watch'}
        </button>
      </div>
    </div>
  );
}

function computeHybridB(
  grad: BagsGraduation,
  config: Pick<SniperConfig, 'minLiquidityUsd' | 'minMomentum1h' | 'maxTokenAgeHours' | 'minVolLiqRatio' | 'tradingHoursGate' | 'minAgeMinutes'>,
  assetFilter: string = 'memecoin',
): { passesAll: boolean; rejectReason: string | null } {
  const liq = grad.liquidity || 0;
  const buys = grad.txn_buys_1h || 0;
  const sells = grad.txn_sells_1h || 0;
  const totalTxns = grad.total_txns_1h ?? (buys + sells);
  const bsRatio = grad.buy_sell_ratio ?? (sells > 0 ? buys / sells : buys);
  const ageH = grad.age_hours ?? 0;
  const change1h = grad.price_change_1h ?? 0;
  const vol24h = grad.volume_24h || 0;
  const volLiq = liq > 0 ? vol24h / liq : 0;

  // Liquidity is NOT a quality signal for xstocks/prestocks/indexes (guaranteed by platform).
  // Only apply liquidity filters to memecoins and blue chips.
  const isTraditional = assetFilter === 'xstock' || assetFilter === 'prestock' || assetFilter === 'index';
  if (!isTraditional && liq < config.minLiquidityUsd) {
    return { passesAll: false, rejectReason: `Liq $${(liq / 1000).toFixed(0)}K < $${(config.minLiquidityUsd / 1000).toFixed(0)}K` };
  }

  // Dead-hour gating disabled for continuous operation:
  // we do not hard-block entries by UTC hour anymore.

  if (config.minAgeMinutes > 0 && grad.graduation_time) {
    const ageMin = (Date.now() / 1000 - grad.graduation_time) / 60;
    if (ageMin < config.minAgeMinutes) {
      return { passesAll: false, rejectReason: `Too fresh ${ageMin.toFixed(1)}m < ${config.minAgeMinutes}m` };
    }
  }

  // Memecoin-specific filters
  if (assetFilter === 'memecoin' && totalTxns > 10 && (bsRatio < 1.0 || bsRatio > 3.0)) return { passesAll: false, rejectReason: `B/S ${bsRatio.toFixed(1)} outside range` };
  if (assetFilter === 'memecoin' && config.maxTokenAgeHours > 0 && ageH > config.maxTokenAgeHours) {
    return { passesAll: false, rejectReason: `Age ${Math.round(ageH)}h > ${config.maxTokenAgeHours}h` };
  }
  if (assetFilter === 'memecoin' && change1h < config.minMomentum1h) {
    return { passesAll: false, rejectReason: `Momentum ${change1h.toFixed(1)}% < ${config.minMomentum1h}%` };
  }

  // Vol/Liq ratio only meaningful for memecoins/blue chips — not xstocks/prestocks/indexes
  if (!isTraditional && vol24h > 0 && volLiq < config.minVolLiqRatio) {
    return { passesAll: false, rejectReason: `Vol/Liq ${volLiq.toFixed(2)} < ${config.minVolLiqRatio}` };
  }

  return { passesAll: true, rejectReason: null };
}
