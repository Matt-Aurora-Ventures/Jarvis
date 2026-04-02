function parseBoolFlag(raw: string | undefined): boolean | null {
  if (raw == null) return null;
  const value = String(raw).trim().toLowerCase();
  if (value === 'true') return true;
  if (value === 'false') return false;
  return null;
}

// Use direct NEXT_PUBLIC_* reads so Next can inline values into client bundles.
const BUILD_FLAG_INVESTMENTS = process.env.NEXT_PUBLIC_ENABLE_INVESTMENTS;
const BUILD_FLAG_PERPS = process.env.NEXT_PUBLIC_ENABLE_PERPS;

export function isInvestmentsEnabled(
  env: Record<string, string | undefined> = process.env,
): boolean {
  const explicit = parseBoolFlag(env.NEXT_PUBLIC_ENABLE_INVESTMENTS);
  if (explicit !== null) return explicit;
  const buildTime = parseBoolFlag(BUILD_FLAG_INVESTMENTS);
  if (buildTime !== null) return buildTime;
  return true;
}

export function isPerpsEnabled(
  env: Record<string, string | undefined> = process.env,
): boolean {
  const explicit = parseBoolFlag(env.NEXT_PUBLIC_ENABLE_PERPS);
  if (explicit !== null) return explicit;
  const buildTime = parseBoolFlag(BUILD_FLAG_PERPS);
  if (buildTime !== null) return buildTime;
  return true;
}
