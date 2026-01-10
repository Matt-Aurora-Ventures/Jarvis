/**
 * k6 Load Testing Script for JARVIS API
 *
 * Run with: k6 run load_test.js
 *
 * Scenarios:
 * 1. Smoke test - verify basic functionality
 * 2. Load test - normal load patterns
 * 3. Stress test - find breaking points
 * 4. Spike test - sudden traffic bursts
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// =============================================================================
// Configuration
// =============================================================================

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-api-key';

// Custom metrics
const errorRate = new Rate('errors');
const quoteLatency = new Trend('quote_latency');
const tradeLatency = new Trend('trade_latency');
const creditsConsumed = new Counter('credits_consumed');

// =============================================================================
// Test Scenarios
// =============================================================================

export const options = {
  scenarios: {
    // Smoke test - minimal load to verify system works
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '1m',
      tags: { scenario: 'smoke' },
      exec: 'smokeTest',
    },

    // Load test - normal expected load
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },  // Ramp up
        { duration: '5m', target: 50 },  // Stay at 50 users
        { duration: '2m', target: 100 }, // Ramp to 100
        { duration: '5m', target: 100 }, // Stay at 100
        { duration: '2m', target: 0 },   // Ramp down
      ],
      tags: { scenario: 'load' },
      exec: 'loadTest',
      startTime: '2m', // Start after smoke test
    },

    // Stress test - find limits
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 100 },
        { duration: '5m', target: 200 },
        { duration: '5m', target: 300 },
        { duration: '5m', target: 400 },
        { duration: '2m', target: 0 },
      ],
      tags: { scenario: 'stress' },
      exec: 'stressTest',
      startTime: '20m', // Start after load test
    },

    // Spike test - sudden bursts
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },  // Spike up
        { duration: '1m', target: 100 },   // Stay at spike
        { duration: '10s', target: 500 },  // Mega spike
        { duration: '30s', target: 500 },  // Brief hold
        { duration: '1m', target: 100 },   // Back to normal
        { duration: '10s', target: 0 },    // Ramp down
      ],
      tags: { scenario: 'spike' },
      exec: 'spikeTest',
      startTime: '40m', // Start after stress test
    },
  },

  thresholds: {
    http_req_duration: ['p(95)<500'],    // 95% of requests < 500ms
    http_req_failed: ['rate<0.01'],       // <1% error rate
    errors: ['rate<0.05'],                // <5% custom errors
    quote_latency: ['p(95)<200'],         // Quote requests < 200ms
    trade_latency: ['p(95)<1000'],        // Trade requests < 1s
  },
};

// =============================================================================
// Helper Functions
// =============================================================================

function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_KEY}`,
  };
}

function handleResponse(response, name) {
  const success = check(response, {
    [`${name} status is 200`]: (r) => r.status === 200,
    [`${name} has valid JSON`]: (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
  });

  if (!success) {
    errorRate.add(1);
  }

  return success;
}

// =============================================================================
// Test Functions
// =============================================================================

export function smokeTest() {
  group('Health Check', () => {
    const response = http.get(`${BASE_URL}/health`, { headers: getHeaders() });
    check(response, {
      'health check returns 200': (r) => r.status === 200,
      'health check is healthy': (r) => {
        const body = JSON.parse(r.body);
        return body.status === 'healthy';
      },
    });
  });

  group('Quote Request', () => {
    const start = Date.now();
    const response = http.get(
      `${BASE_URL}/api/trade/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000000`,
      { headers: getHeaders() }
    );
    quoteLatency.add(Date.now() - start);
    handleResponse(response, 'quote');
    creditsConsumed.add(1);
  });

  sleep(1);
}

export function loadTest() {
  group('API Flow', () => {
    // Get quote
    const quoteStart = Date.now();
    const quoteResponse = http.get(
      `${BASE_URL}/api/trade/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000000`,
      { headers: getHeaders() }
    );
    quoteLatency.add(Date.now() - quoteStart);

    if (handleResponse(quoteResponse, 'quote')) {
      creditsConsumed.add(1);

      // Simulate trade (mock)
      const tradeStart = Date.now();
      const tradeResponse = http.post(
        `${BASE_URL}/api/trade/execute`,
        JSON.stringify({
          inputMint: 'So11111111111111111111111111111111111111112',
          outputMint: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
          amount: 1000000000,
          wallet: 'TestWallet11111111111111111111111111111111',
        }),
        { headers: getHeaders() }
      );
      tradeLatency.add(Date.now() - tradeStart);

      if (handleResponse(tradeResponse, 'trade')) {
        creditsConsumed.add(5);
      }
    }
  });

  group('Credit Balance', () => {
    const response = http.get(
      `${BASE_URL}/api/credits/balance`,
      { headers: getHeaders() }
    );
    handleResponse(response, 'balance');
  });

  group('Staking Stats', () => {
    const response = http.get(
      `${BASE_URL}/api/staking/stats`,
      { headers: getHeaders() }
    );
    handleResponse(response, 'staking-stats');
  });

  sleep(Math.random() * 2 + 1); // 1-3 second think time
}

export function stressTest() {
  // Same as load test but more aggressive
  loadTest();
  sleep(Math.random() * 0.5); // Shorter think time
}

export function spikeTest() {
  // Mix of heavy endpoints
  const endpoints = [
    { path: '/api/trade/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000000', name: 'quote' },
    { path: '/api/credits/balance', name: 'balance' },
    { path: '/api/staking/stats', name: 'stats' },
    { path: '/api/analytics/dashboard', name: 'dashboard' },
  ];

  const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
  const response = http.get(`${BASE_URL}${endpoint.path}`, { headers: getHeaders() });
  handleResponse(response, endpoint.name);

  sleep(Math.random() * 0.2); // Very short think time
}

// =============================================================================
// Setup and Teardown
// =============================================================================

export function setup() {
  // Verify API is running
  const response = http.get(`${BASE_URL}/health`);
  if (response.status !== 200) {
    throw new Error(`API not healthy: ${response.status}`);
  }

  console.log(`Starting load test against ${BASE_URL}`);
  return { startTime: new Date().toISOString() };
}

export function teardown(data) {
  console.log(`Load test completed. Started at ${data.startTime}`);
}

// =============================================================================
// Default Function (if no scenario specified)
// =============================================================================

export default function() {
  loadTest();
}
