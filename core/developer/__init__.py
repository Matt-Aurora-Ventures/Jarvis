"""
JARVIS Developer API

SDK and tools for third-party developers to integrate with JARVIS.

Prompts #61-64: Developer API Infrastructure
"""

from .sdk import (
    JarvisSDK,
    SDKConfig,
    APICredentials,
    RateLimitInfo,
)

from .key_manager import (
    APIKeyManager,
    APIKey,
    KeyScope,
    get_api_key_manager,
)

from .webhooks import (
    WebhookManager,
    Webhook,
    WebhookEvent,
    WebhookDelivery,
    get_webhook_manager,
)

from .oauth import (
    OAuthProvider,
    OAuthToken,
    OAuthScope,
)

__all__ = [
    # SDK
    "JarvisSDK",
    "SDKConfig",
    "APICredentials",
    "RateLimitInfo",
    # API Keys
    "APIKeyManager",
    "APIKey",
    "KeyScope",
    "get_api_key_manager",
    # Webhooks
    "WebhookManager",
    "Webhook",
    "WebhookEvent",
    "WebhookDelivery",
    "get_webhook_manager",
    # OAuth
    "OAuthProvider",
    "OAuthToken",
    "OAuthScope",
]
