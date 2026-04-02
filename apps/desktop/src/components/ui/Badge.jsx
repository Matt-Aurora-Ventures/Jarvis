import React from 'react'

/**
 * Badge - Status indicator component
 * 
 * Variants: default, success, warning, danger, info
 * Sizes: sm, md
 */
function Badge({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className = '',
  ...props
}) {
  const variantStyles = {
    default: 'badge',
    success: 'badge badge-success',
    warning: 'badge badge-warning',
    danger: 'badge badge-danger',
    info: 'badge badge-info',
  }
  
  const sizeStyles = {
    sm: 'badge-sm',
    md: '',
  }

  const classes = [
    variantStyles[variant],
    sizeStyles[size],
    dot && 'badge-dot',
    className,
  ].filter(Boolean).join(' ')

  return (
    <span className={classes} {...props}>
      {dot && <span className="badge-dot-indicator" />}
      {children}
    </span>
  )
}

export default Badge
