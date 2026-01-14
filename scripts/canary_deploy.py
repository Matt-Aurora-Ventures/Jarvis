#!/usr/bin/env python3
"""
Canary Deployment Script

Implements progressive canary deployment with automatic rollback.
Monitors health metrics and gradually increases traffic to new version.
"""
import asyncio
import subprocess
import time
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeploymentState(Enum):
    """Canary deployment states."""
    PENDING = "pending"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    PROMOTING = "promoting"
    ROLLING_BACK = "rolling_back"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class CanaryConfig:
    """Configuration for canary deployment."""
    initial_percentage: int = 10
    increment_percentage: int = 10
    max_percentage: int = 100
    stabilization_minutes: int = 5
    error_threshold_percent: float = 5.0
    latency_threshold_ms: float = 500.0
    min_requests_for_decision: int = 100


@dataclass
class HealthMetrics:
    """Health metrics for canary analysis."""
    total_requests: int
    error_count: int
    error_rate: float
    avg_latency_ms: float
    p99_latency_ms: float


class CanaryDeployer:
    """
    Manages canary deployments with automated rollback.

    Features:
    - Gradual traffic shifting
    - Health metric monitoring
    - Automatic rollback on errors
    - Integration with Kubernetes/kubectl
    """

    def __init__(self, config: CanaryConfig = None):
        self.config = config or CanaryConfig()
        self.state = DeploymentState.PENDING
        self.current_percentage = 0
        self.metrics_history: List[HealthMetrics] = []

    async def deploy(
        self,
        service: str,
        new_version: str,
        namespace: str = "default"
    ) -> bool:
        """
        Execute a canary deployment.

        Args:
            service: Name of the service to deploy
            new_version: New version/image tag
            namespace: Kubernetes namespace

        Returns:
            True if deployment succeeded, False if rolled back
        """
        logger.info(f"Starting canary deployment: {service} -> {new_version}")
        self.state = DeploymentState.DEPLOYING

        try:
            # Deploy canary version
            await self._deploy_canary(service, new_version, namespace)

            # Start with initial traffic
            self.current_percentage = self.config.initial_percentage
            await self._set_traffic_split(
                service, namespace, self.current_percentage
            )

            self.state = DeploymentState.MONITORING

            # Progressive rollout
            while self.current_percentage < self.config.max_percentage:
                # Wait for stabilization
                logger.info(
                    f"Monitoring at {self.current_percentage}% traffic "
                    f"for {self.config.stabilization_minutes} minutes"
                )
                await asyncio.sleep(self.config.stabilization_minutes * 60)

                # Check health
                metrics = await self._collect_metrics(service, namespace)
                self.metrics_history.append(metrics)

                if not self._is_healthy(metrics):
                    logger.error(f"Health check failed: {metrics}")
                    await self._rollback(service, namespace)
                    return False

                # Increment traffic
                self.current_percentage = min(
                    self.current_percentage + self.config.increment_percentage,
                    self.config.max_percentage
                )
                await self._set_traffic_split(
                    service, namespace, self.current_percentage
                )

            # Full promotion
            self.state = DeploymentState.PROMOTING
            await self._promote_canary(service, new_version, namespace)

            self.state = DeploymentState.COMPLETED
            logger.info(f"Canary deployment completed: {service} -> {new_version}")
            return True

        except Exception as e:
            logger.error(f"Deployment failed: {e}")
            self.state = DeploymentState.FAILED
            await self._rollback(service, namespace)
            return False

    async def _deploy_canary(
        self,
        service: str,
        version: str,
        namespace: str
    ) -> None:
        """Deploy canary version alongside stable."""
        logger.info(f"Deploying canary: {service}-canary")

        # Apply canary deployment
        manifest = self._generate_canary_manifest(service, version, namespace)

        # In production, this would apply via kubectl
        logger.info(f"Would apply canary manifest for {service}")

    async def _set_traffic_split(
        self,
        service: str,
        namespace: str,
        canary_percentage: int
    ) -> None:
        """Set traffic split between stable and canary."""
        stable_percentage = 100 - canary_percentage
        logger.info(
            f"Traffic split: stable={stable_percentage}%, "
            f"canary={canary_percentage}%"
        )

        # In production, update Istio VirtualService or similar
        # kubectl patch virtualservice {service} ...

    async def _collect_metrics(
        self,
        service: str,
        namespace: str
    ) -> HealthMetrics:
        """Collect health metrics from monitoring system."""
        # In production, query Prometheus/metrics endpoint
        # This is a mock implementation

        # Simulate metrics collection
        return HealthMetrics(
            total_requests=1000,
            error_count=10,
            error_rate=1.0,
            avg_latency_ms=150.0,
            p99_latency_ms=400.0
        )

    def _is_healthy(self, metrics: HealthMetrics) -> bool:
        """Check if metrics indicate healthy canary."""
        if metrics.total_requests < self.config.min_requests_for_decision:
            logger.warning(
                f"Insufficient requests ({metrics.total_requests}) "
                f"for decision, assuming healthy"
            )
            return True

        if metrics.error_rate > self.config.error_threshold_percent:
            logger.error(
                f"Error rate {metrics.error_rate}% exceeds threshold "
                f"{self.config.error_threshold_percent}%"
            )
            return False

        if metrics.p99_latency_ms > self.config.latency_threshold_ms:
            logger.error(
                f"P99 latency {metrics.p99_latency_ms}ms exceeds threshold "
                f"{self.config.latency_threshold_ms}ms"
            )
            return False

        return True

    async def _promote_canary(
        self,
        service: str,
        version: str,
        namespace: str
    ) -> None:
        """Promote canary to stable."""
        logger.info(f"Promoting canary to stable: {service}")

        # Update stable deployment to use new version
        # kubectl set image deployment/{service} ...

        # Remove canary deployment
        # kubectl delete deployment {service}-canary

    async def _rollback(self, service: str, namespace: str) -> None:
        """Rollback canary deployment."""
        self.state = DeploymentState.ROLLING_BACK
        logger.warning(f"Rolling back canary deployment: {service}")

        # Reset traffic to 100% stable
        await self._set_traffic_split(service, namespace, 0)

        # Delete canary deployment
        # kubectl delete deployment {service}-canary

        self.state = DeploymentState.FAILED

    def _generate_canary_manifest(
        self,
        service: str,
        version: str,
        namespace: str
    ) -> Dict[str, Any]:
        """Generate Kubernetes manifest for canary."""
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": f"{service}-canary",
                "namespace": namespace,
                "labels": {
                    "app": service,
                    "version": "canary"
                }
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": service,
                        "version": "canary"
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": service,
                            "version": "canary"
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": service,
                            "image": f"{service}:{version}"
                        }]
                    }
                }
            }
        }

    def get_status(self) -> Dict[str, Any]:
        """Get current deployment status."""
        return {
            "state": self.state.value,
            "current_percentage": self.current_percentage,
            "metrics_collected": len(self.metrics_history),
            "config": {
                "initial_percentage": self.config.initial_percentage,
                "increment_percentage": self.config.increment_percentage,
                "max_percentage": self.config.max_percentage
            }
        }


async def main():
    """Run canary deployment."""
    import argparse

    parser = argparse.ArgumentParser(description="Canary deployment")
    parser.add_argument("service", help="Service name")
    parser.add_argument("version", help="New version to deploy")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--initial-pct", type=int, default=10)
    parser.add_argument("--increment-pct", type=int, default=10)
    parser.add_argument("--stabilization-mins", type=int, default=5)

    args = parser.parse_args()

    config = CanaryConfig(
        initial_percentage=args.initial_pct,
        increment_percentage=args.increment_pct,
        stabilization_minutes=args.stabilization_mins
    )

    deployer = CanaryDeployer(config)
    success = await deployer.deploy(
        args.service,
        args.version,
        args.namespace
    )

    print(json.dumps(deployer.get_status(), indent=2))
    exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
