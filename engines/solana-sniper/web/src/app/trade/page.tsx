import { TradingTerminal } from '@/components/TradingTerminal';
import { NavBar } from '@/components/NavBar';
import { SystemStatus } from '@/components/SystemStatus';

export default function TradePage() {
  return (
    <main className="min-h-screen p-6 max-w-[1600px] mx-auto">
      {/* Ambient Background */}
      <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#22c55e08] rounded-full blur-[128px]" />
        <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-[#22c55e05] rounded-full blur-[128px]" />
      </div>

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

      {/* Terminal Label */}
      <div className="flex items-center gap-3 mb-6">
        <div className="h-px flex-1 bg-gradient-to-r from-[var(--border)] to-transparent" />
        <span className="text-[10px] uppercase tracking-[0.2em] text-[var(--text-muted)]">Trading Terminal</span>
        <div className="h-px flex-1 bg-gradient-to-l from-[var(--border)] to-transparent" />
      </div>

      <TradingTerminal />
    </main>
  );
}
