'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Shield, Wallet } from 'lucide-react';

// Session-scoped acknowledgment:
// show once per new browser session/tab, but not on every page navigation.
const SESSION_ACK_KEY = 'jarvis-sniper:early-beta-ack:session:v3';
const BANNER_ACK_KEY = 'jarvis-sniper:early-beta-banner-ack:session:v1';

export function EarlyBetaModal() {
  const [open, setOpen] = useState(false);
  const [bannerVisible, setBannerVisible] = useState(true);

  useEffect(() => {
    try {
      const ack = sessionStorage.getItem(SESSION_ACK_KEY);
      setOpen(ack !== '1');
      const bannerAck = sessionStorage.getItem(BANNER_ACK_KEY);
      setBannerVisible(bannerAck !== '1');
    } catch {
      setOpen(true);
      setBannerVisible(true);
    }
  }, []);

  const acknowledge = () => {
    try {
      sessionStorage.setItem(SESSION_ACK_KEY, '1');
    } catch {
      // ignore
    }
    setOpen(false);
  };

  const dismissBanner = () => {
    try {
      sessionStorage.setItem(BANNER_ACK_KEY, '1');
    } catch {
      // ignore
    }
    setBannerVisible(false);
  };

  return (
    <>
      {/* Always-on warning strip so risk language is permanently visible in-app */}
      {bannerVisible && (
        <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-[520] w-[min(96vw,980px)]">
          <div className="rounded-lg border border-accent-error/35 bg-bg-primary/90 backdrop-blur px-3 py-2 text-[10px] sm:text-[11px] leading-relaxed text-text-secondary shadow-lg">
            <div className="flex items-start gap-3">
              <p className="flex-1">
                <span className="font-semibold text-accent-error">PRE-ALPHA WARNING:</span>{' '}
                This is an early showcase. Many algorithms are still being tuned and may perform badly. You can lose all SOL used here.
                Use a burner wallet and tiny size (example: 0.01 SOL). No guarantees. No liability assumed.
              </p>
              <div className="shrink-0 flex items-center gap-1">
                <button
                  onClick={dismissBanner}
                  className="px-2 py-1 rounded border border-accent-warning/35 text-accent-warning hover:bg-accent-warning/10 transition-colors text-[10px] font-semibold"
                  title="Dismiss this warning for this browser session"
                >
                  I accept
                </button>
                <button
                  onClick={dismissBanner}
                  className="w-6 h-6 rounded border border-border-primary text-text-muted hover:text-text-primary hover:bg-bg-tertiary transition-colors text-[12px] leading-none"
                  title="Close"
                  aria-label="Close warning banner"
                >
                  ×
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-[999] flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="early-beta-title"
            className="relative w-full max-w-[620px] card-glass p-5 border border-accent-warning/25 shadow-xl"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 w-9 h-9 rounded-full bg-accent-warning/15 border border-accent-warning/25 flex items-center justify-center">
                <AlertTriangle className="w-4.5 h-4.5 text-accent-warning" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between gap-3">
                  <h2 id="early-beta-title" className="font-display text-base font-semibold">
                    Read this before trading
                  </h2>
                  <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-accent-warning/10 text-accent-warning border border-accent-warning/25">
                    pre-alpha
                  </span>
                </div>

                <p className="mt-2 text-[12px] text-text-secondary leading-relaxed">
                  Plain English: this is super early. Most core features work, but a lot of algorithms are not close to final quality yet.
                  This app is mainly to show how the product works while we continue tuning and backtesting.
                </p>

                <div className="mt-4 rounded-lg border border-accent-error/25 bg-accent-error/5 p-3">
                  <ul className="text-[10px] text-text-secondary leading-relaxed list-disc pl-4 space-y-1">
                    <li>You can absolutely lose your SOL.</li>
                    <li>Use only a burner wallet.</li>
                    <li>Use tiny size (recommended: around <span className="font-semibold text-accent-warning">0.01 SOL</span> per trade).</li>
                    <li>Assume funds used here could be gone.</li>
                    <li>We assume zero responsibility or liability at this stage.</li>
                  </ul>
                </div>

                <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold text-text-primary">
                      <Wallet className="w-3.5 h-3.5 text-accent-neon" />
                      Self-custody
                    </div>
                    <p className="mt-1 text-[10px] text-text-muted leading-relaxed">
                      Keys stay client-side. You can trade in Phantom mode (manual approvals)
                      or Session Wallet mode (temporary burner wallet in this tab).
                    </p>
                  </div>

                  <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                    <div className="flex items-center gap-2 text-[11px] font-semibold text-text-primary">
                      <Shield className="w-3.5 h-3.5 text-accent-warning" />
                      Exit behavior
                    </div>
                    <p className="mt-1 text-[10px] text-text-muted leading-relaxed">
                      In Phantom mode, you must approve exits. In Session Wallet mode, exits are auto-signed while this tab stays open.
                      Slippage and low liquidity can still cause worse fills.
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex flex-col sm:flex-row gap-2">
                  <button
                    autoFocus
                    onClick={acknowledge}
                    className="btn-neon w-full sm:w-auto flex-1"
                  >
                    I understand the risk for this session
                  </button>
                  <a
                    href="https://phantom.app/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-secondary w-full sm:w-auto text-center flex-1"
                  >
                    Get Phantom
                  </a>
                </div>

                <p className="mt-3 text-[9px] text-text-muted font-mono">
                  This warning appears again on every new browser session.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
