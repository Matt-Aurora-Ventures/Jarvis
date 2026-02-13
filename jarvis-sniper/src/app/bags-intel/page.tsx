'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  RefreshCw,
  Zap,
  TrendingUp,
  TrendingDown,
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
  ChevronUp,
  Info,
  ShoppingCart,
  Loader2,
  Globe,
  Copy,
  Wallet,
  BarChart3,
  Flame,
} from 'lucide-react';
import { StatusBar } from '@/components/StatusBar';
import { type ScoreTier, getScoreTier, TIER_CONFIG } from '@/lib/bags-api';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { waitForSignatureStatus } from '@/lib/tx-confirmation';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface BagsIntelToken {
  mint: string;
  symbol: string;
  name: string;
  logoUri: string | null;
  deployer: string | null;
  royaltyWallet: string | null;
  royaltyUsername: string | null;
  royaltyPfp: string | null;
  poolAddress: string | null;
  priceUsd: number;
  marketCap: number;
  liquidity: number;
  volume24h: number;
  volume1h: number;
  txnBuys1h: number;
  txnSells1h: number;
  txnBuys24h: number;
  txnSells24h: number;
  buySellRatio: number;
  priceChange1h: number;
  priceChange6h: number;
  priceChange24h: number;
  website: string | null;
  twitter: string | null;
  telegram: string | null;
  pairCreatedAt: number | null;
  isBags: true;
  category: 'recent' | 'aboutToGraduate' | 'graduated' | 'topEarners';
  creatorUsername: string | null;
  creatorPfp: string | null;
  royaltyBps: number | null;
  lifetimeFeesLamports: number | null;
  score: number;
  bondingCurveScore: number;
  holderDistributionScore: number;
  socialScore: number;
  activityScore: number;
  momentumScore: number;
  topHoldersPct: number | null;
  organicScore: number | null;
  mintAuthorityDisabled: boolean | null;
  freezeAuthorityDisabled: boolean | null;
}

type FilterTier = 'all' | ScoreTier;
type SortKey = 'score' | 'market_cap' | 'volume' | 'momentum';
type CategoryFilter = 'all' | BagsIntelToken['category'];

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'score', label: 'Score' },
  { value: 'market_cap', label: 'Market Cap' },
  { value: 'volume', label: 'Volume 24h' },
  { value: 'momentum', label: 'Momentum' },
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
  { title: 'Volume & Maturity', description: 'Trading volume depth, 24h activity, and token maturity since launch.', icon: BarChart3, weight: '25%' },
  { title: 'Holder Distribution', description: 'Transaction diversity, unique buyer count, and wallet distribution patterns.', icon: Users, weight: '20%' },
  { title: 'Social Presence', description: 'Twitter, website, creator identity, and royalty configuration pulled from Bags + Jupiter.', icon: MessageCircle, weight: '15%' },
  { title: 'Trading Activity', description: 'Buy/sell ratio, 1h volume surge, and real-time transaction flow.', icon: Activity, weight: '25%' },
  { title: 'Price Momentum', description: '1h/6h/24h price change trends and directional conviction.', icon: TrendingUp, weight: '15%' },
];

const REFRESH_INTERVAL_MS = 30_000;

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

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

function shortAddr(addr: string | null): string {
  if (!addr) return '---';
  return `${addr.slice(0, 4)}...${addr.slice(-4)}`;
}

function fmtSolLamports(lamports: number): string {
  const sol = lamports / 1e9;
  if (sol >= 1000) return `${sol.toFixed(0)} SOL`;
  if (sol >= 10) return `${sol.toFixed(2)} SOL`;
  if (sol >= 1) return `${sol.toFixed(3)} SOL`;
  if (sol > 0) return `${sol.toFixed(6)} SOL`;
  return '0 SOL';
}

function pctClass(val: number): string {
  if (val > 0) return 'text-accent-success';
  if (val < 0) return 'text-accent-error';
  return 'text-text-muted';
}

function timeAgo(epochMs: number | null): string {
  if (!epochMs) return '---';
  const diffMs = Date.now() - epochMs;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function sortTokens(items: BagsIntelToken[], key: SortKey): BagsIntelToken[] {
  const sorted = [...items];
  switch (key) {
    case 'score':
      sorted.sort((a, b) => b.score - a.score);
      break;
    case 'market_cap':
      sorted.sort((a, b) => b.marketCap - a.marketCap);
      break;
    case 'volume':
      sorted.sort((a, b) => b.volume24h - a.volume24h);
      break;
    case 'momentum':
      sorted.sort((a, b) => b.priceChange1h - a.priceChange1h);
      break;
  }
  return sorted;
}

/* ------------------------------------------------------------------ */
/*  Sub-components                                                     */
/* ------------------------------------------------------------------ */

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
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
    <span className={`${cfg.badgeClass} inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold tracking-wide`}>
      {cfg.label}
    </span>
  );
}

function base64ToBytes(b64: string): Uint8Array {
  // Browser-safe base64 decode (avoids Buffer dependency).
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function QuickBuyButton({ mint, symbol }: { mint: string; symbol: string }) {
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
      // Make the connect path discoverable from the buy widget.
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
                ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
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
          className="w-16 px-2 py-1 rounded text-[10px] font-mono bg-bg-tertiary border border-border-primary text-text-primary text-center focus:border-purple-500/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/30"
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
            : 'bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/20 hover:border-purple-500/40'
        } disabled:opacity-50`}
      >
        {buying ? (
          <><Loader2 className="w-3.5 h-3.5 animate-spin" />Buying {symbol}...</>
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

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="text-text-muted hover:text-text-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/30 rounded-sm"
      title="Copy address"
      aria-label="Copy address"
    >
      {copied ? <Check className="w-3 h-3 text-accent-neon" /> : <Copy className="w-3 h-3" />}
    </button>
  );
}

function TokenCard({ token }: { token: BagsIntelToken }) {
  const [expanded, setExpanded] = useState(false);
  const [showChart, setShowChart] = useState(false);
  const tier = getScoreTier(token.score);
  const tierColor = TIER_CONFIG[tier].color;
  const chartTarget = token.poolAddress || token.mint;
  const categoryLabel = token.category === 'recent'
    ? 'NEW'
    : token.category === 'aboutToGraduate'
    ? 'NEAR GRAD'
    : token.category === 'graduated'
    ? 'GRAD'
    : 'EARNERS';

  return (
    <div className="card-glass overflow-hidden animate-fade-in">
      {/* Main content */}
      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-3 min-w-0">
            {token.logoUri ? (
              <img
                src={token.logoUri}
                alt={token.symbol}
                className="w-10 h-10 rounded-full bg-bg-tertiary object-cover shrink-0"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 text-sm font-bold shrink-0">
                {token.symbol?.charAt(0) || '?'}
              </div>
            )}
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-display font-bold text-text-primary truncate">{token.name}</h3>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-mono shrink-0">BAGS</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-tertiary text-text-muted font-mono shrink-0">{categoryLabel}</span>
              </div>
              <div className="flex items-center gap-2 text-xs text-text-muted font-mono">
                <span>${token.symbol}</span>
                <span>&middot;</span>
                <span>{shortAddr(token.mint)}</span>
                <CopyButton text={token.mint} />
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <TierBadge tier={tier} />
            <QuickBuyButton mint={token.mint} symbol={token.symbol} />
          </div>
        </div>

        {/* Score ring + Market data row */}
        <div className="flex items-center gap-4 mb-4">
          <div className="relative w-14 h-14 shrink-0">
            <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
              <circle cx="18" cy="18" r="15.5" fill="none" strokeWidth="3" className="stroke-bg-tertiary" />
              <circle
                cx="18" cy="18" r="15.5" fill="none" strokeWidth="3" strokeLinecap="round"
                strokeDasharray={`${(token.score / 100) * 97.4} 97.4`}
                style={{ stroke: tierColor }}
                className="transition-colors duration-700"
              />
            </svg>
            <span className="absolute inset-0 flex items-center justify-center font-mono text-sm font-bold" style={{ color: tierColor }}>
              {Math.round(token.score)}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-x-4 gap-y-1.5 flex-1 text-xs">
            <div>
              <span className="text-text-muted">MCap</span>
              <p className="font-mono text-text-primary">{fmtUsd(token.marketCap)}</p>
            </div>
            <div>
              <span className="text-text-muted">Price</span>
              <p className="font-mono text-text-primary">{fmtPrice(token.priceUsd)}</p>
            </div>
            <div>
              <span className="text-text-muted">Liquidity</span>
              <p className="font-mono text-text-primary">{fmtUsd(token.liquidity)}</p>
            </div>
            <div>
              <span className="text-text-muted">Vol 24h</span>
              <p className="font-mono text-text-primary">{fmtUsd(token.volume24h)}</p>
            </div>
            <div>
              <span className="text-text-muted">Vol 1h</span>
              <p className="font-mono text-text-primary">{fmtUsd(token.volume1h)}</p>
            </div>
            <div>
              <span className="text-text-muted">Age</span>
              <p className="font-mono text-text-secondary">{timeAgo(token.pairCreatedAt)}</p>
            </div>
          </div>
        </div>

        {/* Price changes row */}
        <div className="flex items-center gap-3 mb-4 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-text-muted">1h:</span>
            <span className={`font-mono font-semibold ${pctClass(token.priceChange1h)}`}>
              {token.priceChange1h > 0 ? '+' : ''}{token.priceChange1h.toFixed(1)}%
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-text-muted">6h:</span>
            <span className={`font-mono font-semibold ${pctClass(token.priceChange6h)}`}>
              {token.priceChange6h > 0 ? '+' : ''}{token.priceChange6h.toFixed(1)}%
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-text-muted">24h:</span>
            <span className={`font-mono font-semibold ${pctClass(token.priceChange24h)}`}>
              {token.priceChange24h > 0 ? '+' : ''}{token.priceChange24h.toFixed(1)}%
            </span>
          </div>
          <div className="ml-auto flex items-center gap-1 text-text-muted">
            <span>B/S:</span>
            <span className={`font-mono font-semibold ${token.buySellRatio >= 1.5 ? 'text-accent-success' : token.buySellRatio >= 1 ? 'text-text-primary' : 'text-accent-error'}`}>
              {token.buySellRatio.toFixed(2)}
            </span>
          </div>
        </div>

        {/* 5-dimension scoring bars */}
        <div className="space-y-2 mb-3">
          <ScoreBar label="Volume & Maturity" value={token.bondingCurveScore} color={tierColor} />
          <ScoreBar label="Holder Distribution" value={token.holderDistributionScore} color={tierColor} />
          <ScoreBar label="Social Presence" value={token.socialScore} color={tierColor} />
          <ScoreBar label="Trading Activity" value={token.activityScore} color={tierColor} />
          <ScoreBar label="Price Momentum" value={token.momentumScore} color={tierColor} />
        </div>

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-center gap-1 py-1.5 text-xs text-text-muted hover:text-text-primary transition-colors"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? 'Less detail' : 'More detail'}
        </button>
      </div>

      {/* Expanded section */}
      {expanded && (
        <div className="border-t border-border-primary px-5 py-4 space-y-4 bg-bg-secondary/30">
          {/* Creator / Royalties */}
          <div>
            <h4 className="text-xs font-semibold text-text-secondary mb-2 flex items-center gap-1.5">
              <Wallet className="w-3.5 h-3.5" />
              Creator / Royalties
            </h4>
            <div className="flex flex-col gap-2">
              {/* Created by */}
              <div className="flex items-center gap-2">
                {token.creatorPfp ? (
                  <img
                    src={token.creatorPfp}
                    alt={token.creatorUsername || 'Creator'}
                    className="w-7 h-7 rounded-full bg-bg-tertiary object-cover"
                    onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                  />
                ) : (
                  <div className="w-7 h-7 rounded-full bg-bg-tertiary border border-border-primary flex items-center justify-center text-[10px] font-mono text-text-muted">
                    ?
                  </div>
                )}
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-[10px] font-mono text-text-muted">created by</span>
                    <span className="font-mono text-text-primary truncate">
                      {token.creatorUsername || 'Unknown'}
                    </span>
                    {token.lifetimeFeesLamports != null && token.lifetimeFeesLamports > 0 && (
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-bg-tertiary text-text-secondary border border-border-primary">
                        Earned {fmtSolLamports(token.lifetimeFeesLamports)}
                      </span>
                    )}
                  </div>
                  {token.deployer && (
                    <div className="flex items-center gap-2 mt-1">
                      <code className="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-2 py-1 rounded">
                        {shortAddr(token.deployer)}
                      </code>
                      <CopyButton text={token.deployer} />
                      <a
                        href={`https://solscan.io/account/${token.deployer}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-text-muted hover:text-text-primary"
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  )}
                </div>
              </div>

              {/* Royalties to */}
              {(token.royaltyUsername || token.royaltyWallet || token.royaltyBps != null) && (
                <div className="flex items-center gap-2">
                  {token.royaltyPfp ? (
                    <img
                      src={token.royaltyPfp}
                      alt={token.royaltyUsername || 'Royalty'}
                      className="w-7 h-7 rounded-full bg-bg-tertiary object-cover"
                      onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                    />
                  ) : (
                    <div className="w-7 h-7 rounded-full bg-bg-tertiary border border-border-primary flex items-center justify-center text-[10px] font-mono text-text-muted">
                      $
                    </div>
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-[10px] font-mono text-text-muted">royalties to</span>
                      <span className="font-mono text-text-primary truncate">
                        {token.royaltyUsername || 'Unknown'}
                      </span>
                      {token.royaltyBps != null && (
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent-neon/10 text-accent-neon border border-accent-neon/20">
                          {Math.round(token.royaltyBps / 100)}%
                        </span>
                      )}
                    </div>
                    {token.royaltyWallet && (
                      <div className="flex items-center gap-2 mt-1">
                        <code className="text-[10px] font-mono text-purple-400 bg-purple-500/10 px-2 py-1 rounded">
                          {shortAddr(token.royaltyWallet)}
                        </code>
                        <CopyButton text={token.royaltyWallet} />
                        <a
                          href={`https://solscan.io/account/${token.royaltyWallet}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-text-muted hover:text-text-primary"
                        >
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {(token.topHoldersPct != null || token.organicScore != null) && (
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {token.topHoldersPct != null && (
                    <div className="bg-bg-tertiary/50 rounded-lg p-2.5">
                      <span className="text-text-muted block mb-1">Top holders</span>
                      <span className="font-mono text-text-primary">{token.topHoldersPct.toFixed(1)}%</span>
                    </div>
                  )}
                  {token.organicScore != null && (
                    <div className="bg-bg-tertiary/50 rounded-lg p-2.5">
                      <span className="text-text-muted block mb-1">Organic score</span>
                      <span className="font-mono text-text-primary">{Math.round(token.organicScore)}</span>
                    </div>
                  )}
                </div>
              )}

              {(token.mintAuthorityDisabled != null || token.freezeAuthorityDisabled != null) && (
                <div className="flex flex-wrap gap-2 text-[10px] font-mono">
                  {token.mintAuthorityDisabled != null && (
                    <span className={`px-2 py-1 rounded-full border ${token.mintAuthorityDisabled ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/20' : 'bg-accent-error/10 text-accent-error border-accent-error/20'}`}>
                      Mint auth {token.mintAuthorityDisabled ? 'OFF' : 'ON'}
                    </span>
                  )}
                  {token.freezeAuthorityDisabled != null && (
                    <span className={`px-2 py-1 rounded-full border ${token.freezeAuthorityDisabled ? 'bg-accent-neon/10 text-accent-neon border-accent-neon/20' : 'bg-accent-error/10 text-accent-error border-accent-error/20'}`}>
                      Freeze {token.freezeAuthorityDisabled ? 'OFF' : 'ON'}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Transaction detail */}
          <div>
            <h4 className="text-xs font-semibold text-text-secondary mb-2 flex items-center gap-1.5">
              <Activity className="w-3.5 h-3.5" />
              Transaction Activity
            </h4>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="bg-bg-tertiary/50 rounded-lg p-2.5">
                <span className="text-text-muted block mb-1">1h Buys / Sells</span>
                <span className="font-mono">
                  <span className="text-accent-success">{token.txnBuys1h}</span>
                  {' / '}
                  <span className="text-accent-error">{token.txnSells1h}</span>
                </span>
              </div>
              <div className="bg-bg-tertiary/50 rounded-lg p-2.5">
                <span className="text-text-muted block mb-1">24h Buys / Sells</span>
                <span className="font-mono">
                  <span className="text-accent-success">{token.txnBuys24h}</span>
                  {' / '}
                  <span className="text-accent-error">{token.txnSells24h}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Social links */}
          <div>
            <h4 className="text-xs font-semibold text-text-secondary mb-2 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5" />
              Social & Links
            </h4>
            <div className="flex flex-wrap gap-2">
              {token.twitter && (
                <a href={token.twitter} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#1DA1F2]/10 text-[#1DA1F2] text-xs font-medium hover:bg-[#1DA1F2]/20 transition-colors">
                  <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                  Twitter
                </a>
              )}
              {token.telegram && (
                <a href={token.telegram} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#0088cc]/10 text-[#0088cc] text-xs font-medium hover:bg-[#0088cc]/20 transition-colors">
                  <MessageCircle className="w-3 h-3" />
                  Telegram
                </a>
              )}
              {token.website && (
                <a href={token.website} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-bg-tertiary text-text-secondary text-xs font-medium hover:bg-bg-secondary hover:text-text-primary transition-colors">
                  <Globe className="w-3 h-3" />
                  Website
                </a>
              )}
              {!token.twitter && !token.telegram && !token.website && (
                <span className="text-xs text-text-muted italic">No social links found</span>
              )}
            </div>
          </div>

          {/* External links */}
          <div className="flex flex-wrap gap-2 pt-2 border-t border-border-primary">
            <button
              onClick={() => setShowChart((v) => !v)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-neon/10 hover:bg-accent-neon/20 border border-accent-neon/20 text-xs text-accent-neon transition-colors"
            >
              <BarChart3 className="w-3 h-3" />
              {showChart ? 'Hide Chart' : 'Show Chart'}
            </button>
            <a href={`https://dexscreener.com/solana/${token.mint}`} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-secondary border border-border-primary text-xs text-text-secondary hover:text-text-primary transition-colors">
              <ExternalLink className="w-3 h-3" />DexScreener
            </a>
            <a href={`https://bags.fm/${token.mint}`} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 text-xs text-purple-400 hover:text-purple-300 transition-colors">
              <ExternalLink className="w-3 h-3" />Trade
            </a>
            <a href={`https://solscan.io/token/${token.mint}`} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-secondary border border-border-primary text-xs text-text-secondary hover:text-text-primary transition-colors">
              <ExternalLink className="w-3 h-3" />Solscan
            </a>
            <a href={`https://birdeye.so/token/${token.mint}?chain=solana`} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-tertiary hover:bg-bg-secondary border border-border-primary text-xs text-text-secondary hover:text-text-primary transition-colors">
              <ExternalLink className="w-3 h-3" />Birdeye
            </a>
          </div>

          {/* Inline chart drawer (slides open under the card, keeps user on page) */}
          <div
            className={`overflow-hidden transition-[max-height,opacity] duration-300 ease-out ${
              showChart ? 'max-h-[420px] opacity-100 mt-3' : 'max-h-0 opacity-0'
            }`}
          >
            <div className="rounded-lg overflow-hidden border border-border-primary bg-black/70">
              <iframe
                src={`https://dexscreener.com/solana/${chartTarget}?embed=1&theme=dark&trades=0&info=0`}
                className="w-full h-[360px] border-0"
                title={`${token.symbol} chart`}
                loading="lazy"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="card-glass p-5 flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-full skeleton" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-28 skeleton" />
          <div className="h-3 w-20 skeleton" />
        </div>
        <div className="h-6 w-20 rounded-full skeleton" />
      </div>
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-full skeleton" />
        <div className="grid grid-cols-3 gap-2 flex-1">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} className="h-3 skeleton" />)}
        </div>
      </div>
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-1.5 skeleton rounded-full" />)}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main page                                                          */
/* ------------------------------------------------------------------ */

export default function BagsIntelPage() {
  const [tokens, setTokens] = useState<BagsIntelToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<FilterTier>('all');
  const [activeCategory, setActiveCategory] = useState<CategoryFilter>('all');
  const [sortKey, setSortKey] = useState<SortKey>('score');
  const [sortOpen, setSortOpen] = useState(false);
  const [howWeRateOpen, setHowWeRateOpen] = useState(false);
  const sortRef = useRef<HTMLDivElement>(null);

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
      const res = await fetch('/api/bags/intel?limit=200');
      if (!res.ok) throw new Error(`API returned ${res.status}`);
      const data = await res.json();
      setTokens(data.tokens || []);
      setLastUpdated(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch DeGen intelligence');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(true); }, [fetchData]);
  useEffect(() => {
    const id = setInterval(() => fetchData(false), REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchData]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchData(false);
    setTimeout(() => setIsRefreshing(false), 500);
  };

  const categoryFiltered = activeCategory === 'all'
    ? tokens
    : tokens.filter((t) => t.category === activeCategory);

  const filtered = activeFilter === 'all'
    ? categoryFiltered
    : categoryFiltered.filter((t) => getScoreTier(t.score) === activeFilter);
  const sorted = sortTokens(filtered, sortKey);

  const tierCounts = categoryFiltered.reduce((acc, t) => {
    const tier = getScoreTier(t.score);
    acc[tier] = (acc[tier] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const categoryCounts = tokens.reduce((acc, t) => {
    acc[t.category] = (acc[t.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Stats bar
  const totalVolume = tokens.reduce((s, t) => s + t.volume24h, 0);
  const avgScore = tokens.length > 0 ? Math.round(tokens.reduce((s, t) => s + t.score, 0) / tokens.length) : 0;
  const withSocials = tokens.filter((t) => t.twitter || t.website || t.telegram).length;

  return (
    <div className="min-h-screen flex flex-col">
      <StatusBar />

      <main className="app-shell flex-1 py-8">
        {/* Hero */}
        <section className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-2">
            <p className="text-xs text-purple-400 font-mono tracking-widest">
              BAGS ECOSYSTEM INTEL
            </p>
          </div>
          <h1 className="font-display text-3xl md:text-4xl lg:text-5xl font-bold text-text-primary mb-3">
            Bags Ecosystem
          </h1>
          <p className="text-text-secondary text-base max-w-2xl mx-auto">
            Deep-dive intelligence for Bags launches with deployer/royalty analysis,
            social signal verification, 5-dimension scoring, and one-click buying.
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

        {/* Stats bar */}
        <section className="mb-8 grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="card-glass p-4 text-center">
            <p className="text-xs text-text-muted mb-1">Tokens Tracked</p>
            <p className="text-xl font-mono font-bold text-purple-400">{tokens.length}</p>
          </div>
          <div className="card-glass p-4 text-center">
            <p className="text-xs text-text-muted mb-1">Total Volume 24h</p>
            <p className="text-xl font-mono font-bold text-text-primary">{fmtUsd(totalVolume)}</p>
          </div>
          <div className="card-glass p-4 text-center">
            <p className="text-xs text-text-muted mb-1">Avg Score</p>
            <p className="text-xl font-mono font-bold" style={{ color: TIER_CONFIG[getScoreTier(avgScore)].color }}>{avgScore}</p>
          </div>
          <div className="card-glass p-4 text-center">
            <p className="text-xs text-text-muted mb-1">With Socials</p>
            <p className="text-xl font-mono font-bold text-text-primary">{withSocials}/{tokens.length}</p>
          </div>
        </section>

        {/* How We Score */}
        <section className="mb-8">
          <div className="card-glass overflow-hidden">
            <button
              onClick={() => setHowWeRateOpen((v) => !v)}
              className="w-full p-5 flex items-center justify-between hover:bg-bg-secondary/30 transition-colors"
            >
              <h2 className="font-display font-bold text-base flex items-center gap-2 text-text-primary">
                <Info className="w-4 h-4 text-purple-400" />
                How We Score Bags Tokens
              </h2>
              <ChevronDown className={`w-4 h-4 text-text-muted transition-transform duration-200 ${howWeRateOpen ? 'rotate-180' : ''}`} />
            </button>

            {howWeRateOpen && (
              <div className="px-5 pb-5 space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                  {SCORING_DIMENSIONS.map((dim) => (
                    <div key={dim.title} className="p-4 rounded-xl border border-border-primary hover:border-purple-500/30 transition-colors bg-bg-secondary/50">
                      <div className="flex items-center gap-2 mb-2 text-purple-400">
                        <dim.icon className="w-4 h-4" />
                        <h3 className="font-semibold text-xs">{dim.title}</h3>
                      </div>
                      <p className="text-[10px] text-text-muted leading-relaxed">{dim.description}</p>
                      <p className="text-[10px] font-mono text-purple-400/70 mt-1">Weight: {dim.weight}</p>
                    </div>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-border-primary">
                  {(Object.keys(TIER_META) as ScoreTier[]).map((tier) => {
                    const { min, max, icon: Icon, color, bg } = TIER_META[tier];
                    return (
                      <div key={tier} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full ${bg} border border-border-primary`}>
                        <Icon className={`w-3 h-3 ${color}`} />
                        <span className={`text-xs font-medium capitalize ${color}`}>{tier}</span>
                        <span className="text-xs text-text-muted font-mono">{min}-{max}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </section>

        {/* Filter + Sort */}
        <section className="mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => setActiveCategory('all')}
              className={`px-3 py-2 rounded-full text-sm font-medium transition-colors border ${
                activeCategory === 'all'
                  ? 'bg-bg-tertiary text-text-primary border-border-hover'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
              title="All categories"
            >
              Categories <span className="ml-1.5 font-mono text-xs opacity-70">{tokens.length}</span>
            </button>
            {(['recent', 'aboutToGraduate', 'graduated', 'topEarners'] as const).map((cat) => {
              const label = cat === 'recent' ? 'New' : cat === 'aboutToGraduate' ? 'Near Grad' : cat === 'graduated' ? 'Graduated' : 'Earners';
              const count = categoryCounts[cat] || 0;
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-full text-sm font-medium transition-colors border ${
                    activeCategory === cat
                      ? 'bg-purple-500/15 text-purple-300 border-purple-500/40'
                      : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
                  }`}
                >
                  <span className="text-xs font-mono">{label}</span>
                  <span className="font-mono text-xs opacity-70">{count}</span>
                </button>
              );
            })}
            <span className="hidden sm:inline text-border-primary/60 select-none">|</span>
            <button
              onClick={() => setActiveFilter('all')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors border ${
                activeFilter === 'all'
                  ? 'bg-text-primary text-bg-primary border-text-primary'
                  : 'bg-transparent text-text-secondary border-border-primary hover:bg-bg-tertiary'
              }`}
            >
              All <span className="ml-1.5 font-mono text-xs opacity-70">{categoryFiltered.length}</span>
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

          <div className="relative" ref={sortRef}>
            <button
              onClick={() => setSortOpen((v) => !v)}
              className="flex items-center gap-2 px-4 py-2 rounded-full bg-bg-tertiary border border-border-primary text-sm text-text-secondary hover:text-text-primary hover:border-border-hover transition-colors"
            >
              <ArrowUpDown className="w-3.5 h-3.5" />
              {SORT_OPTIONS.find((o) => o.value === sortKey)?.label}
              <ChevronDown className={`w-3 h-3 transition-transform ${sortOpen ? 'rotate-180' : ''}`} />
            </button>
            {sortOpen && (
              <div className="absolute right-0 mt-2 w-40 card-glass rounded-xl overflow-hidden z-20 shadow-lg">
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => { setSortKey(opt.value); setSortOpen(false); }}
                    className={`w-full text-left px-4 py-2.5 text-sm transition-colors ${
                      sortKey === opt.value
                        ? 'text-purple-400 bg-purple-500/10'
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

        {/* Error */}
        {error && (
          <div className="mb-6 bg-accent-error/10 border border-accent-error/30 rounded-xl p-4 text-accent-error text-sm font-mono">
            {error}
          </div>
        )}

        {/* Token grid */}
        <section>
          {loading ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {Array.from({ length: 6 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : sorted.length === 0 ? (
            <div className="text-center py-20">
              <div className="card-glass p-12 max-w-md mx-auto">
                <Flame className="w-12 h-12 text-purple-400/50 mx-auto mb-4" />
                <h3 className="font-display font-bold text-xl mb-2 text-text-primary">
                  {activeFilter === 'all' ? 'No bags tokens found' : `No ${activeFilter} bags tokens`}
                </h3>
                <p className="text-text-muted text-sm">
                  {activeFilter === 'all' && activeCategory === 'all'
                    ? 'No tokens were returned from upstream. Try refreshing.'
                    : 'Try a different filter or check back soon.'}
                </p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {sorted.map((token) => (
                <TokenCard key={token.mint} token={token} />
              ))}
            </div>
          )}
        </section>

        {/* Footer */}
        <footer className="mt-16 pb-8 text-center">
          <p className="text-xs text-text-muted font-mono">
            Powered by KR8TIV AI &middot; Data via Jupiter Datapi &middot;
            Auto-refreshes every 30s
          </p>
        </footer>
      </main>
    </div>
  );
}

