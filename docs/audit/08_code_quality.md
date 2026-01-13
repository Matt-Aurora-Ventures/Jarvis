# Code Quality & Architecture Improvements (91-100)

## 91. Complete Type Hints

```python
# core/types.py
from typing import TypedDict, Literal, Optional, List, Dict, Any
from datetime import datetime

class TradeDict(TypedDict):
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    amount: float
    price: float
    status: Literal["pending", "filled", "cancelled"]
    created_at: datetime

class PositionDict(TypedDict):
    symbol: str
    size: float
    entry_price: float
    unrealized_pnl: float

class BacktestResultDict(TypedDict):
    symbol: str
    interval: str
    strategy: str
    total_trades: int
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    net_pnl: float

# Usage in functions:
def get_trades(symbol: str, limit: int = 100) -> List[TradeDict]:
    ...

def calculate_position(trades: List[TradeDict]) -> Optional[PositionDict]:
    ...
```

## 92. Dependency Injection

```python
# core/di/container.py
from typing import Type, TypeVar, Dict, Callable
from functools import lru_cache

T = TypeVar('T')

class Container:
    _instances: Dict[Type, object] = {}
    _factories: Dict[Type, Callable] = {}
    
    @classmethod
    def register(cls, interface: Type[T], factory: Callable[[], T]):
        cls._factories[interface] = factory
    
    @classmethod
    def resolve(cls, interface: Type[T]) -> T:
        if interface not in cls._instances:
            if interface not in cls._factories:
                raise ValueError(f"No factory registered for {interface}")
            cls._instances[interface] = cls._factories[interface]()
        return cls._instances[interface]
    
    @classmethod
    def reset(cls):
        cls._instances.clear()

# Usage:
# Container.register(DatabasePool, lambda: ConnectionPool("data/jarvis.db"))
# Container.register(CacheService, lambda: RedisCache())
# db = Container.resolve(DatabasePool)
```

## 93. Config Validation with Pydantic

```python
# core/config/schema.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List

class ProviderConfig(BaseModel):
    name: str
    api_key: Optional[str] = None
    enabled: bool = True
    priority: int = Field(ge=0, le=100, default=50)

class TradingConfig(BaseModel):
    max_position_pct: float = Field(ge=0, le=1, default=0.25)
    default_slippage_bps: float = Field(ge=0, default=2.0)
    risk_per_trade: float = Field(ge=0, le=0.1, default=0.02)

class MemoryConfig(BaseModel):
    target_cap: int = Field(ge=10, le=1000, default=200)
    min_cap: int = Field(ge=10, default=50)
    max_cap: int = Field(le=1000, default=300)
    
    @validator('max_cap')
    def max_greater_than_min(cls, v, values):
        if 'min_cap' in values and v < values['min_cap']:
            raise ValueError('max_cap must be >= min_cap')
        return v

class AppConfig(BaseModel):
    providers: List[ProviderConfig] = []
    trading: TradingConfig = TradingConfig()
    memory: MemoryConfig = MemoryConfig()
    debug: bool = False

def load_validated_config(path: str) -> AppConfig:
    import json
    with open(path) as f:
        data = json.load(f)
    return AppConfig(**data)
```

## 94. Code Documentation Standards

```python
# core/trading_pipeline.py (documented version)
def run_backtest(
    candles: List[Dict[str, Any]],
    symbol: str,
    interval: str,
    strategy: StrategyConfig,
) -> BacktestResult:
    """
    Run a deterministic backtest on historical candle data.
    
    This function simulates trading based on the provided strategy configuration,
    tracking equity curve, trades, and computing performance metrics.
    
    Args:
        candles: List of OHLCV candle dictionaries with keys:
            - timestamp: Unix timestamp (int)
            - open, high, low, close: Price values (float)
            - volume: Trading volume (float)
        symbol: Trading pair symbol (e.g., "BTC/USDC")
        interval: Candle interval (e.g., "1h", "4h", "1d")
        strategy: Strategy configuration including:
            - kind: Strategy type ("sma_cross", "rsi")
            - params: Strategy-specific parameters
            - fee_bps: Trading fee in basis points
            - slippage_bps: Expected slippage in basis points
    
    Returns:
        BacktestResult containing:
            - total_trades: Number of completed trades
            - win_rate: Percentage of profitable trades
            - sharpe_ratio: Risk-adjusted return metric
            - max_drawdown: Maximum peak-to-trough decline
            - net_pnl: Net profit/loss in USD
            - trades: List of individual trade records
    
    Raises:
        ValueError: If candles list is empty or malformed
    
    Example:
        >>> candles = load_candles("BTC", "1h")
        >>> config = StrategyConfig(kind="sma_cross", params={"fast": 5, "slow": 20})
        >>> result = run_backtest(candles, "BTC", "1h", config)
        >>> print(f"Sharpe: {result.sharpe_ratio:.2f}")
    """
    ...
```

## 95. Linting Configuration

```toml
# pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py311"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # Pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
    "ARG", # flake8-unused-arguments
    "SIM", # flake8-simplify
]
ignore = ["E501", "B008", "B905"]

[tool.ruff.isort]
known-first-party = ["core", "api", "plugins"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
plugins = ["pydantic.mypy"]

[tool.mypy.overrides]
module = "tests.*"
disallow_untyped_defs = false
```

## 96. Dead Code Removal Script

```python
# scripts/find_dead_code.py
import ast
import os
from pathlib import Path
from collections import defaultdict

class DeadCodeFinder(ast.NodeVisitor):
    def __init__(self):
        self.defined = defaultdict(set)
        self.used = set()
    
    def visit_FunctionDef(self, node):
        if not node.name.startswith('_'):
            self.defined['functions'].add(node.name)
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        self.defined['classes'].add(node.name)
        self.generic_visit(node)
    
    def visit_Name(self, node):
        self.used.add(node.id)
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        self.used.add(node.attr)
        self.generic_visit(node)

def find_dead_code(directory: Path):
    finder = DeadCodeFinder()
    
    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
            finder.visit(tree)
        except SyntaxError:
            continue
    
    dead_functions = finder.defined['functions'] - finder.used
    dead_classes = finder.defined['classes'] - finder.used
    
    print(f"Potentially unused functions: {dead_functions}")
    print(f"Potentially unused classes: {dead_classes}")

if __name__ == "__main__":
    find_dead_code(Path("core"))
```

## 97. Module Boundaries

```python
# core/__init__.py - Public API definition
"""
Core module for Jarvis.

Public API:
    - config: Configuration management
    - providers: AI provider integration
    - trading_pipeline: Trading and backtesting
    - memory: Memory management
    - encryption: Security utilities
"""

from core.config import load_config, save_local_config
from core.providers import call_provider, provider_health_check
from core.trading_pipeline import run_backtest, paper_trade_cycle, StrategyConfig
from core.memory import append_entry, get_recent_entries
from core.encryption import SecureVault, TokenManager

__all__ = [
    # Config
    "load_config",
    "save_local_config",
    # Providers
    "call_provider",
    "provider_health_check",
    # Trading
    "run_backtest",
    "paper_trade_cycle",
    "StrategyConfig",
    # Memory
    "append_entry",
    "get_recent_entries",
    # Security
    "SecureVault",
    "TokenManager",
]
```

## 98. API Consistency Layer

```python
# api/responses.py
from typing import Any, Dict, Optional, List
from pydantic import BaseModel

class APIResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

def success_response(data: Any, meta: Dict = None) -> Dict:
    return APIResponse(success=True, data=data, meta=meta).model_dump()

def error_response(code: str, message: str, details: Dict = None) -> Dict:
    return APIResponse(
        success=False,
        error={"code": code, "message": message, "details": details}
    ).model_dump()

def paginated_response(items: List, total: int, page: int, page_size: int) -> Dict:
    return success_response(
        data=items,
        meta={
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    )
```

## 99. Deprecation Warnings

```python
# core/deprecation.py
import warnings
import functools
from typing import Callable, Optional

def deprecated(
    reason: str,
    version: str,
    replacement: Optional[str] = None
) -> Callable:
    """Mark a function as deprecated."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = f"{func.__name__} is deprecated since v{version}: {reason}"
            if replacement:
                message += f" Use {replacement} instead."
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        
        wrapper.__doc__ = f"DEPRECATED: {reason}\n\n{func.__doc__ or ''}"
        return wrapper
    return decorator

# Usage:
@deprecated("Use new_function instead", version="3.8.0", replacement="new_function")
def old_function():
    pass
```

## 100. Plugin Architecture

```python
# core/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = None

class Plugin(ABC):
    """Base class for all Jarvis plugins."""
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin. Return True if successful."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Clean up resources."""
        pass
    
    async def on_message(self, message: str) -> Optional[str]:
        """Handle incoming message. Return response or None."""
        return None
    
    async def on_event(self, event_type: str, data: Dict[str, Any]):
        """Handle system event."""
        pass

class PluginManager:
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
    
    def register(self, plugin: Plugin):
        meta = plugin.metadata
        self.plugins[meta.name] = plugin
    
    async def initialize_all(self, config: Dict[str, Any]):
        for name, plugin in self.plugins.items():
            try:
                await plugin.initialize(config.get(name, {}))
            except Exception as e:
                print(f"Failed to initialize {name}: {e}")
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        for plugin in self.plugins.values():
            await plugin.on_event(event_type, data)

# Example plugin:
class HelloWorldPlugin(Plugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="hello-world",
            version="1.0.0",
            description="Simple greeting plugin",
            author="Jarvis Team"
        )
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        return True
    
    async def shutdown(self):
        pass
    
    async def on_message(self, message: str) -> Optional[str]:
        if "hello" in message.lower():
            return "Hello! How can I help you?"
        return None
```
