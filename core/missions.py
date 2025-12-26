"""
Background mission scheduler for Jarvis.

Runs lightweight missions (research, crawling, interviews) whenever the system
detects the user is idle, and writes findings into context documents.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from core import (
    config,
    context_manager,
    crypto_trading,
    git_ops,
    interview,
    notes_manager,
    providers,
    research_engine,
    state,
    youtube_ingest,
)
from core import memory

ROOT = Path(__file__).resolve().parents[1]
MISSIONS_PATH = ROOT / "data" / "missions"
MISSION_STATE_FILE = MISSIONS_PATH / "mission_state.json"
MISSION_LOG_FILE = MISSIONS_PATH / "mission_log.jsonl"


@dataclass
class Mission:
    mission_id: str
    name: str
    interval_minutes: int
    min_idle_seconds: int
    runner: Callable[[], Optional[Dict[str, str]]]
    last_run: float = 0.0
    tags: List[str] = field(default_factory=list)


def _ensure_storage() -> None:
    MISSIONS_PATH.mkdir(parents=True, exist_ok=True)
    if not MISSION_STATE_FILE.exists():
        MISSION_STATE_FILE.write_text("{}", encoding="utf-8")


def _load_state() -> Dict[str, float]:
    _ensure_storage()
    try:
        return json.loads(MISSION_STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(state_map: Dict[str, float]) -> None:
    _ensure_storage()
    MISSION_STATE_FILE.write_text(json.dumps(state_map, indent=2), encoding="utf-8")


def _log_event(mission_id: str, status: str, payload: Dict[str, str]) -> None:
    _ensure_storage()
    entry = {
        "timestamp": time.time(),
        "mission": mission_id,
        "status": status,
        "payload": payload,
    }
    with MISSION_LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _research_summary(title: str, description: str, findings: List[Dict[str, str]]) -> str:
    if not findings:
        return f"No findings collected for {title}. Observation: {description}"
    lines = [f"Findings for {title}", ""]
    for item in findings:
        lines.append(f"- {item.get('title')}: {item.get('snippet', '')[:200]} ({item.get('url')})")
    return "\n".join(lines)


def _summarize_with_model(topic: str, findings: List[Dict[str, str]], goal: str) -> str:
    if not findings:
        return f"No data available for {topic}. Goal: {goal}"
    prompt = (
        f"You are Jarvis researching {topic} to support the user's autonomy goals.\n"
        f"Goal: {goal}\n"
        "Use the findings below to produce a concise summary with actionable insights:\n"
        f"{json.dumps(findings[:5], indent=2)}\n"
        "Output:\n"
        "1. Executive summary (2 sentences)\n"
        "2. Actionable insights (bullets)\n"
        "3. Follow-up experiments or interviews to schedule\n"
    )
    try:
        response = providers.generate_text(prompt, max_output_tokens=400)
        if response:
            return response.strip()
    except Exception:
        pass
    return _research_summary(topic, goal, findings)


def _run_moondev_watcher() -> Optional[Dict[str, str]]:
    url = "https://x.com/MoonDevOnYT"
    try:
        raw_path, payload = notes_manager.ingest_via_curl(url, label="moondev-x", timeout=20)
    except Exception:
        payload = ""
        raw_path = None
    findings = [
        {
            "title": "MoonDev X feed",
            "snippet": payload[:800],
            "url": url,
        }
    ]
    summary = _summarize_with_model(
        "MoonDevOnYT Feed",
        findings,
        "Track actionable strategy drops or hints from MoonDev's X posts.",
    )
    note_body = f"# MoonDevOnYT Feed Digest\n\nSource: {url}\nRaw capture: {raw_path or 'N/A'}\n\n## Summary\n{summary}\n"
    notes_manager.save_note(
        topic="moondev",
        content=note_body,
        fmt="md",
        tags=["moondev", "x", "research"],
        source="mission.moondev_watcher",
        metadata={"url": url},
    )
    doc = context_manager.add_context_document(
        title="MoonDev X Feed Digest",
        source="MoonDev Watcher",
        category="research",
        summary=summary.splitlines()[0] if summary else "MoonDev social snapshot",
        content=summary,
        tags=["moondev", "social", "research"],
        monetization_angle="Spot HFT and automation cues to test quickly.",
        metadata={"source": url},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_hft_sandbox() -> Optional[Dict[str, str]]:
    trader = crypto_trading.CryptoTrading()
    result = trader.run_hft_sandbox_cycle()
    if not result:
        return None
    strategy = result["strategy"]
    summary = (
        f"{strategy['objective']} on {strategy['chain']} {strategy['pair']} "
        f"PnL {result['pnl']} ({result['roi']*100:.2f}% ROI)"
    )
    doc = context_manager.add_context_document(
        title=f"HFT Sandbox – {strategy['pair']} ({strategy['chain']})",
        source="HFT Sandbox",
        category="research",
        summary=summary,
        content=(
            f"## Strategy\n- Chain: {strategy['chain']}\n- Pair: {strategy['pair']}\n"
            f"- Objective: {strategy['objective']}\n- Liquidity: {strategy['liquidity_source']}\n"
            f"- Capital: ${strategy['entry_capital']}\n\n"
            f"## Simulation Results\n- Trades: {result['trades']}\n"
            f"- Win rate: {result['win_rate']*100:.1f}%\n- PnL: {result['pnl']}\n"
            f"- ROI: {result['roi']*100:.2f}%\n"
        ),
        tags=["crypto", "hft", "sandbox"],
        monetization_angle="Identify low-cap strategies worth live testing.",
    )
    return {"doc_id": doc.doc_id, "summary": summary}


def _run_algotradecamp_digest() -> Optional[Dict[str, str]]:
    url = "https://algotradecamp.com"
    try:
        raw_path, payload = notes_manager.ingest_via_curl(url, label="algotradecamp", timeout=30)
    except Exception:
        payload = ""
        raw_path = None
    findings = [{"title": "AlgoTradeCamp Landing", "snippet": payload[:800], "url": url}]
    summary = _summarize_with_model(
        "AlgoTradeCamp Digest",
        findings,
        "Extract new lessons, toolkits, or calls to action relevant to low-cap HFT.",
    )
    note_body = (
        f"# AlgoTradeCamp Snapshot\n\nSource: {url}\nRaw capture: {raw_path or 'N/A'}\n\n"
        f"## Summary\n{summary}\n"
    )
    notes_manager.save_note(
        topic="algotradecamp",
        content=note_body,
        fmt="md",
        tags=["algotradecamp", "learning", "research"],
        source="mission.algotradecamp",
        metadata={"url": url},
    )
    doc = context_manager.add_context_document(
        title="AlgoTradeCamp Learning Digest",
        source="Learning Mission",
        category="research",
        summary=summary.splitlines()[0] if summary else "AlgoTradeCamp snapshot",
        content=summary,
        tags=["learning", "algo", "research"],
        monetization_angle="Convert lessons into concrete HFT experiments.",
        metadata={"source": url},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_youtube_transcripts() -> Optional[Dict[str, str]]:
    channel_url = "https://www.youtube.com/channel/UCN7D80fY9xMYu5mHhUhXEFw"
    videos = youtube_ingest.list_latest_videos(channel_url, limit=3)
    transcripts: List[Dict[str, str]] = []
    for video in videos:
        data = youtube_ingest.fetch_transcript(video["url"], label=video["id"])
        if not data:
            continue
        snippet = data["transcript"][:1200]
        transcripts.append(
            {
                "title": data["title"],
                "snippet": snippet,
                "url": data["url"],
            }
        )
        notes_manager.save_note(
            topic="moondev_youtube",
            content=f"# {data['title']}\n\nSource: {data['url']}\n\n{data['transcript']}",
            fmt="md",
            tags=["moondev", "youtube", "transcript"],
            source="mission.youtube_transcripts",
            metadata={"video_id": data["video_id"], "raw_path": data.get("raw_path")},
        )
    if not transcripts:
        return None
    summary = _summarize_with_model(
        "MoonDev YouTube Transcripts",
        transcripts,
        "Distill concrete bot ideas and infrastructure notes from MoonDev videos.",
    )
    doc = context_manager.add_context_document(
        title="MoonDev YouTube Transcript Digest",
        source="YouTube Harvester",
        category="research",
        summary=summary.splitlines()[0] if summary else "Video transcript digest",
        content=summary,
        tags=["moondev", "youtube", "research"],
        monetization_angle="Select low-cap HFT strategies to prototype.",
        metadata={"videos": [v["url"] for v in transcripts]},
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_self_improvement() -> Optional[Dict[str, str]]:
    attempts = providers.last_generation_attempts(limit=5)
    provider_errors = providers.last_provider_errors()
    recent_memory = memory.get_recent_entries()[-5:]
    summary_lines = [
        "## Provider Diagnostics",
        json.dumps(provider_errors, indent=2),
        "\n## Recent Attempts",
        json.dumps(attempts, indent=2),
        "\n## Recent Memory Highlights",
    ]
    for entry in recent_memory:
        summary_lines.append(f"- {entry.get('text', '')[:160]}")
    note_body = "\n".join(summary_lines)
    notes_manager.save_note(
        topic="self_improvement",
        content=f"# Self-Improvement Scan\n\n{note_body}",
        fmt="md",
        tags=["self-improvement", "diagnostics"],
        source="mission.self_improvement",
    )
    findings = [
        {
            "title": "Provider error state",
            "snippet": json.dumps(provider_errors),
            "url": "internal://providers",
        }
    ]
    summary = _summarize_with_model(
        "Self-Improvement Audit",
        findings,
        "Decide which capabilities to upgrade next (providers, prompts, data ingestion).",
    )
    doc = context_manager.add_context_document(
        title="Self-Improvement Audit",
        source="Mission Scheduler",
        category="improvement",
        summary=summary.splitlines()[0] if summary else "Self-improvement status",
        content=summary,
        tags=["improvement", "diagnostics"],
        monetization_angle="Prioritize upgrades that unblock revenue-driving tasks.",
    )
    return {"doc_id": doc.doc_id, "summary": doc.summary}


def _run_weekly_interview() -> Optional[Dict[str, str]]:
    questions = interview.generate_smart_questions()
    ctx_summary = context_manager.get_context_summary()
    content = f"## Weekly Interview Questions\n\n{questions}\n\n## Current Context\n\n{ctx_summary}"
    doc = context_manager.add_context_document(
        title="Weekly Interview Prep",
        source="Mission Scheduler",
        category="interview",
        summary="Prepared a new set of interview questions based on recent context.",
        content=content,
        tags=["interview", "self-reflection"],
        monetization_angle="Keep alignment between Jarvis improvements and user goals.",
    )
    return {"doc_id": doc.doc_id, "questions": questions[:120]}


def _default_missions(state_map: Dict[str, float]) -> List[Mission]:
    missions = [
        Mission(
            mission_id="moondev_watcher",
            name="Moondev Watcher",
            interval_minutes=180,
            min_idle_seconds=180,
            runner=_run_moondev_watcher,
            tags=["crypto", "research"],
        ),
        Mission(
            mission_id="algotradecamp_digest",
            name="AlgoTradeCamp Digest",
            interval_minutes=240,
            min_idle_seconds=600,
            runner=_run_algotradecamp_digest,
            tags=["learning", "research"],
        ),
        Mission(
            mission_id="youtube_transcripts",
            name="MoonDev YouTube Transcripts",
            interval_minutes=180,
            min_idle_seconds=600,
            runner=_run_youtube_transcripts,
            tags=["youtube", "moondev"],
        ),
        Mission(
            mission_id="self_improvement",
            name="Self-Improvement Pulse",
            interval_minutes=90,
            min_idle_seconds=600,
            runner=_run_self_improvement,
            tags=["improvement", "diagnostics"],
        ),
        Mission(
            mission_id="hft_sandbox",
            name="HFT Sandbox",
            interval_minutes=180,
            min_idle_seconds=900,
            runner=_run_hft_sandbox,
            tags=["crypto", "automation"],
        ),
        Mission(
            mission_id="weekly_interview",
            name="Weekly Interview Prep",
            interval_minutes=60 * 24 * 3,  # every 3 days
            min_idle_seconds=120,
            runner=_run_weekly_interview,
            tags=["interview", "reflection"],
        ),
    ]
    for mission in missions:
        mission.last_run = float(state_map.get(mission.mission_id, 0.0))
    return missions


class MissionScheduler(threading.Thread):
    def __init__(self, poll_seconds: int = 60, idle_grace_seconds: int = 120) -> None:
        super().__init__(daemon=True)
        self._stop_event = threading.Event()
        self._poll_seconds = poll_seconds
        self._idle_grace_seconds = idle_grace_seconds
        cfg = config.load_config()
        self._mission_cfg = cfg.get("missions", {})
        state_map = _load_state()
        self._missions = _default_missions(state_map)

    def stop(self) -> None:
        self._stop_event.set()

    def _current_idle(self) -> float:
        current = state.read_state()
        return float(current.get("passive_idle_seconds", 0))

    def _should_run(self, mission: Mission) -> bool:

        if time.time() - mission.last_run < mission.interval_minutes * 60:
            return False
        idle_seconds = self._current_idle()
        return idle_seconds >= max(mission.min_idle_seconds, self._idle_grace_seconds)

    def _maybe_auto_commit(self, mission: Mission, payload: Optional[Dict[str, str]]) -> None:
        if not self._mission_cfg.get("auto_commit_enabled", True):
            return
        summary = ""
        if isinstance(payload, dict):
            summary = payload.get("summary") or payload.get("doc_id", "")
        try:
            result = git_ops.auto_commit_with_state(
                task_name=f"mission:{mission.mission_id}",
                summary=summary,
                push_after=bool(self._mission_cfg.get("auto_commit_push", True)),
                throttle_seconds=int(self._mission_cfg.get("auto_commit_min_seconds", 10800)),
            )
            if result.get("status") == "committed":
                _log_event(mission.mission_id, "auto_commit", result)
        except Exception as exc:
            _log_event(mission.mission_id, "auto_commit_error", {"error": str(exc)})

    def _run_mission(self, mission: Mission) -> None:
        try:
            result = mission.runner()
            mission.last_run = time.time()
            _log_event(mission.mission_id, "success", result or {})
            if result:
                self._maybe_auto_commit(mission, result)
        except Exception as exc:
            mission.last_run = time.time()
            _log_event(mission.mission_id, "error", {"error": str(exc)})
        finally:
            state_map = {m.mission_id: m.last_run for m in self._missions}
            _save_state(state_map)

    def run(self) -> None:
        cfg = config.load_config()
        mission_cfg = cfg.get("missions", {})
        if not mission_cfg.get("enabled", True):
            state.update_state(missions_enabled=False)
            return
        state.update_state(missions_enabled=True)
        while not self._stop_event.is_set():
            for mission in self._missions:
                if self._should_run(mission):
                    self._run_mission(mission)
            time.sleep(self._poll_seconds)


_scheduler: Optional[MissionScheduler] = None


def start_scheduler(poll_seconds: int = 60) -> MissionScheduler:
    global _scheduler
    if _scheduler and _scheduler.is_alive():
        return _scheduler
    scheduler = MissionScheduler(poll_seconds=poll_seconds)
    scheduler.start()
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler.join(timeout=5)
        _scheduler = None
