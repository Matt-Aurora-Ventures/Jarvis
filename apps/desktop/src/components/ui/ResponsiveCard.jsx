import React from 'react'
import { useIsMobile } from '../../hooks/useMediaQuery'

/**
 * Responsive Card Component
 * Adapts padding, spacing, and layout based on screen size
 */
export function ResponsiveCard({
  children,
  className = '',
  title,
  subtitle,
  icon: Icon,
  actions,
  collapsible = false,
  defaultExpanded = true,
  noPadding = false,
  ...props
}) {
  const isMobile = useIsMobile()
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded)

  const padding = noPadding ? '' : isMobile ? 'p-3' : 'p-4 lg:p-6'

  return (
    <div
      className={`
        bg-gray-800/50 backdrop-blur-sm rounded-lg lg:rounded-xl
        border border-gray-700 overflow-hidden
        ${className}
      `}
      {...props}
    >
      {/* Header */}
      {(title || actions) && (
        <div
          className={`
            flex items-center justify-between gap-3
            ${noPadding ? 'p-3 lg:p-4' : padding}
            ${children ? 'border-b border-gray-700/50' : ''}
          `}
          onClick={collapsible ? () => setIsExpanded(!isExpanded) : undefined}
          style={collapsible ? { cursor: 'pointer' } : undefined}
        >
          <div className="flex items-center gap-2 lg:gap-3 min-w-0">
            {Icon && (
              <div className="p-1.5 lg:p-2 rounded-lg bg-gray-700/50 text-cyan-400 flex-shrink-0">
                <Icon size={isMobile ? 16 : 20} />
              </div>
            )}
            <div className="min-w-0">
              {title && (
                <h3 className="text-sm lg:text-base font-semibold text-white truncate">
                  {title}
                </h3>
              )}
              {subtitle && (
                <p className="text-xs text-gray-400 truncate">{subtitle}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {actions}
            {collapsible && (
              <button className="p-1 text-gray-400 hover:text-white transition-colors">
                <svg
                  className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      )}

      {/* Content */}
      {(!collapsible || isExpanded) && children && (
        <div className={padding}>{children}</div>
      )}
    </div>
  )
}

/**
 * Responsive Stats Card
 * Optimized for displaying metric values
 */
export function ResponsiveStatsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendLabel,
  color = 'cyan',
  className = '',
}) {
  const isMobile = useIsMobile()

  const colorClasses = {
    cyan: 'text-cyan-400 bg-cyan-500/10',
    green: 'text-green-400 bg-green-500/10',
    red: 'text-red-400 bg-red-500/10',
    yellow: 'text-yellow-400 bg-yellow-500/10',
    purple: 'text-purple-400 bg-purple-500/10',
    blue: 'text-blue-400 bg-blue-500/10',
  }

  const trendColors = {
    up: 'text-green-400',
    down: 'text-red-400',
    neutral: 'text-gray-400',
  }

  return (
    <div
      className={`
        bg-gray-800/50 backdrop-blur-sm rounded-lg border border-gray-700
        p-3 lg:p-4 ${className}
      `}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-xs lg:text-sm text-gray-400 truncate">{title}</p>
          <p className={`text-lg lg:text-2xl font-bold text-white mt-0.5 truncate`}>
            {value}
          </p>
          {subtitle && (
            <p className="text-xs text-gray-500 mt-0.5 truncate">{subtitle}</p>
          )}
          {trend !== undefined && (
            <div className={`flex items-center gap-1 mt-1 ${trendColors[trend > 0 ? 'up' : trend < 0 ? 'down' : 'neutral']}`}>
              {trend > 0 ? (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 10l7-7m0 0l7 7m-7-7v18" />
                </svg>
              ) : trend < 0 ? (
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
              ) : null}
              <span className="text-xs">
                {Math.abs(trend)}% {trendLabel}
              </span>
            </div>
          )}
        </div>

        {Icon && (
          <div className={`p-2 rounded-lg ${colorClasses[color]} flex-shrink-0`}>
            <Icon size={isMobile ? 16 : 20} />
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * Responsive Grid Container
 * Auto-adjusts columns based on screen size
 */
export function ResponsiveGrid({
  children,
  cols = { xs: 1, sm: 2, md: 3, lg: 4 },
  gap = { xs: 3, lg: 4 },
  className = '',
}) {
  const colClasses = Object.entries(cols)
    .map(([bp, count]) => {
      if (bp === 'xs') return `grid-cols-${count}`
      return `${bp}:grid-cols-${count}`
    })
    .join(' ')

  const gapClasses = Object.entries(gap)
    .map(([bp, size]) => {
      if (bp === 'xs') return `gap-${size}`
      return `${bp}:gap-${size}`
    })
    .join(' ')

  return (
    <div className={`grid ${colClasses} ${gapClasses} ${className}`}>
      {children}
    </div>
  )
}

/**
 * Responsive Action Bar
 * Stacks buttons on mobile, inline on desktop
 */
export function ResponsiveActionBar({
  children,
  align = 'end',
  className = '',
}) {
  const alignClasses = {
    start: 'justify-start',
    center: 'justify-center',
    end: 'justify-end',
    between: 'justify-between',
  }

  return (
    <div
      className={`
        flex flex-col gap-2
        sm:flex-row sm:items-center ${alignClasses[align]}
        ${className}
      `}
    >
      {React.Children.map(children, (child) =>
        React.cloneElement(child, {
          className: `${child.props.className || ''} w-full sm:w-auto`,
        })
      )}
    </div>
  )
}

export default ResponsiveCard
