"""
Treasury Reports API Routes.

Provides endpoints for treasury performance reports:
- Generate weekly/monthly reports
- List available reports
- Get specific report by ID
- Export reports in various formats
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.pagination import PaginationParams

router = APIRouter(prefix="/api/treasury/reports", tags=["Treasury Reports"])


class ReportRequest(BaseModel):
    """Request to generate a report."""
    year: Optional[int] = None
    month: Optional[int] = None


@router.get("")
async def list_reports(
    period: Optional[str] = Query(None, description="Filter by period: daily, weekly, monthly"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
):
    """
    List available treasury reports with pagination.

    Supports filtering by period (daily, weekly, monthly).
    Returns paginated results with metadata.
    """
    try:
        from core.treasury.reports import get_report_generator, ReportPeriod

        generator = get_report_generator()

        period_filter = None
        if period:
            try:
                period_filter = ReportPeriod(period)
            except ValueError:
                raise HTTPException(400, f"Invalid period: {period}")

        # Calculate offset for pagination
        offset = (page - 1) * page_size

        # Get reports with pagination applied at the source if possible
        # For now, we'll use limit to get slightly more than needed
        reports = await generator.list_reports(period=period_filter, limit=page_size * page)

        # Apply pagination to results
        total = len(reports)
        page_reports = reports[offset:offset + page_size]

        total_pages = (total + page_size - 1) // page_size

        return {
            "reports": page_reports,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(501, f"Reports module not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to list reports: {e}")


@router.get("/{report_id}")
async def get_report(report_id: str):
    """Get a specific report by ID."""
    try:
        from core.treasury.reports import get_report_generator

        generator = get_report_generator()
        report = await generator.get_report(report_id)

        if report is None:
            raise HTTPException(404, f"Report not found: {report_id}")

        return report

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(501, f"Reports module not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to get report: {e}")


@router.post("/generate/weekly")
async def generate_weekly_report():
    """Generate a weekly treasury report."""
    try:
        from core.treasury.reports import get_report_generator

        generator = get_report_generator()
        report = await generator.generate_weekly_report()

        return {
            "status": "generated",
            "report_id": report.report_id,
            "period": report.period.value,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "summary": report.summary,
        }

    except ImportError as e:
        raise HTTPException(501, f"Reports module not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to generate report: {e}")


@router.post("/generate/monthly")
async def generate_monthly_report(request: ReportRequest = None):
    """Generate a monthly treasury report."""
    try:
        from core.treasury.reports import get_report_generator

        generator = get_report_generator()

        year = request.year if request else None
        month = request.month if request else None

        report = await generator.generate_monthly_report(year=year, month=month)

        return {
            "status": "generated",
            "report_id": report.report_id,
            "period": report.period.value,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "summary": report.summary,
        }

    except ImportError as e:
        raise HTTPException(501, f"Reports module not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to generate report: {e}")


@router.get("/{report_id}/export")
async def export_report(
    report_id: str,
    format: str = Query("md", description="Export format: md, json"),
):
    """Export a report to a specific format."""
    try:
        from core.treasury.reports import get_report_generator

        generator = get_report_generator()
        report_data = await generator.get_report(report_id)

        if report_data is None:
            raise HTTPException(404, f"Report not found: {report_id}")

        # Return raw data for JSON format
        if format == "json":
            return report_data

        # For markdown, we need to regenerate the formatted output
        return {
            "format": format,
            "report_id": report_id,
            "message": "Use GET /api/treasury/reports/{report_id} for data",
        }

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(501, f"Reports module not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to export report: {e}")


@router.get("/latest/{period}")
async def get_latest_report(period: str):
    """Get the latest report for a specific period."""
    try:
        from core.treasury.reports import get_report_generator, ReportPeriod

        try:
            period_enum = ReportPeriod(period)
        except ValueError:
            raise HTTPException(400, f"Invalid period: {period}. Use: daily, weekly, monthly")

        generator = get_report_generator()
        reports = await generator.list_reports(period=period_enum, limit=1)

        if not reports:
            raise HTTPException(404, f"No {period} reports available")

        # Get full report
        report = await generator.get_report(reports[0]["id"])
        return report

    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(501, f"Reports module not available: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to get latest report: {e}")
