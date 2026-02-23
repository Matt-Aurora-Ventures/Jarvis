'use client';

import React, { useMemo, useState } from 'react';
import { useInvestmentData } from './useInvestmentData';

function fmtUsd(v: number): string {
  if (!Number.isFinite(v)) return '--';
  return `$${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`;
}

export function AlvaraBasketPanel() {
  const {
    basket,
    performance,
    decisions,
    killSwitchActive,
    driftWarning,
    loading,
    error,
    refresh,
    triggerCycle,
    activateKillSwitch,
    deactivateKillSwitch,
  } = useInvestmentData();

  const [actionState, setActionState] = useState<string>('');

  const perfDelta = useMemo(() => {
    if (performance.length < 2) return null;
    const first = performance[0].nav;
    const last = performance[performance.length - 1].nav;
    if (!Number.isFinite(first) || first === 0) return null;
    const pct = ((last - first) / first) * 100;
    return pct;
  }, [performance]);

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded border border-accent-error/40 bg-accent-error/10 px-3 py-2 text-xs text-accent-error">
          {error}
        </div>
      )}

      {driftWarning && (
        <div className="rounded border border-accent-warning/40 bg-accent-warning/10 px-3 py-2 text-xs text-accent-warning">
          {driftWarning}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>Basket NAV</div>
          <div className="mt-1 text-sm font-semibold text-text-primary">{fmtUsd(basket?.totalNav || 0)}</div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>NAV / Share</div>
          <div className="mt-1 text-sm font-semibold text-text-primary">{fmtUsd(basket?.navPerShare || 0)}</div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>Performance (168h)</div>
          <div className={`mt-1 text-sm font-semibold ${perfDelta === null ? 'text-text-primary' : perfDelta >= 0 ? 'text-green-300' : 'text-red-300'}`}>
            {perfDelta === null ? '--' : `${perfDelta >= 0 ? '+' : ''}${perfDelta.toFixed(2)}%`}
          </div>
        </div>
        <div className="rounded-lg border border-border-primary bg-bg-secondary px-3 py-2 text-xs text-text-muted">
          <div>Kill Switch</div>
          <div className={`mt-1 text-sm font-semibold ${killSwitchActive ? 'text-red-300' : 'text-green-300'}`}>
            {killSwitchActive ? 'ACTIVE' : 'INACTIVE'}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">Basket Weights</h3>
            <button
              onClick={() => void refresh()}
              className="rounded border border-border-primary bg-bg-tertiary px-2 py-1 text-xs text-text-muted"
            >
              Refresh
            </button>
          </div>

          <div className="max-h-[260px] overflow-auto">
            <table className="w-full text-xs">
              <thead className="text-text-muted">
                <tr>
                  <th className="text-left py-1">Token</th>
                  <th className="text-right py-1">Weight</th>
                  <th className="text-right py-1">Price</th>
                  <th className="text-right py-1">Value</th>
                </tr>
              </thead>
              <tbody>
                {(basket?.tokens || []).map((token) => (
                  <tr key={token.symbol} className="border-t border-border-primary/60">
                    <td className="py-1 text-text-primary">{token.symbol}</td>
                    <td className="py-1 text-right text-text-muted">{(token.weight * 100).toFixed(2)}%</td>
                    <td className="py-1 text-right text-text-muted">{fmtUsd(token.priceUsd)}</td>
                    <td className="py-1 text-right text-text-muted">{fmtUsd(token.usdValue)}</td>
                  </tr>
                ))}
                {!basket?.tokens.length && (
                  <tr>
                    <td colSpan={4} className="py-2 text-text-muted">No basket data available.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <h3 className="mb-3 text-sm font-semibold text-text-primary">Operator Actions</h3>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={async () => {
                setActionState('Triggering cycle...');
                try {
                  await triggerCycle();
                  setActionState('Cycle trigger submitted.');
                } catch (err) {
                  const msg = err instanceof Error ? err.message : String(err);
                  setActionState(`Trigger failed: ${msg}`);
                }
              }}
              className="rounded border border-blue-400/40 bg-blue-500/10 px-3 py-2 text-xs text-blue-300"
            >
              Trigger Cycle
            </button>
            <button
              onClick={async () => {
                setActionState('Activating kill switch...');
                try {
                  await activateKillSwitch();
                  setActionState('Kill switch activated.');
                } catch (err) {
                  const msg = err instanceof Error ? err.message : String(err);
                  setActionState(`Activation failed: ${msg}`);
                }
              }}
              className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300"
            >
              Activate Kill Switch
            </button>
            <button
              onClick={async () => {
                setActionState('Deactivating kill switch...');
                try {
                  await deactivateKillSwitch();
                  setActionState('Kill switch deactivated.');
                } catch (err) {
                  const msg = err instanceof Error ? err.message : String(err);
                  setActionState(`Deactivation failed: ${msg}`);
                }
              }}
              className="rounded border border-green-500/40 bg-green-500/10 px-3 py-2 text-xs text-green-300"
            >
              Deactivate Kill Switch
            </button>
          </div>

          <p className="mt-2 text-xs text-text-muted">
            Internal beta mode defaults to dry-run service behavior unless explicitly switched.
          </p>

          {actionState && <p className="mt-3 text-xs text-text-muted">{actionState}</p>}
        </div>
      </div>

      <div className="rounded-xl border border-border-primary bg-bg-secondary p-4">
        <h3 className="mb-3 text-sm font-semibold text-text-primary">Recent Decisions</h3>
        <div className="max-h-[240px] space-y-2 overflow-auto text-xs">
          {loading && decisions.length === 0 && <p className="text-text-muted">Loading decision history...</p>}
          {!loading && decisions.length === 0 && <p className="text-text-muted">No decision history yet.</p>}
          {decisions.map((d) => (
            <div key={d.id} className="rounded border border-border-primary bg-bg-tertiary px-2 py-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-text-primary">{d.action}</span>
                <span className="text-text-muted">{d.timestamp || '--'}</span>
              </div>
              <div className="mt-1 text-text-muted">Confidence: {d.confidence.toFixed(2)} | NAV: {fmtUsd(d.navAtDecision)}</div>
              {d.summary && <div className="mt-1 text-text-muted">{d.summary}</div>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default AlvaraBasketPanel;
