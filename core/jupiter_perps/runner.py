"""Canonical Jupiter Perps runtime entrypoint."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import signal
import time
import tempfile
from importlib import metadata
from pathlib import Path
from typing import Any

from core.jupiter_perps.ai_signal_bridge import ai_signal_loop, exit_decision_to_intent
from core.jupiter_perps.cost_gate import CostGate, CostGateConfig
from core.jupiter_perps.event_journal import EventJournal
from core.jupiter_perps.execution_service import ExecutionService, _deserialize_intent
from core.jupiter_perps.integrity import verify_idl
from core.jupiter_perps.intent import (
    ClosePosition,
    CreateTPSL,
    ExecutionIntent,
    Noop,
    OpenPosition,
    new_idempotency_key,
)
from core.jupiter_perps.live_control import LiveControlConfig, LiveControlState
from core.jupiter_perps.position_manager import PositionManager, PositionManagerConfig
from core.jupiter_perps.price_feed import OraclePriceFeed, OraclePriceFeedConfig
from core.jupiter_perps.reconciliation import discover_existing_tpsl, reconciliation_loop
from core.jupiter_perps.self_adjuster import PerpsAutoTuner, TradeOutcome, TunerConfig
from core.utils.instance_lock import acquire_instance_lock

log = logging.getLogger(__name__)


def _json_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": int(time.time()),
        **fields,
    }
    log.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _default_lock_file() -> str:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return str(base / "Jarvis" / "ralph_wiggum" / "runner.lock")
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return str(base / "jarvis" / "ralph_wiggum" / "runner.lock")


def _default_runtime_dir() -> Path:
    configured = os.environ.get("JARVIS_RALPH_RUNTIME_DIR", "").strip()
    if configured:
        return Path(configured)
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or ".")
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return base / "Jarvis" / "vanguard-standalone"


def _default_intent_queue_path() -> str:
    return str(_default_runtime_dir() / "intent_queue.jsonl")


def _default_intent_cursor_path(queue_path: str) -> str:
    return f"{queue_path}.cursor"


def _verify_idl_with_optional_override(idl_path: str, expected_hash: str) -> None:
    if not idl_path and not expected_hash:
        verify_idl(fatal=True)
        return

    if not idl_path or not expected_hash:
        raise RuntimeError("Both --idl-path and --expected-idl-hash must be provided together")

    target = Path(idl_path)
    if not target.exists():
        raise FileNotFoundError(f"IDL path does not exist: {target}")

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if digest.lower() != expected_hash.lower():
        raise RuntimeError(
            f"IDL hash mismatch expected={expected_hash.lower()} actual={digest.lower()} path={target}"
        )


def _check_version(package: str, expected: str) -> str:
    installed = metadata.version(package)
    if expected and installed != expected:
        raise RuntimeError(f"{package} version mismatch expected={expected} installed={installed}")
    return installed


def verify_runtime_versions(anchorpy_version: str, solders_version: str, solana_version: str) -> dict[str, str]:
    versions = {
        "anchorpy": _check_version("anchorpy", anchorpy_version),
        "solders": _check_version("solders", solders_version),
        "solana": _check_version("solana", solana_version),
    }
    return versions


def _find_and_close_position(
    pm: PositionManager,
    close_key: str,
    position_pda: str,
) -> Any:
    """Find a tracked position matching a ClosePosition intent and mark it closed.

    Close intent keys are formatted as "exit-{original_key}-{uuid}".
    We try: (1) match by PDA, (2) extract original key from close_key.
    """
    # Try matching by PDA
    for pos in pm.get_open_positions():
        if pos.pda == position_pda:
            return pm.mark_closed(pos.idempotency_key)

    # Try extracting original key from "exit-{orig_key}-{uuid}"
    if close_key.startswith("exit-"):
        # "exit-ai-grok_perps-SOL-uuid1-uuid2" -> try progressively shorter segments
        parts = close_key.split("-")
        # Try from the longest possible original key down
        for end in range(len(parts) - 1, 1, -1):
            candidate = "-".join(parts[1:end])
            closed = pm.mark_closed(candidate)
            if closed is not None:
                return closed

    return None


def _load_cursor(path: Path) -> int:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _save_cursor(path: Path, cursor: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(max(0, cursor)), encoding="utf-8")


def _read_external_intents(queue_path: Path, cursor: int) -> tuple[list[ExecutionIntent], int, list[str]]:
    """Read and deserialize intents from queue_path starting from a byte cursor."""
    if not queue_path.exists():
        return [], 0, []

    try:
        file_size = queue_path.stat().st_size
    except OSError:
        return [], 0, []

    current_cursor = max(0, cursor)
    if current_cursor > file_size:
        current_cursor = 0

    intents: list[ExecutionIntent] = []
    rejections: list[str] = []

    try:
        with queue_path.open("r", encoding="utf-8") as handle:
            handle.seek(current_cursor)
            while True:
                line = handle.readline()
                if not line:
                    break
                current_cursor = handle.tell()
                payload_text = line.strip()
                if not payload_text:
                    continue

                try:
                    payload = json.loads(payload_text)
                except Exception as exc:  # noqa: BLE001
                    rejections.append(f"invalid_json:{exc}")
                    continue

                try:
                    intents.append(_deserialize_intent("", payload))
                except Exception as exc:  # noqa: BLE001
                    rejections.append(f"invalid_payload:{exc}")
    except Exception as exc:  # noqa: BLE001
        rejections.append(f"queue_read_failed:{exc}")

    return intents, current_cursor, rejections


async def _intent_consumer(
    queue: asyncio.Queue[ExecutionIntent],
    service: ExecutionService,
    stop_event: asyncio.Event,
    position_manager: PositionManager | None = None,
    tuner: PerpsAutoTuner | None = None,
    journal: EventJournal | None = None,
    live_control: LiveControlState | None = None,
) -> None:
    while not stop_event.is_set():
        try:
            intent = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        result = await service.execute(intent)
        _json_event(
            "intent_processed",
            intent_type=result.intent_type,
            idempotency_key=result.idempotency_key,
            success=result.success,
            skipped_duplicate=result.skipped_duplicate,
            dry_run=result.dry_run,
            tx_signature=result.tx_signature,
            error=result.error,
        )

        # --- Position manager feedback loop ---
        if position_manager is not None and result.success:
            if isinstance(intent, OpenPosition):
                # Register newly opened position for exit tracking
                source = "unknown"
                parts = intent.idempotency_key.split("-")
                if len(parts) >= 2:
                    source = parts[1]  # e.g. "grok_perps" from "ai-grok_perps-SOL-uuid"
                position_manager.register_open(
                    idempotency_key=intent.idempotency_key,
                    market=intent.market,
                    side=intent.side.value,
                    size_usd=intent.size_usd,
                    collateral_usd=intent.collateral_amount_usd,
                    leverage=intent.leverage,
                    entry_price=0.0,  # filled by position monitor on next price tick
                    source=source,
                )
            elif isinstance(intent, ClosePosition):
                # Close intents from position monitor have key "exit-{orig_key}-{uuid}"
                # Find the tracked position by matching the PDA or extracting the original key
                closed_pos = _find_and_close_position(
                    position_manager, intent.idempotency_key, intent.position_pda,
                )
                if closed_pos is not None and tuner is not None:
                    outcome = TradeOutcome(
                        source=closed_pos.source,
                        asset=closed_pos.market.split("-")[0],
                        direction=closed_pos.side,
                        confidence_at_entry=0.0,
                        entry_price=closed_pos.entry_price,
                        exit_price=closed_pos.current_price,
                        pnl_usd=closed_pos.unrealized_pnl_usd,
                        pnl_pct=closed_pos.unrealized_pnl_pct,
                        hold_hours=closed_pos.hold_hours,
                        fees_usd=closed_pos.cumulative_borrow_usd,
                        exit_trigger="close",
                        regime="ranging",
                    )
                    tuner.record_outcome(outcome)
                    if journal is not None and journal.has_local:
                        await tuner.save_outcome_to_sqlite(outcome, journal._sqlite)
                    if live_control is not None:
                        live_control.record_realized_pnl(outcome.pnl_usd)

        queue.task_done()


async def _external_intent_loop(
    queue: asyncio.Queue[ExecutionIntent],
    stop_event: asyncio.Event,
    intent_queue_path: str,
    intent_cursor_path: str,
    poll_interval_seconds: float = 0.5,
) -> None:
    queue_path = Path(intent_queue_path)
    cursor_path = Path(intent_cursor_path)
    cursor = _load_cursor(cursor_path)

    while not stop_event.is_set():
        intents, next_cursor, rejections = _read_external_intents(queue_path, cursor)

        for rejection in rejections:
            _json_event(
                "external_intent_rejected",
                reason=rejection,
                queue_path=str(queue_path),
            )

        for intent in intents:
            await queue.put(intent)
            _json_event(
                "intent_received",
                source="external_queue",
                action=intent.intent_type.value,
                idempotency_key=intent.idempotency_key,
                queue_depth=queue.qsize(),
            )

        if next_cursor != cursor:
            _save_cursor(cursor_path, next_cursor)
            cursor = next_cursor

        await asyncio.sleep(poll_interval_seconds)


async def _micro_loop(queue: asyncio.Queue[ExecutionIntent], stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        intent = Noop(idempotency_key=f"micro-{new_idempotency_key()}")
        try:
            queue.put_nowait(intent)
            _json_event("intent_received", source="micro", action="Noop", queue_depth=queue.qsize())
        except asyncio.QueueFull:
            _json_event("queue_backpressure", source="micro", dropped_action="Noop", queue_depth=queue.qsize())
        await asyncio.sleep(2.0)


async def _macro_loop(queue: asyncio.Queue[ExecutionIntent], stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        intent = Noop(idempotency_key=f"macro-{new_idempotency_key()}")
        try:
            queue.put_nowait(intent)
            _json_event("intent_received", source="macro", action="Noop", queue_depth=queue.qsize())
        except asyncio.QueueFull:
            _json_event("queue_backpressure", source="macro", dropped_action="Noop", queue_depth=queue.qsize())
        await asyncio.sleep(30.0)


async def _position_monitor_loop(
    queue: asyncio.Queue[ExecutionIntent],
    position_manager: PositionManager,
    stop_event: asyncio.Event,
    price_interval: float = 2.0,
    borrow_interval: float = 60.0,
) -> None:
    """Monitor open positions: fetch prices, check exit triggers, queue close intents.

    Also creates on-chain TP/SL trigger orders (via CreateTPSL intents) for positions
    that have received their entry price but don't have on-chain orders yet.

    On first run, discovers existing on-chain Trigger requests to avoid duplicate
    TP/SL submissions after a restart (idempotency across process boundaries).
    """
    last_borrow_update = 0.0
    tpsl_created: set[str] = set()  # idempotency_keys that already have on-chain TP/SL

    # Startup: discover existing on-chain trigger orders to prevent duplicates
    try:
        protected_pdas = await discover_existing_tpsl()
        if protected_pdas:
            # Map protected position PDAs back to tracked position idempotency_keys
            for pos in position_manager.get_open_positions():
                if pos.pda in protected_pdas:
                    tpsl_created.add(pos.idempotency_key)
            _json_event("tpsl_startup_recovery", recovered=len(tpsl_created))
    except Exception:  # noqa: BLE001
        log.debug("TP/SL startup discovery failed, will create fresh", exc_info=True)

    while not stop_event.is_set():
        if position_manager.get_position_count() == 0:
            await asyncio.sleep(price_interval)
            continue

        # Fetch latest prices for open markets
        prices = await _fetch_market_prices(position_manager)

        for market, price in prices.items():
            exits = position_manager.update_price(market, price)
            for exit_dec in exits:
                intent = exit_decision_to_intent(
                    exit_dec.idempotency_key, exit_dec.position_pda,
                )
                try:
                    queue.put_nowait(intent)
                    _json_event(
                        "exit_intent_queued",
                        trigger=exit_dec.trigger,
                        market=exit_dec.market,
                        urgency=exit_dec.urgency,
                        reason=exit_dec.reason,
                    )
                except asyncio.QueueFull:
                    _json_event("queue_backpressure", source="position_monitor", trigger=exit_dec.trigger)
                    position_manager.cancel_pending_exit(exit_dec.idempotency_key)

        # Create on-chain TP/SL for positions with entry price but no trigger orders yet
        for pos in position_manager.get_open_positions():
            if pos.idempotency_key in tpsl_created:
                continue
            if pos.entry_price <= 0 or not pos.pda or pos.pda == pos.idempotency_key:
                continue  # No entry price yet or no on-chain PDA

            triggers = position_manager.compute_tpsl_trigger_prices(pos.idempotency_key)

            # Race condition check: if current price already blew past SL
            # by the time entry_price was confirmed, skip TP/SL creation and
            # queue an immediate market close instead.
            sl_trigger = next((t for t in triggers if t["kind"] == "stop_loss"), None)
            if sl_trigger is not None:
                already_past_sl = False
                if pos.side == "long" and pos.current_price <= sl_trigger["trigger_price"]:
                    already_past_sl = True
                elif pos.side == "short" and pos.current_price >= sl_trigger["trigger_price"]:
                    already_past_sl = True

                if already_past_sl:
                    _json_event(
                        "panic_close",
                        market=pos.market,
                        side=pos.side,
                        current_price=pos.current_price,
                        sl_price=round(sl_trigger["trigger_price"], 4),
                        reason="price already past SL at entry confirmation",
                    )
                    panic_intent = ClosePosition(
                        idempotency_key=f"panic-{pos.idempotency_key}-{new_idempotency_key()[:8]}",
                        position_pda=pos.pda,
                        max_slippage_bps=300,
                    )
                    try:
                        queue.put_nowait(panic_intent)
                    except asyncio.QueueFull:
                        _json_event("queue_backpressure", source="panic_close")
                    tpsl_created.add(pos.idempotency_key)  # don't retry
                    continue

            for trig in triggers:
                tpsl_intent = CreateTPSL(
                    idempotency_key=f"tpsl-{trig['kind']}-{pos.idempotency_key}-{new_idempotency_key()[:8]}",
                    position_pda=trig["position_pda"],
                    trigger_price=trig["trigger_price"],
                    trigger_above_threshold=trig["trigger_above_threshold"],
                    entire_position=True,
                )
                try:
                    queue.put_nowait(tpsl_intent)
                    _json_event(
                        "tpsl_intent_queued",
                        kind=trig["kind"],
                        market=pos.market,
                        trigger_price=round(trig["trigger_price"], 4),
                    )
                except asyncio.QueueFull:
                    _json_event("queue_backpressure", source="tpsl_creation", kind=trig["kind"])
            tpsl_created.add(pos.idempotency_key)

        # Update borrow fees periodically
        now = time.monotonic()
        if now - last_borrow_update >= borrow_interval:
            position_manager.update_borrow_fees()
            last_borrow_update = now

        # Clean up tpsl_created for closed positions
        active_keys = {p.idempotency_key for p in position_manager.get_open_positions()}
        tpsl_created -= (tpsl_created - active_keys)

        await asyncio.sleep(price_interval)


async def _fetch_market_prices(position_manager: PositionManager) -> dict[str, float]:
    """Fetch current prices for all markets with open positions."""
    markets = {p.market for p in position_manager.get_open_positions()}
    prices: dict[str, float] = {}

    for market in markets:
        try:
            price = await _get_market_price(market)
            if price > 0:
                prices[market] = price
        except Exception:
            log.debug("Failed to fetch price for %s", market)

    return prices


_oracle_price_feed = OraclePriceFeed(OraclePriceFeedConfig.from_env())


async def _get_market_price(market: str) -> float:
    """Get current market price using the oracle-backed feed."""
    try:
        return await _oracle_price_feed.get_price(market)
    except Exception:
        log.debug("Failed to fetch oracle price for %s", market, exc_info=True)
        return 0.0


async def _heartbeat_loop(
    queue: asyncio.Queue[ExecutionIntent],
    stop_event: asyncio.Event,
    heartbeat_seconds: int,
    position_manager: PositionManager | None = None,
) -> None:
    while not stop_event.is_set():
        extra: dict[str, Any] = {"queue_depth": queue.qsize()}
        if position_manager is not None:
            extra["open_positions"] = position_manager.get_position_count()
            extra["total_exposure_usd"] = round(position_manager.get_total_exposure_usd(), 2)
            extra["daily_pnl_usd"] = round(position_manager.get_daily_pnl_usd(), 2)
        _json_event("heartbeat", **extra)
        await asyncio.sleep(heartbeat_seconds)


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            signal.signal(sig, lambda *_: stop_event.set())


async def run_runner(args: argparse.Namespace) -> None:
    _verify_idl_with_optional_override(args.idl_path, args.expected_idl_hash)
    runtime_versions = verify_runtime_versions(
        args.anchorpy_version,
        args.solders_version,
        args.solana_version,
    )

    journal = EventJournal(args.db_dsn, sqlite_path=args.sqlite_path)
    await journal.connect()
    live_control = LiveControlState(LiveControlConfig.from_env(args.control_state_path))

    service = ExecutionService(
        journal,
        live_mode=not args.dry_run,
        wallet_address=args.wallet_address,
        rpc_url=args.rpc_url,
        control_state_path=args.control_state_path,
    )
    await service.startup()

    # --- Position management, cost gate, and self-tuning ---
    position_manager = PositionManager(PositionManagerConfig.from_env())
    cost_gate = CostGate(CostGateConfig.from_env())
    tuner = PerpsAutoTuner(TunerConfig.from_env())

    # Load historical trade outcomes from SQLite for self-tuning
    if journal.has_local:
        await tuner.load_from_sqlite(journal._sqlite)

    queue: asyncio.Queue[ExecutionIntent] = asyncio.Queue(maxsize=args.max_queue_size)
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)

    _json_event(
        "startup",
        dry_run=args.dry_run,
        reconcile_interval_seconds=args.reconcile_interval_seconds,
        heartbeat_seconds=args.heartbeat_seconds,
        max_queue_size=args.max_queue_size,
        runtime_versions=runtime_versions,
        ai_bridge_enabled=args.enable_ai_bridge,
        position_monitor_enabled=True,
        control_state_path=str(live_control.path),
        intent_queue_path=args.intent_queue_path,
        intent_cursor_path=args.intent_cursor_path,
    )

    tasks: list[asyncio.Task[Any]] = [
        asyncio.create_task(
            _external_intent_loop(
                queue,
                stop_event,
                intent_queue_path=args.intent_queue_path,
                intent_cursor_path=args.intent_cursor_path,
            ),
            name="external_intent_loop",
        ),
        asyncio.create_task(_micro_loop(queue, stop_event), name="micro_loop"),
        asyncio.create_task(
            _intent_consumer(queue, service, stop_event, position_manager, tuner, journal, live_control),
            name="execution_consumer",
        ),
        asyncio.create_task(
            reconciliation_loop(journal, interval_seconds=args.reconcile_interval_seconds),
            name="reconciliation_loop",
        ),
        asyncio.create_task(
            _heartbeat_loop(queue, stop_event, args.heartbeat_seconds, position_manager),
            name="heartbeat_loop",
        ),
        asyncio.create_task(
            _position_monitor_loop(queue, position_manager, stop_event),
            name="position_monitor",
        ),
    ]

    if args.enable_macro:
        tasks.append(asyncio.create_task(_macro_loop(queue, stop_event), name="macro_loop"))

    if args.enable_ai_bridge:
        tasks.append(asyncio.create_task(
            ai_signal_loop(
                queue, stop_event,
                position_manager=position_manager,
                cost_gate=cost_gate,
                tuner=tuner,
                poll_interval=args.ai_poll_interval,
            ),
            name="ai_signal_bridge",
        ))

    if args.runtime_seconds > 0:
        async def _runtime_guard() -> None:
            await asyncio.sleep(args.runtime_seconds)
            stop_event.set()

        tasks.append(asyncio.create_task(_runtime_guard(), name="runtime_guard"))

    task_errors: list[tuple[str, str]] = []

    def _on_task_done(task: asyncio.Task[Any]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is None:
            return
        task_errors.append((task.get_name(), str(exc)))
        _json_event("task_crash", task=task.get_name(), error=str(exc))
        stop_event.set()

    for task in tasks:
        task.add_done_callback(_on_task_done)

    try:
        await stop_event.wait()
        if task_errors:
            first_name, first_error = task_errors[0]
            raise RuntimeError(f"Runner task failed task={first_name} error={first_error}")
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await service.shutdown()
        _json_event("shutdown", reason="signal_or_runtime_limit")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jupiter Perps canonical runner")
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--runtime-seconds", type=int, default=0)
    parser.add_argument("--reconcile-interval-seconds", type=int, default=10)
    parser.add_argument("--heartbeat-seconds", type=int, default=5)
    parser.add_argument("--max-queue-size", type=int, default=256)
    parser.add_argument("--lock-file", type=str, default=_default_lock_file())
    parser.add_argument("--control-state-path", type=str, default=os.environ.get("PERPS_CONTROL_STATE_PATH", ""))
    parser.add_argument(
        "--intent-queue-path",
        type=str,
        default=os.environ.get("PERPS_INTENT_QUEUE_PATH", _default_intent_queue_path()),
    )
    parser.add_argument(
        "--intent-cursor-path",
        type=str,
        default=os.environ.get("PERPS_INTENT_CURSOR_PATH", ""),
    )
    parser.add_argument("--idl-path", type=str, default="")
    parser.add_argument("--expected-idl-hash", type=str, default="")

    parser.add_argument("--db-dsn", type=str, default=os.environ.get("PERPS_DB_DSN", ""))
    parser.add_argument("--sqlite-path", type=str, default=os.environ.get("PERPS_SQLITE_PATH", ""))
    parser.add_argument("--wallet-address", type=str, default=os.environ.get("PERPS_WALLET_ADDRESS", ""))
    parser.add_argument("--rpc-url", type=str, default=os.environ.get("HELIUS_RPC_URL", "https://api.mainnet-beta.solana.com"))
    parser.add_argument("--disable-macro", action="store_true", default=False)

    parser.add_argument("--disable-ai-bridge", action="store_true", default=False)
    parser.add_argument("--enable-ai-bridge", action="store_true", default=False)
    parser.add_argument("--ai-poll-interval", type=int, default=int(os.environ.get("PERPS_AI_POLL_INTERVAL", "300")))

    parser.add_argument("--anchorpy-version", type=str, default=os.environ.get("PERPS_EXPECTED_ANCHORPY_VERSION", "0.21.0"))
    parser.add_argument("--solders-version", type=str, default=os.environ.get("PERPS_EXPECTED_SOLDERS_VERSION", "0.26.0"))
    parser.add_argument("--solana-version", type=str, default=os.environ.get("PERPS_EXPECTED_SOLANA_VERSION", "0.36.6"))

    return parser


def main() -> None:
    args = build_parser().parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    lock_file_path = Path(args.lock_file)
    try:
        lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file_path.touch(exist_ok=True)
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / "jarvis-ralph-wiggum"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        lock_file_path = fallback_dir / "runner.lock"
        args.lock_file = str(lock_file_path)
        _json_event("lock_path_fallback", lock_file=args.lock_file)

    args.enable_macro = not args.disable_macro
    if args.enable_ai_bridge:
        args.enable_ai_bridge = True
    else:
        args.enable_ai_bridge = False
    if args.disable_ai_bridge:
        args.enable_ai_bridge = False
    if not args.intent_cursor_path:
        args.intent_cursor_path = _default_intent_cursor_path(args.intent_queue_path)

    lock_handle = acquire_instance_lock(
        token=str(lock_file_path.resolve()),
        name="jupiter_perps_runner",
        max_wait_seconds=1,
    )
    if lock_handle is None:
        raise SystemExit(f"Another runner instance is active (lock token: {lock_file_path})")

    try:
        lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file_path.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / "jarvis-ralph-wiggum"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        lock_file_path = fallback_dir / "runner.lock"
        args.lock_file = str(lock_file_path)
        lock_file_path.write_text(str(os.getpid()), encoding="utf-8")
        _json_event("lock_path_fallback", lock_file=args.lock_file)
    try:
        asyncio.run(run_runner(args))
    finally:
        try:
            lock_file_path.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            lock_handle.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()

