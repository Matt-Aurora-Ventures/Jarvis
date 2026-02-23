"""Stateless, idempotent Jupiter Perps execution service."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
from dataclasses import dataclass
from typing import Any

from core.jupiter_perps.event_journal import EventJournal
from core.jupiter_perps.intent import (
    CancelRequest,
    ClosePosition,
    CollateralMint,
    CreateTPSL,
    ExecutionIntent,
    IntentType,
    Noop,
    OpenPosition,
    ReducePosition,
    Side,
    new_idempotency_key,
)
from core.jupiter_perps.live_control import LiveControlConfig, LiveControlState

log = logging.getLogger(__name__)

_ALLOWED_INTENT_TYPES: tuple[type[Any], ...] = (
    OpenPosition,
    ReducePosition,
    ClosePosition,
    CreateTPSL,
    CancelRequest,
    Noop,
)

_ACTION_ALIASES: dict[str, str] = {
    "OpenPosition": IntentType.OPEN_POSITION.value,
    "open_position": IntentType.OPEN_POSITION.value,
    "ReducePosition": IntentType.REDUCE_POSITION.value,
    "reduce_position": IntentType.REDUCE_POSITION.value,
    "ClosePosition": IntentType.CLOSE_POSITION.value,
    "close_position": IntentType.CLOSE_POSITION.value,
    "CancelRequest": IntentType.CANCEL_REQUEST.value,
    "cancel_request": IntentType.CANCEL_REQUEST.value,
    "CreateTPSL": IntentType.CREATE_TPSL.value,
    "create_tpsl": IntentType.CREATE_TPSL.value,
    "Noop": IntentType.NOOP.value,
    "noop": IntentType.NOOP.value,
}

_MAX_POSITION_SIZE_USD = float(os.environ.get("PERPS_MAX_POSITION_USD", "10000"))
_MAX_LEVERAGE = float(os.environ.get("PERPS_MAX_LEVERAGE", "20.0"))
_KILL_SWITCH = os.environ.get("LIFEOS_KILL_SWITCH", "false").lower() == "true"


@dataclass(frozen=True)
class ExecutionResult:
    idempotency_key: str
    intent_type: str
    success: bool
    tx_signature: str | None = None
    slot: int | None = None
    block_time: int | None = None
    error: str | None = None
    skipped_duplicate: bool = False
    dry_run: bool = False


def _risk_gate(intent: ExecutionIntent) -> tuple[bool, str]:
    """Pure deterministic risk gate."""
    if _KILL_SWITCH:
        return False, "LIFEOS_KILL_SWITCH is active"

    if isinstance(intent, OpenPosition):
        if intent.size_usd > _MAX_POSITION_SIZE_USD:
            return False, f"size_usd ${intent.size_usd:.2f} exceeds max ${_MAX_POSITION_SIZE_USD:.2f}"
        if intent.leverage > _MAX_LEVERAGE:
            return False, f"leverage {intent.leverage}x exceeds max {_MAX_LEVERAGE}x"

    return True, "ok"


class ExecutionService:
    """Execution signer service with deterministic behavior."""

    def __init__(
        self,
        journal: EventJournal,
        *,
        live_mode: bool | None = None,
        wallet_address: str | None = None,
        rpc_url: str | None = None,
        control_state_path: str = "",
    ) -> None:
        self._journal = journal
        self._wallet: Any = None
        self._ready = False
        self._live_mode = live_mode if live_mode is not None else os.environ.get("PERPS_LIVE_MODE", "false").lower() == "true"
        self._wallet_address = wallet_address or os.environ.get("PERPS_WALLET_ADDRESS", "")
        self._rpc_url = rpc_url or os.environ.get("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com")
        self._control_state_path = control_state_path
        self._live_control: LiveControlState | None = None

    async def startup(self) -> None:
        """Load wallet dependencies and validate live readiness."""
        if not self._live_mode:
            self._wallet = None
            self._live_control = None
            self._ready = True
            log.info("ExecutionService ready mode=DRY_RUN")
            return

        from core.jupiter_perps.client import perps_client  # noqa: PLC0415
        from core.jupiter_perps.signer import load_signer_keypair  # noqa: PLC0415

        perps_client.assert_live_ready()
        if not self._wallet_address:
            raise RuntimeError("PERPS_WALLET_ADDRESS is required in live mode")
        self._wallet = load_signer_keypair(self._wallet_address)
        self._live_control = LiveControlState(LiveControlConfig.from_env(self._control_state_path))

        self._ready = True
        log.info("ExecutionService ready mode=%s", "LIVE" if self._live_mode else "DRY_RUN")

    async def execute(self, intent: ExecutionIntent) -> ExecutionResult:
        """
        Process one intent with strict ordering:
        risk gate pass -> journal write -> submit/simulate path.
        """
        if not self._ready:
            raise RuntimeError("ExecutionService.startup() has not completed")

        if not isinstance(intent, _ALLOWED_INTENT_TYPES):
            raise ValueError(f"Unsupported execution intent class: {type(intent).__name__}")

        key = intent.idempotency_key
        intent_type = intent.intent_type.value

        if isinstance(intent, Noop):
            return ExecutionResult(idempotency_key=key, intent_type=intent_type, success=True)

        allowed, reason = _risk_gate(intent)
        if not allowed:
            await self._journal.log_rejected(intent, f"risk_gate: {reason}")
            return ExecutionResult(
                idempotency_key=key,
                intent_type=intent_type,
                success=False,
                error=f"risk_gate: {reason}",
            )

        if self._live_mode and isinstance(intent, OpenPosition):
            if self._live_control is None:
                await self._journal.log_rejected(intent, "live_control_unavailable")
                return ExecutionResult(
                    idempotency_key=key,
                    intent_type=intent_type,
                    success=False,
                    error="live_control_unavailable",
                )
            live_allowed, live_reason = self._live_control.can_open_position()
            if not live_allowed:
                await self._journal.log_rejected(intent, f"live_control: {live_reason}")
                return ExecutionResult(
                    idempotency_key=key,
                    intent_type=intent_type,
                    success=False,
                    error=f"live_control: {live_reason}",
                )

        inserted = await self._journal.log_intent(intent)
        if not inserted:
            await self._journal.mark_skipped(key)
            return ExecutionResult(
                idempotency_key=key,
                intent_type=intent_type,
                success=True,
                skipped_duplicate=True,
            )

        if not self._live_mode:
            await self._journal.mark_simulated(key, note="dry_run_deterministic")
            return ExecutionResult(
                idempotency_key=key,
                intent_type=intent_type,
                success=True,
                dry_run=True,
            )

        try:
            return await self._submit_and_confirm(intent)
        except Exception as exc:
            err = str(exc)[:500]
            log.exception("Execution failed key=%s error=%s", key, err)
            await self._journal.mark_failed(key, err)
            return ExecutionResult(
                idempotency_key=key,
                intent_type=intent_type,
                success=False,
                error=err,
            )

    async def _submit_and_confirm(self, intent: ExecutionIntent) -> ExecutionResult:
        key = intent.idempotency_key
        intent_type = intent.intent_type.value

        tx_bytes = await self._build_transaction(intent)
        if self._wallet is None:
            raise RuntimeError("Wallet not available in live mode")
        if not self._wallet_address:
            raise RuntimeError("PERPS_WALLET_ADDRESS is required in live mode")

        from solders.transaction import VersionedTransaction  # noqa: PLC0415
        from core.jupiter_perps.rpc_submit import send_and_confirm_transaction  # noqa: PLC0415

        unsigned_tx = VersionedTransaction.from_bytes(bytes(tx_bytes))
        signed_tx = VersionedTransaction(unsigned_tx.message, [self._wallet])
        submit_result = await send_and_confirm_transaction(signed_tx, self._rpc_url)
        signature = submit_result.signature

        await self._journal.mark_submitted(key, signature)
        slot = int(submit_result.slot or 0)
        block_time = int(submit_result.block_time or 0)
        await self._journal.mark_confirmed(key, slot=slot, block_time=block_time)

        if isinstance(intent, OpenPosition) and self._live_control is not None:
            self._live_control.record_open_position()

        return ExecutionResult(
            idempotency_key=key,
            intent_type=intent_type,
            success=True,
            tx_signature=signature,
            slot=slot,
            block_time=block_time,
        )

    async def _build_transaction(self, intent: ExecutionIntent) -> bytes:
        from core.jupiter_perps.client import perps_client  # noqa: PLC0415

        perps_client.assert_live_ready()
        return await perps_client.build_transaction(
            intent,
            wallet_address=self._wallet_address,
            rpc_url=self._rpc_url,
        )

    async def shutdown(self) -> None:
        self._ready = False
        await self._journal.close()


def _resolve_action(data: dict[str, Any], fallback_intent_type: str = "") -> str:
    raw = data.get("action") or data.get("intent_type") or data.get("type") or fallback_intent_type
    if not isinstance(raw, str):
        raise ValueError("Intent payload must include 'action' or 'intent_type' string")

    action = _ACTION_ALIASES.get(raw)
    if action is None:
        raise ValueError(f"Unknown intent_type: {raw}")
    return action


def normalize_external_intent_payload(data: dict[str, Any], fallback_intent_type: str = "") -> dict[str, Any]:
    """Normalize legacy external payloads to canonical execution intent shape."""
    normalized = dict(data)
    action = _resolve_action(normalized, fallback_intent_type=fallback_intent_type)
    normalized["intent_type"] = action
    normalized.setdefault("idempotency_key", new_idempotency_key())

    if action == IntentType.OPEN_POSITION.value:
        if "collateral_amount_usd" not in normalized and "collateral_usd" in normalized:
            normalized["collateral_amount_usd"] = normalized["collateral_usd"]
        if "max_slippage_bps" not in normalized and "slippage_bps" in normalized:
            normalized["max_slippage_bps"] = normalized["slippage_bps"]

        normalized.setdefault("collateral_mint", CollateralMint.USDC.value)
        if "size_usd" not in normalized:
            collateral = float(normalized.get("collateral_amount_usd", 0.0) or 0.0)
            leverage = float(normalized.get("leverage", 0.0) or 0.0)
            normalized["size_usd"] = collateral * leverage

        if isinstance(normalized.get("market"), str):
            normalized["market"] = normalized["market"].upper()
        if isinstance(normalized.get("side"), str):
            normalized["side"] = normalized["side"].lower()

    if action == IntentType.CLOSE_POSITION.value:
        if "position_pda" not in normalized:
            if "original_position_pda" in normalized:
                normalized["position_pda"] = normalized["original_position_pda"]
            elif "original_idempotency_key" in normalized:
                # Legacy compatibility fallback: callers should send position_pda.
                normalized["position_pda"] = normalized["original_idempotency_key"]
        if "max_slippage_bps" not in normalized and "slippage_bps" in normalized:
            normalized["max_slippage_bps"] = normalized["slippage_bps"]

    return normalized


def _deserialize_intent(intent_type: str, data: dict[str, Any]) -> ExecutionIntent:
    """Deserialize JSON payload into exactly one allowed intent type."""
    normalized = normalize_external_intent_payload(data, fallback_intent_type=intent_type)
    action = _resolve_action(normalized, fallback_intent_type=intent_type)

    if action == IntentType.OPEN_POSITION.value:
        return OpenPosition(
            idempotency_key=normalized["idempotency_key"],
            market=normalized["market"],
            side=Side(normalized["side"]),
            collateral_mint=CollateralMint(normalized["collateral_mint"]),
            collateral_amount_usd=float(normalized["collateral_amount_usd"]),
            leverage=float(normalized["leverage"]),
            size_usd=float(normalized["size_usd"]),
            max_slippage_bps=int(normalized.get("max_slippage_bps", 50)),
        )

    if action == IntentType.REDUCE_POSITION.value:
        return ReducePosition(
            idempotency_key=normalized["idempotency_key"],
            position_pda=normalized["position_pda"],
            reduce_size_usd=float(normalized["reduce_size_usd"]),
            max_slippage_bps=int(normalized.get("max_slippage_bps", 100)),
        )

    if action == IntentType.CLOSE_POSITION.value:
        return ClosePosition(
            idempotency_key=normalized["idempotency_key"],
            position_pda=normalized["position_pda"],
            max_slippage_bps=int(normalized.get("max_slippage_bps", 100)),
        )

    if action == IntentType.CREATE_TPSL.value:
        return CreateTPSL(
            idempotency_key=normalized["idempotency_key"],
            position_pda=normalized["position_pda"],
            trigger_price=float(normalized["trigger_price"]),
            trigger_above_threshold=bool(normalized["trigger_above_threshold"]),
            entire_position=bool(normalized.get("entire_position", True)),
            size_usd=float(normalized.get("size_usd", 0.0)),
        )

    if action == IntentType.CANCEL_REQUEST.value:
        return CancelRequest(
            idempotency_key=normalized["idempotency_key"],
            request_pda=normalized["request_pda"],
        )

    if action == IntentType.NOOP.value:
        return Noop(idempotency_key=normalized.get("idempotency_key", new_idempotency_key()))

    raise ValueError(f"Unknown action: {action}")


async def run_execution_service() -> None:
    """Standalone stdin runner for signer host process testing."""
    import json
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    from core.jupiter_perps.integrity import verify_idl  # noqa: PLC0415

    verify_idl(fatal=True)

    dsn = os.environ.get("PERPS_DB_DSN", "")
    journal = EventJournal(dsn)
    await journal.connect()

    service = ExecutionService(journal)
    await service.startup()

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                intent = _deserialize_intent("", raw)
                result = await service.execute(intent)
                print(json.dumps(dataclasses.asdict(result), sort_keys=True), flush=True)
            except Exception as exc:  # noqa: BLE001
                log.exception("Failed to process intent")
                print(json.dumps({"error": str(exc)}), flush=True)
    finally:
        await service.shutdown()


if __name__ == "__main__":
    asyncio.run(run_execution_service())
