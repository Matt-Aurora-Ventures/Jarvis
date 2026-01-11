import React, { useState, useEffect } from 'react';
import {
  Activity,
  Server,
  Database,
  Wifi,
  Cpu,
  HardDrive,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Zap,
  Globe,
} from 'lucide-react';

type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';

interface ComponentHealth {
  name: string;
  status: HealthStatus;
  latency_ms?: number;
  last_check: string;
  message?: string;
  metrics?: Record<string, number>;
}

interface SystemMetrics {
  cpu_percent: number;
  memory_percent: number;
  disk_percent: number;
  network_in_mbps: number;
  network_out_mbps: number;
}

interface SystemHealth {
  overall_status: HealthStatus;
  components: ComponentHealth[];
  metrics: SystemMetrics;
  uptime_seconds: number;
  version: string;
  last_incident?: {
    timestamp: string;
    component: string;
    message: string;
  };
}

interface SystemHealthDashboardProps {
  apiUrl?: string;
  refreshInterval?: number;
}

export const SystemHealthDashboard: React.FC<SystemHealthDashboardProps> = ({
  apiUrl = '/api/health',
  refreshInterval = 10000,
}) => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchHealth = async () => {
    try {
      const response = await fetch(`${apiUrl}/status`);
      if (!response.ok) throw new Error('Failed to fetch health status');
      const data = await response.json();
      setHealth(data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, refreshInterval);
    return () => clearInterval(interval);
  }, [apiUrl, refreshInterval]);

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  const getStatusIcon = (status: HealthStatus) => {
    switch (status) {
      case 'healthy':
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      case 'degraded':
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case 'unhealthy':
        return <XCircle className="w-5 h-5 text-red-400" />;
      default:
        return <Activity className="w-5 h-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: HealthStatus) => {
    switch (status) {
      case 'healthy':
        return 'text-green-400';
      case 'degraded':
        return 'text-yellow-400';
      case 'unhealthy':
        return 'text-red-400';
      default:
        return 'text-gray-400';
    }
  };

  const getStatusBg = (status: HealthStatus) => {
    switch (status) {
      case 'healthy':
        return 'bg-green-500/20 border-green-500/50';
      case 'degraded':
        return 'bg-yellow-500/20 border-yellow-500/50';
      case 'unhealthy':
        return 'bg-red-500/20 border-red-500/50';
      default:
        return 'bg-gray-500/20 border-gray-500/50';
    }
  };

  const getComponentIcon = (name: string) => {
    const lowerName = name.toLowerCase();
    if (lowerName.includes('database') || lowerName.includes('db')) return Database;
    if (lowerName.includes('api') || lowerName.includes('server')) return Server;
    if (lowerName.includes('websocket') || lowerName.includes('ws')) return Wifi;
    if (lowerName.includes('rpc') || lowerName.includes('solana')) return Globe;
    if (lowerName.includes('redis') || lowerName.includes('cache')) return Zap;
    return Server;
  };

  const getMetricColor = (percent: number) => {
    if (percent >= 90) return 'text-red-400';
    if (percent >= 70) return 'text-yellow-400';
    return 'text-green-400';
  };

  if (isLoading && !health) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (error && !health) {
    return (
      <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-6 text-center">
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-red-400 mb-2">Health Check Failed</h3>
        <p className="text-gray-400">{error}</p>
        <button
          onClick={fetchHealth}
          className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-red-400 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!health) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">System Health</h1>
          <p className="text-gray-400 text-sm mt-1">
            Monitor system components and performance metrics
          </p>
        </div>
        <div className="flex items-center gap-4">
          {lastUpdate && (
            <span className="text-gray-400 text-sm flex items-center gap-1">
              <Clock className="w-4 h-4" />
              Updated {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchHealth}
            disabled={isLoading}
            className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 text-gray-300 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Overall Status Banner */}
      <div className={`rounded-lg p-6 border ${getStatusBg(health.overall_status)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-full ${getStatusBg(health.overall_status)}`}>
              {getStatusIcon(health.overall_status)}
            </div>
            <div>
              <h2 className={`text-xl font-bold ${getStatusColor(health.overall_status)}`}>
                System {health.overall_status.charAt(0).toUpperCase() + health.overall_status.slice(1)}
              </h2>
              <p className="text-gray-400">
                Version {health.version} | Uptime: {formatUptime(health.uptime_seconds)}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-gray-400 text-sm">Components</p>
            <p className="text-white font-medium">
              {health.components.filter(c => c.status === 'healthy').length}/{health.components.length} Healthy
            </p>
          </div>
        </div>

        {health.last_incident && (
          <div className="mt-4 pt-4 border-t border-gray-600">
            <p className="text-gray-400 text-sm">
              Last Incident: {health.last_incident.component} - {health.last_incident.message}
              <span className="text-gray-500 ml-2">
                ({new Date(health.last_incident.timestamp).toLocaleString()})
              </span>
            </p>
          </div>
        )}
      </div>

      {/* System Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Cpu className="w-4 h-4" />
            CPU
          </div>
          <p className={`text-2xl font-bold ${getMetricColor(health.metrics.cpu_percent)}`}>
            {health.metrics.cpu_percent.toFixed(1)}%
          </p>
          <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                health.metrics.cpu_percent >= 90 ? 'bg-red-500' :
                health.metrics.cpu_percent >= 70 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${health.metrics.cpu_percent}%` }}
            />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Server className="w-4 h-4" />
            Memory
          </div>
          <p className={`text-2xl font-bold ${getMetricColor(health.metrics.memory_percent)}`}>
            {health.metrics.memory_percent.toFixed(1)}%
          </p>
          <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                health.metrics.memory_percent >= 90 ? 'bg-red-500' :
                health.metrics.memory_percent >= 70 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${health.metrics.memory_percent}%` }}
            />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <HardDrive className="w-4 h-4" />
            Disk
          </div>
          <p className={`text-2xl font-bold ${getMetricColor(health.metrics.disk_percent)}`}>
            {health.metrics.disk_percent.toFixed(1)}%
          </p>
          <div className="mt-2 h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${
                health.metrics.disk_percent >= 90 ? 'bg-red-500' :
                health.metrics.disk_percent >= 70 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${health.metrics.disk_percent}%` }}
            />
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Wifi className="w-4 h-4" />
            Net In
          </div>
          <p className="text-2xl font-bold text-blue-400">
            {health.metrics.network_in_mbps.toFixed(1)}
          </p>
          <p className="text-gray-500 text-sm">Mbps</p>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Wifi className="w-4 h-4" />
            Net Out
          </div>
          <p className="text-2xl font-bold text-purple-400">
            {health.metrics.network_out_mbps.toFixed(1)}
          </p>
          <p className="text-gray-500 text-sm">Mbps</p>
        </div>
      </div>

      {/* Component Status */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-medium text-white mb-4">Component Status</h3>
        <div className="grid gap-3">
          {health.components.map((component) => {
            const Icon = getComponentIcon(component.name);
            return (
              <div
                key={component.name}
                className={`flex items-center justify-between p-4 rounded-lg border ${getStatusBg(component.status)}`}
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-gray-700 rounded-lg">
                    <Icon className="w-5 h-5 text-gray-300" />
                  </div>
                  <div>
                    <h4 className="text-white font-medium">{component.name}</h4>
                    {component.message && (
                      <p className="text-gray-400 text-sm">{component.message}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {component.latency_ms !== undefined && (
                    <div className="text-right">
                      <p className="text-gray-400 text-sm">Latency</p>
                      <p className={`font-medium ${
                        component.latency_ms > 1000 ? 'text-red-400' :
                        component.latency_ms > 500 ? 'text-yellow-400' : 'text-green-400'
                      }`}>
                        {component.latency_ms}ms
                      </p>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    {getStatusIcon(component.status)}
                    <span className={`font-medium ${getStatusColor(component.status)}`}>
                      {component.status.charAt(0).toUpperCase() + component.status.slice(1)}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default SystemHealthDashboard;
