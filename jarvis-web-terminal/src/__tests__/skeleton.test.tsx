import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  Skeleton,
  SkeletonChart,
  SkeletonTable,
  SkeletonCard,
  SkeletonText,
} from '@/components/ui/Skeleton';

// ---------------------------------------------------------------------------
// Skeleton (base primitive)
// ---------------------------------------------------------------------------

describe('Skeleton', () => {
  it('renders a div with the skeleton shimmer class', () => {
    const { container } = render(<Skeleton />);
    const el = container.firstChild as HTMLElement;
    expect(el).toBeTruthy();
    expect(el.tagName).toBe('DIV');
    expect(el.className).toContain('skeleton');
  });

  it('applies a custom className alongside the base class', () => {
    const { container } = render(<Skeleton className="h-8 w-full" />);
    const el = container.firstChild as HTMLElement;
    expect(el.className).toContain('skeleton');
    expect(el.className).toContain('h-8');
    expect(el.className).toContain('w-full');
  });
});

// ---------------------------------------------------------------------------
// SkeletonChart
// ---------------------------------------------------------------------------

describe('SkeletonChart', () => {
  it('renders a chart-like skeleton structure', () => {
    const { container } = render(<SkeletonChart />);
    // Should have a container element
    expect(container.firstChild).toBeTruthy();
    // Should have multiple skeleton elements simulating chart bars or lines
    const skeletonElements = container.querySelectorAll('.skeleton');
    expect(skeletonElements.length).toBeGreaterThanOrEqual(3);
  });

  it('has a minimum height that mimics a chart area', () => {
    const { container } = render(<SkeletonChart />);
    const wrapper = container.firstChild as HTMLElement;
    // The wrapper should have a height class or style suggesting chart dimensions
    expect(wrapper.className).toMatch(/min-h|h-\[/);
  });
});

// ---------------------------------------------------------------------------
// SkeletonTable
// ---------------------------------------------------------------------------

describe('SkeletonTable', () => {
  it('renders a default number of rows when no prop is given', () => {
    const { container } = render(<SkeletonTable />);
    // Default should produce at least 3 rows
    const rows = container.querySelectorAll('[data-testid="skeleton-row"]');
    expect(rows.length).toBe(3);
  });

  it('renders the specified number of rows', () => {
    const { container } = render(<SkeletonTable rows={5} />);
    const rows = container.querySelectorAll('[data-testid="skeleton-row"]');
    expect(rows.length).toBe(5);
  });

  it('renders 8 rows when requested', () => {
    const { container } = render(<SkeletonTable rows={8} />);
    const rows = container.querySelectorAll('[data-testid="skeleton-row"]');
    expect(rows.length).toBe(8);
  });

  it('each row contains skeleton elements', () => {
    const { container } = render(<SkeletonTable rows={2} />);
    const rows = container.querySelectorAll('[data-testid="skeleton-row"]');
    rows.forEach((row) => {
      const inner = row.querySelectorAll('.skeleton');
      expect(inner.length).toBeGreaterThanOrEqual(1);
    });
  });
});

// ---------------------------------------------------------------------------
// SkeletonCard
// ---------------------------------------------------------------------------

describe('SkeletonCard', () => {
  it('renders a card-shaped skeleton', () => {
    const { container } = render(<SkeletonCard />);
    expect(container.firstChild).toBeTruthy();
    const skeletons = container.querySelectorAll('.skeleton');
    // A card should have at least a title bar and a content area
    expect(skeletons.length).toBeGreaterThanOrEqual(2);
  });

  it('has rounded corners matching card-glass style', () => {
    const { container } = render(<SkeletonCard />);
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain('rounded');
  });
});

// ---------------------------------------------------------------------------
// SkeletonText
// ---------------------------------------------------------------------------

describe('SkeletonText', () => {
  it('renders a default number of text lines', () => {
    const { container } = render(<SkeletonText />);
    const lines = container.querySelectorAll('.skeleton');
    // Default should be 3 lines
    expect(lines.length).toBe(3);
  });

  it('renders the specified number of lines', () => {
    const { container } = render(<SkeletonText lines={5} />);
    const lines = container.querySelectorAll('.skeleton');
    expect(lines.length).toBe(5);
  });

  it('last line is shorter to mimic natural text', () => {
    const { container } = render(<SkeletonText lines={3} />);
    const lines = container.querySelectorAll('.skeleton');
    const lastLine = lines[lines.length - 1] as HTMLElement;
    // The last line should have a width class like w-2/3 or w-3/4
    expect(lastLine.className).toMatch(/w-[23]\/[34]/);
  });
});
