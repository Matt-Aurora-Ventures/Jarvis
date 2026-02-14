import type { SniperConfig } from '@/stores/useSniperStore';
import type {
  StrategyOverrideConfigPatch,
  StrategyOverridePatch,
  StrategyOverrideSnapshot,
  OverrideMutableField,
} from './types';
import { createHash } from 'crypto';

const ALLOWED_FIELDS: OverrideMutableField[] = [
  'stopLossPct',
  'takeProfitPct',
  'trailingStopPct',
  'minScore',
  'minLiquidityUsd',
  'slippageBps',
  'maxTokenAgeHours',
  'minMomentum1h',
  'minVolLiqRatio',
];

const ABS_MAX_DELTA_FIELDS = new Set<OverrideMutableField>([
  'stopLossPct',
  'takeProfitPct',
  'trailingStopPct',
  'slippageBps',
]);

const RELATIVE_MAX_DELTA_FIELDS = new Set<OverrideMutableField>([
  'minScore',
  'minLiquidityUsd',
  'maxTokenAgeHours',
  'minMomentum1h',
  'minVolLiqRatio',
]);

function safeNumber(value: unknown): number | null {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n;
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function signatureForSnapshot(snapshot: Omit<StrategyOverrideSnapshot, 'signature'>): string {
  const canonical = JSON.stringify(snapshot);
  return createHash('sha256').update(canonical).digest('hex');
}

export function normalizePatchAgainstBase(
  baseConfig: SniperConfig,
  rawPatch: Record<string, unknown>,
): { patch: StrategyOverrideConfigPatch; violations: string[] } {
  const out: StrategyOverrideConfigPatch = {};
  const violations: string[] = [];

  for (const [rawKey, rawValue] of Object.entries(rawPatch || {})) {
    const key = rawKey as OverrideMutableField;
    if (!ALLOWED_FIELDS.includes(key)) {
      violations.push(`Field not allowed: ${rawKey}`);
      continue;
    }
    const num = safeNumber(rawValue);
    if (num == null) {
      violations.push(`Field is not numeric: ${rawKey}`);
      continue;
    }

    const base = safeNumber((baseConfig as unknown as Record<string, unknown>)[key]);
    if (base == null) {
      violations.push(`Base config missing numeric field: ${rawKey}`);
      continue;
    }

    let normalized = num;
    if (ABS_MAX_DELTA_FIELDS.has(key)) {
      normalized = clamp(num, base - 5, base + 5);
    } else if (RELATIVE_MAX_DELTA_FIELDS.has(key)) {
      const rel = Math.abs(base) * 0.15;
      normalized = rel > 0 ? clamp(num, base - rel, base + rel) : num;
    }

    if (key === 'minLiquidityUsd' || key === 'maxTokenAgeHours' || key === 'slippageBps') {
      normalized = Math.max(0, Math.round(normalized));
    } else {
      normalized = Number(normalized.toFixed(4));
    }
    out[key] = normalized;
  }

  return { patch: out, violations };
}

export function mergeRuntimeConfigWithStrategyOverride(
  config: SniperConfig,
  activePresetId: string,
  snapshot: StrategyOverrideSnapshot | null | undefined,
): SniperConfig {
  if (!snapshot || !Array.isArray(snapshot.patches) || snapshot.patches.length === 0) {
    return config;
  }
  const match = snapshot.patches.find((p) => p.strategyId === activePresetId);
  if (!match || !match.patch) return config;
  return {
    ...config,
    ...match.patch,
  };
}

export function applyOverrideDecision(
  current: StrategyOverrideSnapshot | null | undefined,
  args: {
    cycleId: string;
    updatedAt?: string;
    patches: StrategyOverridePatch[];
  },
): StrategyOverrideSnapshot {
  const nextNoSig: Omit<StrategyOverrideSnapshot, 'signature'> = {
    version: Math.max(1, Number(current?.version || 0) + 1),
    updatedAt: args.updatedAt || new Date().toISOString(),
    cycleId: args.cycleId,
    patches: args.patches,
  };
  return {
    ...nextNoSig,
    signature: signatureForSnapshot(nextNoSig),
  };
}

export function emptyOverrideSnapshot(): StrategyOverrideSnapshot {
  const base: Omit<StrategyOverrideSnapshot, 'signature'> = {
    version: 1,
    updatedAt: new Date(0).toISOString(),
    cycleId: '',
    patches: [],
  };
  return {
    ...base,
    signature: signatureForSnapshot(base),
  };
}

