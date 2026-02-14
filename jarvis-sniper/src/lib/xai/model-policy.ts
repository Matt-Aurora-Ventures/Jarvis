import { listModels } from './client';

const FRONTIER_ALLOWLIST = new Set([
  'grok-4-1-fast-reasoning',
  'grok-4-fast-reasoning',
  'grok-4',
]);

export interface FrontierResolution {
  ok: boolean;
  selectedModel: string | null;
  availableModels: string[];
  attemptedOrder: string[];
  diagnostic: string;
}

export function defaultFrontierOrder(): string[] {
  const primary = String(process.env.XAI_FRONTIER_MODEL || 'grok-4-1-fast-reasoning').trim();
  const fallbackRaw = String(
    process.env.XAI_FRONTIER_FALLBACK_MODELS || 'grok-4-fast-reasoning,grok-4',
  );
  const fallback = fallbackRaw
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean);
  const deduped: string[] = [];
  for (const id of [primary, ...fallback]) {
    if (!deduped.includes(id)) deduped.push(id);
  }
  return deduped;
}

export function isFrontierModel(modelId: string): boolean {
  return FRONTIER_ALLOWLIST.has(String(modelId || '').trim());
}

export async function resolveFrontierModel(): Promise<FrontierResolution> {
  const order = defaultFrontierOrder();
  for (const id of order) {
    if (!isFrontierModel(id)) {
      return {
        ok: false,
        selectedModel: null,
        availableModels: [],
        attemptedOrder: order,
        diagnostic: `Non-frontier model in policy order: ${id}`,
      };
    }
  }

  const available = await listModels();
  const availableIds = available.map((m) => m.id);
  const selected = order.find((id) => availableIds.includes(id)) || null;
  if (!selected) {
    return {
      ok: false,
      selectedModel: null,
      availableModels: availableIds,
      attemptedOrder: order,
      diagnostic: 'No configured frontier model is available for this key',
    };
  }
  return {
    ok: true,
    selectedModel: selected,
    availableModels: availableIds,
    attemptedOrder: order,
    diagnostic: `Using ${selected}`,
  };
}

