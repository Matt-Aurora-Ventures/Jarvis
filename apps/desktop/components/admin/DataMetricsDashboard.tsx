import React, { useState, useEffect } from 'react';
import {
  Database,
  Users,
  Shield,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';

interface ConsentDistribution {
  tier_0_none: number;
  tier_1_anonymous: number;
  tier_2_pseudonymous: number;
  tier_3_full: number;
  total_users: number;
  opt_in_rate: number;
}

interface QualityMetrics {
  completeness: number;
  accuracy: number;
  freshness: number;
  consistency: number;
  overall: number;
}

interface CollectionStats {
  total_records: number;
  records_last_hour: number;
  records_last_day: number;
  records_last_week: number;
  avg_records_per_hour: number;
  peak_hour_records: number;
  unique_users: number;
}

interface DataMetrics {
  collection_stats: CollectionStats;
  consent_distribution: ConsentDistribution;
  quality_metrics: QualityMetrics;
  anomaly_counts: Record<string, number>;
  health_status: {
    status: 'healthy' | 'degraded' | 'unhealthy';
    quality_score: number;
    consent_rate: number;
    collection_rate: number;
    anomaly_rate: number;
  };
}

interface DataMetricsDashboardProps {
  apiUrl?: string;
  refreshInterval?: number;
}

export const DataMetricsDashboard: React.FC<DataMetricsDashboardProps> = ({
  apiUrl = '/api/data/metrics',
  refreshInterval = 30000,
}) => {
  const [metrics, setMetrics] = useState<DataMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchMetrics = async () => {
    try {
      const response = await fetch(`${apiUrl}/summary`);
      if (!response.ok) throw new Error('Failed to fetch metrics');
      const data = await response.json();
      setMetrics(data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, refreshInterval);
    return () => clearInterval(interval);
  }, [apiUrl, refreshInterval]);

  const formatNumber = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return value.toLocaleString();
  };

  const formatPercent = (value: number) => `${(value * 100).toFixed(1)}%`;

  const getHealthColor = (status: string) => {
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

  const getQualityColor = (score: number) => {
    if (score >= 0.8) return 'text-green-400';
    if (score >= 0.5) return 'text-yellow-400';
    return 'text-red-400';
  };

  if (isLoading && !metrics) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
      </div>
    );
  }

  if (error && !metrics) {
    return (
      <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-6 text-center">
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-red-400 mb-2">Failed to Load Metrics</h3>
        <p className="text-gray-400">{error}</p>
        <button
          onClick={fetchMetrics}
          className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg text-red-400 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!metrics) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Data Collection Metrics</h1>
          <p className="text-gray-400 text-sm mt-1">
            Monitor data collection health and consent trends
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
            onClick={fetchMetrics}
            disabled={isLoading}
            className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 text-gray-300 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Health Status Banner */}
      <div className={`bg-gray-800 rounded-lg p-4 border-l-4 ${
        metrics.health_status.status === 'healthy' ? 'border-green-500' :
        metrics.health_status.status === 'degraded' ? 'border-yellow-500' : 'border-red-500'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {metrics.health_status.status === 'healthy' ? (
              <CheckCircle className="w-6 h-6 text-green-400" />
            ) : metrics.health_status.status === 'degraded' ? (
              <AlertTriangle className="w-6 h-6 text-yellow-400" />
            ) : (
              <XCircle className="w-6 h-6 text-red-400" />
            )}
            <div>
              <h3 className={`font-medium ${getHealthColor(metrics.health_status.status)}`}>
                System {metrics.health_status.status.charAt(0).toUpperCase() + metrics.health_status.status.slice(1)}
              </h3>
              <p className="text-gray-400 text-sm">
                Quality: {formatPercent(metrics.health_status.quality_score)} |
                Consent: {formatPercent(metrics.health_status.consent_rate)} |
                Anomaly: {formatPercent(metrics.health_status.anomaly_rate)}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Database className="w-4 h-4" />
            Total Records
          </div>
          <p className="text-2xl font-bold text-white">
            {formatNumber(metrics.collection_stats.total_records)}
          </p>
          <p className="text-green-400 text-sm flex items-center gap-1">
            <TrendingUp className="w-3 h-3" />
            +{formatNumber(metrics.collection_stats.records_last_day)} today
          </p>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <Users className="w-4 h-4" />
            Unique Users
          </div>
          <p className="text-2xl font-bold text-white">
            {formatNumber(metrics.collection_stats.unique_users)}
          </p>
          <p className="text-gray-400 text-sm">
            {formatPercent(metrics.consent_distribution.opt_in_rate)} opt-in
          </p>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <TrendingUp className="w-4 h-4" />
            Hourly Rate
          </div>
          <p className="text-2xl font-bold text-white">
            {formatNumber(metrics.collection_stats.avg_records_per_hour)}
          </p>
          <p className="text-gray-400 text-sm">
            Peak: {formatNumber(metrics.collection_stats.peak_hour_records)}
          </p>
        </div>

        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center gap-2 text-gray-400 text-sm mb-2">
            <AlertTriangle className="w-4 h-4" />
            Anomalies
          </div>
          <p className="text-2xl font-bold text-yellow-400">
            {Object.values(metrics.anomaly_counts).reduce((a, b) => a + b, 0)}
          </p>
          <p className="text-gray-400 text-sm">
            {Object.keys(metrics.anomaly_counts).length} types detected
          </p>
        </div>
      </div>

      {/* Consent Distribution */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5" />
          Consent Tier Distribution
        </h3>
        <div className="grid grid-cols-4 gap-4">
          {[
            { tier: 'None', count: metrics.consent_distribution.tier_0_none, color: 'bg-gray-500' },
            { tier: 'Anonymous', count: metrics.consent_distribution.tier_1_anonymous, color: 'bg-blue-500' },
            { tier: 'Pseudonymous', count: metrics.consent_distribution.tier_2_pseudonymous, color: 'bg-purple-500' },
            { tier: 'Full', count: metrics.consent_distribution.tier_3_full, color: 'bg-green-500' },
          ].map(({ tier, count, color }) => {
            const percent = metrics.consent_distribution.total_users > 0
              ? (count / metrics.consent_distribution.total_users) * 100
              : 0;
            return (
              <div key={tier} className="text-center">
                <div className="h-24 bg-gray-700 rounded-lg relative overflow-hidden">
                  <div
                    className={`absolute bottom-0 left-0 right-0 ${color} transition-all duration-500`}
                    style={{ height: `${percent}%` }}
                  />
                </div>
                <p className="text-white font-medium mt-2">{tier}</p>
                <p className="text-gray-400 text-sm">{formatNumber(count)} ({percent.toFixed(1)}%)</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Quality Metrics */}
      <div className="bg-gray-800 rounded-lg p-6">
        <h3 className="text-lg font-medium text-white mb-4">Data Quality Scores</h3>
        <div className="space-y-4">
          {[
            { name: 'Completeness', score: metrics.quality_metrics.completeness },
            { name: 'Accuracy', score: metrics.quality_metrics.accuracy },
            { name: 'Freshness', score: metrics.quality_metrics.freshness },
            { name: 'Consistency', score: metrics.quality_metrics.consistency },
          ].map(({ name, score }) => (
            <div key={name}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-400">{name}</span>
                <span className={`font-medium ${getQualityColor(score)}`}>
                  {formatPercent(score)}
                </span>
              </div>
              <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    score >= 0.8 ? 'bg-green-500' :
                    score >= 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${score * 100}%` }}
                />
              </div>
            </div>
          ))}
          <div className="pt-4 border-t border-gray-700">
            <div className="flex items-center justify-between">
              <span className="text-white font-medium">Overall Quality</span>
              <span className={`text-xl font-bold ${getQualityColor(metrics.quality_metrics.overall)}`}>
                {formatPercent(metrics.quality_metrics.overall)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataMetricsDashboard;
