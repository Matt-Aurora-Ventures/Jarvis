'use client';

import { useEffect } from 'react';
import { StatusBar } from '@/components/StatusBar';
import { GraduationFeed } from '@/components/GraduationFeed';
import { SniperControls } from '@/components/SniperControls';
import { PositionsPanel } from '@/components/PositionsPanel';
import { ExecutionLog } from '@/components/ExecutionLog';
import { PerformanceSummary } from '@/components/PerformanceSummary';
import { TokenChart } from '@/components/TokenChart';
import { EarlyBetaModal } from '@/components/EarlyBetaModal';
import { useSniperStore } from '@/stores/useSniperStore';
import { usePnlTracker } from '@/hooks/usePnlTracker';
import { useAutomatedRiskManagement } from '@/hooks/useAutomatedRiskManagement';
import { useTabNotifications } from '@/hooks/useTabNotifications';

const DATA_CLEAR_VERSION = 2; // bump to force-clear stale data again

export default function SniperDashboard() {
  // One-time stale data purge (runs once per DATA_CLEAR_VERSION bump)
  useEffect(() => {
    const key = 'sniper-data-cleared-v';
    const cleared = localStorage.getItem(key);
    if (cleared !== String(DATA_CLEAR_VERSION)) {
      useSniperStore.getState().resetSession();
      localStorage.setItem(key, String(DATA_CLEAR_VERSION));
    }
  }, []);

  // Real-time P&L: polls DexScreener every 3s to update position prices
  usePnlTracker();

  // Automated SL/TP: monitors positions and triggers sells when thresholds hit
  useAutomatedRiskManagement();

  // Tab title flashing for important events (snipes, TP/SL exits)
  useTabNotifications();

  return (
    <div className="min-h-screen flex flex-col overflow-x-hidden">
      <EarlyBetaModal />
      <StatusBar />

      <main className="flex-1 p-3 lg:p-4 max-w-[1920px] mx-auto w-full overflow-x-hidden">
        {/* Main 3-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr_minmax(0,360px)] gap-3 lg:gap-4 h-[calc(100vh-76px)]">
          {/* Left: Token Scanner */}
          <div className="flex flex-col min-h-0 min-w-0">
            <GraduationFeed />
          </div>

          {/* Center: Performance + Chart + Execution Log */}
          <div className="flex flex-col gap-4 min-h-0 min-w-0">
            <PerformanceSummary />
            <TokenChart />
            <div className="flex-1 min-h-0">
              <ExecutionLog />
            </div>
          </div>

          {/* Right: Controls + Positions */}
          <div className="flex flex-col gap-4 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden custom-scrollbar">
            <SniperControls />
            <PositionsPanel />
          </div>
        </div>
      </main>
    </div>
  );
}
