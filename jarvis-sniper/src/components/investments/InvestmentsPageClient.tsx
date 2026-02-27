'use client';

import React, { useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { StatusBar } from '@/components/StatusBar';
import { EarlyBetaModal } from '@/components/EarlyBetaModal';
import { FundRecoveryBanner } from '@/components/FundRecoveryBanner';
import { AlvaraBasketPanel } from '@/components/investments/AlvaraBasketPanel';
import { PerpsSniperPanel } from '@/components/perps/PerpsSniperPanel';
import { FeatureDisabledOverlay } from '@/components/ui/FeatureDisabledOverlay';
import { resolveSurfaceAvailability } from '@/lib/surface-availability';

type InvestmentsTab = 'investments' | 'perps';

function tabFromSearch(input: string | null): InvestmentsTab {
  return input === 'perps' ? 'perps' : 'investments';
}

export function InvestmentsPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = useMemo(() => tabFromSearch(searchParams.get('tab')), [searchParams]);
  const effectiveTab: InvestmentsTab = requestedTab;
  const investmentsSurface = resolveSurfaceAvailability('investments');
  const perpsSurface = resolveSurfaceAvailability('perps');

  const setTab = (next: InvestmentsTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', next);
    router.replace(`/investments?${params.toString()}`);
  };

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />
      <FundRecoveryBanner />

      <main className="app-shell flex-1 py-6 space-y-4">
        <section className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <h1 className="text-lg font-display font-semibold text-text-primary">Investments Workspace</h1>
          <p className="mt-1 text-xs text-text-muted">
            Charts, entries, exits, and take-profit controls for the Jupiter perps sniper workflow.
          </p>
          <div className="mt-3 rounded-lg border border-border-primary bg-bg-tertiary/45 p-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-text-secondary">Quick start</h2>
            <ol className="mt-2 list-decimal pl-4 text-xs text-text-muted space-y-1">
              <li>Pick a surface tab: `Investments Core` for basket ops or `Perps Sniper` for futures execution.</li>
              <li>If trading perps, set daily limits first, then run arm/disarm controls before submitting orders.</li>
              <li>Use tiny size and monitor audit events before switching anything to live mode.</li>
            </ol>
          </div>
          {(!investmentsSurface.enabled || !perpsSurface.enabled) && (
            <a
              href="https://t.me/kr8tivaisystems"
              target="_blank"
              rel="noreferrer"
              className="mt-3 block rounded-lg border border-accent-warning/35 bg-accent-warning/10 p-3 transition-colors hover:bg-accent-warning/15"
            >
              <div className="text-xs font-semibold uppercase tracking-wide text-accent-warning">
                Investments Rollout
              </div>
              <p className="mt-1 text-xs text-text-secondary">
                Some operator controls are in staged rollout for this runtime. Follow Telegram for release updates.
              </p>
              <span className="mt-2 inline-block text-[11px] font-semibold text-accent-warning">
                Get Updates on Telegram
              </span>
            </a>
          )}
        </section>

        <section
          role="tablist"
          aria-label="Investments surfaces"
          className="rounded-xl border border-border-primary bg-bg-secondary p-2"
        >
          <div className="flex flex-wrap gap-2">
            <button
              id="investments-tab-investments"
              role="tab"
              aria-selected={effectiveTab === 'investments'}
              aria-controls="investments-tabpanel-investments"
              onClick={() => setTab('investments')}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                effectiveTab === 'investments'
                  ? 'border-accent-neon/50 bg-accent-neon/12 text-accent-neon'
                  : 'border-border-primary bg-bg-tertiary text-text-muted hover:text-text-primary'
              } ${!investmentsSurface.enabled ? 'opacity-80' : ''}`}
            >
              Investments Core {!investmentsSurface.enabled ? '(disabled)' : ''}
            </button>
            <button
              id="investments-tab-perps"
              role="tab"
              aria-selected={effectiveTab === 'perps'}
              aria-controls="investments-tabpanel-perps"
              onClick={() => setTab('perps')}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                effectiveTab === 'perps'
                  ? 'border-blue-400/50 bg-blue-500/12 text-blue-300'
                  : 'border-border-primary bg-bg-tertiary text-text-muted hover:text-text-primary'
              } ${!perpsSurface.enabled ? 'opacity-80' : ''}`}
            >
              Perps Sniper {!perpsSurface.enabled ? '(disabled)' : ''}
            </button>
          </div>
        </section>

        {effectiveTab === 'investments' ? (
          <div
            id="investments-tabpanel-investments"
            role="tabpanel"
            aria-labelledby="investments-tab-investments"
            className="relative"
          >
            <AlvaraBasketPanel forceDisabledReason={!investmentsSurface.enabled ? investmentsSurface.reason : null} />
            {!investmentsSurface.enabled && (
              <FeatureDisabledOverlay reason={investmentsSurface.reason || 'Investments is disabled.'} />
            )}
          </div>
        ) : (
          <div
            id="investments-tabpanel-perps"
            role="tabpanel"
            aria-labelledby="investments-tab-perps"
            className="relative"
          >
            <PerpsSniperPanel forceDisabledReason={!perpsSurface.enabled ? perpsSurface.reason : null} />
            {!perpsSurface.enabled && <FeatureDisabledOverlay reason={perpsSurface.reason || 'Perps is disabled.'} />}
          </div>
        )}
      </main>
    </div>
  );
}

export default InvestmentsPageClient;

