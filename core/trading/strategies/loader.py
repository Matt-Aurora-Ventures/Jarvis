"""
Strategy Loader
Prompt #83: Treasury Strategy Manager - Dynamic strategy loading

Loads and manages trading strategies from configuration.
"""

import asyncio
import importlib
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
import yaml

from core.trading.strategies.base import (
    TradingStrategy,
    StrategyConfig,
    TradeSignal,
    MarketData,
)

logger = logging.getLogger("jarvis.strategies.loader")


# =============================================================================
# STRATEGY REGISTRY
# =============================================================================

class StrategyRegistry:
    """Registry of available strategy implementations"""

    _strategies: Dict[str, Type[TradingStrategy]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a strategy class"""
        def decorator(strategy_class: Type[TradingStrategy]):
            cls._strategies[name] = strategy_class
            logger.debug(f"Registered strategy: {name}")
            return strategy_class
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[Type[TradingStrategy]]:
        """Get a strategy class by name"""
        return cls._strategies.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered strategies"""
        return list(cls._strategies.keys())


# =============================================================================
# STRATEGY LOADER
# =============================================================================

@dataclass
class LoadedStrategy:
    """A loaded and initialized strategy"""
    instance: TradingStrategy
    config: StrategyConfig
    loaded_at: datetime
    config_path: Optional[str] = None


class StrategyLoader:
    """
    Dynamically loads and manages trading strategies.

    Features:
    - Load strategies from YAML config
    - Hot-reload individual strategies
    - Enable/disable strategies
    - Strategy discovery
    """

    def __init__(
        self,
        config_path: str = None,
        strategies_dir: str = None,
    ):
        self.config_path = config_path or os.getenv(
            "STRATEGIES_CONFIG",
            "config/strategies.yaml"
        )
        self.strategies_dir = strategies_dir or os.getenv(
            "STRATEGIES_DIR",
            "core/trading/strategies/implementations"
        )

        self._strategies: Dict[str, LoadedStrategy] = {}
        self._config: Dict[str, Any] = {}

    # =========================================================================
    # LOADING
    # =========================================================================

    async def load_all(self) -> List[str]:
        """
        Load all strategies from configuration.

        Returns:
            List of loaded strategy names
        """
        # Discover and import strategy implementations
        await self._discover_strategies()

        # Load config
        self._load_config()

        loaded = []
        for name, strategy_config in self._config.get("strategies", {}).items():
            try:
                await self.load_strategy(name, strategy_config)
                loaded.append(name)
            except Exception as e:
                logger.error(f"Failed to load strategy {name}: {e}")

        logger.info(f"Loaded {len(loaded)} strategies: {loaded}")
        return loaded

    async def load_strategy(
        self,
        name: str,
        config_dict: Dict[str, Any] = None,
    ) -> TradingStrategy:
        """
        Load a single strategy.

        Args:
            name: Strategy name
            config_dict: Optional config override

        Returns:
            Loaded strategy instance
        """
        # Get config
        if config_dict is None:
            config_dict = self._config.get("strategies", {}).get(name, {})

        if not config_dict:
            raise ValueError(f"No configuration found for strategy: {name}")

        # Get strategy class
        strategy_class = StrategyRegistry.get(config_dict.get("type", name))
        if not strategy_class:
            raise ValueError(f"Strategy type not found: {config_dict.get('type', name)}")

        # Build config
        config = StrategyConfig(
            name=name,
            version=config_dict.get("version", "1.0.0"),
            enabled=config_dict.get("enabled", True),
            max_allocation_pct=config_dict.get("max_allocation_pct", 0.20),
            max_position_count=config_dict.get("max_position_count", 5),
            max_position_size_pct=config_dict.get("max_position_size_pct", 0.05),
            max_drawdown_pct=config_dict.get("max_drawdown_pct", 0.10),
            stop_loss_pct=config_dict.get("stop_loss_pct", 0.05),
            take_profit_pct=config_dict.get("take_profit_pct", 0.15),
            min_interval_seconds=config_dict.get("min_interval_seconds", 300),
            cooldown_after_loss_seconds=config_dict.get("cooldown_after_loss_seconds", 3600),
            parameters=config_dict.get("parameters", {}),
            description=config_dict.get("description", ""),
            author=config_dict.get("author", ""),
            tags=config_dict.get("tags", []),
        )

        # Instantiate
        instance = strategy_class(config)
        await instance.initialize()

        # Store
        self._strategies[name] = LoadedStrategy(
            instance=instance,
            config=config,
            loaded_at=datetime.now(timezone.utc),
            config_path=self.config_path,
        )

        logger.info(f"Loaded strategy: {name} (type={config_dict.get('type', name)})")
        return instance

    async def reload_strategy(self, name: str) -> TradingStrategy:
        """
        Reload a strategy from configuration.

        Args:
            name: Strategy to reload

        Returns:
            Reloaded strategy instance
        """
        # Shutdown existing
        if name in self._strategies:
            await self._strategies[name].instance.shutdown()
            del self._strategies[name]

        # Reload config
        self._load_config()

        # Load fresh
        return await self.load_strategy(name)

    async def unload_strategy(self, name: str):
        """Unload a strategy"""
        if name in self._strategies:
            await self._strategies[name].instance.shutdown()
            del self._strategies[name]
            logger.info(f"Unloaded strategy: {name}")

    # =========================================================================
    # DISCOVERY
    # =========================================================================

    async def _discover_strategies(self):
        """Discover and import strategy implementations"""
        strategies_path = Path(self.strategies_dir)

        if not strategies_path.exists():
            logger.warning(f"Strategies directory not found: {strategies_path}")
            return

        for file in strategies_path.glob("*.py"):
            if file.name.startswith("_"):
                continue

            try:
                module_path = str(file).replace("/", ".").replace("\\", ".").replace(".py", "")
                importlib.import_module(module_path)
                logger.debug(f"Imported strategy module: {module_path}")
            except Exception as e:
                logger.error(f"Failed to import {file}: {e}")

    def _load_config(self):
        """Load strategy configuration from YAML"""
        config_path = Path(self.config_path)

        if not config_path.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            self._config = {"strategies": {}}
            return

        with open(config_path) as f:
            self._config = yaml.safe_load(f) or {}

        logger.debug(f"Loaded config from {config_path}")

    # =========================================================================
    # MANAGEMENT
    # =========================================================================

    def get_strategy(self, name: str) -> Optional[TradingStrategy]:
        """Get a loaded strategy by name"""
        loaded = self._strategies.get(name)
        return loaded.instance if loaded else None

    def get_all_strategies(self) -> List[TradingStrategy]:
        """Get all loaded strategies"""
        return [s.instance for s in self._strategies.values()]

    def get_enabled_strategies(self) -> List[TradingStrategy]:
        """Get only enabled strategies"""
        return [
            s.instance for s in self._strategies.values()
            if s.instance.is_enabled
        ]

    def enable_strategy(self, name: str) -> bool:
        """Enable a strategy"""
        strategy = self.get_strategy(name)
        if strategy:
            strategy.enable()
            logger.info(f"Enabled strategy: {name}")
            return True
        return False

    def disable_strategy(self, name: str) -> bool:
        """Disable a strategy"""
        strategy = self.get_strategy(name)
        if strategy:
            strategy.disable()
            logger.info(f"Disabled strategy: {name}")
            return True
        return False

    def list_strategies(self) -> List[Dict[str, Any]]:
        """List all loaded strategies with status"""
        return [
            {
                "name": name,
                "type": type(loaded.instance).__name__,
                "enabled": loaded.instance.is_enabled,
                "loaded_at": loaded.loaded_at.isoformat(),
                "config": loaded.config.to_dict(),
                "stats": loaded.instance.get_stats(),
            }
            for name, loaded in self._strategies.items()
        ]

    # =========================================================================
    # EXECUTION
    # =========================================================================

    async def run_analysis(
        self,
        market_data: MarketData,
    ) -> List[TradeSignal]:
        """
        Run all enabled strategies on market data.

        Args:
            market_data: Current market data

        Returns:
            List of generated signals
        """
        signals = []

        for strategy in self.get_enabled_strategies():
            try:
                # Check if strategy can trade
                can_trade, reason = strategy.can_trade()
                if not can_trade:
                    logger.debug(f"Strategy {strategy.name} skipped: {reason}")
                    continue

                # Run analysis
                signal = await strategy.analyze(market_data)
                if signal:
                    signals.append(signal)

                # Check exits for existing positions
                for position in strategy.get_open_positions():
                    exit_signal = await strategy.should_exit(position, market_data)
                    if exit_signal:
                        signals.append(exit_signal)

            except Exception as e:
                logger.error(f"Strategy {strategy.name} analysis failed: {e}")

        return signals


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_strategy_endpoints(loader: StrategyLoader):
    """Create strategy management API endpoints"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/treasury/strategies", tags=["Strategies"])

    class StrategyAction(BaseModel):
        action: str  # "enable", "disable", "reload"

    @router.get("")
    async def list_strategies():
        """List all loaded strategies"""
        return loader.list_strategies()

    @router.get("/{name}")
    async def get_strategy(name: str):
        """Get strategy details"""
        strategy = loader.get_strategy(name)
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")

        loaded = loader._strategies.get(name)
        return {
            "name": name,
            "type": type(strategy).__name__,
            "enabled": strategy.is_enabled,
            "loaded_at": loaded.loaded_at.isoformat() if loaded else None,
            "config": loaded.config.to_dict() if loaded else {},
            "stats": strategy.get_stats(),
            "positions": [
                {
                    "token_mint": p.token_mint,
                    "symbol": p.symbol,
                    "entry_price": str(p.entry_price),
                    "size_sol": str(p.size_sol),
                    "is_open": p.is_open,
                }
                for p in strategy.positions.values()
            ],
        }

    @router.post("/{name}/action")
    async def strategy_action(name: str, action: StrategyAction):
        """Perform action on strategy"""
        if action.action == "enable":
            if loader.enable_strategy(name):
                return {"status": "enabled"}
            raise HTTPException(status_code=404, detail="Strategy not found")

        elif action.action == "disable":
            if loader.disable_strategy(name):
                return {"status": "disabled"}
            raise HTTPException(status_code=404, detail="Strategy not found")

        elif action.action == "reload":
            try:
                await loader.reload_strategy(name)
                return {"status": "reloaded"}
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action.action}")

    @router.get("/registry/available")
    async def list_available():
        """List all registered strategy types"""
        return StrategyRegistry.list_all()

    return router


# =============================================================================
# SINGLETON
# =============================================================================

_loader: Optional[StrategyLoader] = None


def get_strategy_loader() -> StrategyLoader:
    """Get or create the strategy loader singleton"""
    global _loader
    if _loader is None:
        _loader = StrategyLoader()
    return _loader
