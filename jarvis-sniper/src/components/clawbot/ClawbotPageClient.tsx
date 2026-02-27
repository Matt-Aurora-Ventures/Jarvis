'use client';

import React from 'react';
import { StatusBar } from '@/components/StatusBar';
import { EarlyBetaModal } from '@/components/EarlyBetaModal';
import { FundRecoveryBanner } from '@/components/FundRecoveryBanner';
import { FeatureDisabledOverlay } from '@/components/ui/FeatureDisabledOverlay';
import { resolveSurfaceAvailability } from '@/lib/surface-availability';

export function ClawbotPageClient() {
  const clawbotSurface = resolveSurfaceAvailability('clawbot');

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />
      <FundRecoveryBanner />

      <main className="app-shell flex-1 py-6 space-y-4">
        <section className="rounded-xl border border-border-primary bg-bg-secondary p-4">
          <h1 className="text-lg font-display font-semibold text-text-primary">Clawbot</h1>
          <p className="mt-1 text-xs text-text-muted">
            Open Claw control-panel shell for upcoming autonomous execution and recovery tooling.
          </p>
          <a
            href="https://t.me/kr8tivaisystems"
            target="_blank"
            rel="noreferrer"
            className="mt-3 block rounded-lg border border-accent-warning/35 bg-accent-warning/10 p-3 transition-colors hover:bg-accent-warning/15"
          >
            <div className="text-xs font-semibold uppercase tracking-wide text-accent-warning">
              Clawbot Coming Soon
            </div>
            <p className="mt-1 text-xs text-text-secondary">
              This panel is staged for demo visibility while runtime hardening and safety controls are finalized.
            </p>
            <span className="mt-2 inline-block text-[11px] font-semibold text-accent-warning">
              Get Updates on Telegram
            </span>
          </a>
        </section>

        <div className="relative">
          <section className="rounded-xl border border-border-primary bg-bg-secondary p-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-border-primary bg-bg-tertiary p-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Runner</div>
                <div className="mt-1 text-sm font-semibold text-text-primary">Offline</div>
              </div>
              <div className="rounded-lg border border-border-primary bg-bg-tertiary p-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Queue</div>
                <div className="mt-1 text-sm font-semibold text-text-primary">0 Active Tasks</div>
              </div>
              <div className="rounded-lg border border-border-primary bg-bg-tertiary p-3">
                <div className="text-[11px] font-semibold uppercase tracking-wide text-text-muted">Mode</div>
                <div className="mt-1 text-sm font-semibold text-text-primary">Demo Safe</div>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-border-primary bg-bg-tertiary p-3">
              <div className="text-xs font-semibold text-text-primary">Operator Actions</div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled
                  className="rounded border border-blue-400/40 bg-blue-500/10 px-3 py-2 text-xs text-blue-300 opacity-60"
                >
                  Autonomous Sweep
                </button>
                <button
                  type="button"
                  disabled
                  className="rounded border border-green-500/40 bg-green-500/10 px-3 py-2 text-xs text-green-300 opacity-60"
                >
                  Queue Position
                </button>
                <button
                  type="button"
                  disabled
                  className="rounded border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-300 opacity-60"
                >
                  Emergency Halt
                </button>
              </div>
            </div>
          </section>

          <FeatureDisabledOverlay reason={clawbotSurface.reason || 'Clawbot is disabled.'} />
        </div>
      </main>
    </div>
  );
}

export default ClawbotPageClient;

