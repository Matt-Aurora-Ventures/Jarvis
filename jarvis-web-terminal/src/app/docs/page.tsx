import { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
    title: 'Jarvis Terminal - Documentation',
};

export default function DocsPage() {
    return (
        <div className="min-h-screen bg-theme-white text-theme-ink p-8 pt-32 font-sans relative overflow-hidden">
            {/* Header */}
            <header className="fixed top-0 left-0 right-0 z-50 p-6 flex justify-between items-center backdrop-blur-sm bg-theme-white/30 border-b border-theme-border/50">
                <Link href="/" className="font-display text-2xl font-bold tracking-tight hover:opacity-80 transition-opacity">
                    JARVIS<span className="text-accent-neon">.TERMINAL</span>
                </Link>
            </header>

            <main className="max-w-4xl mx-auto relative z-10">
                <h1 className="text-4xl font-display font-bold mb-8">System Documentation</h1>

                <div className="card-glass-white p-8 mb-8">
                    <h2 className="text-2xl font-bold mb-4 font-display">1. Overview</h2>
                    <p className="text-theme-muted leading-relaxed mb-4">
                        Jarvis is an advanced sentiment analysis terminal for the Solana ecosystem.
                        It aggregates data not just from price action, but from the social fabric of the crypto wold.
                    </p>
                </div>

                <div className="card-glass-white p-8 mb-8">
                    <h2 className="text-2xl font-bold mb-4 font-display">2. Market Regime</h2>
                    <p className="text-theme-muted leading-relaxed mb-4">
                        The content displayed in the header represents the global state of the market.
                        <br />
                        <span className="text-accent-neon font-bold">BULL</span>: Aggressive accumulation recommended.
                        <br />
                        <span className="text-accent-error font-bold">BEAR</span>: Capital preservation mode active.
                    </p>
                </div>

                <Link href="/" className="btn-neon inline-block no-underline">
                    RETURN TO TERMINAL
                </Link>
            </main>
        </div>
    );
}
