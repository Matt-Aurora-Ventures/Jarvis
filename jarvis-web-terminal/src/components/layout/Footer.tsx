'use client';

export function Footer() {
    return (
        <footer className="w-full py-4 mt-6 border-t border-accent-neon/10 bg-bg-secondary/80 backdrop-blur-sm">
            <div className="max-w-[1920px] mx-auto px-6 flex justify-between items-center text-sm text-text-muted font-mono">
                <div className="flex gap-6">
                    <span>SYSTEM: ONLINE</span>
                    <span className="text-accent-neon">V.5.0.1 (BETA)</span>
                </div>
                <div className="opacity-50">
                    POWERED BY SOLANA • BAGS.FM • JUPITER
                </div>
            </div>
        </footer>
    );
}
