"""Lazy loading utilities for deferred imports and initialization."""
import importlib
import sys
from typing import Any, Callable, Optional, Dict
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class LazyModule:
    """Lazy module loader that defers import until first access."""
    
    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module = None
    
    def _load(self):
        if self._module is None:
            logger.debug(f"Lazy loading module: {self._module_name}")
            self._module = importlib.import_module(self._module_name)
        return self._module
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)
    
    def __dir__(self):
        return dir(self._load())


def lazy_import(module_name: str) -> LazyModule:
    """Create a lazy module import."""
    return LazyModule(module_name)


class LazyLoader:
    """Generic lazy loader for expensive objects."""
    
    def __init__(self, factory: Callable[[], Any], name: str = None):
        self._factory = factory
        self._instance = None
        self._name = name or factory.__name__
        self._initialized = False
    
    def get(self) -> Any:
        """Get the lazily loaded instance."""
        if not self._initialized:
            logger.debug(f"Lazy initializing: {self._name}")
            self._instance = self._factory()
            self._initialized = True
        return self._instance
    
    def reset(self):
        """Reset the lazy loader to uninitialized state."""
        self._instance = None
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        return self._initialized
    
    def __call__(self) -> Any:
        return self.get()


class LazyProperty:
    """Descriptor for lazy property initialization."""
    
    def __init__(self, factory: Callable):
        self._factory = factory
        self._name = None
    
    def __set_name__(self, owner, name):
        self._name = f"_lazy_{name}"
    
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        
        if not hasattr(obj, self._name):
            setattr(obj, self._name, self._factory(obj))
        return getattr(obj, self._name)


def lazy_property(func: Callable) -> LazyProperty:
    """Decorator for lazy property initialization."""
    return LazyProperty(func)


class ModuleRegistry:
    """Registry for lazy-loaded modules with optional preloading."""
    
    def __init__(self):
        self._modules: Dict[str, LazyModule] = {}
        self._preload_list: list = []
    
    def register(self, name: str, module_path: str, preload: bool = False):
        """Register a module for lazy loading."""
        self._modules[name] = LazyModule(module_path)
        if preload:
            self._preload_list.append(name)
    
    def get(self, name: str) -> Any:
        """Get a registered module."""
        if name not in self._modules:
            raise KeyError(f"Module {name} not registered")
        return self._modules[name]
    
    def preload_all(self):
        """Preload all modules marked for preloading."""
        for name in self._preload_list:
            logger.info(f"Preloading module: {name}")
            self._modules[name]._load()
    
    def __getitem__(self, name: str) -> Any:
        return self.get(name)


# Common lazy imports for Jarvis
_lazy_modules = ModuleRegistry()
_lazy_modules.register("numpy", "numpy")
_lazy_modules.register("pandas", "pandas")
_lazy_modules.register("torch", "torch")
_lazy_modules.register("sklearn", "sklearn")
_lazy_modules.register("matplotlib", "matplotlib.pyplot")


def get_lazy_module(name: str) -> Any:
    """Get a commonly used lazy module."""
    return _lazy_modules.get(name)
