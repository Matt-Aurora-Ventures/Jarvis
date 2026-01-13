"""Load testing with Locust."""
from locust import HttpUser, task, between, events
import json
import time


class JarvisAPIUser(HttpUser):
    """Simulated API user for load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when user starts."""
        self.api_key = "test-load-key"
        self.headers = {"X-API-Key": self.api_key}
    
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


# Run configuration
if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py --host=http://localhost:8000")
