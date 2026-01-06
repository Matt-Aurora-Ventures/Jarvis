import React from 'react'
import { Inbox, Search, FileQuestion, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui'

/**
 * EmptyState - Display when no data/content available
 */
export function EmptyState({
  icon: Icon = Inbox,
  title = 'No data yet',
  message = 'There\'s nothing here right now.',
  action,
  actionLabel = 'Get Started',
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center p-10 text-center ${className}`}>
      <div 
        className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
        style={{ background: 'var(--bg-tertiary)' }}
      >
        <Icon size={32} style={{ color: 'var(--text-tertiary)' }} />
      </div>
      
      <h3 
        className="text-lg font-semibold mb-2"
        style={{ color: 'var(--text-primary)' }}
      >
        {title}
      </h3>
      
      <p 
        className="text-sm max-w-xs mb-6"
        style={{ color: 'var(--text-secondary)' }}
      >
        {message}
      </p>
      
      {action && (
        <Button variant="primary" onClick={action}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}

/**
 * NoResults - Empty state for search results
 */
export function NoResults({ query, onClear }) {
  return (
    <EmptyState
      icon={Search}
      title="No results found"
      message={`We couldn't find anything matching "${query}". Try a different search term.`}
      action={onClear}
      actionLabel="Clear Search"
    />
  )
}

/**
 * NotFound - 404 style empty state
 */
export function NotFound({ onGoBack }) {
  return (
    <EmptyState
      icon={FileQuestion}
      title="Page not found"
      message="The page you're looking for doesn't exist or has been moved."
      action={onGoBack}
      actionLabel="Go Back"
    />
  )
}

/**
 * NoPosition - Trading specific empty state
 */
export function NoPosition({ onScan }) {
  return (
    <EmptyState
      icon={AlertTriangle}
      title="No Active Position"
      message="Sniper is idle. Scan for opportunities or configure auto-snipe settings."
      action={onScan}
      actionLabel="Scan Tokens"
    />
  )
}

export default EmptyState
