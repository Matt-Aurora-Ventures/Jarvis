'use client';

import { useEffect, useRef } from 'react';
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
