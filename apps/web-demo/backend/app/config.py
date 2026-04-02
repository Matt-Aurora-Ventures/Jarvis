"""
Configuration management for JARVIS Web Demo.
Loads from environment variables with secure defaults.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings with validation."""

    # App
    APP_NAME: str = "JARVIS Web Demo"
    APP_ENV: str = "development"  # development, staging, production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api"

    # Security (Rule #1 & #2: Server-side enforcement)
    SECRET_KEY: str  # Required - used for JWT signing
    JWT_SECRET: str  # Separate JWT secret
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 12

    # CORS (Rule #1: Only allowed origins)
    CORS_ORIGINS: list[str] = ["https://jarvislife.io", "http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Rate Limiting (Rule #2: Enforce server-side)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_READ_ENDPOINTS: int = 10
    RATE_LIMIT_WRITE_ENDPOINTS: int = 5
    RATE_LIMIT_TRADE_ENDPOINTS: int = 3
    RATE_LIMIT_AUTH_ENDPOINTS: int = 5

    # Database
    DATABASE_URL: str  # postgresql://user:pass@host:port/db
    REDIS_URL: str = "redis://localhost:6379/0"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Solana
    SOLANA_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    SOLANA_NETWORK: str = "mainnet-beta"  # mainnet-beta, devnet, testnet
    JUPITER_API_URL: str = "https://quote-api.jup.ag/v6"

    # Trading Limits (Rule #1: Server decides limits)
    MAX_POSITIONS: int = 50
    MAX_POSITION_SIZE_SOL: float = 10.0
    MIN_POSITION_SIZE_SOL: float = 0.01
    MAX_SLIPPAGE_BPS: int = 100  # 1%
    SUCCESS_FEE_PERCENTAGE: float = 0.5  # 0.5% on wins

    # AI & Sentiment
    # Option 1: Cloud AI (Grok)
    XAI_API_KEY: Optional[str] = None
    XAI_MODEL: str = "grok-beta"
    XAI_ENABLED: bool = True

    # Option 2: Local AI (Ollama - zero cost, privacy-first)
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3-coder"  # or llama3, mistral, etc.

    # Bags.fm Integration (Required for trading)
    BAGS_API_KEY: Optional[str] = None
    BAGS_API_URL: str = "http://bags-api:3000"  # Local bags-swap-api service
    BAGS_ADMIN_KEY: Optional[str] = None
    SERVICE_FEE_BPS: int = 50  # 0.5% service fee

    # Supervisor Integration
    JARVIS_STATE_DIR: str = "/app/shared_state"

    # Self-Correcting AI
    ANTHROPIC_API_KEY: Optional[str] = None  # For Claude
    OLLAMA_ANTHROPIC_BASE_URL: Optional[str] = "http://ollama:11434/v1"  # For Ollama with Anthropic Messages API

    # Wallet Encryption
    WALLET_ENCRYPTION_ALGORITHM: str = "AES-256-GCM"
    WALLET_KEY_DERIVATION: str = "Argon2"
    WALLET_ARGON2_TIME_COST: int = 3
    WALLET_ARGON2_MEMORY_COST: int = 65536  # 64MB
    WALLET_ARGON2_PARALLELISM: int = 4

    # Security Headers (Rule #3: Enforce backend)
    ENABLE_SECURITY_HEADERS: bool = True
    HSTS_MAX_AGE: int = 31536000  # 1 year

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"

    # Demo Profile
    DEMO_TRADING_PROFILE: str = "demo"
    DEMO_WALLET_PASSWORD: Optional[str] = None

    @field_validator("APP_ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        """Validate environment."""
        if v not in ("development", "staging", "production"):
            raise ValueError("APP_ENV must be development, staging, or production")
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.APP_ENV == "development"

    @property
    def ai_provider(self) -> str:
        """Get the active AI provider."""
        if self.OLLAMA_ENABLED:
            return "ollama"
        elif self.XAI_ENABLED and self.XAI_API_KEY:
            return "grok"
        return "none"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()


# Security validation on startup
def validate_security_settings():
    """
    Validate security settings on startup.
    Rule #2: Enforce everything server-side, including config validation.
    """
    errors = []

    # Check required secrets
    if not settings.SECRET_KEY or len(settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be at least 32 characters")

    if not settings.JWT_SECRET or len(settings.JWT_SECRET) < 32:
        errors.append("JWT_SECRET must be at least 32 characters")

    # Production checks
    if settings.is_production:
        if settings.DEBUG:
            errors.append("DEBUG must be False in production")

        if "localhost" in str(settings.CORS_ORIGINS):
            errors.append("CORS_ORIGINS should not include localhost in production")

        if not settings.DATABASE_URL.startswith("postgresql"):
            errors.append("Production requires PostgreSQL database")

        if settings.HSTS_MAX_AGE < 31536000:
            errors.append("HSTS_MAX_AGE should be at least 1 year in production")

    # AI provider check
    if settings.XAI_ENABLED and not settings.XAI_API_KEY:
        errors.append("XAI_API_KEY required when XAI_ENABLED=True")

    if not settings.XAI_ENABLED and not settings.OLLAMA_ENABLED:
        print("WARNING: No AI provider enabled. Sentiment features will be disabled.")

    if errors:
        raise ValueError(f"Security configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    print(f"✓ Security configuration validated ({settings.APP_ENV})")
    print(f"✓ AI Provider: {settings.ai_provider}")


# Export settings
__all__ = ["settings", "validate_security_settings"]
