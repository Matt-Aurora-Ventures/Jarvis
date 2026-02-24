export type SurfaceKey = 'investments' | 'perps' | 'tradfi';
export type SurfaceState = 'enabled' | 'visible-disabled';

export type SurfaceStatus = {
  state: SurfaceState;
  reason?: string;
};

export type SurfaceAvailability = Record<SurfaceKey, SurfaceStatus>;

type ResolveSurfaceAvailabilityArgs = {
  env?: Record<string, string | undefined>;
  health?: Partial<Record<SurfaceKey, boolean>>;
};

function parseBoolFlag(raw: string | undefined): boolean | null {
  if (raw == null) return null;
  const normalized = String(raw).trim().toLowerCase();
  if (normalized === 'true') return true;
  if (normalized === 'false') return false;
  return null;
}

function defaultEnabledOutsideProd(env: Record<string, string | undefined>): boolean {
  return String(env.NODE_ENV || '').trim().toLowerCase() !== 'production';
}

function resolveSurfaceStatus(
  key: SurfaceKey,
  flagName: string,
  env: Record<string, string | undefined>,
  health: Partial<Record<SurfaceKey, boolean>>,
): SurfaceStatus {
  const explicit = parseBoolFlag(env[flagName]);
  const envEnabled = explicit !== null ? explicit : defaultEnabledOutsideProd(env);

  if (!envEnabled) {
    return {
      state: 'visible-disabled',
      reason: `Disabled by ${flagName} flag.`,
    };
  }

  if (health[key] === false) {
    return {
      state: 'visible-disabled',
      reason: 'Disabled by runtime health status.',
    };
  }

  return { state: 'enabled' };
}

export function resolveSurfaceAvailability({
  env = process.env,
  health = {},
}: ResolveSurfaceAvailabilityArgs = {}): SurfaceAvailability {
  return {
    investments: resolveSurfaceStatus('investments', 'NEXT_PUBLIC_ENABLE_INVESTMENTS', env, health),
    perps: resolveSurfaceStatus('perps', 'NEXT_PUBLIC_ENABLE_PERPS', env, health),
    tradfi: resolveSurfaceStatus('tradfi', 'NEXT_PUBLIC_ENABLE_TRADFI_SNIPER', env, health),
  };
}

export function isSurfaceEnabled(surface: SurfaceStatus): boolean {
  return surface.state === 'enabled';
}
