import { proxyPerpsPost } from '@/lib/perps/proxy';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  return proxyPerpsPost('/open', request);
}
