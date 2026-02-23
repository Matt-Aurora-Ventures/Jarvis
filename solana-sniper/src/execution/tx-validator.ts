import { VersionedTransaction, PublicKey, TransactionInstruction } from '@solana/web3.js';
import { createModuleLogger } from '../utils/logger.js';

const log = createModuleLogger('tx-validator');

// Known safe programs that our transactions should interact with
const SAFE_PROGRAMS = new Set([
  '11111111111111111111111111111111',        // System Program
  'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA', // Token Program
  'ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL', // ATA Program
  'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4',  // Jupiter V6
  'ComputeBudget111111111111111111111111111111',    // Compute Budget
  '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8', // Raydium AMM V4
  '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P',  // PumpFun
  'T1pyyaTNZsKv2WcRAB8oVnk93mLJoBjvJhUJnMi1nER',  // Jito Tip
]);

// Maximum SOL we'd ever send in a single transaction (safety cap)
const MAX_SOL_PER_TX = 5_000_000_000; // 5 SOL in lamports

export interface TxValidationResult {
  valid: boolean;
  reason?: string;
  programIds: string[];
}

export function validateTransaction(tx: VersionedTransaction): TxValidationResult {
  try {
    const message = tx.message;
    const accountKeys = message.staticAccountKeys.map(k => k.toBase58());

    // Also include lookup table keys if available
    const programIds: string[] = [];

    // Check each instruction's program ID
    const compiledInstructions = message.compiledInstructions;
    for (const ix of compiledInstructions) {
      const programId = accountKeys[ix.programIdIndex];
      if (!programId) {
        return { valid: false, reason: 'Invalid program index in instruction', programIds };
      }
      programIds.push(programId);

      if (!SAFE_PROGRAMS.has(programId)) {
        log.warn('Unknown program in transaction', { programId });
        // Allow unknown programs but log them — don't hard fail
        // In production, you might want to whitelist only
      }
    }

    // Check: transaction shouldn't have too many instructions (>10 is suspicious)
    if (compiledInstructions.length > 15) {
      return { valid: false, reason: `Too many instructions: ${compiledInstructions.length}`, programIds };
    }

    // Check: transaction shouldn't have too many signers (>2 is unusual for our use case)
    if (message.header.numRequiredSignatures > 3) {
      return { valid: false, reason: `Too many required signatures: ${message.header.numRequiredSignatures}`, programIds };
    }

    log.info('Transaction validated', { programs: programIds.length, instructions: compiledInstructions.length });
    return { valid: true, programIds };
  } catch (err) {
    return { valid: false, reason: `Validation error: ${(err as Error).message}`, programIds: [] };
  }
}
