'use client';

import { StatusBar } from '@/components/StatusBar';
import { GraduationFeed } from '@/components/GraduationFeed';
import { SniperControls } from '@/components/SniperControls';
import { PositionsPanel } from '@/components/PositionsPanel';
import { ExecutionLog } from '@/components/ExecutionLog';
import { PerformanceSummary } from '@/components/PerformanceSummary';
import { TokenChart } from '@/components/TokenChart';

export default function SniperDashboard() {
  return (
    <div className="min-h-screen flex flex-col">
      <StatusBar />

      <main className="flex-1 p-3 lg:p-4 max-w-[1920px] mx-auto w-full">
        {/* Main 3-column layout */}
        <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr_380px] gap-4 h-[calc(100vh-76px)]">
          {/* Left: Token Scanner */}
          <div className="flex flex-col min-h-0">
            <GraduationFeed />
          </div>

          {/* Center: Performance + Chart + Execution Log */}
          <div className="flex flex-col gap-4 min-h-0">
            <PerformanceSummary />
            <TokenChart />
            <div className="flex-1 min-h-0">
              <ExecutionLog />
            </div>
          </div>

          {/* Right: Controls + Positions */}
          <div className="flex flex-col gap-4 min-h-0 overflow-y-auto custom-scrollbar">
            <SniperControls />
            <PositionsPanel />
          </div>
        </div>
      </main>
    </div>
  );
}
