import {
  Connection,
  Keypair,
  PublicKey,
  VersionedTransaction,
  TransactionMessage,
  ComputeBudgetProgram,
  TransactionInstruction,
} from '@solana/web3.js';
import { getConnection, getWallet } from '../utils/wallet.js';
import { createTipInstruction } from './jito-executor.js';
import { getPriorityFee } from './priority-fees.js';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('tx-builder');

export interface TxBuildOptions {
  instructions: TransactionInstruction[];
  useJitoTip?: boolean;
  jitoTipLamports?: number;
  computeUnits?: number;
  urgency?: number; // 0-1
  signers?: Keypair[];
}

export async function buildTransaction(opts: TxBuildOptions): Promise<VersionedTransaction> {
  const conn = getConnection();
  const wallet = getWallet();

  const instructions: TransactionInstruction[] = [];

  // 1. Compute budget
  const fee = await getPriorityFee(opts.urgency ?? 0.5);
  instructions.push(
    ComputeBudgetProgram.setComputeUnitLimit({
      units: opts.computeUnits ?? 200_000,
    }),
    ComputeBudgetProgram.setComputeUnitPrice({
      microLamports: fee.feeLamports,
    }),
  );

  // 2. User instructions
  instructions.push(...opts.instructions);

  // 3. Jito tip (optional)
  if (opts.useJitoTip) {
    instructions.push(createTipInstruction(wallet.publicKey, opts.jitoTipLamports));
  }

  // 4. Build versioned transaction
  const { blockhash, lastValidBlockHeight } = await conn.getLatestBlockhash('confirmed');

  const message = new TransactionMessage({
    payerKey: wallet.publicKey,
    recentBlockhash: blockhash,
    instructions,
  }).compileToV0Message();

  const tx = new VersionedTransaction(message);

  // 5. Sign
  const signers = [wallet, ...(opts.signers ?? [])];
  tx.sign(signers);

  log.debug('Transaction built', {
    instructions: instructions.length,
    computeUnits: opts.computeUnits ?? 200_000,
    feeTier: fee.tier,
    jitoTip: opts.useJitoTip ?? false,
  });

  return tx;
}

export async function sendAndConfirm(
  tx: VersionedTransaction,
  maxRetries: number = 3,
): Promise<{ signature: string; confirmed: boolean }> {
  const conn = getConnection();

  const signature = await conn.sendRawTransaction(tx.serialize(), {
    skipPreflight: true,
    maxRetries,
  });

  const { blockhash, lastValidBlockHeight } = await conn.getLatestBlockhash('confirmed');

  const confirmation = await conn.confirmTransaction(
    { signature, blockhash, lastValidBlockHeight },
    'confirmed'
  );

  return {
    signature,
    confirmed: !confirmation.value.err,
  };
}
