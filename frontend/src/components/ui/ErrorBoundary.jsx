import React from 'react'
import { AlertTriangle, RefreshCw, Home, ChevronDown, ChevronUp, Bug } from 'lucide-react'

/**
 * ErrorBoundary - Catches JavaScript errors in child components
 *
 * Features:
 * - Graceful error display instead of blank screen
 * - Error details for debugging
 * - Recovery options (retry, go home)
 * - Error reporting callback
 */
export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      showDetails: false,
    }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo })

    // Call error reporting callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }

    // Log to console in development
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
    if (this.props.onRetry) {
      this.props.onRetry()
    }
  }

  handleGoHome = () => {
    window.location.href = '/'
  }

  toggleDetails = () => {
    this.setState(prev => ({ showDetails: !prev.showDetails }))
  }

  render() {
    if (this.state.hasError) {
      // Custom fallback UI if provided
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry)
      }

      const { error, errorInfo, showDetails } = this.state
      const { variant = 'full', title = 'Something went wrong' } = this.props

      // Compact variant for smaller components
      if (variant === 'compact') {
        return (
          <div className="error-boundary-compact">
            <AlertTriangle size={16} />
            <span>{title}</span>
            <button onClick={this.handleRetry} className="btn btn-ghost btn-xs">
              <RefreshCw size={12} />
            </button>
            <style jsx>{`
              .error-boundary-compact {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px 16px;
                background: var(--bg-secondary);
                border: 1px solid var(--color-error);
                border-radius: 8px;
                color: var(--color-error);
                font-size: 14px;
              }
            `}</style>
          </div>
        )
      }

      // Full variant (default)
      return (
        <div className="error-boundary">
          <div className="error-content">
            <div className="error-icon">
              <AlertTriangle size={48} />
            </div>

            <h2 className="error-title">{title}</h2>

            <p className="error-message">
              {error?.message || 'An unexpected error occurred. Please try again.'}
            </p>

            <div className="error-actions">
              <button onClick={this.handleRetry} className="btn btn-primary">
                <RefreshCw size={16} />
                Try Again
              </button>
              <button onClick={this.handleGoHome} className="btn btn-secondary">
                <Home size={16} />
                Go Home
              </button>
            </div>

            {errorInfo && (
              <div className="error-details-toggle">
                <button onClick={this.toggleDetails} className="btn btn-ghost btn-sm">
                  <Bug size={14} />
                  {showDetails ? 'Hide' : 'Show'} Details
                  {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
            )}

            {showDetails && errorInfo && (
              <div className="error-details">
                <h4>Error Stack:</h4>
                <pre>{error?.stack}</pre>
                <h4>Component Stack:</h4>
                <pre>{errorInfo.componentStack}</pre>
              </div>
            )}
          </div>

          <style jsx>{`
            .error-boundary {
              display: flex;
              align-items: center;
              justify-content: center;
              min-height: 300px;
              padding: 24px;
            }

            .error-content {
              max-width: 500px;
              text-align: center;
            }

            .error-icon {
              color: var(--color-error);
              margin-bottom: 16px;
            }

            .error-title {
              font-size: 24px;
              font-weight: 600;
              color: var(--text-primary);
              margin: 0 0 12px 0;
            }

            .error-message {
              color: var(--text-secondary);
              font-size: 16px;
              margin: 0 0 24px 0;
              line-height: 1.5;
            }

            .error-actions {
              display: flex;
              gap: 12px;
              justify-content: center;
              margin-bottom: 16px;
            }

            .error-details-toggle {
              margin-top: 16px;
            }

            .error-details {
              margin-top: 16px;
              text-align: left;
              background: var(--bg-secondary);
              border-radius: 8px;
              padding: 16px;
              max-height: 300px;
              overflow: auto;
            }

            .error-details h4 {
              font-size: 12px;
              font-weight: 600;
              color: var(--text-secondary);
              margin: 0 0 8px 0;
              text-transform: uppercase;
              letter-spacing: 0.5px;
            }

            .error-details h4:not(:first-child) {
              margin-top: 16px;
            }

            .error-details pre {
              margin: 0;
              font-size: 12px;
              color: var(--text-tertiary);
              white-space: pre-wrap;
              word-break: break-word;
            }
          `}</style>
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * withErrorBoundary - HOC to wrap components with error boundary
 */
export function withErrorBoundary(Component, errorBoundaryProps = {}) {
  return function WrappedComponent(props) {
    return (
      <ErrorBoundary {...errorBoundaryProps}>
        <Component {...props} />
      </ErrorBoundary>
    )
  }
}

/**
 * useErrorHandler - Hook for handling errors in functional components
 * Throws errors to be caught by the nearest ErrorBoundary
 */
export function useErrorHandler() {
  const [error, setError] = React.useState(null)

  if (error) {
    throw error
  }

  const handleError = React.useCallback((err) => {
    setError(err)
  }, [])

  const resetError = React.useCallback(() => {
    setError(null)
  }, [])

  return { handleError, resetError }
}

/**
 * ErrorFallback - Simple fallback component for use with ErrorBoundary
 */
export function ErrorFallback({ error, onRetry, message = 'Something went wrong' }) {
  return (
    <div className="error-fallback">
      <AlertTriangle size={24} />
      <p>{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn btn-secondary btn-sm">
          <RefreshCw size={14} />
          Retry
        </button>
      )}
      <style jsx>{`
        .error-fallback {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          padding: 24px;
          color: var(--color-error);
          text-align: center;
        }
        .error-fallback p {
          margin: 0;
          color: var(--text-secondary);
        }
      `}</style>
    </div>
  )
}

export default ErrorBoundary
