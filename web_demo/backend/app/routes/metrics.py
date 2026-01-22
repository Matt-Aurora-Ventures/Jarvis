"""
Metrics API Routes
Exposes performance metrics and system health data.
"""
from fastapi import APIRouter, Response
from typing import Dict
import logging

from app.middleware.metrics_collector import get_metrics_collector

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("/summary")
async def get_metrics_summary() -> Dict:
    """
    Get comprehensive metrics summary.

    Returns:
        - Uptime
        - Total requests and errors
        - Global error rate
        - Time-window metrics (1min, 5min, 15min, all-time)
        - Per-endpoint statistics

    Example:
        GET /api/v1/metrics/summary
    """
    metrics = get_metrics_collector()
    return metrics.get_metrics_summary()


@router.get("/endpoints")
async def get_endpoint_metrics() -> Dict[str, Dict]:
    """
    Get per-endpoint performance metrics.

    Returns:
        Dictionary mapping each endpoint to its statistics:
        - Total requests
        - Error count and rate
        - Average, min, max duration
        - Last request timestamp

    Example:
        GET /api/v1/metrics/endpoints
    """
    metrics = get_metrics_collector()
    return metrics.get_endpoint_stats()


@router.get("/health")
async def get_health_metrics() -> Dict:
    """
    Get system health metrics.

    Returns:
        - Status (healthy/degraded/unhealthy)
        - Error rate
        - Average response time
        - Requests per minute
        - Uptime

    Status determination:
    - healthy: error_rate < 5%, avg_duration < 1000ms
    - degraded: error_rate < 10%, avg_duration < 3000ms
    - unhealthy: error_rate >= 10% or avg_duration >= 3000ms
    """
    metrics = get_metrics_collector()
    summary = metrics.get_metrics_summary()

    # Get recent metrics (last 5 minutes)
    recent = summary["last_5_minutes"]

    # Determine health status
    error_rate = recent["error_rate"]
    avg_duration = recent["avg_duration_ms"]

    if error_rate < 5 and avg_duration < 1000:
        status = "healthy"
        status_code = 200
    elif error_rate < 10 and avg_duration < 3000:
        status = "degraded"
        status_code = 200
    else:
        status = "unhealthy"
        status_code = 503  # Service Unavailable

    return {
        "status": status,
        "status_code": status_code,
        "uptime_hours": summary["uptime_hours"],
        "total_requests": summary["total_requests"],
        "error_rate_percent": error_rate,
        "avg_response_time_ms": avg_duration,
        "requests_per_minute": recent["requests_per_minute"],
        "last_5_minutes": recent
    }


@router.get("/prometheus", response_class=Response)
async def get_prometheus_metrics():
    """
    Get metrics in Prometheus format.

    Returns:
        Prometheus-compatible metrics text

    Example:
        GET /api/v1/metrics/prometheus

    Use with Prometheus scraper:
        - job_name: 'jarvis-web-demo'
          static_configs:
            - targets: ['localhost:8000']
          metrics_path: '/api/v1/metrics/prometheus'
    """
    metrics = get_metrics_collector()
    prom_text = metrics.to_prometheus()
    return Response(content=prom_text, media_type="text/plain")


@router.post("/reset")
async def reset_metrics() -> Dict:
    """
    Reset all metrics (admin only, use with caution).

    Returns:
        Confirmation message

    Note: This endpoint should be protected with admin authentication
    """
    metrics = get_metrics_collector()
    metrics.reset()
    logger.warning("Metrics were reset via API")
    return {
        "status": "success",
        "message": "All metrics have been reset"
    }


@router.get("/realtime")
async def get_realtime_metrics() -> Dict:
    """
    Get real-time metrics for dashboard display.

    Optimized for frontend polling (every 5-10 seconds).

    Returns:
        - Current status
        - Recent requests (last 1 minute)
        - Top endpoints by traffic
        - Top endpoints by errors
        - Top slowest endpoints
    """
    metrics = get_metrics_collector()
    summary = metrics.get_metrics_summary()
    endpoint_stats = summary["endpoints"]

    # Sort endpoints
    endpoints_list = [
        {"endpoint": k, **v}
        for k, v in endpoint_stats.items()
    ]

    # Top by traffic
    top_traffic = sorted(
        endpoints_list,
        key=lambda x: x["total_requests"],
        reverse=True
    )[:10]

    # Top by errors
    top_errors = sorted(
        [e for e in endpoints_list if e["total_errors"] > 0],
        key=lambda x: x["total_errors"],
        reverse=True
    )[:10]

    # Slowest endpoints
    slowest = sorted(
        endpoints_list,
        key=lambda x: x["avg_duration_ms"],
        reverse=True
    )[:10]

    return {
        "status": summary["last_1_minute"]["error_rate"] < 10,
        "timestamp": summary["last_1_minute"],
        "uptime_hours": summary["uptime_hours"],
        "total_requests": summary["total_requests"],
        "total_errors": summary["total_errors"],
        "last_1_minute": summary["last_1_minute"],
        "last_5_minutes": summary["last_5_minutes"],
        "top_traffic": top_traffic,
        "top_errors": top_errors,
        "slowest_endpoints": slowest
    }
