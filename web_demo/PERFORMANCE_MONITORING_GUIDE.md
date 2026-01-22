# Performance Monitoring - Complete Guide

## Overview

The JARVIS Web Demo includes **real-time performance monitoring** with comprehensive metrics collection, visualization, and alerting. Track API performance, error rates, and system health in real-time.

## Architecture

```
┌──────────────────┐
│  HTTP Requests   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Metrics Middleware│──> Record every request
└────────┬─────────┘       - Duration
         │                 - Status code
         │                 - Endpoint
         │                 - Errors
         ▼
┌──────────────────┐
│ Metrics Collector │──> Aggregate stats
└────────┬─────────┘       - Per-endpoint
         │                 - Time windows
         │                 - System-wide
         ▼
┌──────────────────┐
│  REST API        │──> Expose metrics
└────────┬─────────┘       - /metrics/summary
         │                 - /metrics/realtime
         │                 - /metrics/health
         │                 - /metrics/prometheus
         ▼
┌──────────────────┐
│ Frontend Dashboard│──> Visualize
└──────────────────┘       - Real-time charts
                           - Endpoint stats
                           - Health status
                           - Auto-refresh
```

## Features

### Backend

- ✅ **Automatic Collection**: Middleware records all requests
- ✅ **Time Windows**: 1min, 5min, 15min, all-time metrics
- ✅ **Per-Endpoint Stats**: Individual endpoint performance
- ✅ **Prometheus Export**: Compatible with Prometheus monitoring
- ✅ **Health Checks**: System health determination
- ✅ **Slow Request Logging**: Automatic warnings for >1s requests

### Frontend

- ✅ **Real-Time Dashboard**: Live metrics with auto-refresh
- ✅ **Status Overview**: Health, uptime, request rate, error rate
- ✅ **Response Time Tracking**: Min, max, average durations
- ✅ **Top Endpoints**: By traffic, errors, slowness
- ✅ **Auto-Refresh**: Configurable polling (default 5s)
- ✅ **Pause/Resume**: Control data updates

## Backend Setup

### 1. Metrics Collection

The metrics system is automatically enabled when the app starts via [`backend/app/main.py:123`](backend/app/main.py#L123):

```python
# Metrics collection
from app.middleware.metrics_middleware import MetricsMiddleware
app.add_middleware(MetricsMiddleware)
```

No manual setup required - all HTTP requests are automatically tracked.

### 2. API Endpoints

All endpoints are prefixed with `/api/v1/metrics`:

#### **GET /api/v1/metrics/summary**
Get comprehensive metrics summary.

**Response**:
```json
{
  "uptime_seconds": 3661.45,
  "uptime_hours": 1.02,
  "total_requests": 1523,
  "total_errors": 8,
  "global_error_rate": 0.53,
  "last_1_minute": {
    "total_requests": 25,
    "total_errors": 0,
    "error_rate": 0.0,
    "avg_duration_ms": 42.3,
    "min_duration_ms": 12.1,
    "max_duration_ms": 156.7,
    "requests_per_minute": 25.0
  },
  "last_5_minutes": {...},
  "last_15_minutes": {...},
  "all_time": {...},
  "endpoints": {
    "/api/v1/transactions": {
      "total_requests": 342,
      "total_errors": 2,
      "error_rate": 0.58,
      "avg_duration_ms": 45.2,
      "min_duration_ms": 15.3,
      "max_duration_ms": 234.1,
      "last_request": "2026-01-22T14:30:00Z"
    }
  }
}
```

#### **GET /api/v1/metrics/health**
Get system health status.

**Response**:
```json
{
  "status": "healthy",
  "status_code": 200,
  "uptime_hours": 1.02,
  "total_requests": 1523,
  "error_rate_percent": 0.53,
  "avg_response_time_ms": 42.3,
  "requests_per_minute": 25.0,
  "last_5_minutes": {...}
}
```

**Status Determination**:
- `healthy`: error_rate < 5%, avg_duration < 1000ms
- `degraded`: error_rate < 10%, avg_duration < 3000ms
- `unhealthy`: error_rate >= 10% or avg_duration >= 3000ms

#### **GET /api/v1/metrics/realtime**
Get real-time metrics optimized for dashboard polling.

**Response**:
```json
{
  "status": true,
  "uptime_hours": 1.02,
  "total_requests": 1523,
  "total_errors": 8,
  "last_1_minute": {...},
  "last_5_minutes": {...},
  "top_traffic": [
    {
      "endpoint": "/api/v1/transactions",
      "total_requests": 342,
      "total_errors": 2,
      "error_rate": 0.58,
      "avg_duration_ms": 45.2
    }
  ],
  "top_errors": [...],
  "slowest_endpoints": [...]
}
```

#### **GET /api/v1/metrics/endpoints**
Get per-endpoint statistics.

#### **GET /api/v1/metrics/prometheus**
Export metrics in Prometheus format.

**Response** (text/plain):
```
# HELP jarvis_requests_total Total number of requests
# TYPE jarvis_requests_total counter
jarvis_requests_total 1523

# HELP jarvis_errors_total Total number of errors
# TYPE jarvis_errors_total counter
jarvis_errors_total 8

# HELP jarvis_endpoint_requests_total Requests per endpoint
# TYPE jarvis_endpoint_requests_total counter
jarvis_endpoint_requests_total{endpoint="/api/v1/transactions"} 342

# HELP jarvis_endpoint_duration_seconds Request duration per endpoint
# TYPE jarvis_endpoint_duration_seconds histogram
jarvis_endpoint_duration_seconds_sum{endpoint="/api/v1/transactions"} 15.46
jarvis_endpoint_duration_seconds_count{endpoint="/api/v1/transactions"} 342
```

#### **POST /api/v1/metrics/reset**
Reset all metrics (admin only, use with caution).

## Frontend Usage

### 1. Using the PerformanceDashboard Component

```typescript
import { PerformanceDashboard } from './components/Dashboard';

const AdminPanel = () => {
  return (
    <div>
      <h1>System Administration</h1>
      <PerformanceDashboard />
    </div>
  );
};
```

### 2. Using the Hook Directly

```typescript
import { useMetrics } from '../hooks/useMetrics';

const CustomMonitor = () => {
  const { metrics, health, loading, refresh, toggleAutoRefresh, isAutoRefresh } = useMetrics(5000);

  return (
    <div>
      {health && (
        <div>
          Status: {health.status}
          Error Rate: {health.error_rate_percent}%
          Avg Response: {health.avg_response_time_ms}ms
        </div>
      )}
    </div>
  );
};
```

### 3. Custom Refresh Interval

```typescript
// Refresh every 10 seconds instead of 5
const { metrics } = useMetrics(10000);
```

## Monitored Metrics

### System-Wide Metrics

| Metric | Description |
|--------|-------------|
| Uptime | Time since server started |
| Total Requests | All HTTP requests processed |
| Total Errors | Requests with 4xx/5xx status codes |
| Global Error Rate | Percentage of failed requests |
| Requests Per Minute | Current request rate |

### Per-Endpoint Metrics

| Metric | Description |
|--------|-------------|
| Total Requests | Requests to this endpoint |
| Total Errors | Failed requests |
| Error Rate | Percentage of failures |
| Avg Duration | Average response time |
| Min Duration | Fastest response |
| Max Duration | Slowest response |
| Last Request | Timestamp of last request |

### Time Windows

Metrics are aggregated across multiple time windows:
- **Last 1 Minute**: Very recent performance
- **Last 5 Minutes**: Short-term trends
- **Last 15 Minutes**: Medium-term trends
- **All Time**: Since server start

## Performance Considerations

### Metrics Collection Overhead

- **Memory**: ~5MB for 10,000 recent requests
- **CPU**: <0.1% overhead per request
- **Latency**: <0.1ms added to each request

### Dashboard Refresh Rate

Default: 5 seconds (configurable)

**Recommendations**:
- Production: 10-30 seconds
- Development: 5 seconds
- Critical monitoring: 1-2 seconds

### History Limits

By default, the collector keeps the last 10,000 requests in memory. Older requests are automatically discarded.

To adjust:
```python
metrics = MetricsCollector(max_history=50000)
```

## Prometheus Integration

### 1. Configure Prometheus

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'jarvis-web-demo'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/v1/metrics/prometheus'
    scrape_interval: 15s
```

### 2. Start Prometheus

```bash
prometheus --config.file=prometheus.yml
```

### 3. Query Metrics

```promql
# Total requests
jarvis_requests_total

# Request rate (per second)
rate(jarvis_requests_total[5m])

# Error rate
rate(jarvis_errors_total[5m]) / rate(jarvis_requests_total[5m])

# Average duration per endpoint
jarvis_endpoint_duration_seconds_sum / jarvis_endpoint_duration_seconds_count
```

## Alerting

### Health-Based Alerts

The `/health` endpoint returns:
- 200 if healthy/degraded
- 503 if unhealthy

Use this for uptime monitoring:

```bash
# Check every 60s
curl -f http://localhost:8000/api/v1/metrics/health || alert
```

### Custom Alerts

Query the `/realtime` endpoint and alert on conditions:

```typescript
const { metrics } = useMetrics();

if (metrics && metrics.last_5_minutes.error_rate > 10) {
  sendAlert('High error rate detected!');
}

if (metrics && metrics.last_5_minutes.avg_duration_ms > 3000) {
  sendAlert('Slow response times detected!');
}
```

## Troubleshooting

### Metrics Not Updating

1. **Check middleware is enabled**:
   ```bash
   grep "MetricsMiddleware" backend/app/main.py
   ```

2. **Verify endpoints are accessible**:
   ```bash
   curl http://localhost:8000/api/v1/metrics/health
   ```

3. **Check backend logs** for middleware errors

### Dashboard Shows "No Data"

1. **Make some requests** to generate metrics:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/api/v1/transactions
   ```

2. **Check API connectivity**:
   ```bash
   curl http://localhost:8000/api/v1/metrics/realtime
   ```

3. **Verify CORS settings** allow frontend to access metrics endpoints

### Slow Dashboard Updates

1. **Increase refresh interval**:
   ```typescript
   const { metrics } = useMetrics(10000); // 10 seconds
   ```

2. **Pause auto-refresh** when not actively monitoring:
   - Click "Pause" button in dashboard

3. **Check network latency** between frontend and backend

## Monitoring Best Practices

### 1. Set Up Baseline

Monitor your app under normal load to establish baselines:
- Normal error rate
- Typical response times
- Expected request rate

### 2. Define Thresholds

Based on baselines, set alert thresholds:
- Error rate > 5% = warning
- Error rate > 10% = critical
- Avg response time > 1s = warning
- Avg response time > 3s = critical

### 3. Regular Review

- **Daily**: Check error trends
- **Weekly**: Review slowest endpoints
- **Monthly**: Analyze long-term performance trends

### 4. Correlate with Changes

When metrics degrade:
- Check recent deployments
- Review code changes
- Examine database performance
- Check external API status

## API Reference

See [`backend/app/routes/metrics.py`](backend/app/routes/metrics.py) for complete API implementation.

## Future Enhancements

Planned for next iterations:
- [ ] Grafana dashboard templates
- [ ] Historical data persistence (database storage)
- [ ] Email/Slack alerting
- [ ] Performance regression detection
- [ ] Load testing integration
- [ ] Custom metric tags
- [ ] Distributed tracing integration
- [ ] Resource usage tracking (CPU, memory)
- [ ] Database query performance monitoring

---

**Questions?** Check the main documentation at [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
