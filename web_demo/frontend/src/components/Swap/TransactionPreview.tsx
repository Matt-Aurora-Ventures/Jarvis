/**
 * Transaction Preview Modal
 * Builds trust by showing exactly what will happen before signing.
 *
 * Best practices implemented:
 * - Clear breakdown of transaction details
 * - Security warnings and contract verification
 * - Price impact visualization
 * - Network fee display
 * - Audited badge for trust
 */
import React from 'react';
import {
  X,
  Shield,
  CheckCircle,
  AlertTriangle,
  Lock,
  Info,
  ArrowRight,
  TrendingDown,
  Clock
} from 'lucide-react';
import { GlassCard } from '../UI/GlassCard';
import clsx from 'clsx';

interface TransactionPreviewProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  transaction: {
    inputToken: string;
    outputToken: string;
    inputAmount: string;
    outputAmount: string;
    priceImpact: number;
    slippage: number;
    networkFee: number;
    route: Array<{
      dex: string;
      percentage: number;
    }>;
    contractAddress?: string;
    isVerified: boolean;
  };
}

export const TransactionPreview: React.FC<TransactionPreviewProps> = ({
  isOpen,
  onClose,
  onConfirm,
  transaction
}) => {
  if (!isOpen) return null;

  const {
    inputToken,
    outputToken,
    inputAmount,
    outputAmount,
    priceImpact,
    slippage,
    networkFee,
    route,
    contractAddress,
    isVerified
  } = transaction;

  const isHighImpact = priceImpact > 3;
  const isMediumImpact = priceImpact > 1;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <GlassCard className="max-w-md w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-display font-bold">Transaction Preview</h2>
            <p className="text-sm text-muted mt-1">Review before confirming in your wallet</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-surface transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Security Badge */}
        <div className="mb-6 p-4 bg-success/10 border border-success/30 rounded-lg">
          <div className="flex items-start gap-3">
            <Shield className="text-success flex-shrink-0 mt-0.5" size={20} />
            <div>
              <div className="font-semibold text-success mb-1 flex items-center gap-2">
                Secure Transaction
                {isVerified && <CheckCircle size={16} />}
              </div>
              <p className="text-xs text-success/80 leading-relaxed">
                This swap uses audited smart contracts. Your private keys never leave your wallet.
                {isVerified && ' Contract is verified on Solana Explorer.'}
              </p>
            </div>
          </div>
        </div>

        {/* Transaction Details */}
        <div className="space-y-4 mb-6">
          {/* You Will Send */}
          <div className="p-4 bg-surface rounded-lg border border-border">
            <div className="text-sm text-muted mb-2">You will send</div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-mono font-bold">{inputAmount}</span>
              <span className="text-2xl font-bold text-accent">{inputToken}</span>
            </div>
          </div>

          {/* Arrow */}
          <div className="flex justify-center">
            <ArrowRight className="text-muted" size={24} />
          </div>

          {/* You Will Receive */}
          <div className="p-4 bg-surface rounded-lg border border-border">
            <div className="text-sm text-muted mb-2">You will receive (minimum)</div>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-mono font-bold">{outputAmount}</span>
              <span className="text-2xl font-bold text-accent">{outputToken}</span>
            </div>
            <p className="text-xs text-muted mt-2">
              Due to {slippage}% slippage tolerance, you may receive slightly less if the price
              moves.
            </p>
          </div>
        </div>

        {/* Route */}
        {route && route.length > 0 && (
          <div className="mb-6 p-4 bg-surface rounded-lg border border-border">
            <div className="text-sm font-semibold mb-3">Route</div>
            <div className="space-y-2">
              {route.map((r, idx) => (
                <div key={idx} className="flex items-center justify-between text-sm">
                  <span className="text-muted">{r.dex}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-surface-hover rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent rounded-full"
                        style={{ width: `${r.percentage}%` }}
                      />
                    </div>
                    <span className="font-semibold w-10 text-right">{r.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Fees & Impact */}
        <div className="mb-6 space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted flex items-center gap-1">
              <Info size={14} />
              Price Impact
            </span>
            <span
              className={clsx(
                'font-semibold',
                isHighImpact
                  ? 'text-error'
                  : isMediumImpact
                  ? 'text-warning'
                  : 'text-success'
              )}
            >
              {priceImpact.toFixed(2)}%
              {isHighImpact && ' ⚠️'}
            </span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-muted">Slippage Tolerance</span>
            <span className="font-semibold">{slippage}%</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-muted flex items-center gap-1">
              <Clock size={14} />
              Network Fee
            </span>
            <span className="font-semibold">~{networkFee.toFixed(6)} SOL</span>
          </div>

          {contractAddress && (
            <div className="flex items-center justify-between">
              <span className="text-muted flex items-center gap-1">
                <Lock size={14} />
                Contract
              </span>
              <code className="text-xs bg-surface px-2 py-1 rounded font-mono">
                {contractAddress.slice(0, 6)}...{contractAddress.slice(-6)}
                {isVerified && (
                  <CheckCircle size={12} className="inline ml-1 text-success" />
                )}
              </code>
            </div>
          )}
        </div>

        {/* High Impact Warning */}
        {isHighImpact && (
          <div className="mb-6 p-3 bg-error/10 border border-error/30 rounded-lg flex items-start gap-2">
            <AlertTriangle className="text-error flex-shrink-0 mt-0.5" size={16} />
            <div>
              <p className="text-sm text-error font-semibold mb-1">High Price Impact Warning</p>
              <p className="text-xs text-error/80">
                This trade will significantly move the market price ({priceImpact.toFixed(2)}%).
                Consider:
              </p>
              <ul className="text-xs text-error/80 mt-2 ml-4 list-disc space-y-1">
                <li>Splitting into smaller trades</li>
                <li>Using limit orders instead</li>
                <li>Waiting for better liquidity</li>
              </ul>
            </div>
          </div>
        )}

        {/* Security Note */}
        <div className="mb-6 p-3 bg-surface rounded-lg flex items-start gap-2">
          <Info size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p className="text-xs text-muted leading-relaxed">
            <strong>Security:</strong> Always verify the amounts and token addresses in your
            wallet before signing. Never share your private keys or seed phrase.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button onClick={onClose} className="btn btn-secondary flex-1">
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={clsx(
              'btn btn-primary flex-1',
              isHighImpact && 'btn-warning'
            )}
          >
            {isHighImpact ? (
              <>
                <AlertTriangle size={18} />
                <span>Confirm Anyway</span>
              </>
            ) : (
              <>
                <CheckCircle size={18} />
                <span>Confirm in Wallet</span>
              </>
            )}
          </button>
        </div>

        {/* Powered By */}
        <div className="mt-4 text-center text-xs text-muted">
          <div className="flex items-center justify-center gap-1">
            <Shield size={12} className="text-success" />
            <span>Powered by Bags.fm | 0.5% service fee</span>
          </div>
        </div>
      </GlassCard>
    </div>
  );
};
