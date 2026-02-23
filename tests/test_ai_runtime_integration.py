import os

import pytest

from core.ai_runtime.integration import AIRuntimeManager


@pytest.mark.asyncio
async def test_start_sets_arena_env_when_enabled(monkeypatch):
    class _Config:
        enabled = False

    monkeypatch.setattr("core.ai_runtime.integration.AIRuntimeConfig.from_env", lambda: _Config())
    monkeypatch.delenv("JARVIS_USE_ARENA", raising=False)

    manager = AIRuntimeManager()
    started = await manager.start(use_arena=True)

    assert started is False
    assert os.environ["JARVIS_USE_ARENA"] == "1"


@pytest.mark.asyncio
async def test_start_sets_arena_env_default_when_disabled(monkeypatch):
    class _Config:
        enabled = False

    monkeypatch.setattr("core.ai_runtime.integration.AIRuntimeConfig.from_env", lambda: _Config())
    monkeypatch.delenv("JARVIS_USE_ARENA", raising=False)

    manager = AIRuntimeManager()
    started = await manager.start(use_arena=False)

    assert started is False
    assert os.environ["JARVIS_USE_ARENA"] == "0"
