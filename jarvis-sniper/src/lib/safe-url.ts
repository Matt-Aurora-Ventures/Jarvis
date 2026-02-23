/**
 * URL sanitizers used by UI + API responses.
 *
 * Goal: prevent mixed-content (http) and obviously unsafe protocols from
 * being surfaced to the client.
 */

export function safeImageUrl(input: string | null | undefined): string | null {
  const raw = String(input || '').trim();
  if (!raw) return null;

  // Allow inline and blob images (CSP already restricts these).
  if (raw.startsWith('data:') || raw.startsWith('blob:')) return raw;

  // Normalize IPFS URIs to an HTTPS gateway URL.
  if (raw.startsWith('ipfs://')) {
    const path = raw.slice('ipfs://'.length).replace(/^ipfs\//, '');
    if (!path) return null;
    return `https://ipfs.io/ipfs/${path}`;
  }

  try {
    const url = new URL(raw);
    // Mixed content and non-web protocols are blocked.
    if (url.protocol !== 'https:') return null;
    return url.toString();
  } catch {
    return null;
  }
}

