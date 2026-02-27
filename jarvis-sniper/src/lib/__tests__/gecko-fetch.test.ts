import { afterEach, describe, expect, it, vi } from 'vitest';

describe('geckoFetchPaced', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it('aborts when external signal is cancelled', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const signal = init?.signal as AbortSignal | undefined;
      return await new Promise<Response>((_resolve, reject) => {
        if (signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'));
          return;
        }
        signal?.addEventListener(
          'abort',
          () => {
            reject(new DOMException('Aborted', 'AbortError'));
          },
          { once: true },
        );
      });
    });

    const { geckoFetchPaced } = await import('@/lib/gecko-fetch');
    const controller = new AbortController();

    const pending = geckoFetchPaced(
      'https://api.geckoterminal.com/api/v2/networks/solana/pools/test/ohlcv/hour',
      { signal: controller.signal },
    );

    controller.abort();
    await expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
