import { describe, expect, it } from 'vitest';
import {
  buildPrewarmBody,
  isPrewarmTerminalState,
  resolvePrewarmBaseUrl,
} from '@/lib/backtest-prewarm';

describe('backtest prewarm helpers', () => {
  it('prefers valid cloud run tag URL from health payload', () => {
    const payload = { backend: { cloudRunTagUrl: 'https://abc-xyz-uc.a.run.app' } };
    expect(resolvePrewarmBaseUrl(payload, 'https://jarvislife.cloud')).toBe(
      'https://abc-xyz-uc.a.run.app',
    );
  });

  it('falls back to canonical origin when cloud run tag URL is missing', () => {
    const payload = { status: 'ok' };
    expect(resolvePrewarmBaseUrl(payload, 'https://jarvislife.cloud')).toBe(
      'https://jarvislife.cloud',
    );
  });

  it('builds strict real-data prewarm payload', () => {
    const body = buildPrewarmBody('memecoin', 'run-123');
    expect(body.family).toBe('memecoin');
    expect(body.strictNoSynthetic).toBe(true);
    expect(body.sourcePolicy).toBe('allow_birdeye_fallback');
    expect(body.mode).toBe('quick');
    expect(body.dataScale).toBe('fast');
  });

  it('supports explicit prewarm payload options for nightly full sweeps', () => {
    const body = buildPrewarmBody('bluechip', 'run-nightly', {
      mode: 'full',
      dataScale: 'thorough',
      sourcePolicy: 'allow_birdeye_fallback',
      maxTokens: 80,
      lookbackHours: 2160,
      includeEvidence: true,
    });
    expect(body.family).toBe('bluechip');
    expect(body.mode).toBe('full');
    expect(body.dataScale).toBe('thorough');
    expect(body.sourcePolicy).toBe('allow_birdeye_fallback');
    expect(body.maxTokens).toBe(80);
    expect(body.lookbackHours).toBe(2160);
    expect(body.includeEvidence).toBe(true);
  });

  it('marks terminal run states correctly', () => {
    expect(isPrewarmTerminalState('completed')).toBe(true);
    expect(isPrewarmTerminalState('partial')).toBe(true);
    expect(isPrewarmTerminalState('failed')).toBe(true);
    expect(isPrewarmTerminalState('running')).toBe(false);
  });
});
