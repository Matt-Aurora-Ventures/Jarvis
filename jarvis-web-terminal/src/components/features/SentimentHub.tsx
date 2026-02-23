import { TokenSentiment } from '@/types/trading';

interface SentimentHubProps {
    data: TokenSentiment[];
}

export function SentimentHub({ data }: SentimentHubProps) {
    return (
        <div className="w-full">
            <div className="flex justify-between items-end mb-6">
                <h2 className="text-3xl font-display font-bold text-theme-ink">Sentiment Hub</h2>
                <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-neon opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-neon"></span>
                    </span>
                    <span className="text-xs font-mono text-text-muted uppercase tracking-widest">Live Analysis</span>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                {data.map((token) => (
                    <div key={token.symbol} className="card-glass-white p-6 relative overflow-hidden group hover:scale-[1.02] transition-transform duration-300">
                        {/* Glow Effect on Hover */}
                        <div className={`absolute top-0 right-0 w-32 h-32 blur-[60px] rounded-full opacity-0 group-hover:opacity-20 transition-opacity duration-500 pointer-events-none -mr-10 -mt-10 ${token.sentiment === 'bullish' ? 'bg-accent-neon' : token.sentiment === 'bearish' ? 'bg-accent-error' : 'bg-gray-400'
                            }`}></div>

                        <div className="flex justify-between items-start mb-4 relative z-10">
                            <div>
                                <h3 className="text-xl font-bold font-display text-theme-ink">{token.symbol}</h3>
                                <span className="text-xs font-mono text-text-muted">{token.name}</span>
                            </div>
                            <div className={`px-2 py-1 rounded text-[10px] font-bold tracking-wider uppercase border ${token.signal === 'STRONG_BUY' || token.signal === 'BUY'
                                ? 'bg-accent-neon/10 border-accent-neon text-accent-neon'
                                : token.signal === 'STRONG_SELL' || token.signal === 'SELL'
                                    ? 'bg-accent-error/10 border-accent-error text-accent-error'
                                    : 'bg-gray-100 border-gray-200 text-gray-500'
                                }`}>
                                {token.signal.replace('_', ' ')}
                            </div>
                        </div>

                        <div className="flex items-end gap-2 mb-4 relative z-10">
                            <span className="text-2xl font-mono font-bold text-theme-ink">
                                ${token.price_usd < 1 ? token.price_usd.toFixed(6) : token.price_usd.toFixed(2)}
                            </span>
                            <span className={`text-xs font-mono font-bold mb-1 ${token.change_24h >= 0 ? 'text-accent-neon' : 'text-accent-error'}`}>
                                {token.change_24h >= 0 ? '+' : ''}{token.change_24h}%
                            </span>
                        </div>

                        <div className="space-y-2 relative z-10">
                            <div className="flex justify-between text-xs font-mono text-text-muted">
                                <span>SENTIMENT SCORE</span>
                                <span>{token.score}/100</span>
                            </div>
                            <div className="h-1.5 w-full bg-gray-100 rounded-full overflow-hidden">
                                <div
                                    className={`h-full rounded-full transition-all duration-1000 ${token.sentiment === 'bullish' ? 'bg-accent-neon' : token.sentiment === 'bearish' ? 'bg-accent-error' : 'bg-gray-400'
                                        }`}
                                    style={{ width: `${token.score}%` }}
                                ></div>
                            </div>
                        </div>

                        <p className="mt-4 text-xs text-text-muted leading-relaxed line-clamp-2 min-h-[2.5em]">
                            {token.summary}
                        </p>

                    </div>
                ))}
            </div>
        </div>
    );
}
