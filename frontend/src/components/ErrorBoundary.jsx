import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo })
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleReload = () => {
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#FFFFFF',
          padding: '2rem'
        }}>
          <div style={{
            maxWidth: '500px',
            textAlign: 'center',
            padding: '2rem',
            background: '#FEF2F2',
            borderRadius: '16px',
            border: '1px solid #FECACA'
          }}>
            <AlertTriangle size={48} style={{ color: '#EF4444', marginBottom: '1rem' }} />
            <h2 style={{ 
              fontSize: '1.5rem', 
              fontWeight: 600, 
              color: '#111827',
              marginBottom: '0.5rem'
            }}>
              Something went wrong
            </h2>
            <p style={{ 
              color: '#6B7280', 
              marginBottom: '1.5rem',
              fontSize: '0.875rem'
            }}>
              Jarvis encountered an unexpected error. Please try reloading the page.
            </p>
            
            {this.state.error && (
              <details style={{
                textAlign: 'left',
                marginBottom: '1.5rem',
                padding: '1rem',
                background: '#FFF',
                borderRadius: '8px',
                fontSize: '0.75rem',
                color: '#DC2626'
              }}>
                <summary style={{ cursor: 'pointer', fontWeight: 500 }}>
                  Error Details
                </summary>
                <pre style={{ 
                  marginTop: '0.5rem', 
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word'
                }}>
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
            
            <button
              onClick={this.handleReload}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 24px',
                background: '#111827',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '8px',
                fontSize: '0.875rem',
                fontWeight: 500,
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={16} />
              Reload Page
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
