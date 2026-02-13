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

export type WalletTokenHolding = {
  mint: string;
  amountLamports: string;
  decimals: number;
  uiAmount: number;
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

/**
 * Return all non-zero SPL token holdings for an owner wallet.
 * Useful for recovery when local position state is missing but funds remain on-chain.
 */
export async function getOwnerTokenHoldingsLamports(
  connection: Connection,
  owner: string,
): Promise<WalletTokenHolding[]> {
  try {
    const ownerPk = new PublicKey(owner);
    const tokenProgramPk = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');
    const res = await connection.getParsedTokenAccountsByOwner(ownerPk, { programId: tokenProgramPk });

    const byMint = new Map<string, { amount: bigint; decimals: number }>();

    for (const { account } of res.value) {
      const info = (account.data as any)?.parsed?.info;
      const mint = String(info?.mint || '');
      const tokenAmount = info?.tokenAmount;
      const amtRaw = typeof tokenAmount?.amount === 'string' ? tokenAmount.amount : '0';
      const dec = typeof tokenAmount?.decimals === 'number' ? tokenAmount.decimals : 0;
      if (!mint || amtRaw === '0') continue;

      const prev = byMint.get(mint);
      const amt = BigInt(amtRaw);
      if (!prev) {
        byMint.set(mint, { amount: amt, decimals: dec });
      } else {
        byMint.set(mint, { amount: prev.amount + amt, decimals: prev.decimals || dec });
      }
    }

    return [...byMint.entries()]
      .map(([mint, v]) => {
        const scale = 10 ** Math.max(0, v.decimals);
        const uiAmount = scale > 0 ? Number(v.amount) / scale : Number(v.amount);
        return {
          mint,
          amountLamports: v.amount.toString(),
          decimals: v.decimals,
          uiAmount,
        };
      })
      .filter((h) => h.amountLamports !== '0')
      .sort((a, b) => b.uiAmount - a.uiAmount);
  } catch {
    return [];
  }
}
