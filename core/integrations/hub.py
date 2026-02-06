"""
Integration Hub - Central registry for external service integrations.

Provides unified access to all configured external services.
Supports registration, retrieval, health monitoring, and bulk operations.
"""

import logging
from typing import Dict, List, Optional

from .base import Integration

logger = logging.getLogger(__name__)

# Module-level singleton
_hub_instance: Optional["IntegrationHub"] = None


class IntegrationHub:
    """
    Central hub for managing external service integrations.

    Features:
    - Register/unregister integrations
    - Retrieve integrations by name
    - Check configuration status
    - List all registered integrations
    - Bulk connect/disconnect operations
    - Health monitoring for all integrations

    Example:
        hub = IntegrationHub()
        hub.register("telegram", TelegramIntegration(bot_token="..."))

        telegram = hub.get("telegram")
        telegram.connect()
    """

    def __init__(self):
        """Initialize the integration hub with empty registry."""
        self._integrations: Dict[str, Integration] = {}

    def register(self, name: str, integration: Integration) -> None:
        """
        Register an integration with the hub.

        Args:
            name: Unique name for this integration
            integration: Integration instance to register

        Raises:
            TypeError: If integration is not an Integration instance
        """
        if not isinstance(integration, Integration):
            raise TypeError(
                f"Expected Integration instance, got {type(integration).__name__}"
            )

        self._integrations[name] = integration
        logger.info(f"Registered integration: {name}")

    def unregister(self, name: str) -> bool:
        """
        Unregister an integration from the hub.

        Args:
            name: Name of the integration to unregister

        Returns:
            bool: True if integration was unregistered, False if not found
        """
        if name in self._integrations:
            # Disconnect before unregistering
            integration = self._integrations[name]
            if integration.is_connected():
                integration.disconnect()

            del self._integrations[name]
            logger.info(f"Unregistered integration: {name}")
            return True
        return False

    def get(self, name: str) -> Optional[Integration]:
        """
        Get an integration by name.

        Args:
            name: Name of the integration to retrieve

        Returns:
            Integration or None if not found
        """
        return self._integrations.get(name)

    def is_configured(self, name: str) -> bool:
        """
        Check if an integration is registered and configured.

        Args:
            name: Name of the integration to check

        Returns:
            bool: True if integration is registered, False otherwise
        """
        return name in self._integrations

    def list_integrations(self) -> List[str]:
        """
        List all registered integration names.

        Returns:
            List[str]: Names of all registered integrations
        """
        return list(self._integrations.keys())

    def connect_all(self) -> Dict[str, bool]:
        """
        Connect all registered integrations.

        Returns:
            Dict[str, bool]: Map of integration name to connection success
        """
        results = {}
        for name, integration in self._integrations.items():
            try:
                results[name] = integration.connect()
            except Exception as e:
                logger.error(f"Failed to connect {name}: {e}")
                results[name] = False
        return results

    def disconnect_all(self) -> None:
        """Disconnect all registered integrations."""
        for name, integration in self._integrations.items():
            try:
                if integration.is_connected():
                    integration.disconnect()
            except Exception as e:
                logger.error(f"Failed to disconnect {name}: {e}")

    def health_check_all(self) -> Dict[str, bool]:
        """
        Health check all registered integrations.

        Returns:
            Dict[str, bool]: Map of integration name to health status
        """
        results = {}
        for name, integration in self._integrations.items():
            try:
                results[name] = integration.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
        return results

    def get_status(self) -> Dict[str, Dict]:
        """
        Get detailed status of all integrations.

        Returns:
            Dict with integration name as key and status dict as value
        """
        status = {}
        for name, integration in self._integrations.items():
            status[name] = {
                "name": integration.name,
                "description": integration.description,
                "connected": integration.is_connected(),
                "healthy": integration.health_check() if integration.is_connected() else False,
                "required_config": integration.required_config,
            }
        return status


def get_hub() -> IntegrationHub:
    """
    Get the singleton IntegrationHub instance.

    Returns:
        IntegrationHub: The global hub instance
    """
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = IntegrationHub()
    return _hub_instance


def reset_hub() -> None:
    """
    Reset the singleton hub instance.

    Useful for testing or reinitializing the hub.
    """
    global _hub_instance
    if _hub_instance is not None:
        _hub_instance.disconnect_all()
    _hub_instance = None
