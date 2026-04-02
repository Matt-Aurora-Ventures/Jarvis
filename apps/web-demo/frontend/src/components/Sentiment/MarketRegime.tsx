/**
 * Market Regime Component - Beautiful AI Market Analysis Display
 * Shows bull/bear/neutral classification with risk levels
 */
import React from 'react';
import { TrendingUp, TrendingDown, Minus, AlertTriangle, Shield, Activity } from 'lucide-react';
import { GlassCard } from '../UI/GlassCard';
import clsx from 'clsx';

interface MarketRegimeProps {
  regime: 'BULL' | 'BEAR' | 'NEUTRAL';
  riskLevel: 'LOW' | 'NORMAL' | 'HIGH' | 'EXTREME';
  btcChange: number;
  solChange: number;
}

export const MarketRegime: React.FC<MarketRegimeProps> = ({
  regime,
  riskLevel,
  btcChange,
  solChange,
}) => {
  // Regime config
  const regimeConfig = {
    BULL: {
      icon: <TrendingUp className="w-8 h-8" />,
      color: 'text-success',
      bg: 'bg-success/10',
      border: 'border-success/30',
      label: 'BULLISH',
      emoji: '🟢',
    },
    BEAR: {
      icon: <TrendingDown className="w-8 h-8" />,
      color: 'text-error',
      bg: 'bg-error/10',
      border: 'border-error/30',
      label: 'BEARISH',
      emoji: '🔴',
    },
    NEUTRAL: {
      icon: <Minus className="w-8 h-8" />,
      color: 'text-warning',
      bg: 'bg-warning/10',
      border: 'border-warning/30',
      label: 'NEUTRAL',
      emoji: '🟡',
    },
  };

  // Risk level config
  const riskConfig = {
    LOW: {
      icon: <Shield className="w-5 h-5" />,
      color: 'text-success',
      emoji: '🟢',
      description: 'Safe to trade with moderate position sizes',
    },
    NORMAL: {
      icon: <Activity className="w-5 h-5" />,
      color: 'text-warning',
      emoji: '🟡',
      description: 'Normal market conditions, standard risk management',
    },
    HIGH: {
      icon: <AlertTriangle className="w-5 h-5" />,
      color: 'text-warning',
      emoji: '🟠',
      description: 'Increased volatility, reduce position sizes',
    },
    EXTREME: {
      icon: <AlertTriangle className="w-5 h-5" />,
      color: 'text-error',
      emoji: '🔴',
      description: 'Extreme risk, consider sitting out or hedging',
    },
  };

  const currentRegime = regimeConfig[regime];
  const currentRisk = riskConfig[riskLevel];

  return (
    <GlassCard className={clsx('border-2', currentRegime.border)}>
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'p-3 rounded-xl',
            currentRegime.bg
          )}>
            <div className={currentRegime.color}>
              {currentRegime.icon}
            </div>
          </div>

          <div>
            <p className="text-sm text-muted mb-1">AI Market Regime</p>
            <h3 className="text-2xl font-display font-bold flex items-center gap-2">
              <span>{currentRegime.emoji}</span>
              <span className={currentRegime.color}>{currentRegime.label}</span>
            </h3>
          </div>
        </div>

        {/* Risk Level Badge */}
        <div className="text-right">
          <p className="text-xs text-muted mb-1">Risk Level</p>
          <div className={clsx(
            'inline-flex items-center gap-2 px-3 py-1.5 rounded-full',
            riskLevel === 'LOW' && 'bg-success/20',
            riskLevel === 'NORMAL' && 'bg-warning/20',
            riskLevel === 'HIGH' && 'bg-warning/30',
            riskLevel === 'EXTREME' && 'bg-error/20'
          )}>
            <span>{currentRisk.emoji}</span>
            <span className={clsx('font-semibold text-sm', currentRisk.color)}>
              {riskLevel}
            </span>
          </div>
        </div>
      </div>

      {/* Market Data Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        {/* BTC Change */}
        <div className="p-4 bg-surface rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">BTC 24h</span>
            {btcChange >= 0 ? (
              <TrendingUp className="w-4 h-4 text-success" />
            ) : (
              <TrendingDown className="w-4 h-4 text-error" />
            )}
          </div>
          <p className={clsx(
            'text-2xl font-bold',
            btcChange >= 0 ? 'text-success' : 'text-error'
          )}>
            {btcChange >= 0 ? '+' : ''}{btcChange.toFixed(2)}%
          </p>
        </div>

        {/* SOL Change */}
        <div className="p-4 bg-surface rounded-lg">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">SOL 24h</span>
            {solChange >= 0 ? (
              <TrendingUp className="w-4 h-4 text-success" />
            ) : (
              <TrendingDown className="w-4 h-4 text-error" />
            )}
          </div>
          <p className={clsx(
            'text-2xl font-bold',
            solChange >= 0 ? 'text-success' : 'text-error'
          )}>
            {solChange >= 0 ? '+' : ''}{solChange.toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Risk Description */}
      <div className="p-3 bg-surface rounded-lg border border-border">
        <div className="flex items-start gap-2">
          <div className={currentRisk.color}>
            {currentRisk.icon}
          </div>
          <div className="flex-1">
            <p className="text-sm text-muted mb-1">
              <strong className={currentRisk.color}>{riskLevel} Risk:</strong>
            </p>
            <p className="text-sm text-muted">
              {currentRisk.description}
            </p>
          </div>
        </div>
      </div>

      {/* Powered By */}
      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-muted text-center">
          🤖 Powered by Grok AI + Multi-Source Analysis
        </p>
      </div>
    </GlassCard>
  );
};
