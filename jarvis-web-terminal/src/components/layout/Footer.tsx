'use client';

import { ExternalLink } from 'lucide-react';

// ── Quick Links (Solana ecosystem tools) ────────────────────────────
const QUICK_LINKS = [
    { label: 'Jupiter', href: 'https://jup.ag' },
    { label: 'DexScreener', href: 'https://dexscreener.com/solana' },
    { label: 'Birdeye', href: 'https://birdeye.so' },
    { label: 'Solscan', href: 'https://solscan.io' },
    { label: 'DeGen', href: 'https://bags.fm' },
];

// ── Powered By attribution ──────────────────────────────────────────
const POWERED_BY = [
    { label: 'Grok AI', href: 'https://x.ai' },
    { label: 'DexScreener', href: 'https://dexscreener.com' },
    { label: 'GeckoTerminal', href: 'https://www.geckoterminal.com' },
    { label: 'Jupiter', href: 'https://jup.ag' },
];

// ── Social Links (placeholder hrefs for future) ─────────────────────
const SOCIAL_LINKS = [
    { label: 'X / Twitter', href: 'https://x.com/Jarvis_lifeos' },
    { label: 'GitHub', href: 'https://github.com' },
    { label: 'Docs', href: '/docs' },
];

export function Footer() {
    const year = new Date().getFullYear();

    return (
        <footer className="w-full border-t border-border-primary bg-bg-secondary/60 backdrop-blur-sm">
            <div className="max-w-[1920px] mx-auto px-4 py-3">
                {/* Desktop: single row | Mobile: stacked */}
                <div className="flex flex-col sm:flex-row justify-between items-center gap-3">
                    {/* Left: System status + version */}
                    <div className="flex items-center gap-4 text-[10px] font-mono text-text-muted">
                        <span>SYSTEM: ONLINE</span>
                        <span className="px-1.5 py-0.5 rounded bg-accent-neon/15 text-accent-neon border border-accent-neon/30 font-bold">
                            v5.0.1
                        </span>
                        <span className="hidden sm:inline text-border-primary">&middot;</span>
                        <span className="hidden sm:inline">&copy; {year} JARVIS</span>
                    </div>

                    {/* Center: Quick links */}
                    <div className="flex items-center gap-2 flex-wrap justify-center">
                        {QUICK_LINKS.map((link, i) => (
                            <span key={link.label} className="flex items-center gap-2">
                                <a
                                    href={link.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-[10px] font-mono text-text-muted hover:text-accent-neon transition-colors"
                                >
                                    {link.label}
                                </a>
                                {i < QUICK_LINKS.length - 1 && (
                                    <span className="text-border-primary text-[8px]">&middot;</span>
                                )}
                            </span>
                        ))}
                    </div>

                    {/* Right: Social + Powered By */}
                    <div className="flex items-center gap-3">
                        {SOCIAL_LINKS.map((link) => (
                            <a
                                key={link.label}
                                href={link.href}
                                target={link.href.startsWith('http') ? '_blank' : undefined}
                                rel={link.href.startsWith('http') ? 'noopener noreferrer' : undefined}
                                className="text-[10px] font-mono text-text-muted hover:text-accent-neon transition-colors"
                            >
                                {link.label}
                            </a>
                        ))}
                    </div>
                </div>

                {/* Powered By row */}
                <div className="flex items-center justify-center gap-1.5 mt-2 pt-2 border-t border-border-primary/50">
                    <span className="text-[9px] font-mono text-text-muted/60 uppercase tracking-wider">
                        Powered by
                    </span>
                    {POWERED_BY.map((item, i) => (
                        <span key={item.label} className="flex items-center gap-1.5">
                            <a
                                href={item.href}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[9px] font-mono text-text-muted/60 hover:text-accent-neon transition-colors inline-flex items-center gap-0.5"
                            >
                                {item.label}
                                <ExternalLink className="w-2 h-2" />
                            </a>
                            {i < POWERED_BY.length - 1 && (
                                <span className="text-border-primary/50 text-[7px]">&middot;</span>
                            )}
                        </span>
                    ))}
                </div>

                {/* Mobile-only copyright */}
                <div className="sm:hidden text-center mt-2">
                    <span className="text-[9px] font-mono text-text-muted/50">
                        &copy; {year} JARVIS LifeOS
                    </span>
                </div>
            </div>
        </footer>
    );
}
