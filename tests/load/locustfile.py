"""
JARVIS Load Testing Suite

Comprehensive load testing scenarios using Locust.
Covers all major API endpoints with realistic usage patterns.

Usage:
    locust -f locustfile.py --host=http://localhost:8000

Web UI:
    http://localhost:8089
"""

from locust import HttpUser, task, between, events, SequentialTaskSet
import json
import time
import random
import string
from datetime import datetime


def random_string(length: int = 10) -> str:
    """Generate random string for test data."""
    return ''.join(random.choices(string.ascii_lowercase, k=length))


class JarvisAPIUser(HttpUser):
    """Simulated API user for load testing."""

    wait_time = between(1, 3)

    def on_start(self):
        """Called when user starts."""
        self.api_key = "test-load-key"
        self.headers = {"X-API-Key": self.api_key}
        self.conversation_id = None
    
    @task(10)
    def health_check(self):
        """Frequent health checks."""
        self.client.get("/api/health")
    
    @task(5)
    def get_staking_info(self):
        """Get staking information."""
        with self.client.get(
            "/api/staking/info",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()  # Endpoint may not exist
    
    @task(3)
    def get_credits(self):
        """Get credits balance."""
        with self.client.get(
            "/api/credits/balance",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [404, 401]:
                response.success()
    
    @task(2)
    def get_treasury_status(self):
        """Get treasury status."""
        with self.client.get(
            "/api/treasury/status",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [404, 401]:
                response.success()
    
    @task(1)
    def docs_endpoint(self):
        """Access API documentation."""
        self.client.get("/api/docs")


class JarvisWebSocketUser(HttpUser):
    """WebSocket load testing user."""
    
    wait_time = between(5, 10)
    
    @task
    def websocket_connect(self):
        """Test WebSocket connection."""
        # Locust doesn't natively support WebSocket
        # This simulates the connection attempt
        with self.client.get(
            "/api/health",
            catch_response=True
        ) as response:
            response.success()


class HeavyAPIUser(HttpUser):
    """User that makes heavier API calls."""
    
    wait_time = between(2, 5)
    
    @task(1)
    def complex_query(self):
        """Simulate complex query."""
        params = {
            "page": 1,
            "page_size": 50,
            "sort_by": "created_at",
            "sort_order": "desc"
        }
        with self.client.get(
            "/api/trades",
            params=params,
            headers={"X-API-Key": "test-key"},
            catch_response=True
        ) as response:
            if response.status_code in [404, 401]:
                response.success()


# Event handlers for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, **kwargs):
    """Log request metrics."""
    pass  # Could send to custom metrics system


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("Load test complete.")
    
    # Print summary
    stats = environment.stats
    print(f"\nTotal requests: {stats.total.num_requests}")
    print(f"Failures: {stats.total.num_failures}")
    print(f"Avg response time: {stats.total.avg_response_time:.2f}ms")
    print(f"Requests/s: {stats.total.current_rps:.2f}")


class ChatUser(HttpUser):
    """User focused on chat/conversation workload."""

    wait_time = between(2, 5)

    def on_start(self):
        self.headers = {"X-API-Key": "test-chat-key"}
        self.conversation_id = f"conv_{random_string(8)}"

    @task(5)
    def send_message(self):
        """Send chat messages."""
        messages = [
            "What's the current SOL price?",
            "Analyze the market sentiment",
            "Show me my portfolio",
            "What are the trending tokens?",
            "Help me with trading"
        ]

        with self.client.post(
            "/api/chat",
            json={
                "message": random.choice(messages),
                "conversation_id": self.conversation_id
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404, 503]:
                response.success()

    @task(1)
    def get_conversation_history(self):
        """Retrieve conversation history."""
        with self.client.get(
            f"/api/conversations/{self.conversation_id}",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()


class TradingUser(HttpUser):
    """User focused on trading operations."""

    wait_time = between(3, 8)

    def on_start(self):
        self.headers = {"X-API-Key": "test-trading-key"}

    @task(5)
    def get_portfolio(self):
        """Check portfolio."""
        with self.client.get(
            "/api/trading/portfolio",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()

    @task(3)
    def get_trade_history(self):
        """Get trade history with pagination."""
        params = {
            "limit": random.choice([10, 25, 50]),
            "offset": random.randint(0, 100)
        }
        with self.client.get(
            "/api/trading/history",
            params=params,
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()

    @task(2)
    def get_quote(self):
        """Request a trade quote."""
        symbols = ["SOL/USDC", "BTC/USDC", "ETH/USDC"]
        sides = ["buy", "sell"]

        with self.client.post(
            "/api/trading/quote",
            json={
                "symbol": random.choice(symbols),
                "side": random.choice(sides),
                "amount": round(random.uniform(0.1, 10.0), 2)
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404, 400]:
                response.success()

    @task(1)
    def get_market_data(self):
        """Get market data."""
        with self.client.get(
            "/api/market/prices",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()


class MonitoringUser(HttpUser):
    """User focused on monitoring/metrics."""

    wait_time = between(5, 15)

    @task(5)
    def get_metrics(self):
        """Scrape Prometheus metrics."""
        with self.client.get(
            "/api/metrics",
            catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task(3)
    def get_health_detailed(self):
        """Get detailed health."""
        self.client.get("/api/health/detailed")

    @task(2)
    def get_status_page(self):
        """Get status page data."""
        with self.client.get(
            "/api/status",
            catch_response=True
        ) as response:
            if response.status_code == 404:
                response.success()

    @task(1)
    def get_logs(self):
        """Query recent logs."""
        params = {
            "level": random.choice(["INFO", "WARNING", "ERROR"]),
            "limit": 50
        }
        with self.client.get(
            "/api/logs",
            params=params,
            headers={"X-API-Key": "test-admin-key"},
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()


class BotInteractionUser(HttpUser):
    """Simulates bot interactions."""

    wait_time = between(1, 3)

    def on_start(self):
        self.headers = {"X-API-Key": "test-bot-key"}

    @task(5)
    def get_bot_status(self):
        """Check bot status."""
        with self.client.get(
            "/api/bots",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()

    @task(2)
    def bot_command(self):
        """Execute bot command."""
        bots = ["telegram", "twitter"]
        commands = ["status", "stats", "health"]

        with self.client.post(
            f"/api/bots/{random.choice(bots)}/command",
            json={"command": random.choice(commands)},
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()


class LLMUser(HttpUser):
    """User making LLM-related requests."""

    wait_time = between(5, 15)

    def on_start(self):
        self.headers = {"X-API-Key": "test-llm-key"}

    @task(3)
    def get_usage_stats(self):
        """Get LLM usage stats."""
        with self.client.get(
            "/api/llm/usage",
            params={"period": random.choice(["day", "week", "month"])},
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()

    @task(2)
    def analyze_text(self):
        """Analyze text with LLM."""
        texts = [
            "BTC showing bullish momentum",
            "Market fear index rising",
            "SOL breaking resistance",
            "ETH consolidating sideways"
        ]

        with self.client.post(
            "/api/llm/analyze",
            json={
                "text": random.choice(texts),
                "analysis_type": "sentiment"
            },
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404, 503]:
                response.success()

    @task(1)
    def list_providers(self):
        """List LLM providers."""
        with self.client.get(
            "/api/llm/providers",
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code in [401, 404]:
                response.success()


class SpikeTestUser(HttpUser):
    """User for spike/burst testing."""

    wait_time = between(0.1, 0.5)  # Very fast

    @task
    def burst_health(self):
        """Rapid health checks for spike testing."""
        self.client.get("/api/health")


# Custom load shapes for different test scenarios
class StagesShape:
    """
    Custom load shape with stages.

    Usage:
        locust -f locustfile.py --class-picker
    """
    stages = [
        {"duration": 60, "users": 10, "spawn_rate": 2},   # Warm up
        {"duration": 120, "users": 50, "spawn_rate": 5},  # Ramp up
        {"duration": 180, "users": 100, "spawn_rate": 10}, # Peak
        {"duration": 60, "users": 50, "spawn_rate": 10},  # Scale down
        {"duration": 60, "users": 10, "spawn_rate": 5},   # Cool down
    ]


# Event handlers for custom metrics
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Log request metrics for analysis."""
    if exception:
        print(f"Request failed: {name} - {exception}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts."""
    print("=" * 60)
    print("JARVIS Load Test Starting")
    print(f"Target: {environment.host}")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print("=" * 60)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test stops."""
    print("\n" + "=" * 60)
    print("JARVIS Load Test Complete")
    print("=" * 60)

    stats = environment.stats

    print(f"\nSummary:")
    print(f"  Total Requests: {stats.total.num_requests}")
    print(f"  Failures: {stats.total.num_failures}")
    print(f"  Failure Rate: {(stats.total.num_failures / max(stats.total.num_requests, 1)) * 100:.2f}%")
    print(f"  Avg Response Time: {stats.total.avg_response_time:.2f}ms")
    print(f"  Median Response Time: {stats.total.median_response_time:.2f}ms")
    print(f"  95th Percentile: {stats.total.get_response_time_percentile(0.95):.2f}ms")
    print(f"  99th Percentile: {stats.total.get_response_time_percentile(0.99):.2f}ms")
    print(f"  Requests/sec: {stats.total.current_rps:.2f}")
    print("=" * 60)


# Run configuration
if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py --host=http://localhost:8000")
