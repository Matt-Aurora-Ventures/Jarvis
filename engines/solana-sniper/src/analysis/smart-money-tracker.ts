/**
 * Smart Money Wallet Tracker
 *
 * Tracks wallets with historically high win rates on memecoin trades.
 * When a tracked wallet buys a token, it generates a high-priority signal.
 *
 * Data sources:
 * 1. Helius Enhanced Transaction API — parse wallet activity
 * 2. DexScreener — verify token performance
 * 3. Local database — track wallet performance over time
 *
 * Scoring:
 * - Win rate > 70% = "whale" tier
 * - Win rate 50-70% = "smart" tier
 * - Win rate < 50% = tracked but no signal boost
 */
import axios from 'axios';
import fs from 'fs';
import path from 'path';
import { config } from '../config/index.js';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('smart-money');

export interface TrackedWallet {
  address: string;
  label: string;
  tier: 'whale' | 'smart' | 'tracked';
  winRate: number;
  totalTrades: number;
  wins: number;
  losses: number;
  avgPnlPct: number;
  totalPnlUsd: number;
  lastActive: string;
  recentBuys: Array<{
    mint: string;
    symbol?: string;
    boughtAt: string;
    amountUsd: number;
    currentPnlPct?: number;
  }>;
}

export interface SmartMoneySignal {
  mint: string;
  symbol: string;
  walletAddress: string;
  walletLabel: string;
  walletTier: 'whale' | 'smart' | 'tracked';
  walletWinRate: number;
  amountUsd: number;
  signalStrength: number; // 0-1, based on wallet tier + conviction
  timestamp: number;
}

// ─── Wallet database ──────────────────────────────────────
const WALLETS_FILE = path.resolve(process.cwd(), 'data', 'smart-wallets.json');

let walletDb: Map<string, TrackedWallet> = new Map();
let dbLoaded = false;

function loadWalletDb(): void {
  if (dbLoaded) return;
  try {
    if (fs.existsSync(WALLETS_FILE)) {
      const data: TrackedWallet[] = JSON.parse(fs.readFileSync(WALLETS_FILE, 'utf8'));
      walletDb = new Map(data.map(w => [w.address, w]));
      log.info('Loaded smart wallet database', { wallets: walletDb.size });
    }
  } catch {
    log.warn('Failed to load wallet database, starting fresh');
  }
  dbLoaded = true;
}

function saveWalletDb(): void {
  try {
    const dir = path.dirname(WALLETS_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(WALLETS_FILE, JSON.stringify([...walletDb.values()], null, 2));
  } catch (err) {
    log.warn('Failed to save wallet database', { error: (err as Error).message });
  }
}

// ─── Add/update wallet ────────────────────────────────────
export function addTrackedWallet(address: string, label?: string): TrackedWallet {
  loadWalletDb();
  const existing = walletDb.get(address);
  if (existing) return existing;

  const wallet: TrackedWallet = {
    address,
    label: label || `wallet_${address.slice(0, 6)}`,
    tier: 'tracked',
    winRate: 0,
    totalTrades: 0,
    wins: 0,
    losses: 0,
    avgPnlPct: 0,
    totalPnlUsd: 0,
    lastActive: new Date().toISOString(),
    recentBuys: [],
  };

  walletDb.set(address, wallet);
  saveWalletDb();
  log.info('Added tracked wallet', { address: address.slice(0, 8), label: wallet.label });
  return wallet;
}

export function recordWalletTrade(
  address: string,
  result: { mint: string; symbol?: string; pnlPct: number; pnlUsd: number; isWin: boolean },
): void {
  loadWalletDb();
  const wallet = walletDb.get(address);
  if (!wallet) return;

  wallet.totalTrades++;
  if (result.isWin) wallet.wins++;
  else wallet.losses++;
  wallet.winRate = wallet.wins / wallet.totalTrades;
  wallet.totalPnlUsd += result.pnlUsd;
  wallet.avgPnlPct = wallet.totalPnlUsd / Math.max(1, wallet.totalTrades);
  wallet.lastActive = new Date().toISOString();

  // Update tier
  if (wallet.totalTrades >= 10 && wallet.winRate >= 0.7) {
    wallet.tier = 'whale';
  } else if (wallet.totalTrades >= 5 && wallet.winRate >= 0.5) {
    wallet.tier = 'smart';
  }

  saveWalletDb();
}

// ─── Discover smart wallets from top traders ──────────────
export async function discoverSmartWallets(limit = 20): Promise<string[]> {
  loadWalletDb();
  const discovered: string[] = [];

  try {
    // Method 1: DexScreener top traders
    const resp = await axios.get(
      'https://api.dexscreener.com/token-boosts/top/v1',
      { timeout: 8000 },
    );

    const boosts = resp.data ?? [];
    for (const boost of boosts.slice(0, limit)) {
      if (boost.chainId !== 'solana' || !boost.tokenAddress) continue;

      // Get top traders for this token via DexScreener
      try {
        const tradersResp = await axios.get(
          `https://api.dexscreener.com/latest/dex/tokens/${boost.tokenAddress}`,
          { timeout: 8000 },
        );

        const pairs = tradersResp.data?.pairs ?? [];
        if (pairs.length === 0) continue;

        // Extract maker addresses from pair data
        const pair = pairs[0];
        if (pair.txns?.h1?.buys > 100) {
          // High-activity tokens — find top holders via Helius
          if (config.heliusApiKey) {
            try {
              const holdersResp = await axios.get(
                `https://api.helius.xyz/v0/token-metadata?api-key=${config.heliusApiKey}`,
                {
                  params: { mintAccounts: [boost.tokenAddress] },
                  timeout: 8000,
                },
              );

              // Extract top holder wallets
              const meta = holdersResp.data?.[0];
              if (meta?.onChainAccountInfo?.holders) {
                for (const holder of meta.onChainAccountInfo.holders.slice(0, 5)) {
                  if (holder.owner && !walletDb.has(holder.owner)) {
                    addTrackedWallet(holder.owner, `discovered_${boost.name || 'token'}`);
                    discovered.push(holder.owner);
                  }
                }
              }
            } catch {
              // Helius call failed, continue
            }
          }
        }
      } catch {
        // DexScreener rate limit, continue
      }

      // Rate limit
      await new Promise(r => setTimeout(r, 500));
    }
  } catch (err) {
    log.warn('Smart wallet discovery failed', { error: (err as Error).message });
  }

  log.info('Smart wallet discovery complete', { discovered: discovered.length, total: walletDb.size });
  return discovered;
}

// ─── Check if a wallet bought a specific token ────────────
export async function checkWalletBuys(mint: string): Promise<SmartMoneySignal[]> {
  loadWalletDb();
  const signals: SmartMoneySignal[] = [];

  if (!config.heliusApiKey || walletDb.size === 0) return signals;

  try {
    // Get recent buyers of this token via Helius
    const resp = await axios.get(
      `https://api.helius.xyz/v0/addresses/${mint}/transactions?api-key=${config.heliusApiKey}&type=SWAP`,
      { timeout: 10000 },
    );

    const txns = resp.data ?? [];

    for (const txn of txns.slice(0, 50)) {
      // Check if any tracked wallet is involved
      const accounts = txn.accountData?.map((a: { account: string }) => a.account) ?? [];

      for (const account of accounts) {
        const wallet = walletDb.get(account);
        if (!wallet) continue;
        if (wallet.tier === 'tracked' && wallet.winRate < 0.5) continue; // Skip low performers

        // Check if it's a buy (token received)
        const isBuy = txn.tokenTransfers?.some(
          (t: { mint: string; toUserAccount: string }) => t.mint === mint && t.toUserAccount === account,
        );

        if (isBuy) {
          const signalStrength = wallet.tier === 'whale' ? 0.9 :
                                 wallet.tier === 'smart' ? 0.7 : 0.4;

          signals.push({
            mint,
            symbol: mint.slice(0, 6),
            walletAddress: account,
            walletLabel: wallet.label,
            walletTier: wallet.tier,
            walletWinRate: wallet.winRate,
            amountUsd: 0, // Would need to calculate from transfer amount
            signalStrength,
            timestamp: txn.timestamp ? txn.timestamp * 1000 : Date.now(),
          });

          log.info('Smart money buy detected!', {
            wallet: account.slice(0, 8),
            tier: wallet.tier,
            winRate: (wallet.winRate * 100).toFixed(0) + '%',
            token: mint.slice(0, 8),
            signalStrength: signalStrength.toFixed(2),
          });

          // Update wallet's recent buys
          wallet.recentBuys = [
            { mint, boughtAt: new Date().toISOString(), amountUsd: 0 },
            ...wallet.recentBuys.slice(0, 19),
          ];
          wallet.lastActive = new Date().toISOString();
          saveWalletDb();
        }
      }
    }
  } catch (err) {
    log.debug('Smart money check failed', { mint: mint.slice(0, 8), error: (err as Error).message });
  }

  return signals;
}

// ─── Get all tracked wallets ──────────────────────────────
export function getTrackedWallets(): TrackedWallet[] {
  loadWalletDb();
  return [...walletDb.values()].sort((a, b) => b.winRate - a.winRate);
}

export function getSmartWallets(): TrackedWallet[] {
  return getTrackedWallets().filter(w => w.tier === 'whale' || w.tier === 'smart');
}

export function getWalletCount(): { total: number; whale: number; smart: number } {
  loadWalletDb();
  const wallets = [...walletDb.values()];
  return {
    total: wallets.length,
    whale: wallets.filter(w => w.tier === 'whale').length,
    smart: wallets.filter(w => w.tier === 'smart').length,
  };
}

// ─── Compute signal boost for a token based on smart money ──
export function computeSmartMoneyBoost(signals: SmartMoneySignal[]): number {
  if (signals.length === 0) return 0;

  // Weighted average of signal strengths
  const totalWeight = signals.reduce((sum, s) => sum + s.signalStrength, 0);
  const boost = Math.min(0.3, totalWeight * 0.15); // Cap at 0.3 boost

  return boost;
}
