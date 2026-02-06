"""
Configuration validation with Pydantic and ConfigSchema.

Provides:
- Pydantic models for structured config validation
- ConfigSchema class for dynamic validation rules
- ValidationError dataclass for error reporting
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Callable, Tuple, Union, Type
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
import json
import re
import logging

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """AI provider configuration."""
    name: str
    api_key: Optional[str] = None
    enabled: bool = True
    priority: int = Field(ge=0, le=100, default=50)
    timeout: int = Field(ge=1, le=300, default=30)
    max_retries: int = Field(ge=0, le=10, default=3)


class TradingConfig(BaseModel):
    """Trading configuration."""
    max_position_pct: float = Field(ge=0, le=1, default=0.25)
    default_slippage_bps: float = Field(ge=0, default=2.0)
    risk_per_trade: float = Field(ge=0, le=0.1, default=0.02)
    stop_loss_pct: float = Field(ge=0, le=0.5, default=0.05)
    take_profit_pct: float = Field(ge=0, le=1.0, default=0.1)


class MemoryConfig(BaseModel):
    """Memory management configuration."""
    target_cap: int = Field(ge=10, le=1000, default=200)
    min_cap: int = Field(ge=10, default=50)
    max_cap: int = Field(le=1000, default=300)
    quality_threshold: float = Field(ge=0, le=1, default=0.3)
    
    @validator('max_cap')
    def max_greater_than_min(cls, v, values):
        if 'min_cap' in values and v < values['min_cap']:
            raise ValueError('max_cap must be >= min_cap')
        return v


class SecurityConfig(BaseModel):
    """Security configuration."""
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(ge=1, default=100)
    rate_limit_window: int = Field(ge=1, default=60)
    jwt_expiry_minutes: int = Field(ge=1, default=30)
    session_timeout: int = Field(ge=60, default=3600)
    ip_allowlist: List[str] = Field(default_factory=list)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    format: str = "structured"
    file_path: Optional[str] = None
    max_file_size_mb: int = Field(ge=1, le=1000, default=100)
    backup_count: int = Field(ge=0, le=100, default=5)


class AppConfig(BaseModel):
    """Main application configuration."""
    environment: str = Field(default="development", pattern="^(development|staging|production)$")
    debug: bool = False
    providers: List[ProviderConfig] = Field(default_factory=list)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    class Config:
        extra = "allow"


def load_validated_config(path: str = "lifeos.config.json") -> AppConfig:
    """Load and validate configuration from file."""
    config_path = Path(path)
    if not config_path.exists():
        return AppConfig()
    
    with open(config_path) as f:
        data = json.load(f)
    
    return AppConfig(**data)


def validate_config(data: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validate configuration data without loading."""
    errors = []
    try:
        AppConfig(**data)
        return True, []
    except Exception as e:
        errors.append(str(e))
        return False, errors
