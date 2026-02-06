#!/usr/bin/env python3
"""
Generate a fix-it list from the last N hours of Telegram messages in a chat.

Usage:
  python scripts/telegram_fixit_loop.py --chat-id -1003408655098 --hours 48
  python scripts/telegram_fixit_loop.py --chat-id -1003408655098 --hours 48 --loop --interval 1800
"""

import os
import json
import time
import argparse
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient

BASE = Path.home() / ".telegram_dl"
SESSION_SRC = BASE / "session.session"

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Optional .env support
for p in [Path(".env"), Path.home() / ".env"]:
    if p.exists():
        for line in p.read_text().splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TELEGRAM_API_ID" and not API_ID:
                API_ID = v.strip()
            if k.strip() == "TELEGRAM_API_HASH" and not API_HASH:
                API_HASH = v.strip()
            if k.strip() == "TELEGRAM_BOT_TOKEN" and not BOT_TOKEN:
                BOT_TOKEN = v.strip()

if not API_ID or not API_HASH:
    raise SystemExit("Missing TELEGRAM_API_ID / TELEGRAM_API_HASH")

# Topic mapping
TOPICS = {
    "Hostinger/KVM8 access & reboot": [r"hostinger", r"kvm8", r"hpanel", r"console", r"vps", r"reboot", r"restart"],
    "Agent TARS / browser automation": [r"agent[- ]?tars", r"ui[- ]?tars", r"cdp", r"chrome relay", r"browser relay", r"playwright", r"firefox"],
    "Credentials/session/auth": [r"credential", r"login", r"cookie", r"session", r"auth", r"2fa", r"password"],
    "Brave API / web search": [r"brave", r"search api", r"web search"],
    "Hetzner/Yoda SSH": [r"hetzner", r"yoda", r"authorized_keys", r"ssh"],
    "Tailscale/access bridge": [r"tailscale", r"tailnet", r"100\."],
    "Memory / Supermemory / embeddings": [r"supermemory", r"memory search", r"embeddings", r"openai quota", r"404"],
    "Docker/healthcheck/SIGTERM": [r"docker", r"healthcheck", r"sigterm", r"compose", r"watchdog"],
    "Model/provider config": [r"anthropic", r"claude", r"opus", r"sonnet", r"kimi", r"model", r"provider", r"allowlist", r"grok"],
    "Gateway/tools": [r"gateway", r"agent-to-agent", r"agentToAgent", r"config.patch"],
    "Bot crash/instability": [r"crash", r"loop", r"not working", r"down", r"broken", r"failed"],
}

TOPIC_FIXES = {
    "Hostinger/KVM8 access & reboot": [
        "Ensure Hostinger access path works (Agent TARS or Chrome Relay).",
        "Confirm KVM8 uptime and capture crash evidence after reboot.",
        "Apply memory caps and staggered startup on KVM8 supervisor.",
    ],
    "Agent TARS / browser automation": [
        "Use Agent TARS with hybrid control and persistent workspace.",
        "If DOM-only fails, switch to visual-grounding for OAuth flows.",
        "Persist browser session so Google/Hostinger login survives restarts.",
    ],
    "Credentials/session/auth": [
        "Avoid pasting creds in chat; use local OAuth session or secure vault.",
        "If OAuth is required, log in once via Agent TARS and reuse session.",
    ],
    "Brave API / web search": [
        "Add BRAVE_API_KEY to env/secrets for all bots needing web search.",
    ],
    "Hetzner/Yoda SSH": [
        "Add persistent SSH key to Hetzner host; verify Yoda can restart KVM2.",
    ],
    "Tailscale/access bridge": [
        "Start Tailscale daemon and confirm all nodes on tailnet.",
        "Record node IPs in TOOLS.md for quick access.",
    ],
    "Memory / Supermemory / embeddings": [
        "Fix Supermemory API 404s or fallback to local embeddings (Chroma/Gemini).",
        "Ensure memory search isn’t hammering quota; add backoff or disable.",
    ],
    "Docker/healthcheck/SIGTERM": [
        "Converge to a single watchdog; remove conflicting restart scripts.",
        "Set healthcheck interval/retries/start_period to reduce flapping.",
    ],
    "Model/provider config": [
        "Normalize model IDs and provider allowlist; avoid unknown model errors.",
        "Decouple API keys per bot to prevent shared quota failures.",
    ],
    "Gateway/tools": [
        "Keep agent-to-agent tools enabled only as needed; document toggles.",
    ],
    "Bot crash/instability": [
        "Capture logs around crash loops; address root cause before auto-restart.",
    ],
}


def fetch_last_hours(chat_id: int, hours: int, out_dir: Path):
    if not SESSION_SRC.exists():
        raise SystemExit(f"Session not found: {SESSION_SRC}")

    # Copy session to avoid sqlite lock
    session_copy = out_dir / "telegram_session_copy.session"
    if session_copy.exists():
        session_copy.unlink()
    session_copy.write_bytes(SESSION_SRC.read_bytes())

    client = TelegramClient(str(session_copy).replace(".session", ""), int(API_ID), API_HASH)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    async def run():
        if BOT_TOKEN and BOT_TOKEN.strip().lower() not in ("disable", "disabled", "none", "no", "false"):
            await client.start(bot_token=BOT_TOKEN)
        else:
            await client.start()

        all_msgs = []
        offset_id = 0
        offset_date = None
        batch = 1000
        while True:
            msgs = await client.get_messages(chat_id, limit=batch, offset_id=offset_id, offset_date=offset_date)
            if not msgs:
                break
            all_msgs.extend(msgs)
            last = msgs[-1]
            offset_id = last.id
            offset_date = last.date
            if last.date and last.date < cutoff:
                break

        filtered = [m for m in all_msgs if m.date and m.date >= cutoff]
        # sender names
        sender_ids = list({m.sender_id for m in filtered if m.sender_id})
        id_to_name = {}
        if sender_ids:
            try:
                entities = await client.get_entities(sender_ids)
                for ent in entities:
                    name = None
                    if hasattr(ent, "title") and ent.title:
                        name = ent.title
                    else:
                        parts = [getattr(ent, "first_name", None), getattr(ent, "last_name", None)]
                        name = " ".join([p for p in parts if p])
                    if not name and getattr(ent, "username", None):
                        name = ent.username
                    if name:
                        id_to_name[ent.id] = name
            except Exception:
                pass

        def fmt(m):
            name = id_to_name.get(m.sender_id) if m.sender_id else None
            return {
                "id": m.id,
                "date": m.date.isoformat() if m.date else None,
                "sender_id": m.sender_id,
                "sender": name,
                "text": m.text,
            }

        out = [fmt(m) for m in sorted(filtered, key=lambda x: x.date)]

        await client.disconnect()
        return out

    import asyncio
    return asyncio.run(run())


def generate_fixit(msgs):
    compiled = {k: re.compile("|".join(v), re.I) for k, v in TOPICS.items()}
    topic_hits = {k: [] for k in TOPICS}

    for m in msgs:
        text = m.get("text") or ""
        for k, rx in compiled.items():
            if rx.search(text):
                topic_hits[k].append(m)

    def last_mentions(items):
        items = [i for i in items if i.get("text")]
        return items[-3:]

    # Build report
    report = {
        "summary": {
            "total_messages": len(msgs),
            "topics": {k: len(v) for k, v in topic_hits.items()},
        },
        "topics": {},
    }

    for k, items in topic_hits.items():
        report["topics"][k] = {
            "count": len(items),
            "fixes": TOPIC_FIXES.get(k, []),
            "examples": [
                {
                    "date": i.get("date"),
                    "sender": i.get("sender") or i.get("sender_id"),
                    "text": (i.get("text") or "")[:500],
                }
                for i in last_mentions(items)
            ],
        }

    return report


def extract_questions(text: str):
    questions = []
    for line in text.splitlines():
        l = line.strip()
        if not l:
            continue
        if l.startswith("Q:") or l.startswith("Question:") or "?" in l:
            questions.append(l)
    # De-dup while preserving order
    seen = set()
    out = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def render_markdown(report, hours, chat_id, source_title=None, source_text=None):
    lines = []
    lines.append(f"# Fix-It Report (Last {hours}h)\n")
    lines.append(f"Chat: `{chat_id}`")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")

    if source_text:
        title = source_title or "External Source"
        lines.append(f"## Source: {title}")
        questions = extract_questions(source_text)
        if questions:
            lines.append("- Questions extracted:")
            for q in questions[:50]:
                lines.append(f"- {q}")
        excerpt = source_text.strip().splitlines()
        if excerpt:
            lines.append("- Source excerpt:")
            for ln in excerpt[:40]:
                lines.append(f"- {ln}")
        lines.append("")

    lines.append("## Summary")
    lines.append(f"- Total messages: {report['summary']['total_messages']}")
    lines.append("- Topic counts:")
    for k, v in report["summary"]["topics"].items():
        lines.append(f"- {k}: {v}")

    lines.append("\n## Fixes by Topic")
    for k, t in report["topics"].items():
        lines.append(f"\n### {k}")
        lines.append(f"- Mentions: {t['count']}")
        if t["fixes"]:
            lines.append("- Proposed fixes:")
            for fx in t["fixes"]:
                lines.append(f"- {fx}")
        if t["examples"]:
            lines.append("- Recent examples:")
            for ex in t["examples"]:
                lines.append(f"- [{ex['date']}] {ex['sender']}: {ex['text']}")

    return "\n".join(lines) + "\n"


def run_once(chat_id, hours, out_dir: Path, source_file: Path = None, source_title: str = None):
    out_dir.mkdir(parents=True, exist_ok=True)
    msgs = fetch_last_hours(chat_id, hours, out_dir)
    report = generate_fixit(msgs)

    source_text = None
    if source_file and source_file.exists():
        source_text = source_file.read_text(encoding="utf-8", errors="ignore")
        report["source"] = {
            "title": source_title or str(source_file),
            "file": str(source_file),
        }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    raw_path = out_dir / f"fixit_raw_{ts}.json"
    rep_path = out_dir / f"fixit_report_{ts}.json"
    md_path = out_dir / f"fixit_report_{ts}.md"
    latest_md = out_dir / "fixit_latest.md"
    latest_json = out_dir / "fixit_latest.json"

    raw_path.write_text(json.dumps(msgs, indent=2, ensure_ascii=False), encoding="utf-8")
    rep_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_markdown(report, hours, chat_id, source_title, source_text), encoding="utf-8")

    latest_md.write_text(render_markdown(report, hours, chat_id, source_title, source_text), encoding="utf-8")
    latest_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    return md_path, rep_path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--chat-id", type=int, required=True)
    p.add_argument("--hours", type=int, default=48)
    p.add_argument("--loop", action="store_true")
    p.add_argument("--interval", type=int, default=1800, help="seconds between runs")
    p.add_argument("--out-dir", type=str, default="reports")
    p.add_argument("--source-file", type=str, default=None)
    p.add_argument("--source-title", type=str, default=None)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    source_file = Path(args.source_file) if args.source_file else None
    while True:
        md_path, _rep_path = run_once(args.chat_id, args.hours, out_dir, source_file, args.source_title)
        print(f"Wrote: {md_path}")
        if not args.loop:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
