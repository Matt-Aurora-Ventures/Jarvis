"""
Tax Reporting Module

Provides tax reporting functionality including:
- Cost basis tracking (FIFO, LIFO, HIFO)
- Gain/loss calculation
- Wash sale detection
- Tax lot optimization
- Export to CSV/TurboTax format
"""

from core.reporting.tax_reporter import (
    TaxReporter,
    CostBasisMethod,
    TaxLot,
    SaleResult,
    WashSale,
    AnnualSummary,
    InsufficientLotsError,
)

__all__ = [
    "TaxReporter",
    "CostBasisMethod",
    "TaxLot",
    "SaleResult",
    "WashSale",
    "AnnualSummary",
    "InsufficientLotsError",
]
