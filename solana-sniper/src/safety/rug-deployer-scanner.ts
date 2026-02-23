import axios from 'axios';
import { Connection, PublicKey } from '@solana/web3.js';
import { getConnection } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';
import { config } from '../config/index.js';
import fs from 'fs';
import path from 'path';

const log = createModuleLogger('rug-scanner');

export interface RugDeployerResult {
  deployer: string | null;
  isKnownRugger: boolean;
  rugCount: number;
  totalTokensDeployed: number;
  rugRatio: number; // 0-1, higher = more rugs
  riskScore: number; // 0-1, higher = riskier
  recentRugs: Array<{
    mint: string;
    symbol?: string;
    ruggedAt?: string;
    maxMcap?: number;
  }>;
  scanMethod: 'cache' | 'helius' | 'rpc' | 'dexscreener';
}

// ─── Local cache of known rug deployers ─────────────────────
const KNOWN_RUGGERS_FILE = path.resolve(process.cwd(), 'data', 'known-ruggers.json');

interface RuggerEntry {
  address: string;
  rugCount: number;
  totalTokens: number;
  lastSeen: string;
  rugs: Array<{ mint: string; symbol?: string; ruggedAt?: string }>;
}

let ruggerCache: Map<string, RuggerEntry> = new Map();
let cacheLoaded = false;

function loadRuggerCache(): void {
  if (cacheLoaded) return;
  try {
    if (fs.existsSync(KNOWN_RUGGERS_FILE)) {
      const data: RuggerEntry[] = JSON.parse(fs.readFileSync(KNOWN_RUGGERS_FILE, 'utf8'));
      ruggerCache = new Map(data.map(e => [e.address, e]));
      log.info('Loaded rugger cache', { entries: ruggerCache.size });
    }
  } catch {
    log.warn('Failed to load rugger cache, starting fresh');
  }
  cacheLoaded = true;
}

function saveRuggerCache(): void {
  try {
    const dir = path.dirname(KNOWN_RUGGERS_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(KNOWN_RUGGERS_FILE, JSON.stringify([...ruggerCache.values()], null, 2));
  } catch (err) {
    log.warn('Failed to save rugger cache', { error: (err as Error).message });
  }
}

export function addKnownRugger(address: string, rugMint: string, symbol?: string): void {
  loadRuggerCache();
  const existing = ruggerCache.get(address);
  if (existing) {
    if (!existing.rugs.find(r => r.mint === rugMint)) {
      existing.rugCount++;
      existing.rugs.push({ mint: rugMint, symbol, ruggedAt: new Date().toISOString() });
      existing.lastSeen = new Date().toISOString();
    }
  } else {
    ruggerCache.set(address, {
      address,
      rugCount: 1,
      totalTokens: 1,
      lastSeen: new Date().toISOString(),
      rugs: [{ mint: rugMint, symbol, ruggedAt: new Date().toISOString() }],
    });
  }
  saveRuggerCache();
}

// ─── Find deployer of a token ───────────────────────────────
async function findTokenDeployer(mintAddress: string): Promise<string | null> {
  // Method 1: Helius API (fastest, if key available)
  if (config.heliusApiKey) {
    try {
      const resp = await axios.post(
        `https://api.helius.xyz/v0/token-metadata?api-key=${config.heliusApiKey}`,
        { mintAccounts: [mintAddress] },
        { timeout: 8000 },
      );
      const meta = resp.data?.[0];
      if (meta?.onChainAccountInfo?.accountInfo?.owner) {
        return meta.onChainAccountInfo.accountInfo.owner;
      }
    } catch {
      log.debug('Helius deployer lookup failed, trying RPC');
    }
  }

  // Method 2: Get first transaction signatures for the mint account
  try {
    const conn = getConnection();
    const mintPubkey = new PublicKey(mintAddress);

    const signatures = await conn.getSignaturesForAddress(mintPubkey, {
      limit: 1,
    });

    if (signatures.length > 0) {
      const tx = await conn.getParsedTransaction(signatures[signatures.length - 1].signature, {
        maxSupportedTransactionVersion: 0,
      });
      if (tx?.transaction?.message?.accountKeys) {
        // The first signer is typically the deployer/creator
        const firstSigner = tx.transaction.message.accountKeys.find(k => k.signer);
        if (firstSigner) {
          return firstSigner.pubkey.toBase58();
        }
      }
    }
  } catch (err) {
    log.debug('RPC deployer lookup failed', { error: (err as Error).message });
  }

  return null;
}

// ─── Check deployer history ─────────────────────────────────
async function checkDeployerHistory(
  deployerAddress: string,
): Promise<{ tokensMinted: string[]; ruggedTokens: string[] }> {
  const tokensMinted: string[] = [];
  const ruggedTokens: string[] = [];

  // Method 1: Helius parsed transaction history
  if (config.heliusApiKey) {
    try {
      const resp = await axios.get(
        `https://api.helius.xyz/v0/addresses/${deployerAddress}/transactions?api-key=${config.heliusApiKey}&type=TOKEN_MINT`,
        { timeout: 10000 },
      );
      const txns = resp.data ?? [];
      for (const txn of txns) {
        if (txn.tokenTransfers?.length > 0) {
          for (const tt of txn.tokenTransfers) {
            if (tt.mint && !tokensMinted.includes(tt.mint)) {
              tokensMinted.push(tt.mint);
            }
          }
        }
      }
    } catch {
      log.debug('Helius history lookup failed');
    }
  }

  // Method 2: DexScreener to check if tokens still have liquidity
  if (tokensMinted.length > 0) {
    try {
      // Check batch of tokens via DexScreener
      const batchSize = 30;
      for (let i = 0; i < tokensMinted.length; i += batchSize) {
        const batch = tokensMinted.slice(i, i + batchSize);
        const resp = await axios.get(
          `https://api.dexscreener.com/latest/dex/tokens/${batch.join(',')}`,
          { timeout: 10000 },
        );
        const pairs = resp.data?.pairs ?? [];
        const mintSet = new Set(batch);

        for (const mint of mintSet) {
          const mintPairs = pairs.filter((p: Record<string, unknown>) =>
            (p.baseToken as Record<string, unknown>)?.address === mint
          );

          if (mintPairs.length === 0) {
            // No pairs found = possibly rugged or dead
            ruggedTokens.push(mint);
            continue;
          }

          // Check for rug indicators
          for (const pair of mintPairs) {
            const liq = pair.liquidity?.usd ?? 0;
            const fdv = pair.fdv ?? 0;
            const priceChange24h = pair.priceChange?.h24 ?? 0;

            // Rug indicators: <$100 liquidity, >90% drop in 24h, or FDV collapsed
            if (liq < 100 && priceChange24h < -90) {
              if (!ruggedTokens.includes(mint)) {
                ruggedTokens.push(mint);
              }
            }
          }
        }

        // Rate limit between batches
        if (i + batchSize < tokensMinted.length) {
          await new Promise(r => setTimeout(r, 1000));
        }
      }
    } catch {
      log.debug('DexScreener batch check failed');
    }
  }

  // Method 3: If no Helius, try RPC-based approach (slower)
  if (tokensMinted.length === 0) {
    try {
      const conn = getConnection();
      const deployerPubkey = new PublicKey(deployerAddress);

      const signatures = await conn.getSignaturesForAddress(deployerPubkey, {
        limit: 50, // Last 50 transactions
      });

      for (const sig of signatures) {
        try {
          const tx = await conn.getParsedTransaction(sig.signature, {
            maxSupportedTransactionVersion: 0,
          });
          if (!tx?.meta?.postTokenBalances) continue;

          // Look for InitializeMint instructions
          const instructions = tx.transaction.message.instructions;
          for (const ix of instructions) {
            if ('parsed' in ix && ix.parsed?.type === 'initializeMint') {
              const mint = ix.parsed.info?.mint;
              if (mint && !tokensMinted.includes(mint)) {
                tokensMinted.push(mint);
              }
            }
          }
        } catch {
          // Skip failed tx parse
        }
      }
    } catch {
      log.debug('RPC history fallback failed');
    }
  }

  return { tokensMinted, ruggedTokens };
}

// ─── Main scan function ─────────────────────────────────────
export async function scanForRugDeployer(mintAddress: string): Promise<RugDeployerResult> {
  loadRuggerCache();

  const defaultResult: RugDeployerResult = {
    deployer: null,
    isKnownRugger: false,
    rugCount: 0,
    totalTokensDeployed: 0,
    rugRatio: 0,
    riskScore: 0,
    recentRugs: [],
    scanMethod: 'rpc',
  };

  try {
    // Step 1: Find who deployed this token
    const deployer = await findTokenDeployer(mintAddress);
    if (!deployer) {
      log.debug('Could not identify deployer', { mint: mintAddress.slice(0, 8) });
      return { ...defaultResult, riskScore: 0.2 }; // slight penalty for unknown
    }

    defaultResult.deployer = deployer;

    // Step 2: Check local cache first
    const cached = ruggerCache.get(deployer);
    if (cached) {
      const ratio = cached.rugCount / Math.max(1, cached.totalTokens);
      const riskScore = Math.min(1, ratio * 1.5 + (cached.rugCount >= 2 ? 0.3 : 0));

      log.info('Deployer found in rugger cache', {
        deployer: deployer.slice(0, 8),
        rugCount: cached.rugCount,
        riskScore: riskScore.toFixed(2),
      });

      return {
        deployer,
        isKnownRugger: cached.rugCount >= 2,
        rugCount: cached.rugCount,
        totalTokensDeployed: cached.totalTokens,
        rugRatio: ratio,
        riskScore,
        recentRugs: cached.rugs.slice(-5).map(r => ({
          mint: r.mint,
          symbol: r.symbol,
          ruggedAt: r.ruggedAt,
        })),
        scanMethod: 'cache',
      };
    }

    // Step 3: Full deployer history check
    const history = await checkDeployerHistory(deployer);

    const totalTokens = history.tokensMinted.length;
    const rugCount = history.ruggedTokens.length;
    const rugRatio = totalTokens > 0 ? rugCount / totalTokens : 0;

    // Risk scoring
    let riskScore = 0;
    if (rugCount >= 3) riskScore = 0.95; // Serial rugger
    else if (rugCount === 2) riskScore = 0.75;
    else if (rugCount === 1 && totalTokens <= 3) riskScore = 0.5;
    else if (rugCount === 1) riskScore = 0.3;
    else if (totalTokens > 5) riskScore = 0.15; // Many tokens but no rugs = suspicious but not proven
    else riskScore = 0;

    const isKnownRugger = rugCount >= 2;

    // Update cache if rugger found
    if (rugCount > 0) {
      ruggerCache.set(deployer, {
        address: deployer,
        rugCount,
        totalTokens,
        lastSeen: new Date().toISOString(),
        rugs: history.ruggedTokens.map(mint => ({
          mint,
          ruggedAt: new Date().toISOString(),
        })),
      });
      saveRuggerCache();
    }

    log.info('Deployer scan complete', {
      deployer: deployer.slice(0, 8),
      totalTokens,
      rugCount,
      isKnownRugger,
      riskScore: riskScore.toFixed(2),
    });

    return {
      deployer,
      isKnownRugger,
      rugCount,
      totalTokensDeployed: totalTokens,
      rugRatio,
      riskScore,
      recentRugs: history.ruggedTokens.slice(-5).map(mint => ({ mint })),
      scanMethod: config.heliusApiKey ? 'helius' : 'rpc',
    };
  } catch (err) {
    log.error('Rug deployer scan failed', { mint: mintAddress, error: (err as Error).message });
    return { ...defaultResult, riskScore: 0.1 }; // small penalty for scan failure
  }
}

// ─── Scoring function for composite scorer integration ──────
export function scoreRugDeployer(result: RugDeployerResult): number {
  // Invert risk score: higher = safer (matches composite scorer convention)
  return 1 - result.riskScore;
}

// ─── Batch scan for backtest / historical analysis ──────────
export async function batchScanDeployers(
  mints: string[],
  concurrency: number = 3,
): Promise<Map<string, RugDeployerResult>> {
  const results = new Map<string, RugDeployerResult>();

  for (let i = 0; i < mints.length; i += concurrency) {
    const batch = mints.slice(i, i + concurrency);
    const batchResults = await Promise.allSettled(
      batch.map(mint => scanForRugDeployer(mint)),
    );

    for (let j = 0; j < batch.length; j++) {
      const result = batchResults[j];
      if (result.status === 'fulfilled') {
        results.set(batch[j], result.value);
      }
    }

    // Rate limit
    if (i + concurrency < mints.length) {
      await new Promise(r => setTimeout(r, 500));
    }
  }

  return results;
}

// ─── Get all known ruggers ──────────────────────────────────
export function getKnownRuggers(): RuggerEntry[] {
  loadRuggerCache();
  return [...ruggerCache.values()].sort((a, b) => b.rugCount - a.rugCount);
}

export function getRuggerCount(): number {
  loadRuggerCache();
  return ruggerCache.size;
}
