import React, { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X, CheckCircle, AlertCircle, AlertTriangle, Info } from 'lucide-react'

/**
 * Toast notification component
 */
function Toast({ id, type = 'info', title, message, duration = 5000, onClose }) {
  const [isVisible, setIsVisible] = useState(false)
  const [isExiting, setIsExiting] = useState(false)

  useEffect(() => {
    // Animate in
    requestAnimationFrame(() => setIsVisible(true))

    // Auto dismiss
    if (duration > 0) {
      const timer = setTimeout(() => handleClose(), duration)
      return () => clearTimeout(timer)
    }
  }, [duration])

  const handleClose = () => {
    setIsExiting(true)
    setTimeout(() => onClose(id), 200)
  }

  const icons = {
    success: CheckCircle,
    error: AlertCircle,
    warning: AlertTriangle,
    info: Info,
  }

  const colors = {
    success: { bg: 'var(--success-bg)', border: 'var(--success)', icon: 'var(--success)' },
    error: { bg: 'var(--danger-bg)', border: 'var(--danger)', icon: 'var(--danger)' },
    warning: { bg: 'var(--warning-bg)', border: 'var(--warning)', icon: 'var(--warning)' },
    info: { bg: 'var(--info-bg)', border: 'var(--info)', icon: 'var(--info)' },
  }

  const Icon = icons[type]
  const color = colors[type]

  return (
    <div
      className={`
        flex items-start gap-3 p-4 rounded-xl shadow-lg mb-3
        transition-all duration-200 ease-out max-w-sm
        ${isVisible && !isExiting ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-4'}
      `}
      style={{
        background: 'var(--bg-primary)',
        border: `1px solid ${color.border}`,
        borderLeft: `4px solid ${color.border}`,
      }}
      role="alert"
    >
      <Icon size={20} style={{ color: color.icon, flexShrink: 0, marginTop: 2 }} />
      
      <div className="flex-1 min-w-0">
        {title && (
          <p className="font-semibold text-sm mb-1" style={{ color: 'var(--text-primary)' }}>
            {title}
          </p>
        )}
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          {message}
        </p>
      </div>
      
      <button
        onClick={handleClose}
        className="flex-shrink-0 p-1 rounded-md hover:bg-gray-100 transition-colors"
        style={{ color: 'var(--text-tertiary)' }}
      >
        <X size={16} />
      </button>
    </div>
  )
}

/**
 * ToastContainer - Portal for toast notifications
 */
export function ToastContainer({ toasts, onRemove }) {
  if (typeof window === 'undefined') return null

  return createPortal(
    <div
      className="fixed bottom-6 right-6 z-[700] flex flex-col items-end"
      style={{ pointerEvents: 'none' }}
    >
      {toasts.map(toast => (
        <div key={toast.id} style={{ pointerEvents: 'auto' }}>
          <Toast {...toast} onClose={onRemove} />
        </div>
      ))}
    </div>,
    document.body
  )
}

/**
 * useToast hook - Manage toast notifications
 */
let toastId = 0

export function useToast() {
  const [toasts, setToasts] = useState([])

  const addToast = (options) => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, ...options }])
    return id
  }

  const removeToast = (id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }

  const toast = {
    success: (message, title) => addToast({ type: 'success', message, title }),
    error: (message, title) => addToast({ type: 'error', message, title }),
    warning: (message, title) => addToast({ type: 'warning', message, title }),
    info: (message, title) => addToast({ type: 'info', message, title }),
  }

  return { toasts, toast, removeToast, ToastContainer }
}

export default Toast
