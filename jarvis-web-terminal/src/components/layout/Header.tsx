'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ShieldReactor } from '@/components/visuals/ShieldReactor';
import { MarketRegime } from '@/components/features/MarketRegime';
import { WalletButton } from '@/components/ui/WalletButton';
import { ThemeToggleInline } from '@/components/ui/ThemeToggle';
import { useMarketRegime } from '@/hooks/useMarketRegime';
import { useTheme } from '@/context/ThemeContext';
import { useToast } from '@/components/ui/Toast';
import {
    Sun,
    Moon,
    Zap,
    BarChart3,
    Rocket,
    Newspaper,
    Settings,
    Bell,
    TrendingUp,
    Activity,
    Menu,
    X,
    Gauge
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

export function Header() {
    const { data } = useMarketRegime();
    const { theme, toggleTheme } = useTheme();
    const { info } = useToast();
    const [scrolled, setScrolled] = useState(false);
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [notificationCount] = useState(0);

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
                    </div>

                    {/* Center: Market Regime (hidden on mobile/tablet) */}
                    <div className="hidden xl:block">
                        <MarketRegime data={data} />
                    </div>

                    {/* Right: Actions */}
                    <div className="flex items-center gap-2 lg:gap-3">
                        {/* Live Status */}
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-bg-tertiary/50 border border-border-primary">
                            <Activity className="w-3 h-3 text-accent-success animate-pulse" />
                            <span className="text-[10px] font-mono text-text-muted uppercase">Live</span>
                        </div>

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
                        <button onClick={() => info('Notifications coming soon')} className="relative p-2.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover transition-all">
                            <Bell className="w-5 h-5 text-text-secondary" />
                            {notificationCount > 0 && (
                                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full bg-accent-danger text-[10px] font-bold flex items-center justify-center text-white">
                                    {notificationCount}
                                </span>
                            )}
                        </button>

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
