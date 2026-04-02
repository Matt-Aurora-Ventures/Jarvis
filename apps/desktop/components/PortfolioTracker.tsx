/**
 * Portfolio Tracker
 * Prompt #48: Comprehensive portfolio tracking with P&L and analytics
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  PieChart,
  BarChart3,
  History,
  RefreshCw,
  ExternalLink,
  ArrowUpRight,
  ArrowDownRight,
  Coins,
  Lock,
  Flame
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface TokenHolding {
  mint: string;
  symbol: string;
  name: string;
  balance: number;
  decimals: number;
  priceUsd: number;
  valueUsd: number;
  change24h: number;
  costBasis: number;
  unrealizedPnl: number;
  unrealizedPnlPercent: number;
  logo?: string;
}

interface StakedPosition {
  poolId: string;
  poolName: string;
  stakedAmount: number;
  stakedValueUsd: number;
  pendingRewards: number;
  pendingRewardsUsd: number;
  apy: number;
  lockEndDate?: Date;
  multiplier: number;
}

interface LPPosition {
  poolAddress: string;
  poolName: string;
  lpTokens: number;
  token0: { symbol: string; amount: number; valueUsd: number };
  token1: { symbol: string; amount: number; valueUsd: number };
  totalValueUsd: number;
  impermanentLoss: number;
  feesEarned: number;
}

interface Transaction {
  signature: string;
  type: 'swap' | 'stake' | 'unstake' | 'transfer' | 'claim';
  timestamp: Date;
  tokens: {
    in?: { symbol: string; amount: number; valueUsd: number };
    out?: { symbol: string; amount: number; valueUsd: number };
  };
  fee: number;
  status: 'confirmed' | 'failed';
}

interface PortfolioData {
  wallet: string;
  totalValueUsd: number;
  totalCostBasis: number;
  totalPnl: number;
  totalPnlPercent: number;
  change24h: number;
  change24hPercent: number;
  holdings: TokenHolding[];
  stakedPositions: StakedPosition[];
  lpPositions: LPPosition[];
  recentTransactions: Transaction[];
  historicalValues: { date: string; value: number }[];
}

interface TimeRange {
  label: string;
  value: string;
  days: number;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const TIME_RANGES: TimeRange[] = [
  { label: '24H', value: '1d', days: 1 },
  { label: '7D', value: '7d', days: 7 },
  { label: '30D', value: '30d', days: 30 },
  { label: '90D', value: '90d', days: 90 },
  { label: '1Y', value: '1y', days: 365 },
  { label: 'All', value: 'all', days: 9999 }
];

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

const formatCurrency = (value: number): string => {
  if (Math.abs(value) >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `$${(value / 1_000).toFixed(2)}K`;
  }
  return `$${value.toFixed(2)}`;
};

const formatPercent = (value: number): string => {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
};

const formatTokenAmount = (amount: number, decimals: number): string => {
  const value = amount / Math.pow(10, decimals);
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
  return value.toFixed(value < 1 ? 6 : 2);
};

// =============================================================================
// MAIN COMPONENT
// =============================================================================

export function PortfolioTracker({ wallet }: { wallet: string }) {
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<string>('30d');
  const [activeTab, setActiveTab] = useState('overview');

  // Fetch portfolio data
  useEffect(() => {
    const fetchPortfolio = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/portfolio/${wallet}?range=${timeRange}`);
        const data = await response.json();
        setPortfolio(data);
      } catch (error) {
        console.error('Failed to fetch portfolio:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [wallet, timeRange]);

  // Calculate totals
  const totals = useMemo(() => {
    if (!portfolio) return null;

    const stakingValue = portfolio.stakedPositions.reduce(
      (sum, p) => sum + p.stakedValueUsd + p.pendingRewardsUsd, 0
    );
    const lpValue = portfolio.lpPositions.reduce(
      (sum, p) => sum + p.totalValueUsd, 0
    );
    const holdingsValue = portfolio.holdings.reduce(
      (sum, h) => sum + h.valueUsd, 0
    );

    return {
      total: portfolio.totalValueUsd,
      holdings: holdingsValue,
      staking: stakingValue,
      lp: lpValue,
      pendingRewards: portfolio.stakedPositions.reduce(
        (sum, p) => sum + p.pendingRewardsUsd, 0
      )
    };
  }, [portfolio]);

  // Asset allocation for pie chart
  const allocation = useMemo(() => {
    if (!portfolio || !totals) return [];

    return portfolio.holdings
      .filter(h => h.valueUsd > 0)
      .map(h => ({
        name: h.symbol,
        value: h.valueUsd,
        percent: (h.valueUsd / totals.total) * 100
      }))
      .sort((a, b) => b.value - a.value);
  }, [portfolio, totals]);

  if (loading || !portfolio || !totals) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Portfolio</h1>
          <p className="text-muted-foreground flex items-center gap-2">
            <Wallet className="h-4 w-4" />
            {wallet.slice(0, 4)}...{wallet.slice(-4)}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <Select value={timeRange} onValueChange={setTimeRange}>
            <SelectTrigger className="w-24">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIME_RANGES.map(range => (
                <SelectItem key={range.value} value={range.value}>
                  {range.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Portfolio Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Value */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Portfolio Value</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {formatCurrency(portfolio.totalValueUsd)}
            </div>
            <div className={`flex items-center gap-1 text-sm mt-1 ${
              portfolio.change24hPercent >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {portfolio.change24hPercent >= 0 ? (
                <ArrowUpRight className="h-4 w-4" />
              ) : (
                <ArrowDownRight className="h-4 w-4" />
              )}
              {formatPercent(portfolio.change24hPercent)} (24h)
            </div>
          </CardContent>
        </Card>

        {/* Total P&L */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Unrealized P&L</CardDescription>
          </CardHeader>
          <CardContent>
            <div className={`text-3xl font-bold ${
              portfolio.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {portfolio.totalPnl >= 0 ? '+' : ''}{formatCurrency(portfolio.totalPnl)}
            </div>
            <div className={`text-sm mt-1 ${
              portfolio.totalPnlPercent >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {formatPercent(portfolio.totalPnlPercent)}
            </div>
          </CardContent>
        </Card>

        {/* Staking Value */}
        <Card>
          <CardHeader className="pb-2">
            <CardDescription className="flex items-center gap-1">
              <Lock className="h-3 w-3" />
              Staked Value
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {formatCurrency(totals.staking)}
            </div>
            <div className="text-sm text-muted-foreground mt-1">
              +{formatCurrency(totals.pendingRewards)} pending
            </div>
          </CardContent>
        </Card>

        {/* Pending Rewards */}
        <Card className="border-green-200 bg-green-50">
          <CardHeader className="pb-2">
            <CardDescription className="text-green-700 flex items-center gap-1">
              <Coins className="h-3 w-3" />
              Pending Rewards
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-green-700">
              {formatCurrency(totals.pendingRewards)}
            </div>
            <Button size="sm" className="mt-2">
              Claim All
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="holdings">Holdings</TabsTrigger>
          <TabsTrigger value="staking">Staking</TabsTrigger>
          <TabsTrigger value="lp">LP Positions</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6 mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Portfolio Chart */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" />
                  Portfolio Value
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-64 flex items-center justify-center text-muted-foreground">
                  {/* Chart would go here - using recharts or similar */}
                  <p>Portfolio value chart</p>
                </div>
              </CardContent>
            </Card>

            {/* Asset Allocation */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PieChart className="h-5 w-5" />
                  Asset Allocation
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {allocation.slice(0, 5).map((asset, i) => (
                    <div key={asset.name} className="flex items-center gap-3">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{
                          backgroundColor: `hsl(${i * 60}, 70%, 50%)`
                        }}
                      />
                      <div className="flex-1">
                        <div className="flex justify-between">
                          <span className="font-medium">{asset.name}</span>
                          <span>{formatCurrency(asset.value)}</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2 mt-1">
                          <div
                            className="h-2 rounded-full"
                            style={{
                              width: `${asset.percent}%`,
                              backgroundColor: `hsl(${i * 60}, 70%, 50%)`
                            }}
                          />
                        </div>
                      </div>
                      <span className="text-sm text-muted-foreground w-16 text-right">
                        {asset.percent.toFixed(1)}%
                      </span>
                    </div>
                  ))}
                  {allocation.length > 5 && (
                    <p className="text-sm text-muted-foreground">
                      +{allocation.length - 5} more assets
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Top Performers */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Top Performers (24h)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {portfolio.holdings
                  .filter(h => h.valueUsd > 10)
                  .sort((a, b) => b.change24h - a.change24h)
                  .slice(0, 3)
                  .map(token => (
                    <div
                      key={token.mint}
                      className="flex items-center justify-between p-3 bg-muted rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
                          {token.logo ? (
                            <img src={token.logo} alt={token.symbol} className="w-6 h-6 rounded-full" />
                          ) : (
                            <Coins className="h-5 w-5" />
                          )}
                        </div>
                        <div>
                          <p className="font-medium">{token.symbol}</p>
                          <p className="text-sm text-muted-foreground">
                            {formatCurrency(token.valueUsd)}
                          </p>
                        </div>
                      </div>
                      <Badge variant={token.change24h >= 0 ? 'default' : 'destructive'}>
                        {formatPercent(token.change24h)}
                      </Badge>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Holdings Tab */}
        <TabsContent value="holdings" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Token Holdings</CardTitle>
              <CardDescription>All tokens in your wallet</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-2">Token</th>
                      <th className="text-right py-3 px-2">Balance</th>
                      <th className="text-right py-3 px-2">Price</th>
                      <th className="text-right py-3 px-2">Value</th>
                      <th className="text-right py-3 px-2">24h</th>
                      <th className="text-right py-3 px-2">P&L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {portfolio.holdings.map(token => (
                      <tr key={token.mint} className="border-b hover:bg-muted/50">
                        <td className="py-3 px-2">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-primary/10 rounded-full flex items-center justify-center">
                              {token.logo ? (
                                <img src={token.logo} alt={token.symbol} className="w-5 h-5 rounded-full" />
                              ) : (
                                <Coins className="h-4 w-4" />
                              )}
                            </div>
                            <div>
                              <p className="font-medium">{token.symbol}</p>
                              <p className="text-xs text-muted-foreground">{token.name}</p>
                            </div>
                          </div>
                        </td>
                        <td className="text-right py-3 px-2">
                          {formatTokenAmount(token.balance, token.decimals)}
                        </td>
                        <td className="text-right py-3 px-2">
                          ${token.priceUsd < 0.01 ? token.priceUsd.toFixed(6) : token.priceUsd.toFixed(2)}
                        </td>
                        <td className="text-right py-3 px-2 font-medium">
                          {formatCurrency(token.valueUsd)}
                        </td>
                        <td className={`text-right py-3 px-2 ${
                          token.change24h >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {formatPercent(token.change24h)}
                        </td>
                        <td className={`text-right py-3 px-2 ${
                          token.unrealizedPnl >= 0 ? 'text-green-600' : 'text-red-600'
                        }`}>
                          <div>{formatCurrency(token.unrealizedPnl)}</div>
                          <div className="text-xs">
                            {formatPercent(token.unrealizedPnlPercent)}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Staking Tab */}
        <TabsContent value="staking" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Lock className="h-5 w-5" />
                Staking Positions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {portfolio.stakedPositions.map(position => (
                  <div
                    key={position.poolId}
                    className="p-4 border rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-semibold">{position.poolName}</h3>
                        <p className="text-sm text-muted-foreground">
                          {position.multiplier}x multiplier
                        </p>
                      </div>
                      <Badge variant="outline" className="text-green-600 border-green-600">
                        {position.apy.toFixed(1)}% APY
                      </Badge>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">Staked</p>
                        <p className="font-medium">
                          {formatTokenAmount(position.stakedAmount, 9)} KR8TIV
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {formatCurrency(position.stakedValueUsd)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Pending Rewards</p>
                        <p className="font-medium text-green-600">
                          {formatTokenAmount(position.pendingRewards, 9)} KR8TIV
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {formatCurrency(position.pendingRewardsUsd)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Lock Ends</p>
                        <p className="font-medium">
                          {position.lockEndDate
                            ? position.lockEndDate.toLocaleDateString()
                            : 'Flexible'
                          }
                        </p>
                      </div>
                      <div className="flex items-end justify-end gap-2">
                        <Button size="sm" variant="outline">Claim</Button>
                        <Button size="sm" variant="outline">Unstake</Button>
                      </div>
                    </div>
                  </div>
                ))}

                {portfolio.stakedPositions.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <Lock className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>No staking positions</p>
                    <Button className="mt-4">Stake Now</Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* LP Positions Tab */}
        <TabsContent value="lp" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Liquidity Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {portfolio.lpPositions.map(position => (
                  <div
                    key={position.poolAddress}
                    className="p-4 border rounded-lg"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-semibold">{position.poolName}</h3>
                      <span className="font-medium">
                        {formatCurrency(position.totalValueUsd)}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <div>
                        <p className="text-sm text-muted-foreground">
                          {position.token0.symbol}
                        </p>
                        <p className="font-medium">
                          {position.token0.amount.toFixed(4)}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {formatCurrency(position.token0.valueUsd)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">
                          {position.token1.symbol}
                        </p>
                        <p className="font-medium">
                          {position.token1.amount.toFixed(4)}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {formatCurrency(position.token1.valueUsd)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">Fees Earned</p>
                        <p className="font-medium text-green-600">
                          {formatCurrency(position.feesEarned)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-muted-foreground">IL</p>
                        <p className={`font-medium ${
                          position.impermanentLoss < 0 ? 'text-red-600' : 'text-green-600'
                        }`}>
                          {formatPercent(position.impermanentLoss)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}

                {portfolio.lpPositions.length === 0 && (
                  <div className="text-center py-8 text-muted-foreground">
                    <p>No liquidity positions</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5" />
                Transaction History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {portfolio.recentTransactions.map(tx => (
                  <div
                    key={tx.signature}
                    className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        tx.type === 'swap' ? 'bg-blue-100' :
                        tx.type === 'stake' ? 'bg-purple-100' :
                        tx.type === 'claim' ? 'bg-green-100' :
                        'bg-gray-100'
                      }`}>
                        {tx.type === 'swap' && <ArrowUpRight className="h-5 w-5 text-blue-600" />}
                        {tx.type === 'stake' && <Lock className="h-5 w-5 text-purple-600" />}
                        {tx.type === 'unstake' && <Lock className="h-5 w-5 text-purple-600" />}
                        {tx.type === 'claim' && <Coins className="h-5 w-5 text-green-600" />}
                        {tx.type === 'transfer' && <ArrowUpRight className="h-5 w-5 text-gray-600" />}
                      </div>
                      <div>
                        <p className="font-medium capitalize">{tx.type}</p>
                        <p className="text-sm text-muted-foreground">
                          {tx.timestamp.toLocaleString()}
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      {tx.tokens.out && (
                        <p className="text-red-600">
                          -{tx.tokens.out.amount.toFixed(4)} {tx.tokens.out.symbol}
                        </p>
                      )}
                      {tx.tokens.in && (
                        <p className="text-green-600">
                          +{tx.tokens.in.amount.toFixed(4)} {tx.tokens.in.symbol}
                        </p>
                      )}
                    </div>

                    <a
                      href={`https://solscan.io/tx/${tx.signature}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-primary"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// =============================================================================
// API IMPLEMENTATION
// =============================================================================

export const PORTFOLIO_API = `
"""
Portfolio Tracker API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import aiohttp

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])


class TokenHolding(BaseModel):
    mint: str
    symbol: str
    name: str
    balance: int
    decimals: int
    priceUsd: float
    valueUsd: float
    change24h: float
    costBasis: float
    unrealizedPnl: float
    unrealizedPnlPercent: float
    logo: Optional[str] = None


class StakedPosition(BaseModel):
    poolId: str
    poolName: str
    stakedAmount: int
    stakedValueUsd: float
    pendingRewards: int
    pendingRewardsUsd: float
    apy: float
    lockEndDate: Optional[str] = None
    multiplier: float


@router.get("/{wallet}")
async def get_portfolio(wallet: str, range: str = "30d"):
    """Get complete portfolio data for a wallet"""

    # Fetch token accounts
    holdings = await fetch_token_holdings(wallet)

    # Fetch staking positions
    staked = await fetch_staking_positions(wallet)

    # Fetch LP positions
    lp_positions = await fetch_lp_positions(wallet)

    # Fetch transaction history
    transactions = await fetch_transactions(wallet)

    # Calculate totals
    total_value = sum(h.valueUsd for h in holdings)
    total_value += sum(s.stakedValueUsd + s.pendingRewardsUsd for s in staked)

    total_cost_basis = sum(h.costBasis for h in holdings)
    total_pnl = sum(h.unrealizedPnl for h in holdings)

    return {
        "wallet": wallet,
        "totalValueUsd": total_value,
        "totalCostBasis": total_cost_basis,
        "totalPnl": total_pnl,
        "totalPnlPercent": (total_pnl / total_cost_basis * 100) if total_cost_basis else 0,
        "change24h": 0,
        "change24hPercent": 0,
        "holdings": holdings,
        "stakedPositions": staked,
        "lpPositions": lp_positions,
        "recentTransactions": transactions,
        "historicalValues": []
    }


async def fetch_token_holdings(wallet: str) -> List[TokenHolding]:
    """Fetch all token holdings for a wallet"""
    # Would use Helius/Shyft/Solana RPC
    return []


async def fetch_staking_positions(wallet: str) -> List[StakedPosition]:
    """Fetch staking positions"""
    # Would query staking program
    return []


async def fetch_lp_positions(wallet: str) -> List[dict]:
    """Fetch LP positions"""
    # Would query Raydium/Orca/Meteora
    return []


async def fetch_transactions(wallet: str) -> List[dict]:
    """Fetch recent transactions"""
    # Would use Helius/Shyft for parsed transactions
    return []
`;
