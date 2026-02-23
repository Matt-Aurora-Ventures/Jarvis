'use client';

import React, { useMemo, useState } from 'react';
import { usePerpsData } from './usePerpsData';
import { PerpsCandlesChart } from './PerpsCandlesChart';

function fmtPrice(v: number): string {
  if (!Number.isFinite(v) || v <= 0) return '--';
  if (v >= 1000) return `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
  return `$${v.toFixed(4)}`;
}

function fmtPct(v: number | undefined): string {
  if (v === undefined || !Number.isFinite(v)) return '--';
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`;
}

export function PerpsSniperPanel() {
  const {
    prices,
    status,
    positions,
    audit,
    historyMarket,
    historyResolution,
    historyCandles,
    loadingHistory,
    historyError,
    apiError,
    isArmed,
    isLive,
    setHistoryMarket,
    setHistoryResolution,
    openPosition,
    closePosition,
    refreshStatus,
  } = usePerpsData();

  const [market, setMarket] = useState<'SOL-USD' | 'BTC-USD' | 'ETH-USD'>('SOL-USD');
  const [side, setSide] = useState<'long' | 'short'>('long');
  const [collateral, setCollateral] = useState(100);
  const [leverage, setLeverage] = useState(3);
  const [tpPct, setTpPct] = useState('10');
  const [slPct, setSlPct] = useState('5');
  const [orderState, setOrderState] = useState<string>('');

  const canTrade = isArmed && isLive;

  const runnerStatusLabel = useMemo(() => {
    if (!status) return 'Unknown';
    if (status.runner_healthy) return 'Runner Online';
    return 'Runner Offline';
  }, [status]);

  return (
    <div className="space-y-4">
      {apiError && (
        <div className="rounded border border-accent-error/40 bg-accent-error/10 px-3 py-2 text-xs text-accent-error">
          {apiError}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div className="text-text-primary">{runnerStatusLabel}</div>
          <div className="mt-1">Mode: {String(status?.mode || 'disabled').toUpperCase()}</div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>SOL</div>
          <div className="mt-1 text-sm font-semibold text-text-primary">{fmtPrice(prices?.sol || 0)}</div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>BTC</div>
          <div className="mt-1 text-sm font-semibold text-text-primary">{fmtPrice(prices?.btc || 0)}</div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>ETH</div>
          <div className="mt-1 text-sm font-semibold text-text-primary">{fmtPrice(prices?.eth || 0)}</div>
        </div>
      </div>

      <PerpsCandlesChart
        market={historyMarket}
        resolution={historyResolution}
        candles={historyCandles}
        loading={loadingHistory}
        error={historyError}
        onMarketChange={setHistoryMarket}
        onResolutionChange={setHistoryResolution}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Open Position</h3>

          <div className="grid grid-cols-3 gap-2">
            {(['SOL-USD', 'BTC-USD', 'ETH-USD'] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMarket(m)}
                className={`rounded border px-2 py-1 text-xs ${
                  market === m
                    ? 'border-accent-neon/40 bg-accent-neon/10 text-accent-neon'
                    : 'border-border-primary bg-bg-tertiary text-text-muted'
                }`}
              >
                {m.split('-')[0]}
              </button>
            ))}
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              onClick={() => setSide('long')}
              className={`rounded border px-2 py-1 text-xs ${
                side === 'long' ? 'border-green-500/50 bg-green-500/15 text-green-300' : 'border-border-primary bg-bg-tertiary text-text-muted'
              }`}
            >
              LONG
            </button>
            <button
              onClick={() => setSide('short')}
              className={`rounded border px-2 py-1 text-xs ${
                side === 'short' ? 'border-red-500/50 bg-red-500/15 text-red-300' : 'border-border-primary bg-bg-tertiary text-text-muted'
              }`}
            >
              SHORT
            </button>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <label className="flex flex-col gap-1 text-text-muted">
              Collateral (USD)
              <input
                value={collateral}
                onChange={(e) => setCollateral(Number(e.target.value || 0))}
                type="number"
                min={10}
                className="rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-text-primary"
              />
            </label>
            <label className="flex flex-col gap-1 text-text-muted">
              Leverage
              <input
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value || 1))}
                type="number"
                min={1}
                max={250}
                className="rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-text-primary"
              />
            </label>
            <label className="flex flex-col gap-1 text-text-muted">
              Take Profit %
              <input
                value={tpPct}
                onChange={(e) => setTpPct(e.target.value)}
                type="number"
                className="rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-text-primary"
              />
            </label>
            <label className="flex flex-col gap-1 text-text-muted">
              Stop Loss %
              <input
                value={slPct}
                onChange={(e) => setSlPct(e.target.value)}
                type="number"
                className="rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-text-primary"
              />
            </label>
          </div>

          <button
            type="button"
            disabled={!canTrade}
            className="mt-3 w-full rounded border border-accent-neon/40 bg-accent-neon/15 px-3 py-2 text-xs font-semibold text-accent-neon disabled:opacity-50"
            onClick={async () => {
              setOrderState('Submitting...');
              try {
                await openPosition({
                  market,
                  side,
                  collateralUsd: collateral,
                  leverage,
                  tpPct: tpPct ? Number(tpPct) : undefined,
                  slPct: slPct ? Number(slPct) : undefined,
                });
                setOrderState('Order queued successfully.');
              } catch (err) {
                const msg = err instanceof Error ? err.message : String(err);
                setOrderState(`Submit failed: ${msg}`);
              }
            }}
          >
            Open {side.toUpperCase()} {market}
          </button>

          {!canTrade && (
            <p className="mt-2 text-xs text-accent-warning">Live order entry requires mode=LIVE and arm stage=ARMED.</p>
          )}

          {orderState && <p className="mt-2 text-xs text-text-muted">{orderState}</p>}
        </div>

        <div className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">Open Positions</h3>
            <button
              onClick={() => void refreshStatus()}
              className="rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-xs text-text-muted"
            >
              Refresh
            </button>
          </div>

          <div className="max-h-[220px] space-y-2 overflow-auto text-xs">
            {positions.length === 0 && <p className="text-text-muted">No open positions.</p>}
            {positions.map((p, idx) => (
              <div key={`${p.pda || 'pos'}-${idx}`} className="rounded border border-border-primary bg-bg-tertiary px-2 py-2">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-text-primary">{String(p.market || '--')}</span>
                  <span className={`${(p.unrealized_pnl_pct || 0) >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                    {fmtPct(p.unrealized_pnl_pct)}
                  </span>
                </div>
                <div className="mt-1 text-text-muted">Side: {String(p.side || '--')} | Size: ${Number(p.size_usd || 0).toFixed(2)}</div>
                {p.pda && (
                  <button
                    className="mt-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-[11px] text-red-300"
                    onClick={async () => {
                      try {
                        await closePosition(String(p.pda));
                        setOrderState(`Close intent queued for ${String(p.market || p.pda)}`);
                      } catch (err) {
                        const msg = err instanceof Error ? err.message : String(err);
                        setOrderState(`Close failed: ${msg}`);
                      }
                    }}
                  >
                    Queue Close
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border-primary bg-bg-secondary p-4">
        <h3 className="mb-2 text-sm font-semibold text-text-primary">Recent Audit Events</h3>
        <div className="max-h-[180px] space-y-1 overflow-auto text-xs text-text-muted">
          {audit.length === 0 && <p>No audit events found.</p>}
          {audit.slice(0, 30).map((row, idx) => (
            <div key={`${idx}-${String(row.event || 'event')}`}>
              {String(row.event || 'event')} {row.detail ? `- ${String(row.detail)}` : ''}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default PerpsSniperPanel;
