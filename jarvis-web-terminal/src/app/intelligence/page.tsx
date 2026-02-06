'use client';

/**
 * Jarvis Intelligence Dashboard Page
 * 
 * Premium sentiment intelligence hub with real-time market data
 */

import { SentimentDashboard } from '@/components/features/SentimentDashboard';
import { NeuralLattice } from '@/components/visuals/NeuralLattice';

export default function IntelligencePage() {
    return (
        <div className="min-h-screen flex flex-col relative overflow-hidden font-sans">
            <NeuralLattice />

            <main className="flex-1 pt-24 relative z-10">
                <SentimentDashboard />
            </main>
        </div>
    );
}
