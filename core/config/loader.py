"""
JARVIS Configuration Loader - Single Source of Truth

Consolidates all configuration loading into one module:
- Environment variables (.env)
- Config files (JSON, YAML)
- Runtime overrides
- Validation and defaults

Usage:
    from core.config import config, get_config

    # Access settings
    token = config.telegram.bot_token
    rpc_url = config.solana.rpc_url

    # Check if configured
    if config.is_configured("telegram"):
        start_telegram_bot()
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
CONFIG_DIR = ROOT / "config"

T = TypeVar("T")


def _load_env_file(path: Path) -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}

    if not path.exists():
        return env_vars

    try:
        content = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = path.read_text(encoding='utf-16')
        except Exception:
            content = path.read_text(encoding='latin-1')

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if '=' not in line:
            continue

        key, _, value = line.partition('=')
        key = key.strip()
        value = value.strip()

        # Remove quotes
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        env_vars[key] = value

    return env_vars


def _get_env(key: str, default: T = None, cast: Type[T] = str) -> T:
    """Get environment variable with type casting."""
    value = os.environ.get(key)

    if value is None:
        return default

    if cast == bool:
        return value.lower() in ('true', '1', 'yes', 'on')

    if cast == int:
        try:
            return int(value)
        except ValueError:
            return default

    if cast == float:
        try:
            return float(value)
        except ValueError:
            return default

    if cast == list:
        return [v.strip() for v in value.split(',') if v.strip()]

    return value


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""
    bot_token: str = ""
    admin_ids: List[int] = field(default_factory=list)
    admin_chat_id: str = ""
    broadcast_chat_id: str = ""
    buy_bot_token: str = ""
    buy_bot_chat_id: str = ""
    reply_mode: str = "mentions"
    reply_cooldown: int = 12
    reply_model: str = "grok-3"
    claude_model: str = "claude-sonnet-4-20250514"

    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        admin_ids_str = _get_env("TELEGRAM_ADMIN_IDS", "")
        admin_ids = []
        if admin_ids_str:
            admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

        return cls(
            bot_token=_get_env("TELEGRAM_BOT_TOKEN", ""),
            admin_ids=admin_ids,
            admin_chat_id=_get_env("TELEGRAM_ADMIN_CHAT_ID", ""),
            broadcast_chat_id=_get_env("TELEGRAM_BROADCAST_CHAT_ID", ""),
            buy_bot_token=_get_env("TELEGRAM_BUY_BOT_TOKEN", ""),
            buy_bot_chat_id=_get_env("TELEGRAM_BUY_BOT_CHAT_ID", ""),
            reply_mode=_get_env("TG_REPLY_MODE", "mentions"),
            reply_cooldown=_get_env("TG_REPLY_COOLDOWN_SECONDS", 12, int),
            reply_model=_get_env("TG_REPLY_MODEL", "grok-3"),
            claude_model=_get_env("TG_CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        )


@dataclass
class SolanaConfig:
    """Solana blockchain configuration."""
    network: str = "devnet"
    rpc_url: str = "https://api.devnet.solana.com"
    ws_url: str = "wss://api.devnet.solana.com"
    helius_api_key: str = ""
    helius_rpc_url: str = ""
    treasury_wallet_path: str = ""
    active_wallet_path: str = ""
    profit_wallet_path: str = ""

    @classmethod
    def from_env(cls) -> 'SolanaConfig':
        return cls(
            network=_get_env("SOLANA_NETWORK", "devnet"),
            rpc_url=_get_env("SOLANA_RPC_URL", "https://api.devnet.solana.com"),
            ws_url=_get_env("SOLANA_WS_URL", "wss://api.devnet.solana.com"),
            helius_api_key=_get_env("HELIUS_API_KEY", ""),
            helius_rpc_url=_get_env("HELIUS_RPC_URL", ""),
            treasury_wallet_path=_get_env("TREASURY_WALLET_PATH", ""),
            active_wallet_path=_get_env("ACTIVE_WALLET_PATH", ""),
            profit_wallet_path=_get_env("PROFIT_WALLET_PATH", ""),
        )


@dataclass
class TreasuryConfig:
    """Treasury management configuration."""
    reserve_pct: int = 60
    active_pct: int = 30
    profit_pct: int = 10
    live_mode: bool = False
    circuit_breaker_threshold: int = 10
    max_single_trade_pct: float = 2.0
    daily_loss_limit_pct: float = 5.0
    admin_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> 'TreasuryConfig':
        admin_ids_str = _get_env("TREASURY_ADMIN_IDS", "")
        admin_ids = []
        if admin_ids_str:
            admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip().isdigit()]

        return cls(
            reserve_pct=_get_env("TREASURY_RESERVE_PCT", 60, int),
            active_pct=_get_env("TREASURY_ACTIVE_PCT", 30, int),
            profit_pct=_get_env("TREASURY_PROFIT_PCT", 10, int),
            live_mode=_get_env("TREASURY_LIVE_MODE", False, bool),
            circuit_breaker_threshold=_get_env("CIRCUIT_BREAKER_THRESHOLD", 10, int),
            max_single_trade_pct=_get_env("MAX_SINGLE_TRADE_PCT", 2.0, float),
            daily_loss_limit_pct=_get_env("DAILY_LOSS_LIMIT_PCT", 5.0, float),
            admin_ids=admin_ids,
        )


@dataclass
class LLMConfig:
    """LLM provider configuration."""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    xai_api_key: str = ""
    xai_model: str = "grok-3-mini"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.2-3b-instruct:free"

    @classmethod
    def from_env(cls) -> 'LLMConfig':
        return cls(
            openai_api_key=_get_env("OPENAI_API_KEY", ""),
            anthropic_api_key=_get_env("ANTHROPIC_API_KEY", ""),
            xai_api_key=_get_env("XAI_API_KEY", ""),
            xai_model=_get_env("XAI_MODEL", "grok-3-mini"),
            groq_api_key=_get_env("GROQ_API_KEY", ""),
            groq_model=_get_env("GROQ_MODEL", "llama-3.3-70b-versatile"),
            ollama_url=_get_env("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=_get_env("OLLAMA_MODEL", "llama3.2"),
            openrouter_api_key=_get_env("OPENROUTER_API_KEY", ""),
            openrouter_model=_get_env("OPENROUTER_MODEL", "meta-llama/llama-3.2-3b-instruct:free"),
        )


@dataclass
class APIConfig:
    """API server configuration."""
    host: str = "0.0.0.0"
    port: int = 8766
    reload: bool = True
    cors_origins: List[str] = field(default_factory=lambda: ["http://localhost:3000"])
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    jwt_secret: str = "change-me-in-production"

    @classmethod
    def from_env(cls) -> 'APIConfig':
        origins = _get_env("CORS_ORIGINS", "http://localhost:3000")
        origin_list = [o.strip() for o in origins.split(",")]

        return cls(
            host=_get_env("API_HOST", "0.0.0.0"),
            port=_get_env("API_PORT", 8766, int),
            reload=_get_env("API_RELOAD", True, bool),
            cors_origins=origin_list,
            rate_limit_enabled=_get_env("RATE_LIMIT_ENABLED", True, bool),
            rate_limit_requests=_get_env("RATE_LIMIT_REQUESTS", 100, int),
            rate_limit_window=_get_env("RATE_LIMIT_WINDOW_SECONDS", 60, int),
            jwt_secret=_get_env("JWT_SECRET", "change-me-in-production"),
        )


@dataclass
class SecurityConfig:
    """Security configuration."""
    secure_password: str = ""
    admin_key: str = ""
    allowed_ips: List[str] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        ips = _get_env("ALLOWED_IPS", "")
        ip_list = [ip.strip() for ip in ips.split(",") if ip.strip()]

        return cls(
            secure_password=_get_env("JARVIS_SECURE_PASSWORD", ""),
            admin_key=_get_env("JARVIS_ADMIN_KEY", ""),
            allowed_ips=ip_list,
        )


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""
    sentry_dsn: str = ""
    metrics_enabled: bool = False
    metrics_port: int = 9090
    log_level: str = "INFO"
    debug: bool = False

    @classmethod
    def from_env(cls) -> 'MonitoringConfig':
        return cls(
            sentry_dsn=_get_env("SENTRY_DSN", ""),
            metrics_enabled=_get_env("METRICS_ENABLED", False, bool),
            metrics_port=_get_env("METRICS_PORT", 9090, int),
            log_level=_get_env("LOG_LEVEL", "INFO"),
            debug=_get_env("DEBUG", False, bool),
        )


@dataclass
class JarvisConfig:
    """Complete JARVIS configuration."""
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    solana: SolanaConfig = field(default_factory=SolanaConfig)
    treasury: TreasuryConfig = field(default_factory=TreasuryConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    api: APIConfig = field(default_factory=APIConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Runtime state
    _loaded: bool = False
    _env_file_loaded: bool = False

    @classmethod
    def load(cls, env_path: Path = ENV_FILE) -> 'JarvisConfig':
        """Load configuration from environment."""
        # Load .env file into os.environ
        env_vars = _load_env_file(env_path)
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value

        config = cls(
            telegram=TelegramConfig.from_env(),
            solana=SolanaConfig.from_env(),
            treasury=TreasuryConfig.from_env(),
            llm=LLMConfig.from_env(),
            api=APIConfig.from_env(),
            security=SecurityConfig.from_env(),
            monitoring=MonitoringConfig.from_env(),
        )
        config._loaded = True
        config._env_file_loaded = env_path.exists()

        logger.info(f"Configuration loaded (.env: {config._env_file_loaded})")
        return config

    def is_configured(self, section: str) -> bool:
        """Check if a configuration section has required values."""
        checks = {
            "telegram": bool(self.telegram.bot_token),
            "solana": bool(self.solana.rpc_url),
            "treasury": self.treasury.reserve_pct + self.treasury.active_pct + self.treasury.profit_pct == 100,
            "llm": bool(self.llm.xai_api_key or self.llm.groq_api_key or self.llm.openai_api_key),
            "security": bool(self.security.secure_password),
        }
        return checks.get(section, False)

    def get_available_llm_providers(self) -> List[str]:
        """Get list of configured LLM providers."""
        providers = []
        if self.llm.openai_api_key:
            providers.append("openai")
        if self.llm.anthropic_api_key:
            providers.append("anthropic")
        if self.llm.xai_api_key:
            providers.append("xai")
        if self.llm.groq_api_key:
            providers.append("groq")
        if self.llm.openrouter_api_key:
            providers.append("openrouter")
        # Ollama is always available (local)
        providers.append("ollama")
        return providers

    def to_dict(self, hide_secrets: bool = True) -> Dict[str, Any]:
        """Convert config to dictionary."""
        from dataclasses import asdict

        data = {
            "telegram": asdict(self.telegram),
            "solana": asdict(self.solana),
            "treasury": asdict(self.treasury),
            "llm": asdict(self.llm),
            "api": asdict(self.api),
            "security": asdict(self.security),
            "monitoring": asdict(self.monitoring),
        }

        if hide_secrets:
            # Mask sensitive values
            for section in data.values():
                for key in list(section.keys()):
                    if any(s in key.lower() for s in ['token', 'key', 'secret', 'password']):
                        value = section[key]
                        if value:
                            section[key] = f"{value[:4]}...{value[-4:]}" if len(str(value)) > 8 else "****"

        return data


# Global configuration instance
_config: Optional[JarvisConfig] = None


def get_config() -> JarvisConfig:
    """Get global configuration instance."""
    global _config
    if _config is None:
        _config = JarvisConfig.load()
    return _config


def reload_config() -> JarvisConfig:
    """Reload configuration from environment."""
    global _config
    _config = JarvisConfig.load()
    return _config


# Convenience alias
config = property(lambda self: get_config())


if __name__ == "__main__":
    import json

    print("JARVIS Configuration Loader")
    print("=" * 40)

    cfg = get_config()

    print(f"\nLoaded: {cfg._loaded}")
    print(f".env file: {cfg._env_file_loaded}")

    print("\nConfiguration Sections:")
    for section in ["telegram", "solana", "treasury", "llm", "security"]:
        status = "OK" if cfg.is_configured(section) else "NOT CONFIGURED"
        print(f"  {section}: {status}")

    print(f"\nAvailable LLM providers: {cfg.get_available_llm_providers()}")

    print("\nFull config (secrets hidden):")
    print(json.dumps(cfg.to_dict(hide_secrets=True), indent=2))
