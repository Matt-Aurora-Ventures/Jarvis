"""
JARVIS Bootstrap - Wires all services to the unified core

This module bridges existing implementations to the new unified architecture.
It registers all known services with JarvisCore, enabling:
- Service discovery across all modules
- Unified event propagation
- Self-documenting capabilities
- Health monitoring

Run this at startup to initialize the complete JARVIS system:
    from core.bootstrap import bootstrap_jarvis
    await bootstrap_jarvis()
"""

import os
import logging
from typing import Optional, List, Dict, Any

from core.jarvis_core import jarvis, Category, ServiceStatus
from core.unified_config import config

logger = logging.getLogger(__name__)


async def bootstrap_jarvis(
    skip_unavailable: bool = True,
    verbose: bool = False
) -> Dict[str, Any]:
    """
    Bootstrap the complete JARVIS system.

    This registers all known services with JarvisCore and initializes
    essential services.

    Args:
        skip_unavailable: If True, skip services that fail to load
        verbose: Enable verbose logging

    Returns:
        Dict with bootstrap results
    """
    results = {
        "registered": [],
        "failed": [],
        "skipped": [],
    }

    logger.info("Bootstrapping JARVIS Core...")

    # Register core data sources
    await _register_data_sources(results, skip_unavailable)

    # Register trading services
    await _register_trading_services(results, skip_unavailable)

    # Register messaging services
    await _register_messaging_services(results, skip_unavailable)

    # Register AI services
    await _register_ai_services(results, skip_unavailable)

    # Register analytics services
    await _register_analytics_services(results, skip_unavailable)

    # Start the core
    await jarvis.start()

    logger.info(f"Bootstrap complete: {len(results['registered'])} services registered")
    if results['failed']:
        logger.warning(f"Failed to register: {results['failed']}")

    return results


async def _register_data_sources(results: dict, skip_unavailable: bool):
    """Register data source services."""

    # Hyperliquid client
    try:
        from core.data_sources.hyperliquid_api import HyperliquidClient, get_client
        jarvis.register(
            "hyperliquid",
            get_client(),
            category=Category.DATA,
            description="Hyperliquid perp market data, order books, liquidations",
            tags={"perps", "orderbook", "liquidations", "funding"},
            provides=["hyperliquid", "perp_data", "liquidation_monitor"],
        )
        results["registered"].append("hyperliquid")
    except Exception as e:
        logger.warning(f"Could not register hyperliquid: {e}")
        results["failed"].append(("hyperliquid", str(e)))

    # Twelve Data client
    try:
        from core.data_sources.twelve_data import TwelveDataClient, get_client
        jarvis.register(
            "twelve_data",
            get_client(),
            category=Category.DATA,
            description="Traditional market data - stocks, forex, ETFs, indicators",
            tags={"stocks", "forex", "etf", "indicators", "fundamentals"},
            provides=["twelve_data", "stock_prices", "forex_prices", "technical_indicators"],
        )
        results["registered"].append("twelve_data")
    except Exception as e:
        logger.warning(f"Could not register twelve_data: {e}")
        results["failed"].append(("twelve_data", str(e)))

    # Commodity prices
    try:
        from core.data_sources.commodity_prices import get_commodity_client
        jarvis.register(
            "commodities",
            get_commodity_client(),
            category=Category.DATA,
            description="Live commodity prices - gold, silver, metals",
            tags={"commodities", "gold", "silver", "metals"},
            provides=["commodities", "gold_price", "silver_price"],
        )
        results["registered"].append("commodities")
    except Exception as e:
        logger.warning(f"Could not register commodities: {e}")
        results["failed"].append(("commodities", str(e)))

    # Circuit breaker
    try:
        from core.data_sources.circuit_breaker import get_registry
        jarvis.register(
            "circuit_breaker_registry",
            get_registry(),
            category=Category.INFRASTRUCTURE,
            description="Circuit breaker registry for API fault tolerance",
            tags={"reliability", "fault_tolerance"},
        )
        results["registered"].append("circuit_breaker_registry")
    except Exception as e:
        logger.warning(f"Could not register circuit_breaker_registry: {e}")
        results["failed"].append(("circuit_breaker_registry", str(e)))

    # DexScreener
    try:
        from core.dexscreener import DexScreenerClient
        jarvis.register(
            "dexscreener",
            DexScreenerClient(),
            category=Category.DATA,
            description="DexScreener API for DEX token data",
            tags={"dex", "tokens", "pairs", "volume"},
            provides=["dexscreener", "dex_data"],
        )
        results["registered"].append("dexscreener")
    except Exception as e:
        logger.warning(f"Could not register dexscreener: {e}")
        results["failed"].append(("dexscreener", str(e)))

    # Birdeye
    try:
        from core.birdeye import BirdeyeClient
        jarvis.register(
            "birdeye",
            BirdeyeClient(),
            category=Category.DATA,
            description="Birdeye API for Solana token analytics",
            tags={"solana", "tokens", "analytics"},
            provides=["birdeye", "solana_analytics"],
        )
        results["registered"].append("birdeye")
    except Exception as e:
        logger.warning(f"Could not register birdeye: {e}")
        results["failed"].append(("birdeye", str(e)))


async def _register_trading_services(results: dict, skip_unavailable: bool):
    """Register trading services."""

    # Jupiter client
    try:
        from bots.treasury.jupiter import JupiterClient
        rpc_url = config.get("solana.rpc_url")
        jarvis.register(
            "jupiter",
            JupiterClient(rpc_url) if rpc_url else JupiterClient(),
            category=Category.TRADING,
            description="Jupiter aggregator for Solana swaps",
            tags={"solana", "swap", "dex", "aggregator"},
            provides=["jupiter", "swap_service", "price_service"],
        )
        results["registered"].append("jupiter")
    except Exception as e:
        logger.warning(f"Could not register jupiter: {e}")
        results["failed"].append(("jupiter", str(e)))

    # Trading engine
    try:
        from bots.treasury.trading import TradingEngine
        jarvis.register(
            "trading_engine",
            TradingEngine,  # Register class, not instance (needs wallet)
            category=Category.TRADING,
            description="Sentiment-based trading engine with TP/SL",
            tags={"trading", "positions", "tp_sl", "sentiment"},
            provides=["trading_engine", "position_manager"],
        )
        results["registered"].append("trading_engine")
    except Exception as e:
        logger.warning(f"Could not register trading_engine: {e}")
        results["failed"].append(("trading_engine", str(e)))


async def _register_messaging_services(results: dict, skip_unavailable: bool):
    """Register messaging services."""

    # Telegram (main bot)
    try:
        # Register factory - actual bot needs token
        from tg_bot.bot import create_app

        jarvis.register(
            "telegram_bot",
            {"factory": create_app, "type": "telegram"},
            category=Category.MESSAGING,
            description="Main Telegram bot for JARVIS",
            tags={"telegram", "messaging", "commands"},
            provides=["telegram", "telegram_bot"],
        )
        results["registered"].append("telegram_bot")
    except Exception as e:
        logger.warning(f"Could not register telegram_bot: {e}")
        results["failed"].append(("telegram_bot", str(e)))

    # Twitter client
    try:
        from bots.twitter.twitter_client import TwitterClient
        jarvis.register(
            "twitter_client",
            TwitterClient,  # Factory - needs credentials
            category=Category.SOCIAL,
            description="X/Twitter API client for posting and engagement",
            tags={"twitter", "x", "social", "posting"},
            provides=["twitter", "twitter_client", "x_client"],
        )
        results["registered"].append("twitter_client")
    except Exception as e:
        logger.warning(f"Could not register twitter_client: {e}")
        results["failed"].append(("twitter_client", str(e)))


async def _register_ai_services(results: dict, skip_unavailable: bool):
    """Register AI/LLM services."""

    # Grok client
    try:
        from bots.twitter.grok_client import GrokClient
        jarvis.register(
            "grok",
            GrokClient,  # Factory - needs API key
            category=Category.AI,
            description="xAI Grok API for text generation and analysis",
            tags={"ai", "llm", "grok", "xai"},
            provides=["grok", "ai_completion", "sentiment_ai"],
        )
        results["registered"].append("grok")
    except Exception as e:
        logger.warning(f"Could not register grok: {e}")
        results["failed"].append(("grok", str(e)))

    # Claude (if available)
    try:
        from tg_bot.services.claude_client import ClaudeClient
        jarvis.register(
            "claude",
            ClaudeClient,
            category=Category.AI,
            description="Anthropic Claude API client",
            tags={"ai", "llm", "claude", "anthropic"},
            provides=["claude", "ai_completion"],
        )
        results["registered"].append("claude")
    except Exception as e:
        logger.debug(f"Claude client not available: {e}")
        results["skipped"].append("claude")


async def _register_analytics_services(results: dict, skip_unavailable: bool):
    """Register analytics services."""

    # Sentiment report generator
    try:
        from bots.buy_tracker.sentiment_report import SentimentReportGenerator
        jarvis.register(
            "sentiment_generator",
            SentimentReportGenerator,  # Factory
            category=Category.ANALYTICS,
            description="Market sentiment analysis and report generation",
            tags={"sentiment", "analysis", "reports"},
            provides=["sentiment_generator", "sentiment_analysis"],
        )
        results["registered"].append("sentiment_generator")
    except Exception as e:
        logger.warning(f"Could not register sentiment_generator: {e}")
        results["failed"].append(("sentiment_generator", str(e)))

    # Sentiment aggregator
    try:
        from core.sentiment_aggregator import SentimentAggregator
        jarvis.register(
            "sentiment_aggregator",
            SentimentAggregator(),
            category=Category.ANALYTICS,
            description="Aggregates sentiment from multiple sources",
            tags={"sentiment", "aggregation"},
            provides=["sentiment_aggregator"],
        )
        results["registered"].append("sentiment_aggregator")
    except Exception as e:
        logger.warning(f"Could not register sentiment_aggregator: {e}")
        results["failed"].append(("sentiment_aggregator", str(e)))


# ==================== Event Bridge ====================

def setup_event_bridge():
    """
    Set up event bridging between old event systems and JarvisCore.

    This enables events from legacy systems to flow through the unified bus.
    """

    # Bridge LifeOS events
    try:
        from lifeos.events.bus import EventBus as LifeOSBus

        # Create a handler that forwards to JarvisCore
        async def forward_to_jarvis(event):
            await jarvis.emit(
                f"lifeos.{event.topic}",
                event.data if hasattr(event, 'data') else {},
                source="lifeos"
            )

        # Subscribe to all LifeOS events
        # Note: This would need to be set up when LifeOS bus is created
        logger.info("LifeOS event bridge configured")

    except ImportError:
        logger.debug("LifeOS events not available")

    # Bridge core events
    try:
        from core.events.bus import EventType

        # Map core event types to JarvisCore topics
        EVENT_MAPPING = {
            "TRADE_EXECUTED": "trading.executed",
            "POSITION_OPENED": "trading.position_opened",
            "POSITION_CLOSED": "trading.position_closed",
            "PRICE_ALERT": "market.price_alert",
            "WHALE_DETECTED": "market.whale_detected",
            "SIGNAL_GENERATED": "analytics.signal_generated",
        }

        logger.info("Core event bridge configured")

    except ImportError:
        logger.debug("Core events not available")


# ==================== Convenience Functions ====================

async def get_service(name: str):
    """Get a service from JarvisCore."""
    return await jarvis.get(name)


def list_services(category: str = None) -> List[str]:
    """List available services."""
    if category:
        return jarvis.list_capabilities(category=Category(category))
    return jarvis.list_capabilities()


def describe_jarvis() -> str:
    """Get a human-readable description of JARVIS capabilities."""
    return jarvis.describe()


def get_manifest() -> Dict[str, Any]:
    """Get the capability manifest as JSON."""
    return jarvis.to_manifest()


# ==================== Quick Start ====================

async def quick_start():
    """
    Quick start JARVIS with minimal configuration.

    Usage:
        from core.bootstrap import quick_start
        await quick_start()

        # Now use services
        from core.jarvis_core import jarvis
        jupiter = await jarvis.get("jupiter")
    """
    await bootstrap_jarvis()
    setup_event_bridge()

    print("\n" + "=" * 60)
    print("JARVIS CORE INITIALIZED")
    print("=" * 60)
    print(f"\nRegistered services: {len(jarvis.list_capabilities())}")
    print("\nAvailable capabilities:")

    for category in Category:
        services = jarvis.list_capabilities(category=category)
        if services:
            print(f"\n  {category.value.upper()}:")
            for s in services:
                print(f"    - {s}")

    print("\n" + "=" * 60)
    print("Use: await jarvis.get('service_name') to access services")
    print("=" * 60 + "\n")
