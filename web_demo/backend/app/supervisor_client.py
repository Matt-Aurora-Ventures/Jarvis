"""
Supervisor Client - Register with main Jarvis supervisor

Allows web demo backend to be monitored by the central supervisor
that manages all bot components.
"""
import asyncio
import logging
import os
import socket
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SupervisorClient:
    """
    Client for registering with Jarvis supervisor.

    The supervisor monitors all components (Telegram bot, Twitter bot, etc.)
    and can restart them on failure. Web demo registers as a component.
    """

    def __init__(
        self,
        component_name: str = "web_demo_api",
        heartbeat_interval: int = 30,
        state_file: Optional[Path] = None,
    ):
        """
        Initialize supervisor client.

        Args:
            component_name: Unique name for this component
            heartbeat_interval: Seconds between heartbeats
            state_file: Path to shared state file for health reporting
        """
        self.component_name = component_name
        self.heartbeat_interval = heartbeat_interval
        self.state_file = state_file or Path("/app/shared_state") / f"{component_name}.state"
        self.enabled = os.getenv("SUPERVISOR_ENABLED", "false").lower() == "true"
        self.running = False
        self._heartbeat_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start supervisor client - register and begin heartbeats."""
        if not self.enabled:
            logger.info("Supervisor integration disabled (SUPERVISOR_ENABLED=false)")
            return

        logger.info(f"Registering with supervisor as '{self.component_name}'")

        # Create state file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._write_state("starting")

        # Start heartbeat loop
        self.running = True
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(f"Supervisor client started (heartbeat every {self.heartbeat_interval}s)")

    async def stop(self):
        """Stop supervisor client - unregister."""
        if not self.enabled:
            return

        logger.info(f"Unregistering from supervisor: {self.component_name}")

        self.running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        self._write_state("stopped")
        logger.info("Supervisor client stopped")

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to supervisor."""
        try:
            while self.running:
                self._write_state("running")
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            logger.debug("Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"Heartbeat loop error: {e}", exc_info=True)

    def _write_state(self, status: str):
        """Write current state to shared file."""
        try:
            state_data = {
                "component": self.component_name,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
            }

            # Write atomically
            temp_file = self.state_file.with_suffix(".tmp")
            with open(temp_file, "w") as f:
                import json
                json.dump(state_data, f, indent=2)

            temp_file.replace(self.state_file)

        except Exception as e:
            logger.warning(f"Failed to write state file: {e}")

    async def health_check(self) -> dict:
        """
        Return health status for supervisor.

        Supervisor can query this via HTTP endpoint.
        """
        return {
            "component": self.component_name,
            "status": "running" if self.running else "stopped",
            "supervisor_enabled": self.enabled,
            "heartbeat_interval": self.heartbeat_interval,
            "state_file": str(self.state_file),
        }


# Global instance
_supervisor_client: Optional[SupervisorClient] = None


def get_supervisor_client(
    component_name: str = None,
    heartbeat_interval: int = 30,
) -> SupervisorClient:
    """
    Get or create global supervisor client.

    Args:
        component_name: Component name (default from env or 'web_demo_api')
        heartbeat_interval: Seconds between heartbeats

    Returns:
        SupervisorClient instance
    """
    global _supervisor_client

    if _supervisor_client is None:
        name = component_name or os.getenv("COMPONENT_NAME", "web_demo_api")
        _supervisor_client = SupervisorClient(
            component_name=name,
            heartbeat_interval=heartbeat_interval,
        )

    return _supervisor_client


async def startup_supervisor_client():
    """FastAPI lifespan startup - register with supervisor."""
    client = get_supervisor_client()
    await client.start()


async def shutdown_supervisor_client():
    """FastAPI lifespan shutdown - unregister from supervisor."""
    client = get_supervisor_client()
    await client.stop()
