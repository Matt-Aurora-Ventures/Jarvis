import { describe, expect, it } from 'vitest';
import { buildDatasetManifestV2 } from '@/lib/data-plane/manifest-v2';

describe('dataset manifest v2', () => {
  it('is deterministic for identical payloads', () => {
    const records = [
      { mint: 'mint-a', source: 'dexscreener', provenance: { source: 'dexscreener' } },
      { mint: 'mint-b', source: 'geckoterminal', provenance: { source: 'geckoterminal' } },
    ];
    const args = {
      family: 'graduations',
      surface: 'main' as const,
      timeRange: { from: '2026-02-18T00:00:00.000Z', to: '2026-02-19T00:00:00.000Z' },
      records,
    };

    const one = buildDatasetManifestV2(args);
    const two = buildDatasetManifestV2(args);

    expect(one.sha256).toBe(two.sha256);
    expect(one.datasetId).toBe(two.datasetId);
    expect(one.recordCount).toBe(2);
    expect(one.sourceMix.dexscreener).toBe(1);
    expect(one.sourceMix.geckoterminal).toBe(1);
  });
});
