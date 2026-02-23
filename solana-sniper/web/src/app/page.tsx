import { getStats, getRecentTrades, getOpenPositions, getStrategyPerformance, getPnlHistory } from '@/lib/data';
import { StatsGrid } from '@/components/StatsGrid';
import { PositionsTable } from '@/components/PositionsTable';
import { TradesTable } from '@/components/TradesTable';
import { PnlChart } from '@/components/PnlChart';
import { StrategyTable } from '@/components/StrategyTable';
import { SystemStatus } from '@/components/SystemStatus';
import { NavBar } from '@/components/NavBar';
import { ActivityFeed } from '@/components/ActivityFeed';

export const dynamic = 'force-dynamic';
export const revalidate = 5;

export default function Dashboard() {
  const stats = getStats();
  const trades = getRecentTrades(15);
  const positions = getOpenPositions();
  const strategies = getStrategyPerformance();
  const pnlHistory = getPnlHistory();

  return (
    <main className="min-h-screen p-6 max-w-[1600px] mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-[var(--accent)] pulse-green" />
            <h1 className="text-2xl font-bold tracking-tight">
              <span className="text-[var(--accent)]">SOLANA</span>{' '}
              <span className="text-[var(--text-secondary)]">SNIPER</span>
            </h1>
          </div>
          <NavBar />
        </div>
        <SystemStatus />
      </header>

      {/* Stats Grid */}
      <StatsGrid stats={stats} />

      {/* Charts + Activity Feed Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <div className="lg:col-span-2">
          <PnlChart data={pnlHistory} />
        </div>
        <div>
          <ActivityFeed />
        </div>
      </div>

      {/* Positions + Strategy Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mt-4">
        <div className="lg:col-span-2">
          <PositionsTable positions={positions} />
        </div>
        <div>
          <StrategyTable strategies={strategies} />
        </div>
      </div>

      {/* Recent Trades (full width) */}
      <div className="mt-4">
        <TradesTable trades={trades} />
      </div>
    </main>
  );
}
