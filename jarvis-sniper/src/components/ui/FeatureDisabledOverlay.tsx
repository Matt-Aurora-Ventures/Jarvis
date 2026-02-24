import React from 'react';

type FeatureDisabledOverlayProps = {
  title?: string;
  reason: string;
};

export function FeatureDisabledOverlay({
  title = 'Panel visible (staged rollout)',
  reason,
}: FeatureDisabledOverlayProps) {
  return (
    <div
      className="absolute inset-0 z-20 flex items-center justify-center rounded-xl border border-accent-warning/30 bg-bg-primary/75 p-4 backdrop-blur-[1px]"
      data-testid="feature-disabled-overlay"
    >
      <div className="max-w-md rounded-lg border border-accent-warning/40 bg-accent-warning/12 p-3 text-center">
        <div className="text-xs font-semibold uppercase tracking-wide text-accent-warning">{title}</div>
        <p className="mt-1 text-xs text-text-secondary">{reason}</p>
      </div>
    </div>
  );
}

export default FeatureDisabledOverlay;

