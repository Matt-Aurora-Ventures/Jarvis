import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  buildAutonomyReadHeaders,
  buildAutonomyTelemetryHeaders,
  getAutonomyReadToken,
  getAutonomyTelemetryToken,
} from '@/lib/autonomy/client-auth';

type SavedEnv = {
  NEXT_PUBLIC_AUTONOMY_READ_TOKEN?: string;
  NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN?: string;
  NEXT_PUBLIC_AUTONOMY_JOB_TOKEN?: string;
};

const saved: SavedEnv = {
  NEXT_PUBLIC_AUTONOMY_READ_TOKEN: process.env.NEXT_PUBLIC_AUTONOMY_READ_TOKEN,
  NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN: process.env.NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN,
  NEXT_PUBLIC_AUTONOMY_JOB_TOKEN: process.env.NEXT_PUBLIC_AUTONOMY_JOB_TOKEN,
};

function clearEnv(): void {
  delete process.env.NEXT_PUBLIC_AUTONOMY_READ_TOKEN;
  delete process.env.NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN;
  delete process.env.NEXT_PUBLIC_AUTONOMY_JOB_TOKEN;
}

describe('autonomy client auth token scoping', () => {
  beforeEach(() => {
    clearEnv();
  });

  afterEach(() => {
    process.env.NEXT_PUBLIC_AUTONOMY_READ_TOKEN = saved.NEXT_PUBLIC_AUTONOMY_READ_TOKEN;
    process.env.NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN = saved.NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN;
    process.env.NEXT_PUBLIC_AUTONOMY_JOB_TOKEN = saved.NEXT_PUBLIC_AUTONOMY_JOB_TOKEN;
  });

  it('does not fall back to NEXT_PUBLIC_AUTONOMY_JOB_TOKEN for read headers', () => {
    process.env.NEXT_PUBLIC_AUTONOMY_JOB_TOKEN = 'job-public-token';

    expect(getAutonomyReadToken()).toBe('');
    expect(buildAutonomyReadHeaders().get('Authorization')).toBeNull();
  });

  it('does not fall back to NEXT_PUBLIC_AUTONOMY_JOB_TOKEN for telemetry headers', () => {
    process.env.NEXT_PUBLIC_AUTONOMY_JOB_TOKEN = 'job-public-token';

    expect(getAutonomyTelemetryToken()).toBe('');
    expect(buildAutonomyTelemetryHeaders().get('Authorization')).toBeNull();
  });

  it('uses scoped public tokens when explicitly configured', () => {
    process.env.NEXT_PUBLIC_AUTONOMY_READ_TOKEN = 'read-public-token';
    process.env.NEXT_PUBLIC_AUTONOMY_TELEMETRY_TOKEN = 'telemetry-public-token';

    expect(getAutonomyReadToken()).toBe('read-public-token');
    expect(getAutonomyTelemetryToken()).toBe('telemetry-public-token');
    expect(buildAutonomyReadHeaders().get('Authorization')).toBe('Bearer read-public-token');
    expect(buildAutonomyTelemetryHeaders().get('Authorization')).toBe('Bearer telemetry-public-token');
  });
});
