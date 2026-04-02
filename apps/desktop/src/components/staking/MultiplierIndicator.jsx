/**
 * Multiplier Indicator Component
 *
 * Visual indicator for time-weighted multiplier:
 * - Current multiplier value
 * - Progress to next tier
 * - Time until next milestone
 */

import React, { useState, useEffect } from 'react';

// Multiplier tiers with requirements
const MULTIPLIER_TIERS = [
  { multiplier: 1.0, days: 0, label: 'Start' },
  { multiplier: 1.5, days: 7, label: '7 days' },
  { multiplier: 2.0, days: 30, label: '30 days' },
  { multiplier: 2.5, days: 90, label: '90 days' },
];

export default function MultiplierIndicator({ multiplier, stakeStartTime }) {
  const [timeInfo, setTimeInfo] = useState({
    daysStaked: 0,
    nextTier: null,
    daysToNext: 0,
    progress: 0,
  });

  useEffect(() => {
    if (!stakeStartTime) {
      setTimeInfo({ daysStaked: 0, nextTier: null, daysToNext: 0, progress: 0 });
      return;
    }

    const calculateTimeInfo = () => {
      const start = new Date(stakeStartTime);
      const now = new Date();
      const daysStaked = Math.floor((now - start) / (1000 * 60 * 60 * 24));

      // Find current and next tier
      let currentTierIndex = 0;
      for (let i = MULTIPLIER_TIERS.length - 1; i >= 0; i--) {
        if (daysStaked >= MULTIPLIER_TIERS[i].days) {
          currentTierIndex = i;
          break;
        }
      }

      const currentTier = MULTIPLIER_TIERS[currentTierIndex];
      const nextTier = MULTIPLIER_TIERS[currentTierIndex + 1] || null;

      let progress = 100;
      let daysToNext = 0;

      if (nextTier) {
        const daysInCurrentTier = daysStaked - currentTier.days;
        const daysForNextTier = nextTier.days - currentTier.days;
        progress = Math.min(100, (daysInCurrentTier / daysForNextTier) * 100);
        daysToNext = nextTier.days - daysStaked;
      }

      setTimeInfo({
        daysStaked,
        nextTier,
        daysToNext,
        progress,
      });
    };

    calculateTimeInfo();
    const interval = setInterval(calculateTimeInfo, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [stakeStartTime]);

  // Get color based on multiplier
  const getMultiplierColor = (mult) => {
    if (mult >= 2.5) return 'text-yellow-400';
    if (mult >= 2.0) return 'text-green-400';
    if (mult >= 1.5) return 'text-blue-400';
    return 'text-gray-400';
  };

  const getBgColor = (mult) => {
    if (mult >= 2.5) return 'bg-yellow-900/30 border-yellow-700';
    if (mult >= 2.0) return 'bg-green-900/30 border-green-700';
    if (mult >= 1.5) return 'bg-blue-900/30 border-blue-700';
    return 'bg-gray-700/50 border-gray-600';
  };

  const getProgressColor = (mult) => {
    if (mult >= 2.5) return 'bg-yellow-500';
    if (mult >= 2.0) return 'bg-green-500';
    if (mult >= 1.5) return 'bg-blue-500';
    return 'bg-gray-500';
  };

  if (!stakeStartTime) {
    return (
      <div className="mt-2 text-sm text-gray-500">
        No active stake
      </div>
    );
  }

  return (
    <div className={`mt-3 rounded-lg border p-3 ${getBgColor(multiplier)}`}>
      {/* Current Multiplier */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <svg className={`w-4 h-4 ${getMultiplierColor(multiplier)}`} fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M12.395 2.553a1 1 0 00-1.45-.385c-.345.23-.614.558-.822.88-.214.33-.403.713-.57 1.116-.334.804-.614 1.768-.84 2.734a31.365 31.365 0 00-.613 3.58 2.64 2.64 0 01-.945-1.067c-.328-.68-.398-1.534-.398-2.654A1 1 0 005.05 6.05 6.981 6.981 0 003 11a7 7 0 1011.95-4.95c-.592-.591-.98-.985-1.348-1.467-.363-.476-.724-1.063-1.207-2.03zM12.12 15.12A3 3 0 017 13s.879.5 2.5.5c0-1 .5-4 1.25-4.5.5 1 .786 1.293 1.371 1.879A2.99 2.99 0 0113 13a2.99 2.99 0 01-.879 2.121z" clipRule="evenodd" />
          </svg>
          <span className={`font-bold ${getMultiplierColor(multiplier)}`}>
            {multiplier.toFixed(1)}x
          </span>
        </div>
        <span className="text-xs text-gray-400">
          {timeInfo.daysStaked} day{timeInfo.daysStaked !== 1 ? 's' : ''} staked
        </span>
      </div>

      {/* Progress to next tier */}
      {timeInfo.nextTier && (
        <>
          <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden mb-2">
            <div
              className={`h-full ${getProgressColor(multiplier)} transition-all duration-500`}
              style={{ width: `${timeInfo.progress}%` }}
            />
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-400">
              Next: {timeInfo.nextTier.multiplier}x
            </span>
            <span className="text-gray-400">
              {timeInfo.daysToNext} day{timeInfo.daysToNext !== 1 ? 's' : ''} remaining
            </span>
          </div>
        </>
      )}

      {/* Max tier reached */}
      {!timeInfo.nextTier && (
        <div className="flex items-center gap-1 text-xs text-yellow-400">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
          Maximum multiplier achieved!
        </div>
      )}
    </div>
  );
}

// Compact version for display in cards
export function MultiplierBadge({ multiplier }) {
  const getBadgeColor = (mult) => {
    if (mult >= 2.5) return 'bg-yellow-600 text-yellow-100';
    if (mult >= 2.0) return 'bg-green-600 text-green-100';
    if (mult >= 1.5) return 'bg-blue-600 text-blue-100';
    return 'bg-gray-600 text-gray-200';
  };

  return (
    <span className={`px-2 py-0.5 rounded text-xs font-bold ${getBadgeColor(multiplier)}`}>
      {multiplier.toFixed(1)}x
    </span>
  );
}
