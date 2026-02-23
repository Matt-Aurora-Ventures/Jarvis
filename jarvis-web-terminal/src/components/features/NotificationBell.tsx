'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Bell, AlertTriangle, TrendingUp, Check, Trash2 } from 'lucide-react';
import { useNotificationStore, type Notification } from '@/stores/useNotificationStore';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function NotificationIcon({ type }: { type: Notification['type'] }) {
  if (type === 'stop_loss') {
    return <AlertTriangle className="w-4 h-4 text-accent-error shrink-0" />;
  }
  return <TrendingUp className="w-4 h-4 text-accent-neon shrink-0" />;
}

// ---------------------------------------------------------------------------
// NotificationItem
// ---------------------------------------------------------------------------

function NotificationItem({
  notification,
  onClick,
}: {
  notification: Notification;
  onClick: () => void;
}) {
  const isLoss = notification.type === 'stop_loss';
  const changeStr = isLoss
    ? `${notification.changePercent.toFixed(1)}%`
    : `+${notification.changePercent.toFixed(1)}%`;

  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-start gap-3 px-3 py-2.5 text-left transition-colors
        hover:bg-bg-tertiary/60 rounded-lg
        ${notification.read ? 'opacity-60' : ''}
      `}
    >
      <NotificationIcon type={notification.type} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-text-primary truncate">
            {notification.tokenSymbol}
          </span>
          <span
            className={`text-xs font-mono font-medium px-1.5 py-0.5 rounded ${
              isLoss
                ? 'bg-accent-error/10 text-accent-error'
                : 'bg-accent-neon/10 text-accent-neon'
            }`}
          >
            {changeStr}
          </span>
        </div>
        <p className="text-xs text-text-muted mt-0.5">
          {isLoss ? 'Stop Loss' : 'Take Profit'} at $
          {notification.triggerPrice.toFixed(4)}
        </p>
      </div>
      <span className="text-[10px] text-text-muted font-mono shrink-0 mt-0.5">
        {formatTimeAgo(notification.timestamp)}
      </span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// NotificationBell
// ---------------------------------------------------------------------------

export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { notifications, unreadCount, markAllRead, clearAll } =
    useNotificationStore();

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleToggle = () => {
    setOpen((prev) => !prev);
  };

  const handleNotificationClick = () => {
    setOpen(false);
    router.push('/positions');
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Button */}
      <button
        onClick={handleToggle}
        className="relative p-2.5 rounded-full bg-bg-tertiary hover:bg-bg-secondary border border-border-primary hover:border-border-hover transition-all"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <Bell className="w-5 h-5 text-text-secondary" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-accent-error text-[10px] font-bold flex items-center justify-center text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 max-h-96 bg-bg-secondary border border-border-primary rounded-xl shadow-xl overflow-hidden z-[100]">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-primary">
            <h3 className="text-sm font-semibold text-text-primary">
              Notifications
            </h3>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
                  title="Mark all read"
                >
                  <Check className="w-3 h-3" />
                  <span>Read</span>
                </button>
              )}
              {notifications.length > 0 && (
                <button
                  onClick={clearAll}
                  className="flex items-center gap-1 text-xs text-text-muted hover:text-accent-error transition-colors"
                  title="Clear all"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Clear</span>
                </button>
              )}
            </div>
          </div>

          {/* Notification List */}
          <div className="overflow-y-auto max-h-72 p-1">
            {notifications.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-text-muted">
                <Bell className="w-8 h-8 mb-2 opacity-30" />
                <p className="text-sm">No notifications yet</p>
                <p className="text-xs mt-1">
                  SL/TP alerts will appear here
                </p>
              </div>
            ) : (
              notifications.map((n) => (
                <NotificationItem
                  key={n.id}
                  notification={n}
                  onClick={handleNotificationClick}
                />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
