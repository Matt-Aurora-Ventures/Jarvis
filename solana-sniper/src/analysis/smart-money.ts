import axios from 'axios';
import fs from 'fs';
import path from 'path';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('smart-money');
const CACHE_DIR = path.resolve(process.cwd(), 'data', 'smart-money');

// ─── Known profitable wallet categories ──────────────────────
// These are PUBLIC wallet addresses from on-chain data, NOT private keys.
// Sources: Solscan leaderboards, GMGN.ai top traders, Birdeye whale wallets

export interface SmartWallet {
  address: string;
  label: string;
  category: 'whale' | 'insider' | 'degen_winner' | 'fund' | 'kol';
  winRate?: number;       // estimated win rate from historical trades
  avgReturn?: number;     // average return per trade
  totalPnlSol?: number;  // total lifetime P&L in SOL
  lastActive?: number;    // last seen activity (epoch ms)
}

// Top known profitable Solana wallets (from public on-chain analysis)
// These are anonymized addresses commonly tracked by copy-trading platforms
const KNOWN_SMART_WALLETS: SmartWallet[] = [
  // Note: In production, these would be populated from an API or database
  // Placeholder structure - actual addresses should be sourced from:
  // - Birdeye API: /defi/token_trending_wallets
  // - Solscan whale alerts
  // - GMGN.ai top trader boards
];

export interface SmartMoneySignal {
  walletAddress: string;
  walletLabel: string;
  category: SmartWallet['category'];
  tokenMint: string;
  tokenSymbol?: string;
  action: 'buy' | 'sell';
  amountSol: number;
  timestamp: number;
  txHash: string;
  // Derived confidence signal
  signalStrength: number; // 0-1 (higher = more bullish/bearish)
}

export interface SmartMoneyScore {
  mint: string;
  smartBuyers: number;      // count of smart wallets that bought
  smartSellers: number;     // count of smart wallets that sold
  netFlow: number;          // buyers - sellers (positive = bullish)
  avgBuyerWinRate: number;  // average win rate of buyers
  signalScore: number;      // -1 to 1 composite signal
  recentSignals: SmartMoneySignal[];
  computedAt: number;
}

// ─── Cache ───────────────────────────────────────────────────
const SIGNAL_CACHE = new Map<string, { data: SmartMoneyScore; fetchedAt: number }>();
const SIGNAL_CACHE_TTL = 5 * 60 * 1000; // 5 min

function getCachedScore(mint: string): SmartMoneyScore | null {
  const entry = SIGNAL_CACHE.get(mint);
  if (entry && Date.now() - entry.fetchedAt < SIGNAL_CACHE_TTL) return entry.data;
  return null;
}

// ─── Birdeye API integration (free tier available) ───────────
const BIRDEYE_API = 'https://public-api.birdeye.so';

/**
 * Get top traders for a specific token from Birdeye.
 * Birdeye provides data about which wallets are trading a token.
 */
async function fetchBirdeyeTopTraders(mint: string): Promise<Array<{
  address: string;
  volume: number;
  trades: number;
  pnl: number;
}>> {
  const apiKey = process.env.BIRDEYE_API_KEY;
  if (!apiKey) return [];

  try {
    const res = await axios.get(`${BIRDEYE_API}/defi/v3/token/trade-data/single`, {
      params: { address: mint },
      headers: {
        Accept: 'application/json',
        'X-API-KEY': apiKey,
        'x-chain': 'solana',
      },
      timeout: 10000,
    });

    const data = res.data?.data;
    if (!data) return [];

    // Extract trade data
    return [{
      address: 'aggregate',
      volume: data.volume24h || 0,
      trades: data.trade24h || 0,
      pnl: 0,
    }];
  } catch {
    return [];
  }
}

/**
 * Check if any known smart wallets recently traded a token.
 * Uses Helius API (if available) to check recent transactions.
 */
async function checkSmartWalletActivity(mint: string): Promise<SmartMoneySignal[]> {
  const heliusKey = process.env.HELIUS_API_KEY;
  if (!heliusKey) return [];

  const signals: SmartMoneySignal[] = [];

  // Check recent token transactions via Helius
  try {
    const res = await axios.get(
      `https://api.helius.xyz/v0/addresses/${mint}/transactions?api-key=${heliusKey}&type=SWAP&limit=50`,
      { timeout: 15000 }
    );

    const txns = res.data || [];
    const smartAddresses = new Set(KNOWN_SMART_WALLETS.map(w => w.address));

    for (const tx of txns) {
      // Check if any account involved is a known smart wallet
      const accounts = tx.accountData?.map((a: { account: string }) => a.account) || [];
      for (const acc of accounts) {
        if (smartAddresses.has(acc)) {
          const wallet = KNOWN_SMART_WALLETS.find(w => w.address === acc)!;
          signals.push({
            walletAddress: acc,
            walletLabel: wallet.label,
            category: wallet.category,
            tokenMint: mint,
            action: 'buy', // simplified -- would need deeper tx parsing
            amountSol: 0,
            timestamp: tx.timestamp * 1000,
            txHash: tx.signature,
            signalStrength: (wallet.winRate || 0.5) * 0.8,
          });
        }
      }
    }
  } catch (err) {
    log.warn('Helius smart wallet check failed', { error: (err as Error).message });
  }

  return signals;
}

/**
 * Compute a composite smart money score for a token.
 * Combines:
 * - Known whale wallet activity
 * - Volume concentration (is volume from few large wallets = bullish/risky)
 * - Buy/sell flow from top traders
 */
export async function getSmartMoneyScore(mint: string): Promise<SmartMoneyScore> {
  const cached = getCachedScore(mint);
  if (cached) return cached;

  const [signals, traders] = await Promise.all([
    checkSmartWalletActivity(mint),
    fetchBirdeyeTopTraders(mint),
  ]);

  const buyers = signals.filter(s => s.action === 'buy');
  const sellers = signals.filter(s => s.action === 'sell');

  const avgBuyerWinRate = buyers.length > 0
    ? buyers.reduce((s, b) => s + b.signalStrength, 0) / buyers.length
    : 0;

  // Composite signal: more smart buyers = bullish
  let signalScore = 0;
  signalScore += Math.min(0.5, buyers.length * 0.15);    // each smart buyer adds up to 0.5
  signalScore -= Math.min(0.5, sellers.length * 0.15);   // each smart seller subtracts
  signalScore += avgBuyerWinRate * 0.3;                   // high WR buyers add confidence

  // Volume concentration from Birdeye
  if (traders.length > 0 && traders[0].volume > 100000) {
    signalScore += 0.1; // high volume = active interest
  }

  signalScore = Math.max(-1, Math.min(1, signalScore));

  const result: SmartMoneyScore = {
    mint,
    smartBuyers: buyers.length,
    smartSellers: sellers.length,
    netFlow: buyers.length - sellers.length,
    avgBuyerWinRate,
    signalScore,
    recentSignals: signals.slice(0, 10),
    computedAt: Date.now(),
  };

  SIGNAL_CACHE.set(mint, { data: result, fetchedAt: Date.now() });

  if (signals.length > 0) {
    log.info('Smart money signal detected', {
      mint,
      buyers: buyers.length,
      sellers: sellers.length,
      score: signalScore.toFixed(2),
    });
  }

  return result;
}

/**
 * Get the smart money conviction adjustment for use in the sniper's
 * getConvictionMultiplier(). Returns -0.3 to +0.5.
 */
export function getSmartMoneyConvictionBonus(score: SmartMoneyScore): number {
  if (score.signalScore >= 0.5) return 0.5;    // Multiple smart wallets buying
  if (score.signalScore >= 0.3) return 0.3;    // Some smart wallet activity
  if (score.signalScore >= 0.1) return 0.15;   // Light smart money interest
  if (score.signalScore <= -0.3) return -0.3;  // Smart money selling
  if (score.signalScore <= -0.1) return -0.15; // Some smart money exits
  return 0;
}

/**
 * Fetch and save the list of top performing wallets from DexScreener/Birdeye.
 * This is meant to be called periodically (e.g., daily) to refresh the wallet list.
 */
export async function refreshSmartWalletList(): Promise<SmartWallet[]> {
  const wallets: SmartWallet[] = [];

  // Note: In production, this would:
  // 1. Query Birdeye API for top trader leaderboard
  // 2. Filter for wallets with >60% win rate and >50 trades
  // 3. Categorize by trading pattern (whale, degen, fund, etc.)
  // 4. Save to data/smart-money/wallets.json

  try {
    const savePath = path.join(CACHE_DIR, 'wallets.json');
    if (!fs.existsSync(CACHE_DIR)) fs.mkdirSync(CACHE_DIR, { recursive: true });
    fs.writeFileSync(savePath, JSON.stringify({ wallets, updatedAt: new Date().toISOString() }, null, 2));
    log.info('Smart wallet list refreshed', { count: wallets.length });
  } catch (err) {
    log.warn('Failed to save smart wallet list', { error: (err as Error).message });
  }

  return wallets;
}

/**
 * For the backtester: simulate smart money signal based on token characteristics.
 * Tokens that had smart money activity tend to have:
 * - Higher buy/sell ratios
 * - Higher volume spikes
 * - More holder distribution
 * - Better price trajectory
 */
export function simulateSmartMoneyScore(token: {
  buyCount1h: number;
  sellCount1h: number;
  volumeUsd24h: number;
  liquidityUsd: number;
  holderCount: number;
  volumeSurgeRatio?: number;
  isVolumeSurge?: boolean;
}): number {
  let score = 0;

  // Volume surge = smart money accumulation signal
  if (token.isVolumeSurge && (token.volumeSurgeRatio || 0) > 3) {
    score += 0.3;
  } else if (token.isVolumeSurge) {
    score += 0.15;
  }

  // High buy/sell ratio = accumulation
  const ratio = token.buyCount1h / Math.max(1, token.sellCount1h);
  if (ratio > 3) score += 0.2;
  else if (ratio > 2) score += 0.1;

  // Many holders = distribution (smart money distributed, less risk)
  if (token.holderCount > 200) score += 0.1;
  else if (token.holderCount > 100) score += 0.05;

  // High vol/liq = active trading interest
  const volLiq = token.volumeUsd24h / Math.max(1, token.liquidityUsd);
  if (volLiq > 2) score += 0.15;
  else if (volLiq > 1) score += 0.08;

  return Math.max(-1, Math.min(1, score));
}
