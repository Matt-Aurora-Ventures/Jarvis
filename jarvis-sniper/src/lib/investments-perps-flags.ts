function parseBoolFlag(raw: string | undefined): boolean | null {
  if (raw == null) return null;
  const value = String(raw).trim().toLowerCase();
  if (value === 'true') return true;
  if (value === 'false') return false;
  return null;
}

export function isInvestmentsEnabled(
  env: Record<string, string | undefined> = process.env,
): boolean {
  const explicit = parseBoolFlag(env.NEXT_PUBLIC_ENABLE_INVESTMENTS);
  if (explicit !== null) return explicit;
  return false;
}

export function isPerpsEnabled(
  env: Record<string, string | undefined> = process.env,
): boolean {
  const explicit = parseBoolFlag(env.NEXT_PUBLIC_ENABLE_PERPS);
  if (explicit !== null) return explicit;
  return false;
}
