"""
Template Loader

This module provides template loading functionality with caching and file watching.

Features:
- Load templates from the filesystem
- Cache templates for performance
- Watch for file changes and auto-reload
- Support multiple template directories
"""

import os
import time
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Union
from collections import OrderedDict

from core.templates.engine import Template, TemplateSyntaxError


class TemplateNotFoundError(Exception):
    """Raised when a template file cannot be found."""
    pass


class TemplateLoadError(Exception):
    """Raised when a template cannot be loaded or compiled."""
    pass


class TemplateLoader:
    """
    Loads templates from the filesystem with caching.

    Args:
        templates_dir: Directory containing template files
        create_if_missing: Create directory if it doesn't exist
        cache_max_size: Maximum number of templates to cache (0 for unlimited)
    """

    # Default template extensions to try
    DEFAULT_EXTENSIONS = [".txt", ".html", ".md", ".j2"]

    def __init__(
        self,
        templates_dir: Optional[Union[str, Path]] = None,
        create_if_missing: bool = True,
        cache_max_size: int = 100
    ):
        """Initialize the template loader."""
        if templates_dir is None:
            # Default to bots/templates/
            templates_dir = Path(__file__).parent.parent.parent / "bots" / "templates"

        self.templates_dir = Path(templates_dir)

        if not self.templates_dir.exists():
            if create_if_missing:
                self.templates_dir.mkdir(parents=True, exist_ok=True)
            else:
                raise FileNotFoundError(f"Templates directory not found: {self.templates_dir}")

        self._cache: OrderedDict[str, Template] = OrderedDict()
        self._cache_max_size = cache_max_size
        self._cache_hits = 0
        self._cache_misses = 0

        self._watcher: Optional[threading.Thread] = None
        self._watching = False
        self._watch_callback: Optional[Callable] = None

    def load(self, name: str) -> Template:
        """
        Load a template by name.

        Args:
            name: Template name (with or without extension)

        Returns:
            Compiled Template object

        Raises:
            TemplateNotFoundError: If template not found
            TemplateLoadError: If template has syntax errors
        """
        # Security: Prevent directory traversal
        if ".." in name or name.startswith("/") or name.startswith("\\"):
            raise TemplateNotFoundError(f"Invalid template name: {name}")

        # Normalize path separators
        name = name.replace("\\", "/")

        # Find template file
        template_path = self._find_template(name)
        if template_path is None:
            raise TemplateNotFoundError(f"Template not found: {name}")

        # Check cache
        cache_key = str(template_path)
        if cache_key in self._cache:
            self._cache_hits += 1
            # Move to end (LRU)
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        self._cache_misses += 1

        # Load and compile template
        try:
            source = template_path.read_text(encoding="utf-8")
            template = Template(source)
        except TemplateSyntaxError as e:
            raise TemplateLoadError(f"Syntax error in template {name}: {e}")
        except Exception as e:
            raise TemplateLoadError(f"Error loading template {name}: {e}")

        # Add to cache
        self._add_to_cache(cache_key, template)

        return template

    def _find_template(self, name: str) -> Optional[Path]:
        """Find a template file by name."""
        # Check if name already has extension
        name_path = Path(name)
        if name_path.suffix:
            full_path = self.templates_dir / name
            if full_path.exists():
                return full_path
            return None

        # Try default extensions
        for ext in self.DEFAULT_EXTENSIONS:
            full_path = self.templates_dir / (name + ext)
            if full_path.exists():
                return full_path

        return None

    def _add_to_cache(self, key: str, template: Template) -> None:
        """Add a template to the cache, respecting max size."""
        if self._cache_max_size > 0 and len(self._cache) >= self._cache_max_size:
            # Remove oldest item (LRU eviction)
            self._cache.popitem(last=False)

        self._cache[key] = template

    def reload(self, name: str) -> Template:
        """
        Force reload a template, bypassing cache.

        Args:
            name: Template name

        Returns:
            Freshly loaded Template object
        """
        # Find and remove from cache
        template_path = self._find_template(name)
        if template_path is None:
            raise TemplateNotFoundError(f"Template not found: {name}")

        cache_key = str(template_path)
        if cache_key in self._cache:
            del self._cache[cache_key]

        # Load fresh
        return self.load(name)

    def reload_all(self) -> None:
        """Clear cache and force reload all templates on next access."""
        self._cache.clear()

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "cached": len(self._cache),
            "max_size": self._cache_max_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
        }

    def watch_for_changes(
        self,
        auto_reload: bool = False,
        callback: Optional[Callable[[str, Path], None]] = None,
        interval: float = 1.0
    ) -> threading.Thread:
        """
        Start watching for template file changes.

        Args:
            auto_reload: Automatically reload changed templates
            callback: Optional callback function(name, path) on change
            interval: Check interval in seconds

        Returns:
            The watcher thread
        """
        self._watching = True
        self._watch_callback = callback

        def watch_loop():
            last_modified: Dict[str, float] = {}

            # Initialize modification times
            for path in self.templates_dir.rglob("*"):
                if path.is_file():
                    last_modified[str(path)] = path.stat().st_mtime

            while self._watching:
                try:
                    for path in self.templates_dir.rglob("*"):
                        if not path.is_file():
                            continue

                        path_str = str(path)
                        mtime = path.stat().st_mtime

                        if path_str in last_modified:
                            if mtime > last_modified[path_str]:
                                # File changed
                                last_modified[path_str] = mtime
                                name = path.stem

                                if auto_reload:
                                    cache_key = path_str
                                    if cache_key in self._cache:
                                        del self._cache[cache_key]

                                if self._watch_callback:
                                    try:
                                        self._watch_callback(name, path)
                                    except Exception:
                                        pass
                        else:
                            # New file
                            last_modified[path_str] = mtime

                    time.sleep(interval)
                except Exception:
                    pass

        self._watcher = threading.Thread(target=watch_loop, daemon=True)
        self._watcher.start()
        return self._watcher

    def stop_watching(self) -> None:
        """Stop the file watcher."""
        self._watching = False
        if self._watcher:
            self._watcher.join(timeout=2.0)
            self._watcher = None

    def list_templates(self) -> list:
        """
        List all available templates.

        Returns:
            List of template names
        """
        templates = []
        for ext in self.DEFAULT_EXTENSIONS:
            for path in self.templates_dir.rglob(f"*{ext}"):
                relative = path.relative_to(self.templates_dir)
                templates.append(str(relative))
        return sorted(templates)
