"""
Treasury Transparency Dashboard.

Public API endpoints for complete treasury transparency:
- Real-time balances across all wallets
- Trading performance and P&L
- Distribution history
- Risk metrics
- Staking statistics

All data is public - full transparency to build trust.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.treasury.dashboard")


@dataclass
class TreasurySnapshot:
    """Point-in-time snapshot of treasury state."""
    timestamp: datetime
    total_balance_sol: float
    reserve_balance_sol: float
    active_balance_sol: float
    profit_buffer_sol: float
    total_staked_sol: float
    staker_count: int
    pending_rewards_sol: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_balance_sol": self.total_balance_sol,
            "reserve_balance_sol": self.reserve_balance_sol,
            "active_balance_sol": self.active_balance_sol,
            "profit_buffer_sol": self.profit_buffer_sol,
            "total_staked_sol": self.total_staked_sol,
            "staker_count": self.staker_count,
            "pending_rewards_sol": self.pending_rewards_sol,
        }


@dataclass
class TradingStats:
    """Trading performance statistics."""
    period: str  # "24h", "7d", "30d", "all"
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_volume_sol: float
    gross_profit_sol: float
    gross_loss_sol: float
    net_pnl_sol: float
    avg_trade_size_sol: float
    largest_win_sol: float
    largest_loss_sol: float
    partner_fees_earned_sol: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 4),
            "total_volume_sol": round(self.total_volume_sol, 4),
            "gross_profit_sol": round(self.gross_profit_sol, 4),
            "gross_loss_sol": round(self.gross_loss_sol, 4),
            "net_pnl_sol": round(self.net_pnl_sol, 4),
            "avg_trade_size_sol": round(self.avg_trade_size_sol, 4),
            "largest_win_sol": round(self.largest_win_sol, 4),
            "largest_loss_sol": round(self.largest_loss_sol, 4),
            "partner_fees_earned_sol": round(self.partner_fees_earned_sol, 4),
        }


@dataclass
class StakingStats:
    """Staking pool statistics."""
    total_staked_sol: float
    total_stakers: int
    avg_stake_sol: float
    median_stake_sol: float
    total_rewards_distributed_sol: float
    current_apy: float
    next_distribution_at: Optional[datetime]
    rewards_pool_balance_sol: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_staked_sol": round(self.total_staked_sol, 4),
            "total_stakers": self.total_stakers,
            "avg_stake_sol": round(self.avg_stake_sol, 4),
            "median_stake_sol": round(self.median_stake_sol, 4),
            "total_rewards_distributed_sol": round(self.total_rewards_distributed_sol, 4),
            "current_apy": round(self.current_apy, 4),
            "next_distribution_at": self.next_distribution_at.isoformat() if self.next_distribution_at else None,
            "rewards_pool_balance_sol": round(self.rewards_pool_balance_sol, 4),
        }


@dataclass
class DistributionRecord:
    """Record of a profit distribution."""
    id: str
    timestamp: datetime
    total_distributed_sol: float
    to_staking_sol: float
    to_operations_sol: float
    to_development_sol: float
    staker_count: int
    avg_per_staker_sol: float
    transaction_signatures: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "total_distributed_sol": round(self.total_distributed_sol, 4),
            "to_staking_sol": round(self.to_staking_sol, 4),
            "to_operations_sol": round(self.to_operations_sol, 4),
            "to_development_sol": round(self.to_development_sol, 4),
            "staker_count": self.staker_count,
            "avg_per_staker_sol": round(self.avg_per_staker_sol, 6),
            "transaction_signatures": self.transaction_signatures,
        }


class TransparencyDashboard:
    """
    Provides public transparency data for the treasury.

    All methods return public data - no authentication required.
    This builds trust with stakers and the community.
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(self, treasury_manager=None):
        """
        Initialize dashboard.

        Args:
            treasury_manager: TreasuryManager instance
        """
        self._treasury = treasury_manager
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 60  # Cache for 60 seconds

    def _ensure_treasury(self):
        """Ensure treasury manager is available."""
        if self._treasury is None:
            from core.treasury.manager import get_treasury
            self._treasury = get_treasury()

    def _to_sol(self, lamports: int) -> float:
        """Convert lamports to SOL."""
        return lamports / self.LAMPORTS_PER_SOL

    async def get_overview(self) -> Dict[str, Any]:
        """
        Get complete treasury overview.

        Returns all key metrics in one call.
        """
        self._ensure_treasury()

        snapshot = await self.get_snapshot()
        trading_24h = await self.get_trading_stats("24h")
        staking = await self.get_staking_stats()

        return {
            "snapshot": snapshot.to_dict(),
            "trading_24h": trading_24h.to_dict(),
            "staking": staking.to_dict(),
            "health": await self.get_health_status(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def get_snapshot(self) -> TreasurySnapshot:
        """Get current treasury snapshot."""
        self._ensure_treasury()

        await self._treasury.initialize()

        # Get wallet balances
        from core.treasury.wallet import WalletType

        total = await self._treasury.wallet_manager.get_total_balance()
        reserve = await self._treasury.wallet_manager.get_balance(WalletType.RESERVE)
        active = await self._treasury.wallet_manager.get_balance(WalletType.ACTIVE)
        profit = await self._treasury.wallet_manager.get_balance(WalletType.PROFIT)

        # Get staking stats (would come from on-chain data)
        staking_stats = await self._get_staking_from_chain()

        return TreasurySnapshot(
            timestamp=datetime.now(timezone.utc),
            total_balance_sol=self._to_sol(total),
            reserve_balance_sol=self._to_sol(reserve.sol_balance if reserve else 0),
            active_balance_sol=self._to_sol(active.sol_balance if active else 0),
            profit_buffer_sol=self._to_sol(profit.sol_balance if profit else 0),
            total_staked_sol=staking_stats.get("total_staked", 0),
            staker_count=staking_stats.get("staker_count", 0),
            pending_rewards_sol=staking_stats.get("pending_rewards", 0),
        )

    async def get_trading_stats(self, period: str = "24h") -> TradingStats:
        """
        Get trading performance statistics.

        Args:
            period: "24h", "7d", "30d", "all"
        """
        self._ensure_treasury()

        hours_map = {"24h": 24, "7d": 168, "30d": 720, "all": 8760}
        hours = hours_map.get(period, 24)

        pnl = self._treasury.risk_manager.get_pnl(
            "daily" if period == "24h" else "weekly" if period == "7d" else "monthly"
        )

        # Get detailed trade stats from database
        trade_stats = await self._get_trade_stats(hours)

        return TradingStats(
            period=period,
            total_trades=pnl.get("trade_count", 0),
            winning_trades=pnl.get("winning_trades", 0),
            losing_trades=pnl.get("trade_count", 0) - pnl.get("winning_trades", 0),
            win_rate=pnl.get("win_rate", 0),
            total_volume_sol=self._to_sol(trade_stats.get("total_volume", 0)),
            gross_profit_sol=self._to_sol(trade_stats.get("gross_profit", 0)),
            gross_loss_sol=self._to_sol(trade_stats.get("gross_loss", 0)),
            net_pnl_sol=self._to_sol(pnl.get("total_pnl", 0)),
            avg_trade_size_sol=self._to_sol(trade_stats.get("avg_trade_size", 0)),
            largest_win_sol=self._to_sol(trade_stats.get("largest_win", 0)),
            largest_loss_sol=self._to_sol(trade_stats.get("largest_loss", 0)),
            partner_fees_earned_sol=self._to_sol(trade_stats.get("partner_fees", 0)),
        )

    async def get_staking_stats(self) -> StakingStats:
        """Get staking pool statistics."""
        staking_data = await self._get_staking_from_chain()
        dist_stats = self._treasury.distributor.get_distribution_stats()

        # Calculate next distribution
        now = datetime.now(timezone.utc)
        days_until_sunday = (6 - now.weekday()) % 7
        if days_until_sunday == 0 and now.hour >= 0:
            days_until_sunday = 7
        next_distribution = now + timedelta(days=days_until_sunday)
        next_distribution = next_distribution.replace(hour=0, minute=0, second=0, microsecond=0)

        return StakingStats(
            total_staked_sol=staking_data.get("total_staked", 0),
            total_stakers=staking_data.get("staker_count", 0),
            avg_stake_sol=staking_data.get("avg_stake", 0),
            median_stake_sol=staking_data.get("median_stake", 0),
            total_rewards_distributed_sol=self._to_sol(dist_stats.get("total_to_staking", 0)),
            current_apy=staking_data.get("apy", 0),
            next_distribution_at=next_distribution,
            rewards_pool_balance_sol=staking_data.get("rewards_balance", 0),
        )

    async def get_distribution_history(
        self,
        limit: int = 52,
    ) -> List[DistributionRecord]:
        """Get profit distribution history."""
        self._ensure_treasury()

        distributions = self._treasury.distributor.get_distribution_history(limit=limit)

        records = []
        for dist in distributions:
            records.append(DistributionRecord(
                id=str(dist.id),
                timestamp=dist.timestamp,
                total_distributed_sol=self._to_sol(dist.total_amount),
                to_staking_sol=self._to_sol(dist.staking_amount),
                to_operations_sol=self._to_sol(dist.operations_amount),
                to_development_sol=self._to_sol(dist.development_amount),
                staker_count=0,  # Would get from chain
                avg_per_staker_sol=0,  # Would calculate
                transaction_signatures=[
                    s for s in [
                        dist.staking_signature,
                        dist.operations_signature,
                        dist.development_signature,
                    ] if s
                ],
            ))

        return records

    async def get_health_status(self) -> Dict[str, Any]:
        """Get treasury health indicators."""
        self._ensure_treasury()

        risk_status = self._treasury.risk_manager.get_risk_status()
        circuit_breaker = risk_status.get("circuit_breaker", {})

        # Calculate health score (0-100)
        health_score = 100

        # Deduct for circuit breaker issues
        if circuit_breaker.get("state") == "open":
            health_score -= 50
        elif circuit_breaker.get("state") == "half_open":
            health_score -= 25

        # Deduct for consecutive losses
        consecutive_losses = circuit_breaker.get("consecutive_losses", 0)
        health_score -= consecutive_losses * 10

        # Deduct for negative P&L
        pnl_daily = risk_status.get("pnl_daily", {})
        if pnl_daily.get("total_pnl", 0) < 0:
            health_score -= 10

        health_score = max(0, min(100, health_score))

        return {
            "score": health_score,
            "status": "healthy" if health_score >= 70 else "warning" if health_score >= 40 else "critical",
            "trading_allowed": circuit_breaker.get("trading_allowed", False),
            "circuit_breaker_state": circuit_breaker.get("state", "unknown"),
            "consecutive_losses": consecutive_losses,
            "risk_level": "low" if health_score >= 80 else "medium" if health_score >= 50 else "high",
        }

    async def get_wallet_addresses(self) -> Dict[str, str]:
        """Get all treasury wallet addresses (for verification)."""
        self._ensure_treasury()

        return {
            wt.value: w.address
            for wt, w in self._treasury.wallet_manager.wallets.items()
        }

    async def get_allocation_status(self) -> Dict[str, Any]:
        """Get current vs target allocation."""
        self._ensure_treasury()

        allocation = await self._treasury.wallet_manager.check_allocation()

        return {
            wallet_type.value: {
                "current_sol": self._to_sol(status["current_balance"]),
                "current_pct": round(status["current_percentage"] * 100, 2),
                "target_pct": round(status["target_percentage"] * 100, 2),
                "deviation_pct": round(status["deviation"] * 100, 2),
            }
            for wallet_type, status in allocation.items()
        }

    async def get_recent_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent treasury trades (anonymized)."""
        # Would fetch from trade logs
        # Returning minimal info for transparency without revealing strategy
        return []

    async def _get_staking_from_chain(self) -> Dict[str, Any]:
        """Fetch staking data from on-chain program."""
        # Would call Solana RPC to read staking program state
        # For now, return placeholder data
        return {
            "total_staked": 0,
            "staker_count": 0,
            "avg_stake": 0,
            "median_stake": 0,
            "pending_rewards": 0,
            "rewards_balance": 0,
            "apy": 0,
        }

    async def _get_trade_stats(self, hours: int) -> Dict[str, Any]:
        """Get detailed trade statistics."""
        # Would aggregate from trade logs
        return {
            "total_volume": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "avg_trade_size": 0,
            "largest_win": 0,
            "largest_loss": 0,
            "partner_fees": 0,
        }


# =============================================================================
# API Endpoints (FastAPI)
# =============================================================================


def create_dashboard_router():
    """Create FastAPI router for dashboard endpoints."""
    try:
        from fastapi import APIRouter, HTTPException
        from fastapi.responses import JSONResponse
    except ImportError:
        return None

    router = APIRouter(prefix="/api/treasury", tags=["Treasury Dashboard"])
    dashboard = TransparencyDashboard()

    @router.get("/overview")
    async def get_overview():
        """Get complete treasury overview."""
        try:
            return await dashboard.get_overview()
        except Exception as e:
            raise HTTPException(500, str(e))

    @router.get("/snapshot")
    async def get_snapshot():
        """Get current treasury snapshot."""
        snapshot = await dashboard.get_snapshot()
        return snapshot.to_dict()

    @router.get("/trading/{period}")
    async def get_trading_stats(period: str = "24h"):
        """Get trading statistics for period."""
        if period not in ["24h", "7d", "30d", "all"]:
            raise HTTPException(400, "Invalid period")
        stats = await dashboard.get_trading_stats(period)
        return stats.to_dict()

    @router.get("/staking")
    async def get_staking_stats():
        """Get staking pool statistics."""
        stats = await dashboard.get_staking_stats()
        return stats.to_dict()

    @router.get("/distributions")
    async def get_distributions(limit: int = 52):
        """Get distribution history."""
        distributions = await dashboard.get_distribution_history(limit)
        return [d.to_dict() for d in distributions]

    @router.get("/health")
    async def get_health():
        """Get treasury health status."""
        return await dashboard.get_health_status()

    @router.get("/wallets")
    async def get_wallets():
        """Get treasury wallet addresses."""
        return await dashboard.get_wallet_addresses()

    @router.get("/allocation")
    async def get_allocation():
        """Get current allocation status."""
        return await dashboard.get_allocation_status()

    return router


# Singleton
_dashboard: Optional[TransparencyDashboard] = None


def get_dashboard() -> TransparencyDashboard:
    """Get or create dashboard instance."""
    global _dashboard
    if _dashboard is None:
        _dashboard = TransparencyDashboard()
    return _dashboard
