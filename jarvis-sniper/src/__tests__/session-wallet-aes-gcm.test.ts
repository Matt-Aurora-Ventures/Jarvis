/**
 * Tests for AES-256-GCM encryption in session-wallet.ts
 *
 * Validates:
 * 1. encryptSecretKey / decryptSecretKey round-trip with AES-GCM
 * 2. Legacy XOR ciphertext is still decryptable (backward compat)
 * 3. AES-GCM ciphertext is non-deterministic (different salt/iv each call)
 * 4. Async API surface: all wallet-loading functions return Promises
 * 5. createSessionWallet and importSessionWalletSecretKey are async
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Buffer } from 'buffer';

// We need to mock @solana/web3.js since it has native deps that won't load in Node vitest
vi.mock('@solana/web3.js', () => {
  // Minimal Keypair mock that supports fromSecretKey and generate
  class MockKeypair {
    secretKey: Uint8Array;
    publicKey: { toBase58: () => string };

    constructor(secretKey: Uint8Array) {
      this.secretKey = secretKey;
      // Deterministic "public key" derived from first 8 bytes for test identity
      const pkHex = Buffer.from(secretKey.slice(0, 8)).toString('hex');
      this.publicKey = { toBase58: () => `mock_pk_${pkHex}` };
    }

    static fromSecretKey(sk: Uint8Array) {
      return new MockKeypair(sk);
    }

    static fromSeed(seed: Uint8Array) {
      // Expand 32-byte seed to 64-byte "secret key" (ed25519 convention)
      const expanded = new Uint8Array(64);
      expanded.set(seed, 0);
      expanded.set(seed, 32);
      return new MockKeypair(expanded);
    }

    static generate() {
      // Random 64-byte secret key
      const sk = new Uint8Array(64);
      if (typeof crypto !== 'undefined' && crypto.getRandomValues) {
        crypto.getRandomValues(sk);
      } else {
        for (let i = 0; i < 64; i++) sk[i] = Math.floor(Math.random() * 256);
      }
      return new MockKeypair(sk);
    }
  }

  return {
    Keypair: MockKeypair,
    Connection: vi.fn(),
    PublicKey: vi.fn((s: string) => ({ toBase58: () => s })),
    Transaction: vi.fn(),
    SystemProgram: { transfer: vi.fn() },
    VersionedTransaction: vi.fn(),
    LAMPORTS_PER_SOL: 1_000_000_000,
    TransactionMessage: vi.fn(),
  };
});

// Mock browser storage
const storageMap = new Map<string, string>();
const mockStorage = {
  getItem: (key: string) => storageMap.get(key) ?? null,
  setItem: (key: string, value: string) => storageMap.set(key, value),
  removeItem: (key: string) => storageMap.delete(key),
  key: (i: number) => Array.from(storageMap.keys())[i] ?? null,
  get length() { return storageMap.size; },
  clear: () => storageMap.clear(),
};

vi.stubGlobal('sessionStorage', mockStorage);
vi.stubGlobal('localStorage', mockStorage);

describe('AES-256-GCM session wallet encryption', () => {
  beforeEach(() => {
    storageMap.clear();
  });

  it('encryptSecretKey returns a Promise (async API)', async () => {
    // Dynamic import after mocks are set up
    const mod = await import('@/lib/session-wallet');

    // If encryptSecretKey is not exported directly, test through createSessionWallet
    // The key indicator is that createSessionWallet must be async now
    const result = mod.createSessionWallet('FakeMainWallet1111111111111111111111111111111');
    // Must return a Promise (async function)
    expect(result).toBeInstanceOf(Promise);
  });

  it('createSessionWallet returns a Promise with publicKey and keypair', async () => {
    const mod = await import('@/lib/session-wallet');
    const result = await mod.createSessionWallet('FakeMainWallet1111111111111111111111111111111');
    expect(result).toHaveProperty('publicKey');
    expect(result).toHaveProperty('keypair');
    expect(typeof result.publicKey).toBe('string');
    expect(result.publicKey.length).toBeGreaterThan(0);
  });

  it('importSessionWalletSecretKey returns a Promise', async () => {
    const mod = await import('@/lib/session-wallet');
    const fakeSecret = new Uint8Array(64);
    crypto.getRandomValues(fakeSecret);
    const result = mod.importSessionWalletSecretKey(
      fakeSecret,
      'FakeMainWallet1111111111111111111111111111111',
    );
    expect(result).toBeInstanceOf(Promise);
  });

  it('loadSessionWalletFromStorage returns a Promise', async () => {
    const mod = await import('@/lib/session-wallet');
    // First create a wallet so there's something to load
    await mod.createSessionWallet('FakeMainWallet1111111111111111111111111111111');
    const result = mod.loadSessionWalletFromStorage();
    expect(result).toBeInstanceOf(Promise);
  });

  it('loadSessionWalletByPublicKey returns a Promise', async () => {
    const mod = await import('@/lib/session-wallet');
    const created = await mod.createSessionWallet('FakeMainWallet1111111111111111111111111111111');
    const result = mod.loadSessionWalletByPublicKey(created.publicKey);
    expect(result).toBeInstanceOf(Promise);
  });

  it('recoverSessionWalletFromAnyStorage returns a Promise', async () => {
    const mod = await import('@/lib/session-wallet');
    const result = mod.recoverSessionWalletFromAnyStorage();
    expect(result).toBeInstanceOf(Promise);
  });

  it('deterministic derivation is stable for same wallet + signature', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';
    const signature = Uint8Array.from(Array.from({ length: 64 }, (_, i) => i));

    const d1 = await mod.deriveDeterministicSessionWallet(mainWallet, signature);
    const d2 = await mod.deriveDeterministicSessionWallet(mainWallet, signature);

    expect(d1.publicKey).toBe(d2.publicKey);
    expect(Array.from(d1.keypair.secretKey)).toEqual(Array.from(d2.keypair.secretKey));
  });

  it('deterministic derivation changes when main wallet changes', async () => {
    const mod = await import('@/lib/session-wallet');
    const signature = Uint8Array.from(Array.from({ length: 64 }, (_, i) => i));

    const a = await mod.deriveDeterministicSessionWallet(
      'FakeMainWallet1111111111111111111111111111111',
      signature,
    );
    const b = await mod.deriveDeterministicSessionWallet(
      'AnotherWallet11111111111111111111111111111111',
      signature,
    );

    expect(a.publicKey).not.toBe(b.publicKey);
  });

  it('round-trips: decrypt(encrypt(secretKey)) === secretKey', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';

    // Create a wallet, which internally encrypts
    const created = await mod.createSessionWallet(mainWallet);
    const originalSecret = Array.from(created.keypair.secretKey);

    // Load it back (internally decrypts)
    const loaded = await mod.loadSessionWalletFromStorage();
    expect(loaded).not.toBeNull();
    expect(Array.from(loaded!.keypair.secretKey)).toEqual(originalSecret);
  });

  it('AES-GCM ciphertext is non-deterministic (different each call)', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';
    const fakeSecret = new Uint8Array(64);
    crypto.getRandomValues(fakeSecret);

    // Create two wallets with the same secret key
    const imported1 = await mod.importSessionWalletSecretKey(fakeSecret, mainWallet);
    const raw1 = storageMap.get('__jarvis_wallet_persistent');

    storageMap.clear();
    const imported2 = await mod.importSessionWalletSecretKey(fakeSecret, mainWallet);
    const raw2 = storageMap.get('__jarvis_wallet_persistent');

    // The encrypted blobs must differ (random salt + iv)
    expect(raw1).toBeTruthy();
    expect(raw2).toBeTruthy();
    const enc1 = JSON.parse(raw1!).encryptedSecret;
    const enc2 = JSON.parse(raw2!).encryptedSecret;
    expect(enc1).not.toEqual(enc2);
  });

  it('AES-GCM ciphertext is larger than legacy XOR (108+ bytes vs 64)', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';
    const created = await mod.createSessionWallet(mainWallet);

    const raw = storageMap.get('__jarvis_wallet_persistent');
    expect(raw).toBeTruthy();
    const encryptedSecret = JSON.parse(raw!).encryptedSecret;
    const decoded = Buffer.from(encryptedSecret, 'base64');
    // AES-GCM: 16 (salt) + 12 (iv) + 64 (data) + 16 (tag) = 108 bytes
    expect(decoded.length).toBeGreaterThanOrEqual(108);
  });

  it('backward compat: decrypts legacy XOR-encoded secret keys', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';

    // Manually produce a legacy XOR-encrypted blob
    const fakeSecret = new Uint8Array(64);
    crypto.getRandomValues(fakeSecret);
    const key = new TextEncoder().encode(mainWallet.padEnd(64, '0').slice(0, 64));
    const xorEncrypted = new Uint8Array(fakeSecret.length);
    for (let i = 0; i < fakeSecret.length; i++) {
      xorEncrypted[i] = fakeSecret[i] ^ key[i % key.length];
    }
    const legacyBase64 = Buffer.from(xorEncrypted).toString('base64');

    // Simulate what was in storage: a mock Keypair from this secret
    const { Keypair } = await import('@solana/web3.js');
    const kp = Keypair.fromSecretKey(fakeSecret);
    const publicKey = kp.publicKey.toBase58();

    const legacyStored = JSON.stringify({
      publicKey,
      encryptedSecret: legacyBase64,
      mainWallet,
      createdAt: Date.now(),
    });

    storageMap.set('__jarvis_wallet_persistent', legacyStored);
    storageMap.set('__jarvis_session_wallet', legacyStored);

    // loadSessionWalletFromStorage should transparently decrypt legacy XOR
    const loaded = await mod.loadSessionWalletFromStorage();
    expect(loaded).not.toBeNull();
    expect(loaded!.publicKey).toBe(publicKey);
    expect(Array.from(loaded!.keypair.secretKey)).toEqual(Array.from(fakeSecret));
  });

  it('downloadSessionKeyByPubkey is async', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';
    const created = await mod.createSessionWallet(mainWallet);

    // downloadSessionKeyByPubkey should now be async
    const result = mod.downloadSessionKeyByPubkey(created.publicKey);
    expect(result).toBeInstanceOf(Promise);
  });

  it('downloadCurrentSessionKey is async', async () => {
    const mod = await import('@/lib/session-wallet');
    const mainWallet = 'FakeMainWallet1111111111111111111111111111111';
    await mod.createSessionWallet(mainWallet);

    const result = mod.downloadCurrentSessionKey();
    expect(result).toBeInstanceOf(Promise);
  });

  it('checkForRecoverableWallet is still async (already was)', async () => {
    const mod = await import('@/lib/session-wallet');
    const result = mod.checkForRecoverableWallet();
    expect(result).toBeInstanceOf(Promise);
  });
});
