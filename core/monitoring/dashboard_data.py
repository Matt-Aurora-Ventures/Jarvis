"""
Dashboard Data Provider - Unified data source for monitoring dashboards.

Exposes: all health/metrics data
Endpoint: GET /dashboard/data returns JSON

Includes:
- Current health status
- Performance metrics
- Budget usage
- Trading stats
- Recent alerts
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.monitoring.dashboard_data")


class DashboardDataProvider:
    """
    Provides unified dashboard data from all monitoring sources.

    Aggregates:
    - SystemHealthChecker
    - PerformanceTracker
    - BudgetTracker
    - Alerter history
    - Trading statistics
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)

    def _get_health_checker(self):
        """Get health checker instance."""
        try:
            from core.monitoring.health_check import get_system_health_checker
            return get_system_health_checker()
        except Exception as e:
            logger.warning(f"Failed to get health checker: {e}")
            return None

    def _get_performance_tracker(self):
        """Get performance tracker instance."""
        try:
            from core.monitoring.performance_tracker import get_performance_tracker
            return get_performance_tracker()
        except Exception as e:
            logger.warning(f"Failed to get performance tracker: {e}")
            return None

    def _get_budget_tracker(self):
        """Get budget tracker instance."""
        try:
            from core.monitoring.budget_tracker import get_budget_tracker
            return get_budget_tracker()
        except Exception as e:
            logger.warning(f"Failed to get budget tracker: {e}")
            return None

    def _get_alerter(self):
        """Get alerter instance."""
        try:
            from core.monitoring.alerter import get_alerter
            return get_alerter()
        except Exception as e:
            logger.warning(f"Failed to get alerter: {e}")
            return None

    async def _get_health_data(self) -> Dict[str, Any]:
        """Get current health status."""
        checker = self._get_health_checker()
        if checker:
            try:
                return await checker.check_all()
            except Exception as e:
                logger.warning(f"Failed to get health data: {e}")
        return {"status": "unknown", "error": "Health checker unavailable"}

    def _get_performance_data(self) -> Dict[str, Any]:
        """Get performance metrics."""
        tracker = self._get_performance_tracker()
        if tracker:
            try:
                return tracker.get_all_stats()
            except Exception as e:
                logger.warning(f"Failed to get performance data: {e}")
        return {"uptime": {}, "api_availability": {}, "trade_latency": {}}

    def _get_budget_data(self) -> Dict[str, Any]:
        """Get budget usage data."""
        tracker = self._get_budget_tracker()
        if tracker:
            try:
                return tracker.get_all_stats()
            except Exception as e:
                logger.warning(f"Failed to get budget data: {e}")
        return {"total_daily_spend": 0, "services": {}}

    def _get_trading_stats(self) -> Dict[str, Any]:
        """Get trading statistics."""
        try:
            # Try to load from positions file
            positions_path = self.data_dir / "treasury" / ".positions.json"
            if not positions_path.exists():
                positions_path = Path("bots/treasury/.positions.json")

            positions = []
            if positions_path.exists():
                with open(positions_path) as f:
                    positions = json.load(f)

            # Calculate basic stats
            if isinstance(positions, list):
                total_positions = len(positions)
                total_value = sum(p.get("value_usd", 0) for p in positions)
            else:
                total_positions = 0
                total_value = 0

            # Try to get trading history stats
            scorekeeper_path = Path("data/treasury_scorekeeper.json")
            win_rate = 0.0
            total_trades = 0

            if scorekeeper_path.exists():
                with open(scorekeeper_path) as f:
                    scorekeeper = json.load(f)
                    wins = scorekeeper.get("wins", 0)
                    losses = scorekeeper.get("losses", 0)
                    total_trades = wins + losses
                    if total_trades > 0:
                        win_rate = (wins / total_trades) * 100

            return {
                "position_count": total_positions,
                "total_value_usd": round(total_value, 2),
                "total_trades": total_trades,
                "win_rate_percent": round(win_rate, 1)
            }

        except Exception as e:
            logger.warning(f"Failed to get trading stats: {e}")
            return {
                "position_count": 0,
                "total_value_usd": 0,
                "total_trades": 0,
                "win_rate_percent": 0
            }

    def _get_recent_alerts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent alerts."""
        alerter = self._get_alerter()
        if alerter:
            try:
                return alerter.get_alert_history(limit=limit)
            except Exception as e:
                logger.warning(f"Failed to get alerts: {e}")
        return []

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get complete dashboard data.

        Returns comprehensive monitoring data including:
        - Health status
        - Performance metrics
        - Budget usage
        - Trading stats
        - Recent alerts
        """
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "health": await self._get_health_data(),
            "performance": self._get_performance_data(),
            "budget": self._get_budget_data(),
            "trading": self._get_trading_stats(),
            "alerts": self._get_recent_alerts()
        }

    async def get_dashboard_json(self) -> str:
        """Get dashboard data as JSON string."""
        data = await self.get_dashboard_data()
        return json.dumps(data, indent=2, default=str)


# FastAPI Router for dashboard endpoints
def create_dashboard_router():
    """
    Create FastAPI router for dashboard endpoints.

    Endpoints:
    - GET /dashboard/data - Full dashboard data
    - GET /dashboard/health - Health summary only
    - GET /dashboard/budget - Budget summary only
    """
    try:
        from fastapi import APIRouter
        from fastapi.responses import JSONResponse
    except ImportError:
        logger.warning("FastAPI not available, router not created")
        return None

    router = APIRouter(prefix="/dashboard", tags=["dashboard"])

    @router.get("/data", summary="Dashboard Data", description="Get complete dashboard data")
    async def get_dashboard_data():
        """Get complete dashboard data including health, performance, budget, and alerts."""
        provider = DashboardDataProvider()
        data = await provider.get_dashboard_data()
        return JSONResponse(content=data)

    @router.get("/health", summary="Health Summary", description="Get health status only")
    async def get_health_summary():
        """Get health status summary."""
        provider = DashboardDataProvider()
        data = await provider.get_dashboard_data()
        return JSONResponse(content={
            "timestamp": data["timestamp"],
            "health": data["health"]
        })

    @router.get("/budget", summary="Budget Summary", description="Get budget usage only")
    async def get_budget_summary():
        """Get budget usage summary."""
        provider = DashboardDataProvider()
        data = await provider.get_dashboard_data()
        return JSONResponse(content={
            "timestamp": data["timestamp"],
            "budget": data["budget"]
        })

    @router.get("/alerts", summary="Recent Alerts", description="Get recent alerts")
    async def get_alerts():
        """Get recent alerts."""
        provider = DashboardDataProvider()
        data = await provider.get_dashboard_data()
        return JSONResponse(content={
            "timestamp": data["timestamp"],
            "alerts": data["alerts"]
        })

    return router


# Singleton
_provider: Optional[DashboardDataProvider] = None


def get_dashboard_provider() -> DashboardDataProvider:
    """Get or create the dashboard data provider singleton."""
    global _provider
    if _provider is None:
        _provider = DashboardDataProvider()
    return _provider
