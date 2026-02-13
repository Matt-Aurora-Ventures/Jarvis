import type { AutonomyDecision, AutonomyDecisionTarget } from './types';

const DECISIONS = new Set(['hold', 'adjust', 'rollback', 'disable_strategy']);

function asObject(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asString(value: unknown): string {
  return String(value ?? '').trim();
}

function asNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return n;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((v) => asString(v)).filter(Boolean);
}

function extractJsonBlock(raw: string): string | null {
  const text = String(raw || '').trim();
  if (!text) return null;
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}');
  if (start < 0 || end <= start) return null;
  return text.slice(start, end + 1);
}

function parseTargets(value: unknown): AutonomyDecisionTarget[] {
  if (!Array.isArray(value)) return [];
  const out: AutonomyDecisionTarget[] = [];
  for (const row of value) {
    const obj = asObject(row);
    if (!obj) continue;
    const strategyId = asString(obj.strategyId);
    if (!strategyId) continue;
    const patchObj = asObject(obj.patch) || {};
    const patch: Record<string, number> = {};
    for (const [k, v] of Object.entries(patchObj)) {
      const n = asNumber(v, Number.NaN);
      if (Number.isFinite(n)) patch[k] = n;
    }
    out.push({
      strategyId,
      patch: patch as AutonomyDecisionTarget['patch'],
      reason: asString(obj.reason),
      confidence: Math.max(0, Math.min(1, asNumber(obj.confidence, 0))),
      evidence: asStringArray(obj.evidence),
    });
  }
  return out;
}

export function validateAutonomyDecision(input: unknown): {
  ok: boolean;
  decision: AutonomyDecision | null;
  errors: string[];
} {
  const errors: string[] = [];
  const obj = asObject(input);
  if (!obj) {
    return { ok: false, decision: null, errors: ['Decision payload is not a JSON object'] };
  }

  const decision = asString(obj.decision);
  if (!DECISIONS.has(decision)) {
    errors.push(`Unsupported decision value: ${decision || '(missing)'}`);
  }
  const reason = asString(obj.reason);
  if (!reason) errors.push('Missing top-level reason');

  const confidence = Math.max(0, Math.min(1, asNumber(obj.confidence, 0)));
  const targets = parseTargets(obj.targets);
  const evidence = asStringArray(obj.evidence);
  const constraintsObj = asObject(obj.constraintsCheck);
  const alternatives = Array.isArray(obj.alternativesConsidered)
    ? obj.alternativesConsidered
      .map((row) => {
        const item = asObject(row);
        if (!item) return null;
        const option = asString(item.option);
        const rejectedBecause = asString(item.rejectedBecause);
        if (!option || !rejectedBecause) return null;
        return { option, rejectedBecause };
      })
      .filter((v): v is { option: string; rejectedBecause: string } => !!v)
    : [];

  if (!constraintsObj) {
    errors.push('Missing constraintsCheck');
  }
  const constraintsPass = !!constraintsObj?.pass;
  const constraintsReasons = asStringArray(constraintsObj?.reasons);
  if (constraintsReasons.length === 0) {
    errors.push('constraintsCheck.reasons must be non-empty');
  }
  if (alternatives.length === 0) {
    errors.push('alternativesConsidered must be non-empty');
  }

  if (decision === 'adjust' && targets.length === 0) {
    errors.push('adjust decision requires at least one target');
  }

  if (errors.length > 0) {
    return { ok: false, decision: null, errors };
  }

  const parsed: AutonomyDecision = {
    decision: decision as AutonomyDecision['decision'],
    reason,
    confidence,
    targets,
    evidence,
    constraintsCheck: {
      pass: constraintsPass,
      reasons: constraintsReasons,
    },
    alternativesConsidered: alternatives,
  };

  return { ok: true, decision: parsed, errors: [] };
}

export function parseAndValidateAutonomyDecision(raw: string): {
  ok: boolean;
  decision: AutonomyDecision | null;
  errors: string[];
  rawJson: string | null;
} {
  const block = extractJsonBlock(raw);
  if (!block) {
    return {
      ok: false,
      decision: null,
      errors: ['No JSON object found in model response'],
      rawJson: null,
    };
  }
  try {
    const decoded = JSON.parse(block);
    const validated = validateAutonomyDecision(decoded);
    return {
      ...validated,
      rawJson: block,
    };
  } catch (error) {
    return {
      ok: false,
      decision: null,
      errors: [`Failed to parse model JSON: ${error instanceof Error ? error.message : 'unknown'}`],
      rawJson: block,
    };
  }
}
