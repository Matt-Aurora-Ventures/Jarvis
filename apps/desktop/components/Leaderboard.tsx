/**
 * Leaderboard Component
 * Prompt #50: Gamified leaderboard for staking, trading, and referrals
 */

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Progress } from '@/components/ui/progress';
import {
  Trophy,
  Medal,
  Crown,
  TrendingUp,
  Lock,
  Users,
  Flame,
  Star,
  ChevronUp,
  ChevronDown,
  Minus,
  Award,
  Target,
  Zap
} from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

interface LeaderboardEntry {
  rank: number;
  previousRank: number;
  wallet: string;
  displayName?: string;
  avatar?: string;
  score: number;
  change24h: number;
  badges: string[];
  tier: 'bronze' | 'silver' | 'gold' | 'platinum' | 'diamond';
  stats: {
    totalStaked?: number;
    tradingVolume?: number;
    referrals?: number;
    daysActive?: number;
    winRate?: number;
  };
}

interface LeaderboardData {
  category: string;
  period: string;
  entries: LeaderboardEntry[];
  userRank?: LeaderboardEntry;
  totalParticipants: number;
  lastUpdated: Date;
  rewards: {
    rank: number;
    reward: string;
    claimed?: boolean;
  }[];
}

interface LeaderboardCategory {
  id: string;
  name: string;
  icon: React.ElementType;
  description: string;
  metric: string;
}

// =============================================================================
// CONSTANTS
// =============================================================================

const CATEGORIES: LeaderboardCategory[] = [
  {
    id: 'staking',
    name: 'Top Stakers',
    icon: Lock,
    description: 'Highest staked amounts',
    metric: 'Total Staked'
  },
  {
    id: 'trading',
    name: 'Top Traders',
    icon: TrendingUp,
    description: 'Highest trading volume',
    metric: 'Volume'
  },
  {
    id: 'referrals',
    name: 'Top Referrers',
    icon: Users,
    description: 'Most successful referrals',
    metric: 'Referrals'
  },
  {
    id: 'rewards',
    name: 'Top Earners',
    icon: Award,
    description: 'Highest rewards earned',
    metric: 'Rewards'
  }
];

const TIME_PERIODS = [
  { id: 'daily', name: 'Today' },
  { id: 'weekly', name: 'This Week' },
  { id: 'monthly', name: 'This Month' },
  { id: 'alltime', name: 'All Time' }
];

const TIER_COLORS: Record<string, string> = {
  bronze: 'from-amber-600 to-amber-800',
  silver: 'from-gray-300 to-gray-500',
  gold: 'from-yellow-400 to-yellow-600',
  platinum: 'from-cyan-300 to-cyan-500',
  diamond: 'from-purple-400 to-blue-500'
};

const TIER_BADGES: Record<string, string> = {
  bronze: '🥉',
  silver: '🥈',
  gold: '🥇',
  platinum: '💎',
  diamond: '👑'
};

// =============================================================================
// HELPER COMPONENTS
// =============================================================================

function RankChange({ current, previous }: { current: number; previous: number }) {
  const diff = previous - current;

  if (diff === 0) {
    return <Minus className="h-4 w-4 text-muted-foreground" />;
  }

  if (diff > 0) {
    return (
      <div className="flex items-center text-green-600">
        <ChevronUp className="h-4 w-4" />
        <span className="text-xs">{diff}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center text-red-600">
      <ChevronDown className="h-4 w-4" />
      <span className="text-xs">{Math.abs(diff)}</span>
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) {
    return (
      <div className="w-10 h-10 bg-gradient-to-br from-yellow-400 to-yellow-600 rounded-full flex items-center justify-center">
        <Crown className="h-6 w-6 text-white" />
      </div>
    );
  }

  if (rank === 2) {
    return (
      <div className="w-10 h-10 bg-gradient-to-br from-gray-300 to-gray-400 rounded-full flex items-center justify-center">
        <Medal className="h-6 w-6 text-white" />
      </div>
    );
  }

  if (rank === 3) {
    return (
      <div className="w-10 h-10 bg-gradient-to-br from-amber-600 to-amber-700 rounded-full flex items-center justify-center">
        <Medal className="h-6 w-6 text-white" />
      </div>
    );
  }

  return (
    <div className="w-10 h-10 bg-muted rounded-full flex items-center justify-center">
      <span className="font-bold text-muted-foreground">{rank}</span>
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  return (
    <Badge
      className={`bg-gradient-to-r ${TIER_COLORS[tier]} text-white border-0`}
    >
      {TIER_BADGES[tier]} {tier.charAt(0).toUpperCase() + tier.slice(1)}
    </Badge>
  );
}

// =============================================================================
// MAIN COMPONENT
// =============================================================================

interface LeaderboardProps {
  wallet?: string;
}

export function Leaderboard({ wallet }: LeaderboardProps) {
  const [category, setCategory] = useState('staking');
  const [period, setPeriod] = useState('weekly');
  const [data, setData] = useState<LeaderboardData | null>(null);
  const [loading, setLoading] = useState(true);

  // Fetch leaderboard data
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const response = await fetch(
          `/api/leaderboard?category=${category}&period=${period}&wallet=${wallet || ''}`
        );
        const result = await response.json();
        setData(result);
      } catch (error) {
        console.error('Failed to fetch leaderboard:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [category, period, wallet]);

  const currentCategory = CATEGORIES.find(c => c.id === category)!;
  const CategoryIcon = currentCategory.icon;

  // Format score based on category
  const formatScore = (entry: LeaderboardEntry): string => {
    if (category === 'staking' || category === 'rewards') {
      const value = entry.score / 1e9;
      if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(2)}M`;
      if (value >= 1_000) return `${(value / 1_000).toFixed(2)}K`;
      return value.toFixed(2);
    }

    if (category === 'trading') {
      const value = entry.score / 1e9;
      return `$${value >= 1000 ? `${(value / 1000).toFixed(1)}K` : value.toFixed(0)}`;
    }

    return entry.score.toString();
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="h-6 w-6 text-yellow-500" />
            Leaderboard
          </h1>
          <p className="text-muted-foreground">
            Compete with other traders and earn exclusive rewards
          </p>
        </div>

        <div className="flex gap-3">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TIME_PERIODS.map(p => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Category Tabs */}
      <Tabs value={category} onValueChange={setCategory}>
        <TabsList className="grid grid-cols-4 w-full max-w-2xl">
          {CATEGORIES.map(cat => {
            const Icon = cat.icon;
            return (
              <TabsTrigger key={cat.id} value={cat.id} className="flex items-center gap-2">
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{cat.name}</span>
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent value={category} className="mt-6">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Main Leaderboard */}
            <div className="lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <CategoryIcon className="h-5 w-5" />
                    {currentCategory.name}
                  </CardTitle>
                  <CardDescription>{currentCategory.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="space-y-4">
                      {[...Array(10)].map((_, i) => (
                        <div key={i} className="h-16 bg-muted animate-pulse rounded-lg" />
                      ))}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Top 3 Podium */}
                      <div className="grid grid-cols-3 gap-4 mb-8">
                        {data?.entries.slice(0, 3).map((entry, i) => {
                          const positions = [1, 0, 2];
                          const actualEntry = data.entries[positions[i]];
                          const heights = ['h-32', 'h-40', 'h-28'];

                          return (
                            <div
                              key={actualEntry.wallet}
                              className={`flex flex-col items-center justify-end ${
                                i === 1 ? 'order-1' : i === 0 ? 'order-0' : 'order-2'
                              }`}
                            >
                              <Avatar className="w-16 h-16 mb-2 border-4 border-background shadow-lg">
                                <AvatarImage src={actualEntry.avatar} />
                                <AvatarFallback>
                                  {actualEntry.displayName?.[0] || actualEntry.wallet[0]}
                                </AvatarFallback>
                              </Avatar>
                              <p className="font-medium text-sm truncate max-w-full">
                                {actualEntry.displayName || `${actualEntry.wallet.slice(0, 4)}...`}
                              </p>
                              <p className="text-lg font-bold">
                                {formatScore(actualEntry)}
                              </p>
                              <div
                                className={`w-full ${heights[i]} bg-gradient-to-t ${
                                  i === 1 ? 'from-yellow-500/20 to-yellow-500/5' :
                                  i === 0 ? 'from-gray-400/20 to-gray-400/5' :
                                  'from-amber-600/20 to-amber-600/5'
                                } rounded-t-lg flex items-start justify-center pt-2`}
                              >
                                <span className="text-2xl">
                                  {i === 1 ? '🥇' : i === 0 ? '🥈' : '🥉'}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Rest of Leaderboard */}
                      {data?.entries.slice(3).map((entry) => (
                        <div
                          key={entry.wallet}
                          className={`flex items-center gap-4 p-4 rounded-lg border ${
                            entry.wallet === wallet ? 'bg-primary/5 border-primary' : ''
                          }`}
                        >
                          <RankBadge rank={entry.rank} />

                          <div className="w-6">
                            <RankChange current={entry.rank} previous={entry.previousRank} />
                          </div>

                          <Avatar className="h-10 w-10">
                            <AvatarImage src={entry.avatar} />
                            <AvatarFallback>
                              {entry.displayName?.[0] || entry.wallet[0]}
                            </AvatarFallback>
                          </Avatar>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <p className="font-medium truncate">
                                {entry.displayName || `${entry.wallet.slice(0, 6)}...${entry.wallet.slice(-4)}`}
                              </p>
                              <TierBadge tier={entry.tier} />
                            </div>
                            <div className="flex gap-1 mt-1">
                              {entry.badges.slice(0, 3).map((badge, i) => (
                                <span key={i} className="text-xs">{badge}</span>
                              ))}
                            </div>
                          </div>

                          <div className="text-right">
                            <p className="font-bold">{formatScore(entry)}</p>
                            <p className={`text-xs ${
                              entry.change24h >= 0 ? 'text-green-600' : 'text-red-600'
                            }`}>
                              {entry.change24h >= 0 ? '+' : ''}{entry.change24h.toFixed(1)}%
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* User's Rank Card */}
              {data?.userRank && (
                <Card className="mt-4 border-primary">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      <RankBadge rank={data.userRank.rank} />
                      <div className="flex-1">
                        <p className="font-medium">Your Position</p>
                        <p className="text-sm text-muted-foreground">
                          Top {((data.userRank.rank / data.totalParticipants) * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold">{formatScore(data.userRank)}</p>
                        <Progress
                          value={(data.userRank.rank / data.totalParticipants) * 100}
                          className="w-24 mt-1"
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Current Rewards */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Award className="h-5 w-5 text-yellow-500" />
                    {period === 'weekly' ? 'Weekly' : period === 'monthly' ? 'Monthly' : ''} Rewards
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {data?.rewards.map((reward, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-3 bg-muted rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-lg">
                            {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${reward.rank}`}
                          </span>
                          <span className="text-sm text-muted-foreground">
                            Rank {reward.rank}
                          </span>
                        </div>
                        <span className="font-bold text-green-600">{reward.reward}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* Stats */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Flame className="h-5 w-5 text-orange-500" />
                    Competition Stats
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Participants</span>
                      <span className="font-medium">
                        {data?.totalParticipants.toLocaleString()}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Last Updated</span>
                      <span className="font-medium">
                        {data?.lastUpdated ? new Date(data.lastUpdated).toLocaleTimeString() : '-'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Period Ends</span>
                      <span className="font-medium">
                        {period === 'daily' ? 'Tomorrow' :
                         period === 'weekly' ? 'Sunday' :
                         period === 'monthly' ? 'End of Month' : 'Never'}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Achievement Badges */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Star className="h-5 w-5 text-purple-500" />
                    Badges
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-4 gap-2">
                    {['🔥', '⚡', '💎', '🏆', '🚀', '🎯', '👑', '⭐'].map((badge, i) => (
                      <div
                        key={i}
                        className="aspect-square bg-muted rounded-lg flex items-center justify-center text-2xl"
                      >
                        {badge}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-3 text-center">
                    Earn badges by completing achievements
                  </p>
                </CardContent>
              </Card>

              {/* How It Works */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    How It Works
                  </CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground space-y-2">
                  <p>1. Stake, trade, or refer to earn points</p>
                  <p>2. Climb the leaderboard rankings</p>
                  <p>3. Top performers win exclusive rewards</p>
                  <p>4. Rankings reset each period</p>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// =============================================================================
// API IMPLEMENTATION
// =============================================================================

export const LEADERBOARD_API = `
"""
Leaderboard API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import redis.asyncio as redis

router = APIRouter(prefix="/api/leaderboard", tags=["Leaderboard"])


class LeaderboardEntry(BaseModel):
    rank: int
    previousRank: int
    wallet: str
    displayName: Optional[str] = None
    avatar: Optional[str] = None
    score: int
    change24h: float
    badges: List[str]
    tier: str
    stats: Dict[str, Any]


class LeaderboardResponse(BaseModel):
    category: str
    period: str
    entries: List[LeaderboardEntry]
    userRank: Optional[LeaderboardEntry] = None
    totalParticipants: int
    lastUpdated: str
    rewards: List[Dict[str, Any]]


@router.get("")
async def get_leaderboard(
    category: str = "staking",
    period: str = "weekly",
    wallet: Optional[str] = None,
    limit: int = 100
) -> LeaderboardResponse:
    """Get leaderboard data"""

    # Get scores from Redis sorted set
    redis_key = f"leaderboard:{category}:{period}"

    # In production, fetch from Redis
    entries = await fetch_leaderboard_entries(category, period, limit)

    # Find user's rank if wallet provided
    user_rank = None
    if wallet:
        user_rank = await get_user_rank(wallet, category, period)

    # Get rewards for this period
    rewards = get_period_rewards(period)

    return LeaderboardResponse(
        category=category,
        period=period,
        entries=entries,
        userRank=user_rank,
        totalParticipants=len(entries),
        lastUpdated=datetime.utcnow().isoformat(),
        rewards=rewards
    )


async def fetch_leaderboard_entries(
    category: str,
    period: str,
    limit: int
) -> List[LeaderboardEntry]:
    """Fetch leaderboard entries from database"""
    # Would fetch from Redis/PostgreSQL
    return []


async def get_user_rank(
    wallet: str,
    category: str,
    period: str
) -> Optional[LeaderboardEntry]:
    """Get user's rank in leaderboard"""
    # Would query Redis ZRANK
    return None


def get_period_rewards(period: str) -> List[Dict[str, Any]]:
    """Get rewards for leaderboard period"""
    if period == "weekly":
        return [
            {"rank": 1, "reward": "10,000 KR8TIV + NFT"},
            {"rank": 2, "reward": "5,000 KR8TIV"},
            {"rank": 3, "reward": "2,500 KR8TIV"},
            {"rank": 10, "reward": "500 KR8TIV"},
            {"rank": 50, "reward": "100 KR8TIV"}
        ]
    elif period == "monthly":
        return [
            {"rank": 1, "reward": "50,000 KR8TIV + NFT"},
            {"rank": 2, "reward": "25,000 KR8TIV"},
            {"rank": 3, "reward": "10,000 KR8TIV"},
            {"rank": 10, "reward": "2,500 KR8TIV"},
            {"rank": 100, "reward": "250 KR8TIV"}
        ]
    return []


# Background job to update leaderboard
async def update_leaderboard_scores():
    """Background job to recalculate leaderboard scores"""
    # 1. Fetch all staking positions
    # 2. Calculate scores based on:
    #    - Amount staked
    #    - Duration
    #    - Multiplier
    # 3. Update Redis sorted sets
    pass
`;

export default Leaderboard;
