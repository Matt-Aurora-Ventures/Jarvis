'use client';

/**
 * Jarvis Intelligence Dashboard Page
 * 
 * Premium sentiment intelligence hub with real-time market data
 */

import { SentimentDashboard } from '@/components/features/SentimentDashboard';
export default function IntelligencePage() {
    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden font-sans">
            {/* Ambient Background Orbs */}
            <div className="fixed inset-0 -z-10 overflow-hidden pointer-events-none">
                <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-accent-neon/[0.04] rounded-full blur-[128px]" />
                <div className="absolute bottom-1/3 right-1/4 w-80 h-80 bg-accent-neon/[0.03] rounded-full blur-[128px]" />
                <div className="absolute top-2/3 left-1/2 w-64 h-64 bg-accent-success/[0.02] rounded-full blur-[128px]" />
            </div>

            <main className="flex-1 pt-24 relative z-10">
                <SentimentDashboard />
            </main>
        </div>
    );
}
