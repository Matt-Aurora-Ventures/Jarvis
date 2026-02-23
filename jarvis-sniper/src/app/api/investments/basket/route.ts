import { proxyInvestmentsGet } from '@/lib/investments/proxy';

export const runtime = 'nodejs';

export async function GET(request: Request) {
  return proxyInvestmentsGet('/basket', request);
}
