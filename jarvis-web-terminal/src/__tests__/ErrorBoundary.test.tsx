import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';

// A component that throws on render
function ThrowOnRender({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error('Test render error');
  }
  return <div>Child rendered successfully</div>;
}

// A component that throws with a custom message
function ThrowCustomError(): React.ReactNode {
  throw new Error('Custom error message');
}

describe('ErrorBoundary', () => {
  // Suppress React error boundary console.error noise in test output
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Hello World</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('renders fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('Test render error')).toBeInTheDocument();
  });

  it('displays component name when provided', () => {
    render(
      <ErrorBoundary name="Price Chart">
        <ThrowOnRender />
      </ErrorBoundary>
    );
    expect(screen.getByText('Price Chart failed to load')).toBeInTheDocument();
  });

  it('renders custom fallback when provided', () => {
    render(
      <ErrorBoundary fallback={<div>Custom fallback content</div>}>
        <ThrowOnRender />
      </ErrorBoundary>
    );
    expect(screen.getByText('Custom fallback content')).toBeInTheDocument();
    // Should NOT show default fallback
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('shows a Retry button that re-mounts children', () => {
    // Use a flag to control whether the component throws
    let shouldThrow = true;

    function ConditionalThrow() {
      if (shouldThrow) throw new Error('Temporary error');
      return <div>Recovered</div>;
    }

    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>
    );

    // Should show error state with Retry button
    expect(screen.getByText('Temporary error')).toBeInTheDocument();
    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    // Now fix the error and click retry
    shouldThrow = false;
    fireEvent.click(retryButton);

    // Should re-render children successfully
    expect(screen.getByText('Recovered')).toBeInTheDocument();
  });

  it('logs errors to console', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ErrorBoundary name="TestComponent">
        <ThrowCustomError />
      </ErrorBoundary>
    );

    // componentDidCatch should have logged the error
    expect(consoleSpy).toHaveBeenCalled();
    const callArgs = consoleSpy.mock.calls.find(
      (args) => typeof args[0] === 'string' && args[0].includes('[ErrorBoundary: TestComponent]')
    );
    expect(callArgs).toBeDefined();
  });

  it('shows the error message from the caught error', () => {
    render(
      <ErrorBoundary>
        <ThrowCustomError />
      </ErrorBoundary>
    );
    expect(screen.getByText('Custom error message')).toBeInTheDocument();
  });

  it('uses card-glass styling on the fallback container', () => {
    render(
      <ErrorBoundary>
        <ThrowOnRender />
      </ErrorBoundary>
    );
    // The fallback container should have card-glass class
    const container = screen.getByText('Something went wrong').closest('div.card-glass');
    expect(container).toBeInTheDocument();
  });
});
