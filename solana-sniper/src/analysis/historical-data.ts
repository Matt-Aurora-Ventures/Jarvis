import axios from 'axios';
import fs from 'fs';
import path from 'path';
import { createModuleLogger } from '../utils/logger.js';
import { getMacroSnapshot, getCorrelationAdjustment, type MacroSnapshot } from './macro-correlator.js';
import { getHyperliquidCorrelations, type HLCorrelationData } from './hyperliquid-data.js';
import { simulateSmartMoneyScore } from './smart-money.js';
import { fetchBatchOHLCV } from './ohlcv-fetcher.js';

const log = createModuleLogger('historical-data');

// ─── TTL cache for API data ─────────────────────────────────
const CACHE_FILE = path.resolve(process.cwd(), 'data', 'historical-cache.json');
const CACHE_TTL_MS = 30 * 60 * 1000; // 30 minutes (extended for backtesting)

interface CacheEntry {
  tokens: PumpFunHistoricalToken[];
  fetchedAt: number;
}

function readCache(): CacheEntry | null {
  try {
    if (!fs.existsSync(CACHE_FILE)) return null;
    const data: CacheEntry = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
    if (Date.now() - data.fetchedAt < CACHE_TTL_MS && data.tokens.length > 0) {
      log.info('Using cached historical data', { tokens: data.tokens.length, ageMs: Date.now() - data.fetchedAt });
      return data;
    }
  } catch { /* ignore */ }
  return null;
}

function writeCache(tokens: PumpFunHistoricalToken[]): void {
  try {
    const dir = path.dirname(CACHE_FILE);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(CACHE_FILE, JSON.stringify({ tokens, fetchedAt: Date.now() }));
  } catch { /* ignore */ }
}

// ─── xStock mint addresses (hardcoded from xstocks-data registry) ────────
// Tokenized equities, pre-IPO tokens, indexes, and commodities on Solana
const XSTOCK_MINTS: Array<{ mint: string; ticker: string; name: string; category: string }> = [
  // xStocks - Tech
  { mint: 'XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp', ticker: 'AAPLx', name: 'Apple', category: 'XSTOCK' },
  { mint: 'XspzcW1PRtgf6Wj92HCiZdjzKCyFekVD8P5Ueh3dRMX', ticker: 'MSFTx', name: 'Microsoft', category: 'XSTOCK' },
  { mint: 'XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN', ticker: 'GOOGLx', name: 'Alphabet', category: 'XSTOCK' },
  { mint: 'Xs3eBt7uRfJX8QUs4suhyU8p2M6DoUDrJyWBa8LLZsg', ticker: 'AMZNx', name: 'Amazon', category: 'XSTOCK' },
  { mint: 'Xsa62P5mvPszXL1krVUnU5ar38bBSVcWAB6fmPCo5Zu', ticker: 'METAx', name: 'Meta', category: 'XSTOCK' },
  { mint: 'Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh', ticker: 'NVDAx', name: 'NVIDIA', category: 'XSTOCK' },
  { mint: 'XsgSaSvNSqLTtFuyWPBhK9196Xb9Bbdyjj4fH3cPJGo', ticker: 'AVGOx', name: 'Broadcom', category: 'XSTOCK' },
  { mint: 'XsjFwUPiLofddX5cWFHW35GCbXcSu1BCUGfxoQAQjeL', ticker: 'ORCLx', name: 'Oracle', category: 'XSTOCK' },
  { mint: 'XsczbcQ3zfcgAEt9qHQES8pxKAVG5rujPSHQEXi4kaN', ticker: 'CRMx', name: 'Salesforce', category: 'XSTOCK' },
  { mint: 'Xsr3pdLQyXvDJBFgpR5nexCEZwXvigb8wbPYp4YoNFf', ticker: 'CSCOx', name: 'Cisco', category: 'XSTOCK' },
  { mint: 'Xs5UJzmCRQ8DWZjskExdSQDnbE6iLkRu2jjrRAB1JSU', ticker: 'ACNx', name: 'Accenture', category: 'XSTOCK' },
  { mint: 'XshPgPdXFRWB8tP1j82rebb2Q9rPgGX37RuqzohmArM', ticker: 'INTCx', name: 'Intel', category: 'XSTOCK' },
  { mint: 'XspwhyYPdWVM8XBHZnpS9hgyag9MKjLRyE3tVfmCbSr', ticker: 'IBMx', name: 'IBM', category: 'XSTOCK' },
  { mint: 'XsuxRGDzbLjnJ72v74b7p9VY6N66uYgTCyfwwRjVCJA', ticker: 'MRVLx', name: 'Marvell', category: 'XSTOCK' },
  // xStocks - Software & Cybersecurity
  { mint: 'Xs7xXqkcK7K8urEqGg52SECi79dRp2cEKKuYjUePYDw', ticker: 'CRWDx', name: 'CrowdStrike', category: 'XSTOCK' },
  { mint: 'XsoBhf2ufR8fTyNSjqfU71DYGaE6Z3SUGAidpzriAA4', ticker: 'PLTRx', name: 'Palantir', category: 'XSTOCK' },
  { mint: 'XsEH7wWfJJu2ZT3UCFeVfALnVA6CP5ur7Ee11KmzVpL', ticker: 'NFLXx', name: 'Netflix', category: 'XSTOCK' },
  { mint: 'XsPdAVBi8Zc1xvv53k4JcMrQaEDTgkGqKYeh7AYgPHV', ticker: 'APPx', name: 'AppLovin', category: 'XSTOCK' },
  // xStocks - EV & Auto
  { mint: 'XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB', ticker: 'TSLAx', name: 'Tesla', category: 'XSTOCK' },
  { mint: 'Xsf9mBktVB9BSU5kf4nHxPq5hCBJ2j2ui3ecFGxPRGc', ticker: 'GMEx', name: 'GameStop', category: 'XSTOCK' },
  // xStocks - Finance
  { mint: 'XsMAqkcKsUewDrzVkait4e5u4y8REgtyS7jWgCpLV2C', ticker: 'JPMx', name: 'JPMorgan', category: 'XSTOCK' },
  { mint: 'XsgaUyp4jd1fNBCxgtTKkW64xnnhQcvgaxzsbAq5ZD1', ticker: 'GSx', name: 'Goldman Sachs', category: 'XSTOCK' },
  { mint: 'XswsQk4duEQmCbGzfqUUWYmi7pV7xpJ9eEmLHXCaEQP', ticker: 'BACx', name: 'Bank of America', category: 'XSTOCK' },
  { mint: 'XsqgsbXwWogGJsNcVZ3TyVouy2MbTkfCFhCGGGcQZ2p', ticker: 'Vx', name: 'Visa', category: 'XSTOCK' },
  { mint: 'XsApJFV9MAktqnAc6jqzsHVujxkGm9xcSUffaBoYLKC', ticker: 'MAx', name: 'Mastercard', category: 'XSTOCK' },
  { mint: 'Xs7ZdzSHLU9ftNJsii5fCeJhoRWSC32SQGzGQtePxNu', ticker: 'COINx', name: 'Coinbase', category: 'XSTOCK' },
  { mint: 'XsvNBAYkrDRNhA7wPHQfX3ZUXZyZLdnCQDfHZ56bzpg', ticker: 'HOODx', name: 'Robinhood', category: 'XSTOCK' },
  { mint: 'XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ', ticker: 'MSTRx', name: 'MicroStrategy', category: 'XSTOCK' },
  { mint: 'Xs6B6zawENwAbWVi7w92rjazLuAr5Az59qgWKcNb45x', ticker: 'BRK.Bx', name: 'Berkshire B', category: 'XSTOCK' },
  // xStocks - Healthcare
  { mint: 'Xsnuv4omNoHozR6EEW5mXkw8Nrny5rB3jVfLqi6gKMH', ticker: 'LLYx', name: 'Eli Lilly', category: 'XSTOCK' },
  { mint: 'XszvaiXGPwvk2nwb3o9C1CX4K6zH8sez11E6uyup6fe', ticker: 'UNHx', name: 'UnitedHealth', category: 'XSTOCK' },
  { mint: 'XsGVi5eo1Dh2zUpic4qACcjuWGjNv8GCt3dm5XcX6Dn', ticker: 'JNJx', name: 'J&J', category: 'XSTOCK' },
  { mint: 'XsAtbqkAP1HJxy7hFDeq7ok6yM43DQ9mQ1Rh861X8rw', ticker: 'PFEx', name: 'Pfizer', category: 'XSTOCK' },
  { mint: 'XsnQnU7AdbRZYe2akqqpibDdXjkieGFfSkbkjX1Sd1X', ticker: 'MRKx', name: 'Merck', category: 'XSTOCK' },
  { mint: 'XswbinNKyPmzTa5CskMbCPvMW6G5CMnZXZEeQSSQoie', ticker: 'ABBVx', name: 'AbbVie', category: 'XSTOCK' },
  { mint: 'XsHtf5RpxsQ7jeJ9ivNewouZKJHbPxhPoEy6yYvULr7', ticker: 'ABTx', name: 'Abbott', category: 'XSTOCK' },
  { mint: 'Xs8drBWy3Sd5QY3aifG9kt9KFs2K3PGZmx7jWrsrk57', ticker: 'TMOx', name: 'Thermo Fisher', category: 'XSTOCK' },
  { mint: 'Xseo8tgCZfkHxWS9xbFYeKFyMSbWEvZGFV1Gh53GtCV', ticker: 'DHRx', name: 'Danaher', category: 'XSTOCK' },
  { mint: 'XsDgw22qRLTv5Uwuzn6T63cW69exG41T6gwQhEK22u2', ticker: 'MDTx', name: 'Medtronic', category: 'XSTOCK' },
  { mint: 'Xs3ZFkPYT2BN7qBMqf1j1bfTeTm1rFzEFSsQ1z3wAKU', ticker: 'AZNx', name: 'AstraZeneca', category: 'XSTOCK' },
  { mint: 'XsfAzPzYrYjd4Dpa9BU3cusBsvWfVB9gBcyGC87S57n', ticker: 'NVOx', name: 'Novo Nordisk', category: 'XSTOCK' },
  // xStocks - Consumer & Retail
  { mint: 'XsaBXg8dU5cPM6ehmVctMkVqoiRG2ZjMo1cyBJ3AykQ', ticker: 'KOx', name: 'Coca-Cola', category: 'XSTOCK' },
  { mint: 'Xsv99frTRUeornyvCfvhnDesQDWuvns1M852Pez91vF', ticker: 'PEPx', name: 'PepsiCo', category: 'XSTOCK' },
  { mint: 'XsqE9cRRpzxcGKDXj1BJ7Xmg4GRhZoyY1KpmGSxAWT2', ticker: 'MCDx', name: "McDonald's", category: 'XSTOCK' },
  { mint: 'Xs151QeqTCiuKtinzfRATnUESM2xTU6V9Wy8Vy538ci', ticker: 'WMTx', name: 'Walmart', category: 'XSTOCK' },
  { mint: 'XszjVtyhowGjSC5odCqBpW1CtXXwXjYokymrk7fGKD3', ticker: 'HDx', name: 'Home Depot', category: 'XSTOCK' },
  { mint: 'XsYdjDjNUygZ7yGKfQaB6TxLh2gC6RRjzLtLAGJrhzV', ticker: 'PGx', name: 'P&G', category: 'XSTOCK' },
  { mint: 'Xsba6tUnSjDae2VcopDB6FGGDaxRrewFCDa5hKn5vT3', ticker: 'PMx', name: 'Philip Morris', category: 'XSTOCK' },
  // xStocks - Industrial & Energy
  { mint: 'XsaHND8sHyfMfsWPj6kSdd5VwvCayZvjYgKmmcNL5qh', ticker: 'XOMx', name: 'ExxonMobil', category: 'XSTOCK' },
  { mint: 'XsNNMt7WTNA2sV3jrb1NNfNgapxRF5i4i6GcnTRRHts', ticker: 'CVXx', name: 'Chevron', category: 'XSTOCK' },
  { mint: 'XsSr8anD1hkvNMu8XQiVcmiaTP7XGvYu7Q58LdmtE8Z', ticker: 'LINx', name: 'Linde', category: 'XSTOCK' },
  { mint: 'XsRbLZthfABAPAfumWNEJhPyiKDW6TvDVeAeW7oKqA2', ticker: 'HONx', name: 'Honeywell', category: 'XSTOCK' },
  // xStocks - Media & Crypto
  { mint: 'XsvKCaNsxg2GN8jjUmq71qukMJr7Q1c5R2Mk9P8kcS8', ticker: 'CMCSAx', name: 'Comcast', category: 'XSTOCK' },
  { mint: 'XsaQTCgebC2KPbf27KUhdv5JFvHhQ4GDAPURwrEhAzb', ticker: 'AMBRx', name: 'Amber', category: 'XSTOCK' },
  { mint: 'XsueG8BtpquVJX9LVLLEGuViXUungE6WmK5YZ3p3bd1', ticker: 'CRCLx', name: 'Circle', category: 'XSTOCK' },
  // PreStocks
  { mint: 'PreANxuXjsy2pvisWWMNB6YaJNzr7681wJJr2rHsfTh', ticker: 'SPACEX', name: 'SpaceX', category: 'PRESTOCK' },
  { mint: 'PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF', ticker: 'OPENAI', name: 'OpenAI', category: 'PRESTOCK' },
  { mint: 'Pren1FvFX6J3E4kXhJuCiAD5aDmGEb7qJRncwA8Lkhw', ticker: 'ANTHROPIC', name: 'Anthropic', category: 'PRESTOCK' },
  { mint: 'PreC1KtJ1sBPPqaeeqL6Qb15GTLCYVvyYEwxhdfTwfx', ticker: 'XAI', name: 'xAI', category: 'PRESTOCK' },
  { mint: 'PresTj4Yc2bAR197Er7wz4UUKSfqt6FryBEdAriBoQB', ticker: 'ANDURIL', name: 'Anduril', category: 'PRESTOCK' },
  { mint: 'PreLWGkkeqG1s4HEfFZSy9moCrJ7btsHuUtfcCeoRua', ticker: 'KALSHI', name: 'Kalshi', category: 'PRESTOCK' },
  { mint: 'Pre8AREmFPtoJFT8mQSXQLh56cwJmM7CFDRuoGBZiUP', ticker: 'POLYMARKET', name: 'Polymarket', category: 'PRESTOCK' },
  // Indexes
  { mint: 'XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W', ticker: 'SPYx', name: 'S&P 500', category: 'INDEX' },
  { mint: 'Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ', ticker: 'QQQx', name: 'Nasdaq 100', category: 'INDEX' },
  { mint: 'XsjQP3iMAaQ3kQScQKthQpx9ALRbjKAjQtHg6TFomoc', ticker: 'TQQQx', name: 'TQQQ', category: 'INDEX' },
  { mint: 'XsssYEQjzxBCFgvYFFNuhJFBeHNdLWYeUSP8P45cDr9', ticker: 'VTIx', name: 'Vanguard Total', category: 'INDEX' },
  { mint: 'XsqBC5tcVQLYt8wqGCHRnAUUecbRYXoJCReD6w7QEKp', ticker: 'TBLLx', name: 'T-Bills', category: 'INDEX' },
  // Commodities
  { mint: 'Xsv9hRk1z5ystj9MhnA7Lq4vjSsLwzL2nxrwmwtD3re', ticker: 'GLDx', name: 'Gold', category: 'COMMODITY' },
];

const XSTOCK_MINT_SET = new Set(XSTOCK_MINTS.map(x => x.mint));
const XSTOCK_BY_MINT = new Map(XSTOCK_MINTS.map(x => [x.mint, x]));

// ─── Blue Chip Solana tokens (>1 year history, high liquidity, proven track record) ────
const BLUE_CHIP_MINTS: Array<{ mint: string; ticker: string; name: string; category: string }> = [
  // DeFi Blue Chips
  { mint: 'So11111111111111111111111111111111111111112', ticker: 'SOL', name: 'Solana', category: 'BLUE_CHIP' },
  { mint: 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN', ticker: 'JUP', name: 'Jupiter', category: 'BLUE_CHIP' },
  { mint: '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R', ticker: 'RAY', name: 'Raydium', category: 'BLUE_CHIP' },
  { mint: 'orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE', ticker: 'ORCA', name: 'Orca', category: 'BLUE_CHIP' },
  { mint: 'MNDEFzGvMt87ueuHvVU9VcTqsAP5b3fTGPsHuuPA5ey', ticker: 'MNDE', name: 'Marinade', category: 'BLUE_CHIP' },
  { mint: 'SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt', ticker: 'SRM', name: 'Serum', category: 'BLUE_CHIP' },
  { mint: 'HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3', ticker: 'PYTH', name: 'Pyth Network', category: 'BLUE_CHIP' },
  { mint: 'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL', ticker: 'JTO', name: 'Jito', category: 'BLUE_CHIP' },
  { mint: 'WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk', ticker: 'WEN', name: 'Wen', category: 'BLUE_CHIP' },
  // Meme Blue Chips (established, large community, >1yr)
  { mint: 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263', ticker: 'BONK', name: 'Bonk', category: 'BLUE_CHIP' },
  { mint: 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm', ticker: 'WIF', name: 'dogwifhat', category: 'BLUE_CHIP' },
  { mint: 'ukHH6c7mMyiWCf1b9pnWe25TSpkDDt3H5pQZgZ74J82', ticker: 'BOME', name: 'BOOK OF MEME', category: 'BLUE_CHIP' },
  { mint: 'MEW1gQWJ3nEXg2qgERiKu7FAFj79PHvQVREQUzScPP5', ticker: 'MEW', name: 'cat in a dogs world', category: 'BLUE_CHIP' },
  { mint: '7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr', ticker: 'POPCAT', name: 'Popcat', category: 'BLUE_CHIP' },
  // Infrastructure
  { mint: 'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof', ticker: 'RENDER', name: 'Render', category: 'BLUE_CHIP' },
  { mint: '85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ', ticker: 'W', name: 'Wormhole', category: 'BLUE_CHIP' },
  { mint: 'TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6', ticker: 'TNSR', name: 'Tensor', category: 'BLUE_CHIP' },
];

const BLUE_CHIP_MINT_SET = new Set(BLUE_CHIP_MINTS.map(b => b.mint));

// ─── Pump.fun historical data via DexScreener ────────────────
export interface PumpFunHistoricalToken {
  mint: string;
  symbol: string;
  name: string;
  createdAt: number;
  launchPriceUsd: number;
  peakPriceUsd: number;
  currentPriceUsd: number;
  price5min: number;
  price15min: number;
  price1h: number;
  price4h: number;
  price24h: number;
  liquidityUsd: number;
  volumeUsd24h: number;
  holderCount: number;
  buyCount1h: number;
  sellCount1h: number;
  wasRug: boolean;
  ruggedAtPct: number; // how much it dropped from peak
  maxMultiple: number; // peak / launch
  source: 'pumpfun' | 'raydium' | 'pumpswap';

  // ─── Enhanced fields ──────────────────────────
  // Age classification
  ageHours: number;
  ageCategory: 'fresh' | 'young' | 'established' | 'veteran';
  // Volume surge detection
  volumeSurgeRatio: number;
  avgDailyVolume: number;
  isVolumeSurge: boolean;
  // Market structure
  marketCapUsd: number;
  mcapLiqRatio: number;
  // Token classification flags
  isEstablished: boolean;
  isVeteran: boolean;
  isBlueChip: boolean;
  isXStock: boolean;
  // Sub-category for tokenized assets (from XSTOCK_MINTS registry)
  xStockCategory?: 'XSTOCK' | 'PRESTOCK' | 'INDEX' | 'COMMODITY';
  // Macro correlation hints
  btcCorrelation: number;
  // Price trajectory
  priceTrajectory: 'pumping' | 'dumping' | 'consolidating' | 'recovering';
}

// ─── BTC price cache for correlation estimation ──────────────
let _btcPriceChange24h: number | null = null;
let _btcPriceFetchedAt = 0;
const BTC_CACHE_TTL_MS = 10 * 60 * 1000; // 10 min

async function fetchBtcPriceChange(): Promise<number> {
  if (_btcPriceChange24h !== null && Date.now() - _btcPriceFetchedAt < BTC_CACHE_TTL_MS) {
    return _btcPriceChange24h;
  }
  try {
    const resp = await fetchWithRetry(() =>
      axios.get('https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112', { timeout: 8000 })
    );
    // Use SOL as proxy since we are on Solana; alternatively fetch BTC pair
    // DexScreener returns SOL pairs; let's use a BTC pair if available
    const pairs = resp.data?.pairs ?? [];
    const btcPair = pairs.find((p: Record<string, unknown>) => {
      const qt = p.quoteToken as Record<string, string> | undefined;
      return qt?.symbol?.toUpperCase() === 'BTC' || qt?.symbol?.toUpperCase() === 'WBTC';
    });
    if (btcPair) {
      const pc = btcPair.priceChange as Record<string, number> | undefined;
      _btcPriceChange24h = pc?.h24 ?? 0;
    } else {
      // Fallback: use first SOL pair's 24h change as macro proxy
      const firstPair = pairs[0];
      if (firstPair) {
        const pc = firstPair.priceChange as Record<string, number> | undefined;
        _btcPriceChange24h = pc?.h24 ?? 0;
      } else {
        _btcPriceChange24h = 0;
      }
    }
    _btcPriceFetchedAt = Date.now();
  } catch {
    _btcPriceChange24h = _btcPriceChange24h ?? 0;
  }
  return _btcPriceChange24h!;
}

// ─── Helper: classify age ────────────────────────────────────
function classifyAge(ageHours: number): 'fresh' | 'young' | 'established' | 'veteran' {
  if (ageHours < 24) return 'fresh';
  if (ageHours < 7 * 24) return 'young';
  if (ageHours < 90 * 24) return 'established';
  return 'veteran';
}

// ─── Helper: classify price trajectory ───────────────────────
function classifyTrajectory(
  h1Change: number,
  h6Change: number,
  h24Change: number,
): 'pumping' | 'dumping' | 'consolidating' | 'recovering' {
  // Pumping: strong upward movement in last 1h and 6h
  if (h1Change > 10 && h6Change > 5) return 'pumping';
  // Dumping: strong downward movement
  if (h1Change < -10 && h6Change < -5) return 'dumping';
  // Recovering: negative 24h but positive recent
  if (h24Change < -5 && h1Change > 3) return 'recovering';
  // Consolidating: small changes
  return 'consolidating';
}

// ─── Helper: estimate BTC correlation ────────────────────────
function estimateBtcCorrelation(h24Change: number, btcH24Change: number): number {
  if (btcH24Change === 0) return 0;
  // Simple directional correlation: same direction = positive, opposite = negative
  // Magnitude-weighted: if both move similarly, correlation is high
  const sameDir = Math.sign(h24Change) === Math.sign(btcH24Change);
  const magnitudeRatio = Math.min(Math.abs(h24Change), Math.abs(btcH24Change)) /
    Math.max(Math.abs(h24Change), Math.abs(btcH24Change), 0.01);
  if (sameDir) return Math.min(1, magnitudeRatio * 0.8);
  return Math.max(-1, -magnitudeRatio * 0.8);
}

// Fetch recent Solana token launches from DexScreener
export async function fetchDexScreenerPairs(
  minLiquidity: number = 5000,
  limit: number = 100,
  deepFetch: boolean = false,
): Promise<PumpFunHistoricalToken[]> {
  const tokens: PumpFunHistoricalToken[] = [];

  // Fetch BTC price change for correlation estimation
  const btcChange = await fetchBtcPriceChange();

  try {
    // DexScreener latest boosted tokens (active projects) -- with retry
    const resp = await fetchWithRetry(() =>
      axios.get('https://api.dexscreener.com/token-boosts/latest/v1', { timeout: 10000 })
    );
    const boosts = (resp.data ?? []).filter((b: { chainId: string }) => b.chainId === 'solana').slice(0, limit);

    // Batch fetch: DexScreener supports comma-separated addresses (up to 30)
    const addresses = boosts.map((b: { tokenAddress: string }) => b.tokenAddress);
    const batchSize = 30;

    for (let i = 0; i < addresses.length; i += batchSize) {
      const batch = addresses.slice(i, i + batchSize);
      try {
        const pairResp = await fetchWithRetry(() =>
          axios.get(`https://api.dexscreener.com/latest/dex/tokens/${batch.join(',')}`, { timeout: 10000 })
        );

        const allPairs = pairResp.data?.pairs ?? [];

        for (const pair of allPairs) {
          const tokenAddr = pair.baseToken?.address;
          if (!tokenAddr) continue;
          if (parseFloat(pair.liquidity?.usd ?? '0') < minLiquidity) continue;

          // Skip duplicates
          if (tokens.find(t => t.mint === tokenAddr)) continue;

          const parsed = parseDexScreenerPair(pair, tokenAddr, minLiquidity, btcChange);
          if (parsed) tokens.push(parsed);
        }

        // Rate limit between batches
        if (i + batchSize < addresses.length) await sleep(1000);
      } catch {
        continue;
      }
    }
  } catch (err) {
    log.error('DexScreener fetch failed', { error: (err as Error).message });
  }

  // Also fetch from Birdeye new listings
  try {
    const birdResp = await axios.get(
      'https://public-api.birdeye.so/defi/tokenlist?sort_by=created_at&sort_type=desc&offset=0&limit=50',
      {
        headers: { 'x-chain': 'solana' },
        timeout: 10000,
      }
    );

    const birdTokens = birdResp.data?.data?.tokens ?? [];
    for (const bt of birdTokens) {
      if (tokens.some(t => t.mint === bt.address)) continue;

      const ageHours = 24; // approximate since birdeye doesn't give exact creation time here
      const ageCat = classifyAge(ageHours);
      const isXs = XSTOCK_MINT_SET.has(bt.address);

      tokens.push({
        mint: bt.address,
        symbol: bt.symbol ?? 'BIRD',
        name: bt.name ?? 'Unknown',
        createdAt: Date.now() - 86400000,
        launchPriceUsd: bt.price ?? 0,
        peakPriceUsd: bt.price ?? 0,
        currentPriceUsd: bt.price ?? 0,
        price5min: bt.price ?? 0,
        price15min: bt.price ?? 0,
        price1h: bt.price ?? 0,
        price4h: bt.price ?? 0,
        price24h: bt.price ?? 0,
        liquidityUsd: bt.liquidity ?? 0,
        volumeUsd24h: bt.v24hUSD ?? 0,
        holderCount: 30,
        buyCount1h: 0,
        sellCount1h: 0,
        wasRug: false,
        ruggedAtPct: 0,
        maxMultiple: 1,
        source: 'raydium',
        // Enhanced fields
        ageHours,
        ageCategory: ageCat,
        volumeSurgeRatio: 1,
        avgDailyVolume: bt.v24hUSD ?? 0,
        isVolumeSurge: false,
        marketCapUsd: (bt.price ?? 0) * 1_000_000_000,
        mcapLiqRatio: bt.liquidity ? ((bt.price ?? 0) * 1_000_000_000) / bt.liquidity : 0,
        isEstablished: false,
        isVeteran: false,
        isBlueChip: false,
        isXStock: isXs,
        xStockCategory: isXs ? XSTOCK_BY_MINT.get(bt.address)?.category as 'XSTOCK' | 'PRESTOCK' | 'INDEX' | 'COMMODITY' | undefined : undefined,
        btcCorrelation: 0,
        priceTrajectory: 'consolidating',
      });
    }
  } catch {
    log.warn('Birdeye fetch failed');
  }

  // Fetch from DexScreener token profiles (more recent tokens)
  await fetchDexScreenerProfiles(tokens, minLiquidity, btcChange);

  // Fetch from DexScreener search (recent Solana pairs)
  await fetchDexScreenerSearch(tokens, minLiquidity, btcChange);

  // Fetch trending Solana pairs for high-activity tokens
  await fetchDexScreenerTrending(tokens, minLiquidity, btcChange);

  // Fetch newest Solana pairs for fresh data
  await fetchDexScreenerNewPairs(tokens, minLiquidity, btcChange);

  // Fetch from Jupiter verified token list
  await fetchJupiterTokens(tokens, minLiquidity, btcChange);

  // ─── Deep fetch: additional sources for 5000+ tokens ──────
  if (deepFetch) {
    log.info('Deep fetch enabled - fetching from additional sources...');

    await fetchEstablishedTokens(tokens, minLiquidity, btcChange);
    await sleep(1000);

    await fetchVeteranSurgeTokens(tokens, minLiquidity, btcChange);
    await sleep(1000);

    await fetchXStocksTokens(tokens, minLiquidity, btcChange);
    await sleep(1000);

    await fetchBagsGraduations(tokens, minLiquidity, btcChange);
    await sleep(1000);

    // Also fetch blue chip tokens
    await fetchBlueChipTokens(tokens, minLiquidity, btcChange);
    await sleep(1000);

    // Fetch multi-timeframe data for a sample of tokens (expensive, do for top tokens)
    const topTokens = tokens
      .sort((a, b) => b.volumeUsd24h - a.volumeUsd24h)
      .slice(0, 200);
    await fetchMultiTimeframeData(topTokens);
  }

  log.info('Historical data fetched', {
    total: tokens.length,
    pumpfun: tokens.filter(t => t.source === 'pumpfun').length,
    raydium: tokens.filter(t => t.source === 'raydium').length,
    pumpswap: tokens.filter(t => t.source === 'pumpswap').length,
    xstocks: tokens.filter(t => t.isXStock).length,
    blueChips: tokens.filter(t => t.isBlueChip).length,
    established: tokens.filter(t => t.isEstablished).length,
    veterans: tokens.filter(t => t.isVeteran).length,
    volumeSurges: tokens.filter(t => t.isVolumeSurge).length,
    rugs: tokens.filter(t => t.wasRug).length,
    deepFetch,
  });

  return tokens;
}

// ─── Additional data sources ─────────────────────────────────

async function fetchDexScreenerProfiles(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  try {
    const resp = await axios.get(
      'https://api.dexscreener.com/token-profiles/latest/v1',
      { timeout: 10000 }
    );

    const profiles = (resp.data ?? [])
      .filter((p: { chainId: string }) => p.chainId === 'solana')
      .slice(0, 50);

    for (const profile of profiles) {
      if (tokens.some(t => t.mint === profile.tokenAddress)) continue;

      try {
        const pairResp = await axios.get(
          `https://api.dexscreener.com/latest/dex/tokens/${profile.tokenAddress}`,
          { timeout: 5000 }
        );

        const pair = pairResp.data?.pairs?.[0];
        if (!pair) continue;

        const token = parseDexScreenerPair(pair, profile.tokenAddress, minLiquidity, btcChange);
        if (token) tokens.push(token);

        await sleep(200);
      } catch { continue; }
    }
  } catch {
    log.warn('DexScreener profiles fetch failed');
  }
}

async function fetchDexScreenerSearch(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  // Search multiple keywords to get diverse token set
  const keywords = ['solana meme', 'pump fun', 'new solana', 'pumpswap', 'solana token 2026'];

  for (const keyword of keywords) {
    try {
      const resp = await axios.get(
        `https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(keyword)}`,
        { timeout: 10000 }
      );

      const pairs = (resp.data?.pairs ?? [])
        .filter((p: { chainId: string }) => p.chainId === 'solana')
        .slice(0, 20);

      for (const pair of pairs) {
        const mint = pair.baseToken?.address;
        if (!mint || tokens.some(t => t.mint === mint)) continue;

        const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
        if (token) tokens.push(token);
      }

      await sleep(300);
    } catch { continue; }
  }
}

async function fetchJupiterTokens(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  try {
    // Jupiter strict verified tokens
    const resp = await axios.get(
      'https://tokens.jup.ag/tokens?tags=verified',
      { timeout: 10000 }
    );

    const jupTokens = (resp.data ?? []).slice(0, 100);

    for (const jt of jupTokens) {
      if (tokens.some(t => t.mint === jt.address)) continue;
      if (!jt.address) continue;

      try {
        const pairResp = await axios.get(
          `https://api.dexscreener.com/latest/dex/tokens/${jt.address}`,
          { timeout: 5000 }
        );

        const pair = pairResp.data?.pairs?.[0];
        if (!pair) continue;

        const token = parseDexScreenerPair(pair, jt.address, minLiquidity, btcChange);
        if (token) tokens.push(token);

        await sleep(200);
      } catch { continue; }
    }
  } catch {
    log.warn('Jupiter token list fetch failed');
  }
}

async function fetchDexScreenerTrending(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  try {
    // DexScreener top boosted tokens (most promoted)
    const resp = await fetchWithRetry(() =>
      axios.get('https://api.dexscreener.com/token-boosts/top/v1', { timeout: 10000 })
    );

    const boosts = (resp.data ?? [])
      .filter((b: { chainId: string }) => b.chainId === 'solana')
      .slice(0, 60);

    const addresses = boosts
      .map((b: { tokenAddress: string }) => b.tokenAddress)
      .filter((a: string) => !tokens.some(t => t.mint === a));

    // Batch fetch
    const batchSize = 30;
    for (let i = 0; i < addresses.length; i += batchSize) {
      const batch = addresses.slice(i, i + batchSize);
      if (batch.length === 0) continue;

      try {
        const pairResp = await fetchWithRetry(() =>
          axios.get(`https://api.dexscreener.com/latest/dex/tokens/${batch.join(',')}`, { timeout: 10000 })
        );

        for (const pair of pairResp.data?.pairs ?? []) {
          const mint = pair.baseToken?.address;
          if (!mint || tokens.some(t => t.mint === mint)) continue;
          const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
          if (token) tokens.push(token);
        }

        if (i + batchSize < addresses.length) await sleep(500);
      } catch { continue; }
    }
  } catch {
    log.warn('DexScreener trending fetch failed');
  }
}

async function fetchDexScreenerNewPairs(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  // Fetch newest pairs across multiple Solana DEXes
  const dexes = ['pumpswap', 'raydium'];

  for (const dex of dexes) {
    try {
      const resp = await fetchWithRetry(() =>
        axios.get(`https://api.dexscreener.com/latest/dex/pairs/solana?sort=pairAge&order=asc`, { timeout: 10000 })
      );

      const pairs = (resp.data?.pairs ?? []).slice(0, 30);

      for (const pair of pairs) {
        const mint = pair.baseToken?.address;
        if (!mint || tokens.some(t => t.mint === mint)) continue;
        const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
        if (token) tokens.push(token);
      }

      await sleep(500);
    } catch { continue; }
  }

  // Also search for recently created tokens with specific patterns
  const trendingSearches = ['dog', 'cat', 'ai agent', 'trump', 'pepe'];
  for (const term of trendingSearches) {
    try {
      const resp = await fetchWithRetry(() =>
        axios.get(`https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(term)}`, { timeout: 8000 })
      );

      const pairs = (resp.data?.pairs ?? [])
        .filter((p: { chainId: string }) => p.chainId === 'solana')
        .slice(0, 10);

      for (const pair of pairs) {
        const mint = pair.baseToken?.address;
        if (!mint || tokens.some(t => t.mint === mint)) continue;
        const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
        if (token) tokens.push(token);
      }

      await sleep(300);
    } catch { continue; }
  }
}

// ─── NEW: Established token fetcher ──────────────────────────
// Fetch tokens >7 days old with high volume from DexScreener search
async function fetchEstablishedTokens(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  const categories = [
    'established solana',
    'solana defi',
    'solana memecoin',
    'raydium',
    'solana token',
    'solana ecosystem',
    'solana nft',
    'jupiter solana',
    'orca solana',
    'marinade solana',
    'jito solana',
    'bonk solana',
    'wif solana',
    'solana gaming',
    'solana ai',
  ];

  log.info('Fetching established tokens...', { categories: categories.length });

  for (const category of categories) {
    try {
      const resp = await fetchWithRetry(() =>
        axios.get(
          `https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(category)}`,
          { timeout: 10000 }
        )
      );

      const pairs = (resp.data?.pairs ?? [])
        .filter((p: Record<string, unknown>) => {
          if ((p.chainId as string) !== 'solana') return false;
          // Filter for tokens with meaningful volume
          const vol = p.volume as Record<string, string> | undefined;
          const vol24h = parseFloat(vol?.h24 ?? '0');
          return vol24h > 10000;
        })
        .slice(0, 40);

      for (const pair of pairs) {
        const mint = pair.baseToken?.address;
        if (!mint || tokens.some(t => t.mint === mint)) continue;

        const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
        if (token) tokens.push(token);
      }

      await sleep(500);
    } catch {
      log.warn(`Established token fetch failed for: ${category}`);
      continue;
    }
  }

  log.info('Established tokens fetched', {
    established: tokens.filter(t => t.isEstablished).length,
    veterans: tokens.filter(t => t.isVeteran).length,
  });
}

// ─── NEW: Veteran surge token fetcher ────────────────────────
// Look for tokens >30d old with volume spikes (volume_24h > 3x baseline)
async function fetchVeteranSurgeTokens(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  log.info('Fetching veteran surge tokens...');

  // Strategy: fetch trending/top tokens, filter for old ones with volume spikes
  try {
    // 1. DexScreener top boosted (high activity)
    const boostResp = await fetchWithRetry(() =>
      axios.get('https://api.dexscreener.com/token-boosts/top/v1', { timeout: 10000 })
    );
    const topBoosts = (boostResp.data ?? [])
      .filter((b: { chainId: string }) => b.chainId === 'solana')
      .slice(0, 100);

    const newAddresses = topBoosts
      .map((b: { tokenAddress: string }) => b.tokenAddress)
      .filter((a: string) => !tokens.some(t => t.mint === a));

    // Batch fetch pair data
    const batchSize = 30;
    for (let i = 0; i < newAddresses.length; i += batchSize) {
      const batch = newAddresses.slice(i, i + batchSize);
      if (batch.length === 0) continue;

      try {
        const pairResp = await fetchWithRetry(() =>
          axios.get(`https://api.dexscreener.com/latest/dex/tokens/${batch.join(',')}`, { timeout: 10000 })
        );

        for (const pair of pairResp.data?.pairs ?? []) {
          const mint = pair.baseToken?.address;
          if (!mint || tokens.some(t => t.mint === mint)) continue;

          // Only interested in tokens with creation date >30 days ago
          const createdAt = pair.pairCreatedAt as number | undefined;
          if (createdAt) {
            const ageHours = (Date.now() - createdAt) / (1000 * 60 * 60);
            if (ageHours < 30 * 24) continue; // skip if < 30 days old
          }

          const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
          if (token && token.isVolumeSurge) {
            tokens.push(token);
          }
        }

        if (i + batchSize < newAddresses.length) await sleep(500);
      } catch { continue; }
    }

    await sleep(1000);

    // 2. Search for well-known Solana DeFi tokens that might be surging
    const defiSearches = [
      'raydium RAY', 'jupiter JUP', 'marinade MNDE', 'orca ORCA',
      'jito JTO', 'bonk BONK', 'dogwifhat WIF', 'render RNDR',
      'pyth PYTH', 'helium HNT', 'tensor TNSR', 'drift DRIFT',
      'parcl PRCL', 'kamino KMNO', 'sanctum CLOUD', 'popcat',
      'mew MEW', 'bome BOME', 'slerf SLERF', 'wen WEN',
    ];

    for (const search of defiSearches) {
      try {
        const resp = await fetchWithRetry(() =>
          axios.get(`https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(search)}`, { timeout: 8000 })
        );

        const pairs = (resp.data?.pairs ?? [])
          .filter((p: Record<string, unknown>) => (p.chainId as string) === 'solana')
          .slice(0, 5);

        for (const pair of pairs) {
          const mint = pair.baseToken?.address;
          if (!mint || tokens.some(t => t.mint === mint)) continue;

          const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
          if (token) tokens.push(token);
        }

        await sleep(300);
      } catch { continue; }
    }
  } catch {
    log.warn('Veteran surge token fetch failed');
  }

  log.info('Veteran surge tokens fetched', {
    surges: tokens.filter(t => t.isVolumeSurge && t.ageHours > 30 * 24).length,
  });
}

// ─── NEW: xStocks token fetcher ──────────────────────────────
// Fetch data for all tokenized equities/indexes/prestocks
async function fetchXStocksTokens(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  log.info('Fetching xStocks tokens...', { total: XSTOCK_MINTS.length });

  // Filter out mints we already have
  const missingMints = XSTOCK_MINTS.filter(x => !tokens.some(t => t.mint === x.mint));

  // Batch fetch from DexScreener
  const batchSize = 30;
  for (let i = 0; i < missingMints.length; i += batchSize) {
    const batch = missingMints.slice(i, i + batchSize);
    const addresses = batch.map(x => x.mint);

    try {
      const pairResp = await fetchWithRetry(() =>
        axios.get(`https://api.dexscreener.com/latest/dex/tokens/${addresses.join(',')}`, { timeout: 10000 })
      );

      const pairsByMint = new Map<string, Record<string, unknown>>();
      for (const pair of pairResp.data?.pairs ?? []) {
        const mint = pair.baseToken?.address as string;
        if (mint && !pairsByMint.has(mint)) {
          pairsByMint.set(mint, pair);
        }
      }

      for (const xs of batch) {
        if (tokens.some(t => t.mint === xs.mint)) continue;

        const pair = pairsByMint.get(xs.mint);
        if (pair) {
          const token = parseDexScreenerPair(pair, xs.mint, 0, btcChange); // no min liquidity for xstocks
          if (token) {
            // Override fields for xStocks
            token.isXStock = true;
            token.xStockCategory = xs.category as 'XSTOCK' | 'PRESTOCK' | 'INDEX' | 'COMMODITY';
            token.symbol = xs.ticker;
            token.name = xs.name;
            token.ageCategory = 'veteran'; // xStocks are always veteran-class
            token.isVeteran = true;
            tokens.push(token);
          }
        } else {
          // No pair data from DexScreener - create a placeholder entry
          tokens.push({
            mint: xs.mint,
            symbol: xs.ticker,
            name: xs.name,
            createdAt: Date.now() - 180 * 24 * 60 * 60 * 1000, // assume 180 days
            launchPriceUsd: 0,
            peakPriceUsd: 0,
            currentPriceUsd: 0,
            price5min: 0,
            price15min: 0,
            price1h: 0,
            price4h: 0,
            price24h: 0,
            liquidityUsd: 0,
            volumeUsd24h: 0,
            holderCount: 50,
            buyCount1h: 0,
            sellCount1h: 0,
            wasRug: false,
            ruggedAtPct: 0,
            maxMultiple: 1,
            source: 'raydium',
            ageHours: 180 * 24,
            ageCategory: 'veteran',
            volumeSurgeRatio: 1,
            avgDailyVolume: 0,
            isVolumeSurge: false,
            marketCapUsd: 0,
            mcapLiqRatio: 0,
            isEstablished: true,
            isVeteran: true,
            isBlueChip: xs.category === 'INDEX' || xs.category === 'XSTOCK',
            isXStock: true,
            xStockCategory: xs.category as 'XSTOCK' | 'PRESTOCK' | 'INDEX' | 'COMMODITY',
            btcCorrelation: 0.3, // xStocks generally correlate with macro
            priceTrajectory: 'consolidating',
          });
        }
      }

      if (i + batchSize < missingMints.length) await sleep(500);
    } catch {
      log.warn(`xStocks batch fetch failed at index ${i}`);
      continue;
    }
  }

  log.info('xStocks tokens fetched', {
    xstocks: tokens.filter(t => t.isXStock).length,
  });
}

// ─── NEW: Blue Chip token fetcher ────────────────────────────
// Fetch data for major Solana ecosystem tokens with >1yr history
async function fetchBlueChipTokens(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  log.info('Fetching blue chip tokens...', { total: BLUE_CHIP_MINTS.length });

  // Filter out mints we already have
  const missingMints = BLUE_CHIP_MINTS.filter(b => !tokens.some(t => t.mint === b.mint));

  // Batch fetch from DexScreener (up to 30 per request)
  const batchSize = 30;
  for (let i = 0; i < missingMints.length; i += batchSize) {
    const batch = missingMints.slice(i, i + batchSize);
    const addresses = batch.map(b => b.mint);

    try {
      const pairResp = await fetchWithRetry(() =>
        axios.get(`https://api.dexscreener.com/tokens/v1/solana/${addresses.join(',')}`, {
          headers: { Accept: 'application/json' },
          timeout: 15000,
        })
      );

      const pairs: any[] = Array.isArray(pairResp.data) ? pairResp.data : [];

      // Group by base token, pick highest liquidity pair
      const bestPairs = new Map<string, any>();
      for (const pair of pairs) {
        const mintAddr = pair?.baseToken?.address;
        if (!mintAddr) continue;
        const liq = parseFloat(pair?.liquidity?.usd || '0');
        const existing = bestPairs.get(mintAddr);
        if (!existing || liq > (existing._liq || 0)) {
          bestPairs.set(mintAddr, { ...pair, _liq: liq });
        }
      }

      for (const [mint, pair] of bestPairs) {
        if (tokens.some(t => t.mint === mint)) continue;
        const info = BLUE_CHIP_MINTS.find(b => b.mint === mint);
        const token = parseDexScreenerPair(pair, mint, 0, btcChange); // no min liquidity for blue chips
        if (token) {
          token.isBlueChip = true;
          token.ageCategory = 'veteran'; // all blue chips are veteran by definition
          token.isVeteran = true;
          token.isEstablished = true;
          if (info) {
            token.symbol = info.ticker;
            token.name = info.name;
          }
          tokens.push(token);
        }
      }

      if (i + batchSize < missingMints.length) await sleep(500);
    } catch {
      log.warn(`Blue chip batch fetch failed at index ${i}`);
      continue;
    }
  }

  log.info('Blue chip tokens fetched', {
    blueChips: tokens.filter(t => t.isBlueChip).length,
  });
}

// ─── NEW: Bags.fm graduation fetcher ─────────────────────────
// Fetch recently graduated tokens from pumpswap DEX via DexScreener
async function fetchBagsGraduations(
  tokens: PumpFunHistoricalToken[],
  minLiquidity: number,
  btcChange: number,
): Promise<void> {
  log.info('Fetching Bags.fm graduations (via pumpswap pairs)...');

  try {
    // Strategy: search for pumpswap pairs which are graduated pump.fun tokens
    const searchTerms = [
      'pumpswap',
      'graduated',
      'pump graduation',
    ];

    for (const term of searchTerms) {
      try {
        const resp = await fetchWithRetry(() =>
          axios.get(`https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(term)}`, { timeout: 10000 })
        );

        const pairs = (resp.data?.pairs ?? [])
          .filter((p: Record<string, unknown>) => {
            if ((p.chainId as string) !== 'solana') return false;
            const dexId = ((p.dexId as string) ?? '').toLowerCase();
            return dexId.includes('pumpswap') || dexId.includes('pump');
          })
          .slice(0, 50);

        for (const pair of pairs) {
          const mint = pair.baseToken?.address;
          if (!mint || tokens.some(t => t.mint === mint)) continue;

          const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
          if (token) {
            token.source = 'pumpswap';
            tokens.push(token);
          }
        }

        await sleep(500);
      } catch { continue; }
    }

    // Also fetch recent Solana pairs sorted by newest, filtering for pumpswap
    try {
      const resp = await fetchWithRetry(() =>
        axios.get('https://api.dexscreener.com/latest/dex/pairs/solana?sort=pairAge&order=asc', { timeout: 10000 })
      );

      const pumpswapPairs = (resp.data?.pairs ?? [])
        .filter((p: Record<string, unknown>) => {
          const dexId = ((p.dexId as string) ?? '').toLowerCase();
          return dexId.includes('pumpswap');
        })
        .slice(0, 100);

      for (const pair of pumpswapPairs) {
        const mint = pair.baseToken?.address;
        if (!mint || tokens.some(t => t.mint === mint)) continue;

        const token = parseDexScreenerPair(pair, mint, minLiquidity, btcChange);
        if (token) {
          token.source = 'pumpswap';
          tokens.push(token);
        }
      }
    } catch {
      log.warn('Pumpswap new pairs fetch failed');
    }
  } catch {
    log.warn('Bags graduations fetch failed');
  }

  log.info('Bags graduations fetched', {
    pumpswap: tokens.filter(t => t.source === 'pumpswap').length,
  });
}

// ─── NEW: Multi-timeframe OHLCV data enrichment ─────────────
// For each token, try to get OHLCV data at multiple timeframes
// to build better price trajectories
async function fetchMultiTimeframeData(
  tokens: PumpFunHistoricalToken[],
): Promise<void> {
  log.info('Enriching multi-timeframe data...', { tokens: tokens.length });

  let enriched = 0;

  for (const token of tokens) {
    try {
      // DexScreener does not have a public OHLCV endpoint, but we can use
      // the pair's priceChange data at different timeframes.
      // For richer data, we query Jupiter price API for the token.
      const priceResp = await axios.get(
        `https://api.jup.ag/price/v2?ids=${token.mint}`,
        { timeout: 5000 }
      );

      const priceData = priceResp.data?.data?.[token.mint];
      if (priceData?.price) {
        const jupPrice = parseFloat(priceData.price);
        if (jupPrice > 0 && token.currentPriceUsd > 0) {
          // Update current price with Jupiter's more accurate price
          token.currentPriceUsd = jupPrice;

          // Recalculate trajectory with updated price
          const h1Diff = ((jupPrice - token.price1h) / Math.max(token.price1h, 0.0000001)) * 100;
          const h24Diff = ((jupPrice - token.price24h) / Math.max(token.price24h, 0.0000001)) * 100;

          if (h1Diff > 10 && h24Diff > 5) token.priceTrajectory = 'pumping';
          else if (h1Diff < -10 && h24Diff < -5) token.priceTrajectory = 'dumping';
          else if (h24Diff < -5 && h1Diff > 3) token.priceTrajectory = 'recovering';
          else token.priceTrajectory = 'consolidating';

          enriched++;
        }
      }

      // Rate limit: only check every 100ms for Jupiter
      await sleep(100);
    } catch {
      // Non-critical, continue
      continue;
    }
  }

  log.info('Multi-timeframe enrichment complete', { enriched, total: tokens.length });
}

// ─── Enhanced parseDexScreenerPair ───────────────────────────
function parseDexScreenerPair(
  pair: Record<string, unknown>,
  mint: string,
  minLiquidity: number,
  btcChange: number = 0,
): PumpFunHistoricalToken | null {
  const priceUsd = parseFloat((pair.priceUsd as string) ?? '0');
  const liq = pair.liquidity as Record<string, string> | undefined;
  const liquidity = parseFloat(liq?.usd ?? '0');
  if (liquidity < minLiquidity || priceUsd === 0) return null;

  const pc = pair.priceChange as Record<string, number> | undefined;
  const h1Change = pc?.h1 ?? 0;
  const h6Change = pc?.h6 ?? 0;
  const h24Change = pc?.h24 ?? 0;
  const vol = pair.volume as Record<string, string> | undefined;
  const volume = parseFloat(vol?.h24 ?? '0');
  const txns = pair.txns as Record<string, Record<string, number>> | undefined;
  const buys = txns?.h1?.buys ?? 0;
  const sells = txns?.h1?.sells ?? 0;

  const price1h = h1Change !== 0 ? priceUsd / (1 + h1Change / 100) : priceUsd;
  const price4h = h6Change !== 0 ? priceUsd / (1 + h6Change / 200) : priceUsd;
  const price24h = h24Change !== 0 ? priceUsd / (1 + h24Change / 100) : priceUsd;
  const launchPrice = Math.max(0.0000001, price24h * 0.5);
  const peakPrice = priceUsd * Math.max(1, 1 + Math.max(h1Change, h6Change, h24Change) / 100);

  const currentDrop = ((peakPrice - priceUsd) / peakPrice) * 100;

  let source: 'pumpfun' | 'raydium' | 'pumpswap' = 'raydium';
  const dexId = ((pair.dexId as string) ?? '').toLowerCase();
  if (dexId.includes('pumpswap')) source = 'pumpswap';
  else if (dexId.includes('pump')) source = 'pumpfun';

  const bt = pair.baseToken as Record<string, string> | undefined;

  // ─── Compute enhanced fields ──────────────────────────
  const createdAt = (pair.pairCreatedAt as number) ?? Date.now();
  const ageHours = Math.max(0, (Date.now() - createdAt) / (1000 * 60 * 60));
  const ageCategory = classifyAge(ageHours);

  // Volume surge: use volume vs liquidity as baseline proxy
  // A healthy token has vol/liq ratio of about 1-3. Anything >3x baseline = surge.
  const baselineVolume = liquidity * 1.5; // assume baseline daily vol ~ 1.5x liquidity
  const volumeSurgeRatio = baselineVolume > 0 ? volume / baselineVolume : 1;
  const isVolumeSurge = volumeSurgeRatio > 3;

  // Market cap: use FDV if available, else estimate from price * assumed supply
  const fdv = pair.fdv as number | undefined;
  const marketCapUsd = fdv && fdv > 0 ? fdv : priceUsd * 1_000_000_000;
  const mcapLiqRatio = liquidity > 0 ? marketCapUsd / liquidity : 0;

  // Classification flags
  const isXStock = XSTOCK_MINT_SET.has(mint);
  const isEstablished = ageHours > 7 * 24 && liquidity > 50000;
  const isVeteran = ageHours > 90 * 24 && liquidity > 100000;
  const isBlueChip = BLUE_CHIP_MINT_SET.has(mint) || (ageHours > 180 * 24 && liquidity > 500000);

  // BTC correlation estimate
  const btcCorrelation = estimateBtcCorrelation(h24Change, btcChange);

  // Price trajectory
  const priceTrajectory = classifyTrajectory(h1Change, h6Change, h24Change);

  return {
    mint,
    symbol: bt?.symbol ?? 'UNKNOWN',
    name: bt?.name ?? 'Unknown',
    createdAt,
    launchPriceUsd: launchPrice,
    peakPriceUsd: peakPrice,
    currentPriceUsd: priceUsd,
    price5min: priceUsd * 0.98,
    price15min: priceUsd * 0.95,
    price1h,
    price4h,
    price24h,
    liquidityUsd: liquidity,
    volumeUsd24h: volume,
    holderCount: Math.max(20, Math.floor(liquidity / 1000)),
    buyCount1h: buys,
    sellCount1h: sells,
    wasRug: currentDrop > 90 || liquidity < 1000,
    ruggedAtPct: currentDrop,
    maxMultiple: peakPrice / launchPrice,
    source,
    // Enhanced fields
    ageHours,
    ageCategory,
    volumeSurgeRatio,
    avgDailyVolume: baselineVolume,
    isVolumeSurge,
    marketCapUsd,
    mcapLiqRatio,
    isEstablished,
    isVeteran,
    isBlueChip,
    isXStock,
    xStockCategory: isXStock ? XSTOCK_BY_MINT.get(mint)?.category as 'XSTOCK' | 'PRESTOCK' | 'INDEX' | 'COMMODITY' | undefined : undefined,
    btcCorrelation,
    priceTrajectory,
  };
}

// ─── Enhanced backtesting with real pump.fun data ────────────
export interface EnhancedBacktestConfig {
  initialCapitalUsd: number;
  maxPositionUsd: number;
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number; // Trailing stop after first TP hit
  minLiquidityUsd: number;
  minBuySellRatio: number; // minimum buy/sell ratio in 1h
  maxEntryDelayMs: number; // max time after launch to enter
  safetyScoreMin: number;
  maxConcurrentPositions: number;
  partialExitPct: number; // sell this % at first TP
  source: 'all' | 'pumpfun' | 'raydium' | 'pumpswap';

  // ─── Enhanced config fields ──────────────────────────
  // Age-based filters
  minTokenAgeHours: number;      // 0 = no minimum
  maxTokenAgeHours: number;      // 0 = no maximum
  ageCategory: 'all' | 'fresh' | 'young' | 'established' | 'veteran';
  // Volume surge
  requireVolumeSurge: boolean;
  minVolumeSurgeRatio: number;
  // Asset type
  assetType: 'all' | 'memecoin' | 'xstock' | 'bluechip' | 'prestock' | 'index' | 'commodity';
  // Adaptive exits based on age
  adaptiveExits: boolean;
  // Macro regime filter (for regime-conditioned strategy testing)
  macroRegime?: 'risk_on' | 'risk_off' | 'neutral' | 'all';
  // OHLCV candle data: use fine-grained 5-min candles from GeckoTerminal
  // when available (144 checkpoints vs 5 coarse ones). Disabled by default
  // in massive backtest for speed (adds 50+ API calls and ~2 min per run).
  useOhlcv?: boolean;
  // Time-of-day entry filter: only enter positions during these UTC hours
  // Empty array or undefined = no filter (all hours allowed)
  allowedEntryHoursUtc?: number[];
  // Profit-taking ladder: configurable multi-level exits
  // Each level defines when to sell (% of TP target) and how much (% of remaining position)
  // When undefined, uses DEFAULT_PROFIT_LADDER
  profitLadder?: Array<{triggerPctOfTp: number; sellPctOfRemaining: number}>;
}

// Default profit-taking ladder: 4 levels that progressively take profit
// Remaining ~23% rides trailing stop for maximum upside capture
export const DEFAULT_PROFIT_LADDER: Array<{triggerPctOfTp: number; sellPctOfRemaining: number}> = [
  { triggerPctOfTp: 0.3, sellPctOfRemaining: 0.15 },   // At 30% of TP, sell 15%
  { triggerPctOfTp: 0.5, sellPctOfRemaining: 0.20 },   // At 50% of TP, sell 20%
  { triggerPctOfTp: 0.75, sellPctOfRemaining: 0.30 },  // At 75% of TP, sell 30%
  { triggerPctOfTp: 1.0, sellPctOfRemaining: 0.50 },   // At full TP, sell 50%
];

// Aggressive ladder: fewer levels, keeps more riding for upside
// Remaining ~58% rides trailing stop -- more upside capture
export const AGGRESSIVE_PROFIT_LADDER: Array<{triggerPctOfTp: number; sellPctOfRemaining: number}> = [
  { triggerPctOfTp: 0.25, sellPctOfRemaining: 0.10 },
  { triggerPctOfTp: 0.50, sellPctOfRemaining: 0.20 },
  { triggerPctOfTp: 1.0, sellPctOfRemaining: 0.40 },
];

export interface EnhancedBacktestResult {
  config: EnhancedBacktestConfig;
  totalTokensAnalyzed: number;
  tokensPassedFilter: number;
  totalTrades: number;
  wins: number;
  losses: number;
  winRate: number;
  totalPnlUsd: number;
  totalPnlPct: number;
  maxDrawdownPct: number;
  sharpeRatio: number;
  profitFactor: number;
  avgWinPct: number;
  avgLossPct: number;
  expectancy: number; // average P&L per trade
  rugsAvoided: number;
  rugsHit: number;
  bestTrade: { symbol: string; pnlPct: number };
  worstTrade: { symbol: string; pnlPct: number };
  avgHoldTimeMin: number;
  trades: Array<{
    symbol: string;
    source: string;
    entryPrice: number;
    exitPrice: number;
    pnlPct: number;
    pnlUsd: number;
    exitReason: string;
    holdTimeMin: number;
    safetyScore: number;
  }>;
}

// ─── Enhanced checkpoint interpolation ─────────────────────────
// Generates intermediate price points between known checkpoints
// to model intra-period volatility more accurately. Without this,
// the backtester only checks SL/TP at 4-5 coarse time steps,
// missing triggers that would fire between checkpoints.
export function enhanceCheckpoints(
  checkpoints: Array<{ price: number; timeMin: number }>,
): Array<{ price: number; timeMin: number }> {
  if (checkpoints.length <= 1) return [...checkpoints];

  const enhanced: Array<{ price: number; timeMin: number }> = [];

  for (let idx = 0; idx < checkpoints.length; idx++) {
    const cp = checkpoints[idx];
    enhanced.push({ ...cp });

    // Add interpolated points between this and next checkpoint
    if (idx < checkpoints.length - 1) {
      const nextCp = checkpoints[idx + 1];
      const timeDelta = nextCp.timeMin - cp.timeMin;
      const priceDelta = nextCp.price - cp.price;

      // Estimate volatility from the move magnitude
      const movePercent = Math.abs(priceDelta / cp.price) * 100;

      // For volatile moves (>5%), add a mid-point overshoot
      // Price tends to overshoot in both directions before settling:
      // - Rising price dips before continuing up
      // - Falling price bounces before continuing down
      // Both cases mean the mid-point is CLOSER to the start than linear interpolation
      if (movePercent > 5) {
        const midTime = cp.timeMin + timeDelta * 0.4;
        const overshootMagnitude = 0.3 * Math.min(1, movePercent / 20);
        const midPrice = cp.price + priceDelta * (0.4 - overshootMagnitude);
        enhanced.push({ price: Math.max(0.0000001, midPrice), timeMin: midTime });
      }

      // For any significant move (>2%), add a 70% interpolation point
      if (movePercent > 2) {
        const lateTime = cp.timeMin + timeDelta * 0.7;
        const latePrice = cp.price + priceDelta * 0.7;
        enhanced.push({ price: Math.max(0.0000001, latePrice), timeMin: lateTime });
      }
    }
  }

  // Sort by time to ensure chronological order
  enhanced.sort((a, b) => a.timeMin - b.timeMin);

  return enhanced;
}

// ─── Adaptive exit parameters by age/type ────────────────────
interface AdaptiveExitParams {
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
}

function getAdaptiveExits(token: PumpFunHistoricalToken): AdaptiveExitParams {
  // xStocks: sub-category-aware exits for tokenized assets
  if (token.isXStock) {
    switch (token.xStockCategory) {
      case 'INDEX':
        return { stopLossPct: 2, takeProfitPct: 5, trailingStopPct: 1.5 };
      case 'COMMODITY':
        return { stopLossPct: 4, takeProfitPct: 12, trailingStopPct: 3 };
      case 'PRESTOCK':
        return { stopLossPct: 15, takeProfitPct: 50, trailingStopPct: 8 };
      default: // XSTOCK (equities) — tokenized equities move 1-3%/day
        return { stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2 };
    }
  }

  // Blue chips: wide stops, conservative targets, low risk
  if (token.isBlueChip) {
    return { stopLossPct: 10, takeProfitPct: 35, trailingStopPct: 12 };
  }

  switch (token.ageCategory) {
    case 'fresh':   // <24h: high volatility expected
      return { stopLossPct: 25, takeProfitPct: 100, trailingStopPct: 10 };
    case 'young':   // <7d
      return { stopLossPct: 20, takeProfitPct: 75, trailingStopPct: 8 };
    case 'established': // 7-90d: wider trail, let them breathe
      return { stopLossPct: 15, takeProfitPct: 50, trailingStopPct: 12 };
    case 'veteran': // >90d: established slow movers, realistic targets
      return { stopLossPct: 8, takeProfitPct: 20, trailingStopPct: 6 };
    default:
      return { stopLossPct: 20, takeProfitPct: 75, trailingStopPct: 10 };
  }
}

// Pre-fetch data once for the optimizer to reuse across configs
// Uses TTL cache to avoid rate-limiting on rapid iterations
export async function fetchBacktestData(
  minLiquidity: number = 1000,
  deepFetch: boolean = false,
): Promise<PumpFunHistoricalToken[]> {
  // Try cache first
  const cached = readCache();
  if (cached) return cached.tokens;

  // Fresh fetch
  const tokens = await fetchDexScreenerPairs(minLiquidity, 200, deepFetch);
  if (tokens.length > 0) {
    writeCache(tokens);
  }
  return tokens;
}

// ─── Momentum entry slippage ─────────────────────────────────────
// Computes how much of the initial price move we've already missed
// by the time we detect + analyze + execute. If a token is already
// pumping hard at the 15-min mark, our realistic entry is later in
// the move and more expensive. Returns a slippage percentage.
export function computeEntrySlippage(token: { price15min: number; price5min: number }): number {
  const price15m = token.price15min;
  const detectPrice = token.price5min;

  if (price15m <= 0 || detectPrice <= 0) return 0;

  const moveBy15m = ((price15m - detectPrice) / detectPrice) * 100;

  // If token pumped >50% in first 15 min, we probably entered ~60% of the way through
  // If token pumped >20% in first 15 min, we probably entered ~40% of the way through
  // If token pumped >5%  in first 15 min, we caught ~20% of the pump
  // If token dumped >10%, we might have gotten a discount (negative slippage = bonus)
  if (moveBy15m > 50) return moveBy15m * 0.6;
  if (moveBy15m > 20) return moveBy15m * 0.4;
  if (moveBy15m > 5)  return moveBy15m * 0.2;
  if (moveBy15m < -10) return moveBy15m * 0.3;
  return 0; // Small moves: assume we entered at detection price
}

export async function runEnhancedBacktest(
  overrides?: Partial<EnhancedBacktestConfig>,
  cachedData?: PumpFunHistoricalToken[],
): Promise<EnhancedBacktestResult> {
  const cfg: EnhancedBacktestConfig = {
    initialCapitalUsd: 50,
    maxPositionUsd: 2.50,
    stopLossPct: 30,
    takeProfitPct: 100,
    trailingStopPct: 15,
    minLiquidityUsd: 10000,
    minBuySellRatio: 1.5,
    maxEntryDelayMs: 300000, // 5 min
    safetyScoreMin: 0.6,
    maxConcurrentPositions: 3,
    partialExitPct: 50,
    source: 'all',
    // Enhanced defaults
    minTokenAgeHours: 0,
    maxTokenAgeHours: 0,
    ageCategory: 'all',
    requireVolumeSurge: false,
    minVolumeSurgeRatio: 3,
    assetType: 'all',
    adaptiveExits: false,
    ...overrides,
  };

  // Fetch macro environment (cached, won't spam APIs)
  let macroSnapshot: MacroSnapshot | null = null;
  let hlCorrelations: HLCorrelationData | null = null;
  try {
    macroSnapshot = await getMacroSnapshot();
  } catch { /* macro data optional */ }
  try {
    hlCorrelations = await getHyperliquidCorrelations();
  } catch { /* HL data optional */ }

  // Macro regime filter: skip entire backtest if regime doesn't match
  if (cfg.macroRegime && cfg.macroRegime !== 'all' && macroSnapshot) {
    if (macroSnapshot.regime !== cfg.macroRegime) {
      log.info('Skipping backtest: macro regime mismatch', {
        wanted: cfg.macroRegime,
        actual: macroSnapshot.regime,
      });
      // Return empty result for regime mismatch
      return {
        config: cfg,
        totalTokensAnalyzed: 0,
        tokensPassedFilter: 0,
        totalTrades: 0,
        wins: 0,
        losses: 0,
        winRate: 0,
        totalPnlUsd: 0,
        totalPnlPct: 0,
        maxDrawdownPct: 0,
        sharpeRatio: 0,
        profitFactor: 0,
        avgWinPct: 0,
        avgLossPct: 0,
        expectancy: 0,
        rugsAvoided: 0,
        rugsHit: 0,
        bestTrade: { symbol: 'N/A', pnlPct: 0 },
        worstTrade: { symbol: 'N/A', pnlPct: 0 },
        avgHoldTimeMin: 0,
        trades: [],
      };
    }
  }

  // Use cached data if provided (optimizer), otherwise fetch fresh
  const historicalTokens = cachedData ?? await fetchDexScreenerPairs(cfg.minLiquidityUsd, 200);
  const filteredTokens = historicalTokens.filter(t => {
    if (cfg.source !== 'all' && t.source !== cfg.source) return false;
    if (t.liquidityUsd < cfg.minLiquidityUsd) return false;

    // Only apply ratio filter when txn data actually exists
    if (t.buyCount1h > 0 || t.sellCount1h > 0) {
      const ratio = t.buyCount1h / Math.max(1, t.sellCount1h);
      if (ratio < cfg.minBuySellRatio) return false;
    }

    // ─── Enhanced filters ──────────────────────────────
    // Age filters
    if (cfg.minTokenAgeHours > 0 && t.ageHours < cfg.minTokenAgeHours) return false;
    if (cfg.maxTokenAgeHours > 0 && t.ageHours > cfg.maxTokenAgeHours) return false;
    if (cfg.ageCategory !== 'all' && t.ageCategory !== cfg.ageCategory) return false;

    // Volume surge filter
    if (cfg.requireVolumeSurge && !t.isVolumeSurge) return false;
    if (cfg.requireVolumeSurge && t.volumeSurgeRatio < cfg.minVolumeSurgeRatio) return false;

    // Asset type filter (sub-category aware for tokenized assets)
    if (cfg.assetType === 'xstock' && t.xStockCategory !== 'XSTOCK') return false;
    if (cfg.assetType === 'prestock' && t.xStockCategory !== 'PRESTOCK') return false;
    if (cfg.assetType === 'index' && t.xStockCategory !== 'INDEX') return false;
    if (cfg.assetType === 'commodity' && t.xStockCategory !== 'COMMODITY') return false;
    if (cfg.assetType === 'memecoin' && (t.isXStock || t.isBlueChip)) return false;
    if (cfg.assetType === 'bluechip' && !t.isBlueChip) return false;

    return true;
  });

  // Optionally fetch OHLCV candle data for higher resolution simulation
  // Only fetch for filtered tokens (already passed all filters)
  let ohlcvData: Map<string, Array<{ price: number; timeMin: number }>> = new Map();
  if (cfg.useOhlcv === true) { // default to OFF — opt-in only (GeckoTerminal rate limits)
    try {
      ohlcvData = await fetchBatchOHLCV(
        filteredTokens.map(t => ({ mint: t.mint, createdAt: t.createdAt })),
        50, // max 50 tokens (rate limit)
      );
      log.info('OHLCV data fetched', { tokensWithOhlcv: ohlcvData.size, total: filteredTokens.length });
    } catch {
      log.warn('OHLCV fetch failed, using coarse checkpoints');
    }
  }

  const trades: EnhancedBacktestResult['trades'] = [];
  let capital = cfg.initialCapitalUsd;
  let peakCapital = capital;
  let maxDrawdown = 0;
  let openPositions = 0;
  const returns: number[] = [];

  for (const token of filteredTokens) {
    if (openPositions >= cfg.maxConcurrentPositions) continue;

    // Simulate safety check (with macro + HL correlation data)
    const safetyScore = simulateEnhancedSafety(token, macroSnapshot, hlCorrelations);
    if (safetyScore < cfg.safetyScoreMin) {
      continue;
    }

    // Time-of-day filter: skip tokens created outside allowed hours
    if (cfg.allowedEntryHoursUtc && cfg.allowedEntryHoursUtc.length > 0) {
      const creationHour = new Date(token.createdAt * 1000).getUTCHours();
      if (!cfg.allowedEntryHoursUtc.includes(creationHour)) {
        continue; // Skip this token
      }
    }

    if (token.wasRug && safetyScore >= cfg.safetyScoreMin) {
      // Safety missed this rug
      const rugMacroMultiplier = macroSnapshot?.memeExposureMultiplier ?? 1.0;
      const rugPositionUsd = cfg.maxPositionUsd * (token.isXStock ? 1.0 : rugMacroMultiplier);
      const pnlPct = -Math.min(90, token.ruggedAtPct);
      const pnlUsd = rugPositionUsd * (pnlPct / 100);
      capital += pnlUsd;

      trades.push({
        symbol: token.symbol,
        source: token.source,
        entryPrice: token.price5min,
        exitPrice: token.price5min * (1 + pnlPct / 100),
        pnlPct,
        pnlUsd,
        exitReason: 'RUG',
        holdTimeMin: 5,
        safetyScore,
      });
      continue;
    }

    openPositions++;
    const momentumSlippagePct = computeEntrySlippage(token);
    const entryPrice = token.price5min * (1 + momentumSlippagePct / 100) * 1.03; // momentum slippage + 3% swap slippage

    // Apply macro exposure multiplier to position sizing
    const macroMultiplier = macroSnapshot?.memeExposureMultiplier ?? 1.0;
    const adjustedPositionUsd = cfg.maxPositionUsd * (token.isXStock ? 1.0 : macroMultiplier);

    // Determine exit parameters: adaptive or fixed
    let activeSL: number;
    let activeTP: number;
    let activeTrail: number;

    if (cfg.adaptiveExits) {
      const adaptive = getAdaptiveExits(token);
      activeSL = adaptive.stopLossPct;
      activeTP = adaptive.takeProfitPct;
      activeTrail = adaptive.trailingStopPct;
    } else {
      activeSL = cfg.stopLossPct;
      activeTP = cfg.takeProfitPct;
      activeTrail = cfg.trailingStopPct;
    }

    // Simulate chronological price path using available price points
    // Order: entry -> 15min -> peak (est) -> 1h -> 4h
    // Check TP/SL at each time step in sequence
    let exitPrice: number = token.price4h * 0.98;
    let exitReason: string = 'TIME_EXIT';
    let holdTimeMin: number = 240;

    // Use OHLCV candle data if available (144 checkpoints vs 5 coarse ones)
    const ohlcvCheckpoints = ohlcvData.get(token.mint);
    let enhancedCps: Array<{ price: number; timeMin: number }>;

    if (ohlcvCheckpoints && ohlcvCheckpoints.length > 10) {
      // Use OHLCV data directly -- already has fine-grained price points
      enhancedCps = ohlcvCheckpoints;
    } else {
      // Fall back to coarse checkpoints (existing logic)
      const checkpoints: Array<{ price: number; timeMin: number }> = [
        { price: token.price15min, timeMin: 15 },
        { price: token.price1h, timeMin: 60 },
        { price: token.price4h, timeMin: 240 },
      ];

      // Estimate when peak occurs based on price trajectory
      // If peak > price1h, peak likely occurred before 1h; if peak > price4h, before 4h
      if (token.peakPriceUsd > token.price1h && token.peakPriceUsd > entryPrice) {
        // Peak probably occurred between 15min and 1h
        checkpoints.splice(1, 0, { price: token.peakPriceUsd, timeMin: 30 });
      } else if (token.peakPriceUsd > token.price4h && token.peakPriceUsd > entryPrice) {
        // Peak probably occurred between 1h and 4h
        checkpoints.splice(2, 0, { price: token.peakPriceUsd, timeMin: 120 });
      }

      // Enhance checkpoints with interpolated intermediate price points
      // to capture intra-period volatility and trigger SL/TP more accurately
      enhancedCps = enhanceCheckpoints(checkpoints);
    }

    let exited = false;
    let trailingHigh = entryPrice;

    // ─── Profit-taking ladder state ──────────────────────
    const ladder = cfg.profitLadder ?? DEFAULT_PROFIT_LADDER;
    let ladderIdx = 0; // next ladder level to check
    let remainingPct = 1.0; // fraction of position still held (1.0 = 100%)
    let totalSoldPct = 0; // fraction of original position sold via ladder
    let weightedExitSum = 0; // sum of (soldFraction * exitPrice) for partial exits

    for (const cp of enhancedCps) {
      const changePct = ((cp.price - entryPrice) / entryPrice) * 100;
      trailingHigh = Math.max(trailingHigh, cp.price);
      const trailingDrop = ((trailingHigh - cp.price) / trailingHigh) * 100;

      // Check stop loss first (worst case)
      if (changePct <= -activeSL) {
        exitPrice = entryPrice * (1 - activeSL / 100) * 0.97;
        exitReason = 'STOP_LOSS';
        holdTimeMin = cp.timeMin;
        exited = true;
        break;
      }

      // Check trailing stop (after we've had gains)
      if (trailingHigh > entryPrice * 1.05 && trailingDrop >= activeTrail) {
        // Trailing stop hit: compute weighted exit from partial ladder fills + remaining at trailing
        const trailPrice = cp.price;
        if (totalSoldPct > 0) {
          // Weighted average: ladder fills (at their prices) + remaining at trail price
          const totalWeighted = weightedExitSum + remainingPct * trailPrice;
          exitPrice = (totalWeighted / (totalSoldPct + remainingPct)) * 0.97;
        } else {
          exitPrice = trailPrice * 0.97;
        }
        exitReason = 'TRAILING_STOP';
        holdTimeMin = cp.timeMin;
        exited = true;
        break;
      }

      // ─── Configurable profit-taking ladder ──────────────────────
      // Check each pending ladder level in order
      let fullExitTriggered = false;
      while (ladderIdx < ladder.length) {
        const level = ladder[ladderIdx];
        const triggerChangePct = activeTP * level.triggerPctOfTp;

        if (changePct >= triggerChangePct) {
          // This ladder level triggers
          const sellFractionOfRemaining = level.sellPctOfRemaining;
          const sellFractionOfOriginal = remainingPct * sellFractionOfRemaining;
          const levelExitPrice = cp.price; // exit at current checkpoint price

          // Accumulate weighted exit
          weightedExitSum += sellFractionOfOriginal * levelExitPrice;
          totalSoldPct += sellFractionOfOriginal;
          remainingPct -= sellFractionOfOriginal;

          ladderIdx++;

          // If remaining position is negligible (<1%), treat as full exit
          if (remainingPct < 0.01) {
            fullExitTriggered = true;
            break;
          }
        } else {
          break; // price hasn't reached this level yet
        }
      }

      // If all ladder levels triggered or position fully sold
      if (fullExitTriggered || (ladderIdx >= ladder.length && ladder[ladder.length - 1].triggerPctOfTp >= 1.0 && changePct >= activeTP)) {
        // Compute final weighted average exit price
        if (remainingPct > 0.01) {
          // Still have remaining -- exit remainder at current trailing stop price
          const remainderPrice = cp.price * (1 - activeTrail / 100);
          weightedExitSum += remainingPct * remainderPrice;
          totalSoldPct += remainingPct;
          remainingPct = 0;
        }
        exitPrice = (totalSoldPct > 0 ? weightedExitSum / totalSoldPct : cp.price) * 0.97;
        exitReason = 'TAKE_PROFIT_SCALED';
        holdTimeMin = cp.timeMin;
        exited = true;
        break;
      }
    }

    if (!exited) {
      // No full exit trigger hit -- exit at 4h mark
      // If we had partial ladder exits, compute weighted average
      if (totalSoldPct > 0) {
        // Weighted average of ladder fills + remaining at time-exit price
        const timeExitPrice = token.price4h * 0.98;
        weightedExitSum += remainingPct * timeExitPrice;
        totalSoldPct += remainingPct;
        exitPrice = weightedExitSum / totalSoldPct;
        exitReason = 'TIME_EXIT_PARTIAL';
      } else {
        exitPrice = token.price4h * 0.98;
        exitReason = 'TIME_EXIT';
      }
      holdTimeMin = 240;
    }

    const pnlPct = ((exitPrice - entryPrice) / entryPrice) * 100;
    const pnlUsd = adjustedPositionUsd * (pnlPct / 100);
    capital += pnlUsd;
    openPositions--;

    peakCapital = Math.max(peakCapital, capital);
    const drawdown = ((peakCapital - capital) / peakCapital) * 100;
    maxDrawdown = Math.max(maxDrawdown, drawdown);
    returns.push(pnlPct);

    trades.push({
      symbol: token.symbol,
      source: token.source,
      entryPrice,
      exitPrice,
      pnlPct,
      pnlUsd,
      exitReason,
      holdTimeMin,
      safetyScore,
    });
  }

  // Statistics
  const wins = trades.filter(t => t.pnlUsd > 0);
  const losses = trades.filter(t => t.pnlUsd <= 0);
  const avgReturn = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0;
  const stdDev = returns.length > 1
    ? Math.sqrt(returns.reduce((s, r) => s + Math.pow(r - avgReturn, 2), 0) / (returns.length - 1))
    : 1;
  const grossProfit = wins.reduce((s, t) => s + t.pnlUsd, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnlUsd, 0));

  const result: EnhancedBacktestResult = {
    config: cfg,
    totalTokensAnalyzed: historicalTokens.length,
    tokensPassedFilter: filteredTokens.length,
    totalTrades: trades.length,
    wins: wins.length,
    losses: losses.length,
    winRate: trades.length > 0 ? wins.length / trades.length : 0,
    totalPnlUsd: capital - cfg.initialCapitalUsd,
    totalPnlPct: ((capital - cfg.initialCapitalUsd) / cfg.initialCapitalUsd) * 100,
    maxDrawdownPct: maxDrawdown,
    sharpeRatio: stdDev > 0 ? avgReturn / stdDev : 0,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? Infinity : 0),
    avgWinPct: wins.length > 0 ? wins.reduce((s, t) => s + t.pnlPct, 0) / wins.length : 0,
    avgLossPct: losses.length > 0 ? losses.reduce((s, t) => s + t.pnlPct, 0) / losses.length : 0,
    expectancy: trades.length > 0 ? (capital - cfg.initialCapitalUsd) / trades.length : 0,
    rugsAvoided: historicalTokens.filter(t => t.wasRug).length - trades.filter(t => t.exitReason === 'RUG').length,
    rugsHit: trades.filter(t => t.exitReason === 'RUG').length,
    bestTrade: trades.length > 0
      ? { symbol: trades.reduce((a, b) => a.pnlPct > b.pnlPct ? a : b).symbol, pnlPct: Math.max(...trades.map(t => t.pnlPct)) }
      : { symbol: 'N/A', pnlPct: 0 },
    worstTrade: trades.length > 0
      ? { symbol: trades.reduce((a, b) => a.pnlPct < b.pnlPct ? a : b).symbol, pnlPct: Math.min(...trades.map(t => t.pnlPct)) }
      : { symbol: 'N/A', pnlPct: 0 },
    avgHoldTimeMin: trades.length > 0 ? trades.reduce((s, t) => s + t.holdTimeMin, 0) / trades.length : 0,
    trades,
  };

  log.info('Enhanced backtest complete', {
    analyzed: result.totalTokensAnalyzed,
    filtered: result.tokensPassedFilter,
    trades: result.totalTrades,
    winRate: (result.winRate * 100).toFixed(1) + '%',
    pnl: '$' + result.totalPnlUsd.toFixed(2),
    sharpe: result.sharpeRatio.toFixed(2),
    maxDD: result.maxDrawdownPct.toFixed(1) + '%',
    profitFactor: result.profitFactor.toFixed(2),
    rugsAvoided: result.rugsAvoided,
    adaptiveExits: cfg.adaptiveExits,
    ageFilter: cfg.ageCategory,
    assetType: cfg.assetType,
  });

  return result;
}

function simulateEnhancedSafety(
  token: PumpFunHistoricalToken,
  macro?: MacroSnapshot | null,
  hlCorr?: HLCorrelationData | null,
): number {
  let score = 0;

  // 1. Liquidity depth (0-0.20)
  if (token.liquidityUsd >= 100000) score += 0.20;
  else if (token.liquidityUsd >= 50000) score += 0.18;
  else if (token.liquidityUsd >= 25000) score += 0.15;
  else if (token.liquidityUsd >= 10000) score += 0.10;

  // 2. Buy/sell ratio -- strong buy pressure is bullish (0-0.15)
  const ratio = token.buyCount1h / Math.max(1, token.sellCount1h);
  if (ratio >= 5) score += 0.15;
  else if (ratio >= 3) score += 0.12;
  else if (ratio >= 2) score += 0.08;
  else if (ratio >= 1.5) score += 0.05;

  // 3. Volume-to-liquidity ratio -- healthy trading activity (0-0.15)
  const volLiqRatio = token.volumeUsd24h / Math.max(1, token.liquidityUsd);
  if (volLiqRatio >= 2 && volLiqRatio <= 20) score += 0.15; // Healthy range
  else if (volLiqRatio >= 1) score += 0.10;
  else if (volLiqRatio >= 0.5) score += 0.05;
  // Very high ratio (>20) could mean wash trading -- no bonus

  // 4. Holder distribution proxy (0-0.10)
  if (token.holderCount >= 200) score += 0.10;
  else if (token.holderCount >= 100) score += 0.08;
  else if (token.holderCount >= 50) score += 0.05;

  // 5. Price momentum -- not already topped (0-0.15)
  const currentVsPeak = token.currentPriceUsd / Math.max(0.0000001, token.peakPriceUsd);
  if (currentVsPeak >= 0.8) score += 0.15; // Near peak -- strong momentum
  else if (currentVsPeak >= 0.5) score += 0.10; // Moderate pullback
  else if (currentVsPeak >= 0.3) score += 0.03; // Deep pullback -- risky

  // 6. Market cap sanity -- not buying mega-cap tokens (0-0.10)
  if (token.maxMultiple < 5) score += 0.10; // Early stage
  else if (token.maxMultiple < 20) score += 0.07;
  else if (token.maxMultiple < 50) score += 0.03;
  // Massive pump (>50x) -- likely already peaked

  // 7. Volume adequacy -- enough volume to exit (0-0.10)
  if (token.volumeUsd24h >= 100000) score += 0.10;
  else if (token.volumeUsd24h >= 50000) score += 0.08;
  else if (token.volumeUsd24h >= 10000) score += 0.05;

  // 8. Source bonus -- pump.fun tokens have known graduation mechanics (0-0.05)
  if (token.source === 'pumpfun') score += 0.05;

  // ─── NEW: Enhanced scoring factors ────────────────────

  // 9. Token age bonus (0-0.15)
  if (token.ageCategory === 'veteran') score += 0.15;
  else if (token.ageCategory === 'established') score += 0.10;
  else if (token.ageCategory === 'young') score += 0.05;
  // fresh tokens get no age bonus

  // 10. Volume surge bonus (0-0.15)
  if (token.isVolumeSurge) {
    if (token.volumeSurgeRatio > 10) score += 0.08; // extreme surge -- caution (could be manipulation)
    else if (token.volumeSurgeRatio > 5) score += 0.15; // strong surge
    else if (token.volumeSurgeRatio > 3) score += 0.10; // moderate surge
  }

  // 11. Market cap stability: MCap/Liq ratio 2-10 is healthy (0-0.10)
  if (token.mcapLiqRatio >= 2 && token.mcapLiqRatio <= 10) score += 0.10;
  else if (token.mcapLiqRatio > 1 && token.mcapLiqRatio <= 20) score += 0.05;
  // ratio >20 or <1 is unhealthy -- no bonus

  // 12. Price trajectory bonus (0-0.10)
  if (token.priceTrajectory === 'recovering') score += 0.10;
  else if (token.priceTrajectory === 'consolidating') score += 0.05;
  else if (token.priceTrajectory === 'pumping') score += 0.03;
  // dumping gets no bonus

  // 13. xStock bonus -- tokenized equities are a safer asset class (0-0.15)
  if (token.isXStock) score += 0.15;

  // 13b. Blue chip bonus -- established ecosystem tokens with proven track record (0-0.15)
  if (token.isBlueChip && !token.isXStock) score += 0.15;

  // 14. BTC correlation penalty -- if BTC is dumping and token follows (-0.05)
  if (token.btcCorrelation > 0.5 && token.priceTrajectory === 'dumping') {
    score -= 0.05;
  }

  // 15. Macro correlation adjustment (-0.30 to +0.30)
  if (macro) {
    const ageCategory = token.ageCategory || 'fresh';
    const macroAdj = getCorrelationAdjustment(macro, ageCategory, token.isXStock);
    score += macroAdj;
  }

  // 16. Hyperliquid-derived SOL-BTC correlation: if SOL is highly correlated
  // with BTC and BTC is dumping, extra penalty
  if (hlCorr && macro) {
    const solBtcCorr = hlCorr.solBtcCorrelation;
    if (solBtcCorr > 0.7 && macro.btcTrend === 'dumping') {
      score -= 0.10; // SOL-correlated tokens will likely dump too
    } else if (solBtcCorr > 0.7 && macro.btcTrend === 'pumping') {
      score += 0.05; // Rising tide
    }
    // High SOL volatility = reduce conviction
    if (hlCorr.solVolatility > 100) { // >100% annualized vol
      score -= 0.05;
    }
  }

  // 15.5. Smart money simulation score (0-0.15)
  const smartScore = simulateSmartMoneyScore({
    buyCount1h: token.buyCount1h,
    sellCount1h: token.sellCount1h,
    volumeUsd24h: token.volumeUsd24h,
    liquidityUsd: token.liquidityUsd,
    holderCount: token.holderCount,
    volumeSurgeRatio: token.volumeSurgeRatio,
    isVolumeSurge: token.isVolumeSurge,
  });
  score += smartScore * 0.15; // Scale to max 0.15

  // PENALTIES
  // Rug indicator -- heavy penalty
  if (token.wasRug) score -= 0.40;

  // Extreme price drop from peak without being flagged as rug
  if (token.ruggedAtPct > 70 && !token.wasRug) score -= 0.15;

  // Very low volume relative to liquidity (dead token)
  if (volLiqRatio < 0.1 && token.volumeUsd24h > 0) score -= 0.10;

  return Math.max(0, Math.min(1, score));
}

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function fetchWithRetry<T>(
  fn: () => Promise<T>,
  retries: number = 3,
  baseDelay: number = 2000,
): Promise<T> {
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 429 && i < retries - 1) {
        const delay = baseDelay * Math.pow(2, i) + Math.random() * 1000;
        log.info(`Rate limited, retrying in ${(delay / 1000).toFixed(1)}s (attempt ${i + 2}/${retries})`);
        await sleep(delay);
        continue;
      }
      throw err;
    }
  }
  throw new Error('Max retries exceeded');
}
