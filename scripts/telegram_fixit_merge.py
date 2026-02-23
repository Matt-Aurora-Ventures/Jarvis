#!/usr/bin/env python3
"""
Merge multiple telegram_fixit_loop reports into one master "mega fix-it" report.

Input: a directory containing pairs of:
  - fixit_report_YYYYMMDD-HHMMSS.md
  - fixit_report_YYYYMMDD-HHMMSS.json

The markdown contains the chat id in the header line:
  Chat: `123456`

Output:
  - combined markdown with:
    - per-chat summary
    - merged topic counts
    - consolidated P0/P1/P2 fix list

This script is intentionally dependency-free (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


CHAT_LABELS = {
    -5003286623: "kr8tiv (Group)",
    -1003408655098: "KR8TIV AI - Jarvis Life OS (Group)",
    7864180473: "Friday DM (@ClawdFriday_bot)",
    8434411668: "ClawdJarvis DM (@ClawdJarvis_87772_bot)",
    8288059637: "Matt DM (@ClawdMatt_bot)",
    8587062928: "Jarvis Trading Bot DM",
    8582341584: "Yoda DM",
}


CHAT_RE = re.compile(r"^Chat:\s+`(?P<id>-?\d+)`\s*$", re.M)


@dataclass(frozen=True)
class ReportRef:
    chat_id: int
    ts: str  # YYYYMMDD-HHMMSS from filename
    md_path: Path
    json_path: Path


def _parse_chat_id(md_text: str) -> Optional[int]:
    m = CHAT_RE.search(md_text)
    if not m:
        return None
    try:
        return int(m.group("id"))
    except Exception:
        return None


def discover_reports(in_dir: Path) -> List[ReportRef]:
    md_files = sorted(in_dir.glob("fixit_report_*.md"))
    refs: List[ReportRef] = []
    for md_path in md_files:
        ts = md_path.stem.replace("fixit_report_", "")
        json_path = in_dir / f"fixit_report_{ts}.json"
        if not json_path.exists():
            continue
        md_text = md_path.read_text(encoding="utf-8", errors="ignore")
        chat_id = _parse_chat_id(md_text)
        if chat_id is None:
            continue
        refs.append(ReportRef(chat_id=chat_id, ts=ts, md_path=md_path, json_path=json_path))
    return refs


def latest_by_chat(refs: List[ReportRef]) -> Dict[int, ReportRef]:
    out: Dict[int, ReportRef] = {}
    for r in refs:
        prev = out.get(r.chat_id)
        if prev is None or r.ts > prev.ts:
            out[r.chat_id] = r
    return out


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def merge_topic_counts(reports: List[Tuple[int, Dict[str, Any]]]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for _chat_id, rep in reports:
        topics = (rep.get("summary") or {}).get("topics") or {}
        for k, v in topics.items():
            try:
                merged[k] = merged.get(k, 0) + int(v)
            except Exception:
                continue
    return dict(sorted(merged.items(), key=lambda kv: kv[1], reverse=True))


def extract_topic_fixes(rep: Dict[str, Any]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    topics = rep.get("topics") or {}
    for topic, tdata in topics.items():
        fixes = tdata.get("fixes") or []
        out[topic] = [str(f).strip() for f in fixes if str(f).strip()]
    return out


def merge_fixes(reports: List[Tuple[int, Dict[str, Any]]]) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    seen: Dict[str, set] = {}
    for _chat_id, rep in reports:
        per = extract_topic_fixes(rep)
        for topic, fixes in per.items():
            if topic not in merged:
                merged[topic] = []
                seen[topic] = set()
            for fx in fixes:
                if fx in seen[topic]:
                    continue
                seen[topic].add(fx)
                merged[topic].append(fx)
    return merged


def render_master_md(
    latest_refs: Dict[int, ReportRef],
    loaded: List[Tuple[int, Dict[str, Any]]],
    merged_counts: Dict[str, int],
    merged_fixes: Dict[str, List[str]],
) -> str:
    now = datetime.now(timezone.utc).isoformat()

    lines: List[str] = []
    lines.append("# Mega Fix-It Report (Last 48h)")
    lines.append("")
    lines.append(f"Generated: {now}")
    lines.append("")

    lines.append("## Included Chats")
    for chat_id, ref in sorted(latest_refs.items(), key=lambda kv: str(kv[0])):
        label = CHAT_LABELS.get(chat_id, "Unknown chat")
        lines.append(f"- `{chat_id}`: {label} (source: `{ref.md_path}`)")

    lines.append("")
    lines.append("## Merged Topic Counts (All Chats)")
    for topic, count in merged_counts.items():
        lines.append(f"- {topic}: {count}")

    lines.append("")
    lines.append("## Master Fix List (Consolidated)")
    lines.append("")
    lines.append("### P0 (Stop The Bleed)")
    # P0 is opinionated and stable across runs.
    p0 = [
        "Pin valid model IDs and providers per bot (prevent 404/unknown-model crash loops).",
        "Decouple provider keys per bot (Anthropic vs xAI vs NVIDIA vs Google).",
        "Fix restart flapping: healthchecks, watchdog loops, and SIGTERM handling.",
        "Lock identity persistence: `/root/clawd` + `/root/.clawdbot` volume mounts, never ephemeral.",
        "Stabilize KVM8 without wipes: prevent OOM, add swap/caps, and preserve all keys/wallets.",
        "Treasury key recovery: locate + backup the key material on KVM8 before any refactors.",
    ]
    for item in p0:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("### P1 (Make It Autonomous)")
    p1 = [
        "Install and wire MSW (NotebookLM bridge) for grounded answers + follow-up question recursion.",
        "Install/configure Agent TARS (Firefox) as the default UI automation path for OAuth sites.",
        "Make supermemory.ai API the shared long-term memory source of truth (and keep SQLite fallback).",
        "Add fleet-level 'heartbeat' report loop: Telegram status, container health, key error counters.",
    ]
    for item in p1:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("### P2 (Quality + Ops)")
    p2 = [
        "Golden image: one-command spawn for new bots with identity + memory pre-seeded.",
        "Add safe remote actions: recover endpoints, read-only diagnostics, and audited writes.",
        "Tailscale mesh hardening: stable hostnames, ACLs/tags, and documented node map.",
    ]
    for item in p2:
        lines.append(f"- {item}")

    lines.append("")
    lines.append("## Topic-Specific Fix Suggestions (Union of Reports)")
    for topic, fixes in sorted(merged_fixes.items(), key=lambda kv: merged_counts.get(kv[0], 0), reverse=True):
        if not fixes:
            continue
        lines.append(f"### {topic}")
        for fx in fixes:
            lines.append(f"- {fx}")
        lines.append("")

    lines.append("## Per-Chat Summaries (Latest)")
    for chat_id, rep in loaded:
        label = CHAT_LABELS.get(chat_id, "Unknown chat")
        summary = (rep.get("summary") or {})
        lines.append(f"### {label}")
        lines.append(f"- Chat ID: `{chat_id}`")
        lines.append(f"- Total messages scanned: {summary.get('total_messages')}")
        topics = summary.get("topics") or {}
        # show top 6
        top = sorted([(k, int(v)) for k, v in topics.items() if isinstance(v, int) or str(v).isdigit()], key=lambda kv: kv[1], reverse=True)[:6]
        if top:
            lines.append("- Top topics:")
            for k, v in top:
                lines.append(f"- {k}: {v}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", type=str, default="/tmp/telegram_fixit")
    ap.add_argument("--out", type=str, default="reports/telegram_mega_fixit.md")
    args = ap.parse_args()

    in_dir = Path(args.in_dir)
    if not in_dir.exists():
        raise SystemExit(f"Input dir not found: {in_dir}")

    refs = discover_reports(in_dir)
    if not refs:
        raise SystemExit(f"No reports discovered in {in_dir}")

    latest = latest_by_chat(refs)
    loaded: List[Tuple[int, Dict[str, Any]]] = []
    for chat_id, ref in sorted(latest.items(), key=lambda kv: str(kv[0])):
        loaded.append((chat_id, load_json(ref.json_path)))

    merged_counts = merge_topic_counts(loaded)
    merged_fixes = merge_fixes(loaded)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_master_md(latest, loaded, merged_counts, merged_fixes), encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
