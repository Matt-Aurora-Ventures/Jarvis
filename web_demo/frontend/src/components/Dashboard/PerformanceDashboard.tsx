/**
 * Performance Monitoring Dashboard
 * Real-time system health and performance metrics visualization.
 */
import React from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Zap,
  RefreshCw,
  Pause,
  Play
} from 'lucide-react';
import clsx from 'clsx';
import { useMetrics } from '../../hooks/useMetrics';
import { GlassCard } from '../UI/GlassCard';

export const PerformanceDashboard: React.FC = () => {
  const { metrics, health, loading, error, refresh, toggleAutoRefresh, isAutoRefresh } = useMetrics(5000);

  const getStatusBadge = () => {
    if (!health) return null;

    const statusConfig = {
      healthy: { color: 'bg-success/20 text-success', icon: CheckCircle },
      degraded: { color: 'bg-warning/20 text-warning', icon: AlertTriangle },
      unhealthy: { color: 'bg-error/20 text-error', icon: AlertTriangle }
    };

    const config = statusConfig[health.status];
    const Icon = config.icon;

    return (
      <div className={clsx('px-3 py-1 rounded-full text-sm font-semibold flex items-center gap-2', config.color)}>
        <Icon size={16} />
        {health.status.toUpperCase()}
      </div>
    );
  };

  const formatUptime = (hours: number) => {
    if (hours < 1) {
      return `${Math.floor(hours * 60)}m`;
    } else if (hours < 24) {
      return `${hours.toFixed(1)}h`;
    } else {
      const days = Math.floor(hours / 24);
      const remainingHours = Math.floor(hours % 24);
      return `${days}d ${remainingHours}h`;
    }
  };

  const formatDuration = (ms: number) => {
    if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  if (error) {
    return (
      <Glass

Card className="p-6">
        <div className="text-error">Error loading metrics: {error}</div>
      </GlassCard>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-display font-bold">Performance Monitor</h1>
          <p className="text-muted mt-1">Real-time system health and API metrics</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleAutoRefresh}
            className={clsx(
              'btn flex items-center gap-2',
              isAutoRefresh ? 'btn-secondary' : 'btn-primary'
            )}
          >
            {isAutoRefresh ? <Pause size={16} /> : <Play size={16} />}
            {isAutoRefresh ? 'Pause' : 'Resume'}
          </button>
          <button onClick={refresh} className="btn btn-secondary flex items-center gap-2">
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <GlassCard className="p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">Status</span>
            <Activity className="text-accent" size={20} />
          </div>
          {getStatusBadge()}
        </GlassCard>

        <GlassCard className="p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">Uptime</span>
            <Clock className="text-info" size={20} />
          </div>
          <div className="text-2xl font-bold">
            {health ? formatUptime(health.uptime_hours) : '-'}
          </div>
        </GlassCard>

        <GlassCard className="p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">Requests/Min</span>
            <TrendingUp className="text-success" size={20} />
          </div>
          <div className="text-2xl font-bold">
            {metrics ? metrics.last_1_minute.requests_per_minute.toFixed(1) : '-'}
          </div>
        </GlassCard>

        <GlassCard className="p-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-muted">Error Rate</span>
            {metrics && metrics.last_5_minutes.error_rate > 5 ? (
              <AlertTriangle className="text-error" size={20} />
            ) : (
              <CheckCircle className="text-success" size={20} />
            )}
          </div>
          <div className={clsx(
            'text-2xl font-bold',
            metrics && metrics.last_5_minutes.error_rate > 10 ? 'text-error' :
            metrics && metrics.last_5_minutes.error_rate > 5 ? 'text-warning' :
            'text-success'
          )}>
            {metrics ? `${metrics.last_5_minutes.error_rate.toFixed(2)}%` : '-'}
          </div>
        </GlassCard>
      </div>

      {/* Detailed Metrics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Time Windows */}
        <GlassCard>
          <div className="p-6 border-b border-border">
            <h3 className="text-xl font-semibold">Response Times</h3>
          </div>
          <div className="p-6 space-y-4">
            {metrics && [
              { label: 'Last 1 Minute', data: metrics.last_1_minute },
              { label: 'Last 5 Minutes', data: metrics.last_5_minutes }
            ].map(({ label, data }) => (
              <div key={label} className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted">{label}</span>
                  <span className="font-semibold">{formatDuration(data.avg_duration_ms)}</span>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-muted">Min</span>
                      <span>{formatDuration(data.min_duration_ms)}</span>
                    </div>
                    <div className="h-1 bg-surface rounded-full overflow-hidden">
                      <div
                        className="h-full bg-success"
                        style={{ width: `${Math.min((data.min_duration_ms / data.max_duration_ms) * 100, 100)}%` }}
                      />
                    </div>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-muted">Max</span>
                      <span>{formatDuration(data.max_duration_ms)}</span>
                    </div>
                    <div className="h-1 bg-surface rounded-full overflow-hidden">
                      <div className="h-full bg-error" style={{ width: '100%' }} />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </GlassCard>

        {/* Request Statistics */}
        <GlassCard>
          <div className="p-6 border-b border-border">
            <h3 className="text-xl font-semibold">Request Statistics</h3>
          </div>
          <div className="p-6 space-y-4">
            {metrics && (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Total Requests</span>
                  <span className="text-2xl font-bold">{metrics.total_requests.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Total Errors</span>
                  <span className="text-2xl font-bold text-error">{metrics.total_errors.toLocaleString()}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">Success Rate</span>
                  <span className="text-2xl font-bold text-success">
                    {((1 - metrics.total_errors / metrics.total_requests) * 100).toFixed(2)}%
                  </span>
                </div>
              </>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Top Endpoints */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top Traffic */}
        <GlassCard>
          <div className="p-6 border-b border-border flex items-center gap-2">
            <TrendingUp size={20} className="text-accent" />
            <h3 className="text-lg font-semibold">Top Traffic</h3>
          </div>
          <div className="p-6">
            {metrics && metrics.top_traffic.length > 0 ? (
              <div className="space-y-3">
                {metrics.top_traffic.slice(0, 5).map((endpoint, idx) => (
                  <div key={endpoint.endpoint} className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-mono truncate">{endpoint.endpoint}</div>
                      <div className="text-xs text-muted">{formatDuration(endpoint.avg_duration_ms)} avg</div>
                    </div>
                    <div className="text-sm font-semibold ml-2">{endpoint.total_requests}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted text-center py-4">No data available</div>
            )}
          </div>
        </GlassCard>

        {/* Slowest Endpoints */}
        <GlassCard>
          <div className="p-6 border-b border-border flex items-center gap-2">
            <Clock size={20} className="text-warning" />
            <h3 className="text-lg font-semibold">Slowest Endpoints</h3>
          </div>
          <div className="p-6">
            {metrics && metrics.slowest_endpoints.length > 0 ? (
              <div className="space-y-3">
                {metrics.slowest_endpoints.slice(0, 5).map((endpoint) => (
                  <div key={endpoint.endpoint} className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-mono truncate">{endpoint.endpoint}</div>
                      <div className="text-xs text-muted">{endpoint.total_requests} requests</div>
                    </div>
                    <div className="text-sm font-semibold ml-2 text-warning">
                      {formatDuration(endpoint.avg_duration_ms)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-muted text-center py-4">No data available</div>
            )}
          </div>
        </GlassCard>

        {/* Errors */}
        <GlassCard>
          <div className="p-6 border-b border-border flex items-center gap-2">
            <AlertTriangle size={20} className="text-error" />
            <h3 className="text-lg font-semibold">Most Errors</h3>
          </div>
          <div className="p-6">
            {metrics && metrics.top_errors.length > 0 ? (
              <div className="space-y-3">
                {metrics.top_errors.slice(0, 5).map((endpoint) => (
                  <div key={endpoint.endpoint} className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-mono truncate">{endpoint.endpoint}</div>
                      <div className="text-xs text-muted">{endpoint.error_rate.toFixed(2)}% error rate</div>
                    </div>
                    <div className="text-sm font-semibold ml-2 text-error">{endpoint.total_errors}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-success text-center py-4">No errors!</div>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
};
