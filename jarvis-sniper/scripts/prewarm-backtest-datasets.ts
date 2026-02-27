import {
  buildPrewarmBody,
  isPrewarmTerminalState,
  resolvePrewarmBaseUrl,
  type PrewarmBodyOptions,
  type PrewarmDataScale,
  type PrewarmFamily,
} from '@/lib/backtest-prewarm';
import { computeCoverageHealth, resolveCoverageThreshold } from '@/lib/backtest-coverage-policy';
import { mkdirSync, writeFileSync } from 'fs';
import { join } from 'path';

type PollStatus = {
  runId?: string;
  state?: string;
  progress?: number;
  currentActivity?: string;
  datasetsAttempted?: number;
  datasetsSucceeded?: number;
  error?: string | null;
};

const DEFAULT_CANONICAL = 'https://jarvislife.cloud';
const DEFAULT_FAMILIES: PrewarmFamily[] = [
  'memecoin',
  'bags',
  'bluechip',
  'xstock',
  'prestock',
  'index',
];

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseBoolean(raw: string | undefined, fallback: boolean): boolean {
  if (raw == null || raw.trim() === '') return fallback;
  const normalized = raw.trim().toLowerCase();
  return normalized === '1' || normalized === 'true' || normalized === 'yes' || normalized === 'on';
}

function parsePositiveInt(raw: string | undefined): number | undefined {
  if (raw == null || raw.trim() === '') return undefined;
  const n = Number.parseInt(raw.trim(), 10);
  if (!Number.isFinite(n) || n <= 0) return undefined;
  return n;
}

function parseDataScale(raw: string | undefined): PrewarmDataScale {
  return raw?.trim().toLowerCase() === 'thorough' ? 'thorough' : 'fast';
}

function parseMode(raw: string | undefined): NonNullable<PrewarmBodyOptions['mode']> {
  const value = raw?.trim().toLowerCase();
  if (value === 'full' || value === 'grid') return value;
  return 'quick';
}

function parseSourcePolicy(raw: string | undefined): NonNullable<PrewarmBodyOptions['sourcePolicy']> {
  return raw?.trim().toLowerCase() === 'gecko_only' ? 'gecko_only' : 'allow_birdeye_fallback';
}

function defaultMaxTokensForFamily(
  family: PrewarmFamily,
  dataScale: PrewarmDataScale,
): number {
  if (dataScale === 'fast') {
    if (family === 'bluechip') return 5;
    if (family === 'xstock' || family === 'prestock' || family === 'index' || family === 'xstock_index') return 5;
    return 10;
  }
  if (family === 'xstock' || family === 'prestock' || family === 'index' || family === 'xstock_index') return 50;
  return 200;
}

function buildPrewarmOptionsFromEnv(): PrewarmBodyOptions {
  const options: PrewarmBodyOptions = {
    mode: parseMode(process.env.PREWARM_MODE),
    dataScale: parseDataScale(process.env.PREWARM_DATA_SCALE),
    sourcePolicy: parseSourcePolicy(process.env.PREWARM_SOURCE_POLICY),
    includeEvidence: parseBoolean(process.env.PREWARM_INCLUDE_EVIDENCE, false),
    includeReport: parseBoolean(process.env.PREWARM_INCLUDE_REPORT, false),
    strictNoSynthetic: parseBoolean(process.env.PREWARM_STRICT_NO_SYNTHETIC, true),
  };

  const maxTokens = parsePositiveInt(process.env.PREWARM_MAX_TOKENS);
  const lookbackHours = parsePositiveInt(process.env.PREWARM_LOOKBACK_HOURS);
  if (maxTokens) options.maxTokens = Math.min(500, maxTokens);
  if (lookbackHours) options.lookbackHours = Math.min(4320, lookbackHours);

  return options;
}

function parseFamilies(raw: string | undefined): PrewarmFamily[] {
  const values = String(raw || '')
    .split(',')
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);

  if (values.length === 0) return DEFAULT_FAMILIES;
  return values.filter((v): v is PrewarmFamily =>
    ['memecoin', 'bags', 'bluechip', 'xstock', 'prestock', 'index', 'xstock_index'].includes(v),
  );
}

async function postPrewarmRun(
  startUrl: string,
  canonicalOrigin: string,
  family: PrewarmFamily,
  options: PrewarmBodyOptions,
): Promise<string> {
  const runId = `prewarm-${family}-${Date.now()}`;
  const body = buildPrewarmBody(family, runId, options);
  let res: Response;
  try {
    res = await fetch(`${startUrl}/api/backtest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Origin: canonicalOrigin,
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(Number(process.env.PREWARM_START_TIMEOUT_MS || 70_000)),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[prewarm:${family}] start request did not return cleanly (${message}); continuing with runId=${runId}`);
    return runId;
  }

  if (!res.ok) {
    const contentType = String(res.headers.get('content-type') || '').toLowerCase();
    const text = await res.text();
    const htmlLike =
      contentType.includes('text/html') ||
      /^<!doctype html/i.test(text) ||
      /^<html/i.test(text);
    if (htmlLike && res.status >= 500) {
      // Known hosting edge timeout path; run often still exists in monitor registry.
      console.warn(`[prewarm:${family}] start returned HTTP ${res.status}; continuing with monitor runId=${runId}`);
      return runId;
    }
    throw new Error(`[prewarm:${family}] failed to start: HTTP ${res.status} ${text.slice(0, 220)}`);
  }

  const json = (await res.json()) as { runId?: string };
  return String(json?.runId || runId);
}

async function pollRun(baseUrl: string, family: PrewarmFamily, runId: string): Promise<PollStatus> {
  const timeoutMs = Number(process.env.PREWARM_TIMEOUT_MS || 25 * 60 * 1000);
  const pollMs = Number(process.env.PREWARM_POLL_MS || 10_000);
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const res = await fetch(`${baseUrl}/api/backtest/runs/${encodeURIComponent(runId)}`, {
      cache: 'no-store',
    });
    const text = await res.text();
    if (!res.ok) {
      console.warn(`[prewarm:${family}] monitor HTTP ${res.status}: ${text.slice(0, 180)}`);
      await sleep(pollMs);
      continue;
    }
    let status: PollStatus = {};
    try {
      status = JSON.parse(text) as PollStatus;
    } catch {
      console.warn(`[prewarm:${family}] monitor parse failed`);
      await sleep(pollMs);
      continue;
    }

    const state = String(status.state || '').toLowerCase();
    if (isPrewarmTerminalState(state)) {
      return status;
    }

    console.log(
      `[prewarm:${family}] state=${state || 'running'} progress=${status.progress ?? 0} activity=${status.currentActivity || ''}`,
    );
    await sleep(pollMs);
  }

  return { runId, state: 'timeout', error: 'Prewarm polling timed out' };
}

async function main(): Promise<void> {
  const canonical = String(process.env.PREWARM_CANONICAL_ORIGIN || DEFAULT_CANONICAL)
    .trim()
    .replace(/\/+$/, '');
  const families = parseFamilies(process.env.PREWARM_FAMILIES);
  const options = buildPrewarmOptionsFromEnv();
  const dataScale = options.dataScale === 'thorough' ? 'thorough' : 'fast';
  const envMinHitRate = (() => {
    const raw = process.env.PREWARM_MIN_HIT_RATE;
    if (raw == null || raw.trim() === '') return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) return null;
    return Math.max(0, Math.min(1, n));
  })();
  if (families.length === 0) {
    throw new Error('No valid prewarm families configured.');
  }

  const healthRes = await fetch(`${canonical}/api/health`, { cache: 'no-store' });
  if (!healthRes.ok) {
    throw new Error(`Health check failed for ${canonical}: HTTP ${healthRes.status}`);
  }
  const healthJson = await healthRes.json();
  const baseUrl = resolvePrewarmBaseUrl(healthJson, canonical);
  // Start directly on resolved backend URL (run.app when available) to avoid Hosting edge timeouts.
  const startUrl = baseUrl;
  console.log(`[prewarm] canonical=${canonical} base=${baseUrl} mode=${options.mode} scale=${dataScale}`);

  let failures = 0;
  const summaries: Array<{
    family: PrewarmFamily;
    runId: string;
    state: string;
    attempted: number;
    succeeded: number;
    hitRate: number;
    minDatasets: number;
    minHitRate: number;
    healthy: boolean;
    error: string | null;
  }> = [];
  for (const family of families) {
    try {
      const runId = await postPrewarmRun(startUrl, canonical, family, options);
      console.log(`[prewarm:${family}] runId=${runId}`);
      const status = await pollRun(baseUrl, family, runId);
      const terminal = String(status.state || '').toLowerCase();
      const attempted = Math.max(
        Number(status.datasetsAttempted || 0),
        Number(status.datasetsSucceeded || 0),
      );
      const succeeded = Math.max(0, Number(status.datasetsSucceeded || 0));
      const coverageThreshold = resolveCoverageThreshold({
        family,
        dataScale,
        requestedMaxTokens: Math.max(
          1,
          Number(options.maxTokens || defaultMaxTokensForFamily(family, dataScale)),
        ),
      });
      const minHitRate = Math.max(
        coverageThreshold.minHitRate,
        envMinHitRate ?? 0,
      );
      const coverage = computeCoverageHealth(
        { attempted, succeeded },
        { minDatasets: coverageThreshold.minDatasets, minHitRate },
      );

      summaries.push({
        family,
        runId,
        state: terminal,
        attempted,
        succeeded,
        hitRate: coverage.hitRate,
        minDatasets: coverageThreshold.minDatasets,
        minHitRate,
        healthy: coverage.healthy,
        error: status.error || null,
      });

      if (terminal === 'failed' || terminal === 'timeout') {
        failures += 1;
        console.error(`[prewarm:${family}] terminal=${terminal} error=${status.error || 'unknown'}`);
      } else if (!coverage.healthy) {
        failures += 1;
        console.error(
          `[prewarm:${family}] coverage unhealthy attempted=${attempted} succeeded=${succeeded} hitRate=${(coverage.hitRate * 100).toFixed(1)}% minDatasets=${coverageThreshold.minDatasets} minHitRate=${(minHitRate * 100).toFixed(1)}%`,
        );
      } else {
        console.log(
          `[prewarm:${family}] terminal=${terminal} progress=${status.progress ?? 100} hitRate=${(coverage.hitRate * 100).toFixed(1)}%`,
        );
      }
    } catch (error) {
      failures += 1;
      const message = error instanceof Error ? error.message : String(error);
      console.error(`[prewarm:${family}] exception=${message}`);
      summaries.push({
        family,
        runId: '',
        state: 'failed',
        attempted: 0,
        succeeded: 0,
        hitRate: 0,
        minDatasets: 0,
        minHitRate: 0,
        healthy: false,
        error: message,
      });
    }
  }

  try {
    const dir = join(process.cwd(), 'artifacts', 'ops', 'prewarm');
    mkdirSync(dir, { recursive: true });
    const reportPath = join(dir, `prewarm-${Date.now()}.json`);
    writeFileSync(
      reportPath,
      JSON.stringify(
        {
          generatedAt: new Date().toISOString(),
          canonical,
          baseUrl,
          options,
          families: summaries,
          failures,
        },
        null,
        2,
      ),
      'utf8',
    );
    console.log(`[prewarm] report=${reportPath}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[prewarm] unable to write report (${message})`);
  }

  if (failures > 0) {
    throw new Error(`Prewarm finished with ${failures} failing families.`);
  }
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`[prewarm] fatal=${message}`);
  process.exitCode = 1;
});
