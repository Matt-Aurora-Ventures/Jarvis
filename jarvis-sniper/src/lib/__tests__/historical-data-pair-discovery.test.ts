import { describe, expect, it } from 'vitest';
import { buildPairCandidateList, selectBestGeckoPoolAddress } from '@/lib/historical-data';

describe('selectBestGeckoPoolAddress', () => {
  it('picks the highest-liquidity pool address from Gecko token pools payload', () => {
    const payload = {
      data: [
        { attributes: { address: 'pool-low', reserve_in_usd: '1000' } },
        { attributes: { address: 'pool-high', reserve_in_usd: '5000' } },
        { attributes: { address: 'pool-mid', reserve_in_usd: '2500' } },
      ],
    };

    expect(selectBestGeckoPoolAddress(payload)).toBe('pool-high');
  });

  it('returns first valid address when liquidity numbers are missing', () => {
    const payload = {
      data: [
        { attributes: { address: 'pool-a', reserve_in_usd: undefined } },
        { attributes: { address: 'pool-b', reserve_in_usd: null } },
      ],
    };

    expect(selectBestGeckoPoolAddress(payload)).toBe('pool-a');
  });

  it('returns null when no valid address is present', () => {
    const payload = {
      data: [
        { attributes: { address: '' } },
        { attributes: { address: null } },
      ],
    };

    expect(selectBestGeckoPoolAddress(payload)).toBeNull();
  });

  it('prefers stable/WSOL routing pools for the target mint', () => {
    const targetMint = 'TargetMint11111111111111111111111111111111';
    const payload = {
      data: [
        {
          attributes: { address: 'pool-random', reserve_in_usd: '100000' },
          relationships: {
            base_token: { data: { id: `solana_${targetMint}` } },
            quote_token: { data: { id: 'solana_RandomMint' } },
          },
        },
        {
          attributes: { address: 'pool-usdc', reserve_in_usd: '50000' },
          relationships: {
            base_token: { data: { id: `solana_${targetMint}` } },
            quote_token: { data: { id: 'solana_EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v' } },
          },
        },
      ],
    };

    expect(selectBestGeckoPoolAddress(payload, targetMint)).toBe('pool-usdc');
  });
});

describe('buildPairCandidateList', () => {
  it('prioritizes gecko pair first and deduplicates identical pair addresses', () => {
    const pairs = buildPairCandidateList('pool-gecko', 'pool-gecko');
    expect(pairs).toEqual(['pool-gecko']);
  });

  it('keeps dex pair as fallback when gecko pair is unavailable', () => {
    const pairs = buildPairCandidateList(null, 'pool-dex');
    expect(pairs).toEqual(['pool-dex']);
  });

  it('returns empty list when both sources are unavailable', () => {
    const pairs = buildPairCandidateList(null, null);
    expect(pairs).toEqual([]);
  });
});
