'use client';

import { useState, useEffect } from 'react';
import { AlertTriangle, ArrowRight, Loader2, CheckCircle, X, RefreshCw } from 'lucide-react';
import {
  checkForRecoverableWallet,
  loadSessionWalletByPublicKey,
  loadSessionWalletFromStorage,
  sweepToMainWalletAndCloseTokenAccounts,
} from '@/lib/session-wallet';

interface RecoverableWallet {
  publicKey: string;
  mainWallet: string;
  balanceSol: number;
  createdAt: number;
}

/**
 * FundRecoveryBanner — standalone component that checks for orphaned session
 * wallet funds on mount and shows a prominent recovery UI.
 *
 * Renders nothing when no recoverable wallet is found.
 * Dismisses after successful sweep or manual dismiss (session-scoped).
 *
 * Phase 2.3 — Wallet Safety
 */
export function FundRecoveryBanner() {
  const [recoverable, setRecoverable] = useState<RecoverableWallet | null>(null);
  const [sweeping, setSweeping] = useState(false);
  const [sweepResult, setSweepResult] = useState<{ success: boolean; txHash?: string; error?: string } | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [rpcError, setRpcError] = useState(false);

  // Check for orphaned session wallets on mount
  useEffect(() => {
    // Don't re-check if already dismissed this session
    if (typeof sessionStorage !== 'undefined') {
      const flag = sessionStorage.getItem('__jarvis_recovery_dismissed');
      if (flag === '1') {
        setDismissed(true);
        return;
      }
    }

    let cancelled = false;

    const check = async () => {
      try {
        const result = await checkForRecoverableWallet();
        if (!cancelled && result) {
          setRecoverable(result);
        }
      } catch {
        // RPC unavailable on startup — show soft message
        if (!cancelled) {
          setRpcError(true);
        }
      }
    };

    check();
    return () => { cancelled = true; };
  }, []);

  // Auto-dismiss after successful sweep (5 seconds)
  useEffect(() => {
    if (sweepResult?.success) {
      const timer = setTimeout(() => {
        handleDismiss();
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [sweepResult]);

  const handleDismiss = () => {
    setDismissed(true);
    if (typeof sessionStorage !== 'undefined') {
      try { sessionStorage.setItem('__jarvis_recovery_dismissed', '1'); } catch {}
    }
  };

  const handleSweep = async () => {
    if (!recoverable || sweeping) return;

    setSweeping(true);
    setSweepResult(null);

    try {
      // Try to load wallet by public key first, fall back to generic loader
      const wallet = await loadSessionWalletByPublicKey(recoverable.publicKey)
        || await loadSessionWalletFromStorage({ allowBackupFallback: true });

      if (!wallet) {
        setSweepResult({
          success: false,
          error: 'Could not load wallet key from storage. The key may have been cleared.',
        });
        setSweeping(false);
        return;
      }

      const sweep = await sweepToMainWalletAndCloseTokenAccounts(wallet.keypair, recoverable.mainWallet);

      if (sweep.sweepSignature || sweep.closedTokenAccounts > 0) {
        setSweepResult({ success: true, txHash: sweep.sweepSignature || undefined });
      } else {
        setSweepResult({
          success: false,
          error: 'Balance too low to sweep (less than fee buffer).',
        });
      }
    } catch (err: any) {
      setSweepResult({
        success: false,
        error: `Sweep failed: ${err?.message || 'Unknown error'}. Your funds are safe -- the wallet key is preserved. Try again or use Manual Recovery in Settings.`,
      });
    } finally {
      setSweeping(false);
    }
  };

  const handleRetry = () => {
    setSweepResult(null);
    handleSweep();
  };

  // Nothing to show
  if (dismissed) return null;
  if (!recoverable && !rpcError) return null;

  // RPC error on startup — show soft warning
  if (rpcError && !recoverable) {
    return (
      <div className="mx-3 mt-3 p-3 rounded-lg bg-bg-secondary border border-border-primary">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-text-muted flex-shrink-0" />
          <span className="text-[11px] text-text-muted">
            Could not check for recoverable wallets. If you had a session wallet, try refreshing when network is available.
          </span>
          <button
            onClick={handleDismiss}
            className="ml-auto text-text-muted hover:text-text-secondary transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    );
  }

  if (!recoverable) return null;

  const relativeTime = (() => {
    const diff = Date.now() - recoverable.createdAt;
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  })();

  return (
    <div className="mx-3 mt-3 p-4 rounded-lg bg-accent-warning/10 border border-accent-warning/30 animate-fade-in">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-accent-warning flex-shrink-0 mt-0.5" />

        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-bold text-accent-warning mb-1">
            FUNDS DETECTED IN SESSION WALLET
          </h3>
          <p className="text-[11px] text-text-secondary mb-3">
            {recoverable.balanceSol.toFixed(4)} SOL found in session wallet{' '}
            <span className="font-mono text-text-muted">
              {recoverable.publicKey.slice(0, 4)}...{recoverable.publicKey.slice(-4)}
            </span>
            {' '}(created {relativeTime})
          </p>

          {/* Success state */}
          {sweepResult?.success && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-neon/10 border border-accent-neon/30 mb-2">
              <CheckCircle className="w-4 h-4 text-accent-neon flex-shrink-0" />
              <div className="text-[11px] text-accent-neon">
                <span className="font-semibold">Funds recovered successfully!</span>
                {sweepResult.txHash && (
                  <a
                    href={`https://solscan.io/tx/${sweepResult.txHash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-1 underline opacity-80 hover:opacity-100"
                  >
                    View tx
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Error state */}
          {sweepResult && !sweepResult.success && (
            <div className="flex items-center gap-2 p-2.5 rounded-lg bg-accent-error/10 border border-accent-error/30 mb-2">
              <AlertTriangle className="w-3.5 h-3.5 text-accent-error flex-shrink-0" />
              <span className="text-[10px] text-accent-error">{sweepResult.error}</span>
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-2">
            {!sweepResult?.success && (
              <>
                {sweepResult && !sweepResult.success ? (
                  <button
                    onClick={handleRetry}
                    disabled={sweeping}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-semibold bg-accent-warning/20 text-accent-warning border border-accent-warning/30 hover:bg-accent-warning/30 transition-all disabled:opacity-50"
                  >
                    {sweeping ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="w-3.5 h-3.5" />
                    )}
                    Retry Sweep
                  </button>
                ) : (
                  <button
                    onClick={handleSweep}
                    disabled={sweeping}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[11px] font-semibold bg-accent-warning/20 text-accent-warning border border-accent-warning/30 hover:bg-accent-warning/30 transition-all disabled:opacity-50"
                  >
                    {sweeping ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <ArrowRight className="w-3.5 h-3.5" />
                    )}
                    Sweep to Main Wallet
                  </button>
                )}
              </>
            )}

            <button
              onClick={handleDismiss}
              className="px-3 py-1.5 rounded-md text-[11px] text-text-muted hover:text-text-secondary border border-border-primary hover:border-border-hover transition-all"
            >
              Dismiss
            </button>
          </div>
        </div>

        <button
          onClick={handleDismiss}
          className="text-text-muted hover:text-text-secondary transition-colors flex-shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
