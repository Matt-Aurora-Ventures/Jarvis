import React from 'react'

/**
 * LoadingSpinner - Animated loading indicator
 */
export function LoadingSpinner({ size = 'md', className = '' }) {
  const sizes = {
    sm: 'w-4 h-4 border-2',
    md: 'w-6 h-6 border-2',
    lg: 'w-10 h-10 border-3',
    xl: 'w-16 h-16 border-4',
  }

  return (
    <div
      className={`
        ${sizes[size]}
        border-gray-200 border-t-primary rounded-full animate-spin
        ${className}
      `}
      style={{
        borderTopColor: 'var(--primary)',
        borderRightColor: 'var(--border-light)',
        borderBottomColor: 'var(--border-light)',
        borderLeftColor: 'var(--border-light)',
      }}
      role="status"
      aria-label="Loading"
    />
  )
}

/**
 * LoadingOverlay - Full-screen or container loading state
 */
export function LoadingOverlay({ message = 'Loading...' }) {
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/80 backdrop-blur-sm z-50">
      <LoadingSpinner size="lg" />
      <p className="mt-4 text-sm text-secondary">{message}</p>
    </div>
  )
}

/**
 * LoadingCard - Card-shaped loading skeleton
 */
export function LoadingCard() {
  return (
    <div className="card p-6 animate-pulse">
      <div className="flex items-center gap-3 mb-4">
        <div className="skeleton w-10 h-10 rounded-lg" />
        <div className="flex-1">
          <div className="skeleton h-4 w-24 mb-2" />
          <div className="skeleton h-3 w-16" />
        </div>
      </div>
      <div className="space-y-2">
        <div className="skeleton h-3 w-full" />
        <div className="skeleton h-3 w-3/4" />
      </div>
    </div>
  )
}

export default LoadingSpinner
