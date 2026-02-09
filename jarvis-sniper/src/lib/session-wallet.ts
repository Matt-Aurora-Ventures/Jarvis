/**
 * Session Wallet — Ephemeral Keypair for Automated Signing
 *
 * Creates a temporary keypair that can auto-sign transactions without
 * Phantom popups. Used for:
 * - Automated SL/TP execution (no user interaction needed)
 * - Batch operations (close all, Jito bundles)
 * - Server-side risk management execution
 *
 * Security model:
 * - Keypair is generated fresh each session
 * - Only funded with small amounts (max position SOL + gas)
 * - Encrypted in sessionStorage (not localStorage — dies with tab)
 * - Auto-sweeps profits back to main wallet after trades
 * - Capital segregation: main wallet never exposed to automation
 *
 * Flow:
 * 1. User clicks "Enable Auto-Execute" → generates keypair
 * 2. User transfers SOL from Phantom to session wallet
 * 3. System auto-signs sell transactions when SL/TP triggers
 * 4. After trade, profits sweep back to main wallet
 * 5. Session ends → keypair is discarded
 */

import {
  Keypair,
  Connection,
  PublicKey,
  Transaction,
  SystemProgram,
  VersionedTransaction,
  LAMPORTS_PER_SOL,
  TransactionMessage,
} from '@solana/web3.js';

const RPC_URL = process.env.NEXT_PUBLIC_SOLANA_RPC || 'https://api.mainnet-beta.solana.com';
const SESSION_KEY = '__jarvis_session_wallet';

// ─── Types ───

export interface SessionWalletState {
  /** Session wallet public key (base58) */
  publicKey: string;
  /** Whether the session wallet is funded and ready */
  funded: boolean;
  /** SOL balance in the session wallet */
  balanceSol: number;
  /** Main wallet that owns this session (for sweep-back) */
  mainWallet: string;
  /** When the session was created */
  createdAt: number;
}

// ─── Keypair Management ───

/**
 * Encrypt a keypair's secret key for sessionStorage.
 * Uses a simple XOR with a derived key — sufficient for ephemeral session data.
 * (For server-side production, use proper encryption like AES-256-GCM.)
 */
function encryptSecretKey(secretKey: Uint8Array, mainWallet: string): string {
  const key = new TextEncoder().encode(mainWallet.padEnd(64, '0').slice(0, 64));
  const encrypted = new Uint8Array(secretKey.length);
  for (let i = 0; i < secretKey.length; i++) {
    encrypted[i] = secretKey[i] ^ key[i % key.length];
  }
  return Buffer.from(encrypted).toString('base64');
}

function decryptSecretKey(encrypted: string, mainWallet: string): Uint8Array {
  const key = new TextEncoder().encode(mainWallet.padEnd(64, '0').slice(0, 64));
  const data = Buffer.from(encrypted, 'base64');
  const decrypted = new Uint8Array(data.length);
  for (let i = 0; i < data.length; i++) {
    decrypted[i] = data[i] ^ key[i % key.length];
  }
  return decrypted;
}

/**
 * Generate a new session keypair and store encrypted in sessionStorage.
 */
export function createSessionWallet(mainWallet: string): {
  publicKey: string;
  keypair: Keypair;
} {
  const keypair = Keypair.generate();
  const pubkey = keypair.publicKey.toBase58();

  const stored = {
    publicKey: pubkey,
    encryptedSecret: encryptSecretKey(keypair.secretKey, mainWallet),
    mainWallet,
    createdAt: Date.now(),
  };

  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(stored));
  }

  return { publicKey: pubkey, keypair };
}

/**
 * Load the session keypair from sessionStorage (no Phantom required).
 * Returns null if no session exists or decryption fails.
 */
export function loadSessionWalletFromStorage(): { keypair: Keypair; publicKey: string; mainWallet: string; createdAt: number } | null {
  if (typeof sessionStorage === 'undefined') return null;

  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;

  try {
    const stored = JSON.parse(raw);
    if (!stored?.encryptedSecret || !stored?.mainWallet || !stored?.publicKey) return null;
    const secretKey = decryptSecretKey(stored.encryptedSecret, stored.mainWallet);
    return {
      keypair: Keypair.fromSecretKey(secretKey),
      publicKey: String(stored.publicKey),
      mainWallet: String(stored.mainWallet),
      createdAt: Number(stored.createdAt || Date.now()),
    };
  } catch {
    return null;
  }
}

/**
 * Destroy the session wallet (clear from sessionStorage).
 */
export function destroySessionWallet(): void {
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(SESSION_KEY);
  }
}

/**
 * Check if a session wallet exists for this main wallet.
 */
export function hasSessionWallet(mainWallet: string): boolean {
  if (typeof sessionStorage === 'undefined') return false;
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return false;
  try {
    return JSON.parse(raw).mainWallet === mainWallet;
  } catch {
    return false;
  }
}

// ─── Transaction Helpers ───

/**
 * Get the SOL balance of the session wallet.
 */
export async function getSessionBalance(publicKey: string): Promise<number> {
  const connection = new Connection(RPC_URL, 'confirmed');
  const balance = await connection.getBalance(new PublicKey(publicKey));
  return balance / LAMPORTS_PER_SOL;
}

/**
 * Build a transaction to fund the session wallet from the main wallet.
 * Returns an unsigned transaction that needs to be signed by Phantom.
 */
export async function buildFundSessionTx(
  mainWallet: string,
  sessionPublicKey: string,
  amountSol: number,
): Promise<VersionedTransaction> {
  const connection = new Connection(RPC_URL, 'confirmed');
  const from = new PublicKey(mainWallet);
  const to = new PublicKey(sessionPublicKey);

  const instruction = SystemProgram.transfer({
    fromPubkey: from,
    toPubkey: to,
    lamports: Math.floor(amountSol * LAMPORTS_PER_SOL),
  });

  const blockhash = await connection.getLatestBlockhash('confirmed');
  const messageV0 = new TransactionMessage({
    payerKey: from,
    recentBlockhash: blockhash.blockhash,
    instructions: [instruction],
  }).compileToV0Message();

  return new VersionedTransaction(messageV0);
}

/**
 * Build a transaction to sweep all SOL back from session wallet to main wallet.
 * The session wallet signs this automatically (no Phantom needed).
 * Leaves a small amount for rent.
 */
export async function sweepToMainWallet(
  sessionKeypair: Keypair,
  mainWallet: string,
): Promise<string | null> {
  const connection = new Connection(RPC_URL, 'confirmed');
  const balance = await connection.getBalance(sessionKeypair.publicKey);

  // Leave 5000 lamports for rent exemption
  const sweepAmount = balance - 5000;
  if (sweepAmount <= 0) return null;

  const instruction = SystemProgram.transfer({
    fromPubkey: sessionKeypair.publicKey,
    toPubkey: new PublicKey(mainWallet),
    lamports: sweepAmount,
  });

  const blockhash = await connection.getLatestBlockhash('confirmed');
  const messageV0 = new TransactionMessage({
    payerKey: sessionKeypair.publicKey,
    recentBlockhash: blockhash.blockhash,
    instructions: [instruction],
  }).compileToV0Message();

  const tx = new VersionedTransaction(messageV0);
  tx.sign([sessionKeypair]);

  const sig = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    preflightCommitment: 'confirmed',
  });

  return sig;
}

/**
 * Sweep ONLY the excess SOL back to the main wallet, leaving a reserve behind
 * for continued trading + fees.
 *
 * This is used to "bank profits" automatically while keeping the session wallet
 * funded enough to continue auto-sniping.
 */
export async function sweepExcessToMainWallet(
  sessionKeypair: Keypair,
  mainWallet: string,
  reserveSol: number,
): Promise<string | null> {
  const connection = new Connection(RPC_URL, 'confirmed');
  const balance = await connection.getBalance(sessionKeypair.publicKey);

  // Keep a reserve + tiny dust for fees.
  const keepLamports = Math.floor(Math.max(0, reserveSol) * LAMPORTS_PER_SOL) + 5000;
  const sweepAmount = balance - keepLamports;

  // Avoid sweeping tiny amounts (keeps noise down, avoids edge-case fee issues).
  if (sweepAmount < 0.001 * LAMPORTS_PER_SOL) return null;

  const instruction = SystemProgram.transfer({
    fromPubkey: sessionKeypair.publicKey,
    toPubkey: new PublicKey(mainWallet),
    lamports: sweepAmount,
  });

  const blockhash = await connection.getLatestBlockhash('confirmed');
  const messageV0 = new TransactionMessage({
    payerKey: sessionKeypair.publicKey,
    recentBlockhash: blockhash.blockhash,
    instructions: [instruction],
  }).compileToV0Message();

  const tx = new VersionedTransaction(messageV0);
  tx.sign([sessionKeypair]);

  const sig = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    preflightCommitment: 'confirmed',
  });

  return sig;
}

/**
 * Sign a VersionedTransaction with the session keypair.
 * Used for auto-executing sells when SL/TP triggers.
 */
export function signWithSession(
  tx: VersionedTransaction,
  sessionKeypair: Keypair,
): VersionedTransaction {
  tx.sign([sessionKeypair]);
  return tx;
}

/**
 * Helper: determine whether the session wallet is likely funded enough to trade.
 * Keep this intentionally conservative: session wallet must hold the trading budget
 * plus some headroom for fees.
 */
export function isLikelyFunded(balanceSol: number, desiredBudgetSol: number): boolean {
  // ~0.02 SOL covers a few priority fees + rent/ATA creation overhead.
  const feeBuffer = 0.02;
  return balanceSol >= Math.max(0.01, desiredBudgetSol + feeBuffer);
}
