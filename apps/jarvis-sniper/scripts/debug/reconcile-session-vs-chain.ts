import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

type RpcStatus = {
  slot?: number;
  confirmations?: number | null;
  err?: unknown;
  confirmationStatus?: 'processed' | 'confirmed' | 'finalized' | null;
};

type Args = {
  sessionPath: string;
  wallet?: string;
  rpcUrl: string;
  outPath?: string;
};

const DEFAULT_RPC =
  process.env.SOLANA_RPC_URL ||
  process.env.NEXT_PUBLIC_SOLANA_RPC ||
  'https://api.mainnet-beta.solana.com';

function parseArgs(argv: string[]): Args {
  const args: Partial<Args> = { rpcUrl: DEFAULT_RPC };
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    const next = argv[i + 1];
    if (token === '--session' && next) {
      args.sessionPath = next;
      i++;
      continue;
    }
    if (token === '--wallet' && next) {
      args.wallet = next;
      i++;
      continue;
    }
    if (token === '--rpc' && next) {
      args.rpcUrl = next;
      i++;
      continue;
    }
    if (token === '--out' && next) {
      args.outPath = next;
      i++;
      continue;
    }
  }
  if (!args.sessionPath) {
    throw new Error('Missing --session <path-to-session-markdown>');
  }
  return args as Args;
}

async function rpcCall<T>(rpcUrl: string, method: string, params: unknown[]): Promise<T> {
  const res = await fetch(rpcUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  if (!res.ok) {
    throw new Error(`RPC ${method} failed: HTTP ${res.status}`);
  }
  const json = await res.json();
  if (json?.error) {
    throw new Error(`RPC ${method} error: ${JSON.stringify(json.error)}`);
  }
  return json.result as T;
}

function extractLikelySignatures(markdown: string): string[] {
  const signatureRegex = /\b[1-9A-HJ-NP-Za-km-z]{80,90}\b/g;
  const seen = new Set<string>();
  const out: string[] = [];
  for (const match of markdown.matchAll(signatureRegex)) {
    const sig = String(match[0] || '').trim();
    if (!sig || seen.has(sig)) continue;
    seen.add(sig);
    out.push(sig);
  }
  return out;
}

function classifyStatus(status: RpcStatus | null | undefined): 'confirmed' | 'failed' | 'unresolved' {
  if (!status) return 'unresolved';
  if (status.err) return 'failed';
  if (status.confirmationStatus === 'confirmed' || status.confirmationStatus === 'finalized') return 'confirmed';
  return 'unresolved';
}

function formatTsIso(ts: number): string {
  if (!Number.isFinite(ts) || ts <= 0) return '';
  return new Date(ts).toISOString();
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const content = await readFile(args.sessionPath, 'utf8');
  const signatures = extractLikelySignatures(content);

  const statusBySig = new Map<string, RpcStatus | null>();
  const chunkSize = 256;
  for (let i = 0; i < signatures.length; i += chunkSize) {
    const chunk = signatures.slice(i, i + chunkSize);
    const result = await rpcCall<{ value: Array<RpcStatus | null> }>(
      args.rpcUrl,
      'getSignatureStatuses',
      [chunk, { searchTransactionHistory: true }],
    );
    for (let idx = 0; idx < chunk.length; idx++) {
      statusBySig.set(chunk[idx], result?.value?.[idx] ?? null);
    }
  }

  let confirmed = 0;
  let failed = 0;
  let unresolved = 0;
  for (const sig of signatures) {
    const cls = classifyStatus(statusBySig.get(sig));
    if (cls === 'confirmed') confirmed++;
    else if (cls === 'failed') failed++;
    else unresolved++;
  }

  let walletBalanceLamports: number | null = null;
  let walletRecentSigs: Array<{ signature: string; blockTime?: number | null; err?: unknown }> = [];
  let tokenAccountCount: number | null = null;
  let nonZeroTokenAccounts: number | null = null;

  if (args.wallet) {
    walletBalanceLamports = await rpcCall<number>(args.rpcUrl, 'getBalance', [args.wallet, { commitment: 'confirmed' }])
      .then((r: any) => Number(r?.value ?? r))
      .catch(() => null);

    walletRecentSigs = await rpcCall<Array<{ signature: string; blockTime?: number | null; err?: unknown }>>(
      args.rpcUrl,
      'getSignaturesForAddress',
      [args.wallet, { limit: 100 }],
    ).catch(() => []);

    const tokenRows = await rpcCall<any>(args.rpcUrl, 'getTokenAccountsByOwner', [
      args.wallet,
      { programId: 'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA' },
      { encoding: 'jsonParsed' },
    ]).catch(() => ({ value: [] }));

    const token2022Rows = await rpcCall<any>(args.rpcUrl, 'getTokenAccountsByOwner', [
      args.wallet,
      { programId: 'TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb' },
      { encoding: 'jsonParsed' },
    ]).catch(() => ({ value: [] }));

    const allRows = [...(tokenRows?.value || []), ...(token2022Rows?.value || [])];
    tokenAccountCount = allRows.length;
    nonZeroTokenAccounts = allRows.filter((row) => {
      const amt = String(row?.account?.data?.parsed?.info?.tokenAmount?.amount || '0');
      return amt !== '0';
    }).length;
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const outPath = args.outPath || path.join('debug', `debug-report-${timestamp}.md`);
  await mkdir(path.dirname(outPath), { recursive: true });

  const lines: string[] = [];
  lines.push('# Debug Report: Session Log vs Chain');
  lines.push('');
  lines.push(`- Session file: \`${args.sessionPath}\``);
  lines.push(`- RPC: \`${args.rpcUrl}\``);
  lines.push(`- Generated: \`${new Date().toISOString()}\``);
  if (args.wallet) lines.push(`- Wallet: \`${args.wallet}\``);
  lines.push('');

  lines.push('## Signature Reconciliation');
  lines.push('');
  lines.push(`- Signatures found in session markdown: ${signatures.length}`);
  lines.push(`- Confirmed on-chain: ${confirmed}`);
  lines.push(`- Failed on-chain: ${failed}`);
  lines.push(`- Unresolved/not found: ${unresolved}`);
  lines.push('');

  lines.push('| Signature | Chain Status | Confirmation | Error |');
  lines.push('|---|---|---|---|');
  for (const sig of signatures.slice(0, 120)) {
    const row = statusBySig.get(sig);
    const cls = classifyStatus(row);
    const confirmation = row?.confirmationStatus ? String(row.confirmationStatus) : 'none';
    const err = row?.err ? JSON.stringify(row.err).replace(/\|/g, '\\|') : '';
    lines.push(`| \`${sig}\` | ${cls} | ${confirmation} | ${err} |`);
  }
  if (signatures.length > 120) {
    lines.push('');
    lines.push(`_Truncated table to first 120 signatures (of ${signatures.length})._`);
  }
  lines.push('');

  if (args.wallet) {
    lines.push('## Wallet Snapshot');
    lines.push('');
    lines.push(`- SOL balance (lamports): ${walletBalanceLamports ?? 'n/a'}`);
    lines.push(`- SOL balance (SOL): ${walletBalanceLamports != null ? (walletBalanceLamports / 1e9).toFixed(6) : 'n/a'}`);
    lines.push(`- Token accounts total: ${tokenAccountCount ?? 'n/a'}`);
    lines.push(`- Token accounts non-zero: ${nonZeroTokenAccounts ?? 'n/a'}`);
    lines.push('');
    lines.push('### Recent Wallet Signatures (latest 25)');
    lines.push('');
    lines.push('| Signature | Block Time (UTC) | Error |');
    lines.push('|---|---|---|');
    for (const row of walletRecentSigs.slice(0, 25)) {
      const ts = row.blockTime ? formatTsIso(Number(row.blockTime) * 1000) : '';
      const err = row.err ? JSON.stringify(row.err).replace(/\|/g, '\\|') : '';
      lines.push(`| \`${row.signature}\` | ${ts} | ${err} |`);
    }
    lines.push('');
  }

  lines.push('## Mismatch Summary');
  lines.push('');
  if (signatures.length === 0) {
    lines.push('- Unable to reconcile session tx claims: no full transaction signatures were found in the session markdown.');
    lines.push('- Provide a session export with complete tx signatures (not shortened prefixes) for direct claim-vs-chain verification.');
  } else if (unresolved === 0 && failed === 0) {
    lines.push('- No unresolved/failed session signatures detected in sampled set.');
  } else {
    lines.push(`- Severity HIGH: ${unresolved} unresolved/not-found signature(s) in session claims.`);
    lines.push(`- Severity MEDIUM: ${failed} failed signature(s) in session claims.`);
    lines.push('- On-chain state should remain source-of-truth for P&L and fill history.');
  }
  lines.push('');

  await writeFile(outPath, lines.join('\n'), 'utf8');
  process.stdout.write(`Debug report written: ${outPath}\n`);
}

main().catch((err) => {
  process.stderr.write(`reconcile-session-vs-chain failed: ${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
});
