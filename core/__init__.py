"""
JARVIS/LifeOS Core Package.

By default this module preserves eager imports for backwards compatibility.
Set `JARVIS_CORE_MINIMAL_IMPORTS=1` to enable lazy exports and avoid importing
the broader runtime graph when only a narrow subsystem (for example
`core.jupiter_perps`) is required.
"""

from __future__ import annotations

import importlib
import os
from typing import Any

_MINIMAL_IMPORTS = os.environ.get("JARVIS_CORE_MINIMAL_IMPORTS", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    # core.jarvis_core
    "jarvis": ("core.jarvis_core", "jarvis"),
    "JarvisCore": ("core.jarvis_core", "JarvisCore"),
    "Category": ("core.jarvis_core", "Category"),
    "ServiceStatus": ("core.jarvis_core", "ServiceStatus"),
    "Event": ("core.jarvis_core", "Event"),
    "capability": ("core.jarvis_core", "capability"),
    "on": ("core.jarvis_core", "on"),
    "emit": ("core.jarvis_core", "emit"),
    "get": ("core.jarvis_core", "get"),
    "register": ("core.jarvis_core", "register"),
    # core.unified_config
    "unified_config": ("core.unified_config", "config"),
    # core.audit_logger
    "get_audit_logger": ("core.audit_logger", "get_audit_logger"),
    "AuditLogger": ("core.audit_logger", "AuditLogger"),
    "AuditCategory": ("core.audit_logger", "AuditCategory"),
    # core.feature_flags
    "get_feature_flags": ("core.feature_flags", "get_feature_flags"),
    "is_feature_enabled": ("core.feature_flags", "is_feature_enabled"),
    "FeatureFlags": ("core.feature_flags", "FeatureFlags"),
    # core.health_monitor
    "get_health_monitor": ("core.health_monitor", "get_health_monitor"),
    "HealthMonitor": ("core.health_monitor", "HealthMonitor"),
    "HealthStatus": ("core.health_monitor", "HealthStatus"),
    # core.config_hot_reload
    "get_config_manager": ("core.config_hot_reload", "get_config_manager"),
    "get_config": ("core.config_hot_reload", "get_config"),
    "set_config": ("core.config_hot_reload", "set_config"),
    # core.interfaces
    "IPriceService": ("core.interfaces", "IPriceService"),
    "ISentimentService": ("core.interfaces", "ISentimentService"),
    "ISwapService": ("core.interfaces", "ISwapService"),
    "IMessagingService": ("core.interfaces", "IMessagingService"),
    "IWalletService": ("core.interfaces", "IWalletService"),
    "IAIService": ("core.interfaces", "IAIService"),
    "PriceData": ("core.interfaces", "PriceData"),
    "SentimentResult": ("core.interfaces", "SentimentResult"),
    "SwapQuote": ("core.interfaces", "SwapQuote"),
    "SwapResult": ("core.interfaces", "SwapResult"),
    "TradeSignal": ("core.interfaces", "TradeSignal"),
}

__all__ = list(_EXPORT_MAP.keys())


def _load_export(name: str) -> Any:
    module_name, attr_name = _EXPORT_MAP[name]
    module = importlib.import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __getattr__(name: str) -> Any:
    if name in _EXPORT_MAP:
        return _load_export(name)
    raise AttributeError(f"module 'core' has no attribute '{name}'")


if not _MINIMAL_IMPORTS:
    for _name in __all__:
        _load_export(_name)
