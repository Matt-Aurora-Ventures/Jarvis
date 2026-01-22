/**
 * Metrics Types
 * TypeScript interfaces for performance metrics
 */

export interface TimeWindowMetrics {
  total_requests: number;
  total_errors: number;
  error_rate: number;
  avg_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
  requests_per_minute: number;
}

export interface EndpointStats {
  total_requests: number;
  total_errors: number;
  error_rate: number;
  avg_duration_ms: number;
  min_duration_ms: number;
  max_duration_ms: number;
  last_request: string | null;
}

export interface MetricsSummary {
  uptime_seconds: number;
  uptime_hours: number;
  total_requests: number;
  total_errors: number;
  global_error_rate: number;
  last_1_minute: TimeWindowMetrics;
  last_5_minutes: TimeWindowMetrics;
  last_15_minutes: TimeWindowMetrics;
  all_time: TimeWindowMetrics;
  endpoints: Record<string, EndpointStats>;
}

export interface HealthMetrics {
  status: 'healthy' | 'degraded' | 'unhealthy';
  status_code: number;
  uptime_hours: number;
  total_requests: number;
  error_rate_percent: number;
  avg_response_time_ms: number;
  requests_per_minute: number;
  last_5_minutes: TimeWindowMetrics;
}

export interface EndpointMetric {
  endpoint: string;
  total_requests: number;
  total_errors: number;
  error_rate: number;
  avg_duration_ms: number;
}

export interface RealtimeMetrics {
  status: boolean;
  timestamp: TimeWindowMetrics;
  uptime_hours: number;
  total_requests: number;
  total_errors: number;
  last_1_minute: TimeWindowMetrics;
  last_5_minutes: TimeWindowMetrics;
  top_traffic: EndpointMetric[];
  top_errors: EndpointMetric[];
  slowest_endpoints: EndpointMetric[];
}
