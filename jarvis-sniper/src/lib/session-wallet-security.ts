export type SessionWalletCreationMode = 'random' | 'deterministic';

function isTruthy(value: string | undefined): boolean {
  const normalized = String(value || '').trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

export function getSessionWalletCreationMode(): SessionWalletCreationMode {
  const explicit = String(process.env.NEXT_PUBLIC_SESSION_WALLET_CREATION_MODE || '').trim().toLowerCase();
  if (explicit === 'deterministic') return 'deterministic';
  if (explicit === 'random') return 'random';

  // Backward-compatible toggle used in older builds.
  if (isTruthy(process.env.NEXT_PUBLIC_SESSION_WALLET_DETERMINISTIC)) {
    return 'deterministic';
  }

  // Security-first default: rotate a fresh random wallet on each "Create".
  return 'random';
}

export function isDeterministicSessionWalletMode(): boolean {
  return getSessionWalletCreationMode() === 'deterministic';
}
