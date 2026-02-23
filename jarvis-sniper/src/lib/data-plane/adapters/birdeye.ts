import { runSourceProbe } from '@/lib/data-plane/adapters/source-probe';

export function probeBirdeye<T>(fetcher: () => Promise<T>) {
  return runSourceProbe({ source: 'birdeye', fetcher, activeSources: 3 });
}
