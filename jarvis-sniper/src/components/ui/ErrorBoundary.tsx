'use client';

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Optional name for the panel/section (shown in fallback UI) */
  panelName?: string;
  /** Optional custom fallback UI */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary that catches render errors in child components.
 *
 * - Prevents a single broken panel from crashing the entire trading terminal.
 * - Shows a clean fallback UI with retry button.
 * - Logs errors to console with component stack for debugging.
 * - Styled with the existing dark terminal theme.
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary panelName="Token Chart">
 *   <TokenChart />
 * </ErrorBoundary>
 * ```
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const panelName = this.props.panelName || 'Unknown Panel';
    console.error(
      `[ErrorBoundary] ${panelName} crashed:`,
      error,
      '\nComponent stack:',
      errorInfo.componentStack,
    );
  }

  private handleRetry = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children;
    }

    if (this.props.fallback) {
      return this.props.fallback;
    }

    const panelName = this.props.panelName || 'This panel';

    return (
      <div
        className="flex flex-col items-center justify-center gap-3 p-6 rounded-lg h-full min-h-[120px]"
        style={{
          backgroundColor: 'var(--bg-secondary, #111214)',
          border: '1px solid var(--border-primary, rgba(255,255,255,0.08))',
        }}
      >
        <div
          className="text-sm font-medium"
          style={{ color: 'var(--accent-danger, #ef4444)' }}
        >
          Something went wrong
        </div>
        <div
          className="text-xs text-center max-w-[280px]"
          style={{ color: 'var(--text-muted, #64748B)' }}
        >
          {panelName} encountered an error.{' '}
          {this.state.error?.message
            ? `(${this.state.error.message.slice(0, 80)})`
            : ''}
        </div>
        <button
          onClick={this.handleRetry}
          className="px-3 py-1.5 text-xs font-medium rounded-md transition-colors cursor-pointer"
          style={{
            backgroundColor: 'var(--bg-tertiary, #1A1B1E)',
            color: 'var(--text-primary, #F8FAFC)',
            border: '1px solid var(--border-primary, rgba(255,255,255,0.08))',
          }}
        >
          Try Again
        </button>
      </div>
    );
  }
}
