"""
Template Engine

This module provides the core template engine for parsing and rendering templates.

Syntax:
- Variables: {{name}} - substitutes the value of 'name' from context
- Defaults: {{name|default:value}} - uses 'value' if 'name' is missing
- Conditionals: {{#if condition}}...{{/if}} - renders block if condition is truthy
- Else: {{#if condition}}...{{#else}}...{{/if}} - conditional with else branch
- Unless: {{#unless condition}}...{{/unless}} - renders if condition is falsy
- Helpers: {{helper arg1 arg2}} - calls helper function with arguments
- Nested access: {{user.name}} - accesses nested dictionary values
"""

import re
from typing import Any, Dict, Optional, Callable, List, Tuple
from pathlib import Path

from core.templates.helpers import get_builtin_helpers


class TemplateSyntaxError(Exception):
    """Raised when a template has invalid syntax."""
    pass


class TemplateRenderError(Exception):
    """Raised when template rendering fails."""
    pass


class Template:
    """
    A compiled template that can be rendered with context.

    Args:
        source: The template source string
    """

    # Regex patterns for template syntax
    VAR_PATTERN = re.compile(r"\{\{([^#/][^}]*?)\}\}")
    BLOCK_START_PATTERN = re.compile(r"\{\{#(if|unless)\s+([^}]+)\}\}")
    BLOCK_ELSE_PATTERN = re.compile(r"\{\{#else\}\}")
    BLOCK_END_PATTERN = re.compile(r"\{\{/(if|unless)\}\}")

    def __init__(self, source: str):
        """Initialize template with source string."""
        self.source = source
        self._validate_syntax()

    def _validate_syntax(self) -> None:
        """Validate template syntax."""
        # Check for unclosed variable tags
        open_count = self.source.count("{{")
        close_count = self.source.count("}}")
        if open_count != close_count:
            raise TemplateSyntaxError("Unclosed template tag")

        # Check for balanced blocks
        stack = []
        for match in re.finditer(r"\{\{#(if|unless)\s+([^}]+)\}\}", self.source):
            stack.append(match.group(1))

        for match in re.finditer(r"\{\{/(if|unless)\}\}", self.source):
            block_type = match.group(1)
            if not stack:
                raise TemplateSyntaxError(f"Unexpected closing tag: {{{{/{block_type}}}}}")
            expected = stack.pop()
            if expected != block_type:
                raise TemplateSyntaxError(
                    f"Mismatched block tags: expected {{{{/{expected}}}}}, got {{{{/{block_type}}}}}"
                )

        if stack:
            raise TemplateSyntaxError(f"Unclosed block: {{{{#{stack[-1]}}}}}")

    def render(
        self,
        context: Dict[str, Any],
        helpers: Optional[Dict[str, Callable]] = None
    ) -> str:
        """
        Render the template with the given context.

        Args:
            context: Dictionary of values to substitute
            helpers: Optional dictionary of helper functions

        Returns:
            Rendered template string
        """
        if helpers is None:
            helpers = {}

        result = self.source

        # Process conditionals first (they may contain variables)
        result = self._process_conditionals(result, context)

        # Process helpers
        result = self._process_helpers(result, context, helpers)

        # Process variables
        result = self._process_variables(result, context)

        return result

    def _process_conditionals(self, text: str, context: Dict[str, Any]) -> str:
        """Process if/unless blocks in the template."""
        # Process from innermost to outermost
        max_iterations = 100  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Find an if/unless block without nested blocks inside
            match = self._find_innermost_block(text)
            if not match:
                break

            block_type, condition, if_content, else_content, full_match, start, end = match

            # Evaluate condition
            condition_value = self._get_value(condition.strip(), context)
            is_truthy = self._is_truthy(condition_value)

            # Invert for unless
            if block_type == "unless":
                is_truthy = not is_truthy

            # Replace block with appropriate content
            if is_truthy:
                replacement = if_content
            else:
                replacement = else_content

            text = text[:start] + replacement + text[end:]

        return text

    def _find_innermost_block(self, text: str) -> Optional[Tuple]:
        """Find the innermost conditional block."""
        # Find all block starts
        starts = list(re.finditer(r"\{\{#(if|unless)\s+([^}]+)\}\}", text))
        if not starts:
            return None

        # For each start, find its matching end
        for start_match in reversed(starts):  # Start from innermost
            start_pos = start_match.start()
            block_type = start_match.group(1)
            condition = start_match.group(2)

            # Find content after start
            content_start = start_match.end()

            # Find matching end (accounting for nested blocks)
            depth = 1
            pos = content_start
            else_pos = None

            while pos < len(text) and depth > 0:
                # Look for next tag
                next_start = text.find("{{#" + block_type, pos)
                next_else = text.find("{{#else}}", pos)
                next_end = text.find("{{/" + block_type + "}}", pos)

                # Find which comes first
                positions = []
                if next_start != -1:
                    positions.append(("start", next_start))
                if next_else != -1 and depth == 1:  # Only track else at current depth
                    positions.append(("else", next_else))
                if next_end != -1:
                    positions.append(("end", next_end))

                if not positions:
                    break

                positions.sort(key=lambda x: x[1])
                tag_type, tag_pos = positions[0]

                if tag_type == "start":
                    depth += 1
                    pos = tag_pos + 1
                elif tag_type == "else":
                    else_pos = tag_pos
                    pos = tag_pos + 9  # len("{{#else}}")
                elif tag_type == "end":
                    depth -= 1
                    if depth == 0:
                        # Found matching end
                        end_pos = tag_pos + len("{{/" + block_type + "}}")

                        if else_pos is not None:
                            if_content = text[content_start:else_pos]
                            else_content = text[else_pos + 9:tag_pos]  # 9 = len("{{#else}}")
                        else:
                            if_content = text[content_start:tag_pos]
                            else_content = ""

                        full_match = text[start_pos:end_pos]
                        return (
                            block_type,
                            condition,
                            if_content,
                            else_content,
                            full_match,
                            start_pos,
                            end_pos
                        )
                    pos = tag_pos + 1

        return None

    def _process_helpers(
        self,
        text: str,
        context: Dict[str, Any],
        helpers: Dict[str, Callable]
    ) -> str:
        """Process helper function calls."""
        def replace_helper(match: re.Match) -> str:
            content = match.group(1).strip()
            parts = content.split()

            if len(parts) < 2:
                return match.group(0)  # Not a helper call

            helper_name = parts[0]
            if helper_name not in helpers:
                return ""  # Unknown helper returns empty

            # Get arguments
            args = []
            for part in parts[1:]:
                value = self._get_value(part, context)
                args.append(value)

            try:
                result = helpers[helper_name](*args)
                return str(result) if result is not None else ""
            except Exception:
                return ""

        # Match helper calls (has space after first word)
        pattern = re.compile(r"\{\{(\w+\s+[^}]+)\}\}")
        return pattern.sub(replace_helper, text)

    def _process_variables(self, text: str, context: Dict[str, Any]) -> str:
        """Process variable substitutions."""
        def replace_var(match: re.Match) -> str:
            content = match.group(1).strip()

            # Check for default value
            if "|default:" in content:
                var_name, default = content.split("|default:", 1)
                value = self._get_value(var_name.strip(), context)
                if value is None or value == "":
                    return default
                return str(value)

            # Check if it's a helper call (has space)
            if " " in content:
                return match.group(0)  # Leave for helper processing

            value = self._get_value(content, context)
            if value is None:
                return ""
            return str(value)

        return self.VAR_PATTERN.sub(replace_var, text)

    def _get_value(self, path: str, context: Dict[str, Any]) -> Any:
        """Get a value from context using dot notation."""
        parts = path.split(".")
        value = context

        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, (list, tuple)):
                try:
                    index = int(part)
                    value = value[index]
                except (ValueError, IndexError):
                    return None
            else:
                return None

            if value is None:
                return None

        return value

    def _is_truthy(self, value: Any) -> bool:
        """Check if a value is truthy."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, (list, tuple, dict)):
            return len(value) > 0
        return bool(value)


class TemplateEngine:
    """
    Template engine for compiling and rendering templates.

    Usage:
        engine = TemplateEngine()
        template = engine.compile("Hello, {{name}}!")
        result = template.render({"name": "World"})
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the template engine.

        Args:
            templates_dir: Optional directory for named templates
        """
        self.templates_dir = Path(templates_dir) if templates_dir else None
        self.helpers: Dict[str, Callable] = {}
        self._cache: Dict[str, Template] = {}

        # Load built-in helpers
        self._load_builtin_helpers()

    def _load_builtin_helpers(self) -> None:
        """Load built-in helper functions."""
        self.helpers.update(get_builtin_helpers())

    def compile(self, source: str) -> Template:
        """
        Compile a template string.

        Args:
            source: The template source string

        Returns:
            Compiled Template object

        Raises:
            TemplateSyntaxError: If template has invalid syntax
        """
        return Template(source)

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a named template from the templates directory.

        Args:
            template_name: Name of the template file
            context: Dictionary of values to substitute

        Returns:
            Rendered template string

        Raises:
            FileNotFoundError: If template file not found
            TemplateSyntaxError: If template has invalid syntax
        """
        if self.templates_dir is None:
            raise ValueError("templates_dir not set")

        # Add extension if not present
        if not template_name.endswith((".txt", ".html", ".md")):
            template_name = template_name + ".txt"

        template_path = self.templates_dir / template_name

        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")

        # Check cache
        cache_key = str(template_path)
        if cache_key not in self._cache:
            source = template_path.read_text(encoding="utf-8")
            self._cache[cache_key] = self.compile(source)

        return self._cache[cache_key].render(context, helpers=self.helpers)

    def register_helper(self, name: str, func: Callable) -> None:
        """
        Register a helper function.

        Args:
            name: Name to use in templates
            func: The helper function
        """
        self.helpers[name] = func

    def clear_cache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()
