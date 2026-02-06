"""Tests for DI providers."""
import pytest
from abc import ABC, abstractmethod


class TestProviderABC:
    """Test Provider abstract base class."""

    def test_provider_is_abstract(self):
        """Provider should be abstract and not instantiable."""
        from core.di.providers import Provider

        with pytest.raises(TypeError):
            Provider()

    def test_provider_requires_provide_method(self):
        """Provider subclass must implement provide()."""
        from core.di.providers import Provider

        class IncompleteProvider(Provider):
            pass

        with pytest.raises(TypeError):
            IncompleteProvider()

    def test_provider_subclass_can_implement(self):
        """Valid Provider subclass should be instantiable."""
        from core.di.providers import Provider

        class ValidProvider(Provider):
            def provide(self):
                return "value"

        provider = ValidProvider()
        assert provider.provide() == "value"


class TestClassProvider:
    """Test ClassProvider for instantiating classes."""

    def test_class_provider_creates_instance(self):
        """ClassProvider should create instance of the class."""
        from core.di.providers import ClassProvider

        class MyService:
            pass

        provider = ClassProvider(MyService)
        instance = provider.provide()

        assert isinstance(instance, MyService)

    def test_class_provider_new_instance_each_time(self):
        """ClassProvider should create new instance each provide call."""
        from core.di.providers import ClassProvider

        class MyService:
            pass

        provider = ClassProvider(MyService)
        instance1 = provider.provide()
        instance2 = provider.provide()

        assert instance1 is not instance2

    def test_class_provider_with_args(self):
        """ClassProvider should pass args to constructor."""
        from core.di.providers import ClassProvider

        class MyService:
            def __init__(self, name: str, count: int):
                self.name = name
                self.count = count

        provider = ClassProvider(MyService, args=("test", 42))
        instance = provider.provide()

        assert instance.name == "test"
        assert instance.count == 42

    def test_class_provider_with_kwargs(self):
        """ClassProvider should pass kwargs to constructor."""
        from core.di.providers import ClassProvider

        class MyService:
            def __init__(self, name: str = "default", count: int = 0):
                self.name = name
                self.count = count

        provider = ClassProvider(MyService, kwargs={"name": "custom", "count": 100})
        instance = provider.provide()

        assert instance.name == "custom"
        assert instance.count == 100

    def test_class_provider_with_dependency_resolver(self):
        """ClassProvider should use resolver for dependencies."""
        from core.di.providers import ClassProvider
        from core.di.container import Container

        class Logger:
            pass

        class MyService:
            def __init__(self, logger: Logger):
                self.logger = logger

        container = Container()
        container.register_singleton(Logger, lambda: Logger())

        provider = ClassProvider(MyService, container=container)
        instance = provider.provide()

        assert isinstance(instance.logger, Logger)


class TestFactoryProvider:
    """Test FactoryProvider for using factory functions."""

    def test_factory_provider_calls_factory(self):
        """FactoryProvider should call factory function."""
        from core.di.providers import FactoryProvider

        def create_service():
            return {"type": "service"}

        provider = FactoryProvider(create_service)
        instance = provider.provide()

        assert instance == {"type": "service"}

    def test_factory_provider_new_instance_each_time(self):
        """FactoryProvider should call factory each time."""
        from core.di.providers import FactoryProvider

        call_count = [0]

        def create_service():
            call_count[0] += 1
            return {"call": call_count[0]}

        provider = FactoryProvider(create_service)
        instance1 = provider.provide()
        instance2 = provider.provide()

        assert instance1["call"] == 1
        assert instance2["call"] == 2

    def test_factory_provider_with_args(self):
        """FactoryProvider should pass args to factory."""
        from core.di.providers import FactoryProvider

        def create_service(name: str, count: int):
            return {"name": name, "count": count}

        provider = FactoryProvider(create_service, args=("test", 42))
        instance = provider.provide()

        assert instance["name"] == "test"
        assert instance["count"] == 42

    def test_factory_provider_with_kwargs(self):
        """FactoryProvider should pass kwargs to factory."""
        from core.di.providers import FactoryProvider

        def create_service(name: str = "default"):
            return {"name": name}

        provider = FactoryProvider(create_service, kwargs={"name": "custom"})
        instance = provider.provide()

        assert instance["name"] == "custom"

    def test_factory_provider_async_factory(self):
        """FactoryProvider should work with async factories."""
        import asyncio
        from core.di.providers import FactoryProvider

        async def async_create_service():
            return {"async": True}

        provider = FactoryProvider(async_create_service)
        instance = asyncio.get_event_loop().run_until_complete(provider.provide_async())

        assert instance["async"] is True


class TestValueProvider:
    """Test ValueProvider for returning fixed values."""

    def test_value_provider_returns_value(self):
        """ValueProvider should return the fixed value."""
        from core.di.providers import ValueProvider

        provider = ValueProvider({"config": "value"})
        instance = provider.provide()

        assert instance == {"config": "value"}

    def test_value_provider_returns_same_instance(self):
        """ValueProvider should always return exact same object."""
        from core.di.providers import ValueProvider

        value = {"mutable": "dict"}
        provider = ValueProvider(value)

        instance1 = provider.provide()
        instance2 = provider.provide()

        assert instance1 is instance2
        assert instance1 is value

    def test_value_provider_with_none(self):
        """ValueProvider should handle None value."""
        from core.di.providers import ValueProvider

        provider = ValueProvider(None)
        instance = provider.provide()

        assert instance is None


class TestSingletonProvider:
    """Test SingletonProvider wrapper."""

    def test_singleton_provider_caches_instance(self):
        """SingletonProvider should cache first instance."""
        from core.di.providers import SingletonProvider, ClassProvider

        class MyService:
            pass

        inner_provider = ClassProvider(MyService)
        provider = SingletonProvider(inner_provider)

        instance1 = provider.provide()
        instance2 = provider.provide()

        assert instance1 is instance2

    def test_singleton_provider_with_factory(self):
        """SingletonProvider should work with FactoryProvider."""
        from core.di.providers import SingletonProvider, FactoryProvider

        call_count = [0]

        def create_service():
            call_count[0] += 1
            return {"call": call_count[0]}

        inner_provider = FactoryProvider(create_service)
        provider = SingletonProvider(inner_provider)

        instance1 = provider.provide()
        instance2 = provider.provide()

        assert call_count[0] == 1  # Factory called only once
        assert instance1 is instance2


class TestProviderWithContainer:
    """Test providers integrated with container."""

    def test_container_accepts_providers(self):
        """Container should accept Provider instances."""
        from core.di.container import Container
        from core.di.providers import ClassProvider, FactoryProvider, ValueProvider

        class MyService:
            pass

        container = Container()

        # Using ClassProvider
        container.register_provider(MyService, ClassProvider(MyService))

        instance = container.resolve(MyService)
        assert isinstance(instance, MyService)

    def test_container_factory_provider(self):
        """Container should work with FactoryProvider."""
        from core.di.container import Container
        from core.di.providers import FactoryProvider

        container = Container()

        config = {"env": "test"}
        container.register_provider(dict, FactoryProvider(lambda: config.copy()))

        result = container.resolve(dict)
        assert result == {"env": "test"}

    def test_container_value_provider(self):
        """Container should work with ValueProvider."""
        from core.di.container import Container
        from core.di.providers import ValueProvider

        container = Container()

        settings = {"debug": True}
        container.register_provider(type(settings), ValueProvider(settings))

        # Alternative: register by string name
        container.register_named("settings", ValueProvider(settings))
        result = container.resolve_named("settings")
        assert result["debug"] is True
