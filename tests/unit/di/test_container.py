"""Tests for dependency injection container."""
import pytest
from abc import ABC, abstractmethod
from typing import Protocol


class TestContainerBasics:
    """Test basic container functionality."""

    def test_container_singleton_pattern(self):
        """Container.get_instance() should return the same instance."""
        from core.di.container import Container

        container1 = Container.get_instance()
        container2 = Container.get_instance()

        assert container1 is container2

    def test_container_register_and_resolve(self):
        """Should register and resolve a simple dependency."""
        from core.di.container import Container, Scope

        container = Container()

        class MyService:
            def get_value(self):
                return 42

        container.register(MyService, lambda: MyService(), Scope.TRANSIENT)

        service = container.resolve(MyService)
        assert isinstance(service, MyService)
        assert service.get_value() == 42

    def test_container_register_singleton(self):
        """register_singleton should return same instance on multiple resolves."""
        from core.di.container import Container

        container = Container()

        class SingletonService:
            pass

        container.register_singleton(SingletonService, lambda: SingletonService())

        instance1 = container.resolve(SingletonService)
        instance2 = container.resolve(SingletonService)

        assert instance1 is instance2

    def test_container_transient_returns_new_instance(self):
        """Transient scope should return new instance each time."""
        from core.di.container import Container, Scope

        container = Container()

        class TransientService:
            pass

        container.register(TransientService, lambda: TransientService(), Scope.TRANSIENT)

        instance1 = container.resolve(TransientService)
        instance2 = container.resolve(TransientService)

        assert instance1 is not instance2

    def test_container_register_instance(self):
        """register_instance should store and return the exact instance."""
        from core.di.container import Container

        container = Container()

        class MyService:
            pass

        instance = MyService()
        container.register_instance(MyService, instance)

        resolved = container.resolve(MyService)
        assert resolved is instance

    def test_container_resolve_unregistered_raises(self):
        """Resolving unregistered interface should raise ValueError."""
        from core.di.container import Container

        container = Container()

        class UnregisteredService:
            pass

        with pytest.raises(ValueError, match="No factory registered"):
            container.resolve(UnregisteredService)

    def test_container_contains(self):
        """Container should support 'in' operator."""
        from core.di.container import Container, Scope

        container = Container()

        class RegisteredService:
            pass

        class NotRegisteredService:
            pass

        container.register(RegisteredService, lambda: RegisteredService(), Scope.TRANSIENT)

        assert RegisteredService in container
        assert NotRegisteredService not in container

    def test_container_reset_clears_instances(self):
        """reset() should clear cached singleton instances."""
        from core.di.container import Container

        container = Container()

        class SingletonService:
            pass

        container.register_singleton(SingletonService, lambda: SingletonService())

        instance1 = container.resolve(SingletonService)
        container.reset()
        instance2 = container.resolve(SingletonService)

        assert instance1 is not instance2


class TestScopedContainer:
    """Test scoped container functionality."""

    def test_create_scope_returns_scoped_container(self):
        """create_scope() should return a ScopedContainer."""
        from core.di.container import Container, ScopedContainer

        container = Container()
        scoped = container.create_scope()

        assert isinstance(scoped, ScopedContainer)

    def test_scoped_container_inherits_singletons(self):
        """Scoped container should share singletons with parent."""
        from core.di.container import Container

        container = Container()

        class SingletonService:
            pass

        container.register_singleton(SingletonService, lambda: SingletonService())
        singleton_instance = container.resolve(SingletonService)

        scoped = container.create_scope()
        scoped_singleton = scoped.resolve(SingletonService)

        assert scoped_singleton is singleton_instance

    def test_scoped_services_are_unique_per_scope(self):
        """Services with REQUEST scope should be unique per scope."""
        from core.di.container import Container, Scope

        container = Container()

        class RequestService:
            pass

        container.register(RequestService, lambda: RequestService(), Scope.REQUEST)

        scope1 = container.create_scope()
        scope2 = container.create_scope()

        # Within same scope, should get same instance
        instance1a = scope1.resolve(RequestService)
        instance1b = scope1.resolve(RequestService)
        assert instance1a is instance1b

        # Different scopes should get different instances
        instance2 = scope2.resolve(RequestService)
        assert instance1a is not instance2

    def test_scoped_container_dispose(self):
        """Scoped container dispose() should clear scoped instances."""
        from core.di.container import Container, Scope

        container = Container()

        class RequestService:
            pass

        container.register(RequestService, lambda: RequestService(), Scope.REQUEST)

        scoped = container.create_scope()
        instance1 = scoped.resolve(RequestService)
        scoped.dispose()

        # After dispose, should not be able to resolve
        # Or create a new scope and verify new instance
        scoped2 = container.create_scope()
        instance2 = scoped2.resolve(RequestService)
        assert instance1 is not instance2

    def test_scoped_container_context_manager(self):
        """Scoped container should work as context manager."""
        from core.di.container import Container, Scope

        container = Container()

        class RequestService:
            pass

        container.register(RequestService, lambda: RequestService(), Scope.REQUEST)

        with container.create_scope() as scope:
            instance = scope.resolve(RequestService)
            assert isinstance(instance, RequestService)


class TestContainerWithInterfaces:
    """Test container with interface/implementation pattern."""

    def test_register_interface_with_implementation(self):
        """Should be able to register interface with concrete implementation."""
        from core.di.container import Container

        class IRepository(ABC):
            @abstractmethod
            def get_data(self) -> str:
                pass

        class ConcreteRepository(IRepository):
            def get_data(self) -> str:
                return "data"

        container = Container()
        container.register_singleton(IRepository, lambda: ConcreteRepository())

        repo = container.resolve(IRepository)
        assert isinstance(repo, ConcreteRepository)
        assert repo.get_data() == "data"

    def test_register_protocol_with_implementation(self):
        """Should work with Protocol-based interfaces."""
        from core.di.container import Container

        class ILogger(Protocol):
            def log(self, message: str) -> None:
                ...

        class ConsoleLogger:
            def log(self, message: str) -> None:
                print(message)

        container = Container()
        container.register_singleton(ILogger, lambda: ConsoleLogger())

        logger = container.resolve(ILogger)
        assert hasattr(logger, 'log')


class TestContainerDependencyChain:
    """Test resolving dependencies with chains."""

    def test_resolve_with_dependencies(self):
        """Should resolve services that depend on other services."""
        from core.di.container import Container

        class Database:
            def query(self):
                return "data"

        class Repository:
            def __init__(self, db: Database):
                self.db = db

            def get_data(self):
                return self.db.query()

        container = Container()
        container.register_singleton(Database, lambda: Database())
        container.register_singleton(
            Repository,
            lambda: Repository(container.resolve(Database))
        )

        repo = container.resolve(Repository)
        assert repo.get_data() == "data"

    def test_auto_resolve_dependencies(self):
        """Container should auto-resolve dependencies via type hints."""
        from core.di.container import Container

        class Logger:
            def log(self, msg: str):
                pass

        class Service:
            def __init__(self, logger: Logger):
                self.logger = logger

        container = Container()
        container.register_singleton(Logger, lambda: Logger())
        container.register_auto(Service)  # Should auto-detect Logger dependency

        service = container.resolve(Service)
        assert isinstance(service.logger, Logger)
