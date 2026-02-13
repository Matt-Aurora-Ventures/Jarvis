import { Connection, LAMPORTS_PER_SOL, PublicKey } from '@solana/web3.js';

export interface SignerSolBalanceCheck {
  ok: boolean;
  availableLamports: number;
  requiredLamports: number;
  reserveLamports: number;
  availableSol: number;
  requiredSol: number;
  error?: string;
}

function toSafeLamports(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.floor(value));
}

export async function checkSignerSolBalance(
  connection: Connection,
  walletAddress: string,
  requiredLamports: number,
  reserveLamports = 3_000_000,
): Promise<SignerSolBalanceCheck> {
  const reserve = toSafeLamports(reserveLamports);
  const required = toSafeLamports(requiredLamports) + reserve;

  try {
    const pubkey = new PublicKey(walletAddress);
    const availableLamports = toSafeLamports(await connection.getBalance(pubkey, 'confirmed'));
    return {
      ok: availableLamports >= required,
      availableLamports,
      requiredLamports: required,
      reserveLamports: reserve,
      availableSol: availableLamports / LAMPORTS_PER_SOL,
      requiredSol: required / LAMPORTS_PER_SOL,
    };
  } catch (error) {
    return {
      ok: false,
      availableLamports: 0,
      requiredLamports: required,
      reserveLamports: reserve,
      availableSol: 0,
      requiredSol: required / LAMPORTS_PER_SOL,
      error: error instanceof Error ? error.message : 'Wallet balance check failed',
    };
  }
}
