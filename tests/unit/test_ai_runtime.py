"""Tests for AI runtime optional behavior."""

import pytest
from unittest.mock import patch, AsyncMock

from core.ai_runtime.supervisor import AISupervisor
from core.ai_runtime.config import AIRuntimeConfig
from core.ai_runtime.ollama_client import OllamaResponse


@pytest.mark.asyncio
async def test_ai_runtime_offline_fail_open():
    cfg = AIRuntimeConfig(
        enabled=True,
        interval_seconds=1,
        timeout_seconds=1,
        model="qwen3-coder",
        max_tokens=64,
        base_url="http://127.0.0.1:1",
    )
    supervisor = AISupervisor(cfg)

    sample_errors = [
        {
            "id": "abc123",
            "component": "telegram_bot",
            "message": "Sample error",
            "count": 3,
            "last_seen": "2026-01-01T00:00:00Z",
        }
    ]

    with patch("core.ai_runtime.agents.error_tracker.get_frequent_errors", return_value=sample_errors):
        with patch(
            "core.ai_runtime.ollama_client.OllamaClient.chat",
            new=AsyncMock(return_value=OllamaResponse(success=False, error="offline")),
        ):
            reports = await supervisor.run_once()

    assert isinstance(reports, list)
    assert len(reports) == 1
    report = reports[0]
    assert report.agent == "telegram_agent"
    assert report.error_count == 1
