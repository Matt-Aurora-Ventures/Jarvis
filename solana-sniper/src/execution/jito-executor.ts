import {
  VersionedTransaction,
  SystemProgram,
  TransactionInstruction,
  TransactionMessage,
  PublicKey,
  Keypair,
} from '@solana/web3.js';
import axios from 'axios';
import { config } from '../config/index.js';
import { JITO_TIP_ACCOUNTS, JITO_TIP_LAMPORTS } from '../config/constants.js';
import { getConnection, getWallet } from '../utils/wallet.js';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('jito');

const JITO_BUNDLE_URL = 'https://mainnet.block-engine.jito.wtf/api/v1/bundles';

export function getRandomTipAccount(): PublicKey {
  const idx = Math.floor(Math.random() * JITO_TIP_ACCOUNTS.length);
  return new PublicKey(JITO_TIP_ACCOUNTS[idx]);
}

export function createTipInstruction(
  fromPubkey: PublicKey,
  tipLamports: number = JITO_TIP_LAMPORTS,
): TransactionInstruction {
  return SystemProgram.transfer({
    fromPubkey,
    toPubkey: getRandomTipAccount(),
    lamports: tipLamports,
  });
}

export async function sendJitoBundle(
  transactions: VersionedTransaction[],
): Promise<{ success: boolean; bundleId: string | null; error: string | null }> {
  try {
    const serialized = transactions.map(tx =>
      Buffer.from(tx.serialize()).toString('base64')
    );

    const resp = await axios.post(
      JITO_BUNDLE_URL,
      {
        jsonrpc: '2.0',
        id: 1,
        method: 'sendBundle',
        params: [serialized],
      },
      { timeout: 10000 }
    );

    const bundleId = resp.data?.result;

    if (bundleId) {
      log.info('Jito bundle sent', { bundleId });
      return { success: true, bundleId, error: null };
    }

    const error = resp.data?.error?.message ?? 'Unknown Jito error';
    log.error('Jito bundle rejected', { error });
    return { success: false, bundleId: null, error };
  } catch (err) {
    log.error('Jito bundle send failed', { error: (err as Error).message });
    return { success: false, bundleId: null, error: (err as Error).message };
  }
}

export async function checkBundleStatus(bundleId: string): Promise<string> {
  try {
    const resp = await axios.post(
      JITO_BUNDLE_URL,
      {
        jsonrpc: '2.0',
        id: 1,
        method: 'getBundleStatuses',
        params: [[bundleId]],
      },
      { timeout: 5000 }
    );

    const statuses = resp.data?.result?.value;
    if (statuses && statuses.length > 0) {
      return statuses[0].confirmation_status ?? 'unknown';
    }
    return 'pending';
  } catch {
    return 'unknown';
  }
}
