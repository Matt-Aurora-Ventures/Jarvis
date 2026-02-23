import { proxyPerpsGet } from '@/lib/perps/proxy';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  return proxyPerpsGet('/status', request);
}
