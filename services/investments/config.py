"""Investment service configuration — loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


_ENV_ALREADY_LOADED = False


def load_investment_env(env_file: str | Path | None = None) -> None:
    """Load service-local .env values without overriding real environment vars."""
    global _ENV_ALREADY_LOADED

    if env_file is not None:
        load_dotenv(dotenv_path=Path(env_file), override=False)
        return

    if _ENV_ALREADY_LOADED:
        return

    service_dir = Path(__file__).resolve().parent
    repo_root = service_dir.parents[1]
    for candidate in (service_dir / ".env", repo_root / ".env"):
        if candidate.exists():
            load_dotenv(dotenv_path=candidate, override=False)

    _ENV_ALREADY_LOADED = True


load_investment_env()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float = 0.0) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int = 0) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class InvestmentConfig:
    # --- LLM Keys ---
    xai_api_key: str = field(default_factory=lambda: _env("XAI_API_KEY"))
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))

    # --- Database ---
    database_url: str = field(
        default_factory=lambda: _env(
            "DATABASE_URL",
            "postgresql://jarvis:jarvis_dev@localhost:5433/jarvis_investments",
        )
    )
    redis_url: str = field(
        default_factory=lambda: _env("REDIS_URL", "redis://localhost:6380")
    )

    # --- Ethereum Mainnet (EVM) ---
    base_rpc_url: str = field(
        default_factory=lambda: _env(
            "ETH_RPC_URL", _env("BASE_RPC_URL", "https://eth.llamarpc.com")
        )
    )
    management_wallet_key: str = field(
        default_factory=lambda: _env("MANAGEMENT_WALLET_KEY")
    )
    basket_address: str = field(default_factory=lambda: _env("BASKET_ADDRESS"))

    # --- Solana ---
    solana_rpc_url: str = field(
        default_factory=lambda: _env(
            "SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"
        )
    )
    solana_wallet_key: str = field(
        default_factory=lambda: _env("SOLANA_WALLET_KEY")
    )
    staking_pool_address: str = field(
        default_factory=lambda: _env("STAKING_POOL_ADDRESS")
    )
    authority_reward_account: str = field(
        default_factory=lambda: _env("AUTHORITY_REWARD_ACCOUNT")
    )

    # --- Price Feeds ---
    birdeye_api_key: str = field(default_factory=lambda: _env("BIRDEYE_API_KEY"))

    # --- Operational ---
    dry_run: bool = field(default_factory=lambda: _env_bool("DRY_RUN", True))
    api_port: int = field(
        default_factory=lambda: _env_int("INVESTMENT_API_PORT", 8770)
    )
    basket_id: str = field(default_factory=lambda: _env("BASKET_ID", "alpha"))

    # --- Safety Limits ---
    max_single_token_pct: float = 0.30
    max_rebalance_change_pct: float = 0.25
    max_daily_cumulative_pct: float = 0.40
    max_correlated_exposure_pct: float = 0.60
    min_token_liquidity_usd: float = 50_000.0
    max_daily_bridge_usd: float = 50_000.0
    max_single_bridge_usd: float = 10_000.0
    bridge_threshold_usd: float = 50.0
    bridge_max_gas_gwei: float = 5.0
    enable_bridge_automation: bool = field(
        default_factory=lambda: _env_bool("ENABLE_BRIDGE_AUTOMATION", False)
    )
    enable_staking_automation: bool = field(
        default_factory=lambda: _env_bool("ENABLE_STAKING_AUTOMATION", False)
    )

    # --- API Authentication ---
    admin_key: str = field(default_factory=lambda: _env("INVESTMENT_ADMIN_KEY"))

    # --- LLM Models ---
    grok_sentiment_model: str = "grok-4-1-fast-non-reasoning"
    grok_trader_model: str = "grok-4-1-fast-non-reasoning"
    claude_risk_model: str = "claude-sonnet-4-6"
    chatgpt_macro_model: str = "gpt-4o"

    def validate(self) -> list[str]:
        """Return list of missing required configuration items."""
        missing = []
        if not self.dry_run:
            if not self.xai_api_key:
                missing.append("XAI_API_KEY (required when DRY_RUN=false)")
            if not self.anthropic_api_key:
                missing.append("ANTHROPIC_API_KEY (required when DRY_RUN=false)")
            if not self.openai_api_key:
                missing.append("OPENAI_API_KEY (required when DRY_RUN=false)")
            if not self.management_wallet_key:
                missing.append("MANAGEMENT_WALLET_KEY (required when DRY_RUN=false)")
            if not self.basket_address:
                missing.append("BASKET_ADDRESS (required when DRY_RUN=false)")
        return missing
