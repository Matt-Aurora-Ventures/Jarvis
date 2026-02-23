import { Suspense } from 'react';
import { InvestmentsPageClient } from '@/components/investments/InvestmentsPageClient';

export const runtime = 'nodejs';

function InvestmentsLoadingFallback() {
  return (
    <main className="app-shell py-6">
      <section className="rounded-xl border border-border-primary bg-bg-secondary p-4 text-xs text-text-muted">
        Loading investments panel...
      </section>
    </main>
  );
}

export default function InvestmentsPage() {
  return (
    <Suspense fallback={<InvestmentsLoadingFallback />}>
      <InvestmentsPageClient />
    </Suspense>
  );
}
