const DEFAULT_DEV_RPC_URL = 'https://api.mainnet-beta.solana.com';

export type ServerRpcSource =
  | 'helius_gatekeeper'
  | 'solana_rpc_url'
  | 'next_public_fallback'
  | 'default_fallback'
  | 'missing'
  | 'invalid_url'
  | 'invalid_provider';

export interface ServerRpcResolution {
  ok: boolean;
  url: string | null;
  source: ServerRpcSource;
  isProduction: boolean;
  diagnostic: string;
  sanitizedUrl: string | null;
}

function sanitizeRpcUrl(raw: string): string {
  try {
    const parsed = new URL(raw);
    if (parsed.searchParams.has('api-key')) {
      parsed.searchParams.set('api-key', '***');
    }
    return `${parsed.origin}${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return '(invalid-rpc-url)';
  }
}

function parseRpcUrl(raw: string): URL | null {
  try {
    const parsed = new URL(raw);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null;
    return parsed;
  } catch {
    return null;
  }
}

function isHeliusRpcHost(hostname: string): boolean {
  const host = hostname.trim().toLowerCase();
  return host === 'helius-rpc.com' || host.endsWith('.helius-rpc.com');
}

export function resolveServerRpcConfig(): ServerRpcResolution {
  const isProduction = process.env.NODE_ENV === 'production';
  const candidates: Array<{ source: ServerRpcSource; value: string }> = [];

  const gatekeeper = String(process.env.HELIUS_GATEKEEPER_RPC_URL || '').trim();
  if (gatekeeper) {
    candidates.push({ source: 'helius_gatekeeper', value: gatekeeper });
  }

  const legacyServer = String(process.env.SOLANA_RPC_URL || '').trim();
  if (legacyServer) {
    candidates.push({ source: 'solana_rpc_url', value: legacyServer });
  }

  if (!isProduction) {
    const nextPublic = String(process.env.NEXT_PUBLIC_SOLANA_RPC || '').trim();
    if (nextPublic) {
      candidates.push({ source: 'next_public_fallback', value: nextPublic });
    }
    candidates.push({ source: 'default_fallback', value: DEFAULT_DEV_RPC_URL });
  }

  for (const candidate of candidates) {
    const parsed = parseRpcUrl(candidate.value);
    const sanitizedUrl = sanitizeRpcUrl(candidate.value);
    if (!parsed) {
      if (isProduction) {
        return {
          ok: false,
          url: null,
          source: 'invalid_url',
          isProduction,
          sanitizedUrl,
          diagnostic: `Invalid server RPC URL for ${candidate.source}: ${sanitizedUrl}`,
        };
      }
      continue;
    }

    if (isProduction && !isHeliusRpcHost(parsed.hostname)) {
      return {
        ok: false,
        url: null,
        source: 'invalid_provider',
        isProduction,
        sanitizedUrl,
        diagnostic: `Production RPC must use Helius (*.helius-rpc.com). Got ${sanitizedUrl}`,
      };
    }

    return {
      ok: true,
      url: parsed.toString(),
      source: candidate.source,
      isProduction,
      sanitizedUrl,
      diagnostic: `Using ${candidate.source}: ${sanitizedUrl}`,
    };
  }

  return {
    ok: false,
    url: null,
    source: 'missing',
    isProduction,
    sanitizedUrl: null,
    diagnostic: isProduction
      ? 'Missing server RPC config (set HELIUS_GATEKEEPER_RPC_URL or SOLANA_RPC_URL).'
      : 'Missing server RPC config.',
  };
}

