import React from 'react';

type FeatureDisabledOverlayProps = {
  title?: string;
  reason?: string;
  testId?: string;
};

export function FeatureDisabledOverlay({
  title = 'Feature Temporarily Disabled',
  reason,
  testId,
}: FeatureDisabledOverlayProps) {
  return (
    <div
      data-testid={testId}
      className="pointer-events-auto absolute inset-0 z-20 flex items-center justify-center rounded-xl border border-accent-warning/30 bg-bg-primary/80 p-4 backdrop-blur-[2px]"
    >
      <div className="max-w-md rounded-lg border border-accent-warning/35 bg-accent-warning/10 p-3 text-center">
        <div className="text-xs font-semibold uppercase tracking-wide text-accent-warning">{title}</div>
        <p className="mt-2 text-xs text-text-secondary">
          {reason || 'Actions are paused while this surface is in a staged rollout.'}
        </p>
      </div>
    </div>
  );
}

export default FeatureDisabledOverlay;
