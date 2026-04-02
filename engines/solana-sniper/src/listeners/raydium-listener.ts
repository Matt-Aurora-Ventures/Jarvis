import { Connection, PublicKey, Commitment } from '@solana/web3.js';
import { EventEmitter } from 'events';
import { getConnection } from '../utils/wallet.js';
import { RAYDIUM_AMM_V4, WSOL_MINT } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import type { NewPoolEvent } from '../types/index.js';

const log = createModuleLogger('raydium-listener');

// Raydium AMM V4 account layout offsets for pool state
const POOL_STATE_SIZE = 752;
const QUOTE_MINT_OFFSET = 432; // offset of quoteMint in LiquidityStateV4

export class RaydiumListener extends EventEmitter {
  private conn: Connection;
  private subscriptionId: number | null = null;
  private seenPools: Set<string> = new Set();

  constructor() {
    super();
    this.conn = getConnection();
  }

  async start(): Promise<void> {
    log.info('Starting Raydium pool listener...');

    this.subscriptionId = this.conn.onProgramAccountChange(
      RAYDIUM_AMM_V4,
      async (updatedAccountInfo, context) => {
        try {
          const accountData = updatedAccountInfo.accountInfo.data;
          if (accountData.length < POOL_STATE_SIZE) return;

          const poolAddress = updatedAccountInfo.accountId.toBase58();
          if (this.seenPools.has(poolAddress)) return;
          this.seenPools.add(poolAddress);

          // Decode pool state manually (avoid full SDK dependency)
          // baseMint at offset 400, quoteMint at offset 432
          const baseMint = new PublicKey(accountData.slice(400, 432)).toBase58();
          const quoteMint = new PublicKey(accountData.slice(432, 464)).toBase58();
          const lpMint = new PublicKey(accountData.slice(272, 304)).toBase58();
          const baseVault = new PublicKey(accountData.slice(336, 368)).toBase58();
          const quoteVault = new PublicKey(accountData.slice(368, 400)).toBase58();

          // Only care about SOL-paired pools
          if (quoteMint !== WSOL_MINT.toBase58() && baseMint !== WSOL_MINT.toBase58()) {
            return;
          }

          const tokenMint = baseMint === WSOL_MINT.toBase58() ? quoteMint : baseMint;

          const event: NewPoolEvent = {
            type: 'raydium_pool',
            mint: tokenMint,
            poolAddress,
            baseMint,
            quoteMint,
            baseVault,
            quoteVault,
            lpMint,
            timestamp: Date.now(),
            raw: { slot: context.slot },
          };

          log.info('New Raydium pool detected', {
            pool: poolAddress.slice(0, 8),
            token: tokenMint.slice(0, 8),
            slot: context.slot,
          });

          this.emit('newPool', event);
        } catch (err) {
          log.error('Error processing pool update', { error: (err as Error).message });
        }
      },
      'confirmed' as Commitment,
      [
        { dataSize: POOL_STATE_SIZE },
        {
          memcmp: {
            offset: QUOTE_MINT_OFFSET,
            bytes: WSOL_MINT.toBase58(),
          },
        },
      ],
    );

    log.info('Raydium listener active', { subscriptionId: this.subscriptionId });
  }

  async stop(): Promise<void> {
    if (this.subscriptionId !== null) {
      await this.conn.removeProgramAccountChangeListener(this.subscriptionId);
      this.subscriptionId = null;
      log.info('Raydium listener stopped');
    }
  }

  getSeenCount(): number {
    return this.seenPools.size;
  }
}
