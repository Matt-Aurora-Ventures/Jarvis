import { VersionedTransaction, Connection } from '@solana/web3.js';
import axios from 'axios';
import { getConnection, getWallet } from '../utils/wallet.js';
import { config } from '../config/index.js';
import { LAMPORTS_PER_SOL } from '../config/constants.js';
import { createModuleLogger } from '../utils/logger.js';
import { validateTransaction } from '../execution/tx-validator.js';
import type { ExecutionResult } from '../types/index.js';

const log = createModuleLogger('pumpportal');

const PUMPPORTAL_TRADE_URL = 'https://pumpportal.fun/api/trade-local';

interface PumpPortalTradeRequest {
  publicKey: string;
  action: 'buy' | 'sell';
  mint: string;
  amount: number; // SOL for buys, token amount for sells
  denominatedInSol: 'true' | 'false';
  slippage: number; // percentage
  priorityFee: number; // SOL
  pool: 'pump' | 'raydium';
}

export async function executePumpPortalBuy(
  mintAddress: string,
  solAmount: number,
  slippagePct: number = 25, // pump.fun needs higher slippage
  priorityFeeSol: number = 0.0001,
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const wallet = getWallet();
  const conn = getConnection();

  if (config.tradingMode === 'paper') {
    log.info('PAPER TRADE (PumpPortal buy)', { mint: mintAddress.slice(0, 8), sol: solAmount });
    return {
      success: true,
      signature: `paper_pump_${Date.now()}`,
      error: null,
      side: 'BUY',
      mint: mintAddress,
      amountIn: solAmount,
      amountOut: 0,
      priceUsd: 0,
      feeUsd: 0,
      executedAt: Date.now(),
      mode: 'paper',
      latencyMs: Date.now() - startTime,
    };
  }

  try {
    const body: PumpPortalTradeRequest = {
      publicKey: wallet.publicKey.toBase58(),
      action: 'buy',
      mint: mintAddress,
      amount: solAmount,
      denominatedInSol: 'true',
      slippage: slippagePct,
      priorityFee: priorityFeeSol,
      pool: 'pump',
    };

    const resp = await axios.post(PUMPPORTAL_TRADE_URL, body, {
      timeout: 10000,
      responseType: 'arraybuffer',
    });

    const tx = VersionedTransaction.deserialize(new Uint8Array(resp.data));

    // Validate transaction before signing
    const validation = validateTransaction(tx);
    if (!validation.valid) {
      log.error('TX validation failed — refusing to sign', { reason: validation.reason, mint: mintAddress });
      return {
        success: false, signature: null, error: `TX validation failed: ${validation.reason}`,
        mint: mintAddress, side: 'BUY' as const, amountIn: solAmount, amountOut: 0,
        priceUsd: 0, feeUsd: 0, executedAt: Date.now(),
        mode: config.tradingMode as 'paper' | 'live', latencyMs: Date.now() - startTime,
      };
    }

    tx.sign([wallet]);

    const signature = await conn.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 3,
    });

    // Wait for confirmation
    const latestBlockhash = await conn.getLatestBlockhash('confirmed');
    await conn.confirmTransaction({
      signature,
      blockhash: latestBlockhash.blockhash,
      lastValidBlockHeight: latestBlockhash.lastValidBlockHeight,
    }, 'confirmed');

    const latency = Date.now() - startTime;
    log.info('PumpPortal buy executed', {
      sig: signature.slice(0, 16),
      mint: mintAddress.slice(0, 8),
      sol: solAmount,
      latency: latency + 'ms',
    });

    return {
      success: true,
      signature,
      error: null,
      side: 'BUY',
      mint: mintAddress,
      amountIn: solAmount,
      amountOut: 0, // Need to parse from TX
      priceUsd: 0,
      feeUsd: priorityFeeSol * 200,
      executedAt: Date.now(),
      mode: 'live',
      latencyMs: latency,
    };
  } catch (err) {
    log.error('PumpPortal buy failed', { error: (err as Error).message });
    return {
      success: false,
      signature: null,
      error: (err as Error).message,
      side: 'BUY',
      mint: mintAddress,
      amountIn: solAmount,
      amountOut: 0,
      priceUsd: 0,
      feeUsd: 0,
      executedAt: Date.now(),
      mode: config.tradingMode,
      latencyMs: Date.now() - startTime,
    };
  }
}

export async function executePumpPortalSell(
  mintAddress: string,
  tokenAmount: number,
  slippagePct: number = 25,
  priorityFeeSol: number = 0.0005,
): Promise<ExecutionResult> {
  const startTime = Date.now();
  const wallet = getWallet();
  const conn = getConnection();

  if (config.tradingMode === 'paper') {
    log.info('PAPER TRADE (PumpPortal sell)', { mint: mintAddress.slice(0, 8), tokens: tokenAmount });
    return {
      success: true,
      signature: `paper_pump_sell_${Date.now()}`,
      error: null,
      side: 'SELL',
      mint: mintAddress,
      amountIn: tokenAmount,
      amountOut: 0,
      priceUsd: 0,
      feeUsd: 0,
      executedAt: Date.now(),
      mode: 'paper',
      latencyMs: Date.now() - startTime,
    };
  }

  try {
    const body: PumpPortalTradeRequest = {
      publicKey: wallet.publicKey.toBase58(),
      action: 'sell',
      mint: mintAddress,
      amount: tokenAmount,
      denominatedInSol: 'false',
      slippage: slippagePct,
      priorityFee: priorityFeeSol,
      pool: 'pump',
    };

    const resp = await axios.post(PUMPPORTAL_TRADE_URL, body, {
      timeout: 10000,
      responseType: 'arraybuffer',
    });

    const tx = VersionedTransaction.deserialize(new Uint8Array(resp.data));

    const sellValidation = validateTransaction(tx);
    if (!sellValidation.valid) {
      log.error('Sell TX validation failed', { reason: sellValidation.reason, mint: mintAddress });
      return {
        success: false, signature: null, error: `TX validation failed: ${sellValidation.reason}`,
        mint: mintAddress, side: 'SELL' as const, amountIn: tokenAmount, amountOut: 0,
        priceUsd: 0, feeUsd: 0, executedAt: Date.now(),
        mode: config.tradingMode as 'paper' | 'live', latencyMs: Date.now() - startTime,
      };
    }

    tx.sign([wallet]);

    const signature = await conn.sendRawTransaction(tx.serialize(), {
      skipPreflight: true,
      maxRetries: 3,
    });

    const latestBlockhash = await conn.getLatestBlockhash('confirmed');
    await conn.confirmTransaction({
      signature,
      blockhash: latestBlockhash.blockhash,
      lastValidBlockHeight: latestBlockhash.lastValidBlockHeight,
    }, 'confirmed');

    const latency = Date.now() - startTime;
    log.info('PumpPortal sell executed', {
      sig: signature.slice(0, 16),
      mint: mintAddress.slice(0, 8),
      latency: latency + 'ms',
    });

    return {
      success: true,
      signature,
      error: null,
      side: 'SELL',
      mint: mintAddress,
      amountIn: tokenAmount,
      amountOut: 0,
      priceUsd: 0,
      feeUsd: priorityFeeSol * 200,
      executedAt: Date.now(),
      mode: 'live',
      latencyMs: latency,
    };
  } catch (err) {
    log.error('PumpPortal sell failed', { error: (err as Error).message });
    return {
      success: false,
      signature: null,
      error: (err as Error).message,
      side: 'SELL',
      mint: mintAddress,
      amountIn: tokenAmount,
      amountOut: 0,
      priceUsd: 0,
      feeUsd: 0,
      executedAt: Date.now(),
      mode: config.tradingMode,
      latencyMs: Date.now() - startTime,
    };
  }
}
