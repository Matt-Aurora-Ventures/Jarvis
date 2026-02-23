/**
 * Skeleton -- Reusable loading skeleton primitives
 *
 * Uses the `.skeleton` CSS class from globals.css which provides
 * a shimmer gradient animation on bg-tertiary backgrounds.
 *
 * Components:
 *  - Skeleton       Base block (div with shimmer)
 *  - SkeletonChart  Mimics a price chart area with bars
 *  - SkeletonTable  Mimics a data table with N rows
 *  - SkeletonCard   Mimics a stat/strategy card
 *  - SkeletonText   Mimics a text block with N lines
 */

// ---------------------------------------------------------------------------
// Base Skeleton
// ---------------------------------------------------------------------------

export function Skeleton({ className }: { className?: string }) {
  return <div className={`skeleton rounded ${className ?? ''}`} />;
}

// ---------------------------------------------------------------------------
// SkeletonChart -- Mimics a candlestick chart area
// ---------------------------------------------------------------------------

export function SkeletonChart() {
  return (
    <div className="min-h-[300px] flex flex-col gap-3 p-4">
      {/* Header area: symbol + price */}
      <div className="flex items-center gap-3">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-4 w-12" />
      </div>
      {/* Chart body: simulated bars at various heights */}
      <div className="flex-1 flex items-end gap-1 pt-4">
        {[40, 55, 35, 65, 50, 70, 45, 60, 75, 55, 48, 62, 58, 42, 68].map(
          (h, i) => (
            <Skeleton
              key={i}
              className="flex-1 rounded-t"
              // Use inline style for dynamic heights since Tailwind can't do arbitrary array values
            />
          ),
        )}
      </div>
      {/* X-axis labels */}
      <div className="flex justify-between">
        <Skeleton className="h-3 w-10" />
        <Skeleton className="h-3 w-10" />
        <Skeleton className="h-3 w-10" />
        <Skeleton className="h-3 w-10" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SkeletonTable -- Mimics a tabular list with N rows
// ---------------------------------------------------------------------------

export function SkeletonTable({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          data-testid="skeleton-row"
          className="flex items-center gap-3 px-3 py-2 rounded-lg bg-bg-tertiary/20"
        >
          {/* Rank / Icon placeholder */}
          <Skeleton className="h-6 w-6 rounded-md shrink-0" />
          {/* Name / Symbol */}
          <Skeleton className="h-4 flex-1" />
          {/* Price */}
          <Skeleton className="h-4 w-16 shrink-0" />
          {/* Change */}
          <Skeleton className="h-4 w-12 shrink-0" />
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// SkeletonCard -- Mimics a strategy or stat card
// ---------------------------------------------------------------------------

export function SkeletonCard() {
  return (
    <div className="rounded-lg border border-border-primary/30 bg-bg-secondary/30 p-3 space-y-3">
      {/* Title bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Skeleton className="h-2 w-2 rounded-full" />
          <Skeleton className="h-4 w-28" />
        </div>
        <Skeleton className="h-3 w-3 rounded" />
      </div>
      {/* Win rate bar */}
      <div className="space-y-1">
        <div className="flex justify-between">
          <Skeleton className="h-3 w-14" />
          <Skeleton className="h-3 w-8" />
        </div>
        <Skeleton className="h-1.5 w-full rounded-full" />
      </div>
      {/* Signal badge */}
      <Skeleton className="h-8 w-full rounded-md" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// SkeletonText -- Mimics a paragraph of text with N lines
// ---------------------------------------------------------------------------

export function SkeletonText({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={`h-3 ${i === lines - 1 ? 'w-2/3' : 'w-full'}`}
        />
      ))}
    </div>
  );
}
