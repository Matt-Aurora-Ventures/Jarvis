/**
 * Metrics API Service
 * Handles all metrics and performance monitoring API calls.
 */
import {
  MetricsSummary,
  HealthMetrics,
  RealtimeMetrics,
  EndpointStats
} from '../types/metrics';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const API_V1_PREFIX = '/api/v1';

class MetricsService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = `${API_BASE_URL}${API_V1_PREFIX}/metrics`;
  }

  /**
   * Get comprehensive metrics summary
   */
  async getSummary(): Promise<MetricsSummary> {
    const response = await fetch(`${this.baseUrl}/summary`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch metrics summary: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get per-endpoint metrics
   */
  async getEndpoints(): Promise<Record<string, EndpointStats>> {
    const response = await fetch(`${this.baseUrl}/endpoints`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch endpoint metrics: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get system health metrics
   */
  async getHealth(): Promise<HealthMetrics> {
    const response = await fetch(`${this.baseUrl}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch health metrics: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get real-time metrics for dashboard
   */
  async getRealtime(): Promise<RealtimeMetrics> {
    const response = await fetch(`${this.baseUrl}/realtime`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch realtime metrics: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get Prometheus metrics (text format)
   */
  async getPrometheus(): Promise<string> {
    const response = await fetch(`${this.baseUrl}/prometheus`, {
      method: 'GET'
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch Prometheus metrics: ${response.statusText}`);
    }

    return response.text();
  }

  /**
   * Reset all metrics (admin only)
   */
  async reset(): Promise<void> {
    const response = await fetch(`${this.baseUrl}/reset`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    });

    if (!response.ok) {
      throw new Error(`Failed to reset metrics: ${response.statusText}`);
    }
  }
}

export const metricsService = new MetricsService();
