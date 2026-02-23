export interface InvestmentBasketTokenView {
  symbol: string;
  weight: number;
  priceUsd: number;
  liquidityUsd: number;
  usdValue: number;
}

export interface InvestmentBasketView {
  tokens: InvestmentBasketTokenView[];
  totalNav: number;
  navPerShare: number;
}

export interface InvestmentPerformancePoint {
  timestamp: string;
  nav: number;
}

export interface InvestmentDecisionView {
  id: string;
  timestamp: string;
  action: 'REBALANCE' | 'HOLD' | 'EMERGENCY_EXIT' | string;
  confidence: number;
  navAtDecision: number;
  summary: string;
  newWeights?: Record<string, number>;
}

function asNumber(value: unknown): number {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

export function normalizeInvestmentBasket(payload: unknown): InvestmentBasketView {
  const obj = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const tokenMap = (obj.tokens && typeof obj.tokens === 'object' ? obj.tokens : {}) as Record<string, unknown>;

  const totalNav = asNumber(obj.total_nav ?? obj.nav_usd ?? obj.totalNav);
  const tokens = Object.entries(tokenMap)
    .map(([symbol, raw]) => {
      const row = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
      const weight = asNumber(row.weight);
      const priceUsd = asNumber(row.price_usd ?? row.priceUsd);
      const liquidityUsd = asNumber(row.liquidity_usd ?? row.liquidityUsd);
      const usdValue = totalNav > 0 ? weight * totalNav : asNumber(row.usd_value ?? row.value_usd);
      return { symbol, weight, priceUsd, liquidityUsd, usdValue };
    })
    .sort((a, b) => b.weight - a.weight);

  return {
    tokens,
    totalNav,
    navPerShare: asNumber(obj.nav_per_share ?? obj.navPerShare ?? totalNav),
  };
}

export function normalizeInvestmentPerformance(payload: unknown): InvestmentPerformancePoint[] {
  if (Array.isArray(payload)) {
    return payload
      .map((p) => {
        const row = (p && typeof p === 'object' ? p : {}) as Record<string, unknown>;
        return {
          timestamp: String(row.timestamp ?? row.ts ?? ''),
          nav: asNumber(row.nav ?? row.nav_usd),
        };
      })
      .filter((p) => p.timestamp.length > 0);
  }

  const obj = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>;
  const points = Array.isArray(obj.points) ? obj.points : [];
  return points
    .map((p) => {
      const row = (p && typeof p === 'object' ? p : {}) as Record<string, unknown>;
      return {
        timestamp: String(row.timestamp ?? row.ts ?? ''),
        nav: asNumber(row.nav ?? row.nav_usd),
      };
    })
    .filter((p) => p.timestamp.length > 0);
}

export function normalizeInvestmentDecisions(payload: unknown): InvestmentDecisionView[] {
  const rows = Array.isArray(payload) ? payload : [];
  return rows.map((item) => {
    const row = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>;
    return {
      id: String(row.id ?? ''),
      timestamp: String(row.timestamp ?? row.ts ?? ''),
      action: String(row.action ?? 'HOLD'),
      confidence: asNumber(row.confidence),
      navAtDecision: asNumber(row.nav_at_decision ?? row.nav_usd),
      summary: String(row.summary ?? row.reasoning ?? ''),
      newWeights: (row.new_weights ?? row.final_weights) as Record<string, number> | undefined,
    };
  });
}
