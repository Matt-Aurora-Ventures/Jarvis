from datetime import datetime, timezone
import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, patch
import sys

import pytest

from core.data.solscan_api import HolderInfo, TransactionInfo


# Local test env may not have python-telegram-bot installed.
if "telegram" not in sys.modules:
    telegram_mod = ModuleType("telegram")
    telegram_constants_mod = ModuleType("telegram.constants")
    telegram_error_mod = ModuleType("telegram.error")
    telegram_ext_mod = ModuleType("telegram.ext")
    telegram_constants_mod.ParseMode = SimpleNamespace(MARKDOWN="MARKDOWN", HTML="HTML")
    telegram_mod.InputMediaPhoto = type("InputMediaPhoto", (), {})
    telegram_ext_mod.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)

    class _RetryAfter(Exception):
        retry_after = 0

    class _BadRequest(Exception):
        pass

    telegram_error_mod.RetryAfter = _RetryAfter
    telegram_error_mod.BadRequest = _BadRequest
    sys.modules["telegram"] = telegram_mod
    sys.modules["telegram.constants"] = telegram_constants_mod
    sys.modules["telegram.error"] = telegram_error_mod
    sys.modules["telegram.ext"] = telegram_ext_mod

_MODULE_PATH = Path(__file__).resolve().parents[2] / "tg_bot" / "handlers" / "analyze_drill_down.py"
_SPEC = importlib.util.spec_from_file_location("analyze_drill_down_test", _MODULE_PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_MOD)
fetch_holder_data = _MOD.fetch_holder_data
fetch_recent_trades = _MOD.fetch_recent_trades


@pytest.mark.asyncio
async def test_fetch_holder_data_uses_solscan_holders():
    api = SimpleNamespace(
        get_token_holders=AsyncMock(
            return_value=[
                HolderInfo(
                    owner="wallet-1",
                    amount=2_500_000_000,
                    rank=1,
                    percentage=12.5,
                    decimals=6,
                ),
                HolderInfo(
                    owner="wallet-2",
                    amount=900_000_000,
                    rank=2,
                    percentage=4.5,
                    decimals=6,
                ),
            ]
        )
    )

    with patch("core.data.solscan_api.get_solscan_api", return_value=api):
        holders = await fetch_holder_data("So11111111111111111111111111111111111111112")

    assert holders == [
        {"address": "wallet-1", "percentage": 12.5, "amount": 2500},
        {"address": "wallet-2", "percentage": 4.5, "amount": 900},
    ]


@pytest.mark.asyncio
async def test_fetch_holder_data_returns_empty_when_solscan_unavailable():
    api = SimpleNamespace(get_token_holders=AsyncMock(return_value=[]))

    with patch("core.data.solscan_api.get_solscan_api", return_value=api):
        holders = await fetch_holder_data("bad-token")

    assert holders == []


@pytest.mark.asyncio
async def test_fetch_recent_trades_uses_solscan_transactions():
    now = int(datetime.now(timezone.utc).timestamp())
    api = SimpleNamespace(
        get_recent_transactions=AsyncMock(
            return_value=[
                TransactionInfo(
                    signature="sig-1",
                    block_time=now - 120,
                    amount=80_000,
                    tx_type="buy",
                    success=True,
                ),
                TransactionInfo(
                    signature="sig-2",
                    block_time=now - 900,
                    amount=2_500,
                    tx_type="sell",
                    success=True,
                ),
            ]
        )
    )

    with patch("core.data.solscan_api.get_solscan_api", return_value=api):
        trades = await fetch_recent_trades("So11111111111111111111111111111111111111112", limit=2)

    assert len(trades) == 2
    assert trades[0]["type"] == "buy"
    assert trades[0]["amount_usd"] == 80000
    assert trades[0]["is_whale"] is True
    assert trades[0]["time"].endswith("ago")
    assert trades[1]["type"] == "sell"
    assert trades[1]["amount_usd"] == 2500
    assert trades[1]["is_whale"] is False
