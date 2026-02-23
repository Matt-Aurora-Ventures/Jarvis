import { existsSync, readFileSync, rmSync, mkdtempSync } from 'fs';
import { join } from 'path';
import { tmpdir } from 'os';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type EnvSnapshot = {
  NODE_ENV?: string;
  JARVIS_SPOT_PROTECTION_ROOT?: string;
  SPOT_PROTECTION_LOCAL_MODE?: string;
  SPOT_PROTECTION_PROVIDER_URL?: string;
  SPOT_PROTECTION_PROVIDER_PATH?: string;
  SPOT_PROTECTION_PROVIDER_TOKEN?: string;
  SPOT_PROTECTION_PROVIDER_TIMEOUT_MS?: string;
};

const envSnapshot: EnvSnapshot = {
  NODE_ENV: process.env.NODE_ENV,
  JARVIS_SPOT_PROTECTION_ROOT: process.env.JARVIS_SPOT_PROTECTION_ROOT,
  SPOT_PROTECTION_LOCAL_MODE: process.env.SPOT_PROTECTION_LOCAL_MODE,
  SPOT_PROTECTION_PROVIDER_URL: process.env.SPOT_PROTECTION_PROVIDER_URL,
  SPOT_PROTECTION_PROVIDER_PATH: process.env.SPOT_PROTECTION_PROVIDER_PATH,
  SPOT_PROTECTION_PROVIDER_TOKEN: process.env.SPOT_PROTECTION_PROVIDER_TOKEN,
  SPOT_PROTECTION_PROVIDER_TIMEOUT_MS: process.env.SPOT_PROTECTION_PROVIDER_TIMEOUT_MS,
};

describe('spot-protection adapter lifecycle', () => {
  let rootDir = '';

  beforeEach(() => {
    vi.resetModules();
    rootDir = mkdtempSync(join(tmpdir(), 'jarvis-spot-protection-'));
    process.env.JARVIS_SPOT_PROTECTION_ROOT = rootDir;
    process.env.SPOT_PROTECTION_LOCAL_MODE = 'true';
    delete process.env.SPOT_PROTECTION_PROVIDER_URL;
    delete process.env.SPOT_PROTECTION_PROVIDER_PATH;
    delete process.env.SPOT_PROTECTION_PROVIDER_TOKEN;
    delete process.env.SPOT_PROTECTION_PROVIDER_TIMEOUT_MS;
  });

  afterEach(() => {
    vi.resetModules();
    if (rootDir && existsSync(rootDir)) {
      rmSync(rootDir, { recursive: true, force: true });
    }
    process.env.NODE_ENV = envSnapshot.NODE_ENV;
    process.env.JARVIS_SPOT_PROTECTION_ROOT = envSnapshot.JARVIS_SPOT_PROTECTION_ROOT;
    process.env.SPOT_PROTECTION_LOCAL_MODE = envSnapshot.SPOT_PROTECTION_LOCAL_MODE;
    process.env.SPOT_PROTECTION_PROVIDER_URL = envSnapshot.SPOT_PROTECTION_PROVIDER_URL;
    process.env.SPOT_PROTECTION_PROVIDER_PATH = envSnapshot.SPOT_PROTECTION_PROVIDER_PATH;
    process.env.SPOT_PROTECTION_PROVIDER_TOKEN = envSnapshot.SPOT_PROTECTION_PROVIDER_TOKEN;
    process.env.SPOT_PROTECTION_PROVIDER_TIMEOUT_MS = envSnapshot.SPOT_PROTECTION_PROVIDER_TIMEOUT_MS;
  });

  it('activates in local mode and persists lifecycle across module reloads', async () => {
    const first = await import('@/lib/execution/spot-protection');
    const preflight = await first.preflightSpotProtection();
    expect(preflight.ok).toBe(true);
    expect(preflight.provider).toBe('local');

    const activation = await first.activateSpotProtection({
      positionId: 'pos-1',
      walletAddress: 'wallet-1',
      mint: 'mint-1',
      symbol: 'AAA',
      entryPriceUsd: 1.23,
      quantity: 100,
      tpPercent: 20,
      slPercent: 10,
    });
    expect(activation.ok).toBe(true);
    expect(activation.status).toBe('active');
    expect(activation.tpOrderKey).toMatch(/^local-tp:/);
    expect(activation.slOrderKey).toMatch(/^local-sl:/);

    const recordsFile = join(rootDir, 'records.json');
    expect(existsSync(recordsFile)).toBe(true);
    const onDisk = JSON.parse(readFileSync(recordsFile, 'utf8')) as Record<string, { status: string }>;
    expect(onDisk['pos-1']?.status).toBe('active');

    vi.resetModules();
    const restarted = await import('@/lib/execution/spot-protection');
    const reconciled = await restarted.reconcileSpotProtection(['pos-1']);
    expect(reconciled.ok).toBe(true);
    expect(reconciled.records).toHaveLength(1);
    expect(reconciled.records[0].positionId).toBe('pos-1');
    expect(reconciled.records[0].status).toBe('active');
  });

  it('cancels lifecycle records and keeps cancellation state in reconcile output', async () => {
    const adapter = await import('@/lib/execution/spot-protection');
    await adapter.activateSpotProtection({
      positionId: 'pos-cancel',
      walletAddress: 'wallet-2',
      mint: 'mint-2',
      symbol: 'BBB',
      entryPriceUsd: 2.5,
      quantity: 20,
      tpPercent: 15,
      slPercent: 8,
    });

    const cancelled = await adapter.cancelSpotProtection('pos-cancel', 'position_closed');
    expect(cancelled.ok).toBe(true);
    expect(cancelled.status).toBe('cancelled');
    expect(cancelled.record?.cancelledAt).toBeTypeOf('number');

    const reconciled = await adapter.reconcileSpotProtection(['pos-cancel']);
    expect(reconciled.ok).toBe(true);
    expect(reconciled.records).toHaveLength(1);
    expect(reconciled.records[0].status).toBe('cancelled');
  });
});

