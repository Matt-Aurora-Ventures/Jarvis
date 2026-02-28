"""Prompt template primitives."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List

_VAR_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@dataclass
class PromptTemplate:
    name: str
    template: str
    description: str = ""

    def get_variables(self) -> List[str]:
        return sorted(set(_VAR_RE.findall(self.template)))

    def validate(self, context: Dict[str, object]) -> List[str]:
        missing: List[str] = []
        for var in self.get_variables():
            if var not in context:
                missing.append(f"Missing variable: {var}")
        return missing

    def render(self, context: Dict[str, object]) -> str:
        rendered = self.template
        for var in self.get_variables():
            if var in context:
                rendered = re.sub(
                    r"\{\{\s*" + re.escape(var) + r"\s*\}\}",
                    str(context[var]),
                    rendered,
                )
        return rendered

