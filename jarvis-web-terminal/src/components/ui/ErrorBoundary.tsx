'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  name?: string; // Component name for error reporting
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      `[ErrorBoundary${this.props.name ? `: ${this.props.name}` : ''}]`,
      error,
      errorInfo
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: undefined });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="card-glass p-4 flex flex-col items-center gap-3 text-center">
          <AlertTriangle className="w-6 h-6 text-accent-error" />
          <div>
            <p className="text-sm font-medium text-text-primary">
              {this.props.name
                ? `${this.props.name} failed to load`
                : 'Something went wrong'}
            </p>
            <p className="text-xs text-text-muted mt-1">
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
          </div>
          <button
            onClick={this.handleRetry}
            className="flex items-center gap-2 px-3 py-1.5 text-xs rounded-lg bg-accent-neon/10 text-accent-neon hover:bg-accent-neon/20 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
