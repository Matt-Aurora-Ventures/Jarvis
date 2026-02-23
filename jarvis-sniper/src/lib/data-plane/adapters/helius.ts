import { runSourceProbe } from '@/lib/data-plane/adapters/source-probe';

export function probeHelius<T>(fetcher: () => Promise<T>) {
  return runSourceProbe({ source: 'helius', fetcher, activeSources: 2 });
}
