import { PublicKey } from '@solana/web3.js';
import { getConnection } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';
import type { HolderAnalysisResult } from '../types/index.js';
import { MAX_TOP10_HOLDER_PCT, MIN_HOLDER_COUNT } from '../config/constants.js';

const log = createModuleLogger('holder-analyzer');

export async function analyzeHolders(mintAddress: string): Promise<HolderAnalysisResult> {
  const conn = getConnection();

  try {
    const mintPubkey = new PublicKey(mintAddress);
    const supply = await conn.getTokenSupply(mintPubkey);
    const totalSupply = parseFloat(supply.value.amount);

    if (totalSupply === 0) {
      return { topHolders: [], top10ConcentrationPct: 100, holderCount: 0, isSafe: false };
    }

    const largestAccounts = await conn.getTokenLargestAccounts(mintPubkey);
    const top10 = largestAccounts.value.slice(0, 10);

    const topHolders = top10.map(acc => ({
      address: acc.address.toBase58(),
      pct: (parseFloat(acc.amount) / totalSupply) * 100,
    }));

    const top10Pct = topHolders.reduce((sum, h) => sum + h.pct, 0);

    // Estimate total holder count from token program accounts (capped query)
    const tokenAccounts = await conn.getProgramAccounts(
      new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'),
      {
        filters: [
          { dataSize: 165 },
          { memcmp: { offset: 0, bytes: mintAddress } },
        ],
        dataSlice: { offset: 0, length: 0 }, // Don't fetch data, just count
      }
    );
    const holderCount = tokenAccounts.length;

    const result: HolderAnalysisResult = {
      topHolders,
      top10ConcentrationPct: top10Pct,
      holderCount,
      isSafe: top10Pct <= MAX_TOP10_HOLDER_PCT && holderCount >= MIN_HOLDER_COUNT,
    };

    log.info('Holder analysis complete', {
      mint: mintAddress.slice(0, 8),
      top10Pct: top10Pct.toFixed(1),
      holders: holderCount,
      safe: result.isSafe,
    });

    return result;
  } catch (err) {
    log.error('Holder analysis failed', { mint: mintAddress, error: (err as Error).message });
    return { topHolders: [], top10ConcentrationPct: 100, holderCount: 0, isSafe: false };
  }
}

export function scoreHolderAnalysis(result: HolderAnalysisResult): number {
  let score = 0;
  // Holder concentration score (lower = better)
  if (result.top10ConcentrationPct <= 30) score += 0.5;
  else if (result.top10ConcentrationPct <= 50) score += 0.3;
  else if (result.top10ConcentrationPct <= 70) score += 0.1;

  // Holder count score
  if (result.holderCount >= 100) score += 0.5;
  else if (result.holderCount >= 50) score += 0.3;
  else if (result.holderCount >= 10) score += 0.1;

  return score;
}
