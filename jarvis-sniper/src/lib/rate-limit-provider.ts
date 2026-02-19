export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  retryAfterMs?: number;
}

export interface RateLimitProvider {
  mode: 'memory' | 'redis';
  check(ip: string): Promise<RateLimitResult>;
}

export interface RateLimitProviderOptions {
  keyPrefix: string;
  maxRequests: number;
  windowMs: number;
}

export interface RateLimitProviderDiagnostics {
  mode: 'memory' | 'redis';
  requestedMode: 'memory' | 'redis';
  distributedBacked: boolean;
  configPresent: boolean;
  warning: string | null;
}

let rateLimitProviderWarningEmitted = false;

function isRedisRequested(): boolean {
  const explicit = String(process.env.JARVIS_RATE_LIMIT_PROVIDER || '').trim().toLowerCase();
  if (explicit === 'redis') return true;
  if (explicit === 'memory') return false;
  return String(process.env.REDIS_URL || '').trim().length > 0
    || String(process.env.UPSTASH_REDIS_REST_URL || '').trim().length > 0;
}

function shouldFailClosedForDistributedState(): boolean {
  const explicit = String(process.env.JARVIS_STRICT_DISTRIBUTED_STATE || '').trim().toLowerCase();
  if (explicit === 'true') return true;
  if (explicit === 'false') return false;
  return process.env.NODE_ENV === 'production';
}

function distributedConfigPresent(): boolean {
  return String(process.env.UPSTASH_REDIS_REST_URL || '').trim().length > 0
    && String(process.env.UPSTASH_REDIS_REST_TOKEN || '').trim().length > 0;
}

function createLimiterKey(prefix: string, ip: string): string {
  const safePrefix = String(prefix || 'default').trim() || 'default';
  const safeIp = String(ip || 'unknown').trim() || 'unknown';
  return `jarvis:ratelimit:${safePrefix}:${safeIp}`;
}

function distributedStateWarning(): string {
  return 'Redis mode requested for rate-limit-provider, but UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN are not fully configured.';
}

function emitDistributedWarningOnce(message: string): void {
  if (rateLimitProviderWarningEmitted) return;
  rateLimitProviderWarningEmitted = true;
  console.warn(`[rate-limit-provider] ${message}`);
}

class UpstashRestClient {
  private readonly baseUrl: string;
  private readonly token: string;

  constructor() {
    this.baseUrl = String(process.env.UPSTASH_REDIS_REST_URL || '').trim().replace(/\/+$/, '');
    this.token = String(process.env.UPSTASH_REDIS_REST_TOKEN || '').trim();
  }

  get configured(): boolean {
    return this.baseUrl.length > 0 && this.token.length > 0;
  }

  async exec(command: string[]): Promise<unknown> {
    if (!this.configured) {
      throw new Error('UPSTASH_REDIS_REST_URL/UPSTASH_REDIS_REST_TOKEN must be configured for redis rate limiting');
    }

    const response = await fetch(`${this.baseUrl}/pipeline`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify([command]),
      cache: 'no-store',
    });

    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new Error(`Upstash rate-limit command failed: ${response.status} ${text}`.trim());
    }

    const payload = (await response.json()) as Array<{ error?: string; result?: unknown }>;
    const first = payload?.[0];
    if (!first) {
      throw new Error('Upstash rate-limit response was empty');
    }
    if (first.error) {
      throw new Error(`Upstash rate-limit error: ${first.error}`);
    }
    return first.result ?? null;
  }
}

function resolveModeOrThrow(): 'memory' | 'redis' {
  if (!isRedisRequested()) return 'memory';

  if (!distributedConfigPresent()) {
    const message = distributedStateWarning();
    if (shouldFailClosedForDistributedState()) {
      throw new Error(`[rate-limit-provider] ${message}`);
    }
    emitDistributedWarningOnce(message);
    return 'memory';
  }

  return 'redis';
}

function handleRedisMisconfigurationIfRequested(): void {
  if (!isRedisRequested()) return;
  if (distributedConfigPresent()) return;
  const message = distributedStateWarning();
  if (shouldFailClosedForDistributedState()) {
    throw new Error(`[rate-limit-provider] ${message}`);
  }
  emitDistributedWarningOnce(message);
}

abstract class BaseSlidingWindowLimiter implements RateLimitProvider {
  abstract mode: 'memory' | 'redis';

  protected readonly keyPrefix: string;
  protected readonly maxRequests: number;
  protected readonly windowMs: number;

  protected constructor(options: RateLimitProviderOptions) {
    this.keyPrefix = String(options.keyPrefix || 'default').trim() || 'default';
    this.maxRequests = Math.max(1, Math.floor(options.maxRequests || 1));
    this.windowMs = Math.max(1000, Math.floor(options.windowMs || 60_000));
  }

  protected abstract getTimestamps(key: string): number[];
  protected abstract setTimestamps(key: string, timestamps: number[]): void;
  protected abstract clearTimestamps(key: string): void;

  async check(ip: string): Promise<RateLimitResult> {
    const safeIp = String(ip || 'unknown').trim() || 'unknown';
    const key = `${this.keyPrefix}:${safeIp}`;

    const now = Date.now();
    const windowStart = now - this.windowMs;

    const timestamps = this.getTimestamps(key).filter((t) => t > windowStart);
    if (timestamps.length >= this.maxRequests) {
      const oldestInWindow = timestamps[0];
      const retryAfterMs = oldestInWindow + this.windowMs - now;
      this.setTimestamps(key, timestamps);
      return {
        allowed: false,
        remaining: 0,
        retryAfterMs: Math.max(1, retryAfterMs),
      };
    }

    timestamps.push(now);
    this.setTimestamps(key, timestamps);

    if (timestamps.length === 0) {
      this.clearTimestamps(key);
    }

    return {
      allowed: true,
      remaining: Math.max(0, this.maxRequests - timestamps.length),
    };
  }
}

class InMemoryRateLimitProvider extends BaseSlidingWindowLimiter {
  readonly mode = 'memory' as const;
  private store = new Map<string, number[]>();


  constructor(options: RateLimitProviderOptions) {
    super(options);
  }
  protected getTimestamps(key: string): number[] {
    return this.store.get(key) || [];
  }

  protected setTimestamps(key: string, timestamps: number[]): void {
    this.store.set(key, timestamps);
  }

  protected clearTimestamps(key: string): void {
    this.store.delete(key);
  }
}

class UpstashRateLimitProvider implements RateLimitProvider {
  readonly mode = 'redis' as const;
  private readonly keyPrefix: string;
  private readonly maxRequests: number;
  private readonly windowMs: number;
  private readonly client: UpstashRestClient;

  private static readonly SLIDING_WINDOW_LUA = `
local key = KEYS[1]
local seqKey = KEYS[2]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])

redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local current = redis.call('ZCARD', key)

if current >= limit then
  local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
  local retry = 1
  if oldest[2] ~= nil then
    retry = math.max(1, window - (now - tonumber(oldest[2])))
  end
  redis.call('PEXPIRE', key, window)
  redis.call('PEXPIRE', seqKey, window)
  return {0, 0, retry}
end

local seq = redis.call('INCR', seqKey)
local member = tostring(now) .. '-' .. tostring(seq)
redis.call('ZADD', key, now, member)
redis.call('PEXPIRE', key, window)
redis.call('PEXPIRE', seqKey, window)

local remaining = limit - (current + 1)
if remaining < 0 then remaining = 0 end
return {1, remaining, 0}
`;

  constructor(options: RateLimitProviderOptions) {
    this.keyPrefix = String(options.keyPrefix || 'default').trim() || 'default';
    this.maxRequests = Math.max(1, Math.floor(options.maxRequests || 1));
    this.windowMs = Math.max(1000, Math.floor(options.windowMs || 60_000));
    this.client = new UpstashRestClient();
  }

  async check(ip: string): Promise<RateLimitResult> {
    const now = Date.now();
    const key = createLimiterKey(this.keyPrefix, ip);
    const seqKey = `${key}:seq`;
    const result = await this.client.exec([
      'EVAL',
      UpstashRateLimitProvider.SLIDING_WINDOW_LUA,
      '2',
      key,
      seqKey,
      String(now),
      String(this.windowMs),
      String(this.maxRequests),
    ]);

    const tuple = Array.isArray(result) ? result : [];
    const allowed = Number(tuple[0] ?? 0) === 1;
    const remaining = Math.max(0, Number(tuple[1] ?? 0));
    const retryAfterMs = Math.max(0, Number(tuple[2] ?? 0));

    return allowed
      ? { allowed: true, remaining }
      : { allowed: false, remaining: 0, retryAfterMs: Math.max(1, retryAfterMs) };
  }
}

export function createRateLimitProvider(options: RateLimitProviderOptions): RateLimitProvider {
  const mode = resolveModeOrThrow();
  if (mode === 'redis') {
    return new UpstashRateLimitProvider(options);
  }
  return new InMemoryRateLimitProvider(options);
}

export function getRateLimitProviderMode(): 'memory' | 'redis' {
  return resolveModeOrThrow();
}

export function getRateLimitProviderDiagnostics(): RateLimitProviderDiagnostics {
  handleRedisMisconfigurationIfRequested();
  const redisRequested = isRedisRequested();
  const configPresent = distributedConfigPresent();
  const mode = redisRequested && configPresent ? 'redis' : 'memory';
  const warning = redisRequested && !configPresent
    ? distributedStateWarning()
    : null;

  return {
    mode,
    requestedMode: redisRequested ? 'redis' : 'memory',
    distributedBacked: mode === 'redis',
    configPresent,
    warning,
  };
}

export function __resetRateLimitProviderWarningForTests(): void {
  rateLimitProviderWarningEmitted = false;
}
