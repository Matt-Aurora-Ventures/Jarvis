/**
 * URL safety helpers.
 *
 * Used to prevent mixed-content (http://) and sketchy/icon-host URLs from being
 * rendered in the client. Prefer returning `undefined` over attempting to load
 * an insecure resource.
 */

function isLikelyIpHost(hostname: string): boolean {
  // IPv4
  if (/^\d{1,3}(\.\d{1,3}){3}$/.test(hostname)) return true;
  // IPv6
  if (hostname.includes(':')) return true;
  return false;
}

export function safeImageUrl(raw: string | null | undefined): string | undefined {
  const input = String(raw || '').trim();
  if (!input) return undefined;

  // Allow safe in-page references (used rarely, but safe under our CSP).
  if (input.startsWith('data:') || input.startsWith('blob:')) return input;

  // Allow https URLs as-is.
  if (input.startsWith('https://')) return input;

  // Normalize common crypto URI schemes.
  if (input.startsWith('ipfs://')) {
    const cid = input.slice('ipfs://'.length).replace(/^ipfs\//, '');
    return cid ? `https://ipfs.io/ipfs/${cid}` : undefined;
  }
  if (input.startsWith('ar://')) {
    const id = input.slice('ar://'.length);
    return id ? `https://arweave.net/${id}` : undefined;
  }

  // Mixed-content / insecure resources: allow a conservative upgrade from http->https
  // only when the hostname is not an IP and no explicit port is present.
  if (input.startsWith('http://')) {
    try {
      const url = new URL(input);
      if (isLikelyIpHost(url.hostname)) return undefined;
      if (url.hostname === 'localhost') return undefined;
      if (url.port) return undefined;
      url.protocol = 'https:';
      return url.toString();
    } catch {
      return undefined;
    }
  }

  return undefined;
}

