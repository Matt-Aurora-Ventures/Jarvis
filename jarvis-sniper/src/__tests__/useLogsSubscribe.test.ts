import { describe, it, expect } from 'vitest';

/**
 * Unit tests for the logsSubscribe hook's core logic: extractMintFromLogs and base58Encode.
 * These are tested as pure functions extracted from useLogsSubscribe.
 * The hook itself (React effect + WebSocket lifecycle) is best tested via integration/E2E.
 */

// Re-implement the pure functions from useLogsSubscribe for unit testing.
// The hook file doesn't export them, so we test the logic directly.

const ALPHABET = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';

function base58Encode(bytes: Uint8Array): string {
  const ZERO = BigInt(0);
  const BASE = BigInt(58);
  const BYTE = BigInt(256);
  let num = ZERO;
  for (const b of bytes) {
    num = num * BYTE + BigInt(b);
  }
  let str = '';
  while (num > ZERO) {
    const rem = Number(num % BASE);
    num = num / BASE;
    str = ALPHABET[rem] + str;
  }
  for (const b of bytes) {
    if (b !== 0) break;
    str = '1' + str;
  }
  return str;
}

function extractMintFromLogs(logs: string[]): string | null {
  const createIdx = logs.findIndex(
    (l) => l.includes('Instruction: Create') || l.includes('Program log: Create'),
  );
  if (createIdx === -1) return null;

  for (let i = createIdx + 1; i < logs.length; i++) {
    const line = logs[i];
    if (line.startsWith('Program data:')) {
      try {
        const b64 = line.slice('Program data: '.length).trim();
        const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
        if (bytes.length >= 32) {
          return base58Encode(bytes.slice(0, 32));
        }
      } catch {
        // skip
      }
    }
    if (line.includes('Instruction:') && i !== createIdx) break;
  }

  return null;
}

describe('base58Encode', () => {
  it('encodes a known 32-byte public key correctly', () => {
    // All zeros should encode to "1" repeated (leading zero bytes)
    const zeros = new Uint8Array(32);
    const result = base58Encode(zeros);
    expect(result).toBe('1'.repeat(32));
  });

  it('encodes non-zero bytes', () => {
    const bytes = new Uint8Array(32);
    bytes[31] = 1; // Smallest non-zero value
    const result = base58Encode(bytes);
    expect(result.length).toBeGreaterThan(0);
    // Should start with leading '1's for the 31 zero bytes
    expect(result.startsWith('1'.repeat(31))).toBe(true);
  });

  it('produces only valid base58 characters', () => {
    const bytes = new Uint8Array(32);
    for (let i = 0; i < 32; i++) bytes[i] = i * 8;
    const result = base58Encode(bytes);
    for (const ch of result) {
      expect(ALPHABET).toContain(ch);
    }
  });
});

describe('extractMintFromLogs', () => {
  it('returns null when no Create instruction found', () => {
    const logs = [
      'Program log: Transfer',
      'Program data: abc123',
    ];
    expect(extractMintFromLogs(logs)).toBeNull();
  });

  it('returns null when Create found but no Program data follows', () => {
    const logs = [
      'Program log: Instruction: Create',
      'Program log: Success',
    ];
    expect(extractMintFromLogs(logs)).toBeNull();
  });

  it('extracts mint from valid Program data after Create instruction', () => {
    // Create 32 bytes of known data, then base64 encode it
    const mintBytes = new Uint8Array(32);
    for (let i = 0; i < 32; i++) mintBytes[i] = i + 1;
    const b64 = btoa(String.fromCharCode(...mintBytes));

    const logs = [
      'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P invoke [1]',
      'Program log: Instruction: Create',
      `Program data: ${b64}`,
      'Program 6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P success',
    ];

    const result = extractMintFromLogs(logs);
    expect(result).not.toBeNull();
    expect(typeof result).toBe('string');
    expect(result!.length).toBeGreaterThan(20); // Solana addresses are ~44 chars
  });

  it('stops at next Instruction: line', () => {
    const logs = [
      'Program log: Instruction: Create',
      'Program log: Instruction: Transfer', // Should stop here
      'Program data: AAAA', // Should NOT be reached
    ];
    expect(extractMintFromLogs(logs)).toBeNull();
  });

  it('handles Program log: Create variant', () => {
    const mintBytes = new Uint8Array(64); // 64 bytes, first 32 are mint
    for (let i = 0; i < 32; i++) mintBytes[i] = 100 + i;
    const b64 = btoa(String.fromCharCode(...mintBytes));

    const logs = [
      'Program log: Create',
      `Program data: ${b64}`,
    ];

    const result = extractMintFromLogs(logs);
    expect(result).not.toBeNull();
  });
});
