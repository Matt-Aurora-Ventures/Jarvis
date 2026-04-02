import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('data-source-config', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('exports DATA_SOURCE defaulting to pumpportal', async () => {
    // Clear env to test default
    delete process.env.NEXT_PUBLIC_DATA_SOURCE;
    const mod = await import('@/lib/data-source-config');
    expect(mod.DATA_SOURCE).toBe('pumpportal');
  });

  it('exports PUMPPORTAL_WS_URL with correct default', async () => {
    delete process.env.NEXT_PUBLIC_PUMPPORTAL_WS;
    const mod = await import('@/lib/data-source-config');
    expect(mod.PUMPPORTAL_WS_URL).toBe('wss://pumpportal.fun/api/data');
  });

  it('exports correct PumpFun program ID', async () => {
    const mod = await import('@/lib/data-source-config');
    expect(mod.PUMPFUN_PROGRAM_ID).toBe('6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P');
  });

  it('DataSourceMode type includes all valid options', async () => {
    const mod = await import('@/lib/data-source-config');
    const validModes = ['pumpportal', 'logs-subscribe', 'poll-only'];
    expect(validModes).toContain(mod.DATA_SOURCE);
  });
});
