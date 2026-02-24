'use client';

import React, { useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { StatusBar } from '@/components/StatusBar';
import { EarlyBetaModal } from '@/components/EarlyBetaModal';
import { FundRecoveryBanner } from '@/components/FundRecoveryBanner';
import { AlvaraBasketPanel } from '@/components/investments/AlvaraBasketPanel';
import { PerpsSniperPanel } from '@/components/perps/PerpsSniperPanel';
import { isSurfaceEnabled, resolveSurfaceAvailability } from '@/lib/surface-availability';

type InvestmentsTab = 'basket' | 'perps';

function tabFromSearch(input: string | null): InvestmentsTab {
  return input === 'perps' ? 'perps' : 'basket';
}

export function InvestmentsPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedTab = useMemo(() => tabFromSearch(searchParams.get('tab')), [searchParams]);
  const availability = useMemo(() => resolveSurfaceAvailability(), []);
  const investmentsSurface = availability.investments;
  const perpsSurface = availability.perps;
  const investmentsEnabled = isSurfaceEnabled(investmentsSurface);
  const perpsEnabled = isSurfaceEnabled(perpsSurface);

  const setTab = (next: InvestmentsTab) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set('tab', next);
    router.replace(`/investments?${params.toString()}`);
  };

  const effectiveTab: InvestmentsTab = requestedTab;
  const activeSurface = effectiveTab === 'basket' ? investmentsSurface : perpsSurface;
  const isActiveSurfaceDisabled = !isSurfaceEnabled(activeSurface);

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
          <a
            href="https://t.me/kr8tivaisystems"
            target="_blank"
            rel="noreferrer"
            className="mt-3 block rounded-lg border border-accent-warning/35 bg-accent-warning/10 p-3 transition-colors hover:bg-accent-warning/15"
          >
            <div className="text-xs font-semibold uppercase tracking-wide text-accent-warning">
              Investments Coming Soon
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              This section is temporarily in staged rollout while we finish reliability upgrades. Follow Telegram for
              release updates.
            </p>
            <span className="mt-2 inline-block text-[11px] font-semibold text-accent-warning">
              Get Updates on Telegram
            </span>
          </a>
        </section>

        <section className="rounded-xl border border-border-primary bg-bg-secondary p-2">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setTab('basket')}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                effectiveTab === 'basket'
                  ? 'border-accent-neon/50 bg-accent-neon/12 text-accent-neon'
                  : 'border-border-primary bg-bg-tertiary text-text-muted hover:text-text-primary'
              } ${!investmentsEnabled ? 'opacity-80' : ''}`}
              aria-disabled={!investmentsEnabled}
              title={investmentsSurface.reason || undefined}
            >
              Alvara Basket
            </button>
            <button
              onClick={() => setTab('perps')}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold ${
                effectiveTab === 'perps'
                  ? 'border-blue-400/50 bg-blue-500/12 text-blue-300'
                  : 'border-border-primary bg-bg-tertiary text-text-muted hover:text-text-primary'
              } ${!perpsEnabled ? 'opacity-80' : ''}`}
              aria-disabled={!perpsEnabled}
              title={perpsSurface.reason || undefined}
            >
              Perps Sniper
            </button>
          </div>
        </section>

        {isActiveSurfaceDisabled && (
          <section className="rounded-xl border border-accent-warning/30 bg-accent-warning/10 p-4 text-xs text-accent-warning">
            {activeSurface.reason || 'This surface is disabled for staged rollout.'}
          </section>
        )}

        {effectiveTab === 'basket' ? (
          <AlvaraBasketPanel
            disabled={!investmentsEnabled}
            disabledReason={investmentsSurface.reason}
          />
        ) : (
          <PerpsSniperPanel
            disabled={!perpsEnabled}
            disabledReason={perpsSurface.reason}
          />
        )}
      </main>
    </div>
  );
}

export default InvestmentsPageClient;
