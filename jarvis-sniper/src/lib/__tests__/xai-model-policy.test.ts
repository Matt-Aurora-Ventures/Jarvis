import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockListModels = vi.fn();

vi.mock('@/lib/xai/client', () => ({
  listModels: mockListModels,
}));

describe('xai frontier model policy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.XAI_FRONTIER_MODEL = 'grok-4-1-fast-reasoning';
    process.env.XAI_FRONTIER_FALLBACK_MODELS = 'grok-4-fast-reasoning,grok-4';
  });

  it('selects frontier fast primary model when available', async () => {
    mockListModels.mockResolvedValue([
      { id: 'grok-4-1-fast-reasoning' },
      { id: 'grok-4' },
    ]);
    const mod = await import('@/lib/xai/model-policy');
    const result = await mod.resolveFrontierModel();
    expect(result.ok).toBe(true);
    expect(result.selectedModel).toBe('grok-4-1-fast-reasoning');
  });

  it('fails closed when configured policy includes non-frontier model', async () => {
    process.env.XAI_FRONTIER_MODEL = 'grok-3-mini';
    mockListModels.mockResolvedValue([{ id: 'grok-3-mini' }]);
    const mod = await import('@/lib/xai/model-policy');
    const result = await mod.resolveFrontierModel();
    expect(result.ok).toBe(false);
    expect(result.selectedModel).toBeNull();
    expect(result.diagnostic).toContain('Non-frontier model');
  });

  it('fails closed when no frontier model is available for key', async () => {
    mockListModels.mockResolvedValue([{ id: 'grok-3-mini' }]);
    const mod = await import('@/lib/xai/model-policy');
    const result = await mod.resolveFrontierModel();
    expect(result.ok).toBe(false);
    expect(result.selectedModel).toBeNull();
  });
});

