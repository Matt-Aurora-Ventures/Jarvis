'use client';

const EXTERNAL_LINKS = [
    { label: 'DexScreener', href: 'https://dexscreener.com/solana' },
    { label: 'Solscan', href: 'https://solscan.io' },
    { label: 'Jupiter', href: 'https://jup.ag' },
    { label: 'Bags.fm', href: 'https://bags.fm' },
    { label: 'Docs', href: '/docs' },
];

export function Footer() {
    return (
        <footer className="w-full py-3 border-t border-border-primary bg-bg-secondary/60 backdrop-blur-sm">
            <div className="max-w-[1920px] mx-auto px-4 flex flex-col sm:flex-row justify-between items-center gap-2">
                <div className="flex items-center gap-4 text-[10px] font-mono text-text-muted">
                    <span>SYSTEM: ONLINE</span>
                    <span className="px-1.5 py-0.5 rounded bg-accent-neon/15 text-accent-neon border border-accent-neon/30 font-bold">v5.0.1</span>
                </div>
                <div className="flex items-center gap-3">
                    {EXTERNAL_LINKS.map((link, i) => (
                        <span key={link.label} className="flex items-center gap-3">
                            <a
                                href={link.href}
                                target={link.href.startsWith('http') ? '_blank' : undefined}
                                rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                                className="text-[10px] font-mono text-text-muted hover:text-accent-neon transition-colors"
                            >
                                {link.label}
                            </a>
                            {i < EXTERNAL_LINKS.length - 1 && (
                                <span className="text-border-primary text-[8px]">&middot;</span>
                            )}
                        </span>
                    ))}
                </div>
            </div>
        </footer>
    );
}
