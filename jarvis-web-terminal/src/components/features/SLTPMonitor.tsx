'use client';

import { useStopLossMonitor, type SLTPEvent } from '@/lib/stop-loss-manager';
import { useToast } from '@/components/ui/Toast';
import { playNotificationSound } from '@/lib/notification-sound';
import { useNotificationStore } from '@/stores/useNotificationStore';

/**
 * SLTPMonitor
 *
 * Invisible component that activates the stop-loss/take-profit monitor
 * and shows toast notifications when thresholds are crossed.
 * Also plays sound alerts and persists events to the notification store.
 *
 * Place anywhere in the component tree (inside ToastProvider).
 * Renders nothing to the DOM.
 */
export function SLTPMonitor() {
  const toast = useToast();
  const addNotification = useNotificationStore((s) => s.addNotification);

  useStopLossMonitor((event: SLTPEvent) => {
    // Persist to notification store
    addNotification({
      type: event.type,
      tokenSymbol: event.tokenSymbol,
      entryPrice: event.entryPrice,
      triggerPrice: event.currentPrice,
      changePercent: event.changePercent,
      timestamp: Date.now(),
    });

    if (event.type === 'stop_loss') {
      // Play descending error sound
      playNotificationSound('error');
      toast.error(
        `Stop Loss triggered for ${event.tokenSymbol}! ` +
        `Entry: $${event.entryPrice.toFixed(4)} -> $${event.currentPrice.toFixed(4)} (${event.changePercent.toFixed(1)}%)`
      );
    } else {
      // Play ascending success sound
      playNotificationSound('success');
      toast.success(
        `Take Profit hit for ${event.tokenSymbol}! ` +
        `Entry: $${event.entryPrice.toFixed(4)} -> $${event.currentPrice.toFixed(4)} (+${event.changePercent.toFixed(1)}%)`
      );
    }
  });

  return null;
}
