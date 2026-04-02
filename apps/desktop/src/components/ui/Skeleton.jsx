import React from 'react'

/**
 * Skeleton - Loading placeholder component with multiple variants
 */
function Skeleton({
  width,
  height,
  rounded = 'md',
  className = '',
  animate = true,
  ...props
}) {
  const roundedStyles = {
    none: '',
    sm: 'skeleton-rounded-sm',
    md: 'skeleton-rounded-md',
    lg: 'skeleton-rounded-lg',
    full: 'skeleton-rounded-full',
  }

  const style = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  }

  return (
    <div
      className={`skeleton ${roundedStyles[rounded]} ${animate ? 'skeleton-animate' : ''} ${className}`}
      style={style}
      {...props}
    />
  )
}

function SkeletonText({ lines = 3, className = '' }) {
  return (
    <div className={`skeleton-text ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height={16}
          width={i === lines - 1 ? '70%' : '100%'}
          rounded="sm"
        />
      ))}
    </div>
  )
}

function SkeletonCard({ className = '' }) {
  return (
    <div className={`skeleton-card ${className}`}>
      <Skeleton height={120} rounded="lg" />
      <div style={{ padding: '1rem' }}>
        <Skeleton height={20} width="60%" rounded="sm" />
        <SkeletonText lines={2} />
      </div>
    </div>
  )
}

/**
 * SkeletonPosition - Loading skeleton for trading positions
 */
function SkeletonPosition({ className = '' }) {
  return (
    <div className={`skeleton-position ${className}`} style={{
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      padding: '16px',
      background: 'var(--bg-secondary)',
      borderRadius: '8px',
    }}>
      {/* Token icon */}
      <Skeleton width={40} height={40} rounded="full" />

      {/* Token info */}
      <div style={{ flex: 1 }}>
        <Skeleton height={18} width="40%" rounded="sm" />
        <div style={{ height: '8px' }} />
        <Skeleton height={14} width="25%" rounded="sm" />
      </div>

      {/* Value */}
      <div style={{ textAlign: 'right' }}>
        <Skeleton height={18} width={80} rounded="sm" />
        <div style={{ height: '8px' }} />
        <Skeleton height={14} width={60} rounded="sm" />
      </div>
    </div>
  )
}

/**
 * SkeletonChart - Loading skeleton for price charts
 */
function SkeletonChart({ height = 200, className = '' }) {
  return (
    <div className={`skeleton-chart ${className}`} style={{
      height,
      padding: '16px',
      background: 'var(--bg-secondary)',
      borderRadius: '8px',
    }}>
      {/* Chart header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px' }}>
        <Skeleton height={24} width={120} rounded="sm" />
        <Skeleton height={24} width={80} rounded="sm" />
      </div>

      {/* Chart area */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: '4px',
        height: 'calc(100% - 60px)',
        paddingTop: '16px',
      }}>
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
            <Skeleton
              height={`${30 + Math.random() * 60}%`}
              width="100%"
              rounded="sm"
            />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * SkeletonStats - Loading skeleton for stats grid
 */
function SkeletonStats({ count = 4, className = '' }) {
  return (
    <div className={`skeleton-stats ${className}`} style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${Math.min(count, 4)}, 1fr)`,
      gap: '16px',
    }}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} style={{
          padding: '16px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
        }}>
          <Skeleton height={14} width="50%" rounded="sm" />
          <div style={{ height: '12px' }} />
          <Skeleton height={28} width="70%" rounded="sm" />
          <div style={{ height: '8px' }} />
          <Skeleton height={12} width="40%" rounded="sm" />
        </div>
      ))}
    </div>
  )
}

/**
 * SkeletonTable - Loading skeleton for data tables
 */
function SkeletonTable({ rows = 5, cols = 4, className = '' }) {
  return (
    <div className={`skeleton-table ${className}`} style={{
      background: 'var(--bg-secondary)',
      borderRadius: '8px',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: '16px',
        padding: '16px',
        borderBottom: '1px solid var(--border-primary)',
      }}>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} height={14} width="70%" rounded="sm" />
        ))}
      </div>

      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 1fr)`,
          gap: '16px',
          padding: '16px',
          borderBottom: rowIdx < rows - 1 ? '1px solid var(--border-primary)' : 'none',
        }}>
          {Array.from({ length: cols }).map((_, colIdx) => (
            <Skeleton
              key={colIdx}
              height={16}
              width={`${50 + Math.random() * 40}%`}
              rounded="sm"
            />
          ))}
        </div>
      ))}
    </div>
  )
}

/**
 * SkeletonMessage - Loading skeleton for chat messages
 */
function SkeletonMessage({ isUser = false, className = '' }) {
  return (
    <div className={`skeleton-message ${className}`} style={{
      display: 'flex',
      flexDirection: isUser ? 'row-reverse' : 'row',
      gap: '12px',
      marginBottom: '16px',
    }}>
      {/* Avatar */}
      <Skeleton width={36} height={36} rounded="full" />

      {/* Message bubble */}
      <div style={{
        maxWidth: '70%',
        padding: '12px 16px',
        background: 'var(--bg-secondary)',
        borderRadius: '16px',
      }}>
        <Skeleton height={14} width={200} rounded="sm" />
        <div style={{ height: '8px' }} />
        <Skeleton height={14} width={150} rounded="sm" />
      </div>
    </div>
  )
}

// Attach all variants to main component
Skeleton.Text = SkeletonText
Skeleton.Card = SkeletonCard
Skeleton.Position = SkeletonPosition
Skeleton.Chart = SkeletonChart
Skeleton.Stats = SkeletonStats
Skeleton.Table = SkeletonTable
Skeleton.Message = SkeletonMessage

export default Skeleton
export {
  Skeleton,
  SkeletonText,
  SkeletonCard,
  SkeletonPosition,
  SkeletonChart,
  SkeletonStats,
  SkeletonTable,
  SkeletonMessage
}
