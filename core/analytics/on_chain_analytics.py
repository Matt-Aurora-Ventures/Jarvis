"""
On-Chain Analytics System
Prompts #54-56: On-chain analytics, cohort analysis, and predictive analytics
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# ON-CHAIN ANALYTICS (Prompt #54)
# =============================================================================

class MetricType(str, Enum):
    TVL = "tvl"
    VOLUME = "volume"
    USERS = "users"
    TRANSACTIONS = "transactions"
    FEES = "fees"
    STAKED = "staked"
    APY = "apy"


@dataclass
class MetricDataPoint:
    """A single data point for a metric"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series data for a metric"""
    metric: MetricType
    period: str
    data_points: List[MetricDataPoint] = field(default_factory=list)

    @property
    def values(self) -> List[float]:
        return [dp.value for dp in self.data_points]

    @property
    def latest(self) -> Optional[float]:
        return self.data_points[-1].value if self.data_points else None

    def change(self, periods: int = 1) -> Optional[float]:
        if len(self.data_points) <= periods:
            return None
        current = self.data_points[-1].value
        previous = self.data_points[-1-periods].value
        if previous == 0:
            return None
        return ((current - previous) / previous) * 100


class OnChainAnalytics:
    """Collects and analyzes on-chain data"""

    def __init__(self, rpc_url: str, program_id: str):
        self.rpc_url = rpc_url
        self.program_id = program_id
        self.metrics: Dict[MetricType, MetricSeries] = {}
        self._cache: Dict[str, Any] = {}

    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect all current metrics"""
        now = datetime.utcnow()

        metrics = {
            "timestamp": now.isoformat(),
            "tvl": await self._get_tvl(),
            "total_staked": await self._get_total_staked(),
            "active_stakers": await self._get_active_stakers(),
            "daily_volume": await self._get_daily_volume(),
            "daily_transactions": await self._get_daily_transactions(),
            "total_fees_collected": await self._get_fees_collected(),
            "current_apy": await self._get_current_apy(),
            "token_price": await self._get_token_price()
        }

        # Store in time series
        for metric_type in MetricType:
            if metric_type.value in metrics:
                self._add_data_point(metric_type, metrics[metric_type.value], now)

        return metrics

    async def get_historical_metrics(
        self,
        metric: MetricType,
        period: str = "7d"
    ) -> MetricSeries:
        """Get historical data for a metric"""
        days = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365}.get(period, 7)
        cutoff = datetime.utcnow() - timedelta(days=days)

        series = self.metrics.get(metric)
        if not series:
            return MetricSeries(metric=metric, period=period)

        filtered = MetricSeries(
            metric=metric,
            period=period,
            data_points=[
                dp for dp in series.data_points
                if dp.timestamp >= cutoff
            ]
        )
        return filtered

    async def get_protocol_stats(self) -> Dict[str, Any]:
        """Get comprehensive protocol statistics"""
        return {
            "tvl": {
                "current": await self._get_tvl(),
                "change_24h": await self._get_metric_change(MetricType.TVL, 1),
                "change_7d": await self._get_metric_change(MetricType.TVL, 7)
            },
            "volume": {
                "daily": await self._get_daily_volume(),
                "weekly": await self._get_weekly_volume(),
                "monthly": await self._get_monthly_volume()
            },
            "users": {
                "total": await self._get_total_users(),
                "active_daily": await self._get_active_users(1),
                "active_weekly": await self._get_active_users(7),
                "active_monthly": await self._get_active_users(30)
            },
            "staking": {
                "total_staked": await self._get_total_staked(),
                "stakers": await self._get_active_stakers(),
                "average_stake": await self._get_average_stake(),
                "current_apy": await self._get_current_apy()
            },
            "fees": {
                "total_collected": await self._get_fees_collected(),
                "daily_revenue": await self._get_daily_revenue(),
                "fee_rate": await self._get_fee_rate()
            }
        }

    def _add_data_point(self, metric: MetricType, value: float, timestamp: datetime):
        """Add a data point to a metric series"""
        if metric not in self.metrics:
            self.metrics[metric] = MetricSeries(metric=metric, period="all")

        self.metrics[metric].data_points.append(
            MetricDataPoint(timestamp=timestamp, value=value)
        )

        # Keep only last 90 days
        cutoff = datetime.utcnow() - timedelta(days=90)
        self.metrics[metric].data_points = [
            dp for dp in self.metrics[metric].data_points
            if dp.timestamp >= cutoff
        ]

    async def _get_metric_change(self, metric: MetricType, days: int) -> Optional[float]:
        series = self.metrics.get(metric)
        if not series or len(series.data_points) < days:
            return None

        current = series.data_points[-1].value
        previous = series.data_points[-1-days].value if len(series.data_points) > days else series.data_points[0].value
        if previous == 0:
            return None
        return ((current - previous) / previous) * 100

    # Placeholder methods - would query actual on-chain data
    async def _get_tvl(self) -> float:
        return 10_000_000.0

    async def _get_total_staked(self) -> float:
        return 5_000_000.0

    async def _get_active_stakers(self) -> int:
        return 1500

    async def _get_daily_volume(self) -> float:
        return 500_000.0

    async def _get_weekly_volume(self) -> float:
        return 3_500_000.0

    async def _get_monthly_volume(self) -> float:
        return 15_000_000.0

    async def _get_daily_transactions(self) -> int:
        return 2500

    async def _get_fees_collected(self) -> float:
        return 50_000.0

    async def _get_current_apy(self) -> float:
        return 25.0

    async def _get_token_price(self) -> float:
        return 0.001

    async def _get_total_users(self) -> int:
        return 5000

    async def _get_active_users(self, days: int) -> int:
        return {1: 500, 7: 1500, 30: 3000}.get(days, 500)

    async def _get_average_stake(self) -> float:
        return 3333.33

    async def _get_daily_revenue(self) -> float:
        return 5000.0

    async def _get_fee_rate(self) -> float:
        return 0.3  # 0.3%


# =============================================================================
# COHORT ANALYSIS (Prompt #55)
# =============================================================================

@dataclass
class CohortData:
    """Data for a user cohort"""
    cohort_id: str
    start_date: datetime
    size: int
    retention: Dict[int, float] = field(default_factory=dict)  # week -> retention %
    ltv: float = 0.0
    avg_trades: float = 0.0
    avg_stake: float = 0.0
    conversion_rate: float = 0.0


class CohortAnalyzer:
    """Analyzes user cohorts for retention and LTV"""

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.cohorts: Dict[str, CohortData] = {}

    async def create_cohort(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> CohortData:
        """Create a new cohort from users who joined in date range"""
        cohort_id = f"cohort_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"

        # Get users who joined in this period
        users = await self._get_users_by_join_date(start_date, end_date)

        cohort = CohortData(
            cohort_id=cohort_id,
            start_date=start_date,
            size=len(users)
        )

        self.cohorts[cohort_id] = cohort
        return cohort

    async def calculate_retention(
        self,
        cohort_id: str,
        weeks: int = 12
    ) -> Dict[int, float]:
        """Calculate week-over-week retention for a cohort"""
        cohort = self.cohorts.get(cohort_id)
        if not cohort:
            raise ValueError("Cohort not found")

        retention = {}
        for week in range(1, weeks + 1):
            week_start = cohort.start_date + timedelta(weeks=week)
            week_end = week_start + timedelta(weeks=1)

            active = await self._get_active_users_in_period(
                cohort_id, week_start, week_end
            )
            retention[week] = (active / cohort.size * 100) if cohort.size > 0 else 0

        cohort.retention = retention
        return retention

    async def calculate_ltv(
        self,
        cohort_id: str,
        months: int = 12
    ) -> float:
        """Calculate lifetime value for a cohort"""
        cohort = self.cohorts.get(cohort_id)
        if not cohort:
            raise ValueError("Cohort not found")

        # Sum of all revenue from cohort users
        total_revenue = await self._get_cohort_revenue(cohort_id, months)
        ltv = total_revenue / cohort.size if cohort.size > 0 else 0

        cohort.ltv = ltv
        return ltv

    async def get_cohort_comparison(
        self,
        cohort_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Compare multiple cohorts"""
        comparison = {}

        for cohort_id in cohort_ids:
            cohort = self.cohorts.get(cohort_id)
            if not cohort:
                continue

            comparison[cohort_id] = {
                "size": cohort.size,
                "start_date": cohort.start_date.isoformat(),
                "retention_week_1": cohort.retention.get(1, 0),
                "retention_week_4": cohort.retention.get(4, 0),
                "retention_week_12": cohort.retention.get(12, 0),
                "ltv": cohort.ltv,
                "avg_trades": cohort.avg_trades,
                "avg_stake": cohort.avg_stake
            }

        return comparison

    async def get_retention_matrix(
        self,
        start_date: datetime,
        cohort_period: str = "weekly",
        num_cohorts: int = 12
    ) -> List[Dict[str, Any]]:
        """Generate retention matrix for multiple cohorts"""
        matrix = []

        for i in range(num_cohorts):
            if cohort_period == "weekly":
                cohort_start = start_date - timedelta(weeks=i)
                cohort_end = cohort_start + timedelta(weeks=1)
            else:  # monthly
                cohort_start = start_date.replace(day=1) - timedelta(days=30*i)
                cohort_end = cohort_start + timedelta(days=30)

            cohort = await self.create_cohort(cohort_start, cohort_end)
            await self.calculate_retention(cohort.cohort_id)

            matrix.append({
                "cohort": cohort_start.strftime("%Y-%m-%d"),
                "size": cohort.size,
                "retention": cohort.retention
            })

        return matrix

    # Placeholder methods
    async def _get_users_by_join_date(
        self,
        start: datetime,
        end: datetime
    ) -> List[str]:
        return ["user1", "user2", "user3"]

    async def _get_active_users_in_period(
        self,
        cohort_id: str,
        start: datetime,
        end: datetime
    ) -> int:
        return 50

    async def _get_cohort_revenue(
        self,
        cohort_id: str,
        months: int
    ) -> float:
        return 10000.0


# =============================================================================
# PREDICTIVE ANALYTICS (Prompt #56)
# =============================================================================

@dataclass
class Prediction:
    """A prediction result"""
    metric: str
    predicted_value: float
    confidence: float
    prediction_date: datetime
    horizon_days: int
    model_version: str
    features_used: List[str] = field(default_factory=list)


class PredictiveAnalytics:
    """Machine learning-based predictions for protocol metrics"""

    def __init__(self, analytics: OnChainAnalytics):
        self.analytics = analytics
        self.predictions: List[Prediction] = []
        self.model_version = "v1.0"

    async def predict_tvl(
        self,
        horizon_days: int = 7
    ) -> Prediction:
        """Predict TVL for the next N days"""
        # Get historical data
        series = await self.analytics.get_historical_metrics(
            MetricType.TVL, "30d"
        )

        if len(series.values) < 7:
            # Not enough data, return current value
            current = series.latest or 0
            return Prediction(
                metric="tvl",
                predicted_value=current,
                confidence=0.5,
                prediction_date=datetime.utcnow() + timedelta(days=horizon_days),
                horizon_days=horizon_days,
                model_version=self.model_version
            )

        # Simple exponential moving average prediction
        alpha = 0.3
        ema = series.values[0]
        for value in series.values[1:]:
            ema = alpha * value + (1 - alpha) * ema

        # Trend adjustment
        if len(series.values) >= 14:
            recent_trend = (series.values[-1] - series.values[-7]) / 7
            predicted = ema + (recent_trend * horizon_days)
        else:
            predicted = ema

        # Calculate confidence based on volatility
        if len(series.values) >= 7:
            volatility = statistics.stdev(series.values[-7:]) / statistics.mean(series.values[-7:])
            confidence = max(0.3, min(0.9, 1 - volatility))
        else:
            confidence = 0.5

        prediction = Prediction(
            metric="tvl",
            predicted_value=predicted,
            confidence=confidence,
            prediction_date=datetime.utcnow() + timedelta(days=horizon_days),
            horizon_days=horizon_days,
            model_version=self.model_version,
            features_used=["historical_tvl", "ema", "trend"]
        )

        self.predictions.append(prediction)
        return prediction

    async def predict_volume(
        self,
        horizon_days: int = 7
    ) -> Prediction:
        """Predict trading volume"""
        series = await self.analytics.get_historical_metrics(
            MetricType.VOLUME, "30d"
        )

        if not series.values:
            return Prediction(
                metric="volume",
                predicted_value=0,
                confidence=0.3,
                prediction_date=datetime.utcnow() + timedelta(days=horizon_days),
                horizon_days=horizon_days,
                model_version=self.model_version
            )

        # Use simple moving average
        window = min(7, len(series.values))
        sma = sum(series.values[-window:]) / window
        predicted = sma * horizon_days

        prediction = Prediction(
            metric="volume",
            predicted_value=predicted,
            confidence=0.6,
            prediction_date=datetime.utcnow() + timedelta(days=horizon_days),
            horizon_days=horizon_days,
            model_version=self.model_version,
            features_used=["historical_volume", "sma"]
        )

        self.predictions.append(prediction)
        return prediction

    async def predict_churn_risk(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """Predict churn risk for a specific user"""
        # Get user activity metrics
        user_metrics = await self._get_user_metrics(user_id)

        # Simple rule-based churn scoring
        risk_score = 0.0
        risk_factors = []

        # Check days since last activity
        days_inactive = user_metrics.get("days_since_last_activity", 0)
        if days_inactive > 30:
            risk_score += 0.4
            risk_factors.append("inactive_30d")
        elif days_inactive > 14:
            risk_score += 0.2
            risk_factors.append("inactive_14d")
        elif days_inactive > 7:
            risk_score += 0.1
            risk_factors.append("inactive_7d")

        # Check declining activity trend
        if user_metrics.get("activity_declining", False):
            risk_score += 0.2
            risk_factors.append("declining_activity")

        # Check if unstaked recently
        if user_metrics.get("unstaked_recently", False):
            risk_score += 0.3
            risk_factors.append("unstaked")

        # Check trade frequency
        if user_metrics.get("trades_last_30d", 0) < 5:
            risk_score += 0.1
            risk_factors.append("low_trade_frequency")

        return {
            "user_id": user_id,
            "churn_risk": min(1.0, risk_score),
            "risk_level": "high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low",
            "risk_factors": risk_factors,
            "recommendations": self._get_retention_recommendations(risk_factors)
        }

    async def predict_optimal_apy(
        self,
        target_tvl: float
    ) -> Dict[str, Any]:
        """Predict optimal APY to reach target TVL"""
        current_tvl = await self.analytics._get_tvl()
        current_apy = await self.analytics._get_current_apy()

        # Simple elasticity model: TVL changes ~2% for every 1% APY change
        elasticity = 2.0

        required_tvl_change = (target_tvl - current_tvl) / current_tvl * 100
        required_apy_change = required_tvl_change / elasticity

        optimal_apy = current_apy + required_apy_change

        return {
            "current_tvl": current_tvl,
            "target_tvl": target_tvl,
            "current_apy": current_apy,
            "recommended_apy": max(5, min(100, optimal_apy)),
            "expected_time_to_target": self._estimate_time_to_target(
                current_tvl, target_tvl, optimal_apy
            )
        }

    def _get_retention_recommendations(
        self,
        risk_factors: List[str]
    ) -> List[str]:
        """Get retention recommendations based on risk factors"""
        recommendations = []

        if "inactive_30d" in risk_factors or "inactive_14d" in risk_factors:
            recommendations.append("Send re-engagement email with special offer")
        if "unstaked" in risk_factors:
            recommendations.append("Offer staking bonus for re-staking")
        if "low_trade_frequency" in risk_factors:
            recommendations.append("Send trading opportunity alerts")
        if "declining_activity" in risk_factors:
            recommendations.append("Offer loyalty rewards")

        return recommendations

    def _estimate_time_to_target(
        self,
        current: float,
        target: float,
        apy: float
    ) -> int:
        """Estimate days to reach target TVL"""
        if target <= current:
            return 0

        # Assume daily growth rate based on APY difference
        daily_growth = 0.001 * (apy / 25)  # 0.1% per day at 25% APY
        if daily_growth <= 0:
            return 365

        days = 0
        value = current
        while value < target and days < 365:
            value *= (1 + daily_growth)
            days += 1

        return days

    async def _get_user_metrics(self, user_id: str) -> Dict[str, Any]:
        """Get metrics for a specific user"""
        return {
            "days_since_last_activity": 5,
            "activity_declining": False,
            "unstaked_recently": False,
            "trades_last_30d": 15
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_analytics_endpoints(
    analytics: OnChainAnalytics,
    cohort_analyzer: CohortAnalyzer,
    predictor: PredictiveAnalytics
):
    """Create API endpoints for analytics"""
    from fastapi import APIRouter

    router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

    @router.get("/metrics")
    async def get_current_metrics():
        """Get current protocol metrics"""
        return await analytics.collect_metrics()

    @router.get("/metrics/{metric}/history")
    async def get_metric_history(metric: str, period: str = "7d"):
        """Get historical data for a metric"""
        series = await analytics.get_historical_metrics(
            MetricType(metric), period
        )
        return {
            "metric": metric,
            "period": period,
            "data": [
                {"timestamp": dp.timestamp.isoformat(), "value": dp.value}
                for dp in series.data_points
            ]
        }

    @router.get("/protocol-stats")
    async def get_protocol_stats():
        """Get comprehensive protocol statistics"""
        return await analytics.get_protocol_stats()

    @router.get("/cohorts/retention-matrix")
    async def get_retention_matrix(period: str = "weekly", num_cohorts: int = 12):
        """Get retention matrix"""
        start_date = datetime.utcnow()
        return await cohort_analyzer.get_retention_matrix(
            start_date, period, num_cohorts
        )

    @router.get("/predictions/tvl")
    async def predict_tvl(horizon_days: int = 7):
        """Predict TVL"""
        prediction = await predictor.predict_tvl(horizon_days)
        return {
            "predicted_value": prediction.predicted_value,
            "confidence": prediction.confidence,
            "prediction_date": prediction.prediction_date.isoformat()
        }

    @router.get("/predictions/churn/{user_id}")
    async def predict_churn(user_id: str):
        """Predict churn risk for a user"""
        return await predictor.predict_churn_risk(user_id)

    @router.get("/predictions/optimal-apy")
    async def predict_optimal_apy(target_tvl: float):
        """Predict optimal APY for target TVL"""
        return await predictor.predict_optimal_apy(target_tvl)

    return router
