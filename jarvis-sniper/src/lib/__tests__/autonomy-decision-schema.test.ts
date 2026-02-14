import { describe, expect, it } from 'vitest';
import {
  parseAndValidateAutonomyDecision,
  validateAutonomyDecision,
} from '@/lib/autonomy/decision-schema';

describe('autonomy decision schema', () => {
  it('accepts a valid explainable decision payload', () => {
    const payload = {
      decision: 'adjust',
      reason: 'Recent quality metrics improved with controlled risk reduction.',
      confidence: 0.78,
      targets: [
        {
          strategyId: 'pump_fresh_tight',
          patch: { stopLossPct: 19, takeProfitPct: 48 },
          reason: 'Lower volatility regime supports slightly wider TP.',
          confidence: 0.75,
          evidence: ['volatilityRegime.avgMomentum1h', 'wrGate.primary'],
        },
      ],
      evidence: ['matrix.strategyRows', 'matrix.metrics.liquidityRegime'],
      constraintsCheck: {
        pass: true,
        reasons: ['delta caps respected', 'single strategy adjusted'],
      },
      alternativesConsidered: [
        { option: 'hold', rejectedBecause: 'confidence above change threshold' },
      ],
    };
    const result = validateAutonomyDecision(payload);
    expect(result.ok).toBe(true);
    expect(result.decision?.decision).toBe('adjust');
  });

  it('rejects malformed payload missing constraints and alternatives', () => {
    const result = validateAutonomyDecision({
      decision: 'adjust',
      reason: 'x',
      confidence: 0.5,
      targets: [],
      evidence: [],
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.includes('constraintsCheck'))).toBe(true);
  });

  it('extracts and validates JSON block from model response text', () => {
    const raw = `Model output:\n{"decision":"hold","reason":"insufficient evidence","confidence":0.2,"targets":[],"evidence":[],"constraintsCheck":{"pass":false,"reasons":["low sample"]},"alternativesConsidered":[{"option":"adjust","rejectedBecause":"low confidence"}]}`;
    const result = parseAndValidateAutonomyDecision(raw);
    expect(result.ok).toBe(true);
    expect(result.decision?.decision).toBe('hold');
  });
});

