import React from 'react'
import { Search } from 'lucide-react'

/**
 * Input - Form input component
 * 
 * Variants: default, search
 * Sizes: sm, md, lg
 */
const Input = React.forwardRef(({
  type = 'text',
  variant = 'default',
  size = 'md',
  error = false,
  icon: Icon,
  className = '',
  ...props
}, ref) => {
  const sizeStyles = {
    sm: 'input-sm',
    md: '',
    lg: 'input-lg',
  }

  const classes = [
    'input',
    sizeStyles[size],
    error && 'input-error',
    Icon && 'input-with-icon',
    className,
  ].filter(Boolean).join(' ')

  if (variant === 'search') {
    return (
      <div className="input-search-wrapper">
        <Search size={16} className="input-search-icon" />
        <input
          ref={ref}
          type="text"
          className={`input input-search ${classes}`}
          {...props}
        />
      </div>
    )
  }

  if (Icon) {
    return (
      <div className="input-icon-wrapper">
        <Icon size={16} className="input-icon" />
        <input ref={ref} type={type} className={classes} {...props} />
      </div>
    )
  }

  return <input ref={ref} type={type} className={classes} {...props} />
})

Input.displayName = 'Input'

export default Input
