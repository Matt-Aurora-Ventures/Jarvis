export type WalletDeepLinkKind = 'phantom' | 'solflare';

export function isProbablyMobileUserAgent(ua: string): boolean {
  const text = String(ua || '');
  return /Android|iPhone|iPad|iPod|Mobile/i.test(text);
}

export function isProbablyMobile(): boolean {
  if (typeof navigator === 'undefined') return false;
  return isProbablyMobileUserAgent(navigator.userAgent || '');
}

export function buildPhantomBrowseDeepLink(targetUrl: string, refUrl: string): string {
  // Phantom uses: https://phantom.app/ul/browse/<encodedTarget>?ref=<encodedRef>
  const t = encodeURIComponent(String(targetUrl || ''));
  const r = encodeURIComponent(String(refUrl || ''));
  return `https://phantom.app/ul/browse/${t}?ref=${r}`;
}

export function buildSolflareBrowseDeepLink(targetUrl: string, refUrl: string): string {
  // Solflare uses: https://solflare.com/ul/v1/browse/<encodedTarget>?ref=<encodedRef>
  const t = encodeURIComponent(String(targetUrl || ''));
  const r = encodeURIComponent(String(refUrl || ''));
  return `https://solflare.com/ul/v1/browse/${t}?ref=${r}`;
}

export function getCanonicalOrigin(): string {
  const raw = String(process.env.NEXT_PUBLIC_CANONICAL_ORIGIN || '').trim();
  if (!raw) return getRefUrl();
  return raw.replace(/\/+$/, '');
}

export function getRefUrl(): string {
  if (typeof window === 'undefined') return '';
  return window.location.origin;
}

export function getCanonicalUrl(): string {
  if (typeof window === 'undefined') return '';
  const origin = getCanonicalOrigin();
  const path = window.location.pathname || '/';
  const search = window.location.search || '';
  const hash = window.location.hash || '';
  return `${origin}${path}${search}${hash}`;
}

export function getCurrentUrl(opts?: { canonical?: boolean }): string {
  if (typeof window === 'undefined') return '';
  return opts?.canonical ? getCanonicalUrl() : window.location.href;
}

export function openWalletDeepLink(kind: WalletDeepLinkKind, opts?: { targetUrl?: string }): void {
  if (typeof window === 'undefined') return;
  const targetUrl = opts?.targetUrl || getCurrentUrl({ canonical: true });
  const refUrl = getCanonicalOrigin();
  const url = kind === 'phantom'
    ? buildPhantomBrowseDeepLink(targetUrl, refUrl)
    : buildSolflareBrowseDeepLink(targetUrl, refUrl);
  window.location.assign(url);
}
