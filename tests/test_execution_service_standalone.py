from __future__ import annotations

import pytest

from core.jupiter_perps.execution_service import ExecutionService
from core.jupiter_perps.intent import Noop


class _DummyJournal:
    async def close(self) -> None:
        return


@pytest.mark.asyncio
async def test_execution_service_dry_run_startup_and_noop() -> None:
    service = ExecutionService(_DummyJournal(), live_mode=False, wallet_address="", rpc_url="")
    await service.startup()

    result = await service.execute(Noop(idempotency_key="noop-test"))
    assert result.success is True
    assert result.intent_type == "noop"
    assert result.skipped_duplicate is False

    await service.shutdown()
