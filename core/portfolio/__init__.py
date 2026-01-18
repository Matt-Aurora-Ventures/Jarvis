"""
JARVIS Portfolio Management

Track portfolio positions, P&L, and performance analytics.
Includes tax reporting, multi-wallet aggregation, and portfolio optimization.

Prompts #107-108: Portfolio Tracking
Prompts #293: Multi-Asset Support and Portfolio Optimization
"""

from .tracker import (
    PortfolioTracker,
    Portfolio,
    Position,
    Transaction,
    TransactionType,
    get_portfolio_tracker,
)
from .performance import (
    PerformanceAnalyzer,
    PerformanceMetrics,
    TimeFrame,
)
from .tax_reporting import (
    TaxReportGenerator,
    TaxReportingService,
    TaxYearSummary,
    TaxLot,
    CapitalGain,
    TaxableIncome,
    CostBasisMethod,
    GainType,
    IncomeType,
    get_tax_service,
)
from .correlation import (
    CorrelationMatrix,
    CorrelationResult,
    get_correlation_matrix,
)
from .optimizer import (
    PortfolioOptimizer,
    OptimizationResult,
    FrontierPoint,
    get_portfolio_optimizer,
)
from .risk_calculator import (
    MultiAssetRiskCalculator,
    RiskMetrics,
    get_risk_calculator,
)
from .rebalancer import (
    Rebalancer,
    RebalanceTrade,
    RebalanceResult,
    get_rebalancer,
)
from .sector_rotation import (
    SectorRotation,
    SectorAllocation,
    get_sector_rotation,
)

__all__ = [
    # Tracker
    "PortfolioTracker",
    "Portfolio",
    "Position",
    "Transaction",
    "TransactionType",
    "get_portfolio_tracker",
    # Performance
    "PerformanceAnalyzer",
    "PerformanceMetrics",
    "TimeFrame",
    # Tax Reporting
    "TaxReportGenerator",
    "TaxReportingService",
    "TaxYearSummary",
    "TaxLot",
    "CapitalGain",
    "TaxableIncome",
    "CostBasisMethod",
    "GainType",
    "IncomeType",
    "get_tax_service",
    # Correlation (NEW)
    "CorrelationMatrix",
    "CorrelationResult",
    "get_correlation_matrix",
    # Optimizer (NEW)
    "PortfolioOptimizer",
    "OptimizationResult",
    "FrontierPoint",
    "get_portfolio_optimizer",
    # Risk Calculator (NEW)
    "MultiAssetRiskCalculator",
    "RiskMetrics",
    "get_risk_calculator",
    # Rebalancer (NEW)
    "Rebalancer",
    "RebalanceTrade",
    "RebalanceResult",
    "get_rebalancer",
    # Sector Rotation (NEW)
    "SectorRotation",
    "SectorAllocation",
    "get_sector_rotation",
]
