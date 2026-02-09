'use client';

import { useState, useEffect } from 'react';
import { Settings, Zap, Shield, Target, TrendingUp, ChevronDown, ChevronUp, Crosshair, AlertTriangle, Wallet, Lock, Unlock, DollarSign } from 'lucide-react';
import { useSniperStore, type SniperConfig } from '@/stores/useSniperStore';
import { usePhantomWallet } from '@/hooks/usePhantomWallet';

const BUDGET_PRESETS = [0.1, 0.2, 0.5, 1.0];

export function SniperControls() {
  const { config, setConfig, loadBestEver, positions, budget, setBudgetSol, authorizeBudget, deauthorizeBudget, budgetRemaining } = useSniperStore();
  const { connected } = usePhantomWallet();
  const [expanded, setExpanded] = useState(true);
  const [bestEverLoaded, setBestEverLoaded] = useState(false);
  const [customBudget, setCustomBudget] = useState('');
  const [budgetFocused, setBudgetFocused] = useState(false);

  // Load BEST_EVER on mount
  useEffect(() => {
    loadBestEverConfig();
  }, []);

  async function loadBestEverConfig() {
    try {
      const res = await fetch('/api/best-ever');
      if (res.ok) {
        const data = await res.json();
        if (data.config) {
          loadBestEver(data.config);
          setBestEverLoaded(true);
        }
      }
    } catch {
      // Fallback — use defaults
    }
  }

  const openPositionCount = positions.filter(p => p.status === 'open').length;
  const atCapacity = openPositionCount >= config.maxConcurrentPositions;
  const remaining = budgetRemaining();
  const perSnipeSol = budget.budgetSol > 0
    ? Math.round((budget.budgetSol / config.maxConcurrentPositions) * 100) / 100
    : 0;

  function handleBudgetPreset(sol: number) {
    setBudgetSol(sol);
    setCustomBudget('');
  }

  function commitCustomBudget() {
    const v = parseFloat(customBudget);
    if (!isNaN(v) && v > 0 && v <= 100) {
      setBudgetSol(v);
    }
    setBudgetFocused(false);
  }

  function handleAuthorize() {
    if (budget.authorized) {
      deauthorizeBudget();
    } else {
      authorizeBudget();
    }
  }

  return (
    <div className="card-glass p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-accent-neon" />
          <h2 className="font-display text-sm font-semibold">Sniper Strategy</h2>
        </div>
        {bestEverLoaded && (
          <span className="text-[9px] font-mono text-accent-neon bg-accent-neon/10 px-2 py-0.5 rounded-full border border-accent-neon/20">
            BEST_EVER LOADED
          </span>
        )}
      </div>

      {!connected && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-warning/10 border border-accent-warning/20 mb-4">
          <AlertTriangle className="w-4 h-4 text-accent-warning flex-shrink-0" />
          <span className="text-[11px] text-accent-warning">Connect wallet to enable trading</span>
        </div>
      )}

      {/* ─── SOL BUDGET SECTION ─── */}
      <div className="p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Wallet className="w-3.5 h-3.5 text-accent-neon" />
          <span className="text-xs font-semibold">Snipe Budget</span>
          {budget.authorized && (
            <span className="ml-auto text-[9px] font-mono text-accent-neon bg-accent-neon/10 px-1.5 py-0.5 rounded-full border border-accent-neon/20 flex items-center gap-1">
              <Unlock className="w-2.5 h-2.5" /> AUTHORIZED
            </span>
          )}
        </div>

        {/* Quick-select buttons */}
        <div className="flex gap-1.5 mb-3">
          {BUDGET_PRESETS.map((sol) => (
            <button
              key={sol}
              onClick={() => handleBudgetPreset(sol)}
              disabled={budget.authorized}
              className={`flex-1 text-[11px] font-mono font-bold py-2 rounded-lg transition-all ${
                budget.budgetSol === sol && !budgetFocused
                  ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
                  : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
              } ${budget.authorized ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              {sol} SOL
            </button>
          ))}
        </div>

        {/* Custom amount input */}
        <div className="flex items-center gap-2 mb-3">
          <div className={`flex-1 flex items-center gap-2 p-2 rounded-lg bg-bg-tertiary border transition-all ${
            budgetFocused ? 'border-accent-neon/40' : 'border-border-primary'
          }`}>
            <DollarSign className="w-3 h-3 text-text-muted" />
            <input
              type="text"
              inputMode="decimal"
              placeholder="Custom amount..."
              value={budgetFocused ? customBudget : (customBudget || '')}
              disabled={budget.authorized}
              onFocus={() => setBudgetFocused(true)}
              onBlur={() => commitCustomBudget()}
              onChange={(e) => setCustomBudget(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') commitCustomBudget(); }}
              className="flex-1 bg-transparent text-xs font-mono text-text-primary outline-none placeholder:text-text-muted/40 disabled:opacity-50"
            />
            <span className="text-[10px] text-text-muted font-mono">SOL</span>
          </div>
        </div>

        {/* Budget summary */}
        <div className="flex items-center justify-between text-[10px] font-mono mb-3 px-1">
          <div className="flex flex-col gap-0.5">
            <span className="text-text-muted">Total Budget</span>
            <span className="text-text-primary font-bold text-xs">{budget.budgetSol} SOL</span>
          </div>
          <div className="flex flex-col gap-0.5 text-center">
            <span className="text-text-muted">Per Snipe</span>
            <span className="text-text-primary font-bold text-xs">~{perSnipeSol} SOL</span>
          </div>
          <div className="flex flex-col gap-0.5 text-right">
            <span className="text-text-muted">Remaining</span>
            <span className={`font-bold text-xs ${remaining > 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
              {budget.authorized ? `${remaining} SOL` : '—'}
            </span>
          </div>
        </div>

        {/* Recommended note */}
        <div className="text-[9px] text-text-muted/60 mb-3 px-1">
          Recommended: 0.5 SOL for testing, 1-2 SOL for active sniping
        </div>

        {/* Authorize / Deauthorize button */}
        <button
          onClick={handleAuthorize}
          disabled={!connected || budget.budgetSol <= 0}
          className={`w-full py-2.5 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-2 ${
            budget.authorized
              ? 'bg-accent-error/15 text-accent-error border border-accent-error/30 hover:bg-accent-error/25'
              : 'bg-accent-neon text-black hover:bg-accent-neon/90'
          } ${(!connected || budget.budgetSol <= 0) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          {budget.authorized ? (
            <><Lock className="w-3.5 h-3.5" /> Revoke Authorization</>
          ) : (
            <><Unlock className="w-3.5 h-3.5" /> Authorize {budget.budgetSol} SOL</>
          )}
        </button>
      </div>

      {/* Auto-Snipe Toggle */}
      <div className="flex items-center justify-between p-3 rounded-lg bg-bg-secondary border border-border-primary mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
            config.autoSnipe ? 'bg-accent-neon/15 text-accent-neon' : 'bg-bg-tertiary text-text-muted'
          }`}>
            <Crosshair className="w-4 h-4" />
          </div>
          <div>
            <span className="text-sm font-semibold">Auto-Snipe</span>
            <p className="text-[10px] text-text-muted">
              {!budget.authorized
                ? 'Authorize a budget to enable'
                : config.autoSnipe
                  ? 'Buying tokens above score threshold'
                  : 'Manual mode — click to snipe'}
            </p>
          </div>
        </div>
        <button
          onClick={() => setConfig({ autoSnipe: !config.autoSnipe })}
          disabled={!connected || !budget.authorized}
          className={`relative w-12 h-6 rounded-full transition-all duration-300 ${
            config.autoSnipe ? 'bg-accent-neon' : 'bg-bg-tertiary border border-border-primary'
          } ${(!connected || !budget.authorized) ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <span className={`absolute top-0.5 w-5 h-5 rounded-full transition-all duration-300 ${
            config.autoSnipe
              ? 'left-[26px] bg-black'
              : 'left-0.5 bg-text-muted'
          }`} />
        </button>
      </div>

      {atCapacity && (
        <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/20 mb-4">
          <AlertTriangle className="w-4 h-4 text-accent-error flex-shrink-0" />
          <span className="text-[11px] text-accent-error">
            At max capacity ({openPositionCount}/{config.maxConcurrentPositions})
          </span>
        </div>
      )}

      {/* Config Section */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center justify-between w-full text-xs text-text-muted hover:text-text-secondary transition-colors mb-3"
      >
        <span className="font-medium uppercase tracking-wider">Parameters</span>
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>

      {expanded && (
        <div className="space-y-3 animate-fade-in">
          <div className="grid grid-cols-2 gap-3">
            <ConfigField
              icon={<Shield className="w-3.5 h-3.5 text-accent-error" />}
              label="Stop Loss"
              value={config.stopLossPct}
              suffix="%"
              onChange={(v) => setConfig({ stopLossPct: v })}
              min={1}
              max={50}
            />
            <ConfigField
              icon={<Target className="w-3.5 h-3.5 text-accent-neon" />}
              label="Take Profit"
              value={config.takeProfitPct}
              suffix="%"
              onChange={(v) => setConfig({ takeProfitPct: v })}
              min={5}
              max={500}
            />
            <ConfigField
              icon={<TrendingUp className="w-3.5 h-3.5 text-accent-warning" />}
              label="Trailing Stop"
              value={config.trailingStopPct}
              suffix="%"
              onChange={(v) => setConfig({ trailingStopPct: v })}
              min={1}
              max={30}
            />
            <ConfigField
              icon={<Zap className="w-3.5 h-3.5 text-accent-neon" />}
              label="Per-Snipe Size"
              value={config.maxPositionSol}
              suffix=" SOL"
              onChange={(v) => setConfig({ maxPositionSol: v })}
              min={0.01}
              max={50}
              step={0.01}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <ConfigField
              label="Min Score"
              value={config.minScore}
              onChange={(v) => setConfig({ minScore: v })}
              min={0}
              max={100}
            />
            <ConfigField
              label="Max Positions"
              value={config.maxConcurrentPositions}
              onChange={(v) => setConfig({ maxConcurrentPositions: v })}
              min={1}
              max={50}
            />
          </div>

          {/* Jito Toggle */}
          <div className="flex items-center justify-between p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
            <div className="flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-accent-neon" />
              <span className="text-xs font-medium">Jito MEV Protection</span>
            </div>
            <button
              onClick={() => setConfig({ useJito: !config.useJito })}
              className={`relative w-10 h-5 rounded-full transition-all ${
                config.useJito ? 'bg-accent-neon' : 'bg-bg-tertiary border border-border-primary'
              }`}
            >
              <span className={`absolute top-0.5 w-4 h-4 rounded-full transition-all ${
                config.useJito ? 'left-[22px] bg-black' : 'left-0.5 bg-text-muted'
              }`} />
            </button>
          </div>

          {/* Slippage */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-text-muted">Slippage</span>
            <div className="flex gap-1">
              {[100, 150, 300, 500].map((bps) => (
                <button
                  key={bps}
                  onClick={() => setConfig({ slippageBps: bps })}
                  className={`text-[10px] font-mono px-2 py-1 rounded transition-all ${
                    config.slippageBps === bps
                      ? 'bg-accent-neon/15 text-accent-neon border border-accent-neon/30'
                      : 'bg-bg-tertiary text-text-muted border border-border-primary hover:border-border-hover'
                  }`}
                >
                  {(bps / 100).toFixed(1)}%
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ConfigField({
  icon,
  label,
  value,
  suffix = '',
  onChange,
  min = 0,
  max = 100,
  step = 1,
}: {
  icon?: React.ReactNode;
  label: string;
  value: number;
  suffix?: string;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  // Display rounded to 2 decimal places
  const displayValue = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
  const [localValue, setLocalValue] = useState(displayValue);
  const [focused, setFocused] = useState(false);

  // Sync from parent when not focused
  useEffect(() => {
    if (!focused) {
      const dv = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
      setLocalValue(dv);
    }
  }, [value, focused]);

  const commit = (raw: string) => {
    const v = parseFloat(raw);
    if (!isNaN(v) && v >= min && v <= max) {
      onChange(Math.round(v * 100) / 100);
    } else {
      const dv = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
      setLocalValue(dv);
    }
  };

  return (
    <div className="flex flex-col gap-1.5 p-2.5 rounded-lg bg-bg-secondary border border-border-primary">
      <div className="flex items-center gap-1.5">
        {icon}
        <span className="text-[10px] text-text-muted uppercase tracking-wider">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <input
          type="text"
          inputMode="decimal"
          value={localValue}
          onFocus={() => setFocused(true)}
          onBlur={() => { setFocused(false); commit(localValue); }}
          onChange={(e) => setLocalValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') commit(localValue); }}
          className="w-full bg-transparent text-sm font-mono font-bold text-text-primary outline-none"
        />
        {suffix && <span className="text-[10px] text-text-muted font-mono whitespace-nowrap">{suffix}</span>}
      </div>
    </div>
  );
}
