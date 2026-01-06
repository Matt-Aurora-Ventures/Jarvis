import React from 'react'

/**
 * Skeleton - Loading placeholder component
 */
function Skeleton({ 
  width, 
  height, 
  rounded = 'md',
  className = '',
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
      className={`skeleton ${roundedStyles[rounded]} ${className}`}
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

Skeleton.Text = SkeletonText
Skeleton.Card = SkeletonCard

export default Skeleton
