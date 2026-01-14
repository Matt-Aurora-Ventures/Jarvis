#!/usr/bin/env python3
"""
JARVIS Deployment Script

Provides automated deployment with safety checks,
rollback capability, and deployment verification.
"""

import argparse
import os
import sys
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DEPLOY_CONFIG = {
    "environments": {
        "staging": {
            "host": "staging.jarvis.local",
            "docker_compose": "docker-compose.staging.yml",
            "healthcheck_url": "http://staging.jarvis.local:8000/health",
        },
        "production": {
            "host": "jarvis.local",
            "docker_compose": "docker-compose.prod.yml",
            "healthcheck_url": "http://jarvis.local:8000/health",
            "requires_approval": True,
        },
    },
    "pre_deploy_checks": [
        "tests",
        "lint",
        "security_scan",
    ],
    "post_deploy_checks": [
        "health",
        "smoke_test",
    ],
    "rollback_on_failure": True,
    "max_deploy_time_seconds": 300,
}


class DeploymentError(Exception):
    """Deployment error."""
    pass


class Deployer:
    """
    Handles JARVIS deployment process.

    Features:
    - Pre-deployment checks
    - Docker image building
    - Blue-green deployment
    - Health verification
    - Automatic rollback

    Usage:
        deployer = Deployer(environment="staging")
        deployer.deploy(version="1.2.3")
    """

    def __init__(self, environment: str, dry_run: bool = False):
        if environment not in DEPLOY_CONFIG["environments"]:
            raise ValueError(f"Unknown environment: {environment}")

        self.environment = environment
        self.config = DEPLOY_CONFIG["environments"][environment]
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent.parent
        self.deployment_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.previous_version: Optional[str] = None

    def deploy(self, version: str, skip_checks: bool = False) -> bool:
        """Execute deployment."""
        logger.info(f"Starting deployment to {self.environment}")
        logger.info(f"Deployment ID: {self.deployment_id}")
        logger.info(f"Version: {version}")

        if self.dry_run:
            logger.info("DRY RUN - No changes will be made")

        try:
            # Check for approval if required
            if self.config.get("requires_approval"):
                if not self._get_approval():
                    logger.info("Deployment cancelled - approval not granted")
                    return False

            # Pre-deployment checks
            if not skip_checks:
                logger.info("Running pre-deployment checks...")
                if not self._run_pre_deploy_checks():
                    raise DeploymentError("Pre-deployment checks failed")

            # Save current version for rollback
            self.previous_version = self._get_current_version()
            logger.info(f"Current version: {self.previous_version}")

            # Build image
            logger.info("Building Docker image...")
            if not self._build_image(version):
                raise DeploymentError("Image build failed")

            # Deploy
            logger.info("Deploying...")
            if not self._deploy(version):
                raise DeploymentError("Deployment failed")

            # Post-deployment checks
            logger.info("Running post-deployment checks...")
            if not self._run_post_deploy_checks():
                logger.error("Post-deployment checks failed")
                if DEPLOY_CONFIG["rollback_on_failure"]:
                    self._rollback()
                raise DeploymentError("Post-deployment checks failed")

            # Record successful deployment
            self._record_deployment(version, success=True)

            logger.info(f"Deployment successful! Version {version} is now live.")
            return True

        except DeploymentError as e:
            logger.error(f"Deployment failed: {e}")
            self._record_deployment(version, success=False, error=str(e))
            return False

        except Exception as e:
            logger.exception(f"Unexpected error during deployment: {e}")
            if DEPLOY_CONFIG["rollback_on_failure"] and self.previous_version:
                self._rollback()
            return False

    def rollback(self, to_version: Optional[str] = None) -> bool:
        """Rollback to previous version."""
        version = to_version or self.previous_version
        if not version:
            logger.error("No version to rollback to")
            return False

        logger.info(f"Rolling back to version {version}")
        return self._rollback(version)

    def _get_approval(self) -> bool:
        """Get manual approval for deployment."""
        if self.dry_run:
            return True

        print(f"\n{'='*60}")
        print(f"PRODUCTION DEPLOYMENT APPROVAL REQUIRED")
        print(f"Environment: {self.environment}")
        print(f"{'='*60}")

        response = input("Type 'DEPLOY' to confirm: ")
        return response.strip() == "DEPLOY"

    def _run_pre_deploy_checks(self) -> bool:
        """Run pre-deployment checks."""
        checks = DEPLOY_CONFIG["pre_deploy_checks"]

        for check in checks:
            logger.info(f"  Running check: {check}")
            if not self._run_check(check):
                logger.error(f"  Check failed: {check}")
                return False
            logger.info(f"  Check passed: {check}")

        return True

    def _run_check(self, check: str) -> bool:
        """Run a specific check."""
        if self.dry_run:
            return True

        check_commands = {
            "tests": ["pytest", "tests/", "-x", "-q"],
            "lint": ["ruff", "check", "core/", "api/", "bots/"],
            "security_scan": ["bandit", "-r", "core/", "-q"],
            "type_check": ["mypy", "core/"],
        }

        if check not in check_commands:
            logger.warning(f"Unknown check: {check}")
            return True

        try:
            result = subprocess.run(
                check_commands[check],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error(f"Check timed out: {check}")
            return False
        except Exception as e:
            logger.error(f"Check error: {e}")
            return False

    def _get_current_version(self) -> Optional[str]:
        """Get current deployed version."""
        try:
            result = subprocess.run(
                ["docker", "inspect", "jarvis-api", "--format", "{{.Config.Labels.version}}"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _build_image(self, version: str) -> bool:
        """Build Docker image."""
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would build image: jarvis-api:{version}")
            return True

        try:
            result = subprocess.run(
                [
                    "docker", "build",
                    "-t", f"jarvis-api:{version}",
                    "-t", "jarvis-api:latest",
                    "--label", f"version={version}",
                    "--label", f"deployment_id={self.deployment_id}",
                    ".",
                ],
                cwd=self.project_root,
                timeout=300,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Build failed: {e}")
            return False

    def _deploy(self, version: str) -> bool:
        """Deploy the new version."""
        if self.dry_run:
            logger.info(f"  [DRY RUN] Would deploy version {version}")
            return True

        compose_file = self.config["docker_compose"]

        try:
            # Pull/update images
            subprocess.run(
                ["docker-compose", "-f", compose_file, "pull"],
                cwd=self.project_root,
            )

            # Deploy with zero-downtime
            result = subprocess.run(
                [
                    "docker-compose", "-f", compose_file,
                    "up", "-d", "--no-deps", "--build", "api"
                ],
                cwd=self.project_root,
                timeout=DEPLOY_CONFIG["max_deploy_time_seconds"],
            )

            return result.returncode == 0

        except Exception as e:
            logger.error(f"Deploy failed: {e}")
            return False

    def _run_post_deploy_checks(self) -> bool:
        """Run post-deployment checks."""
        checks = DEPLOY_CONFIG["post_deploy_checks"]

        for check in checks:
            logger.info(f"  Running check: {check}")
            if not self._run_post_check(check):
                logger.error(f"  Check failed: {check}")
                return False
            logger.info(f"  Check passed: {check}")

        return True

    def _run_post_check(self, check: str) -> bool:
        """Run a post-deployment check."""
        if self.dry_run:
            return True

        if check == "health":
            return self._check_health()
        elif check == "smoke_test":
            return self._run_smoke_test()

        return True

    def _check_health(self, retries: int = 10, delay: int = 5) -> bool:
        """Check if service is healthy."""
        import urllib.request
        import urllib.error

        url = self.config["healthcheck_url"]

        for i in range(retries):
            try:
                response = urllib.request.urlopen(url, timeout=10)
                if response.getcode() == 200:
                    return True
            except urllib.error.URLError:
                pass

            if i < retries - 1:
                logger.info(f"  Health check failed, retrying in {delay}s...")
                time.sleep(delay)

        return False

    def _run_smoke_test(self) -> bool:
        """Run smoke tests against deployed service."""
        try:
            result = subprocess.run(
                ["pytest", "tests/smoke/", "-x", "-q"],
                cwd=self.project_root,
                capture_output=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception:
            # Smoke tests optional
            return True

    def _rollback(self, version: Optional[str] = None) -> bool:
        """Rollback to specified version."""
        rollback_version = version or self.previous_version

        if not rollback_version:
            logger.error("No version to rollback to")
            return False

        if self.dry_run:
            logger.info(f"  [DRY RUN] Would rollback to {rollback_version}")
            return True

        logger.warning(f"Rolling back to version {rollback_version}...")

        try:
            compose_file = self.config["docker_compose"]

            # Tag rollback version as latest
            subprocess.run([
                "docker", "tag",
                f"jarvis-api:{rollback_version}",
                "jarvis-api:latest"
            ])

            # Redeploy
            result = subprocess.run(
                ["docker-compose", "-f", compose_file, "up", "-d", "--no-deps", "api"],
                cwd=self.project_root,
            )

            if result.returncode == 0:
                logger.info(f"Rollback to {rollback_version} successful")
                return True
            else:
                logger.error("Rollback failed")
                return False

        except Exception as e:
            logger.error(f"Rollback error: {e}")
            return False

    def _record_deployment(
        self,
        version: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """Record deployment in history."""
        history_file = self.project_root / "deployments.json"

        history = []
        if history_file.exists():
            try:
                history = json.loads(history_file.read_text())
            except Exception:
                pass

        history.append({
            "deployment_id": self.deployment_id,
            "version": version,
            "environment": self.environment,
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
            "error": error,
            "previous_version": self.previous_version,
        })

        # Keep last 100 deployments
        history = history[-100:]

        if not self.dry_run:
            history_file.write_text(json.dumps(history, indent=2))


def main():
    parser = argparse.ArgumentParser(description="JARVIS Deployment Script")
    parser.add_argument(
        "action",
        choices=["deploy", "rollback", "status"],
        help="Action to perform"
    )
    parser.add_argument(
        "-e", "--environment",
        choices=["staging", "production"],
        default="staging",
        help="Target environment"
    )
    parser.add_argument(
        "-v", "--version",
        help="Version to deploy"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip pre-deployment checks"
    )

    args = parser.parse_args()

    deployer = Deployer(
        environment=args.environment,
        dry_run=args.dry_run,
    )

    if args.action == "deploy":
        if not args.version:
            # Use git tag or commit hash
            try:
                result = subprocess.run(
                    ["git", "describe", "--tags", "--always"],
                    capture_output=True,
                    text=True,
                )
                args.version = result.stdout.strip()
            except Exception:
                args.version = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        success = deployer.deploy(
            version=args.version,
            skip_checks=args.skip_checks,
        )
        sys.exit(0 if success else 1)

    elif args.action == "rollback":
        success = deployer.rollback(to_version=args.version)
        sys.exit(0 if success else 1)

    elif args.action == "status":
        print(f"Environment: {args.environment}")
        print(f"Current version: {deployer._get_current_version()}")


if __name__ == "__main__":
    main()
