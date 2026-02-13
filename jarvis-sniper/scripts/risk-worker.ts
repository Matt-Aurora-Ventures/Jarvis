#!/usr/bin/env npx tsx
/**
 * Jarvis Sniper — 24/7 Risk Worker
 *
 * Standalone Node.js script that monitors open positions and executes
 * SL/TP sells automatically — even when the browser is closed.
 *
 * Architecture:
 * - Reads positions from .positions.json (written by the Next.js app)
 * - Uses DexScreener for a fast "near trigger" check (USD price)
 * - When near SL/TP: fetches a Bags quote (token->SOL) to compute realizable P&L
 * - When SL/TP triggers: builds sell tx via Bags API, signs with SNIPER_PRIVATE_KEY, sends
 * - Updates .positions.json with close status
 *
 * Requirements:
 * - SNIPER_PRIVATE_KEY in .env.local (base58-encoded Solana keypair)
 * - BAGS_API_KEY in .env.local (Bags API key for quoting + building swap tx)
 * - .positions.json populated by the web app
 *
 * Usage:
 *   npx tsx scripts/risk-worker.ts
 *
 * Or add to package.json scripts:
 *   "risk-worker": "npx tsx scripts/risk-worker.ts"
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { BagsSDK } from '@bagsfm/bags-sdk';
import {
  Connection,
  PublicKey,
  Keypair,
  VersionedTransaction,
  TransactionMessage,
  AddressLookupTableAccount,
  ComputeBudgetProgram,
} from '@solana/web3.js';

// Load .env.local
const envPath = join(process.cwd(), '.env.local');
if (existsSync(envPath)) {
  const envContent = readFileSync(envPath, 'utf-8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx < 0) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim();
    if (!process.env[key]) process.env[key] = val;
  }
}

// Config
const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const PRIVATE_KEY = process.env.SNIPER_PRIVATE_KEY || '';
const BAGS_API_KEY = process.env.BAGS_API_KEY || '';
const CHECK_INTERVAL_MS = 3000; // 3 seconds
const SOL_MINT = 'So11111111111111111111111111111111111111112';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const SLIPPAGE_BPS = Number(process.env.RISK_WORKER_SLIPPAGE_BPS || '200');
const PRIORITY_FEE_MICROLAMPORTS = Number(process.env.RISK_WORKER_PRIORITY_FEE_MICRO_LAMPORTS || '200000');
const NEAR_TRIGGER_FACTOR = Number(process.env.RISK_WORKER_NEAR_FACTOR || '0.8');
const POSITIONS_FILE = join(process.cwd(), '.positions.json');

interface PersistedPosition {
  id: string;
  mint: string;
  symbol: string;
  amount: number;
  amountLamports?: string;
  solInvested: number;
  entryPrice: number;
  stopLossPct: number;
  takeProfitPct: number;
  txHash?: string;
  walletAddress: string;
  status: 'open' | 'closed' | 'sl_hit' | 'tp_hit';
  entryTime: number;
  closeTxHash?: string;
}

function readPositions(): PersistedPosition[] {
  try {
    if (!existsSync(POSITIONS_FILE)) return [];
    return JSON.parse(readFileSync(POSITIONS_FILE, 'utf-8'));
  } catch {
    return [];
  }
}

function writePositions(positions: PersistedPosition[]): void {
  writeFileSync(POSITIONS_FILE, JSON.stringify(positions, null, 2), 'utf-8');
}

function closePosition(mint: string, status: 'sl_hit' | 'tp_hit', closeTxHash?: string): void {
  const positions = readPositions();
  const updated = positions.map((p) => {
    if (p.mint === mint && p.status === 'open') {
      return { ...p, status, closeTxHash };
    }
    return p;
  });
  writePositions(updated);
}

let wallet: Keypair | null = null;
let connection: Connection;
let sdk: BagsSDK | null = null;
const inFlight = new Set<string>();

function getWallet(): Keypair {
  if (!wallet) {
    if (!PRIVATE_KEY) {
      throw new Error(
        'SNIPER_PRIVATE_KEY not set in .env.local.\n' +
        'Export your Phantom private key and add:\n' +
        '  SNIPER_PRIVATE_KEY=<base58 private key>\n' +
        'WARNING: Use a dedicated trading wallet with limited funds.',
      );
    }
    // Support both base58 and JSON array formats
    try {
      const bs58 = require('bs58') as { decode: (s: string) => Uint8Array };
      wallet = Keypair.fromSecretKey(bs58.decode(PRIVATE_KEY));
    } catch {
      // Try JSON array format
      const bytes = JSON.parse(PRIVATE_KEY);
      wallet = Keypair.fromSecretKey(new Uint8Array(bytes));
    }
    console.log(`[Risk Worker] Wallet: ${wallet.publicKey.toBase58()}`);
  }
  return wallet;
}

function getSDK(): BagsSDK {
  if (!sdk) {
    if (!BAGS_API_KEY) {
      throw new Error('BAGS_API_KEY not set in .env.local. Required for Bags-only quoting/swaps.');
    }
    sdk = new BagsSDK(BAGS_API_KEY, connection, 'confirmed');
  }
  return sdk;
}

function minLamports(a: string, b: string): string {
  try {
    const aa = BigInt(a);
    const bb = BigInt(b);
    return (aa <= bb ? aa : bb).toString();
  } catch {
    // Safer fallback: don't oversell.
    return b;
  }
}

async function fetchPrices(mints: string[]): Promise<Record<string, number>> {
  const prices: Record<string, number> = {};
  if (mints.length === 0) return prices;

  // DexScreener supports up to 30 addresses per call
  const batches: string[][] = [];
  for (let i = 0; i < mints.length; i += 30) {
    batches.push(mints.slice(i, i + 30));
  }

  for (const batch of batches) {
    try {
      const res = await fetch(`${DEXSCREENER_TOKENS}/${batch.join(',')}`, {
        headers: { Accept: 'application/json' },
      });
      if (!res.ok) continue;
      const pairs: any[] = await res.json();

      // Group by baseToken.address, pick pair with highest liquidity
      const bestPair = new Map<string, any>();
      for (const pair of pairs) {
        const mint = pair.baseToken?.address;
        if (!mint) continue;
        const liq = parseFloat(pair.liquidity?.usd || '0');
        const existing = bestPair.get(mint);
        if (!existing || liq > (existing._liq || 0)) {
          bestPair.set(mint, { ...pair, _liq: liq });
        }
      }

      for (const [mint, pair] of bestPair) {
        const price = parseFloat(pair.priceUsd || '0');
        if (price > 0) prices[mint] = price;
      }
    } catch {
      // ignore batch failures
    }
  }

  return prices;
}

async function getTokenBalanceLamports(owner: PublicKey, mint: string): Promise<string> {
  try {
    const mintPk = new PublicKey(mint);
    const res = await connection.getParsedTokenAccountsByOwner(owner, { mint: mintPk });
    let total = BigInt(0);
    for (const { account } of res.value) {
      const amt = (account.data as any)?.parsed?.info?.tokenAmount?.amount;
      if (typeof amt === 'string' && amt.length > 0) total += BigInt(amt);
    }
    return total.toString();
  } catch {
    return '0';
  }
}

async function resolveSellAmountLamports(pos: PersistedPosition, owner: PublicKey): Promise<string | null> {
  const walletBal = await getTokenBalanceLamports(owner, pos.mint);
  if (walletBal === '0') return null;
  if (!pos.amountLamports || pos.amountLamports === '0') return walletBal;
  return minLamports(pos.amountLamports, walletBal);
}

async function getSellQuoteBags(tokenMint: string, amountLamports: string): Promise<any | null> {
  try {
    const bags = getSDK();
    return await bags.trade.getQuote({
      inputMint: new PublicKey(tokenMint),
      outputMint: new PublicKey(SOL_MINT),
      amount: Number(amountLamports),
      slippageMode: 'manual',
      slippageBps: SLIPPAGE_BPS,
    });
  } catch (err) {
    console.warn('[SellQuote] Bags quote failed:', err instanceof Error ? err.message : err);
    return null;
  }
}

async function injectPriorityFee(
  tx: VersionedTransaction,
  microLamports: number,
): Promise<VersionedTransaction> {
  try {
    if (microLamports <= 0) return tx;

    const altAccounts: AddressLookupTableAccount[] = await Promise.all(
      tx.message.addressTableLookups.map(async (lookup) => {
        const res = await connection.getAddressLookupTable(lookup.accountKey);
        if (!res.value) throw new Error(`ALT not found: ${lookup.accountKey.toBase58()}`);
        return new AddressLookupTableAccount({
          key: lookup.accountKey,
          state: res.value.state,
        });
      }),
    );

    const message = TransactionMessage.decompile(tx.message, {
      addressLookupTableAccounts: altAccounts,
    });

    const hasComputeBudget = message.instructions.some(
      (ix) => ix.programId.equals(ComputeBudgetProgram.programId),
    );

    if (!hasComputeBudget) {
      message.instructions.unshift(
        ComputeBudgetProgram.setComputeUnitPrice({ microLamports }),
      );
    }

    const newMessage = message.compileToV0Message(altAccounts);
    return new VersionedTransaction(newMessage);
  } catch {
    return tx; // non-fatal
  }
}

async function executeSellFromQuote(pos: PersistedPosition, quote: any): Promise<string | null> {
  const kp = getWallet();

  // Safety: don't attempt to sell positions created by a different wallet.
  if (pos.walletAddress && pos.walletAddress !== kp.publicKey.toBase58()) {
    console.warn(
      `[Sell] Skipping ${pos.symbol}: position wallet ${pos.walletAddress.slice(0, 8)}... does not match worker wallet ${kp.publicKey.toBase58().slice(0, 8)}...`,
    );
    return null;
  }

  try {
    const bags = getSDK();
    const swap = await bags.trade.createSwapTransaction({
      quoteResponse: quote,
      userPublicKey: kp.publicKey,
    });

    let tx = swap.transaction;
    if (PRIORITY_FEE_MICROLAMPORTS > 0) {
      tx = await injectPriorityFee(tx, PRIORITY_FEE_MICROLAMPORTS);
    }

    tx.sign([kp]);

    const sig = await connection.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 3,
    });

    const confirm = await connection.confirmTransaction(sig, 'confirmed');
    if (confirm.value.err) {
      console.error(`[Sell] On-chain failure for ${pos.symbol}: ${sig}`);
      return null;
    }

    return sig;
  } catch (err) {
    console.error(`[Sell] Exception for ${pos.symbol}:`, err instanceof Error ? err.message : err);
    return null;
  }
}

async function monitorLoop(): Promise<void> {
  const positions = readPositions();
  const open = positions.filter((p) => p.status === 'open');

  if (open.length === 0) return;

  // Fetch prices for all open positions
  const mints = [...new Set(open.map((p) => p.mint))];
  const prices = await fetchPrices(mints);

  for (const pos of open) {
    if (inFlight.has(pos.id)) continue;
    const currentPrice = prices[pos.mint];
    if (!currentPrice || !pos.entryPrice) continue;

    const pnlPct = ((currentPrice - pos.entryPrice) / pos.entryPrice) * 100;

    // Fast preliminary check before doing the expensive quote
    const nearSl = pnlPct <= -(pos.stopLossPct * NEAR_TRIGGER_FACTOR);
    const nearTp = pnlPct >= (pos.takeProfitPct * NEAR_TRIGGER_FACTOR);
    if (!nearSl && !nearTp) {
      if (Math.random() < 0.1) {
        console.log(
          `[Monitor] ${pos.symbol}: ${pnlPct.toFixed(1)}% | SL -${pos.stopLossPct}% | TP +${pos.takeProfitPct}%`,
        );
      }
      continue;
    }

    // If we can't trade, still log (but don't attempt execution).
    if (!BAGS_API_KEY || !PRIVATE_KEY) {
      if (pnlPct <= -pos.stopLossPct || pnlPct >= pos.takeProfitPct) {
        console.warn(`[Monitor] ${pos.symbol}: trigger reached but worker cannot execute (missing BAGS_API_KEY or SNIPER_PRIVATE_KEY)`);
      }
      continue;
    }

    // Resolve sell amount and fetch Bags quote to compute realizable exit.
    const kp = getWallet();
    const sellAmountLamports = await resolveSellAmountLamports(pos, kp.publicKey);
    if (!sellAmountLamports) continue;

    const quote = await getSellQuoteBags(pos.mint, sellAmountLamports);
    if (!quote) {
      if (pnlPct <= -pos.stopLossPct) {
        console.error(`[Monitor] ${pos.symbol}: SL reached but no sell route (liquidity may be gone)`);
      }
      continue;
    }

    const exitValueSol = Number(BigInt(quote.outAmount)) / 1e9;
    const realPnlPct = ((exitValueSol - pos.solInvested) / pos.solInvested) * 100;

    const hitSl = realPnlPct <= -pos.stopLossPct;
    const hitTp = realPnlPct >= pos.takeProfitPct;
    if (!hitSl && !hitTp) continue;

    const trigger = hitTp ? 'TP' : 'SL';
    const status = hitTp ? 'tp_hit' : 'sl_hit';

    inFlight.add(pos.id);
    try {
      console.log(
        `[${trigger} TRIGGERED] ${pos.symbol}: ${realPnlPct.toFixed(1)}% (exit ${exitValueSol.toFixed(4)} SOL) — selling...`,
      );

      const txHash = await executeSellFromQuote(pos, quote);
      if (txHash) {
        console.log(`[SOLD] ${pos.symbol} — tx: ${txHash}`);
        closePosition(pos.mint, status, txHash);
      } else {
        console.error(`[FAILED] Could not sell ${pos.symbol} — will retry next cycle`);
      }
    } finally {
      inFlight.delete(pos.id);
    }
  }
}

// Main
async function main() {
  console.log('========================================');
  console.log('  Jarvis Sniper — Risk Worker');
  console.log('  24/7 Stop Loss / Take Profit Monitor');
  console.log('========================================');
  console.log(`  RPC: ${RPC_URL.slice(0, 40)}...`);
  console.log(`  Interval: ${CHECK_INTERVAL_MS}ms`);
  console.log(`  Positions file: ${POSITIONS_FILE}`);

  connection = new Connection(RPC_URL, 'confirmed');

  // Validate wallet on startup
  try {
    getWallet();
  } catch (err) {
    console.error((err as Error).message);
    console.log('\nThe risk worker will monitor prices but cannot execute sells without SNIPER_PRIVATE_KEY.');
    console.log('Positions will still be tracked and logged.\n');
  }

  // Validate Bags API key on startup
  try {
    getSDK();
  } catch (err) {
    console.error((err as Error).message);
    console.log('\nThe risk worker will monitor prices but cannot execute sells without BAGS_API_KEY.');
    console.log('Positions will still be tracked and logged.\n');
  }

  const initial = readPositions().filter((p) => p.status === 'open');
  console.log(`  Open positions: ${initial.length}`);
  for (const p of initial) {
    console.log(`    - ${p.symbol} (${p.mint.slice(0, 8)}...) | SL ${p.stopLossPct}% | TP ${p.takeProfitPct}%`);
  }
  console.log('========================================\n');

  // Run monitoring loop
  const run = async () => {
    try {
      await monitorLoop();
    } catch (err) {
      console.error('[Risk Worker] Loop error:', err);
    }
  };

  // Initial check
  await run();

  // Continuous loop
  setInterval(run, CHECK_INTERVAL_MS);
}

main().catch(console.error);
