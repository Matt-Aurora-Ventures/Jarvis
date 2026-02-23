import axios from 'axios';
import { GOPLUS_API } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import type { GoPlusResult } from '../types/index.js';

const log = createModuleLogger('goplus');

interface GoPlusResponse {
  code: number;
  result: Record<string, {
    is_honeypot?: string;
    honeypot_with_same_creator?: string;
    is_proxy?: string;
    can_take_back_ownership?: string;
    is_mintable?: string;
    is_open_source?: string;
    buy_tax?: string;
    sell_tax?: string;
    holder_count?: string;
    lp_holder_count?: string;
    is_anti_whale?: string;
    is_blacklisted?: string;
    is_whitelisted?: string;
    transfer_pausable?: string;
    cannot_sell_all?: string;
    slippage_modifiable?: string;
    personal_slippage_modifiable?: string;
    trading_cooldown?: string;
    external_call?: string;
  }>;
}

export async function checkGoPlus(mintAddress: string): Promise<GoPlusResult> {
  try {
    const url = `${GOPLUS_API}/solana/token_security?contract_addresses=${mintAddress}`;
    const resp = await axios.get<GoPlusResponse>(url, { timeout: 5000 });

    const tokenData = resp.data.result?.[mintAddress.toLowerCase()] ?? resp.data.result?.[mintAddress];

    if (!tokenData) {
      log.warn('GoPlus: no data for token', { mint: mintAddress.slice(0, 8) });
      return defaultGoPlusResult();
    }

    const risks: string[] = [];
    const isHoneypot = tokenData.is_honeypot === '1';
    const hasProxy = tokenData.is_proxy === '1';
    const canTakeBack = tokenData.can_take_back_ownership === '1';
    const hasMint = tokenData.is_mintable === '1';
    const isOpenSource = tokenData.is_open_source === '1';
    const buyTax = parseFloat(tokenData.buy_tax ?? '0');
    const sellTax = parseFloat(tokenData.sell_tax ?? '0');

    if (isHoneypot) risks.push('HONEYPOT DETECTED');
    if (hasProxy) risks.push('Proxy contract');
    if (canTakeBack) risks.push('Owner can reclaim');
    if (hasMint) risks.push('Mintable');
    if (buyTax > 0.1) risks.push(`High buy tax: ${(buyTax * 100).toFixed(1)}%`);
    if (sellTax > 0.1) risks.push(`High sell tax: ${(sellTax * 100).toFixed(1)}%`);
    if (tokenData.cannot_sell_all === '1') risks.push('Cannot sell all tokens');
    if (tokenData.slippage_modifiable === '1') risks.push('Slippage modifiable');
    if (tokenData.transfer_pausable === '1') risks.push('Transfer pausable');
    if (tokenData.trading_cooldown === '1') risks.push('Trading cooldown');
    if (tokenData.external_call === '1') risks.push('External call risk');

    const result: GoPlusResult = {
      isHoneypot,
      hasProxyContract: hasProxy,
      canTakeBackOwnership: canTakeBack,
      hasMintFunction: hasMint,
      isOpenSource,
      buyTax,
      sellTax,
      risks,
    };

    log.info('GoPlus check complete', {
      mint: mintAddress.slice(0, 8),
      honeypot: isHoneypot,
      risks: risks.length,
    });

    return result;
  } catch (err) {
    log.error('GoPlus check failed', { mint: mintAddress, error: (err as Error).message });
    return defaultGoPlusResult();
  }
}

function defaultGoPlusResult(): GoPlusResult {
  return {
    isHoneypot: false,
    hasProxyContract: false,
    canTakeBackOwnership: false,
    hasMintFunction: false,
    isOpenSource: false,
    buyTax: 0,
    sellTax: 0,
    risks: ['GoPlus API unavailable - proceed with caution'],
  };
}

export function scoreGoPlus(result: GoPlusResult): number {
  if (result.isHoneypot) return 0;
  if (result.canTakeBackOwnership) return 0;

  let score = 1.0;
  if (result.hasProxyContract) score -= 0.3;
  if (result.hasMintFunction) score -= 0.2;
  if (!result.isOpenSource) score -= 0.1;
  if (result.buyTax > 0.05) score -= 0.2;
  if (result.sellTax > 0.05) score -= 0.2;
  score -= result.risks.length * 0.05;

  return Math.max(0, score);
}
