import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info, Bell } from 'lucide-react'

/**
 * Notification System with Toast/Snackbar support
 *
 * Features:
 * - Multiple notification types (success, error, warning, info)
 * - Auto-dismiss with configurable duration
 * - Stack multiple notifications
 * - Actions and callbacks
 * - Persist option
 */

// Notification types with their config
const NOTIFICATION_TYPES = {
  success: {
    icon: CheckCircle,
    color: 'var(--success)',
    bgColor: 'rgba(34, 197, 94, 0.1)',
  },
  error: {
    icon: AlertCircle,
    color: 'var(--danger)',
    bgColor: 'rgba(239, 68, 68, 0.1)',
  },
  warning: {
    icon: AlertTriangle,
    color: 'var(--warning)',
    bgColor: 'rgba(245, 158, 11, 0.1)',
  },
  info: {
    icon: Info,
    color: 'var(--accent-primary)',
    bgColor: 'rgba(59, 130, 246, 0.1)',
  },
}

// Context for notifications
const NotificationContext = createContext(null)

/**
 * NotificationProvider - Wrap your app with this to enable notifications
 */
export function NotificationProvider({ children, position = 'bottom-right', maxNotifications = 5 }) {
  const [notifications, setNotifications] = useState([])

  // Add a notification
  const addNotification = useCallback((notification) => {
    const id = Date.now() + Math.random()
    const newNotification = {
      id,
      type: 'info',
      duration: 5000,
      dismissible: true,
      ...notification,
    }

    setNotifications((prev) => {
      const updated = [...prev, newNotification]
      return updated.slice(-maxNotifications) // Keep only last N notifications
    })

    // Auto-dismiss if duration is set
    if (newNotification.duration > 0 && !newNotification.persist) {
      setTimeout(() => {
        removeNotification(id)
      }, newNotification.duration)
    }

    return id
  }, [maxNotifications])

  // Remove a notification
  const removeNotification = useCallback((id) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
  }, [])

  // Clear all notifications
  const clearNotifications = useCallback(() => {
    setNotifications([])
  }, [])

  // Convenience methods
  const notify = {
    success: (message, options = {}) => addNotification({ type: 'success', message, ...options }),
    error: (message, options = {}) => addNotification({ type: 'error', message, duration: 8000, ...options }),
    warning: (message, options = {}) => addNotification({ type: 'warning', message, ...options }),
    info: (message, options = {}) => addNotification({ type: 'info', message, ...options }),
    custom: (notification) => addNotification(notification),
  }

  const value = {
    notifications,
    addNotification,
    removeNotification,
    clearNotifications,
    notify,
  }

  return (
    <NotificationContext.Provider value={value}>
      {children}
      <NotificationContainer
        notifications={notifications}
        position={position}
        onDismiss={removeNotification}
      />
    </NotificationContext.Provider>
  )
}

/**
 * useNotifications - Hook to access notification system
 */
export function useNotifications() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider')
  }
  return context
}

/**
 * NotificationContainer - Renders the notification stack
 */
function NotificationContainer({ notifications, position, onDismiss }) {
  const positionStyles = {
    'top-right': { top: 16, right: 16 },
    'top-left': { top: 16, left: 16 },
    'bottom-right': { bottom: 16, right: 16 },
    'bottom-left': { bottom: 16, left: 16 },
    'top-center': { top: 16, left: '50%', transform: 'translateX(-50%)' },
    'bottom-center': { bottom: 16, left: '50%', transform: 'translateX(-50%)' },
  }

  if (notifications.length === 0) return null

  return (
    <div className="notification-container" style={positionStyles[position]}>
      {notifications.map((notification) => (
        <NotificationItem
          key={notification.id}
          notification={notification}
          onDismiss={() => onDismiss(notification.id)}
        />
      ))}

      <style jsx>{`
        .notification-container {
          position: fixed;
          z-index: 9999;
          display: flex;
          flex-direction: column;
          gap: 8px;
          max-width: 400px;
          width: 100%;
          pointer-events: none;
        }

        .notification-container > :global(*) {
          pointer-events: auto;
        }
      `}</style>
    </div>
  )
}

/**
 * NotificationItem - Individual notification toast
 */
function NotificationItem({ notification, onDismiss }) {
  const { type, message, title, action, dismissible } = notification
  const config = NOTIFICATION_TYPES[type] || NOTIFICATION_TYPES.info
  const Icon = config.icon

  const [isExiting, setIsExiting] = useState(false)

  const handleDismiss = () => {
    setIsExiting(true)
    setTimeout(onDismiss, 200) // Wait for exit animation
  }

  return (
    <div className={`notification ${isExiting ? 'exiting' : ''}`}>
      <div className="notification-icon">
        <Icon size={20} />
      </div>

      <div className="notification-content">
        {title && <div className="notification-title">{title}</div>}
        <div className="notification-message">{message}</div>

        {action && (
          <button className="notification-action" onClick={action.onClick}>
            {action.label}
          </button>
        )}
      </div>

      {dismissible && (
        <button className="notification-dismiss" onClick={handleDismiss}>
          <X size={16} />
        </button>
      )}

      <style jsx>{`
        .notification {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 14px 16px;
          background: var(--bg-primary);
          border: 1px solid var(--border-primary);
          border-left: 4px solid ${config.color};
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          animation: slideIn 0.2s ease-out;
        }

        .notification.exiting {
          animation: slideOut 0.2s ease-in forwards;
        }

        .notification-icon {
          flex-shrink: 0;
          color: ${config.color};
        }

        .notification-content {
          flex: 1;
          min-width: 0;
        }

        .notification-title {
          font-weight: 600;
          font-size: 14px;
          color: var(--text-primary);
          margin-bottom: 4px;
        }

        .notification-message {
          font-size: 13px;
          color: var(--text-secondary);
          line-height: 1.4;
        }

        .notification-action {
          margin-top: 8px;
          padding: 4px 12px;
          font-size: 12px;
          font-weight: 500;
          color: ${config.color};
          background: ${config.bgColor};
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: opacity 0.2s;
        }

        .notification-action:hover {
          opacity: 0.8;
        }

        .notification-dismiss {
          flex-shrink: 0;
          padding: 4px;
          color: var(--text-tertiary);
          background: none;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: color 0.2s, background 0.2s;
        }

        .notification-dismiss:hover {
          color: var(--text-primary);
          background: var(--bg-secondary);
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateX(100%);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        @keyframes slideOut {
          from {
            opacity: 1;
            transform: translateX(0);
          }
          to {
            opacity: 0;
            transform: translateX(100%);
          }
        }
      `}</style>
    </div>
  )
}

/**
 * NotificationBell - Bell icon with unread count badge
 */
export function NotificationBell({ unreadCount = 0, onClick }) {
  return (
    <button className="notification-bell" onClick={onClick}>
      <Bell size={20} />
      {unreadCount > 0 && (
        <span className="notification-badge">
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}

      <style jsx>{`
        .notification-bell {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          background: none;
          border: none;
          border-radius: 8px;
          color: var(--text-secondary);
          cursor: pointer;
          transition: color 0.2s, background 0.2s;
        }

        .notification-bell:hover {
          color: var(--text-primary);
          background: var(--bg-secondary);
        }

        .notification-badge {
          position: absolute;
          top: 2px;
          right: 2px;
          min-width: 16px;
          height: 16px;
          padding: 0 4px;
          font-size: 10px;
          font-weight: 600;
          color: white;
          background: var(--danger);
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
        }
      `}</style>
    </button>
  )
}

export default NotificationProvider
