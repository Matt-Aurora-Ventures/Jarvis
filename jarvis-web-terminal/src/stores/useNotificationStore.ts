'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Notification {
  id: string;
  type: 'stop_loss' | 'take_profit';
  tokenSymbol: string;
  entryPrice: number;
  triggerPrice: number;
  changePercent: number;
  timestamp: number;
  read: boolean;
}

export interface NotificationState {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (n: Omit<Notification, 'id' | 'read'>) => void;
  markAllRead: () => void;
  clearAll: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Maximum number of notifications to keep in the store */
const MAX_NOTIFICATIONS = 50;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set) => ({
      notifications: [],
      unreadCount: 0,

      addNotification: (n) =>
        set((state) => {
          const newNotification: Notification = {
            ...n,
            id: generateId(),
            read: false,
          };
          // Prepend (most recent first) and cap at MAX_NOTIFICATIONS
          const notifications = [newNotification, ...state.notifications].slice(
            0,
            MAX_NOTIFICATIONS,
          );
          const unreadCount = notifications.filter((x) => !x.read).length;
          return { notifications, unreadCount };
        }),

      markAllRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({
            ...n,
            read: true,
          })),
          unreadCount: 0,
        })),

      clearAll: () =>
        set({
          notifications: [],
          unreadCount: 0,
        }),
    }),
    {
      name: 'jarvis-notifications',
    },
  ),
);
