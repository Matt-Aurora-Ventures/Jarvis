'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronUp,
  Play,
  Loader2,
  Trash2,
  Download,
  FlaskConical,
  Copy,
  AlertTriangle,
} from 'lucide-react';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';
import { useBacktest, type BacktestDataScale, type BacktestSummary } from '@/hooks/useBacktest';

// ─── Helpers ────────────────────────────────────────────────────────────────

function winRateColor(wr: string): string {
  const val = parseFloat(wr);
  if (isNaN(val)) return 'text-text-muted';
  if (val >= 55) return 'text-accent-success';
  if (val >= 45) return 'text-accent-warning';
  return 'text-accent-error';
}

function sharpeColor(s: string): string {
  const val = parseFloat(s);
  if (isNaN(val)) return 'text-text-muted';
  if (val >= 1.0) return 'text-accent-success';
  if (val >= 0.5) return 'text-accent-warning';
  return 'text-accent-error';
}

function isUnderperformer(row: BacktestSummary): boolean {
  return parseFloat(row.winRate) < 40 || parseFloat(row.profitFactor) < 1.0;
}

function formatTimestamp(ts: number | null): string {
  if (!ts) return 'Never';
  const d = new Date(ts);
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ─── Component ──────────────────────────────────────────────────────────────

export function BacktestPanel() {
  const { state, runBacktest, runAllStrategies, clearResults } = useBacktest();
  const [collapsed, setCollapsed] = useState(true);
  const [selectedStrategy, setSelectedStrategy] = useState('all');
  const [mode, setMode] = useState<'quick' | 'full' | 'grid'>('quick');
  const [dataScale, setDataScale] = useState<BacktestDataScale>('fast');

  const handleRun = () => {
    if (selectedStrategy === 'all') {
      runAllStrategies(dataScale);
    } else {
      runBacktest(selectedStrategy, mode, dataScale);
    }
  };

  return (
    <div className="rounded-lg border border-border-primary bg-bg-secondary/80 backdrop-blur-sm overflow-hidden">
      {/* ── Header ────────────────────────────────────────────────────── */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => setCollapsed((c) => !c)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setCollapsed((c) => !c); } }}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-bg-tertiary/40 transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-2">
          <FlaskConical size={14} className="text-accent-neon" />
          <span className="text-xs font-mono font-bold uppercase tracking-wider text-text-primary">
            Strategy Validation
          </span>
          {state.lastRunAt && (
            <span className="text-[10px] font-mono text-text-muted ml-2">
              Last: {formatTimestamp(state.lastRunAt)}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!collapsed && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                runAllStrategies(dataScale);
              }}
              disabled={state.isRunning}
              className="px-2 py-1 text-[10px] font-mono font-semibold uppercase rounded
                         bg-accent-neon/10 text-accent-neon border border-accent-neon/20
                         hover:bg-accent-neon/20 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-colors"
            >
              Run All
            </button>
          )}
          {collapsed ? (
            <ChevronDown size={14} className="text-text-muted" />
          ) : (
            <ChevronUp size={14} className="text-text-muted" />
          )}
        </div>
      </div>

      {/* ── Body (collapsible) ────────────────────────────────────────── */}
      {!collapsed && (
        <div className="border-t border-border-primary px-4 py-3 space-y-3">
          {/* Controls row */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Strategy selector */}
            <select
              value={selectedStrategy}
              onChange={(e) => setSelectedStrategy(e.target.value)}
              disabled={state.isRunning}
              className="bg-bg-tertiary border border-border-primary rounded px-2 py-1.5
                         text-xs font-mono text-text-primary
                         focus:outline-none focus:border-accent-neon/40
                         disabled:opacity-40"
            >
              <option value="all">All Strategies ({STRATEGY_PRESETS.length})</option>
              {STRATEGY_PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>

            {/* Mode selector */}
            <div className="flex items-center gap-1 bg-bg-tertiary rounded border border-border-primary p-0.5">
              {(['quick', 'full', 'grid'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  disabled={state.isRunning}
                  className={`px-2 py-1 text-[10px] font-mono uppercase rounded transition-colors
                    ${
                      mode === m
                        ? 'bg-accent-neon/20 text-accent-neon'
                        : 'text-text-muted hover:text-text-secondary'
                    }
                    disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  {m}
                </button>
              ))}
            </div>

            {/* Data scale selector */}
            <div
              className="flex items-center gap-1 bg-bg-tertiary rounded border border-border-primary p-0.5"
              title="Fast uses smaller samples; Thorough runs ~10x more data for a more honest read (slower)."
            >
              {([
                { id: 'fast', label: 'Fast' },
                { id: 'thorough', label: '10x' },
              ] as const).map((d) => (
                <button
                  key={d.id}
                  onClick={() => setDataScale(d.id)}
                  disabled={state.isRunning}
                  className={`px-2 py-1 text-[10px] font-mono uppercase rounded transition-colors
                    ${
                      dataScale === d.id
                        ? 'bg-accent-neon/20 text-accent-neon'
                        : 'text-text-muted hover:text-text-secondary'
                    }
                    disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  {d.label}
                </button>
              ))}
            </div>

            {/* Run button */}
            <button
              onClick={handleRun}
              disabled={state.isRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-semibold uppercase rounded
                         bg-accent-neon/15 text-accent-neon border border-accent-neon/25
                         hover:bg-accent-neon/25 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-colors"
            >
              {state.isRunning ? (
                <Loader2 size={12} className="animate-spin" />
              ) : (
                <Play size={12} />
              )}
              {state.isRunning ? 'Running...' : 'Run'}
            </button>

            {/* Clear button */}
            {(state.results || state.activeRunId) && !state.isRunning && (
              <div className="flex items-center gap-2">
                {(state.evidence?.runId || state.activeRunId) && (
                  <button
                    onClick={() => {
                      const runId = state.evidence?.runId || state.activeRunId;
                      if (!runId) return;
                      window.open(`/api/backtest/runs/${encodeURIComponent(runId)}/artifacts?format=csv`, '_blank');
                    }}
                    className="flex items-center gap-1 px-2 py-1.5 text-[10px] font-mono uppercase
                               text-text-muted hover:text-accent-neon transition-colors"
                    title={
                      state.evidence
                        ? `Download evidence CSV (${state.evidence.tradeCount} trades, ${state.evidence.datasetCount} datasets)`
                        : 'Download evidence CSV'
                    }
                  >
                    <Download size={10} />
                    Evidence
                  </button>
                )}

                <button
                  onClick={clearResults}
                  className="flex items-center gap-1 px-2 py-1.5 text-[10px] font-mono uppercase
                             text-text-muted hover:text-accent-error transition-colors"
                  title="Clear results"
                >
                  <Trash2 size={10} />
                  Clear
                </button>
              </div>
            )}
          </div>

          {/* Progress indicator */}
          {state.isRunning && state.progress && (
            <div className="flex items-center gap-2 text-xs font-mono text-accent-neon animate-pulse">
              <Loader2 size={12} className="animate-spin" />
              <span>
                Testing {state.progress.currentStrategy}... ({state.progress.current}/
                {state.progress.total})
              </span>
            </div>
          )}

          {(state.activeRunId || state.runStatus) && (
            <div className="rounded border border-border-primary bg-bg-tertiary/30 p-2 space-y-1">
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-text-muted">
                {state.activeRunId && (
                  <span className="inline-flex items-center gap-1 rounded border border-border-primary px-1.5 py-0.5">
                    Run: {state.activeRunId}
                    <button
                      onClick={() => navigator.clipboard.writeText(state.activeRunId || '')}
                      className="hover:text-text-primary transition-colors"
                      title="Copy run id"
                    >
                      <Copy size={10} />
                    </button>
                  </span>
                )}
                {state.runStatus && (
                  <>
                    <span className="rounded border border-border-primary px-1.5 py-0.5">
                      State: {state.runStatus.state}
                    </span>
                    <span className="rounded border border-border-primary px-1.5 py-0.5">
                      Chunks: {state.runStatus.completedChunks}/{state.runStatus.totalChunks} (+{state.runStatus.failedChunks} failed)
                    </span>
                    <span className="rounded border border-border-primary px-1.5 py-0.5">
                      Progress: {state.runStatus.progress}%
                    </span>
                  </>
                )}
              </div>
              {state.runStatus?.currentActivity && (
                <div className="text-[10px] font-mono text-text-secondary">
                  Activity: {state.runStatus.currentActivity}
                </div>
              )}
              {state.artifactAvailability && (
                <div className="flex flex-wrap items-center gap-1 text-[9px] font-mono uppercase">
                  {(['manifest', 'evidence', 'report', 'csv'] as const).map((k) => (
                    <span
                      key={k}
                      className={`rounded px-1.5 py-0.5 border ${
                        state.artifactAvailability?.[k]
                          ? 'text-accent-success border-accent-success/30 bg-accent-success/10'
                          : 'text-text-muted border-border-primary bg-bg-secondary'
                      }`}
                    >
                      {k}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {state.isStalled && (
            <div className="flex items-center gap-2 text-xs font-mono text-accent-warning bg-accent-warning/10 rounded px-3 py-2 border border-accent-warning/20">
              <AlertTriangle size={12} />
              <span>
                Backtest appears stalled ({state.stallSeconds}s without heartbeat). Run ID is retained and polling continues.
              </span>
            </div>
          )}

          {state.detachedRun && state.detachedReason && (
            <div className="flex items-center gap-2 text-xs font-mono text-accent-warning bg-accent-warning/10 rounded px-3 py-2 border border-accent-warning/20">
              <AlertTriangle size={12} />
              <span>{state.detachedReason}</span>
            </div>
          )}

          {/* Error */}
          {state.error && (
            <div className="text-xs font-mono text-accent-error bg-accent-error/10 rounded px-3 py-2 border border-accent-error/20">
              Error: {state.error}
            </div>
          )}

          {/* Results table */}
          {state.results && state.results.length > 0 ? (
            <div className="overflow-x-auto -mx-4 px-4">
              <table className="w-full text-[11px] font-mono">
                <thead>
                  <tr className="text-text-muted border-b border-border-primary">
                    <th className="text-left py-2 pr-3 font-semibold">Strategy</th>
                    <th className="text-left py-2 pr-3 font-semibold">Token</th>
                    <th className="text-left py-2 pr-3 font-semibold">Src</th>
                    <th className="text-right py-2 pr-3 font-semibold">Trades</th>
                    <th className="text-right py-2 pr-3 font-semibold">Win Rate</th>
                    <th className="text-right py-2 pr-3 font-semibold">PF</th>
                    <th className="text-right py-2 pr-3 font-semibold">Sharpe</th>
                    <th className="text-right py-2 pr-3 font-semibold">Max DD</th>
                    <th className="text-right py-2 pr-3 font-semibold">Expect.</th>
                    <th className="text-right py-2 font-semibold">Avg Hold</th>
                  </tr>
                </thead>
                <tbody>
                  {state.results.map((row, i) => {
                    const under = isUnderperformer(row);
                    return (
                      <tr
                        key={`${row.strategyId}-${row.token}-${i}`}
                        className={`border-b border-border-primary/50 hover:bg-bg-tertiary/30 transition-colors ${
                          under ? 'bg-accent-error/5' : ''
                        }`}
                      >
                        <td className="py-1.5 pr-3 text-text-primary whitespace-nowrap">
                          <span className="truncate max-w-[140px] inline-block align-middle">
                            {STRATEGY_PRESETS.find((p) => p.id === row.strategyId)?.name ??
                              row.strategyId}
                          </span>
                          {under && (
                            <span className="ml-1.5 px-1 py-0.5 text-[9px] font-bold uppercase rounded bg-accent-error/20 text-accent-error">
                              Underperformer
                            </span>
                          )}
                        </td>
                        <td className="py-1.5 pr-3 text-text-secondary">{row.token}</td>
                        <td className="py-1.5 pr-3 text-text-muted whitespace-nowrap">
                          {row.dataSource ? (
                            <span
                              className={`px-1 py-0.5 text-[9px] font-bold uppercase rounded border ${
                                row.validated
                                  ? 'bg-accent-success/10 text-accent-success border-accent-success/25'
                                  : 'bg-accent-warning/10 text-accent-warning border-accent-warning/25'
                              }`}
                              title={row.validated ? 'Real candles' : 'Client / unverified candles'}
                            >
                              {row.dataSource}
                            </span>
                          ) : (
                            <span className="text-[9px] font-mono">n/a</span>
                          )}
                        </td>
                        <td className="py-1.5 pr-3 text-right text-text-secondary">
                          {row.trades}
                        </td>
                        <td className={`py-1.5 pr-3 text-right font-semibold ${winRateColor(row.winRate)}`}>
                          {row.winRate}
                        </td>
                        <td
                          className={`py-1.5 pr-3 text-right ${
                            parseFloat(row.profitFactor) < 1.0
                              ? 'text-accent-error'
                              : 'text-text-secondary'
                          }`}
                        >
                          {row.profitFactor}
                        </td>
                        <td className={`py-1.5 pr-3 text-right ${sharpeColor(row.sharpe)}`}>
                          {row.sharpe}
                        </td>
                        <td className="py-1.5 pr-3 text-right text-accent-error">
                          {row.maxDD}
                        </td>
                        <td className="py-1.5 pr-3 text-right text-text-secondary">
                          {row.expectancy}
                        </td>
                        <td className="py-1.5 text-right text-text-muted">{row.avgHold}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            !state.isRunning &&
            !state.error && (
              <div className="text-xs font-mono text-text-muted text-center py-6 border border-dashed border-border-primary rounded">
                No backtest data. Click &quot;Run All&quot; to validate strategies against
                historical data.
              </div>
            )
          )}

          {/* Last run timestamp */}
          {state.lastRunAt && (
            <div className="text-[10px] font-mono text-text-muted text-right pt-1">
              Last validated: {formatTimestamp(state.lastRunAt)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
