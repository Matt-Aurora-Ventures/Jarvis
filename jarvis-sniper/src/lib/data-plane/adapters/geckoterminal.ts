import { runSourceProbe } from '@/lib/data-plane/adapters/source-probe';

export function probeGeckoTerminal<T>(fetcher: () => Promise<T>) {
  return runSourceProbe({ source: 'geckoterminal', fetcher, activeSources: 3 });
}
