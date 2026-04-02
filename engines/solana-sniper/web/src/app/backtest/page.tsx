import { getStrategyPerformance, getBacktestHistory, getBestConfig } from '@/lib/data';
import { BacktestDashboard } from '@/components/BacktestDashboard';

export const dynamic = 'force-dynamic';
export const revalidate = 5;

export default function BacktestPage() {
  const strategies = getStrategyPerformance();
  const history = getBacktestHistory();
  const bestConfig = getBestConfig();

  return (
    <main className="min-h-screen p-6 max-w-[1600px] mx-auto">
      <header className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <a href="/" className="text-[var(--text-muted)] hover:text-[var(--accent)] transition-colors text-sm">&larr; Dashboard</a>
          <h1 className="text-2xl font-bold tracking-tight">
            <span className="text-[var(--accent)]">BACKTEST</span>{' '}
            <span className="text-[var(--text-secondary)]">RESULTS</span>
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <a href="/optimize" className="text-xs px-3 py-1.5 rounded-lg border border-[var(--border)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors">
            Optimizer &rarr;
          </a>
        </div>
      </header>

      <BacktestDashboard strategies={strategies} history={history} bestConfig={bestConfig} />
    </main>
  );
}
