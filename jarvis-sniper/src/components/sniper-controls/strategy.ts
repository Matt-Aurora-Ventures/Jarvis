import type { BagsGraduation } from '@/lib/bags-api';
import type { AssetType } from '@/stores/useSniperStore';

export type StrategySuggestion = { presetId: string; reason: string } | null;

/**
 * Analyze the current scanner feed and suggest the best strategy preset.
 * Pure function, no side effects.
 */
export function suggestStrategy(
  graduations: BagsGraduation[],
  assetType: AssetType = 'memecoin',
): StrategySuggestion {
  if (graduations.length < 3) return null;

  if (assetType === 'bags') {
    const freshCount = graduations.filter((g) => (g.age_hours ?? 999) < 48).length;
    const highScoreCount = graduations.filter((g) => g.score >= 55).length;
    const momPositive = graduations.filter((g) => (g.price_change_1h ?? 0) > 0).length;
    const momPct = momPositive / graduations.length;

    if (highScoreCount >= 5) {
      return {
        presetId: 'bags_bluechip',
        reason: `${highScoreCount} high-score (55+) bags tokens — quality focus`,
      };
    }
    if (momPct >= 0.4 && graduations.length >= 10) {
      return {
        presetId: 'bags_aggressive',
        reason: `${Math.round(momPct * 100)}% positive momentum across ${graduations.length} tokens`,
      };
    }
    if (freshCount >= 3) {
      return {
        presetId: 'bags_dip_buyer',
        reason: `${freshCount} fresh bags launches (<48h)`,
      };
    }
    return {
      presetId: 'bags_bluechip',
      reason: 'Default safe bags strategy — established tokens',
    };
  }

  const liqs = graduations.map((g) => g.liquidity || 0).filter((l) => l > 0);
  const momPositive = graduations.filter((g) => (g.price_change_1h ?? 0) > 0).length;
  const momPct = momPositive / graduations.length;
  const highVolCount = graduations.filter((g) => {
    const l = g.liquidity || 0;
    const v = g.volume_24h || 0;
    return l > 0 && v / l >= 3;
  }).length;
  const freshCount = graduations.filter((g) => (g.age_hours ?? 999) < 24).length;

  const countAbove = (usd: number) => liqs.filter((l) => l >= usd).length;
  const above10k = countAbove(10000);
  const above25k = countAbove(25000);
  const above40k = countAbove(40000);
  const above100k = countAbove(100000);

  if (above100k >= 2 && momPct >= 0.4) {
    return {
      presetId: 'elite',
      reason: `${above100k} tokens above $100K liq + ${Math.round(momPct * 100)}% momentum`,
    };
  }
  if (momPct >= 0.45 && highVolCount >= 2 && above40k >= 2) {
    return {
      presetId: 'let_it_ride',
      reason: `${Math.round(momPct * 100)}% momentum + ${highVolCount} high-vol tokens`,
    };
  }
  if (freshCount >= 3 && above10k >= 3) {
    return {
      presetId: 'pump_fresh_tight',
      reason: `${freshCount} fresh tokens + active market`,
    };
  }
  if (above25k >= 3 && momPct >= 0.3) {
    return {
      presetId: 'sol_veteran',
      reason: `${above25k} tokens with $25K+ liq & ${Math.round(momPct * 100)}% momentum`,
    };
  }
  if (above40k >= 2) {
    return {
      presetId: 'hybrid_b',
      reason: `${above40k} tokens above $40K liq — balanced approach`,
    };
  }
  if (freshCount >= 4 && above10k >= 2) {
    return {
      presetId: 'micro_cap_surge',
      reason: `${freshCount} fresh micro-caps detected`,
    };
  }
  return {
    presetId: 'pump_fresh_tight',
    reason: 'Default safe strategy for mixed launch conditions',
  };
}
