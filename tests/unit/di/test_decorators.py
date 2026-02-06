"""Tests for DI decorators."""
import pytest
from abc import ABC, abstractmethod


class TestInjectableDecorator:
    """Test @injectable decorator."""

    def test_injectable_marks_class(self):
        """@injectable should mark class as injectable."""
        from core.di.decorators import injectable

        @injectable
        class MyService:
            pass

        assert hasattr(MyService, '__injectable__')
        assert MyService.__injectable__ is True

    def test_injectable_preserves_class(self):
        """@injectable should not modify class behavior."""
        from core.di.decorators import injectable

        @injectable
        class MyService:
            def __init__(self, value: int = 10):
                self.value = value

            def get_value(self):
                return self.value

        service = MyService(42)
        assert service.get_value() == 42

    def test_injectable_with_name(self):
        """@injectable can specify a custom service name."""
        from core.di.decorators import injectable

        @injectable(name="custom_service")
        class MyService:
            pass

        assert MyService.__injectable_name__ == "custom_service"


class TestSingletonDecorator:
    """Test @singleton decorator."""

    def test_singleton_marks_scope(self):
        """@singleton should set scope to SINGLETON."""
        from core.di.decorators import singleton
        from core.di.container import Scope

        @singleton
        class MyService:
            pass

        assert hasattr(MyService, '__scope__')
        assert MyService.__scope__ == Scope.SINGLETON

    def test_singleton_with_container_registration(self):
        """@singleton classes should auto-register with container."""
        from core.di.decorators import singleton
        from core.di.container import Container

        container = Container()

        @singleton(container=container)
        class MySingletonService:
            pass

        # Should be registered in container
        assert MySingletonService in container

        # Should return same instance
        instance1 = container.resolve(MySingletonService)
        instance2 = container.resolve(MySingletonService)
        assert instance1 is instance2


class TestScopedDecorator:
    """Test @scoped decorator."""

    def test_scoped_marks_request_scope(self):
        """@scoped should set scope to REQUEST."""
        from core.di.decorators import scoped
        from core.di.container import Scope

        @scoped
        class MyService:
            pass

        assert hasattr(MyService, '__scope__')
        assert MyService.__scope__ == Scope.REQUEST


class TestTransientDecorator:
    """Test @transient decorator."""

    def test_transient_marks_transient_scope(self):
        """@transient should set scope to TRANSIENT."""
        from core.di.decorators import transient
        from core.di.container import Scope

        @transient
        class MyService:
            pass

        assert hasattr(MyService, '__scope__')
        assert MyService.__scope__ == Scope.TRANSIENT


class TestInjectDecorator:
    """Test @inject decorator for dependency injection."""

    def test_inject_single_dependency(self):
        """@inject should inject single dependency."""
        from core.di.decorators import inject
        from core.di.container import Container

        class Logger:
            def log(self, msg: str):
                return f"logged: {msg}"

        container = Container()
        container.register_singleton(Logger, lambda: Logger())

        # Patch global container for test
        from core.di import container as di_container
        original = di_container.container
        di_container.container = container

        try:
            @inject(Logger)
            def my_function(logger: Logger):
                return logger.log("test")

            result = my_function()
            assert result == "logged: test"
        finally:
            di_container.container = original

    def test_inject_multiple_dependencies(self):
        """@inject should handle multiple dependencies."""
        from core.di.decorators import inject
        from core.di.container import Container

        class Logger:
            pass

        class Database:
            pass

        container = Container()
        container.register_singleton(Logger, lambda: Logger())
        container.register_singleton(Database, lambda: Database())

        from core.di import container as di_container
        original = di_container.container

        try:
            di_container.container = container

            @inject(Logger, Database)
            def my_function(logger: Logger, database: Database):
                return (logger, database)

            result = my_function()
            assert isinstance(result[0], Logger)
            assert isinstance(result[1], Database)
        finally:
            di_container.container = original

    def test_inject_preserves_explicit_args(self):
        """@inject should allow explicit args to override."""
        from core.di.decorators import inject
        from core.di.container import Container

        class Logger:
            def __init__(self, name: str = "default"):
                self.name = name

        container = Container()
        container.register_singleton(Logger, lambda: Logger("container"))

        from core.di import container as di_container
        original = di_container.container

        try:
            di_container.container = container

            @inject(Logger)
            def my_function(logger: Logger):
                return logger.name

            # With no explicit arg, uses injected
            result = my_function()
            assert result == "container"

            # With explicit arg, uses explicit
            explicit_logger = Logger("explicit")
            result = my_function(logger=explicit_logger)
            assert result == "explicit"
        finally:
            di_container.container = original

    def test_inject_async_function(self):
        """@inject should work with async functions."""
        import asyncio
        from core.di.decorators import inject
        from core.di.container import Container

        class AsyncService:
            async def get_data(self):
                return "async_data"

        container = Container()
        container.register_singleton(AsyncService, lambda: AsyncService())

        from core.di import container as di_container
        original = di_container.container

        try:
            di_container.container = container

            @inject(AsyncService)
            async def async_function(service: AsyncService):
                return await service.get_data()

            result = asyncio.get_event_loop().run_until_complete(async_function())
            assert result == "async_data"
        finally:
            di_container.container = original

    def test_inject_method(self):
        """@inject should work with class methods."""
        from core.di.decorators import inject
        from core.di.container import Container

        class Logger:
            def log(self, msg: str):
                return msg

        container = Container()
        container.register_singleton(Logger, lambda: Logger())

        from core.di import container as di_container
        original = di_container.container

        try:
            di_container.container = container

            class MyClass:
                @inject(Logger)
                def process(self, logger: Logger):
                    return logger.log("processed")

            obj = MyClass()
            result = obj.process()
            assert result == "processed"
        finally:
            di_container.container = original


class TestInjectByName:
    """Test named injection."""

    def test_inject_by_name(self):
        """Should be able to inject by registered name."""
        from core.di.decorators import inject_by_name
        from core.di.container import Container

        container = Container()
        container.register_named("primary_db", lambda: {"host": "primary"})
        container.register_named("replica_db", lambda: {"host": "replica"})

        from core.di import container as di_container
        original = di_container.container

        try:
            di_container.container = container

            @inject_by_name(db="primary_db")
            def get_primary(db):
                return db["host"]

            @inject_by_name(db="replica_db")
            def get_replica(db):
                return db["host"]

            assert get_primary() == "primary"
            assert get_replica() == "replica"
        finally:
            di_container.container = original
