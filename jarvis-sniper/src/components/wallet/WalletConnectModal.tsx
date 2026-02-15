'use client';

import { useMemo, useState } from 'react';
import { Copy, ExternalLink, Smartphone, Monitor, X, Check } from 'lucide-react';
import {
  getCurrentUrl,
  isProbablyMobile,
  openWalletDeepLink,
  type WalletDeepLinkKind,
} from '@/lib/wallet-deeplinks';

export function WalletConnectModal(props: {
  open: boolean;
  onClose: () => void;
  preferredKind?: WalletDeepLinkKind;
}) {
  const { open, onClose, preferredKind } = props;
  const isMobile = useMemo(() => isProbablyMobile(), []);
  const [copied, setCopied] = useState(false);

  if (!open) return null;

  const url = getCurrentUrl({ canonical: true });
  const primary: WalletDeepLinkKind = preferredKind === 'solflare' ? 'solflare' : 'phantom';
  const secondary: WalletDeepLinkKind = primary === 'phantom' ? 'solflare' : 'phantom';

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center p-4">
      <button
        type="button"
        className="absolute inset-0 bg-black/70 backdrop-blur-sm cursor-pointer"
        onClick={onClose}
        aria-label="Close connect wallet dialog"
      />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="wallet-connect-title"
        className="relative w-full max-w-[560px] card-glass p-5 border border-border-primary shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
              {isMobile ? (
                <Smartphone className="w-4 h-4 text-accent-neon" />
              ) : (
                <Monitor className="w-4 h-4 text-accent-neon" />
              )}
              <h2 id="wallet-connect-title" className="font-display text-base font-semibold">
                Connect Wallet
              </h2>
            </div>
            <p className="text-[12px] text-text-secondary leading-relaxed">
              {isMobile ? (
                <>
                  Mobile browsers (Safari/Chrome) cannot use wallet extensions. Open this page inside your wallet app&apos;s
                  browser to connect.
                </>
              ) : (
                <>
                  Install a wallet extension (Phantom or Solflare), then click Connect again. If you are on mobile, use
                  the wallet app&apos;s in-app browser.
                </>
              )}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-9 h-9 rounded-full bg-bg-tertiary border border-border-primary hover:border-border-hover flex items-center justify-center text-text-muted hover:text-text-primary transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => openWalletDeepLink(primary)}
            className="btn-neon w-full text-center flex items-center justify-center gap-2"
            title={primary === 'phantom' ? 'Open in Phantom' : 'Open in Solflare'}
          >
            {primary === 'phantom' ? 'Open in Phantom' : 'Open in Solflare'}
            <ExternalLink className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => openWalletDeepLink(secondary)}
            className="btn-secondary w-full text-center flex items-center justify-center gap-2"
            title={secondary === 'phantom' ? 'Open in Phantom' : 'Open in Solflare'}
          >
            {secondary === 'phantom' ? 'Open in Phantom' : 'Open in Solflare'}
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-4 rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[10px] font-mono font-semibold uppercase tracking-wider text-text-muted">
              Current page
            </div>
            <button
              type="button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(url || '');
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                } catch {
                  // ignore
                }
              }}
              className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-bg-secondary border border-border-primary text-[10px] font-mono text-text-secondary hover:text-text-primary hover:border-border-hover transition-colors"
              title="Copy link"
            >
              {copied ? <Check className="w-3 h-3 text-accent-neon" /> : <Copy className="w-3 h-3" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <div className="mt-2 text-[10px] font-mono text-text-secondary break-all">
            {url || '(unavailable)'}
          </div>
        </div>

        <div className="mt-4 flex flex-col sm:flex-row gap-2">
          <a
            href="https://phantom.app/download"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-bg-tertiary border border-border-primary text-sm text-text-secondary hover:text-text-primary hover:border-border-hover transition-colors"
          >
            Install Phantom
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
          <a
            href="https://solflare.com/download"
            target="_blank"
            rel="noopener noreferrer"
            className="w-full sm:w-auto flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-bg-tertiary border border-border-primary text-sm text-text-secondary hover:text-text-primary hover:border-border-hover transition-colors"
          >
            Install Solflare
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>
    </div>
  );
}
