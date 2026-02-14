'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  RefreshCw,
  Zap,
  TrendingUp,
  Users,
  MessageCircle,
  Activity,
  Star,
  Check,
  Minus,
  AlertTriangle,
  XCircle,
  ExternalLink,
  Clock,
  ArrowUpDown,
  ChevronDown,
  Info,
  ShoppingCart,
  Loader2,
  Twitter,
  Globe,
  Send,
} from 'lucide-react';
import { StatusBar } from '@/components/StatusBar';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { VersionedTransaction } from '@solana/web3.js';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { waitForSignatureStatus } from '@/lib/tx-confirmation';
import { safeImageUrl } from '@/lib/safe-url';
import {
  type BagsGraduation,
  type ScoreTier,
  getScoreTier,
  TIER_CONFIG,
} from '@/lib/bags-api';

/* ------------------------------------------------------------------ */
/*  Types & constants                                                 */
/* ------------------------------------------------------------------ */

type FilterTier = 'all' | ScoreTier;
type SortKey = 'score' | 'market_cap' | 'liquidity' | 'time';

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'score', label: 'Score' },
  { value: 'market_cap', label: 'Market Cap' },
  { value: 'liquidity', label: 'Liquidity' },
  { value: 'time', label: 'Newest' },
];

const TIER_META: Record<
  ScoreTier,
  { min: number; max: number; icon: typeof Star; color: string; bg: string }
> = {
  exceptional: { min: 85, max: 100, icon: Star, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  strong: { min: 70, max: 84, icon: Check, color: 'text-accent-success', bg: 'bg-accent-success/10' },
  average: { min: 50, max: 69, icon: Minus, color: 'text-text-muted', bg: 'bg-accent-warning/10' },
  weak: { min: 30, max: 49, icon: AlertTriangle, color: 'text-accent-warning', bg: 'bg-accent-warning/10' },
  poor: { min: 0, max: 29, icon: XCircle, color: 'text-accent-error', bg: 'bg-accent-error/10' },
};

const SCORING_DIMENSIONS = [
  {
    title: 'Bonding Curve Analysis',
    description:
      'Duration of the bonding curve phase, total volume, unique buyer count, and buy/sell ratio patterns.',
    icon: TrendingUp,
  },
  {
    title: 'Holder Distribution',
    description:
      'Top-holder concentration, wallet diversity, and distribution fairness across all holders.',
    icon: Users,
  },
  {
    title: 'Social Signals',
    description:
      'Community engagement metrics, linked socials (Twitter, Telegram, website), and founder verification.',
    icon: MessageCircle,
  },
  {
    title: 'On-chain Metrics',
    description:
      'Trading volume, transaction activity, buy pressure momentum, and price change signals.',
    icon: Activity,
  },
];

const REFRESH_INTERVAL_MS = 30_000;

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function timeAgo(epochSec: number): string {
  const diffMs = Date.now() - epochSec * 1000;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function fmtUsd(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  if (val >= 1) return `$${val.toFixed(2)}`;
  if (val >= 0.0001) return `$${val.toFixed(6)}`;
  return `$${val.toExponential(2)}`;
}

function fmtPrice(val: number): string {
  if (val >= 1) return `$${val.toFixed(2)}`;
  if (val >= 0.0001) return `$${val.toFixed(6)}`;
  if (val > 0) return `$${val.toExponential(2)}`;
  return '$0';
}

function sortGraduations(
  items: BagsGraduation[],
  key: SortKey,
): BagsGraduation[] {
  const sorted = [...items];
  switch (key) {
    case 'score':
      sorted.sort((a, b) => b.score - a.score);
      break;
    case 'market_cap':
      sorted.sort((a, b) => b.market_cap - a.market_cap);
      break;
    case 'liquidity':
      sorted.sort((a, b) => b.liquidity - a.liquidity);
      break;
    case 'time':
      sorted.sort((a, b) => b.graduation_time - a.graduation_time);
      break;
  }
  return sorted;
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                    */
/* ------------------------------------------------------------------ */

function ScoreBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-text-secondary">{label}</span>
        <span className="font-mono text-text-primary">{Math.round(clamped)}</span>
      </div>
      <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${clamped}%`, backgroundColor: color }}
        />
      </div>
    </div>
  );
}

function TierBadge({ tier }: { tier: ScoreTier }) {
  const cfg = TIER_CONFIG[tier];
  return (
    <span
      className={`${cfg.badgeClass} inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide`}
    >
      {cfg.label}
    </span>
  );
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function QuickBuyButton({ mint }: { mint: string }) {
  const [buying, setBuying] = useState(false);
  const [result, setResult] = useState<'success' | 'error' | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [amount, setAmount] = useState('0.1');
  const PRESET_AMOUNTS = ['0.05', '0.1', '0.25', '0.5', '1'];
  const { connected, connecting, connect, publicKey, signTransaction } = usePhantomWallet();

  async function handleBuy() {
    const solAmount = parseFloat(amount);
    if (isNaN(solAmount) || solAmount <= 0) return;

    if (!connected || !publicKey) {
      try { await connect(); } catch {}
      setResult('error');
      setErrorMsg('Connect wallet first');
      setTimeout(() => { setResult(null); setErrorMsg(null); }, 3000);
      return;
    }

    setBuying(true);
    setResult(null);
    setErrorMsg(null);
    try {
      const res = await fetch('/api/bags/swap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          userPublicKey: publicKey.toBase58(),
          inputMint: 'So11111111111111111111111111111111111111112',
          outputMint: mint,
          amount: Math.round(solAmount * 1e9), // SOL to lamports
          slippageBps: 500,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (err?.code === 'INSUFFICIENT_SIGNER_SOL') {
          const available = Number(err.availableSol || 0);
          const required = Number(err.requiredSol || 0);
          throw new Error(
            `Insufficient SOL: ${available.toFixed(4)} available, ${required.toFixed(4)} required (includes fee reserve).`,
          );
        }
        throw new Error(err.error || `Swap failed (${res.status})`);
      }
      const json = await res.json();
      const txBase64 = String(json?.transaction || '');
      if (!txBase64) throw new Error('Missing swap transaction');
      const tx = VersionedTransaction.deserialize(base64ToBytes(txBase64));
      const signed = await signTransaction(tx);
      const connection = getSharedConnection();
      const sig = await connection.sendRawTransaction(signed.serialize(), {
        skipPreflight: false,
        maxRetries: 3,
      });
      const status = await waitForSignatureStatus(connection, sig, { maxWaitMs: 45_000, pollMs: 2500 });
      if (status.state === 'failed') {
        throw new Error(status.error || 'Swap failed on-chain');
      }
      setResult('success');
    } catch (err) {
      setResult('error');
      setErrorMsg(err instanceof Error ? err.message : 'Swap failed');
    } finally {
      setBuying(false);
      setTimeout(() => { setResult(null); setErrorMsg(null); }, 4000);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5">
        {PRESET_AMOUNTS.map((preset) => (
          <button
            key={preset}
            onClick={() => setAmount(preset)}
            className={`px-2 py-1 rounded text-[10px] font-mono font-semibold transition-colors ${
              amount === preset
                ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30'
                : 'bg-bg-tertiary text-text-muted border border-border-primary hover:text-text-primary'
            }`}
          >
            {preset}
          </button>
        ))}
        <input
          type="number"
          step="0.01"
          min="0.001"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-16 px-2 py-1 rounded text-[10px] font-mono bg-bg-tertiary border border-border-primary text-text-primary text-center focus:border-accent-neon/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-neon/30"
          aria-label="Buy amount in SOL"
          placeholder="SOL"
        />
      </div>
      <button
        onClick={handleBuy}
        disabled={buying || connecting || parseFloat(amount) <= 0}
        className={`flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
          result === 'success'
            ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30'
            : result === 'error'
            ? 'bg-accent-error/20 text-accent-error border border-accent-error/30'
            : 'bg-accent-neon/10 hover:bg-accent-neon/20 text-accent-neon border border-accent-neon/20 hover:border-accent-neon/40'
        } disabled:opacity-50`}
      >
        {buying ? (
          <><Loader2 className="w-3.5 h-3.5 animate-spin" />Buying...</>
        ) : connecting ? (
          <><Loader2 className="w-3.5 h-3.5 animate-spin" />Connecting...</>
        ) : result === 'success' ? (
          <><Check className="w-3.5 h-3.5" />Bought {amount} SOL!</>
        ) : result === 'error' ? (
          <><XCircle className="w-3.5 h-3.5" />{errorMsg || 'Failed'}</>
        ) : (
          <><ShoppingCart className="w-3.5 h-3.5" />Buy {amount} SOL</>
        )}
      </button>
    </div>
  );
}

function GraduationCard({ grad }: { grad: BagsGraduation }) {
  const tier = getScoreTier(grad.score);
  const tierColor = TIER_CONFIG[tier].color;
  const [chartOpen, setChartOpen] = useState(false);
  const safeLogoUri = safeImageUrl(grad.logo_uri);
  const chartUrl = (grad as any).chart_url || `https://dexscreener.com/solana/${grad.mint}`;
  const website = (grad as any).website as string | undefined;
  const twitter = grad.twitter as string | undefined;
  const telegram = (grad as any).telegram as string | undefined;
  const pairAddress = (grad as any).pair_address as string | undefined;
  const chartEmbedUrl = `https://dexscreener.com/solana/${pairAddress || grad.mint}?embed=1&theme=dark&trades=0&info=0`;

  return (
    <div className="card-glass p-5 flex flex-col gap-4 animate-fade-in">
      {/* Header: Logo + Name + Tier */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          {safeLogoUri ? (
            <img
              src={safeLogoUri}
              alt={grad.symbol}
              className="w-10 h-10 rounded-full bg-bg-tertiary object-cover shrink-0"
              onError={(e) => {
                (e.currentTarget as HTMLImageElement).style.display = 'none';
              }}
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-bg-tertiary flex items-center justify-center text-text-muted text-sm font-bold shrink-0">
              {grad.symbol?.charAt(0) || '?'}
            </div>
          )}
          <div className="min-w-0">
            <h3 className="font-display font-bold text-text-primary truncate">
              {grad.name}
            </h3>
            <p className="text-xs text-text-muted font-mono truncate">
              ${grad.symbol}
            </p>
          </div>
        </div>
        <TierBadge tier={tier} />
      </div>

      {/* Score ring */}
      <div className="flex items-center gap-4">
        <div className="relative w-14 h-14 shrink-0">
          <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
            <circle
              cx="18"
              cy="18"
              r="15.5"
              fill="none"
              strokeWidth="3"
              className="stroke-bg-tertiary"
            />
            <circle
              cx="18"
              cy="18"
              r="15.5"
              fill="none"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${(grad.score / 100) * 97.4} 97.4`}
              style={{ stroke: tierColor }}
              className="transition-colors duration-700"
            />
          </svg>
          <span
            className="absolute inset-0 flex items-center justify-center font-mono text-sm font-bold"
            style={{ color: tierColor }}
          >
            {Math.round(grad.score)}
          </span>
        </div>

        {/* Market data */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 flex-1 text-xs">
          <div>
            <span className="text-text-muted">MCap</span>
            <p className="font-mono text-text-primary">{fmtUsd(grad.market_cap)}</p>
          </div>
          <div>
            <span className="text-text-muted">Price</span>
            <p className="font-mono text-text-primary">{fmtPrice(grad.price_usd)}</p>
          </div>
          <div>
            <span className="text-text-muted">Liquidity</span>
            <p className="font-mono text-text-primary">{fmtUsd(grad.liquidity)}</p>
          </div>
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-text-muted" />
            <span className="font-mono text-text-secondary">
              {timeAgo(grad.graduation_time)}
            </span>
          </div>
        </div>
      </div>

      {/* Scoring breakdown (4 dimensions, NO liquidity) */}
      <div className="space-y-2">
        <ScoreBar
          label="Bonding Curve"
          value={grad.bonding_curve_score}
          color={tierColor}
        />
        <ScoreBar
          label="Holder Distribution"
          value={grad.holder_distribution_score}
          color={tierColor}
        />
        <ScoreBar
          label="Social Signals"
          value={grad.social_score}
          color={tierColor}
        />
        <ScoreBar
          label="On-chain Activity"
          value={
            // Use available on-chain metrics to derive an activity bar
            grad.volume_24h
              ? Math.min(100, (grad.volume_24h / 50_000) * 100)
              : Math.min(
                  100,
                  ((grad.txn_buys_1h || 0) + (grad.txn_sells_1h || 0)) / 2,
                )
          }
          color={tierColor}
        />
      </div>

      {/* Actions */}
      <div className="mt-auto flex flex-col gap-2">
        <QuickBuyButton mint={grad.mint} />
        {(twitter || website || telegram) && (
          <div className="flex items-center gap-2 flex-wrap">
            {twitter && (
              <a
                href={twitter}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] border border-border-primary bg-bg-tertiary text-text-secondary hover:text-text-primary hover:border-border-hover"
              >
                <Twitter className="w-3 h-3" />
                Twitter
              </a>
            )}
            {telegram && (
              <a
                href={telegram}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] border border-border-primary bg-bg-tertiary text-text-secondary hover:text-text-primary hover:border-border-hover"
              >
                <Send className="w-3 h-3" />
                Telegram
              </a>
            )}
            {website && (
              <a
                href={website}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] border border-border-primary bg-bg-tertiary text-text-secondary hover:text-text-primary hover:border-border-hover"
              >
                <Globe className="w-3 h-3" />
                Website
              </a>
            )}
          </div>
        )}
        <button
          onClick={() => setChartOpen((v) => !v)}
          className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover text-sm text-text-secondary hover:text-text-primary transition-colors"
        >
          <ExternalLink className="w-3.5 h-3.5" />
          {chartOpen ? 'Hide Chart' : 'View Chart'}
        </button>
        <div
          className={`overflow-hidden transition-[max-height,opacity] duration-300 ${
            chartOpen ? 'max-h-[360px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          <div className="rounded-lg border border-border-primary overflow-hidden bg-black/40">
            <iframe
              src={chartEmbedUrl}
              className="w-full h-[300px] border-0"
              loading="lazy"
              title={`${grad.symbol} chart`}
            />
          </div>
          <div className="pt-2">
            <a
              href={chartUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-text-muted hover:text-text-primary inline-flex items-center gap-1.5"
            >
              <ExternalLink className="w-3 h-3" />
              Open full chart
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="card-glass p-5 flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full skeleton" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-24 skeleton" />
          <div className="h-3 w-16 skeleton" />
        </div>
        <div className="h-6 w-20 rounded-full skeleton" />
      </div>
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-full skeleton" />
        <div className="grid grid-cols-2 gap-2 flex-1">
          <div className="h-3 skeleton" />
          <div className="h-3 skeleton" />
          <div className="h-3 skeleton" />
          <div className="h-3 skeleton" />
        </div>
      </div>
      <div className="space-y-3">
        <div className="h-1.5 skeleton rounded-full" />
        <div className="h-1.5 skeleton rounded-full" />
        <div className="h-1.5 skeleton rounded-full" />
        <div className="h-1.5 skeleton rounded-full" />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                         */
/* ------------------------------------------------------------------ */

export default function BagsGraduationsPage() {
  const [graduations, setGraduations] = useState<BagsGraduation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<FilterTier>('all');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortOpen, setSortOpen] = useState(false);
  const [howWeRateOpen, setHowWeRateOpen] = useState(true);
  const sortRef = useRef<HTMLDivElement>(null);

  // Close sort dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (sortRef.current && !sortRef.current.contains(e.target as Node)) {
        setSortOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const fetchData = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/graduations?mode=launches&maxAgeHours=96');
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();
      const raw: BagsGraduation[] = data.graduations || [];
      const byMint = new Map<string, BagsGraduation>();
      for (const g of raw) {
        if (!g?.mint) continue;
        const prev = byMint.get(g.mint);
        if (!prev || (g.score || 0) >= (prev.score || 0)) byMint.set(g.mint, g);
      }
      setGraduations([...byMint.values()]);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch graduations');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchData(true);
  }, [fetchData]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(() => fetchData(false), REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchData]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchData(false);
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Filter + sort
  const filtered =
    activeFilter === 'all'
      ? graduations
      : graduations.filter((g) => getScoreTier(g.score) === activeFilter);
  const sorted = sortGraduations(filtered, sortKey);

  // Stats
  const tierCounts = graduations.reduce(
    (acc, g) => {
      const t = getScoreTier(g.score);
      acc[t] = (acc[t] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <div className="min-h-screen flex flex-col">
      <StatusBar />

      <main className="app-shell flex-1 py-8">
        {/* Hero */}
        <section className="text-center mb-10">
          <div className="flex items-center justify-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-md bg-amber-500/20 flex items-center justify-center text-amber-400 font-bold text-lg">D</div>
            <p className="text-xs text-accent-neon font-mono tracking-widest">
              DEGEN LAUNCH INTEL
            </p>
          </div>
          <h1 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold text-text-primary mb-3">
            DeGen Launches
          </h1>
          <p className="text-text-secondary text-base max-w-2xl mx-auto">
            Real-time intelligence on new launches across supported launchpads,
            scored and ranked by the KR8TIV quality engine.
          </p>
          <div className="flex items-center justify-center gap-2 mt-3">
            {lastUpdated && (
              <span className="text-xs text-text-muted font-mono">
                Updated {lastUpdated.toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary text-xs font-medium text-text-secondary hover:text-text-primary transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </section>

        {/* How We Rate */}
        <section className="mb-10">
          <div className="card-glass overflow-hidden">
            <button
              onClick={() => setHowWeRateOpen((v) => !v)}
              className="w-full p-5 flex items-center justify-between hover:bg-bg-secondary/30 transition-colors"
            >
              <h2 className="font-display font-bold text-base flex items-center gap-2 text-text-primary">
                <Info className="w-4 h-4 text-accent-neon" />
                How We Rate Tokens
              </h2>
              <ChevronDown
                className={`w-4 h-4 text-text-muted transition-transform duration-200 ${
                  howWeRateOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {howWeRateOpen && (
              <div className="px-5 pb-5 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                  {SCORING_DIMENSIONS.map((dim) => (
                    <div
                      key={dim.title}
                      className="p-4 rounded-xl border border-border-primary hover:border-border-hover transition-colors bg-bg-secondary/50"
                    >
                      <div className="flex items-center gap-2 mb-2 text-accent-neon">
                        <dim.icon className="w-4 h-4" />
                        <h3 className="font-semibold text-sm">{dim.title}</h3>
                      </div>
                      <p className="text-xs text-text-muted leading-relaxed">
                        {dim.description}
                      </p>
                    </div>
                  ))}
                </div>

                {/* Score tiers legend */}
                <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-border-primary">
                  {(Object.keys(TIER_META) as ScoreTier[]).map((tier) => {
                    const { min, max, icon: Icon, color, bg } = TIER_META[tier];
                    return (
                      <div
                        key={tier}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full ${bg} border border-border-primary`}
                      >
                        <Icon className={`w-3 h-3 ${color}`} />
                        <span
                          className={`text-xs font-medium capitalize ${color}`}
                        >
                          {tier}
                        </span>
                        <span className="text-xs text-text-muted font-mono">
                          {min}-{max}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Filter + Sort controls */}
        <section className="mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          {/* Tier filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors border ${
                activeFilter === 'all'
                  ? 'bg-text-primary text-bg-primary border-text-primary'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
            >
              All
              <span className="ml-1.5 font-mono text-xs opacity-70">
                {graduations.length}
              </span>
            </button>
            {(Object.keys(TIER_META) as ScoreTier[]).map((tier) => {
              const { icon: Icon, color, bg } = TIER_META[tier];
              const count = tierCounts[tier] || 0;
              return (
                <button
                  key={tier}
                  onClick={() => setActiveFilter(tier)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-sm font-medium transition-colors border ${
                    activeFilter === tier
                      ? `${bg} ${color} border-current`
                      : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span className="capitalize hidden xs:inline">{tier}</span>
                  <span className="font-mono text-xs opacity-70">{count}</span>
                </button>
              );
            })}
          </div>

          {/* Sort dropdown */}
          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setSortOpen((v) => !v)}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-bg-tertiary border border-border-primary text-sm text-text-secondary hover:text-text-primary hover:border-border-hover transition-colors"
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
              {SORT_OPTIONS.find((o) => o.value === sortKey)?.label}
              <ChevronDown
                className={`w-3 h-3 transition-transform ${sortOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {sortOpen && (
              <div className="absolute right-0 mt-2 w-40 card-glass rounded-xl overflow-hidden z-20 shadow-lg">
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => {
                      setSortKey(opt.value);
                      setSortOpen(false);
                    }}
                    className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                      sortKey === opt.value
                        ? 'text-accent-neon bg-accent-neon/10'
                        : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Error banner */}
        {error && (
          <div className="mb-6 bg-accent-error/10 border border-accent-error/30 rounded-xl p-4 text-accent-error text-sm font-mono">
            {error}
          </div>
        )}

        {/* Graduations grid */}
        <section>
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonCard key={i} />
              ))}
            </div>
          ) : sorted.length === 0 ? (
            <div className="text-center py-20">
              <div className="card-glass p-12 max-w-md mx-auto">
                <Zap className="w-12 h-12 text-text-muted mx-auto mb-4" />
                <h3 className="font-display font-bold text-xl mb-2 text-text-primary">
                  {activeFilter === 'all'
                    ? 'No graduations yet'
                    : `No ${activeFilter} tokens`}
                </h3>
                <p className="text-text-muted text-sm">
                  {activeFilter === 'all'
                    ? 'Waiting for tokens to complete bonding curve...'
                    : 'Try a different filter or check back soon.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {sorted.map((grad, idx) => (
                <GraduationCard key={`${grad.mint}:${grad.symbol || 'sym'}:${idx}`} grad={grad} />
              ))}
            </div>
          )}
        </section>

        {/* Footer attribution */}
        <footer className="mt-16 pb-8 text-center">
          <p className="text-xs text-text-muted font-mono">
            Powered by KR8TIV AI &middot; Data via DexScreener &middot;
            Auto-refreshes every 30s
          </p>
        </footer>
      </main>
    </div>
  );
}

