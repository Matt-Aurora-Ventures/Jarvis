'use client';

import { useEffect, useRef } from 'react';
import { useSniperStore } from '@/stores/useSniperStore';
import {
  cancelSpotProtectionClient,
  reconcileSpotProtectionClient,
} from '@/lib/execution/spot-protection-client';
import { resolveOnChainProtectionConfig } from '@/lib/onchain-protection-config';

const RECONCILE_INTERVAL_MS = 45_000;

interface PositionSnapshot {
  status: string;
  hadProtection: boolean;
  closeReason: string;
}

function hasProtection(pos: {
  protectionStatus?: string;
  tpOrderKey?: string;
  slOrderKey?: string;
  jupTpOrderKey?: string;
  jupSlOrderKey?: string;
}): boolean {
  return Boolean(
    pos.protectionStatus === 'pending'
    || pos.protectionStatus === 'active'
    || pos.tpOrderKey
    || pos.slOrderKey
    || pos.jupTpOrderKey
    || pos.jupSlOrderKey,
  );
}

export function useSpotProtectionLifecycle() {
  const positions = useSniperStore((s) => s.positions);
  const updatePosition = useSniperStore((s) => s.updatePosition);
  const addExecution = useSniperStore((s) => s.addExecution);
  const protectionConfig = resolveOnChainProtectionConfig();
  const prevRef = useRef<Map<string, PositionSnapshot>>(new Map());
  const cancelledRef = useRef<Set<string>>(new Set());
  const reconcileInFlightRef = useRef(false);

  useEffect(() => {
    if (!protectionConfig.enabled) return;
    let cancelled = false;

    const reconcile = async () => {
      if (cancelled || reconcileInFlightRef.current) return;
      const openPositions = useSniperStore
        .getState()
        .positions
        .filter((p) => p.status === 'open' && !p.manualOnly);
      if (openPositions.length === 0) return;

      reconcileInFlightRef.current = true;
      try {
        const ids = openPositions.map((p) => p.id);
        const result = await reconcileSpotProtectionClient(ids);
        if (!result.ok) {
          addExecution({
            id: `spot-protection-reconcile-fail-${Date.now()}`,
            type: 'error',
            symbol: 'SYSTEM',
            mint: '',
            reason: `Protection reconcile failed: ${result.reason || 'unknown error'}`,
            timestamp: Date.now(),
          });
          return;
        }

        const byId = new Map(result.records.map((record) => [record.positionId, record]));
        for (const position of openPositions) {
          const record = byId.get(position.id);
          if (!record) {
            updatePosition(position.id, {
              protectionStatus: 'failed',
              onChainSlTp: false,
              protectionUpdatedAt: Date.now(),
              protectionFailureReason: 'Protection record missing during reconciliation.',
            });
            continue;
          }
          updatePosition(position.id, {
            protectionStatus: record.status,
            tpOrderKey: record.tpOrderKey,
            slOrderKey: record.slOrderKey,
            jupTpOrderKey: record.tpOrderKey,
            jupSlOrderKey: record.slOrderKey,
            onChainSlTp: record.status === 'active',
            protectionUpdatedAt: record.updatedAt || Date.now(),
            protectionFailureReason: record.failureReason,
          });
        }
      } finally {
        reconcileInFlightRef.current = false;
      }
    };

    void reconcile();
    const timer = setInterval(() => { void reconcile(); }, RECONCILE_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [addExecution, protectionConfig.enabled, updatePosition]);

  useEffect(() => {
    const current = new Map<string, PositionSnapshot>();
    for (const pos of positions) {
      current.set(pos.id, {
        status: pos.status,
        hadProtection: hasProtection(pos),
        closeReason: pos.status,
      });
    }

    const toCancel: Array<{ id: string; reason: string }> = [];
    for (const [id, previous] of prevRef.current.entries()) {
      const now = current.get(id);
      if (!now) continue;
      if (previous.status !== 'open' || now.status === 'open') continue;
      if (!previous.hadProtection) continue;
      if (cancelledRef.current.has(id)) continue;
      toCancel.push({ id, reason: `position_${now.closeReason || 'closed'}` });
    }

    prevRef.current = current;
    if (toCancel.length === 0) return;

    for (const item of toCancel) {
      cancelledRef.current.add(item.id);
      void cancelSpotProtectionClient(item.id, item.reason).then((result) => {
        if (!result.ok) {
          addExecution({
            id: `spot-protection-cancel-fail-${Date.now()}-${item.id.slice(-4)}`,
            type: 'error',
            symbol: 'SYSTEM',
            mint: '',
            reason: `Protection cancel failed for ${item.id}: ${result.reason || 'unknown error'}`,
            timestamp: Date.now(),
          });
          return;
        }
        addExecution({
          id: `spot-protection-cancel-ok-${Date.now()}-${item.id.slice(-4)}`,
          type: 'info',
          symbol: 'SYSTEM',
          mint: '',
          reason: `Protection cancelled for position ${item.id}`,
          timestamp: Date.now(),
        });
      });
    }
  }, [addExecution, positions]);
}
