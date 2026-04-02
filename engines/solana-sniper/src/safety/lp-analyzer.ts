import { Connection, PublicKey } from '@solana/web3.js';
import { getConnection } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';
import type { LPAnalysisResult } from '../types/index.js';

const log = createModuleLogger('lp-analyzer');

export async function analyzeLiquidity(
  lpMintAddress: string,
  poolAddress?: string,
): Promise<LPAnalysisResult> {
  const conn = getConnection();

  try {
    const lpMint = new PublicKey(lpMintAddress);
    const supply = await conn.getTokenSupply(lpMint);
    const totalSupply = parseFloat(supply.value.amount);

    // Check largest LP holders to see burn/lock status
    const largestAccounts = await conn.getTokenLargestAccounts(lpMint);
    const accounts = largestAccounts.value;

    let burnedAmount = 0;
    let lockedAmount = 0;

    // Dead addresses that indicate burned LP
    const BURN_ADDRESSES = [
      '1nc1nerator11111111111111111111111111111111',
      '1111111111111111111111111111111111111111111',
      'deaddeaddeaddeaddeaddeaddeaddeaddeaddeaddead',
    ];

    for (const account of accounts) {
      const ownerInfo = await conn.getAccountInfo(new PublicKey(account.address));
      if (!ownerInfo) {
        // If account doesn't exist, LP is effectively burned
        burnedAmount += parseFloat(account.amount);
        continue;
      }

      // Check if the owner is a known burn address
      const ownerAddr = account.address.toBase58();
      if (BURN_ADDRESSES.some(burn => ownerAddr.includes(burn))) {
        burnedAmount += parseFloat(account.amount);
      }
    }

    const burnedPct = totalSupply > 0 ? (burnedAmount / totalSupply) * 100 : 0;
    const lockedPct = totalSupply > 0 ? (lockedAmount / totalSupply) * 100 : 0;

    const result: LPAnalysisResult = {
      lpBurnedPct: burnedPct,
      lpLockedPct: lockedPct,
      totalLpSupply: totalSupply,
      isLpSafe: burnedPct + lockedPct >= 90,
    };

    log.info('LP analysis complete', {
      lp: lpMintAddress.slice(0, 8),
      burnedPct: burnedPct.toFixed(1),
      safe: result.isLpSafe,
    });

    return result;
  } catch (err) {
    log.error('LP analysis failed', { lp: lpMintAddress, error: (err as Error).message });
    return {
      lpBurnedPct: 0,
      lpLockedPct: 0,
      totalLpSupply: 0,
      isLpSafe: false,
    };
  }
}

export function scoreLpAnalysis(result: LPAnalysisResult): number {
  const combined = result.lpBurnedPct + result.lpLockedPct;
  if (combined >= 95) return 1.0;
  if (combined >= 90) return 0.8;
  if (combined >= 70) return 0.5;
  if (combined >= 50) return 0.3;
  return 0.0;
}
