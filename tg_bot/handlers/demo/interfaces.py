"""Explicit interfaces for modular demo handler domains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol


@dataclass(frozen=True)
class DemoRequestContext:
    """Common request context used across demo handlers/services."""

    user_id: Optional[int]
    chat_id: Optional[int]
    token_address: Optional[str] = None
    metadata: Dict[str, Any] | None = None


class DemoStateStore(Protocol):
    """State access contract for demo flows."""

    def get(self, key: str, default: Any = None) -> Any:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


class DemoTradingService(Protocol):
    """Trading service contract used by demo handlers."""

    async def execute_buy(self, context: DemoRequestContext, amount_sol: float) -> Dict[str, Any]:
        ...

    async def execute_sell(self, context: DemoRequestContext, percent: float) -> Dict[str, Any]:
        ...


class DemoMenuService(Protocol):
    """UI/menu service contract used by handlers."""

    def build_main_menu(self) -> Any:
        ...

    def build_token_menu(self, token_address: str) -> Any:
        ...
