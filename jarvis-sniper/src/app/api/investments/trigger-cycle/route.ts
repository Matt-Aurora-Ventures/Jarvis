import { proxyInvestmentsPost } from '@/lib/investments/proxy';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  return proxyInvestmentsPost('/trigger-cycle', request);
}
