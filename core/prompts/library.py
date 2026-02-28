"""Prompt library with in-memory + file-backed templates."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from core.prompts.templates import PromptTemplate


class PromptLibrary:
    def __init__(self, prompts_dir: str | Path | None = None):
        self.prompts_dir = Path(prompts_dir) if prompts_dir is not None else Path("data/prompts")
        self._prompts: Dict[str, PromptTemplate] = {}
        self._load_file_prompts()

    def _load_file_prompts(self) -> None:
        if not self.prompts_dir.exists() or not self.prompts_dir.is_dir():
            return
        for path in self.prompts_dir.glob("*.txt"):
            name = path.stem
            template_text = path.read_text(encoding="utf-8")
            self._prompts[name] = PromptTemplate(name=name, template=template_text)

    def register_prompt(self, name: str, template: PromptTemplate | str) -> None:
        if not name:
            return
        if isinstance(template, PromptTemplate):
            self._prompts[name] = template
        else:
            self._prompts[name] = PromptTemplate(name=name, template=str(template))

    def unregister_prompt(self, name: str) -> None:
        self._prompts.pop(name, None)

    def get_prompt(self, name: str, **kwargs: object) -> str | None:
        template = self._prompts.get(name)
        if template is None:
            return None
        return template.render(kwargs)

    def list_prompts(self) -> List[str]:
        return sorted(self._prompts.keys())

