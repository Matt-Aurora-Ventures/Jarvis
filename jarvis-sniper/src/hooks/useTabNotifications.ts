'use client';

import { useEffect, useRef } from 'react';
import { toast } from 'sonner';
import { useSniperStore } from '@/stores/useSniperStore';
import { playNotificationSound } from '@/lib/notification-sound';

const ORIGINAL_TITLE = 'Jarvis Sniper';

/**
 * Flashes the browser tab title when important events occur:
 * - Snipe executed
 * - TP/SL/Trail triggered
 * - Errors
 *
 * Resets when the user focuses the tab.
 */
export function useTabNotifications() {
  const prevCountRef = useRef<number>(0);
  const flashIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Subscribe to store changes (Zustand v4 API: single callback)
    const unsubscribe = useSniperStore.subscribe((state) => {
        const newLen = state.executionLog.length;
        if (newLen <= prevCountRef.current) {
          prevCountRef.current = newLen;
          return;
        }

        const latest = state.executionLog[0]; // most recent is first
        if (!latest) return;

        prevCountRef.current = newLen;

        // Only notify for important events
        const important = ['snipe', 'tp_exit', 'sl_exit', 'exit_pending', 'error'];
        if (!important.includes(latest.type)) return;

        // Play sound for all important events (even when focused)
        playNotificationSound(latest.type);

        // Show toast popup
        const amountStr = latest.amount ? `${latest.amount} SOL` : '';
        if (latest.type === 'snipe') {
          toast.success(`Sniped ${latest.symbol}`, {
            description: amountStr ? `${amountStr} swap submitted` : 'Swap submitted',
            duration: 5000,
          });
        } else if (latest.type === 'tp_exit') {
          toast.success(`TP Hit — ${latest.symbol}`, {
            description: `Take profit triggered${amountStr ? ` (${amountStr})` : ''}`,
            duration: 5000,
          });
        } else if (latest.type === 'sl_exit') {
          toast.warning(`SL Hit — ${latest.symbol}`, {
            description: `Stop loss triggered${amountStr ? ` (${amountStr})` : ''}`,
            duration: 5000,
          });
        } else if (latest.type === 'error') {
          toast.error(`Error — ${latest.symbol}`, {
            description: latest.reason?.slice(0, 80) || 'Swap failed',
            duration: 8000,
          });
        } else if (latest.type === 'exit_pending') {
          toast.info(`Approve exit — ${latest.symbol}`, {
            description: 'Phantom approval needed',
            duration: 10000,
          });
        }

        // Don't flash title if tab is already focused
        if (document.hasFocus()) return;

        // Build flash title
        const prefix = latest.type === 'snipe' ? 'SNIPE'
          : latest.type === 'tp_exit' ? 'TP HIT'
          : latest.type === 'sl_exit' ? 'SL HIT'
          : latest.type === 'exit_pending' ? 'APPROVE'
          : 'ERROR';

        const flashTitle = `[${prefix}] ${latest.symbol} — Jarvis Sniper`;

        // Clear existing flash
        if (flashIntervalRef.current) {
          clearInterval(flashIntervalRef.current);
        }

        // Flash between original and alert title
        let showFlash = true;
        flashIntervalRef.current = setInterval(() => {
          document.title = showFlash ? flashTitle : ORIGINAL_TITLE;
          showFlash = !showFlash;
        }, 1000);
    });

    // Stop flashing when tab gains focus
    const handleFocus = () => {
      if (flashIntervalRef.current) {
        clearInterval(flashIntervalRef.current);
        flashIntervalRef.current = null;
      }
      document.title = ORIGINAL_TITLE;
    };

    window.addEventListener('focus', handleFocus);

    return () => {
      unsubscribe();
      window.removeEventListener('focus', handleFocus);
      if (flashIntervalRef.current) clearInterval(flashIntervalRef.current);
      document.title = ORIGINAL_TITLE;
    };
  }, []);
}
