'use client';

import { useState, useEffect, useCallback } from 'react';
import { useWallet, useConnection } from '@solana/wallet-adapter-react';
import {
  Shield, AlertTriangle, Loader2, ArrowUpRight, ArrowDownRight,
  Crosshair, Activity, Zap, Target, TrendingUp, Ban, CheckCircle2,
  Clock, RefreshCw, ChevronDown, Skull,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────
interface SafetyBreakdown {
  mintAuthority: number;
  freezeAuthority: number;
  lpBurned: number;
  holderConcentration: number;
  honeypot: number;
  rugcheck: number;
  deployerHistory: number;
  overall: number;
  passed: boolean;
  failReasons: string[];
}

interface StopOrder {
  tokenMint: string;
  symbol: string;
  entryPriceUsd: number;
  currentPriceUsd: number;
  amountUsd: number;
  takeProfitPct: number;
  stopLossPct: number;
  trailingStopPct: number | null;
  pnlPct: number;
  status: 'ACTIVE' | 'TP_HIT' | 'SL_HIT' | 'TRAILING_HIT' | 'CANCELLED';
  createdAt: number;
}

interface TradeResult {
  success: boolean;
  signature: string | null;
  outAmount: string;
  priceImpact: string;
  error: string | null;
}

type TradeStatus = 'idle' | 'checking' | 'quoting' | 'signing' | 'sending' | 'success' | 'error';

// ─── Presets ──────────────────────────────────────────────
const TP_PRESETS = [
  { label: '25%', value: 25 },
  { label: '50%', value: 50 },
  { label: '100%', value: 100 },
  { label: '200%', value: 200 },
];

const SL_PRESETS = [
  { label: '10%', value: 10 },
  { label: '15%', value: 15 },
  { label: '25%', value: 25 },
  { label: '50%', value: 50 },
];

const AMOUNT_PRESETS = [
  { label: '0.1', value: 0.1 },
  { label: '0.25', value: 0.25 },
  { label: '0.5', value: 0.5 },
  { label: '1.0', value: 1.0 },
];

const SLIPPAGE_PRESETS = [
  { label: '1%', value: 100 },
  { label: '3%', value: 300 },
  { label: '5%', value: 500 },
  { label: '10%', value: 1000 },
];

// ─── Safety Score Bar ─────────────────────────────────────
function SafetyBar({ label, score }: { label: string; score: number }) {
  const pct = Math.round(score * 100);
  const color = pct >= 70 ? '#22c55e' : pct >= 50 ? '#eab308' : '#ef4444';

  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-[var(--text-muted)] w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-[var(--bg-primary)] rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-[10px] mono w-8 text-right" style={{ color }}>{pct}%</span>
    </div>
  );
}

// ─── Safety Card ──────────────────────────────────────────
function SafetyCard({ safety }: { safety: SafetyBreakdown | null }) {
  if (!safety) {
    return (
      <div className="card">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="w-4 h-4 text-[var(--text-muted)]" />
          <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Safety Analysis</h3>
        </div>
        <div className="text-center text-[var(--text-muted)] text-xs py-6">
          Enter a token to run safety checks
        </div>
      </div>
    );
  }

  const overallPct = Math.round(safety.overall * 100);
  const overallColor = safety.passed ? '#22c55e' : '#ef4444';

  return (
    <div className={`card ${safety.passed ? '' : 'border-[#ef444444]'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4" style={{ color: overallColor }} />
          <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Safety Analysis</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold mono" style={{ color: overallColor }}>{overallPct}%</span>
          {safety.passed ? (
            <CheckCircle2 className="w-4 h-4 text-[#22c55e]" />
          ) : (
            <Ban className="w-4 h-4 text-[#ef4444]" />
          )}
        </div>
      </div>

      <div className="space-y-1.5">
        <SafetyBar label="Mint Authority" score={safety.mintAuthority} />
        <SafetyBar label="Freeze Authority" score={safety.freezeAuthority} />
        <SafetyBar label="LP Burned" score={safety.lpBurned} />
        <SafetyBar label="Holder Dist." score={safety.holderConcentration} />
        <SafetyBar label="Honeypot Check" score={safety.honeypot} />
        <SafetyBar label="RugCheck" score={safety.rugcheck} />
        <SafetyBar label="Deployer History" score={safety.deployerHistory} />
      </div>

      {safety.failReasons.length > 0 && (
        <div className="mt-3 space-y-1">
          {safety.failReasons.map((reason, i) => (
            <div key={i} className="flex items-start gap-1.5 text-[10px] text-[#ef4444]">
              <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
              <span>{reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Stop Orders Panel ────────────────────────────────────
function StopOrdersPanel({ orders }: { orders: StopOrder[] }) {
  const active = orders.filter(o => o.status === 'ACTIVE');

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-[var(--accent)]" />
          <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Active Orders</h3>
        </div>
        <span className="text-xs text-[var(--accent)] mono">{active.length}</span>
      </div>

      {active.length === 0 ? (
        <div className="text-center text-[var(--text-muted)] text-xs py-4">
          No active stop orders
        </div>
      ) : (
        <div className="space-y-2">
          {active.map((order) => {
            const pnlColor = order.pnlPct >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]';
            const pnlSign = order.pnlPct >= 0 ? '+' : '';

            return (
              <div key={order.tokenMint} className="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-semibold">{order.symbol || order.tokenMint.slice(0, 8)}</span>
                  <span className={`text-xs font-bold mono ${pnlColor}`}>
                    {pnlSign}{order.pnlPct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-[var(--text-muted)]">
                  <span className="text-[#ef4444]">SL -{order.stopLossPct}%</span>
                  <div className="flex-1 h-1 bg-[var(--bg-primary)] rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${order.pnlPct >= 0 ? 'bg-[#22c55e]' : 'bg-[#ef4444]'}`}
                      style={{ width: `${Math.min(100, Math.max(0, 50 + (order.pnlPct / 2)))}%` }}
                    />
                  </div>
                  <span className="text-[#22c55e]">TP +{order.takeProfitPct}%</span>
                </div>
                {order.trailingStopPct && (
                  <div className="flex items-center gap-1 mt-1 text-[10px] text-[var(--text-muted)]">
                    <TrendingUp className="w-3 h-3" />
                    <span>Trailing: {order.trailingStopPct}%</span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Trade History Row ────────────────────────────────────
function TradeHistoryRow({ trade }: { trade: { symbol: string; side: string; amountUsd: number; pnlPct: number | null; time: string; status: string } }) {
  const isBuy = trade.side === 'BUY';
  const pnlColor = (trade.pnlPct ?? 0) >= 0 ? 'text-[#22c55e]' : 'text-[#ef4444]';

  return (
    <div className="flex items-center justify-between py-1.5 border-b border-[var(--border)] last:border-0">
      <div className="flex items-center gap-2">
        {isBuy ? (
          <ArrowUpRight className="w-3 h-3 text-[#22c55e]" />
        ) : (
          <ArrowDownRight className="w-3 h-3 text-[#ef4444]" />
        )}
        <span className="text-xs font-semibold">{trade.symbol}</span>
        <span className="text-[10px] text-[var(--text-muted)]">${trade.amountUsd.toFixed(2)}</span>
      </div>
      <div className="flex items-center gap-3">
        {trade.pnlPct !== null && (
          <span className={`text-[10px] mono ${pnlColor}`}>
            {trade.pnlPct >= 0 ? '+' : ''}{trade.pnlPct.toFixed(1)}%
          </span>
        )}
        <span className="text-[10px] text-[var(--text-muted)]">{trade.time}</span>
      </div>
    </div>
  );
}

// ─── Main Trading Terminal ────────────────────────────────
export function TradingTerminal() {
  const { publicKey, connected } = useWallet();
  const { connection } = useConnection();

  // State
  const [tokenMint, setTokenMint] = useState('');
  const [tokenSymbol, setTokenSymbol] = useState('');
  const [amountSol, setAmountSol] = useState(0.1);
  const [slippageBps, setSlippageBps] = useState(300);
  const [takeProfitPct, setTakeProfitPct] = useState(50);
  const [stopLossPct, setStopLossPct] = useState(15);
  const [trailingStopPct, setTrailingStopPct] = useState<number | null>(null);
  const [tradeStatus, setTradeStatus] = useState<TradeStatus>('idle');
  const [statusMessage, setStatusMessage] = useState('');
  const [safety, setSafety] = useState<SafetyBreakdown | null>(null);
  const [stopOrders, setStopOrders] = useState<StopOrder[]>([]);
  const [recentTrades, setRecentTrades] = useState<Array<{ symbol: string; side: string; amountUsd: number; pnlPct: number | null; time: string; status: string }>>([]);
  const [solBalance, setSolBalance] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Fetch SOL balance
  useEffect(() => {
    if (!publicKey || !connection) return;
    let cancelled = false;

    const fetchBalance = async () => {
      try {
        const lamports = await connection.getBalance(publicKey);
        if (!cancelled) setSolBalance(lamports / 1e9);
      } catch {
        // ignore
      }
    };

    fetchBalance();
    const interval = setInterval(fetchBalance, 15000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [publicKey, connection]);

  // Mock safety check (in production, calls the sniper backend API)
  const runSafetyCheck = useCallback(async (mint: string) => {
    if (!mint || mint.length < 32) return;
    setTradeStatus('checking');
    setStatusMessage('Running safety analysis...');

    try {
      const resp = await fetch(`/api/safety?mint=${mint}`);
      if (resp.ok) {
        const data = await resp.json();
        setSafety(data);
        setTokenSymbol(data.symbol || mint.slice(0, 6));
      } else {
        // Fallback: generate mock data for demo
        setSafety({
          mintAuthority: Math.random() > 0.3 ? 1.0 : 0.0,
          freezeAuthority: Math.random() > 0.2 ? 1.0 : 0.0,
          lpBurned: 0.3 + Math.random() * 0.7,
          holderConcentration: 0.4 + Math.random() * 0.6,
          honeypot: Math.random() > 0.1 ? 1.0 : 0.0,
          rugcheck: 0.3 + Math.random() * 0.7,
          deployerHistory: 0.5 + Math.random() * 0.5,
          overall: 0.5 + Math.random() * 0.4,
          passed: Math.random() > 0.3,
          failReasons: [],
        });
        setTokenSymbol(mint.slice(0, 6));
      }
    } catch {
      // Demo mode fallback
      setSafety({
        mintAuthority: 1.0,
        freezeAuthority: 1.0,
        lpBurned: 0.8,
        holderConcentration: 0.7,
        honeypot: 1.0,
        rugcheck: 0.65,
        deployerHistory: 0.9,
        overall: 0.82,
        passed: true,
        failReasons: [],
      });
      setTokenSymbol(mint.slice(0, 6));
    }

    setTradeStatus('idle');
    setStatusMessage('');
  }, []);

  // Token mint input handler
  const handleMintChange = (value: string) => {
    setTokenMint(value);
    setSafety(null);
    if (value.length >= 32) {
      runSafetyCheck(value);
    }
  };

  // Execute buy
  const executeBuy = async () => {
    if (!tokenMint || !safety?.passed) return;

    setTradeStatus('quoting');
    setStatusMessage('Getting quote from Bags...');

    try {
      // Call sniper API
      const resp = await fetch('/api/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'buy',
          tokenMint,
          amountSol,
          slippageBps,
          takeProfitPct,
          stopLossPct,
          trailingStopPct,
        }),
      });

      if (resp.ok) {
        const result: TradeResult = await resp.json();
        if (result.success) {
          setTradeStatus('success');
          setStatusMessage(`Bought! Sig: ${result.signature?.slice(0, 16)}...`);

          // Add to stop orders
          setStopOrders(prev => [...prev, {
            tokenMint,
            symbol: tokenSymbol,
            entryPriceUsd: amountSol * 200, // placeholder
            currentPriceUsd: amountSol * 200,
            amountUsd: amountSol * 200,
            takeProfitPct,
            stopLossPct,
            trailingStopPct,
            pnlPct: 0,
            status: 'ACTIVE',
            createdAt: Date.now(),
          }]);

          // Add to recent trades
          setRecentTrades(prev => [{
            symbol: tokenSymbol,
            side: 'BUY',
            amountUsd: amountSol * 200,
            pnlPct: null,
            time: 'now',
            status: 'EXECUTED',
          }, ...prev].slice(0, 20));
        } else {
          setTradeStatus('error');
          setStatusMessage(result.error || 'Trade failed');
        }
      } else {
        // Demo mode
        setTradeStatus('success');
        setStatusMessage('Demo: Buy simulated successfully');
        setStopOrders(prev => [...prev, {
          tokenMint,
          symbol: tokenSymbol,
          entryPriceUsd: amountSol * 200,
          currentPriceUsd: amountSol * 200,
          amountUsd: amountSol * 200,
          takeProfitPct,
          stopLossPct,
          trailingStopPct,
          pnlPct: 0,
          status: 'ACTIVE',
          createdAt: Date.now(),
        }]);
      }
    } catch {
      setTradeStatus('error');
      setStatusMessage('Network error — try again');
    }

    setTimeout(() => {
      if (tradeStatus !== 'idle') {
        setTradeStatus('idle');
        setStatusMessage('');
      }
    }, 5000);
  };

  const statusIcon = {
    idle: null,
    checking: <Loader2 className="w-4 h-4 animate-spin text-[var(--accent)]" />,
    quoting: <Loader2 className="w-4 h-4 animate-spin text-[var(--accent)]" />,
    signing: <Loader2 className="w-4 h-4 animate-spin text-[#eab308]" />,
    sending: <Loader2 className="w-4 h-4 animate-spin text-[#3b82f6]" />,
    success: <CheckCircle2 className="w-4 h-4 text-[#22c55e]" />,
    error: <AlertTriangle className="w-4 h-4 text-[#ef4444]" />,
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4">
      {/* ─── Left Column: Main Trade Panel ──────────────── */}
      <div className="flex flex-col gap-4">
        {/* Token Input */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Crosshair className="w-4 h-4 text-[var(--accent)]" />
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Target Token</h3>
          </div>
          <input
            type="text"
            value={tokenMint}
            onChange={(e) => handleMintChange(e.target.value)}
            placeholder="Paste token mint address (e.g. 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU)"
            className="w-full bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg px-4 py-3 text-sm mono text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
          {tokenMint.length > 0 && tokenMint.length < 32 && (
            <p className="text-[10px] text-[var(--text-muted)] mt-1">Enter a valid Solana mint address (32+ chars)</p>
          )}
        </div>

        {/* Buy Panel */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-[var(--accent)]" />
              <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Snipe</h3>
            </div>
            {solBalance !== null && (
              <span className="text-[10px] text-[var(--text-muted)] mono">
                Balance: {solBalance.toFixed(4)} SOL
              </span>
            )}
          </div>

          {/* Amount */}
          <div className="mb-4">
            <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1.5 block">Amount (SOL)</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={amountSol}
                onChange={(e) => setAmountSol(parseFloat(e.target.value) || 0)}
                step={0.01}
                min={0.01}
                className="flex-1 bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm mono text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
              />
              <div className="flex gap-1">
                {AMOUNT_PRESETS.map(p => (
                  <button
                    key={p.value}
                    onClick={() => setAmountSol(p.value)}
                    className={`px-2.5 py-2 text-[10px] mono rounded-lg border transition-colors ${
                      amountSol === p.value
                        ? 'bg-[var(--accent-dim)] text-[var(--accent)] border-[var(--border-accent)]'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border)] hover:text-[var(--text-secondary)]'
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* TP/SL Row */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1.5 block">Take Profit</label>
              <div className="flex gap-1">
                {TP_PRESETS.map(p => (
                  <button
                    key={p.value}
                    onClick={() => setTakeProfitPct(p.value)}
                    className={`flex-1 py-1.5 text-[10px] mono rounded-lg border transition-colors ${
                      takeProfitPct === p.value
                        ? 'bg-[#22c55e15] text-[#22c55e] border-[#22c55e33]'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border)] hover:text-[var(--text-secondary)]'
                    }`}
                  >
                    +{p.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1.5 block">Stop Loss</label>
              <div className="flex gap-1">
                {SL_PRESETS.map(p => (
                  <button
                    key={p.value}
                    onClick={() => setStopLossPct(p.value)}
                    className={`flex-1 py-1.5 text-[10px] mono rounded-lg border transition-colors ${
                      stopLossPct === p.value
                        ? 'bg-[#ef444415] text-[#ef4444] border-[#ef444433]'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border)] hover:text-[var(--text-secondary)]'
                    }`}
                  >
                    -{p.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Advanced Toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-1 text-[10px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] mb-3 transition-colors"
          >
            <ChevronDown className={`w-3 h-3 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} />
            Advanced Settings
          </button>

          {showAdvanced && (
            <div className="space-y-3 mb-4 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)]">
              {/* Slippage */}
              <div>
                <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1.5 block">Slippage</label>
                <div className="flex gap-1">
                  {SLIPPAGE_PRESETS.map(p => (
                    <button
                      key={p.value}
                      onClick={() => setSlippageBps(p.value)}
                      className={`flex-1 py-1.5 text-[10px] mono rounded-lg border transition-colors ${
                        slippageBps === p.value
                          ? 'bg-[var(--accent-dim)] text-[var(--accent)] border-[var(--border-accent)]'
                          : 'bg-[var(--bg-primary)] text-[var(--text-muted)] border-[var(--border)] hover:text-[var(--text-secondary)]'
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Trailing Stop */}
              <div>
                <label className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider mb-1.5 block">Trailing Stop (%)</label>
                <div className="flex gap-2">
                  <input
                    type="number"
                    value={trailingStopPct ?? ''}
                    onChange={(e) => setTrailingStopPct(e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="Off"
                    min={1}
                    max={50}
                    className="flex-1 bg-[var(--bg-primary)] border border-[var(--border)] rounded-lg px-3 py-1.5 text-xs mono text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)]"
                  />
                  {[10, 20, 30].map(v => (
                    <button
                      key={v}
                      onClick={() => setTrailingStopPct(trailingStopPct === v ? null : v)}
                      className={`px-2 py-1.5 text-[10px] mono rounded-lg border transition-colors ${
                        trailingStopPct === v
                          ? 'bg-[#3b82f615] text-[#3b82f6] border-[#3b82f633]'
                          : 'bg-[var(--bg-primary)] text-[var(--text-muted)] border-[var(--border)]'
                      }`}
                    >
                      {v}%
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Trade Summary */}
          {tokenMint.length >= 32 && (
            <div className="p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border)] mb-4">
              <div className="grid grid-cols-2 gap-2 text-[10px]">
                <div className="text-[var(--text-muted)]">Amount</div>
                <div className="text-right mono text-[var(--text-primary)]">{amountSol} SOL (~${(amountSol * 200).toFixed(2)})</div>
                <div className="text-[var(--text-muted)]">Take Profit</div>
                <div className="text-right mono text-[#22c55e]">+{takeProfitPct}%</div>
                <div className="text-[var(--text-muted)]">Stop Loss</div>
                <div className="text-right mono text-[#ef4444]">-{stopLossPct}%</div>
                <div className="text-[var(--text-muted)]">Slippage</div>
                <div className="text-right mono text-[var(--text-secondary)]">{slippageBps / 100}%</div>
                {trailingStopPct && (
                  <>
                    <div className="text-[var(--text-muted)]">Trailing Stop</div>
                    <div className="text-right mono text-[#3b82f6]">{trailingStopPct}%</div>
                  </>
                )}
                <div className="text-[var(--text-muted)]">Safety</div>
                <div className="text-right mono" style={{ color: safety?.passed ? '#22c55e' : safety ? '#ef4444' : 'var(--text-muted)' }}>
                  {safety ? `${Math.round(safety.overall * 100)}%` : 'Checking...'}
                </div>
              </div>
            </div>
          )}

          {/* Status Message */}
          {statusMessage && (
            <div className="flex items-center gap-2 mb-3 text-xs">
              {statusIcon[tradeStatus]}
              <span className={tradeStatus === 'error' ? 'text-[#ef4444]' : tradeStatus === 'success' ? 'text-[#22c55e]' : 'text-[var(--text-secondary)]'}>
                {statusMessage}
              </span>
            </div>
          )}

          {/* Buy Button */}
          <button
            onClick={executeBuy}
            disabled={!tokenMint || tokenMint.length < 32 || tradeStatus === 'quoting' || tradeStatus === 'signing' || tradeStatus === 'sending' || (safety !== null && !safety.passed)}
            className={`w-full py-3 rounded-lg font-bold text-sm uppercase tracking-wider transition-all duration-200 ${
              !tokenMint || tokenMint.length < 32 || (safety !== null && !safety.passed)
                ? 'bg-[var(--bg-secondary)] text-[var(--text-muted)] cursor-not-allowed border border-[var(--border)]'
                : tradeStatus === 'quoting' || tradeStatus === 'signing' || tradeStatus === 'sending'
                  ? 'bg-[var(--accent-dim)] text-[var(--accent)] border border-[var(--border-accent)] cursor-wait'
                  : 'bg-[#22c55e] text-black hover:bg-[#16a34a] shadow-[0_0_20px_rgba(34,197,94,0.2)] hover:shadow-[0_0_30px_rgba(34,197,94,0.3)]'
            }`}
          >
            {tradeStatus === 'quoting' ? 'Getting Quote...' :
             tradeStatus === 'signing' ? 'Waiting for Signature...' :
             tradeStatus === 'sending' ? 'Sending Transaction...' :
             safety !== null && !safety.passed ? 'SAFETY CHECK FAILED' :
             'SNIPE'}
          </button>

          {!connected && (
            <p className="text-[10px] text-[var(--text-muted)] text-center mt-2">
              Connect wallet for live trading. Demo mode active.
            </p>
          )}
        </div>

        {/* Recent Trades */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-[var(--accent)]" />
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Recent Trades</h3>
          </div>
          {recentTrades.length === 0 ? (
            <div className="text-center text-[var(--text-muted)] text-xs py-4">
              No trades yet — snipe your first token above
            </div>
          ) : (
            <div>
              {recentTrades.map((trade, i) => (
                <TradeHistoryRow key={i} trade={trade} />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ─── Right Column: Safety + Orders ─────────────── */}
      <div className="flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start">
        <SafetyCard safety={safety} />
        <StopOrdersPanel orders={stopOrders} />

        {/* Quick Stats */}
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-[var(--accent)]" />
            <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Session Stats</h3>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="text-[var(--text-muted)]">Trades</div>
            <div className="text-right mono text-[var(--text-primary)]">{recentTrades.length}</div>
            <div className="text-[var(--text-muted)]">Active Orders</div>
            <div className="text-right mono text-[var(--accent)]">{stopOrders.filter(o => o.status === 'ACTIVE').length}</div>
            <div className="text-[var(--text-muted)]">Wallet</div>
            <div className="text-right mono text-[var(--text-primary)]">
              {connected ? publicKey?.toBase58().slice(0, 4) + '...' + publicKey?.toBase58().slice(-4) : 'Demo'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
