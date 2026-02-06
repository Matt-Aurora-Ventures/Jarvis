'use client';

export function Footer() {
    return (
        <footer className="w-full py-6 mt-12 border-t border-theme-cyan/10 bg-theme-dark/80 backdrop-blur-sm">
            <div className="max-w-[1920px] mx-auto px-6 flex justify-between items-center text-sm text-theme-muted font-mono">
                <div className="flex gap-6">
                    <span>SYSTEM: ONLINE</span>
                    <span className="text-theme-cyan">V.5.0.1 (BETA)</span>
                </div>
                <div className="opacity-50">
                    POWERED BY SOLANA • BAGS.FM • JUPITER
                </div>
            </div>
        </footer>
    );
}
