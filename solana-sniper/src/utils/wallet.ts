import { Keypair, Connection, LAMPORTS_PER_SOL } from '@solana/web3.js';
import bs58 from 'bs58';
import { config } from '../config/index.js';
import { createModuleLogger } from './logger.js';

const log = createModuleLogger('wallet');

let _wallet: Keypair | null = null;
let _connection: Connection | null = null;

export function getWallet(): Keypair {
  if (!_wallet) {
    if (!config.walletPrivateKey) {
      throw new Error('WALLET_PRIVATE_KEY not set');
    }
    _wallet = Keypair.fromSecretKey(bs58.decode(config.walletPrivateKey));
    // Clear private key from config memory after Keypair creation
    (config as { walletPrivateKey: string }).walletPrivateKey = '';
    log.info('Wallet loaded', { pubkey: _wallet.publicKey.toBase58().slice(0, 8) + '...' });
  }
  return _wallet;
}

export function getConnection(): Connection {
  if (!_connection) {
    _connection = new Connection(config.rpcUrl, {
      commitment: 'confirmed',
      wsEndpoint: config.rpcUrl.replace('https://', 'wss://'),
    });
    log.info('RPC connected', { url: config.rpcUrl.split('?')[0] });
  }
  return _connection;
}

export async function getSolBalance(): Promise<number> {
  const conn = getConnection();
  const wallet = getWallet();
  const balance = await conn.getBalance(wallet.publicKey);
  return balance / LAMPORTS_PER_SOL;
}

export async function getSolBalanceUsd(): Promise<{ sol: number; usd: number }> {
  const sol = await getSolBalance();
  // Quick SOL price from Jupiter
  try {
    const resp = await fetch(`https://price.jup.ag/v6/price?ids=SOL`);
    const data = await resp.json() as { data: { SOL: { price: number } } };
    const price = data.data.SOL.price;
    return { sol, usd: sol * price };
  } catch {
    log.warn('Failed to fetch SOL price, using fallback');
    return { sol, usd: sol * 200 }; // fallback estimate
  }
}
