"""
Base Integration Abstract Class.

Provides the abstract interface that all integrations must implement.
This ensures consistent behavior across all external service integrations.
"""

from abc import ABC, abstractmethod
from typing import List


class Integration(ABC):
    """
    Abstract base class for all external service integrations.

    All integrations must implement:
    - name: A unique identifier for the integration
    - description: Human-readable description
    - required_config: List of required configuration keys
    - connect(): Establish connection to the service
    - disconnect(): Close connection to the service
    - is_connected(): Check if currently connected
    - health_check(): Verify the service is healthy
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this integration.

        Returns:
            str: The integration name (e.g., "telegram", "x_twitter")
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of this integration.

        Returns:
            str: Description of what this integration does
        """
        pass

    @property
    @abstractmethod
    def required_config(self) -> List[str]:
        """
        List of required configuration keys for this integration.

        Returns:
            List[str]: Configuration keys needed (e.g., ["api_key", "secret"])
        """
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish a connection to the external service.

        Returns:
            bool: True if connection was successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close the connection to the external service.

        This should clean up any resources and set the connection state to disconnected.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to the external service.

        Returns:
            bool: True if connected, False otherwise
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Verify the external service is healthy and accessible.

        This should perform a lightweight check to ensure the service
        is responding correctly.

        Returns:
            bool: True if healthy, False otherwise
        """
        pass
