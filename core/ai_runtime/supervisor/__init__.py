"""
AI Supervisor Module

Central coordinator for all AI agents.
"""

from __future__ import annotations

import asyncio
import logging
from typing import List

from core.ai_runtime.agents import AgentReport, build_default_agents
from core.ai_runtime.config import AIRuntimeConfig, get_ai_runtime_config
from core.ai_runtime.ollama_client import OllamaClient

from .ai_supervisor import AISupervisor as ActionSupervisor, PendingAction, SupervisorState
from .correlator import InsightCorrelator

logger = logging.getLogger("jarvis.ai_runtime.supervisor")


class AISupervisor:
    """Lightweight supervisor used by tests and simple runtime loops."""

    def __init__(self, config: AIRuntimeConfig | None = None):
        self.config = config or get_ai_runtime_config()
        self.agents = build_default_agents()
        self._running = False
        self._client = None
        if self.config.enabled:
            self._client = OllamaClient(
                base_url=self.config.base_url,
                model=self.config.model,
                timeout_seconds=self.config.timeout_seconds,
            )

    async def run_once(self) -> List[AgentReport]:
        reports: List[AgentReport] = []
        if not self.config.enabled:
            return reports

        for agent in self.agents:
            try:
                report = await agent.run(self._client)
                if report:
                    reports.append(report)
            except Exception as exc:
                logger.debug("Agent %s failed: %s", agent.name, exc)
        return reports

    async def start(self) -> None:
        self._running = True
        if not self.config.enabled:
            logger.info("AI runtime disabled; supervisor idle")
        else:
            logger.info(
                "AI runtime enabled (model=%s base_url=%s interval=%ss)",
                self.config.model,
                self.config.base_url,
                self.config.interval_seconds,
            )

        while self._running:
            try:
                await self.run_once()
            except Exception as exc:
                logger.debug("AI supervisor loop error: %s", exc)
            await asyncio.sleep(max(5, self.config.interval_seconds))

    async def stop(self) -> None:
        self._running = False


__all__ = [
    "AISupervisor",
    "ActionSupervisor",
    "PendingAction",
    "SupervisorState",
    "InsightCorrelator",
]
