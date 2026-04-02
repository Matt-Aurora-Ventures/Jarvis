import React, { useState, useEffect, useCallback } from 'react'
import { Bell, X, Check, AlertTriangle, Info, Trash2 } from 'lucide-react'

/**
 * NotificationCenter component
 * Centralized notification management with persistent storage
 */
export default function NotificationCenter() {
  const [notifications, setNotifications] = useState([])
  const [isOpen, setIsOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    // Load notifications from storage
    const stored = localStorage.getItem('jarvis_notifications')
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        setNotifications(parsed)
        setUnreadCount(parsed.filter(n => !n.read).length)
      } catch (e) {
        console.error('Failed to parse notifications:', e)
      }
    }

    // Listen for new notifications
    const handleNotification = (event) => {
      const { type, title, message, timestamp } = event.detail
      addNotification(type, title, message)
    }

    window.addEventListener('jarvis-notification', handleNotification)

    // Listen for Electron notifications
    if (window.electronAPI) {
      window.electronAPI.onJarvisLog((data) => {
        if (data.includes('ERROR') || data.includes('WARN')) {
          addNotification('warning', 'Backend Warning', data.slice(0, 100))
        }
      })

      window.electronAPI.onJarvisError((data) => {
        addNotification('error', 'Backend Error', data.slice(0, 100))
      })
    }

    return () => {
      window.removeEventListener('jarvis-notification', handleNotification)
    }
  }, [])

  const addNotification = useCallback((type, title, message) => {
    const notification = {
      id: Date.now(),
      type, // 'info', 'success', 'warning', 'error'
      title,
      message,
      timestamp: new Date().toISOString(),
      read: false,
    }

    setNotifications(prev => {
      const updated = [notification, ...prev].slice(0, 50) // Keep last 50
      localStorage.setItem('jarvis_notifications', JSON.stringify(updated))
      return updated
    })
    setUnreadCount(prev => prev + 1)

    // Show native notification if available
    if (window.electronAPI && Notification.permission === 'granted') {
      window.electronAPI.showNotification(title, message)
    }
  }, [])

  const markAsRead = (id) => {
    setNotifications(prev => {
      const updated = prev.map(n =>
        n.id === id ? { ...n, read: true } : n
      )
      localStorage.setItem('jarvis_notifications', JSON.stringify(updated))
      return updated
    })
    setUnreadCount(prev => Math.max(0, prev - 1))
  }

  const markAllAsRead = () => {
    setNotifications(prev => {
      const updated = prev.map(n => ({ ...n, read: true }))
      localStorage.setItem('jarvis_notifications', JSON.stringify(updated))
      return updated
    })
    setUnreadCount(0)
  }

  const clearAll = () => {
    setNotifications([])
    setUnreadCount(0)
    localStorage.removeItem('jarvis_notifications')
  }

  const deleteNotification = (id) => {
    setNotifications(prev => {
      const notification = prev.find(n => n.id === id)
      const updated = prev.filter(n => n.id !== id)
      localStorage.setItem('jarvis_notifications', JSON.stringify(updated))
      if (notification && !notification.read) {
        setUnreadCount(c => Math.max(0, c - 1))
      }
      return updated
    })
  }

  const getIcon = (type) => {
    switch (type) {
      case 'success': return <Check className="w-4 h-4 text-green-400" />
      case 'warning': return <AlertTriangle className="w-4 h-4 text-yellow-400" />
      case 'error': return <AlertTriangle className="w-4 h-4 text-red-400" />
      default: return <Info className="w-4 h-4 text-blue-400" />
    }
  }

  const formatTime = (timestamp) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date

    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return date.toLocaleDateString()
  }

  return (
    <div className="relative">
      {/* Bell icon with badge */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-white transition-colors"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-xs text-white flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between p-3 border-b border-gray-700">
            <span className="font-medium text-white">Notifications</span>
            <div className="flex items-center gap-2">
              <button
                onClick={markAllAsRead}
                className="text-xs text-blue-400 hover:text-blue-300"
              >
                Mark all read
              </button>
              <button
                onClick={clearAll}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Clear all
              </button>
            </div>
          </div>

          {/* Notifications list */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No notifications
              </div>
            ) : (
              notifications.map(notification => (
                <div
                  key={notification.id}
                  className={`p-3 border-b border-gray-800 hover:bg-gray-800/50 transition-colors ${
                    !notification.read ? 'bg-gray-800/30' : ''
                  }`}
                  onClick={() => markAsRead(notification.id)}
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      {getIcon(notification.type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-white text-sm truncate">
                          {notification.title}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteNotification(notification.id)
                          }}
                          className="text-gray-500 hover:text-red-400"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                      <p className="text-xs text-gray-400 mt-0.5 truncate">
                        {notification.message}
                      </p>
                      <span className="text-xs text-gray-500 mt-1 block">
                        {formatTime(notification.timestamp)}
                      </span>
                    </div>
                    {!notification.read && (
                      <div className="w-2 h-2 bg-blue-500 rounded-full mt-2" />
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// Helper to trigger notifications from anywhere in the app
export function triggerNotification(type, title, message) {
  window.dispatchEvent(new CustomEvent('jarvis-notification', {
    detail: { type, title, message, timestamp: new Date().toISOString() }
  }))
}
