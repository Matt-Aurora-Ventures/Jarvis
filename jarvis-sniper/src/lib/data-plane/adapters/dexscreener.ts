import { runSourceProbe } from '@/lib/data-plane/adapters/source-probe';

export function probeDexScreener<T>(fetcher: () => Promise<T>) {
  return runSourceProbe({ source: 'dexscreener', fetcher, activeSources: 3 });
}
