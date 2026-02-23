import { describe, it, expect } from 'vitest';
import { VersionedTransaction, VersionedMessage, MessageV0, PublicKey, TransactionInstruction, ComputeBudgetProgram } from '@solana/web3.js';
import { validateTransaction } from '../execution/tx-validator.js';

describe('Transaction Validator', () => {
  it('should reject transactions with too many instructions', () => {
    // Create a mock transaction with excessive instructions
    const mockMessage = {
      staticAccountKeys: [
        new PublicKey('11111111111111111111111111111111'),
        new PublicKey('ComputeBudget111111111111111111111111111111'),
      ],
      header: { numRequiredSignatures: 1, numReadonlySignedAccounts: 0, numReadonlyUnsignedAccounts: 1 },
      compiledInstructions: Array(20).fill({ programIdIndex: 0, accountKeyIndexes: [], data: new Uint8Array() }),
      recentBlockhash: 'test',
      addressTableLookups: [],
    } as unknown as MessageV0;

    const tx = new VersionedTransaction(mockMessage);
    const result = validateTransaction(tx);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain('Too many instructions');
  });

  it('should reject transactions with too many signers', () => {
    const mockMessage = {
      staticAccountKeys: [
        new PublicKey('11111111111111111111111111111111'),
      ],
      header: { numRequiredSignatures: 5, numReadonlySignedAccounts: 0, numReadonlyUnsignedAccounts: 0 },
      compiledInstructions: [{ programIdIndex: 0, accountKeyIndexes: [], data: new Uint8Array() }],
      recentBlockhash: 'test',
      addressTableLookups: [],
    } as unknown as MessageV0;

    const tx = new VersionedTransaction(mockMessage);
    const result = validateTransaction(tx);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain('Too many required signatures');
  });

  it('should accept valid transactions with known programs', () => {
    const mockMessage = {
      staticAccountKeys: [
        new PublicKey('11111111111111111111111111111111'),
        new PublicKey('ComputeBudget111111111111111111111111111111'),
      ],
      header: { numRequiredSignatures: 1, numReadonlySignedAccounts: 0, numReadonlyUnsignedAccounts: 1 },
      compiledInstructions: [
        { programIdIndex: 0, accountKeyIndexes: [], data: new Uint8Array() },
        { programIdIndex: 1, accountKeyIndexes: [], data: new Uint8Array() },
      ],
      recentBlockhash: 'test',
      addressTableLookups: [],
    } as unknown as MessageV0;

    const tx = new VersionedTransaction(mockMessage);
    const result = validateTransaction(tx);
    expect(result.valid).toBe(true);
    expect(result.programIds).toHaveLength(2);
  });
});
