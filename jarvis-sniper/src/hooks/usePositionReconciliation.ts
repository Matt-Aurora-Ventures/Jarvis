'use client';

import { useEffect, useRef } from 'react';
import { usePhantomWallet } from './usePhantomWallet';
import { useSniperStore } from '@/stores/useSniperStore';
import { resolveActiveWallet } from '@/lib/position-scope';
import { getConnection as getSharedConnection } from '@/lib/rpc-url';
import { getOwnerTokenBalanceLamportsWithRetry } from '@/lib/solana-tokens';
import { reconcileSignatureStatuses, type SignatureStatusResult } from '@/lib/tx-confirmation';

const RECONCILE_INTERVAL_MS = 5 * 60 * 1000;
const RECONCILE_GRACE_MS = 5 * 60 * 1000;

type ReconcileReason = 'no_onchain_balance' | 'buy_tx_unresolved' | 'buy_tx_failed';

function signatureReason(status: SignatureStatusResult | undefined): ReconcileReason | null {
  if (!status) return null;
  if (status.state === 'failed') return 'buy_tx_failed';
  if (status.state === 'unresolved') return 'buy_tx_unresolved';
  return null;
}

export function usePositionReconciliation() {
  const { address } = usePhantomWallet();
  const tradeSignerMode = useSniperStore((s) => s.tradeSignerMode);
  const sessionWalletPubkey = useSniperStore((s) => s.sessionWalletPubkey);
  const addExecution = useSniperStore((s) => s.addExecution);
  const setTxReconcilerRunning = useSniperStore((s) => s.setTxReconcilerRunning);
  const inFlightRef = useRef(false);

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      if (cancelled || inFlightRef.current) return;

      const state = useSniperStore.getState();
      const activeWallet = resolveActiveWallet(
        tradeSignerMode,
        sessionWalletPubkey,
        address,
      );
      if (!activeWallet) return;

      const now = Date.now();
      const candidates = state.positions.filter((p) => (
        p.status === 'open'
        && p.walletAddress === activeWallet
        && !p.isClosing
        && now - Number(p.entryTime || 0) >= RECONCILE_GRACE_MS
      ));
      if (candidates.length === 0) return;

      inFlightRef.current = true;
      setTxReconcilerRunning(true);
      try {
        const signatures = [...new Set(
          candidates
            .map((p) => String(p.txHash || '').trim())
            .filter(Boolean),
        )];

        let statusBySig: Record<string, SignatureStatusResult> = {};
        if (signatures.length > 0) {
          try {
            statusBySig = await reconcileSignatureStatuses(signatures);
          } catch {
            // Signature RPC reconciliation is best-effort. We still run wallet-balance checks.
          }
        }

        const connection = getSharedConnection();
        const reconciled: Array<{ symbol: string; reason: ReconcileReason }> = [];

        for (const candidate of candidates) {
          if (cancelled) return;
          const latest = useSniperStore.getState().positions.find((p) => p.id === candidate.id);
          if (!latest || latest.status !== 'open' || latest.isClosing) continue;

          const txHash = String(latest.txHash || '').trim();
          const txReason = signatureReason(txHash ? statusBySig[txHash] : undefined);

          const bal = await getOwnerTokenBalanceLamportsWithRetry(
            connection,
            activeWallet,
            latest.mint,
            { attempts: 3, delayMs: 600, requireNonZero: false },
          );
          const noBalance = !bal || bal.amountLamports === '0';

          const reason: ReconcileReason | null = txReason || (noBalance ? 'no_onchain_balance' : null);
          if (!reason) continue;

          useSniperStore.getState().reconcilePosition(latest.id, reason);
          reconciled.push({
            symbol: latest.symbol || latest.mint.slice(0, 6),
            reason,
          });
        }

        if (reconciled.length > 0) {
          const byReason = reconciled.reduce<Record<ReconcileReason, number>>((acc, row) => {
            acc[row.reason] = (acc[row.reason] || 0) + 1;
            return acc;
          }, {
            no_onchain_balance: 0,
            buy_tx_unresolved: 0,
            buy_tx_failed: 0,
          });
          const sample = [...new Set(reconciled.map((r) => r.symbol))].slice(0, 6).join(', ');
          addExecution({
            id: `tx-reconcile-${Date.now()}`,
            type: 'info',
            symbol: 'SYNC',
            mint: '',
            amount: 0,
            reason: `Reconciled ${reconciled.length} position(s): ${byReason.no_onchain_balance} no-balance, ${byReason.buy_tx_unresolved} unresolved, ${byReason.buy_tx_failed} failed${sample ? ` (${sample})` : ''}`,
            timestamp: Date.now(),
          });
        }
      } finally {
        inFlightRef.current = false;
        setTxReconcilerRunning(false);
      }
    };

    void run();
    const timer = setInterval(() => {
      void run();
    }, RECONCILE_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
      inFlightRef.current = false;
      setTxReconcilerRunning(false);
    };
  }, [address, tradeSignerMode, sessionWalletPubkey, addExecution, setTxReconcilerRunning]);
}
