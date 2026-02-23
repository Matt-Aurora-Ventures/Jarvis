import { PublicKey } from '@solana/web3.js';
import { getMint } from '@solana/spl-token';
import { getConnection } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';
import type { MintCheckResult } from '../types/index.js';

const log = createModuleLogger('mint-checker');

export async function checkMintAuthority(mintAddress: string): Promise<MintCheckResult> {
  const conn = getConnection();
  const mintPubkey = new PublicKey(mintAddress);

  try {
    const mintInfo = await getMint(conn, mintPubkey);

    const result: MintCheckResult = {
      mintAuthorityRevoked: mintInfo.mintAuthority === null,
      freezeAuthorityRevoked: mintInfo.freezeAuthority === null,
      mintAuthority: mintInfo.mintAuthority?.toBase58() ?? null,
      freezeAuthority: mintInfo.freezeAuthority?.toBase58() ?? null,
    };

    log.info('Mint check complete', {
      mint: mintAddress.slice(0, 8),
      mintRevoked: result.mintAuthorityRevoked,
      freezeRevoked: result.freezeAuthorityRevoked,
    });

    return result;
  } catch (err) {
    log.error('Mint check failed', { mint: mintAddress, error: (err as Error).message });
    // Fail-safe: assume dangerous if we can't check
    return {
      mintAuthorityRevoked: false,
      freezeAuthorityRevoked: false,
      mintAuthority: 'UNKNOWN',
      freezeAuthority: 'UNKNOWN',
    };
  }
}

export function scoreMintCheck(result: MintCheckResult): number {
  let score = 0;
  if (result.mintAuthorityRevoked) score += 0.5;
  if (result.freezeAuthorityRevoked) score += 0.5;
  return score;
}
