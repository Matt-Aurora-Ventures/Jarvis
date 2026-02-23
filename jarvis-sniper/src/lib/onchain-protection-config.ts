export interface OnChainProtectionConfig {
  requested: boolean;
  runtimeReady: boolean;
  lifecycleReady: boolean;
  enabled: boolean;
  reason: string | null;
}

function asEnabledFlag(value: string | undefined): boolean {
  return String(value || '').trim().toLowerCase() === 'true';
}

export function resolveOnChainProtectionConfig(
  env: Record<string, string | undefined> = process.env,
): OnChainProtectionConfig {
  const requested = asEnabledFlag(env.NEXT_PUBLIC_ENABLE_EXPERIMENTAL_ONCHAIN_SLTP);
  const runtimeReady = asEnabledFlag(env.NEXT_PUBLIC_ONCHAIN_SLTP_RUNTIME_READY);
  const lifecycleReady = asEnabledFlag(env.NEXT_PUBLIC_ONCHAIN_SLTP_LIFECYCLE_READY);
  const enabled = requested && runtimeReady && lifecycleReady;

  if (enabled) {
    return {
      requested,
      runtimeReady,
      lifecycleReady,
      enabled,
      reason: null,
    };
  }

  if (requested && !runtimeReady) {
    return {
      requested,
      runtimeReady,
      lifecycleReady,
      enabled,
      reason: 'Experimental on-chain SL/TP requested, but runtime is not marked ready.',
    };
  }

  if (requested && runtimeReady && !lifecycleReady) {
    return {
      requested,
      runtimeReady,
      lifecycleReady,
      enabled,
      reason: 'On-chain SL/TP runtime is enabled, but lifecycle is not marked ready.',
    };
  }

  return {
    requested,
    runtimeReady,
    lifecycleReady,
    enabled,
    reason: 'On-chain SL/TP is disabled for this runtime.',
  };
}
