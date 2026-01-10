"""
Dynamic APY System
Prompt #41: APY that adjusts based on TVL
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class APYConfig:
    """Configuration for dynamic APY"""
    base_apy_bps: int = 5000  # 50% base APY
    min_apy_bps: int = 500    # 5% floor
    max_apy_bps: int = 10000  # 100% ceiling
    target_tvl: Decimal = Decimal("1000000")  # $1M target
    adjustment_speed: float = 0.5  # How quickly APY adjusts


@dataclass
class APYSnapshot:
    """Point-in-time APY snapshot"""
    timestamp: datetime
    tvl: Decimal
    apy_bps: int
    stakers: int
    reward_rate: Decimal


# =============================================================================
# DYNAMIC APY CALCULATOR
# =============================================================================

class DynamicAPYCalculator:
    """Calculates dynamic APY based on TVL"""

    def __init__(self, config: Optional[APYConfig] = None):
        self.config = config or APYConfig()
        self.history: List[APYSnapshot] = []

    def calculate_apy(self, current_tvl: Decimal) -> int:
        """
        Calculate APY based on current TVL.

        Formula: APY = base_apy * (1 / sqrt(tvl / target_tvl))

        - Lower TVL → Higher APY (attract stakers)
        - Higher TVL → Lower APY (sustainable)
        """
        if current_tvl <= 0:
            return self.config.max_apy_bps

        if self.config.target_tvl <= 0:
            return self.config.base_apy_bps

        # Calculate ratio
        ratio = float(current_tvl / self.config.target_tvl)

        # Apply inverse sqrt formula
        if ratio > 0:
            multiplier = 1 / math.sqrt(ratio)
        else:
            multiplier = 1

        # Adjust with speed parameter for smoothing
        multiplier = 1 + (multiplier - 1) * self.config.adjustment_speed

        # Calculate APY
        dynamic_apy = int(self.config.base_apy_bps * multiplier)

        # Clamp to min/max
        return max(self.config.min_apy_bps,
                   min(self.config.max_apy_bps, dynamic_apy))

    def calculate_reward_rate(
        self,
        apy_bps: int,
        total_staked: Decimal,
        token_price: Decimal
    ) -> Decimal:
        """
        Convert APY to reward rate (SOL per second per staked token).

        Args:
            apy_bps: APY in basis points
            total_staked: Total tokens staked
            token_price: Token price in USD

        Returns:
            Reward rate (SOL lamports per second per token)
        """
        if total_staked <= 0 or token_price <= 0:
            return Decimal("0")

        # Convert APY to decimal
        apy = Decimal(apy_bps) / Decimal(10000)

        # Annual reward per token in USD
        annual_reward_usd = token_price * apy

        # Convert to SOL (assuming SOL price)
        sol_price = Decimal("100")  # Would fetch from price feed
        annual_reward_sol = annual_reward_usd / sol_price

        # Convert to per-second rate
        seconds_per_year = Decimal(365 * 24 * 60 * 60)
        rate_per_second = annual_reward_sol / seconds_per_year

        # Convert to lamports (1e9)
        return rate_per_second * Decimal(1e9)

    def snapshot(
        self,
        tvl: Decimal,
        stakers: int,
        reward_rate: Decimal
    ) -> APYSnapshot:
        """Record a snapshot of current APY"""
        apy = self.calculate_apy(tvl)
        snapshot = APYSnapshot(
            timestamp=datetime.utcnow(),
            tvl=tvl,
            apy_bps=apy,
            stakers=stakers,
            reward_rate=reward_rate
        )
        self.history.append(snapshot)

        # Keep last 1000 snapshots
        if len(self.history) > 1000:
            self.history = self.history[-1000:]

        return snapshot

    def get_projected_apy(
        self,
        additional_stake: Decimal,
        current_tvl: Decimal
    ) -> Dict[str, Any]:
        """Calculate how APY would change with additional stake"""
        current_apy = self.calculate_apy(current_tvl)
        new_tvl = current_tvl + additional_stake
        new_apy = self.calculate_apy(new_tvl)

        return {
            "current_tvl": float(current_tvl),
            "current_apy_bps": current_apy,
            "current_apy_pct": current_apy / 100,
            "new_tvl": float(new_tvl),
            "new_apy_bps": new_apy,
            "new_apy_pct": new_apy / 100,
            "apy_change_bps": new_apy - current_apy
        }

    def estimate_earnings(
        self,
        stake_amount: Decimal,
        stake_duration_days: int,
        current_tvl: Decimal,
        token_price: Decimal
    ) -> Dict[str, Any]:
        """Estimate earnings for a stake"""
        apy = self.calculate_apy(current_tvl)
        apy_decimal = Decimal(apy) / Decimal(10000)

        # Calculate earnings
        stake_value = stake_amount * token_price
        annual_earnings = stake_value * apy_decimal
        daily_earnings = annual_earnings / 365
        period_earnings = daily_earnings * stake_duration_days

        return {
            "stake_amount": float(stake_amount),
            "stake_value_usd": float(stake_value),
            "apy_bps": apy,
            "apy_pct": float(apy_decimal * 100),
            "daily_earnings_usd": float(daily_earnings),
            "period_earnings_usd": float(period_earnings),
            "annual_earnings_usd": float(annual_earnings),
            "note": "Estimates based on current APY which may change with TVL"
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_apy_endpoints(calculator: DynamicAPYCalculator):
    """Create API endpoints for APY system"""
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/apy", tags=["Dynamic APY"])

    @router.get("/current")
    async def get_current_apy(tvl: float):
        """Get current APY for given TVL"""
        apy = calculator.calculate_apy(Decimal(str(tvl)))
        return {
            "tvl": tvl,
            "apy_bps": apy,
            "apy_pct": apy / 100,
            "config": {
                "base_apy_pct": calculator.config.base_apy_bps / 100,
                "min_apy_pct": calculator.config.min_apy_bps / 100,
                "max_apy_pct": calculator.config.max_apy_bps / 100,
                "target_tvl": float(calculator.config.target_tvl)
            }
        }

    @router.get("/history")
    async def get_apy_history(limit: int = 100):
        """Get APY history"""
        return [
            {
                "timestamp": s.timestamp.isoformat(),
                "tvl": float(s.tvl),
                "apy_bps": s.apy_bps,
                "apy_pct": s.apy_bps / 100,
                "stakers": s.stakers
            }
            for s in calculator.history[-limit:]
        ]

    @router.post("/project")
    async def project_apy(additional_stake: float, current_tvl: float):
        """Project APY change with additional stake"""
        return calculator.get_projected_apy(
            Decimal(str(additional_stake)),
            Decimal(str(current_tvl))
        )

    @router.post("/estimate")
    async def estimate_earnings(
        stake_amount: float,
        duration_days: int,
        current_tvl: float,
        token_price: float
    ):
        """Estimate earnings for a stake"""
        return calculator.estimate_earnings(
            Decimal(str(stake_amount)),
            duration_days,
            Decimal(str(current_tvl)),
            Decimal(str(token_price))
        )

    @router.get("/chart")
    async def get_apy_curve():
        """Get APY curve for visualization"""
        points = []
        for tvl_multiplier in [0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 10]:
            tvl = calculator.config.target_tvl * Decimal(str(tvl_multiplier))
            apy = calculator.calculate_apy(tvl)
            points.append({
                "tvl": float(tvl),
                "tvl_multiplier": tvl_multiplier,
                "apy_bps": apy,
                "apy_pct": apy / 100
            })
        return {
            "target_tvl": float(calculator.config.target_tvl),
            "curve": points
        }

    return router


# =============================================================================
# FRONTEND COMPONENT (React)
# =============================================================================

APY_DISPLAY_COMPONENT = '''
// APYDisplay.jsx - Dynamic APY visualization
import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export function APYDisplay({ currentTVL }) {
  const [apyData, setApyData] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    // Fetch current APY
    fetch(`/api/apy/current?tvl=${currentTVL}`)
      .then(res => res.json())
      .then(setApyData);

    // Fetch history
    fetch('/api/apy/history?limit=30')
      .then(res => res.json())
      .then(setHistory);
  }, [currentTVL]);

  if (!apyData) return <div>Loading...</div>;

  return (
    <div className="apy-display">
      <div className="current-apy">
        <h3>Current APY</h3>
        <div className="apy-value">{apyData.apy_pct.toFixed(2)}%</div>
        <div className="tvl">TVL: ${(currentTVL / 1e6).toFixed(2)}M</div>
      </div>

      <div className="apy-info">
        <p>APY adjusts dynamically based on total staked:</p>
        <ul>
          <li>Lower TVL = Higher APY (attracts stakers)</li>
          <li>Higher TVL = Lower APY (sustainable)</li>
        </ul>
        <div className="range">
          Floor: {apyData.config.min_apy_pct}% |
          Ceiling: {apyData.config.max_apy_pct}%
        </div>
      </div>

      <div className="apy-chart">
        <h4>APY History (30 days)</h4>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={history}>
            <XAxis dataKey="timestamp" />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="apy_pct"
              stroke="#8884d8"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
'''
