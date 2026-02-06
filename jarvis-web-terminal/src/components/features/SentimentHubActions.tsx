'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useWallet } from '@solana/wallet-adapter-react';
import { useToast } from '@/components/ui/Toast';
import {
    Zap,
    BarChart3,
    Rocket,
    Search,
    Activity,
    Wallet,
    Flame,
    Sparkles,
    Star,
    Bell,
    Settings,
    RefreshCw,
    Brain,
    ExternalLink,
} from 'lucide-react';
import Link from 'next/link';

// Action button types
interface ActionButton {
    icon: React.ReactNode;
    label: string;
    onClick?: () => void;
    href?: string;
    color?: string;
    badge?: string;
    disabled?: boolean;
}

interface QuickBuyButtonProps {
    amount: number;
    onBuy: (amount: number) => void;
    disabled?: boolean;
}

function QuickBuyButton({ amount, onBuy, disabled }: QuickBuyButtonProps) {
    return (
        <button
            onClick={() => onBuy(amount)}
            disabled={disabled}
            className={`
                flex items-center gap-2 px-4 py-2.5 rounded-lg font-mono text-sm font-medium transition-all
                ${disabled
                    ? 'bg-bg-tertiary text-text-muted cursor-not-allowed'
                    : 'bg-green-500/20 text-green-400 hover:bg-green-500/30 border border-green-500/30'}
            `}
        >
            <div className="w-2 h-2 rounded-full bg-green-400" />
            Buy {amount} SOL
        </button>
    );
}

interface ActionGridButtonProps extends ActionButton {
}

function ActionGridButton({ icon, label, onClick, href, color = 'text-text-secondary', badge, disabled }: ActionGridButtonProps) {
    const content = (
        <div className={`
            flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all
            ${disabled
                ? 'bg-bg-tertiary text-text-muted cursor-not-allowed'
                : 'bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover'}
        `}>
            <span className={color}>{icon}</span>
            <span className="text-text-primary">{label}</span>
            {badge && (
                <span className="ml-auto px-1.5 py-0.5 rounded bg-accent-neon/20 text-accent-neon text-[10px] font-mono">
                    {badge}
                </span>
            )}
        </div>
    );

    if (href && !disabled) {
        return <Link href={href}>{content}</Link>;
    }

    return (
        <button onClick={onClick} disabled={disabled} className="w-full text-left">
            {content}
        </button>
    );
}

function isSolanaAddress(input: string): boolean {
    return /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(input.trim());
}

export function SentimentHubActions() {
    const router = useRouter();
    const { connected } = useWallet();
    const { warning: toastWarning, info: toastInfo } = useToast();
    const [mode, setMode] = useState<'PAPER' | 'LIVE'>('PAPER');
    const [searchToken, setSearchToken] = useState('');

    const handleQuickBuy = (amount: number) => {
        if (!connected) {
            toastWarning('Please connect your wallet first');
            return;
        }
        router.push('/trade');
    };

    const handleSearch = () => {
        const query = searchToken.trim();
        if (!query) return;

        if (isSolanaAddress(query)) {
            window.open(`https://dexscreener.com/solana/${query}`, '_blank');
        } else {
            window.open(`https://dexscreener.com/search?q=${encodeURIComponent(query)}`, '_blank');
        }
        toastInfo(`Searching DexScreener for "${query}"`);
    };

    return (
        <div className="card-glass p-4 space-y-4">
            {/* Mode Indicator */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Settings className="w-4 h-4 text-text-muted" />
                    <span className="text-xs text-text-muted">Mode:</span>
                    <button
                        onClick={() => setMode(mode === 'PAPER' ? 'LIVE' : 'PAPER')}
                        className={`
                            px-2 py-1 rounded text-xs font-mono font-bold transition-all
                            ${mode === 'LIVE'
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-yellow-500/20 text-yellow-400'}
                        `}
                    >
                        {mode === 'PAPER' && <span className="mr-1">⚪</span>}
                        {mode === 'LIVE' && <span className="mr-1">🟢</span>}
                        {mode}
                    </button>
                </div>
                <p className="text-[10px] text-text-muted italic">Tap to trade with AI-powered signals</p>
            </div>

            {/* Header */}
            <div className="flex items-center justify-center gap-2 py-2 border-y border-border-primary">
                <BarChart3 className="w-5 h-5 text-accent-neon" />
                <span className="font-display font-bold text-lg text-text-primary">SENTIMENT HUB</span>
            </div>

            {/* Top Actions Row */}
            <div className="grid grid-cols-2 gap-2">
                <ActionGridButton
                    icon={<Zap className="w-4 h-4" />}
                    label="INSTA SNIPE"
                    color="text-yellow-400"
                    href="/trade"
                />
                <ActionGridButton
                    icon={<BarChart3 className="w-4 h-4" />}
                    label="AI Report"
                    color="text-accent-neon"
                    href="/"
                />
                <ActionGridButton
                    icon={<Brain className="w-4 h-4" />}
                    label="AI Picks"
                    color="text-blue-400"
                    badge="HOT"
                    href="/"
                />
                <ActionGridButton
                    icon={<Flame className="w-4 h-4" />}
                    label="Trending"
                    color="text-orange-400"
                    href="/"
                />
            </div>

            {/* Bags Top 15 */}
            <ActionGridButton
                icon={<Rocket className="w-4 h-4" />}
                label="BAGS TOP 15"
                color="text-pink-400"
                badge="LIVE"
                href="/launches"
            />

            {/* Search Token */}
            <div className="flex gap-2">
                <div className="flex-1 relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                    <input
                        type="text"
                        value={searchToken}
                        onChange={(e) => setSearchToken(e.target.value)}
                        placeholder="Search token..."
                        className="w-full pl-10 pr-4 py-2.5 rounded-lg bg-bg-tertiary border border-border-primary text-sm font-mono text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-neon"
                        onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    />
                </div>
                <button
                    onClick={handleSearch}
                    className="px-4 py-2.5 rounded-lg bg-accent-neon text-theme-dark font-mono text-sm font-bold hover:bg-accent-neon/80 transition-all"
                >
                    <Search className="w-4 h-4" />
                </button>
            </div>

            {/* Quick Buy Buttons */}
            <div className="grid grid-cols-2 gap-2">
                <QuickBuyButton amount={0.1} onBuy={handleQuickBuy} disabled={!connected} />
                <QuickBuyButton amount={0.5} onBuy={handleQuickBuy} disabled={!connected} />
                <QuickBuyButton amount={1} onBuy={handleQuickBuy} disabled={!connected} />
                <QuickBuyButton amount={5} onBuy={handleQuickBuy} disabled={!connected} />
            </div>

            {/* Action Grid */}
            <div className="grid grid-cols-2 gap-2">
                <ActionGridButton
                    icon={<Zap className="w-4 h-4" />}
                    label="Quick Trade"
                    color="text-yellow-400"
                    href="/trade"
                />
                <ActionGridButton
                    icon={<BarChart3 className="w-4 h-4" />}
                    label="Positions"
                    color="text-blue-400"
                    href="/positions"
                />
                <ActionGridButton
                    icon={<Sparkles className="w-4 h-4" />}
                    label="AI Intel"
                    color="text-accent-neon"
                    badge="NEW"
                    href="/intel"
                />
                <ActionGridButton
                    icon={<Activity className="w-4 h-4" />}
                    label="Bags Intel"
                    color="text-green-400"
                    href="/bags-intel"
                />
            </div>

            {/* Tools */}
            <div className="grid grid-cols-2 gap-2">
                <ActionGridButton
                    icon={<Star className="w-4 h-4" />}
                    label="Watchlist"
                    color="text-yellow-400"
                    onClick={() => toastInfo('Watchlist coming soon')}
                />
                <ActionGridButton
                    icon={<Bell className="w-4 h-4" />}
                    label="Alerts"
                    color="text-red-400"
                    onClick={() => toastInfo('Price alerts coming soon')}
                />
                <ActionGridButton
                    icon={<ExternalLink className="w-4 h-4" />}
                    label="DexScreener"
                    color="text-accent-neon"
                    onClick={() => window.open('https://dexscreener.com/solana', '_blank')}
                />
                <ActionGridButton
                    icon={<Wallet className="w-4 h-4" />}
                    label="Solscan"
                    color="text-accent-neon"
                    onClick={() => window.open('https://solscan.io', '_blank')}
                />
            </div>

            {/* Bottom Actions */}
            <div className="flex gap-2 pt-2 border-t border-border-primary">
                <ActionGridButton
                    icon={<RefreshCw className="w-4 h-4" />}
                    label="Refresh"
                    color="text-text-muted"
                    onClick={() => window.location.reload()}
                />
                <ActionGridButton
                    icon={<Settings className="w-4 h-4" />}
                    label="Settings"
                    color="text-text-muted"
                    onClick={() => toastInfo('Settings coming soon')}
                />
            </div>

            {/* Connect Wallet CTA */}
            {!connected && (
                <div className="p-3 rounded-lg bg-accent-neon/10 border border-accent-neon/20 text-center">
                    <p className="text-sm text-accent-neon font-medium">
                        Connect wallet to unlock all trading features
                    </p>
                </div>
            )}
        </div>
    );
}
