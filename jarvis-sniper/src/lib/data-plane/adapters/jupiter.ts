import { runSourceProbe } from '@/lib/data-plane/adapters/source-probe';

export function probeJupiter<T>(fetcher: () => Promise<T>) {
  return runSourceProbe({ source: 'jupiter', fetcher, activeSources: 3 });
}
