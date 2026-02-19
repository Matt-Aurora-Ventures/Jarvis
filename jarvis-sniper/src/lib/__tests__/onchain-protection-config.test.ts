import { describe, expect, it } from 'vitest';
import { resolveOnChainProtectionConfig } from '../onchain-protection-config';

describe('resolveOnChainProtectionConfig', () => {
  it('defaults to disabled when no env flags are set', () => {
    const cfg = resolveOnChainProtectionConfig({});

    expect(cfg.requested).toBe(false);
    expect(cfg.runtimeReady).toBe(false);
    expect(cfg.lifecycleReady).toBe(false);
    expect(cfg.enabled).toBe(false);
    expect(cfg.reason).toMatch(/disabled/i);
  });

  it('stays disabled when experimental flag is on but runtime is not ready', () => {
    const cfg = resolveOnChainProtectionConfig({
      NEXT_PUBLIC_ENABLE_EXPERIMENTAL_ONCHAIN_SLTP: 'true',
    });

    expect(cfg.requested).toBe(true);
    expect(cfg.runtimeReady).toBe(false);
    expect(cfg.lifecycleReady).toBe(false);
    expect(cfg.enabled).toBe(false);
    expect(cfg.reason).toMatch(/runtime/i);
  });

  it('stays disabled when runtime is ready but lifecycle is not marked ready', () => {
    const cfg = resolveOnChainProtectionConfig({
      NEXT_PUBLIC_ENABLE_EXPERIMENTAL_ONCHAIN_SLTP: 'true',
      NEXT_PUBLIC_ONCHAIN_SLTP_RUNTIME_READY: 'true',
    });

    expect(cfg.requested).toBe(true);
    expect(cfg.runtimeReady).toBe(true);
    expect(cfg.lifecycleReady).toBe(false);
    expect(cfg.enabled).toBe(false);
    expect(cfg.reason).toMatch(/lifecycle/i);
  });

  it('enables protection only when experimental, runtime-ready, and lifecycle-ready flags are all true', () => {
    const cfg = resolveOnChainProtectionConfig({
      NEXT_PUBLIC_ENABLE_EXPERIMENTAL_ONCHAIN_SLTP: 'true',
      NEXT_PUBLIC_ONCHAIN_SLTP_RUNTIME_READY: 'true',
      NEXT_PUBLIC_ONCHAIN_SLTP_LIFECYCLE_READY: 'true',
    });

    expect(cfg.requested).toBe(true);
    expect(cfg.runtimeReady).toBe(true);
    expect(cfg.lifecycleReady).toBe(true);
    expect(cfg.enabled).toBe(true);
    expect(cfg.reason).toBeNull();
  });
});
