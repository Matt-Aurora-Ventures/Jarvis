"""Base plugin architecture."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import importlib
import logging

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)


class Plugin(ABC):
    """Base class for all Jarvis plugins."""
    
    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the plugin. Return True if successful."""
        pass
    
    @abstractmethod
    async def shutdown(self):
        """Clean up resources."""
        pass
    
    async def on_message(self, message: str, context: Dict[str, Any] = None) -> Optional[str]:
        """Handle incoming message. Return response or None."""
        return None
    
    async def on_event(self, event_type: str, data: Dict[str, Any]):
        """Handle system event."""
        pass
    
    async def on_command(self, command: str, args: List[str]) -> Optional[str]:
        """Handle command. Return response or None."""
        return None
    
    def get_commands(self) -> List[str]:
        """Return list of commands this plugin handles."""
        return []
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Return JSON schema for plugin configuration."""
        return self.metadata.config_schema


class PluginManager:
    """Manage plugin lifecycle."""
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self._initialized: set = set()
    
    def register(self, plugin: Plugin):
        """Register a plugin."""
        meta = plugin.metadata
        if meta.name in self.plugins:
            logger.warning(f"Plugin {meta.name} already registered, replacing")
        self.plugins[meta.name] = plugin
        logger.info(f"Registered plugin: {meta.name} v{meta.version}")
    
    def unregister(self, name: str):
        """Unregister a plugin."""
        if name in self.plugins:
            del self.plugins[name]
            self._initialized.discard(name)
    
    async def initialize_all(self, config: Dict[str, Any] = None):
        """Initialize all registered plugins."""
        config = config or {}
        
        for name, plugin in self.plugins.items():
            if name in self._initialized:
                continue
            
            plugin_config = config.get(name, {})
            try:
                success = await plugin.initialize(plugin_config)
                if success:
                    self._initialized.add(name)
                    logger.info(f"Initialized plugin: {name}")
                else:
                    logger.error(f"Failed to initialize plugin: {name}")
            except Exception as e:
                logger.error(f"Error initializing plugin {name}: {e}")
    
    async def shutdown_all(self):
        """Shutdown all plugins."""
        for name, plugin in self.plugins.items():
            if name not in self._initialized:
                continue
            try:
                await plugin.shutdown()
                self._initialized.discard(name)
                logger.info(f"Shutdown plugin: {name}")
            except Exception as e:
                logger.error(f"Error shutting down plugin {name}: {e}")
    
    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Broadcast event to all plugins."""
        for name, plugin in self.plugins.items():
            if name not in self._initialized:
                continue
            try:
                await plugin.on_event(event_type, data)
            except Exception as e:
                logger.error(f"Plugin {name} error handling event {event_type}: {e}")
    
    async def handle_message(self, message: str, context: Dict[str, Any] = None) -> Optional[str]:
        """Pass message to plugins until one responds."""
        for name, plugin in self.plugins.items():
            if name not in self._initialized:
                continue
            try:
                response = await plugin.on_message(message, context)
                if response:
                    return response
            except Exception as e:
                logger.error(f"Plugin {name} error handling message: {e}")
        return None
    
    async def handle_command(self, command: str, args: List[str]) -> Optional[str]:
        """Route command to appropriate plugin."""
        for name, plugin in self.plugins.items():
            if name not in self._initialized:
                continue
            if command in plugin.get_commands():
                try:
                    return await plugin.on_command(command, args)
                except Exception as e:
                    logger.error(f"Plugin {name} error handling command {command}: {e}")
        return None
    
    def get_all_commands(self) -> Dict[str, List[str]]:
        """Get all commands from all plugins."""
        return {name: plugin.get_commands() for name, plugin in self.plugins.items()}
    
    def load_from_directory(self, directory: Path):
        """Load plugins from a directory."""
        if not directory.exists():
            return
        
        for plugin_file in directory.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            
            module_name = plugin_file.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, plugin_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Look for Plugin subclass
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, Plugin) and attr is not Plugin:
                        plugin = attr()
                        self.register(plugin)
                        break
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_file}: {e}")


# Global plugin manager
plugin_manager = PluginManager()
