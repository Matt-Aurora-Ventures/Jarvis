'use client';

import React, { useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { StatusBar } from '@/components/StatusBar';
import { EarlyBetaModal } from '@/components/EarlyBetaModal';
import { FundRecoveryBanner } from '@/components/FundRecoveryBanner';
import { AlvaraBasketPanel } from '@/components/investments/AlvaraBasketPanel';
import { PerpsSniperPanel } from '@/components/perps/PerpsSniperPanel';
import { isInvestmentsEnabled, isPerpsEnabled } from '@/lib/investments-perps-flags';

type InvestmentsTab = 'basket' | 'perps';

function tabFromSearch(input: string | null): InvestmentsTab {
  return input === 'perps' ? 'perps' : 'basket';
}

export function InvestmentsPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = useMemo(() => tabFromSearch(searchParams.get('tab')), [searchParams]);
  const investmentsEnabled = isInvestmentsEnabled();
  const perpsEnabled = isPerpsEnabled();

  const setTab = (next: InvestmentsTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', next);
    router.replace(`/investments?${params.toString()}`);
  };

  const hasVisibleTab = investmentsEnabled || perpsEnabled;
  const effectiveTab: InvestmentsTab =
    requestedTab === 'perps' && perpsEnabled
      ? 'perps'
      : investmentsEnabled
        ? 'basket'
        : perpsEnabled
          ? 'perps'
          : 'basket';

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />
      <FundRecoveryBanner />

      <main className="app-shell flex-1 py-6 space-y-4">
        <section className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <h1 className="text-lg font-display font-semibold text-text-primary">Investments</h1>
          <p className="mt-1 text-xs text-text-muted">
            Internal beta surface for Alvara basket operations and Jupiter perps execution panels.
          </p>
        </section>

        <section className="rounded-xl border border-border-primary bg-bg-secondary p-2">
          <div className="flex flex-wrap gap-2">
            {investmentsEnabled && (
              <button
                onClick={() => setTab('basket')}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                  effectiveTab === 'basket'
                    ? 'border-accent-neon/50 bg-accent-neon/12 text-accent-neon'
                    : 'border-border-primary bg-bg-tertiary text-text-muted hover:text-text-primary'
                }`}
              >
                Alvara Basket
              </button>
            )}
            {perpsEnabled && (
              <button
                onClick={() => setTab('perps')}
                className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                  effectiveTab === 'perps'
                    ? 'border-blue-400/50 bg-blue-500/12 text-blue-300'
                    : 'border-border-primary bg-bg-tertiary text-text-muted hover:text-text-primary'
                }`}
              >
                Perps Sniper
              </button>
            )}
          </div>
        </section>

        {!hasVisibleTab && (
          <section className="rounded-xl border border-accent-warning/30 bg-accent-warning/10 p-4 text-xs text-accent-warning">
            Investments and perps are disabled in this environment. Enable at least one of
            `NEXT_PUBLIC_ENABLE_INVESTMENTS` or `NEXT_PUBLIC_ENABLE_PERPS`.
          </section>
        )}

        {hasVisibleTab && (effectiveTab === 'basket' ? <AlvaraBasketPanel /> : <PerpsSniperPanel />)}
      </main>
    </div>
  );
}

export default InvestmentsPageClient;
