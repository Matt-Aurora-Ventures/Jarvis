import { isInvestmentsEnabled, isPerpsEnabled } from '@/lib/investments-perps-flags';

export type SurfaceKey = 'investments' | 'perps' | 'tradfi' | 'clawbot';

export interface SurfaceAvailability {
  key: SurfaceKey;
  visible: true;
  enabled: boolean;
  reason: string | null;
}

function parseBoolFlag(raw: string | undefined): boolean | null {
  if (raw == null) return null;
  const value = String(raw).trim().toLowerCase();
  if (value === 'true') return true;
  if (value === 'false') return false;
  return null;
}

function defaultEnabledOutsideProd(
  env: Record<string, string | undefined> = process.env,
): boolean {
  return String(env.NODE_ENV || '').trim().toLowerCase() !== 'production';
}

function isTradfiEnabled(env: Record<string, string | undefined> = process.env): boolean {
  const explicit = parseBoolFlag(env.NEXT_PUBLIC_ENABLE_TRADFI);
  if (explicit !== null) return explicit;
  return defaultEnabledOutsideProd(env);
}

function disabledReasonFor(key: SurfaceKey): string {
  switch (key) {
    case 'investments':
      return 'Investments is in staged rollout for this runtime.';
    case 'perps':
      return 'Perps is in staged rollout for this runtime.';
    case 'tradfi':
      return 'TradFi is in staged rollout for this runtime.';
    case 'clawbot':
      return 'Clawbot is in staged rollout for this runtime.';
    default:
      return 'This surface is unavailable in this runtime.';
  }
}

export function resolveSurfaceAvailability(
  key: SurfaceKey,
  env: Record<string, string | undefined> = process.env,
): SurfaceAvailability {
  let enabled = false;
  if (key === 'investments') enabled = isInvestmentsEnabled(env);
  if (key === 'perps') enabled = isPerpsEnabled(env);
  if (key === 'tradfi') enabled = isTradfiEnabled(env);
  // Keep Clawbot demo-safe until backend control-plane hardening is complete.
  if (key === 'clawbot') enabled = false;
  return {
    key,
    visible: true,
    enabled,
    reason: enabled ? null : disabledReasonFor(key),
  };
}

export function getSurfaceAvailabilityMap(
  env: Record<string, string | undefined> = process.env,
): Record<SurfaceKey, SurfaceAvailability> {
  return {
    investments: resolveSurfaceAvailability('investments', env),
    perps: resolveSurfaceAvailability('perps', env),
    tradfi: resolveSurfaceAvailability('tradfi', env),
    clawbot: resolveSurfaceAvailability('clawbot', env),
  };
}

