import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('GET /api/investments/version', () => {
  beforeEach(() => {
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_BUILD_SHA;
    delete process.env.GITHUB_SHA;
    delete process.env.INVESTMENTS_SERVICE_BUILD_SHA;
  });

  it('reports drift when workspace and service SHAs differ', async () => {
    process.env.NEXT_PUBLIC_BUILD_SHA = 'workspace-sha';
    process.env.INVESTMENTS_SERVICE_BUILD_SHA = 'container-sha';

    const route = await import('@/app/api/investments/version/route');
    const res = await route.GET();
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.driftDetected).toBe(true);
    expect(String(body.warning || '')).toContain('differs');
  });
});
