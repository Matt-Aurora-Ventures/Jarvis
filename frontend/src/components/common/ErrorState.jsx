import React from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui'

/**
 * ErrorState - Display error messages with retry option
 */
export function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred. Please try again.',
  onRetry,
  icon: Icon = AlertCircle,
  className = '',
}) {
  return (
    <div className={`flex flex-col items-center justify-center p-10 text-center ${className}`}>
      <div 
        className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
        style={{ background: 'var(--danger-bg)' }}
      >
        <Icon size={32} style={{ color: 'var(--danger)' }} />
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
      
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          <RefreshCw size={16} />
          Try Again
        </Button>
      )}
    </div>
  )
}

/**
 * ErrorBoundary - Catch React component errors
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorState
          title="Component Error"
          message={this.state.error?.message || 'This component failed to render.'}
          onRetry={this.handleRetry}
        />
      )
    }

    return this.props.children
  }
}

export default ErrorState
