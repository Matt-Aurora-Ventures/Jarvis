#!/usr/bin/env python3
"""
Telegram Bot E2E Test Runner (Telethon user client)

This runs end-to-end checks *in Telegram* by logging in as a user account
and interacting with a bot via messages + inline keyboard clicks.

Prereqs (same as other Telethon scripts in this repo):
- TELEGRAM_API_ID / TELEGRAM_API_HASH in env or .env
- A valid Telethon session at ~/.telegram_dl/session.session

Examples:
  python scripts/telegram_bot_e2e.py --bot @jarviskr8tivbot smoke
  python scripts/telegram_bot_e2e.py --bot @jarviskr8tivbot buy --amount 0.1 --require-bags
  python scripts/telegram_bot_e2e.py --bot @jarviskr8tivbot crawl --max-depth 3 --max-steps 80

Windows wrapper (runs via WSL + repo venv):
  .\\scripts\\telegram_bot_e2e.ps1 --bot @jarviskr8tivbot crawl --max-depth 3 --max-steps 80

Safety:
- The "buy" scenario may execute a real on-chain trade depending on the bot config.
  Use a test wallet / minimal amount.
- The "crawl" scenario never executes buys/sells, key exports, or sends. It only
  opens menus and validates back navigation.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from telethon import TelegramClient

# Windows terminals can be cp1252; the bot UI contains emojis.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass


BASE = Path.home() / ".telegram_dl"
SESSION_SRC = BASE / "session.session"


def _load_dotenv() -> tuple[Optional[str], Optional[str]]:
    # Minimal .env support (mirrors scripts/telegram_fetch.py behavior)
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    for p in [Path(".env"), Path.home() / ".env"]:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "TELEGRAM_API_ID" and not api_id:
                api_id = v
            if k == "TELEGRAM_API_HASH" and not api_hash:
                api_hash = v
    return api_id, api_hash


def _copy_session(out_dir: Path) -> Path:
    if not SESSION_SRC.exists():
        raise SystemExit(f"Telethon session not found: {SESSION_SRC}")
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"telegram_e2e_session_{int(time.time())}.session"
    dst.write_bytes(SESSION_SRC.read_bytes())
    return dst


def _decode_btn_data(btn) -> str:
    data = getattr(btn, "data", None)
    if data is None:
        return ""
    if isinstance(data, bytes):
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return ""
    return str(data)


def _find_button_by_data_prefix(message, prefix: str) -> Optional[Tuple[int, int, object]]:
    buttons = getattr(message, "buttons", None) or []
    for r, row in enumerate(buttons):
        for c, btn in enumerate(row):
            if _decode_btn_data(btn).startswith(prefix):
                return r, c, btn
    return None


def _find_button_by_text_contains(message, needle: str) -> Optional[Tuple[int, int, object]]:
    buttons = getattr(message, "buttons", None) or []
    needle_l = needle.lower()
    for r, row in enumerate(buttons):
        for c, btn in enumerate(row):
            txt = (getattr(btn, "text", "") or "").lower()
            if needle_l in txt:
                return r, c, btn
    return None


def _amount_to_btn_str(amount: float) -> str:
    # Match the bot's callback formatting (e.g. "1" not "1.0")
    if abs(amount - round(amount)) < 1e-9:
        return str(int(round(amount)))
    return f"{amount:.8f}".rstrip("0").rstrip(".")


def _looks_like_error(text: str) -> bool:
    t = (text or "").lower()
    # Keep this conservative: match only known bad states we want to eliminate.
    return any(
        s in t
        for s in (
            "🔴 error",
            "operation failed",
            "trade execution failed",
            "buy failed",
            "handler error in",
            "traceback",
            "object has no attribute",
            "sorry, something went wrong",
            "unknown bags.fm action",
        )
    )


def _looks_like_placeholder(text: str) -> bool:
    """Detect clearly fake/placeholder content we want to eliminate."""
    t = (text or "").lower()
    return any(
        s in t
        for s in (
            "using mock data",
            "mock data",
            "placeholder",
            "fartcoin",
        )
    )


def _page_signature(text: str) -> str:
    """Best-effort stable page id for back-navigation verification."""
    raw = text or ""
    for line in raw.splitlines():
        l = line.strip()
        if not l:
            continue
        # Strip common markdown markers so signatures are stable across parse_mode fallbacks.
        l = re.sub(r"[*_`]", "", l)
        return l[:90]
    return ""


@dataclass(frozen=True)
class _Btn:
    r: int
    c: int
    data: str
    text: str


def _iter_callback_buttons(message) -> list[_Btn]:
    out: list[_Btn] = []
    buttons = getattr(message, "buttons", None) or []
    for r, row in enumerate(buttons):
        for c, btn in enumerate(row):
            data = _decode_btn_data(btn)
            if not data:
                continue
            out.append(_Btn(r=r, c=c, data=data, text=getattr(btn, "text", "") or ""))
    return out


def _has_demo_callbacks(message) -> bool:
    for b in _iter_callback_buttons(message):
        if b.data.startswith("demo:"):
            return True
    return False


_CRAWL_HARD_DENY_ACTIONS = {
    # Trading / funds movement
    "execute_buy",
    "sell",
    "sell_all",
    "send_sol",
    "send_sol_confirm",
    "send_sol_exec",
    "bags_exec",
    "hub_buy",
    "snipe_confirm",
    # Secret material
    "export_key",
    "export_key_confirm",
    "wallet_reset_confirm",
    "wallet_reset",
    # Wallet import/create (can prompt for secrets)
    "wallet_create",
    "wallet_import",
    "import_mode_key",
    "import_mode_seed",
    # Bot state toggles that could trigger trading
    "ai_auto_toggle",
    "ai_risk",
    "ai_max",
    "ai_conf",
    # Non-navigation noise
    "close",
    "noop",
    "copy_ca",
    "view_chart",
}


def _crawl_is_safe_callback(data: str) -> bool:
    if not data or not data.startswith("demo:"):
        return False
    action = data.split(":", 2)[1] if ":" in data else ""
    if action in _CRAWL_HARD_DENY_ACTIONS:
        return False
    # Prefix-based denies (some actions aren't cleanly captured by action parsing).
    if data.startswith("demo:execute_buy:"):
        return False
    if data.startswith("demo:sell:"):
        return False
    if data.startswith("demo:bags_exec:"):
        return False
    if data.startswith("demo:snipe_confirm:"):
        return False
    if data.startswith("demo:hub_buy:"):
        return False
    if data.startswith("demo:copy_ca:"):
        return False
    return True


def _crawl_normalize_callback(data: str) -> str:
    """Group callback variants (token ids, amounts) to keep crawl bounded."""
    if not data or not data.startswith("demo:"):
        return data
    parts = data.split(":")
    if len(parts) <= 2:
        return data
    # Normalize to action-level (demo:<action>:*)
    return f"demo:{parts[1]}:*"


def _is_trade_terminal(text: str) -> bool:
    t = (text or "").lower()
    return (
        _looks_like_error(t)
        or "buy order executed" in t
        or "tp/sl monitoring active" in t
    )


@dataclass(frozen=True)
class StepResult:
    name: str
    ok: bool
    details: str


async def _latest_message_id(client: TelegramClient, chat) -> int:
    msgs = await client.get_messages(chat, limit=1)
    return int(msgs[0].id) if msgs else 0


async def _wait_for_bot_response(
    client: TelegramClient,
    chat,
    *,
    bot_id: int,
    after_id: int,
    timeout_s: float,
) -> object:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msgs = await client.get_messages(chat, limit=10)
        for m in msgs:
            if int(m.id) <= int(after_id):
                continue
            if int(getattr(m, "sender_id", 0) or 0) == int(bot_id):
                return m
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for bot response after msg_id={after_id}")


async def _wait_for_message_edit(
    client: TelegramClient,
    chat,
    *,
    msg_id: int,
    old_text: str,
    old_edit_date,
    timeout_s: float,
) -> object:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        m = await client.get_messages(chat, ids=msg_id)
        if not m:
            await asyncio.sleep(0.5)
            continue
        if (m.text or "") != (old_text or ""):
            return m
        if getattr(m, "edit_date", None) != old_edit_date:
            return m
        await asyncio.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for message edit msg_id={msg_id}")


async def _click_and_wait(
    client: TelegramClient,
    message,
    *,
    r: int,
    c: int,
    bot_id: int,
    timeout_s: float,
) -> object:
    chat = message.chat_id
    before_latest = await _latest_message_id(client, chat)
    msg_id = int(message.id)
    old_text = message.text or ""
    old_edit_date = getattr(message, "edit_date", None)

    await message.click(r, c)

    # Prefer edits (demo UI edits in place), but accept new messages too.
    try:
        return await _wait_for_message_edit(
            client,
            chat,
            msg_id=msg_id,
            old_text=old_text,
            old_edit_date=old_edit_date,
            timeout_s=timeout_s,
        )
    except TimeoutError:
        return await _wait_for_bot_response(
            client,
            chat,
            bot_id=bot_id,
            after_id=before_latest,
            timeout_s=timeout_s,
        )


async def _click_and_wait_trade_result(
    client: TelegramClient,
    message,
    *,
    r: int,
    c: int,
    timeout_s: float,
) -> object:
    """
    Trade executions typically produce multiple edits (loading -> final).
    Wait for the message to reach a terminal state.
    """
    chat = message.chat_id
    msg_id = int(message.id)
    await message.click(r, c)

    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        last = await client.get_messages(chat, ids=msg_id)
        if last and _is_trade_terminal(last.text or ""):
            return last
        await asyncio.sleep(0.8)
    if last:
        return last
    raise TimeoutError(f"Timed out waiting for trade result msg_id={msg_id}")


async def _send_and_wait(
    client: TelegramClient,
    chat,
    *,
    bot_id: int,
    text: str,
    timeout_s: float,
) -> object:
    before_latest = await _latest_message_id(client, chat)
    await client.send_message(chat, text)
    return await _wait_for_bot_response(
        client,
        chat,
        bot_id=bot_id,
        after_id=before_latest,
        timeout_s=timeout_s,
    )


async def scenario_smoke(
    client: TelegramClient,
    *,
    bot_username: str,
    timeout_s: float,
) -> list[StepResult]:
    bot = await client.get_entity(bot_username)
    bot_id = int(getattr(bot, "id"))
    out: list[StepResult] = []

    # 1) /start should render the base menu
    msg = await _send_and_wait(client, bot, bot_id=bot_id, text="/start", timeout_s=timeout_s)
    out.append(StepResult("send:/start", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

    # 2) Enter demo UI (prefer inline button, fall back to /demo)
    btn = _find_button_by_data_prefix(msg, "demo:main") or _find_button_by_text_contains(msg, "demo")
    if btn:
        msg = await _click_and_wait(client, msg, r=btn[0], c=btn[1], bot_id=bot_id, timeout_s=timeout_s)
        out.append(StepResult("click:demo_main", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))
    else:
        msg = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
        out.append(StepResult("send:/demo", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

    # 3) Click Trending
    btn = _find_button_by_data_prefix(msg, "demo:trending") or _find_button_by_text_contains(msg, "trending")
    if not btn:
        out.append(StepResult("click:trending", ok=False, details="Trending button not found"))
        return out
    msg = await _click_and_wait(client, msg, r=btn[0], c=btn[1], bot_id=bot_id, timeout_s=timeout_s)
    out.append(StepResult("click:trending", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

    # 4) Click first Quick Buy button (but do not execute trade in smoke)
    btn = _find_button_by_data_prefix(msg, "demo:quick_buy:")
    if not btn:
        out.append(StepResult("click:quick_buy", ok=False, details="Quick buy button not found on trending page"))
        return out
    msg = await _click_and_wait(client, msg, r=btn[0], c=btn[1], bot_id=bot_id, timeout_s=timeout_s)
    out.append(StepResult("click:quick_buy", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

    return out


async def scenario_buy(
    client: TelegramClient,
    *,
    bot_username: str,
    amount_sol: float,
    timeout_s: float,
    require_bags: bool,
) -> list[StepResult]:
    bot = await client.get_entity(bot_username)
    bot_id = int(getattr(bot, "id"))
    out: list[StepResult] = []

    amount_str = _amount_to_btn_str(amount_sol)

    if abs(amount_sol - 0.1) < 1e-9:
        # Use the safe 2-step quick-buy flow (confirm screen).
        steps = await scenario_smoke(client, bot_username=bot_username, timeout_s=timeout_s)
        out.extend(steps)
        if any(not s.ok for s in steps):
            return out

        msgs = await client.get_messages(bot, limit=3)
        current = next((m for m in msgs if int(getattr(m, "sender_id", 0) or 0) == bot_id), None)
        if not current:
            out.append(StepResult("locate:confirm_screen", ok=False, details="Could not locate latest bot message"))
            return out

        btn = _find_button_by_text_contains(current, "confirm") or _find_button_by_data_prefix(current, "demo:execute_buy:")
        if not btn:
            out.append(StepResult("click:confirm_buy", ok=False, details="Confirm buy button not found"))
            return out

        msg = await _click_and_wait_trade_result(client, current, r=btn[0], c=btn[1], timeout_s=timeout_s * 2)
        step_name = "click:confirm_buy"
    else:
        # Use buy_custom to select an explicit amount preset (executes immediately).
        msg = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
        out.append(StepResult("send:/demo", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

        btn = _find_button_by_data_prefix(msg, "demo:trending") or _find_button_by_text_contains(msg, "trending")
        if not btn:
            out.append(StepResult("click:trending", ok=False, details="Trending button not found"))
            return out
        msg = await _click_and_wait(client, msg, r=btn[0], c=btn[1], bot_id=bot_id, timeout_s=timeout_s)
        out.append(StepResult("click:trending", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

        btn = _find_button_by_data_prefix(msg, "demo:buy_custom:")
        if not btn:
            out.append(StepResult("click:buy_custom", ok=False, details="Buy custom button not found on trending page"))
            return out
        msg = await _click_and_wait(client, msg, r=btn[0], c=btn[1], bot_id=bot_id, timeout_s=timeout_s)
        out.append(StepResult("click:buy_custom", ok=not _looks_like_error(msg.text or ""), details=(msg.text or "")[:160]))

        btn = _find_button_by_data_prefix(msg, "demo:execute_buy:")
        if not btn:
            out.append(StepResult("click:amount", ok=False, details="Amount buttons not found"))
            return out

        # Try to pick the requested amount.
        chosen = None
        buttons = getattr(msg, "buttons", None) or []
        for r, row in enumerate(buttons):
            for c, b in enumerate(row):
                data = _decode_btn_data(b)
                if data.startswith("demo:execute_buy:") and data.endswith(f":{amount_str}"):
                    chosen = (r, c, b)
                    break
            if chosen:
                break
        if not chosen:
            out.append(StepResult("click:amount", ok=False, details=f"Requested amount not available: {amount_str}"))
            return out

        msg = await _click_and_wait_trade_result(client, msg, r=chosen[0], c=chosen[1], timeout_s=timeout_s * 2)
        step_name = f"click:amount:{amount_str}"

    text = msg.text or ""
    ok = not _looks_like_error(text)

    if require_bags:
        ok = ok and ("bags" in text.lower()) and ("jupiter" not in text.lower())

    out.append(StepResult(step_name, ok=ok, details=text[:240]))
    return out


async def scenario_crawl(
    client: TelegramClient,
    *,
    bot_username: str,
    timeout_s: float,
    max_depth: int,
    max_steps: int,
    max_per_page: int,
    delay_ms: int,
    stop_on_fail: bool,
) -> list[StepResult]:
    bot = await client.get_entity(bot_username)
    bot_id = int(getattr(bot, "id"))
    out: list[StepResult] = []

    msg = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
    out.append(StepResult("send:/demo", ok=(not _looks_like_error(msg.text or "")), details=(msg.text or "")[:160]))
    if _looks_like_error(msg.text or ""):
        return out

    steps = 0
    visited: set[str] = set()

    async def _crawl_page(message, depth: int) -> object:
        nonlocal steps
        if steps >= max_steps or depth >= max_depth:
            return message

        parent_sig = _page_signature(message.text or "")

        # Ensure Previous Menu is present on every page we visit (except the initial /demo page,
        # which may not have navigation history yet).
        prev_btn = _find_button_by_data_prefix(message, "demo:nav_back")
        require_prev = depth > 0
        out.append(
            StepResult(
                f"crawl:has_prev:d{depth}:{parent_sig}",
                ok=(prev_btn is not None) or (not require_prev),
                details=(message.text or "")[:160],
            )
        )
        if require_prev and prev_btn is None and stop_on_fail:
            return message

        # Collect safe callbacks for this page.
        btns = _iter_callback_buttons(message)
        safe: list[_Btn] = []
        seen_norm: set[str] = set()
        for b in btns:
            if b.data == "demo:nav_back":
                continue
            if not _crawl_is_safe_callback(b.data):
                continue
            norm = _crawl_normalize_callback(b.data)
            if norm in seen_norm:
                continue
            if norm in visited:
                continue
            seen_norm.add(norm)
            safe.append(b)

        # Prefer menu-level actions over token-specific actions.
        def _prio(b: _Btn) -> tuple[int, str]:
            action = b.data.split(":", 2)[1] if ":" in b.data else b.data
            top = {
                "main",
                "refresh",
                "trending",
                "ai_picks",
                "ai_report",
                "quick_trade",
                "bags_fm",
                "hub",
                "positions",
                "balance",
                "wallet_menu",
                "settings",
                "watchlist",
                "dca",
                "learning",
                "performance",
                "token_search",
            }
            return (0 if action in top else 1, b.data)

        safe.sort(key=_prio)
        safe = safe[: max(0, int(max_per_page))]

        for b in safe:
            if steps >= max_steps:
                break

            norm = _crawl_normalize_callback(b.data)
            visited.add(norm)

            await asyncio.sleep(max(0, delay_ms) / 1000.0)
            try:
                raw = await _click_and_wait(
                    client,
                    message,
                    r=b.r,
                    c=b.c,
                    bot_id=bot_id,
                    timeout_s=timeout_s,
                )
                steps += 1
            except TimeoutError as exc:
                out.append(
                    StepResult(
                        f"crawl:timeout:{norm}:d{depth}->{depth+1}",
                        ok=False,
                        details=str(exc)[:200],
                    )
                )
                if stop_on_fail:
                    return message
                # Recovery: reset to /demo and continue.
                try:
                    message = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
                    steps += 1
                except Exception:
                    pass
                continue
            except Exception as exc:
                out.append(
                    StepResult(
                        f"crawl:click_error:{norm}:d{depth}->{depth+1}",
                        ok=False,
                        details=str(exc)[:200],
                    )
                )
                if stop_on_fail:
                    return message
                try:
                    message = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
                    steps += 1
                except Exception:
                    pass
                continue

            raw_text = raw.text or ""

            # Some actions respond by sending a side-message (photo/caption) while leaving the
            # current menu unchanged. In that case, keep crawling from the menu message.
            child_menu = raw
            try:
                if not _has_demo_callbacks(raw):
                    refreshed = await client.get_messages(message.chat_id, ids=int(message.id))
                    if refreshed and _has_demo_callbacks(refreshed):
                        child_menu = refreshed
            except Exception:
                pass

            child_text = child_menu.text or ""
            child_sig = _page_signature(child_text)
            nav_changed = child_sig != parent_sig
            ok_child = (
                (not _looks_like_error(raw_text))
                and (not _looks_like_error(child_text))
                and (not _looks_like_placeholder(raw_text))
                and (not _looks_like_placeholder(child_text))
            )
            out.append(
                StepResult(
                    f"crawl:click:{norm}:d{depth}->{depth+1}",
                    ok=ok_child,
                    details=(raw_text or child_text or "")[:200],
                )
            )
            if (not ok_child) and stop_on_fail:
                return child_menu

            # If the menu didn't change, treat this as a side-effect action and continue.
            if not nav_changed:
                message = child_menu
                continue

            # Recurse deeper from the child menu page.
            child_menu = await _crawl_page(child_menu, depth + 1)

            # Back to parent.
            back_btn = _find_button_by_data_prefix(child_menu, "demo:nav_back")
            if not back_btn:
                out.append(
                    StepResult(
                        f"crawl:back_missing:{norm}:d{depth+1}",
                        ok=False,
                        details=(child_menu.text or "")[:200],
                    )
                )
                if stop_on_fail:
                    return child_menu
                # Recovery: reset to /demo (nav stack also resets).
                message = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
                steps += 1
                continue

            await asyncio.sleep(max(0, delay_ms) / 1000.0)
            try:
                back = await _click_and_wait(
                    client,
                    child_menu,
                    r=back_btn[0],
                    c=back_btn[1],
                    bot_id=bot_id,
                    timeout_s=timeout_s,
                )
                steps += 1
            except TimeoutError as exc:
                out.append(
                    StepResult(
                        f"crawl:back_timeout:{norm}:d{depth+1}->{depth}",
                        ok=False,
                        details=str(exc)[:200],
                    )
                )
                if stop_on_fail:
                    return child_menu
                message = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
                steps += 1
                continue
            except Exception as exc:
                out.append(
                    StepResult(
                        f"crawl:back_error:{norm}:d{depth+1}->{depth}",
                        ok=False,
                        details=str(exc)[:200],
                    )
                )
                if stop_on_fail:
                    return child_menu
                message = await _send_and_wait(client, bot, bot_id=bot_id, text="/demo", timeout_s=timeout_s)
                steps += 1
                continue

            back_sig = _page_signature(back.text or "")
            ok_back = (not _looks_like_error(back.text or "")) and (back_sig == parent_sig)
            out.append(
                StepResult(
                    f"crawl:back:{norm}:to:{parent_sig}",
                    ok=ok_back,
                    details=(back.text or "")[:200],
                )
            )
            message = back

            if (not ok_back) and stop_on_fail:
                return message

        return message

    await _crawl_page(msg, 0)
    return out


async def run(args) -> int:
    api_id, api_hash = _load_dotenv()
    if not api_id or not api_hash:
        raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH in env or .env")

    session_copy = _copy_session(Path(".tmp"))
    client = TelegramClient(str(session_copy).replace(".session", ""), int(api_id), api_hash)

    async with client:
        await client.start()
        if args.scenario == "smoke":
            results = await scenario_smoke(client, bot_username=args.bot, timeout_s=args.timeout)
        elif args.scenario == "buy":
            results = await scenario_buy(
                client,
                bot_username=args.bot,
                amount_sol=args.amount,
                timeout_s=args.timeout,
                require_bags=args.require_bags,
            )
        elif args.scenario == "crawl":
            results = await scenario_crawl(
                client,
                bot_username=args.bot,
                timeout_s=args.timeout,
                max_depth=args.max_depth,
                max_steps=args.max_steps,
                max_per_page=args.max_per_page,
                delay_ms=args.delay_ms,
                stop_on_fail=args.stop_on_fail,
            )
        else:
            raise SystemExit(f"Unknown scenario: {args.scenario}")

    print("telegram_bot_e2e")
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(f"- {r.name}: {status} | {r.details}")

    return 0 if all(r.ok for r in results) else 1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", type=str, required=True, help="Bot username, e.g. @jarviskr8tivbot")
    ap.add_argument("--timeout", type=float, default=45.0)
    ap.add_argument("--amount", type=float, default=0.1)
    ap.add_argument("--require-bags", action="store_true", help="Fail if response indicates Jupiter was used")
    ap.add_argument("--max-depth", type=int, default=3, help="crawl: max navigation depth")
    ap.add_argument("--max-steps", type=int, default=80, help="crawl: total click budget (includes back clicks)")
    ap.add_argument("--max-per-page", type=int, default=10, help="crawl: max unique callbacks to explore per page")
    ap.add_argument("--delay-ms", type=int, default=350, help="crawl: delay between clicks to reduce rate limits")
    ap.add_argument("--stop-on-fail", action="store_true", help="crawl: stop immediately on first failure")
    ap.add_argument("scenario", choices=("smoke", "buy", "crawl"))
    raise SystemExit(asyncio.run(run(ap.parse_args())))


if __name__ == "__main__":
    main()
