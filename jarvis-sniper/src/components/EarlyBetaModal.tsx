'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, Shield, Wallet } from 'lucide-react';

const STORAGE_KEY = 'jarvis-sniper:early-beta-ack:v1';

export function EarlyBetaModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      const ack = localStorage.getItem(STORAGE_KEY);
      setOpen(ack !== '1');
    } catch {
      setOpen(true);
    }
  }, []);

  const acknowledge = () => {
    try {
      localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      // ignore
    }
    setOpen(false);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[999] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" />

      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="early-beta-title"
        className="relative w-full max-w-[560px] card-glass p-5 border border-accent-warning/25 shadow-xl"
      >
        <div className="flex items-start gap-3">
          <div className="mt-0.5 w-9 h-9 rounded-full bg-accent-warning/15 border border-accent-warning/25 flex items-center justify-center">
            <AlertTriangle className="w-4.5 h-4.5 text-accent-warning" />
          </div>
          <div className="flex-1">
            <div className="flex items-center justify-between gap-3">
              <h2 id="early-beta-title" className="font-display text-base font-semibold">
                Quick heads up (early beta)
              </h2>
              <span className="text-[10px] font-mono font-semibold uppercase tracking-wider px-2 py-1 rounded-full bg-accent-warning/10 text-accent-warning border border-accent-warning/25">
                testing
              </span>
            </div>

            <p className="mt-2 text-[12px] text-text-secondary leading-relaxed">
              This app is in very early testing. Trades are real, and you can lose 100% of the funds you use.
              Please use a small amount and a dedicated wallet while we harden everything.
            </p>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                <div className="flex items-center gap-2 text-[11px] font-semibold text-text-primary">
                  <Wallet className="w-3.5 h-3.5 text-accent-neon" />
                  Self-custody
                </div>
                <p className="mt-1 text-[10px] text-text-muted leading-relaxed">
                  Your private keys never touch our servers. You can trade in Phantom mode (manual approvals) or Session Wallet mode (a temporary burner wallet stored in this tab for auto-signing).
                </p>
              </div>

               <div className="rounded-lg bg-bg-tertiary/60 border border-border-primary p-3">
                  <div className="flex items-center gap-2 text-[11px] font-semibold text-text-primary">
                    <Shield className="w-3.5 h-3.5 text-accent-warning" />
                    SL/TP can auto-execute
                  </div>
                <p className="mt-1 text-[10px] text-text-muted leading-relaxed">
                  Phantom mode: when SL/TP/trailing/expiry hits, the position shows "Exit pending" and you must click Approve to sign the sell.
                  Session Wallet mode: exits are auto-signed and submitted via Bags as long as this tab stays open.
                  If you close the tab, automation stops.
                  Low-liquidity tokens can still slip past targets (or have no route to sell).
                  If you're seeing lots of "Low liquidity" skips, lower Min Liquidity (USD) while testing.
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-lg border border-accent-error/25 bg-accent-error/5 p-3">
              <p className="text-[10px] text-text-secondary leading-relaxed">
                If you are not comfortable potentially losing all funds used here, don’t use it yet.
              </p>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row gap-2">
              <button
                autoFocus
                onClick={acknowledge}
                className="btn-neon w-full sm:w-auto flex-1"
              >
                I understand, continue
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
              Tip: use a burner wallet and tiny size (ex: 0.01 SOL) while testing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
