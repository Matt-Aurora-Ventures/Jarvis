import { afterEach, describe, expect, it } from 'vitest';
import { resolveServerRpcConfig } from '@/lib/server-rpc-config';

const ORIGINAL_NODE_ENV = process.env.NODE_ENV;
const ORIGINAL_GATEKEEPER = process.env.HELIUS_GATEKEEPER_RPC_URL;
const ORIGINAL_SERVER_RPC = process.env.SOLANA_RPC_URL;
const ORIGINAL_PUBLIC_RPC = process.env.NEXT_PUBLIC_SOLANA_RPC;

function restoreEnv() {
  process.env.NODE_ENV = ORIGINAL_NODE_ENV;
  if (ORIGINAL_GATEKEEPER === undefined) {
    delete process.env.HELIUS_GATEKEEPER_RPC_URL;
  } else {
    process.env.HELIUS_GATEKEEPER_RPC_URL = ORIGINAL_GATEKEEPER;
  }
  if (ORIGINAL_SERVER_RPC === undefined) {
    delete process.env.SOLANA_RPC_URL;
  } else {
    process.env.SOLANA_RPC_URL = ORIGINAL_SERVER_RPC;
  }
  if (ORIGINAL_PUBLIC_RPC === undefined) {
    delete process.env.NEXT_PUBLIC_SOLANA_RPC;
  } else {
    process.env.NEXT_PUBLIC_SOLANA_RPC = ORIGINAL_PUBLIC_RPC;
  }
}

afterEach(() => {
  restoreEnv();
});

describe('server-rpc-config', () => {
  it('fails closed in production when no RPC URL is configured', () => {
    process.env.NODE_ENV = 'production';
    delete process.env.HELIUS_GATEKEEPER_RPC_URL;
    delete process.env.SOLANA_RPC_URL;
    delete process.env.NEXT_PUBLIC_SOLANA_RPC;

    const res = resolveServerRpcConfig();
    expect(res.ok).toBe(false);
    expect(res.source).toBe('missing');
  });

  it('fails in production when RPC host is not Helius', () => {
    process.env.NODE_ENV = 'production';
    delete process.env.HELIUS_GATEKEEPER_RPC_URL;
    process.env.SOLANA_RPC_URL = 'https://api.mainnet-beta.solana.com';

    const res = resolveServerRpcConfig();
    expect(res.ok).toBe(false);
    expect(res.source).toBe('invalid_provider');
  });

  it('passes in production with Helius Gatekeeper URL and sanitizes api-key in diagnostics', () => {
    process.env.NODE_ENV = 'production';
    process.env.HELIUS_GATEKEEPER_RPC_URL = 'https://beta.helius-rpc.com/?api-key=secret-key-value';
    process.env.SOLANA_RPC_URL = 'https://api.mainnet-beta.solana.com';

    const res = resolveServerRpcConfig();
    expect(res.ok).toBe(true);
    expect(res.source).toBe('helius_gatekeeper');
    expect(res.sanitizedUrl).toContain('api-key=***');
    expect(res.sanitizedUrl).not.toContain('secret-key-value');
  });

  it('allows development fallback path when no server URL is set', () => {
    process.env.NODE_ENV = 'development';
    delete process.env.HELIUS_GATEKEEPER_RPC_URL;
    delete process.env.SOLANA_RPC_URL;
    delete process.env.NEXT_PUBLIC_SOLANA_RPC;

    const res = resolveServerRpcConfig();
    expect(res.ok).toBe(true);
    expect(res.source).toBe('default_fallback');
    expect(res.url).toBe('https://api.mainnet-beta.solana.com/');
  });
});

