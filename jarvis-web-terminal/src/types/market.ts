export interface MarketRegime {
    regime: 'BULL' | 'BEAR' | 'CRAB';
    risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    sol_trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    sol_change_24h: number;
}
