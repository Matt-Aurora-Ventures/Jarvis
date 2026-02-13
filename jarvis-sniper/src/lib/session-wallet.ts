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
 * - Encrypted in sessionStorage + backed up to localStorage (survives tab close)
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
  TransactionInstruction,
  VersionedTransaction,
  LAMPORTS_PER_SOL,
  TransactionMessage,
} from '@solana/web3.js';
import { Buffer } from 'buffer';
import { getRpcUrl, getConnection } from './rpc-url';
import { waitForSignatureStatus } from './tx-confirmation';
import { withTimeout } from './async-timeout';

const SESSION_KEY = '__jarvis_session_wallet';
const PERSISTENT_KEY = '__jarvis_wallet_persistent'; // localStorage backup
const WALLET_BY_PUBKEY_PREFIX = '__jarvis_session_wallet_by_pubkey:';
const SPL_TOKEN_PROGRAM_ID = new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA');
const SPL_TOKEN_2022_PROGRAM_ID = new PublicKey('TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb');
const SPL_CLOSE_ACCOUNT_INSTRUCTION = Buffer.from([9]);
const TOKEN_ACCOUNT_CLOSE_CHUNK = 6;

function keyForPubkey(pubkey: string): string {
  return `${WALLET_BY_PUBKEY_PREFIX}${pubkey}`;
}

// ─── Deterministic Recovery (never lose keys) ────────────────────────────────

const DETERMINISTIC_DOMAIN = 'jarvis-session-wallet:v1';

export function getDeterministicSessionWalletMessage(mainWallet: string): Uint8Array {
  // IMPORTANT: This message must be stable forever for recovery to work.
  // It must also be wallet-specific to avoid key collisions across users.
  const msg = [
    'JARVIS SNIPER - RECOVERABLE SESSION WALLET',
    `Domain: ${DETERMINISTIC_DOMAIN}`,
    `Main wallet: ${mainWallet}`,
    '',
    'Signing this message will derive your Session Wallet key.',
    'Do not sign this message on untrusted sites.',
  ].join('\n');
  return new TextEncoder().encode(msg);
}

async function sha256Bytes(input: Uint8Array): Promise<Uint8Array> {
  if (typeof crypto === 'undefined' || !crypto.subtle) {
    throw new Error('WebCrypto unavailable (cannot derive deterministic session wallet)');
  }
  // Ensure we always pass a plain ArrayBuffer to WebCrypto for compatibility.
  const ab = new ArrayBuffer(input.byteLength);
  new Uint8Array(ab).set(input);
  const hash = await crypto.subtle.digest('SHA-256', ab);
  return new Uint8Array(hash);
}

/**
 * Derive a deterministic (recoverable) session wallet from a Phantom signature.
 * This does NOT persist anything; it just returns the keypair.
 */
export async function deriveDeterministicSessionWallet(
  mainWallet: string,
  signature: Uint8Array,
): Promise<{ publicKey: string; keypair: Keypair }> {
  const domain = new TextEncoder().encode(`${DETERMINISTIC_DOMAIN}:${mainWallet}`);
  const material = new Uint8Array(domain.length + signature.length);
  material.set(domain, 0);
  material.set(signature, domain.length);

  const hash = await sha256Bytes(material);
  const seed = hash.slice(0, 32);
  const keypair = Keypair.fromSeed(seed);
  const publicKey = keypair.publicKey.toBase58();
  return { publicKey, keypair };
}

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

export interface SessionWalletCleanupResult {
  closedTokenAccounts: number;
  failedToCloseTokenAccounts: number;
  skippedNonZeroTokenAccounts: number;
  reclaimedLamports: number;
  closeSignatures: string[];
}

export interface SessionWalletSweepResult extends SessionWalletCleanupResult {
  sweepSignature: string | null;
}

// ─── Keypair Management ───

interface StoredSessionWalletV1 {
  publicKey: string;
  encryptedSecret: string;
  mainWallet: string;
  createdAt: number;
  /** Optional metadata: how this wallet was created (helps explain recovery paths). */
  derivation?: 'random' | 'phantom_signMessage_v1';
}

/**
 * AES-256-GCM encryption for session wallet secret keys.
 *
 * Key derivation: PBKDF2(mainWallet, random salt, 210k iterations) -> AES-256 key
 * Ciphertext format: salt(16) || iv(12) || ciphertext(N + 16 GCM tag)
 *
 * Legacy XOR ciphertext (<=64 bytes) is transparently handled in decryptSecretKey
 * for backward compatibility with wallets encrypted before this upgrade.
 */
const ENCRYPTION_ITERATIONS = 210_000;

async function deriveAesKey(mainWallet: string, salt: Uint8Array): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(mainWallet) as BufferSource,
    'PBKDF2',
    false,
    ['deriveKey'],
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt: salt as BufferSource, iterations: ENCRYPTION_ITERATIONS, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

async function encryptSecretKey(secretKey: Uint8Array, mainWallet: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveAesKey(mainWallet, salt);
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: iv as BufferSource }, key, secretKey as BufferSource);
  const packed = new Uint8Array(salt.length + iv.length + new Uint8Array(ciphertext).length);
  packed.set(salt, 0);
  packed.set(iv, salt.length);
  packed.set(new Uint8Array(ciphertext), salt.length + iv.length);
  return Buffer.from(packed).toString('base64');
}

async function decryptSecretKey(encrypted: string, mainWallet: string): Promise<Uint8Array> {
  const packed = new Uint8Array(Buffer.from(encrypted, 'base64'));

  // Legacy XOR: exactly 64 bytes (ed25519 secret key size)
  // AES-GCM: 16 (salt) + 12 (iv) + ciphertext (64 + 16 GCM tag = 80) = 108 bytes
  if (packed.length <= 64) {
    const key = new TextEncoder().encode(mainWallet.padEnd(64, '0').slice(0, 64));
    const decrypted = new Uint8Array(packed.length);
    for (let i = 0; i < packed.length; i++) {
      decrypted[i] = packed[i] ^ key[i % key.length];
    }
    return decrypted;
  }

  const salt = packed.slice(0, 16);
  const iv = packed.slice(16, 28);
  const ciphertext = packed.slice(28);
  const aesKey = await deriveAesKey(mainWallet, salt);
  const plaintext = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: iv as BufferSource }, aesKey, ciphertext as BufferSource);
  return new Uint8Array(plaintext);
}

function persistStoredWalletV1(stored: StoredSessionWalletV1): void {
  const raw = JSON.stringify(stored);

  if (typeof sessionStorage !== 'undefined') {
    try { sessionStorage.setItem(SESSION_KEY, raw); } catch {}
  }
  if (typeof localStorage !== 'undefined') {
    try { localStorage.setItem(PERSISTENT_KEY, raw); } catch {}
    // Keep a per-wallet backup so creating a new session wallet doesn't overwrite recovery.
    try { localStorage.setItem(keyForPubkey(stored.publicKey), raw); } catch {}
  }
}

async function decodeStoredWalletV1(stored: StoredSessionWalletV1): Promise<{ keypair: Keypair; publicKey: string; mainWallet: string; createdAt: number } | null> {
  try {
    const secretKey = await decryptSecretKey(stored.encryptedSecret, stored.mainWallet);
    const keypair = Keypair.fromSecretKey(secretKey);
    const derivedPubkey = keypair.publicKey.toBase58();
    if (derivedPubkey !== stored.publicKey) return null;
    return {
      keypair,
      publicKey: stored.publicKey,
      mainWallet: stored.mainWallet,
      createdAt: Number(stored.createdAt || Date.now()),
    };
  } catch {
    return null;
  }
}

/**
 * Import a session wallet secret key (e.g., from a backup file) and persist it in browser storage.
 * This enables sweeping funds even if the original tab/session is gone.
 */
export async function importSessionWalletSecretKey(
  secretKey: Uint8Array,
  mainWallet: string,
  createdAt: number = Date.now(),
  derivation: StoredSessionWalletV1['derivation'] = 'random',
): Promise<{ publicKey: string; keypair: Keypair }> {
  const keypair = Keypair.fromSecretKey(secretKey);
  const publicKey = keypair.publicKey.toBase58();

  const stored: StoredSessionWalletV1 = {
    publicKey,
    encryptedSecret: await encryptSecretKey(keypair.secretKey, mainWallet),
    mainWallet,
    createdAt,
    derivation,
  };

  persistStoredWalletV1(stored);
  return { publicKey, keypair };
}

/**
 * Generate a new session keypair and store encrypted in sessionStorage.
 */
export async function createSessionWallet(mainWallet: string): Promise<{
  publicKey: string;
  keypair: Keypair;
}> {
  const keypair = Keypair.generate();
  const pubkey = keypair.publicKey.toBase58();

  const stored: StoredSessionWalletV1 = {
    publicKey: pubkey,
    encryptedSecret: await encryptSecretKey(keypair.secretKey, mainWallet),
    mainWallet,
    createdAt: Date.now(),
    derivation: 'random',
  };

  persistStoredWalletV1(stored);

  return { publicKey: pubkey, keypair };
}

/**
 * Load the session keypair from sessionStorage (no Phantom required).
 * Returns null if no session exists or decryption fails.
 */
export async function loadSessionWalletFromStorage(options?: {
  mainWallet?: string;
  allowBackupFallback?: boolean;
}): Promise<{ keypair: Keypair; publicKey: string; mainWallet: string; createdAt: number } | null> {
  const scopedMainWallet = String(options?.mainWallet || '').trim();
  const allowBackupFallback = options?.allowBackupFallback === true;
  // Try sessionStorage first (current session), then localStorage (persisted across sessions)
  const sources: Array<{ storage: Storage | undefined; key: string }> = [
    { storage: typeof sessionStorage !== 'undefined' ? sessionStorage : undefined, key: SESSION_KEY },
    { storage: typeof localStorage !== 'undefined' ? localStorage : undefined, key: PERSISTENT_KEY },
  ];

  for (const { storage, key } of sources) {
    if (!storage) continue;
    const raw = storage.getItem(key);
    if (!raw) continue;

    try {
      const stored = JSON.parse(raw) as StoredSessionWalletV1;
      if (!stored?.encryptedSecret || !stored?.mainWallet || !stored?.publicKey) continue;
      if (scopedMainWallet && String(stored.mainWallet) !== scopedMainWallet) continue;
      const result = await decodeStoredWalletV1(stored);
      if (!result) continue;

      // If recovered from localStorage, also restore to sessionStorage
      if (key === PERSISTENT_KEY && typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem(SESSION_KEY, raw);
      }

      return result;
    } catch {
      continue;
    }
  }

  // Optional fallback: recover from newest per-pubkey backup.
  // Disabled by default to avoid silently binding a prior wallet to a different main wallet.
  if (allowBackupFallback && typeof localStorage !== 'undefined') {
    let best: StoredSessionWalletV1 | null = null;
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith(WALLET_BY_PUBKEY_PREFIX)) continue;
      const raw = localStorage.getItem(k);
      if (!raw) continue;
      try {
        const stored = JSON.parse(raw) as StoredSessionWalletV1;
        if (!stored?.encryptedSecret || !stored?.mainWallet || !stored?.publicKey) continue;
        if (scopedMainWallet && String(stored.mainWallet) !== scopedMainWallet) continue;
        if (!best || Number(stored.createdAt || 0) > Number(best.createdAt || 0)) best = stored;
      } catch {
        continue;
      }
    }
    if (best) {
      const decoded = await decodeStoredWalletV1(best);
      if (decoded) {
        // Restore active pointers for convenience.
        persistStoredWalletV1(best);
        return decoded;
      }
    }
  }

  return null;
}

/**
 * Load a specific session wallet by its public key.
 * This is critical for recovering "expired" session wallets that still have funds,
 * even if the active session pointer was replaced.
 */
export async function loadSessionWalletByPublicKey(
  publicKey: string,
  options?: { mainWallet?: string },
): Promise<{ keypair: Keypair; publicKey: string; mainWallet: string; createdAt: number } | null> {
  const scopedMainWallet = String(options?.mainWallet || '').trim();
  const keysToCheck: Array<{ storage: Storage | undefined; key: string }> = [
    { storage: typeof localStorage !== 'undefined' ? localStorage : undefined, key: keyForPubkey(publicKey) },
    { storage: typeof sessionStorage !== 'undefined' ? sessionStorage : undefined, key: keyForPubkey(publicKey) },
    { storage: typeof sessionStorage !== 'undefined' ? sessionStorage : undefined, key: SESSION_KEY },
    { storage: typeof localStorage !== 'undefined' ? localStorage : undefined, key: PERSISTENT_KEY },
  ];

  for (const { storage, key } of keysToCheck) {
    if (!storage) continue;
    const raw = storage.getItem(key);
    if (!raw) continue;
    try {
      const stored = JSON.parse(raw) as StoredSessionWalletV1;
      if (!stored?.encryptedSecret || !stored?.mainWallet || !stored?.publicKey) continue;
      if (String(stored.publicKey) !== publicKey) continue;
      if (scopedMainWallet && String(stored.mainWallet) !== scopedMainWallet) continue;
      const decoded = await decodeStoredWalletV1(stored);
      if (!decoded) continue;
      // Restore active pointers for convenience.
      persistStoredWalletV1(stored);
      return decoded;
    } catch {
      continue;
    }
  }

  return null;
}

export function listStoredSessionWallets(): Array<{ publicKey: string; mainWallet: string; createdAt: number }> {
  const out: Array<{ publicKey: string; mainWallet: string; createdAt: number }> = [];
  const seen = new Set<string>();

  const add = (stored: any) => {
    const pk = String(stored?.publicKey || '');
    if (!pk || seen.has(pk)) return;
    const mw = String(stored?.mainWallet || '');
    const createdAt = Number(stored?.createdAt || 0);
    if (!mw) return;
    seen.add(pk);
    out.push({ publicKey: pk, mainWallet: mw, createdAt });
  };

  // LocalStorage: all known backups.
  if (typeof localStorage !== 'undefined') {
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (!k || !k.startsWith(WALLET_BY_PUBKEY_PREFIX)) continue;
      const raw = localStorage.getItem(k);
      if (!raw) continue;
      try { add(JSON.parse(raw)); } catch {}
    }

    try {
      const raw = localStorage.getItem(PERSISTENT_KEY);
      if (raw) add(JSON.parse(raw));
    } catch {}
  }

  // SessionStorage: active session pointer (if any).
  if (typeof sessionStorage !== 'undefined') {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (raw) add(JSON.parse(raw));
    } catch {}
  }

  // Newest first
  out.sort((a, b) => (b.createdAt || 0) - (a.createdAt || 0));
  return out;
}

/**
 * Best-effort recovery: scan browser storage for older keys/records that look like session wallets.
 * If found, restore into canonical keys and per-pubkey backups.
 */
export async function recoverSessionWalletFromAnyStorage(
  targetPublicKey?: string,
): Promise<{ keypair: Keypair; publicKey: string; mainWallet: string; createdAt: number } | null> {
  const storages: Array<Storage | undefined> = [
    typeof sessionStorage !== 'undefined' ? sessionStorage : undefined,
    typeof localStorage !== 'undefined' ? localStorage : undefined,
  ];

  for (const storage of storages) {
    if (!storage) continue;
    for (let i = 0; i < storage.length; i++) {
      const k = storage.key(i);
      if (!k) continue;
      const raw = storage.getItem(k);
      if (!raw || raw.length < 20) continue;
      // Fast filter to avoid JSON.parse on huge/unrelated blobs.
      if (!raw.includes('publicKey') || (!raw.includes('encryptedSecret') && !raw.includes('secretKey'))) continue;

      try {
        const parsed = JSON.parse(raw) as any;
        const pk = String(parsed?.publicKey || '');
        if (!pk) continue;
        if (targetPublicKey && pk !== targetPublicKey) continue;

        // Current format: encryptedSecret + mainWallet
        if (typeof parsed?.encryptedSecret === 'string' && typeof parsed?.mainWallet === 'string') {
          const stored: StoredSessionWalletV1 = {
            publicKey: pk,
            encryptedSecret: parsed.encryptedSecret,
            mainWallet: String(parsed.mainWallet),
            createdAt: Number(parsed.createdAt || Date.now()),
          };
          const decoded = await decodeStoredWalletV1(stored);
          if (!decoded) continue;
          persistStoredWalletV1(stored);
          return decoded;
        }

        // Older format: secretKey array (Uint8Array serialized) + mainWallet
        if (Array.isArray(parsed?.secretKey) && typeof parsed?.mainWallet === 'string') {
          const secretKey = Uint8Array.from(parsed.secretKey.map((n: any) => Number(n)));
          const keypair = Keypair.fromSecretKey(secretKey);
          const derivedPk = keypair.publicKey.toBase58();
          if (derivedPk !== pk) continue;
          const stored: StoredSessionWalletV1 = {
            publicKey: pk,
            encryptedSecret: await encryptSecretKey(secretKey, String(parsed.mainWallet)),
            mainWallet: String(parsed.mainWallet),
            createdAt: Number(parsed.createdAt || Date.now()),
          };
          persistStoredWalletV1(stored);
          return {
            keypair,
            publicKey: pk,
            mainWallet: stored.mainWallet,
            createdAt: stored.createdAt,
          };
        }
      } catch {
        continue;
      }
    }
  }

  return null;
}

/**
 * Destroy the session wallet (clear from sessionStorage).
 */
export function destroySessionWallet(): void {
  if (typeof sessionStorage !== 'undefined') {
    sessionStorage.removeItem(SESSION_KEY);
  }
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(PERSISTENT_KEY);
  }
}

/**
 * Clear only the active session wallet pointer keys.
 * Keeps per-pubkey encrypted backups intact for explicit recovery/import flows.
 */
export function clearActiveSessionPointer(): void {
  if (typeof sessionStorage !== 'undefined') {
    try { sessionStorage.removeItem(SESSION_KEY); } catch {}
  }
  if (typeof localStorage !== 'undefined') {
    try { localStorage.removeItem(PERSISTENT_KEY); } catch {}
  }
}

/**
 * Check if a session wallet exists for this main wallet.
 */
export function hasSessionWallet(mainWallet: string): boolean {
  // Check both sessionStorage and localStorage
  for (const [storage, key] of [
    [typeof sessionStorage !== 'undefined' ? sessionStorage : null, SESSION_KEY],
    [typeof localStorage !== 'undefined' ? localStorage : null, PERSISTENT_KEY],
  ] as const) {
    if (!storage) continue;
    const raw = (storage as Storage).getItem(key as string);
    if (!raw) continue;
    try {
      if (JSON.parse(raw).mainWallet === mainWallet) return true;
    } catch {
      continue;
    }
  }
  return false;
}

// ─── Transaction Helpers ───

/**
 * Get the SOL balance of the session wallet.
 */
export async function getSessionBalance(publicKey: string): Promise<number> {
  const connection = getConnection();
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
  const connection = getConnection();
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

type ClosableTokenAccount = {
  pubkey: PublicKey;
  lamports: number;
  programId: PublicKey;
};

function buildCloseTokenAccountIx(
  tokenAccount: PublicKey,
  destination: PublicKey,
  owner: PublicKey,
  programId: PublicKey,
): TransactionInstruction {
  return new TransactionInstruction({
    programId,
    keys: [
      { pubkey: tokenAccount, isSigner: false, isWritable: true },
      { pubkey: destination, isSigner: false, isWritable: true },
      { pubkey: owner, isSigner: true, isWritable: false },
    ],
    data: SPL_CLOSE_ACCOUNT_INSTRUCTION,
  });
}

function chunkArray<T>(items: T[], size: number): T[][] {
  const out: T[][] = [];
  for (let i = 0; i < items.length; i += size) {
    out.push(items.slice(i, i + size));
  }
  return out;
}

function toPublicKey(value: unknown): PublicKey | null {
  try {
    if (value && typeof (value as any).toBase58 === 'function') return value as PublicKey;
    return new PublicKey(String(value || ''));
  } catch {
    return null;
  }
}

function parseTokenAmount(entry: any): string {
  const amount = entry?.account?.data?.parsed?.info?.tokenAmount?.amount;
  return typeof amount === 'string' ? amount : '0';
}

async function fetchClosableTokenAccounts(
  connection: Connection,
  owner: PublicKey,
): Promise<{ closable: ClosableTokenAccount[]; nonZeroAccounts: number }> {
  const settled = await Promise.allSettled([
    connection.getParsedTokenAccountsByOwner(owner, { programId: SPL_TOKEN_PROGRAM_ID }),
    connection.getParsedTokenAccountsByOwner(owner, { programId: SPL_TOKEN_2022_PROGRAM_ID }),
  ]);

  const closable: ClosableTokenAccount[] = [];
  let nonZeroAccounts = 0;

  const ingest = (result: any, programId: PublicKey) => {
    const rows = Array.isArray(result?.value) ? result.value : [];
    for (const row of rows) {
      const tokenAccount = toPublicKey(row?.pubkey);
      if (!tokenAccount) continue;
      const amountRaw = parseTokenAmount(row);
      if (amountRaw === '0') {
        closable.push({
          pubkey: tokenAccount,
          lamports: Math.max(0, Number(row?.account?.lamports || 0)),
          programId,
        });
      } else {
        nonZeroAccounts += 1;
      }
    }
  };

  if (settled[0]?.status === 'fulfilled') ingest(settled[0].value, SPL_TOKEN_PROGRAM_ID);
  if (settled[1]?.status === 'fulfilled') ingest(settled[1].value, SPL_TOKEN_2022_PROGRAM_ID);

  return { closable, nonZeroAccounts };
}

/**
 * Close zero-balance SPL token accounts and reclaim their rent into destination.
 * Non-zero token accounts are intentionally skipped.
 */
export async function closeEmptyTokenAccounts(
  sessionKeypair: Keypair,
  destinationWallet?: string,
): Promise<SessionWalletCleanupResult> {
  const connection = getConnection();
  const owner = sessionKeypair.publicKey;
  const destination = destinationWallet ? new PublicKey(destinationWallet) : owner;
  const { closable, nonZeroAccounts } = await fetchClosableTokenAccounts(connection, owner);

  if (closable.length === 0) {
    return {
      closedTokenAccounts: 0,
      failedToCloseTokenAccounts: 0,
      skippedNonZeroTokenAccounts: nonZeroAccounts,
      reclaimedLamports: 0,
      closeSignatures: [],
    };
  }

  let closedTokenAccounts = 0;
  let failedToCloseTokenAccounts = 0;
  let reclaimedLamports = 0;
  const closeSignatures: string[] = [];
  const chunks = chunkArray(closable, TOKEN_ACCOUNT_CLOSE_CHUNK);

  for (const batch of chunks) {
    try {
      const instructions = batch.map((acc) =>
        buildCloseTokenAccountIx(acc.pubkey, destination, owner, acc.programId),
      );
      const blockhash = await connection.getLatestBlockhash('confirmed');
      const messageV0 = new TransactionMessage({
        payerKey: owner,
        recentBlockhash: blockhash.blockhash,
        instructions,
      }).compileToV0Message();
      const tx = new VersionedTransaction(messageV0);
      tx.sign([sessionKeypair]);

      const sig = await connection.sendRawTransaction(tx.serialize(), {
        skipPreflight: false,
        preflightCommitment: 'confirmed',
        maxRetries: 3,
      });

      const status = await waitForSignatureStatus(connection, sig, { maxWaitMs: 45_000, pollMs: 2500 });
      if (status.state === 'failed') {
        failedToCloseTokenAccounts += batch.length;
        continue;
      }

      closeSignatures.push(sig);
      closedTokenAccounts += batch.length;
      reclaimedLamports += batch.reduce((sum, acc) => sum + Math.max(0, acc.lamports), 0);
    } catch {
      failedToCloseTokenAccounts += batch.length;
    }
  }

  return {
    closedTokenAccounts,
    failedToCloseTokenAccounts,
    skippedNonZeroTokenAccounts: nonZeroAccounts,
    reclaimedLamports,
    closeSignatures,
  };
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
  console.log('[sweepToMainWallet] Session pubkey:', sessionKeypair.publicKey.toBase58());
  const connection = getConnection();
  const balance = await connection.getBalance(sessionKeypair.publicKey);
  console.log('[sweepToMainWallet] Balance:', balance, 'lamports (', balance / LAMPORTS_PER_SOL, 'SOL)');

  // Solana accounts must either be at 0 lamports (closed) or above rent-exempt
  // minimum (~890,880 lamports). A simple transfer has 1 signature = 5,000 lamports fee.
  // Transfer (balance - 5000) so the account closes to exactly 0 after the fee.
  const BASE_FEE_LAMPORTS = 5_000;
  const sweepAmount = balance - BASE_FEE_LAMPORTS;
  if (sweepAmount <= 0) {
    console.log('[sweepToMainWallet] Balance too low. Need >', BASE_FEE_LAMPORTS, 'lamports, have', balance);
    return null;
  }
  console.log('[sweepToMainWallet] Sweeping', sweepAmount, 'lamports to', mainWallet, '(fee:', BASE_FEE_LAMPORTS, '→ account closes to 0)');

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

  // Confirm so the UI can reliably refresh balances immediately after sweep.
  try {
    await waitForSignatureStatus(connection, sig, { maxWaitMs: 60_000, pollMs: 2500 });
  } catch {
    // If confirmation fails/times out, return the signature anyway.
  }

  return sig;
}

/**
 * Full sweep-back routine:
 * 1) close empty token accounts and reclaim rent,
 * 2) sweep remaining SOL to the main wallet.
 */
export async function sweepToMainWalletAndCloseTokenAccounts(
  sessionKeypair: Keypair,
  mainWallet: string,
): Promise<SessionWalletSweepResult> {
  const cleanup = await closeEmptyTokenAccounts(sessionKeypair, mainWallet);
  const sweepSignature = await sweepToMainWallet(sessionKeypair, mainWallet);
  return {
    ...cleanup,
    sweepSignature,
  };
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
  const connection = getConnection();
  const balance = await connection.getBalance(sessionKeypair.publicKey);

  // Keep a reserve + fee for this sweep tx. Reserve must stay above rent-exempt (~890,880)
  // or the account will fail simulation. Add rent-exempt buffer to be safe.
  const BASE_FEE_LAMPORTS = 5_000;
  const RENT_EXEMPT_MINIMUM = 890_880;
  const reserveLamports = Math.floor(Math.max(0, reserveSol) * LAMPORTS_PER_SOL);
  const keepLamports = Math.max(reserveLamports, RENT_EXEMPT_MINIMUM) + BASE_FEE_LAMPORTS;
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

  try {
    await waitForSignatureStatus(connection, sig, { maxWaitMs: 60_000, pollMs: 2500 });
  } catch {
    // If confirmation fails/times out, return the signature anyway.
  }

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

// ─── Auto-Sweep on Page Unload (WALLET-01 + Phase 2.3 hardening) ───

/**
 * Fire-and-forget sweep — builds and sends the sweep transaction WITHOUT awaiting
 * confirmation. Critical for beforeunload/pagehide where the browser won't wait
 * for async operations. Uses a 5-second timeout to prevent hanging on slow RPC.
 *
 * If sweep fails (network, timeout, etc.), the wallet key persists in localStorage
 * and can be recovered via FundRecoveryBanner on next visit.
 */
export async function sweepToMainWalletFireAndForget(
  sessionKeypair: Keypair,
  mainWallet: string,
): Promise<void> {
  try {
    const connection = getConnection();

    // beforeunload/pagehide won't wait for slow RPC. Use a short timeout per call, but
    // always clear timers to avoid late unhandled rejections that can wedge the UI.
    const TIMEOUT_MS = 5_000;

    const balance = await withTimeout(
      connection.getBalance(sessionKeypair.publicKey),
      TIMEOUT_MS,
      'sweep timeout (balance)',
    );

    const FEE_BUFFER_LAMPORTS = 5_000; // Close account to 0 (avoids rent-exempt error)
    const sweepAmount = balance - FEE_BUFFER_LAMPORTS;
    if (sweepAmount <= 0) return;

    const blockhash = await withTimeout(
      connection.getLatestBlockhash('confirmed'),
      TIMEOUT_MS,
      'sweep timeout (blockhash)',
    );

    const instruction = SystemProgram.transfer({
      fromPubkey: sessionKeypair.publicKey,
      toPubkey: new PublicKey(mainWallet),
      lamports: sweepAmount,
    });

    const messageV0 = new TransactionMessage({
      payerKey: sessionKeypair.publicKey,
      recentBlockhash: blockhash.blockhash,
      instructions: [instruction],
    }).compileToV0Message();

    const tx = new VersionedTransaction(messageV0);
    tx.sign([sessionKeypair]);

    // Fire and forget — do NOT await confirmation.
    // In beforeunload context, the browser may kill the page before confirm resolves.
    connection.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      preflightCommitment: 'confirmed',
    }).catch(() => {
      // Silently fail — wallet key persists in localStorage for recovery
    });
  } catch {
    // Silently fail — wallet key persists in localStorage for recovery
  }
}

/**
 * Register event handlers that sweep all funds back to the main wallet when
 * the tab closes or goes hidden.
 *
 * Uses fire-and-forget sweep (no await) for reliability in beforeunload.
 * Also listens to visibilitychange (more reliable on mobile browsers).
 * Pre-fetches blockhash every 30s to minimize async work at teardown time.
 *
 * Call this once when the session wallet is activated.
 * The sweep is best-effort: if the network is down, funds remain in the
 * persistent wallet (localStorage) and can be recovered on next visit.
 */
export function registerAutoSweep(sessionKeypair: Keypair, mainWallet: string): () => void {
  // Pre-fetch a blockhash so the teardown handler has less async work
  const refreshBlockhash = async () => {
    try {
      const connection = getConnection();
      await connection.getLatestBlockhash('confirmed');
    } catch { /* ignore */ }
  };
  refreshBlockhash();
  const refreshInterval = setInterval(refreshBlockhash, 30_000);

  const handler = () => {
    // Fire-and-forget: don't await
    sweepToMainWalletFireAndForget(sessionKeypair, mainWallet).catch(() => {});
  };

  const visibilityHandler = () => {
    if (document.visibilityState === 'hidden') {
      handler();
    }
  };

  window.addEventListener('beforeunload', handler);
  window.addEventListener('pagehide', handler);
  window.addEventListener('visibilitychange', visibilityHandler);

  // Return cleanup function
  return () => {
    clearInterval(refreshInterval);
    window.removeEventListener('beforeunload', handler);
    window.removeEventListener('pagehide', handler);
    window.removeEventListener('visibilitychange', visibilityHandler);
  };
}

/**
 * Check if there's a persisted wallet with funds that needs recovery.
 * Call this on app startup to detect abandoned session wallets.
 */
export async function checkForRecoverableWallet(): Promise<{
  publicKey: string;
  mainWallet: string;
  balanceSol: number;
  createdAt: number;
} | null> {
  const wallet = await loadSessionWalletFromStorage({ allowBackupFallback: true });
  if (!wallet) return null;

  try {
    const balance = await getSessionBalance(wallet.publicKey);
    if (balance > 0.001) {
      return {
        publicKey: wallet.publicKey,
        mainWallet: wallet.mainWallet,
        balanceSol: balance,
        createdAt: wallet.createdAt,
      };
    }
  } catch {
    // RPC error — can't check balance
  }
  return null;
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

// ─── Key Backup / Export ───

/**
 * Export the session wallet private key as a downloadable text file.
 * The file contains the JSON array format (compatible with Solana CLI,
 * Phantom "Import Private Key", and other wallets).
 *
 * **CRITICAL SAFETY FEATURE:** Users must NEVER lose access to funded wallets.
 * This function triggers a browser file download so users have an offline backup
 * of their session wallet key.
 */
export function exportSessionKeyAsFile(keypair: Keypair, publicKey: string): void {
  const secretBytes = Array.from(keypair.secretKey);
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

  const content = [
    '=== JARVIS SESSION WALLET BACKUP ===',
    `Date: ${new Date().toISOString()}`,
    `Public Key: ${publicKey}`,
    '',
    'IMPORTANT: This file contains your private key.',
    'Anyone with this file can access the funds in this wallet.',
    'Store it safely and delete it after sweeping funds back.',
    '',
    '--- Private Key (JSON array — use with Solana CLI / import tools) ---',
    JSON.stringify(secretBytes),
    '',
    '--- Public Key (for reference) ---',
    publicKey,
    '',
    '=== END BACKUP ===',
  ].join('\n');

  const filename = `jarvis-session-wallet-${publicKey.slice(0, 8)}-${timestamp}.txt`;

  // Method 1: Anchor-click download (works when called from direct user gesture)
  try {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    // Defer cleanup — revoking immediately can abort the download in Firefox
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 1000);
    return;
  } catch {
    // Fall through to method 2
  }

  // Method 2: data-URI fallback (works even when user gesture context is lost)
  try {
    const dataUri = 'data:text/plain;charset=utf-8,' + encodeURIComponent(content);
    const a = document.createElement('a');
    a.href = dataUri;
    a.download = filename;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => document.body.removeChild(a), 1000);
  } catch (err) {
    console.error('[SessionWallet] All download methods failed:', err);
  }
}

/**
 * Export the current active session wallet key as a downloadable file.
 * Returns true if the key was found and download triggered, false otherwise.
 */
export async function downloadCurrentSessionKey(): Promise<boolean> {
  const wallet = await loadSessionWalletFromStorage({ allowBackupFallback: true });
  if (!wallet) return false;
  exportSessionKeyAsFile(wallet.keypair, wallet.publicKey);
  return true;
}

/**
 * Export a specific session wallet by public key as a downloadable file.
 * Returns true if the key was found and download triggered, false otherwise.
 */
export async function downloadSessionKeyByPubkey(publicKey: string): Promise<boolean> {
  const wallet = await loadSessionWalletByPublicKey(publicKey);
  if (!wallet) return false;
  exportSessionKeyAsFile(wallet.keypair, wallet.publicKey);
  return true;
}
