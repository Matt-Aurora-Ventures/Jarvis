import { describe, expect, it } from 'vitest';
import {
  normalizeBacktestCloudRunUrl,
  normalizeBacktestErrorMessage,
  stallThresholdForMode,
} from '@/hooks/useBacktest';

describe('useBacktest transport helpers', () => {
  it('normalizes HTML 502 payloads into a concise message', () => {
    const msg = normalizeBacktestErrorMessage({
      status: 502,
      contentType: 'text/html; charset=utf-8',
      body: '<!DOCTYPE html><html><head><title>Error 502 (Server Error)</title></head><body>gateway</body></html>',
    });

    expect(msg).toContain('HTTP 502');
    expect(msg.toLowerCase()).toContain('processing');
    expect(msg.toLowerCase()).not.toContain('<!doctype');
  });

  it('preserves short plain-text error payloads', () => {
    const msg = normalizeBacktestErrorMessage({
      status: 500,
      contentType: 'text/plain',
      body: 'upstream dependency unavailable',
    });
    expect(msg).toBe('upstream dependency unavailable');
  });

  it('accepts only https://*.a.run.app candidates for cloud run bypass', () => {
    expect(normalizeBacktestCloudRunUrl('https://svc-abcde-uc.a.run.app/health')).toBe(
      'https://svc-abcde-uc.a.run.app',
    );
    expect(normalizeBacktestCloudRunUrl('https://jarvislife.cloud')).toBeNull();
    expect(normalizeBacktestCloudRunUrl('http://svc-abcde-uc.a.run.app')).toBeNull();
  });

  it('uses tuned stall thresholds for quick/thorough/full-grid modes', () => {
    expect(stallThresholdForMode('quick', 'fast')).toBe(360_000);
    expect(stallThresholdForMode('quick', 'thorough')).toBe(600_000);
    expect(stallThresholdForMode('full', 'thorough')).toBe(900_000);
    expect(stallThresholdForMode('grid', 'fast')).toBe(900_000);
  });
});

