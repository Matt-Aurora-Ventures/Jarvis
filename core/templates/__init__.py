"""
Template Engine for Message Formatting

This module provides a template engine for consistent, customizable message formatting.

Components:
- Template: A compiled template that can be rendered with context
- TemplateEngine: Main engine for compiling and rendering templates
- TemplateLoader: Loads templates from the filesystem with caching
- Helpers: Built-in helper functions for formatting dates, numbers, etc.

Usage:
    from core.templates import TemplateEngine, TemplateLoader

    # Direct template compilation
    engine = TemplateEngine()
    template = engine.compile("Hello, {{name}}!")
    result = template.render({"name": "World"})

    # Loading templates from files
    loader = TemplateLoader()
    result = loader.load("greeting").render({"name": "World"})
"""

from core.templates.engine import (
    Template,
    TemplateEngine,
    TemplateSyntaxError,
    TemplateRenderError,
)

from core.templates.loader import (
    TemplateLoader,
    TemplateNotFoundError,
    TemplateLoadError,
)

from core.templates.helpers import (
    format_date,
    format_number,
    format_currency,
    truncate,
    uppercase,
    lowercase,
    capitalize,
    get_builtin_helpers,
    HelperError,
)

__all__ = [
    # Engine
    "Template",
    "TemplateEngine",
    "TemplateSyntaxError",
    "TemplateRenderError",
    # Loader
    "TemplateLoader",
    "TemplateNotFoundError",
    "TemplateLoadError",
    # Helpers
    "format_date",
    "format_number",
    "format_currency",
    "truncate",
    "uppercase",
    "lowercase",
    "capitalize",
    "get_builtin_helpers",
    "HelperError",
]
