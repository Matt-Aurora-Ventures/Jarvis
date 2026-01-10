"""
JARVIS Portfolio Management

Track portfolio positions, P&L, and performance analytics.
Includes tax reporting and multi-wallet aggregation.

Prompts #107-108: Portfolio Tracking
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
]
