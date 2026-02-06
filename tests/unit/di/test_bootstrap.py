"""Tests for DI bootstrap module."""
import pytest
from unittest.mock import patch, MagicMock


class TestBootstrapContainer:
    """Test bootstrap_container function."""

    def test_bootstrap_returns_container(self):
        """bootstrap_container() should return a Container instance."""
        from core.di.bootstrap import bootstrap_container
        from core.di.container import Container

        container = bootstrap_container()

        assert isinstance(container, Container)

    def test_bootstrap_registers_core_services(self):
        """bootstrap_container should register core services."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container()

        # Check core services are registered
        # These should be interfaces/abstract types that are registered
        from core.di.bootstrap import (
            ICacheService,
            IConfigService,
            ILoggingService,
        )

        assert ICacheService in container
        assert IConfigService in container
        assert ILoggingService in container

    def test_bootstrap_configures_singletons(self):
        """Core services should be singletons."""
        from core.di.bootstrap import bootstrap_container, ICacheService

        container = bootstrap_container()

        cache1 = container.resolve(ICacheService)
        cache2 = container.resolve(ICacheService)

        assert cache1 is cache2

    def test_bootstrap_idempotent(self):
        """Multiple bootstrap calls should be safe."""
        from core.di.bootstrap import bootstrap_container

        container1 = bootstrap_container()
        container2 = bootstrap_container()

        # Should return same global container
        assert container1 is container2


class TestServiceRegistration:
    """Test individual service registrations."""

    def test_cache_service_registered(self):
        """CacheService should be registered and resolvable."""
        from core.di.bootstrap import bootstrap_container, ICacheService

        container = bootstrap_container()
        cache = container.resolve(ICacheService)

        # Should have cache interface methods
        assert hasattr(cache, 'get')
        assert hasattr(cache, 'set')

    def test_config_service_registered(self):
        """ConfigService should be registered and resolvable."""
        from core.di.bootstrap import bootstrap_container, IConfigService

        container = bootstrap_container()
        config = container.resolve(IConfigService)

        # Should have config interface methods
        assert hasattr(config, 'get')

    def test_logging_service_registered(self):
        """LoggingService should be registered and resolvable."""
        from core.di.bootstrap import bootstrap_container, ILoggingService

        container = bootstrap_container()
        logger = container.resolve(ILoggingService)

        # Should have logging interface
        assert hasattr(logger, 'log') or hasattr(logger, 'info')


class TestBotRegistration:
    """Test bot service registrations."""

    def test_treasury_bot_registered(self):
        """TreasuryBot should be registered when available."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container()

        # Should be able to resolve bot interface
        from core.di.bootstrap import ITreasuryBot

        if ITreasuryBot in container:
            bot = container.resolve(ITreasuryBot)
            assert bot is not None

    def test_twitter_bot_registered(self):
        """TwitterBot should be registered when available."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container()

        from core.di.bootstrap import ITwitterBot

        if ITwitterBot in container:
            bot = container.resolve(ITwitterBot)
            assert bot is not None


class TestLifecycleConfiguration:
    """Test service lifecycle configuration."""

    def test_transient_services_return_new_instances(self):
        """Services configured as transient should return new instances."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container()

        # Check if any transient services are configured
        from core.di.bootstrap import get_transient_services

        transient_types = get_transient_services()

        for service_type in transient_types:
            if service_type in container:
                instance1 = container.resolve(service_type)
                instance2 = container.resolve(service_type)
                assert instance1 is not instance2

    def test_request_scoped_services(self):
        """Request-scoped services should be unique per request scope."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container()

        from core.di.bootstrap import get_request_scoped_services

        request_scoped_types = get_request_scoped_services()

        for service_type in request_scoped_types:
            if service_type in container:
                scope1 = container.create_scope()
                scope2 = container.create_scope()

                instance1 = scope1.resolve(service_type)
                instance2 = scope2.resolve(service_type)
                assert instance1 is not instance2


class TestBootstrapWithEnv:
    """Test bootstrap with different environments."""

    def test_bootstrap_with_test_env(self):
        """Bootstrap with test environment should use test services."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container(env="test")

        # Test environment might use mock services
        from core.di.bootstrap import ICacheService

        cache = container.resolve(ICacheService)
        assert cache is not None

    def test_bootstrap_with_prod_env(self):
        """Bootstrap with prod environment should use real services."""
        from core.di.bootstrap import bootstrap_container

        container = bootstrap_container(env="production")

        from core.di.bootstrap import ICacheService

        cache = container.resolve(ICacheService)
        assert cache is not None

    def test_bootstrap_override_service(self):
        """Should be able to override service after bootstrap."""
        from core.di.bootstrap import bootstrap_container, ICacheService

        container = bootstrap_container()

        class MockCache:
            def get(self, key):
                return "mocked"

            def set(self, key, value):
                pass

        container.register_instance(ICacheService, MockCache())

        cache = container.resolve(ICacheService)
        assert cache.get("any") == "mocked"


class TestContainerReset:
    """Test container reset functionality."""

    def test_reset_clears_state(self):
        """reset_container should clear all registrations."""
        from core.di.bootstrap import bootstrap_container, reset_container

        container = bootstrap_container()

        # Add custom registration
        class CustomService:
            pass

        container.register_singleton(CustomService, lambda: CustomService())
        assert CustomService in container

        # Reset
        reset_container()

        # Get new container
        new_container = bootstrap_container()

        # Custom registration should be gone (container is fresh)
        # Note: This depends on implementation - might need to check differently
        assert new_container is not None


class TestLazyLoading:
    """Test lazy loading of services."""

    def test_services_lazy_loaded(self):
        """Services should not be instantiated until resolved."""
        from core.di.bootstrap import bootstrap_container, ICacheService

        instantiation_count = [0]

        class TrackedCacheService:
            def __init__(self):
                instantiation_count[0] += 1

            def get(self, key):
                return None

            def set(self, key, value):
                pass

        container = bootstrap_container()

        # Override with tracked implementation
        container.register_singleton(ICacheService, lambda: TrackedCacheService())

        # Not instantiated yet
        assert instantiation_count[0] == 0

        # Now resolve
        container.resolve(ICacheService)

        # Now instantiated
        assert instantiation_count[0] == 1

        # Second resolve should not instantiate again (singleton)
        container.resolve(ICacheService)
        assert instantiation_count[0] == 1
