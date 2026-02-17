import { MarketRegime as MarketRegimeType } from '@/types/market';

interface MarketRegimeProps {
    data: MarketRegimeType;
}

export function MarketRegime({ data }: MarketRegimeProps) {
    const isBullish = data.regime === 'BULL';
    const isBearish = data.regime === 'BEAR';

    return (
        <div className="flex items-center gap-4 bg-bg-secondary/60 backdrop-blur-md rounded-full px-6 py-2 border border-border-primary">
            <div className="flex flex-col">
                <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">Market Regime</span>
                <div className="flex items-center gap-2">
                    <span className={`font-display font-bold text-lg ${isBullish ? 'text-accent-neon' : isBearish ? 'text-accent-error' : 'text-text-primary'
                        }`}>
                        {data.regime}
                    </span>
                    <div className="flex gap-1">
                        {isBullish && (
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-neon opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-neon"></span>
                            </span>
                        )}
                        {isBearish && (
                            <span className="relative flex h-2 w-2">
                                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-error opacity-75"></span>
                                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-error"></span>
                            </span>
                        )}
                    </div>
                </div>
            </div>

            <div className="h-8 w-px bg-border-primary mx-2"></div>

            <div className="flex flex-col">
                <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">Risk Level</span>
                <span className={`font-mono font-bold text-sm ${data.risk_level === 'LOW' ? 'text-accent-neon' :
                    data.risk_level === 'HIGH' || data.risk_level === 'CRITICAL' ? 'text-accent-error' : 'text-text-primary'
                    }`}>
                    {data.risk_level}
                </span>
            </div>

            <div className="h-8 w-px bg-border-primary mx-2"></div>

            <div className="flex flex-col">
                <span className="text-[10px] font-mono text-text-muted tracking-wider uppercase">SOL Trend</span>
                <span className={`font-mono text-sm ${data.sol_trend === 'BULLISH' ? 'text-accent-neon' : 'text-text-muted'}`}>
                    {data.sol_trend === 'BULLISH' ? '↗' : data.sol_trend === 'BEARISH' ? '↘' : '→'} {data.sol_change_24h}%
                </span>
            </div>
        </div>
    );
}
