'use client';

import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { ShieldReactor } from '@/components/visuals/ShieldReactor';
import { MarketRegime } from '@/components/features/MarketRegime';
import { WalletButton } from '@/components/ui/WalletButton';
import { ThemeToggleInline } from '@/components/ui/ThemeToggle';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import { useTreasuryMetrics } from '@/hooks/useTreasuryMetrics';
import { useTheme } from '@/context/ThemeContext';
import { useToast } from '@/components/ui/Toast';
import { useNetworkStatus, formatLatency, formatBlockHeight } from '@/hooks/useNetworkStatus';
import { KeyboardShortcutsHelp } from '@/components/ui/KeyboardShortcutsHelp';
import { NotificationBell } from '@/components/features/NotificationBell';
import {
    Sun,
    Moon,
    Zap,
    BarChart3,
    Rocket,
    Newspaper,
    Settings,
    TrendingUp,
    Activity,
    Menu,
    X,
    Gauge,
    Wifi,
    WifiOff,
    RefreshCw
} from 'lucide-react';

interface NavItem {
    label: string;
    href: string;
    icon: React.ReactNode;
    badge?: string;
}

const NAV_ITEMS: NavItem[] = [
    { label: 'Dashboard', href: '/', icon: <Gauge className="w-4 h-4" /> },
    { label: 'Trade', href: '/trade', icon: <TrendingUp className="w-4 h-4" /> },
    { label: 'Positions', href: '/positions', icon: <BarChart3 className="w-4 h-4" /> },
    { label: 'Launches', href: '/launches', icon: <Rocket className="w-4 h-4" />, badge: 'LIVE' },
    { label: 'Intel', href: '/intel', icon: <Newspaper className="w-4 h-4" /> },
];

function NetworkStatusIndicator() {
    const { status, latency, blockHeight, refresh } = useNetworkStatus();

    const statusConfig = {
        connected: {
            dotColor: 'bg-accent-success',
            textColor: 'text-accent-success',
            label: 'LIVE',
            icon: <Wifi className="w-3 h-3" />,
        },
        degraded: {
            dotColor: 'bg-accent-warning',
            textColor: 'text-accent-warning',
            label: 'SLOW',
            icon: <Wifi className="w-3 h-3" />,
        },
        disconnected: {
            dotColor: 'bg-accent-error',
            textColor: 'text-accent-error',
            label: 'DOWN',
            icon: <WifiOff className="w-3 h-3" />,
        },
    };

    const config = statusConfig[status];

    return (
        <button
            onClick={refresh}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-tertiary/50 border border-border-primary hover:bg-bg-tertiary transition-all group cursor-pointer"
            title={`Solana RPC: ${status} | Latency: ${formatLatency(latency)} | Slot: ${formatBlockHeight(blockHeight)} | Click to refresh`}
        >
            <span className="relative flex h-2 w-2">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${config.dotColor} opacity-75`} />
                <span className={`relative inline-flex rounded-full h-2 w-2 ${config.dotColor}`} />
            </span>
            <span className={`${config.textColor} group-hover:text-text-primary transition-colors`}>
                {config.icon}
            </span>
            <span className={`text-[10px] font-mono ${config.textColor} uppercase`}>
                {config.label}
            </span>
            {latency > 0 && (
                <span className="text-[10px] font-mono text-text-muted">
                    {formatLatency(latency)}
                </span>
            )}
            {blockHeight && (
                <span className="text-[10px] font-mono text-text-muted hidden lg:inline">
                    #{formatBlockHeight(blockHeight)}
                </span>
            )}
        </button>
    );
}

/* -- Seeded PRNG for deterministic sparkline data ----------------------- */
function generateTrendData(seed: number, points = 10): number[] {
    let s = Math.abs(seed * 2654435761) >>> 0 || 1;
    function rand() {
        s = (s + 0x6D2B79F5) | 0;
        let t = Math.imul(s ^ (s >>> 15), 1 | s);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    }
    const base = Math.abs(seed) || 1;
    const data = [base];
    for (let i = 1; i < points; i++) {
        const delta = (rand() - 0.45) * base * 0.1;
        data.push(Math.max(0, data[i - 1] + delta));
    }
    return data;
}

/* -- Tiny inline SVG sparkline ----------------------------------------- */
function MiniSparkline({ data, positive }: { data: number[]; positive: boolean }) {
    const width = 40;
    const height = 16;

    const points = useMemo(() => {
        if (data.length < 2) return '';
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;
        return data
            .map((v, i) => {
                const x = (i / (data.length - 1)) * width;
                const y = height - ((v - min) / range) * height;
                return `${x},${y}`;
            })
            .join(' ');
    }, [data]);

    const strokeColor = positive ? 'var(--accent-neon)' : 'var(--accent-error)';
    const fillColor = positive ? 'var(--accent-neon)' : 'var(--accent-error)';

    if (data.length < 2) return null;

    // Build the fill polygon: line points + bottom-right + bottom-left
    const fillPoints = `${points} ${width},${height} 0,${height}`;

    return (
        <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} fill="none" className="shrink-0">
            <defs>
                <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={fillColor} stopOpacity="0.3" />
                    <stop offset="100%" stopColor={fillColor} stopOpacity="0" />
                </linearGradient>
            </defs>
            <polygon points={fillPoints} fill="url(#sparkFill)" />
            <polyline
                points={points}
                stroke={strokeColor}
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                fill="none"
            />
        </svg>
    );
}

/* -- Portfolio snippet for the header bar ------------------------------ */
function PortfolioSnippet() {
    const { pnl, rawData } = useTreasuryMetrics();
    const positive = rawData.totalPnL >= 0;

    const sparkData = useMemo(
        () => generateTrendData(rawData.totalPnL || 1, 10),
        [rawData.totalPnL]
    );

    // PNL percent: derive from totalPnL as a rough indicator
    const pnlPercent = rawData.totalPnL !== 0
        ? ((rawData.totalPnL / (Math.abs(rawData.totalPnL) + 100)) * 100)
        : 0;
    const pnlPercentFormatted = (pnlPercent >= 0 ? '+' : '') + pnlPercent.toFixed(1) + '%';

    return (
        <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-bg-tertiary/30 border border-border-primary rounded-lg">
            <div className="flex flex-col items-end">
                <span className="text-[10px] text-text-muted font-mono leading-none">PNL</span>
                <span className={`text-xs font-mono font-semibold leading-tight ${positive ? 'text-accent-neon' : 'text-accent-error'}`}>
                    {pnl}
                </span>
            </div>
            <MiniSparkline data={sparkData} positive={positive} />
            <span className={`text-[10px] font-mono font-medium px-1.5 py-0.5 rounded ${
                positive
                    ? 'bg-accent-neon/10 text-accent-neon'
                    : 'bg-accent-error/10 text-accent-error'
            }`}>
                {pnlPercentFormatted}
            </span>
        </div>
    );
}

export function Header() {
    const { data } = useMarketRegime();
    const { theme, toggleTheme } = useTheme();
    const { info } = useToast();
    const [scrolled, setScrolled] = useState(false);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    // Track scroll for enhanced header blur
    useEffect(() => {
        const handleScroll = () => setScrolled(window.scrollY > 10);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    return (
        <header className={`
            fixed top-0 left-0 right-0 z-50 transition-all duration-300
            ${scrolled
                ? 'bg-bg-primary/90 backdrop-blur-xl border-b border-border-primary shadow-lg'
                : 'bg-bg-primary/80 backdrop-blur-xl border-b border-border-primary'}
        `}>
            <div className="max-w-[1920px] mx-auto px-4 lg:px-6">
                <div className="flex items-center justify-between h-14 lg:h-16">
                    {/* Left: Logo & Nav */}
                    <div className="flex items-center gap-6 lg:gap-8">
                        <Link href="/" className="flex items-center gap-3 group">
                            <div className="relative">
                                <ShieldReactor />
                                {/* Live indicator */}
                                <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 bg-accent-neon rounded-full animate-pulse" />
                            </div>
                            <div className="hidden sm:block">
                                <h1 className="font-display text-xl lg:text-2xl font-bold tracking-tight text-text-primary">
                                    JARVIS<span className="text-accent-neon">.TERMINAL</span>
                                </h1>
                                <p className="text-[10px] text-text-muted font-mono -mt-0.5 tracking-wider">
                                    SENTIMENT INTELLIGENCE
                                </p>
                            </div>
                        </Link>

                        {/* Navigation */}
                        <nav className="hidden lg:flex items-center gap-1">
                            {NAV_ITEMS.map((item) => (
                                <Link
                                    key={item.href}
                                    href={item.href}
                                    className="relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-all group"
                                >
                                    {item.icon}
                                    <span>{item.label}</span>
                                    {item.badge && (
                                        <span className="px-1.5 py-0.5 rounded-full bg-accent-neon/20 text-accent-neon text-[10px] font-mono font-bold animate-pulse">
                                            {item.badge}
                                        </span>
                                    )}
                                    {/* Hover underline */}
                                    <span className="absolute bottom-0 left-1/2 -translate-x-1/2 w-0 h-0.5 bg-accent-neon rounded-full group-hover:w-8 transition-all duration-300" />
                                </Link>
                            ))}
                        </nav>

                        {/* Portfolio Sparkline */}
                        <PortfolioSnippet />
                    </div>

                    {/* Center: Market Regime (hidden on mobile/tablet) */}
                    <div className="hidden xl:block">
                        <MarketRegime data={data} />
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-2 lg:gap-3">
                        {/* Network Status */}
                        <NetworkStatusIndicator />

                        {/* Theme Toggle */}
                        <div className="hidden sm:block">
                            <ThemeToggleInline />
                        </div>

                        {/* Simple theme toggle for mobile */}
                        <button
                            onClick={toggleTheme}
                            className="sm:hidden p-2.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover transition-all group"
                            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
                        >
                            {theme === 'light' ? (
                                <Moon className="w-5 h-5 text-text-secondary group-hover:text-text-primary transition-colors" />
                            ) : (
                                <Sun className="w-5 h-5 text-text-secondary group-hover:text-accent-neon transition-colors" />
                            )}
                        </button>

                        {/* Notifications */}
                        <NotificationBell />

                        {/* Keyboard Shortcuts */}
                        <div className="hidden md:block">
                            <KeyboardShortcutsHelp />
                        </div>

                        {/* Settings */}
                        <button onClick={() => info('Settings coming soon')} className="hidden md:block p-2.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover transition-all">
                            <Settings className="w-5 h-5 text-text-secondary" />
                        </button>

                        {/* Wallet */}
                        <div className="relative z-50 hidden sm:block">
                            <WalletButton />
                        </div>

                        {/* Mobile Menu Toggle */}
                        <button
                            className="lg:hidden p-2.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary transition-all"
                            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                        >
                            {mobileMenuOpen ? (
                                <X className="w-5 h-5 text-text-primary" />
                            ) : (
                                <Menu className="w-5 h-5 text-text-secondary" />
                            )}
                        </button>
                    </div>
                </div>
            </div>

            {/* Mobile Menu */}
            {mobileMenuOpen && (
                <div className="lg:hidden absolute top-full left-0 right-0 bg-bg-primary/95 backdrop-blur-xl border-b border-border-primary">
                    <nav className="px-4 py-4 space-y-1">
                        {NAV_ITEMS.map((item) => (
                            <Link
                                key={item.href}
                                href={item.href}
                                className="flex items-center gap-3 px-4 py-3 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-tertiary transition-all"
                                onClick={() => setMobileMenuOpen(false)}
                            >
                                {item.icon}
                                <span className="font-medium">{item.label}</span>
                                {item.badge && (
                                    <span className="ml-auto px-2 py-0.5 rounded-full bg-accent-neon/20 text-accent-neon text-xs font-mono font-bold">
                                        {item.badge}
                                    </span>
                                )}
                            </Link>
                        ))}

                        {/* Mobile Wallet */}
                        <div className="pt-3 mt-3 border-t border-border-primary">
                            <div className="px-4 sm:hidden">
                                <WalletButton />
                            </div>
                        </div>

                        {/* Mobile Market Regime */}
                        <div className="pt-3 mt-3 border-t border-border-primary xl:hidden">
                            <div className="px-4">
                                <p className="text-xs text-text-muted mb-2">MARKET REGIME</p>
                                <MarketRegime data={data} />
                            </div>
                        </div>
                    </nav>
                </div>
            )}
        </header>
    );
}
