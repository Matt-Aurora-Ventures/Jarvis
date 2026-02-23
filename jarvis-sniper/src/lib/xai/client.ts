import { randomUUID } from 'crypto';

export interface XaiModelRecord {
  id: string;
}

export interface XaiBatchState {
  num_requests?: number;
  num_pending?: number;
  num_success?: number;
  num_error?: number;
  num_cancelled?: number;
}

export interface XaiBatchInfo {
  batch_id: string;
  name?: string;
  create_time?: string;
  expire_time?: string;
  cancel_time?: string;
  cancel_by_xai_message?: string;
  state?: XaiBatchState;
  cost_breakdown?: unknown;
}

export interface XaiBatchRequest {
  batch_request_id: string;
  completion_request: Record<string, unknown>;
}

export interface XaiBatchResult {
  batch_request_id: string;
  response?: unknown;
  error?: unknown;
}

export interface XaiBatchResultsPage {
  results: XaiBatchResult[];
  pagination_token?: string;
}

export interface XaiApiErrorShape {
  message: string;
  type?: string;
  code?: string;
}

export class XaiApiError extends Error {
  status: number;
  correlationId: string;
  code?: string;
  details?: unknown;

  constructor(args: {
    message: string;
    status: number;
    correlationId: string;
    code?: string;
    details?: unknown;
  }) {
    super(args.message);
    this.name = 'XaiApiError';
    this.status = args.status;
    this.correlationId = args.correlationId;
    this.code = args.code;
    this.details = args.details;
  }
}

const DEFAULT_BASE_URL = 'https://api.x.ai/v1';

function baseUrl(): string {
  return String(process.env.XAI_BASE_URL || DEFAULT_BASE_URL).trim().replace(/\/+$/, '');
}

function apiKey(): string {
  // Secrets injected via Secret Manager can sometimes include embedded newlines.
  // xAI keys never contain whitespace, so stripping is safe and prevents subtle auth failures.
  return String(process.env.XAI_API_KEY || '')
    .trim()
    .replace(/\s+/g, '');
}

function mustApiKey(): string {
  const key = apiKey();
  if (!key) {
    throw new XaiApiError({
      message: 'XAI_API_KEY is not configured',
      status: 503,
      correlationId: randomUUID(),
      code: 'XAI_KEY_MISSING',
    });
  }
  return key;
}

function makeCorrelationId(): string {
  return `xai-${Date.now()}-${randomUUID().slice(0, 8)}`;
}

async function parseJsonSafe(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text.slice(0, 4000) };
  }
}

async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const correlationId = makeCorrelationId();
  const key = mustApiKey();
  const url = `${baseUrl()}${path}`;
  const headers = new Headers(init.headers || {});
  headers.set('Authorization', `Bearer ${key}`);
  headers.set('X-Correlation-Id', correlationId);
  if (!headers.has('Content-Type') && init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  const response = await fetch(url, { ...init, headers });
  const payload = await parseJsonSafe(response);
  if (!response.ok) {
    const apiError = (payload as { error?: XaiApiErrorShape } | null)?.error;
    const rawText = (payload as { raw?: string } | null)?.raw;
    throw new XaiApiError({
      message: apiError?.message || rawText || `xAI API request failed (${response.status})`,
      status: response.status,
      correlationId,
      code: apiError?.code,
      details: payload,
    });
  }
  return payload as T;
}

export async function listModels(): Promise<XaiModelRecord[]> {
  const payload = await requestJson<{ data?: Array<{ id?: string }> }>('/models', { method: 'GET' });
  return (payload.data || [])
    .map((row) => String(row?.id || '').trim())
    .filter(Boolean)
    .map((id) => ({ id }));
}

export async function createBatch(name: string): Promise<string> {
  const payload = await requestJson<Record<string, unknown>>('/batches', {
    method: 'POST',
    body: JSON.stringify({
      name,
    }),
  });
  const id = String(payload?.batch_id || payload?.id || '').trim();
  if (!id) {
    throw new XaiApiError({
      message: 'xAI batch create returned empty batch id',
      status: 502,
      correlationId: makeCorrelationId(),
      code: 'XAI_BATCH_ID_MISSING',
      details: payload,
    });
  }
  return id;
}

export async function getBatch(batchId: string): Promise<XaiBatchInfo> {
  const payload = await requestJson<Record<string, unknown>>(
    `/batches/${encodeURIComponent(batchId)}`,
    { method: 'GET' },
  );
  const state = (payload.state && typeof payload.state === 'object') ? (payload.state as XaiBatchState) : undefined;
  return {
    batch_id: String(payload.batch_id || payload.id || ''),
    name: typeof payload.name === 'string' ? payload.name : undefined,
    create_time: typeof payload.create_time === 'string' ? payload.create_time : undefined,
    expire_time: typeof payload.expire_time === 'string' ? payload.expire_time : undefined,
    cancel_time: typeof payload.cancel_time === 'string' ? payload.cancel_time : undefined,
    cancel_by_xai_message: typeof payload.cancel_by_xai_message === 'string' ? payload.cancel_by_xai_message : undefined,
    state,
    cost_breakdown: payload.cost_breakdown,
  };
}

export async function addBatchRequests(batchId: string, batchRequests: XaiBatchRequest[]): Promise<void> {
  await requestJson<Record<string, unknown>>(`/batches/${encodeURIComponent(batchId)}/requests`, {
    method: 'POST',
    body: JSON.stringify({
      // REST Batch API uses a tagged union wrapper to support multiple endpoint types.
      // For chat completions, the expected variant is `chat_get_completion`.
      batch_requests: batchRequests.map((req) => ({
        batch_request: {
          chat_get_completion: req,
        },
      })),
    }),
  });
}

export async function getBatchResults(args: {
  batchId: string;
  limit?: number;
  paginationToken?: string;
}): Promise<XaiBatchResultsPage> {
  const query: string[] = [];
  if (typeof args.limit === 'number' && Number.isFinite(args.limit) && args.limit > 0) {
    query.push(`limit=${encodeURIComponent(String(Math.floor(args.limit)))}`);
  }
  if (args.paginationToken) {
    query.push(`pagination_token=${encodeURIComponent(String(args.paginationToken))}`);
  }
  const suffix = query.length ? `?${query.join('&')}` : '';
  const payload = await requestJson<Record<string, unknown>>(
    `/batches/${encodeURIComponent(args.batchId)}/results${suffix}`,
    { method: 'GET' },
  );
  const resultsRaw = Array.isArray(payload.results) ? payload.results : [];
  const results: XaiBatchResult[] = resultsRaw
    .map((row) => {
      if (!row || typeof row !== 'object') return null;
      const rec = row as Record<string, unknown>;
      let batch_request_id = String(rec.batch_request_id || '').trim();
      let response = rec.response;
      let error = rec.error;

      // Some API shapes wrap results similarly to requests:
      // { batch_result: { chat_get_completion: { batch_request_id, response, error } } }
      if (!batch_request_id) {
        const batchResult = rec.batch_result;
        if (batchResult && typeof batchResult === 'object') {
          const variant = (batchResult as any).chat_get_completion;
          if (variant && typeof variant === 'object') {
            batch_request_id = String(variant.batch_request_id || '').trim();
            response = variant.response ?? variant.completion_response ?? response;
            error = variant.error ?? error;
          }
        }
      }

      if (!batch_request_id) return null;
      return {
        batch_request_id,
        response,
        error,
      } as XaiBatchResult;
    })
    .filter((v): v is XaiBatchResult => Boolean(v));

  return {
    results,
    pagination_token: typeof payload.pagination_token === 'string' ? payload.pagination_token : undefined,
  };
}
