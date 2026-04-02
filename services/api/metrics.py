"""
Metrics API Endpoints.

Provides REST API endpoints for metrics:
- GET /metrics - Prometheus format
- GET /metrics/json - JSON format

Authentication via API key (header or query param).
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Header, Query, Depends
from fastapi.responses import PlainTextResponse, JSONResponse

from core.metrics.exporter import PrometheusExporter
from core.metrics.aggregator import MetricsAggregator

logger = logging.getLogger(__name__)


def create_metrics_router(
    exporter: PrometheusExporter,
    api_key: str,
    prefix: str = "",
) -> APIRouter:
    """
    Create a FastAPI router for metrics endpoints.

    Args:
        exporter: PrometheusExporter instance
        api_key: Required API key for authentication
        prefix: URL prefix for the router

    Returns:
        APIRouter with /metrics and /metrics/json endpoints
    """
    router = APIRouter(prefix=prefix, tags=["metrics"])

    async def verify_api_key(
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
        query_api_key: Optional[str] = Query(None, alias="api_key"),
    ) -> str:
        """
        Verify API key from header or query parameter.

        Raises:
            HTTPException: If API key is missing or invalid
        """
        provided_key = x_api_key or query_api_key

        if not provided_key:
            raise HTTPException(
                status_code=401,
                detail="Missing API key. Provide via X-API-Key header or api_key query param",
            )

        if provided_key != api_key:
            logger.warning("Invalid API key attempt for metrics endpoint")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key",
            )

        return provided_key

    @router.get("/metrics", response_class=PlainTextResponse)
    async def get_metrics_prometheus(
        _key: str = Depends(verify_api_key),
    ) -> PlainTextResponse:
        """
        Get metrics in Prometheus text format.

        Returns:
            PlainTextResponse with Prometheus-formatted metrics
        """
        try:
            content = exporter.export()
            return PlainTextResponse(
                content=content,
                media_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error exporting Prometheus metrics: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error generating metrics",
            )

    @router.get("/metrics/json")
    async def get_metrics_json(
        _key: str = Depends(verify_api_key),
    ) -> Dict[str, Any]:
        """
        Get metrics in JSON format.

        Returns:
            JSON object with bot metrics and aggregates
        """
        try:
            # Get per-bot stats
            bots: Dict[str, Dict[str, Any]] = {}
            total_received = 0
            total_sent = 0
            total_commands = 0
            total_errors = 0

            for source in exporter.aggregator.sources:
                stats = source.get_stats()
                bots[source.bot_name] = {
                    "messages_received": stats["messages_received"],
                    "messages_sent": stats["messages_sent"],
                    "commands_processed": stats["commands_processed"],
                    "errors_total": stats["errors_total"],
                    "response_times_count": stats["response_times_count"],
                    "avg_response_time": stats["avg_response_time"],
                }

                total_received += stats["messages_received"]
                total_sent += stats["messages_sent"]
                total_commands += stats["commands_processed"]
                total_errors += stats["errors_total"]

            # Calculate aggregate percentiles
            p50, p95, p99 = exporter.aggregator.get_percentiles("response_times")

            return {
                "bots": bots,
                "totals": {
                    "total_messages_received": total_received,
                    "total_messages_sent": total_sent,
                    "total_commands": total_commands,
                    "total_errors": total_errors,
                    "p50_response_time": p50,
                    "p95_response_time": p95,
                    "p99_response_time": p99,
                },
            }

        except Exception as e:
            logger.error(f"Error generating JSON metrics: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error generating metrics",
            )

    return router
