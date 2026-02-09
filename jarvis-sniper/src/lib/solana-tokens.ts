import { Connection, PublicKey } from '@solana/web3.js';

/**
 * Minimal SPL token helpers used by the sniper UI.
 * - Resolve token balances in *raw units* (lamports) so sells don't guess decimals.
 * - Keep this dependency-light (no @solana/spl-token) and client-safe.
 */

export type TokenBalanceLamports = {
  /** Raw amount in the smallest unit */
  amountLamports: string;
  /** Token decimals (best effort) */
  decimals: number;
};

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * Sum all SPL token accounts for `owner` filtered to `mint` (parsed RPC).
 * Returns `0` when no account exists yet.
 */
export async function getOwnerTokenBalanceLamports(
  connection: Connection,
  owner: string,
  mint: string,
): Promise<TokenBalanceLamports | null> {
  try {
    const ownerPk = new PublicKey(owner);
    const mintPk = new PublicKey(mint);
    const res = await connection.getParsedTokenAccountsByOwner(ownerPk, { mint: mintPk });

    let total = BigInt(0);
    let decimals = 0;

    for (const { account } of res.value) {
      const info = (account.data as any)?.parsed?.info;
      const tokenAmount = info?.tokenAmount;
      const amt = tokenAmount?.amount;
      const dec = tokenAmount?.decimals;
      if (typeof dec === 'number') decimals = dec;
      if (typeof amt === 'string' && amt.length > 0) {
        total += BigInt(amt);
      }
    }

    return { amountLamports: total.toString(), decimals };
  } catch {
    return null;
  }
}

export async function getOwnerTokenBalanceLamportsWithRetry(
  connection: Connection,
  owner: string,
  mint: string,
  opts?: { attempts?: number; delayMs?: number; requireNonZero?: boolean },
): Promise<TokenBalanceLamports | null> {
  const attempts = Math.max(1, opts?.attempts ?? 4);
  const delayMs = Math.max(50, opts?.delayMs ?? 350);
  const requireNonZero = opts?.requireNonZero ?? true;

  for (let i = 0; i < attempts; i++) {
    const bal = await getOwnerTokenBalanceLamports(connection, owner, mint);
    if (!bal) {
      await sleep(delayMs);
      continue;
    }
    if (!requireNonZero || bal.amountLamports !== '0') return bal;
    await sleep(delayMs);
  }

  return await getOwnerTokenBalanceLamports(connection, owner, mint);
}

export function minLamportsString(a: string, b: string): string {
  try {
    const aa = BigInt(a);
    const bb = BigInt(b);
    return (aa <= bb ? aa : bb).toString();
  } catch {
    // Fall back to b if parse fails (safer to not oversell).
    return b;
  }
}
