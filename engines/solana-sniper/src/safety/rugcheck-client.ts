import axios from 'axios';
import { RUGCHECK_API } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import type { RugCheckResult } from '../types/index.js';

const log = createModuleLogger('rugcheck');

interface RugCheckResponse {
  score: number;
  risks: Array<{ name: string; description: string; level: string; score: number }>;
  tokenMeta?: { name: string; symbol: string };
}

export async function checkRugCheck(mintAddress: string): Promise<RugCheckResult> {
  try {
    const url = `${RUGCHECK_API}/tokens/${mintAddress}/report/summary`;
    const resp = await axios.get<RugCheckResponse>(url, { timeout: 5000 });
    const data = resp.data;

    // RugCheck score: lower = more risky, higher = safer
    // Normalize to 0-100 where 100 = safest
    const normalizedScore = Math.max(0, Math.min(100, data.score ?? 0));

    const risks = (data.risks ?? [])
      .filter(r => r.level === 'danger' || r.level === 'warn')
      .map(r => `${r.name}: ${r.description}`);

    const result: RugCheckResult = {
      score: normalizedScore,
      risks,
      isVerified: normalizedScore >= 70,
      reportUrl: `https://rugcheck.xyz/tokens/${mintAddress}`,
    };

    log.info('RugCheck complete', {
      mint: mintAddress.slice(0, 8),
      score: normalizedScore,
      risks: risks.length,
    });

    return result;
  } catch (err) {
    log.error('RugCheck failed', { mint: mintAddress, error: (err as Error).message });
    return {
      score: 0,
      risks: ['RugCheck API unavailable'],
      isVerified: false,
      reportUrl: `https://rugcheck.xyz/tokens/${mintAddress}`,
    };
  }
}

export function scoreRugCheck(result: RugCheckResult): number {
  return result.score / 100;
}
