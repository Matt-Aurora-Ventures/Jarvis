import { randomUUID } from 'crypto';

export interface XaiModelRecord {
  id: string;
}

export interface XaiBatchInfo {
  id: string;
  status: string;
  input_file_id?: string;
  output_file_id?: string;
  error_file_id?: string;
  endpoint?: string;
  completion_window?: string;
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
  // Secret Manager values can include stray whitespace/newlines; sanitize to avoid invalid header chars.
  return String(process.env.XAI_API_KEY || '')
    .replace(/[\x00-\x20\x7f]/g, '')
    .trim();
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
    throw new XaiApiError({
      message: apiError?.message || `xAI API request failed (${response.status})`,
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

export async function uploadBatchInputFile(jsonl: string): Promise<string> {
  const correlationId = makeCorrelationId();
  const key = mustApiKey();
  const url = `${baseUrl()}/files`;
  const form = new FormData();
  form.append('purpose', 'batch');
  form.append(
    'file',
    new Blob([jsonl], { type: 'application/x-ndjson' }),
    `xai-batch-${Date.now()}.jsonl`,
  );

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${key}`,
      'X-Correlation-Id': correlationId,
    },
    body: form,
  });
  const payload = await parseJsonSafe(response);
  if (!response.ok) {
    const apiError = (payload as { error?: XaiApiErrorShape } | null)?.error;
    throw new XaiApiError({
      message: apiError?.message || `xAI file upload failed (${response.status})`,
      status: response.status,
      correlationId,
      code: apiError?.code,
      details: payload,
    });
  }
  const id = String((payload as { id?: string } | null)?.id || '').trim();
  if (!id) {
    throw new XaiApiError({
      message: 'xAI file upload returned empty file id',
      status: 502,
      correlationId,
      code: 'XAI_FILE_ID_MISSING',
      details: payload,
    });
  }
  return id;
}

export async function createBatch(
  inputFileId: string,
  endpoint = '/v1/chat/completions',
  completionWindow = '24h',
): Promise<string> {
  const payload = await requestJson<{ id?: string }>('/batches', {
    method: 'POST',
    body: JSON.stringify({
      input_file_id: inputFileId,
      endpoint,
      completion_window: completionWindow,
    }),
  });
  const id = String(payload?.id || '').trim();
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
  const payload = await requestJson<Record<string, unknown>>(`/batches/${encodeURIComponent(batchId)}`, {
    method: 'GET',
  });
  return {
    id: String(payload.id || ''),
    status: String(payload.status || 'unknown'),
    input_file_id: typeof payload.input_file_id === 'string' ? payload.input_file_id : undefined,
    output_file_id: typeof payload.output_file_id === 'string' ? payload.output_file_id : undefined,
    error_file_id: typeof payload.error_file_id === 'string' ? payload.error_file_id : undefined,
    endpoint: typeof payload.endpoint === 'string' ? payload.endpoint : undefined,
    completion_window: typeof payload.completion_window === 'string' ? payload.completion_window : undefined,
  };
}

export async function getFileContent(fileId: string): Promise<string> {
  const correlationId = makeCorrelationId();
  const key = mustApiKey();
  const url = `${baseUrl()}/files/${encodeURIComponent(fileId)}/content`;
  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${key}`,
      'X-Correlation-Id': correlationId,
    },
  });
  const text = await response.text();
  if (!response.ok) {
    let details: unknown = text;
    try {
      details = JSON.parse(text);
    } catch {
      // keep text fallback
    }
    throw new XaiApiError({
      message: `xAI file content fetch failed (${response.status})`,
      status: response.status,
      correlationId,
      code: 'XAI_FILE_CONTENT_FAILED',
      details,
    });
  }
  return text;
}

