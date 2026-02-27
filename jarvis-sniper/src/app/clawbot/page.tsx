import { Suspense } from 'react';
import { ClawbotPageClient } from '@/components/clawbot/ClawbotPageClient';

export const runtime = 'nodejs';

function ClawbotLoadingFallback() {
  return (
    <main className="app-shell py-6">
      <section className="rounded-xl border border-border-primary bg-bg-secondary p-4 text-xs text-text-muted">
        Loading clawbot panel...
      </section>
    </main>
  );
}

export default function ClawbotPage() {
  return (
    <Suspense fallback={<ClawbotLoadingFallback />}>
      <ClawbotPageClient />
    </Suspense>
  );
}

