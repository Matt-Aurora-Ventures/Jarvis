import axios from 'axios';
import { config } from '../config/index.js';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('priority-fees');

interface HeliusFeeResponse {
  result: {
    priorityFeeLevels: {
      min: number;
      low: number;
      medium: number;
      high: number;
      veryHigh: number;
      unsafeMax: number;
    };
  };
}

export type FeeTier = 'LOW' | 'MEDIUM' | 'HIGH' | 'ULTRA';

export async function getPriorityFee(urgency: number = 0.5): Promise<{ feeLamports: number; tier: FeeTier }> {
  try {
    if (!config.heliusApiKey) {
      return getStaticFee(urgency);
    }

    const resp = await axios.post<HeliusFeeResponse>(
      `https://mainnet.helius-rpc.com/?api-key=${config.heliusApiKey}`,
      {
        jsonrpc: '2.0',
        id: 'fee-estimate',
        method: 'getPriorityFeeEstimate',
        params: [{ options: { includeAllPriorityFeeLevels: true } }],
      },
      { timeout: 3000 }
    );

    const levels = resp.data.result.priorityFeeLevels;

    let feeLamports: number;
    let tier: FeeTier;

    if (urgency < 0.3) {
      feeLamports = levels.low;
      tier = 'LOW';
    } else if (urgency < 0.6) {
      feeLamports = levels.medium;
      tier = 'MEDIUM';
    } else if (urgency < 0.9) {
      feeLamports = levels.high;
      tier = 'HIGH';
    } else {
      feeLamports = levels.veryHigh;
      tier = 'ULTRA';
    }

    log.debug('Priority fee estimated', { tier, feeLamports, urgency });
    return { feeLamports, tier };
  } catch (err) {
    log.warn('Priority fee API failed, using static', { error: (err as Error).message });
    return getStaticFee(urgency);
  }
}

function getStaticFee(urgency: number): { feeLamports: number; tier: FeeTier } {
  if (urgency < 0.3) return { feeLamports: 10_000, tier: 'LOW' };
  if (urgency < 0.6) return { feeLamports: 100_000, tier: 'MEDIUM' };
  if (urgency < 0.9) return { feeLamports: 500_000, tier: 'HIGH' };
  return { feeLamports: 1_000_000, tier: 'ULTRA' };
}
