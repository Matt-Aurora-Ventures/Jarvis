'use client';

/**
 * QuickBuyWidget -- In-app buy via Bags API
 *
 * Replaces all Jupiter redirect buttons with a one-click buy flow.
 * Supports compact mode for inline table use and full mode for drawers/panels.
 * Includes TP/SL configuration and wallet integration.
 */

import { useState, useCallback, useMemo } from 'react';
import { useWallet } from '@solana/wallet-adapter-react';
import { Connection, VersionedTransaction } from '@solana/web3.js';
import { Zap, Loader2, ShieldCheck } from 'lucide-react';
import { getBagsTradingClient, SOL_MINT } from '@/lib/bags-trading';
import { useToast } from '@/components/ui/Toast';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RPC_URL =
  process.env.NEXT_PUBLIC_SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com';

const AMOUNT_PRESETS = [0.1, 0.25, 0.5, 1] as const;

const DEFAULT_SLIPPAGE_BPS = 100; // 1%

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface QuickBuyWidgetProps {
  tokenMint: string;
  tokenSymbol: string;
  compact?: boolean;
  defaultAmount?: number;
  suggestedTP?: number;
  suggestedSL?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function QuickBuyWidget({
  tokenMint,
  tokenSymbol,
  compact = false,
  defaultAmount = 0.5,
  suggestedTP = 20,
  suggestedSL = 10,
}: QuickBuyWidgetProps) {
  const { publicKey, signTransaction, connected } = useWallet();
  const toast = useToast();

  const [amount, setAmount] = useState(defaultAmount);
  const [tp, setTp] = useState(suggestedTP);
  const [sl, setSl] = useState(suggestedSL);
  const [isBuying, setIsBuying] = useState(false);

  // Memoize connection so we don't create a new one every render
  const connection = useMemo(() => new Connection(RPC_URL, 'confirmed'), []);

  // ---- Buy handler -------------------------------------------------------

  const handleBuy = useCallback(async () => {
    if (!connected || !publicKey || !signTransaction) {
      toast.warning('Connect your wallet first');
      return;
    }

    setIsBuying(true);
    try {
      const tradingClient = getBagsTradingClient(connection);

      toast.info(`Swapping ${amount} SOL for ${tokenSymbol}...`);

      const result = await tradingClient.executeSwap(
        publicKey.toBase58(),
        SOL_MINT,
        tokenMint,
        amount,
        DEFAULT_SLIPPAGE_BPS,
        signTransaction as (tx: VersionedTransaction) => Promise<VersionedTransaction>,
        false, // useJito
      );

      if (result.success) {
        // Record position entry for win/loss tracking
        if (result.outputAmount > 0) {
          const entryPrice = amount / result.outputAmount;
          tradingClient.recordPositionEntry(tokenMint, entryPrice, result.outputAmount);

          // Calculate TP/SL for reference
          const tpsl = tradingClient.calculateTPSL(entryPrice, tp, sl, true);
          console.log(
            `[QuickBuy] ${tokenSymbol} entry: $${entryPrice.toFixed(8)} | TP: $${tpsl.tpPrice.toFixed(8)} | SL: $${tpsl.slPrice.toFixed(8)}`,
          );
        }

        toast.success(
          `Bought ${tokenSymbol} with ${amount} SOL`,
          result.txHash,
        );
      } else {
        toast.error(`Buy failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Transaction failed';
      toast.error(message);
    } finally {
      setIsBuying(false);
    }
  }, [
    connected,
    publicKey,
    signTransaction,
    connection,
    amount,
    tokenMint,
    tokenSymbol,
    tp,
    sl,
    toast,
  ]);

  // ---- Compact mode -------------------------------------------------------

  if (compact) {
    return (
      <div className="flex items-center gap-1.5">
        {/* Amount Presets */}
        {AMOUNT_PRESETS.map((preset) => (
          <button
            key={preset}
            onClick={(e) => {
              e.stopPropagation();
              setAmount(preset);
            }}
            className={`px-1.5 py-0.5 text-[10px] font-mono rounded transition-colors
              ${amount === preset
                ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/40'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary border border-transparent'
              }`}
          >
            {preset}
          </button>
        ))}

        {/* Buy Button */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleBuy();
          }}
          disabled={isBuying || !connected}
          className={`inline-flex items-center gap-1 px-2 py-1 text-[10px] font-semibold rounded-md
            transition-all duration-150
            ${connected
              ? 'bg-accent-neon/20 text-accent-neon hover:bg-accent-neon/30 border border-accent-neon/30'
              : 'bg-bg-tertiary text-text-muted border border-border-primary cursor-not-allowed'
            }
            disabled:opacity-50`}
          title={
            !connected
              ? 'Connect Wallet'
              : `Buy ${amount} SOL of ${tokenSymbol} (TP:${tp}% SL:${sl}%)`
          }
        >
          {isBuying ? (
            <Loader2 className="w-3 h-3 animate-spin" />
          ) : (
            <Zap className="w-3 h-3" />
          )}
          {connected ? `${amount}` : 'Wallet'}
        </button>
      </div>
    );
  }

  // ---- Full mode ----------------------------------------------------------

  return (
    <div className="space-y-3">
      {/* Amount Selector */}
      <div>
        <label className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1.5 block">
          Amount (SOL)
        </label>
        <div className="flex gap-1.5">
          {AMOUNT_PRESETS.map((preset) => (
            <button
              key={preset}
              onClick={() => setAmount(preset)}
              className={`flex-1 py-1.5 text-xs font-mono rounded-md transition-colors
                ${amount === preset
                  ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/40'
                  : 'bg-bg-tertiary text-text-muted hover:text-text-primary border border-border-primary'
                }`}
            >
              {preset}
            </button>
          ))}
        </div>
      </div>

      {/* TP/SL Row */}
      <div className="flex gap-3">
        <div className="flex-1">
          <label className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1 block">
            TP %
          </label>
          <input
            type="number"
            value={tp}
            onChange={(e) => setTp(Math.max(0, parseFloat(e.target.value) || 0))}
            className="w-full px-2 py-1.5 text-xs font-mono rounded-md
              bg-bg-tertiary text-text-primary border border-border-primary
              focus:border-accent-neon/50 focus:outline-none transition-colors"
            min={0}
            step={5}
          />
        </div>
        <div className="flex-1">
          <label className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-1 block">
            SL %
          </label>
          <input
            type="number"
            value={sl}
            onChange={(e) => setSl(Math.max(0, parseFloat(e.target.value) || 0))}
            className="w-full px-2 py-1.5 text-xs font-mono rounded-md
              bg-bg-tertiary text-text-primary border border-border-primary
              focus:border-accent-neon/50 focus:outline-none transition-colors"
            min={0}
            step={5}
          />
        </div>
      </div>

      {/* Buy Button */}
      <button
        onClick={handleBuy}
        disabled={isBuying || !connected}
        className={`w-full py-3 px-4 rounded-lg font-semibold text-sm
          flex items-center justify-center gap-2 transition-all duration-200
          ${connected
            ? 'bg-accent-neon/20 text-accent-neon border border-accent-neon/30 hover:bg-accent-neon/30 hover:border-accent-neon/50'
            : 'bg-bg-tertiary text-text-muted border border-border-primary cursor-not-allowed'
          }
          disabled:opacity-50`}
      >
        {isBuying ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Executing...
          </>
        ) : !connected ? (
          'Connect Wallet'
        ) : (
          <>
            <ShieldCheck className="w-4 h-4" />
            BUY {amount} SOL
          </>
        )}
      </button>

      {/* TP/SL Summary */}
      {connected && (
        <div className="flex items-center justify-center gap-3 text-[10px] text-text-muted font-mono">
          <span>TP: +{tp}%</span>
          <span className="text-border-primary">|</span>
          <span>SL: -{sl}%</span>
        </div>
      )}
    </div>
  );
}
