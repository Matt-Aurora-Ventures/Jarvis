import { proxyInvestmentsPost, verifyInvestmentsAdminAuth } from '@/lib/investments/proxy';

export const runtime = 'nodejs';

export async function POST(request: Request) {
  const authError = verifyInvestmentsAdminAuth(request);
  if (authError) return authError;
  return proxyInvestmentsPost('/trigger-cycle', request);
}
