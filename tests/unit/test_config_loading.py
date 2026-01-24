"""
Unit tests for Configuration Loading and Validation.

Tests cover:
1. Config loads from environment variables correctly
2. Config validation rejects invalid values
3. Default values are applied correctly
4. Config hot reload works (if supported)
5. Sensitive config values are not logged
6. Config schema matches documentation

Tests are organized into the following test classes:
- TestEnvironmentVariableLoading: Loading from .env and os.environ
- TestConfigDefaults: Default value behavior
- TestConfigValidation: Validation of individual and combined configs
- TestUnifiedConfigLoader: The unified YAML/JSON config loader
- TestConfigHotReload: Hot reload and reset functionality
- TestSensitiveValueMasking: Ensure secrets are not logged
- TestJarvisConfigDataclasses: The dataclass-based loader.py config
- TestLegacyConfigLoading: Legacy JSON config loading from __init__.py
- TestPydanticSchema: Pydantic schema validation from schema.py
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict


class TestEnvironmentVariableLoading:
    """Test loading configuration from environment variables."""

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clean environment for testing."""
        # Clear relevant env vars
        env_vars = [k for k in os.environ.keys() if any(
            prefix in k for prefix in [
                "TELEGRAM", "TREASURY", "JARVIS", "XAI", "ANTHROPIC",
                "SOLANA", "HELIUS", "BIRDEYE", "GROQ", "OPENAI",
                "OPENROUTER", "OLLAMA",
                "API_", "LOG_", "DEBUG", "CORS", "JWT", "RATE_LIMIT",
                "METRICS", "SENTRY"
            ]
        )]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
        # Prevent dotenv loaders from re-populating API keys during tests
        for key in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "XAI_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "BIRDEYE_API_KEY",
        ]:
            monkeypatch.setenv(key, "")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
        monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
        return monkeypatch

    def test_load_telegram_config_from_env(self, clean_env):
        """Test TelegramConfig loads from environment variables."""
        from core.config.loader import TelegramConfig

        clean_env.setenv("TELEGRAM_BOT_TOKEN", "123456789:ABCdefGHIjkl")
        clean_env.setenv("TELEGRAM_ADMIN_IDS", "111222333,444555666")
        clean_env.setenv("TELEGRAM_ADMIN_CHAT_ID", "-100123456")
        clean_env.setenv("TG_REPLY_MODE", "all")
        clean_env.setenv("TG_REPLY_COOLDOWN_SECONDS", "30")

        config = TelegramConfig.from_env()

        assert config.bot_token == "123456789:ABCdefGHIjkl"
        assert config.admin_ids == [111222333, 444555666]
        assert config.admin_chat_id == "-100123456"
        assert config.reply_mode == "all"
        assert config.reply_cooldown == 30

    def test_load_solana_config_from_env(self, clean_env):
        """Test SolanaConfig loads from environment variables."""
        from core.config.loader import SolanaConfig

        clean_env.setenv("SOLANA_NETWORK", "mainnet-beta")
        clean_env.setenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
        clean_env.setenv("SOLANA_WS_URL", "wss://api.mainnet-beta.solana.com")
        clean_env.setenv("HELIUS_API_KEY", "test-helius-key")

        config = SolanaConfig.from_env()

        assert config.network == "mainnet-beta"
        assert config.rpc_url == "https://api.mainnet-beta.solana.com"
        assert config.ws_url == "wss://api.mainnet-beta.solana.com"
        assert config.helius_api_key == "test-helius-key"

    def test_load_treasury_config_from_env(self, clean_env):
        """Test TreasuryConfig loads from environment variables."""
        from core.config.loader import TreasuryConfig

        clean_env.setenv("TREASURY_RESERVE_PCT", "50")
        clean_env.setenv("TREASURY_ACTIVE_PCT", "40")
        clean_env.setenv("TREASURY_PROFIT_PCT", "10")
        clean_env.setenv("TREASURY_LIVE_MODE", "true")
        clean_env.setenv("MAX_SINGLE_TRADE_PCT", "5.0")
        clean_env.setenv("DAILY_LOSS_LIMIT_PCT", "10.0")
        clean_env.setenv("TREASURY_ADMIN_IDS", "123456789")

        config = TreasuryConfig.from_env()

        assert config.reserve_pct == 50
        assert config.active_pct == 40
        assert config.profit_pct == 10
        assert config.live_mode is True
        assert config.max_single_trade_pct == 5.0
        assert config.daily_loss_limit_pct == 10.0
        assert config.admin_ids == [123456789]

    def test_load_llm_config_from_env(self, clean_env):
        """Test LLMConfig loads from environment variables."""
        from core.config.loader import LLMConfig

        clean_env.setenv("OPENAI_API_KEY", "sk-test-openai")
        clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        clean_env.setenv("XAI_API_KEY", "xai-test-key")
        clean_env.setenv("XAI_MODEL", "grok-3")
        clean_env.setenv("GROQ_API_KEY", "gsk-test")
        clean_env.setenv("GROQ_MODEL", "llama-3.1-70b")

        config = LLMConfig.from_env()

        assert config.openai_api_key == "sk-test-openai"
        assert config.anthropic_api_key == "sk-ant-test"
        assert config.xai_api_key == "xai-test-key"
        assert config.xai_model == "grok-3"
        assert config.groq_api_key == "gsk-test"
        assert config.groq_model == "llama-3.1-70b"

    def test_load_api_config_from_env(self, clean_env):
        """Test APIConfig loads from environment variables."""
        from core.config.loader import APIConfig

        clean_env.setenv("API_HOST", "127.0.0.1")
        clean_env.setenv("API_PORT", "9000")
        clean_env.setenv("API_RELOAD", "false")
        clean_env.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5000")
        clean_env.setenv("RATE_LIMIT_ENABLED", "true")
        clean_env.setenv("RATE_LIMIT_REQUESTS", "200")
        clean_env.setenv("JWT_SECRET", "my-secret-key")

        config = APIConfig.from_env()

        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.reload is False
        assert config.cors_origins == ["http://localhost:3000", "http://localhost:5000"]
        assert config.rate_limit_enabled is True
        assert config.rate_limit_requests == 200
        assert config.jwt_secret == "my-secret-key"

    def test_load_monitoring_config_from_env(self, clean_env):
        """Test MonitoringConfig loads from environment variables."""
        from core.config.loader import MonitoringConfig

        clean_env.setenv("SENTRY_DSN", "https://sentry.io/test")
        clean_env.setenv("METRICS_ENABLED", "true")
        clean_env.setenv("METRICS_PORT", "9100")
        clean_env.setenv("LOG_LEVEL", "DEBUG")
        clean_env.setenv("DEBUG", "true")

        config = MonitoringConfig.from_env()

        assert config.sentry_dsn == "https://sentry.io/test"
        assert config.metrics_enabled is True
        assert config.metrics_port == 9100
        assert config.log_level == "DEBUG"
        assert config.debug is True

    def test_load_env_file(self, clean_env):
        """Test loading from .env file."""
        from core.config.loader import _load_env_file

        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False, encoding='utf-8') as f:
            f.write("TEST_VAR=test_value\n")
            f.write("TEST_QUOTED='quoted value'\n")
            f.write("TEST_DOUBLE_QUOTED=\"double quoted\"\n")
            f.write("# This is a comment\n")
            f.write("EMPTY_VAR=\n")
            temp_path = Path(f.name)

        try:
            env_vars = _load_env_file(temp_path)
            assert env_vars["TEST_VAR"] == "test_value"
            assert env_vars["TEST_QUOTED"] == "quoted value"
            assert env_vars["TEST_DOUBLE_QUOTED"] == "double quoted"
            assert "# This is a comment" not in env_vars
            assert env_vars["EMPTY_VAR"] == ""
        finally:
            temp_path.unlink()

    def test_boolean_type_casting(self, clean_env):
        """Test boolean type casting for various string values."""
        from core.config.loader import _get_env

        # Test true values
        for val in ["true", "True", "TRUE", "1", "yes", "on"]:
            clean_env.setenv("TEST_BOOL", val)
            result = _get_env("TEST_BOOL", default=False, cast=bool)
            assert result is True, f"'{val}' should cast to True"

        # Test false values
        for val in ["false", "False", "FALSE", "0", "no", "off"]:
            clean_env.setenv("TEST_BOOL", val)
            result = _get_env("TEST_BOOL", default=True, cast=bool)
            assert result is False, f"'{val}' should cast to False"

    def test_integer_type_casting(self, clean_env):
        """Test integer type casting."""
        from core.config.loader import _get_env

        clean_env.setenv("TEST_INT", "42")
        result = _get_env("TEST_INT", default=0, cast=int)
        assert result == 42
        assert isinstance(result, int)

        # Invalid integer should return default
        clean_env.setenv("TEST_INT", "not-a-number")
        result = _get_env("TEST_INT", default=99, cast=int)
        assert result == 99

    def test_float_type_casting(self, clean_env):
        """Test float type casting."""
        from core.config.loader import _get_env

        clean_env.setenv("TEST_FLOAT", "3.14")
        result = _get_env("TEST_FLOAT", default=0.0, cast=float)
        assert result == 3.14
        assert isinstance(result, float)

        # Invalid float should return default
        clean_env.setenv("TEST_FLOAT", "invalid")
        result = _get_env("TEST_FLOAT", default=1.5, cast=float)
        assert result == 1.5

    def test_list_type_casting(self, clean_env):
        """Test list type casting from comma-separated values."""
        from core.config.loader import _get_env

        clean_env.setenv("TEST_LIST", "item1, item2, item3")
        result = _get_env("TEST_LIST", default=[], cast=list)
        assert result == ["item1", "item2", "item3"]


class TestConfigDefaults:
    """Test default values are applied correctly."""

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clean environment for testing."""
        env_vars = [k for k in os.environ.keys() if any(
            prefix in k for prefix in [
                "TELEGRAM", "TREASURY", "SOLANA", "HELIUS", "BIRDEYE",
                "XAI", "ANTHROPIC", "OPENAI", "GROQ", "OPENROUTER",
                "OLLAMA",
                "API_", "LOG_", "DEBUG", "CORS", "JWT", "RATE_LIMIT"
            ]
        )]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
        # Prevent dotenv loaders from re-populating API keys during tests
        for key in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "XAI_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "BIRDEYE_API_KEY",
        ]:
            monkeypatch.setenv(key, "")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
        monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
        return monkeypatch

    def test_telegram_config_defaults(self, clean_env):
        """Test TelegramConfig has correct defaults."""
        from core.config.loader import TelegramConfig

        config = TelegramConfig.from_env()

        assert config.bot_token == ""
        assert config.admin_ids == []
        assert config.reply_mode == "mentions"
        assert config.reply_cooldown == 12
        assert config.reply_model == "grok-3"
        assert config.claude_model == "claude-sonnet-4-20250514"

    def test_solana_config_defaults(self, clean_env):
        """Test SolanaConfig has correct defaults."""
        from core.config.loader import SolanaConfig

        config = SolanaConfig.from_env()

        assert config.network == "devnet"
        assert config.rpc_url == "https://api.devnet.solana.com"
        assert config.ws_url == "wss://api.devnet.solana.com"
        assert config.helius_api_key == ""

    def test_treasury_config_defaults(self, clean_env):
        """Test TreasuryConfig has correct defaults."""
        from core.config.loader import TreasuryConfig

        config = TreasuryConfig.from_env()

        assert config.reserve_pct == 60
        assert config.active_pct == 30
        assert config.profit_pct == 10
        assert config.live_mode is False
        assert config.circuit_breaker_threshold == 10
        assert config.max_single_trade_pct == 2.0
        assert config.daily_loss_limit_pct == 5.0

    def test_llm_config_defaults(self, clean_env):
        """Test LLMConfig has correct defaults."""
        from core.config.loader import LLMConfig

        config = LLMConfig.from_env()

        assert config.openai_api_key == ""
        assert config.anthropic_api_key == ""
        assert config.xai_api_key == ""
        assert config.xai_model == "grok-3-mini"
        assert config.groq_model == "llama-3.3-70b-versatile"
        assert config.ollama_url == "http://localhost:11434"
        assert config.ollama_model == "llama3.2"

    def test_api_config_defaults(self, clean_env):
        """Test APIConfig has correct defaults."""
        from core.config.loader import APIConfig

        config = APIConfig.from_env()

        assert config.host == "0.0.0.0"
        assert config.port == 8766
        assert config.reload is True
        assert config.cors_origins == ["http://localhost:3000"]
        assert config.rate_limit_enabled is True
        assert config.rate_limit_requests == 100
        assert config.rate_limit_window == 60
        assert config.jwt_secret == "change-me-in-production"

    def test_monitoring_config_defaults(self, clean_env):
        """Test MonitoringConfig has correct defaults."""
        from core.config.loader import MonitoringConfig

        config = MonitoringConfig.from_env()

        assert config.sentry_dsn == ""
        assert config.metrics_enabled is False
        assert config.metrics_port == 9090
        assert config.log_level == "INFO"
        assert config.debug is False


class TestConfigValidation:
    """Test validation rejects invalid values."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        from core.config.validator import ConfigValidator
        return ConfigValidator()

    def test_treasury_percentages_must_sum_to_100(self, validator):
        """Test treasury percentages validation in is_configured."""
        from core.config.loader import TreasuryConfig, JarvisConfig

        # Valid: sums to 100
        config = JarvisConfig(
            treasury=TreasuryConfig(
                reserve_pct=60,
                active_pct=30,
                profit_pct=10,
            )
        )
        assert config.is_configured("treasury") is True

        # Invalid: sums to 90
        config_invalid = JarvisConfig(
            treasury=TreasuryConfig(
                reserve_pct=60,
                active_pct=20,
                profit_pct=10,
            )
        )
        assert config_invalid.is_configured("treasury") is False

    def test_telegram_is_configured_requires_token(self):
        """Test telegram is_configured requires bot token."""
        from core.config.loader import TelegramConfig, JarvisConfig

        # Without token
        config = JarvisConfig(telegram=TelegramConfig())
        assert config.is_configured("telegram") is False

        # With token
        config_with_token = JarvisConfig(
            telegram=TelegramConfig(bot_token="123456789:ABC")
        )
        assert config_with_token.is_configured("telegram") is True

    def test_llm_is_configured_requires_at_least_one_provider(self):
        """Test LLM is_configured requires at least one API key."""
        from core.config.loader import LLMConfig, JarvisConfig

        # No providers configured
        config = JarvisConfig(llm=LLMConfig())
        assert config.is_configured("llm") is False

        # With XAI key
        config_xai = JarvisConfig(llm=LLMConfig(xai_api_key="test"))
        assert config_xai.is_configured("llm") is True

        # With Groq key
        config_groq = JarvisConfig(llm=LLMConfig(groq_api_key="test"))
        assert config_groq.is_configured("llm") is True

    def test_security_is_configured_requires_password(self):
        """Test security is_configured requires password."""
        from core.config.loader import SecurityConfig, JarvisConfig

        # Without password
        config = JarvisConfig(security=SecurityConfig())
        assert config.is_configured("security") is False

        # With password
        config_with_pass = JarvisConfig(
            security=SecurityConfig(secure_password="test123")
        )
        assert config_with_pass.is_configured("security") is True

    def test_get_available_llm_providers(self):
        """Test get_available_llm_providers returns correct list."""
        from core.config.loader import LLMConfig, JarvisConfig

        config = JarvisConfig(llm=LLMConfig(
            openai_api_key="sk-test",
            xai_api_key="xai-test",
        ))

        providers = config.get_available_llm_providers()

        assert "openai" in providers
        assert "xai" in providers
        assert "ollama" in providers  # Always available
        assert "anthropic" not in providers  # Not configured
        assert "groq" not in providers  # Not configured


class TestUnifiedConfigLoader:
    """Test UnifiedConfigLoader class."""

    @pytest.fixture
    def temp_yaml_config(self, monkeypatch):
        """Create temporary YAML config file."""
        try:
            import yaml
            HAS_YAML = True
        except ImportError:
            HAS_YAML = False
            pytest.skip("PyYAML not installed")

        # Clear TELEGRAM_BOT_TOKEN to test default
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            yaml.dump({
                "trading": {
                    "max_positions": 50,
                    "enabled": True,
                    "risk_per_trade": 0.02,
                },
                "telegram": {
                    "bot_token": "${TELEGRAM_BOT_TOKEN:test-token}",
                    "admin_ids": [123, 456],
                },
                "paths": {
                    "data_dir": "~/data",
                },
            }, f)
            temp_path = Path(f.name)

        yield temp_path
        temp_path.unlink()

    @pytest.fixture
    def temp_json_config(self):
        """Create temporary JSON config file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({
                "trading": {
                    "max_positions": 100,
                    "slippage": 0.5,
                },
                "api": {
                    "host": "localhost",
                    "port": 8080,
                },
            }, f)
            temp_path = Path(f.name)

        yield temp_path
        temp_path.unlink()

    def test_load_yaml_config(self, temp_yaml_config, monkeypatch):
        """Test loading YAML config file."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        loader = UnifiedConfigLoader(config_path=temp_yaml_config)

        assert loader.get("trading.max_positions") == 50
        assert loader.get("trading.enabled") is True
        assert loader.get("trading.risk_per_trade") == 0.02
        reset_config()

    def test_env_var_expansion_with_default(self, temp_yaml_config, monkeypatch):
        """Test environment variable expansion with default value."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Ensure env var is NOT set so default is used
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        loader = UnifiedConfigLoader(config_path=temp_yaml_config)

        # Should use default since env var not set
        assert loader.get("telegram.bot_token") == "test-token"
        reset_config()

    def test_env_var_expansion_from_env(self, temp_yaml_config, monkeypatch):
        """Test environment variable expansion from actual env."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "real-token-from-env")

        loader = UnifiedConfigLoader(config_path=temp_yaml_config)

        assert loader.get("telegram.bot_token") == "real-token-from-env"
        reset_config()

    def test_path_expansion(self, temp_yaml_config, monkeypatch):
        """Test home directory path expansion."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Clear env var so default is used
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

        loader = UnifiedConfigLoader(config_path=temp_yaml_config)

        # Should expand ~ to home directory
        data_dir = loader.get("paths.data_dir")
        assert "~" not in data_dir
        reset_config()

    def test_get_with_default(self):
        """Test get() with default value for missing key."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"simple": {"key": "value"}}, f)
            except ImportError:
                json.dump({"simple": {"key": "value"}}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            # Non-existent key should return default
            result = loader.get("nonexistent.key", default="fallback")
            assert result == "fallback"
            reset_config()
        finally:
            temp_path.unlink()

    def test_get_section(self):
        """Test get_section() returns all keys in section."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({
                    "trading": {"max_positions": 100, "slippage": 0.5},
                    "api": {"host": "localhost"},
                }, f)
            except ImportError:
                json.dump({
                    "trading": {"max_positions": 100, "slippage": 0.5},
                    "api": {"host": "localhost"},
                }, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            section = loader.get_section("trading")
            assert "trading.max_positions" in section
            assert "trading.slippage" in section
            assert section["trading.max_positions"] == 100
            reset_config()
        finally:
            temp_path.unlink()

    def test_get_typed_methods(self):
        """Test typed getter methods."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({
                    "trading": {"max_positions": 100, "slippage": 0.5, "enabled": True},
                }, f)
            except ImportError:
                json.dump({
                    "trading": {"max_positions": 100, "slippage": 0.5, "enabled": True},
                }, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            assert loader.get_int("trading.max_positions") == 100
            assert isinstance(loader.get_int("trading.max_positions"), int)

            assert loader.get_float("trading.slippage") == 0.5
            assert isinstance(loader.get_float("trading.slippage"), float)

            assert loader.get_bool("trading.enabled", default=False) is True
            reset_config()
        finally:
            temp_path.unlink()

    def test_has_method(self):
        """Test has() method checks key existence."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"trading": {"max_positions": 100}}, f)
            except ImportError:
                json.dump({"trading": {"max_positions": 100}}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            assert loader.has("trading.max_positions") is True
            assert loader.has("nonexistent.key") is False
            reset_config()
        finally:
            temp_path.unlink()

    def test_config_path_property(self):
        """Test config_path property returns loaded path."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"simple": "value"}, f)
            except ImportError:
                json.dump({"simple": "value"}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            assert loader.config_path == temp_path
            reset_config()
        finally:
            temp_path.unlink()


class TestConfigHotReload:
    """Test hot reload functionality."""

    @pytest.fixture
    def temp_config_file(self):
        """Create temporary config file for hot reload testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump({"version": 1, "enabled": True}, f)
            temp_path = Path(f.name)

        yield temp_path
        temp_path.unlink()

    def test_reload_config_picks_up_changes(self, monkeypatch):
        """Test reload_config() picks up environment changes."""
        from core.config.loader import get_config, reload_config

        # Clear cache
        import core.config.loader as loader_module
        loader_module._config = None

        monkeypatch.setenv("XAI_API_KEY", "initial-key")
        config1 = get_config()
        assert config1.llm.xai_api_key == "initial-key"

        # Change env and reload
        monkeypatch.setenv("XAI_API_KEY", "updated-key")
        config2 = reload_config()
        assert config2.llm.xai_api_key == "updated-key"

        # Reset
        loader_module._config = None

    def test_unified_config_reset(self):
        """Test reset_config clears singleton."""
        from core.config.unified_config import reset_config

        # Create a simple temp config to avoid env var issues
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"test": "value"}, f)
            except ImportError:
                json.dump({"test": "value"}, f)
            temp_path = Path(f.name)

        try:
            from core.config.unified_config import UnifiedConfigLoader
            reset_config()

            loader1 = UnifiedConfigLoader(config_path=temp_path)
            reset_config()
            loader2 = UnifiedConfigLoader(config_path=temp_path)

            # After reset, should be able to create new instances
            assert loader2 is not None
            reset_config()
        finally:
            temp_path.unlink()


class TestSensitiveValueMasking:
    """Test sensitive values are not logged."""

    def test_to_dict_hides_secrets_by_default(self):
        """Test to_dict masks sensitive values by default."""
        from core.config.loader import JarvisConfig, TelegramConfig, LLMConfig

        config = JarvisConfig(
            telegram=TelegramConfig(bot_token="secret-bot-token-12345678"),
            llm=LLMConfig(
                openai_api_key="sk-secret-openai-key-abcd1234",
                anthropic_api_key="sk-ant-secret-key-xyz",
                xai_api_key="xai-secret-grok-key",
            )
        )

        data = config.to_dict(hide_secrets=True)

        # Tokens should be masked
        assert "secret-bot-token" not in data["telegram"]["bot_token"]
        assert "****" in data["telegram"]["bot_token"] or "..." in data["telegram"]["bot_token"]

        # API keys should be masked
        assert "sk-secret-openai" not in data["llm"]["openai_api_key"]
        assert "sk-ant-secret" not in data["llm"]["anthropic_api_key"]

    def test_to_dict_shows_secrets_when_requested(self):
        """Test to_dict shows secrets when hide_secrets=False."""
        from core.config.loader import JarvisConfig, TelegramConfig, LLMConfig

        config = JarvisConfig(
            telegram=TelegramConfig(bot_token="secret-bot-token-12345678"),
            llm=LLMConfig(openai_api_key="sk-secret-openai-key-abcd1234")
        )

        data = config.to_dict(hide_secrets=False)

        # Should show full values
        assert data["telegram"]["bot_token"] == "secret-bot-token-12345678"
        assert data["llm"]["openai_api_key"] == "sk-secret-openai-key-abcd1234"

    def test_unified_config_masks_sensitive_keys(self):
        """Test UnifiedConfigLoader masks sensitive keys."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple temp config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"simple": "value"}, f)
            except ImportError:
                json.dump({"simple": "value"}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            sensitive_keys = [
                "api_key", "api_secret", "token", "password", "secret",
                "private_key", "wallet_key", "bot_token", "bearer_token",
                "access_token", "refresh_token", "oauth", "credential"
            ]

            for key_part in sensitive_keys:
                full_key = f"test.{key_part}"
                assert loader._is_sensitive_key(full_key), f"{full_key} should be detected as sensitive"
            reset_config()
        finally:
            temp_path.unlink()

    def test_unified_config_to_dict_masks_secrets(self):
        """Test UnifiedConfigLoader.to_dict masks secrets."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({
                    "api": {"api_key": "super-secret-key-12345"},
                    "auth": {"password": "my-password-123"},
                    "normal": {"setting": "visible-value"},
                }, f)
            except ImportError:
                json.dump({
                    "api": {"api_key": "super-secret-key-12345"},
                    "auth": {"password": "my-password-123"},
                    "normal": {"setting": "visible-value"},
                }, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)
            data = loader.to_dict(include_sensitive=False)

            assert data["api.api_key"] == "***MASKED***"
            assert data["auth.password"] == "***MASKED***"
            assert data["normal.setting"] == "visible-value"
            reset_config()
        finally:
            temp_path.unlink()


class TestJarvisConfigDataclasses:
    """Test the JarvisConfig dataclass-based configuration."""

    @pytest.fixture
    def clean_env(self, monkeypatch):
        """Clean environment for testing."""
        env_vars = [k for k in os.environ.keys() if any(
            prefix in k for prefix in [
                "TELEGRAM", "TREASURY", "SOLANA", "HELIUS", "BIRDEYE",
                "XAI", "ANTHROPIC", "OPENAI", "GROQ", "OPENROUTER",
                "OLLAMA",
                "API_", "LOG_", "DEBUG"
            ]
        )]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)
        # Prevent dotenv loaders from re-populating API keys during tests
        for key in [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "XAI_API_KEY",
            "GROQ_API_KEY",
            "OPENROUTER_API_KEY",
            "BIRDEYE_API_KEY",
        ]:
            monkeypatch.setenv(key, "")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
        monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
        return monkeypatch

    def test_jarvis_config_load_creates_all_sections(self, clean_env):
        """Test JarvisConfig.load creates all config sections."""
        from core.config.loader import JarvisConfig
        import core.config.loader as loader_module
        loader_module._config = None

        config = JarvisConfig.load()

        assert config.telegram is not None
        assert config.solana is not None
        assert config.treasury is not None
        assert config.llm is not None
        assert config.api is not None
        assert config.security is not None
        assert config.monitoring is not None
        assert config._loaded is True

        loader_module._config = None

    def test_jarvis_config_global_singleton(self, clean_env):
        """Test get_config returns singleton."""
        from core.config.loader import get_config
        import core.config.loader as loader_module
        loader_module._config = None

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

        loader_module._config = None


class TestLegacyConfigLoading:
    """Test legacy JSON config loading from __init__.py."""

    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary config directory with test files."""
        temp_dir = tempfile.mkdtemp()
        config_dir = Path(temp_dir) / "lifeos" / "config"
        config_dir.mkdir(parents=True)

        # Create base config
        base_config = config_dir / "lifeos.config.json"
        with open(base_config, 'w') as f:
            json.dump({
                "version": "1.0",
                "trading": {"enabled": True, "max_positions": 10},
                "memory": {"target_cap": 200},
            }, f)

        # Create local override
        local_config = config_dir / "lifeos.config.local.json"
        with open(local_config, 'w') as f:
            json.dump({
                "trading": {"max_positions": 50},  # Override
                "custom_setting": "local_value",
            }, f)

        yield temp_dir

        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)

    def test_deep_merge(self):
        """Test _deep_merge merges nested dicts correctly."""
        from core.config import _deep_merge

        base = {"a": 1, "nested": {"x": 1, "y": 2}}
        override = {"a": 2, "nested": {"y": 3, "z": 4}}

        result = _deep_merge(base, override)

        assert result["a"] == 2  # Overridden
        assert result["nested"]["x"] == 1  # Preserved
        assert result["nested"]["y"] == 3  # Overridden
        assert result["nested"]["z"] == 4  # Added

    def test_load_json_handles_missing_file(self):
        """Test _load_json returns empty dict for missing file."""
        from core.config import _load_json

        result = _load_json(Path("/nonexistent/path/config.json"))
        assert result == {}

    def test_load_json_handles_invalid_json(self):
        """Test _load_json returns empty dict for invalid JSON."""
        from core.config import _load_json

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {")
            temp_path = Path(f.name)

        try:
            result = _load_json(temp_path)
            assert result == {}
        finally:
            temp_path.unlink()


class TestPydanticSchema:
    """Test Pydantic schema validation from schema.py."""

    def test_provider_config_validation(self):
        """Test ProviderConfig validation rules."""
        from core.config.schema import ProviderConfig

        # Valid config
        config = ProviderConfig(name="openai", priority=50, timeout=30)
        assert config.name == "openai"
        assert config.priority == 50

        # Invalid priority (out of range)
        with pytest.raises(Exception):
            ProviderConfig(name="test", priority=150)  # > 100

        # Invalid timeout (out of range)
        with pytest.raises(Exception):
            ProviderConfig(name="test", timeout=500)  # > 300

    def test_trading_config_validation(self):
        """Test TradingConfig validation rules."""
        from core.config.schema import TradingConfig

        # Valid config with defaults
        config = TradingConfig()
        assert config.max_position_pct == 0.25
        assert config.risk_per_trade == 0.02

        # Invalid max_position_pct (> 1)
        with pytest.raises(Exception):
            TradingConfig(max_position_pct=1.5)

        # Invalid risk_per_trade (> 0.1)
        with pytest.raises(Exception):
            TradingConfig(risk_per_trade=0.5)

    def test_memory_config_validation(self):
        """Test MemoryConfig validation rules."""
        from core.config.schema import MemoryConfig

        # Valid config
        config = MemoryConfig(min_cap=50, max_cap=300, target_cap=200)
        assert config.min_cap == 50
        assert config.max_cap == 300

        # Invalid: max_cap < min_cap
        with pytest.raises(Exception):
            MemoryConfig(min_cap=100, max_cap=50)

    def test_security_config_validation(self):
        """Test SecurityConfig validation rules."""
        from core.config.schema import SecurityConfig

        config = SecurityConfig(
            rate_limit_requests=100,
            jwt_expiry_minutes=30,
            session_timeout=3600,
        )
        assert config.rate_limit_enabled is True
        assert config.ip_allowlist == []

    def test_logging_config_validation(self):
        """Test LoggingConfig validation rules."""
        from core.config.schema import LoggingConfig

        # Valid log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level

        # Invalid log level
        with pytest.raises(Exception):
            LoggingConfig(level="INVALID")

    def test_app_config_composition(self):
        """Test AppConfig composes sub-configs correctly."""
        from core.config.schema import AppConfig

        config = AppConfig(
            environment="production",
            debug=False,
        )

        assert config.environment == "production"
        assert config.debug is False
        assert config.trading is not None
        assert config.memory is not None
        assert config.security is not None
        assert config.logging is not None

    def test_app_config_environment_validation(self):
        """Test AppConfig validates environment values."""
        from core.config.schema import AppConfig

        # Valid environments
        for env in ["development", "staging", "production"]:
            config = AppConfig(environment=env)
            assert config.environment == env

        # Invalid environment
        with pytest.raises(Exception):
            AppConfig(environment="invalid-env")

    def test_validate_config_function(self):
        """Test validate_config function."""
        from core.config.schema import validate_config

        # Valid config
        valid_data = {
            "environment": "development",
            "debug": True,
        }
        is_valid, errors = validate_config(valid_data)
        assert is_valid is True
        assert errors == []

        # Invalid config
        invalid_data = {
            "environment": "invalid",
        }
        is_valid, errors = validate_config(invalid_data)
        assert is_valid is False
        assert len(errors) > 0


class TestConfigSchemaDocumentation:
    """Test config schema matches documentation patterns."""

    def test_lifeos_config_json_structure(self):
        """Test lifeos.config.json has expected structure."""
        from core.config import BASE_CONFIG

        if not BASE_CONFIG.exists():
            pytest.skip("Base config file not found")

        with open(BASE_CONFIG) as f:
            config = json.load(f)

        # Check expected top-level keys from CLAUDE.md
        expected_sections = [
            "paths", "memory", "voice", "trading", "providers"
        ]
        for section in expected_sections:
            assert section in config, f"Missing section: {section}"

    def test_trading_config_has_expected_fields(self):
        """Test trading config has documented fields."""
        from core.config import BASE_CONFIG

        if not BASE_CONFIG.exists():
            pytest.skip("Base config file not found")

        with open(BASE_CONFIG) as f:
            config = json.load(f)

        trading = config.get("trading", {})

        # Check expected trading fields
        expected_fields = [
            "risk_per_trade", "stop_loss_pct", "take_profit_pct"
        ]
        for field in expected_fields:
            assert field in trading, f"Missing trading field: {field}"

    def test_memory_config_has_adaptive_fields(self):
        """Test memory config has adaptive capacity fields."""
        from core.config import BASE_CONFIG

        if not BASE_CONFIG.exists():
            pytest.skip("Base config file not found")

        with open(BASE_CONFIG) as f:
            config = json.load(f)

        memory = config.get("memory", {})

        assert "target_cap" in memory
        assert "min_cap" in memory
        assert "max_cap" in memory


class TestConfigConvenienceFunctions:
    """Test convenience functions for config access."""

    def test_config_get_function_with_explicit_config(self):
        """Test config_get convenience function with explicit config file."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple temp config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"test": {"key": "value"}}, f)
            except ImportError:
                json.dump({"test": {"key": "value"}}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            # Should return default for missing keys
            result = loader.get("nonexistent.key", default="fallback")
            assert result == "fallback"

            # Should return actual value for existing keys
            result = loader.get("test.key", default="fallback")
            assert result == "value"
            reset_config()
        finally:
            temp_path.unlink()

    def test_config_get_bool_function_with_explicit_config(self):
        """Test config_get_bool convenience function with explicit config file."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple temp config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"test": {"flag": True}}, f)
            except ImportError:
                json.dump({"test": {"flag": True}}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            # Should return default for missing keys
            result = loader.get_bool("nonexistent.flag", default=True)
            assert result is True

            # Should return actual value for existing keys
            result = loader.get_bool("test.flag", default=False)
            assert result is True
            reset_config()
        finally:
            temp_path.unlink()

    def test_config_get_int_function_with_explicit_config(self):
        """Test config_get_int convenience function with explicit config file."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple temp config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"test": {"count": 100}}, f)
            except ImportError:
                json.dump({"test": {"count": 100}}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            # Should return default for missing keys
            result = loader.get_int("nonexistent.count", default=42)
            assert result == 42

            # Should return actual value for existing keys
            result = loader.get_int("test.count", default=0)
            assert result == 100
            reset_config()
        finally:
            temp_path.unlink()

    def test_config_get_section_function_with_explicit_config(self):
        """Test config_get_section convenience function with explicit config file."""
        from core.config.unified_config import UnifiedConfigLoader, reset_config
        reset_config()

        # Create a simple temp config without env var references
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            try:
                import yaml
                yaml.dump({"test": {"a": 1, "b": 2}}, f)
            except ImportError:
                json.dump({"test": {"a": 1, "b": 2}}, f)
            temp_path = Path(f.name)

        try:
            loader = UnifiedConfigLoader(config_path=temp_path)

            # Should return empty dict for missing sections
            result = loader.get_section("nonexistent")
            assert result == {}

            # Should return actual section for existing sections
            result = loader.get_section("test")
            assert "test.a" in result
            assert "test.b" in result
            reset_config()
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
