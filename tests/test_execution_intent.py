"""
test_execution_intent.py — Tests for execution intent schema and validation.

Tests:
    1. OpenPosition validates leverage bounds
    2. OpenPosition validates market names
    3. OpenPosition validates size_usd bounds
    4. ClosePosition/ReducePosition are immutable (frozen)
    5. Intent types serialize correctly to dict
    6. _deserialize_intent round-trips correctly
    7. Noop intent is always valid
    8. new_idempotency_key() generates unique UUID v4 values
"""

import dataclasses
import uuid

import pytest

from core.jupiter_perps.intent import (
    CancelRequest,
    ClosePosition,
    CollateralMint,
    CreateTPSL,
    ExecutionIntent,
    IntentType,
    MAX_LEVERAGE,
    MAX_POSITION_USD,
    MIN_LEVERAGE,
    MIN_POSITION_USD,
    Noop,
    OpenPosition,
    ReducePosition,
    Side,
    new_idempotency_key,
)
from core.jupiter_perps.execution_service import _deserialize_intent


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_open_intent(**overrides) -> OpenPosition:
    defaults = dict(
        idempotency_key=new_idempotency_key(),
        market="SOL-USD",
        side=Side.LONG,
        collateral_mint=CollateralMint.USDC,
        collateral_amount_usd=100.0,
        leverage=5.0,
        size_usd=500.0,
        max_slippage_bps=50,
    )
    defaults.update(overrides)
    return OpenPosition(**defaults)


# ─── OpenPosition Validation ──────────────────────────────────────────────────

class TestOpenPositionValidation:
    def test_valid_intent_creates_successfully(self):
        intent = make_open_intent()
        assert intent.market == "SOL-USD"
        assert intent.side == Side.LONG
        assert intent.leverage == 5.0

    def test_intent_is_immutable(self):
        intent = make_open_intent()
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            intent.leverage = 99.0  # type: ignore

    def test_rejects_unsupported_market(self):
        with pytest.raises(ValueError, match="Unsupported market"):
            make_open_intent(market="DOGE-USD")

    def test_rejects_leverage_below_min(self):
        with pytest.raises(ValueError, match="Leverage"):
            make_open_intent(leverage=0.5, size_usd=50.0)

    def test_rejects_leverage_above_max(self):
        with pytest.raises(ValueError, match="Leverage"):
            make_open_intent(leverage=MAX_LEVERAGE + 1, size_usd=MAX_LEVERAGE * 100 + 100)

    def test_accepts_max_leverage(self):
        intent = make_open_intent(
            leverage=MAX_LEVERAGE,
            size_usd=MIN_POSITION_USD * MAX_LEVERAGE,
        )
        assert intent.leverage == MAX_LEVERAGE

    def test_rejects_size_below_min(self):
        with pytest.raises(ValueError, match="Size"):
            make_open_intent(leverage=1.0, size_usd=MIN_POSITION_USD - 0.01)

    def test_rejects_size_above_max(self):
        with pytest.raises(ValueError, match="Size"):
            make_open_intent(size_usd=MAX_POSITION_USD + 1)

    def test_rejects_invalid_slippage(self):
        with pytest.raises(ValueError, match="Slippage"):
            make_open_intent(max_slippage_bps=-1)

    def test_all_supported_markets(self):
        from core.jupiter_perps.intent import SUPPORTED_MARKETS
        for market in SUPPORTED_MARKETS:
            intent = make_open_intent(market=market)
            assert intent.market == market

    def test_both_sides(self):
        long_intent = make_open_intent(side=Side.LONG)
        short_intent = make_open_intent(side=Side.SHORT)
        assert long_intent.side == Side.LONG
        assert short_intent.side == Side.SHORT

    def test_intent_type_is_correct(self):
        intent = make_open_intent()
        assert intent.intent_type == IntentType.OPEN_POSITION

    def test_created_at_ns_is_set(self):
        intent = make_open_intent()
        assert intent.created_at_ns > 0

    def test_idempotency_key_preserved(self):
        key = "my-custom-key-123"
        intent = make_open_intent(idempotency_key=key)
        assert intent.idempotency_key == key


# ─── Other Intent Types ───────────────────────────────────────────────────────

class TestClosePosition:
    def test_creates_successfully(self):
        intent = ClosePosition(
            idempotency_key=new_idempotency_key(),
            position_pda="Eo4LXZxpkMZ7mACEaCvrmwcmpyAL3JUH8L8ZBvd2w4cQ",
        )
        assert intent.intent_type == IntentType.CLOSE_POSITION

    def test_is_immutable(self):
        intent = ClosePosition(
            idempotency_key="test",
            position_pda="somepda",
        )
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            intent.position_pda = "otherpda"  # type: ignore


class TestReducePosition:
    def test_rejects_zero_reduce_size(self):
        with pytest.raises(ValueError, match="reduce_size_usd must be positive"):
            ReducePosition(
                idempotency_key="test",
                position_pda="somepda",
                reduce_size_usd=0.0,
            )

    def test_rejects_negative_reduce_size(self):
        with pytest.raises(ValueError, match="reduce_size_usd must be positive"):
            ReducePosition(
                idempotency_key="test",
                position_pda="somepda",
                reduce_size_usd=-100.0,
            )


class TestCreateTPSL:
    def test_creates_stop_loss_successfully(self):
        intent = CreateTPSL(
            idempotency_key="tpsl-sl-test",
            position_pda="Eo4LXZxpkMZ7mACEaCvrmwcmpyAL3JUH8L8ZBvd2w4cQ",
            trigger_price=140.0,
            trigger_above_threshold=False,  # SL for long: trigger when price drops
        )
        assert intent.intent_type == IntentType.CREATE_TPSL
        assert intent.trigger_price == 140.0
        assert intent.trigger_above_threshold is False
        assert intent.entire_position is True

    def test_creates_take_profit_successfully(self):
        intent = CreateTPSL(
            idempotency_key="tpsl-tp-test",
            position_pda="Eo4LXZxpkMZ7mACEaCvrmwcmpyAL3JUH8L8ZBvd2w4cQ",
            trigger_price=165.0,
            trigger_above_threshold=True,  # TP for long: trigger when price rises
        )
        assert intent.trigger_above_threshold is True

    def test_is_immutable(self):
        intent = CreateTPSL(
            idempotency_key="test",
            position_pda="somepda",
            trigger_price=100.0,
            trigger_above_threshold=True,
        )
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            intent.trigger_price = 200.0  # type: ignore

    def test_rejects_zero_trigger_price(self):
        with pytest.raises(ValueError, match="trigger_price must be positive"):
            CreateTPSL(
                idempotency_key="test",
                position_pda="somepda",
                trigger_price=0.0,
                trigger_above_threshold=True,
            )

    def test_rejects_negative_trigger_price(self):
        with pytest.raises(ValueError, match="trigger_price must be positive"):
            CreateTPSL(
                idempotency_key="test",
                position_pda="somepda",
                trigger_price=-50.0,
                trigger_above_threshold=False,
            )

    def test_partial_close_requires_size_usd(self):
        with pytest.raises(ValueError, match="size_usd must be positive"):
            CreateTPSL(
                idempotency_key="test",
                position_pda="somepda",
                trigger_price=100.0,
                trigger_above_threshold=True,
                entire_position=False,
                size_usd=0.0,
            )

    def test_partial_close_with_valid_size(self):
        intent = CreateTPSL(
            idempotency_key="test",
            position_pda="somepda",
            trigger_price=100.0,
            trigger_above_threshold=True,
            entire_position=False,
            size_usd=250.0,
        )
        assert intent.entire_position is False
        assert intent.size_usd == 250.0

    def test_in_execution_intent_union(self):
        """CreateTPSL should be included in the ExecutionIntent union type."""
        intent = CreateTPSL(
            idempotency_key="test",
            position_pda="somepda",
            trigger_price=100.0,
            trigger_above_threshold=True,
        )
        assert isinstance(intent, CreateTPSL)
        # Verify it matches the union
        from typing import get_args
        union_types = get_args(ExecutionIntent)
        assert CreateTPSL in union_types


class TestNoop:
    def test_creates_with_auto_key(self):
        noop = Noop()
        assert noop.intent_type == IntentType.NOOP
        assert len(noop.idempotency_key) > 0

    def test_creates_with_custom_key(self):
        noop = Noop(idempotency_key="heartbeat-001")
        assert noop.idempotency_key == "heartbeat-001"


# ─── Idempotency Key ──────────────────────────────────────────────────────────

class TestIdempotencyKey:
    def test_generates_valid_uuid_v4(self):
        key = new_idempotency_key()
        parsed = uuid.UUID(key)
        assert parsed.version == 4

    def test_generates_unique_keys(self):
        keys = {new_idempotency_key() for _ in range(100)}
        assert len(keys) == 100


# ─── Serialization Round-Trip ─────────────────────────────────────────────────

class TestDeserialization:
    def test_open_position_round_trip(self):
        original = make_open_intent()
        raw = {
            "intent_type": "open_position",
            "idempotency_key": original.idempotency_key,
            "market": original.market,
            "side": original.side.value,
            "collateral_mint": original.collateral_mint.value,
            "collateral_amount_usd": original.collateral_amount_usd,
            "leverage": original.leverage,
            "size_usd": original.size_usd,
            "max_slippage_bps": original.max_slippage_bps,
        }
        deserialized = _deserialize_intent("open_position", raw)
        assert isinstance(deserialized, OpenPosition)
        assert deserialized.idempotency_key == original.idempotency_key
        assert deserialized.market == original.market
        assert deserialized.leverage == original.leverage

    def test_close_position_round_trip(self):
        raw = {
            "intent_type": "close_position",
            "idempotency_key": "test-close",
            "position_pda": "somepda123",
        }
        intent = _deserialize_intent("close_position", raw)
        assert isinstance(intent, ClosePosition)
        assert intent.position_pda == "somepda123"

    def test_create_tpsl_round_trip(self):
        raw = {
            "intent_type": "create_tpsl",
            "idempotency_key": "tpsl-test-1",
            "position_pda": "somepda123",
            "trigger_price": 140.0,
            "trigger_above_threshold": False,
            "entire_position": True,
        }
        intent = _deserialize_intent("create_tpsl", raw)
        assert isinstance(intent, CreateTPSL)
        assert intent.trigger_price == 140.0
        assert intent.trigger_above_threshold is False
        assert intent.entire_position is True

    def test_noop_round_trip(self):
        raw = {"intent_type": "noop", "idempotency_key": "heartbeat-001"}
        intent = _deserialize_intent("noop", raw)
        assert isinstance(intent, Noop)

    def test_unknown_intent_type_raises(self):
        with pytest.raises(ValueError, match="Unknown intent_type"):
            _deserialize_intent("hack_the_planet", {"idempotency_key": "test"})

    def test_dataclass_serializes_to_dict(self):
        intent = make_open_intent()
        d = dataclasses.asdict(intent)
        assert d["intent_type"] == IntentType.OPEN_POSITION
        assert d["market"] == "SOL-USD"
        assert d["leverage"] == 5.0

    def test_legacy_open_position_payload_is_normalized(self):
        raw = {
            "type": "OpenPosition",
            "idempotency_key": "legacy-open-1",
            "market": "SOL-USD",
            "side": "long",
            "collateral_usd": 125.0,
            "leverage": 4.0,
        }
        intent = _deserialize_intent("", raw)
        assert isinstance(intent, OpenPosition)
        assert intent.collateral_amount_usd == 125.0
        assert intent.size_usd == 500.0
        assert intent.collateral_mint == CollateralMint.USDC

    def test_legacy_close_position_payload_is_normalized(self):
        raw = {
            "type": "ClosePosition",
            "idempotency_key": "legacy-close-1",
            "position_pda": "pda-123",
        }
        intent = _deserialize_intent("", raw)
        assert isinstance(intent, ClosePosition)
        assert intent.position_pda == "pda-123"
