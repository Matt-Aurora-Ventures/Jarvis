"""
JARVIS/LifeOS Core Package

The unified core provides:
- JarvisCore: Central service registry and event bus
- Interfaces: Abstract interfaces for all service types
- Config: Unified configuration system
- Bootstrap: System initialization
- Introspection: Self-awareness and capability discovery
"""

# Legacy imports
from core import config, interview, passive

# Unified Core System
from core.jarvis_core import (
    jarvis,
    JarvisCore,
    Category,
    ServiceStatus,
    Event,
    capability,
    on,
    emit,
    get,
    register,
)

from core.unified_config import config as unified_config

from core.interfaces import (
    IPriceService,
    ISentimentService,
    ISwapService,
    IMessagingService,
    IWalletService,
    IAIService,
    PriceData,
    SentimentResult,
    SwapQuote,
    SwapResult,
    TradeSignal,
)

__all__ = [
    # Core singleton
    'jarvis',
    'JarvisCore',

    # Enums
    'Category',
    'ServiceStatus',

    # Event system
    'Event',
    'emit',
    'on',

    # Service registration
    'capability',
    'register',
    'get',

    # Configuration
    'unified_config',

    # Interfaces
    'IPriceService',
    'ISentimentService',
    'ISwapService',
    'IMessagingService',
    'IWalletService',
    'IAIService',

    # Data types
    'PriceData',
    'SentimentResult',
    'SwapQuote',
    'SwapResult',
    'TradeSignal',
]
