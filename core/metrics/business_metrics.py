"""
Business Metrics System
Prompts #79-80: KPI tracking, business dashboards, and advanced cohort analysis
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Metric periods
HOURLY = "hourly"
DAILY = "daily"
WEEKLY = "weekly"
MONTHLY = "monthly"

# Alert thresholds
CRITICAL_THRESHOLD = 0.9
WARNING_THRESHOLD = 0.7


# =============================================================================
# MODELS
# =============================================================================

class MetricType(str, Enum):
    COUNTER = "counter"        # Monotonically increasing
    GAUGE = "gauge"            # Point-in-time value
    HISTOGRAM = "histogram"    # Distribution of values
    RATE = "rate"              # Change per unit time


class MetricCategory(str, Enum):
    REVENUE = "revenue"
    USERS = "users"
    ENGAGEMENT = "engagement"
    PERFORMANCE = "performance"
    GROWTH = "growth"
    RETENTION = "retention"


@dataclass
class MetricDefinition:
    """Definition of a business metric"""
    id: str
    name: str
    description: str
    category: MetricCategory
    metric_type: MetricType
    unit: str
    formula: Optional[str] = None
    target: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None


@dataclass
class MetricValue:
    """A recorded metric value"""
    metric_id: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    dimensions: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KPISnapshot:
    """Snapshot of key performance indicators"""
    timestamp: datetime
    tvl: Decimal
    daily_volume: Decimal
    daily_fees: Decimal
    daily_active_users: int
    total_users: int
    new_users_24h: int
    average_stake: Decimal
    retention_7d: float
    churn_rate: float


@dataclass
class CohortData:
    """Data for a user cohort"""
    cohort_id: str
    start_date: datetime
    size: int
    retention: Dict[int, float]  # day -> retention rate
    revenue: Dict[int, Decimal]  # day -> cumulative revenue
    activity: Dict[int, int]     # day -> active users
    characteristics: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# METRIC DEFINITIONS
# =============================================================================

CORE_METRICS = [
    MetricDefinition(
        id="tvl",
        name="Total Value Locked",
        description="Total value of assets staked/locked in the protocol",
        category=MetricCategory.REVENUE,
        metric_type=MetricType.GAUGE,
        unit="USD"
    ),
    MetricDefinition(
        id="daily_volume",
        name="Daily Trading Volume",
        description="Total trading volume in the last 24 hours",
        category=MetricCategory.REVENUE,
        metric_type=MetricType.GAUGE,
        unit="USD"
    ),
    MetricDefinition(
        id="daily_fees",
        name="Daily Fees Collected",
        description="Total fees collected in the last 24 hours",
        category=MetricCategory.REVENUE,
        metric_type=MetricType.GAUGE,
        unit="USD"
    ),
    MetricDefinition(
        id="dau",
        name="Daily Active Users",
        description="Unique users active in the last 24 hours",
        category=MetricCategory.USERS,
        metric_type=MetricType.GAUGE,
        unit="users"
    ),
    MetricDefinition(
        id="wau",
        name="Weekly Active Users",
        description="Unique users active in the last 7 days",
        category=MetricCategory.USERS,
        metric_type=MetricType.GAUGE,
        unit="users"
    ),
    MetricDefinition(
        id="mau",
        name="Monthly Active Users",
        description="Unique users active in the last 30 days",
        category=MetricCategory.USERS,
        metric_type=MetricType.GAUGE,
        unit="users"
    ),
    MetricDefinition(
        id="new_users",
        name="New Users",
        description="New users in the period",
        category=MetricCategory.GROWTH,
        metric_type=MetricType.COUNTER,
        unit="users"
    ),
    MetricDefinition(
        id="retention_d1",
        name="Day 1 Retention",
        description="Users returning on day 1",
        category=MetricCategory.RETENTION,
        metric_type=MetricType.GAUGE,
        unit="percent",
        target=40.0,
        warning_threshold=30.0,
        critical_threshold=20.0
    ),
    MetricDefinition(
        id="retention_d7",
        name="Day 7 Retention",
        description="Users returning on day 7",
        category=MetricCategory.RETENTION,
        metric_type=MetricType.GAUGE,
        unit="percent",
        target=25.0,
        warning_threshold=15.0,
        critical_threshold=10.0
    ),
    MetricDefinition(
        id="retention_d30",
        name="Day 30 Retention",
        description="Users returning on day 30",
        category=MetricCategory.RETENTION,
        metric_type=MetricType.GAUGE,
        unit="percent",
        target=15.0,
        warning_threshold=10.0,
        critical_threshold=5.0
    ),
    MetricDefinition(
        id="arpu",
        name="Average Revenue Per User",
        description="Average revenue per user in the period",
        category=MetricCategory.REVENUE,
        metric_type=MetricType.GAUGE,
        unit="USD"
    ),
    MetricDefinition(
        id="ltv",
        name="Customer Lifetime Value",
        description="Predicted lifetime value of a customer",
        category=MetricCategory.REVENUE,
        metric_type=MetricType.GAUGE,
        unit="USD"
    ),
    MetricDefinition(
        id="churn_rate",
        name="Churn Rate",
        description="Monthly user churn rate",
        category=MetricCategory.RETENTION,
        metric_type=MetricType.GAUGE,
        unit="percent",
        target=5.0,
        warning_threshold=10.0,
        critical_threshold=15.0
    ),
    MetricDefinition(
        id="nps",
        name="Net Promoter Score",
        description="User satisfaction score",
        category=MetricCategory.ENGAGEMENT,
        metric_type=MetricType.GAUGE,
        unit="score",
        target=50.0,
        warning_threshold=30.0,
        critical_threshold=10.0
    )
]


# =============================================================================
# BUSINESS METRICS TRACKER
# =============================================================================

class BusinessMetricsTracker:
    """Tracks and analyzes business metrics"""

    def __init__(self):
        self.metrics: Dict[str, MetricDefinition] = {m.id: m for m in CORE_METRICS}
        self.values: Dict[str, List[MetricValue]] = {}
        self.snapshots: List[KPISnapshot] = []

    # =========================================================================
    # METRIC RECORDING
    # =========================================================================

    async def record_metric(
        self,
        metric_id: str,
        value: float,
        dimensions: Dict[str, str] = None,
        metadata: Dict[str, Any] = None
    ):
        """Record a metric value"""
        if metric_id not in self.values:
            self.values[metric_id] = []

        metric_value = MetricValue(
            metric_id=metric_id,
            value=value,
            dimensions=dimensions or {},
            metadata=metadata or {}
        )

        self.values[metric_id].append(metric_value)

        # Check thresholds
        definition = self.metrics.get(metric_id)
        if definition:
            await self._check_thresholds(definition, value)

    async def _check_thresholds(self, definition: MetricDefinition, value: float):
        """Check if value breaches thresholds"""
        if definition.critical_threshold is not None:
            # For retention/NPS, lower is worse
            if definition.metric_type == MetricType.GAUGE and "retention" in definition.id:
                if value < definition.critical_threshold:
                    logger.critical(f"CRITICAL: {definition.name} = {value} (< {definition.critical_threshold})")
            # For churn, higher is worse
            elif "churn" in definition.id:
                if value > definition.critical_threshold:
                    logger.critical(f"CRITICAL: {definition.name} = {value} (> {definition.critical_threshold})")

    async def record_snapshot(self, snapshot: KPISnapshot):
        """Record a KPI snapshot"""
        self.snapshots.append(snapshot)

        # Record individual metrics
        await self.record_metric("tvl", float(snapshot.tvl))
        await self.record_metric("daily_volume", float(snapshot.daily_volume))
        await self.record_metric("daily_fees", float(snapshot.daily_fees))
        await self.record_metric("dau", snapshot.daily_active_users)
        await self.record_metric("retention_d7", snapshot.retention_7d)
        await self.record_metric("churn_rate", snapshot.churn_rate)

    # =========================================================================
    # METRIC QUERIES
    # =========================================================================

    async def get_metric(
        self,
        metric_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        dimensions: Dict[str, str] = None
    ) -> List[MetricValue]:
        """Get metric values with optional filtering"""
        values = self.values.get(metric_id, [])

        if start_time:
            values = [v for v in values if v.timestamp >= start_time]
        if end_time:
            values = [v for v in values if v.timestamp <= end_time]
        if dimensions:
            values = [
                v for v in values
                if all(v.dimensions.get(k) == val for k, val in dimensions.items())
            ]

        return values

    async def get_current_value(self, metric_id: str) -> Optional[float]:
        """Get the most recent value for a metric"""
        values = self.values.get(metric_id, [])
        if not values:
            return None
        return values[-1].value

    async def get_metric_summary(
        self,
        metric_id: str,
        period: str = DAILY
    ) -> Dict[str, Any]:
        """Get summary statistics for a metric"""
        now = datetime.utcnow()

        if period == HOURLY:
            start = now - timedelta(hours=1)
        elif period == DAILY:
            start = now - timedelta(days=1)
        elif period == WEEKLY:
            start = now - timedelta(weeks=1)
        else:  # MONTHLY
            start = now - timedelta(days=30)

        values = await self.get_metric(metric_id, start_time=start)

        if not values:
            return {"no_data": True}

        nums = [v.value for v in values]

        return {
            "metric_id": metric_id,
            "period": period,
            "count": len(nums),
            "min": min(nums),
            "max": max(nums),
            "avg": statistics.mean(nums),
            "median": statistics.median(nums),
            "std_dev": statistics.stdev(nums) if len(nums) > 1 else 0,
            "current": nums[-1],
            "change": (nums[-1] - nums[0]) / nums[0] * 100 if nums[0] != 0 else 0
        }

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    async def calculate_trend(
        self,
        metric_id: str,
        period: str = DAILY
    ) -> Dict[str, Any]:
        """Calculate trend for a metric"""
        summary = await self.get_metric_summary(metric_id, period)

        if "no_data" in summary:
            return {"trend": "unknown", "confidence": 0}

        change = summary.get("change", 0)

        if change > 10:
            trend = "strongly_increasing"
        elif change > 2:
            trend = "increasing"
        elif change > -2:
            trend = "stable"
        elif change > -10:
            trend = "decreasing"
        else:
            trend = "strongly_decreasing"

        return {
            "trend": trend,
            "change_percent": change,
            "current_value": summary.get("current"),
            "period": period
        }

    async def forecast_metric(
        self,
        metric_id: str,
        days_ahead: int = 7
    ) -> Dict[str, Any]:
        """Forecast metric values using simple linear regression"""
        values = await self.get_metric(
            metric_id,
            start_time=datetime.utcnow() - timedelta(days=30)
        )

        if len(values) < 7:
            return {"error": "Insufficient data for forecast"}

        # Simple linear regression
        x = list(range(len(values)))
        y = [v.value for v in values]

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        intercept = (sum_y - slope * sum_x) / n

        # Forecast
        forecasts = []
        for d in range(1, days_ahead + 1):
            predicted = intercept + slope * (len(values) + d)
            forecasts.append({
                "day": d,
                "value": predicted,
                "date": (datetime.utcnow() + timedelta(days=d)).strftime("%Y-%m-%d")
            })

        return {
            "metric_id": metric_id,
            "current_value": y[-1],
            "forecasts": forecasts,
            "trend_slope": slope,
            "confidence": 0.7 if len(values) >= 14 else 0.5
        }


# =============================================================================
# ADVANCED COHORT ANALYZER
# =============================================================================

class AdvancedCohortAnalyzer:
    """Advanced cohort analysis for user behavior"""

    def __init__(self):
        self.cohorts: Dict[str, CohortData] = {}
        self.user_cohorts: Dict[str, str] = {}  # user -> cohort_id
        self.user_activity: Dict[str, List[datetime]] = {}  # user -> activity timestamps

    async def create_cohort(
        self,
        cohort_id: str,
        users: List[str],
        start_date: datetime,
        characteristics: Dict[str, Any] = None
    ) -> CohortData:
        """Create a new cohort"""
        cohort = CohortData(
            cohort_id=cohort_id,
            start_date=start_date,
            size=len(users),
            retention={0: 100.0},
            revenue={0: Decimal("0")},
            activity={0: len(users)},
            characteristics=characteristics or {}
        )

        self.cohorts[cohort_id] = cohort

        for user in users:
            self.user_cohorts[user] = cohort_id

        logger.info(f"Created cohort {cohort_id} with {len(users)} users")
        return cohort

    async def record_user_activity(self, user: str, timestamp: datetime = None):
        """Record user activity"""
        timestamp = timestamp or datetime.utcnow()

        if user not in self.user_activity:
            self.user_activity[user] = []

        self.user_activity[user].append(timestamp)

    async def calculate_retention(
        self,
        cohort_id: str,
        max_days: int = 30
    ) -> Dict[int, float]:
        """Calculate retention curve for a cohort"""
        cohort = self.cohorts.get(cohort_id)
        if not cohort:
            return {}

        # Get users in cohort
        cohort_users = [
            user for user, cid in self.user_cohorts.items()
            if cid == cohort_id
        ]

        retention = {0: 100.0}

        for day in range(1, max_days + 1):
            target_date = cohort.start_date + timedelta(days=day)
            active_count = 0

            for user in cohort_users:
                activities = self.user_activity.get(user, [])
                # Check if user was active on target day
                if any(
                    act.date() == target_date.date()
                    for act in activities
                ):
                    active_count += 1

            retention[day] = (active_count / len(cohort_users) * 100) if cohort_users else 0

        cohort.retention = retention
        return retention

    async def build_retention_matrix(
        self,
        period: str = "weekly",
        num_cohorts: int = 8
    ) -> Dict[str, Any]:
        """Build a retention matrix for multiple cohorts"""
        matrix = {}
        cohort_list = sorted(
            self.cohorts.values(),
            key=lambda c: c.start_date,
            reverse=True
        )[:num_cohorts]

        for cohort in cohort_list:
            retention = await self.calculate_retention(cohort.cohort_id)
            cohort_label = cohort.start_date.strftime("%Y-%m-%d")

            if period == "weekly":
                matrix[cohort_label] = {
                    f"Week {i}": retention.get(i * 7, 0)
                    for i in range(5)
                }
            else:  # daily
                matrix[cohort_label] = {
                    f"Day {i}": retention.get(i, 0)
                    for i in [0, 1, 3, 7, 14, 30]
                }

        return {
            "period": period,
            "cohorts": num_cohorts,
            "matrix": matrix
        }

    async def calculate_ltv(
        self,
        cohort_id: str,
        arpu: Decimal,
        months: int = 24
    ) -> Dict[str, Any]:
        """Calculate customer lifetime value for a cohort"""
        retention = await self.calculate_retention(cohort_id, max_days=months * 30)

        # Monthly retention (approximate)
        monthly_retention = [
            retention.get(i * 30, 0) / 100
            for i in range(months + 1)
        ]

        # Calculate LTV as sum of expected revenue each month
        ltv = Decimal("0")
        for month, ret_rate in enumerate(monthly_retention):
            if month == 0:
                continue
            monthly_revenue = arpu * Decimal(str(ret_rate))
            ltv += monthly_revenue

        # Calculate average lifetime
        avg_lifetime = sum(monthly_retention) if monthly_retention else 0

        return {
            "cohort_id": cohort_id,
            "ltv": float(ltv),
            "average_lifetime_months": avg_lifetime,
            "monthly_arpu": float(arpu),
            "monthly_retention": monthly_retention[:6]  # First 6 months
        }

    async def segment_cohorts(
        self,
        characteristic: str
    ) -> Dict[str, List[CohortData]]:
        """Segment cohorts by a characteristic"""
        segments = {}

        for cohort in self.cohorts.values():
            value = cohort.characteristics.get(characteristic, "unknown")
            if value not in segments:
                segments[value] = []
            segments[value].append(cohort)

        return segments

    async def compare_cohorts(
        self,
        cohort_ids: List[str],
        metric: str = "retention"
    ) -> Dict[str, Any]:
        """Compare multiple cohorts on a metric"""
        comparison = {}

        for cohort_id in cohort_ids:
            cohort = self.cohorts.get(cohort_id)
            if not cohort:
                continue

            if metric == "retention":
                retention = await self.calculate_retention(cohort_id)
                comparison[cohort_id] = {
                    "d1": retention.get(1, 0),
                    "d7": retention.get(7, 0),
                    "d14": retention.get(14, 0),
                    "d30": retention.get(30, 0),
                    "size": cohort.size
                }
            elif metric == "revenue":
                comparison[cohort_id] = {
                    "total": float(sum(cohort.revenue.values())),
                    "per_user": float(sum(cohort.revenue.values())) / cohort.size if cohort.size > 0 else 0,
                    "size": cohort.size
                }

        return {
            "metric": metric,
            "cohorts": comparison
        }


# =============================================================================
# DASHBOARD GENERATOR
# =============================================================================

class DashboardGenerator:
    """Generates business dashboards"""

    def __init__(
        self,
        metrics_tracker: BusinessMetricsTracker,
        cohort_analyzer: AdvancedCohortAnalyzer
    ):
        self.metrics = metrics_tracker
        self.cohorts = cohort_analyzer

    async def generate_executive_dashboard(self) -> Dict[str, Any]:
        """Generate executive summary dashboard"""
        now = datetime.utcnow()

        # Key metrics
        tvl = await self.metrics.get_current_value("tvl") or 0
        dau = await self.metrics.get_current_value("dau") or 0
        daily_volume = await self.metrics.get_current_value("daily_volume") or 0
        daily_fees = await self.metrics.get_current_value("daily_fees") or 0

        # Trends
        tvl_trend = await self.metrics.calculate_trend("tvl")
        dau_trend = await self.metrics.calculate_trend("dau")

        # Retention
        retention_summary = await self.metrics.get_metric_summary("retention_d7")

        return {
            "generated_at": now.isoformat(),
            "key_metrics": {
                "tvl": {"value": tvl, "trend": tvl_trend.get("trend")},
                "dau": {"value": dau, "trend": dau_trend.get("trend")},
                "daily_volume": daily_volume,
                "daily_fees": daily_fees,
                "fee_rate": daily_fees / daily_volume * 100 if daily_volume > 0 else 0
            },
            "retention": {
                "d7_avg": retention_summary.get("avg", 0),
                "d7_current": retention_summary.get("current", 0)
            },
            "health_status": self._calculate_health_status(tvl, dau, daily_volume)
        }

    async def generate_growth_dashboard(self) -> Dict[str, Any]:
        """Generate growth-focused dashboard"""
        # User growth
        new_users = await self.metrics.get_metric_summary("new_users", WEEKLY)
        dau_summary = await self.metrics.get_metric_summary("dau", WEEKLY)
        wau_summary = await self.metrics.get_metric_summary("wau", WEEKLY)
        mau_summary = await self.metrics.get_metric_summary("mau", MONTHLY)

        # Stickiness (DAU/MAU ratio)
        dau = await self.metrics.get_current_value("dau") or 0
        mau = await self.metrics.get_current_value("mau") or 1
        stickiness = dau / mau * 100 if mau > 0 else 0

        # Forecasts
        dau_forecast = await self.metrics.forecast_metric("dau", days_ahead=7)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "user_growth": {
                "new_users_weekly": new_users.get("current", 0),
                "new_users_change": new_users.get("change", 0),
                "dau": dau_summary.get("current", 0),
                "wau": wau_summary.get("current", 0),
                "mau": mau_summary.get("current", 0)
            },
            "engagement": {
                "stickiness": stickiness,
                "dau_wau_ratio": dau / wau_summary.get("current", 1) * 100 if wau_summary.get("current") else 0
            },
            "forecast": {
                "dau_7d": dau_forecast.get("forecasts", []),
                "trend": dau_forecast.get("trend_slope", 0)
            }
        }

    async def generate_revenue_dashboard(self) -> Dict[str, Any]:
        """Generate revenue-focused dashboard"""
        # Revenue metrics
        daily_fees = await self.metrics.get_metric_summary("daily_fees", DAILY)
        daily_volume = await self.metrics.get_metric_summary("daily_volume", DAILY)

        # ARPU
        arpu = await self.metrics.get_current_value("arpu") or 0

        # LTV (if available)
        ltv = await self.metrics.get_current_value("ltv") or 0

        # Fee breakdown by type (mock)
        fee_breakdown = {
            "swap": 0.6,
            "stake": 0.2,
            "unstake": 0.15,
            "other": 0.05
        }

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "revenue": {
                "daily_fees": daily_fees.get("current", 0),
                "daily_volume": daily_volume.get("current", 0),
                "fee_rate_bps": (
                    daily_fees.get("current", 0) / daily_volume.get("current", 1) * 10000
                    if daily_volume.get("current") else 0
                )
            },
            "unit_economics": {
                "arpu": arpu,
                "ltv": ltv,
                "ltv_cac_ratio": ltv / 50 if ltv > 0 else 0  # Assume $50 CAC
            },
            "fee_breakdown": fee_breakdown
        }

    async def generate_retention_dashboard(self) -> Dict[str, Any]:
        """Generate retention-focused dashboard"""
        # Retention metrics
        d1 = await self.metrics.get_current_value("retention_d1") or 0
        d7 = await self.metrics.get_current_value("retention_d7") or 0
        d30 = await self.metrics.get_current_value("retention_d30") or 0

        # Churn
        churn = await self.metrics.get_current_value("churn_rate") or 0

        # Retention matrix
        matrix = await self.cohorts.build_retention_matrix(period="weekly", num_cohorts=4)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "retention": {
                "d1": d1,
                "d7": d7,
                "d30": d30
            },
            "churn": {
                "monthly_rate": churn,
                "annualized": (1 - (1 - churn/100) ** 12) * 100
            },
            "retention_matrix": matrix,
            "benchmarks": {
                "d1_target": 40,
                "d7_target": 25,
                "d30_target": 15
            }
        }

    def _calculate_health_status(
        self,
        tvl: float,
        dau: float,
        volume: float
    ) -> str:
        """Calculate overall health status"""
        # Simple health calculation
        if tvl > 1_000_000 and dau > 1000 and volume > 100_000:
            return "excellent"
        elif tvl > 500_000 and dau > 500 and volume > 50_000:
            return "good"
        elif tvl > 100_000 and dau > 100 and volume > 10_000:
            return "fair"
        else:
            return "needs_attention"


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_metrics_endpoints(
    tracker: BusinessMetricsTracker,
    cohorts: AdvancedCohortAnalyzer,
    dashboard: DashboardGenerator
):
    """Create business metrics API endpoints"""
    from fastapi import APIRouter
    from pydantic import BaseModel
    from typing import Optional

    router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

    class RecordMetricRequest(BaseModel):
        metric_id: str
        value: float
        dimensions: Optional[Dict[str, str]] = None

    @router.post("/record")
    async def record_metric(request: RecordMetricRequest):
        """Record a metric value"""
        await tracker.record_metric(
            request.metric_id,
            request.value,
            request.dimensions
        )
        return {"status": "recorded"}

    @router.get("/metric/{metric_id}")
    async def get_metric(metric_id: str, period: str = "daily"):
        """Get metric summary"""
        return await tracker.get_metric_summary(metric_id, period)

    @router.get("/metric/{metric_id}/trend")
    async def get_metric_trend(metric_id: str, period: str = "daily"):
        """Get metric trend"""
        return await tracker.calculate_trend(metric_id, period)

    @router.get("/metric/{metric_id}/forecast")
    async def get_metric_forecast(metric_id: str, days: int = 7):
        """Get metric forecast"""
        return await tracker.forecast_metric(metric_id, days)

    @router.get("/dashboard/executive")
    async def get_executive_dashboard():
        """Get executive dashboard"""
        return await dashboard.generate_executive_dashboard()

    @router.get("/dashboard/growth")
    async def get_growth_dashboard():
        """Get growth dashboard"""
        return await dashboard.generate_growth_dashboard()

    @router.get("/dashboard/revenue")
    async def get_revenue_dashboard():
        """Get revenue dashboard"""
        return await dashboard.generate_revenue_dashboard()

    @router.get("/dashboard/retention")
    async def get_retention_dashboard():
        """Get retention dashboard"""
        return await dashboard.generate_retention_dashboard()

    @router.get("/cohorts/retention-matrix")
    async def get_retention_matrix(period: str = "weekly", num_cohorts: int = 8):
        """Get cohort retention matrix"""
        return await cohorts.build_retention_matrix(period, num_cohorts)

    @router.get("/cohorts/{cohort_id}/ltv")
    async def get_cohort_ltv(cohort_id: str, arpu: float = 10.0, months: int = 24):
        """Calculate LTV for a cohort"""
        return await cohorts.calculate_ltv(cohort_id, Decimal(str(arpu)), months)

    @router.get("/definitions")
    async def get_metric_definitions():
        """Get all metric definitions"""
        return [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "category": m.category.value,
                "unit": m.unit,
                "target": m.target
            }
            for m in tracker.metrics.values()
        ]

    return router
