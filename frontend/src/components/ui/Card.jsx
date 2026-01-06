import React from 'react'

/**
 * Card - Container component with header/body/footer sections
 * 
 * Variants: default, elevated, bordered
 */
function Card({ 
  children, 
  variant = 'default',
  className = '',
  ...props 
}) {
  const variantStyles = {
    default: 'card',
    elevated: 'card card-elevated',
    bordered: 'card card-bordered',
  }

  return (
    <div className={`${variantStyles[variant]} ${className}`} {...props}>
      {children}
    </div>
  )
}

function CardHeader({ children, className = '', actions, ...props }) {
  return (
    <div className={`card-header ${className}`} {...props}>
      {typeof children === 'string' ? (
        <div className="card-title">{children}</div>
      ) : (
        children
      )}
      {actions && <div className="card-actions">{actions}</div>}
    </div>
  )
}

function CardTitle({ children, icon: Icon, className = '', ...props }) {
  return (
    <div className={`card-title ${className}`} {...props}>
      {Icon && <Icon className="card-title-icon" size={20} />}
      {children}
    </div>
  )
}

function CardBody({ children, className = '', ...props }) {
  return (
    <div className={`card-body ${className}`} {...props}>
      {children}
    </div>
  )
}

function CardFooter({ children, className = '', ...props }) {
  return (
    <div className={`card-footer ${className}`} {...props}>
      {children}
    </div>
  )
}

Card.Header = CardHeader
Card.Title = CardTitle
Card.Body = CardBody
Card.Footer = CardFooter

export default Card
